"""Companion to qualify_oida_http: real Central/Akousmata processes and one run.

Uses only the parent runner's fresh workspace and already verified Oída process.
No inference substitution, mocks, active-service changes or external providers.
"""

import hashlib
import http.client
import json
import re
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def planning_options(planner):
    # Central intentionally lets per-run choices override workspace defaults.
    return {"provider_id": "local_ecology" if planner else "local_structured",
            "model_id": planner["model_id"] if planner else None,
            "reasoning_context": "record", "reasoning_sound": True}


def validate_situated_stop(run, planner=None):
    """Require a retained bounded decision with explicit deterministic/learned identity."""
    chain = run.get("results", {}).get("reasoning_chain") or {}
    decisions = chain.get("decisions") or []
    receipts = chain.get("decision_receipts") or []
    if (chain.get("contract") != "listening-swarm/reasoning-chain/v1"
            or chain.get("status") != "complete" or len(decisions) != 1
            or chain.get("moves") or len(receipts) != 1):
        raise RuntimeError("Situated chain did not retain one bounded stop decision")
    decision = decisions[0]
    if (decision.get("status") != "complete" or decision.get("action") != "stop"
            or decision.get("record_id") != chain.get("record_id")
            or not re.fullmatch(r"[a-f0-9]{64}", str(decision.get("record_sha256", "")))):
        raise RuntimeError("Situated decision lacks expected owner evidence")
    refs = (decision.get("decision") or {}).get("next_move", {}).get("evidence_refs")
    if planner:
        if (decision.get("provider_id") != "local_ecology"
                or decision.get("basis") != "LLM decision"
                or decision.get("model_id") != planner["model_id"]
                or decision.get("deployment") != planner["deployment"]
                or decision.get("blockers") or not refs):
            raise RuntimeError("Learned situated decision identity mismatch")
    elif (decision.get("provider_id") != "local_structured"
          or decision.get("basis") != "deterministic; no LLM used"
          or refs != [f"event:{chain.get('record_id')}:anchor"]):
        raise RuntimeError("Deterministic situated decision evidence mismatch")
    receipt = receipts[0]
    if (receipt.get("decision_id") != decision.get("id")
            or receipt.get("initiator_class") != ("model_proposed_admitted" if planner else "deterministic_policy")
            or receipt.get("is_authorizing") is not False):
        raise RuntimeError("Situated stop authority attribution mismatch")
    return chain


def validate_situated_record(chain, record):
    # Oída's journal uses ASCII-escaped canonical JSON; Central's record export
    # uses UTF-8 literals. Compare each digest with its own declared byte recipe.
    from oida.owner_journal import canonical
    expected = hashlib.sha256(canonical(record).encode()).hexdigest()
    if chain["decisions"][0]["record_sha256"] != expected:
        raise RuntimeError("Situated decision digest does not bind the retained account")
    return {"status": "passed", "sha256": expected,
            "hash_basis": "Oida owner_journal.canonical: sorted compact JSON, ensure_ascii=True"}


def validate_owner_snapshot(chain, saved):
    for key in ("id", "status", "record_id", "record_sha256", "provider_id", "model_id", "basis", "deployment", "decision"):
        if saved.get(key) != chain["decisions"][0].get(key):
            raise RuntimeError("Central and durable owner decision differ: " + key)
    offered = {item["ref"] for item in saved["evidence"]}
    cited = list(saved["decision"]["next_move"]["evidence_refs"])
    cited += [ref for finding in saved["decision"].get("findings", []) for ref in finding["evidence_refs"]]
    if not cited or not set(cited) <= offered:
        raise RuntimeError("Learned decision cites evidence outside retained context")
    return {"status": "passed", "evidence_items": len(offered)}


