import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    log_level: str = "INFO"
    mikrotik_host: str = "192.168.88.1"
    mikrotik_user: str = "user"
    mikrotik_password: str = "password"
    mikrotik_sync_interval_seconds: int = 10
    mikrotik_dns_manager: bool = True
    reverse_proxy_ip: str | None = None
    traefik_configs_path: str = "./configs"
    tls_cert_resolver: str = "letsEncrypt"  # cloudflare | selfSigned | letsEncrypt


settings: Settings = Settings()
