from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ExternalHealthCheckCreate(BaseModel):
    target_type: str = Field(..., max_length=30)
    target_url_or_path: str = Field(..., max_length=500)
    status: str = Field(..., max_length=30)
    mock_response: Optional[str] = None

class ExternalHealthCheckResponse(ExternalHealthCheckCreate):
    id: int
    checked_at: Optional[datetime]

    class Config:
        from_attributes = True

class RemoteCommandApprovalCreate(BaseModel):
    command_type: str = Field(..., max_length=100)
    target_server: str = Field(..., max_length=100)

class RemoteCommandApprovalResponse(RemoteCommandApprovalCreate):
    id: int
    requested_by: Optional[str] = None
    approval_state: str
    dry_run_result: Optional[str]
    audit_event: Optional[str]
    requested_at: Optional[datetime]

    class Config:
        from_attributes = True

class ConfigVersionCreate(BaseModel):
    component_name: str = Field(..., max_length=100)
    version_tag: str = Field(..., max_length=50)
    config_payload: Optional[str] = None
    rollback_metadata: Optional[str] = None

class ConfigVersionResponse(ConfigVersionCreate):
    id: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class HAClusterStateCreate(BaseModel):
    node_name: str = Field(..., max_length=100)
    role: str = Field(..., max_length=30)
    health_state: str = Field(..., max_length=30)

class HAClusterStateResponse(HAClusterStateCreate):
    id: int
    last_heartbeat: Optional[datetime]

    class Config:
        from_attributes = True
