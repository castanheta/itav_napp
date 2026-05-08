"""Schemas for high-level scaling operations."""
from enum import Enum
from ipaddress import ip_address

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


class ScalingAction(str, Enum):
    """Supported scaling actions."""

    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"


class ScalingTargetType(str, Enum):
    """Supported target scopes."""

    SLICE = "SLICE"
    USERS = "USERS"


class StepStatus(str, Enum):
    """Execution status for a single step."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class OperationStatus(str, Enum):
    """Terminal operation status."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class BaseScalingOperationRequest(BaseModel):
    """Common request payload fields for scaling operations."""

    action: ScalingAction = Field(..., description="High-level scaling action.")
    uplinkKbps: int | None = Field(
        None, gt=0, description="Requested uplink throughput delta in kbit/s."
    )
    downlinkKbps: int | None = Field(
        None, gt=0, description="Requested downlink throughput delta in kbit/s."
    )
    notificationDestination: AnyHttpUrl = Field(
        ..., description="Callback URL that receives terminal operation status."
    )
    requestId: str | None = Field(None, description="Optional client correlation identifier.")

    @model_validator(mode="after")
    def _validate_throughput_fields(self) -> "BaseScalingOperationRequest":
        if self.uplinkKbps is None and self.downlinkKbps is None:
            raise ValueError("At least one of uplinkKbps or downlinkKbps is required.")
        return self


class SliceScalingOperationRequest(BaseScalingOperationRequest):
    """Request payload for slice scaling operations."""

    sliceId: str = Field(..., description="Slice identifier.")


class UserScalingOperationRequest(BaseScalingOperationRequest):
    """Request payload for user scaling operations."""

    imsis: list[str] | None = Field(
        None, description="Required when ipAddresses is omitted."
    )
    ipAddresses: list[str] | None = Field(
        None, description="Required when imsis is omitted."
    )

    @field_validator("imsis")
    @classmethod
    def _validate_imsis(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [imsi.strip() for imsi in value if imsi.strip()]
        if not normalized:
            raise ValueError("imsis must contain at least one non-empty value.")
        return normalized

    @field_validator("ipAddresses")
    @classmethod
    def _validate_ip_addresses(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized: list[str] = []
        for item in value:
            candidate = item.strip()
            if not candidate:
                continue
            ip_address(candidate)
            normalized.append(candidate)
        if not normalized:
            raise ValueError("ipAddresses must contain at least one valid IP address.")
        return normalized

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "UserScalingOperationRequest":
        has_imsis = self.imsis is not None
        has_ips = self.ipAddresses is not None
        if has_imsis == has_ips:
            raise ValueError(
                "Provide exactly one of imsis or ipAddresses for user scaling."
            )
        return self


class ScalingStepResult(BaseModel):
    """Per-step execution result."""

    name: str = Field(..., description="Step name.")
    endpoint: str = Field(..., description="Provider endpoint called for this step.")
    status: StepStatus = Field(..., description="Step result status.")
    providerStatusCode: int | None = Field(
        None, description="HTTP status code returned by provider."
    )
    detail: str = Field(..., description="Execution detail for this step.")


class ScalingOperationCallbackPayload(BaseModel):
    """Terminal callback payload sent to xApp."""

    task_id: str
    requestId: str | None = None
    status: OperationStatus
    action: ScalingAction
    targetType: ScalingTargetType
    summary: str
    steps: list[ScalingStepResult]
    errorCode: int | None = None
    failedStep: str | None = None
