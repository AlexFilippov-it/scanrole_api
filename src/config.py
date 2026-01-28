import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    wp_introspect_url: str
    wp_introspect_secret: str
    db_host: str
    db_name: str
    db_user: str
    db_pass: str
    role_table: str
    api_base_url: str
    log_level: str
    rate_limit_enabled: bool
    rate_limit_ip_per_minute: int
    rate_limit_ip_per_day: int
    rate_limit_token_per_minute: int
    rate_limit_token_per_day: int
    rate_limit_health_per_minute: int
    trust_proxy_headers: bool


def get_settings() -> Settings:
    return Settings(
        wp_introspect_url=os.getenv("WP_INTROSPECT_URL", "").strip(),
        wp_introspect_secret=os.getenv("WP_INTROSPECT_SECRET", "").strip(),
        db_host=os.getenv("DB_HOST", ""),
        db_name=os.getenv("DB_NAME", ""),
        db_user=os.getenv("DB_USER", ""),
        db_pass=os.getenv("DB_PASS", ""),
        role_table=os.getenv("ROLE_TABLE", "jobspy_normalized_jobs"),
        api_base_url=os.getenv("API_BASE_URL", "*"),
        log_level=os.getenv("LOG_LEVEL", "info"),
        rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes", "on"),
        rate_limit_ip_per_minute=int(os.getenv("RATE_LIMIT_IP_PER_MINUTE", "60")),
        rate_limit_ip_per_day=int(os.getenv("RATE_LIMIT_IP_PER_DAY", "1000")),
        rate_limit_token_per_minute=int(os.getenv("RATE_LIMIT_TOKEN_PER_MINUTE", "120")),
        rate_limit_token_per_day=int(os.getenv("RATE_LIMIT_TOKEN_PER_DAY", "2000")),
        rate_limit_health_per_minute=int(os.getenv("RATE_LIMIT_HEALTH_PER_MINUTE", "300")),
        trust_proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes", "on"),
    )
