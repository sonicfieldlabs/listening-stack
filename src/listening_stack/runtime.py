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

from . import __version__
from .catalog import normalize_profile, profile_includes
from .installer import STATE_DIRECTORY, load_state
from .system import Runner, executable


RUNTIME_FILENAME = "runtime.json"
MAX_HEALTH_BYTES = 128 * 1024
MAX_RUNTIME_BYTES = 64 * 1024


def runtime_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / RUNTIME_FILENAME


def status(root: Path, target: str = "all") -> Dict[str, object]:
    _validate_target(target)
    state = load_state(root)
    component = normalize_profile(str(state.get("profile") or state["component"]))
    environment = _environment(state)
    result: Dict[str, object] = {"root": str(root), "component": component}
    if target in {"all", "oida"} and profile_includes(component, "oida"):
        result["oida"] = _identified_status(_health_url(environment, "OIDA"), "oida")
    if target in {"all", "germ"} and profile_includes(component, "germ"):
        result["germ"] = _identified_status(_health_url(environment, "GERM"), "germ")
    return result


def start(
    root: Path, target: str = "all", runner: Optional[Runner] = None
) -> Dict[str, object]:
    _validate_target(target)
    runner = runner or Runner()
    state = load_state(root)
    component = normalize_profile(str(state.get("profile") or state["component"]))
    environment = _environment(state)
    uv = executable("uv") or "uv"
    oida_health = _health_url(environment, "OIDA")
    germ_health = _health_url(environment, "GERM")
    started: Dict[str, object] = {}
    if target in {"all", "oida"} and profile_includes(component, "oida"):
        existing = _http_status(oida_health)
        if existing.get("running"):
            _require_identity(existing, "oida")
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
            started["oida"] = _wait_for(
                oida_health, timeout=60, expected_identity="oida"
            )
    if target in {"all", "germ"} and profile_includes(component, "germ"):
        existing = _http_status(germ_health)
        if existing.get("running"):
            _require_identity(existing, "germ")
            existing["reused"] = True
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
                        environment["GERM_HOST"],
                        "--port",
                        environment["GERM_PORT"],
                    ],
                    cwd=str(root / "src" / "germ"),
                    env=merged,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=output,
                    start_new_session=True,
                    close_fds=True,
                )
            runtime = {
                "germ_pid": process.pid,
                "germ_pid_start": _process_start_token(process.pid),
                "germ_log": str(log),
            }
            try:
                _write_runtime(root, runtime)
            except OSError:
                _terminate_process(process)
                raise
            try:
                started["germ"] = _wait_for(
                    germ_health, timeout=60, expected_identity="germ"
                )
            except (Exception, KeyboardInterrupt) as exc:
                returncode = process.poll()
                _terminate_process(process)
                try:
                    _write_runtime(root, {})
                except OSError:
                    pass
                if returncode is not None:
                    raise RuntimeError(
                        "GERM exited with status %s; inspect %s" % (returncode, log)
                    ) from exc
                raise
    return started


def stop(
    root: Path, target: str = "all", runner: Optional[Runner] = None
) -> Dict[str, object]:
    _validate_target(target)
    runner = runner or Runner()
    state = load_state(root)
    component = normalize_profile(str(state.get("profile") or state["component"]))
    environment = _environment(state)
    uv = executable("uv") or "uv"
    oida_health = _health_url(environment, "OIDA")
    stopped: Dict[str, object] = {}
    if target in {"all", "oida"} and profile_includes(component, "oida"):
        runner.run(
            [uv, "run", "oida", "stop", "--json"],
            cwd=root / "src" / "oida",
            env=environment,
            check=False,
        )
        stopped["oida"] = not bool(_http_status(oida_health).get("running"))
    if target in {"all", "germ"} and profile_includes(component, "germ"):
        runtime = _read_runtime(root)
        pid = int(runtime.get("germ_pid", 0) or 0)
        if not pid:
            stopped["germ"] = False
        elif not _pid_exists(pid):
            stopped["germ"] = True
            _write_runtime(root, {})
        elif not _pid_is_germ(pid, str(runtime.get("germ_pid_start", ""))):
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
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and _pid_exists(pid):
                    time.sleep(0.05)
            if _pid_exists(pid):
                raise RuntimeError("GERM process %d did not stop" % pid)
            _write_runtime(root, {})
            stopped["germ"] = True
    return stopped


