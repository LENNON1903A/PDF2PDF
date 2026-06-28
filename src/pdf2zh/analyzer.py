from __future__ import annotations

import statistics
from pathlib import Path

import fitz

from .models import PageAnalysis, TextBlock, TextStyle
from .rules import (
    bbox_inside,
    is_caption,
    is_table_title,
    is_toc_entry,
    normalize_text,
    overlaps_any,
    should_keep_verbatim,
)


def _style_from_spans(spans: list[dict]) -> TextStyle:
    first = spans[0]
    font = str(first.get("font", ""))
    flags = int(first.get("flags", 0))
    lower_font = font.lower()
    return TextStyle(
        font=font,
        size=float(first.get("size", 10.0)),
        color=int(first.get("color", 0)),
        bold="bold" in lower_font or bool(flags & 16),
        italic="italic" in lower_font or "oblique" in lower_font or bool(flags & 2),
    )


def _covered_text_regions(page: fitz.Page) -> list[tuple[float, float, float, float]]:
    try:
        entries = page.get_bboxlog()
    except Exception:
        return []

    covered: list[tuple[float, float, float, float]] = []
    for index, (kind, bbox, *_rest) in enumerate(entries):
        if kind not in {"fill-text", "stroke-text"}:
            continue
        text_bbox = tuple(float(value) for value in bbox)
        if any(
            later_kind in {"fill-image", "fill-path"}
            and bbox_inside(text_bbox, tuple(float(value) for value in later_bbox), tolerance=1)
            for later_kind, later_bbox, *_later_rest in entries[index + 1 :]
        ):
            covered.append(text_bbox)
    return covered


def _extract_table_regions(page: fitz.Page) -> tuple[list[tuple], list[tuple]]:
    fragments: list[tuple] = []
    try:
        finder = page.find_tables()
    except Exception:
        return [], []

    for table in finder.tables:
        bbox = tuple(float(v) for v in table.bbox)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if (
            width < page.rect.width * 0.35
            or height < 8
            or (bbox[1] < 5 and height < 120)
        ):
            continue
        fragments.append(bbox)

    merged: list[list[float]] = []
    for x0, y0, x1, y1 in sorted(fragments, key=lambda item: (item[1], item[0])):
        if merged:
            region = merged[-1]
            overlap = max(0.0, min(x1, region[2]) - max(x0, region[0]))
            narrower = min(x1 - x0, region[2] - region[0])
            if narrower and overlap / narrower >= 0.7 and y0 <= region[3] + 35:
                region[0] = min(region[0], x0)
                region[1] = min(region[1], y0)
                region[2] = max(region[2], x1)
                region[3] = max(region[3], y1)
                continue
        merged.append([x0, y0, x1, y1])

    table_bboxes = [tuple(region) for region in merged]
    header_bboxes = [
        (x0, max(0.0, y0 - 28.0), x1, min(y1, y0 + 5.0))
        for x0, y0, x1, y1 in table_bboxes
        if y1 - y0 >= 22.0
    ]
    return table_bboxes, header_bboxes


