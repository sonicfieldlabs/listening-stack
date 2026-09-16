"""Read-only metadata inventory. Equal-size candidates are not proven duplicates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from collections import defaultdict
from pathlib import Path

SUFFIXES = {".safetensors", ".bin", ".pt", ".pth", ".onnx", ".ts", ".npz", ".ckpt"}


def inventory(roots, *, hash_contents=False):
    rows, identities = [], defaultdict(list)
    excluded_files = []
    candidates = defaultdict(list)
    content_groups = defaultdict(list)
    excluded = {".venv", "__pycache__", "node_modules", ".git", "blobs"}
    for label, root in roots.items():
        root = root.resolve()
        if not root.is_dir():
            raise ValueError(f"Missing selected root: {label}")
        for directory, folders, files in os.walk(root, followlinks=False):
            folders[:] = sorted(name for name in folders if name not in excluded)
            for name in sorted(files):
                path = Path(directory) / name
                if path.suffix.lower() not in SUFFIXES:
                    continue
                ref = label + "/" + path.relative_to(root).as_posix()
                # .ts also means TypeScript. Only admit the TorchScript archive
                # structure here, without loading or executing a model.
                if path.suffix.lower() == ".ts":
                    try:
                        with zipfile.ZipFile(path) as archive:
                            members = archive.namelist()
                            torchscript = any(n.endswith("/data.pkl") or n == "data.pkl" for n in members) and any(n.endswith("/constants.pkl") or n == "constants.pkl" for n in members)
                    except (OSError, zipfile.BadZipFile):
                        torchscript = False
                    if not torchscript:
                        excluded_files.append({"ref": ref, "reason": "Not a recognized TorchScript archive; .ts may be source code"})
                        continue
                try:
                    stat = path.stat()
                except OSError:
                    rows.append({"ref": ref, "status": "unreadable", "symlink": path.is_symlink()})
                    continue
                if not path.is_file():
                    continue
                digest = None
                if hash_contents:
                    value = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            value.update(chunk)
                    after = path.stat()
                    if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                        raise ValueError(f"Artifact changed during hashing: {ref}")
                    digest = value.hexdigest()
                    content_groups[digest].append(ref)
                rows.append({"ref": ref, "status": "content_hashed" if hash_contents else "observed_metadata_only", "bytes": stat.st_size,
                             "symlink": path.is_symlink(), "content_sha256": digest})
                identities[(stat.st_dev, stat.st_ino)].append(ref)
                candidates[(name, stat.st_size)].append(ref)
    return {
        "scope": "Selected roots only; suffix-filtered weight artifacts; no license admission or model execution. Blob directories omitted; snapshot file symlinks included without traversing directory symlinks.",
        "content_hashing": hash_contents,
        "excluded_nonweight_files": excluded_files,
        "roots": sorted(roots), "files": rows,
        "same_file_aliases": [refs for refs in identities.values() if len(refs) > 1],
        "same_name_size_candidates": [refs for refs in candidates.values() if len(refs) > 1],
        "same_content_sha256": {digest: refs for digest, refs in content_groups.items() if len(refs) > 1},
        "deletion_authorized": False,
        "note": "Same-name/size is only a candidate relation. Content hashes establish byte equality, not license or safe deletion; deployment-reference review remains required.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True, help="label=absolute-directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha256", action="store_true", help="Stream file contents to establish byte identity")
    args = parser.parse_args()
    roots = {}
    for item in args.root:
        label, separator, directory = item.partition("=")
        if not separator or not label or label in roots or "/" in label or not Path(directory).is_absolute():
            parser.error("Each root needs a unique path-free label and an absolute directory")
        roots[label] = Path(directory)
    value = inventory(roots, hash_contents=args.sha256)
    encoded = json.dumps(value, indent=2) + "\n"
    args.output.write_text(encoded)
    print(f"{len(value['files'])} artifacts; {len(value['same_file_aliases'])} alias groups; metadata inventory SHA-256 {hashlib.sha256(encoded.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
