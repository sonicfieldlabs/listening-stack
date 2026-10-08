"""Assemble an unpublished offline public wheel bundle with source identities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from listening_stack.candidate import CONTRACT, PROFILES, digest, verify, verify_value, wheel_identity
from prepare_local_candidate import OWNERS


def build(wheel_dir, output, profile, source_inventory):
    wheel_dir, output = Path(wheel_dir).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Fresh output required")
    if any((parent / ".git").exists() for parent in output.resolve().parents):
        raise ValueError("Candidate output must be outside source checkouts")
    if output.resolve().is_relative_to(wheel_dir) or wheel_dir.is_relative_to(output.resolve()):
        raise ValueError("Wheel inputs and output must be separate")
    if profile not in PROFILES:
        raise ValueError("Unknown candidate compatibility profile")
    source_inventory = Path(source_inventory)
    if source_inventory.is_symlink() or not source_inventory.is_file():
        raise ValueError("Expected a regular source inventory")
    inventory_bytes = source_inventory.read_bytes()
    inventory = json.loads(inventory_bytes)
    if not inventory or any(owner not in OWNERS for owner in inventory):
        raise ValueError("Expected public owner source identities")
    if any(not item.get("base_commit") or not item.get("source_inputs_sha256") for item in inventory.values()):
        raise ValueError("Missing source identity")
    sources = sorted(wheel_dir.glob("*.whl"))
    wheels = []
    for source in sources:
        if source.is_symlink() or not source.is_file():
            raise ValueError("Wheel symlinks are refused")
        wheels.append({"file": source.name, "sha256": digest(source), **wheel_identity(source)})
    manifest = {
        "contract": CONTRACT, "published": False, "compatibility_profile": profile,
        "wheels": wheels, "source_inventory_sha256": digest(source_inventory),
        "status": "source-ready", "installed_artifact_qualification": "pending",
        "publication": {"status": "waiting-for-published-refs", "released_profile_changed": False,
                        "candidate_commits": "pending", "immutable_remote_refs": "pending"},
        "runtime": {"python": ">=3.12", "uv": "preinstalled; no interpreter downloads",
                    "platform": "wheel tags must match the selected interpreter and host",
                    "models": "not installed", "services": "not started"},
    }
    verify_value(manifest, wheel_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".candidate-wheels-", dir=output.parent))
    try:
        for source, item in zip(sources, wheels):
            target = staging / source.name
            shutil.copyfile(source, target)
            if digest(target) != item["sha256"]:
                raise ValueError("Wheel changed during assembly")
        (staging / "source-inventory.json").write_bytes(inventory_bytes)
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        verify(staging / "manifest.json")
        output.mkdir(mode=0o700)
        for path in staging.iterdir():
            path.rename(output / path.name)
    finally:
        shutil.rmtree(staging)
    return {"status": "source-ready", "published": False, "wheels": len(wheels),
            "manifest_sha256": digest(output / "manifest.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--source-inventory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.wheel_dir, args.output, args.profile, args.source_inventory)))
