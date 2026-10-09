# Local candidate installation

The public installer continues to use the immutable released component pins in
`catalog.py`. Its managed adapter selection belongs to that released Oída
revision. A local wheel candidate has a separate manifest and does not change
those pins or configure a managed installation.

The unpublished core profile selects Oída 0.12.0, Akousma 0.8.4, Akousmata 0.8.3,
AKOUO contract 0.10.1 and installer 0.5.1. The full profile adds GERM 0.7.0.
MASA and Cosmoaudition remain independent applications. The AKOUO contract
package version does not change the AKOUO protocol version.

## Preparing inputs

Use `scripts/prepare_local_candidate.py` with an explicit repository parent and
a fresh private output outside every owner checkout. It checks every selected
owner before copying, records the base commits and exact source hashes, and
preserves tracked deletions and untracked source inputs. It copies no Git
history. Source snapshots may still contain development records and require a
release content review before distribution.

```bash
python scripts/prepare_local_candidate.py \
  --root /path/to/owner-parent --output /private/candidate-sources
```

Build the selected owner wheels from those exact inputs. Resolve their normal
runtime dependencies for the intended interpreter and platform into a separate
wheel directory. Keep model, optional provider and test dependencies outside
the runtime bundle. Every transitive dependency must have a wheel; installation
runs offline with dependency resolution disabled and then checks the resulting
dependency graph. An incomplete set fails instead of downloading packages.

```bash
python scripts/build_candidate.py \
  --wheel-dir /private/runtime-wheels \
  --source-inventory /private/candidate-sources/source-inventory.json \
  --profile listening-stack-core/v1 --output /private/core-bundle
```

Use `listening-stack-full/v1` for a bundle that contains GERM. The manifest
records exact wheel hashes, Python requirements and source inventory identity.
The base commit alone does not identify an uncommitted candidate. A final
candidate commit and published immutable references remain separate release
requirements.

## Installing and checking

The candidate runtime requires Python 3.12 or newer and a preinstalled `uv`.
Choose the interpreter whose platform tags match the selected wheels. These
commands use fresh roots, inherit no provider credentials or owner stores, and
start no services or model workers.

```bash
python -m listening_stack.candidate verify /private/core-bundle/manifest.json
python -m listening_stack.candidate install /private/core-bundle/manifest.json \
  --root /private/core-runtime --python 3.13
python -m listening_stack.candidate doctor --root /private/core-runtime
```

Keep the bundle beside its runtime evidence. Doctor checks the original manifest
and wheel hashes, dependency consistency, installed versions and isolated owner
imports. It compares installed owner files directly with the pinned wheel bytes,
including schemas and notices. Installed RECORD files are not its byte authority.

A source snapshot is `source-ready`. Passing a fresh offline installation and
its installed checks establishes `artifact-qualified` for that exact host,
interpreter and manifest. It remains `waiting-for-published-refs` until the
required component commits and releases exist remotely and the released profile
has been reviewed against them. Those labels do not establish model inference,
physical-device behavior or every supported platform.

## Cleanup and rollback

Candidate roots do not migrate memory, update provider settings or replace an
existing environment. Preserve the bundle and receipt for review. After stopping
any process you started manually, remove only the exact disposable runtime root
you created. Inspect its `state` directory first because later use may have
created records or audio. There is no automatic destructive uninstall command.
A failed install leaves its fresh root available for inspection; retry with a
new root. Existing managed installations use their original lifecycle commands.
