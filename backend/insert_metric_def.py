#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'e:\\monitor\\backend')
os.chdir('e:\\monitor\\backend')

from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# SQL로 직접 메트릭 정의 삽입
metrics = [
    ("CPU_USAGE_PCT", "CPU 사용률 (%)", "CPU", "FLOAT", "PERCENT", "AVG"),
    ("MEM_USAGE_PCT", "메모리 사용률 (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    ("MEM_AVAILABLE_BYTES", "사용 가능 메모리 (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    ("DISK_USAGE_PCT", "디스크 사용률 (%)", "DISK", "FLOAT", "PERCENT", "AVG"),
    ("DISK_AVAILABLE_BYTES", "사용 가능 디스크 (Bytes)", "DISK", "BIGINT", "BYTES", "AVG"),
    ("NET_BYTES_SENT", "네트워크 송신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
    ("NET_BYTES_RECV", "네트워크 수신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
    ("PROCESS_CPU_PCT", "Top Process CPU Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    ("PROCESS_MEM_PCT", "Top Process Memory Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    ("PORT_LISTEN", "TCP Port Listening Status", "PORT", "FLOAT", "BOOLEAN", "LAST"),
    ("SERVICE_STATUS", "Service Running Status", "SERVICE", "FLOAT", "BOOLEAN", "LAST"),
]

for code, name, category, value_type, unit, agg_type in metrics:
    # 기존 데이터 확인
    result = db.execute(
        text("SELECT METRIC_CODE FROM MON_METRIC_DEF WHERE METRIC_CODE = :code"),
        {"code": code}
    ).fetchone()
    
    if not result:
        db.execute(
            text("""INSERT INTO MON_METRIC_DEF 
            (METRIC_CODE, METRIC_NAME, CATEGORY_CODE, VALUE_TYPE_CODE, UNIT_CODE, AGG_TYPE_CODE,
             WINDOWS_SUPPORT_YN, LINUX_SUPPORT_YN, USE_YN)
            VALUES (:code, :name, :category, :value_type, :unit, :agg_type, :win, :linux, :use)"""),
            {
                "code": code,
                "name": name,
                "category": category,
                "value_type": value_type,
                "unit": unit,
                "agg_type": agg_type,
                "win": "Y",
                "linux": "Y",
                "use": "Y"
            }
        )
        print(f"Inserted: {code}")
    else:
        print(f"Already exists: {code}")

db.commit()
db.close()
print("Done!")
