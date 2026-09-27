"""
pdf_converter.py
Cross-platform PDF converter for Word documents with Windows Word COM automation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def convert_docx_to_pdf(docx_path: Path, pdf_path: Optional[Path] = None) -> Path:
    """Converts a .docx file to .pdf using Windows COM interface or docx2pdf."""
    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Windows native Word COM Automation
    if sys.platform == "win32":
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(str(docx_path.resolve()))
            # 17 = wdFormatPDF
            doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)
            doc.Close()
            word.Quit()
            return pdf_path
        except Exception:
            pass

    # Fallback to docx2pdf if installed
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))
        return pdf_path
    except ImportError:
        raise RuntimeError(
            "PDF conversion requires Microsoft Word (via pywin32) or the 'docx2pdf' package.\n"
            "Install pywin32 with: py -3 -m pip install pywin32"
        )
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}")
