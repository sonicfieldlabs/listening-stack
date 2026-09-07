"""Shared, isolated verification of the installed core and its selected paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .catalog import REPOSITORIES


def core_probe_command(root: Path) -> List[str]:
    """Import actual installed packages without cwd/PYTHONPATH fallback or writes."""
    root = root.resolve()
    packages = {
        "oida": ("sonicfield-oida", "oida", "oida"),
        "akouo_contract": ("akouo-contract", "akouo", "src/akouo_contract"),
        "akousma": ("akousma", "earworm", "packages/py-akousma/akousma"),
        "akousmata_app": ("akousmata", "akousmata", "akousmata_app"),
    }
    expected = {
        module: {"distribution": distribution, "version": REPOSITORIES[key].version,
                 "path": str(root / "src" / key / relative),
                 "project": str(root / "src" / key / ('packages/py-akousma' if key == 'earworm' else ''))}
        for module, (distribution, key, relative) in packages.items()
    }
    script = '''import importlib, importlib.metadata, json, os, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
expected = json.loads(sys.argv[1])
root = Path(sys.argv[2])
results = {}
for name, spec in expected.items():
    module = importlib.import_module(name)
    actual = Path(module.__file__).resolve().parent
    wanted = Path(spec["path"])
    dist = importlib.metadata.distribution(spec["distribution"])
    if actual == wanted and wanted.resolve() == wanted:
        installation = 'editable'
    else:
        site = Path(dist.locate_file('')).resolve()
        venv = root / 'src/oida/.venv'
        if venv not in site.parents or actual != site / name:
            raise RuntimeError("installed module outside selected environment: " + name)
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        url = urlsplit(direct.get('url', ''))
        if url.scheme != 'file' or url.netloc or unquote(url.path) != spec['project']:
            raise RuntimeError("package was built from an unselected source: " + name)
        installation = 'packaged'
    version = dist.version
    if version != spec["version"]:
        raise RuntimeError("installed distribution version mismatch: " + name)
    results[name] = {"path": str(actual), "version": version, "installation": installation}
from akouo_contract import schema_path
schema = schema_path('listening-context')
if root not in schema.resolve().parents:
    raise RuntimeError('AKOUO schema outside selected installation')
json.loads(schema.read_text())
paths = {"AKOUSMATA_PATH": "data/akousmata", "HF_HOME": "models/huggingface",
         "OIDA_DATA_DIR": "data/oida", "OIDA_AUDIO_DIR": "data/audio"}
for name, relative in paths.items():
    wanted = root / relative
    if os.environ.get(name) != str(wanted) or wanted.resolve() != wanted:
        raise RuntimeError("configured path outside selected installation: " + name)
from akousmata_app.paths import store_root
if store_root() != root / "data/akousmata":
    raise RuntimeError("navigator resolves a different store")
print(json.dumps({"modules": results, "store": str(store_root()), "paths_checked": list(paths)}))
'''
    return [str(root / "src/oida/.venv/bin/python"), "-I", "-B", "-c", script,
            json.dumps(expected), str(root)]
