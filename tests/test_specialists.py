from pathlib import Path
import pytest
from listening_stack.specialists import prepare, source_component, PINS


def test_source_pin_covers_preprocessing_and_label_metadata(tmp_path):
    (tmp_path / "model.py").write_text("model = 1")
    (tmp_path / "metadata").mkdir()
    labels = tmp_path / "metadata/labels.csv"
    labels.write_text("one")
    original = source_component(tmp_path, "a" * 40)
    labels.write_text("two")
    assert source_component(tmp_path, "a" * 40)["sha256"] != original["sha256"]


def test_checkpoint_mismatch_is_refused_before_worker_execution(tmp_path, monkeypatch):
    (tmp_path / "requirements.lock").write_text("test")
    (tmp_path / "EfficientAT").mkdir()
    (tmp_path / "mn04_as.pt").write_bytes(b"wrong")
    monkeypatch.setattr(
        "subprocess.check_output", lambda *a, **k: PINS["tag_events"]["revision"]
    )

    def never(*a, **k):
        pytest.fail("worker must not run before artifact verification")

    monkeypatch.setattr("subprocess.run", never)
    with pytest.raises(ValueError, match="artifact mismatch"):
        prepare(tmp_path, tmp_path, tmp_path)
