from sqlalchemy import Column, String, Integer, Float, ForeignKey, CHAR, TIMESTAMP
from app.core.database import Base


class MetricDef(Base):
    """mon_metric_def - 메트릭(지표) 정의 마스터"""
    __tablename__ = "mon_metric_def"

    metric_code = Column(String(60), primary_key=True)
    metric_name = Column(String(100), nullable=False)
    category_code = Column(String(30))
    value_type_code = Column(String(30))
    unit_code = Column(String(30))
    agg_type_code = Column(String(30))
    windows_support_yn = Column(CHAR(1), default='Y')
    linux_support_yn = Column(CHAR(1), default='Y')
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)


class MetricCurrent(Base):
    """mon_metric_curr - 메트릭 현재 값 (최신 수집 데이터)"""
    __tablename__ = "mon_metric_curr"

    server_id = Column(Integer, primary_key=True)
    metric_code = Column(String(60), ForeignKey("mon_metric_def.metric_code"), primary_key=True)
    dimension_key = Column(String(60), primary_key=True, default='-')
    dimension_value = Column(String(200), primary_key=True, default='-')
    metric_value = Column(Float)         # Oracle NUMBER can store integer and decimal metrics
    string_value = Column(String(1000))
    status_code = Column(String(30))
    collected_at = Column(TIMESTAMP, nullable=False)
    received_at = Column(TIMESTAMP, nullable=False)


class MetricHistory(Base):
    """mon_metric_hist - 메트릭 이력 데이터"""
    __tablename__ = "mon_metric_hist"

    # DB에서 metric_hist_id는 nullable이며 PK가 아님.
    # SQLAlchemy는 PK 필수이므로 __mapper_args__로 처리
    metric_hist_id = Column(Integer)
    server_id = Column(Integer, nullable=False)          # FK 제약조건 DB에 없음
    agent_id = Column(Integer)
    metric_code = Column(String(60), nullable=False)
    dimension_key = Column(String(60))
    dimension_value = Column(String(200))
    metric_value = Column(Float)         # Oracle NUMBER can store integer and decimal metrics
    string_value = Column(String(1000))
    status_code = Column(String(30))
    quality_code = Column(String(30))
    collected_at = Column(TIMESTAMP, nullable=False)
    received_at = Column(TIMESTAMP, nullable=False)
    batch_uid = Column(String(40))

    __mapper_args__ = {
        "primary_key": [metric_hist_id]
    }
