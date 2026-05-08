"""Router for high-level scaling operations."""
from fastapi import APIRouter, status

from app.schemas.scaling_operations import (
    SliceScalingOperationRequest,
    UserScalingOperationRequest,
)
from app.services import scaling_operations as scaling_service

router = APIRouter()
scaling_callback_router = APIRouter()


@scaling_callback_router.post(
    "{$request.body.notificationDestination}",
    description="Terminal status callback for scaling operation.",
    response_model=None,
)
async def send_scaling_notification() -> None:
    """OpenAPI callback documentation only."""


@router.post(
    "/scaling-operation/slice",
    description="Submit a high-level scaling operation for a slice target.",
    tags=["Scaling Operations API"],
    responses={
        status.HTTP_202_ACCEPTED: {
            "model": dict,
            "description": "Scaling operation accepted for asynchronous processing.",
        }
    },
    response_model_exclude_unset=True,
    callbacks=scaling_callback_router.routes,
)
async def scale_slice(request: SliceScalingOperationRequest):
    """Accept a slice scaling request and run provider orchestration asynchronously."""
    return await scaling_service.submit_slice_scaling_operation(request)


@router.post(
    "/scaling-operation/user",
    description="Submit a high-level scaling operation for user targets.",
    tags=["Scaling Operations API"],
    responses={
        status.HTTP_202_ACCEPTED: {
            "model": dict,
            "description": "Scaling operation accepted for asynchronous processing.",
        }
    },
    response_model_exclude_unset=True,
    callbacks=scaling_callback_router.routes,
)
async def scale_user(request: UserScalingOperationRequest):
    """Accept a user scaling request and run provider orchestration asynchronously."""
    return await scaling_service.submit_user_scaling_operation(request)
