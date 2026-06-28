from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

BlockKind = Literal["body", "heading", "caption", "table_title", "table_header", "toc", "keep"]


@dataclass
class TextStyle:
    font: str
    size: float
    color: int
    bold: bool
    italic: bool


@dataclass
class TextBlock:
    page: int
    index: int
    group_index: int
    text: str
    bbox: tuple[float, float, float, float]
    style: TextStyle
    kind: BlockKind
    translate: bool
    reason: str
    line_count: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PageAnalysis:
    page: int
    width: float
    height: float
    blocks: list[TextBlock] = field(default_factory=list)
    table_bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    figure_bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "width": self.width,
            "height": self.height,
            "table_bboxes": self.table_bboxes,
            "figure_bboxes": self.figure_bboxes,
            "blocks": [block.to_dict() for block in self.blocks],
        }
