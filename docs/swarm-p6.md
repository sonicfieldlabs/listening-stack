# P6 local compatibility and rollout

P6 extends the existing Station Program/Run and Oída situated contracts. It requires the P1 event/beat specialists and P2 acoustic owner for the prepared role recipe; generation review uses the existing P5 provider configuration. No new service, port, model installation or environment is needed.

Update Station and Akousmata together and restart the source-based Oída service. Akousmata carries generated ancestry through parent links before serving acoustic candidates. Legacy run/preset payloads are validated with new optional fields defaulting off; original parameter meanings are preserved. Running work is never automatically replayed on restart.

The new optional Run fields are `share_analysis`, `acoustic_retrieval` and `review_generation`; Plan adds `role`. Oída Rules adds `acoustic_retrieval` and `review_generation`. Adaptive specialist/window permissions remain the P4 fields. Receipts are additive fields in existing run/chain JSON; no destructive database migration is required.

Rollback: finish or stop active work, then disable the new recipe options. Existing manual workflows remain available. To install older code, retain the current database backup first and remove new fields from a copy of a new draft; never rewrite old Auditums to force older application compatibility. New P6 drafts are not promised readable by pre-P6 binaries.

The default installer does not provision this research runtime. The local supervisor, ports and private Tailscale ingress remain unchanged. No push or public deployment is part of this phase.
