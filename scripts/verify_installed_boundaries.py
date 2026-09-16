"""Fail-closed Python 3.12 installed-package boundary lane; no model downloads.

Run with the disposable candidate environment's Python, never an owner service
environment. Profiles are separate evidence, not an aggregate runtime verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import distribution
from pathlib import Path

PROFILES = {
    "germ-full": (
        "germ", ["tests"],
        {"server": "germ", "pyroomacoustics": "pyroomacoustics", "akousmata_app.derivatives": "akousmata", "akousma": "akousma"},
    ),
    "core": (
        "listening-stack", ["tests"],
        {"listening_stack": "sonicfield-listening-stack", "akousma": "akousma", "akousmata_app": "akousmata"},
    ),
    "central-owner": (
        "listeningstackweb", ["tests/test_c1_owner_boundaries.py"],
        {"listeningstackweb": "listeningstackweb", "oida.source_capture": "sonicfield-oida", "akousma": "akousma"},
    ),
    "records": (
        "akouo", ["tests/test_record_workflows.py"],
        {"akouo_contract": "akouo-contract", "akousma": "akousma"},
    ),
    "derivatives": (
        "germ", ["tests/test_spectral_brief.py", "tests/test_processing_adapter.py"],
        {"server": "germ", "akousmata_app.derivatives": "akousmata", "akousma": "akousma"},
    ),
    "room": (
        "germ", ["tests/test_room_engine.py"],
        {"server": "germ", "pyroomacoustics": "pyroomacoustics", "akousma": "akousma"},
    ),
}


class Results:
    def __init__(self):
        self.passed = self.skipped = self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped += 1
        if report.failed:
            self.failed += 1
        if report.when == "call" and report.passed:
            self.passed += 1

    def pytest_collectreport(self, report):
        if report.skipped:
            self.skipped += 1
        if report.failed:
            self.failed += 1


def installed_identity(modules):
    result = {}
    prefix = Path(sys.prefix).resolve()
    for name, package in modules.items():
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(prefix) or "site-packages" not in origin.parts:
            raise ValueError(f"{name} is not imported from the installed candidate")
        dist = distribution(package)
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        if direct.get("dir_info", {}).get("editable"):
            raise ValueError(f"{name} is editable, not a release candidate")
        rows = [[path.relative_to(origin.parent).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()]
                for path in sorted(origin.parent.rglob("*.py"))]
        result[name] = {
            "distribution": package, "version": dist.version,
            "origin_within_environment": origin.relative_to(prefix).as_posix(),
            "module_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
            "python_source_tree_sha256": hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest(),
            "wheel_sha256": direct.get("archive_info", {}).get("hashes", {}).get("sha256"),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Parent of the repository checkouts")
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("This lane requires Python 3.12")
    repo, tests, modules = PROFILES[args.profile]
    result = {"profile": args.profile, "observed_at": datetime.now(UTC).isoformat(),
              "python": sys.version.split()[0], "status": "failed", "scope": "Installed contract boundary, not live model qualification"}
    code = 1
    try:
        result["installed"] = installed_identity(modules)
        if args.profile in {"derivatives", "room", "germ-full"}:
            validator = Path(os.environ.get("GERM_TEST_MASA_VALIDATOR", ""))
            if not validator.is_file():
                raise ValueError("Required MASA validator has not been selected")
            result["masa_validator_entry_sha256"] = hashlib.sha256(validator.read_bytes()).hexdigest()
        import pytest
        collected = Results()
        code = int(pytest.main([*(str(args.root / repo / test) for test in tests),
                               "-o", "pythonpath=", "-q", "-rs"], plugins=[collected]))
        result.update(passed=collected.passed, skipped=collected.skipped, failed=collected.failed)
        if not collected.passed or collected.skipped or collected.failed:
            code = 1
        result["status"] = "passed" if code == 0 else "failed"
    except (ImportError, OSError, ValueError) as exc:
        # No private absolute paths or environment values in portable reports.
        result["error_type"] = type(exc).__name__
        print(f"Required profile {args.profile} could not start: {type(exc).__name__}", file=sys.stderr)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
