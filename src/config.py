from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Canvas LMS
    canvas_api_url: str = "https://aucegypt.instructure.com"
    canvas_api_token: str = ""       # Optional if using email/password
    canvas_email: str = ""           # For browser-based login
    canvas_password: str = ""        # For browser-based login
    canvas_cookies_b64: str = ""     # Base64-encoded cookies for cloud deployment

    # Twilio WhatsApp
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    user_whatsapp_to: str

    # Settings
    reminder_hour_utc: int = 5
    upcoming_days: int = 7
    snapshot_path: str = "snapshot.json"


settings = Settings()
