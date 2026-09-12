"""Verify and install a complete local wheel set without rewriting release pins."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
from email.parser import BytesParser

CONTRACT = "listening-stack/candidate-set/v1"
PHASE5 = {
    "sonicfield-oida": "0.11.1",
    "akousma": "0.8.1",
    "akousmata": "0.8.1",
    "akouo-contract": "0.10.0",
    "germ": "0.6.0",
    "listeningstackweb": "0.1.0",
    "sonicfield-listening-stack": "0.4.1",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest):
    manifest = Path(manifest).resolve()
    if manifest.stat().st_size > 1024 * 1024:
        raise ValueError("Oversized candidate manifest")
    value = json.loads(manifest.read_text())
    if value.get("contract") != CONTRACT or value.get("published") is not False:
        raise ValueError("Expected an explicitly unpublished candidate set")
    wheels = value.get("wheels")
    if not isinstance(wheels, list) or not 1 <= len(wheels) <= 200:
        raise ValueError("Expected 1–200 pinned wheels")
    names, distributions = set(), set()
    for item in wheels:
        name = item["file"]
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name) or name in names:
            raise ValueError("Unsafe or duplicate wheel name")
        names.add(name)
        path = manifest.parent / name
        if path.is_symlink() or not path.is_file() or digest(path) != item["sha256"]:
            raise ValueError("Wheel checksum mismatch: " + name)
        with zipfile.ZipFile(path) as archive:
            metadata = [
                n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
            ]
            if (
                len(metadata) != 1
                or archive.getinfo(metadata[0]).file_size > 1024 * 1024
            ):
                raise ValueError("Invalid wheel metadata")
            info = BytesParser().parsebytes(archive.read(metadata[0]))
        normalized = re.sub(r"[-_.]+", "-", info["Name"]).lower()
        if (
            normalized in distributions
            or normalized != item["distribution"]
            or info["Version"] != item["version"]
        ):
            raise ValueError("Duplicate or mismatched distribution")
        distributions.add(normalized)
    if (
        not {
            "sonicfield-oida",
            "akousma",
            "akousmata",
            "akouo-contract",
            "sonicfield-listening-stack",
            "listeningstackweb",
        }
        <= distributions
    ):
        raise ValueError("Candidate is missing a required core or application wheel")
    profile = value.get("compatibility_profile")
    if profile is not None:
        if profile != "centaur-phase5/v1":
            raise ValueError("Unknown candidate compatibility profile")
        actual = {item["distribution"]: item["version"] for item in wheels}
        if any(actual.get(name) != version for name, version in PHASE5.items()):
            raise ValueError(
                "Phase 5 requires the qualified GERM and listening contract versions"
            )
    return value


def install(manifest, root, python="3.13"):
    manifest, root = Path(manifest).resolve(), Path(root).resolve()
    value = verify(manifest)  # Verify all bytes before creating or executing anything.
    if root.exists():
        raise ValueError(
            "Choose a new candidate root; existing environments are preserved"
        )
    root.mkdir(parents=True)
    subprocess.run(
        [
            "uv",
            "venv",
            "--no-python-downloads",
            "--python",
            python,
            str(root / ".venv"),
        ],
        check=True,
    )
    executable = root / ".venv/bin/python"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(executable),
            "--offline",
            "--no-index",
            "--no-deps",
            *[str(manifest.parent / w["file"]) for w in value["wheels"]],
        ],
        check=True,
    )
    subprocess.run(["uv", "pip", "check", "--python", str(executable)], check=True)
    receipt = {
        "contract": CONTRACT,
        "manifest_sha256": digest(manifest),
        "wheels": value["wheels"],
        "compatibility_profile": value.get("compatibility_profile"),
        "mode": "isolated-candidate",
        "managed_source_install": False,
        "memory_migration": "not_requested",
        "services_started": False,
    }
    (root / "candidate-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return doctor(root)


def doctor(root):
    root = Path(root).resolve()
    receipt = json.loads((root / "candidate-receipt.json").read_text())
    if receipt.get("contract") != CONTRACT:
        raise ValueError("Invalid candidate receipt")
    script = """import importlib, importlib.metadata, json, sys, hashlib, base64
from pathlib import Path
expected=json.loads(sys.argv[1]); prefix=Path(sys.prefix).resolve()
for item in expected:
 d=importlib.metadata.distribution(item['distribution'])
 assert d.version==item['version'], item['distribution']
 assert prefix in Path(d.locate_file('')).resolve().parents, item['distribution']
 for file in d.files or []:
  if file.hash:
   actual=base64.urlsafe_b64encode(hashlib.new(file.hash.mode,Path(d.locate_file(file)).read_bytes()).digest()).rstrip(b'=').decode()
   assert actual==file.hash.value, str(file)
modules=['oida','akousma','akousmata_app','akouo_contract','listening_stack','listeningstackweb']
if any(item['distribution']=='germ' for item in expected): modules.append('server.identity')
for name in modules:
 m=importlib.import_module(name);assert prefix in Path(m.__file__).resolve().parents,name
print(json.dumps({'isolated_imports':True,'installed_record_hashes':True,'distribution_count':len(expected)}))
"""
    result = subprocess.run(
        [
            str(root / ".venv/bin/python"),
            "-I",
            "-c",
            script,
            json.dumps(receipt["wheels"]),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=root,
    )
    return {
        **json.loads(result.stdout),
        "mode": "isolated-candidate",
        "managed_source_install": False,
        "model_and_host_qualification": "not_claimed",
        "manifest_sha256": receipt["manifest_sha256"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("manifest", type=Path)
    run = sub.add_parser("install")
    run.add_argument("manifest", type=Path)
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--python", default="3.13")
    status = sub.add_parser("doctor")
    status.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        value = verify(args.manifest)
        result = {"verified_wheels": len(value["wheels"]), "published": False}
    elif args.command == "install":
        result = install(args.manifest, args.root, args.python)
    else:
        result = doctor(args.root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
