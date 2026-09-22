from app.core.config import configure_runtime_settings

# Explicitly load encrypted local configuration before importing routes that use
# settings or construct the database engine. This does not modify os.environ.
settings = configure_runtime_settings()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.agent.v1.router import router as agent_router
from app.api.web.v1.router import router as web_router
from app.api.admin.v1.router import router as admin_router
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')

@asynccontextmanager
async def lifespan(app: FastAPI):
    """API lifecycle only; schema changes are applied by Alembic before deploy."""
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
from app.api.web.v1.extension import router as extension_router
app.include_router(extension_router, prefix="/api/v1/p3", tags=["P3 Extension API"])
