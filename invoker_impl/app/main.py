"""'Main entry point for the FastAPI application."""

from fastapi import FastAPI

from app.routers import scaling_operations
from app.config import get_settings
from app.utils.logger import get_app_logger
from app.utils.http_callback_server import callback_app

from app.capif.client import CAPIFClient
from contextlib import asynccontextmanager
import app.dependencies as _deps
import asyncio


settings = get_settings()

logger = get_app_logger(__name__)
logger.info("Starting Network APP")
logger.info("Host: %s, Port: %s", settings.invoker_host, settings.invoker_port)
logger.info("Log Directory Path: %s", settings.invoker_log_directory_path)
logger.info("Log Filename Path: %s", settings.invoker_log_filename_path)
logger.info("Provider Target URL: %s", settings.provider_target_url)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.capif_enabled:
        client = CAPIFClient(config_file=settings.capif_config_file)
        await client.onboard()
        await client.refresh_token()  # block until first token is available
        _deps.capif_client = client

        refresh_task = asyncio.create_task(
            client.run_token_refresh_loop(),
            name="capif_token_refresh",
        )
    else:
        #logger.warning("CAPIF is disabled — skipping onboarding and token acquisition")
        refresh_task = None

    yield

    if settings.capif_enabled and refresh_task is not None:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        await _deps.capif_client.offboard()

app = FastAPI(lifespan=lifespan)
app.mount("/_internal", callback_app)

app.include_router(scaling_operations.router, prefix="/napp/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.invoker_host, port=settings.invoker_port)
