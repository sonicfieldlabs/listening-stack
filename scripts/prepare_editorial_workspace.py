"""Clone owner stores read-only, then authorize exact selected records only in the clone.

Explicit owner delegation, record digests and expiry are required. This does not
override absent consent, mutate historical records, copy audio, publish or send.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace", "bundle", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("reviewer-group", "authorized-by", "basis", "expires-at"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--record", action="append", required=True)
    args = parser.parse_args()
    from akousmata_app import editorial_grants, exports
    from listeningstackweb.export_safety import digest
    from listeningstackweb.store_snapshot import SnapshotSet
    from listeningstackweb.trace_export import CONTROL_STORES

    from listeningstackweb import audio_release
    for module in (editorial_grants, audio_release):
        if not Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
            parser.error("Installed candidate required")
    if (not args.out.is_absolute() or args.out.exists() or args.out.is_symlink()
            or not args.out.parent.is_dir() or args.out.resolve().is_relative_to(args.workspace.resolve())):
        parser.error("Fresh absolute output outside the source workspace required")
    raw = args.bundle.read_bytes()
    bundle = json.loads(raw)
    approved = bundle["disclosure"]["decision"]["scope"]["records"]
    identifiers = sorted(set(args.record))
    if len(identifiers) != len(args.record) or any(i not in approved for i in identifiers):
        parser.error("Distinct records from the explicitly scoped bundle required")
    source_stores = {"akousmata": "akousmata/index.sqlite", **CONTROL_STORES}
    with SnapshotSet() as snapshots:
        for name, relative in source_stores.items():
            snapshots.add(name, args.workspace / relative)
        snapshots.require_join_window(60)
        conn = snapshots.snapshots["akousmata"].connect()
        try:
            records = []
            for identifier in identifiers:
                row = conn.execute("SELECT record FROM akousmata WHERE akousma_id=?", (identifier,)).fetchone()
                record = json.loads(row[0]) if row else None
                if record is None or digest(record) != approved[identifier]:
                    raise ValueError("Selected record differs from approved source bytes")
                if not exports.exportable(record)[0]:
                    raise ValueError("Selected record requires owner consent review; no historical consent override")
                records.append(record)
        finally:
            conn.close()
        args.out.mkdir(mode=0o700)
        for name, relative in source_stores.items():
            target = args.out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshots.snapshots[name].path, target)
        report = {"contract": "centaur/editorial-candidate-workspace/v1", "scope": "Candidate-only authorizations; no live writes, audio copying or delivery",
                  "bundle_sha256": hashlib.sha256(raw).hexdigest(), "source_snapshots": snapshots.receipt(), "decisions": []}
    conn = sqlite3.connect(args.out / "akousmata/index.sqlite")
    conn.row_factory = sqlite3.Row
    def get(identifier):
        row = conn.execute("SELECT record FROM akousmata WHERE akousma_id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None
    owner = SimpleNamespace(conn=conn, get=get)
    try:
        for record in records:
            identifier = record["akousma_id"]
            metadata = editorial_grants.grant(owner, identifier, reviewer_group=args.reviewer_group,
                expected_record_sha256=approved[identifier], authorized_by=args.authorized_by,
                basis=args.basis, expires_at=args.expires_at)
            audio = record.get("audio") or {}
            from listeningstackweb.media_packaging import normalise_hash
            release = audio_release.record_release(args.out / "station", asset_id=audio["asset_id"],
                record_id=identifier, audience="editorial", authorized_by=args.authorized_by, basis=args.basis,
                content_sha256=normalise_hash(audio.get("content_hash")), record_sha256=approved[identifier],
                expires_at=args.expires_at, source_terms="Stored consent classification retained; operator private-review authorization is not independent rights clearance")
            if digest(get(identifier)) != approved[identifier]:
                raise ValueError("Candidate authorization unexpectedly changed source record")
            report["decisions"].append({"record_id": identifier, "metadata": metadata, "audio": release.as_dict()})
    finally:
        conn.close()
    report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.out / "candidate-authorization-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "candidate-authorized-not-exported", "records": len(records), "output": str(args.out)}))


if __name__ == "__main__":
    main()
