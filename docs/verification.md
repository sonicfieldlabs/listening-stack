# Candidate verification

Use the explicit offline candidate profiles described in [candidate-release.md](candidate-release.md). Build the selected owners as wheels and install their complete dependency closure in a fresh private environment. Do not add owner source trees to `PYTHONPATH`.

The installed candidate doctor checks the receipt, manifest, complete wheel checksums, dependency consistency and owner payload bytes. `scripts/verify_candidate_resources.py` provides the independent installed resource comparison. Run `scripts/check_tests.py` separately for the `unit` and `owners` scopes with their declared extras and an explicit JUnit output destination.

These checks establish installed software and contract behavior. They do not establish model inference, live provider behavior, physical audio, or optional DSP engines. Model admission requires independently reviewed evaluation receipts bound to the exact worker, runtime and checkpoint files.

`scripts/inventory_weights.py --root label=/path/to/directory --output /path/to/private/report.json` inventories explicitly selected roots without deletion. Use `--sha256` for byte equality. Neither a size match nor a hash match establishes license clearance or authorizes deletion.
