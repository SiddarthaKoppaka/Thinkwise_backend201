# src/core/config.py
from pydantic import AnyHttpUrl, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # JWT
    JWT_SECRET:             str
    JWT_ALGORITHM:          str              = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int         = 60

    # SMTP
    SMTP_HOST:              str
    SMTP_PORT:              int
    SMTP_USER:              str
    SMTP_PASSWORD:          str
    EMAILS_FROM:            EmailStr

    # CORS / Frontend
    CORS_ORIGINS:           list[AnyHttpUrl] = ["http://localhost:3000"]

    # Tell pydantic-settings to load .env and ignore any extras
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
