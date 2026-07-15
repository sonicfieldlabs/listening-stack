"""Installation orchestration for Oída, GERM, and their selected models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import sys
from typing import Dict, List, Mapping, Sequence, Tuple

from .catalog import (
    GERM_SOURCE_KEYS,
    MODELS,
    MOSS_AUDIO_REPOSITORY,
    OIDA_SOURCE_KEYS,
    REPOSITORIES,
    STABLE_AUDIO_REPOSITORY,
    Model,
    Repository,
)
from .system import Runner, executable, is_apple_silicon


STATE_DIRECTORY = ".listening-stack"
STATE_FILENAME = "state.json"
ENV_FILENAME = "stack.env"
ALLOWED_INTEGRATIONS = ("hermes", "codex", "claude", "openclaw", "opencode")


@dataclass
class Selection:
    component: str
    model_keys: List[str]
    integrations: List[str]
    provider: str
    root: Path
    accept_model_terms: bool = False
    install_system_dependencies: bool = True
    start_after_install: bool = False


def state_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / STATE_FILENAME


def environment_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / ENV_FILENAME


def load_state(root: Path) -> Dict[str, object]:
    path = state_path(root)
    if not path.is_file():
        raise FileNotFoundError(
            "No Listening Stack installation state exists at %s" % path
        )
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Unsupported or invalid Listening Stack state at %s" % path)
    return value


class Installer:
    def __init__(self, selection: Selection, runner: Runner) -> None:
        self.selection = selection
        self.runner = runner
        self.root = selection.root.expanduser().resolve()
        self.src_root = self.root / "src"
        self.vendor_root = self.root / "vendor"
        self.models_root = self.root / "models"
        self.hf_home = self.models_root / "huggingface"
        self.commits: Dict[str, str] = {}
        self.uv = executable("uv") or "uv"
        self.hf = executable("hf") or "hf"

    @property
    def models(self) -> List[Model]:
        return [MODELS[key] for key in self.selection.model_keys]

    def install(self) -> Dict[str, object]:
        self._validate_selection()
        self._heading("Preparing installation root")
        self._make_directories()

        self._heading("Checking system dependencies")
        self._ensure_base_tools()
        self._ensure_uv()
        self._ensure_python()
        self._ensure_ffmpeg()

        self._heading("Installing Sonic Field sources")
        self._install_sources()

        if any(model.application == "oida" for model in self.models):
            self._heading("Preparing the MOSS-Audio runtime")
            self._install_upstream(
                MOSS_AUDIO_REPOSITORY, self.vendor_root / "MOSS-Audio"
            )

        if any(model.application == "germ" for model in self.models):
            self._heading("Preparing the Stable Audio 3 runtime")
            self._install_upstream(
                STABLE_AUDIO_REPOSITORY, self.vendor_root / "stable-audio-3"
            )

        self._heading("Creating application environments")
        self._sync_applications()

        if self.models:
            self._heading("Downloading selected models")
            self._ensure_hf()
            self._download_models()

        environment = self._environment()
        self._heading("Writing local configuration")
        self._write_environment(environment)
        state = self._write_state(environment)

        if self.selection.integrations:
            self._heading("Installing selected agent integrations")
            self._install_integrations(environment)

        self._heading("Verifying application imports")
        self._verify_installation(environment)
        return state

    def _validate_selection(self) -> None:
        if self.selection.component not in {"oida", "germ", "full"}:
            raise ValueError("component must be oida, germ, or full")
        if self.selection.provider not in {"auto", "mlx", "python", "mock"}:
            raise ValueError("provider must be auto, mlx, python, or mock")
        unknown = [key for key in self.selection.model_keys if key not in MODELS]
        if unknown:
            raise ValueError("Unknown models: " + ", ".join(unknown))
        allowed_apps = (
            {"oida", "germ"}
            if self.selection.component == "full"
            else {self.selection.component}
        )
        wrong = [
            model.key for model in self.models if model.application not in allowed_apps
        ]
        if wrong:
            raise ValueError(
                "Models do not match the selected component: " + ", ".join(wrong)
            )
        invalid_integrations = [
            item
            for item in self.selection.integrations
            if item not in ALLOWED_INTEGRATIONS
        ]
        if invalid_integrations:
            raise ValueError("Unknown integrations: " + ", ".join(invalid_integrations))
        if self.selection.integrations and self.selection.component == "germ":
            raise ValueError(
                "Agent integrations are supplied by Oída; install Oída or the full stack first"
            )
        if (
            any(model.gated for model in self.models)
            and not self.selection.accept_model_terms
        ):
            raise ValueError(
                "Stable Audio 3 weights are gated. Review their model pages and pass "
                "--accept-model-terms, or rerun interactively. The installer cannot accept terms for you."
            )
        if (
            any(model.application == "germ" for model in self.models)
            and self.selection.provider == "mlx"
            and not is_apple_silicon()
        ):
            raise ValueError(
                "The Stable Audio 3 MLX provider requires Apple Silicon macOS"
            )
        if (
            any(model.application == "germ" for model in self.models)
            and self.selection.provider == "mock"
        ):
            raise ValueError(
                "Select the MLX or Python provider when downloading Stable Audio 3 models"
            )

    def _make_directories(self) -> None:
        for path in (
            self.src_root,
            self.vendor_root,
            self.models_root,
            self.hf_home,
            self.root / "data" / "oida",
            self.root / "data" / "germ",
            self.root / "logs",
            self.root / "run",
            self.root / STATE_DIRECTORY,
        ):
            self.runner.note("  create %s" % path)
            if not self.runner.dry_run:
                path.mkdir(parents=True, exist_ok=True)

    def _ensure_base_tools(self) -> None:
        missing = [name for name in ("git", "curl") if not executable(name)]
        if missing:
            raise RuntimeError(
                "Missing required command(s): %s. Install them with your operating system package manager and rerun."
                % ", ".join(missing)
            )
        self.runner.note("  ✓ git")
        self.runner.note("  ✓ curl")
        self.runner.note("  ✓ Python %s" % platform.python_version())
        if sys.version_info < (3, 9):
            raise RuntimeError(
                "The installation assistant requires Python 3.9 or newer"
            )
        if sys.platform == "darwin" and not self.runner.dry_run:
            result = self.runner.capture(["xcode-select", "-p"], check=False)
            if not result:
                self.runner.note(
                    "  ! Xcode command-line tools are missing. Run: xcode-select --install"
                )

    def _ensure_uv(self) -> None:
        found = executable("uv")
        if found:
            self.uv = found
            self.runner.note("  ✓ uv at %s" % found)
            return
        if not self.selection.install_system_dependencies:
            raise RuntimeError(
                "uv is required. Install it from https://docs.astral.sh/uv/ and rerun."
            )
        self.runner.note(
            "  uv is missing; installing it with Astral's official installer."
        )
        script = self.root / STATE_DIRECTORY / "uv-install.sh"
        self.runner.run(
            [
                executable("curl") or "curl",
                "--proto",
                "=https",
                "--tlsv1.2",
                "-LsSf",
                "https://astral.sh/uv/install.sh",
                "-o",
                str(script),
            ]
        )
        self.runner.run(["sh", str(script)])
        if not self.runner.dry_run:
            script.unlink(missing_ok=True)
            found = executable("uv")
            if not found:
                raise RuntimeError(
                    "uv installation completed but the executable could not be found"
                )
            self.uv = found

    def _ensure_python(self) -> None:
        self.runner.run([self.uv, "python", "install", "3.12"])

    def _ensure_ffmpeg(self) -> None:
        if executable("ffmpeg"):
            self.runner.note("  ✓ ffmpeg")
            return
        if not self.selection.install_system_dependencies:
            self.runner.note("  ! ffmpeg is missing; audio decoding may be incomplete.")
            return
        if executable("brew"):
            self.runner.note("  Installing ffmpeg with Homebrew.")
            self.runner.run([executable("brew") or "brew", "install", "ffmpeg"])
            return
        if executable("apt-get"):
            self.runner.note("  Installing ffmpeg with apt.")
            prefix = [] if os.geteuid() == 0 else ["sudo"]
            self.runner.run(prefix + ["apt-get", "update"])
            self.runner.run(prefix + ["apt-get", "install", "-y", "ffmpeg"])
            return
        if executable("dnf"):
            prefix = [] if os.geteuid() == 0 else ["sudo"]
            self.runner.run(prefix + ["dnf", "install", "-y", "ffmpeg"])
            return
        self.runner.note(
            "  ! ffmpeg is missing and no supported package manager was found."
        )
        self.runner.note("    Install ffmpeg before using model-backed audio decoding.")

    def _source_keys(self) -> Tuple[str, ...]:
        if self.selection.component == "oida":
            return OIDA_SOURCE_KEYS
        if self.selection.component == "germ":
            return GERM_SOURCE_KEYS
        return OIDA_SOURCE_KEYS + GERM_SOURCE_KEYS

    def _install_sources(self) -> None:
        for key in self._source_keys():
            spec = REPOSITORIES[key]
            self.commits[key] = self._install_repository(spec, self.src_root / key)

    def _install_upstream(self, spec: Repository, destination: Path) -> None:
        self.commits[spec.key] = self._install_repository(spec, destination)

    def _install_repository(self, spec: Repository, destination: Path) -> str:
        if destination.exists() and not (destination / ".git").is_dir():
            raise RuntimeError(
                "Refusing to replace non-Git directory: %s" % destination
            )
        if (destination / ".git").is_dir():
            origin = self.runner.capture(
                ["git", "remote", "get-url", "origin"], cwd=destination
            )
            if _normalise_git_url(origin) != _normalise_git_url(spec.url):
                raise RuntimeError(
                    "%s has unexpected origin %s; expected %s"
                    % (destination, origin, spec.url)
                )
            dirty = self.runner.capture(
                ["git", "status", "--porcelain"], cwd=destination
            )
            if dirty:
                raise RuntimeError(
                    "Refusing to update dirty installation checkout: %s" % destination
                )
            self.runner.run(
                ["git", "fetch", "--depth", "1", "origin", spec.branch], cwd=destination
            )
            self.runner.run(
                ["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination
            )
        else:
            self.runner.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    spec.branch,
                    spec.url,
                    str(destination),
                ]
            )
        commit = self.runner.capture(["git", "rev-parse", "HEAD"], cwd=destination)
        self.runner.note(
            "  ✓ %s %s" % (spec.name, commit[:12] if commit else "planned")
        )
        return commit or "planned"

    def _sync_applications(self) -> None:
        model_apps = {model.application for model in self.models}
        if self.selection.component in {"oida", "full"}:
            command = [self.uv, "sync", "--locked", "--python", "3.12"]
            if "oida" in model_apps:
                command.extend(["--extra", "moss"])
            self.runner.run(command, cwd=self.src_root / "oida")
        if self.selection.component in {"germ", "full"}:
            command = [self.uv, "sync", "--locked", "--python", "3.12"]
            provider = self._resolved_provider()
            if "germ" in model_apps and provider == "python":
                command.extend(["--extra", "python-provider"])
            self.runner.run(command, cwd=self.src_root / "germ")
            if "germ" in model_apps and provider == "python":
                self.runner.run(
                    [
                        self.uv,
                        "sync",
                        "--locked",
                        "--python",
                        "3.12",
                        "--extra",
                        "ui",
                        "--extra",
                        "lora",
                    ],
                    cwd=self.vendor_root / "stable-audio-3",
                )
            elif "germ" in model_apps and provider == "mlx":
                self.runner.run(
                    ["./install.sh"],
                    cwd=self.vendor_root / "stable-audio-3" / "optimized" / "mlx",
                )

    def _ensure_hf(self) -> None:
        found = executable("hf")
        if found:
            self.hf = found
            self.runner.note("  ✓ Hugging Face CLI at %s" % found)
            return
        self.runner.run([self.uv, "tool", "install", "huggingface_hub"])
        if not self.runner.dry_run:
            found = executable("hf")
            if not found:
                raise RuntimeError(
                    "Hugging Face CLI installation completed but `hf` could not be found"
                )
            self.hf = found

    def _download_models(self) -> None:
        environment = {"HF_HOME": str(self.hf_home)}
        gated = [model for model in self.models if model.gated]
        if gated:
            status = self.runner.capture(
                [self.hf, "auth", "whoami"], env=environment, check=False
            )
            if not status and not self.runner.dry_run:
                print(
                    "\nStable Audio 3 access requires a Hugging Face account that has accepted each selected model's terms."
                )
                for model in gated:
                    print("  - %s" % model.url)
                self.runner.run([self.hf, "auth", "login"], env=environment)
        for model in self.models:
            command = [self.hf, "download", model.model_id]
            if model.application == "oida":
                command.extend(["--local-dir", str(self._moss_model_path(model))])
            self.runner.run(command, env=environment)

    def _moss_model_path(self, model: Model) -> Path:
        return self.models_root / "moss-audio" / model.model_id.rsplit("/", 1)[-1]

    def _resolved_provider(self) -> str:
        if not any(model.application == "germ" for model in self.models):
            return "mock"
        if self.selection.provider != "auto":
            return self.selection.provider
        return "mlx" if is_apple_silicon() else "python"

    def _environment(self) -> Dict[str, str]:
        environment: Dict[str, str] = {
            "HF_HOME": str(self.hf_home),
            "OIDA_DATA_DIR": str(self.root / "data" / "oida"),
            "OIDA_AUDIO_DIR": str(self.root / "data" / "audio"),
            "OIDA_HOST": "127.0.0.1",
            "OIDA_PORT": "8765",
            "GERM_HOST": "127.0.0.1",
            "GERM_PORT": "5178",
            "GERM_OUTPUT_DIR": str(self.root / "data" / "germ"),
            "GERM_OIDA_URL": "http://127.0.0.1:8765",
            "GERM_OFFICIAL_REPO_DIR": str(self.vendor_root / "stable-audio-3"),
            "GERM_MLX_REPO_DIR": str(self.vendor_root / "stable-audio-3"),
        }
        moss = [model for model in self.models if model.application == "oida"]
        if moss:
            instruct = _preferred_moss(moss, "instruct")
            thinking = _preferred_moss(moss, "thinking")
            environment.update(
                {
                    "OIDA_ENGINE_PROFILE": "mac-mps",
                    "OIDA_MOSS_AUDIO_REPO": str(self.vendor_root / "MOSS-Audio"),
                    "OIDA_MOSS_INSTRUCT_MODEL": str(self._moss_model_path(instruct)),
                    "OIDA_MOSS_THINKING_MODEL": str(self._moss_model_path(thinking)),
                    "OIDA_REQUIRE_MODEL": "1",
                    "OIDA_MOSS_PREWARM": "0",
                }
            )
        else:
            environment.update(
                {"OIDA_ENGINE_PROFILE": "stub", "OIDA_REQUIRE_MODEL": "0"}
            )
        stable = [model for model in self.models if model.application == "germ"]
        provider = self._resolved_provider()
        environment["GERM_ACTIVE_PROVIDER"] = {
            "mlx": "stable_audio_mlx",
            "python": "stable_audio_python",
            "mock": "mock",
        }.get(provider, "mock")
        environment["GERM_DEFAULT_MODEL"] = _preferred_stable_model(stable)
        return environment

    def _write_environment(self, environment: Mapping[str, str]) -> None:
        path = environment_path(self.root)
        lines = [
            "# Generated by the Listening Stack installer. Contains paths and settings, never tokens."
        ]
        for key in sorted(environment):
            lines.append("%s=%s" % (key, shlex.quote(environment[key])))
        self.runner.note("  write %s" % path)
        if not self.runner.dry_run:
            _atomic_write(path, "\n".join(lines) + "\n", mode=0o600)

    def _write_state(self, environment: Mapping[str, str]) -> Dict[str, object]:
        state: Dict[str, object] = {
            "schema_version": 1,
            "installer_version": "0.1.0",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "component": self.selection.component,
            "models": list(self.selection.model_keys),
            "provider": self._resolved_provider(),
            "integrations": list(self.selection.integrations),
            "commits": dict(self.commits),
            "environment": dict(environment),
        }
        path = state_path(self.root)
        self.runner.note("  write %s" % path)
        if not self.runner.dry_run:
            _atomic_write(
                path, json.dumps(state, indent=2, sort_keys=True) + "\n", mode=0o600
            )
        return state

    def _install_integrations(self, environment: Mapping[str, str]) -> None:
        oida = self.src_root / "oida"
        for integration in self.selection.integrations:
            self.runner.run(
                [self.uv, "run", "oida", "integrate", integration, "--json"],
                cwd=oida,
                env=environment,
            )

    def _verify_installation(self, environment: Mapping[str, str]) -> None:
        if self.selection.component in {"oida", "full"}:
            self.runner.run(
                [
                    self.uv,
                    "run",
                    "python",
                    "-c",
                    "import oida; print('Oída import: ok')",
                ],
                cwd=self.src_root / "oida",
                env=environment,
            )
        if self.selection.component in {"germ", "full"}:
            self.runner.run(
                [
                    self.uv,
                    "run",
                    "python",
                    "-c",
                    "from server.main import app; print('GERM import: ' + app.title)",
                ],
                cwd=self.src_root / "germ",
                env=environment,
            )

    def _heading(self, title: str) -> None:
        print("\n%s" % title)


def _preferred_moss(models: Sequence[Model], kind: str) -> Model:
    candidates = [model for model in models if kind in model.key]
    if not candidates:
        # One selected MOSS checkpoint can serve both Oída routes.
        candidates = list(models)
    return sorted(candidates, key=lambda model: (model.size_bytes, model.key))[0]


def _preferred_stable_model(models: Sequence[Model]) -> str:
    if not models:
        return "mock-sine"
    preference = ("stable-small-sfx", "stable-small-music", "stable-medium")
    by_key = {model.key: model for model in models}
    selected = next((by_key[key] for key in preference if key in by_key), models[0])
    return selected.model_id.rsplit("stable-audio-3-", 1)[-1]


def _normalise_git_url(value: str) -> str:
    cleaned = value.strip().removesuffix(".git").rstrip("/")
    if cleaned.startswith("git@github.com:"):
        cleaned = "https://github.com/" + cleaned.split(":", 1)[1]
    return cleaned.lower()


def _atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, mode)
    temporary.replace(path)
