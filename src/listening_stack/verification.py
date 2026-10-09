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


def germ_probe_command(root: Path) -> List[str]:
    """Verify GERM's selected source, interpreter, dependency and paths without app startup."""
    root = root.resolve()
    expected = {"germ_version": REPOSITORIES["germ"].version,
                "akousma_version": REPOSITORIES["earworm"].version,
                "akousma_revision": REPOSITORIES["earworm"].revision}
    script = '''import importlib.metadata, json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
expected = json.loads(sys.argv[2])
project = root / 'src/germ'
if project.resolve() != project or sys.version_info[:2] != (3, 12):
    raise RuntimeError('GERM needs its selected source and Python 3.12 environment')
sys.path.insert(0, str(project))
import server.identity, server.config, akousma
if Path(server.identity.__file__).resolve().parent != project / 'server':
    raise RuntimeError('GERM imported from another checkout')
if server.identity.__version__ != expected['germ_version']:
    raise RuntimeError('GERM version mismatch')
dist = importlib.metadata.distribution('akousma')
site = Path(dist.locate_file('')).resolve()
if project / '.venv' not in site.parents or Path(akousma.__file__).resolve().parent != site / 'akousma':
    raise RuntimeError('GERM dependency imported outside its environment')
direct = json.loads(dist.read_text('direct_url.json') or '{}')
if dist.version != expected['akousma_version'] or direct.get('vcs_info', {}).get('commit_id') != expected['akousma_revision']:
    raise RuntimeError('GERM Akousma dependency does not match the pinned revision')
settings = server.config.get_settings()
for name, relative in {'GERM_OUTPUT_DIR': 'data/germ', 'AKOUSMATA_PATH': 'data/akousmata',
                       'HF_HOME': 'models/huggingface'}.items():
    wanted = root / relative
    if os.environ.get(name) != str(wanted) or wanted.resolve() != wanted:
        raise RuntimeError('GERM configured path outside selected installation: ' + name)
if settings.output_root.resolve() != root / 'data/germ':
    raise RuntimeError('GERM resolves an unselected output directory')
print(json.dumps({'germ_version': server.identity.__version__, 'python': sys.version.split()[0],
                  'akousma_version': dist.version, 'akousma_revision': expected['akousma_revision'],
                  'source': str(project), 'output': str(settings.output_root)}))
'''
    return [str(root / "src/germ/.venv/bin/python"), "-I", "-B", "-c", script,
            str(root), json.dumps(expected)]
