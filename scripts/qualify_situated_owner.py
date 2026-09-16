"""Real Oída HTTP decision over a retained account through a live local planner."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time


def validate_decision(decision, record, model_id, deployment):
    from oida.owner_journal import canonical
    if (decision.get("status") != "complete" or decision.get("basis") != "LLM decision"
            or decision.get("provider_id") != "local_ecology"
            or decision.get("model_id") != model_id
            or decision.get("action") != "stop" or decision.get("blockers")
            or decision.get("record_sha256") != hashlib.sha256(canonical(record).encode()).hexdigest()
            or not decision.get("evidence") or decision.get("deployment") != deployment):
        raise RuntimeError("Learned decision missing expected retained evidence")


def qualify(record_path, config_path, environment, output):
    from akousma import AkousmataStore
    from oida.reasoning.local import worker
    from oida.situated_listener import Settings

    root = output / "situated-owner"
    root.mkdir(mode=0o700)
    record = json.loads(record_path.read_text())
    store = AkousmataStore(root / "memory")
    try:
        store.put(record)
        if store.get(record["akousma_id"]) != record:
            raise RuntimeError("Imported account bytes changed")
    finally:
        store.close()
    cfg = json.loads(config_path.read_text())
    selected = next(e for e in cfg["models"] if e["id"] == cfg["recommended_model"])
    deployment = {"revision": selected["revision"], "evaluation_sha256": selected["evaluation_sha256"],
                  "worker_sha256": hashlib.sha256(Path(worker.__file__).read_bytes()).hexdigest()}
    env = {**environment, "HOME": str(root), "OIDA_DATA_DIR": str(root / "oida"),
           "OIDA_AUDIO_DIR": str(root / "audio"), "OIDA_TRIAL_DIR": str(root / "trial"),
           "AKOUSMATA_PATH": str(root / "memory"), "AKOUSMATA_WATCHER": "0",
           "OIDA_ENGINE_PROFILE": "mac-mps", "OIDA_MOSS_PREWARM": "0",
           "OIDA_MOSS_BACKUP_MODEL": "", "OIDA_REQUIRE_MODEL": "0",
           "OIDA_SONICFIELD_ROOT": str(root / "no-sonicfield"),
           "LISTENINGSTACK_WORKSPACE_ID": "planner-owner-qualification",
           "LISTENINGSTACK_WORKSPACE_GENERATION": "candidate-1"}
    report = {"status": "running", "scope": "real learned HTTP decision over previously retained account; no new audio inference or Central dispatch",
              "record_file_sha256": hashlib.sha256(record_path.read_bytes()).hexdigest()}
    headers = {}
    child = None
    def request(method, path, body=None, expected=200):
        connection = http.client.HTTPConnection("127.0.0.1", report["port"], timeout=120)
        try:
            connection.request(method, path, None if body is None else json.dumps(body),
                               {"Content-Type": "application/json", **headers})
            response = connection.getresponse()
            raw = response.read(4 * 1024 * 1024 + 1)
            if response.status != expected or len(raw) > 4 * 1024 * 1024:
                (root / "failed-response.json").write_bytes(raw)
                raise RuntimeError("Unexpected situated owner status: " + str(response.status))
            return json.loads(raw)
        finally:
            connection.close()
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            report["port"] = listener.getsockname()[1]
            env["OIDA_PORT"] = str(report["port"])
            with (root / "service.log").open("x") as log:
                child = subprocess.Popen([sys.executable, "-I", "-m", "uvicorn", "oida.server:create_app",
                    "--factory", "--fd", str(listener.fileno())], env=env, cwd=root,
                    pass_fds=(listener.fileno(),), stdout=log, stderr=log)
            report["pid"] = child.pid
        deadline = time.monotonic() + 60
        while True:
            if child.poll() is not None:
                raise RuntimeError("Oida exited before readiness")
            try:
                identity = request("GET", "/owner/identity")
                break
            except (OSError, http.client.HTTPException):
                if time.monotonic() > deadline:
                    raise TimeoutError("Oida readiness deadline")
                time.sleep(.2)
        if (identity["workspace_id"] != env["LISTENINGSTACK_WORKSPACE_ID"]
                or identity["generation"] != env["LISTENINGSTACK_WORKSPACE_GENERATION"]
                or identity["pid"] != child.pid):
            raise RuntimeError("Oida workspace identity mismatch")
        headers.update({"x-centaur-workspace": identity["workspace_id"],
                        "x-centaur-generation": identity["generation"], "x-centaur-binding": identity["binding"]})
        policy = Settings(enabled=True, provider_id="local_ecology", model_id=cfg["recommended_model"]).model_dump()
        policy["context"] = {"sound": True, "memories": False, "web": False}
        policy["rules"].update(relisten="never", continuation="never", max_steps=1)
        request("POST", "/reasoning/workspace/situated/config", policy)
        payload = {"request_id": "learned-stop-1", "chain_id": "qualification-chain",
                   "record_id": record["akousma_id"], "allowed_actions": ["stop"]}
        started = time.monotonic()
        decision = request("POST", "/reasoning/workspace/situated/decide", payload)
        report["decision_seconds"] = time.monotonic() - started
        (root / "decision.json").write_text(json.dumps(decision, indent=2) + "\n")
        validate_decision(decision, record, cfg["recommended_model"], deployment)
        journal = root / "oida" / "owner-journal.sqlite3"
        def read_journal():
            db = sqlite3.connect(journal.as_uri() + "?mode=ro", uri=True)
            try:
                saved = db.execute("SELECT payload FROM snapshots WHERE kind=? AND subject=?",
                                   ("situated_decision", payload["request_id"])).fetchone()
                boundary = db.execute("SELECT COUNT(*),MAX(sequence) FROM events").fetchone()
                return json.loads(saved[0]), boundary
            finally:
                db.close()
        saved, before = read_journal()
        if saved != decision:
            raise RuntimeError("HTTP decision differs from durable owner receipt")
        if request("POST", "/reasoning/workspace/situated/decide", payload) != decision:
            raise RuntimeError("Same-ID replay changed the decision")
        request("POST", "/reasoning/workspace/situated/decide", {**payload, "chain_id": "conflict"}, expected=409)
        if read_journal()[1] != before:
            raise RuntimeError("Replay grew the owner journal")
        store = AkousmataStore(root / "memory")
        try:
            if store.get(record["akousma_id"]) != record:
                raise RuntimeError("Reasoning changed the source account")
        finally:
            store.close()
        report.update(status="passed", decision_id=decision["id"], record_sha256=decision["record_sha256"],
                      evidence_items=len(decision["evidence"]), replay_unchanged=True, account_unchanged=True,
                      deployment=decision["deployment"])
    finally:
        if child is not None:
            child.terminate()
            try:
                child.wait(timeout=15)
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
        (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] != "passed":
        raise RuntimeError("Situated owner qualification failed")
    return report
