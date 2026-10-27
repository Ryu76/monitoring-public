# 통합관제 현재 PRD 상태 및 완료 계획

- **기준일:** 2026-10-02
- **대상 저장소:** `Ryu76/monitoring`
- **기준 코드:** `origin/main`의 `b717a41` (`Merge pull request #5 from Ryu76/ai-pro/frontend-audit`)
- **문서 목적:** 과거 진행 보고·PR·worktree를 현재 GitHub 및 로컬 Git 상태와 대조하여, PRD 완료 기준과 다음 실행 순서를 하나의 기준 문서로 정리한다.
- **비밀정보 원칙:** DB DSN, 계정, 비밀번호, 토큰, 암호화 키는 이 문서에 기록하지 않는다.

> 이 문서는 `MASTER_PRD_BACKLOG.md`의 구현 백로그를 대체하지 않는다. 2026-10-02 시점의 **현재 상태, 검증 범위, 병합 후 잔여 worktree, 추가 계획**을 명확히 하는 운영 기준 문서다.

---

## 1. 판단 원칙과 문서 우선순위

### 1.1 상태 판단 원칙

1. GitHub `origin/main` 및 병합 PR이 코드 반영 여부의 기준이다.
2. 과거 `PROGRESS.md`, `WORK_PAUSED_20260921.md`, 개별 worktree의 보고서는 당시 증거이며 현재 상태를 자동으로 보장하지 않는다.
3. 단위 테스트·mocked browser test·SQLite 테스트는 범위가 제한된 증거다. Oracle, Docker worker topology, 실제 브라우저-백엔드, 운영 알림은 별도 증거가 필요하다.
4. 원본 worktree 또는 미커밋 변경을 reset, clean, stash, pull로 제거하지 않는다. 먼저 보존·분류·검증한다.
5. 운영 Oracle DDL은 암시적 commit이므로, 명시 승인된 additive change와 변경 창 없이 실행하지 않는다.

### 1.2 문서 우선순위

| 우선순위 | 문서/증거 | 용도 |
|---|---|---|
| 1 | GitHub `origin/main`, 병합 PR, clean worktree 검증 결과 | 현재 코드 반영·검증 판단 |
| 2 | 본 문서 | 재개 순서, 완료 게이트, 의사결정 기준 |
| 3 | `MASTER_PRD_BACKLOG.md` | 기능 백로그·PRD ID별 목표 |
| 4 | `WORKTREE_AND_PR_DISPOSITION_REGISTER_20261002.md` | dirty worktree 및 PR 처리 대상 |
| 5 | `07_status/PROGRESS.md`, `07_status/WORK_PAUSED_20260921.md` | 과거 실행 증거·이력 |

---

## 2. 반영 완료된 코드 기준선

2026-10-02에 확인한 GitHub 병합 이력은 다음과 같다.

| PR | 병합일 | 반영 범위 | 현재 판정 |
|---|---:|---|---|
| #1 | 2026-09-21 | 통합 PRD 구현·수집 안정성·Oracle 11g migration 보정·DPAPI 설정·기본 QA | `origin/main` 반영 |
| #2 | 2026-09-22 | read model 모듈화·Windows 전체 테스트 runner·lazy chart | `origin/main` 반영 |
| #4 | 2026-09-22 | Oracle-backed authentication 및 QA 보정 | `origin/main` 반영 |
| #5 | 2026-09-22 | frontend audit 지적 보정 | `origin/main` 반영 |

현재 `origin/main`에 반영된 구현에는 다음이 포함된다.

- Agent 수집·승인 상태·spool·receipt/watermark 정합성 모델
- Oracle 11g additive migration 및 trigger pseudorecord escape 보정
- P3 확장 관제 기반, RBAC/audit 관련 보정 범위
- API/worker 분리와 Windows용 전체 테스트 runner 기반
- dashboard/read model 모듈화 및 lazy chart loading
- frontend audit 보정

이 목록은 코드가 병합되었다는 사실을 뜻한다. 운영 환경에서의 완전한 전환·배포 검증을 뜻하지는 않는다.

---

## 3. 검증 증거와 남은 검증 공백

### 3.1 과거에 기록된 성공 증거

아래는 과거 실행 로그에 기록된 증거이며, 현재 clean `origin/main` 전체에 대한 재검증 결과는 아니다.

