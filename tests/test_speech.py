import json
import pytest
from listening_stack.speech import prepare, PINS


def test_speech_rejects_release_and_checkpoint_substitution(tmp_path):
    pins=tmp_path/'upstream.json';pins.write_text('{}')
    with pytest.raises(ValueError, match='pins'): prepare(tmp_path,tmp_path,tmp_path/'receipt.json')
    pins.write_text(json.dumps(PINS))
    for kind in PINS:
        (tmp_path/kind).mkdir();(tmp_path/kind/'model.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hashes'): prepare(tmp_path,tmp_path,tmp_path/'receipt.json')
