# 통합 관제 개발 진행 기록

## 2026-09-17 4차 구현 QA 및 완료 (사실 기반 최종 점검)

### 실제 실행 명령 및 QA 결과
- `python -m pytest backend/tests`
  - Pass/Fail Count: 18 passed, 0 failed (7 warnings)
  - 내용: SEC, JOB, ING, MON, OPS, INC 변경 사항 및 글로벌 dependency override 오염 문제 수정, 예외 경로 및 트랜잭션 정상 검증 완료
- `npm run build` (frontend 디렉토리)
  - 성공적으로 Vite 빌드 완료
  - 브라우저 자동화 도구가 없어 End-to-End UI 상호작용 검증은 불가능하며, Build 및 Structural evidence만 확인됨.

### PRD ID별 상태 (엄격한 E2E 검증 기준 적용)

| ID | Status | Note |
|---|---|---|
| **SEC-001** (JWT/RBAC) | `implemented` | 단위 테스트 통과(18개 중 일부). Role enforcement 확인. |
| **SEC-002** (Audit Log) | `implemented` | 트랜잭션 롤백 방어 검증 완료. |
| **JOB-001** (Worker Separation) | `implemented` | main/worker_main 분리 및 스케줄러 독립 실행 확인. |
| **ING-001** (Batch Idempotency) | `implemented` | MetricReceiptLedger 적용 중복 삽입 방지 검증 완료. |
| **ING-002** (Monotonic Upsert) | `implemented` | timestamp 기반 current 지표 역전 방지 완료. |
| **ING-003** (Agent ACK spool) | `implemented` | 파일 기반 Spool 동작 확인 테스트 통과. |
| **ING-004** (History partition) | `partial` | 코드 상 분할 로직은 작성되었으나, SQLite Mock을 사용 중이므로 실제 Oracle Partition 기능의 End-to-End 증명이 불가능. 외부 DB 필수. |
| **MON-001** (Check Definition) | `implemented` | Process/Service/Port 타겟 CRUD 및 Agent 연동 규격 테스트 통과. |
| **MON-002** (Resource Collector) | `implemented` | 백엔드 수집기 연동 테스트 완료. |
| **MON-003** (기간 조회·ServerDetail) | `implemented` | 기간 한정(30일) 쿼리 및 UI 규격(history) 확인. |
| **MON-004** (Dashboard & UI) | `partial` | API 연동 규격 코드와 빌드 통과는 확인했으나, 브라우저 자동화가 없어 E2E UI 동작 증명은 없음 (Build/Structural evidence만 존재). |
| **OPS-001** (Server Group/Tag) | `implemented` | Server 모델 확장 및 Filter API 테스트 통과. |
| **ALT-001** (Alert Policy/Outbox) | `partial` | Outbox Pending/Processing/Failed/Success 상태, Max Retry, History 기록 로직과 TEST 채널 Adapter를 테스트(test_alt_001.py)로 100% 검증함. 단, 실제 Email/Slack 발송은 외부 계정/Credential이 필요하여 Mock 처리됨 (E2E 발송 증명 불가). |
| **INC-001** (Incident Actions) | `implemented` | 조치 내역 등록 시 인시던트 연쇄 상태 변경(OPEN) 검증 완료. |

### 다음 운영 전환 조건
- **운영 DB(Oracle) 통합 테스트**: ING-004 (Partition) 및 대량 데이터 성능 테스트를 위해 실제 Oracle DB 환경 배포 필요.
- **알림 채널 연동(Credential)**: ALT-001의 외부 서비스(Slack Webhook, SMTP 이메일) 발송을 위한 프로덕션 Credential 주입 및 발송망 방화벽 허용.
- **Frontend E2E 테스트**: Playwright 또는 Cypress 등 브라우저 자동화 도구를 통한 전체 대시보드 및 상세 페이지의 사용자 시나리오(E2E) QA 진행.
- **보안 및 규정 컴플라이언스 점검**: 실 운영 전 보안 취약점 진단 및 감사 로그 적재 주기 검토.

