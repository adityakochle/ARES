"""Diagnostic output schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class DiagnosticSeverity(str, Enum):
    """Severity levels for diagnostics."""
    CRITICAL = "critical"      # Immediate shutdown required
    HIGH = "high"              # Requires attention within hours
    MEDIUM = "medium"          # Schedule maintenance
    LOW = "low"                # Monitor condition


class DiagnosticOutput(BaseModel):
    """Complete diagnostic output from ARES system."""
    
    # Diagnosis
    fault_summary: str = Field(description="Brief summary of the fault")
    probable_cause: str = Field(description="Root cause analysis")
    severity: DiagnosticSeverity = Field(description="Severity level")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence 0-1")
    
    # Actions
    immediate_actions: List[str] = Field(description="Immediate steps to take")
    repair_steps: List[str] = Field(description="Detailed repair procedure")
    sop_references: List[str] = Field(description="Referenced SOP sections")
    
    # Safety
    safety_notes: List[str] = Field(description="Critical safety information")
    contraindications: List[str] = Field(description="Actions to avoid")
    validated: bool = Field(description="Whether output passed safety validation")
    
    # Traceability
    sources_used: List[str] = Field(description="Document sources used")
    reasoning_chain: List[str] = Field(description="Step-by-step reasoning")
    
    class Config:
        use_enum_values = True
