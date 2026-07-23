"""Read-only installation and host checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
from typing import Dict, List, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from . import __version__
from .catalog import (
    ACCOUNTABLE_LISTENING_CONTRACTS,
    ALL_REPOSITORIES,
    MODELS,
    REPOSITORIES,
    memory_guidance,
    source_keys,
)
from .installer import _normalise_git_url, environment_path, load_state, state_path
from .runtime import status as runtime_status
from .system import executable, is_apple_silicon, total_ram_gb


@dataclass
class Check:
    name: str
    status: str
    detail: str
    remedy: str = ""


MAX_GATEWAY_CONTRACT_BYTES = 2 * 1024 * 1024
OIDA_SCHEMA_PATHS = {
    "host_perception": "/gateway/schema/host-perception",
    "listening_event": "/gateway/schema/listening-event",
    "listening_context": "/gateway/schema/listening-context",
}


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

    component = str(state.get("component", ""))
    if component in {"oida", "full"}:
        recorded_contracts = state.get("contracts")
        contract_set_matches = (
            isinstance(recorded_contracts, dict)
            and recorded_contracts == dict(ACCOUNTABLE_LISTENING_CONTRACTS)
        )
        checks.append(
            Check(
                "state:contracts",
                "pass" if contract_set_matches else "warn",
                "accountable-listening compatibility set recorded"
                if contract_set_matches
                else "missing or stale accountable-listening compatibility set",
                "Rerun `listening-stack install` with this installer to record the current contracts."
                if not contract_set_matches
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
            if application == "oida" and is_running:
                checks.extend(
                    _check_oida_accountability_contracts(str(info.get("url") or ""))
                )
    return _result(checks, running)


def _check_oida_accountability_contracts(base_url: str) -> List[Check]:
    """Verify the installed listening stack at Oída's live boundary."""
    try:
        manifest = _fetch_local_json(base_url, "/gateway")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return [
            Check(
                "contract:oida-gateway",
                "fail",
                "could not read the live gateway contract: %s" % exc,
                "Restart Oída from this installation and rerun the doctor.",
            )
        ]

    components = manifest.get("components")
    component_contracts = components if isinstance(components, dict) else {}
    actual = {
        "gateway": manifest.get("contract"),
        "akouo": _nested_value(component_contracts, "akouo", "contract"),
        "earworm": _nested_value(component_contracts, "earworm", "contract"),
        "akousmata": _nested_value(component_contracts, "akousmata", "contract"),
    }
    expected = {
        key: ACCOUNTABLE_LISTENING_CONTRACTS[key]
        for key in ("gateway", "akouo", "earworm", "akousmata")
    }
    mismatches = [
        "%s=%s (expected %s)" % (key, actual[key] or "missing", expected[key])
        for key in expected
        if actual[key] != expected[key]
    ]
    expected_version = REPOSITORIES["oida"].version
    if manifest.get("version") != expected_version:
        mismatches.append(
            "oida=%s (expected %s)"
            % (manifest.get("version") or "missing", expected_version)
        )

    advertised = manifest.get("schemas")
    if not isinstance(advertised, dict):
        mismatches.append("schemas=missing")
    else:
        for key, path in OIDA_SCHEMA_PATHS.items():
            if advertised.get(key) != path:
                mismatches.append(
                    "schema.%s=%s (expected %s)"
                    % (key, advertised.get(key) or "missing", path)
                )

    checks = [
        Check(
            "contract:oida-gateway",
            "pass" if not mismatches else "fail",
            "Oída %s exposes %s with AKOÚŌ, Earworm, and Akousmata ownership intact"
            % (expected_version, expected["gateway"])
            if not mismatches
            else "; ".join(mismatches),
            "Rerun the installer and restart Oída to restore the pinned compatibility set."
            if mismatches
            else "",
        )
    ]
    for key, path in OIDA_SCHEMA_PATHS.items():
        expected_contract = ACCOUNTABLE_LISTENING_CONTRACTS[key]
        try:
            schema = _fetch_local_json(base_url, path)
            actual_contract = _nested_value(schema, "properties", "contract", "const")
            matches = actual_contract == expected_contract
            checks.append(
                Check(
                    "schema:%s" % key.replace("_", "-"),
                    "pass" if matches else "fail",
                    "%s at %s" % (actual_contract or "contract missing", path),
                    "Rerun the installer and restart Oída so the live schema matches %s."
                    % expected_contract
                    if not matches
                    else "",
                )
            )
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            checks.append(
                Check(
                    "schema:%s" % key.replace("_", "-"),
                    "fail",
                    "could not read %s: %s" % (path, exc),
                    "Rerun the installer and restart Oída so this schema is available.",
                )
            )
    return checks


def _fetch_local_json(base_url: str, path: str) -> Dict[str, object]:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
    ):
        raise ValueError("gateway URL must be an unauthenticated loopback HTTP URL")
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("gateway path must be absolute")
    url = base_url.rstrip("/") + path
    request = Request(
        url,
        headers={"User-Agent": "sonicfield-listening-stack/%s" % __version__},
    )
    with urlopen(request, timeout=2.0) as response:
        if response.geturl() != url:
            raise ValueError("refusing redirected gateway contract response")
        raw = response.read(MAX_GATEWAY_CONTRACT_BYTES + 1)
    if len(raw) > MAX_GATEWAY_CONTRACT_BYTES:
        raise ValueError("gateway contract response is too large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("gateway contract response is not an object")
    return value


def _nested_value(value: object, *keys: str) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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
