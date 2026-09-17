# 통합 관제 개발 진행 기록

## 2026-09-17 1차 구현 QA 및 추가 구현

### 실제 실행 명령 및 QA 결과
- \pytest tests/test_sec_001.py\ (4 passed)
- \pytest tests/test_agent_metrics.py tests/test_audit.py\ (3 passed, 0 failed)
- \pytest tests/test_mon_003.py\ (1 passed, 0 failed)
- \python agent/test_spool.py\ (1 passed)

### PRD ID별 상태

| ID | Status | Note |
|---|---|---|
| **SEC-001** (JWT/RBAC) | \implemented\ | 단위 테스트 통과 (test_sec_001.py). Role enforcement 적용. |
| **SEC-002** (Audit Log) | \implemented\ | 트랜잭션 오류(조기 커밋) 수정 및 테스트 통과 (test_audit.py). |
| **JOB-001** (Worker Separation) | \implemented\ | main.py와 worker_main.py 분리 확인. |
| **ING-001** (Batch Idempotency) | \implemented\ | MetricReceiptLedger 적용 및 중복 테스트 통과. |
| **ING-002** (Monotonic Upsert) | \implemented\ | 과거 지표 도착 시 current 역전 방지 테스트 통과. |
| **ING-003** (Agent ACK spool) | \implemented\ | Windows DB connection lifecycle 오류 수정 및 테스트 통과. |
| **MON-002** (Resource Collector) | \implemented\ | 서버와 에이전트 contract 동기화 확인. |
| **MON-003** (기간 조회·ServerDetail 추세) | \implemented\ | GET /servers/{id}/metrics/{code}/history 엔드포인트 신규 개발. MetricHistory 삽입 오류 (ORA-14400 / PK) 방어 로직 추가 및 Mock (SQLite) 테스트 완료. |
| **ING-004** (History partition) | \locked\ | Oracle DB DDL/Partition 설정 필요. |

### 다음 작업
- P2 항목(MON-001, MON-004) UI/Dashboard 연동 Frontend 구현.
- P1 항목 중 ING-004 (History Partition)는 Oracle 환경 준비 시 진행.
