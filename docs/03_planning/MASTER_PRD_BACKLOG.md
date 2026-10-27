# 통합관제 마스터 PRD 백로그

## 원칙

- 구현은 API URL·payload·DB schema의 공개 계약을 먼저 고정하고, 작은 검증 가능 단위로 진행한다.
- Python/Harness/test는 Conda `monitor_backend`만 사용한다.
- 운영 Oracle·운영 Agent·실제 알림 채널·운영 비밀값은 명시 승인 전 사용하지 않는다.
- 자동 commit/push/merge/deploy는 하지 않는다.
- 2026-10-02 현재 병합 상태·검증 공백·worktree 정리 순서는 [현재 PRD 상태 및 완료 계획](CURRENT_PRD_STATUS_AND_COMPLETION_PLAN_20261002.md)과 [Worktree 및 PR 처리 등록부](WORKTREE_AND_PR_DISPOSITION_REGISTER_20261002.md)를 기준으로 한다. 이 백로그의 과거 상태 표기는 당시 기록이며, 현재 코드 반영 여부는 `origin/main`과 병합 PR로 대조한다.

## 0. 현재 반영·검증 가능한 기준선

| ID | 항목 | 상태 |
| --- | --- | --- |
| BASE-001 | frontend route lazy loading | 통합 worktree 반영·production build PASS |
| BASE-002 | config/Compose fail-closed | 통합 worktree 반영·Conda test PASS |
| BASE-003 | check target 값 변환 domain 분리 | 통합 worktree 반영·pytest 3 PASS |
| DOC-001 | 문서와 QA 산출물 docs 분류 | 진행 중 |

## 1. P0 — 보안·신뢰성 기반

| ID | 구현 범위 | 완료 기준 | 선행 조건 |
| --- | --- | --- | --- |
| SEC-001 | Web API JWT 인증 강제 | 무토큰 401, 역할 부족 403, CUD 계약 test | 권한 매트릭스 확정 |
| SEC-002 | 역할 권한·감사 로그 | actor/IP/target/before-after 기록, UI/API 테스트 | DB migration 설계 |
| AGT-001 | Agent PENDING 승인·credential 정책 | 미승인 수집 차단, 승인 후 허용 | 등록 token/rotation 결정 |
| CFG-001 | 운영 secret/SQL log 안전화 | source fallback 없음, echo false, secret scan PASS | BASE-002 |
| JOB-001 | API와 Worker/Scheduler 분리 | 중복 실행 없음, graceful shutdown | 실행 topology 결정 |

## 2. P1 — 수집 데이터 정확성

| ID | 구현 범위 | 완료 기준 | 선행 조건 |
| --- | --- | --- | --- |
| ING-001 | receipt ledger·batch 멱등성 | 같은 batch 중복 history 없음 | 개발 Oracle migration |
| ING-002 | timestamp-monotonic current upsert | 과거 metric이 current 역전 안 함 | ING-001 |
| ING-003 | Agent ACK 기반 spool | crash/restart 후 ACK 전 payload 보존 | SQLite tests |
| ING-004 | History partition/retention | 현재 시점 history insert·보관 확인 | 개발 Oracle 승인 |

## 3. P2 — 핵심 관제 기능

| ID | 구현 범위 | 완료 기준 |
| --- | --- | --- |
| MON-001 | process/service/port 정의·history | OS별 상태·current/history/API/UI |
| MON-002 | resource 세부 collector | CPU core/load/swap/disk IO/network rate·dimension contract |
| MON-003 | 기간 조회·ServerDetail 추세 | range 제한, average/max/threshold chart |
| MON-004 | dashboard 상태·상위 자원·drill-down | filter와 URL 상태를 포함한 browser 검증 |
| OPS-001 | server group/tag/filter | CRUD·다중 배정·dashboard/API 일관성 |
| ALT-001 | alert policy/outbox/history | test channel, retry, secret masking |
| INC-001 | incident state/timeline 고도화 | event→incident→action→close/reopen trace |

## 4. P3 — 확장 관제·운영 플랫폼

URL/SSL, 로그, Oracle/DB, batch/file, HA, remote command approval, config versioning, report/retention, package/service/deployment을 각각 별도 PRD와 개발 DB/테스트 자산으로 진행한다.

## 5. QA 게이트

각 PRD는 `06_quality/01_테스트계획서.md`와 테스트 수행가이드를 따른다. 최소 unit/contract/negative/regression을 통과하고, DB·브라우저·UAT는 전용 개발 환경 증거가 확보될 때만 완료 처리한다.

## 현재 차단 항목

- 전용 개발 Oracle, 암호화된 개발 설정, 안전한 테스트 계정이 없어 DB 통합·3회 수집·UAT·성능/부하·운영 배포 QA는 실행할 수 없다.
- 권한 매트릭스와 Agent credential/등록 정책이 확정되지 않아 SEC-001/AGT-001의 공개 계약을 확정할 수 없다.
