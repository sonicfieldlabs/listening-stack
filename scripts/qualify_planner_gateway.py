"""Qualify one isolated local planner gateway using a freshly evaluated worker.

No mutation of existing deployments or credentials; no release promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import runpy
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def admitted_evaluation(evaluation, worker_sha):
    cases = {"no-evidence", "spanish-gap", "permission", "conflict", "budget", "portuguese",
             "generated-not-proof", "bounded-selection", "holdout-no-cause",
             "holdout-external-command", "holdout-span", "holdout-stop-repeat"}
    if (evaluation.get("status") != "passed" or evaluation.get("worker_sha256") != worker_sha
            or len(evaluation.get("rows", [])) != 12
            or {r["case"] for r in evaluation["rows"]} != cases
            or not all(r.get("passed") is True and r.get("historical_task_passed") is True
                       and r.get("proposal_boundary_issues") == [] for r in evaluation["rows"])):
        raise ValueError("Exact worker must pass the complete stricter evaluation")


def main():
    from akousma.resource_admission import admission_status, resource_directory
    from oida.reasoning.local import gateway, worker
    from oida.reasoning.registry import build_provider_registry
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "deployment", "evaluation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--owner-record", type=Path, help="Also qualify actual Oida decision persistence over this retained account")
    parser.add_argument("--central-variant", type=Path, help="Run fresh MOSS listening through Central with this installed model variant")
    parser.add_argument("--instruct", type=Path)
    parser.add_argument("--thinking", type=Path)
    parser.add_argument("--libraries")
    args = parser.parse_args()
    connected = (args.central_variant, args.instruct, args.thinking, args.libraries)
    if any(connected) and not all(connected):
        parser.error("Connected qualification requires --central-variant, --instruct, --thinking and --libraries")
    if not sys.flags.isolated or not args.output.is_absolute() or args.output.exists():
        parser.error("Isolated candidate Python and fresh absolute output required")
    verifier = runpy.run_path(str(Path(__file__).with_name("verify_candidate_resources.py")))["check"]
    resources = verifier(args.manifest)
    evaluation = json.loads(args.evaluation.read_text())
    admitted_evaluation(evaluation, sha(worker.__file__))
    old = json.loads(args.deployment.read_text())
    entry = next(e for e in old["models"] if e["id"] == evaluation["model"])
    if entry["revision"] != evaluation["revision"]:
        raise ValueError("Evaluation checkpoint differs from deployment")
    # Only the evaluated source adapter files may differ from the old inventory.
    changed_adapters = {r["file"] for r in evaluation["admission_drift"]}
    if any(not name.endswith(("/oida/reasoning/local/worker.py", "/oida/reasoning/local/gateway.py")) for name in changed_adapters):
        raise ValueError("Unexpected prior admission drift")
    files = {}
    for name, expected in entry["files"].items():
        if name in changed_adapters:
            continue
        if sha(name) != expected:
            raise ValueError("Pinned model/runtime changed: " + name)
        files[name] = expected
    files.update({str(Path(worker.__file__).resolve()): sha(worker.__file__),
                  str(Path(gateway.__file__).resolve()): sha(gateway.__file__),
                  str(args.evaluation.resolve()): sha(args.evaluation)})
    if admission_status()["busy"]:
        raise RuntimeError("Managed heavy operation active")
    args.output.mkdir(mode=0o700)
    token = secrets.token_urlsafe(48)
    token_file = args.output / "owner-token"
    token_file.write_text(token)
    token_file.chmod(0o600)
    report = {"status": "running", "scope": "isolated authenticated gateway and one learned stop proposal; not situated execution or swarm",
              "resources": resources, "evaluation_sha256": sha(args.evaluation),
              "runner_sha256": sha(__file__), "checked_inherited_files": len(files) - 3}
    if args.owner_record:
        report["scope"] = "real local gateway, adapter and persisted situated decision over a retained account; no fresh audio, Central dispatch or swarm"
    if args.central_variant:
        report["scope"] = "real local gateway and fresh Central audio-to-memory-to-learned-stop; no recursive action, generation or swarm"
    child = None
    def request(port, method, path, payload=None, *, authenticate=True, origin=False, expected=200):
        headers = {"Content-Type": "application/json"}
        if authenticate:
            headers["Authorization"] = "Bearer " + token
        if origin:
            headers["Origin"] = "http://untrusted.invalid"
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=90)
        try:
            connection.request(method, path, None if payload is None else json.dumps(payload), headers)
            response = connection.getresponse()
            body = response.read(256 * 1024 + 1)
            if response.status != expected or len(body) > 256 * 1024:
                raise RuntimeError("Unexpected gateway response: " + str(response.status))
            return json.loads(body)
        finally:
            connection.close()
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            port = report["port"] = listener.getsockname()[1]
            config = {**old, "token_file": str(token_file), "base_url": f"http://127.0.0.1:{port}/v1",
                      "models": [{**entry, "files": files, "evaluation_sha256": sha(args.evaluation),
                                  "task_checks": {"passed": 12, "total": 12}}],
                      "recommended_model": entry["id"], "qualification_scope": "private candidate only",
                      "evaluations": [{"model": "qwen", "passed": 12, "total": 12,
                                       "admitted": True, "basis": "reused strict regression; candidate only"}]}
            config_file = args.output / "deployments.json"
            config_file.write_text(json.dumps(config, indent=2) + "\n")
            config_file.chmod(0o600)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(args.output),
                   "OIDA_LOCAL_REASONING_CONFIG": str(config_file), "HF_HUB_OFFLINE": "1",
                   "LISTENINGSTACK_RESOURCE_DIR": str(resource_directory().resolve())}
            with (args.output / "gateway.log").open("x") as log:
                child = subprocess.Popen([sys.executable, "-I", "-m", "uvicorn",
                    "oida.reasoning.local.gateway:create_app", "--factory", "--fd", str(listener.fileno())],
                    env=env, cwd=args.output, pass_fds=(listener.fileno(),), stdout=log, stderr=log)
            report["pid"] = child.pid
        deadline = time.monotonic() + 60
        while True:
            if child.poll() is not None:
                raise RuntimeError("Gateway exited before readiness")
            try:
                models = request(port, "GET", "/v1/models")
                break
            except (OSError, http.client.HTTPException):
                if time.monotonic() > deadline:
                    raise TimeoutError("Gateway readiness timeout")
                time.sleep(0.2)
        if [m["id"] for m in models["data"]] != [entry["id"]]:
            raise RuntimeError("Wrong admitted model catalogue")
        request(port, "GET", "/v1/models", authenticate=False, expected=401)
        request(port, "GET", "/v1/models", origin=True, expected=401)
        os.environ["OIDA_LOCAL_REASONING_CONFIG"] = str(config_file)
        provider = build_provider_registry().get("local_ecology")
        if provider.base_url != config["base_url"]:
            raise RuntimeError("Registry did not select candidate endpoint")
        req = json.loads(args.evaluation.with_name("no-evidence-request.json").read_text())
        payload = {"model": entry["id"], "messages": req["messages"], "max_tokens": req["max_tokens"],
                   "response_format": {"type": "json_schema", "json_schema": {"schema": req["schema"]}}}
        started = time.monotonic()
        response = request(port, "POST", "/v1/chat/completions", payload)
        report["inference_seconds"] = time.monotonic() - started
        (args.output / "response.json").write_text(json.dumps(response, indent=2) + "\n")
        decision = json.loads(response["choices"][0]["message"]["content"])
        import jsonschema
        jsonschema.validate(decision, worker.request_schema(req["schema"], req["messages"][1]["content"]))
        if decision["next_move"]["action"] != "stop":
            raise RuntimeError("Bounded stop request did not stop")
        deployment = response["centaur_deployment"]
        if (deployment["worker_sha256"] != sha(worker.__file__)
                or deployment["evaluation_sha256"] != sha(args.evaluation)
                or deployment["revision"] != entry["revision"]):
            raise RuntimeError("Gateway deployment receipt mismatch")
        verifier(args.manifest)
        if args.owner_record:
            qualify_owner = runpy.run_path(str(Path(__file__).with_name("qualify_situated_owner.py")))["qualify"]
            report["situated_owner"] = qualify_owner(args.owner_record, config_file, env, args.output)
        if args.central_variant:
            connected_output = args.output / "central-connected"
            command = [str(args.central_variant / ".venv/bin/python"), "-I",
                       str(Path(__file__).with_name("qualify_oida_http.py")),
                       "--manifest", str(args.manifest), "--variant", str(args.central_variant),
                       "--instruct", str(args.instruct), "--thinking", str(args.thinking),
                       "--libraries", args.libraries, "--output", str(connected_output),
                       "--central", "--central-situated", "--planner-config", str(config_file)]
            with (args.output / "connected.log").open("x") as log:
                # The child owns bounded deadlines and shutdown of all its services.
                completed = subprocess.run(command, env=env, cwd=args.output, stdout=log, stderr=log, check=False)
            report["connected_returncode"] = completed.returncode
            if completed.returncode:
                raise RuntimeError("Connected learned qualification failed; retained all receipts")
            report["connected_report_sha256"] = sha(connected_output / "report.json")
        report["status"] = "passed"
    finally:
        if child is not None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
                report["status"] = "failed-forced-shutdown"
            report["returncode"] = child.returncode
            with socket.socket() as probe:
                report["port_closed"] = probe.connect_ex(("127.0.0.1", report["port"])) != 0
            if not report["port_closed"]:
                report["status"] = "failed-port-open"
        if report["status"] == "running":
            report["status"] = "failed"
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "port_closed", "inference_seconds")}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
