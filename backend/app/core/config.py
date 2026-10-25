from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    access_token_minutes: int = 30
    # Development retains Swagger; set APP_ENV=production for deployment.
    app_env: Literal['development', 'production'] = 'development'
    # Comma-separated explicit web origins; empty for same-origin/proxy setups.
    cors_origins: str = ''

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


settings = Settings()
