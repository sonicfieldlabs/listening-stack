from types import SimpleNamespace
from listening_stack.installer import _preferred_stable_model


def test_stable_audio_model_names_belong_to_the_selected_runtime():
    models = [SimpleNamespace(key="stable-small-sfx", model_id="stabilityai/stable-audio-3-small-sfx")]
    assert _preferred_stable_model(models, provider="mlx") == "sm-sfx"
    assert _preferred_stable_model(models, provider="python") == "small-sfx"
    assert _preferred_stable_model(models) == "small-sfx"
