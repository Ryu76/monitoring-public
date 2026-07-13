import oracledb
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 애플리케이션의 모델 및 DB 설정 로드
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_database_url
from app.models import Base

# Oracle 11g Thick mode 활성화
try:
    oracledb.init_oracle_client()
except Exception:
    pass

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """기존 DB에 이미 존재하는 인덱스와 FK 제약조건 변경을 무시합니다.
    테이블/컬럼 구조 변경만 감지하도록 설정합니다."""
    if type_ == "index":
        return False  # 인덱스 변경 무시 (DB에 이미 최적화된 인덱스 존재)
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=False,         # Oracle NUMBER vs Integer 등 타입 비교 무시
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,         # Oracle NUMBER vs Integer 등 타입 비교 무시
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
