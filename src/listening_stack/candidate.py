"""Verify and install unpublished public component wheels in a fresh environment."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

CONTRACT = "listening-stack/candidate-set/v1"
CORE = {
    "sonicfield-oida": "0.12.0", "akousma": "0.8.4", "akousmata": "0.8.3",
    "akouo-contract": "0.10.1", "sonicfield-listening-stack": "0.5.1",
}
FULL = {**CORE, "germ": "0.7.0"}
PROFILES = {"listening-stack-core/v1": CORE, "listening-stack-full/v1": FULL}
APPLICATIONS = frozenset(FULL)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def wheel_identity(path):
    """Read bounded metadata after checking every archive member path."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
            or "\\" in name or "\x00" in name
            or (archive.getinfo(name).external_attr >> 16) & 0o170000 == 0o120000
            for name in names
        ):
            raise ValueError("Unsafe or duplicate wheel member")
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1 or archive.getinfo(metadata[0]).file_size > 1024 * 1024:
            raise ValueError("Invalid wheel metadata")
        info = BytesParser().parsebytes(archive.read(metadata[0]))
        if not info["Name"] or not info["Version"]:
            raise ValueError("Missing wheel identity")
        return {"distribution": re.sub(r"[-_.]+", "-", info["Name"]).lower(),
                "version": info["Version"], "requires_python": info.get("Requires-Python")}


def verify(manifest):
    manifest = Path(manifest)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1024 * 1024:
        raise ValueError("Expected a bounded regular candidate manifest")
    value = json.loads(manifest.read_text())
    if "source_inventory_sha256" in value:
        inventory = manifest.parent / "source-inventory.json"
        if inventory.is_symlink() or not inventory.is_file() or digest(inventory) != value["source_inventory_sha256"]:
            raise ValueError("Source inventory changed")
    return verify_value(value, manifest.parent)


def verify_value(value, wheel_dir):
    """Preflight an in-memory selection against its original wheel directory."""
    if value.get("contract") != CONTRACT or value.get("published") is not False:
        raise ValueError("Expected an explicitly unpublished candidate set")
    profile = value.get("compatibility_profile")
    if profile not in PROFILES:
        raise ValueError("Unknown candidate compatibility profile")
    wheels = value.get("wheels")
    if not isinstance(wheels, list) or not 1 <= len(wheels) <= 200:
        raise ValueError("Expected 1–200 pinned wheels")
    names, actual = set(), {}
    for item in wheels:
        name = item.get("file", "")
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name) or name in names:
            raise ValueError("Unsafe or duplicate wheel name")
        names.add(name)
        path = Path(wheel_dir) / name
        if path.is_symlink() or not path.is_file() or digest(path) != item.get("sha256"):
            raise ValueError("Wheel checksum mismatch: " + name)
        identity = wheel_identity(path)
        distribution = identity["distribution"]
        if distribution in actual or any(identity[key] != item.get(key) for key in ("distribution", "version")):
            raise ValueError("Duplicate or mismatched distribution")
        if distribution.startswith("sonicfield-") and distribution not in APPLICATIONS:
            raise ValueError("Unreviewed application wheel")
        actual[distribution] = identity["version"]
    required = PROFILES[profile]
    if any(actual.get(name) != version for name, version in required.items()) or set(actual) & APPLICATIONS != set(required):
        raise ValueError("Candidate profile requires its exact declared component versions")
    return value


def selected_environment(root, include_germ=False):
    """Do not inherit provider credentials, owner stores, or import overrides."""
    root = Path(root).resolve()
    environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "UV_CACHE_DIR") if key in os.environ}
    environment.update({
        "HOME": str(root / "state/home"), "XDG_CACHE_HOME": str(root / "state/cache"),
        "XDG_CONFIG_HOME": str(root / "state/config"),
        "XDG_DATA_HOME": str(root / "state/data"),
        "AKOUSMATA_PATH": str(root / "state/akousmata"), "AKOUSMATA_WATCHER": "0",
        "OIDA_DATA_DIR": str(root / "state/oida"), "OIDA_AUDIO_DIR": str(root / "state/audio"),
        "OIDA_MOSS_PREWARM": "0", "OIDA_JOBS_WORKER": "0",
        "LISTENINGSTACK_RESOURCE_DIR": str(root / "state/resources"),
        "HF_HOME": str(root / "state/huggingface"),
        "HF_HUB_OFFLINE": "1", "UV_NO_CONFIG": "1", "UV_PYTHON_DOWNLOADS": "never",
    })
    if include_germ:
        environment.update({"GERM_OUTPUT_DIR": str(root / "state/germ"), "GERM_ACTIVE_PROVIDER": "mock"})
    return environment


