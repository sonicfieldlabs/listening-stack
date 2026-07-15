from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.installer import Installer, Selection  # noqa: E402
from listening_stack.system import Runner  # noqa: E402


class InstallerTests(unittest.TestCase):
    def selection(self, root, **changes):
        values = {
            "component": "full",
            "model_keys": [],
            "integrations": [],
            "provider": "auto",
            "root": Path(root),
            "accept_model_terms": False,
            "install_system_dependencies": True,
        }
        values.update(changes)
        return Selection(**values)

    def test_dry_run_model_free_install_has_no_filesystem_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "install"
            state = Installer(
                self.selection(root), Runner(dry_run=True, quiet=True)
            ).install()
            self.assertEqual(state["component"], "full")
            self.assertFalse(root.exists())

    def test_gated_weights_require_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = self.selection(
                temporary,
                component="germ",
                model_keys=["stable-small-sfx"],
                provider="python",
            )
            with self.assertRaisesRegex(ValueError, "gated"):
                Installer(selection, Runner(dry_run=True, quiet=True)).install()

    def test_mlx_is_rejected_away_from_apple_silicon(self):
        from unittest.mock import patch

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("listening_stack.installer.is_apple_silicon", return_value=False),
        ):
            selection = self.selection(
                temporary,
                component="germ",
                model_keys=["stable-small-sfx"],
                provider="mlx",
                accept_model_terms=True,
            )
            with self.assertRaisesRegex(ValueError, "Apple Silicon"):
                Installer(selection, Runner(dry_run=True, quiet=True)).install()


if __name__ == "__main__":
    unittest.main()