def _environment(state: Mapping[str, object]) -> Dict[str, str]:
    raw = state.get("environment", {})
    if not isinstance(raw, dict):
        raise ValueError("Installation state contains no valid environment")
    environment = {str(key): str(value) for key, value in raw.items()}
    environment.setdefault("OIDA_HOST", "127.0.0.1")
    environment.setdefault("OIDA_PORT", "8765")
    environment.setdefault("GERM_HOST", "127.0.0.1")
    environment.setdefault("GERM_PORT", "5178")
    for prefix in ("OIDA", "GERM"):
        host_key = "%s_HOST" % prefix
        port_key = "%s_PORT" % prefix
        host = environment.get(host_key, "127.0.0.1").strip().lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                "%s_HOST must remain loopback for Listening Stack lifecycle commands"
                % prefix
            )
        environment[host_key] = host
        environment[port_key] = str(_port(environment, prefix))
    return environment


def _validate_target(target: str) -> None:
    if target not in {"all", "oida", "germ"}:
        raise ValueError("target must be all, oida, or germ")


def _port(environment: Mapping[str, str], prefix: str) -> int:
    key = "%s_PORT" % prefix
    try:
        port = int(environment.get(key, "8765" if prefix == "OIDA" else "5178"))
    except ValueError as exc:
        raise ValueError("%s must be an integer" % key) from exc
    if not 1 <= port <= 65535:
        raise ValueError("%s must be between 1 and 65535" % key)
    return port


def _health_url(environment: Mapping[str, str], prefix: str) -> str:
    host = environment.get("%s_HOST" % prefix, "127.0.0.1")
    url_host = "[%s]" % host if ":" in host else host
    return "http://%s:%d/health" % (url_host, _port(environment, prefix))


def _http_status(url: str) -> Dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "sonicfield-listening-stack/%s" % __version__},
    )
    try:
        with urlopen(request, timeout=2.0) as response:
            raw = response.read(MAX_HEALTH_BYTES + 1)
        if len(raw) > MAX_HEALTH_BYTES:
            raise ValueError("health response is too large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("health response is not an object")
        return {"running": True, "url": url.rsplit("/health", 1)[0], "health": data}
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return {
            "running": False,
            "url": url.rsplit("/health", 1)[0],
            "detail": str(exc),
        }


def _wait_for(
    url: str, timeout: float, expected_identity: str = ""
) -> Dict[str, object]:
    deadline = time.monotonic() + timeout
    last: Dict[str, object] = {}
    while time.monotonic() < deadline:
        last = _http_status(url)
        if last.get("running"):
            if expected_identity:
                _require_identity(last, expected_identity)
            return last
        time.sleep(0.25)
    raise RuntimeError(
        "Gateway did not become ready at %s: %s" % (url, last.get("detail", "timeout"))
    )


def _health_identity(value: Mapping[str, object]) -> str:
    health = value.get("health")
    if not isinstance(health, dict):
        return ""
    return str(health.get("name") or health.get("server") or "").strip().lower()


def _identified_status(url: str, expected: str) -> Dict[str, object]:
    value = _http_status(url)
    if value.get("running") and _health_identity(value) != expected:
        actual = _health_identity(value)
        value["running"] = False
        value["identity_mismatch"] = True
        value["detail"] = "%s identifies %s, not %s" % (
            value.get("url", "the occupied port"),
            actual or "an unknown service",
            expected,
        )
    return value


def _require_identity(value: Mapping[str, object], expected: str) -> None:
    actual = _health_identity(value)
    if actual != expected:
        raise RuntimeError(
            "Refusing to use %s because its health endpoint identifies %s, not %s"
            % (
                value.get("url", "the occupied port"),
                actual or "an unknown service",
                expected,
            )
        )


def _read_runtime(root: Path) -> Dict[str, object]:
    path = runtime_path(root)
    if path.is_symlink():
        return {}
    if not path.is_file():
        return {}
    try:
        if path.stat().st_size > MAX_RUNTIME_BYTES:
            return {}
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


def _terminate_process(process) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _process_start_token(pid: int) -> str:
    try:
        return subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "lstart="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _pid_is_germ(pid: int, expected_start: str = "") -> bool:
    try:
        command = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if "uvicorn" not in command or "server.main:app" not in command:
        return False
    return not expected_start or _process_start_token(pid) == expected_start
