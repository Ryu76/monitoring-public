"""FastAPI 공통 의존성(Dependency) 모듈"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
import jwt

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent import Agent
from app.models.system import SysUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")


def get_db():
    """DB 세션 제너레이터 (FastAPI Depends 용)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def verify_agent(
    x_agent_uid: str = Header(..., alias="X-Agent-Uid", description="에이전트 고유 UID"),
    db: Session = Depends(get_db),
) -> Agent:
    """
    Agent 인증 의존성.
    X-Agent-Uid 헤더를 읽어 DB에서 에이전트를 조회하고,
    승인(APPROVED) 상태인지 확인합니다.

    Returns:
        Agent ORM 인스턴스 (인증 성공 시)
    """
    # 1. DB에서 agent_uid로 조회
    stmt = select(Agent).where(Agent.agent_uid == x_agent_uid)
    result = db.execute(stmt)
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "code": "AGENT_NOT_FOUND",
                "message": f"등록되지 않은 에이전트입니다. (uid={x_agent_uid})"
            }
        )

    # 2. 상태 확인: APPROVED만 허용
    if agent.status_code != "APPROVED":
        status_messages = {
            "PENDING": "에이전트가 아직 관리자 승인을 받지 않았습니다.",
            "BLOCKED": "에이전트가 차단되었습니다. 관리자에게 문의하세요.",
            "REVOKED": "에이전트 인증이 폐기되었습니다.",
        }
        msg = status_messages.get(agent.status_code, f"에이전트 상태가 유효하지 않습니다. (status={agent.status_code})")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "code": "AGENT_NOT_APPROVED",
                "message": msg,
                "current_status": agent.status_code
            }
        )

    return agent

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> SysUser:
    """
    JWT 토큰을 검증하고 현재 인증된 관리자(SysUser) 객체를 반환합니다.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        login_id: str = payload.get("sub")
        if login_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
        
    user = db.execute(select(SysUser).where(SysUser.login_id == login_id)).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if user.status_code != 'ACTIVE' or user.use_yn != 'Y':
        raise HTTPException(status_code=403, detail="Inactive user")
    return user


def require_roles(allowed_roles: list[str]):
    """
    특정 롤을 가진 사용자만 접근할 수 있도록 검증합니다.
    """
    async def role_checker(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> SysUser:
        from app.models.system import SysRole, SysUserRole
        user_roles = db.execute(
            select(SysRole.role_code)
            .join(SysUserRole, SysRole.role_id == SysUserRole.role_id)
            .where(SysUserRole.user_id == current_user.user_id)
        ).scalars().all()
        
        if "SUPER_ADMIN" in user_roles:
            return current_user
            
        for role in allowed_roles:
            if role in user_roles:
                return current_user
                
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="권한이 없습니다."
        )
    return role_checker
