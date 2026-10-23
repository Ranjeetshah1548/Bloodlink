"""
Centralised application settings, loaded from environment variables / .env.
Nothing sensitive is hardcoded here - see .env.example for the full list.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "bloodlink"
    DB_USER: str = "bloodlink_user"
    DB_PASSWORD: str = "change_me"
    DATABASE_URL: str | None = None

    # Auth
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # OTP
    OTP_PROVIDER: str = "console"
    OTP_EXPIRE_SECONDS: int = 300
    OTP_LENGTH: int = 6
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Maps
    MAP_PROVIDER: str = "osm"
    GOOGLE_MAPS_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    # ML
    ML_MODEL_PATH: str = "app/ml/model.pkl"

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
