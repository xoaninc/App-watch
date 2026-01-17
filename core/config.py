from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_secret_key(self, environment: str) -> None:
        """Validate SECRET_KEY is properly configured in production."""
        if environment == "production" and self.SECRET_KEY == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production. "
                "Set the SECRET_KEY environment variable."
            )


class CelerySettings(BaseSettings):
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270  # 4.5 minutes

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "renfeserver_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Sentry (only used in production)
    SENTRY_DSN: str = ""

    # Auth settings (nested)
    auth: AuthSettings = AuthSettings()

    # Celery settings (nested)
    celery: CelerySettings = CelerySettings()

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
