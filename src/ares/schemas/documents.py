"""Document and chunk schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class EquipmentSystem(str, Enum):
    """Maritime equipment systems."""
    MAIN_ENGINE = "main_engine"
    AUXILIARY_ENGINE = "auxiliary_engine"
    FUEL_OIL_PURIFIER = "fuel_oil_purifier"
    PUMPS = "pumps_compressors"
    HVAC = "hvac_refrigeration"
    PURIFIER_CLARIFIER = "purifier_clarifier"
    BOILERS = "boilers"
    ELECTRICAL = "electrical"
    SAFETY_SYSTEMS = "safety_systems"


class DocumentType(str, Enum):
    """Types of technical documents."""
    SOP = "sop"
    MANUAL = "manual"
    TROUBLESHOOTING = "troubleshooting"
    SAFETY_BULLETIN = "safety_bulletin"
    PARTS_CATALOG = "parts_catalog"


class DocumentChunk(BaseModel):
    """A chunk of a document with metadata and embedding."""
    
    id: str = Field(description="Unique chunk identifier")
    text: str = Field(description="Chunk text content")
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding (1536-dim)")
    
    # Metadata for filtering
    equipment_system: EquipmentSystem
    document_type: DocumentType
    section_number: Optional[str] = None
    page_number: int
    source_file: str
    
    # Safety metadata
    safety_critical: bool = False
    contains_warnings: bool = False
    contains_limits: bool = False
    
    # Extraction metadata
    ocr_confidence: Optional[float] = None  # None for text PDFs
    extraction_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        use_enum_values = True


class DocumentMetadata(BaseModel):
    """Metadata for a document."""
    
    filename: str
    document_type: DocumentType
    equipment_system: EquipmentSystem
    total_pages: int
    upload_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
