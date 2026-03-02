"""Benchmark framework for ARES system."""

import json
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Result from running a single benchmark scenario."""
    scenario_id: str
    scenario_name: str
    expected_severity: str
    actual_severity: str
    confidence_score: float
    time_seconds: float
    correct: bool
    safety_violations: List[str]


# ---------------------------------------------------------------------------
# Output parsers
# ---------------------------------------------------------------------------

def _parse_severity(output: str) -> str:
    """
    Extract the highest-confidence severity level from crew output text.

    Tries explicit labelled patterns first, then falls back to keyword scan.
    """
    text = output.lower()

    # Explicit label patterns (e.g. "SEVERITY: HIGH", "Severity: Critical")
    for pattern in (
        r"severity[:\s]+([a-z]+)",
        r"severity level[:\s]+([a-z]+)",
        r"assessment[:\s]+([a-z]+)",
    ):
        m = re.search(pattern, text)
        if m:
            candidate = m.group(1).upper()
            if candidate in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                return candidate

    # Keyword fallback — most severe wins
    for sev in ("critical", "high", "medium", "low"):
        if sev in text:
            return sev.upper()

    return "UNKNOWN"


def _parse_confidence(output: str) -> float:
    """
    Extract a confidence score (0.0–1.0) from crew output text.

    Handles both decimal (0.85) and percentage (85%) formats.
    """
    text = output.lower()

    patterns = (
        r"confidence[:\s]+([0-9]+\.?[0-9]*)\s*%",   # "confidence: 85%"
        r"confidence score[:\s]+([0-9]+\.?[0-9]*)",  # "confidence score: 0.85"
        r"confidence[:\s]+([0-9]+\.?[0-9]*)",        # "confidence: 0.85"
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            val = float(m.group(1))
            return val / 100.0 if val > 1.0 else val

    return 0.5  # neutral default when not parseable


# ---------------------------------------------------------------------------
# Scenario generator
# ---------------------------------------------------------------------------

class ScenarioGenerator:
    """Generate synthetic failure scenarios for benchmarking."""

    @staticmethod
    def generate_default_scenarios() -> List[Dict[str, Any]]:
        """Generate 150 synthetic maritime failure scenarios."""
        scenarios = []

        # Bearing overheat scenarios
        for i in range(30):
            scenarios.append({
                "id": f"bearing_overheat_{i}",
                "name": f"Bearing Overheat - Variant {i}",
                "fault_description": (
                    f"High vibration detected in Port Side Main Propulsion Bearing. "
                    f"Thermal sensors reporting {70 + i % 20}\u00b0C and rising. "
                    f"Engine RPM stable at {400 + i % 200}."
                ),
                "equipment": "main_engine",
                "expected_severity": "HIGH" if i % 3 == 0 else "MEDIUM",
                "expected_diagnosis": "Lube Oil Film Breakdown",
            })

        # Generator trip scenarios
        for i in range(25):
            scenarios.append({
                "id": f"generator_trip_{i}",
                "name": f"Generator Trip - Variant {i}",
                "fault_description": (
                    f"Auxiliary Generator #{(i % 3) + 1} tripped on overcurrent. "
                    f"Load was {70 + i % 30}% at time of trip. Other generators stable."
                ),
                "equipment": "auxiliary_engine",
                "expected_severity": "MEDIUM",
                "expected_diagnosis": "Overcurrent Protection Activation",
            })

        # Alfa Laval Purifier and Clarifier (S946) failures
        for i in range(20):
            scenarios.append({
                "id": f"purifier_failure_{i}",
                "name": f"Alfa Laval S946 Purifier Failure - Variant {i}",
                "fault_description": (
                    f"Main Engine Fuel Oil Purifier (Alfa Laval S946) showing signs of malfunction. "
                    f"Differential pressure across disc stack: {0.8 + i % 15 / 10:.1f} bar. "
                    f"Bowl vibration detected. Throughput reduced from 40 m\u00b3/h to {30 + i % 10} m\u00b3/h."
                ),
                "equipment": "fuel_oil_purifier",
                "expected_severity": "CRITICAL",
                "expected_diagnosis": "Disc Stack Contamination or Bowl Bearing Wear",
            })

        # Pump failures
        for i in range(25):
            scenarios.append({
                "id": f"pump_failure_{i}",
                "name": f"Pump Failure - Variant {i}",
                "fault_description": (
                    f"Fuel Transfer Pump showing reduced discharge. "
                    f"Pressure dropped from 3.5 bar to {2.0 + i % 15 / 10:.1f} bar. "
                    f"Cavitation noise detected."
                ),
                "equipment": "pumps_compressors",
                "expected_severity": "HIGH",
                "expected_diagnosis": "Pump Cavitation or Wear",
            })

        # HVAC failures
        for i in range(20):
            scenarios.append({
                "id": f"hvac_failure_{i}",
                "name": f"HVAC Failure - Variant {i}",
                "fault_description": (
                    f"Engine room temperature rising. Main cooler fans operating at 100%. "
                    f"Cooler outlet temp {55 + i % 15}\u00b0C. Seawater inlet temp 28\u00b0C."
                ),
                "equipment": "hvac_refrigeration",
                "expected_severity": "MEDIUM",
                "expected_diagnosis": "Cooler Effectiveness Degradation",
            })

        # Electrical faults
        for i in range(15):
            scenarios.append({
                "id": f"electrical_fault_{i}",
                "name": f"Electrical Fault - Variant {i}",
                "fault_description": (
                    "Main switchboard showing unbalanced phase voltage. "
                    "Phase A: 440V, Phase B: 435V, Phase C: 428V. Load distribution normal."
                ),
                "equipment": "electrical",
                "expected_severity": "MEDIUM",
                "expected_diagnosis": "Phase Imbalance or Generator Issue",
            })

        # Safety system failures
        for i in range(15):
            scenarios.append({
                "id": f"safety_failure_{i}",
                "name": f"Safety System Failure - Variant {i}",
                "fault_description": (
                    "Fire detection system smoke sensor in Engine Room showing intermittent faults. "
                    "Self-test failing. Backup sensor operational."
                ),
                "equipment": "safety_systems",
                "expected_severity": "HIGH",
                "expected_diagnosis": "Sensor Malfunction",
            })

        return scenarios

    @staticmethod
    def save_scenarios(scenarios: List[Dict[str, Any]], path: str) -> None:
        """Save scenarios to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(scenarios, f, indent=2)
        logger.info(f"Saved {len(scenarios)} scenarios to {path}")

    @staticmethod
    def load_scenarios(path: str) -> List[Dict[str, Any]]:
        """Load scenarios from JSON file."""
        if not Path(path).exists():
            logger.warning(f"Scenarios file not found: {path}")
            return []
        with open(path, "r") as f:
            scenarios = json.load(f)
        logger.info(f"Loaded {len(scenarios)} scenarios from {path}")
        return scenarios


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """Run benchmark scenarios and collect metrics."""

    def __init__(self, diagnostic_crew) -> None:
        """
        Initialize benchmark runner.

        Args:
            diagnostic_crew: ARESDiagnosticCrew instance
        """
        self.crew = diagnostic_crew
        self.results: List[ScenarioResult] = []

    def run_scenario(self, scenario: Dict[str, Any]) -> ScenarioResult:
        """
        Run a single scenario and record results.

        Args:
            scenario: Scenario dictionary

        Returns:
            ScenarioResult with parsed severity and confidence
        """
        start = time.time()
        try:
            inputs = {
                "fault_description": scenario["fault_description"],
                "equipment": scenario.get("equipment", "unknown"),
            }
            result = self.crew.crew().kickoff(inputs=inputs)
            elapsed = time.time() - start

            result_text = str(result)
            actual_severity = _parse_severity(result_text)
            confidence = _parse_confidence(result_text)
            expected = scenario.get("expected_severity", "UNKNOWN")
            is_correct = actual_severity == expected

            scenario_result = ScenarioResult(
                scenario_id=scenario["id"],
                scenario_name=scenario["name"],
                expected_severity=expected,
                actual_severity=actual_severity,
                confidence_score=confidence,
                time_seconds=elapsed,
                correct=is_correct,
                safety_violations=[],
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"Error running scenario {scenario['id']}: {e}")
            scenario_result = ScenarioResult(
                scenario_id=scenario["id"],
                scenario_name=scenario["name"],
                expected_severity=scenario.get("expected_severity", "UNKNOWN"),
                actual_severity="ERROR",
                confidence_score=0.0,
                time_seconds=elapsed,
                correct=False,
                safety_violations=[str(e)],
            )

        self.results.append(scenario_result)
        return scenario_result

    def run_benchmark(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run full benchmark suite.

        Args:
            scenarios: List of scenarios to run

        Returns:
            Dictionary with benchmark metrics
        """
        logger.info(f"Starting benchmark with {len(scenarios)} scenarios")
        for i, scenario in enumerate(scenarios):
            logger.info(f"Running scenario {i + 1}/{len(scenarios)}: {scenario['id']}")
            self.run_scenario(scenario)
        return self.calculate_metrics()

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate benchmark metrics from accumulated results."""
        if not self.results:
            return {}

        correct_count = sum(1 for r in self.results if r.correct)
        avg_time = sum(r.time_seconds for r in self.results) / len(self.results)
        violation_count = sum(len(r.safety_violations) for r in self.results)
        avg_confidence = sum(r.confidence_score for r in self.results) / len(self.results)

        return {
            "total_scenarios": len(self.results),
            "correct_diagnoses": correct_count,
            "accuracy": correct_count / len(self.results),
            "avg_time_seconds": avg_time,
            "safety_violations": violation_count,
            "violation_rate": violation_count / len(self.results),
            "avg_confidence": avg_confidence,
            "results": [asdict(r) for r in self.results],
        }

    def save_results(self, path: str) -> None:
        """Save benchmark results to JSON."""
        metrics = self.calculate_metrics()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved benchmark results to {path}")
