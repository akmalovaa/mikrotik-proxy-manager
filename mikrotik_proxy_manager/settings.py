import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    log_level: str = "INFO"
    mikrotik_log_file: str  = "logs.0.txt"


settings: Settings = Settings()