"""Compare installed application bytes directly to the pinned wheel inventory.

Run with candidate Python -I. Installed RECORD is checked by candidate doctor;
this independent check does not use that mutable RECORD as its byte authority.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import sys

APPLICATIONS = {"sonicfield-listening-stack", "sonicfield-oida", "akouo-contract", "akousma", "akousmata", "germ", "listeningstackweb"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest: Path):
    value = json.loads(manifest.read_text())
    if value.get("published") is not False or value.get("compatibility_profile") != "centaur-phase17/v1":
        raise ValueError("Expected unpublished Phase 17 manifest")
    resources = manifest.parent / "wheel-resources.json"
    if digest(resources) != value["wheel_resources_sha256"]:
        raise ValueError("Resource inventory changed")
    inventory = json.loads(resources.read_text())
    prefix = Path(sys.prefix).resolve()
    result = {}
    for wheel in value["wheels"]:
        name = wheel["distribution"]
        if name not in APPLICATIONS:
            continue
        if digest(manifest.parent / wheel["file"]) != wheel["sha256"]:
            raise ValueError("Pinned wheel changed: " + name)
        dist = distribution(name)
        if dist.version != wheel["version"]:
            raise ValueError("Wrong installed version: " + name)
        count = non_python = 0
        for resource in inventory[name]:
            member = resource["path"]
            if member.endswith(".dist-info/RECORD"):
                continue  # Installer rewrites RECORD; not a source authority here.
            if ".data/" in member:
                raise ValueError("Review application wheel relocation: " + member)
            installed = Path(dist.locate_file(member)).resolve()
            if not installed.is_relative_to(prefix) or not installed.is_file() or digest(installed) != resource["sha256"]:
                raise ValueError("Installed resource differs from pinned wheel: " + member)
            count += 1
            non_python += not member.endswith(".py")
        result[name] = {"version": dist.version, "wheel_sha256": wheel["sha256"],
                        "checked_files": count, "non_python_files": non_python}
    if set(result) != APPLICATIONS:
        raise ValueError("Missing application resource inventory")
    return {"status": "passed", "scope": "installed application bytes, not model inference",
            "manifest_sha256": digest(manifest), "applications": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.manifest)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
