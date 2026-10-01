"""The acoustic prepare step refuses unverified weights.

Converted to unittest on 15 September 2026, finding P1-14/R-B. The project
documented `python3 -m unittest discover -s tests -v`, which collects a module
like this but never calls a module-level function. This test existed, looked
present in the tree, and had never run under the documented command.

Counting the rest showed the problem was wider than one test: seven modules held
eleven bare functions that the documented runner silently skipped. So the runner
is now pytest, which collects both styles. This module stays unittest because it
then runs under either one, which is the more robust of the two positions.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from listening_stack.acoustic import REVISION, prepare


class UnverifiedWeightsTest(unittest.TestCase):
    def test_unverified_weights_rejected_before_environment(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "model").mkdir()
            (root / "model/pytorch_model.bin").write_bytes(b"invalid")
            (root / "upstream.json").write_text(
                json.dumps(
                    dict(
                        sha=REVISION,
                        siblings=[
                            dict(
                                rfilename="pytorch_model.bin",
                                lfs=dict(sha256="0" * 64),
                            )
                        ],
                    )
                )
            )
            report = root / "report.json"
            report.write_text("{}")

            with self.assertRaisesRegex(ValueError, "Weights"):
                prepare(root, root, report)


if __name__ == "__main__":
    unittest.main()
