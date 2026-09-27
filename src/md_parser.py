"""
md_parser.py
Deterministic Markdown AST parser for agentic document processing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InlineSpan:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link: Optional[str] = None


@dataclass
class Token:
    pass


@dataclass
class HeadingToken(Token):
    level: int
    text: str


@dataclass
class ParagraphToken(Token):
    text: str


@dataclass
class CalloutToken(Token):
    callout_type: str  # NOTE, TIP, IMPORTANT, WARNING, CAUTION, INFO
    text: str


@dataclass
class BulletListToken(Token):
    items: List[str] = field(default_factory=list)


@dataclass
class OrderedListToken(Token):
    items: List[str] = field(default_factory=list)


@dataclass
class CodeBlockToken(Token):
    language: str
    code: str


@dataclass
class TableToken(Token):
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class DividerToken(Token):
    pass


def parse_inline_spans(text: str) -> List[InlineSpan]:
    """Parses markdown inline styling: bold, italic, code, links."""
    # Pattern matching bold-italic, bold, italic, code, links
    pattern = re.compile(
        r"(\*\*\*(.*?)\*\*\*)"                       # 1: bold+italic
        r"|(\*\*(.*?)\*\*)"                          # 3: bold
        r"|(\*(.*?)\*)"                              # 5: italic
        r"|(`(.*?)`)"                                # 7: inline code
        r"|(\[(.*?)\]\((.*?)\))"                     # 9: link [text](url)
    )

    spans: List[InlineSpan] = []
    last_idx = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            spans.append(InlineSpan(text=text[last_idx:start]))

        if match.group(1):  # bold italic
            spans.append(InlineSpan(text=match.group(2), bold=True, italic=True))
        elif match.group(3):  # bold
            spans.append(InlineSpan(text=match.group(4), bold=True))
        elif match.group(5):  # italic
            spans.append(InlineSpan(text=match.group(6), italic=True))
        elif match.group(7):  # code
            spans.append(InlineSpan(text=match.group(8), code=True))
        elif match.group(9):  # link
            spans.append(InlineSpan(text=match.group(10), link=match.group(11)))

        last_idx = end

    if last_idx < len(text):
        spans.append(InlineSpan(text=text[last_idx:]))

    return spans if spans else [InlineSpan(text=text)]


class MarkdownParser:
    """Parses standard markdown content into a list of block tokens."""

    def __init__(self, content: str):
        self.raw_lines = content.splitlines()

    def parse(self) -> List[Token]:
        tokens: List[Token] = []
        i = 0
        total_lines = len(self.raw_lines)

        while i < total_lines:
            line = self.raw_lines[i]
            line_strip = line.strip()

            # Empty line
            if not line_strip:
                i += 1
                continue

            # Code block
            if line_strip.startswith("```"):
                lang = line_strip[3:].strip()
                code_lines = []
                i += 1
                while i < total_lines and not self.raw_lines[i].strip().startswith("```"):
                    code_lines.append(self.raw_lines[i])
                    i += 1
                i += 1  # Skip closing ```
                tokens.append(CodeBlockToken(language=lang, code="\n".join(code_lines)))
                continue

            # Horizontal rule
            if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", line_strip):
                tokens.append(DividerToken())
                i += 1
                continue

            # Headings
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line_strip)
            if heading_match:
                level = len(heading_match.group(1))
                htext = heading_match.group(2).strip()
                tokens.append(HeadingToken(level=level, text=htext))
                i += 1
                continue

            # Callouts or Blockquotes
            if line_strip.startswith(">"):
                callout_type = "NOTE"
                callout_lines = []
                first_line = re.sub(r"^>\s*", "", line_strip)
                alert_match = re.match(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|INFO)\]\s*(.*)$", first_line, re.IGNORECASE)
                if alert_match:
                    callout_type = alert_match.group(1).upper()
                    if alert_match.group(2):
                        callout_lines.append(alert_match.group(2))
                else:
                    callout_lines.append(first_line)

                i += 1
                while i < total_lines and self.raw_lines[i].strip().startswith(">"):
                    cleaned = re.sub(r"^>\s*", "", self.raw_lines[i].strip())
                    callout_lines.append(cleaned)
                    i += 1

                tokens.append(CalloutToken(callout_type=callout_type, text=" ".join(callout_lines)))
                continue

            # Tables
            if "|" in line_strip and line_strip.startswith("|") and line_strip.endswith("|"):
                headers = [c.strip() for c in line_strip.strip("|").split("|")]
                rows = []
                i += 1
                # Skip divider line (| :--- | :--- |)
                if i < total_lines and re.match(r"^\|(?:\s*[:\-]+\s*\|)+$", self.raw_lines[i].strip()):
                    i += 1
                while i < total_lines and "|" in self.raw_lines[i] and self.raw_lines[i].strip().startswith("|"):
                    row = [c.strip() for c in self.raw_lines[i].strip("|").split("|")]
                    rows.append(row)
                    i += 1
                tokens.append(TableToken(headers=headers, rows=rows))
                continue

            # Bullet List
            if re.match(r"^[\*\-]\s+(.*)$", line_strip):
                items = []
                while i < total_lines and re.match(r"^[\*\-]\s+(.*)$", self.raw_lines[i].strip()):
                    m = re.match(r"^[\*\-]\s+(.*)$", self.raw_lines[i].strip())
                    items.append(m.group(1))
                    i += 1
                tokens.append(BulletListToken(items=items))
                continue

            # Ordered List
            if re.match(r"^\d+\.\s+(.*)$", line_strip):
                items = []
                while i < total_lines and re.match(r"^\d+\.\s+(.*)$", self.raw_lines[i].strip()):
                    m = re.match(r"^\d+\.\s+(.*)$", self.raw_lines[i].strip())
                    items.append(m.group(1))
                    i += 1
                tokens.append(OrderedListToken(items=items))
                continue

            # Regular Paragraph
            para_lines = [line_strip]
            i += 1
            while i < total_lines:
                next_line = self.raw_lines[i].strip()
                if not next_line or next_line.startswith("#") or next_line.startswith(">") or next_line.startswith("```") or next_line.startswith("|") or re.match(r"^[\*\-]\s+", next_line) or re.match(r"^\d+\.\s+", next_line) or re.match(r"^(\-{3,}|\*{3,}|_{3,})$", next_line):
                    break
                para_lines.append(next_line)
                i += 1

            tokens.append(ParagraphToken(text=" ".join(para_lines)))

        return tokens
