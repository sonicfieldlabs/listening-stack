"""Inspect installed research declarations without reading sources or owners."""
from __future__ import annotations

from importlib.metadata import version


def installed_capabilities():
    # Lazy imports keep managed bootstrap and historical profiles independent.
    from oida.local_passages import CONTRACT as local_contract, MAX_PASSAGE_BYTES
    from oida.research_references import CONTEXT_CONTRACT, REFERENCE_CONTRACT
    from oida.research_recipes import descriptions
    from oida.sonicfield_discovery import ENDPOINT, RESULT_CONTRACT

    recipe = descriptions()
    if (recipe["contract"] != "oida/research-recipe/v1"
            or recipe["names"] != ["selected_context_return", "local_relisten_return"]
            or recipe["automatic_source_selection"] is not False
            or recipe["automatic_continuation"] is not False):
        raise ValueError("Unsupported installed research recipe declaration")
    return {
        "contract": "listening-stack/research-support/v1",
        "state": "installed_software",
        "owners": {name: version(name) for name in
                   ("sonicfield-oida", "akousma", "akousmata", "akouo-contract")},
        "contracts": {"reference": REFERENCE_CONTRACT, "context": CONTEXT_CONTRACT,
                      "local_passage": local_contract, "public_result": RESULT_CONTRACT},
        "recipes": recipe,
        "local_passage_max_bytes": MAX_PASSAGE_BYTES,
        "public_endpoint": ENDPOINT,
        "source_read": "not_requested", "public_network": "not_probed",
        "provider_availability": "not_probed", "model_execution": "not_requested",
        "owner_activation": "not_requested", "host_connection": "not_configured",
        "canonical_memory_promotion": "not_requested",
    }
