from __future__ import annotations

import os
import sys
from pathlib import Path


def find_project_root() -> Path:
    configured = os.getenv("PDF2ZH_PROJECT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3]


bundled_core = Path(__file__).resolve().parents[1] / "lib"
project_core = find_project_root() / "src"
core = bundled_core if (bundled_core / "pdf2zh").is_dir() else project_core
if not (core / "pdf2zh").is_dir():
    raise SystemExit(
        "pdf2zh core not found. Reinstall the complete Skill folder or set "
        "PDF2ZH_PROJECT_ROOT to the project directory."
    )
sys.path.insert(0, str(core))

try:
    from pdf2zh.cli import main  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name in {"fitz", "PIL", "requests"}:
        raise SystemExit(
            f"Missing Python dependency: {exc.name}. Install the packages listed in "
            f"{Path(__file__).resolve().parents[1] / 'requirements.txt'}"
        ) from exc
    raise


if __name__ == "__main__":
    main()
