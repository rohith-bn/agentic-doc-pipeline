"""
cli.py
Command Line Interface for agentic-doc-pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.docx_builder import DocxBuilder
    from src.md_parser import MarkdownParser
    from src.pdf_converter import convert_docx_to_pdf
else:
    from .docx_builder import DocxBuilder
    from .md_parser import MarkdownParser
    from .pdf_converter import convert_docx_to_pdf

STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"


def load_style(style_arg: str) -> dict:
    # 1. Check if direct JSON file path
    p = Path(style_arg)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    # 2. Check in builtin styles directory
    candidate = STYLES_DIR / f"{style_arg}.json"
    if candidate.exists():
        with open(candidate, "r", encoding="utf-8") as f:
            return json.load(f)

    # 3. Default fallback to modern_tech
    default_p = STYLES_DIR / "modern_tech.json"
    if default_p.exists():
        with open(default_p, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def cmd_build(args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input markdown file does not exist: {input_path}", file=sys.stderr)
        return 1

    content = input_path.read_text(encoding="utf-8")
    parser = MarkdownParser(content)
    tokens = parser.parse()

    style_cfg = load_style(args.style)
    builder = DocxBuilder(style_cfg)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".docx")
    out_docx = builder.build(tokens, output_path)
    print(f"[SUCCESS] Generated Word document: {out_docx.resolve()}")
    return 0


def cmd_pdf(args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input docx file does not exist: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else None
    try:
        pdf_out = convert_docx_to_pdf(input_path, output_path)
        print(f"[SUCCESS] Converted to PDF: {pdf_out.resolve()}")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


def cmd_pipeline(args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input markdown file does not exist: {input_path}", file=sys.stderr)
        return 1

    content = input_path.read_text(encoding="utf-8")
    tokens = MarkdownParser(content).parse()
    style_cfg = load_style(args.style)

    docx_out_path = Path(args.output_docx) if args.output_docx else input_path.with_suffix(".docx")
    DocxBuilder(style_cfg).build(tokens, docx_out_path)
    print(f"[SUCCESS] Generated Word document: {docx_out_path.resolve()}")

    if args.no_pdf:
        return 0

    pdf_out_path = Path(args.output_pdf) if args.output_pdf else docx_out_path.with_suffix(".pdf")
    try:
        convert_docx_to_pdf(docx_out_path, pdf_out_path)
        print(f"[SUCCESS] Converted to PDF: {pdf_out_path.resolve()}")
        return 0
    except Exception as e:
        print(f"[WARNING] Word DOCX generated, but PDF conversion skipped: {e}", file=sys.stderr)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-doc",
        description="Deterministic Markdown to styled DOCX and PDF converter engine for AI workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: build
    p_build = subparsers.add_parser("build", help="Convert Markdown to styled .docx")
    p_build.add_argument("--input", "-i", required=True, help="Input Markdown file path.")
    p_build.add_argument("--style", "-s", default="modern_tech", help="Style name (din_5008, modern_tech) or path to JSON.")
    p_build.add_argument("--output", "-o", help="Target .docx file path.")
    p_build.set_defaults(func=cmd_build)

    # Subcommand: pdf
    p_pdf = subparsers.add_parser("pdf", help="Convert .docx to .pdf")
    p_pdf.add_argument("--input", "-i", required=True, help="Input .docx file path.")
    p_pdf.add_argument("--output", "-o", help="Target .pdf file path.")
    p_pdf.set_defaults(func=cmd_pdf)

    # Subcommand: pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Convert Markdown to .docx AND .pdf in one step")
    p_pipe.add_argument("--input", "-i", required=True, help="Input Markdown file path.")
    p_pipe.add_argument("--style", "-s", default="din_5008", help="Style profile name or JSON path.")
    p_pipe.add_argument("--output-docx", help="Target .docx file path.")
    p_pipe.add_argument("--output-pdf", help="Target .pdf file path.")
    p_pipe.add_argument("--no-pdf", action="store_true", help="Skip PDF generation.")
    p_pipe.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
