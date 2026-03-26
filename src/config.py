from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Canvas LMS
    canvas_api_url: str = "https://aucegypt.instructure.com"

    # WhatsApp Bridge (Baileys)
    baileys_bridge_url: str = "http://localhost:3001"

    # Database
    database_path: str = "canvas_reminder.db"

    # Admin
    admin_key: str = ""

    # Settings
    upcoming_days: int = 30


settings = Settings()
