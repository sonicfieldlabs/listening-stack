"""Small, testable process and platform helpers."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from typing import Mapping, Optional, Sequence


class CommandError(RuntimeError):
    pass


class Runner:
    def __init__(self, dry_run: bool = False, quiet: bool = False) -> None:
        self.dry_run = dry_run
        self.quiet = quiet

    def note(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        normalized = [str(item) for item in command]
        location = " (in %s)" % cwd if cwd else ""
        self.note("  $ %s%s" % (shlex.join(normalized), location))
        if self.dry_run:
            return subprocess.CompletedProcess(normalized, 0, "", "")
        merged = os.environ.copy()
        if env:
            merged.update({str(key): str(value) for key, value in env.items()})
        result = subprocess.run(
            normalized,
            cwd=str(cwd) if cwd else None,
            env=merged,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise CommandError(
                "Command failed with exit status %d: %s"
                % (result.returncode, shlex.join(normalized))
            )
        return result

    def capture(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        check: bool = True,
    ) -> str:
        normalized = [str(item) for item in command]
        location = " (in %s)" % cwd if cwd else ""
        if self.dry_run:
            self.note("  $ %s%s" % (shlex.join(normalized), location))
            return ""
        merged = os.environ.copy()
        if env:
            merged.update({str(key): str(value) for key, value in env.items()})
        result = subprocess.run(
            normalized,
            cwd=str(cwd) if cwd else None,
            env=merged,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise CommandError(
                "Command failed: %s\n%s" % (shlex.join(normalized), detail)
            )
        return result.stdout.strip()


def executable(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    directories = [Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"]
    for variable in ("UV_INSTALL_DIR", "UV_TOOL_BIN_DIR", "XDG_BIN_HOME"):
        configured = os.environ.get(variable)
        if configured:
            directories.append(Path(configured).expanduser())
    for directory in dict.fromkeys(directories):
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def total_ram_gb() -> Optional[float]:
    try:
        if sys.platform == "darwin":
            raw = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(raw.strip()) / (1024**3)
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024**2)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return None