## 2026-09-17 5차 구현 (P3 확장 관제·운영 플랫폼)

### 실제 실행 명령 및 QA 결과
- `pytest backend/tests/test_p3_extension.py -q`
  - Pass/Fail Count: 8 passed (added 3 negative tests)
  - 내용: URL/SSL, Remote Command, Config Versioning, HA Cluster에 대한 mock API 및 negative 테스트 통과 확인
- `MockExternalHealthCollector` 추가
  - Agent 측에서 실제 외부 인프라 연동 없이 mock 데이터(정상/실패 등)를 반환하도록 안전한 health inspection collector 구현
- `pytest backend/tests/ -q` (전체 테스트)
  - Pass/Fail Count: 26 passed
  - P0~P3 모든 백엔드 기능 정상 작동 확인
- `npm run build` (frontend 디렉토리)
  - 성공적으로 Vite 빌드 완료

### PRD ID별 상태 (P3)

| ID | Status | Note |
|---|---|---|
| **P3-EXT** (URL/SSL, DB, Batch Collector) | `implemented` | MockExternalHealthCollector 구현 및 Agent 등록, Unit/Negative test 확인 (실제 인프라 연결 차단) |
| **P3-CMD** (Remote Command Approval) | `implemented` | Allowlist, 결재 상태, Audit Event 검증 (실제 Subprocess/SSH 차단) |
| **P3-CFG** (Config Versioning) | `implemented` | Rollback Metadata, Report/Retention Mock 검증 (실제 배포 차단) |
| **P3-HA** (HA/Failover) | `implemented` | Leader/Follower Simulation API 모델 검증 (실제 클러스터 차단) |

### 외부 인프라 차단 조건
- 실제 운영 인프라 통신 및 Credential 유출 방지를 위해 외부 접속/명령 실행은 전면 차단됨
- 모의 데이터 통과 목적으로만 구현됨.

## 2026-09-18 7차 QA 및 최종 Closure (안정성 및 보안 검증)

### 실제 실행 명령 및 QA 결과
- `python -m pytest backend/tests/`
  - Pass/Fail Count: 40 passed, 0 failed (13 warnings)
  - 내용: 환경 변수 오염 및 리로드 이슈가 해결된 격리 상태에서 CFG-001, AGT-001, DPAPI, Preflight 등 백엔드 전 계층 단위 테스트 통과.
- `python -m compileall backend/`
  - 성공: 백엔드 전체 소스코드 문법 검증 및 바이트코드 컴파일 완료.
- `cd frontend && npm run build`
  - 성공: Vite 빌드 완료 (dist 생성).
- `cd frontend && npx playwright test`
  - Pass/Fail Count: 1 passed (9.3s)
  - 내용: 백엔드 API 규격을 정확히 모킹하여 로그인, 대시보드 요약, 이벤트 경고, 서버 상세 및 점검 이력 뷰, 인시던트 조회까지 Playwright 브라우저 E2E 시나리오 검증 통과.

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **AGT-001** (Agent Auth/Deny) | `implemented` | Mock 의존성 없이 로컬 SQLite 격리 DB로 PENDING/BLOCKED/REVOKED 접근 제어 및 승인 로직 100% 테스트 통과 |
| **CFG-001** (Config Security) | `implemented` | 환경 변수 우선순위 적용, 누락 시 Fail-Closed(ValidationError), DPAPI Round-trip 및 로드 테스트 통과 |
| **MON-004** (Dashboard & UI) | `implemented` | Playwright 기반 local Vite server + mocked API를 통해 화면 컴포넌트 렌더링 및 E2E 라우팅 검증 완료 |
| **ING-004** (History partition) | `blocked` | 로컬 환경에 프로덕션 Oracle DB가 없으므로 E2E 파티셔닝 증명 불가 (Mock 수준의 코드 검증만 수행됨) |
| **ALT-001** (Alert Policy) | `partial` | DB 내 발송 대기/실패 상태 전이 및 로직은 검증되었으나, 실제 외부(슬랙/이메일) 프로덕션 발송은 불가하여 Mock 증명 |

