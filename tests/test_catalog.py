from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.catalog import (  # noqa: E402
    MODELS,
    memory_guidance,
    planned_disk_gb,
    preset_models,
    selected_models,
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


if __name__ == "__main__":
    unittest.main()
