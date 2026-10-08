"""Read-only native Coastal selection diagnostic, not an approved publication.

Run with the isolated candidate Python -I. Snapshot owner SQLite stores through
Central's online-backup reader; never open them for owner writes or execute runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import listeningstackweb.trace_export as trace_module
from listeningstackweb.store_snapshot import SnapshotSet
from listeningstackweb.trace_export import CONTROL_STORES, build_trace, open_sources

import listeningstackweb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    origin = Path(listeningstackweb.__file__).resolve()
    if not origin.is_relative_to(Path(sys.prefix).resolve()):
        parser.error("Installed candidate import required")
    if args.out.exists() or not args.out.is_absolute() or not args.out.parent.is_dir():
        parser.error("Fresh absolute output with an existing parent required")
    if args.out.resolve().is_relative_to(args.workspace.resolve()):
        parser.error("Diagnostic output must be outside the live workspace")
    swarm_id = "swarm-swarm-coastal-1789471547"
    with SnapshotSet() as snapshots:
        for key, relative in CONTROL_STORES.items():
            snapshots.add(key, args.workspace / relative)
        snapshots.require_join_window(60)
        sources = open_sources(snapshots.snapshots, {})
        try:
            programs = [p for p in sources.rows("programs", "programs") if p.get("swarm_id") == swarm_id]
            if len(programs) != 3:
                raise ValueError("Expected three retained Coastal programs")
            record_ids = {e["record_id"] for p in programs for e in p.get("events", []) if e.get("record_id")}
            if len(record_ids) != 6:
                raise ValueError("Expected six retained Coastal record references")
            trace = build_trace(sources, record_ids, case_id="coastal-native-diagnostic")
            selected_programs = trace["programs"]
            selected_ids = {p["program_id"] for p in selected_programs}
            expected_ids = {p["id"] for p in programs}
            if selected_ids != expected_ids:
                raise ValueError("Program selection differs from native Coastal membership")
            event_run_ids = {e["run_id"] for p in selected_programs for e in p["events"] if e.get("run_id")}
            selected_run_ids = {r["run_id"] for r in trace["runs"]}
            if not event_run_ids.issubset(selected_run_ids):
                raise ValueError("Materialized event runs missing from trace")
            report = {
                "status": "passed", "scope": "Native store selection only; not approval, media or inference qualification",
                "candidate_module_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
                "trace_export_module_sha256": hashlib.sha256(Path(trace_module.__file__).read_bytes()).hexdigest(),
                "diagnostic_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "swarm_id": swarm_id, "record_ids": sorted(record_ids),
                "programs": [{"id": p["program_id"], "role": p.get("role"), "status": p.get("status"),
                              "events": len(p["events"]), "run_ids": p.get("run_ids")} for p in selected_programs],
                "runs": len(trace["runs"]), "events": sum(len(p["events"]) for p in selected_programs),
                "completeness": trace.get("completeness"), "snapshot_receipt": snapshots.receipt(),
            }
            args.out.mkdir()
            for name, value in (("report.json", report), ("trace-unapproved.json", trace)):
                (args.out / name).write_text(json.dumps(value, indent=2) + "\n")
            print(json.dumps({"status": report["status"], "programs": len(programs), "runs": report["runs"],
                              "events": report["events"], "output": str(args.out)}))
        finally:
            for connection in sources.connections.values():
                connection.close()


if __name__ == "__main__":
    main()
