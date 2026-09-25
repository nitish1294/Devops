from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration comes from the environment (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "HRMS Recruit"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- PostgreSQL: structured, relational, transactional records ---
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "hrms"
    POSTGRES_PASSWORD: str = "hrms"
    POSTGRES_DB: str = "hrms"

    # --- MongoDB: schema-flexible documents (resumes, logs, templates) ---
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    MONGO_DB: str = "hrms_docs"

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # --- Login protection ---
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 300
    LOGIN_LOCKOUT_SECONDS: int = 900

    # --- Outbound email ---
    # With SMTP_HOST unset, mail is rendered and queued but never sent, which is
    # what you want on a staging box. Set it and the worker starts delivering.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT: int = 20
    MAIL_FROM: str = "talent@example.com"
    MAIL_FROM_NAME: str = "Talent Team"
    MAIL_WORKER_ENABLED: bool = True
    MAIL_WORKER_INTERVAL: int = 20
    MAIL_MAX_ATTEMPTS: int = 4

    # --- Company identity, used on offer letters and calendar invites ---
    COMPANY_NAME: str = "Probus Insurance"
    COMPANY_ADDRESS: str = "Andheri West, Mumbai, Maharashtra"
    COMPANY_WEBSITE: str = "https://example.com"
    APP_BASE_URL: str = "http://localhost"

    # --- Observability ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # --- Schema ---
    # Alembic owns the schema. This is an escape hatch for throwaway databases.
    AUTO_CREATE_SCHEMA: bool = False

    # --- Uploads ---
    MAX_RESUME_BYTES: int = 10 * 1024 * 1024

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:4200,http://localhost"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
