from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.utils.logger import get_app_logger
from app.dependencies import get_callback_data_queue

log = get_app_logger(__name__)

callback_app = FastAPI(
    title="Internal Callback API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)
queue = get_callback_data_queue()

@callback_app.post("/callback",status_code=status.HTTP_204_NO_CONTENT)
async def receive_callback(request: Request):
    """Receive internal notifications from external API."""
    
    try:
        data = await request.json()
        await queue.put(data)
        log.info("Received callback data: %s", data)
    except Exception as exc:
        log.error("Error processing callback request: %s", exc)
        return JSONResponse(content={"message": "Error processing request", "status": "failed"}, status_code=500)

