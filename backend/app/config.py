from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://mycelium:mycelium_demo@localhost:5432/mycelium"
    secret_key: str = "dev-secret-change-in-production"
    base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"  # comma-separated

    # Magic link
    magic_link_ttl_minutes: int = 15
    session_ttl_days: int = 30

    # Voyage AI
    voyage_api_key: str = ""
    voyage_model: str = "voyage-context-3"
    embedding_dimensions: int = 1024

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "mycelium@localhost"
    smtp_use_tls: bool = False

    # Matching
    similarity_threshold: float = 0.5
    max_matches_per_digest: int = 10
    match_dedup_days: int = 30

    # Bootstrap
    founding_user_email: str = ""

    # Trust
    vouch_cooldown_days: int = 7
    cooling_decay_factor: float = 0.85
    analytics_interval_hours: int = 4
    analytics_debounce_seconds: int = 30

    model_config = {"env_file": ".env", "extra": "ignore", "env_prefix": "", "case_sensitive": False}


settings = Settings()
