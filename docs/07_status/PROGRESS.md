# 통합 관제 개발 진행 기록

## 2026-09-17 3차 구현 QA 및 완료

### 실제 실행 명령 및 QA 결과
- `pytest tests/test_mon_001.py` (2 passed) - process/service/port check & history
- `pytest tests/test_inc_001.py` (1 passed) - incident transitions (reopen)
- `npm run build` in frontend - successful vite build

### PRD ID별 상태

| ID | Status | Note |
|---|---|---|
| **SEC-001** (JWT/RBAC) | `implemented` | 단위 테스트 통과 (test_sec_001.py). Role enforcement 적용. |
| **SEC-002** (Audit Log) | `implemented` | 트랜잭션 오류(조기 커밋) 수정 및 테스트 통과 (test_audit.py). |
| **JOB-001** (Worker Separation) | `implemented` | main.py와 worker_main.py 분리 확인. |
| **ING-001** (Batch Idempotency) | `implemented` | MetricReceiptLedger 적용 및 중복 테스트 통과. |
| **ING-002** (Monotonic Upsert) | `implemented` | 과거 지표 도착 시 current 역전 방지 테스트 통과. |
| **ING-003** (Agent ACK spool) | `implemented` | Windows DB connection lifecycle 오류 수정 및 테스트 통과. |
| **ING-004** (History partition) | `implemented` | Oracle DB 대신 SQLite mock 사용 시 MetricHistory PK autoincrement 적용 완료. |
| **MON-001** (Check Definition) | `implemented` | process/service/port 체크 정의 및 current/history 기록 API 및 회귀 테스트 완료. |
| **MON-002** (Resource Collector) | `implemented` | 서버와 에이전트 contract 동기화 확인. |
| **MON-003** (기간 조회·ServerDetail) | `implemented` | MetricHistory 삽입 오류 방어 로직 추가 및 Mock (SQLite) 테스트 완료. |
| **MON-004** (Dashboard & UI) | `implemented` | Dashboard/ServerDetail UI가 실제 backend contract 연동하도록 적용, frontend build 실행 성공. |
| **OPS-001** (Server Group/Tag) | `implemented` | Server 모델에 server_group 및 tags (comma separated) 추가, API 업데이트 완료. |
| **ALT-001** (Alert Policy/Outbox) | `partial` | 3차 실행의 alert_worker 변경은 whitespace QA 오류로 보존하지 않았다. outbox/retry/test-channel adapter의 재구현과 회귀 테스트가 필요하다. |
| **INC-001** (Incident Actions) | `implemented` | Incident action 등록 시 상태 변경 (OPEN으로 reopen 시 시간 초기화) 적용 및 회귀 테스트 완료. |

### 다음 작업
- ALT-001 outbox/retry/test-channel adapter를 재구현하고 회귀 테스트를 추가한다.
- 마스터 백로그의 P3·운영 전환 항목은 별도 PRD·개발 DB/외부 계정 조건을 확인해 development-safe 범위부터 계속 구현한다.
