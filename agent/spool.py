import sqlite3
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MetricSpooler:
    """
    네트워크 단절 시 지표 데이터를 로컬 SQLite에 임시 저장(Buffering)하고
    복구 시 순차적으로 꺼내서 전송하기 위한 Failover 큐
    """
    def __init__(self, db_path: str = "spool.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics_spool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def push(self, metrics: List[Dict[str, Any]]):
        """수집된 지표(dict 리스트)를 스풀에 저장"""
        if not metrics:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for metric in metrics:
                payload = json.dumps(metric)
                cursor.execute('INSERT INTO metrics_spool (payload) VALUES (?)', (payload,))
            conn.commit()
            
    def pop_batch(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """스풀에서 최대 batch_size 만큼 지표를 꺼내옴 (읽은 후 자동 삭제)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, payload FROM metrics_spool ORDER BY id ASC LIMIT ?', (batch_size,))
            rows = cursor.fetchall()
            
            results = []
            ids_to_delete = []
            for row in rows:
                try:
                    payload = json.loads(row[1])
                    # payload 내에 _spool_id 등을 넣고 싶지 않으므로 순수 페이로드만 결과에 담음
                    results.append(payload)
                    ids_to_delete.append(row[0])
                except json.JSONDecodeError:
                    ids_to_delete.append(row[0])
                    
            if ids_to_delete:
                placeholders = ','.join('?' for _ in ids_to_delete)
                cursor.execute(f'DELETE FROM metrics_spool WHERE id IN ({placeholders})', ids_to_delete)
                conn.commit()
                
            return results

    def get_count(self) -> int:
        """현재 스풀에 쌓인 지표 수 반환"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM metrics_spool')
            count = cursor.fetchone()[0]
            return count
