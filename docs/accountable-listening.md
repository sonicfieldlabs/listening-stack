# Accountable Listening Architecture

Listening Stack 0.4.0 treats listening as a chain of bounded contracts, not as
one undifferentiated model response. Each concept has one semantic owner and is
parsed once at the boundary that owns it.

## Ownership

| Boundary | Owner | Contract | Responsibility |
| --- | --- | --- | --- |
| Gateway | Oída | `oida/gateway/v0.6` | Decision-first runtime perception, routing, covenant application, and integration surfaces |
| Host input | Oída | `oida/host-perception/v0.4` | Attributed perception supplied by an audio-capable host |
| Listening event | Oída | `oida/listening-event/v0.3` | A hearing that actually occurred, with context, passes, provenance, apparatus, decisions, and disagreement |
| Route outcome | Oída | `oida/route-outcome/v0.1` | A complete refusal or other pre-perception stop without a fabricated hearing |
| Listening context | AKOÚŌ | `akouo/listening-context/v2` | Position, apertures, scales, sources, participants, authority, passes, decisions, and honest absence |
| Claims and routes | AKOÚŌ | `akouo/v0.9` | Listening modes, evidence classes, provenance, ensembles, confidence, and limits |
| Durable auditum | Earworm / Akousma 1.6 | `earworm/v0.7` and `earworm/auditum/v2` | Addressable human, agent, plural, hearing, or decision lineage; lossless listener types; disagreement; receipts; and revision |
| Memory navigator | Akousmata | `akousmata/v0.7` | Human/machine rendering, querying, and structural audit without redefining claims |

“Tokenized auditum” means structured, addressable, and versioned. It does not
mean cryptocurrency, a tradable asset, or a financial token.

## The Runtime Invariants

- A covenant states what the listener may do.
- A route decision states whether perception, memory, disclosure, retention, or
  action proceeds. Its outcome is data even when no hearing follows.
- Position states where and in what relation listening occurred.
- Apparatus states what the listener can sense.
- Apertures state which evidence openings were actually available in this run.
- Claims state what the available evidence supports.
- Prompts, transcripts, and contextual descriptions remain attributed text;
  their presence does not prove that a listener heard their contents.
- Action authority states what may be changed; capability alone never grants it.
- Honest absences name unavailable evidence rather than silently filling it in.
- Honest absence, epistemic undetermination, and coded silence are different:
  one names missing evidence, one marks the limit of a claim, and one records a
  decision such as pause, abstain, refuse, withhold, forget, or do not act.
- Distinct routes remain distinct listenings, and disagreement remains visible.
- Several listeners are plural listening, not automatically an ear swarm. An
  ear swarm requires attributable passes and explicit influence edges showing
  reciprocal reorientation while permissions and disagreement remain intact.
- Revision creates lineage. It does not mutate an earlier listening into a new
  historical fact.
- Human and machine accounts remain separate records. Human edits create an
  additive revision; machine listening cores cannot be edited in place.
- Record class is derived from `auditum.listenings[].listener_type`, never from
  a namespace spelling. Other listener types remain lossless.
- Forgetting creates a receipt. A deleted record must not silently resurrect
  through an index, cache, graph, or later import.

For host-supplied perception, the host declaration is retained as attributed
input. Oída derives the effective listening context from what was actually
submitted, clamps authority to observe-only, and does not promote model
observations into measurements when no measurement aperture was open.

## What the Installer Proves

The install plan shows immutable releases and source revisions. Completed
`state.json` records both those commits and the accountable-listening contract
matrix under `listening-stack/state/v2`. Its profile and exact component list
make the four-project core distinguishable from the optional GERM layer. The
installer writes state only after source synchronization and import verification
succeed.

When Oída is running, `listening-stack doctor` verifies:

1. the process identifies as Oída on the configured loopback address;
2. `/gateway` reports Oída 0.10.0 and the expected component contracts;
3. the gateway advertises all required schema endpoints;
4. the host-perception schema requires `oida/host-perception/v0.4`;
5. the listening-event schema requires `oida/listening-event/v0.3`;
6. the listening-context schema requires `akouo/listening-context/v2`;
7. the route-outcome schema requires `oida/route-outcome/v0.1`;
8. the same manifest advertises separate human/machine records,
   `listener_type` classification, additive human revisions, and immutable
   machine cores.

These checks use only GET requests to the live HTTP boundary; the doctor never
creates, revises, or deletes an Akousma. Package metadata is useful
evidence, but it is not a substitute for the contract that integrations
actually receive.

## Progressive Disclosure

The normal integration path is deliberately small:

1. install or update the pinned core, adding GERM only when cultivation is part
   of the intended apparatus;
2. start Oída;
3. run the doctor;
4. integrate a selected host through Oída;
5. inspect detailed component schemas only when extending the protocol.

Component documentation remains canonical for field-level semantics. The
installer owns only compatibility, reproducibility, lifecycle, and verification.
