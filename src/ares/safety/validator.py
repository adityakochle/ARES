"""Safety validation."""

import logging
from typing import List, Dict, Any
from ares.schemas import DiagnosticOutput, DiagnosticSeverity

logger = logging.getLogger(__name__)


class SafetyValidator:
    """Validate diagnostic outputs for safety compliance."""
    
    def __init__(self, rules_engine):
        """
        Initialize validator.
        
        Args:
            rules_engine: SafetyRulesEngine instance
        """
        self.rules_engine = rules_engine
    
    def validate_diagnostic(
        self,
        diagnostic: DiagnosticOutput,
    ) -> tuple[bool, List[str]]:
        """
        Validate diagnostic output against safety rules.
        
        Args:
            diagnostic: DiagnosticOutput to validate
            
        Returns:
            Tuple of (is_valid, violation_list)
        """
        violations = []
        
        # Check contraindications
        contradictions = self.rules_engine.check_contraindications(
            diagnostic.fault_summary,
            diagnostic.immediate_actions + diagnostic.repair_steps,
        )
        
        if contradictions:
            for contradiction in contradictions:
                violations.append(
                    f"Action '{contradiction['action']}' contradicted by: {contradiction['reason']}"
                )
        
        # Critical severity checks
        if diagnostic.severity == DiagnosticSeverity.CRITICAL:
            if not diagnostic.immediate_actions:
                violations.append("Critical severity requires immediate actions")
            if diagnostic.confidence_score < 0.7:
                violations.append("Critical severity requires confidence > 70%")
        
        # Validation flag check
        if not diagnostic.validated:
            violations.append("Diagnostic not marked as validated")
        
        is_valid = len(violations) == 0
        return is_valid, violations
    
    def correct_violations(
        self,
        diagnostic: DiagnosticOutput,
        violations: List[str],
    ) -> DiagnosticOutput:
        """
        Attempt to correct safety violations.
        
        Args:
            diagnostic: Original diagnostic
            violations: List of violations
            
        Returns:
            Corrected diagnostic
        """
        # Remove prohibited actions
        contradictions = self.rules_engine.check_contraindications(
            diagnostic.fault_summary,
            diagnostic.immediate_actions,
        )
        
        prohibited_actions = {c["action"].lower() for c in contradictions}
        
        corrected_actions = [
            action for action in diagnostic.immediate_actions
            if action.lower() not in prohibited_actions
        ]
        
        if corrected_actions != diagnostic.immediate_actions:
            logger.info(f"Removed {len(diagnostic.immediate_actions) - len(corrected_actions)} prohibited actions")
            diagnostic.immediate_actions = corrected_actions
        
        return diagnostic
