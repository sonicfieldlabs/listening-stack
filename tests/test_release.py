import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack import __version__  # noqa: E402


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "listening_stack_build_release", ROOT / "scripts" / "build_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def test_release_versions_are_consistent(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('version = "%s"' % __version__, pyproject)
        self.assertIn("version: %s" % __version__, citation)
        self.assertIn("Current installer release: `%s`" % __version__, readme)

    def test_archive_is_reproducible_across_source_mtime_changes(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "src"
            source.mkdir()
            main = source / "__main__.py"
            main.write_text("print('ok')\n", encoding="utf-8")
            package = source / "package.py"
            package.write_text("VALUE = 1\n", encoding="utf-8")
            (source / "private.txt").write_text(
                "not an archive asset\n", encoding="utf-8"
            )
            output = temporary_path / "app.pyz"
            with patch.object(builder, "SOURCE", source):
                builder.build_archive(output)
                first = hashlib.sha256(output.read_bytes()).digest()
                os.utime(main, (1_900_000_000, 1_900_000_000))
                os.utime(package, (1_800_000_000, 1_800_000_000))
                builder.build_archive(output)
                second = hashlib.sha256(output.read_bytes()).digest()
            self.assertEqual(first, second)
            self.assertTrue(os.access(output, os.X_OK))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["__main__.py", "package.py"])


if __name__ == "__main__":
    unittest.main()
