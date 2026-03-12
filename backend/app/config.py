from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str   # Used server-side only — bypasses RLS when needed by agents
    SUPABASE_ANON_KEY: str           # Used for citizen-facing public reads

    # Gemini
    GEMINI_API_KEY: str

    # Bhashini
    BHASHINI_USER_ID: str
    BHASHINI_API_KEY: str
    BHASHINI_PIPELINE_ID: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str

    # SMTP Email
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str = "noreply@ps-crm.in"

    # App
    FRONTEND_URL: str
    BACKEND_URL: str
    INTERNAL_CRON_KEY: str   # Secret for /internal/run-predictive-agent

    class Config:
        env_file = ".env"


settings = Settings()
