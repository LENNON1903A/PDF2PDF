from __future__ import annotations

import re
from collections.abc import Iterable

CAPTION_RE = re.compile(
    r"^\s*(fig(?:ure|ura)?|table|tabla|chart|gr[aá]fico)\s*\d+[\s.:]",
    re.IGNORECASE,
)
TABLE_TITLE_RE = re.compile(
    r"^\s*(?:table|tabla)(?:\s+\d+[\s.:]|\s+de\b)",
    re.IGNORECASE,
)
TOC_DOTS_RE = re.compile(r"\.{5,}\s*\d+\s*$")
URL_RE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
FORMULA_RE = re.compile(r"[∑√≤≥≈∞]|\\(?:frac|sum|sqrt)|[A-Za-z]\s*=\s*[^,.;]{2,}")
ONLY_DATA_RE = re.compile(r"^[\d\s.,:%$€£¥+\-–—()/]+$")
ACRONYM_RE = re.compile(r"^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9./&+\-]{1,}$")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def is_caption(text: str) -> bool:
    return bool(CAPTION_RE.match(normalize_text(text)))


def is_table_title(text: str) -> bool:
    return bool(TABLE_TITLE_RE.match(normalize_text(text)))


def is_toc_entry(text: str) -> bool:
    return bool(TOC_DOTS_RE.search(normalize_text(text)))


def should_keep_verbatim(text: str) -> bool:
    compact = normalize_text(text)
    if not compact:
        return True
    if not any(character.isalnum() for character in compact):
        return True
    if (
        URL_RE.search(compact)
        or ONLY_DATA_RE.fullmatch(compact)
        or ACRONYM_RE.fullmatch(compact)
    ):
        return True
    if FORMULA_RE.search(compact) and len(compact) < 120:
        if ":" in compact or "：" in compact:
            return False
        return True
    return False


def bbox_inside(
    bbox: tuple[float, float, float, float],
    container: tuple[float, float, float, float],
    tolerance: float = 2.0,
) -> bool:
    x0, y0, x1, y1 = bbox
    cx0, cy0, cx1, cy1 = container
    return x0 >= cx0 - tolerance and y0 >= cy0 - tolerance and x1 <= cx1 + tolerance and y1 <= cy1 + tolerance


def overlaps_any(
    bbox: tuple[float, float, float, float],
    containers: Iterable[tuple[float, float, float, float]],
) -> bool:
    x0, y0, x1, y1 = bbox
    return any(
        min(x1, cx1) > max(x0, cx0) and min(y1, cy1) > max(y0, cy0)
        for cx0, cy0, cx1, cy1 in containers
    )
