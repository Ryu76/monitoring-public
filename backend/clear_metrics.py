#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'e:\\monitor\\backend')

from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 테이블 비우기
print("Clearing tables...")
db.execute(text("DELETE FROM mon_metric_hist"))
db.execute(text("DELETE FROM mon_metric_curr"))
db.commit()
db.close()

print("✓ Tables cleared!")
