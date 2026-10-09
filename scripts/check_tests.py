"""Run the unit or owner integration partition against installed packages."""
import argparse
import importlib
import importlib.util
from pathlib import Path
import sys

import listening_stack
import pytest


OWNER_TESTS = (
    "tests/test_memory_restore.py",
    "tests/test_planner_evaluation.py",
    "tests/test_situated_owner_qualification.py",
    "tests/test_phase17_tools.py",
    "tests/test_situated_qualification.py",
)
OWNERS = ("oida", "akousma", "akousmata_app", "akouo_contract")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=("unit", "owners"))
    parser.add_argument("--junitxml", required=True)
    args = parser.parse_args()
    prefix = Path(sys.prefix).resolve()
    modules = {"listening_stack": listening_stack}
    for name in OWNERS:
        if args.scope == "unit":
            if importlib.util.find_spec(name) is not None:
                raise RuntimeError("Unit tests require the test extra only; found ambient owner " + name)
        else:
            modules[name] = importlib.import_module(name)
    for name, module in modules.items():
        if not Path(module.__file__).resolve().is_relative_to(prefix):
            raise RuntimeError("Expected an installed package: " + name)
    root = Path(__file__).resolve().parents[1]
    selection = [str(root / path) for path in OWNER_TESTS] if args.scope == "owners" else [
        str(root / "tests"), *["--ignore=" + str(root / path) for path in OWNER_TESTS]
    ]
    result = pytest.main(["-q", "-ra", "-p", "no:cacheprovider", *selection,
                          "--junitxml", args.junitxml])
    for name, module in tuple(sys.modules.items()):
        if any(name == package or name.startswith(package + ".") for package in modules):
            path = getattr(module, "__file__", None)
            if path and not Path(path).resolve().is_relative_to(prefix):
                raise RuntimeError("Tests escaped to sibling source: " + name)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
