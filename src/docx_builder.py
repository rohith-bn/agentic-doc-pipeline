"""
docx_builder.py
Deterministic Word document generator applying DIN 5008 or modern tech styling profiles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Inches, Pt, RGBColor

from .md_parser import (
    BulletListToken,
    CalloutToken,
    CodeBlockToken,
    DividerToken,
    HeadingToken,
    InlineSpan,
    OrderedListToken,
    ParagraphToken,
    TableToken,
    Token,
    parse_inline_spans,
)


def hex_to_rgb(hex_str: str) -> RGBColor:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) != 6:
        return RGBColor(30, 41, 59)
    return RGBColor(int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))


def set_cell_background(cell, hex_color: str):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color.lstrip("#")}"/>')
    cell._tc.get_or_add_tcPr().append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m_name, m_val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m_name}')
        node.set(qn('w:w'), str(m_val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


class DocxBuilder:
    """Compiles Markdown tokens into a high-standard .docx document."""

    def __init__(self, style_config: Dict[str, Any]):
        self.config = style_config
        self.doc = docx.Document()
        self._apply_page_setup()

    def _apply_page_setup(self):
        page_cfg = self.config.get("page", {})
        section = self.doc.sections[0]
        section.top_margin = Cm(page_cfg.get("margin_top_cm", 2.0))
        section.bottom_margin = Cm(page_cfg.get("margin_bottom_cm", 2.0))
        section.left_margin = Cm(page_cfg.get("margin_left_cm", 2.0))
        section.right_margin = Cm(page_cfg.get("margin_right_cm", 2.0))

        # Base normal style font
        typo = self.config.get("typography", {})
        style_normal = self.doc.styles["Normal"]
        style_normal.font.name = typo.get("font_family", "Calibri")
        style_normal.font.size = Pt(typo.get("font_size_body_pt", 11))
        style_normal.font.color.rgb = hex_to_rgb(self.config.get("colors", {}).get("text_primary", "1E293B"))

    def _append_inline_spans(self, paragraph, spans: List[InlineSpan]):
        typo = self.config.get("typography", {})
        colors = self.config.get("colors", {})
        base_font = typo.get("font_family", "Calibri")

        for span in spans:
            run = paragraph.add_run(span.text)
            run.font.name = base_font
            if span.bold:
                run.bold = True
            if span.italic:
                run.italic = True
            if span.code:
                run.font.name = "Consolas"
                run.font.size = Pt(typo.get("font_size_body_pt", 11) - 1.0)
                run.font.color.rgb = hex_to_rgb(colors.get("accent", "0284C7"))
            if span.link:
                run.font.color.rgb = hex_to_rgb(colors.get("accent", "0284C7"))
                run.underline = True

    def build(self, tokens: List[Token], output_path: Path) -> Path:
        typo = self.config.get("typography", {})
        colors = self.config.get("colors", {})
        headings_cfg = typo.get("headings", {})

        for token in tokens:
            if isinstance(token, HeadingToken):
                p = self.doc.add_paragraph()
                p_format = p.paragraph_format
                h_key = f"h{min(token.level, 3)}"
                h_meta = headings_cfg.get(h_key, {})

                p_format.space_before = Pt(h_meta.get("space_before_pt", 10))
                p_format.space_after = Pt(h_meta.get("space_after_pt", 4))
                p_format.keep_with_next = True

                run = p.add_run(token.text)
                run.font.name = h_meta.get("font_family", typo.get("font_family", "Calibri"))
                run.font.size = Pt(h_meta.get("font_size_pt", 14))
                run.bold = h_meta.get("bold", True)
                run.font.color.rgb = hex_to_rgb(h_meta.get("color_hex", "0F172A"))

            elif isinstance(token, ParagraphToken):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_after = Pt(typo.get("space_after_pt", 4))
                p.paragraph_format.line_spacing = typo.get("line_spacing", 1.15)
                spans = parse_inline_spans(token.text)
                self._append_inline_spans(p, spans)

            elif isinstance(token, BulletListToken):
                for item in token.items:
                    p = self.doc.add_paragraph(style="List Bullet")
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = typo.get("line_spacing", 1.15)
                    spans = parse_inline_spans(item)
                    self._append_inline_spans(p, spans)

            elif isinstance(token, OrderedListToken):
                for item in token.items:
                    p = self.doc.add_paragraph(style="List Number")
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = typo.get("line_spacing", 1.15)
                    spans = parse_inline_spans(item)
                    self._append_inline_spans(p, spans)

            elif isinstance(token, CalloutToken):
                tbl = self.doc.add_table(rows=1, cols=1)
                tbl.autofit = True
                cell = tbl.cell(0, 0)
                set_cell_background(cell, colors.get("callout_bg", "F8FAFC"))
                set_cell_margins(cell, top=140, bottom=140, left=200, right=150)

                # Set callout left border
                tcPr = cell._tc.get_or_add_tcPr()
                accent_hex = colors.get("callout_border", "0284C7").lstrip("#")
                borders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>\n'
                    f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{accent_hex}"/>\n'
                    f'  <w:top w:val="none"/>\n'
                    f'  <w:right w:val="none"/>\n'
                    f'  <w:bottom w:val="none"/>\n'
                    f'</w:tcBorders>'
                )
                tcPr.append(borders)

                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                header_run = p.add_run(f"[{token.callout_type}] ")
                header_run.bold = True
                header_run.font.size = Pt(typo.get("font_size_body_pt", 11) - 0.5)
                header_run.font.color.rgb = hex_to_rgb(colors.get("callout_border", "0284C7"))

                spans = parse_inline_spans(token.text)
                self._append_inline_spans(p, spans)

                # Empty space after table
                spacer = self.doc.add_paragraph()
                spacer.paragraph_format.space_before = Pt(0)
                spacer.paragraph_format.space_after = Pt(4)

            elif isinstance(token, CodeBlockToken):
                tbl = self.doc.add_table(rows=1, cols=1)
                tbl.autofit = True
                cell = tbl.cell(0, 0)
                set_cell_background(cell, colors.get("code_bg", "F1F5F9"))
                set_cell_margins(cell, top=120, bottom=120, left=150, right=150)

                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(token.code)
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
                run.font.color.rgb = hex_to_rgb(colors.get("text_primary", "1E293B"))

                spacer = self.doc.add_paragraph()
                spacer.paragraph_format.space_after = Pt(4)

            elif isinstance(token, TableToken):
                num_cols = len(token.headers)
                tbl = self.doc.add_table(rows=len(token.rows) + 1, cols=num_cols)
                tbl.autofit = True

                # Style header row
                header_bg = colors.get("table_header_bg", "E2E8F0")
                for col_idx, h_text in enumerate(token.headers):
                    cell = tbl.cell(0, col_idx)
                    set_cell_background(cell, header_bg)
                    set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                    p = cell.paragraphs[0]
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    run = p.add_run(h_text)
                    run.bold = True
                    run.font.size = Pt(typo.get("font_size_body_pt", 11) - 0.5)

                # Data rows
                for row_idx, row_data in enumerate(token.rows):
                    for col_idx in range(num_cols):
                        val = row_data[col_idx] if col_idx < len(row_data) else ""
                        cell = tbl.cell(row_idx + 1, col_idx)
                        set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
                        p = cell.paragraphs[0]
                        p.paragraph_format.space_before = Pt(1)
                        p.paragraph_format.space_after = Pt(1)
                        spans = parse_inline_spans(val)
                        self._append_inline_spans(p, spans)

                spacer = self.doc.add_paragraph()
                spacer.paragraph_format.space_after = Pt(4)

            elif isinstance(token, DividerToken):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
                pBdr = parse_xml(
                    f'<w:pBdr {nsdecls("w")}>\n'
                    f'  <w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E1"/>\n'
                    f'</w:pBdr>'
                )
                p._p.get_or_add_pPr().append(pBdr)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(output_path))
        return output_path
