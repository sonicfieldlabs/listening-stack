from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.catalog import Repository  # noqa: E402
from listening_stack.installer import (  # noqa: E402
    HF_CLI_VERSION,
    STATE_CONTRACT,
    Installer,
    Selection,
    load_state,
    state_path,
)
from listening_stack.system import Runner  # noqa: E402


class InstallerTests(unittest.TestCase):
    def selection(self, root, **changes):
        values = {
            "component": "core",
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
            self.assertEqual(state["schema_version"], 2)
            self.assertEqual(state["contract"], STATE_CONTRACT)
            self.assertEqual(state["profile"], "core")
            self.assertEqual(state["component"], "core")
            self.assertEqual(
                state["components"], ["earworm", "akouo", "akousmata", "oida"]
            )
            self.assertEqual(state["optional_components"], [])
            self.assertEqual(state["installer_version"], "0.3.3")
            self.assertEqual(state["contracts"]["gateway"], "oida/gateway/v0.5")
            self.assertEqual(
                state["contracts"]["listening_context"],
                "akouo/listening-context/v2",
            )
            self.assertEqual(
                state["environment"]["AKOUSMATA_PATH"],
                str(Path(state["root"]) / "data" / "akousmata"),
            )
            self.assertNotIn("GERM_ENABLE_CLOUD_VISION", state["environment"])
            self.assertNotIn("OIDA_GERM_URL", state["environment"])
            self.assertNotIn("germ", state["commits"])
            self.assertFalse(root.exists())

    def test_full_profile_explicitly_includes_germ_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "install"
            state = Installer(
                self.selection(root, component="full"),
                Runner(dry_run=True, quiet=True),
            ).install()
            self.assertEqual(state["profile"], "full")
            self.assertEqual(state["optional_components"], ["germ"])
            self.assertIn("germ", state["components"])
            self.assertEqual(state["environment"]["GERM_ENABLE_CLOUD_VISION"], "0")
            self.assertEqual(
                state["environment"]["OIDA_GERM_URL"], "http://127.0.0.1:5178"
            )
            self.assertEqual(
                set(state["environment"]["GERM_ALLOWED_INPUT_ROOTS"].split(",")),
                {
                    str(Path(state["root"]) / "data" / "germ"),
                    str(Path(state["root"]) / "data" / "audio"),
                    str(Path(state["root"]) / "data" / "akousmata"),
                },
            )
            self.assertEqual(
                set(state["environment"]["GERM_ALLOWED_MODEL_ROOTS"].split(",")),
                {
                    str(Path(state["root"]) / "vendor" / "stable-audio-3"),
                    str(Path(state["root"]) / "models"),
                    str(Path(state["root"]) / "data" / "germ"),
                },
            )
            self.assertFalse(root.exists())

    def test_germ_only_profile_does_not_configure_oida(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "install"
            state = Installer(
                self.selection(root, component="germ"),
                Runner(dry_run=True, quiet=True),
            ).install()
            environment = state["environment"]
            self.assertEqual(state["components"], ["germ"])
            self.assertNotIn("OIDA_HOST", environment)
            self.assertNotIn("GERM_OIDA_URL", environment)
            self.assertNotIn(
                str(Path(state["root"]) / "data" / "audio"),
                environment["GERM_ALLOWED_INPUT_ROOTS"].split(","),
            )

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

    def test_duplicate_models_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = self.selection(
                Path(temporary) / "stack",
                component="core",
                model_keys=["moss-4b-instruct", "moss-4b-instruct"],
            )
            with self.assertRaisesRegex(ValueError, "duplicates"):
                Installer(selection, Runner(dry_run=True, quiet=True)).install()

    def test_existing_git_repository_is_not_an_install_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            (root / ".git").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "existing Git repository"):
                Installer(
                    self.selection(root), Runner(dry_run=True, quiet=True)
                ).install()

    def test_load_state_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            path = state_path(root)
            path.parent.mkdir(parents=True)
            target = Path(temporary) / "state.json"
            target.write_text("{}", encoding="utf-8")
            path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "Refusing symlinked"):
                load_state(root)

    def test_load_state_accepts_legacy_component_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            path = state_path(root)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "component": "oida",
                        "environment": {},
                        "commits": {},
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_state(root)["component"], "oida")

    def test_load_state_rejects_tampered_v2_profile_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            path = state_path(root)
            path.parent.mkdir(parents=True)
            state = {
                "schema_version": 2,
                "contract": STATE_CONTRACT,
                "profile": "core",
                "component": "core",
                "components": ["earworm", "akouo", "akousmata", "oida"],
                "core_components": ["earworm", "akouo", "akousmata", "oida"],
                "optional_components": ["germ"],
                "environment": {},
                "commits": {},
                "contracts": {},
                "repositories": {},
            }
            path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "profile metadata"):
                load_state(root)

    def test_install_root_inside_git_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            (project / ".git").mkdir(parents=True)
            root = project / "nested" / "stack"
            with self.assertRaisesRegex(
                ValueError, "inside an existing Git repository"
            ):
                Installer(
                    self.selection(root), Runner(dry_run=True, quiet=True)
                ).install()

    def test_symlinked_managed_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            outside = Path(temporary) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "models").symlink_to(outside, target_is_directory=True)
            installer = Installer(self.selection(root), Runner(quiet=True))
            with self.assertRaisesRegex(RuntimeError, "symlinked managed directory"):
                installer._make_directories()

    def test_python_provider_prepares_both_germ_and_official_workflows(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = self.selection(
                Path(temporary) / "stack",
                component="germ",
                model_keys=["stable-small-sfx"],
                provider="python",
                accept_model_terms=True,
            )
            installer = Installer(selection, Runner(dry_run=True, quiet=True))
            with patch.object(installer.runner, "run") as run:
                installer._sync_applications()
            self.assertEqual(run.call_count, 2)
            germ_call, official_call = run.call_args_list
            self.assertIn("python-provider", germ_call.args[0])
            self.assertEqual(germ_call.kwargs["cwd"], installer.src_root / "germ")
            self.assertIn("ui", official_call.args[0])
            self.assertIn("lora", official_call.args[0])
            self.assertEqual(
                official_call.kwargs["cwd"], installer.vendor_root / "stable-audio-3"
            )

    def test_existing_wrong_hf_cli_version_is_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            installer = Installer(
                self.selection(Path(temporary) / "stack"), Runner(quiet=True)
            )
            binary = Path(installer.hf)
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(0o755)
            with (
                patch.object(
                    installer.runner,
                    "capture",
                    side_effect=["1.0.0", HF_CLI_VERSION],
                ),
                patch.object(installer.runner, "run") as run,
            ):
                installer._ensure_hf()
            self.assertIn("--force", run.call_args.args[0])
            self.assertIn("huggingface_hub==%s" % HF_CLI_VERSION, run.call_args.args[0])

    def test_repository_checkout_fetches_and_verifies_exact_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Listening Stack Tests"],
                cwd=source,
                check=True,
            )
            (source / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip()
            destination = temporary_path / "installed"
            repository = Repository(
                key="fixture",
                name="Fixture",
                url=source.as_uri(),
                ref="main",
                revision=revision,
            )
            installer = Installer(
                self.selection(temporary_path / "stack"), Runner(quiet=True)
            )
            installed = installer._install_repository(repository, destination)
            self.assertEqual(installed, revision)
            self.assertEqual(
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=destination, text=True
                ).strip(),
                revision,
            )

    def test_repository_checkout_recovers_empty_interrupted_git_init(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Listening Stack Tests"],
                cwd=source,
                check=True,
            )
            (source / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip()
            destination = temporary_path / "interrupted"
            subprocess.run(["git", "init", "-q", str(destination)], check=True)
            repository = Repository(
                key="fixture",
                name="Fixture",
                url=source.as_uri(),
                ref="main",
                revision=revision,
            )
            installer = Installer(
                self.selection(temporary_path / "stack"), Runner(quiet=True)
            )
            self.assertEqual(
                installer._install_repository(repository, destination), revision
            )


if __name__ == "__main__":
    unittest.main()
