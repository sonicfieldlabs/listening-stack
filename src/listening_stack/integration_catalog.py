"""Host adapters qualified against the selected immutable Oída revision."""
from .catalog import REPOSITORIES, profile_includes


OIDA_INTEGRATIONS = {
    # Oída 0.10.0: matches its integrate parser and adapter implementations.
    "4f934c7854bceda044f5be22f2567315d4af7ba2": (
        "hermes", "codex", "claude", "openclaw", "opencode",
    ),
}


def supported_integrations(profile="core", *, revision=None):
    if not profile_includes(profile, "oida"):
        return ()
    selected = REPOSITORIES["oida"].revision if revision is None else revision
    try:
        return OIDA_INTEGRATIONS[selected]
    except KeyError as exc:
        raise ValueError("No reviewed integration capabilities for Oída revision " + str(selected)) from exc


def select_integrations(targets, profile="core", *, revision=None):
    available = supported_integrations(profile, revision=revision)
    invalid = [name for name in targets if name != "all" and name not in available]
    if invalid:
        raise ValueError("Integrations unsupported by the selected Oída compatibility pin: " + ", ".join(invalid))
    if targets and not available:
        raise ValueError("This profile does not include Oída integrations")
    return list(available) if "all" in targets else list(dict.fromkeys(targets))
