"""Two isolated installed-Central starts, HTTP identity/static checks and shutdown.

Run with candidate Python -I. No owners, workspace, intake or store is connected.
This is service-process qualification, not listening or full-route acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.flags.isolated or args.output.exists() or not args.output.is_absolute():
        parser.error("Candidate Python -I and fresh absolute output required")
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("published") is not False:
        raise ValueError("Unpublished candidate required")
    rows = [w for w in manifest["wheels"] if w["distribution"] in {"listeningstackweb", "sonicfield-telar"}]
    if len(rows) != 1:
        raise ValueError("Exactly one Central or Telar wheel required")
    row = rows[0]
    package = "telar" if row["distribution"] == "sonicfield-telar" else "listeningstackweb"
    module = importlib.import_module(package)
    snapshot = importlib.import_module(package + ".runtime_identity").snapshot
    root = Path(module.__file__).resolve().parent
    if not root.is_relative_to(Path(sys.prefix).resolve()) or "site-packages" not in root.parts:
        raise ValueError("Installed Central required")
    wheel = args.manifest.parent / row["file"]
    if sha(wheel.read_bytes()) != row["sha256"]:
        raise ValueError("Wheel identity changed")
    with zipfile.ZipFile(wheel) as archive:
        resources = {name.removeprefix(package + "/"): archive.read(name)
                     for name in archive.namelist() if name.startswith(package + "/") and not name.endswith("/")}
    if not resources:
        raise ValueError("Application resource inventory is empty")

    def verify_installed():
        for name, data in resources.items():
            if (root / name).read_bytes() != data:
                raise ValueError("Installed resource changed: " + name)

    verify_installed()
    expected_identity = snapshot()
    args.output.mkdir(mode=0o700)
    (args.output / "private-home").mkdir(mode=0o700)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "en_US.UTF-8",
                   "HOME": str(args.output / "private-home"), "PYTHONUNBUFFERED": "1",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OIDA_MOSS_BACKUP_MODEL": ""}
    report = {"status": "running", "scope": "installed disconnected Central HTTP process, not owner execution or model inference",
              "manifest_sha256": sha(manifest_bytes), "central_wheel_sha256": row["sha256"],
              "runner_sha256": sha(Path(__file__).read_bytes()), "starts": [], "paid_calls": False}
    try:
        for cycle in range(2):
            record = {"cycle": cycle, "checks": []}
            report["starts"].append(record)
            log_path = args.output / f"central-{cycle}.log"
            with log_path.open("x") as log:
                child = subprocess.Popen([sys.executable, "-I", "-m", package + ".server", "--port", "0"],
                                         cwd=args.output, env=environment, stdout=log, stderr=subprocess.STDOUT)
                record["pid"] = child.pid
                try:
                    deadline = time.monotonic() + 30
                    match = None
                    while time.monotonic() < deadline:
                        if child.poll() is not None:
                            raise RuntimeError("Central exited before readiness")
                        match = re.search(r"Uvicorn running on http://127\.0\.0\.1:(\d+)", log_path.read_text())
                        if match:
                            break
                        time.sleep(0.1)
                    if not match:
                        raise TimeoutError("Central startup timeout")
                    port = int(match.group(1))
                    record["port"] = port

                    def request(route, status, expected=None, host=None):
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                        try:
                            connection.request("GET", route, headers={"Host": host} if host else {})
                            response = connection.getresponse()
                            body = response.read(4 * 1024 * 1024 + 1)
                            if response.status != status or len(body) > 4 * 1024 * 1024:
                                raise AssertionError(f"Unexpected response: {route}, {response.status}")
                            if expected is not None and body != expected:
                                raise AssertionError("Static bytes differ from wheel: " + route)
                            record["checks"].append({"route": route, "host_override": host, "status": status,
                                                     "bytes": len(body), "sha256": sha(body)})
                            if route.startswith("/api/") or route == "/runtime.json":
                                assert response.getheader("cache-control") == "no-store"
                            return body
                        finally:
                            connection.close()

                    status = json.loads(request("/api/status", 200))
                    assert status["execution"] == "not_connected" and status["public_store"] is False
                    runtime = json.loads(request("/runtime.json", 200))
                    assert runtime["identity"] == expected_identity
                    assert not runtime["owner_controls"] and not runtime["intake"] and runtime["workspace"] is None
                    record["runtime"] = runtime
                    request("/", 307)
                    for route in ("/stack", "/history", "/observatory", "/monitor", "/workspaces"):
                        request(route, 200, resources["static/index.html"])
                    for name, data in resources.items():
                        if name.startswith("static/assets/"):
                            request("/" + name.removeprefix("static/"), 200, data)
                    request("/api/public/snapshot", 503)
                    request("/api/status", 400, host="untrusted.example")
                finally:
                    child.terminate()
                    try:
                        record["exit_code"] = child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                        record["forced_kill"] = True
                    record["stopped"] = child.poll() is not None
                if record.get("forced_kill") or record["exit_code"] not in (0, -15):
                    raise RuntimeError("Central did not stop cleanly")
                assert "Application shutdown complete" in log_path.read_text()
                with socket.socket() as probe:
                    probe.settimeout(1)
                    record["port_closed"] = probe.connect_ex(("127.0.0.1", record["port"])) != 0
                if not record["port_closed"]:
                    raise RuntimeError("Candidate port still accepts connections after shutdown")
                verify_installed()
        assert report["starts"][0]["pid"] != report["starts"][1]["pid"]
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "starts": len(report["starts"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
