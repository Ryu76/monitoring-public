from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# --- Token Schemas ---
class TokenResponse(BaseModel):
    success: bool = True
    code: str = "OK"
    access_token: str
    token_type: str = "bearer"
    user_info: dict

class LoginRequest(BaseModel):
    login_id: str
    password: str

# --- User Schemas ---
class UserBase(BaseModel):
    login_id: str
    user_name: str
    dept_name: Optional[str] = None
    position_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status_code: str = "ACTIVE"
    use_yn: str = "Y"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    user_name: Optional[str] = None
    password: Optional[str] = None
    dept_name: Optional[str] = None
    position_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status_code: Optional[str] = None
    use_yn: Optional[str] = None

class UserResponse(UserBase):
    user_id: int
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class GenericResponse(BaseModel):
    success: bool
    code: str
    message: str
    data: Optional[dict] = None

# --- SysCode Schemas ---
class CodeGroupBase(BaseModel):
    group_code: str
    group_name: str
    description: Optional[str] = None
    use_yn: str = "Y"

class CodeGroupResponse(CodeGroupBase):
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CodeBase(BaseModel):
    code: str
    group_code: str
    code_name: str
    sort_order: Optional[int] = 0
    description: Optional[str] = None
    use_yn: str = "Y"

class CodeResponse(CodeBase):
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
