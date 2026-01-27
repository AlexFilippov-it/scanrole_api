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
    )
