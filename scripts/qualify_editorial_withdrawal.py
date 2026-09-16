"""Real-record withdrawal qualification in a new clone of a candidate workspace.

No live workspace, approved package or earlier authorization is modified.
Static copies already disclosed cannot be recalled by this test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate-workspace", "exporter", "out", "audio-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--reviewer-group", required=True)
    args = parser.parse_args()
    from akousmata_app import editorial_grants
    from listeningstackweb.disclosure_policy import DisclosureError
    from listeningstackweb.store_snapshot import SnapshotSet
    from listeningstackweb.trace_export import CONTROL_STORES

    import listeningstackweb
    from listeningstackweb import audio_release
    for module in (listeningstackweb, editorial_grants):
        if not Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
            parser.error("Installed candidate required")
    source = args.candidate_workspace
    if not (source / "candidate-authorization-receipt.json").is_file():
        parser.error("Explicit candidate authorization receipt required")
    if (not args.out.is_absolute() or args.out.exists() or args.out.is_symlink()
            or not args.out.parent.is_dir() or args.out.resolve().is_relative_to(source.resolve())):
        parser.error("Fresh output outside source candidate required")
    export = runpy.run_path(str(args.exporter))["export_transaction"]
    args.out.mkdir(mode=0o700)
    workspace = args.out / "workspace"
    with SnapshotSet() as snapshots:
        for name, relative in {"akousmata": "akousmata/index.sqlite", **CONTROL_STORES}.items():
            snap = snapshots.add(name, source / relative)
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snap.path, target)
        receipt = snapshots.receipt()
    shutil.copyfile(source / "station/audio-releases.json", workspace / "station/audio-releases.json")
    kwargs = {"root": workspace / "akousmata", "workspace": workspace, "case_id": "withdrawal-qualification",
        "identifiers": [args.record], "audience": "editorial", "reviewer_group": args.reviewer_group,
        "station_root": workspace / "station", "audio_roots": (args.audio_root,), "include_media": True,
        "dry_run": True, "prepare_decision": True}
    before = export(**kwargs)["bundle"]
    asset = before["assets"][0]
    if not asset["media_included"]:
        raise ValueError("Positive baseline audio must resolve before withdrawal")
    prior = audio_release.AudioReleases.load(workspace / "station").find(asset["asset_id"], "editorial", args.record)
    audio_release.record_release(workspace / "station", asset_id=prior.asset_id, record_id=prior.record_id,
        audience=prior.audience, authorized_by="Candidate withdrawal qualification", basis="Technical withdrawal only in a fresh clone",
        content_sha256=prior.content_sha256, record_sha256=prior.record_sha256, expires_at=prior.expires_at, revoked=True)
    withdrawn = export(**kwargs)["bundle"]
    if withdrawn["assets"][0]["media_included"] or "revoked" not in withdrawn["assets"][0]["withheld_reason"]:
        raise ValueError("Audio withdrawal was not enforced")
    conn = sqlite3.connect(workspace / "akousmata/index.sqlite")
    conn.row_factory = sqlite3.Row
    owner = SimpleNamespace(conn=conn, get=lambda identifier: json.loads(conn.execute(
        "SELECT record FROM akousmata WHERE akousma_id=?", (identifier,)).fetchone()[0]))
    try:
        editorial_grants.revoke(owner, args.record, reviewer_group=args.reviewer_group,
            authorized_by="Candidate withdrawal qualification", basis="Technical metadata withdrawal only in a fresh clone")
    finally:
        conn.close()
    try:
        export(**kwargs)
    except DisclosureError as exc:
        if "private metadata grant is not current" not in str(exc):
            raise
    else:
        raise ValueError("Private metadata withdrawal must refuse the whole preview")
    report = {"contract": "centaur/editorial-withdrawal-qualification/v1", "status": "passed",
        "scope": "Candidate-only positive baseline, audio withheld, metadata withdrawal refuses export; not remote recall or Station host removal",
        "record_id": args.record, "asset_id": prior.asset_id, "content_sha256": prior.content_sha256,
        "source_snapshots": receipt, "baseline_included": True, "audio_withdrawn_reason": withdrawn["assets"][0]["withheld_reason"],
        "metadata_withdrawn_state": "export-refused", "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "scope": report["scope"], "output": str(args.out)}))


if __name__ == "__main__":
    main()
