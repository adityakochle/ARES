"""Safety rules engine."""

import yaml
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from ares.schemas.safety import SafetyRules, EquipmentLimit, Interlock, Contraindication

logger = logging.getLogger(__name__)

# Default rules file: resolve from package root regardless of CWD.
# File layout: .../ares/src/ares/safety/rules_engine.py
#              .../ares/data/safety_rules.yaml
_PKG_ROOT = Path(__file__).parents[3]  # goes up: safety/ -> ares/ -> src/ -> ares/
_DEFAULT_RULES_PATH = _PKG_ROOT / "data" / "safety_rules.yaml"


class SafetyRulesEngine:
    """Load and manage safety rules for maritime equipment."""

    def __init__(self, rules_path: Optional[str] = None) -> None:
        """
        Initialize safety rules engine.

        Args:
            rules_path: Path to safety rules YAML file.  When None the engine
                        resolves the file relative to the package root, which
                        works regardless of the current working directory.
        """
        if rules_path is not None:
            candidate = Path(rules_path)
        else:
            # Try CWD-relative path first (backwards compat), then pkg-root
            cwd_candidate = Path("data/safety_rules.yaml")
            candidate = cwd_candidate if cwd_candidate.exists() else _DEFAULT_RULES_PATH

        self.rules_path: Path = candidate
        self.rules: Optional[SafetyRules] = None
        self.load_rules()

    def load_rules(self) -> bool:
        """
        Load safety rules from YAML file.

        Returns:
            True if loaded successfully
        """
        if not self.rules_path.exists():
            logger.warning(f"Safety rules file not found: {self.rules_path}")
            self.rules = self._create_default_rules()
            return False

        try:
            with open(self.rules_path, "r") as f:
                data = yaml.safe_load(f)

            self.rules = SafetyRules(
                equipment_limits=self._parse_equipment_limits(data.get("equipment_limits", {})),
                interlocks=self._parse_interlocks(data.get("interlocks", {})),
                contraindications=self._parse_contraindications(data.get("contraindications", [])),
                last_updated=data.get("last_updated", "unknown"),
            )

            logger.info("Safety rules loaded successfully from %s", self.rules_path)
            return True
        except Exception as e:
            logger.error(f"Error loading safety rules: {e}")
            self.rules = self._create_default_rules()
            return False

    def check_equipment_limits(
        self,
        equipment_name: str,
        parameter: str,
        value: float,
    ) -> Dict[str, Any]:
        """
        Check if parameter value is within safe limits.

        Args:
            equipment_name: Equipment name
            parameter: Parameter name
            value: Current value

        Returns:
            Dict with status, limit info, severity
        """
        if not self.rules:
            return {"status": "unknown", "reason": "No rules loaded"}

        equipment_limits = self.rules.equipment_limits.get(equipment_name, {})
        if not equipment_limits:
            return {"status": "unknown", "reason": f"No limits for {equipment_name}"}

        limit = equipment_limits.get(parameter)
        if not limit:
            return {"status": "unknown", "reason": f"No limit for {parameter}"}

        # Check thresholds from most severe to least severe
        if limit.critical is not None and value > limit.critical:
            return {
                "status": "critical",
                "severity": "CRITICAL",
                "value": value,
                "limit": limit.critical,
                "unit": limit.unit,
            }

        if limit.warning is not None and value > limit.warning:
            return {
                "status": "warning",
                "severity": "HIGH",
                "value": value,
                "limit": limit.warning,
                "unit": limit.unit,
            }

        if limit.normal_max is not None and value > limit.normal_max:
            return {
                "status": "elevated",
                "severity": "MEDIUM",
                "value": value,
                "limit": limit.normal_max,
                "unit": limit.unit,
            }

        if limit.normal_min is not None and value < limit.normal_min:
            return {
                "status": "low",
                "severity": "MEDIUM",
                "value": value,
                "limit": limit.normal_min,
                "unit": limit.unit,
            }

        return {
            "status": "normal",
            "severity": "LOW",
            "value": value,
            "unit": limit.unit,
        }

    def check_contraindications(
        self,
        condition: str,
        proposed_actions: List[str],
    ) -> List[Dict[str, str]]:
        """
        Check if proposed actions violate any contraindications.

        Args:
            condition: Current condition description
            proposed_actions: List of proposed actions

        Returns:
            List of contraindication dicts (empty if none)
        """
        if not self.rules:
            return []

        violations = []
        condition_lower = condition.lower()

        for contraindication in self.rules.contraindications:
            trigger_lower = contraindication.condition.lower()
            if trigger_lower in condition_lower:
                prohibited = {a.lower() for a in contraindication.prohibited_actions}
                for action in proposed_actions:
                    if action.lower() in prohibited:
                        violations.append({
                            "action": action,
                            "reason": contraindication.reason,
                            "condition": contraindication.condition,
                        })

        return violations

    def check_interlocks(self, equipment_name: str) -> List[Dict[str, Any]]:
        """
        Get all interlocks for an equipment.

        Args:
            equipment_name: Equipment name

        Returns:
            List of interlock dicts
        """
        if not self.rules:
            return []

        interlocks = self.rules.interlocks.get(equipment_name, [])
        return [
            {
                "name": interlock.name,
                "trigger": interlock.trigger,
                "action": interlock.action,
                "override_allowed": interlock.override_allowed,
            }
            for interlock in interlocks
        ]

    @staticmethod
    def _parse_equipment_limits(data: Dict) -> Dict[str, Dict[str, EquipmentLimit]]:
        """Parse equipment limits from raw YAML data."""
        result: Dict[str, Dict[str, EquipmentLimit]] = {}
        for equipment, limits_dict in data.items():
            result[equipment] = {}
            for param, limit_data in limits_dict.items():
                result[equipment][param] = EquipmentLimit(**limit_data)
        return result

    @staticmethod
    def _parse_interlocks(data: Dict) -> Dict[str, List[Interlock]]:
        """Parse interlocks from raw YAML data."""
        result: Dict[str, List[Interlock]] = {}
        for equipment, interlocks_list in data.items():
            result[equipment] = [Interlock(**i) for i in interlocks_list]
        return result

    @staticmethod
    def _parse_contraindications(data: List) -> List[Contraindication]:
        """Parse contraindications from raw YAML data."""
        return [Contraindication(**item) for item in data]

    @staticmethod
    def _create_default_rules() -> SafetyRules:
        """Create minimal default rules when the YAML file cannot be loaded."""
        return SafetyRules(
            equipment_limits={},
            interlocks={},
            contraindications=[],
            last_updated="default",
        )
