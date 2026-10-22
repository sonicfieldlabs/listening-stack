# Listening research candidate

The versioned research selections are:

| Profile suffix | Oída | Installer | Status |
| --- | --- | --- | --- |
| `/v1` | 0.13.2 | 0.6.1 | Historical unpublished P7/P8 candidate bytes |
| `/v2` | 0.14.0 | 0.7.0 | October release identities; exact manifest still required |
| `/v3` | 0.14.1 | 0.7.1 | Audit repair candidates; unpublished, selected for current owner CI |

Both `listening-research-core` and `listening-research-full` use these suffixes.
The repair profiles preserve the earlier selections and require new wheel hashes.
Research CI installs the repaired owner wheel and requires zero skipped cohort tests.
Preparing or verifying a candidate does not publish or activate it.

`listening-research-core/v1` and `listening-research-full/v1` are explicit,
unpublished selections for the P2–P6 research adapters. Core selects Oída
0.13.2, Akousma 0.10.1, Akousmata 0.9.1, AKOÚŌ 0.12.1 and installer 0.6.1.
Full adds GERM 0.7.0. These are local candidate versions: the manifest's exact
wheel hashes and source inventory identify their bytes. An earlier wheel with
the same version is not this candidate. A future public release needs new
immutable release identities and its own qualification.

The published managed bootstrap, historical core/full and inscription profiles
retain their selections. This does not upgrade an existing installation or
select a new default. Khipu remains a separately packaged private consumer.

Use the existing candidate commands with a complete, reviewed offline bundle:

```sh
listening-stack candidate verify /absolute/bundle/manifest.json
listening-stack candidate install /absolute/bundle/manifest.json --root /absolute/fresh/runtime --python 3.13
listening-stack candidate doctor --root /absolute/fresh/runtime
```

Installation refuses an existing root. Doctor checks the pinned owner files,
installed imports and dependency metadata, then inspects inscription and research
declarations. Research inspection consults no wiki, network, model or owner.
An older same-version Oída wheel without the research modules fails inspection.
Full's GERM remains an independent owner; inclusion does not select a generator
engine, checkpoint, source permission or output destination.

Research references and local passages are optional context contracts. They do
not renumber the acoustic gateway, the historical host profile or stored records.
The public MCP recipe subset excludes private passages, earlier conversations
and local re-listening. Installing an owner does not activate an agent plugin,
adopt LISTENING.md, approve material uses or promote an account to canonical memory.

For an upgrade, compare the old/new exact manifests, supported declarations and
store formats first. Finish or cancel running work; preserve the prior environment,
configuration, stores and receipts. Qualify save/reopen and owner handoff in fresh
fixture roots before a separately selected activation. Rollback selects the retained
environment with its matching pre-upgrade stores; do not open new-format data with
older binaries or replay interrupted operations automatically.

P7's private evidence packet records the first selection, its installed boundary
tests and upgrade/rollback rehearsal. Its review and P8 supersede those artifacts
with cohorts r1 and r2 (certifi 2026.10.19 and the repaired local planner worker);
use the newest selected manifest, not one with the same versions. Hardware, learned model quality, human review,
platform releases and service activation require their own named evidence.
