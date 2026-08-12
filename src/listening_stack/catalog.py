"""Pinned projects and model planning data used by the installer.

Static model sizes are fallbacks captured from the official Hugging Face API.
The CLI can refresh them before installation without requiring a token.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import __version__


MAX_MODEL_API_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class Repository:
    key: str
    name: str
    url: str
    ref: str = "main"
    version: str = ""
    revision: str = ""


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    model_id: str
    application: str
    family: str
    size_bytes: int
    minimum_ram_gb: int
    recommended_ram_gb: int
    license_label: str
    gated: bool
    role: str
    hardware: str
    download_revision: str = ""

    @property
    def url(self) -> str:
        return "https://huggingface.co/" + self.model_id

    @property
    def size_gb(self) -> float:
        return self.size_bytes / 1_000_000_000


REPOSITORIES: Mapping[str, Repository] = {
    "oida": Repository(
        key="oida",
        name="Oída",
        url="https://github.com/sonicfieldlabs/oida.git",
        ref="v0.10.0",
        version="0.10.0",
        revision="4f934c7854bceda044f5be22f2567315d4af7ba2",
    ),
    "germ": Repository(
        key="germ",
        name="GERM",
        url="https://github.com/sonicfieldlabs/germ.git",
        ref="v0.5.0",
        version="0.5.0",
        revision="2b765983e2e6c89008d4d6f8fba9701876ee4783",
    ),
    "akouo": Repository(
        key="akouo",
        name="AKOÚŌ",
        url="https://github.com/sonicfieldlabs/akouo.git",
        ref="v0.9.2",
        version="0.9.2",
        revision="d3c0405279ae00e3b6e1ebc46136aefa0889ab7a",
    ),
    "earworm": Repository(
        key="earworm",
        name="Earworm",
        url="https://github.com/sonicfieldlabs/earworm.git",
        ref="v0.7.0",
        version="0.7.0",
        revision="c130fa61423517a0cc2ca8071124537978fad825",
    ),
    "akousmata": Repository(
        key="akousmata",
        name="Akousmata",
        url="https://github.com/sonicfieldlabs/akousmata.git",
        ref="v0.7.0",
        version="0.7.0",
        revision="838029d80360e04a01149437f30610503fd66794",
    ),
}

# GERM consumes these released protocols over explicit interoperability
# boundaries. They are compatibility references, not installer-managed source
# checkouts: the Listening Stack installs GERM and records which independent
# releases its bridge was reviewed against.
GERM_INTEROPERABILITY_REPOSITORIES: Mapping[str, Repository] = {
    "masa": Repository(
        key="masa",
        name="MASA",
        url="https://github.com/sonicfieldlabs/MASA.git",
        ref="v0.2.0",
        version="0.2.0",
        revision="a967339d77cb7adfb977061e6f3299ff27e55619",
    ),
    "cosmoaudition": Repository(
        key="cosmoaudition",
        name="Cosmoaudition",
        url="https://github.com/sonicfieldlabs/cosmoaudition.git",
        ref="v0.2.0",
        version="0.2.0",
        revision="d56e76a2be7b3385fc3b0ce5a9f3b307f502b4f6",
    ),
}

GERM_INTEROPERABILITY_CONTRACTS: Mapping[str, str] = {
    "masa_version": "0.2.0",
    "masa_matter_record": (
        "https://masa.sonicfield.org/schemas/0.2.0/matter-record.schema.json"
    ),
    "masa_processing_request": (
        "https://masa.sonicfield.org/schemas/0.2.0/processing-request.schema.json"
    ),
    "cosmoaudition_version": "0.2.0",
    "cosmoaudition_bridge": "cosmoaudition-germ/v0.2",
    "cosmoaudition_modulation": "cosmo/modulation/v0.2",
    "cosmoaudition_signal_catalog": "cosmo/signal-catalog/v0.2",
}


def germ_interoperability_metadata() -> Dict[str, object]:
    """Return JSON-compatible compatibility metadata for GERM profiles."""

    return {
        "contracts": dict(GERM_INTEROPERABILITY_CONTRACTS),
        "repositories": {
            key: {
                "name": repository.name,
                "url": repository.url,
                "ref": repository.ref,
                "version": repository.version,
                "revision": repository.revision,
            }
            for key, repository in sorted(
                GERM_INTEROPERABILITY_REPOSITORIES.items()
            )
        },
    }

# One semantic owner per contract. The installer records this matrix in local
# state and the doctor verifies it at Oída's live gateway/schema boundary.
ACCOUNTABLE_LISTENING_CONTRACTS: Mapping[str, str] = {
    "gateway": "oida/gateway/v0.6",
    "host_perception": "oida/host-perception/v0.4",
    "listening_event": "oida/listening-event/v0.3",
    "route_outcome": "oida/route-outcome/v0.1",
    "listening_context": "akouo/listening-context/v2",
    "akouo": "akouo/v0.9",
    "earworm": "earworm/v0.7",
    "akousma_schema": "1.6",
    "auditum": "earworm/auditum/v2",
    "akousmata": "akousmata/v0.7",
}

# These are semantic declarations advertised by Oída's read-only gateway
# manifest. They describe storage behavior; they do not grant write authority.
MEMORY_ACCOUNT_CAPABILITIES: Mapping[str, object] = {
    "separate_human_and_machine_records": True,
    "classification_source": "auditum.listenings[].listener_type",
    "human_revisions": "additive_new_record",
    "machine_core_immutable": True,
}

CORE_SOURCE_KEYS: Tuple[str, ...] = ("earworm", "akouo", "akousmata", "oida")
GERM_SOURCE_KEYS: Tuple[str, ...] = ("germ",)

MOSS_AUDIO_REPOSITORY = Repository(
    key="moss-audio",
    name="MOSS-Audio",
    url="https://github.com/OpenMOSS/MOSS-Audio.git",
    ref="main",
    revision="5cbb1d823937cd5b5de3d8fa4d3a7253ebd3b883",
)
STABLE_AUDIO_REPOSITORY = Repository(
    key="stable-audio-3",
    name="Stable Audio 3",
    url="https://github.com/Stability-AI/stable-audio-3.git",
    ref="main",
    # Match the immutable source revision in GERM v0.5.0's uv.lock.
    revision="fa5ee841dd49bae0fa361fac26904adc27fd400e",
)

ALL_REPOSITORIES: Mapping[str, Repository] = {
    **REPOSITORIES,
    MOSS_AUDIO_REPOSITORY.key: MOSS_AUDIO_REPOSITORY,
    STABLE_AUDIO_REPOSITORY.key: STABLE_AUDIO_REPOSITORY,
}


MODELS: Mapping[str, Model] = {
    "moss-4b-instruct": Model(
        "moss-4b-instruct",
        "MOSS-Audio 4B Instruct",
        "OpenMOSS-Team/MOSS-Audio-4B-Instruct",
        "oida",
        "MOSS-Audio",
        10_451_725_200,
        16,
        24,
        "Apache-2.0",
        False,
        "Direct instruction following and fast listening passes",
        "Apple Silicon, CUDA, or CPU; local inference speed varies",
        download_revision="6907a499dc0e87cc77c8ae0fe23fd0eb5476a02d",
    ),
    "moss-4b-thinking": Model(
        "moss-4b-thinking",
        "MOSS-Audio 4B Thinking",
        "OpenMOSS-Team/MOSS-Audio-4B-Thinking",
        "oida",
        "MOSS-Audio",
        10_451_727_872,
        16,
        24,
        "Apache-2.0",
        False,
        "Deeper listening, music analysis, and bounded re-listening",
        "Apple Silicon, CUDA, or CPU; local inference speed varies",
        download_revision="0099773e141bd410bc698c03c9a029e7c2ec8169",
    ),
    "moss-8b-instruct": Model(
        "moss-8b-instruct",
        "MOSS-Audio 8B Instruct",
        "OpenMOSS-Team/MOSS-Audio-8B-Instruct",
        "oida",
        "MOSS-Audio",
        18_111_010_792,
        24,
        48,
        "Apache-2.0",
        False,
        "Larger direct-instruction listening model",
        "A high-memory Apple Silicon or CUDA system is recommended",
        download_revision="6521a39181b47a18f2d9f4b3acfb5bca7b76b57f",
    ),
    "moss-8b-thinking": Model(
        "moss-8b-thinking",
        "MOSS-Audio 8B Thinking",
        "OpenMOSS-Team/MOSS-Audio-8B-Thinking",
        "oida",
        "MOSS-Audio",
        18_111_010_792,
        24,
        48,
        "Apache-2.0",
        False,
        "Larger reasoning model for complex listening passes",
        "A high-memory Apple Silicon or CUDA system is recommended",
        download_revision="3d09aad8d7803dd131c8f42d2c09364d1f9367db",
    ),
    "stable-small-sfx": Model(
        "stable-small-sfx",
        "Stable Audio 3 Small SFX",
        "stabilityai/stable-audio-3-small-sfx",
        "germ",
        "Stable Audio 3",
        3_493_474_189,
        8,
        16,
        "Stability AI Community License + component terms",
        True,
        "Fast sound-effect generation and editing, up to 120 seconds",
        "CPU, CUDA, or Apple Silicon optimized path",
    ),
    "stable-small-music": Model(
        "stable-small-music",
        "Stable Audio 3 Small Music",
        "stabilityai/stable-audio-3-small-music",
        "germ",
        "Stable Audio 3",
        3_493_474_189,
        8,
        16,
        "Stability AI Community License + component terms",
        True,
        "Fast music generation and editing, up to 120 seconds",
        "CPU, CUDA, or Apple Silicon optimized path",
    ),
    "stable-medium": Model(
        "stable-medium",
        "Stable Audio 3 Medium",
        "stabilityai/stable-audio-3-medium",
        "germ",
        "Stable Audio 3",
        10_445_205_909,
        16,
        24,
        "Stability AI Community License + component terms",
        True,
        "Higher-quality music and sound generation, up to 380 seconds",
        "CUDA GPU; upstream reports about 6.5 GB peak VRAM",
    ),
}

MODEL_PRESETS: Mapping[str, Mapping[str, Tuple[str, ...]]] = {
    "core": {
        "recommended": ("moss-4b-instruct", "moss-4b-thinking"),
        "4b": ("moss-4b-instruct", "moss-4b-thinking"),
        "8b": ("moss-8b-instruct", "moss-8b-thinking"),
        "all": (
            "moss-4b-instruct",
            "moss-4b-thinking",
            "moss-8b-instruct",
            "moss-8b-thinking",
        ),
        "none": (),
    },
    "oida": {
        "recommended": ("moss-4b-instruct", "moss-4b-thinking"),
        "4b": ("moss-4b-instruct", "moss-4b-thinking"),
        "8b": ("moss-8b-instruct", "moss-8b-thinking"),
        "all": (
            "moss-4b-instruct",
            "moss-4b-thinking",
            "moss-8b-instruct",
            "moss-8b-thinking",
        ),
        "none": (),
    },
    "germ": {
        "recommended": ("stable-small-sfx", "stable-small-music"),
        "small": ("stable-small-sfx", "stable-small-music"),
        "medium": ("stable-medium",),
        "all": ("stable-small-sfx", "stable-small-music", "stable-medium"),
        "none": (),
    },
    "full": {
        "recommended": (
            "moss-4b-instruct",
            "moss-4b-thinking",
            "stable-small-sfx",
            "stable-small-music",
        ),
        "all": tuple(MODELS),
        "none": (),
    },
}

RUNTIME_RESERVE_GB: Mapping[str, int] = {
    "core": 7,
    "oida": 7,
    "germ": 9,
    "full": 14,
}


def normalize_profile(profile: str) -> str:
    """Return the canonical install profile, retaining the old Oída alias."""
    if profile == "oida":
        return "core"
    if profile in {"core", "germ", "full"}:
        return profile
    raise ValueError("profile must be core, germ, or full")


def profile_includes(profile: str, application: str) -> bool:
    canonical = normalize_profile(profile)
    if application == "oida":
        return canonical in {"core", "full"}
    if application == "germ":
        return canonical in {"germ", "full"}
    raise ValueError("application must be oida or germ")


def source_keys(component: str) -> Tuple[str, ...]:
    profile = normalize_profile(component)
    if profile == "core":
        return CORE_SOURCE_KEYS
    if profile == "germ":
        return GERM_SOURCE_KEYS
    if profile == "full":
        return CORE_SOURCE_KEYS + GERM_SOURCE_KEYS
    raise AssertionError("unreachable install profile")


def selected_models(
    keys: Sequence[str], catalog: Mapping[str, Model] = MODELS
) -> List[Model]:
    unknown = [key for key in keys if key not in catalog]
    if unknown:
        raise ValueError("Unknown model selection: " + ", ".join(unknown))
    return [catalog[key] for key in keys]


def preset_models(component: str, preset: str) -> Tuple[str, ...]:
    try:
        return MODEL_PRESETS[component][preset]
    except KeyError as exc:
        choices = ", ".join(sorted(MODEL_PRESETS.get(component, {})))
        raise ValueError(
            "Unknown model preset %r. Choices: %s" % (preset, choices)
        ) from exc


def model_disk_gb(models: Iterable[Model]) -> float:
    return sum(model.size_bytes for model in models) / 1_000_000_000


def planned_disk_gb(component: str, models: Sequence[Model]) -> float:
    # Keep 15% download/extraction headroom in addition to source and environments.
    return RUNTIME_RESERVE_GB[normalize_profile(component)] + model_disk_gb(models) * 1.15


def memory_guidance(models: Sequence[Model]) -> Tuple[int, int]:
    """Return recommended RAM for one model and for two app models concurrently."""
    if not models:
        return (8, 8)
    single = max(model.recommended_ram_gb for model in models)
    oida = max(
        (m.recommended_ram_gb for m in models if m.application == "oida"), default=0
    )
    germ = max(
        (m.recommended_ram_gb for m in models if m.application == "germ"), default=0
    )
    concurrent = max(single, oida + germ)
    return (single, concurrent)


def refresh_model_sizes(
    models: Sequence[Model], timeout: float = 12.0
) -> Tuple[List[Model], List[str]]:
    if not models:
        return [], []
    workers = min(4, len(models))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(
            executor.map(lambda model: _refresh_model_size(model, timeout), models)
        )
    refreshed = [model for model, _ in results]
    warnings = [warning for _, warning in results if warning]
    return refreshed, warnings


def _refresh_model_size(model: Model, timeout: float) -> Tuple[Model, Optional[str]]:
    request = Request(
        "https://huggingface.co/api/models/" + model.model_id,
        headers={"User-Agent": "sonicfield-listening-stack/%s" % __version__},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_MODEL_API_BYTES + 1)
        if len(raw) > MAX_MODEL_API_BYTES:
            raise ValueError("model metadata response is too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("model metadata response is not an object")
        value = payload.get("usedStorage")
        if type(value) is int and value > 0:
            return replace(model, size_bytes=value), None
        return (
            model,
            "No live size was reported for %s; using the catalog estimate."
            % model.label,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return model, "Could not refresh %s: %s" % (model.label, exc)


def format_gb(size_bytes: int) -> str:
    return "%.2f GB" % (size_bytes / 1_000_000_000)
