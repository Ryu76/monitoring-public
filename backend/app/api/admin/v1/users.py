from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_roles
from app.core.security import get_password_hash
from app.models.system import SysRole, SysUser, SysUserRole
from app.schemas.admin import GenericResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()


def _is_active_super_admin(db: Session, user: SysUser) -> bool:
    return db.execute(
        select(SysRole.role_id)
        .join(SysUserRole, SysRole.role_id == SysUserRole.role_id)
        .where(
            SysUserRole.user_id == user.user_id,
            SysRole.role_code == "SUPER_ADMIN",
            SysRole.use_yn == "Y",
        )
    ).first() is not None


def _ensure_not_last_active_super_admin(db: Session, user: SysUser) -> None:
    """Prevent disabling the final usable SUPER_ADMIN without a schema change."""
    if not _is_active_super_admin(db, user):
        return

    # Serialize competing account-disable requests on the shared active role.
    # The Oracle row lock is held until the endpoint commits or rolls back.
    db.execute(
        select(SysRole.role_id)
        .where(
            SysRole.role_code == "SUPER_ADMIN",
            SysRole.use_yn == "Y",
        )
        .with_for_update()
    ).scalar_one_or_none()

    active_count = db.execute(
        select(func.count())
        .select_from(SysUser)
        .join(SysUserRole, SysUserRole.user_id == SysUser.user_id)
        .join(SysRole, SysRole.role_id == SysUserRole.role_id)
        .where(
            SysRole.role_code == "SUPER_ADMIN",
            SysRole.use_yn == "Y",
            SysUser.status_code == "ACTIVE",
            SysUser.use_yn == "Y",
        )
    ).scalar_one()
    if active_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable the last active SUPER_ADMIN",
        )


@router.post("/", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles(["SUPER_ADMIN"])),
):
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
        created_by=current_user.login_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return GenericResponse(
        success=True,
        code="CREATED",
        message="사용자가 등록되었습니다.",
        data={"user_id": new_user.user_id},
    )


@router.get("/", response_model=List[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles(["SUPER_ADMIN"])),
):
    """관리자 목록 조회"""
    return db.execute(select(SysUser)).scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles(["SUPER_ADMIN"])),
):
    """관리자 상세 조회"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=GenericResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles(["SUPER_ADMIN"])),
):
    """관리자 정보 수정"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    will_be_inactive = (
        (req.status_code is not None and req.status_code != "ACTIVE")
        or (req.use_yn is not None and req.use_yn != "Y")
    )
    if will_be_inactive:
        _ensure_not_last_active_super_admin(db, user)

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
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles(["SUPER_ADMIN"])),
):
    """관리자 비활성화 (논리 삭제)"""
    user = db.execute(select(SysUser).where(SysUser.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    _ensure_not_last_active_super_admin(db, user)

    user.use_yn = "N"
    user.status_code = "INACTIVE"
    user.updated_at = datetime.now(timezone.utc)
    user.updated_by = current_user.login_id
    db.commit()
    return GenericResponse(success=True, code="DELETED", message="사용자가 비활성화되었습니다.")
