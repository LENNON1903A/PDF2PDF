from dataclasses import dataclass


@dataclass(frozen=True)
class QualityPreset:
    dpi: int
    jpeg_quality: int


PRESETS = {
    "preview": QualityPreset(dpi=150, jpeg_quality=80),
    "standard": QualityPreset(dpi=240, jpeg_quality=92),
    "print": QualityPreset(dpi=300, jpeg_quality=95),
}


def get_preset(name: str) -> QualityPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown quality preset: {name}") from exc

