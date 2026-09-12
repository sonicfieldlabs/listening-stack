# Policy-aware memory restore (D5, unreleased)

Run `listening-stack restore-memory bundle.zip --store CURRENT_STORE` from an
installed core environment containing Akousmata/Earworm. The current initialized
store and its forgetting ledger must exist. The command delegates verified E17
import to Akousmata; it never replaces the database or installs an old ledger.

Identity/hash conflicts, unsupported reader contracts, current restricted consent
and forgotten IDs refuse restoration. Old/new reader negotiation is explicit;
canonical 1.6/1.7 payloads and unknown private extensions retain their identity.
An identical retry reuses records. Graph imports require the owner-selected
installed MASA validator/core modules documented by Akousmata.

Rollback means returning to a prior pinned runtime with its declared reader
capabilities. It never means rolling back revocations. An old reader must reject
new unsupported records before applying the bundle. Contract/identity checks run
before writes; an unexpected I/O/concurrent-policy failure during the additive
batch can leave earlier accepted records, so retry reuses them. This does not
promise atomic filesystem/database rollback or restoration of external audio.

The D5 evidence installs local wheel builds outside sibling checkouts and checks
manifest negotiation, repeated import, conflicts and restore through the current
ledger. Package runtime and synthetic evidence remain distinct from a loaded
model, physical-device or full platform installation gate.
