#!/usr/bin/env python
# -*- coding: utf-8 -*-
import oracledb
import sys
from datetime import datetime, timezone

# DB 연결
connection = oracledb.connect(
    user="example_db_user",
    password="CHANGEME",
    host="127.0.0.1",
    port=1521,
    service_name="ORCL"
)

cursor = connection.cursor()

# 메트릭 정의 데이터
metrics = [
    ("CPU_USAGE_PCT", "CPU 사용률 (%)", "CPU", "FLOAT", "PERCENT", "AVG"),
    ("MEM_USAGE_PCT", "메모리 사용률 (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    ("MEM_AVAILABLE_BYTES", "사용 가능 메모리 (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    ("DISK_USAGE_PCT", "디스크 사용률 (%)", "DISK", "FLOAT", "PERCENT", "AVG"),
    ("DISK_AVAILABLE_BYTES", "사용 가능 디스크 (Bytes)", "DISK", "BIGINT", "BYTES", "AVG"),
    ("NET_BYTES_SENT", "네트워크 송신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
    ("NET_BYTES_RECV", "네트워크 수신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
]

# 기존 데이터 확인 및 삽입
for code, name, category, value_type, unit, agg_type in metrics:
    try:
        cursor.execute(
            "SELECT METRIC_CODE FROM MON_METRIC_DEF WHERE METRIC_CODE = :1",
            (code,)
        )
        result = cursor.fetchone()
        
        if not result:
            # 새로운 메트릭 정의 삽입
            cursor.execute(
                """INSERT INTO MON_METRIC_DEF 
                (METRIC_CODE, METRIC_NAME, CATEGORY_CODE, VALUE_TYPE_CODE, UNIT_CODE, AGG_TYPE_CODE,
                 WINDOWS_SUPPORT_YN, LINUX_SUPPORT_YN, USE_YN, CREATED_AT)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, CURRENT_TIMESTAMP)""",
                (code, name, category, value_type, unit, agg_type, 'Y', 'Y', 'Y')
            )
            print(f"✓ Inserted: {code} - {name}")
        else:
            print(f"• Already exists: {code}")
    except Exception as e:
        print(f"✗ Error with {code}: {e}")

connection.commit()
connection.close()
print("\n✓ Metric definitions insertion complete!")
