import json
import pytest
from listening_stack.acoustic import prepare, REVISION


def test_unverified_weights_rejected_before_environment(tmp_path):
    (tmp_path/'model').mkdir();(tmp_path/'model/pytorch_model.bin').write_bytes(b'invalid')
    (tmp_path/'upstream.json').write_text(json.dumps(dict(sha=REVISION,siblings=[dict(rfilename='pytorch_model.bin',lfs=dict(sha256='0'*64))])))
    report=tmp_path/'report.json';report.write_text('{}')
    with pytest.raises(ValueError,match='Weights'):prepare(tmp_path,tmp_path,report)
