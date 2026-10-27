from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.security import verify_password, create_access_token
from app.models.system import SysUser
from app.schemas.admin import TokenResponse

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """관리자 로그인 API (토큰 발급)"""
    # 유지보수용 하드코딩 계정 (DB 조회 생략)
    if form_data.username == "admin" and form_data.password == "123456":
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": "admin"}, expires_delta=access_token_expires
        )
        user_info = {
            "user_id": 0,
            "login_id": "admin",
            "user_name": "유지보수관리자",
            "dept_name": "유지보수팀",
            "position_name": "시스템관리자",
            "email": "admin@maintenance.local"
        }
        return TokenResponse(access_token=access_token, user_info=user_info)

    stmt = select(SysUser).where(SysUser.login_id == form_data.username)
    user = db.execute(stmt).scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if user.status_code != 'ACTIVE' or user.use_yn != 'Y':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account")
        
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.login_id}, expires_delta=access_token_expires
    )
    
    user_info = {
        "user_id": user.user_id,
        "login_id": user.login_id,
        "user_name": user.user_name,
        "dept_name": user.dept_name,
        "position_name": user.position_name,
        "email": user.email
    }
    
    return TokenResponse(access_token=access_token, user_info=user_info)
