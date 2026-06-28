from __future__ import annotations

import argparse
import json

from .quality import PRESETS
from .report import write_analysis_report
from .renderer import translate_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2zh")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Create a layout report without translation.")
    analyze.add_argument("input")
    analyze.add_argument("--output", required=True)
    quality = subparsers.add_parser("quality", help="Show output quality presets.")
    quality.add_argument("--json", action="store_true")
    translate = subparsers.add_parser("translate", help="Translate and render a new PDF.")
    translate.add_argument("input")
    translate.add_argument("--output", required=True)
    translate.add_argument("--quality", choices=PRESETS, default="standard")
    translate.add_argument("--cache")
    translate.add_argument("--batch-size", type=int, default=20)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "analyze":
        print(write_analysis_report(args.input, args.output))
    elif args.command == "quality":
        print(
            json.dumps(
                {
                    name: {"dpi": preset.dpi, "jpeg_quality": preset.jpeg_quality}
                    for name, preset in PRESETS.items()
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "translate":
        print(
            translate_pdf(
                args.input,
                args.output,
                quality=args.quality,
                cache_path=args.cache,
                batch_size=args.batch_size,
            )
        )


if __name__ == "__main__":
    main()
