# AI Pro PRD Code Audit

| ID | 항목 | 상태 | 근거 경로 | 미확인/차단 사유 |
| --- | --- | --- | --- | --- |
| BASE-001 | frontend route lazy loading | not-started | `frontend/src/router/index.ts` | 라우트 컴포넌트를 동기적으로 import하고 있어 lazy loading 미적용됨 |
| BASE-002 | config/Compose fail-closed | partial | `backend/app/core/config.py` | 설정 로딩 코드는 있으나 환경변수 복호화 실패 시 앱이 종료되지 않고 빈 딕셔너리 및 기본값(fallback)으로 구동됨 |
| BASE-003 | check target 값 변환 domain 분리 | partial | `backend/app/api/agent/v1/router.py` | 변환 로직은 있으나 domain 분리 없이 라우터 내부에 하드코딩됨 |
| DOC-001 | 문서와 QA 산출물 docs 분류 | partial | `doc/` | docs 분류(03_planning 등)와 별도로 doc/에 산출물이 혼재되어 있음 |
| SEC-001 | Web API JWT 인증 강제 | partial | `backend/app/api/web/v1/router.py` | 인증 구조는 있으나 CUD API 엔드포인트 전체에 토큰 검증 적용 여부가 미확인/누락됨 |
| SEC-002 | 역할 권한·감사 로그 | partial | `backend/app/core/audit.py` | 감사 코드가 있으나 SYS_AUDIT_LOG의 IP, before-after 및 권한 매트릭스가 완비되지 않음 |
| AGT-001 | Agent PENDING 승인·credential 정책 | partial | `backend/app/api/agent/v1/router.py` | enroll API가 존재하지만 PENDING 대기 없이 즉시 APPROVED 처리됨 |
| CFG-001 | 운영 secret/SQL log 안전화 | partial | `backend/app/core/config.py` | 설정 검증이 있으나 secret/SQL 설정 fallback 값이 존재해 안전성 요건을 충족하지 못함 |
| JOB-001 | API와 Worker/Scheduler 분리 | partial | `backend/app/main.py` | worker/scheduler 코드가 있으나 lifespan 이벤트에서 API와 동일 프로세스로 기동함 |
| ING-001 | receipt ledger·batch 멱등성 | partial | `backend/app/api/agent/v1/router.py` | metric 수신 로직은 있으나 동일 batch 중복에 대한 receipt ledger 및 멱등성 검증이 부재함 |
| ING-002 | timestamp-monotonic current upsert | partial | `backend/app/api/agent/v1/router.py` | current upsert는 있으나 timestamp 역전 방지 검증이 없음 |
| ING-003 | Agent ACK 기반 spool | partial | `agent/spool.py` | spool 구현은 있으나 ACK 기반 재시도와 SQLite 보존 검증 테스트가 부재함 |
| ING-004 | History partition/retention | partial | `backend/app/api/agent/v1/router.py` | history 경로가 있으나 partition/retention 검증과 이력 insert 완결성이 미확인됨 |
| MON-001 | process/service/port 정의·history | partial | `backend/app/api/agent/v1/router.py` | 수집 경로는 있으나 상태 history 저장의 완결성이 미확인됨 |
| MON-002 | resource 세부 collector | partial | `agent/collectors/common.py` | 기본 collector는 있으나 CPU core, load, disk IO 등의 상세 지표가 누락됨 |
| MON-003 | 기간 조회·ServerDetail 추세 | partial | `backend/app/api/web/v1/router.py` | 조회 API는 있으나 MetricHistory 기반 기간 추세 contract가 미완성임 |
| MON-004 | dashboard 상태·상위 자원·drill-down | partial | `frontend/src/components/Dashboard.vue` | 대시보드 UI는 있으나 API와 browser 검증을 포함한 drill-down contract가 미완성임 |
| OPS-001 | server group/tag/filter | not-started | `backend/db_schema.json` | server_group 테이블 및 태그·필터 구조가 확인되지 않음 |
| ALT-001 | alert policy/outbox/history | partial | `backend/app/alert_worker.py` | alert worker는 있으나 outbox, test channel, retry, secret masking이 완비되지 않음 |
| INC-001 | incident state/timeline 고도화 | partial | `backend/app/api/web/v1/router.py` | event 처리 경로는 있으나 action/close/reopen 추적 timeline이 미완성임 |
| P3-GROUPED | 기타 별도 PRD 및 DB 확장 항목군 | blocked | N/A | 개발 DB와 환경 분리 승인, 개별 PRD가 없어 검증·구현 범위를 확정할 수 없음 |
