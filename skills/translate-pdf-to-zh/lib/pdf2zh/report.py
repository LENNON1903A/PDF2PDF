from __future__ import annotations

import json
from pathlib import Path

from .analyzer import analyze_pdf


def write_analysis_report(input_path: str, output_path: str) -> Path:
    pages = analyze_pdf(input_path)
    payload = {
        "input": str(Path(input_path).resolve()),
        "pages": [page.to_dict() for page in pages],
        "summary": {
            "page_count": len(pages),
            "block_count": sum(len(page.blocks) for page in pages),
            "translate_count": sum(block.translate for page in pages for block in page.blocks),
            "kept_count": sum(not block.translate for page in pages for block in page.blocks),
            "table_header_count": sum(
                block.kind == "table_header" for page in pages for block in page.blocks
            ),
        },
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
