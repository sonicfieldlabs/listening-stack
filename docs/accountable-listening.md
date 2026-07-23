# Accountable Listening Architecture

Listening Stack 0.2.0 treats listening as a chain of bounded contracts, not as
one undifferentiated model response. Each concept has one semantic owner and is
parsed once at the boundary that owns it.

## Ownership

| Boundary | Owner | Contract | Responsibility |
| --- | --- | --- | --- |
| Gateway | Oída | `oida/gateway/v0.4` | Runtime perception, routing, covenant application, and integration surfaces |
| Host input | Oída | `oida/host-perception/v0.3` | Attributed perception supplied by an audio-capable host |
| Listening event | Oída | `oida/listening-event/v0.2` | Cross-surface runtime result with context, apparatus, and disagreement |
| Listening context | AKOÚŌ | `akouo/listening-context/v1` | Position, apertures, scales, sources, participants, authority, and honest absence |
| Claims | AKOÚŌ | `akouo/v0.8` | Listening modes, evidence classes, confidence, and limits |
| Durable auditum | Earworm | `earworm/auditum/v1` | Addressable listening lineage, disagreement, action receipts, revision, and forgetting |
| Memory navigator | Akousmata | `akousmata/v0.5` | Rendering, querying, and structural audit without redefining claims |

“Tokenized auditum” means structured, addressable, and versioned. It does not
mean cryptocurrency, a tradable asset, or a financial token.

## The Runtime Invariants

- A covenant states what the listener may do.
- Position states where and in what relation listening occurred.
- Apparatus states what the listener can sense.
- Apertures state which evidence openings were actually available in this run.
- Claims state what the available evidence supports.
- Action authority states what may be changed; capability alone never grants it.
- Honest absences name unavailable evidence rather than silently filling it in.
- Distinct routes remain distinct listenings, and disagreement remains visible.
- Revision creates lineage. It does not mutate an earlier listening into a new
  historical fact.

For host-supplied perception, the host declaration is retained as attributed
input. Oída derives the effective listening context from what was actually
submitted, clamps authority to observe-only, and does not promote model
observations into measurements when no measurement aperture was open.

## What the Installer Proves

The install plan shows immutable releases and source revisions. Completed
`state.json` records both those commits and the accountable-listening contract
matrix. The installer writes state only after source synchronization and import
verification succeed.

When Oída is running, `listening-stack doctor` verifies:

1. the process identifies as Oída on the configured loopback address;
2. `/gateway` reports Oída 0.8.0 and the expected component contracts;
3. the gateway advertises all required schema endpoints;
4. the host-perception schema requires `oida/host-perception/v0.3`;
5. the listening-event schema requires `oida/listening-event/v0.2`;
6. the listening-context schema requires `akouo/listening-context/v1`.

These checks happen at the live HTTP boundary. Package metadata is useful
evidence, but it is not a substitute for the contract that integrations
actually receive.

## Progressive Disclosure

The normal integration path is deliberately small:

1. install or update the pinned stack;
2. start Oída;
3. run the doctor;
4. integrate a selected host through Oída;
5. inspect detailed component schemas only when extending the protocol.

Component documentation remains canonical for field-level semantics. The
installer owns only compatibility, reproducibility, lifecycle, and verification.
