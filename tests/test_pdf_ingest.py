"""
test_pdf_ingest.py
Automated unit tests for PDFIngestor (reverse ingestion pipeline).
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf as fitz  # PyMuPDF
from src.pdf_ingest import IngestionResult, PDFIngestor


class TestPDFIngestor(unittest.TestCase):
    def setUp(self):
        self.test_dir = PROJECT_ROOT / "tests" / "fixtures"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.sample_pdf_path = self.test_dir / "sample_digital.pdf"
        self.scanned_pdf_path = self.test_dir / "sample_scanned.pdf"
        self.image_pdf_path = self.test_dir / "sample_with_image.pdf"

        # 1. Generate digital PDF with text and table
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (50, 72),
            "# Engineering Architecture Specification\n\n"
            "This document verifies the deterministic reverse ingestion pipeline.\n\n"
            "Feature Summary:\n"
            "- Sub-second parsing\n"
            "- Markdown table preservation\n"
            "- Zero token burn\n\n",
            fontsize=12,
        )
        # Add a table-like layout
        table_text = (
            "| Subsystem | Clock Rate | Margin |\n"
            "| :--- | :--- | :--- |\n"
            "| SPI Flash | 80 MHz | 25% |\n"
            "| CAN Bus | 500 kbps | 14.3% |\n"
        )
        page.insert_text((50, 200), table_text, fontsize=10)
        doc.save(str(self.sample_pdf_path))
        doc.close()

        # 2. Generate scanned mock PDF (pure image on page, no text)
        doc_scanned = fitz.open()
        p_scanned = doc_scanned.new_page()
        # Create a tiny 10x10 pixmap
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), 1)
        pix.clear_with(255)
        p_scanned.insert_image(fitz.Rect(50, 50, 200, 200), pixmap=pix)
        doc_scanned.save(str(self.scanned_pdf_path))
        doc_scanned.close()

    def tearDown(self):
        # Clean up generated test artifacts
        for f in [self.sample_pdf_path, self.scanned_pdf_path, self.image_pdf_path]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

    def test_parse_page_range(self):
        # Range parsing
        self.assertEqual(PDFIngestor.parse_page_range("1-3", 10), [0, 1, 2])
        self.assertEqual(PDFIngestor.parse_page_range("1,3,5", 10), [0, 2, 4])
        self.assertEqual(PDFIngestor.parse_page_range("4", 5), [3])
        self.assertIsNone(PDFIngestor.parse_page_range(None, 5))
        self.assertIsNone(PDFIngestor.parse_page_range("", 5))

    def test_digital_pdf_ingestion(self):
        ingestor = PDFIngestor(self.sample_pdf_path)
        out_md = self.test_dir / "extracted_sample.md"
        result = ingestor.ingest(output_md_path=out_md)

        self.assertIsInstance(result, IngestionResult)
        self.assertEqual(result.page_count, 1)
        self.assertGreater(result.char_count, 50)
        self.assertFalse(result.is_scanned)
        self.assertIn("Engineering Architecture Specification", result.markdown)
        self.assertTrue(out_md.exists())

        # Cleanup
        if out_md.exists():
            out_md.unlink()

    def test_scanned_pdf_warning(self):
        ingestor = PDFIngestor(self.scanned_pdf_path)
        result = ingestor.ingest()
        self.assertTrue(result.is_scanned)
        self.assertIsNotNone(result.warning)
        self.assertIn("OCR preprocessing is required", result.warning)

    def test_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            PDFIngestor("non_existent_file.pdf")


if __name__ == "__main__":
    unittest.main()
