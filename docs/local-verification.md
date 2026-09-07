# Local installation verification

Use a fresh directory outside development checkouts and a model-free core to
verify the installer before selecting model weights:

```bash
listening-stack install --component core --models none \
  --root /absolute/path/to/disposable-stack --yes --skip-system-dependencies
listening-stack doctor --root /absolute/path/to/disposable-stack --json
```

Install system prerequisites first when using `--skip-system-dependencies`.
This still permits the installer to provision Python 3.12 through uv. Source
fetches and locked dependency downloads may use the network; no model download
or agent integration is selected by this command.

The installer and doctor share an isolated core probe. It imports Oída, AKOÚŌ,
Akousma and Akousmata, checks distribution versions and their source/package
locations, reads the bundled listening-context schema, verifies configured
data/model paths, and checks the navigator's selected store. Python runs with
`-I -B`, so cwd/PYTHONPATH cannot provide missing packages and the probe writes no
bytecode or store records. Packaged distributions must originate from the managed
source projects and reside in the managed environment. External editable sources,
missing schemas, version drift and redirected store paths fail the check.

Doctor also checks exact repository pins and live gateway contracts. A schema
may declare the expected contract through `const` or a compatible `enum`; if both
are present, both must permit the expected value. A healthy HTTP endpoint alone
does not establish compatibility. Doctor's schema check verifies advertised
contract versions, not the full semantic equivalence of every schema constraint.

The default port may already belong to another Oída installation. Doctor reports
that process's contracts; it does not prove process ownership or that it is using
the selected store. For an isolated live check, use an unused loopback port in
the disposable installation's environment/state and start its own interpreter
with `python -I -m oida.server --profile stub --host 127.0.0.1 --port PORT`.
Apply that installation's environment to the process, stop the exact process
you started, and restore the temporary configuration after the check. Do not
stop an existing unrelated service to make the test pass.

## Migration and rollback scope

Version 1 installation state remains readable. Rerunning the same profile with
this installer writes version 2 state. Keep copies of `.listening-stack/state.json`
and `stack.env` before testing migration, and verify retained data separately.
They contain local paths and belong in private evidence, not a public report.

Restoring those two files can test configuration rollback at unchanged source
revisions. It does not roll back a Python environment, source update or record
schema migration. Installation updates are not transactional across repositories
and environments; a failed update may leave sources changed with older completed
state. Restore a verified whole installation backup or rerun the pinned installer
to recover. The installer never automatically deletes retained data.

## Evidence and remaining checks

Local verification on macOS arm64 with Python 3.12 exercised a fresh core install,
built core packages, a live stub gateway and all 28 doctor checks, plus version
1-to-2 configuration migration and restoration at unchanged pins. The dependency
inventory records installed distribution metadata and retained licence-file hashes;
missing metadata is an explicit absence, not an inferred licence approval.

This evidence covers the released pinned core with unreleased installer fixes.
Unpublished working-tree changes in other repositories are not part of that pin
set. Linux, macOS Intel, optional GERM/full profiles, model/provider downloads,
accelerators, devices and agent integrations still need their own fresh-install
evidence. A Linux container being available on the test host is not such evidence.
The installer version and released compatibility pins remain unchanged.