def install(manifest, root, python="3.12"):
    manifest, root = Path(manifest).absolute(), Path(root).absolute()
    value = verify(manifest)
    if root.exists() or root.is_symlink():
        raise ValueError("Choose a new candidate root; existing environments are preserved")
    root, manifest = root.resolve(), manifest.resolve()
    if root.is_relative_to(manifest.parent) or manifest.parent.is_relative_to(root):
        raise ValueError("Candidate root must be separate from its wheel bundle")
    if any((parent / ".git").exists() for parent in root.parents):
        raise ValueError("Candidate root must be outside source checkouts")
    # Resolve the existing interpreter before replacing HOME. uv's managed
    # interpreter inventory otherwise moves to the empty candidate HOME.
    lookup = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "UV_PYTHON_INSTALL_DIR") if key in os.environ}
    lookup.update({"HOME": str(Path.home()), "UV_NO_CONFIG": "1", "UV_PYTHON_DOWNLOADS": "never"})
    interpreter = subprocess.run(["uv", "python", "find", "--no-python-downloads", python],
                                 check=True, env=lookup, capture_output=True, text=True).stdout.strip()
    subprocess.run([interpreter, "-I", "-c", "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer required'"],
                   check=True, env=lookup, capture_output=True, text=True)
    root.mkdir(parents=True, mode=0o700)
    environment = selected_environment(root, include_germ="germ" in PROFILES[value["compatibility_profile"]])
    for name in ("home", "cache", "config"):
        (root / "state" / name).mkdir(parents=True, mode=0o700)
    subprocess.run(["uv", "venv", "--no-python-downloads", "--python", interpreter, str(root / ".venv")],
                   check=True, env=environment)
    executable = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    subprocess.run(["uv", "pip", "install", "--python", str(executable), "--offline", "--no-index", "--no-deps",
                    *[str(manifest.parent / item["file"]) for item in value["wheels"]]], check=True, env=environment)
    subprocess.run(["uv", "pip", "check", "--python", str(executable)], check=True, env=environment)
    receipt = {"contract": CONTRACT, "manifest": str(manifest), "manifest_sha256": digest(manifest),
               "wheels": value["wheels"], "compatibility_profile": value["compatibility_profile"],
               "mode": "isolated-candidate", "managed_source_install": False,
               "memory_migration": "not_requested", "services_started": False}
    path = root / "candidate-receipt.json"
    with path.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)
    return doctor(root)


def doctor(root):
    root = Path(root).resolve()
    receipt = json.loads((root / "candidate-receipt.json").read_text())
    if receipt.get("contract") != CONTRACT:
        raise ValueError("Invalid candidate receipt")
    manifest = Path(receipt["manifest"])
    if digest(manifest) != receipt["manifest_sha256"]:
        raise ValueError("Candidate manifest changed")
    value = verify(manifest)
    if value["wheels"] != receipt["wheels"] or value["compatibility_profile"] != receipt["compatibility_profile"]:
        raise ValueError("Candidate receipt differs from its manifest")
    script = r'''import importlib, importlib.metadata, json, sys, hashlib, zipfile
from pathlib import Path
expected=json.loads(sys.argv[1]); bundle=Path(sys.argv[2]); owners=set(json.loads(sys.argv[3]))
prefix=Path(sys.prefix).resolve(); checked=0
for item in expected:
 d=importlib.metadata.distribution(item['distribution'])
 assert d.version==item['version'], item['distribution']
 assert Path(d.locate_file('')).resolve().is_relative_to(prefix), item['distribution']
 if item['distribution'] not in owners: continue
 with zipfile.ZipFile(bundle/item['file']) as archive:
  for name in archive.namelist():
   if name.endswith('/') or name.endswith('.dist-info/RECORD'): continue
   assert '.data/' not in name, name
   path=Path(d.locate_file(name)).resolve()
   assert path.is_relative_to(prefix) and path.is_file(), name
   assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(archive.read(name)).digest(), name
   checked+=1
modules=['oida','akousma','akousmata_app','akouo_contract','listening_stack']
if 'germ' in owners: modules.append('server.identity')
for name in modules:
 m=importlib.import_module(name); assert Path(m.__file__).resolve().is_relative_to(prefix), name
print(json.dumps({'isolated_imports':True,'pinned_owner_bytes':True,'owner_payload_files':checked,
                  'distribution_count':len(expected),'python':sys.version.split()[0],
                  'platform':sys.platform}))
'''
    executable = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    environment = selected_environment(root, include_germ="germ" in PROFILES[value["compatibility_profile"]])
    subprocess.run(["uv", "pip", "check", "--python", str(executable)], check=True, env=environment,
                   capture_output=True, text=True)
    result = subprocess.run([str(executable), "-I", "-c", script, json.dumps(value["wheels"]),
                             str(manifest.parent), json.dumps(sorted(PROFILES[value["compatibility_profile"]]))],
                            capture_output=True, text=True, check=True, cwd=root, env=environment)
    return {**json.loads(result.stdout), "mode": "isolated-candidate", "managed_source_install": False,
            "status": "artifact-qualified", "publication": "waiting-for-published-refs",
            "compatibility_profile": value["compatibility_profile"],
            "model_and_host_qualification": "not_claimed", "manifest_sha256": receipt["manifest_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("manifest", type=Path)
    run = sub.add_parser("install")
    run.add_argument("manifest", type=Path)
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--python", default="3.12")
    status = sub.add_parser("doctor")
    status.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        value = verify(args.manifest)
        result = {"verified_wheels": len(value["wheels"]), "published": False, "status": "source-ready",
                  "publication": "waiting-for-published-refs"}
    elif args.command == "install":
        result = install(args.manifest, args.root, args.python)
    else:
        result = doctor(args.root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
