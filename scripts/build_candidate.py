#!/usr/bin/env python3
"""Package the explicitly selected offline wheels and cached journal handoff."""

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from listening_stack.candidate import CONTRACT, verify  # noqa: E402
from build_release import build_archive  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wheel-dir", type=Path, required=True)
    p.add_argument("--static-dir", type=Path, required=True)
    p.add_argument("--editorial-dir", type=Path, required=True)
    p.add_argument("--source-inventory", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise ValueError("Choose a new output directory")
    out.mkdir(parents=True)
    (out / "wheels").mkdir()
    wheels = []
    for source in sorted(args.wheel_dir.glob("*.whl")):
        if source.is_symlink():
            raise ValueError("Wheel symlinks are refused")
        target = out / "wheels" / source.name
        shutil.copy2(source, target)
        with zipfile.ZipFile(target) as z:
            m = BytesParser().parsebytes(
                z.read(
                    next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
                )
            )
            licenses = [
                n
                for n in z.namelist()
                if any(s in n.lower() for s in ("license", "notice", "copying"))
            ]
        wheels.append(
            dict(
                file=target.name,
                sha256=sha(target),
                distribution=re.sub(r"[-_.]+", "-", m["Name"]).lower(),
                version=m["Version"],
                license_expression=m.get("License-Expression"),
                license_files=licenses,
            )
        )
    manifest = dict(
        contract=CONTRACT,
        published=False,
        wheels=wheels,
        scope="Uncommitted local candidate; published Git refs unchanged",
        host=dict(
            system=platform.system(),
            machine=platform.machine(),
            python="3.13",
            qualification="This wheel set only; not full L2 coverage",
        ),
        integrations=["hermes", "claude", "codex", "opencode", "openclaw", "pi"],
        separate_installations=[
            "GERM and models/providers",
            "MASA",
            "Cosmoaudition",
            "Cesta",
            "ListeningMD clients",
        ],
    )
    (out / "wheels/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify(out / "wheels/manifest.json")
    for file in args.static_dir.rglob("*"):
        if file.is_symlink():
            raise ValueError("Static symlinks are refused")
    shutil.copytree(args.static_dir, out / "static")
    (out / "editorial").mkdir()
    for name in (
        "figures_v25.md",
        "diagram_content_v1.json",
        "five_stage_captions_v1.md",
        "schema_examples_v1.md",
    ):
        shutil.copy2(args.editorial_dir / name, out / "editorial" / name)
    for source in sorted(args.editorial_dir.glob("antikythera_v25_d*.svg")):
        shutil.copy2(source, out / "editorial" / source.name)
    shutil.copy2(args.source_inventory, out / "source-sha256.json")
    shutil.copy2(ROOT / "docs/candidate-release.md", out / "README.md")
    shutil.copy2(ROOT / "LICENSE", out / "INSTALLER-LICENSE")
    build_archive(out / "listening-stack.pyz")
    checks = {
        str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()
    }
    (out / "checksums.json").write_text(json.dumps(checks, indent=2) + "\n")
    with zipfile.ZipFile(
        out.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as z:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    str(Path(out.name) / path.relative_to(out)),
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, path.read_bytes())
    print(
        json.dumps(
            dict(
                archive=str(out.with_suffix(".zip")),
                sha256=sha(out.with_suffix(".zip")),
                wheels=len(wheels),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
