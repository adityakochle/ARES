"""Safety rules schemas."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class EquipmentLimit(BaseModel):
    """Equipment operating limit."""
    
    normal_max: Optional[float] = None
    normal_min: Optional[float] = None
    warning: Optional[float] = None
    critical: Optional[float] = None
    unit: str
    description: Optional[str] = None


class Interlock(BaseModel):
    """Equipment safety interlock."""
    
    name: str
    trigger: str = Field(description="Condition that triggers this interlock")
    action: str = Field(description="Automatic action taken")
    override_allowed: bool = False
    description: Optional[str] = None


class Contraindication(BaseModel):
    """Action contraindication based on condition."""
    
    condition: str = Field(description="When this condition is true")
    prohibited_actions: List[str] = Field(description="Actions that must not be taken")
    reason: str = Field(description="Why this action is prohibited")


class EquipmentLimits(BaseModel):
    """Limits for a specific equipment."""
    
    equipment_name: str
    limits: Dict[str, EquipmentLimit]


class SafetyRules(BaseModel):
    """Complete safety rules database."""
    
    equipment_limits: Dict[str, Dict[str, EquipmentLimit]] = Field(
        description="Limits by equipment and parameter"
    )
    interlocks: Dict[str, List[Interlock]] = Field(
        description="Interlocks by equipment"
    )
    contraindications: List[Contraindication] = Field(
        description="Global contraindications"
    )
    last_updated: str = Field(description="When rules were last updated")
