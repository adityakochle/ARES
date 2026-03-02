"""Document chunking strategy."""

import logging
from typing import List, Dict, Optional
from ares.schemas import DocumentChunk, EquipmentSystem, DocumentType

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Split documents into semantic chunks with metadata."""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            min_chunk_size: Minimum chunk size to create
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Find chunk end
            end = start + self.chunk_size
            
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Try to break at sentence boundary
            break_point = text.rfind(". ", start, end)
            if break_point > start + self.min_chunk_size:
                end = break_point + 2  # Include the period and space
            else:
                # Fall back to whitespace
                break_point = text.rfind(" ", start, end)
                if break_point > start + self.min_chunk_size:
                    end = break_point + 1
            
            chunks.append(text[start:end])
            next_start = end - self.chunk_overlap
            # Guarantee forward progress: if overlap would keep us at the same
            # position or go backwards (happens when the break_point is very
            # close to `start`), skip ahead to `end` instead.
            start = next_start if next_start > start else end
        
        return chunks
    
    def create_chunks(
        self,
        pages_dict: Dict[int, dict],
        filename: str,
        equipment_system: EquipmentSystem,
        document_type: DocumentType,
        is_text_pdf: bool,
    ) -> List[DocumentChunk]:
        """
        Create document chunks with metadata.
        
        Args:
            pages_dict: Dictionary of page_number -> {text, tables, ocr_confidence}
            filename: Source filename
            equipment_system: Equipment system classification
            document_type: Document type classification
            is_text_pdf: Whether original was text PDF
            
        Returns:
            List of DocumentChunk objects
        """
        chunks = []
        chunk_id = 0
        
        for page_num in sorted(pages_dict.keys()):
            page_data = pages_dict[page_num]
            text = page_data.get("text", "")
            ocr_conf = page_data.get("ocr_confidence")
            
            # Split into chunks
            text_chunks = self.chunk_text(text)
            
            for chunk_text in text_chunks:
                if len(chunk_text.strip()) < self.min_chunk_size:
                    continue
                
                chunk_id_str = f"{filename}_{page_num}_{chunk_id}"
                
                chunk = DocumentChunk(
                    id=chunk_id_str,
                    text=chunk_text,
                    equipment_system=equipment_system,
                    document_type=document_type,
                    page_number=page_num,
                    source_file=filename,
                    safety_critical=self._is_safety_critical(chunk_text),
                    contains_warnings=self._contains_warnings(chunk_text),
                    contains_limits=self._contains_limits(chunk_text),
                    ocr_confidence=ocr_conf if not is_text_pdf else None,
                )
                
                chunks.append(chunk)
                chunk_id += 1
        
        logger.info(f"Created {len(chunks)} chunks from {filename}")
        return chunks
    
    @staticmethod
    def _is_safety_critical(text: str) -> bool:
        """Check if text contains safety-critical information."""
        safety_keywords = [
            "caution", "warning", "danger", "critical", "shutdown",
            "pressure relief", "interlock", "safety", "must not"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in safety_keywords)
    
    @staticmethod
    def _contains_warnings(text: str) -> bool:
        """Check if text contains warnings."""
        warning_keywords = ["caution", "warning", "attention", "alert"]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in warning_keywords)
    
    @staticmethod
    def _contains_limits(text: str) -> bool:
        """Check if text contains operating limits."""
        limit_keywords = ["maximum", "minimum", "limit", "range", "pressure", "temperature"]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in limit_keywords)
