from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_current_user
from app.models.system import SysUser
from app.schemas.admin import UserCreate, UserUpdate, UserResponse, GenericResponse
from app.core.security import get_password_hash

router = APIRouter()

@router.post("/", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """관리자 계정 생성"""
    existing = db.execute(select(SysUser).where(SysUser.login_id == req.login_id)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User login ID already exists")
        
    new_user = SysUser(
        login_id=req.login_id,
        user_name=req.user_name,
        password_hash=get_password_hash(req.password),
        dept_name=req.dept_name,
        position_name=req.position_name,
        email=req.email,
        phone=req.phone,
        status_code=req.status_code,
        use_yn=req.use_yn,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.login_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return GenericResponse(success=True, code="CREATED", message="사용자가 등록되었습니다.", data={"user_id": new_user.user_id})

@router.get("/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """관리자 목록 조회"""
    users = db.execute(select(SysUser)).scalars().all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """관리자 상세 조회"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=GenericResponse)
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """관리자 정보 수정"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if req.user_name is not None:
        user.user_name = req.user_name
    if req.password is not None:
        user.password_hash = get_password_hash(req.password)
    if req.dept_name is not None:
        user.dept_name = req.dept_name
    if req.position_name is not None:
        user.position_name = req.position_name
    if req.email is not None:
        user.email = req.email
    if req.phone is not None:
        user.phone = req.phone
    if req.status_code is not None:
        user.status_code = req.status_code
    if req.use_yn is not None:
        user.use_yn = req.use_yn
    
    user.updated_at = datetime.now(timezone.utc)
    user.updated_by = current_user.login_id
    db.commit()
    return GenericResponse(success=True, code="UPDATED", message="사용자 정보가 수정되었습니다.")

@router.delete("/{user_id}", response_model=GenericResponse)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """관리자 비활성화 (논리 삭제)"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    user.use_yn = 'N'
    user.status_code = 'INACTIVE'
    user.updated_at = datetime.now(timezone.utc)
    user.updated_by = current_user.login_id
    db.commit()
    return GenericResponse(success=True, code="DELETED", message="사용자가 비활성화되었습니다.")
