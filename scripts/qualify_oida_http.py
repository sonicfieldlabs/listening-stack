"""Isolated installed Oída HTTP qualification; optional real local listening calls.

Run with candidate Python -I. Uses a reserved loopback socket, isolated owner
state, no provider credentials and offline checkpoints. Does not change previews.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import runpy
import socket
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pass_receipts(value):
    if isinstance(value, dict):
        yield from value.get("pass_provenance", [])
        for key, child in value.items():
            if key != "pass_provenance":
                yield from pass_receipts(child)
    elif isinstance(value, list):
        for child in value:
            yield from pass_receipts(child)


def listening_cases(family, checkpoint, pass_name):
    """Same task through alias and canonical selectors, never fallback probes."""
    from oida.reasoning.audio_selection import selector
    from oida.reasoning.model_catalog import find_model_spec

    actual = selector(find_model_spec("oida_moss", str(checkpoint))).model_dump()
    if not actual["model_id"].endswith("-" + family.capitalize()):
        raise ValueError("Checkpoint does not match the selected local model family")
    return [
        {"operation_id": f"http-{family}-{pass_name}-{index}",
         "pass": pass_name,
         "requested": selector(find_model_spec("oida_moss", model_id)).model_dump(),
         "actual": actual}
        for index, model_id in enumerate((family, actual["model_id"]))
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "variant", "instruct", "thinking", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--libraries", required=True)
    parser.add_argument(
        "--central",
        action="store_true",
        help="Also run connected Central and Akousmata in a fresh workspace",
    )
    parser.add_argument(
        "--listen", action="store_true", help="Two real requests: alias and canonical model"
    )
    parser.add_argument("--central-situated", action="store_true",
                        help="Require a real deterministic situated stop after the Central listening run")
    parser.add_argument("--planner-config", type=Path,
                        help="Explicit isolated local planner configuration for a learned situated stop")
    parser.add_argument("--listen-model", choices=("instruct", "thinking"), default="instruct")
    parser.add_argument("--listen-pass", choices=("caption", "events", "music", "speech", "transcribe"), default="caption")
    args = parser.parse_args()
    if args.central_situated and not args.central:
        parser.error("--central-situated requires --central")
    if args.planner_config and not (args.central and args.central_situated):
        parser.error("--planner-config requires --central --central-situated")
    if not args.listen and (args.listen_model != "instruct" or args.listen_pass != "caption"):
        parser.error("Model/pass selection requires --listen")
    if not sys.flags.isolated or not args.output.is_absolute() or args.output.exists():
        parser.error("Candidate Python -I and fresh absolute output required")
    verifier = Path(__file__).with_name("verify_candidate_resources.py")
    check = runpy.run_path(str(verifier))["check"]
    identity = check(args.manifest)
    selection_raw = (args.variant / "selection.json").read_bytes()
    selection = json.loads(selection_raw)
    if selection["base_manifest_sha256"] != sha(args.manifest.read_bytes()):
        raise ValueError("Model variant and application manifest differ")
    for row in selection["upstream_files"]:
        if (
            sha((args.variant / "moss-source" / row["path"]).read_bytes())
            != row["sha256"]
        ):
            raise ValueError("Upstream source changed")
    from akousma.resource_admission import admission_status, resource_directory
    from oida.reasoning.audio_selection import selector
    from oida.reasoning.model_catalog import find_model_spec

    if admission_status()["busy"]:
        raise RuntimeError(
            "Managed heavy operation active; do not contend with current services"
        )
    args.output.mkdir(mode=0o700)
    (args.output / "home").mkdir(mode=0o700)
    fixture = args.output / "synthetic.wav"
    with wave.open(str(fixture), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(
            b"".join(
                struct.pack("<h", round(1200 * math.sin(2 * math.pi * 440 * i / 16000)))
                for i in range(16000)
            )
        )
    report = {
        "status": "running",
        "scope": "installed Oida HTTP; not Central dispatch or semantic accuracy",
        "resources": identity,
        "variant_selection_sha256": sha(selection_raw),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "verifier_sha256": sha(verifier.read_bytes()),
        "real_inference_requested": args.listen or args.central,
        "listening_cases": [],
        "paid_calls": False,
        "checks": [],
    }
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "en_US.UTF-8",
        "HOME": str(args.output / "home"),
        "PYTHONUNBUFFERED": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HOME": str(args.output / "hf-cache"),
        "TOKENIZERS_PARALLELISM": "false",
        "DYLD_LIBRARY_PATH": args.libraries,
        "OIDA_ENGINE_PROFILE": "mac-mps",
        "OIDA_MOSS_AUDIO_REPO": str(args.variant / "moss-source"),
        "OIDA_MOSS_INSTRUCT_MODEL": str(args.instruct.resolve()),
        "OIDA_MOSS_THINKING_MODEL": str(args.thinking.resolve()),
        "OIDA_REQUIRE_MODEL": "1",
        "OIDA_MOSS_BACKUP_MODEL": "",
        "OIDA_MOSS_PREWARM": "0",
        "OIDA_DATA_DIR": str(args.output / "state"),
        "OIDA_AUDIO_DIR": str(args.output / "audio"),
        "OIDA_TRIAL_DIR": str(args.output / "trial"),
        "AKOUSMATA_PATH": str(args.output / "store"),
        "AKOUSMATA_WATCHER": "0",
        "OIDA_SONICFIELD_ROOT": str(args.output / "no-sonicfield"),
        "LISTENINGSTACK_RESOURCE_DIR": str(resource_directory().resolve()),
        "LISTENINGSTACK_WORKSPACE_ID": "http-qualification",
        "LISTENINGSTACK_WORKSPACE_GENERATION": "1",
    }
    if args.planner_config:
        environment["OIDA_LOCAL_REASONING_CONFIG"] = str(args.planner_config.resolve(strict=True))
    registry = context = None
    if args.central:
        from dataclasses import replace

        from listeningstackweb.workspace import WorkspaceRegistry

        registry = WorkspaceRegistry(
            args.output / "workspace-root", args.output / "trial"
        )
        registry.create(
            slug="qualification", name="Private runtime qualification", kind="testing"
        )
        context = replace(
            registry.context("qualification"), generation="qualification-1"
        )
        environment.update(
            {
                "OIDA_DATA_DIR": str(context.paths["oida"]),
                "OIDA_AUDIO_DIR": str(context.paths["oida_audio"]),
                "AKOUSMATA_PATH": str(context.paths["akousmata"]),
                "LISTENINGSTACK_WORKSPACE_ID": context.id,
                "LISTENINGSTACK_WORKSPACE_GENERATION": context.generation,
            }
        )
        report["scope"] = (
            "isolated Oida HTTP and connected Central caption-to-memory; not full-stack qualification"
        )
    headers = {}
    child = None
    started = time.monotonic()
    try:
        with (
            socket.socket() as reserved,
            (args.output / "service.log").open("x") as log,
        ):
            reserved.bind(("127.0.0.1", 0))
            reserved.listen(128)
            port = reserved.getsockname()[1]
            environment["OIDA_PORT"] = str(port)
            report["port"] = port
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "uvicorn",
                    "oida.server:create_app",
                    "--factory",
                    "--fd",
                    str(reserved.fileno()),
                ],
                pass_fds=(reserved.fileno(),),
                env=environment,
                cwd=args.output,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            report["pid"] = child.pid
            reserved.close()

            def request(
                method, path, expected=200, payload=None, binding=True, timeout=10
            ):
                connection = http.client.HTTPConnection(
                    "127.0.0.1", port, timeout=timeout
                )
                try:
                    sent_headers = dict(headers) if binding else {}
                    if payload is not None:
                        sent_headers["Content-Type"] = "application/json"
                    connection.request(
                        method,
                        path,
                        json.dumps(payload) if payload is not None else None,
                        sent_headers,
                    )
                    response = connection.getresponse()
                    body = response.read(8 * 1024 * 1024 + 1)
                    if len(body) > 8 * 1024 * 1024 or response.status != expected:
                        report["failed_response"] = {
                            "method": method,
                            "path": path,
                            "status": response.status,
                            "expected_status": expected,
                            "oversized": len(body) > 8 * 1024 * 1024,
                            "sha256": sha(body),
                        }
                        # Private synthetic qualification, bounded diagnostics;
                        # no credentials or shared historical records are used.
                        if len(body) <= 8 * 1024 * 1024:
                            (args.output / "failed-response.json").write_bytes(body)
                        raise RuntimeError(
                            f"Unexpected bounded response: {method} {path} {response.status}"
                        )
                    report["checks"].append(
                        {
                            "method": method,
                            "path": path,
                            "status": response.status,
                            "sha256": sha(body),
                        }
                    )
                    return json.loads(body)
                finally:
                    connection.close()

            deadline = time.monotonic() + 150
            while True:
                if child.poll() is not None:
                    raise RuntimeError("Oida exited before readiness")
                try:
                    health = request("GET", "/health", timeout=1)
                    break
                except (OSError, http.client.HTTPException):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Oida readiness timeout")
                    time.sleep(0.2)
            assert health["pid"] == child.pid and health["profile"] == "mac-mps"
            assert (
                health["port"] == port
                and health["hf_hub_offline"]
                and not health["allow_hf_hub"]
            )
            owner = request("GET", "/owner/identity")
            assert owner["mode"] == "workspace" and owner["pid"] == child.pid
            headers.update(
                {
                    "x-centaur-workspace": owner["workspace_id"],
                    "x-centaur-generation": owner["generation"],
                    "x-centaur-binding": owner["binding"],
                }
            )
            request("POST", "/gateway/listen", 409, {}, binding=False)
            options = request("GET", "/listening/options")
            (args.output / "listening-options.json").write_text(
                json.dumps(options, indent=2) + "\n"
            )
            checkpoint = getattr(args, args.listen_model)
            cases = listening_cases(args.listen_model, checkpoint, args.listen_pass)
            for model_id in (args.listen_model, cases[0]["actual"]["model_id"]):
                selection = selector(
                    find_model_spec("oida_moss", model_id)
                ).model_dump()
                if not any(
                    row.get("audio_model") == selection and row.get("available")
                    for row in options["models"]
                ):
                    raise RuntimeError(
                        "Configured selector is not available to Central clients"
                    )
            base = {
                "path": str(fixture),
                "passes": ["caption"],
                "remember": False,
                "privacy_mode": "incognito",
                "raw_audio_policy": "not_stored",
                "expected_source_sha256": sha(fixture.read_bytes()),
            }
            request(
                "POST", "/gateway/listen", 400, {**base, "model_id": "does-not-exist"}
            )
            if args.listen:
                for index, case in enumerate(cases):
                    case_started = time.monotonic()
                    result = request(
                        "POST",
                        "/gateway/listen",
                        payload={
                            **base,
                            "passes": [case["pass"]],
                            "audio_model": case["requested"],
                            "operation_id": case["operation_id"],
                        },
                        timeout=600,
                    )
                    receipts = list(pass_receipts(result))
                    if not receipts or any(
                        r.get("requested_audio_model") != case["requested"]
                        or r.get("actual_audio_model") != case["actual"]
                        for r in receipts
                    ):
                        raise RuntimeError(
                            "HTTP event lost requested/actual model attribution"
                        )
                    if result.get("status") != "complete" or result.get("outcome") != "listened":
                        raise RuntimeError("HTTP inference did not complete listening")
                    (args.output / f"{case['pass']}-{index}.json").write_text(
                        json.dumps(result, indent=2) + "\n"
                    )
                    operation = request("GET", f"/operations/{case['operation_id']}")
                    if operation.get("status") != "complete":
                        raise RuntimeError(
                            "HTTP inference has no completed operation receipt"
                        )
                    (args.output / f"operation-{index}.json").write_text(
                        json.dumps(operation, indent=2) + "\n"
                    )
                    report["listening_cases"].append({
                        **case, "status": "passed", "wall_seconds": time.monotonic() - case_started,
                        "evidence": f"{case['pass']}-{index}.json",
                        "scope": "HTTP execution and model attribution; not semantic accuracy or action planning",
                    })
            if args.central:
                if (
                    owner["workspace_id"] != context.id
                    or owner["generation"] != context.generation
                ):
                    raise RuntimeError("Oida workspace identity mismatch")
                companion = Path(__file__).with_name("qualify_central_connected.py")
                report["central"] = runpy.run_path(str(companion))["qualify"](
                    registry,
                    context,
                    environment,
                    port,
                    fixture,
                    selector(
                        find_model_spec("oida_moss", str(args.instruct))
                    ).model_dump(),
                    args.output,
                    situated=args.central_situated,
                    planner_config=args.planner_config,
                )
            check(args.manifest)
            report["status"] = "passed"
    finally:
        if child is not None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
                report["status"] = "failed-forced-shutdown"
            report["returncode"] = child.returncode
            with socket.socket() as probe:
                report["port_closed"] = (
                    probe.connect_ex(("127.0.0.1", report["port"])) != 0
                )
            if (
                not report["port_closed"]
                or "Application shutdown complete"
                not in (args.output / "service.log").read_text()
            ):
                report["status"] = "failed-shutdown"
        if report["status"] == "running":
            report["status"] = "failed"
        report["wall_seconds"] = time.monotonic() - started
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {key: report[key] for key in ("status", "wall_seconds", "port_closed")}
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
