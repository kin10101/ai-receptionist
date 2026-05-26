from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Voice Scheduling Receptionist"
    api_prefix: str = "/api/v1"
    default_timezone: str = "UTC"
    environment: str = Field(default="dev")

    model_config = SettingsConfigDict(env_prefix="RECEPTIONIST_", extra="ignore")


settings = Settings()
