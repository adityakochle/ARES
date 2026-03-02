"""PDF processing with text extraction and OCR."""

import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from pathlib import Path
from typing import Generator, Tuple, Optional
import logging
import gc
import tempfile

logger = logging.getLogger(__name__)

# Lower DPI reduces image size and RAM usage (150 = good balance for OCR accuracy)
OCR_DPI = 150


class PDFProcessor:
    """Process PDFs for text extraction and OCR."""

    def __init__(self, ocr_threshold: float = 0.85):
        """
        Initialize PDF processor.

        Args:
            ocr_threshold: Confidence threshold for OCR (0-1)
        """
        self.ocr_threshold = ocr_threshold

    def is_text_pdf(self, pdf_path: str) -> bool:
        """
        Check if PDF contains extractable text.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if PDF has text, False if scanned
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:3]:  # Check first 3 pages
                    text = page.extract_text()
                    if text and len(text.strip()) > 100:
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking PDF type: {e}")
            return False

    def iter_pages(
        self, pdf_path: str
    ) -> Generator[Tuple[int, dict, int, bool], None, None]:
        """
        Yield one page at a time as (page_num, page_data, total_pages, is_text).

        This is the memory-safe entry point for large documents.  For scanned
        PDFs each page is OCR'd, yielded, and freed before the next page is
        loaded — so RAM usage stays constant regardless of document length.

        Args:
            pdf_path: Path to PDF file

        Yields:
            Tuple of (1-based page number, page_data dict, total_pages, is_text)
        """
        pdf_path = str(Path(pdf_path).resolve())
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        is_text = self.is_text_pdf(pdf_path)

        # Get total page count (cheap metadata read)
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

        if is_text:
            # Text PDF: stream pages through pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for idx, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    tables = page.extract_tables()
                    yield idx, {"text": text or "", "tables": tables or []}, total_pages, True
        else:
            # Scanned PDF: write each page image to a temp file on disk so that
            # Python's heap never holds the raw pixel data (~6 MB per page at
            # 150 DPI).  Tesseract reads the file path directly (subprocess),
            # so no PIL Image object is created in the main process.
            with tempfile.TemporaryDirectory() as tmpdir:
                for page_num in range(total_pages):
                    image_paths = convert_from_path(
                        pdf_path,
                        first_page=page_num + 1,
                        last_page=page_num + 1,
                        dpi=OCR_DPI,
                        output_folder=tmpdir,
                        paths_only=True,   # returns file paths, not PIL Images
                    )
                    if not image_paths:
                        logger.warning(f"No image rendered for page {page_num + 1}, skipping")
                        continue

                    img_path = image_paths[0]
                    # Pass the file path — pytesseract hands it straight to the
                    # tesseract subprocess, keeping pixel data out of Python heap
                    text = pytesseract.image_to_string(img_path)
                    confidence = min(0.95, len(text) / 1000)

                    page_data = {
                        "text": text,
                        "tables": [],
                        "ocr_confidence": confidence,
                    }

                    # Delete the temp image file immediately
                    Path(img_path).unlink(missing_ok=True)
                    gc.collect()

                    logger.info(f"OCR page {page_num + 1}/{total_pages}")
                    yield page_num + 1, page_data, total_pages, False

            logger.info(f"OCR complete: {total_pages} pages processed")

    # ------------------------------------------------------------------
    # Legacy bulk methods — kept for backward compatibility
    # ------------------------------------------------------------------

    def extract_text_pdf(self, pdf_path: str) -> Tuple[dict, int]:
        """Extract all text pages from a text-based PDF into a dict."""
        pages_dict: dict = {}
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                for idx, page in enumerate(pdf.pages, 1):
                    pages_dict[idx] = {
                        "text": page.extract_text() or "",
                        "tables": page.extract_tables() or [],
                    }
            logger.info(f"Extracted text from {total_pages} pages")
            return pages_dict, total_pages
        except Exception as e:
            logger.error(f"Error extracting text PDF: {e}")
            return {}, 0

    def extract_scanned_pdf(self, pdf_path: str) -> Tuple[dict, int]:
        """
        Extract text from scanned PDF using OCR.

        Warning: loads all pages into memory before returning.
        For large documents use iter_pages() instead.
        """
        pages_dict: dict = {}
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

            for page_num in range(total_pages):
                images = convert_from_path(
                    pdf_path,
                    first_page=page_num + 1,
                    last_page=page_num + 1,
                    dpi=OCR_DPI,
                )
                if not images:
                    continue

                image = images[0]
                text = pytesseract.image_to_string(image)
                confidence = min(0.95, len(text) / 1000)

                pages_dict[page_num + 1] = {
                    "text": text,
                    "tables": [],
                    "ocr_confidence": confidence,
                }

                del image
                del images
                gc.collect()

                logger.info(f"OCR page {page_num + 1}/{total_pages}")

            logger.info(f"OCR extracted text from {total_pages} pages")
            return pages_dict, total_pages
        except Exception as e:
            logger.error(f"Error extracting scanned PDF: {e}")
            return {}, 0

    def process_pdf(self, pdf_path: str) -> Tuple[dict, int, bool]:
        """
        Process a PDF and return all content.

        Warning: loads the entire document into memory.
        For large documents use iter_pages() instead.
        """
        pdf_path = str(Path(pdf_path).resolve())

        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        is_text = self.is_text_pdf(pdf_path)

        if is_text:
            pages_dict, total_pages = self.extract_text_pdf(pdf_path)
        else:
            pages_dict, total_pages = self.extract_scanned_pdf(pdf_path)

        return pages_dict, total_pages, is_text
