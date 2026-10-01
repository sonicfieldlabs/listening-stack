"""Snapshot selected public owner sources after preflighting the entire selection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

OWNERS = ("listening-stack", "oida", "akouo", "earworm", "akousmata", "germ", "MASA", "cosmoaudition")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                                    "-C", str(source), *args],
                                   env=dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0"))


def inspect(source):
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Missing or non-regular owner: " + source.name)
    if Path(os.fsdecode(git(source, "rev-parse", "--show-toplevel")).strip()).resolve() != source.resolve():
        raise ValueError("Owner must have its own Git root: " + source.name)
    paths = sorted(set(git(source, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""})
    files, deleted = {}, []
    for encoded in paths:
        relative = Path(os.fsdecode(encoded))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source path")
        path = source / relative
        if relative.name == ".DS_Store":
            continue
        if path.is_symlink() or (path.exists() and not path.is_file()) or not path.resolve().is_relative_to(source.resolve()):
            raise ValueError("Review non-regular source input: " + str(relative))
        if not path.exists():
            deleted.append(relative.as_posix())
            continue
        files[relative.as_posix()] = {"sha256": sha(path.read_bytes()), "mode": path.stat().st_mode & 0o777}
    return {"base_commit": git(source, "rev-parse", "HEAD").decode().strip(),
            "tracked_diff_sha256": sha(git(source, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv")),
            "files": files, "deleted": deleted,
            "source_inputs_sha256": sha(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()),
            "candidate_commit": None}


def prepare(root, output, owners=OWNERS):
    root, output = Path(root).resolve(), Path(output).absolute()
    owners = tuple(owners)
    if not owners or len(set(owners)) != len(owners) or any(owner not in OWNERS for owner in owners):
        raise ValueError("Choose distinct supported public owners")
    if output.exists() or output.is_symlink() or any(output.resolve().is_relative_to(root / owner) for owner in OWNERS):
        raise ValueError("Fresh destination outside owner checkouts required")
    if any((parent / ".git").exists() for parent in output.resolve().parents):
        raise ValueError("Fresh destination outside owner checkouts required")
    # Check every owner before creating output or copying the first source file.
    inventory = {owner: inspect(root / owner) for owner in owners}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".candidate-snapshot-", dir=output.parent))
    try:
        for owner, item in inventory.items():
            for relative, identity in item["files"].items():
                path = root / owner / relative
                data = path.read_bytes()
                if path.is_symlink() or sha(data) != identity["sha256"]:
                    raise ValueError("Source changed during snapshot")
                target = staging / "sources" / owner / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(identity["mode"])
        if any(inspect(root / owner) != inventory[owner] for owner in owners):
            raise ValueError("Source changed during snapshot")
        (staging / "source-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        (staging / "selection.json").write_text(json.dumps({
            "contract": "listening-stack/source-selection/v1", "published": False,
            "status": "source-ready", "owners": list(owners),
            "source_inventory_sha256": sha((staging / "source-inventory.json").read_bytes()),
            "limits": ["No runtime qualification", "No published candidate refs", "No Git history copied"],
        }, indent=2) + "\n")
        output.mkdir(mode=0o700)
        for path in staging.iterdir():
            path.rename(output / path.name)
    finally:
        shutil.rmtree(staging)
    return {"status": "source-ready", "owners": len(inventory), "published": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owners", nargs="+", choices=OWNERS, default=OWNERS)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output, args.owners)))
