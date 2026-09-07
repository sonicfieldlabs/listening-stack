import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from listening_stack.installer import Installer, Selection
from listening_stack.system import Runner
from listening_stack.verification import core_probe_command
from listening_stack.doctor import _check_core_environment


class CoreVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "install"
        self.python_root = self.root / "src/oida/.venv"
        venv.EnvBuilder(with_pip=False).create(self.python_root)
        self.command = core_probe_command(self.root)
        self.expected = json.loads(self.command[-2])
        python = self.command[0]
        site = Path(subprocess.check_output([python, "-I", "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True).strip())
        imports = []
        for module, spec in self.expected.items():
            path = Path(spec["path"]); path.mkdir(parents=True, exist_ok=True)
            (path / "__init__.py").write_text("")
            imports.append(str(path.parent))
            info = site / (spec["distribution"].replace("-", "_") + "-" + spec["version"] + ".dist-info")
            info.mkdir()
            (info / "METADATA").write_text("Metadata-Version: 2.1\nName: " + spec["distribution"] + "\nVersion: " + spec["version"] + "\n")
        self.pth = site / "fixture.pth"
        self.pth.write_text("\n".join(imports) + "\n")
        akouo = Path(self.expected['akouo_contract']['path'])
        (akouo / '__init__.py').write_text("from pathlib import Path\ndef schema_path(name): return Path(__file__).parent / (name + '.json')\n")
        (akouo / 'listening-context.json').write_text('{}')
        (Path(self.expected['akousmata_app']['path']) / 'paths.py').write_text(
            "import os\nfrom pathlib import Path\ndef store_root(): return Path(os.environ['AKOUSMATA_PATH'])\n")
        installer = Installer(Selection('core', [], [], 'mock', self.root), Runner(quiet=True))
        self.environment = installer._environment()
        for relative in ('data/akousmata', 'data/oida', 'data/audio', 'models/huggingface'):
            (self.root / relative).mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_actual_imports_ignore_pythonpath_and_do_not_create_store_files(self):
        poison = Path(self.tmp.name) / 'poison'; poison.mkdir()
        (poison / 'oida.py').write_text("raise RuntimeError('borrowed import')")
        environment = dict(self.environment, PYTHONPATH=str(poison))
        self.assertEqual(_check_core_environment(self.root, environment).status, 'pass')
        self.assertEqual(list((self.root / 'data/akousmata').iterdir()), [])
        self.assertEqual(list(self.root.glob('src/*/__pycache__')), [])

    def test_import_from_external_editable_checkout_is_rejected(self):
        outside = Path(self.tmp.name) / 'external'; outside.mkdir()
        (outside / 'oida').mkdir(); (outside / 'oida/__init__.py').write_text('')
        self.pth.write_text(str(outside) + '\n' + self.pth.read_text())
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'fail')

    def test_distribution_drift_is_rejected(self):
        site = self.pth.parent
        metadata = next(site.glob('akousma-*.dist-info/METADATA'))
        metadata.write_text(metadata.read_text().replace('Version: 0.7.0', 'Version: 0.0.1'))
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'fail')

    def test_unselected_and_symlinked_store_paths_are_rejected(self):
        environment = dict(self.environment, AKOUSMATA_PATH=str(Path(self.tmp.name)/'other'))
        self.assertEqual(_check_core_environment(self.root, environment).status, 'fail')
        selected = self.root / 'data/akousmata'; selected.rmdir()
        external = Path(self.tmp.name) / 'other'; external.mkdir()
        selected.symlink_to(external, target_is_directory=True)
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'fail')

    def test_missing_interpreter_is_not_healthy(self):
        self.assertEqual(_check_core_environment(self.root / 'missing', {}).status, 'fail')

    def test_missing_bundled_schema_is_not_healthy(self):
        (Path(self.expected['akouo_contract']['path']) / 'listening-context.json').unlink()
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'fail')

    def test_packaged_distribution_origin_must_match_managed_project(self):
        site = self.pth.parent
        for module, spec in self.expected.items():
            shutil.move(spec['path'], site / module)
            info = site / (spec['distribution'].replace('-', '_') + '-' + spec['version'] + '.dist-info')
            (info / 'direct_url.json').write_text(json.dumps({'url': Path(spec['project']).as_uri(), 'dir_info': {}}))
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'pass')
        origin = next(site.glob('sonicfield_oida-*.dist-info/direct_url.json'))
        origin.write_text(json.dumps({'url': (Path(self.tmp.name)/'unselected-project').as_uri()}))
        self.assertEqual(_check_core_environment(self.root, self.environment).status, 'fail')


if __name__ == '__main__':
    unittest.main()
