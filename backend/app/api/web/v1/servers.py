from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies import get_db
from app.models.server import Server
from app.schemas.server import ServerListResponse, ServerResponse

router = APIRouter()

@router.get("", response_model=ServerListResponse)
def get_servers(db: Session = Depends(get_db)):
    """서버 목록 조회 (사용 중인 서버만)"""
    stmt = select(Server).where(Server.use_yn == 'Y')
    result = db.execute(stmt)
    servers = result.scalars().all()
    
    return {
        "success": True,
        "code": "OK",
        "data": servers
    }

@router.get("/{server_id}", response_model=ServerResponse)
def get_server_detail(server_id: int, db: Session = Depends(get_db)):
    """단일 서버 상세 정보 조회"""
    stmt = select(Server).where(Server.server_id == server_id)
    result = db.execute(stmt)
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
        
    return server
