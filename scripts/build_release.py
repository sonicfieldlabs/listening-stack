#!/usr/bin/env python3
"""Build the standalone, standard-library-only zip application."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
DIST = ROOT / "dist"
OUTPUT = DIST / "listening-stack.pyz"
CHECKSUM = DIST / "listening-stack.pyz.sha256"
SHEBANG = b"#!/usr/bin/env python3\n"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def source_files() -> list[Path]:
    return sorted(
        (path for path in SOURCE.rglob("*") if path.is_file() and path.suffix == ".py"),
        key=lambda path: path.relative_to(SOURCE).as_posix(),
    )


def build_archive(output: Path) -> None:
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("wb") as raw:
            raw.write(SHEBANG)
            with zipfile.ZipFile(
                raw, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for path in source_files():
                    relative = path.relative_to(SOURCE).as_posix()
                    info = zipfile.ZipInfo(relative, date_time=ZIP_TIMESTAMP)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
        temporary.chmod(0o755)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    for path in source_files():
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    DIST.mkdir(parents=True, exist_ok=True)
    build_archive(OUTPUT)
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    checksum_temporary = CHECKSUM.with_name(CHECKSUM.name + ".tmp")
    checksum_temporary.write_text(
        "%s  listening-stack.pyz\n" % digest, encoding="utf-8"
    )
    checksum_temporary.replace(CHECKSUM)
    print(OUTPUT)
    print(CHECKSUM)


if __name__ == "__main__":
    main()
