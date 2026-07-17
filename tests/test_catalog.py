from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.catalog import (  # noqa: E402
    MODELS,
    REPOSITORIES,
    memory_guidance,
    planned_disk_gb,
    preset_models,
    refresh_model_sizes,
    selected_models,
    source_keys,
)


class CatalogTests(unittest.TestCase):
    def test_recommended_full_set_covers_both_apps(self):
        models = selected_models(preset_models("full", "recommended"))
        self.assertEqual({model.application for model in models}, {"oida", "germ"})

    def test_all_set_contains_every_public_choice(self):
        self.assertEqual(set(preset_models("full", "all")), set(MODELS))

    def test_memory_is_summed_only_for_concurrent_apps(self):
        models = selected_models(preset_models("full", "all"))
        single, concurrent = memory_guidance(models)
        self.assertEqual(single, 48)
        self.assertEqual(concurrent, 72)

    def test_disk_plan_includes_runtime_reserve(self):
        self.assertEqual(planned_disk_gb("full", []), 14)
        self.assertGreater(planned_disk_gb("full", list(MODELS.values())), 90)

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(ValueError):
            selected_models(["not-a-model"])

    def test_release_compatibility_set_is_immutable(self):
        self.assertEqual(REPOSITORIES["oida"].version, "0.6.5")
        self.assertEqual(REPOSITORIES["germ"].version, "0.2.5")
        for repository in REPOSITORIES.values():
            self.assertEqual(len(repository.revision), 40)
            int(repository.revision, 16)

    def test_source_keys_are_component_specific(self):
        self.assertEqual(source_keys("germ"), ("germ",))
        self.assertIn("oida", source_keys("oida"))
        self.assertIn("germ", source_keys("full"))
        with self.assertRaises(ValueError):
            source_keys("unknown")

    def test_oida_downloads_use_immutable_model_revisions(self):
        oida_models = [
            model for model in MODELS.values() if model.application == "oida"
        ]
        self.assertTrue(oida_models)
        for model in oida_models:
            self.assertEqual(len(model.download_revision), 40)
            int(model.download_revision, 16)

    def test_live_size_refresh_rejects_boolean_storage_values(self):
        from unittest.mock import patch

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b'{"usedStorage": true}'

        model = MODELS["moss-4b-instruct"]
        with patch("listening_stack.catalog.urlopen", return_value=Response()):
            refreshed, warnings = refresh_model_sizes([model])
        self.assertEqual(refreshed, [model])
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
