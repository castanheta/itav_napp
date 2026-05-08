import asyncio
from asyncio import Queue as AsyncQueue

from app.utils.logger import get_app_logger

logger = get_app_logger(__name__)

task_registry: dict[str,asyncio.Task] = {}

callback_data_queue: AsyncQueue = AsyncQueue()

def get_task_registry() -> dict[str, asyncio.Task]:
    """
    Returns the current task registry.

    Returns:
        dict[str, asyncio.Task]: A dictionary mapping task IDs to asyncio Task objects.
    """
    return task_registry

def get_callback_data_queue() -> AsyncQueue:
    """
    Returns the callback data queue.

    Returns:
        Queue: The queue used for storing callback data.
    """
    return callback_data_queue