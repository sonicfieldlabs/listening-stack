"""Snapshot current owner sources into a fresh private candidate build directory.

No installs, service changes, model calls, release promotion or implicit cleanup.
The historical dependency register is a selection input, not fresh qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

OWNERS = ("listening-stack", "oida", "akouo", "earworm", "akousmata", "germ", "listeningstackweb")
APPLICATIONS = {"sonicfield-listening-stack", "sonicfield-oida", "akouo-contract", "akousma", "akousmata", "germ", "listeningstackweb"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def prepare(root: Path, output: Path, register: Path, owners=OWNERS):
    root, output = root.resolve(), output.resolve()
    if output.exists() or any(output.is_relative_to(root / owner) for owner in (*OWNERS, "masa", "cosmoaudition", "auditumswe")):
        raise ValueError("Fresh destination outside owner checkouts required")
    register_bytes = register.read_bytes()
    dependencies = json.loads(register_bytes)["dependencies"]
    output.mkdir(parents=True)
    inventory = {}
    for owner in owners:
        source = root / owner
        destination = output / "sources" / owner
        before = git(source, "diff", "HEAD", "--binary")
        paths = sorted(set(git(source, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""})
        files = []
        for encoded in paths:
            relative = Path(encoded.decode())
            if relative.name == ".DS_Store":
                continue
            path = source / relative
            if not path.exists():  # A tracked deletion is represented in the diff.
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Review non-regular source input: {owner}/{relative}")
            data = path.read_bytes()
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(path.stat().st_mode & 0o777)
            files.append({"path": relative.as_posix(), "bytes": len(data), "sha256": sha(data)})
        if git(source, "diff", "HEAD", "--binary") != before:
            raise ValueError(f"Tracked source changed during snapshot: {owner}")
        inventory[owner] = {"head": git(source, "rev-parse", "HEAD").decode().strip(),
                            "tracked_diff_sha256": sha(before), "files": files,
                            "source_fingerprint": sha(json.dumps(files, sort_keys=True).encode())}
    (output / "source-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    selected = sorted(f"{item['name']}=={item['version']}" for item in dependencies if item["name"].lower() not in APPLICATIONS)
    (output / "dependencies.in").write_text("\n".join(selected) + "\n")
    (output / "selection.json").write_text(json.dumps({
        "profile": "centaur-phase17/v1", "published": False, "status": "source-snapshot-only",
        "dependency_register_sha256": sha(register_bytes), "selected_dependencies": selected,
        "limits": ["No fresh runtime or model qualification", "Central web assets must be rebuilt in the snapshot",
                   "Dependency wheels and complete installed resource identity still required"],
    }, indent=2) + "\n")
    print(json.dumps({"status": "source-snapshot-only", "owners": len(inventory),
                      "files": sum(len(item["files"]) for item in inventory.values()), "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dependency-register", type=Path, required=True)
    parser.add_argument("--owners", nargs="+", choices=(*OWNERS, "masa", "cosmoaudition", "auditumswe"), default=OWNERS)
    args = parser.parse_args()
    prepare(args.root, args.output, args.dependency_register, tuple(dict.fromkeys(args.owners)))
