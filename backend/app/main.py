from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.agent.v1.router import router as agent_router
from app.api.web.v1.router import router as web_router
from app.api.admin.v1.router import router as admin_router
from app.worker import start_worker
from app.scheduler import start_scheduler
from app.alert_worker import start_alert_worker
from app.aggregator import start_aggregator
from app.core.database import engine
from app.db_init import ensure_operational_tables
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 기동 시 API 전용 초기화를 수행합니다."""
    try:
        ensure_operational_tables(engine)
    except Exception as exc:
        logging.getLogger(__name__).warning("DB initialization skipped: %s", exc)
    logging.getLogger(__name__).info("API started. (Workers are separated)")
    yield
    logging.getLogger(__name__).info("API shutting down.")

app = FastAPI(
    title="통합 서버 모니터링 관제 시스템 API",
    description="Python/FastAPI 기반의 관제 시스템 백엔드 API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 설정 (프론트엔드 Vite 개발 서버 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Monitoring API is running"}

# 라우터 등록
app.include_router(agent_router, prefix="/agent/v1", tags=["Agent API"])
app.include_router(web_router, prefix="/api/v1", tags=["Web API"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin API"])