def qualify(registry, context, environment, owner_port, fixture, audio_model, output, *, situated=False, planner_config=None):
    from listeningstackweb.runtime_identity import snapshot

    planner = None
    if planner_config:
        if not situated:
            raise ValueError("Learned planner qualification requires situated mode")
        from oida.reasoning.local import worker
        cfg = json.loads(Path(planner_config).read_text())
        selected = next(e for e in cfg["models"] if e["id"] == cfg["recommended_model"])
        planner = {"model_id": selected["id"], "deployment": {
            "revision": selected["revision"], "evaluation_sha256": selected["evaluation_sha256"],
            "worker_sha256": hashlib.sha256(Path(worker.__file__).read_bytes()).hexdigest()}}

    report = {
        "status": "running",
        "scope": "one real caption-to-memory Central run; no reasoning, generation or swarm",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "processes": [],
        "checks": [],
    }
    children = []
    if situated:
        report["scope"] = "real caption-to-memory and deterministic situated stop; no learned planning, recursive action, generation or swarm"
    if planner:
        report["scope"] = "real caption-to-memory through Central and learned situated stop; no recursive action, generation or swarm"
        report["planner"] = planner
    headers = {
        "X-Centaur-Workspace": context.id,
        "X-Centaur-Generation": context.generation,
    }
    owner_binding = None

    def request(port, method, path, payload=None, status=200, binding=True):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            sent = {"Content-Type": "application/json", **(headers if binding else {})}
            if binding and port == owner_port and owner_binding:
                sent["X-Centaur-Binding"] = owner_binding
            connection.request(
                method, path, json.dumps(payload) if payload is not None else None, sent
            )
            response = connection.getresponse()
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024 or response.status != status:
                (output / "central-failed-response.txt").write_bytes(body)
                raise RuntimeError(
                    f"Central qualification: {method} {path} returned {response.status}"
                )
            report["checks"].append(
                {"port": port, "method": method, "path": path, "status": status}
            )
            return json.loads(body)
        finally:
            connection.close()

    def launch(name, command, env, pass_fds=()):
        log_path = output / f"{name}.log"
        with log_path.open("x") as log:
            child = subprocess.Popen(
                command,
                env=env,
                cwd=output,
                pass_fds=pass_fds,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        row = {"name": name, "pid": child.pid}
        report["processes"].append(row)
        children.append((child, row, log_path))
        return child, row, log_path

    def ready(child, port, path):
        deadline = time.monotonic() + 90
        while True:
            if child.poll() is not None:
                raise RuntimeError("Connected child exited before readiness")
            try:
                return request(port, "GET", path)
            except (OSError, http.client.HTTPException):
                if time.monotonic() > deadline:
                    raise TimeoutError("Connected child readiness timeout")
                time.sleep(0.2)

    try:
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            reserved.listen(128)
            memory_port = reserved.getsockname()[1]
            child, row, _ = launch(
                "akousmata",
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "uvicorn",
                    "akousmata_app.server:app",
                    "--fd",
                    str(reserved.fileno()),
                ],
                environment,
                (reserved.fileno(),),
            )
            row["port"] = memory_port
        owner = ready(child, memory_port, "/owner/identity")
        if (
            owner.get("workspace_id") != context.id
            or owner.get("generation") != context.generation
            or owner.get("owner") != "akousmata"
        ):
            raise RuntimeError("Memory owner identity mismatch")
        registry.publish_active(context.slug, generation=context.generation)
        central_env = {
            **environment,
            "LISTENINGSTACK_OWNER_OIDA": f"http://127.0.0.1:{owner_port}",
            "LISTENINGSTACK_OWNER_AKOUSMATA": f"http://127.0.0.1:{memory_port}",
        }
        child, row, log_path = launch(
            "central",
            [
                sys.executable,
                "-I",
                "-m",
                "listeningstackweb.server",
                "--port",
                "0",
                "--owner-controls",
                "--workspace",
                context.slug,
                "--workspace-root",
                str(registry.root),
                "--trial-root",
                str(registry.trial_root),
            ],
            central_env,
        )
        deadline = time.monotonic() + 90
        while True:
            if child.poll() is not None:
                raise RuntimeError("Central exited before readiness")
            match = re.search(
                r"Uvicorn running on http://127\.0\.0\.1:(\d+)", log_path.read_text()
            )
            if match:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Central startup timeout")
            time.sleep(0.2)
        central_port = row["port"] = int(match.group(1))
        runtime = request(central_port, "GET", "/runtime.json")
        if runtime["identity"] != snapshot():
            raise RuntimeError("Central installed identity mismatch")
        request(
            central_port,
            "POST",
            "/api/owner/control/run",
            {},
            status=409,
            binding=False,
        )
        options = request(central_port, "GET", "/api/owner/listening/options")
        if not any(
            m.get("audio_model") == audio_model and m.get("available")
            for m in options["models"]
        ):
            raise RuntimeError("Central cannot select the configured model")
        if situated:
            from oida.situated_listener import Settings
            identity = request(owner_port, "GET", "/owner/identity")
            if (identity.get("workspace_id") != context.id
                    or identity.get("generation") != context.generation
                    or not identity.get("binding")):
                raise RuntimeError("Situated configuration owner binding mismatch")
            owner_binding = identity["binding"]
            policy = Settings(enabled=True).model_dump()
            if planner:
                policy.update(provider_id="local_ecology", model_id=planner["model_id"])
            policy["context"] = {"sound": True, "memories": False, "web": False}
            policy["rules"].update(relisten="never", continuation="never", max_steps=1)
            policy["relistening"]["enabled"] = False
            request(owner_port, "POST", "/reasoning/workspace/situated/config", policy)
        result = request(
            central_port,
            "POST",
            "/api/owner/control/run",
            {
                "request_id": "qualification-caption",
                "options": {
                    **planning_options(planner),
                    "source": {
                        "kind": "file",
                        "label": "Synthetic qualification tone",
                        "ref": str(fixture),
                        "seconds": 1.0,
                        "audio_model": audio_model,
                        "explicit_passes": ["caption"],
                    },
                    "memory": "record",
                    "retention_mode": "do_not_preserve",
                    "reasoning": situated,
                    "generation": "off",
                },
            },
        )
        deadline = time.monotonic() + 600
        while result["status"] in {"running", "stopping"}:
            if time.monotonic() > deadline:
                raise TimeoutError("Central run deadline")
            time.sleep(0.5)
            result = request(
                central_port, "GET", "/api/owner/control/runs/qualification-caption"
            )
        (output / "central-run.json").write_text(json.dumps(result, indent=2) + "\n")
        if result["status"] != "complete":
            raise RuntimeError(
                "Central run did not complete; retained its actual result"
            )
        if situated:
            chain = validate_situated_stop(result, planner)
            (output / "central-situated-chain.json").write_text(json.dumps(chain, indent=2) + "\n")
            report["situated_stop"] = "passed"
        record_id = result["results"]["listening_record_id"]
        record = request(memory_port, "GET", "/api/records/" + record_id)["record"]
        operation = request(
            owner_port,
            "GET",
            "/operations/" + result["results"]["listening_operation_id"],
        )
        if (
            operation["status"] != "complete"
            or operation.get("akousma_id") != record_id
        ):
            raise RuntimeError("Central and owner operation record identities differ")
        digest = hashlib.sha256(
            json.dumps(
                record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        if digest != result["results"]["record_sha256"]:
            raise RuntimeError("Central and retained account bytes differ")
        if situated:
            report["situated_record_binding"] = validate_situated_record(chain, record)
        if planner:
            journal = context.paths["oida"] / "owner-journal.sqlite3"
            db = sqlite3.connect(journal.as_uri() + "?mode=ro", uri=True)
            try:
                row = db.execute("SELECT payload FROM snapshots WHERE kind=? AND subject=?",
                                 ("situated_decision", chain["decisions"][0]["id"])).fetchone()
            finally:
                db.close()
            if not row:
                raise RuntimeError("Learned Central decision has no durable owner snapshot")
            saved = json.loads(row[0])
            (output / "central-owner-decision.json").write_text(json.dumps(saved, indent=2) + "\n")
            report["learned_owner_snapshot"] = validate_owner_snapshot(chain, saved)
        (output / "central-record.json").write_text(json.dumps(record, indent=2) + "\n")
        (output / "central-operation.json").write_text(
            json.dumps(operation, indent=2) + "\n"
        )

        # The owner journal is read-only evidence here, never a source of new
        # operations. Replaying a completed Central ID must not dispatch again.
        def owner_cutoff():
            journal = context.paths["oida"] / "owner-journal.sqlite3"
            connection = sqlite3.connect(journal.as_uri() + "?mode=ro", uri=True)
            try:
                return connection.execute(
                    "SELECT COUNT(*), MAX(sequence) FROM events"
                ).fetchone()
            finally:
                connection.close()

        before = owner_cutoff()
        command = child.args
        child.terminate()
        child.wait(timeout=20)
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", central_port)) == 0:
                raise RuntimeError("First Central port remained open after shutdown")
        child, row, log_path = launch("central-restart", command, central_env)
        deadline = time.monotonic() + 90
        while True:
            if child.poll() is not None:
                raise RuntimeError("Restarted Central exited before readiness")
            match = re.search(
                r"Uvicorn running on http://127\.0\.0\.1:(\d+)", log_path.read_text()
            )
            if match:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Central restart timeout")
            time.sleep(0.2)
        central_port = row["port"] = int(match.group(1))
        runtime = request(central_port, "GET", "/runtime.json")
        if runtime["identity"] != snapshot():
            raise RuntimeError("Restarted Central identity changed")
        retained = request(
            central_port, "GET", "/api/owner/control/runs/qualification-caption"
        )
        replay_payload = {"request_id": result["id"], "options": result["options"]}
        transport = request(central_port, "GET", "/api/owner/transport/state")
        if (
            transport["mode"] != "stopped"
            or transport["active"]
            or transport["requests"]
            or transport["actions"]
            or transport["unresolved_occurrences"]
        ):
            raise RuntimeError(
                "Restart has unsettled work; do not bypass Transport admission"
            )
        request(
            central_port, "POST", "/api/owner/control/run", replay_payload, status=409
        )
        resumed = request(central_port, "POST", "/api/owner/transport/resume", {})
        if resumed["mode"] != "running":
            raise RuntimeError("Reviewed Transport did not resume")
        replay = request(central_port, "POST", "/api/owner/control/run", replay_payload)
        if retained != result or replay != result:
            raise RuntimeError("Restart or replay changed the completed Central run")
        changed = json.loads(json.dumps(replay_payload))
        changed["options"]["question"] = (
            "Different request under the same ID must be refused"
        )
        request(central_port, "POST", "/api/owner/control/run", changed, status=409)
        after = owner_cutoff()
        if before != after:
            raise RuntimeError("Owner journal changed during completed-run replay")
        (output / "central-replay.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "retained_run_identical": True,
                    "replay_identical": True,
                    "conflicting_request_status": 409,
                    "restart_admission": transport["mode"],
                    "resumed_admission": resumed["mode"],
                    "owner_events_before": before,
                    "owner_events_after": after,
                    "scope": "completed run restart/replay; not interrupted inference recovery",
                },
                indent=2,
            )
            + "\n"
        )
        report["restart_replay"] = "passed"
        from akousma.resource_admission import admission_status

        accounts_before = request(memory_port, "GET", "/api/records?limit=1000")
        cancelled_payload = json.loads(json.dumps(replay_payload))
        cancelled_payload["request_id"] = "qualification-cancel"
        cancel_operation = (
            "control-" + hashlib.sha256(b"qualification-cancel").hexdigest()[:40]
        )
        owner_pid = request(owner_port, "GET", "/owner/identity")["pid"]
        request(central_port, "POST", "/api/owner/control/run", cancelled_payload)
        deadline = time.monotonic() + 90
        while True:
            run = request(
                central_port, "GET", "/api/owner/control/runs/qualification-cancel"
            )
            admission = admission_status()
            holder = admission.get("holder") or {}
            if (
                run.get("results", {}).get("listening_operation_id") == cancel_operation
                and admission.get("busy")
                and holder.get("pid") == owner_pid
                and holder.get("capability") == "generate"
            ):
                running = request(owner_port, "GET", "/operations/" + cancel_operation)
                if running["status"] == "running":
                    break
            if (
                run["status"] not in {"running", "stopping"}
                or time.monotonic() > deadline
            ):
                raise RuntimeError(
                    "Could not observe the target operation inside admitted generation"
                )
            time.sleep(0.05)
        stopped = request(central_port, "POST", "/api/owner/transport/stop", {})
        deadline = time.monotonic() + 600
        while True:
            run = request(
                central_port, "GET", "/api/owner/control/runs/qualification-cancel"
            )
            transport_after = request(central_port, "GET", "/api/owner/transport/state")
            if not transport_after["active"] and run["status"] not in {
                "running",
                "stopping",
            }:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Cancelled Central worker did not settle")
            time.sleep(0.2)
        cancelled = request(owner_port, "GET", "/operations/" + cancel_operation)
        accounts_after = request(memory_port, "GET", "/api/records?limit=1000")
        cancellation = {
            "observed_operation": running,
            "admitted_generation": admission,
            "stop_response": stopped,
            "settled_run": run,
            "settled_transport": transport_after,
            "owner_receipt": cancelled,
            "accounts_unchanged": accounts_before == accounts_after,
            "scope": "cancellation during admitted generate; not token-level interruption or immediate GPU release",
        }
        (output / "central-cancellation.json").write_text(
            json.dumps(cancellation, indent=2) + "\n"
        )
        if (
            cancelled["status"] != "cancelled"
            or cancelled.get("akousma_id")
            or cancelled.get("event_id")
            or accounts_before != accounts_after
            or run.get("results", {}).get("record_id")
        ):
            raise RuntimeError(
                "Cancellation did not fence retained account publication"
            )
        report["cancellation_publication_fence"] = "passed"
        report["cancelled_central_status"] = run["status"]
        if run["status"] != "stopped" or transport_after["actions"]:
            raise RuntimeError("Acknowledged cancellation still requires Central review")
        report.update(status="passed", record_id=record_id, record_sha256=digest)
    finally:
        for child, row, log_path in reversed(children):
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
                report["status"] = "failed-forced-shutdown"
            row["returncode"] = child.returncode
            if row.get("port"):
                with socket.socket() as probe:
                    row["port_closed"] = (
                        probe.connect_ex(("127.0.0.1", row["port"])) != 0
                    )
                if not row["port_closed"]:
                    report["status"] = "failed-port-open"
            row["shutdown_logged"] = (
                "Application shutdown complete" in log_path.read_text()
            )
            if not row["shutdown_logged"]:
                report["status"] = "failed-shutdown"
        if report["status"] == "running":
            report["status"] = "failed"
        (output / "central-connected-report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    if report["status"] != "passed":
        raise RuntimeError("Connected qualification failed")
    return report
