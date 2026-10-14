# LISTENING.md inscription candidate

Installer 0.6.1 adds `listening-md-core/v1` for a separately selected, unpublished wheel bundle. Its exact application versions are Oída 0.13.2, Akousma 0.10.1, Akousmata 0.9.1, AKOÚŌ 0.12.1 and Listening Stack 0.6.1. Khipu is a separate private consumer. This profile contains no GERM or model weights.

The existing managed installer and the historical candidate profiles keep their published/source selections. Choosing a newer candidate does not rewrite those selections. Every wheel in a bundle is named by version and SHA-256, including its runtime dependencies. The candidate verifier preflights the complete bundle before creating an environment. Installation requires a fresh directory outside source checkouts and uses explicit offline wheel paths.

```sh
listening-stack candidate verify /absolute/bundle/manifest.json
listening-stack candidate install /absolute/bundle/manifest.json --root /absolute/fresh/runtime
listening-stack candidate doctor --root /absolute/fresh/runtime
```

The diagnostic compares installed owner files with the original archives before inspecting their declarations. `inscriptions` reports the installed owner's seven conventions, text account/work outputs, byte limits, canonical file directions and lifecycle contracts. It calls only the declarative capability handler and reads verified packaged resources. It creates no store, probes no provider and adopts no file. Configured models, source uses, authority, token budgeting and actual execution remain explicit owner responsibilities.

TTT listening can encounter a primary inscription; TTT sounding can produce a completed textual work. That work can return as another operation's subject without an acoustic render. Conventions for JSON, Morse, notation, glyphs, code and MIDI describe representations and projections, with original bytes kept separately. They do not establish an acoustic event or phenomenal experience.

Required unsupported controls stop at their actual owner gate. A changing draft leaves the current exact adoption intact. Source read, execution, retention and disclosure permissions remain distinct. The five example files stay illustrative until selected and adopted under the enclosing authority.

The `owner-test` extra selects this exact owner cohort from `vendor/`; `owner-test-wheels.json`, `SHA256SUMS` and `uv.lock` name its bytes. Earlier wheels remain registered for conservation. The tests run installed packages with isolated paths; source repositories are not import fallbacks.

The current candidate is local software qualification. It is not a public release, model qualification, active-owner rollout or hosted-service claim.
