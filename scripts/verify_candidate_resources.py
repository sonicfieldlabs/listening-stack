"""Compare installed public owner resources directly with pinned wheel bytes."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import sys
import zipfile

from listening_stack.candidate import PROFILES, digest, verify


def check(manifest):
    manifest = Path(manifest)
    value = verify(manifest)
    applications = set(PROFILES[value["compatibility_profile"]])
    prefix = Path(sys.prefix).resolve()
    result = {}
    for wheel in value["wheels"]:
        name = wheel["distribution"]
        if name not in applications:
            continue
        dist = distribution(name)
        if dist.version != wheel["version"]:
            raise ValueError("Wrong installed version: " + name)
        count = non_python = 0
        with zipfile.ZipFile(manifest.parent / wheel["file"]) as archive:
            for member in archive.namelist():
                if member.endswith("/") or member.endswith(".dist-info/RECORD"):
                    continue
                if ".data/" in member:
                    raise ValueError("Review application wheel relocation: " + member)
                installed = Path(dist.locate_file(member)).resolve()
                if not installed.is_relative_to(prefix) or not installed.is_file() or (
                    digest(installed) != hashlib.sha256(archive.read(member)).hexdigest()
                ):
                    raise ValueError("Installed resource differs from pinned wheel: " + member)
                count += 1
                non_python += not member.endswith(".py")
        result[name] = {"version": dist.version, "wheel_sha256": wheel["sha256"],
                        "checked_files": count, "non_python_files": non_python}
    return {"status": "passed", "scope": "installed owner bytes; model inference not tested",
            "manifest_sha256": digest(manifest), "applications": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.manifest)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
