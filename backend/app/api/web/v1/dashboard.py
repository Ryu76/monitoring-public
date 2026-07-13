from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.api.dependencies import get_db
from app.models.server import Server, ServerStatusCurr
from app.schemas.dashboard import DashboardSummaryResponse

router = APIRouter()

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """대시보드 요약 정보 조회"""
    # 사용 중인 서버 총 수
    stmt_total = select(func.count(Server.server_id)).where(Server.use_yn == 'Y')
    result_total = db.execute(stmt_total)
    total_servers = result_total.scalar() or 0

    # 상태별 서버 수 (mon_server_status_curr 기준)
    stmt_normal = select(func.count(ServerStatusCurr.server_id)).where(
        ServerStatusCurr.composite_status == 'NORMAL'
    )
    stmt_warning = select(func.count(ServerStatusCurr.server_id)).where(
        ServerStatusCurr.composite_status == 'WARNING'
    )
    stmt_critical = select(func.count(ServerStatusCurr.server_id)).where(
        ServerStatusCurr.composite_status == 'CRITICAL'
    )

    normal = db.execute(stmt_normal).scalar() or 0
    warning = db.execute(stmt_warning).scalar() or 0
    critical = db.execute(stmt_critical).scalar() or 0

    return {
        "success": True,
        "code": "OK",
        "data": {
            "total_servers": total_servers,
            "normal": normal,
            "warning": warning,
            "critical": critical
        }
    }
