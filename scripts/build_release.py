#!/usr/bin/env python3
"""Build the standalone, standard-library-only zip application."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import shutil
import zipapp


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
DIST = ROOT / "dist"
OUTPUT = DIST / "listening-stack.pyz"


def main() -> None:
    for path in SOURCE.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    zipapp.create_archive(
        SOURCE,
        target=OUTPUT,
        interpreter="/usr/bin/env python3",
        filter=lambda path: "__pycache__" not in path.parts and path.suffix != ".pyc",
        compressed=True,
    )
    OUTPUT.chmod(0o755)
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    checksum = DIST / "listening-stack.pyz.sha256"
    checksum.write_text("%s  listening-stack.pyz\n" % digest, encoding="utf-8")
    print(OUTPUT)
    print(checksum)


if __name__ == "__main__":
    main()
