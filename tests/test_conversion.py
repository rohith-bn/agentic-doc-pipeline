"""
test_conversion.py
Automated unit tests for agentic-doc-pipeline AST parser and docx generator.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.docx_builder import DocxBuilder
from src.md_parser import (
    CalloutToken,
    CodeBlockToken,
    HeadingToken,
    MarkdownParser,
    ParagraphToken,
    TableToken,
    parse_inline_spans,
)


class TestMarkdownParser(unittest.TestCase):
    def test_heading_parsing(self):
        md = "# Heading 1\n\n## Heading 2\n\n### Heading 3"
        parser = MarkdownParser(md)
        tokens = parser.parse()
        self.assertEqual(len(tokens), 3)
        self.assertTrue(all(isinstance(t, HeadingToken) for t in tokens))
        self.assertEqual(tokens[0].level, 1)
        self.assertEqual(tokens[0].text, "Heading 1")
        self.assertEqual(tokens[1].level, 2)
        self.assertEqual(tokens[2].level, 3)

    def test_callout_parsing(self):
        md = "> [!IMPORTANT]\n> Safety critical parameters require static allocation."
        parser = MarkdownParser(md)
        tokens = parser.parse()
        self.assertEqual(len(tokens), 1)
        self.assertIsInstance(tokens[0], CalloutToken)
        self.assertEqual(tokens[0].callout_type, "IMPORTANT")
        self.assertIn("Safety critical parameters", tokens[0].text)

    def test_table_parsing(self):
        md = "| Metric | Value |\n| :--- | :--- |\n| Frequency | 1 kHz |\n| Jitter | 0 us |"
        parser = MarkdownParser(md)
        tokens = parser.parse()
        self.assertEqual(len(tokens), 1)
        self.assertIsInstance(tokens[0], TableToken)
        self.assertEqual(tokens[0].headers, ["Metric", "Value"])
        self.assertEqual(len(tokens[0].rows), 2)
        self.assertEqual(tokens[0].rows[0], ["Frequency", "1 kHz"])

    def test_inline_spans(self):
        text = "This is **bold**, *italic*, and `code_snippet`."
        spans = parse_inline_spans(text)
        self.assertTrue(any(s.bold for s in spans))
        self.assertTrue(any(s.italic for s in spans))
        self.assertTrue(any(s.code for s in spans))


class TestDocxBuilder(unittest.TestCase):
    def test_build_docx_from_tokens(self):
        md = "# Architecture Specification\n\nDeterministic system test paragraph with **bold** text."
        parser = MarkdownParser(md)
        tokens = parser.parse()

        style_cfg = {
            "page": {"margin_top_cm": 2.0, "margin_bottom_cm": 2.0, "margin_left_cm": 2.0, "margin_right_cm": 2.0},
            "typography": {
                "font_family": "Calibri",
                "font_size_body_pt": 11,
                "line_spacing": 1.15,
                "space_after_pt": 4,
                "headings": {"h1": {"font_family": "Calibri", "font_size_pt": 18, "bold": True, "space_before_pt": 10, "space_after_pt": 4, "color_hex": "0F172A"}}
            },
            "colors": {"text_primary": "1E293B", "accent": "0284C7"}
        }

        builder = DocxBuilder(style_cfg)
        out_dir = PROJECT_ROOT / "output"
        out_file = out_dir / "unit_test_sample.docx"

        result = builder.build(tokens, out_file)
        self.assertTrue(result.exists())
        self.assertGreater(result.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
