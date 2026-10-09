"""Prepare an isolated MOSS qualification variant without changing its base.

This is source/dependency selection, not model or runtime qualification. Shared
checkpoints remain read-only. Resolve and install the generated inputs separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(manifest: Path, moss_repo: Path, oida_source: Path, output: Path):
    manifest, moss_repo, oida_source, output = (
        path.resolve() for path in (manifest, moss_repo, oida_source, output)
    )
    if output.exists() or any(output.is_relative_to(root) for root in (moss_repo, oida_source, manifest.parent)):
        raise ValueError("Fresh destination outside selected sources and wheel set required")
    raw = manifest.read_bytes()
    selected = json.loads(raw)
    wheel_rows = selected["wheels"]
    requirements = []
    for row in wheel_rows:
        if Path(row["file"]).name != row["file"]:
            raise ValueError("Wheel manifest contains a non-flat path")
        wheel = manifest.parent / row["file"]
        if digest(wheel.read_bytes()) != row["sha256"]:
            raise ValueError(f"Wheel changed: {row['file']}")
        requirements.append(f"{row['distribution']}=={row['version']}")
    project_bytes = (oida_source / "pyproject.toml").read_bytes()
    extras = tomllib.loads(project_bytes.decode())["project"]["optional-dependencies"]["moss"]
    # Use the owner's tested adapter requirements, not an implicit editable install
    # of the upstream demo and its unrelated Gradio/Streamlit dependencies.
    inputs = requirements + extras
    before = subprocess.check_output(["git", "-C", str(moss_repo), "diff", "HEAD", "--binary"])
    tracked = subprocess.check_output(["git", "-C", str(moss_repo), "ls-files", "-z"]).split(b"\0")
    files = []
    payloads = []
    for name in sorted(set(tracked) - {b""}):
        relative = Path(name.decode())
        source = moss_repo / relative
        if relative.is_absolute() or ".." in relative.parts or source.is_symlink() or not source.is_file():
            raise ValueError("Upstream snapshot requires regular tracked files")
        data = source.read_bytes()
        files.append({"path": relative.as_posix(), "sha256": digest(data), "bytes": len(data)})
        payloads.append((relative, data, source.stat().st_mode & 0o777))
    if subprocess.check_output(["git", "-C", str(moss_repo), "diff", "HEAD", "--binary"]) != before:
        raise ValueError("Upstream source changed during snapshot")
    profiler = (oida_source / "scripts/profile-moss-runtime.py").read_bytes()
    output.mkdir(parents=True)
    for relative, data, mode in payloads:
        target = output / "moss-source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode)
    (output / "requirements.in").write_text("\n".join(inputs) + "\n")
    (output / "profile-moss-runtime.py").write_bytes(profiler)
    (output / "selection.json").write_text(json.dumps({
        "status": "selected-not-qualified", "base_manifest_sha256": digest(raw),
        "base_wheels": wheel_rows, "oida_project_sha256": digest(project_bytes),
        "moss_requirements": extras, "profiler_sha256": digest(profiler),
        "upstream_head": subprocess.check_output(["git", "-C", str(moss_repo), "rev-parse", "HEAD"]).decode().strip(),
        "upstream_diff_sha256": digest(before), "upstream_files": files,
        "limits": ["No model execution yet", "No checkpoint license or content admission yet",
                   "No application installation changed", "Only tracked upstream source captured"],
    }, indent=2) + "\n")
    print(json.dumps({"output": str(output), "base_wheels": len(wheel_rows), "upstream_files": len(files)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "moss-repo", "oida-source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.manifest, args.moss_repo, args.oida_source, args.output)
