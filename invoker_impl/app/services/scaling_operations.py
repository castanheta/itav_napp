"""Service layer for high-level scaling operations."""

import asyncio
import uuid
from dataclasses import dataclass

import requests
from fastapi import status
from fastapi.responses import JSONResponse
from requests import Response
from requests.exceptions import RequestException

from app.config import get_settings
from app.dependencies import get_task_registry, get_capif_token
from app.schemas.scaling_operations import (
    OperationStatus,
    ScalingAction,
    ScalingOperationCallbackPayload,
    ScalingStepResult,
    ScalingTargetType,
    StepStatus,
    SliceScalingOperationRequest,
    UserScalingOperationRequest,
)
from app.utils.logger import get_app_logger

log = get_app_logger(__name__)
settings = get_settings()
task_registry = get_task_registry()


@dataclass
class PlannedStep:
    """Internal representation of one provider step."""

    method: str
    name: str
    endpoint: str
    payload: dict


def _build_step_url(path_suffix: str) -> str:
    return f"{settings.provider_target_url.rstrip('/')}/{path_suffix.lstrip('/')}"


def _build_target_payload(
    request: SliceScalingOperationRequest | UserScalingOperationRequest,
    target_type: ScalingTargetType,
) -> dict:
    target: dict = {"targetType": target_type.value}
    if target_type == ScalingTargetType.SLICE:
        target["sliceId"] = request.sliceId
    elif request.imsis is not None:
        target["imsis"] = request.imsis
    else:
        target["ipAddresses"] = request.ipAddresses
    return target


def _antenna_payload(id: str, ran: str) -> dict:
    antenna_payload = {
        "antenna_id": f"{id}",
        "ran": f"{ran}",
    }
    return antenna_payload


def _power_payload(id: str, power: int, ran: str) -> dict:
    power_payload = {
        "antenna_id": f"{id}",
        "modifications": {"MIMO": True, "max_transmit_power": power},
        "ran": f"{ran}",
    }
    return power_payload


def _build_step_plan(
    request: SliceScalingOperationRequest | UserScalingOperationRequest,
    target_type: ScalingTargetType,
) -> list[PlannedStep]:
    target_payload = _build_target_payload(request, target_type)
    throughput_payload = {
        **target_payload,
        "action": request.action.value,
        "uplinkKbps": request.uplinkKbps,
        "downlinkKbps": request.downlinkKbps,
    }
    scale_up_steps = [
        PlannedStep(
            method="post",
            name="scale_throughput",
            endpoint=_build_step_url("/network-ops/moveToSlice/"),
            payload=throughput_payload,
        ),
        PlannedStep(
            method="post",
            name="set_151_antenna_state",
            endpoint=_build_step_url("/ran/antenna/activate"),
            payload=_antenna_payload("151", "aveiroseaport"),
        ),
        PlannedStep(
            method="post",
            name="set_153_antenna_state",
            endpoint=_build_step_url("/ran/antenna/activate"),
            payload=_antenna_payload("153", "aveiroseaport"),
        ),
        PlannedStep(
            method="put",
            name="set_152_antenna_power",
            endpoint=_build_step_url("/ran/antenna/modify"),
            payload=_power_payload("152", 242, "aveiroseaport"),
        ),
    ]

    scale_down_steps = [
        PlannedStep(
            method="post",
            name="scale_throughput",
            endpoint=_build_step_url("/network-ops/moveToSlice/"),
            payload=throughput_payload,
        ),
        PlannedStep(
            method="post",
            name="set_151_antenna_state",
            endpoint=_build_step_url("/ran/antenna/deactivate"),
            payload=_antenna_payload("151", "aveiroseaport"),
        ),
        PlannedStep(
            method="post",
            name="set_153_antenna_state",
            endpoint=_build_step_url("/ran/antenna/deactivate"),
            payload=_antenna_payload("153", "aveiroseaport"),
        ),
        PlannedStep(
            method="put",
            name="set_152_antenna_power",
            endpoint=_build_step_url("/ran/antenna/modify"),
            payload=_power_payload("152", 70, "aveiroseaport"),
        ),
    ]

    if request.action == ScalingAction.SCALE_UP:
        return scale_up_steps
    return scale_down_steps


def _build_headers(jwt_token: str | None) -> dict:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    return headers


async def _post_json(url: str, payload: dict, jwt_token: str | None = None) -> Response:
    headers = _build_headers(jwt_token)

    def _request() -> Response:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response

    return await asyncio.to_thread(_request)


