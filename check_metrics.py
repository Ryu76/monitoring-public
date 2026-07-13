#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'e:\\monitor\\backend')

from app.core.database import SessionLocal
from app.models.resource import MetricDef

db = SessionLocal()
metrics = db.query(MetricDef).all()
print(f"Total metrics: {len(metrics)}")
for m in metrics:
    print(f"  {m.metric_code}: {m.metric_name}")
db.close()
