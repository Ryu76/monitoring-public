import os
import platform
from pydantic_settings import BaseSettings
from pydantic import Field

class AgentSettings(BaseSettings):
    # 중앙 API 설정
    API_BASE_URL: str = Field("http://127.0.0.1:8000/agent/v1", env="MONITOR_API_BASE_URL")

    # 에이전트 식별 정보 (파일에 저장)
    AGENT_UID_FILE: str = "agent_uid.txt"
    SERVER_UID_FILE: str = "server_uid.txt"

    # 수집 주기 및 설정
    COLLECT_INTERVAL_SEC: int = Field(30, env="MONITOR_COLLECT_INTERVAL_SEC")
    HEARTBEAT_INTERVAL_SEC: int = Field(60, env="MONITOR_HEARTBEAT_INTERVAL_SEC")
    METRICS_BATCH_SIZE: int = Field(100, env="MONITOR_METRICS_BATCH_SIZE")

    # 로컬 스풀러 설정
    SPOOL_DB_PATH: str = Field("spool.db", env="MONITOR_SPOOL_DB_PATH")
    PROCESS_TOP_N: int = Field(5, env="MONITOR_PROCESS_TOP_N")
    CHECK_PORTS: str = Field("8000,5173", env="MONITOR_CHECK_PORTS")
    CHECK_PROCESSES: str = Field("", env="MONITOR_CHECK_PROCESSES")
    CHECK_SERVICES: str = Field("", env="MONITOR_CHECK_SERVICES")

    # 에이전트 메타데이터
    HOST_NAME: str = platform.node()
    OS_TYPE_CODE: str = "WINDOWS" if platform.system() == "Windows" else "LINUX"
    OS_NAME: str = platform.system()
    OS_VERSION: str = platform.version()

    # 테스트를 위한 기본 IP 설정 (실운영 환경에서는 적절히 동적 획득)
    MGMT_IP: str = Field("127.0.0.1", env="MONITOR_MGMT_IP")
    SERVICE_IP: str = Field("127.0.0.1", env="MONITOR_SERVICE_IP")

    AGENT_VERSION: str = "1.0.0"
    INSTALL_PATH: str = os.getcwd()
    RUN_ACCOUNT: str = os.getenv("USERNAME", os.getenv("USER", "unknown"))

settings = AgentSettings()
