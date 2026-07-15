"""Start, stop, and inspect the installed local gateways."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .installer import STATE_DIRECTORY, load_state
from .system import Runner, executable


RUNTIME_FILENAME = "runtime.json"


def runtime_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / RUNTIME_FILENAME


def status(root: Path) -> Dict[str, object]:
    state = load_state(root)
    component = str(state["component"])
    result: Dict[str, object] = {"root": str(root), "component": component}
    if component in {"oida", "full"}:
        result["oida"] = _http_status("http://127.0.0.1:8765/health")
    if component in {"germ", "full"}:
        result["germ"] = _http_status("http://127.0.0.1:5178/health")
    return result


def start(
    root: Path, target: str = "all", runner: Optional[Runner] = None
) -> Dict[str, object]:
    runner = runner or Runner()
    state = load_state(root)
    component = str(state["component"])
    environment = _environment(state)
    uv = executable("uv") or "uv"
    started: Dict[str, object] = {}
    if target in {"all", "oida"} and component in {"oida", "full"}:
        existing = _http_status("http://127.0.0.1:8765/health")
        if existing.get("running") and _health_name(existing) == "oida":
            existing["reused"] = True
            started["oida"] = existing
        else:
            profile = (
                "mac-mps"
                if any(str(key).startswith("moss-") for key in state.get("models", []))
                else "stub"
            )
            runner.run(
                [uv, "run", "oida", "start", "--profile", profile, "--json"],
                cwd=root / "src" / "oida",
                env=environment,
            )
            started["oida"] = _wait_for("http://127.0.0.1:8765/health", timeout=60)
    if target in {"all", "germ"} and component in {"germ", "full"}:
        existing = _http_status("http://127.0.0.1:5178/health")
        if existing.get("running"):
            started["germ"] = existing
        else:
            log = root / "logs" / "germ.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            merged = os.environ.copy()
            merged.update(environment)
            with log.open("ab", buffering=0) as output:
                process = subprocess.Popen(
                    [
                        uv,
                        "run",
                        "uvicorn",
                        "server.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "5178",
                    ],
                    cwd=str(root / "src" / "germ"),
                    env=merged,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=output,
                    start_new_session=True,
                    close_fds=True,
                )
            _write_runtime(root, {"germ_pid": process.pid, "germ_log": str(log)})
            try:
                started["germ"] = _wait_for("http://127.0.0.1:5178/health", timeout=60)
            except RuntimeError:
                if process.poll() is not None:
                    raise RuntimeError(
                        "GERM exited with status %s; inspect %s"
                        % (process.returncode, log)
                    )
                raise
    return started


def stop(
    root: Path, target: str = "all", runner: Optional[Runner] = None
) -> Dict[str, object]:
    runner = runner or Runner()
    state = load_state(root)
    component = str(state["component"])
    environment = _environment(state)
    uv = executable("uv") or "uv"
    stopped: Dict[str, object] = {}
    if target in {"all", "oida"} and component in {"oida", "full"}:
        runner.run(
            [uv, "run", "oida", "stop", "--json"],
            cwd=root / "src" / "oida",
            env=environment,
            check=False,
        )
        stopped["oida"] = not bool(
            _http_status("http://127.0.0.1:8765/health").get("running")
        )
    if target in {"all", "germ"} and component in {"germ", "full"}:
        runtime = _read_runtime(root)
        pid = int(runtime.get("germ_pid", 0) or 0)
        if not pid:
            stopped["germ"] = False
        elif not _pid_exists(pid):
            stopped["germ"] = True
            _write_runtime(root, {})
        elif not _pid_is_germ(pid):
            raise RuntimeError(
                "Refusing to stop PID %d because it is not the recorded GERM server"
                % pid
            )
        else:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and _pid_exists(pid):
                time.sleep(0.1)
            if _pid_exists(pid):
                os.kill(pid, signal.SIGKILL)
            _write_runtime(root, {})
            stopped["germ"] = True
    return stopped


def _environment(state: Mapping[str, object]) -> Dict[str, str]:
    raw = state.get("environment", {})
    if not isinstance(raw, dict):
        raise ValueError("Installation state contains no valid environment")
    return {str(key): str(value) for key, value in raw.items()}


def _http_status(url: str) -> Dict[str, object]:
    request = Request(url, headers={"User-Agent": "sonicfield-listening-stack/0.1"})
    try:
        with urlopen(request, timeout=2.0) as response:
            data = json.load(response)
        return {"running": True, "url": url.rsplit("/health", 1)[0], "health": data}
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return {
            "running": False,
            "url": url.rsplit("/health", 1)[0],
            "detail": str(exc),
        }


def _wait_for(url: str, timeout: float) -> Dict[str, object]:
    deadline = time.monotonic() + timeout
    last: Dict[str, object] = {}
    while time.monotonic() < deadline:
        last = _http_status(url)
        if last.get("running"):
            return last
        time.sleep(0.25)
    raise RuntimeError(
        "Gateway did not become ready at %s: %s" % (url, last.get("detail", "timeout"))
    )


def _health_name(value: Mapping[str, object]) -> str:
    health = value.get("health")
    if not isinstance(health, dict):
        return ""
    return str(health.get("name", "")).lower()


def _read_runtime(root: Path) -> Dict[str, object]:
    path = runtime_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_runtime(root: Path, value: Mapping[str, object]) -> None:
    path = runtime_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(dict(value), indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _pid_is_germ(pid: int) -> bool:
    try:
        command = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "uvicorn" in command and "server.main:app" in command
