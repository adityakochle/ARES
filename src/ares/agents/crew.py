"""ARES agent definitions and orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Type

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ares.config import settings
from ares.ingestion import DocumentEmbedder
from ares.retrieval import QdrantVectorDB
from ares.safety import SafetyRulesEngine, SafetyValidator

logger = logging.getLogger(__name__)

# Config YAML lives at src/ares/config/, one level up from src/ares/agents/
_CONFIG_DIR = Path(__file__).parent.parent / "config"


# ---------------------------------------------------------------------------
# Custom tools with injected dependencies
# ---------------------------------------------------------------------------

class _SearchInput(BaseModel):
    query: str = Field(
        description="Descriptive search query about the fault, equipment, or procedure"
    )
    equipment_system: Optional[str] = Field(
        default=None,
        description=(
            "Optional equipment filter: main_engine, auxiliary_engine, "
            "fuel_oil_purifier, purifier_clarifier, pumps_compressors, hvac_refrigeration, "
            "boilers, electrical, safety_systems"
        ),
    )
    limit: int = Field(default=5, ge=1, le=10, description="Number of results (1-10)")


class QdrantSearchTool(BaseTool):
    """Search the maritime technical knowledge base via Qdrant vector DB."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "maritime_knowledge_search"
    description: str = (
        "Search the maritime technical documentation knowledge base. "
        "Retrieves relevant SOP sections, equipment specifications, fault patterns, "
        "and repair procedures from ingested technical manuals. "
        "Use this to obtain technical context before analysing a fault."
    )
    args_schema: Type[BaseModel] = _SearchInput

    # Private attributes — injected after construction, not pydantic fields
    _vector_db: Any = PrivateAttr(default=None)
    _embedder: Any = PrivateAttr(default=None)

    def __init__(self, *, vector_db: Any, embedder: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._vector_db = vector_db
        self._embedder = embedder

    def _run(
        self,
        query: str,
        equipment_system: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        try:
            vec = self._embedder.embed_single(query)
            hits = self._vector_db.search(
                query_vector=vec,
                limit=limit,
                equipment_system=equipment_system,
            )
            if not hits:
                return "No relevant documentation found in the knowledge base for this query."
            parts = []
            for i, h in enumerate(hits, 1):
                flag = " [SAFETY-CRITICAL]" if h.get("safety_critical") else ""
                parts.append(
                    f"[{i}] {h.get('source_file', 'unknown')} "
                    f"(p.{h.get('page_number', '?')}) | score={h.get('score', 0):.3f}{flag}\n"
                    f"{h.get('text', '')}"
                )
            return "\n---\n".join(parts)
        except Exception as exc:
            logger.error("QdrantSearchTool error: %s", exc)
            return f"Search failed: {exc}"


class _SafetyInput(BaseModel):
    condition: str = Field(description="Current fault condition or equipment state")
    proposed_actions: str = Field(
        description="Comma-separated list of proposed actions to validate"
    )


class SafetyCheckTool(BaseTool):
    """Validate proposed actions against maritime safety rules."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "safety_rules_check"
    description: str = (
        "Check proposed repair or operational actions against the maritime safety rules. "
        "Detects contraindications, prohibited actions, and interlock violations. "
        "Always call this before finalising any recommended actions."
    )
    args_schema: Type[BaseModel] = _SafetyInput

    _rules_engine: Any = PrivateAttr(default=None)

    def __init__(self, *, rules_engine: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._rules_engine = rules_engine

    def _run(self, condition: str, proposed_actions: str) -> str:
        try:
            actions = [a.strip() for a in proposed_actions.split(",") if a.strip()]
            violations = self._rules_engine.check_contraindications(condition, actions)
            if not violations:
                return f"PASS — all {len(actions)} proposed action(s) are safe for: {condition}"
            lines = [f"SAFETY VIOLATIONS ({len(violations)} found):"]
            for v in violations:
                lines.append(
                    f"  \u2717 '{v['action']}' is PROHIBITED under '{v['condition']}': {v['reason']}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.error("SafetyCheckTool error: %s", exc)
            return f"Safety check failed: {exc}"


# ---------------------------------------------------------------------------
# Crew definition
# ---------------------------------------------------------------------------

@CrewBase
class ARESDiagnosticCrew:
    """ARES diagnostic crew for maritime equipment fault analysis."""

    # Override default config paths. @CrewBase uses these as-is when they are
    # absolute strings, so the module directory is not prepended.
    agents_config = str(_CONFIG_DIR / "agents.yaml")
    tasks_config = str(_CONFIG_DIR / "tasks.yaml")

    def __init__(self) -> None:
        """Initialise shared components and build tools."""
        self.vector_db = QdrantVectorDB()
        self.embedder = DocumentEmbedder()
        self.safety_rules = SafetyRulesEngine()
        self.safety_validator = SafetyValidator(self.safety_rules)

        self._search_tool = QdrantSearchTool(
            vector_db=self.vector_db,
            embedder=self.embedder,
        )
        self._safety_tool = SafetyCheckTool(rules_engine=self.safety_rules)

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @agent
    def supervisor_agent(self) -> Agent:
        """Orchestration agent."""
        return Agent(
            config=self.agents_config["supervisor_agent"],
            llm=settings.reasoning_model,
            verbose=True,
        )

    @agent
    def researcher_agent(self) -> Agent:
        """Technical documentation retrieval agent with RAG search tool."""
        return Agent(
            config=self.agents_config["researcher_agent"],
            llm=settings.reasoning_model,
            tools=[self._search_tool],
            verbose=True,
        )

    @agent
    def analyst_agent(self) -> Agent:
        """Failure pattern analysis agent."""
        return Agent(
            config=self.agents_config["analyst_agent"],
            llm=settings.reasoning_model,
            verbose=True,
        )

    @agent
    def validator_agent(self) -> Agent:
        """Safety compliance validation agent with rules check tool."""
        return Agent(
            config=self.agents_config["validator_agent"],
            llm=settings.validation_model,
            tools=[self._safety_tool],
            verbose=True,
        )

    # ------------------------------------------------------------------
    # Tasks — Process.sequential passes each task's output as context to
    # the next task automatically; no explicit context= is needed.
    # ------------------------------------------------------------------

    @task
    def research_task(self) -> Task:
        """Retrieve relevant technical documentation from the knowledge base."""
        return Task(config=self.tasks_config["research_task"])

    @task
    def analysis_task(self) -> Task:
        """Analyse the fault and determine root cause."""
        return Task(config=self.tasks_config["analysis_task"])

    @task
    def validation_task(self) -> Task:
        """Validate the diagnostic against safety rules and produce final report."""
        return Task(config=self.tasks_config["validation_task"])

    # ------------------------------------------------------------------
    # Crew
    # ------------------------------------------------------------------

    @crew
    def crew(self) -> Crew:
        """Assemble the ARES sequential diagnostic crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
