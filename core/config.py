import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    # No default - must be set via .env or environment variable
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CelerySettings(BaseSettings):
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270  # 4.5 minutes

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    # Database - No default password for security
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""  # Required via .env
    POSTGRES_DB: str = "renfeserver_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False  # Default to False for security

    # Admin token for /admin endpoints
    ADMIN_TOKEN: str = ""

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Sentry (only used in production)
    SENTRY_DSN: str = ""

    # Groq AI
    GROQ_API_KEY: str = ""

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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def validate_production_settings(self) -> None:
        """Validate critical settings for production environment.

        Call this during application startup.
        Raises ValueError if production settings are invalid.
        """
        errors = []

        if self.is_production:
            # Check SECRET_KEY
            if not self.auth.SECRET_KEY or len(self.auth.SECRET_KEY) < 32:
                errors.append(
                    "SECRET_KEY must be set to a secure value (min 32 chars) in production"
                )

            # Check POSTGRES_PASSWORD
            if not self.POSTGRES_PASSWORD or self.POSTGRES_PASSWORD == "postgres":
                errors.append(
                    "POSTGRES_PASSWORD must be set to a secure value in production"
                )

            # Check ADMIN_TOKEN
            if not self.ADMIN_TOKEN or len(self.ADMIN_TOKEN) < 32:
                errors.append(
                    "ADMIN_TOKEN must be set to a secure value (min 32 chars) in production"
                )

            # Check DEBUG is disabled
            if self.DEBUG:
                errors.append("DEBUG must be False in production")

        if errors:
            raise ValueError(
                "Production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    def validate_development_settings(self) -> None:
        """Set sensible defaults for development if not configured."""
        # Generate random SECRET_KEY for development if not set
        if not self.auth.SECRET_KEY:
            self.auth.SECRET_KEY = secrets.token_urlsafe(32)
            print("WARNING: Using auto-generated SECRET_KEY for development")

        # Use default password for development if not set
        if not self.POSTGRES_PASSWORD:
            self.POSTGRES_PASSWORD = "postgres"
            print("WARNING: Using default POSTGRES_PASSWORD for development")

        # Generate admin token for development if not set
        if not self.ADMIN_TOKEN:
            self.ADMIN_TOKEN = secrets.token_urlsafe(32)
            print(f"WARNING: Using auto-generated ADMIN_TOKEN for development: {self.ADMIN_TOKEN}")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Create settings instance
settings = Settings()

# Validate based on environment
if settings.is_production:
    settings.validate_production_settings()
else:
    settings.validate_development_settings()
