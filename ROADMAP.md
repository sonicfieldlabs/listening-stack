# Roadmap

The roadmap describes public-alpha direction and does not promise dates.

## Near Term

- Signed release artifacts in addition to SHA-256 checksums.
- More precise CUDA, Apple unified-memory, CPU, and free-disk preflight.
- Resumable install summaries after interrupted provider or model downloads.
- Released-artifact smoke tests that exercise Oída's accountable-listening
  gateway and one model-free Oída-to-GERM handoff.
- Screen-reader and low-vision terminal audits.
- Compatibility-set migration previews with release notes before changing pins.
- Contract-diff previews that distinguish additive schema changes from semantic
  ownership or authority changes.

## Toward Beta

- Migration previews and explicit upgrade commands for future installer-state
  contracts beyond the backward-readable version 2 format.
- Opt-in version-channel selection beyond the default tested compatibility set.
- Reproducible provider-lock metadata and model revision pinning.
- Optional signed desktop launchers built from the same assistant core.
- End-to-end smoke fixtures that start both model-free gateways and complete one
  Oída-to-GERM handoff.

## Non-Goals

- Merging the component repositories or their histories.
- Redistributing third-party model weights.
- Accepting licenses, creating accounts, or managing cloud billing for users.
- Opening local gateways to external networks automatically.
- Treating a successful install as a judgment about output quality, consent,
  rights, or appropriate use.

D7 provides a separate unpublished, checksum-pinned offline core/app candidate and
native Pi adapter compatibility. See [candidate release and handoff](docs/candidate-release.md).
Published Git tag/SHA promotion awaits actual release commits; L2 broader host/profile
qualification remains open. No local candidate implies a pushed release.
