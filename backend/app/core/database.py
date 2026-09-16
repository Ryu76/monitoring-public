import oracledb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_database_url

# Oracle 11g 호환을 위해 Thick mode를 활성화합니다.
# 시스템에 Oracle Instant Client가 설치되어 있어야 합니다.
try:
    oracledb.init_oracle_client()
except Exception as e:
    print("Warning: Failed to initialize Oracle Client for Thick mode. Ensure Oracle Instant Client is installed.", e)

# SQLAlchemy 동기 엔진 구성
engine = create_engine(
    get_database_url(),
    echo=False, # 개발 환경용 쿼리 로깅
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
