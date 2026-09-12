"""Central configuration. Secrets come from a gitignored .env, read server-side only."""
from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
EXPORT_DIR = DATA_DIR / "exports"
SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROOMBRIDGE_", env_file=str(REPO_ROOT / ".env"), extra="ignore"
    )

    # OpenRouter key. The alias makes it readable from a bare OPENROUTER_API_KEY in the
    # .env file or the shell (no ROOMBRIDGE_ prefix), which is what everyone expects.
    openrouter_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "ROOMBRIDGE_OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Default backbone for mediation steps and for the auditor.
    default_model: str = "anthropic/claude-sonnet-4.5"
    auditor_model: str = "anthropic/claude-sonnet-4.5"

    # Sampling counts (see plan section 8).
    generation_k: int = 4
    audit_samples: int = 3
    escalation_samples: int = 3
    max_revision_iterations: int = 1

    # Provider behaviour.
    request_timeout_s: float = 90.0
    max_retries: int = 4

    # Governance.
    live_input_enabled: bool = True

    db_path: Path = DATA_DIR / "runs.db"

    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


def load_settings() -> "Settings":
    # The OPENROUTER_API_KEY alias handles both the .env file and the shell environment.
    return Settings()


settings = load_settings()