| 검증 | 마지막 기록된 결과 | 증명 범위 |
|---|---|---|
| Backend pytest | `46 passed, 9 warnings` | SQLite/mock 기반 backend 회귀 |
| Python compile | pass | Python 문법/bytecode |
| Frontend production build | pass | TypeScript/Vite build |
| Git whitespace | pass | 당시 diff의 whitespace |
| Oracle read-only preflight | pass | Oracle 11.2.0.1.0 연결·baseline schema 접근, rollback |
| Approved additive Oracle migration | pass | 승인된 `c2a445586611` additive 객체 적용 |
| Oracle DML rollback test | pass | check target/result 및 receipt ledger DML rollback |

### 3.2 완료 전 반드시 닫아야 하는 공백

| 게이트 | 미완료 증거 | 완료 기준 |
|---|---|---|
| Clean-main regression | 최신 `origin/main`에서 backend/frontend 품질 게이트를 한 번에 재실행한 기록 없음 | 전용 clean worktree에서 backend test, compile, frontend build, runner `all` 결과 보존 |
| Dirty diff review | 4개 worktree 및 원본 폴더에 미커밋 변경 존재 | 파일별 retain/rework/discard 결정과 독립 테스트·리뷰 |
| Browser-backend E2E | mocked Playwright만으로는 실제 backend/history 계약을 증명하지 못함 | test backend + seeded DB를 사용한 최소 browser smoke |
| Oracle runtime integration | 과거 DDL/DML 증거는 있으나 현 코드 기준 login→Bearer→보호 endpoint 및 schema contract 재검증 없음 | read-only preflight, rollback DML, 인증 체인 QA |
| Worker topology | Compose/worker 실행을 현 병합본 기준으로 실제 검증한 증거 없음 | API와 worker 동시 기동, scheduler/outbox 경로 smoke |
| 운영 전환 | 실제 알림·운영 Agent·배포·UAT 미수행 | 별도 승인 후 UAT, rollback rehearsal, 운영 인수 |

---

## 4. 추가 계획: 순서와 완료 조건

### Phase 0 — 증거 보존 및 작업공간 격리

**목적:** 기존 작업을 잃지 않고 재검증 가능한 기준선을 만든다.

1. 원본 `E:\python\monitoring`의 dirty 상태를 보존한다.
2. `WORKTREE_AND_PR_DISPOSITION_REGISTER_20261002.md`의 대상별로 수정 파일·테스트·의도를 읽고 분류한다.
3. `origin/main`에서 새 clean QA worktree를 만들고, 원본·dirty worktree와 분리한다.
4. 이 단계에서는 reset, stash, force push, merge, 운영 DB 변경을 하지 않는다.

**완료 조건:** 모든 dirty worktree가 보존되며, clean QA worktree가 `origin/main`과 동일한 commit을 가리킨다.

### Phase 1 — 현재 main 재검증

**목적:** 과거 성공 기록이 아닌 2026-10-02 이후의 current-main 증거를 만든다.

권장 명령은 프로젝트의 Conda 계약을 유지한다.

```text
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m pytest backend/tests -q
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m compileall -q backend
cd frontend && npm run build
run_all.bat all
```

- `run_all.bat all`은 backend와 frontend가 모두 실제 실행되는지 별도 확인한다.
- 브라우저 test가 있으면 mock 여부와 실제 backend smoke 여부를 분리해 기록한다.
- 실패 시 clean worktree에 임의 수정을 누적하지 않고, 실패 원인·재현 명령·영향 범위를 기록한다.

**완료 조건:** 정확한 pass/fail 개수, warning, 실행 commit, 명령, 시각이 `07_status/`에 남는다.

### Phase 2 — 미커밋 변경 분류 및 독립 PR화

**목적:** 여러 worktree의 변경을 하나의 불명확한 작업으로 섞지 않는다.

1. ORM efficiency diff는 query count, API response contract, 전체 회귀 테스트로 평가한다.
2. performance/maintenance worktree의 설치 배치 파일 삭제는 실제 설치 문서·운영 경로 영향이 확인되기 전까지 반영하지 않는다.
3. maintenance auth 후속 수정은 이미 main에 포함된 bootstrap 기능과 중복 여부를 확인한다.
4. PRD audit worktree의 문서·테스트는 코드 변경과 분리한다.
5. retain 결정된 단위만 새 clean branch에서 재구성하고, focused test → 전체 gate → 독립 리뷰 순으로 새 PR을 만든다.

**완료 조건:** 각 diff가 `retain`, `rework`, `discard` 중 하나로 결정되고, retain 항목은 단일 목적 PR과 재현 가능한 검증 결과를 가진다.

