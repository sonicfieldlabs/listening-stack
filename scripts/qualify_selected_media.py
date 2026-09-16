"""Bounded, read-only byte availability for explicitly selected publication cases.

Availability is not authorization, playback or perceptual validation. No audio
is copied, no grants are created, and private paths stay in a local report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def inspect(bundles, roots, resolve):
    report = {"contract": "centaur/selected-media-inventory/v1", "observed_at": datetime.now(UTC).isoformat(),
              "scope": "Byte availability only; no authorization, export, playback or perceptual claim", "cases": []}
    for path in bundles:
        raw = path.read_bytes()
        bundle = json.loads(raw)
        rows = []
        for asset in bundle["assets"]:
            located = resolve(asset.get("content_hash"))
            row = {"record_id": asset["account_id"], "asset_id": asset["asset_id"],
                   "content_hash": asset.get("content_hash"), "grant_state_in_bundle": asset.get("grant", {}).get("state"),
                   "status": "digest-verified-available" if located else "not-found-in-selected-roots"}
            if located:
                # A private local report, never a release input or path-based grant.
                row.update(bytes=located.stat().st_size, suffix=located.suffix,
                           root_index=next(i for i, root in enumerate(roots) if located.is_relative_to(root)),
                           relative_path=str(located.relative_to(next(root for root in roots if located.is_relative_to(root)))))
            rows.append(row)
        report["cases"].append({"case_id": bundle["case_id"], "bundle_sha256": hashlib.sha256(raw).hexdigest(), "assets": rows})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, action="append", required=True)
    parser.add_argument("--audio-root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import listeningstackweb.media_packaging as media
    if not Path(media.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        parser.error("Installed candidate required")
    if not args.out.is_absolute() or args.out.exists() or args.out.is_symlink() or not args.out.parent.is_dir():
        parser.error("Fresh absolute output with existing parent required")
    roots = tuple(args.audio_root)
    if any(not root.is_absolute() for root in roots):
        parser.error("Explicit absolute audio roots required")
    if any(args.out.resolve().is_relative_to(root.resolve()) for root in roots):
        parser.error("Output must not be inside an audio root")
    resolver = media.MediaResolver(roots)
    report = inspect(args.bundle, roots, resolver.resolve)
    report["scanned_entries"] = resolver.scanned
    report["media_resolver_sha256"] = hashlib.sha256(Path(media.__file__).read_bytes()).hexdigest()
    report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.out.open("x") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.out), "cases": [{"case_id": c["case_id"], "assets": len(c["assets"]),
        "available": sum(a["status"] == "digest-verified-available" for a in c["assets"])} for c in report["cases"]]}))


if __name__ == "__main__":
    main()
