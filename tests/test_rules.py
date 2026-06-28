import filecmp
from pathlib import Path
import fitz
from pdf2zh.quality import get_preset
from types import SimpleNamespace

from pdf2zh.analyzer import _covered_text_regions
from pdf2zh.deepseek import (
    CACHE_VERSION,
    DeepSeekTranslator,
    fixed_translation,
    normalize_translation,
)
from pdf2zh.renderer import _connected_groups, _find_fonts, _wrap, translate_pdf
from pdf2zh.rules import is_caption, is_table_title, is_toc_entry, should_keep_verbatim


def test_document_rules() -> None:
    assert is_caption("Figura 35. Meses trabajando")
    assert is_caption("Figure 2: Architecture")
    assert is_table_title("Tabla 21. Matriz de comparacion")
    assert is_toc_entry("7.5 Servicios Basicos................44")
    assert should_keep_verbatim("https://example.com")
    assert should_keep_verbatim("95.8%")
    assert should_keep_verbatim("•")
    assert should_keep_verbatim("— — —")
    assert should_keep_verbatim("ENSA")
    assert should_keep_verbatim("IFC")
    assert not should_keep_verbatim("ÍNDICE DE TABLAS")
    assert not should_keep_verbatim("PROYECTO CASCABEL")
    assert not should_keep_verbatim("Gate condition: p >= 0.95")
    assert not should_keep_verbatim("This paragraph should be translated.")


def test_standard_quality() -> None:
    preset = get_preset("standard")
    assert preset.dpi == 240
    assert preset.jpeg_quality == 92


def test_closing_punctuation_does_not_start_a_line() -> None:
    from PIL import ImageFont

    regular, _bold = _find_fonts()
    font = ImageFont.truetype(str(regular), 20)
    lines = _wrap("测试文字。继续", font, 82)
    assert all(not line.startswith("。") for line in lines)


def test_bullet_rows_split_connected_text() -> None:
    blocks = [
        SimpleNamespace(bbox=(92, 95, 540, 110)),
        SimpleNamespace(bbox=(92, 111, 200, 125)),
        SimpleNamespace(bbox=(92, 126, 540, 141)),
    ]
    groups = _connected_groups(blocks, split_starts=[95, 126])
    assert [len(group) for group in groups] == [2, 1]


def test_fully_covered_text_is_hidden() -> None:
    page = SimpleNamespace(
        get_bboxlog=lambda: [
            ("fill-text", (10, 10, 50, 20)),
            ("fill-image", (0, 0, 100, 100)),
        ]
    )
    assert _covered_text_regions(page) == [(10.0, 10.0, 50.0, 20.0)]


def test_partially_covered_text_remains_visible() -> None:
    page = SimpleNamespace(
        get_bboxlog=lambda: [
            ("fill-text", (10, 10, 50, 20)),
            ("fill-image", (30, 0, 100, 100)),
        ]
    )
    assert _covered_text_regions(page) == []


def test_cache_key_includes_version_and_model(tmp_path) -> None:
    translator = DeepSeekTranslator(
        api_key="test-key",
        model="test-model",
        cache_path=tmp_path / "cache.json",
    )
    key = translator._cache_key("English", "Hello")
    assert key.startswith(f"{CACHE_VERSION}|test-model|English|zh|")


def test_document_error_messages_are_localized() -> None:
    assert normalize_translation(
        "图90. Impactos. 58 ¡Error! Marcador no definido."
    ).endswith("错误！未定义书签。")


def test_common_index_headings_have_fixed_translations() -> None:
    assert fixed_translation("ÍNDICE DE TABLAS") == "表格目录"
    assert fixed_translation(" List of Tables ") == "表格目录"
    assert fixed_translation("ÍNDICE DE FIGURAS") == "图目录"


def test_rejects_pdf_without_selectable_text(tmp_path) -> None:
    source = tmp_path / "scan.pdf"
    output = tmp_path / "output.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()
    try:
        translate_pdf(str(source), str(output))
    except ValueError as exc:
        assert "selectable text" in str(exc)
    else:
        raise AssertionError("Expected scanned-PDF protection.")


def test_refuses_input_overwrite(tmp_path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"not opened because validation runs first")
    try:
        translate_pdf(str(source), str(source))
    except ValueError as exc:
        assert "different" in str(exc)
    else:
        raise AssertionError("Expected overwrite protection.")


def test_refuses_existing_output(tmp_path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    source.write_bytes(b"x")
    output.write_bytes(b"x")
    try:
        translate_pdf(str(source), str(output))
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected existing-output protection.")


def test_skill_bundled_core_matches_project() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = project_root / "src" / "pdf2zh"
    bundled = project_root / "skills" / "translate-pdf-to-zh" / "lib" / "pdf2zh"
    source_files = sorted(
        path.relative_to(source)
        for path in source.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    bundled_files = sorted(
        path.relative_to(bundled)
        for path in bundled.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    assert bundled_files == source_files
    assert all(
        filecmp.cmp(source / relative, bundled / relative, shallow=False)
        for relative in source_files
    )
