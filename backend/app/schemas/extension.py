from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class P3Mutation(BaseModel):
    """Reject server-controlled actor fields instead of silently ignoring them."""
    model_config = ConfigDict(extra="forbid")


class ExternalHealthCheckCreate(P3Mutation):
    target_type: str = Field(..., max_length=30)
    target_url_or_path: str = Field(..., max_length=500)
    status: str = Field(..., max_length=30)
    mock_response: Optional[str] = None


class ExternalHealthCheckResponse(ExternalHealthCheckCreate):
    id: int
    checked_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


class RemoteCommandApprovalCreate(P3Mutation):
    command_type: str = Field(..., max_length=100)
    target_server: str = Field(..., max_length=100)


class RemoteCommandApprovalResponse(RemoteCommandApprovalCreate):
    id: int
    requested_by: Optional[str] = None
    approval_state: str
    dry_run_result: Optional[str]
    audit_event: Optional[str]
    requested_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


class ConfigVersionCreate(P3Mutation):
    component_name: str = Field(..., max_length=100)
    version_tag: str = Field(..., max_length=50)
    config_payload: Optional[str] = None
    rollback_metadata: Optional[str] = None


class ConfigVersionResponse(ConfigVersionCreate):
    id: int
    created_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


class HAClusterStateCreate(P3Mutation):
    node_name: str = Field(..., max_length=100)
    role: str = Field(..., max_length=30)
    health_state: str = Field(..., max_length=30)


class HAClusterStateResponse(HAClusterStateCreate):
    id: int
    last_heartbeat: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)
