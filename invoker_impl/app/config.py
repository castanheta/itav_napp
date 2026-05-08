"""Configuration settings for the application using Pydantic."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    invoker_host: str = "127.0.0.1"
    invoker_port: int = 8001
    invoker_log_directory_path: str = "./invoker_impl/logs/"
    invoker_log_filename_path: str = "./invoker_impl/logs/app_logger"
    provider_target_url: str = "http://10.16.10.78:8000"
    invoker_access_token_file: str = (
        "./invoker_impl/invoker_folder/ppavlidis/jwt_token.txt"
    )
    current_loc_enabled: bool = False
    current_loc_max_num_reports: int = 2
    current_loc_rep_period: int = 20
    notification_destination: str = "http://invoker:8001"


settings = Settings()


def get_settings() -> Settings:
    """
    Retrieve the current application settings.

    Returns:
        Settings: An instance containing the application's configuration settings.
    """
    return settings
