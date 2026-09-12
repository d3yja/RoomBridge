"""Central configuration. Secrets come from a gitignored .env, read server-side only."""
from __future__ import annotations

from pathlib import Path

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

    # OpenRouter (read from OPENROUTER_API_KEY, no prefix).
    openrouter_api_key: str = ""
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
    import os

    s = Settings()
    # OPENROUTER_API_KEY has no ROOMBRIDGE_ prefix; pull it explicitly.
    if not s.openrouter_api_key:
        s.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return s


settings = load_settings()
