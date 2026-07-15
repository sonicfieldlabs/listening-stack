"""Pinned projects and model planning data used by the installer.

Static model sizes are fallbacks captured from the official Hugging Face API.
The CLI can refresh them before installation without requiring a token.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Iterable, List, Mapping, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GIB = 1024**3


@dataclass(frozen=True)
class Repository:
    key: str
    name: str
    url: str
    branch: str = "main"
    version: str = ""


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

    @property
    def url(self) -> str:
        return "https://huggingface.co/" + self.model_id

    @property
    def size_gb(self) -> float:
        return self.size_bytes / 1_000_000_000


REPOSITORIES: Mapping[str, Repository] = {
    "oida": Repository(
        "oida",
        "Oída",
        "https://github.com/sonicfieldlabs/oida.git",
        version="0.6.0",
    ),
    "germ": Repository(
        "germ",
        "GERM",
        "https://github.com/sonicfieldlabs/germ.git",
        version="0.2.0",
    ),
    "akouo": Repository(
        "akouo",
        "AKOÚŌ",
        "https://github.com/sonicfieldlabs/akouo.git",
        version="0.7.0",
    ),
    "earworm": Repository(
        "earworm",
        "Earworm",
        "https://github.com/sonicfieldlabs/earworm.git",
        version="0.4.0",
    ),
    "akousmata": Repository(
        "akousmata",
        "Akousmata",
        "https://github.com/sonicfieldlabs/akousmata.git",
        version="0.4.0",
    ),
}

OIDA_SOURCE_KEYS: Tuple[str, ...] = ("earworm", "akouo", "akousmata", "oida")
GERM_SOURCE_KEYS: Tuple[str, ...] = ("germ",)

MOSS_AUDIO_REPOSITORY = Repository(
    "moss-audio",
    "MOSS-Audio",
    "https://github.com/OpenMOSS/MOSS-Audio.git",
    branch="main",
)
STABLE_AUDIO_REPOSITORY = Repository(
    "stable-audio-3",
    "Stable Audio 3",
    "https://github.com/Stability-AI/stable-audio-3.git",
    branch="main",
)


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

RUNTIME_RESERVE_GB: Mapping[str, int] = {"oida": 7, "germ": 9, "full": 14}


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
    return RUNTIME_RESERVE_GB[component] + model_disk_gb(models) * 1.15


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
    refreshed: List[Model] = []
    warnings: List[str] = []
    for model in models:
        request = Request(
            "https://huggingface.co/api/models/" + model.model_id,
            headers={"User-Agent": "sonicfield-listening-stack/0.1"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            value = payload.get("usedStorage")
            if isinstance(value, int) and value > 0:
                refreshed.append(replace(model, size_bytes=value))
            else:
                refreshed.append(model)
                warnings.append(
                    "No live size was reported for %s; using the catalog estimate."
                    % model.label
                )
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            refreshed.append(model)
            warnings.append("Could not refresh %s: %s" % (model.label, exc))
    return refreshed, warnings


def format_gb(size_bytes: int) -> str:
    return "%.2f GB" % (size_bytes / 1_000_000_000)
