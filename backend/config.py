from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vision:changeme@localhost:5432/vision"
    redis_url: str = "redis://localhost:6379"
    ollama_url: str = "http://localhost:11434"

    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@vision.local"

    hcaptcha_secret: str = ""
    frontend_url: str = "http://localhost"
    open_registration: bool = True
    google_client_id: str = ""

    anthropic_api_key: str = ""
    tineye_api_key: str = ""
    geospy_api_key: str = ""
    shodan_api_key: str = ""
    virustotal_api_key: str = ""
    hibp_api_key: str = ""
    github_token: str = ""

    upload_dir: str = "/tmp/vision-uploads"
    production: bool = False  # set True via env in prod; controls Secure cookie flag

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
