import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    log_level: str = "INFO"
    mikrotik_host: str  = '192.168.88.1'
    mikrotik_user: str = "user-api"
    mikrotik_password: str = "SuperPassword"
    mikrotik_log_file: str  = "logs/logs.0.txt"
    traefik_configs_path: str = "./configs"


settings: Settings = Settings()