### Phase 3 — GitHub PR 및 브랜치 정리

**목적:** 실제 반영 상태와 GitHub 화면의 상태를 일치시킨다.

- PR #3은 head commit이 `origin/main`의 조상으로 확인되지만, base branch가 `ai-pro/performance-modular`인 오래된 PR이다.
- 파일 수준 비교와 현재 main의 검증을 마친 뒤, 중복 PR이면 **merge가 아니라 close** 한다.
- 이미 main에 포함된 worktree branch는 별도 변경이 없고 보존 가치가 없다는 판단이 끝난 뒤에만 정리한다.

**완료 조건:** open PR은 실제 미반영 코드를 전달하는 PR만 남고, stale PR·branch의 처리 근거가 기록된다.

### Phase 4 — Oracle 및 실제 통합 QA

**목적:** mock/SQLite 증거를 Oracle·인증·worker 실행 증거로 보완한다.

1. 설정은 암호화된 파일 또는 승인된 실행 환경에서만 제공한다. 비밀값은 채팅·Git·문서에 기록하지 않는다.
2. 우선 `SELECT 1 FROM DUAL`, 버전, schema ownership, required table/index/trigger를 read-only 확인한다.
3. 로그인 → Bearer token → 즉시 보호 endpoint를 실제 DB 인증 흐름으로 검사한다.
4. 필요한 DML smoke는 명시적 transaction과 `ROLLBACK`으로 실행한다.
5. DDL은 이미 적용된 additive migration과 현재 schema를 read-only로 대조한다. 새 DDL은 변경 창·DBA 승인·rollback 계획이 없으면 실행하지 않는다.
6. API와 worker를 함께 기동하여 heartbeat, event/outbox, retry, duplicate receipt, stale snapshot 경로를 시험한다.

**완료 조건:** Oracle version·schema·권한·인증 체인·rollback DML·worker path의 증거가 현 commit 기준으로 보존된다.

### Phase 5 — 제한 운영 및 인수

**목적:** 실제 운영 전환을 조건부·가역적으로 검증한다.

- 테스트 Agent와 승인된 test notification channel만 사용한다.
- 운영 배포 전에 backup, restore, rollback owner, stop criteria, alert contact를 서면 확정한다.
- 제한 운영 중 API/worker/alert/DB 상태, error budget, spool backlog, audit log를 관찰한다.
- 중단 기준이 발생하면 신규 흐름을 중지하고 승인된 rollback 절차로 전환한다.

**완료 조건:** UAT, rollback rehearsal, 운영 책임자 인수, 운영 전환 체크리스트가 모두 승인된다.

---

## 5. PRD 완료 판정

| 판정 | 정의 |
|---|---|
| `MERGED` | 코드가 `origin/main`에 반영됨. 운영 검증 완료를 의미하지 않음. |
| `VERIFIED_LOCAL` | clean worktree에서 unit/contract/build 등의 로컬 검증을 현재 commit 기준으로 통과함. |
| `VERIFIED_ORACLE` | 승인된 Oracle 환경에서 read-only/rollback 범위의 통합 검증을 통과함. |
| `READY_FOR_LIMITED_OPERATION` | current-main 검증, Oracle/worker/browser 통합 QA, rollback 계획, 담당자 승인이 충족됨. |
| `DONE` | 제한 운영·롤백 리허설·운영 인수까지 완료됨. |

현재 판정은 다음과 같다.

```text
코드 병합: 주요 기능 MERGED
현재 main 전체 재검증: NOT_YET_VERIFIED
운영 Oracle/worker/browser 통합: PARTIALLY_EVIDENCED, current-main 재검증 필요
제한 운영/인수: NOT_STARTED
프로젝트 완료: NOT_DONE
```

---

## 6. 재개 전 금지 사항

- dirty 원본 또는 worktree에서 `git reset --hard`, `git clean -fd`, force push를 실행하지 않는다.
- 원본 `main`에 pull/merge하지 않는다. 먼저 보존·분류한다.
- 새로운 코드 변경을 PR #3에 추가하지 않는다.
- DB DSN·password·token·암호화 키를 문서, 로그, 대화에 남기지 않는다.
- Oracle DDL을 `alembic upgrade head`로 일괄 실행하지 않는다. 승인된 additive revision만 별도 검토 후 적용한다.
- mock 성공을 실제 Oracle, 실제 browser, 실제 notification, 운영 배포 성공으로 표현하지 않는다.
