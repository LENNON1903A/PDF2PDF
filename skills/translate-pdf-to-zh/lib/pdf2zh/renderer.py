from __future__ import annotations

import io
import json
import re
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import fitz
from PIL import Image, ImageDraw, ImageFont

from .analyzer import analyze_page
from .deepseek import DeepSeekTranslator
from .quality import get_preset

SPANISH_MARKERS = re.compile(r"[áéíóúüñ¿¡]|\b(?:de|del|la|el|para|con|por|una|los|las)\b", re.I)
PIPELINE_VERSION = "layout-v3"
CLOSING_PUNCTUATION = frozenset("，。！？；：、）》】〕〉」』,.!?;:%)")


def _find_fonts() -> tuple[Path, Path]:
    regular_candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), regular)
    if regular is None:
        raise FileNotFoundError(
            "No Chinese font found. Install Microsoft YaHei or Noto Sans CJK."
        )
    return regular, bold or regular


def _rgb(packed: int) -> tuple[int, int, int]:
    return ((packed >> 16) & 255, (packed >> 8) & 255, packed & 255)


def _background(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x0, y0, x1, y1 = box
    width, height = image.size
    points = [
        (max(0, x0 - 4), max(0, y0 - 4)),
        (min(width - 1, x1 + 4), max(0, y0 - 4)),
        (max(0, x0 - 4), min(height - 1, y1 + 4)),
        (min(width - 1, x1 + 4), min(height - 1, y1 + 4)),
    ]
    colors = [image.getpixel(point)[:3] for point in points]
    return tuple(sorted(channel)[len(channel) // 2] for channel in zip(*colors))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_.%/+()-]+|\s+|.", text)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    current = ""
    for token in _tokens(text.replace("\n", " ")):
        candidate = current + token
        if current and draw.textlength(candidate, font=font) > max_width:
            if token in CLOSING_PUNCTUATION:
                lines.append(candidate.rstrip())
                current = ""
            else:
                lines.append(current.rstrip())
                current = token.lstrip()
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines or [text]


def _fit(
    text: str,
    font_path: Path,
    original_size_px: float,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for ratio in (1.0, 0.95, 0.9, 0.85, 0.8):
        size = max(7, round(original_size_px * ratio))
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(text, font, max_width)
        line_height = max(1, round(size * 1.22))
        if len(lines) * line_height <= max_height:
            return font, lines, line_height
    size = max(7, round(original_size_px * 0.8))
    font = ImageFont.truetype(str(font_path), size)
    return font, _wrap(text, font, max_width), max(1, round(size * 1.1))


def _source_language(texts: list[str]) -> str:
    joined = " ".join(texts)
    return "Spanish" if SPANISH_MARKERS.search(joined) else "English"


def _translate_chunks(
    translator: DeepSeekTranslator,
    texts: list[str],
    source_language: str,
    chunk_size: int = 24,
) -> list[str]:
    translated: list[str] = []
    for start in range(0, len(texts), chunk_size):
        translated.extend(
            translator.translate_batch(texts[start : start + chunk_size], source_language)
        )
    return translated


def _connected_groups(
    blocks: list,
    split_starts: list[float] | None = None,
) -> list[list]:
    groups: list[list] = []
    split_starts = split_starts or []
    for block in sorted(blocks, key=lambda item: (item.bbox[1], item.bbox[0])):
        if groups and any(abs(block.bbox[1] - start) <= 2 for start in split_starts):
            groups.append([block])
            continue
        for group in groups:
            gx0 = min(item.bbox[0] for item in group)
            gy0 = min(item.bbox[1] for item in group)
            gx1 = max(item.bbox[2] for item in group)
            gy1 = max(item.bbox[3] for item in group)
            horizontal_overlap = min(gx1, block.bbox[2]) - max(gx0, block.bbox[0])
            vertical_gap = block.bbox[1] - gy1
            if horizontal_overlap > 2 and -3 <= vertical_gap <= 5:
                group.append(block)
                break
        else:
            groups.append([block])
    return groups


def translate_pdf(
    input_path: str,
    output_path: str,
    quality: str = "standard",
    cache_path: str | None = None,
    batch_size: int = 20,
) -> Path:
    source_path = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source_path == target:
        raise ValueError("Output path must be different from the input PDF.")
    if target.exists():
        raise FileExistsError(f"Output PDF already exists: {target}")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if not source_path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source_path}")

    preset = get_preset(quality)
    zoom = preset.dpi / 72.0
    source = fitz.open(str(source_path))
    try:
        if not len(source):
            raise ValueError("Input PDF has no pages.")
        if not any(page.get_text().strip() for page in source):
            raise ValueError(
                "Input PDF has no selectable text. OCR is required before translation."
            )

        translator = DeepSeekTranslator(cache_path=cache_path)
        regular_font, bold_font = _find_fonts()
        target.parent.mkdir(parents=True, exist_ok=True)
        work_dir = target.with_name(f"{target.name}.pdf2zh-work")
        work_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = work_dir / "manifest.json"
        source_stat = source_path.stat()
        manifest = {
            "pipeline_version": PIPELINE_VERSION,
            "source": str(source_path),
            "source_size": source_stat.st_size,
            "source_mtime_ns": source_stat.st_mtime_ns,
            "quality": quality,
            "batch_size": batch_size,
        }
        if manifest_path.exists():
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing_manifest != manifest:
                raise RuntimeError(
                    f"Existing work directory belongs to a different job: {work_dir}"
                )
        else:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        part_paths = []
        for batch_start in range(0, len(source), batch_size):
            batch_end = min(len(source), batch_start + batch_size)
            part_path = work_dir / f"pages-{batch_start + 1:04d}-{batch_end:04d}.pdf"
            part_paths.append(part_path)
            if _valid_part(part_path, source, batch_start, batch_end):
                continue
            temporary_part = part_path.with_name(
                f"{part_path.name}.{uuid.uuid4().hex}.tmp"
            )
            part_document = fitz.open()
            try:
                for page_index in range(batch_start, batch_end):
                    _render_page(
                        source[page_index],
                        page_index,
                        part_document,
                        translator,
                        regular_font,
                        bold_font,
                        zoom,
                        preset.jpeg_quality,
                    )
                part_document.save(str(temporary_part), deflate=True)
            finally:
                part_document.close()
            temporary_part.replace(part_path)

        merged = fitz.open()
        temporary_target = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            for part_path in part_paths:
                part = fitz.open(str(part_path))
                try:
                    merged.insert_pdf(part)
                finally:
                    part.close()
            merged.save(str(temporary_target), deflate=True)
        finally:
            merged.close()
        temporary_target.replace(target)
        shutil.rmtree(work_dir)
        return target
    finally:
        source.close()


def _valid_part(
    part_path: Path,
    source: fitz.Document,
    start: int,
    end: int,
) -> bool:
    if not part_path.exists():
        return False
    try:
        part = fitz.open(str(part_path))
        if len(part) != end - start:
            return False
        return all(
            part[index - start].rect == source[index].rect
            for index in range(start, end)
        )
    except Exception:
        return False
    finally:
        if "part" in locals():
            part.close()


def _render_page(
    page: fitz.Page,
    page_index: int,
    output: fitz.Document,
    translator: DeepSeekTranslator,
    regular_font: Path,
    bold_font: Path,
    zoom: float,
    jpeg_quality: int,
) -> None:
    analysis = analyze_page(page, page_index + 1)
    grouped: dict[tuple[int, str], list] = {}
    list_starts: dict[int, list[float]] = {}
    for block in analysis.blocks:
        if block.translate:
            grouped.setdefault((block.group_index, block.kind), []).append(block)
        elif block.text.strip() and not any(
            character.isalnum() for character in block.text
        ):
            list_starts.setdefault(block.group_index, []).append(block.bbox[1])
    targets = []
    for (group_index, _kind), blocks in grouped.items():
        for connected in _connected_groups(blocks, list_starts.get(group_index)):
            targets.append(
                SimpleNamespace(
                    text=" ".join(block.text for block in connected),
                    bbox=(
                        min(block.bbox[0] for block in connected),
                        min(block.bbox[1] for block in connected),
                        max(block.bbox[2] for block in connected),
                        max(block.bbox[3] for block in connected),
                    ),
                    style=connected[0].style,
                    kind=connected[0].kind,
                )
            )
    targets.sort(key=lambda block: (block.bbox[1], block.bbox[0]))
    texts = [target.text for target in targets]
    translations = (
        _translate_chunks(translator, texts, _source_language(texts)) if texts else []
    )

    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    draw = ImageDraw.Draw(image)
    next_y: dict[int, float] = {}
    for position, block in enumerate(targets):
        lower = [
            candidate.bbox[1]
            for candidate in targets[position + 1 :]
            if candidate.bbox[1] > block.bbox[1] + 1
            and candidate.bbox[0] < block.bbox[2]
            and candidate.bbox[2] > block.bbox[0]
        ]
        next_y[id(block)] = min(lower) if lower else analysis.height

    for block, translated in zip(targets, translations):
        x0 = round(block.bbox[0] * zoom)
        y0 = round(block.bbox[1] * zoom)
        x1 = round(block.bbox[2] * zoom)
        y1 = round(block.bbox[3] * zoom)
        pad = max(2, round(zoom))
        bg = _background(image, (x0, y0, x1, y1))
        draw.rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), fill=bg)
        available_bottom = min(
            analysis.height,
            max(block.bbox[3], next_y[id(block)] - 1.5),
        )
        max_height = max(y1 - y0, round((available_bottom - block.bbox[1]) * zoom))
        max_width = max(8, x1 - x0)
        font_path = bold_font if block.style.bold else regular_font
        font, lines, line_height = _fit(
            translated,
            font_path,
            block.style.size * zoom,
            max_width,
            max_height,
        )
        color = _rgb(block.style.color)
        for line_index, line in enumerate(lines):
            draw.text(
                (x0, y0 + line_index * line_height),
                line,
                fill=color,
                font=font,
            )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    out_page = output.new_page(width=page.rect.width, height=page.rect.height)
    out_page.insert_image(out_page.rect, stream=buffer.getvalue())
