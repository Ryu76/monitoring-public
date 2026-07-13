import oracledb
from sqlalchemy import create_engine, MetaData
import json

from app.core.config import get_database_url

try:
    oracledb.init_oracle_client()
except Exception as e:
    pass

engine = create_engine(get_database_url())
metadata = MetaData()
metadata.reflect(bind=engine)

tables_info = {}
for table in metadata.sorted_tables:
    # Filter only 'mon_' tables or 'sys_' tables to avoid huge output of all Oracle system tables
    if not (table.name.lower().startswith('mon_') or table.name.lower().startswith('sys_')):
        continue
    
    cols = []
    for c in table.columns:
        cols.append({
            "name": c.name,
            "type": str(c.type),
            "nullable": c.nullable,
            "primary_key": c.primary_key
        })
    tables_info[table.name] = cols

with open("db_schema.json", "w", encoding="utf-8") as f:
    json.dump(tables_info, f, indent=2)

print(f"Reflected {len(tables_info)} tables to db_schema.json")
