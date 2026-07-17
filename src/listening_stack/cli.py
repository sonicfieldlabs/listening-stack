"""Accessible terminal interface for the Listening Stack assistant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from . import __version__
from .catalog import (
    MODELS,
    MODEL_PRESETS,
    REPOSITORIES,
    Model,
    format_gb,
    memory_guidance,
    planned_disk_gb,
    preset_models,
    refresh_model_sizes,
    selected_models,
    source_keys,
)
from .doctor import run_doctor
from .installer import ALLOWED_INTEGRATIONS, Installer, Selection, load_state
from .runtime import start as start_runtime
from .runtime import status as runtime_status
from .runtime import stop as stop_runtime
from .system import CommandError, Runner, is_apple_silicon, total_ram_gb


DEFAULT_ROOT = Path.home() / "SonicField" / "ListeningStack"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="listening-stack",
        description="Install and operate Oída, GERM, and their local model runtimes.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Run the installation assistant.")
    install.add_argument("--component", choices=["full", "oida", "germ"])
    model_selection = install.add_mutually_exclusive_group()
    model_selection.add_argument(
        "--models",
        help="Preset name or comma-separated model keys. Use `listening-stack models` to inspect choices.",
    )
    model_selection.add_argument(
        "--no-models",
        action="store_true",
        help="Install model-free stub/mock paths only.",
    )
    install.add_argument(
        "--provider", choices=["auto", "mlx", "python", "mock"], default="auto"
    )
    install.add_argument(
        "--integration",
        action="append",
        default=[],
        help="Oída host integration; repeat or use comma-separated names.",
    )
    install.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    install.add_argument("--accept-model-terms", action="store_true")
    install.add_argument("--skip-system-dependencies", action="store_true")
    install.add_argument(
        "--start",
        action="store_true",
        help="Start installed gateways after verification.",
    )
    install.add_argument(
        "--yes",
        action="store_true",
        help="Accept the displayed install plan without prompting.",
    )
    install.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without changing the system.",
    )

    models = subparsers.add_parser(
        "models", help="Show available model choices and planning guidance."
    )
    models.add_argument(
        "--live",
        action="store_true",
        help="Refresh sizes from the official Hugging Face API.",
    )
    models.add_argument("--json", action="store_true")

    doctor = subparsers.add_parser(
        "doctor", help="Check dependencies, sources, models, and gateways."
    )
    doctor.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    doctor.add_argument("--json", action="store_true")

    for name, help_text in (
        ("start", "Start one or both installed gateways."),
        ("stop", "Stop gateways managed by this installation."),
        ("status", "Inspect local gateway status."),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "target", nargs="?", choices=["all", "oida", "germ"], default="all"
        )
        command.add_argument("--root", type=Path, default=DEFAULT_ROOT)
        command.add_argument("--json", action="store_true")

    integrate = subparsers.add_parser(
        "integrate", help="Install Oída adapters for selected agent hosts."
    )
    integrate.add_argument(
        "targets", nargs="+", choices=list(ALLOWED_INTEGRATIONS) + ["all"]
    )
    integrate.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    integrate.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    if not raw_args:
        raw_args = ["install"]
    args = parser.parse_args(raw_args)
    command = args.command
    try:
        if command == "install":
            _install(args)
        elif command == "models":
            _models(args)
        elif command == "doctor":
            _doctor(args)
        elif command == "start":
            _emit(
                start_runtime(args.root.expanduser().resolve(), args.target), args.json
            )
        elif command == "stop":
            _emit(
                stop_runtime(args.root.expanduser().resolve(), args.target), args.json
            )
        elif command == "status":
            _emit(
                runtime_status(args.root.expanduser().resolve(), args.target), args.json
            )
        elif command == "integrate":
            _integrate(args)
        else:
            parser.print_help()
    except (CommandError, FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
        print("\nListening Stack command stopped: %s" % exc, file=sys.stderr)
        raise SystemExit(1)


def _install(args: argparse.Namespace) -> None:
    _banner()
    interactive = not args.yes and sys.stdin.isatty()
    if args.component:
        component = args.component
    elif interactive:
        component = _choose_one(
            "What would you like to install?",
            [
                ("full", "Oída + GERM (recommended)"),
                ("oida", "Oída only"),
                ("germ", "GERM only"),
            ],
            default=1,
        )
    else:
        component = "full"

    if args.no_models:
        model_keys: List[str] = []
    elif args.models:
        model_keys = _parse_models(component, args.models)
    elif interactive:
        model_keys = _interactive_models(component)
    else:
        model_keys = list(preset_models(component, "recommended"))

    models = selected_models(model_keys)
    stable_models = [model for model in models if model.application == "germ"]
    provider = args.provider
    if stable_models and provider == "auto" and interactive:
        if is_apple_silicon():
            provider = _choose_one(
                "Which GERM runtime should be prepared?",
                [
                    ("mlx", "Apple Silicon MLX (recommended)"),
                    ("python", "Python/CUDA provider"),
                ],
                default=1,
            )
        else:
            provider = "python"
            print(
                "\nGERM will use the Python provider. Small models can run on CPU; Medium expects CUDA upstream."
            )

    integrations = _flatten(args.integration)
    if "all" in integrations:
        integrations = list(ALLOWED_INTEGRATIONS)
    if component in {"oida", "full"} and not integrations and interactive:
        integrations = _choose_many(
            "Optional Oída agent integrations (press Enter for none)",
            [
                ("hermes", "Hermes"),
                ("codex", "Codex"),
                ("claude", "Claude"),
                ("openclaw", "OpenClaw"),
                ("opencode", "OpenCode"),
            ],
        )
    invalid_integrations = [
        item for item in integrations if item not in ALLOWED_INTEGRATIONS
    ]
    if invalid_integrations:
        raise ValueError("Unknown integrations: " + ", ".join(invalid_integrations))

    root = args.root.expanduser().resolve()
    if interactive and args.root == DEFAULT_ROOT:
        entered = input("\nInstallation directory [%s]: " % root).strip()
        if entered:
            root = Path(entered).expanduser().resolve()

    refreshed, warnings = (
        refresh_model_sizes(models) if models and not args.dry_run else (models, [])
    )
    _print_plan(
        component,
        refreshed,
        integrations,
        provider,
        root,
        install_system_dependencies=not args.skip_system_dependencies,
    )
    for warning in warnings:
        print("  ! %s" % warning)

    accept_terms = bool(args.accept_model_terms)
    gated = [model for model in models if model.gated]
    if gated and not accept_terms and interactive:
        print("\nStable Audio 3 weight access is gated and separately licensed.")
        print(
            "The installer cannot accept these terms for you. Review each selected page:"
        )
        for model in gated:
            print("  - %s" % model.url)
        accept_terms = _confirm(
            "I have reviewed the applicable terms and want to continue", default=False
        )

    if (
        interactive
        and not args.yes
        and not _confirm("Proceed with this installation", default=True)
    ):
        print("No changes made.")
        return

    selection = Selection(
        component=component,
        model_keys=model_keys,
        integrations=integrations,
        provider=provider,
        root=root,
        accept_model_terms=accept_terms,
        install_system_dependencies=not args.skip_system_dependencies,
        start_after_install=bool(args.start),
    )
    installer = Installer(selection, Runner(dry_run=args.dry_run))
    installer.install()

    if args.dry_run:
        print(
            "\nDry run complete. No files, packages, models, or integrations were changed."
        )
        return
    if selection.start_after_install:
        print("\nStarting installed gateways")
        started = start_runtime(root)
        print(json.dumps(started, indent=2, ensure_ascii=False))
    print("\nListening Stack installation complete.")
    if component in {"oida", "full"}:
        print("  Oída: http://127.0.0.1:8765")
    if component in {"germ", "full"}:
        print("  GERM: http://127.0.0.1:5178/dashboard")
    print("\nNext steps:")
    print("  listening-stack doctor --root %s" % _shell_path(root))
    if not selection.start_after_install:
        print("  listening-stack start --root %s" % _shell_path(root))
    print("  listening-stack status --root %s" % _shell_path(root))
    if any(model.gated for model in models):
        print(
            "  If a gated download was denied, accept access on its model page and rerun this installer."
        )


def _interactive_models(component: str) -> List[str]:
    if component == "oida":
        selection = _choose_one(
            "Which Oída models should be downloaded?",
            [
                ("recommended", "MOSS-Audio 4B Instruct + Thinking (recommended)"),
                ("8b", "MOSS-Audio 8B Instruct + Thinking"),
                ("all", "All four MOSS-Audio checkpoints"),
                ("none", "No model; install Oída's deterministic/stub path"),
                ("custom", "Choose individual checkpoints"),
            ],
            default=1,
        )
    elif component == "germ":
        selection = _choose_one(
            "Which GERM models should be downloaded?",
            [
                ("recommended", "Stable Audio 3 Small SFX + Small Music (recommended)"),
                ("medium", "Stable Audio 3 Medium"),
                ("all", "Small SFX + Small Music + Medium"),
                ("none", "No weights; install GERM's mock path"),
                ("custom", "Choose individual checkpoints"),
            ],
            default=1,
        )
    else:
        selection = _choose_one(
            "Which model set should be downloaded?",
            [
                (
                    "recommended",
                    "MOSS-Audio 4B pair + Stable Audio 3 Small pair (recommended)",
                ),
                ("all", "All listed MOSS-Audio and Stable Audio 3 checkpoints"),
                ("none", "No models; install both model-free paths"),
                ("custom", "Choose individual checkpoints"),
            ],
            default=1,
        )
    if selection != "custom":
        return list(preset_models(component, selection))
    allowed = [
        model
        for model in MODELS.values()
        if component == "full" or model.application == component
    ]
    return _choose_many(
        "Choose checkpoints",
        [
            (model.key, "%s — %s" % (model.label, format_gb(model.size_bytes)))
            for model in allowed
        ],
    )


def _parse_models(component: str, raw: str) -> List[str]:
    value = raw.strip().lower()
    if value in MODEL_PRESETS[component]:
        return list(preset_models(component, value))
    keys = list(
        dict.fromkeys(part.strip().lower() for part in raw.split(",") if part.strip())
    )
    selected_models(keys)
    return keys


def _print_plan(
    component: str,
    models: Sequence[Model],
    integrations: Sequence[str],
    provider: str,
    root: Path,
    install_system_dependencies: bool,
) -> None:
    print("\nInstall plan")
    print(
        "  Applications: %s"
        % {"full": "Oída + GERM", "oida": "Oída", "germ": "GERM"}[component]
    )
    print("  Directory:    %s" % root)
    print("  Sources:")
    for key in source_keys(component):
        repository = REPOSITORIES[key]
        release = "v%s" % repository.version if repository.version else repository.ref
        print("    - %s %s (%s)" % (repository.name, release, repository.revision[:12]))
    if models:
        print("  Models:")
        for model in models:
            gate = "; gated" if model.gated else ""
            print("    - %s (%s%s)" % (model.label, format_gb(model.size_bytes), gate))
    else:
        print("  Models:       none; deterministic stub/mock paths only")
    if any(model.application == "germ" for model in models):
        resolved = provider
        if provider == "auto":
            resolved = "mlx" if is_apple_silicon() else "python"
        print("  GERM runtime: %s" % resolved)
    print("  Integrations: %s" % (", ".join(integrations) if integrations else "none"))
    print(
        "  System tools: %s"
        % (
            "install missing uv/ffmpeg when supported"
            if install_system_dependencies
            else "must already be provisioned"
        )
    )
    print(
        "  Disk plan:    about %.1f GB including model-download headroom and environments"
        % planned_disk_gb(component, models)
    )
    single, concurrent = memory_guidance(models)
    print("  Memory guide: %d GB suggested for one selected model" % single)
    if component == "full" and models:
        print(
            "                %d GB if Oída and GERM load their largest selected models together"
            % concurrent
        )
    available_ram = total_ram_gb()
    if available_ram is not None and available_ram < single:
        print(
            "  ! This machine reports %.1f GB RAM, below the one-model planning guide."
            % available_ram
        )
    try:
        free = (
            shutil.disk_usage(
                str(root.parent if root.parent.exists() else Path.home())
            ).free
            / 1_000_000_000
        )
        if free < planned_disk_gb(component, models):
            print(
                "  ! Only %.1f GB appears free near the installation directory." % free
            )
    except OSError:
        pass
    if integrations:
        print(
            "  Note: selected integrations write host config/skill files and preserve backups where supported."
        )


def _models(args: argparse.Namespace) -> None:
    models = list(MODELS.values())
    warnings: List[str] = []
    if args.live:
        models, warnings = refresh_model_sizes(models)
    if args.json:
        payload = [
            {
                "key": model.key,
                "label": model.label,
                "model_id": model.model_id,
                "application": model.application,
                "size_bytes": model.size_bytes,
                "minimum_ram_gb": model.minimum_ram_gb,
                "recommended_ram_gb": model.recommended_ram_gb,
                "license": model.license_label,
                "gated": model.gated,
                "url": model.url,
                "download_revision": model.download_revision or None,
            }
            for model in models
        ]
        print(json.dumps({"models": payload, "warnings": warnings}, indent=2))
        return
    print("Model catalog\n")
    for model in models:
        access = "gated terms" if model.gated else "public download"
        print("%s  %s" % (model.key, model.label))
        print(
            "  %s · %s · %s"
            % (format_gb(model.size_bytes), access, model.license_label)
        )
        print(
            "  RAM guide: %d GB minimum / %d GB suggested"
            % (model.minimum_ram_gb, model.recommended_ram_gb)
        )
        print("  %s" % model.url)
    for warning in warnings:
        print("\n! %s" % warning)
    print(
        "\nRAM figures are installer planning guidance. Storage is additive; RAM is not unless models run concurrently."
    )


def _doctor(args: argparse.Namespace) -> None:
    result = run_doctor(args.root.expanduser().resolve())
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["ok"]:
            raise SystemExit(1)
        return
    symbols = {"pass": "✓", "info": "·", "warn": "!", "fail": "×"}
    for check in result["checks"]:
        print(
            "%s %-24s %s"
            % (symbols.get(check["status"], "?"), check["name"], check["detail"])
        )
        if check.get("remedy"):
            print("  %s" % check["remedy"])
    summary = result["summary"]
    print(
        "\n%d passed, %d warnings, %d failures"
        % (summary["pass"], summary["warn"], summary["fail"])
    )
    if not result["ok"]:
        raise SystemExit(1)


def _integrate(args: argparse.Namespace) -> None:
    root = args.root.expanduser().resolve()
    state = load_state(root)
    if state.get("component") == "germ":
        raise ValueError("This installation does not include Oída")
    targets = (
        list(ALLOWED_INTEGRATIONS)
        if "all" in args.targets
        else list(dict.fromkeys(args.targets))
    )
    environment = {
        str(key): str(value) for key, value in dict(state["environment"]).items()
    }
    runner = Runner(dry_run=args.dry_run)
    uv = shutil.which("uv") or "uv"
    for target in targets:
        runner.run(
            [uv, "run", "oida", "integrate", target, "--json"],
            cwd=root / "src" / "oida",
            env=environment,
        )


def _choose_one(prompt: str, options: Sequence[Tuple[str, str]], default: int) -> str:
    print("\n%s" % prompt)
    for index, (_, label) in enumerate(options, start=1):
        suffix = " [default]" if index == default else ""
        print("  %d) %s%s" % (index, label, suffix))
    while True:
        raw = input("Choice [%d]: " % default).strip()
        if not raw:
            return options[default - 1][0]
        try:
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1][0]
        except ValueError:
            pass
        print("Enter a number from 1 to %d." % len(options))


def _choose_many(prompt: str, options: Sequence[Tuple[str, str]]) -> List[str]:
    print("\n%s" % prompt)
    for index, (_, label) in enumerate(options, start=1):
        print("  %d) %s" % (index, label))
    while True:
        raw = input("Choices (comma-separated, Enter for none): ").strip()
        if not raw:
            return []
        try:
            indexes = [int(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError:
            print("Use comma-separated numbers, for example: 1,3")
            continue
        if indexes and all(1 <= index <= len(options) for index in indexes):
            return list(dict.fromkeys(options[index - 1][0] for index in indexes))
        print("Every choice must be between 1 and %d." % len(options))


def _confirm(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input("%s [%s]: " % (prompt, suffix)).strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Enter yes or no.")


def _flatten(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        result.extend(part.strip().lower() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(result))


def _emit(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return
    if not isinstance(value, Mapping):
        print(value)
        return
    for key, item in value.items():
        if isinstance(item, (dict, list)):
            print("%s: %s" % (key, json.dumps(item, ensure_ascii=False)))
        else:
            print("%s: %s" % (key, item))


def _banner() -> None:
    print("The Listening Stack")
    print(
        "Oída hears. GERM cultivates. Akousmata remembers. AKOÚŌ structures. Earworm routes."
    )
    print(
        "\nThis assistant installs local public-alpha software. It will show every model, license boundary, and host change before proceeding."
    )


def _shell_path(path: Path) -> str:
    value = str(path)
    return (
        "'%s'" % value.replace("'", "'\\''")
        if any(char.isspace() for char in value)
        else value
    )


if __name__ == "__main__":
    main()
