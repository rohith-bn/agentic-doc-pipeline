"""
pdf_ingest.py
Deterministic reverse ingestion engine (PDF -> Markdown).
Extracts text, headers, and tables from digital PDF documents into clean, token-thrifty
GitHub-Flavored Markdown for AI agent context and human documentation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union


@dataclass
class IngestionResult:
    """Encapsulates the output of the PDF ingestion process."""
    markdown: str
    page_count: int
    char_count: int
    image_count: int = 0
    images_saved: List[Path] = field(default_factory=list)
    is_scanned: bool = False
    warning: Optional[str] = None


class PDFIngestor:
    """
    Reverse ingestion engine converting PDF documents into GitHub-Flavored Markdown.
    Supports table reconstruction, page range slicing, and optional image asset extraction.
    """

    def __init__(self, pdf_path: Union[str, Path]):
        self.pdf_path = Path(pdf_path).resolve()
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF document not found: {self.pdf_path}")

    @staticmethod
    def is_ingest_supported() -> bool:
        """Checks if pymupdf4llm or fitz is available in the current Python environment."""
        try:
            import pymupdf4llm  # type: ignore
            return True
        except ImportError:
            try:
                import pymupdf as fitz  # type: ignore
                return True
            except ImportError:
                return False

    @staticmethod
    def parse_page_range(page_spec: Optional[str], total_pages: int) -> Optional[List[int]]:
        """
        Parses human page specifications (e.g. '1-3', '1,4,7', '2') into 0-based page indices.
        Returns None if no specification provided (meaning all pages).
        """
        if not page_spec:
            return None

        selected: set[int] = set()
        parts = [p.strip() for p in page_spec.split(",") if p.strip()]

        for part in parts:
            if "-" in part:
                tokens = part.split("-")
                if len(tokens) == 2 and tokens[0].isdigit() and tokens[1].isdigit():
                    start, end = int(tokens[0]), int(tokens[1])
                    for p in range(start, end + 1):
                        if 1 <= p <= total_pages:
                            selected.add(p - 1)
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    selected.add(p - 1)

        return sorted(list(selected)) if selected else None

    def ingest(
        self,
        output_md_path: Optional[Union[str, Path]] = None,
        extract_images: bool = False,
        images_dir: Optional[Union[str, Path]] = None,
        pages: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingests the PDF and converts it into GitHub-Flavored Markdown.

        Args:
            output_md_path: Optional destination .md file path to write.
            extract_images: If True, writes image files to disk and links them in markdown.
            images_dir: Target directory for extracted images. Defaults to '<output_dir>/images'.
            pages: Page range specification (e.g. '1-5', '1,3,7').
        """
        if not self.is_ingest_supported():
            raise RuntimeError(
                "PDF reverse ingestion requires 'pymupdf4llm'.\n"
                "Install it with: pip install \"agentic-doc-pipeline[ingest]\" or pip install pymupdf4llm"
            )

        import pymupdf as fitz  # PyMuPDF

        doc = fitz.open(str(self.pdf_path))
        total_pages = len(doc)
        selected_pages = self.parse_page_range(pages, total_pages)
        pages_to_process = selected_pages if selected_pages is not None else list(range(total_pages))

        # Check for scanned image-only PDF (no digital text streams)
        total_text_chars = 0
        total_embedded_images = 0
        for p_idx in pages_to_process:
            page = doc[p_idx]
            total_text_chars += len(page.get_text("text").strip())
            total_embedded_images += len(page.get_images())

        is_scanned = total_text_chars < 30 and total_embedded_images > 0
        scanned_warning = None
        if is_scanned:
            scanned_warning = (
                f"Document '{self.pdf_path.name}' contains 0 digital text streams across {len(pages_to_process)} pages. "
                "This appears to be a scanned image-only PDF. OCR preprocessing is required for full text extraction."
            )

        # Setup image extraction paths if requested
        images_saved: List[Path] = []
        target_images_dir: Optional[Path] = None
        if extract_images and total_embedded_images > 0:
            if images_dir:
                target_images_dir = Path(images_dir).resolve()
            elif output_md_path:
                target_images_dir = Path(output_md_path).resolve().parent / "images"
            else:
                target_images_dir = self.pdf_path.parent / "images"
            target_images_dir.mkdir(parents=True, exist_ok=True)

        # Perform markdown conversion
        try:
            import pymupdf4llm

            if extract_images and target_images_dir:
                # pymupdf4llm image extraction
                md_text = pymupdf4llm.to_markdown(
                    doc=doc,
                    pages=pages_to_process,
                    write_images=True,
                    image_path=str(target_images_dir),
                    image_format="png",
                )
                if target_images_dir.exists():
                    images_saved = sorted(list(target_images_dir.glob("*.png")))
            else:
                md_text = pymupdf4llm.to_markdown(
                    doc=doc,
                    pages=pages_to_process,
                    write_images=False,
                )
        except Exception:
            # Fallback to PyMuPDF fitz layout / text parser
            page_chunks: List[str] = []
            for p_idx in pages_to_process:
                page = doc[p_idx]
                page_chunks.append(page.get_text("text"))
            md_text = "\n\n---\n\n".join(page_chunks)

        doc.close()

        # Sanitize markdown (remove excessive blank lines and trailing carriage returns)
        md_text = md_text.replace("\r\n", "\n")
        md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()

        # Insert comment placeholders for images if not extracted to disk
        if not extract_images and total_embedded_images > 0:
            md_text += f"\n\n<!-- Note: {total_embedded_images} embedded image(s) omitted to optimize token thrift. Use --extract-images to preserve image files. -->\n"

        # Write to file if path provided
        if output_md_path:
            out_file = Path(output_md_path).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(md_text, encoding="utf-8")

        return IngestionResult(
            markdown=md_text,
            page_count=len(pages_to_process),
            char_count=len(md_text),
            image_count=len(images_saved) if extract_images else total_embedded_images,
            images_saved=images_saved,
            is_scanned=is_scanned,
            warning=scanned_warning,
        )
