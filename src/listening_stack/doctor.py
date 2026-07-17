"""Read-only installation and host checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
from typing import Dict, List, Mapping

from . import __version__
from .catalog import ALL_REPOSITORIES, MODELS, memory_guidance, source_keys
from .installer import _normalise_git_url, environment_path, load_state, state_path
from .runtime import status as runtime_status
from .system import executable, is_apple_silicon, total_ram_gb


@dataclass
class Check:
    name: str
    status: str
    detail: str
    remedy: str = ""


def run_doctor(root: Path) -> Dict[str, object]:
    checks: List[Check] = []
    for command in ("git", "curl", "uv", "ffmpeg"):
        found = executable(command)
        level = "pass" if found else ("fail" if command in {"git", "uv"} else "warn")
        remedy = "Install %s and rerun the doctor." % command if not found else ""
        checks.append(
            Check("command:%s" % command, level, found or "not found", remedy)
        )

    checks.append(
        Check(
            "python",
            "pass" if sys.version_info >= (3, 9) else "fail",
            platform.python_version(),
        )
    )
    memory = total_ram_gb()
    disk = shutil.disk_usage(str(root.parent if root.parent.exists() else Path.home()))
    checks.append(
        Check(
            "disk",
            "pass" if disk.free >= 5 * 1024**3 else "warn",
            "%.1f GB free near %s" % (disk.free / 1024**3, root),
        )
    )

    try:
        state = load_state(root)
        checks.append(_check_private_file("state", state_path(root)))
    except (OSError, ValueError) as exc:
        checks.append(
            Check("state", "fail", str(exc), "Run `listening-stack install`.")
        )
        return _result(checks, {})

    checks.append(_check_private_file("environment", environment_path(root)))
    recorded_root = str(state.get("root", ""))
    checks.append(
        Check(
            "state:root",
            "pass" if recorded_root == str(root) else "warn",
            recorded_root or "not recorded",
            "Rerun the installer at this root to refresh relocated paths."
            if recorded_root != str(root)
            else "",
        )
    )
    installed_version = str(state.get("installer_version", "unknown"))
    checks.append(
        Check(
            "state:installer",
            "pass" if installed_version == __version__ else "warn",
            "%s (running %s)" % (installed_version, __version__),
            "Rerun `listening-stack install` to apply the current compatibility set."
            if installed_version != __version__
            else "",
        )
    )

    raw_models = state.get("models", [])
    model_keys = (
        [str(key) for key in raw_models] if isinstance(raw_models, list) else []
    )
    unknown_models = [key for key in model_keys if key not in MODELS]
    if unknown_models:
        checks.append(
            Check(
                "models:catalog",
                "warn",
                "unknown recorded models: %s" % ", ".join(unknown_models),
                "Rerun the installer with a current model selection.",
            )
        )
    selected = [MODELS[key] for key in model_keys if key in MODELS]
    single, concurrent = memory_guidance(selected)
    if memory is None:
        checks.append(Check("memory", "warn", "could not determine total RAM"))
    else:
        level = "pass" if memory >= single else "warn"
        checks.append(
            Check(
                "memory",
                level,
                "%.1f GB installed; %d GB suggested for one selected model, %d GB if both apps load models together"
                % (memory, single, concurrent),
            )
        )

    component = str(state.get("component", ""))
    commits = state.get("commits", {}) if isinstance(state.get("commits"), dict) else {}
    for key in source_keys(component):
        path = root / "src" / key
        checks.append(_check_repository(path, key, str(commits.get(key, ""))))
    selected_apps = {model.application for model in selected}
    for key, path in (
        ("moss-audio", root / "vendor" / "MOSS-Audio"),
        ("stable-audio-3", root / "vendor" / "stable-audio-3"),
    ):
        application = "oida" if key == "moss-audio" else "germ"
        if application in selected_apps:
            checks.append(_check_repository(path, key, str(commits.get(key, ""))))

    hf_home = root / "models" / "huggingface" / "hub"
    for model in selected:
        checks.append(_check_model(root, hf_home, model))

    provider = str(state.get("provider", "mock"))
    if provider == "mlx" and not is_apple_silicon():
        checks.append(
            Check("provider", "fail", "MLX selected on a non-Apple-Silicon host")
        )
    elif provider == "mlx":
        binary = root / "vendor" / "stable-audio-3" / "optimized" / "mlx" / "sa3"
        checks.append(
            Check(
                "provider",
                "pass" if binary.is_file() and os.access(binary, os.X_OK) else "fail",
                "MLX executable at %s" % binary
                if binary.is_file() and os.access(binary, os.X_OK)
                else "MLX executable is missing or not executable at %s" % binary,
                "Rerun the installer with the MLX provider."
                if not binary.is_file()
                else "",
            )
        )
    elif provider == "python":
        python = root / "src" / "germ" / ".venv" / "bin" / "python"
        available = _module_available(python, "stable_audio_3")
        checks.append(
            Check(
                "provider",
                "pass" if available else "fail",
                "Stable Audio 3 Python provider is importable"
                if available
                else "stable_audio_3 is not importable from GERM's environment",
                "Rerun the installer with the Python provider."
                if not available
                else "",
            )
        )
        if any(model.key == "stable-medium" for model in selected):
            checks.append(
                Check(
                    "provider:cuda",
                    "pass" if executable("nvidia-smi") else "warn",
                    executable("nvidia-smi")
                    or "Stable Audio 3 Medium is selected but no NVIDIA utility was found",
                    "Use a compatible CUDA host for the Medium checkpoint."
                    if not executable("nvidia-smi")
                    else "",
                )
            )
    elif provider == "mock":
        checks.append(Check("provider", "pass", provider))
    else:
        checks.append(Check("provider", "fail", "unknown provider %s" % provider))

    environment = state.get("environment", {})
    shared_store = (
        str(environment.get("AKOUSMATA_PATH", ""))
        if isinstance(environment, dict)
        else ""
    )
    expected_store = str(root / "data" / "akousmata")
    checks.append(
        Check(
            "data:akousmata",
            "pass" if shared_store == expected_store else "warn",
            shared_store or "shared store is not pinned to the install root",
            "Rerun the installer so Oída and GERM share one bounded Akousmata store."
            if shared_store != expected_store
            else "",
        )
    )
    if component in {"germ", "full"} and isinstance(environment, dict):
        checks.append(_check_germ_boundary(root, environment))

    try:
        running = runtime_status(root)
    except (OSError, ValueError) as exc:
        checks.append(Check("runtime", "fail", str(exc)))
        running = {}
    for application in ("oida", "germ"):
        info = running.get(application)
        if isinstance(info, dict):
            identity_mismatch = bool(info.get("identity_mismatch"))
            is_running = bool(info.get("running"))
            checks.append(
                Check(
                    "gateway:%s" % application,
                    "pass" if is_running else ("fail" if identity_mismatch else "info"),
                    "running at %s" % info.get("url")
                    if is_running
                    else str(info.get("detail") or "not running"),
                    "Run `listening-stack start %s`." % application
                    if not is_running and not identity_mismatch
                    else "",
                )
            )
    return _result(checks, running)


def _check_private_file(name: str, path: Path) -> Check:
    if path.is_symlink():
        return Check(
            name,
            "fail",
            "refusing symlink at %s" % path,
            "Replace it by rerunning the installer at a trusted install root.",
        )
    if not path.is_file():
        return Check(name, "fail", "missing at %s" % path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        return Check(name, "fail", str(exc))
    private = mode & 0o077 == 0
    return Check(
        name,
        "pass" if private else "warn",
        "%s (mode %04o)" % (path, mode),
        "Restrict the file to its owner with `chmod 600`." if not private else "",
    )


def _check_germ_boundary(root: Path, environment: Mapping[str, object]) -> Check:
    expected_inputs = {
        str(root / "data" / "germ"),
        str(root / "data" / "audio"),
        str(root / "data" / "akousmata"),
    }
    expected_models = {
        str(root / "vendor" / "stable-audio-3"),
        str(root / "models"),
        str(root / "data" / "germ"),
    }
    hosts = _comma_values(environment.get("GERM_ALLOWED_HOSTS", ""))
    inputs = _comma_values(environment.get("GERM_ALLOWED_INPUT_ROOTS", ""))
    models = _comma_values(environment.get("GERM_ALLOWED_MODEL_ROOTS", ""))
    cloud_disabled = str(environment.get("GERM_ENABLE_CLOUD_VISION", "")) == "0"
    expected_hosts = {"localhost", "127.0.0.1"}
    bounded = (
        hosts == expected_hosts
        and inputs == expected_inputs
        and models == expected_models
        and cloud_disabled
    )
    return Check(
        "security:germ-boundary",
        "pass" if bounded else "warn",
        "loopback hosts, install-root input/model paths, cloud vision disabled"
        if bounded
        else "GERM's recorded host, path, or cloud boundary differs from the installer default",
        "Review the change or rerun the installer to restore the local-only boundary."
        if not bounded
        else "",
    )


def _comma_values(value: object) -> set[str]:
    return {item.strip() for item in str(value).split(",") if item.strip()}


def _check_model(root: Path, hf_home: Path, model) -> Check:
    if model.application == "oida":
        path = root / "models" / "moss-audio" / model.model_id.rsplit("/", 1)[-1]
        config_present = (path / "config.json").is_file()
        weights_present = _contains_file(path, "*.safetensors")
    else:
        cache_name = "models--" + model.model_id.replace("/", "--")
        path = hf_home / cache_name / "snapshots"
        config_present = _contains_file(path, "model_config.json")
        weights_present = _contains_file(path, "*.safetensors")
    present = config_present and weights_present
    missing = []
    if not config_present:
        missing.append("configuration")
    if not weights_present:
        missing.append("Safetensors weights")
    return Check(
        "model:%s" % model.key,
        "pass" if present else "warn",
        str(path) if present else "%s missing at %s" % (" and ".join(missing), path),
        "Run the installer again with this model selected." if not present else "",
    )


def _contains_file(root: Path, pattern: str) -> bool:
    if not root.is_dir():
        return False
    try:
        return any(path.is_file() for path in root.rglob(pattern))
    except OSError:
        return False


def _module_available(python: Path, module: str) -> bool:
    if not python.is_file() or not os.access(python, os.X_OK):
        return False
    try:
        result = subprocess.run(
            [
                str(python),
                "-c",
                "import importlib.util, sys; sys.exit(importlib.util.find_spec(%r) is None)"
                % module,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _check_repository(path: Path, key: str, expected_commit: str) -> Check:
    if not (path / ".git").is_dir():
        return Check("repo:%s" % key, "fail", "missing at %s" % path)
    try:
        origin = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(path),
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(path),
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return Check("repo:%s" % key, "fail", str(exc))
    spec = ALL_REPOSITORIES[key]
    origin_ok = _normalise_git_url(origin) == _normalise_git_url(spec.url)
    commit_ok = (
        not expected_commit or expected_commit == "planned" or commit == expected_commit
    )
    if not origin_ok:
        return Check("repo:%s" % key, "fail", "unexpected origin %s" % origin)
    if dirty:
        return Check("repo:%s" % key, "warn", "checkout has local changes")
    if not commit_ok:
        return Check(
            "repo:%s" % key, "warn", "commit differs from recorded installation state"
        )
    if spec.revision and commit != spec.revision:
        release = "v%s" % spec.version if spec.version else spec.ref
        return Check(
            "repo:%s" % key,
            "warn",
            "%s at %s; current compatibility set expects %s at %s"
            % (origin, commit[:12], release, spec.revision[:12]),
            "Rerun `listening-stack install` to update the pinned checkout.",
        )
    release = " v%s" % spec.version if spec.version else ""
    return Check(
        "repo:%s" % key,
        "pass",
        "%s%s at %s" % (spec.name, release, commit[:12]),
    )


def _result(checks: List[Check], running: Mapping[str, object]) -> Dict[str, object]:
    counts = {
        level: sum(1 for check in checks if check.status == level)
        for level in ("pass", "info", "warn", "fail")
    }
    return {
        "ok": counts["fail"] == 0,
        "summary": counts,
        "checks": [asdict(check) for check in checks],
        "runtime": dict(running),
    }
