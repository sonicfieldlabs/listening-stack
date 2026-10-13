"""Inspect installed inscription adapters without starting owners or probing models."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path


def installed_capabilities():
    # Import inside the opt-in diagnostic: the standalone managed installer remains
    # standard-library-only, and historical candidate profiles need no new owner API.
    from akouo_contract.listening_profiles import load_listening_presets
    from akouo_contract.representations import load_representation_routes
    from akousma.representation_store import RepresentationStore
    from akousmata_app.representations import RepresentationNavigator
    from oida.listening_profiles import LISTENING_CONTRACTS, SUPPORTED_CONTROLS
    from oida.representation_api import build_router

    # Only the installed owner's declarative capability handler is called. Other
    # handlers, registry creation, persistence and provider execution are not invoked.
    router = build_router(data_dir=Path("unused-candidate-capability-probe"),
                          memory_root=lambda: (_ for _ in ()).throw(RuntimeError("No store probe")),
                          workspace_ref="candidate:capability-inspection", actor_ref="candidate:inspection",
                          registry_factory=lambda: (_ for _ in ()).throw(RuntimeError("No provider probe")),
                          require_admin=lambda _request: None)
    handler = next(route.endpoint for route in router.routes
                   if route.path == "/representations/capabilities")
    declaration = handler(None)
    if declaration.get("contract") != "oida/representation-execution/v1" or declaration.get("audio_required") is not False:
        raise ValueError("Unsupported installed inscription capability declaration")
    presets = load_listening_presets()
    routes = load_representation_routes()
    return {
        "contract": "listening-stack/inscription-support/v1", "state": "installed_software",
        "owners": {name: version(name) for name in ("sonicfield-oida", "akousma", "akousmata", "akouo-contract")},
        "execution": {key: declaration[key] for key in ("contract", "status", "conventions", "max_source_bytes",
                      "max_context_bytes", "max_prompt_bytes", "output_forms", "output_kinds", "audio_required",
                      "adoption_default", "token_budget")},
        "routing": {"contract": routes["contract"], "status": routes["status"], "required_contracts": routes["required_contracts"]},
        "lifecycle": {"contract": presets["contract"], "status": presets["status"],
                      "supported_contracts": list(LISTENING_CONTRACTS), "supported_controls": list(SUPPORTED_CONTROLS),
                      "presets": [{key: p[key] for key in ("id", "revision_ref", "document_sha256", "adoption", "example_kind")}
                                  for p in presets["presets"]]},
        "custody": {"owner": "akousma", "adapter": RepresentationStore.__name__},
        "navigation": {"owner": "akousmata", "adapter": RepresentationNavigator.__name__},
        "provider_availability": "not_probed", "model_execution": "not_requested",
        "owner_activation": "not_requested", "acoustic_realization": "not_requested",
    }
