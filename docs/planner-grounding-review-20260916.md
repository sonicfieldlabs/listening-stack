# Retained-account grounding regression: 16 September 2026

Status: **semantic qualification failed; no deployment promotion**. This is a
development counterexample, not an unseen holdout or a general accuracy estimate.

## Source and scope

The real connected `planner-central-02` run produced a complete local decision,
correct record/model joins, resolvable citations, and durable restart/replay.
Those technical checks remain valid. They do not validate the prose's truth.

Private source receipt:
`/Volumes/x/dev/sfl/qualification-20260916/planner-central-02/central-connected/central-owner-decision.json`

SHA-256: `661c7bf0375ed6390b2b127d48eb1135a20be56777f4febcf945160af8360962`.

The account describes a one-second mono synthetic tone. Its original unsupported
spatial caption is retained as `undetermined`, with a basis stating the mono
input limitation. `retained_event()` deliberately presents inherited claims as
retained accounts, not fresh measurements. The planner nevertheless repeats
unsupported prose as observations. Do not fix this by rewriting the original
account, relabelling its claims as measured, or dropping the negative evidence.

## Explicit review requirements

1. Stereo placement cannot be established from the offered mono account. A
   summary may report that an account claimed it, but must preserve the caveat.
2. The 1.04-second endpoint contradicts the supplied 1.00-second duration. It
   must be reported as a conflicting claim, not an observed event endpoint.
3. A gap finding rejecting a claim must not coexist with an unqualified
   assertion of the same claim in the summary, findings or next-move reason.
4. Retained inferred/undetermined claims must not become fresh measured facts
   merely by receiving a valid citation.
5. A bounded stop means no further action is proposed within the allowed set;
   it is not proof of completeness or correctness.

These are human-reviewed acceptance criteria. Word matching and JSON-schema
validity are not substitutes for checking entailment and attribution.

## Retained experiments

- `planner-regression-05`: longer grounding instructions, 11/12 reused task
  regressions. The bounded-selection request omits its requested `transcribe`
  specialist, though it selects the correct interval. `planner-grounding-01`
  then fails to produce a complete JSON object. Its raw worker log and request
  are retained; no inference about unretained output content is made.
- `planner-regression-06`: shorter instructions, also 11/12, same omission.
  Worker SHA-256
  `5094484043b4baad46c1df2b0692fa3cb96abf286e9d0442476b9d1572da1076`.
  The bounded retained-evidence replay `planner-grounding-02` generates valid
  JSON with offered citations but **fails requirements 1–4 above** on inspection.
  It asserts centered stereo placement and a controlled studio environment,
  repeats the 1.04-second endpoint, and separately says stereo placement is
  unsupported. It also overstates what the inherited DSP claims establish.
  Output SHA-256
  `e8baffbd21832a9ae385a368ada41d986cbf5ac55895b68109d0aaf56b8b001e`.
  Usage: 5,699 prompt / 1,316 completion tokens.
- `planner-regression-07`: the shorter grounding guidance plus an explicit
  reminder that a re-listen action does not itself select a requested specialist
  restores **12/12** task regressions in 71.26 s. Frozen worker SHA-256
  `a84c2739d51e7156c1bddabebe8d150a8040e68ae6d6af2ae1cc3a1f0937ceb2`;
  evaluation `a8f1fec897377f257962d23b895e493393ee9e11d24db1d3a183c09a53e54dbf`.
  This reused task score is not semantic admission or installed qualification.

`scripts/replay_planner_evidence.py` provides the repeatable local replay lane:
it verifies the frozen worker, checkpoint/runtime file inventory and revision;
uses the shared heavy-operation lease and a 90-second process timeout; offers
only stop with no specialist or interval selection; retains requests, outputs,
hashes and failure logs. It does not reconstruct the original HTTP request or
assert semantic success. It uses no cloud service and performs no admission.

## Next implementation, before promotion

Prompt-only mitigation is insufficient in this observed case. Add an explicit,
non-authorizing quality-review receipt separate from operational completion.
Keep exact source refs and epistemic status available in the owner projection;
surface unresolved contradictions in Central and Station without replacing raw
prose. Assess structured claim/time/channel constraints before prose generation,
and independent consistency checking afterward. Do not label unchecked prose
as verified or use a second model's agreement as ground truth.

Test positive and negative attribution cases, comparison records with different
durations/channels, generated descendants, missing metadata and withheld
evidence. Numeric duration limits must bind to the correct event/input, not a
global duration or an unrelated comparison. Avoid regex-only semantic gates.
Any changed worker must repeat existing capability/action regressions, this
negative replay, new held-out semantic cases and connected owner qualification.

The currently qualified worker remains
`acf5cccb4c92395e70a2a128e3c909881cc08258fa341327ad44f24a1e48c885`.
Its operational qualification is not revoked by this report, but semantic
qualification remains open. Failed prompt variants are preserved in their
private evaluation directories, not installed or promoted.
