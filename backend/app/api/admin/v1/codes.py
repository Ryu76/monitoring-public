from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_current_user
from app.models.system import SysCode, SysUser, SysCodeGroup
from app.schemas.admin import CodeGroupResponse, CodeResponse, GenericResponse

router = APIRouter()

@router.get("/groups", response_model=List[CodeGroupResponse])
def get_code_groups(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    groups = db.execute(select(SysCodeGroup)).scalars().all()
    return groups

@router.get("/", response_model=List[CodeResponse])
def get_codes(group_code: str = None, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    stmt = select(SysCode)
    if group_code:
        stmt = stmt.where(SysCode.group_code == group_code)
    stmt = stmt.order_by(SysCode.sort_order)
    codes = db.execute(stmt).scalars().all()
    return codes
