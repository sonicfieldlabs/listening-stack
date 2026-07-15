# Roadmap

The roadmap describes public-alpha direction and does not promise dates.

## Near Term

- Signed release artifacts in addition to SHA-256 checksums.
- More precise CUDA, Apple unified-memory, CPU, and free-disk preflight.
- Resumable install summaries after interrupted provider or model downloads.
- Contract tests against released Oída and GERM installer surfaces.
- Screen-reader and low-vision terminal audits.
- Explicit update previews showing source commits before checkout.

## Toward Beta

- Stable installer-state migrations.
- Version-channel selection for application tags and tested compatibility sets.
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
