"""Configuration settings for the application using Pydantic."""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    invoker_host: str = "127.0.0.1"
    invoker_port: int = 8001
    invoker_log_directory_path: str = "./invoker_impl/logs/"
    invoker_log_filename_path: str = "./invoker_impl/logs/app_logger"
    provider_target_url: str = "https://10.16.10.78:8080"
    capif_enabled: bool = True
    capif_config_file: str = (
        "app/capif/invoker_config.json"
    )

settings = Settings()

def get_settings() -> Settings:
    return settings