async def _put_json(url: str, payload: dict, jwt_token: str | None = None) -> Response:
    headers = _build_headers(jwt_token)

    def _request() -> Response:
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        return response

    return await asyncio.to_thread(_request)


async def _send_terminal_callback(
    callback_url: str, payload: ScalingOperationCallbackPayload
) -> None:
    try:
        response = await _post_json(
            callback_url, payload.model_dump(mode="json", exclude_none=True)
        )
        response.raise_for_status()
        log.info("Sent scaling callback successfully to %s", callback_url)
    except RequestException as exc:
        log.error("Failed to send callback to %s: %s", callback_url, exc)


async def _run_operation(
    task_id: str,
    request: SliceScalingOperationRequest | UserScalingOperationRequest,
    target_type: ScalingTargetType,
) -> None:
    step_results: list[ScalingStepResult] = []
    callback_url = str(request.notificationDestination)

    try:
        if not settings.provider_target_url:
            raise ValueError("Missing provider_target_url configuration.")

        log.info("Starting scaling operation task_id=%s", task_id)
        if settings.capif_enabled:
            jwt_token = get_capif_token()
            if jwt_token is None:
                raise RuntimeError("CAPIF token is not available")
        else:
            jwt_token = None
        steps = _build_step_plan(request, target_type)

        for step in steps:
            if step.method == "post":
                response = await _post_json(step.endpoint, step.payload, jwt_token)
            else:
                response = await _put_json(step.endpoint, step.payload, jwt_token)

            if response.status_code >= 400:
                detail = response.text
                step_results.append(
                    ScalingStepResult(
                        name=step.name,
                        endpoint=step.endpoint,
                        status=StepStatus.FAILED,
                        providerStatusCode=response.status_code,
                        detail=detail,
                    )
                )
                # callback_payload = ScalingOperationCallbackPayload(
                #     task_id=task_id,
                #     requestId=request.requestId,
                #     status=OperationStatus.FAILED,
                #     action=request.action,
                #     targetType=target_type,
                #     summary="Scaling operation failed.",
                #     steps=step_results,
                #     errorCode=response.status_code,
                #     failedStep=step.name,
                # )
                # await _send_terminal_callback(callback_url, callback_payload)
                return

            step_results.append(
                ScalingStepResult(
                    name=step.name,
                    endpoint=step.endpoint,
                    status=StepStatus.SUCCEEDED,
                    providerStatusCode=response.status_code,
                    detail="Step completed successfully.",
                )
            )

        # callback_payload = ScalingOperationCallbackPayload(
        #     task_id=task_id,
        #     requestId=request.requestId,
        #     status=OperationStatus.SUCCEEDED,
        #     action=request.action,
        #     targetType=target_type,
        #     summary="Scaling operation completed successfully.",
        #     steps=step_results,
        # )
        # await _send_terminal_callback(callback_url, callback_payload)

    except Exception as exc:  # noqa: BLE001
        log.error("Scaling operation task_id=%s failed: %s", task_id, exc)
        step_results.append(
            ScalingStepResult(
                name="onboarding_or_runtime",
                endpoint="N/A",
                status=StepStatus.FAILED,
                providerStatusCode=500,
                detail=str(exc),
            )
        )
        callback_payload = ScalingOperationCallbackPayload(
            task_id=task_id,
            requestId=request.requestId,
            status=OperationStatus.FAILED,
            action=request.action,
            targetType=target_type,
            summary="Scaling operation failed before completion.",
            steps=step_results,
            errorCode=500,
            failedStep=step_results[-1].name,
        )
        await _send_terminal_callback(callback_url, callback_payload)
    finally:
        task_registry.pop(task_id, None)
        log.info("Scaling task removed from registry task_id=%s", task_id)


async def _submit_operation(
    request: SliceScalingOperationRequest | UserScalingOperationRequest,
    target_type: ScalingTargetType,
) -> JSONResponse:
    task_id = str(uuid.uuid4())
    task_registry[task_id] = asyncio.create_task(
        _run_operation(task_id, request, target_type)
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"message": "Request is being processed", "task_id": task_id},
    )


async def submit_slice_scaling_operation(
    request: SliceScalingOperationRequest,
) -> JSONResponse:
    """Create and register a background task for slice scaling."""
    return await _submit_operation(request, ScalingTargetType.SLICE)


async def submit_user_scaling_operation(
    request: UserScalingOperationRequest,
) -> JSONResponse:
    """Create and register a background task for user scaling."""
    return await _submit_operation(request, ScalingTargetType.USERS)