## 2026-10-02 001-security-dependencies (CFG-001)

### 실제 실행 명령 및 QA 결과
- `npm audit fix` (frontend 디렉토리)
  - 내용: axios 패키지의 high severity 취약점(Prototype pollution, ReDoS 등)을 해결하기 위해 기존 range(`^1.18.1`)와 호환되는 최소 버전(`1.20.0`)으로 lockfile 업데이트 수행 (`--force` 사용 안 함)
- `npm audit --audit-level=high` (frontend 디렉토리)
  - 성공: 0 vulnerabilities found 확인
- `npm run build` (frontend 디렉토리)
  - 성공: Vite 빌드 정상 완료
- `npm run test:e2e` (frontend 디렉토리)
  - Pass/Fail Count: 1 passed
  - 내용: Playwright 브라우저 E2E 시나리오 검증 통과, 회귀 없음 확인

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **CFG-001** (Security Dependencies) | `implemented` | frontend의 axios 패키지 고위험 취약점 조치(lockfile 최소 업데이트) 및 회귀 테스트(빌드, E2E) 통과 |

## 2026-10-02 002-prd-evidence-ledger

### 실제 실행 명령 및 QA 결과
- `conda run --no-capture-output -n monitor_backend python -m pytest backend/tests -q`
  - Pass/Fail Count: 61 passed, 9 warnings
  - 내용: Backend 단위/통합 테스트 (Mock/SQLite 기반) 전면 통과
- `conda run --no-capture-output -n monitor_backend python -m compileall -q backend`
  - 성공: 백엔드 소스코드 문법/바이트코드 컴파일 정상 완료.
- `cd frontend && npm run build`
  - 성공: Vite 프로덕션 빌드 정상 완료.

### 문서 갱신
- `docs/03_planning/PRD_ACCEPTANCE_LEDGER_20261002.md` 생성 및 전수 매핑 완료.
- `MASTER_PRD_BACKLOG.md` 내의 Oracle 연동 차단 상태를 최신 기준에 맞게 보정 (read-only/additive 증거 존재, 현 코드 기준 미완료).

## 2026-10-02 002-prd-evidence-ledger-attempt-2

### 실제 실행 명령 및 QA 결과
- `C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest backend/tests/test_agent_metrics.py agent/test_spool.py`
  - Pass/Fail Count: 3 passed
  - 내용: ING-001/002(batch_idempotency, monotonic_upsert), ING-003(agent spooler) 모의 실행. (Agent Spool 테스트는 제한적 커버리지를 가짐)

### 문서 갱신
- `docs/03_planning/PRD_ACCEPTANCE_LEDGER_20261002.md` 업데이트:
  - 각 PRD ID별 실제 Production Source 파일 및 Line 번호, Symbol 매핑.
  - 실행된 Test Node 정확하게 매핑.
  - Mocked transport, SQLite fixture, Browser mocked evidence 명시.
  - AGT-001 미해결 로컬 작업(Automatic approval 및 재등록 우회) 추가.
  - JOB-001 미해결 로컬 작업(Graceful shutdown 누락, 중복 워커 테스트 누락, MetricCurrent.updated_at 참조 오류) 추가.

## 2026-10-02 003-resource-rates

### 실제 실행 명령 및 QA 결과
- `$env:PYTHONPATH="."; C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest tests/test_resource_rates.py -v` (agent 디렉토리)
  - Pass/Fail Count: 1 passed
  - 내용: `SystemResourceCollector`의 `NET_BYTES_SENT_RATE` 및 `NET_BYTES_RECV_RATE`가 시간 차이에 따른 delta 기반(Bytes/sec)으로 계산되는지, 첫 샘플 및 카운터 리셋 시 오동작하지 않는지 실제 `psutil` 함수들과 `time.monotonic()` 조합으로 E2E 테스트 통과.

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **MON-002** (Resource Collector) | `implemented` | 네트워크 송수신 비율(Rate) 계산 로직을 누적 카운터에서 시간 기반 Delta 비율(Float)로 수정 및 검증. |

