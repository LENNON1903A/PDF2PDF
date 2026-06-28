---
name: translate-pdf-to-zh
description: Translate electronic-text English or Spanish PDFs into Simplified Chinese while preserving the original visual layout. Use for PDF translation, pdf2pdf conversion, layout-preserving Chinese PDF output, DeepSeek-assisted document translation, and documents containing body text, tables, figures, captions, formulas, headers, footers, or tables of contents.
---

# Translate PDF To Chinese

Use the bundled project core instead of improvising PDF parsing or layout rules inside the agent.
Do not modify the source PDF.

## Required Rules

- Translate ordinary body text, headings, and page headers.
- Keep page footers, page numbers, logos, formulas, URLs, numbers, units, acronyms, and proper names unchanged unless they form part of a normal sentence.
- For tables, translate the table title and only the top column-header row. Keep every other table cell unchanged.
- For figures and charts, keep all text inside the image or chart unchanged. Translate only external figure titles and captions.
- For a table of contents, translate entry titles while preserving section numbers, dot leaders, and page numbers.
- Preserve page size, color, visual placement, and bold appearance. Preserve italic appearance when the available Chinese font supports it; otherwise use the closest regular or bold face.
- Prefer Microsoft YaHei regular and bold on Windows. Do not copy proprietary font files into the Skill; use Noto Sans CJK or PingFang as portable fallbacks.
- Keep text that is invisible in the rendered source invisible. In particular, do not translate text fully covered by a later image or solid shape.
- When text does not fit: request a shorter translation, allow additional lines, shrink by up to 15%, then use 80% of the original size if still necessary. Do not add a manual-review marker.
- Always use the standard preset unless the user explicitly requests another preset: 240 DPI and JPEG quality 92.
- Process long documents in 20-page batches by default. Persist completed batch PDFs and the translation cache so interrupted work can resume, then merge batches automatically.

Read [references/layout-rules.md](references/layout-rules.md) before changing classification or rendering behavior.

## Workflow

1. Verify the input is an electronic-text PDF. Do not OCR unless the user provides a scanned document.
2. Run layout analysis before translation:

```powershell
python scripts/run_pdf2zh.py analyze "input.pdf" --output "input.pdf2zh-report.json"
```

3. Inspect the report summary. If table detection is uncertain, preserve the affected table body.
4. Before online translation, tell the user that document text will be sent to DeepSeek.
5. Read the API key only from `DEEPSEEK_API_KEY`. Never request or display it.
6. Cache translations and process in 20-page batches so interrupted jobs can resume.
7. Write output to a new file. Never overwrite the input.
8. Compare page count and dimensions before reporting success.

Run translation after analysis and confirmation that document text may be sent to DeepSeek:

```powershell
python scripts/run_pdf2zh.py translate "input.pdf" --output "input_zh.pdf" --cache "input.pdf2zh-cache.json"
```

Do not ask the user to select a quality preset. The omitted `--quality` option means standard.
Only use `--quality preview` or `--quality print` when the user explicitly requests it.

## Cross-Agent Use

This folder uses plain Markdown and Python and includes its own `lib/pdf2zh` runtime core.
Copy the complete Skill folder when moving it to Codex, WorkBuddy, or another agent.
Do not copy only `SKILL.md`, and do not depend on an agent-specific LLM callback.

The wrapper loads the bundled core first. `PDF2ZH_PROJECT_ROOT` is only a development fallback:

```powershell
python scripts/run_pdf2zh.py quality --json
```

Required packages are listed in `requirements.txt`. If dependencies are missing, stop and explain
what is missing. Do not install software or send document data without the user's confirmation.

Use official DeepSeek defaults. Only honor `DEEPSEEK_MODEL` or `DEEPSEEK_BASE_URL` when the user
or deployment environment explicitly provides them.
