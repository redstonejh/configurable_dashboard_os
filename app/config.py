from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    database_path: str = Field("./data/dashboard_skeleton.db", validation_alias="APP_DATABASE_PATH")
    log_path: str = Field("./logs/app.log", validation_alias="APP_LOG_PATH")
    poll_interval_seconds: int = Field(60, validation_alias="APP_POLL_INTERVAL_SECONDS")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def ensure_dirs(self) -> None:
        for file_path in (self.database_path, self.log_path):
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_app_settings() -> AppSettings:
    settings = AppSettings()
    settings.ensure_dirs()
    return settings
