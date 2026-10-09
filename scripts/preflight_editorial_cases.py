"""Read-only, records-only editorial scope previews from explicit case selections.

Run with an isolated candidate Python -I. This prepares no approval, runs no
models and copies no audio. Output is private diagnostic material, not a release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path


def selection(path):
    raw = path.read_bytes()
    bundle = json.loads(raw)
    accounts = bundle.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Selection requires nonempty accounts")
    ids = [a.get("account_id") if isinstance(a, dict) else None for a in accounts]
    if any(not isinstance(i, str) or not i.strip() for i in ids):
        raise ValueError("Selection requires exact account IDs")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate account IDs in selection")
    case = bundle.get("case_id")
    if not isinstance(case, str) or not case.strip():
        raise ValueError("Selection requires a case ID")
    return {"case_id": case, "record_ids": sorted(ids),
            "selection_sha256": hashlib.sha256(raw).hexdigest()}


def preflight(workspace, bundles, output, export):
    workspace = workspace.resolve()
    if not output.is_absolute() or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Fresh absolute output with existing parent required")
    if output.resolve().is_relative_to(workspace):
        raise ValueError("Output must be outside the live workspace")
    selections = [selection(path) for path in bundles]
    if not selections or len({s["case_id"] for s in selections}) != len(selections):
        raise ValueError("Require distinct nonempty case selections")
    output.mkdir(mode=0o700)
    report = {"contract": "centaur/editorial-case-preflight/v1",
              "started_at": datetime.now(UTC).isoformat(),
              "scope": "Records-only unapproved previews; no inference, audio, publication or delivery",
              "cases": []}
    for index, selected in enumerate(selections, 1):
        entry = dict(selected)
        try:
            preview = export(root=workspace / "akousmata", workspace=workspace,
                             case_id=selected["case_id"], identifiers=selected["record_ids"],
                             audience="editorial", dry_run=True, prepare_decision=True,
                             include_media=False)
            bundle = preview["bundle"]
            if preview.get("published") is not False or preview.get("preview_only") is not True:
                raise ValueError("Exporter did not return an unpublished preview")
            if sorted(a["account_id"] for a in bundle["accounts"]) != selected["record_ids"]:
                raise ValueError("Exported account set differs from exact selection")
            if any(a.get("media_included") or a.get("media_path") for a in bundle.get("assets", [])):
                raise ValueError("Records-only preview unexpectedly includes media")
            proposal = bundle["disclosure"]["approval_proposal"]
            if proposal.get("state") != "unapproved":
                raise ValueError("Expected unapproved decision proposal")
            name = f"case-{index:02d}-preview.json"
            encoded = (json.dumps(preview, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
            (output / name).write_bytes(encoded)
            (output / f"case-{index:02d}-decision-proposal.json").write_text(
                json.dumps(proposal, indent=2, allow_nan=False) + "\n")
            trace = bundle.get("trace", {})
            entry.update(status="prepared-unapproved", preview=name,
                         preview_sha256=hashlib.sha256(encoded).hexdigest(),
                         completeness=trace.get("completeness"),
                         programs=len(trace.get("programs", [])), runs=len(trace.get("runs", [])))
        except Exception as exc:
            entry.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        report["cases"].append(entry)
    report["status"] = "prepared-unapproved" if all(c["status"] == "prepared-unapproved" for c in report["cases"]) else "incomplete"
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--exporter", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Import before the frozen CLI inserts its checkout source path.
    import listeningstackweb
    import listeningstackweb.trace_export as trace
    prefix = Path(sys.prefix).resolve()
    for module in (listeningstackweb, trace):
        if not Path(module.__file__).resolve().is_relative_to(prefix):
            parser.error("Installed candidate imports required")
    if not args.exporter.is_absolute() or not args.exporter.is_file():
        parser.error("Explicit absolute frozen exporter required")
    export = runpy.run_path(str(args.exporter))["export_transaction"]
    report = preflight(args.workspace, args.bundle, args.out, export)
    report["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["exporter_sha256"] = hashlib.sha256(args.exporter.read_bytes()).hexdigest()
    report["installed_trace_sha256"] = hashlib.sha256(Path(trace.__file__).read_bytes()).hexdigest()
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "cases": [
        {k: c[k] for k in ("case_id", "status", "programs", "runs", "error") if k in c}
        for c in report["cases"]], "output": str(args.out)}))
    return 0 if report["status"] == "prepared-unapproved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
