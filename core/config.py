from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class GroqSettings(BaseSettings):
    GROQ_API_KEY: str = ""
    GROQ_TIMEOUT: int = 10
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_TOKENS: int = 500
    GROQ_TEMPERATURE: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CelerySettings(BaseSettings):
    CELERY_BROKER_URL: str = "redis://localhost:6399/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6399/0"
    CELERY_TASK_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270  # 4.5 minutes

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class S3Settings(BaseSettings):
    AWS_ACCESS_KEY_ID: str = "minioadmin"  # Default for local MinIO
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"  # Default for local MinIO
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = "http://localhost:9002"  # MinIO endpoint, empty for real AWS
    S3_REPORTS_BUCKET: str = "renfeserver-reports"
    S3_SIGNED_URL_EXPIRY: int = 3600  # 1 hour

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ReportSettings(BaseSettings):
    REPORT_RETENTION_DAYS: int = 365
    REPORT_MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class StripeSettings(BaseSettings):
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER_MONTHLY: str = ""
    STRIPE_PRICE_STARTER_ANNUAL: str = ""
    STRIPE_PRICE_PROFESSIONAL_MONTHLY: str = ""
    STRIPE_PRICE_PROFESSIONAL_ANNUAL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "renfeserver_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5444

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Email service selection (smtp or mailgun)
    EMAIL_SERVICE: str = "smtp"

    # SMTP settings (for development with Mailpit)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1028
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@localhost"
    SMTP_USE_TLS: bool = False

    # Mailgun settings (for production)
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAILGUN_API_URL: str = "https://api.mailgun.net/v3"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Sentry (only used in production)
    SENTRY_DSN: str = ""

    # Auth settings (nested)
    auth: AuthSettings = AuthSettings()

    # Groq AI settings (nested)
    groq: GroqSettings = GroqSettings()

    # Celery settings (nested)
    celery: CelerySettings = CelerySettings()

    # S3 settings (nested)
    s3: S3Settings = S3Settings()

    # Report settings (nested)
    report: ReportSettings = ReportSettings()

    # Stripe settings (nested)
    stripe: StripeSettings = StripeSettings()

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
