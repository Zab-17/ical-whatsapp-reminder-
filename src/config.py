from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Canvas LMS
    canvas_api_url: str = "https://aucegypt.instructure.com"
    canvas_api_token: str = ""
    canvas_email: str = ""
    canvas_password: str = ""
    canvas_cookies_b64: str = ""

    # WhatsApp (Green API)
    green_api_instance_id: str
    green_api_token: str
    user_whatsapp_to: str  # Phone number without + (e.g., 201154069714)

    # Settings
    reminder_hour_utc: int = 5
    upcoming_days: int = 7
    snapshot_path: str = "snapshot.json"


settings = Settings()
