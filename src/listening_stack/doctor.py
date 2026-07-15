"""Read-only installation and host checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Mapping

from .catalog import MODELS, REPOSITORIES, memory_guidance
from .installer import load_state
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
        checks.append(
            Check("state", "pass", str(root / ".listening-stack" / "state.json"))
        )
    except (OSError, ValueError) as exc:
        checks.append(
            Check("state", "fail", str(exc), "Run `listening-stack install`.")
        )
        return _result(checks, {})

    selected = [MODELS[key] for key in state.get("models", []) if key in MODELS]
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
    source_keys = (
        ["germ"] if component == "germ" else ["earworm", "akouo", "akousmata", "oida"]
    )
    if component == "full":
        source_keys.append("germ")
    commits = state.get("commits", {}) if isinstance(state.get("commits"), dict) else {}
    for key in source_keys:
        path = root / "src" / key
        checks.append(_check_repository(path, key, str(commits.get(key, ""))))

    hf_home = root / "models" / "huggingface" / "hub"
    for model in selected:
        if model.application == "oida":
            path = root / "models" / "moss-audio" / model.model_id.rsplit("/", 1)[-1]
            present = (path / "config.json").is_file()
        else:
            cache_name = "models--" + model.model_id.replace("/", "--")
            path = hf_home / cache_name
            present = path.is_dir() and any(path.iterdir())
        checks.append(
            Check(
                "model:%s" % model.key,
                "pass" if present else "warn",
                str(path) if present else "not found at %s" % path,
                "Run the installer again with this model selected."
                if not present
                else "",
            )
        )

    provider = str(state.get("provider", "mock"))
    if provider == "mlx" and not is_apple_silicon():
        checks.append(
            Check("provider", "fail", "MLX selected on a non-Apple-Silicon host")
        )
    elif provider == "python" and not executable("nvidia-smi"):
        checks.append(
            Check(
                "provider",
                "warn",
                "Python provider selected; no NVIDIA utility found. Small models may run on CPU, but Medium expects CUDA upstream.",
            )
        )
    else:
        checks.append(Check("provider", "pass", provider))

    running = runtime_status(root)
    for application in ("oida", "germ"):
        info = running.get(application)
        if isinstance(info, dict):
            checks.append(
                Check(
                    "gateway:%s" % application,
                    "pass" if info.get("running") else "info",
                    "running at %s" % info.get("url")
                    if info.get("running")
                    else "not running",
                    "Run `listening-stack start %s`." % application
                    if not info.get("running")
                    else "",
                )
            )
    return _result(checks, running)


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
    expected_origin = REPOSITORIES[key].url.removesuffix(".git")
    origin_ok = origin.removesuffix(".git") == expected_origin
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
    return Check("repo:%s" % key, "pass", "%s at %s" % (origin, commit[:12]))


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