def _extract_figure_regions(
    page: fitz.Page,
    table_bboxes: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    if not hasattr(page, "cluster_drawings"):
        return []
    regions = []
    drawings = page.get_drawings()
    text_blocks = [block for block in page.get_text("blocks") if block[4].strip()]
    for rect in page.cluster_drawings():
        bbox = tuple(float(value) for value in rect)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < page.rect.width * 0.4 or height < page.rect.height * 0.12:
            continue
        if bbox[1] < 5:
            continue
        drawing_count = sum(
            fitz.Rect(drawing["rect"]).intersects(fitz.Rect(bbox))
            for drawing in drawings
        )
        inside_text = [
            normalize_text(block[4])
            for block in text_blocks
            if bbox_inside(
                (float(block[0]), float(block[1]), float(block[2]), float(block[3])),
                bbox,
                tolerance=3,
            )
        ]
        average_text_length = (
            sum(len(text) for text in inside_text) / len(inside_text)
            if inside_text
            else 0
        )
        if drawing_count < 4 and not (
            drawing_count >= 3
            and len(inside_text) >= 3
            and average_text_length <= 35
        ):
            continue
        overlapping_tables = [table for table in table_bboxes if overlaps_any(bbox, [table])]
        if overlapping_tables:
            figure_area = width * height
            table_area = sum(
                (table[2] - table[0]) * (table[3] - table[1])
                for table in overlapping_tables
            )
            if figure_area <= table_area * 1.4:
                continue
        regions.append(bbox)
    return regions


def analyze_page(page: fitz.Page, page_number: int) -> PageAnalysis:
    raw_blocks = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
    sizes = [
        float(span.get("size", 0))
        for block in raw_blocks
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span.get("text", "").strip()
    ]
    body_size = statistics.median(sizes) if sizes else 10.0
    table_bboxes, header_bboxes = _extract_table_regions(page)
    figure_bboxes = _extract_figure_regions(page, table_bboxes)
    covered_text_bboxes = _covered_text_regions(page)
    for table_bbox in table_bboxes:
        candidates: dict[int, list[tuple[float, float, float, float]]] = {}
        for block in raw_blocks:
            for line in block.get("lines", []):
                line_bbox = tuple(float(v) for v in line["bbox"])
                if not bbox_inside(line_bbox, table_bbox, tolerance=3):
                    continue
                spans = [span for span in line.get("spans", []) if span.get("text", "").strip()]
                if not spans:
                    continue
                style = _style_from_spans(spans)
                if not style.bold:
                    continue
                candidates.setdefault(round(line_bbox[1] / 3), []).append(line_bbox)
        for boxes in sorted(candidates.values(), key=lambda items: min(box[1] for box in items)):
            if len(boxes) < 3:
                continue
            header_bboxes.append(
                (
                    min(box[0] for box in boxes),
                    min(box[1] for box in boxes) - 2,
                    max(box[2] for box in boxes),
                    max(box[3] for box in boxes) + 2,
                )
            )
            break
    result = PageAnalysis(
        page=page_number,
        width=float(page.rect.width),
        height=float(page.rect.height),
        table_bboxes=table_bboxes,
        figure_bboxes=figure_bboxes,
    )

    extracted_lines = [
        (block_index, block, line)
        for block_index, block in enumerate(raw_blocks)
        for line in block.get("lines", [])
        if any(span.get("text", "").strip() for span in line.get("spans", []))
    ]

    for index, (block_index, block, line) in enumerate(extracted_lines):
        spans = [span for span in line.get("spans", []) if span.get("text", "")]
        text = "".join(span.get("text", "") for span in spans).strip()
        if not text:
            continue

        bbox = tuple(float(v) for v in line["bbox"])
        style = _style_from_spans(spans)
        compact = normalize_text(text)
        kind = "body"
        translate = True
        reason = "ordinary text"

        overlapping_table = next(
            (table for table in table_bboxes if overlaps_any(bbox, [table])),
            None,
        )
        inside_figure = any(
            bbox_inside(bbox, figure, tolerance=3) for figure in figure_bboxes
        )
        if any(bbox_inside(bbox, hidden, tolerance=3) for hidden in covered_text_bboxes):
            kind, translate, reason = "keep", False, "text fully covered by a later image or shape"
        elif inside_figure:
            kind, translate, reason = "keep", False, "text inside chart or vector figure"
        elif any(bbox_inside(bbox, header, tolerance=4) for header in header_bboxes):
            kind, translate, reason = "table_header", True, "top row of detected table"
        elif overlapping_table:
            kind, translate, reason = "keep", False, "table body remains in source language"
        elif is_table_title(compact):
            kind, translate, reason = "table_title", True, "table title outside table"
        elif is_caption(compact):
            kind, translate, reason = "caption", True, "external figure or table caption"
        elif is_toc_entry(compact):
            kind, translate, reason = "toc", True, "translate title and preserve numbers"
        elif bbox[1] > page.rect.height * 0.94:
            kind, translate, reason = "keep", False, "footer or page number"
        elif should_keep_verbatim(compact):
            kind, translate, reason = "keep", False, "formula, URL, number, or protected token"
        elif style.size >= body_size * 1.2:
            kind, translate, reason = "heading", True, "heading"

        result.blocks.append(
            TextBlock(
                page=page_number,
                index=index,
                group_index=block_index,
                text=text,
                bbox=bbox,
                style=style,
                kind=kind,
                translate=translate,
                reason=reason,
                line_count=1,
            )
        )
    return result


def analyze_pdf(path: str | Path) -> list[PageAnalysis]:
    document = fitz.open(str(path))
    try:
        return [analyze_page(page, index + 1) for index, page in enumerate(document)]
    finally:
        document.close()
