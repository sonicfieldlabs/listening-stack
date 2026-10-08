"""Run the frozen MOSS profiler offline, with isolated state and a host-wide lease.

Invoke with the selected model environment's Python -I. The parent records a
bounded subprocess result; the worker retains admission through unload, so another
managed service cannot start heavy compute while a canary model is resident.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import distributions
import json
import math
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time


def selected_environment(output: Path, libraries: str):
    # Do not inherit provider credentials, OIDA configuration, Python path hooks,
    # proxy settings or fallback selections from the interactive environment.
    environment = {name: os.environ[name] for name in ("HOME", "PATH", "TMPDIR", "LANG") if name in os.environ}
    environment.update(
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
        TOKENIZERS_PARALLELISM="false", OIDA_MOSS_BACKUP_MODEL="",
        OIDA_DATA_DIR=str(output / "state"), OIDA_AUDIO_DIR=str(output / "audio"),
        OIDA_TRIAL_DIR=str(output / "trial"), HF_HOME=str(output / "hf-cache"),
        PYTHONUNBUFFERED="1", DYLD_LIBRARY_PATH=libraries,
    )
    # Intentionally retain the default host-wide heavy lease, not a private lock.
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("variant", "instruct", "thinking", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--libraries", required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--tokens", type=int, default=32)
    parser.add_argument("--check-runtime-only", action="store_true")
    parser.add_argument("--routed-selections", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 1800:
        parser.error("Timeout must be finite and within 1..1800 seconds")
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 45 or not 1 <= args.tokens <= 256:
        parser.error("Input and output must stay within the bounded profiler limits")
    args.variant, args.output = args.variant.resolve(), args.output.resolve()
    selection = json.loads((args.variant / "selection.json").read_text())
    profiler = args.variant / "profile-moss-runtime.py"
    if hashlib.sha256(profiler.read_bytes()).hexdigest() != selection["profiler_sha256"]:
        raise ValueError("Selected profiler changed")
    for row in selection["upstream_files"]:
        source = args.variant / "moss-source" / row["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Selected upstream source changed")
    if args.worker:
        from akousma.resource_admission import heavy_lease

        sys.argv = [str(profiler), "--output", str(args.output / "profile.json"),
                    "--moss-repo", str(args.variant / "moss-source"),
                    "--instruct", str(args.instruct.resolve()),
                    "--thinking", str(args.thinking.resolve()),
                    "--seconds", str(args.seconds), "--tokens", str(args.tokens)]
        if args.check_runtime_only:
            sys.argv.append("--check-runtime-only")
        if args.routed_selections:
            sys.argv.append("--routed-selections")
        with heavy_lease("phase17-isolated-moss", "offline-qualification", timeout=1):
            runpy.run_path(str(profiler), run_name="__main__")
        return
    if args.output.exists():
        raise ValueError("Fresh run output required; previous evidence is never overwritten")
    args.output.mkdir(parents=True)
    command = [sys.executable, "-I", str(Path(__file__).resolve()), *sys.argv[1:], "--worker"]
    start = time.monotonic()
    receipt = {"status": "running", "paid_calls": False, "fallback": False,
               "scope": "offline synthetic MOSS canary; not semantic accuracy, HTTP dispatch or full-stack qualification",
               "execution_path": "local-router-selections" if args.routed_selections else "adapter",
               "variant_selection_sha256": hashlib.sha256((args.variant / "selection.json").read_bytes()).hexdigest(),
               "requirements_lock_sha256": hashlib.sha256((args.variant / "requirements.lock").read_bytes()).hexdigest(),
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "python": sys.version, "prefix": sys.prefix,
               "distributions": sorted(({"name": d.metadata["Name"], "version": d.version} for d in distributions()), key=lambda d: d["name"].lower()),
               "seconds": args.seconds, "token_cap": args.tokens,
               "timeout_seconds": args.timeout, "decoder_only": args.check_runtime_only}
    receipt_path = args.output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    try:
        with (args.output / "process.log").open("w") as log:
            result = subprocess.run(command, env=selected_environment(args.output, args.libraries),
                                    cwd=args.output, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=args.timeout, check=False)
        receipt.update(status="process-complete" if result.returncode == 0 else "failed",
                       returncode=result.returncode)
    except subprocess.TimeoutExpired:
        receipt.update(status="timed-out", returncode=None)
    finally:
        receipt["wall_seconds"] = time.monotonic() - start
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in ("status", "wall_seconds", "decoder_only")}))
    if receipt["status"] != "process-complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
