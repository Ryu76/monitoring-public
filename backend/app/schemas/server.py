from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class ServerBase(BaseModel):
    server_id: int
    server_uid: str
    server_name: str
    host_name: Optional[str] = None
    mgmt_ip: Optional[str] = None
    service_ip: Optional[str] = None
    os_type_code: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    server_role_code: Optional[str] = None
    env_code: Optional[str] = None
    importance_code: Optional[str] = None
    owner_dept: Optional[str] = None
    owner_name: Optional[str] = None
    use_yn: str = 'Y'

class ServerCreate(ServerBase):
    pass

class ServerResponse(ServerBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ServerListResponse(BaseModel):
    success: bool
    code: str
    data: List[ServerResponse]
