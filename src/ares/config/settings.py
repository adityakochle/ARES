"""Configuration and settings for ARES."""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path

# If a `.env` file exists inside the `ares/` package directory we want to
# make sure it is loaded before the settings object is constructed.  The
# default behaviour of ``pydantic_settings`` is to look for an ``env_file``
# relative to the current working directory, which in our CLI invocation is
# the workspace root.  In development the `.env` file lives inside
# ``ares/.env`` so the settings instance would fall back to defaults and end
# up trying to connect to a local Qdrant instance, which is why users were
# seeing ``Connection refused`` errors during ingestion.  By explicitly
# loading the dotenv file from the package root we guarantee the values are
# available no matter where the CLI is executed from.

env_candidate = Path(__file__).parents[3] / ".env"
if env_candidate.exists():
    # Use python-dotenv to populate os.environ
    try:
        from dotenv import load_dotenv
        load_dotenv(env_candidate)
    except ImportError:
        # dotenv is optional; if it's missing we'll rely on the environment
        # already being populated by the user/equipment.
        pass
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-small"
    reasoning_model: str = "gpt-4o-mini"
    validation_model: str = "gpt-4o"
    
    # Qdrant Configuration
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    qdrant_collection: str = "maritime_docs"
    
    # Application Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    app_env: str = os.getenv("APP_ENV", "development")
    
    # Document Processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100
    
    # Inference Configuration
    embedding_batch_size: int = 32
    vector_dim: int = 1536  # text-embedding-3-small dimension
    
    # Safety Configuration
    safety_rules_path: str = "data/safety_rules.yaml"
    enable_safety_validation: bool = True
    
    # Benchmark Configuration
    benchmark_scenarios_path: str = "data/benchmarks/scenarios.json"
    # Validators to clean up values coming from environment
    @field_validator("embedding_model", mode="before")
    @classmethod
    def _clean_embedding_model(cls, v: object) -> object:
        """Normalize the embedding model string.

        - Strip surrounding quotes that may be introduced when users copy a
          value from `.env` and include quotes.
        - Allow users to accidentally prefix the model with ``openai/`` which
          is a pattern used elsewhere but not accepted by the API.
        """
        if not isinstance(v, str):
            return v
        cleaned = v.strip().strip('"').strip("'")
        if cleaned.startswith("openai/"):
            cleaned = cleaned.split("/", 1)[1]
        return cleaned
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    
    def validate_critical_settings(self) -> bool:
        """Validate that critical settings are configured."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not self.qdrant_url:
            raise ValueError("QDRANT_URL environment variable is required")
        return True


# Global settings instance
settings = Settings()
