# D7 local candidate and journal handoff

The current development work is uncommitted. Published tag/SHA pins in
`catalog.py` identify the earlier release and cannot identify these working-tree
bytes. They remain unchanged. The D7 candidate instead pins every wheel by SHA-256,
distribution and version in an explicitly unpublished manifest. Package numbers
are unchanged; hashes distinguish these builds from published packages.

## Install and verify the candidate

The local handoff archive contains the installer zipapp, a complete offline
wheel directory and `manifest.json`. Use a new environment root:

```sh
python3 listening-stack.pyz --help
python3 -m zipfile -e listening-stack.pyz candidate-installer
PYTHONPATH=candidate-installer python3 -m listening_stack.candidate verify wheels/manifest.json
PYTHONPATH=candidate-installer python3 -m listening_stack.candidate install wheels/manifest.json --root /absolute/new-candidate --python 3.13
/absolute/new-candidate/.venv/bin/python -m listening_stack.candidate doctor --root /absolute/new-candidate
```

`uv` and a local compatible Python must already be available. All wheels are
verified before installation; unsafe paths, duplicates, missing core artifacts,
changed bytes and existing target roots are refused. Installation uses explicit
local wheels with `--offline --no-index --no-deps`, then checks dependency
compatibility. No sibling checkout, Git fetch, model download, host configuration,
service startup or memory migration is implicit. The manifest is a local operator
trust input, not a signed public release.

This candidate's binary wheel set targets macOS arm64, Python 3.13 and macOS 14+
(the SciPy wheel minimum). It is not a universal installer release. The ordinary
source installer still checks its published pins and managed installation state;
`candidate doctor` reports isolated candidate status separately. L2's remaining
host, optional profile, model and physical-device matrix is not closed here.

## Component ownership

| Component | Published source installer | D7 offline candidate |
|---|---|---|
| Oída, Earworm, AKOÚŌ, Akousmata | Managed core and selected data/model paths | Included wheels; no model weights |
| GERM | Optional managed profile | Separate installation; use the recorded D4/D5 candidate and provider requirements |
| listeningstackweb | Separate application | Included wheel plus standalone cached static reader |
| MASA | Separate protocol/runtime installation | Separate; do not infer it from a GERM adapter |
| Cosmoaudition | Separate application/runtime installation | Separate; browser and observation adapters do not install it |
| Cesta / ListeningMD | Separate client/integration | Separate; retained contracts do not install applications |
| Hermes, Claude Code, Codex, OpenCode, OpenClaw, Pi | Explicit selected Oída integrations | Host apps installed separately; candidate Oída supplies adapter assets |

Pi uses an explicit native extension launch, staged by `oida integrate pi`.
It leaves Pi settings and provider credentials alone. The other five adapters
retain their own installation behavior; choose a target deliberately rather than
using `all` on an active workstation. This verification staged only Pi in a
temporary directory and exercised existing adapter tests with isolated fixtures.

## Migration and rollback

Install a candidate into a new root. Keep application data outside that root.
Review compatible record contracts before an explicit import. The existing
`restore-memory` path preserves the current forgetting ledger and rejects a
backup that would resurrect forgotten records. D7 verifies this with a synthetic
old/new record bundle outside the checkouts.

Rollback means stopping the candidate service and selecting the previously
verified runtime, while retaining the current data/forgetting ledger. It does not
mean restoring an old database over current revocations. Keep both runtime roots
until verification is complete. Provider execution and distributed side effects
are not rolled back by selecting an older interpreter.

## Cached journal handoff

The handoff includes `static/`, its existing cached example, schema assets and
source captions, plus SHA-256 checksums. Designers can serve `static/` with an
ordinary local HTTP server; no Python inference package or owner service is needed.
The public snapshot remains an age-limited cached example, not a live journal.
Live private intake requires the separately configured app service and real human
operator/contact. The D6 delivery demo is an independent, explicitly synthetic
runtime exhibit; it does not replace the cached example's provenance.

See the local worklog `evidence/d7/` for the candidate archive, exact manifest,
licence inventory, Pi loader/API receipts, installation checks and remaining gaps.
Release publication and replacing published Git pins require actual reviewed
release commits and compatible artifacts; this local handoff does neither.
