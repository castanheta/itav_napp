"""'Main entry point for the FastAPI application."""

from fastapi import FastAPI

from app.routers import scaling_operations
from app.config import get_settings
from app.utils.logger import get_app_logger
from app.utils.http_callback_server import callback_app

settings = get_settings()

logger = get_app_logger(__name__)
logger.info("Starting Network APP")
logger.info("Host: %s, Port: %s", settings.invoker_host, settings.invoker_port)
logger.info("Log Directory Path: %s", settings.invoker_log_directory_path)
logger.info("Log Filename Path: %s", settings.invoker_log_filename_path)
logger.info("Provider Target URL: %s", settings.provider_target_url)
logger.info("Invoker Access Token File: %s", settings.invoker_access_token_file)
logger.info("Current Location Enabled: %s", settings.current_loc_enabled)
logger.info(
    "Current Location Max Number of Reports: %s", settings.current_loc_max_num_reports
)
logger.info("Current Location Report Period: %s", settings.current_loc_rep_period)
logger.info("Notification Destination: %s", settings.notification_destination)


app = FastAPI()
app.mount("/_internal", callback_app)

app.include_router(scaling_operations.router, prefix="/napp/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.invoker_host, port=settings.invoker_port)
