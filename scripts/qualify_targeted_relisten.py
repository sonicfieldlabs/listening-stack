"""Real installed local caption -> two targeted passes; no HTTP/planner qualification.

Use candidate Python -I. All audio/state is synthetic and private. A subprocess
deadline bounds the run; the host-wide lease covers model residency through unload.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_sidecar(sidecar, event, turn, model):
    if (sidecar.get("base_event_id") != event["id"]
            or sidecar.get("conversation_id") != "qualification-conversation"
            or sidecar.get("turn_id") != turn
            or sidecar.get("segment_ref") != event["segment"]["id"]
            or sidecar.get("segment_hash") != event["segment"]["data_ref"]["sha256"]
            or sidecar.get("model") != str(model)
            or not sidecar.get("observation")
            or "reasoning_trace" in sidecar):
        raise ValueError("Targeted sidecar lost source/turn/model attribution")
    binding = sidecar.get("source_binding", {})
    if (binding.get("status") != "verified"
            or binding.get("observed_sha256") != sidecar["segment_hash"]):
        raise ValueError("Targeted source binding is not verified")
    receipts = sidecar.get("pass_provenance", [])
    if not receipts or any(r.get("model") != str(model)
                           or r.get("effective_input", {}).get("status") != "known"
                           or r.get("weights", {}).get("status") != "known"
                           for r in receipts):
        raise ValueError("Targeted pass lacks actual input/weight provenance")
    body = {key: value for key, value in sidecar.items() if key != "sha256"}
    if sidecar.get("sha256") != digest(json.dumps(body, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode()):
        raise ValueError("Targeted sidecar digest mismatch")


def worker(args):
    from dataclasses import replace
    import numpy as np
    import soundfile as sf
    import torch
    from akousma.resource_admission import heavy_lease
    from oida.config import load_config
    from oida.engine_mps import MpsMossEngine
    from oida.listening import listening_event_dict
    from oida.reporting import report, report_to_dict
    from oida.relisten import TargetedRelistener, RelistenUnavailable

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is required for this candidate profile")
    config = replace(load_config(profile="mac-mps"),
        moss_audio_repo=args.variant / "moss-source",
        instruct_model=str(args.instruct), thinking_model=str(args.thinking),
        resident_mode="single", allow_hf_hub=False, hf_hub_offline=True, prewarm=False)
    engine = MpsMossEngine(config)
    result = {"status": "running", "pid": os.getpid(), "passes": [],
              "scope": "real direct installed adapter/re-listener; no HTTP, planner or semantic accuracy"}

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")

    with heavy_lease("phase17-targeted-relisten", "offline-qualification", timeout=1):
        try:
            engine.ensure_ready()
            audio = args.output / "synthetic.wav"
            samples = (0.035 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)).astype(np.float32)
            sf.write(audio, samples, 16000, subtype="PCM_16")
            baseline_started = time.monotonic()
            perception = report_to_dict(report(engine, str(audio), "qualification",
                passes=["caption"], chunk_seconds=45, overlap_seconds=0))
            save("initial-perception.json", perception)
            result["initial_seconds"] = time.monotonic() - baseline_started
            save("worker-report.json", result)
            event = listening_event_dict(perception, privacy_mode="session", raw_audio_policy="external_ref")
            if not event.get("pass_provenance"):
                raise RuntimeError("Initial encounter lacks model provenance")
            save("initial-event.json", event)
            initial = deepcopy(event)
            relistener = TargetedRelistener(engine)
            assignments = engine.runtime_status()["assignments"]
            for turn in ("cold-thinking", "warm-thinking"):
                started = time.monotonic()
                sidecar = relistener.run(event=event,
                    question="Is the sound continuous or intermittent? Give a brief observation.",
                    conversation_id="qualification-conversation", turn_id=turn)
                validate_sidecar(sidecar, initial, turn, args.thinking)
                if event != initial or engine.runtime_status()["assignments"] != assignments:
                    raise RuntimeError("Targeted pass changed its source event or assignments")
                save(turn + ".json", sidecar)
                result["passes"].append({"turn": turn, "status": "passed",
                    "wall_seconds": time.monotonic() - started, "sidecar_sha256": sidecar["sha256"]})
                save("worker-report.json", result)
            # Only the synthetic file owned by this fresh output is changed.
            original = audio.read_bytes()
            sf.write(audio, np.zeros(16000, dtype=np.float32), 16000, subtype="PCM_16")
            try:
                relistener.run(event=event, question="Is there a pulse?",
                    conversation_id="qualification-conversation", turn_id="changed-source")
            except RelistenUnavailable as exc:
                if "no longer matches" not in str(exc):
                    raise
                result["changed_source_refusal"] = "passed"
            else:
                raise RuntimeError("Changed source was accepted")
            finally:
                audio.write_bytes(original)
            if event != initial:
                raise RuntimeError("Changed-source refusal mutated the original event")
            result["status"] = "passed"
        finally:
            engine._clear_loaded_models(None)
            torch.mps.synchronize()
            result["final_runtime"] = engine.runtime_status()
            result["final_tensor_bytes"] = torch.mps.current_allocated_memory()
            result["final_driver_bytes"] = torch.mps.driver_allocated_memory()
            if result["final_runtime"]["loaded_models"]:
                result["status"] = "failed-unload"
            if result["status"] == "running":
                result["status"] = "failed"
            save("worker-report.json", result)
    if result["status"] != "passed":
        raise RuntimeError("Targeted qualification failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "variant", "instruct", "thinking", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--libraries", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not sys.flags.isolated or not all(getattr(args, name).is_absolute()
            for name in ("manifest", "variant", "instruct", "thinking", "output")):
        parser.error("Python -I and absolute paths required")
    if args.worker:
        worker(args)
        return
    if args.output.exists():
        parser.error("Fresh output required")
    verifier = Path(__file__).with_name("verify_candidate_resources.py")
    check = runpy.run_path(str(verifier))["check"]
    resources = check(args.manifest)
    selection_bytes = (args.variant / "selection.json").read_bytes()
    selection = json.loads(selection_bytes)
    if selection["base_manifest_sha256"] != digest(args.manifest.read_bytes()):
        raise ValueError("Variant does not belong to this base candidate")
    for row in selection["upstream_files"]:
        if digest((args.variant / "moss-source" / row["path"]).read_bytes()) != row["sha256"]:
            raise ValueError("Pinned upstream source changed")
    from akousma.resource_admission import admission_status, resource_directory
    if admission_status()["busy"]:
        raise RuntimeError("Managed heavy work is active; preserving existing services")
    args.output.mkdir(mode=0o700)
    (args.output / "home").mkdir(mode=0o700)
    environment_tool = Path(__file__).with_name("run_moss_qualification.py")
    environment = runpy.run_path(str(environment_tool))["selected_environment"](args.output, args.libraries)
    environment.update(HOME=str(args.output / "home"),
        LISTENINGSTACK_RESOURCE_DIR=str(resource_directory().resolve()))
    result = {"status": "running", "resources": resources, "paid_calls": False,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "verifier_sha256": digest(verifier.read_bytes()),
        "environment_helper_sha256": digest(environment_tool.read_bytes()),
        "variant_selection_sha256": digest(selection_bytes),
        "requirements_sha256": digest((args.variant / "requirements.lock").read_bytes()),
        "timeout_seconds": 900, "scope": "direct local re-listener; not HTTP or planner acceptance"}
    started = time.monotonic()
    try:
        with (args.output / "process.log").open("x") as log:
            child = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                *sys.argv[1:], "--worker"], cwd=args.output, env=environment,
                stdout=log, stderr=subprocess.STDOUT, timeout=900, check=False)
        result["returncode"] = child.returncode
        worker_result = json.loads((args.output / "worker-report.json").read_text())
        check(args.manifest)
        result["status"] = "passed" if child.returncode == 0 and worker_result["status"] == "passed" else "failed"
        result["worker_pid"] = worker_result["pid"]
    except subprocess.TimeoutExpired:
        result["status"] = "failed-timeout"
    finally:
        if result["status"] == "running":
            result["status"] = "failed"
        result["wall_seconds"] = time.monotonic() - started
        (args.output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "wall_seconds")}))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
