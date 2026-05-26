from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Voice Scheduling Receptionist"
    api_prefix: str = "/api/v1"
    default_timezone: str = "UTC"
    environment: str = Field(default="dev")
    
    # LLM Configuration
    openai_api_key: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_temperature: float = Field(default=0.0)

    model_config = SettingsConfigDict(env_prefix="RECEPTIONIST_", extra="ignore")


settings = Settings()
