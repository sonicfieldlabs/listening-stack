# Phase 11 candidate verification

Use a disposable Python 3.12 environment. Build the selected checkouts as wheels
and install the explicit wheel set together; do not add owner checkouts to
`PYTHONPATH`. Include pytest, HTTPX/HTTPX2 and the declared package dependencies.
Do not install model extras for contract verification.

Run `scripts/verify_installed_boundaries.py` with that environment's Python,
`--root` naming the parent of the checkouts, `--profile` and an explicit
`--report` destination. Profiles are `core`, `central-owner`, `records`,
`derivatives`, `room`, and `germ-full`. Each fails on missing imports, editable/source imports,
zero executed tests, any skip, or a test failure. Reports record imported module
digests and available wheel digests without private paths. A module digest is not
a complete dependency closure hash.

The latter three profiles additionally require `GERM_TEST_MASA_VALIDATOR` pointing
to the reviewed built validator entry. Its entry hash is recorded, not a claim
that MASA's complete package conformance suite ran. `room` requires the declared
`pyroomacoustics==0.10.0` optional dependency. Synthetic tests establish technical
contracts and bounded DSP behavior, not live listening or perceptual truth.

`scripts/inventory_weights.py --root label=/absolute/directory --output report.json`
inventories selected roots without deletion. Metadata-only duplicate candidates
must not be promoted to identical weights. Snapshot symlinks can establish that
two names refer to the same file; physical copies require content verification.
Use `--sha256` to stream content hashes and detect byte-equal files; this does not
authorize deleting them. Environment-contained models, directory symlinks,
unselected roots and artifacts outside the declared suffix filter remain outside
the inventory. Review those separately before calling the inventory complete.

After this change, ACE and research deployment manifests must include
`server/deployment_validation.py` in their hash set. Existing manifests lacking
that binding are refused. Rebuild admission manifests with `generation.prepare`
or `research.prepare` only after reviewing the pinned worker evaluation and
environment. Do not edit old acceptance receipts or regenerate them merely to
make admission green. Active deployments were not modified by this work.
