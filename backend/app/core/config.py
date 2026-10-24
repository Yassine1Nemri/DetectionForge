from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "sqlite:///./detectionforge.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    splunk_field_mappings: dict[str, str] = Field(default_factory=lambda: {"EventID": "EventCode"})

    @field_validator("splunk_field_mappings")
    @classmethod
    def safe_fields(cls, value: dict[str, str]) -> dict[str, str]:
        import re

        if len(value) > 100 or any(
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,127}", field)
            for pair in value.items()
            for field in pair
        ):
            raise ValueError("Field mappings must contain simple field identifiers")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
