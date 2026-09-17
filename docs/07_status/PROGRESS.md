# 통합 관제 개발 진행 기록

## 작업 정책

- 자동 commit, push, deploy, 운영 DB 쓰기·DDL은 수행하지 않는다.
- 프로젝트/worktree/.git 폴더를 삭제하거나 훼손하지 않는다.
- 외부 시스템 연동 불가 시 development-safe 어댑터/mock을 사용하여 진행을 차단하지 않는다.

## 2026-09-17 AI-Pro Full Implementation 결과

`docs/03_planning/MASTER_PRD_BACKLOG.md`를 기반으로 P0, P1, P2 우선순위 기능들을 구현하였다.

### 구현 완료 기능

**[P0] SEC-001 | Web API JWT 인증 강제 및 RBAC**
- `backend/app/api/dependencies.py`에 `require_roles` Dependency를 구현하여 역할을 강제하였다.
- `backend/app/api/web/v1/router.py` 엔드포인트들에 ADMIN, OPERATOR 등의 권한을 추가하였다.
- 단위 테스트(`test_sec_001.py`)를 통해 무토큰 401, 역할 부족 403, 업데이트 권한 200 통과를 확인하였다.

**[P0] SEC-002 | 역할 권한·감사 로그**
- `backend/app/core/audit.py`를 작성하여 `SysAuditLog` 테이블에 actor/IP/target/before-after 데이터를 JSON 형태로 기록하도록 구현하였다.
- 서버 업데이트 라우터(`update_server`)에 적용 및 단위 테스트 검증을 완료하였다.

**[P0] AGT-001 | Agent PENDING 승인·credential 정책**
- `backend/app/api/dependencies.py`의 `verify_agent`에서 에이전트 상태가 `APPROVED`가 아닌 경우 `403 FORBIDDEN`으로 차단하는 로직을 검증 및 확인하였다. (사전 구현 적용됨)

**[P0] JOB-001 | API와 Worker/Scheduler 분리**
- FastAPI 기동 시 `main.py`의 lifespan에서 스케줄러와 워커가 기동되던 중복 가능성 문제를 해소하였다.
- `backend/app/worker_main.py`를 분리하여 단독 워커 프로세스로 실행 가능하게 설계하였다.
- `run_all.bat` 및 `run_all_commented.bat` 스크립트를 업데이트하여 워커가 독립 프로세스로 기동되도록 수정하였다.

**[P1] ING-001 | receipt ledger·batch 멱등성**
- `MetricReceiptLedger` 모델을 `app.models.resource`에 추가하여 배치 멱등성을 구현하였다.
- `backend/app/api/agent/v1/router.py`의 `receive_metrics`에서 `batch_uid`를 확인하고 중복 수신 시 무시하도록 처리하였다.

**[P1] ING-002 | timestamp-monotonic current upsert**
- `receive_metrics` 처리 시 새로운 메트릭의 `collected_at`이 기존 DB의 최신 값 `collected_at`보다 이전일 경우(과거 데이터 도착) 덮어쓰지 않고 무시하도록(`pass`) 로직을 추가하였다.

**[P1] ING-003 | Agent ACK 기반 spool**
- 에이전트의 `agent/spool.py`에서 배치 데이터를 pop할 때 삭제하지 않고 백엔드에 전송 후 HTTP 200 OK 수신 시에만 삭제하도록(ACK 기반) 변경하였다.
- 로컬 SQLite 기반 `agent/test_spool.py` 자동화 테스트를 통해 push, pop, 미전송 보존, ack 기능을 성공적으로 검증하였다.

**[P2] MON-001 | process/service/port 정의·history**
- `AgentConfig`를 통한 프로세스, 서비스, 포트 정의 및 감시 수집 코드가 이미 구현되어 있음을 확인하였다.
- 수집된 상태 이력이 DB에 정상 처리됨을 검증하였다.

**[P2] MON-002 | resource 세부 collector**
- 에이전트의 `SystemResourceCollector` (`agent/collectors/common.py`)에 CPU core, Load average, Swap, Disk IO, Network interface rate 등 세부 지표 수집을 추가하였다.
- 백엔드 라우터(`backend/app/api/agent/v1/router.py`)의 `METRIC_DEFINITIONS` 목록에 추가된 세부 지표 코드들을 등록하여 정상 수신되도록 계약을 동기화하였다.

### 다음 단계
- P2 항목 중 UI 반영 부분(Dashboard 등)의 구현 및 Frontend와의 연동 테스트 수행.
- P3 항목(오래된 데이터 정리 Batch, Notification 등) 백로그 진행.
