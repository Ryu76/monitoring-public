"""Agent 등록 및 인증 관련 Pydantic 스키마"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ──────────────────────────────────────
# Agent 등록 (Enroll)
# ──────────────────────────────────────

class AgentEnrollRequest(BaseModel):
    """Agent가 최초 등록 시 전송하는 정보"""
    host_name: str = Field(..., max_length=255, description="호스트명")
    os_type_code: str = Field(..., max_length=30, description="OS 유형 코드 (WINDOWS, LINUX)")
    os_name: Optional[str] = Field(None, max_length=100, description="OS 이름")
    os_version: Optional[str] = Field(None, max_length=100, description="OS 버전")
    mgmt_ip: str = Field(..., max_length=45, description="관리 IP")
    service_ip: Optional[str] = Field(None, max_length=45, description="서비스 IP")
    agent_version: Optional[str] = Field(None, max_length=50, description="에이전트 버전")
    install_path: Optional[str] = Field(None, max_length=500, description="설치 경로")
    run_account: Optional[str] = Field(None, max_length=100, description="실행 계정")


class AgentEnrollData(BaseModel):
    """등록 성공 시 반환되는 데이터"""
    agent_uid: str
    server_uid: str
    server_id: int
    agent_id: int
    status_code: str  # PENDING → 관리자 승인 필요

    class Config:
        from_attributes = True


class AgentEnrollResponse(BaseModel):
    """등록 API 응답"""
    success: bool
    code: str
    message: str
    data: AgentEnrollData


# ──────────────────────────────────────
# Agent 하트비트 (Heartbeat)
# ──────────────────────────────────────

class HeartbeatRequest(BaseModel):
    """Agent 하트비트 수신"""
    agent_version: Optional[str] = None
    local_queue_count: Optional[int] = Field(0, ge=0, description="로컬 스풀 큐 건수")
    collector_statuses: Optional[dict] = Field(None, description="Collector별 상태")


class HeartbeatResponse(BaseModel):
    success: bool
    code: str
    message: str
    data: Optional[dict] = None


# ──────────────────────────────────────
# Agent 지표 Bulk 수신 (Metrics)
# ──────────────────────────────────────

class MetricItem(BaseModel):
    """개별 지표 항목"""
    metric_code: str = Field(..., max_length=60)
    dimension_key: Optional[str] = Field("-", max_length=60)
    dimension_value: Optional[str] = Field("-", max_length=200)
    metric_value: Optional[float] = None
    string_value: Optional[str] = Field(None, max_length=1000)
    status_code: Optional[str] = Field(None, max_length=30)
    quality_code: Optional[str] = Field(None, max_length=30)
    collected_at: datetime


class MetricBulkRequest(BaseModel):
    """지표 Bulk 전송 페이로드"""
    batch_uid: str = Field(..., max_length=40, description="배치 고유 ID")
    sequence: int = Field(..., ge=0, description="전송 순번")
    collected_at: datetime = Field(..., description="수집 시각")
    items: List[MetricItem] = Field(..., min_length=1, description="지표 항목 리스트")


class MetricBulkResponse(BaseModel):
    success: bool
    code: str
    message: str
    received_count: int


# ──────────────────────────────────────
# Agent 설정 조회 (Config)
# ──────────────────────────────────────

class AgentConfigData(BaseModel):
    """Agent에게 내려보내는 수집 설정"""
    collect_interval_sec: int = 30
    heartbeat_interval_sec: int = 60
    metrics_batch_size: int = 100
    enabled_collectors: List[str] = []
    check_processes: List[str] = []
    check_services: List[str] = []
    check_ports: List[int] = []


class AgentConfigResponse(BaseModel):
    success: bool
    code: str
    data: AgentConfigData
