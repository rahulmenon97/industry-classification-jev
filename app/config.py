from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env.local", extra="ignore")
    typesafe_api_key: SecretStr = SecretStr("")
    exa_api_key: SecretStr = SecretStr("")
    jev_model: str = "jev-latest"
    database_path: Path = ROOT / "storage" / "runs.sqlite3"
    identity_threshold: float = Field(default=0.8, ge=0, le=1)
