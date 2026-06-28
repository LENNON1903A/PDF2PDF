# Layout And Translation Rules

## Contents

1. Translation scope
2. Table rules
3. Figure rules
4. Fitting rules
5. Output quality
6. Safety

## Translation Scope

Translate body text, headings, page headers, external captions, table titles, and
table-of-contents entry titles. Preserve formulas, URLs, standalone data, units, acronyms,
page numbers, footers, and logos.

Preserve hidden source text as hidden. When PDF drawing order shows that a later image or
solid shape fully covers a text object, do not translate or redraw that text. Do not apply
this rule to partial overlap.

## Table Rules

Translate only a table title outside the table and the uppermost column-header row.
Keep all subsequent rows unchanged, including first-column category names, descriptions,
status values, notes, and data. When table detection is uncertain, preserve the content.

## Figure Rules

Treat charts and raster images as indivisible visual content. Do not translate internal
titles, axis labels, legends, callouts, or labels. Translate only external text blocks that
begin with labels such as Figure, Figura, Chart, Table, Tabla, or Grafico.

For vector charts, detect the enclosing drawing cluster by page-relative width and height.
Protect all text inside that region. Do not use page numbers, fixed coordinates, or
document-specific chart labels.

## Fitting Rules

Use Microsoft YaHei (`msyh.ttc`) for regular Chinese text and Microsoft YaHei Bold
(`msyhbd.ttc`) for bold text on Windows. Do not bundle proprietary font files in the Skill.
On other systems, fall back to Noto Sans CJK or PingFang.

Keep the original page dimensions, text color, and visual placement. Preserve bold when a
bold Chinese face is available. Preserve italic only when the selected Chinese font provides
an italic face; otherwise use the closest regular or bold face.

Use this order:

1. Ask the translator for a shorter Chinese rendering.
2. Add lines within the available region.
3. Reduce font size by no more than 15%.
4. If still too large, set the size to 80% of the original and render.

Do not add a warning or manual-review mark to the PDF.

## Output Quality

- Preview: 150 DPI, JPEG 80.
- Standard: 240 DPI, JPEG 92. Use by default.
- Print: 300 DPI, JPEG 95.

Keep page dimensions unchanged. Never overwrite the source.
Do not ask which quality preset to use. Select standard automatically unless the user asks
for preview or print quality.

## Long Documents

- Use 20 pages per batch by default.
- Write each completed batch to a temporary work directory.
- Keep the work directory after interruption and resume from valid completed batches.
- Merge all batches into one PDF after completion, then remove the temporary work directory.
- Refuse to overwrite the source PDF or an existing output PDF.
- Keep the translation cache after completion for inexpensive reruns.
- Namespace translation cache entries by pipeline/model version so changed rules do not reuse
  incompatible cached results.

## Safety

DeepSeek receives document text during online translation. Warn the user before the first
online run. Read the API key from `DEEPSEEK_API_KEY`; never store it in this Skill, source
control, logs, reports, or generated PDFs.