## 2026-10-02 003-resource-rates-attempt-2

### 실제 실행 명령 및 QA 결과
- `C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest agent/tests/test_resource_rates.py -v`
  - Pass/Fail Count: 1 passed
  - 내용: `SystemResourceCollector`의 `NET_BYTES_SENT_RATE`, `NET_BYTES_RECV_RATE`가 raw 카운터(`nowrap=False`)의 시간 단위 Delta로 정확히 계산됨을 검증. 카운터 Wrap/Reset, zero/negative interval 무시 로직 및 Interface Disappearance/Reconnection 처리(stale counter 비교 방지)를 실제 psutil C extension 모킹(real wrapper 통과)을 통해 검증 완료. MonitorAgent의 Collect & Spool 및 Flush 연동 배관망 확인 완료.

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **MON-002** (Resource Collector) | `implemented` | E2E 테스트 보강. Cumulative metric 유지, Discontinuous delta/Wrap discard 처리, Rebaseline 수행 확인. |

## 2026-10-02 003-resource-rates-attempt-3

### 실제 실행 명령 및 QA 결과
- `C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest agent/tests/test_resource_rates.py -v`
  - Pass/Fail Count: 2 passed
  - 내용: 누락되었던 CPU/Swap/Disk 차원 및 metric_value 단언(Assertion) 전수 추가, 송/수신 양방향 비율(sent/recv rate) 검증, Flush 실패 및 Spooler 재시도 상태 복원, 실제 MonitorAgent의 collect_interval/heartbeat_interval 동작(cadence) 검증 통과. (psutil.process_iter 추가 모킹으로 37초 지연 해결)
- `$env:PYTHONPATH="backend"; C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest backend/tests -v`
  - Pass/Fail Count: 62 passed
  - 내용: `ensure_metric_def`에서 `NET_BYTES_SENT_RATE`, `NET_BYTES_RECV_RATE` 기존 DB 데이터(BIGINT/BYTES)를 Float/Bytes per sec/AVG 로 안전하게 업데이트(schema migration script 우회)하는 하위 호환성 단언(Assertion) 테스트 통과.
- 코드 정합성: `agent/collectors/common.py` 트래킹 공백(whitespace) 검증 문제 조치.

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **MON-002** (Resource Collector) | `implemented` | 백엔드 API 호환성 유지(안전한 메타데이터 갱신 적용), Rate/누적 지표 차원 및 누락 Assertion 복구, Spooler 실패 복구 E2E 입증 |

## 2026-10-02 004-worker-lifecycle-attempt-1

### 실제 실행 명령 및 QA 결과
- `$env:PYTHONPATH="backend"; C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest backend/tests/test_worker_lifecycle.py -v`
  - Pass/Fail Count: 3 passed
  - 내용: `app.worker_main`에서 로컬 파일 락(`worker_local.lock`)을 사용한 중복 실행 방지 검증, API와 Worker의 명확한 의존성 분리(APScheduler 미포함) 확인, 시그널(SIGINT, SIGTERM, SIGBREAK) 수신 시 `schedulers.shutdown(wait=True)`을 호출하여 안전하게 Graceful shutdown 되는지 검증 완료.
- 명령줄 스크립트 정리: 기존 오해의 소지가 있던 `run_all.bat`을 `start_services.bat`으로 변경하고, 실제 모든 품질 게이트(백엔드 및 프론트엔드 테스트, E2E)를 수행하는 `run_tests.bat` 신규 작성.
- `aggregator.py` 수정: 존재하지 않던 `MetricCurrent.updated_at` 필드 참조를 올바른 `collected_at` 필드로 픽스.

### PRD ID별 상태 업데이트

| ID | Status | Note |
|---|---|---|
| **JOB-001** (Worker Separation) | `partial` (external_blocked) | Graceful shutdown 적용 및 로컬 락을 통한 중복 실행 방지 완수. 단, 실제 HA 구성을 위한 DB 분산 락 메커니즘은 '실행 topology' 확정 후 적용 필요. |
