"""Bind freshly built application wheels, selected dependencies and all wheel resources.

This creates an unpublished install input, not a qualification certificate.
"""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from listening_stack.candidate import CONTRACT, PHASE17, verify


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assemble(build: Path, output: Path):
    if output.exists():
        raise ValueError("Fresh output required")
    selection = json.loads((build / "selection.json").read_text())
    expected = dict(PHASE17)
    for requirement in selection["selected_dependencies"]:
        name, version = requirement.split("==")
        expected[re.sub(r"[-_.]+", "-", name).lower()] = version
    sources = sorted((build / "application-wheels").glob("*.whl")) + sorted((build / "dependency-wheels").glob("*.whl"))
    wheels, resources, actual = [], {}, {}
    for source in sources:
        if source.is_symlink():
            raise ValueError("Wheel symlink refused")
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):
                raise ValueError("Unsafe or duplicate wheel member")
            metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise ValueError("Expected one wheel metadata file")
            info = BytesParser().parsebytes(archive.read(metadata[0]))
            name = re.sub(r"[-_.]+", "-", info["Name"]).lower()
            if name in actual:
                raise ValueError("Duplicate distribution: " + name)
            actual[name] = info["Version"]
            resources[name] = [{"path": member, "sha256": digest(archive.read(member)), "bytes": archive.getinfo(member).file_size}
                               for member in sorted(names) if not member.endswith("/")]
            wheels.append({"file": source.name, "distribution": name, "version": info["Version"],
                           "sha256": digest(source.read_bytes())})
    if actual != expected:
        raise ValueError("Wheel set does not match selected applications and dependencies: " +
                         str({name: (expected.get(name), actual.get(name)) for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name)}))
    output.mkdir(parents=True)
    for source in sources:
        shutil.copy2(source, output / source.name)
    resource_bytes = (json.dumps(resources, indent=2) + "\n").encode()
    (output / "wheel-resources.json").write_bytes(resource_bytes)
    source_bytes = (build / "source-inventory.json").read_bytes()
    (output / "source-inventory.json").write_bytes(source_bytes)
    manifest = {"contract": CONTRACT, "published": False, "compatibility_profile": "centaur-phase17/v1",
                "host": {"python": "3.12", "platform": "macOS arm64"}, "wheels": wheels,
                "source_inventory_sha256": digest(source_bytes), "wheel_resources_sha256": digest(resource_bytes),
                "selection_sha256": digest((build / "selection.json").read_bytes()),
                "qualification": "not claimed; fresh isolated install and tests required"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify(output / "manifest.json")
    print(json.dumps({"status": "unpublished-install-input", "wheels": len(wheels),
                      "wheel_members": sum(len(rows) for rows in resources.values()),
                      "manifest_sha256": digest((output / "manifest.json").read_bytes())}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assemble(args.build.resolve(), args.output.resolve())
