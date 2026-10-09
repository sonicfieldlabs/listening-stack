import pytest
from listening_stack.evaluation import create_evaluation, verify_evaluation


def test_private_baseline_is_immutable_and_detects_corruption(tmp_path):
    manifest = create_evaluation(tmp_path)
    assert manifest.stat().st_mode & 0o777 == 0o600
    assert verify_evaluation(tmp_path) == []
    with pytest.raises(FileExistsError):
        create_evaluation(tmp_path)
    (tmp_path / "silence.wav").write_bytes(b"changed")
    assert verify_evaluation(tmp_path) == ["fixture changed: silence.wav"]
