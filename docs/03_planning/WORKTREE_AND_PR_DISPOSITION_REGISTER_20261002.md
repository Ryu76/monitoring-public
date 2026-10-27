# 통합관제 Worktree 및 PR 처리 등록부

- **기준일:** 2026-10-02
- **저장소:** `Ryu76/monitoring`
- **기준 main:** `origin/main` / `b717a41`
- **목적:** 병합된 코드, 오래된 PR, 미커밋 변경을 혼동하지 않고 보존·검토·정리 순서를 통제한다.

> 이 등록부는 삭제·reset·merge 명령이 아니다. 각 대상의 처리 결정과 검증이 끝나기 전까지 기존 worktree를 보존한다.

---

## 1. 현재 GitHub PR 상태

| PR | 상태 | 기준 브랜치 | head 브랜치 | 판정 | 필요한 처리 |
|---|---|---|---|---|---|
| #1 | `MERGED` (2026-09-21) | `main` | `ai-pro/integrated-full-implementation` | main 반영 완료 | 과거 증거 보관 |
| #2 | `MERGED` (2026-09-22) | `main` | `ai-pro/performance-modular` | main 반영 완료 | dirty 후속 변경과 분리 |
| #4 | `MERGED` (2026-09-22) | `main` | `ai-pro/qa-oracle-remediation` | main 반영 완료 | current-main Oracle QA에서 재검증 |
| #5 | `MERGED` (2026-09-22) | `main` | `ai-pro/frontend-audit` | main 반영 완료 | current-main frontend build에서 재검증 |
| #3 | `OPEN` | `ai-pro/performance-modular` | `ai-pro/maintenance-account` | head commit `5e591f2`는 현재 `origin/main`의 조상 | 파일 비교 및 main 재검증 후 stale PR로 close 검토. merge 금지. |

PR #3은 `main`이 아니라 이미 병합된 feature branch를 base로 사용한다. open 상태만으로 미반영 작업으로 취급하지 않는다.

---

## 2. 보존 대상 worktree

| 경로 | 브랜치/기준 | 현 상태 | 내용 | 처분 전 필수 확인 |
|---|---|---|---|---|
| `E:\python\monitoring` | local `main` / `bc591bb` | dirty, `origin/main`보다 29 commits 뒤 | 오래된 원본과 22개 미커밋 변경 | 파일별 출처·의도·중복을 확인할 때까지 pull/reset/clean 금지 |
| `E:\python\monitoring-worktrees\ai-pro-orm-efficiency` | `ai-pro/orm-efficiency` / `b717a41` | dirty | ORM/query efficiency, scheduler/worker/read-model 변경 + 신규 query batch/test | API contract, query count, full regression, 새 PR 분리 |
| `E:\python\monitoring-worktrees\ai-pro-performance-modular` | `ai-pro/performance-modular` / main ancestor | dirty | schema/router/test/run_all 수정, install batch 삭제 | batch 삭제의 설치·운영 영향, current main과 차이, test runner all 검증 |
| `E:\python\monitoring-worktrees\ai-pro-maintenance-account` | `ai-pro/maintenance-account` / main ancestor | dirty | admin auth 수정, install batch 삭제, `sql.md` 신규 | main의 bootstrap 기능과 중복 여부, auth 영향, 문서 범위 확인 |
| `E:\python\monitoring-worktrees\ai-pro-monitoring-prd-audit-20260916` | old baseline | untracked 항목 존재 | 과거 PRD audit 문서/테스트 산출물 | 현재 PRD에 유효한 문서만 새 docs branch로 이관 |

### 공통 안전 규칙

```text
1. 현재 worktree에서 reset, clean, stash, merge, commit, push를 수행하지 않는다.
2. retain 판정을 받은 변경도 원 worktree에서 바로 commit하지 않는다.
3. origin/main 기준 clean branch로 재구성하고 focused test → full gate → review를 통과한 뒤 새 PR로 분리한다.
4. generated artifact, credential, local DB, test result directory는 commit 대상에서 제외한다.
```

---

## 3. Worktree별 판정 절차

### 3.1 ORM efficiency

**판정 목표:** 실제 query 감소와 response contract 보존이 증명되는 변경만 유지한다.

| 확인 항목 | 통과 기준 |
|---|---|
| API 응답 | URL, request/response fields, pagination/filter 의미 불변 |
| DB 효율 | 대표 다건 fixture에서 query 수 또는 batch 수가 측정 가능하게 감소 |
| Scheduler/worker | 기존 job 주기·중복 방지·failure handling 계약 불변 |
| 테스트 | read model contract, query efficiency, backend 전체 test, compile 통과 |
| 문서 | 측정 전후 조건과 결과를 기록 |

### 3.2 performance-modular 후속 diff

**판정 목표:** 이미 merged된 PR #2와 현재 미커밋 변경을 분리한다.

| 확인 항목 | 통과 기준 |
|---|---|
| `run_all.bat` | `all` 모드가 backend와 frontend 단계를 모두 실제 실행 |
| `install_*.bat` 삭제 | 설치 경로가 다른 공식 문서/runner로 대체되었음이 확인될 때만 허용 |
| schema/router 변경 | public contract 및 backend test 보존 |
| 결론 | 삭제의 근거가 부족하면 삭제 변경은 retain하지 않음 |

### 3.3 maintenance-account 후속 diff

**판정 목표:** maintenance bootstrap 커밋과 uncommitted admin auth 변경을 분리한다.

| 확인 항목 | 통과 기준 |
|---|---|
| bootstrap | 명시적 환경변수로만 local Oracle read-only maintenance mode가 활성화됨 |
| auth | 운영 admin 인증·권한·세션 정책을 우회하지 않음 |
| scripts/docs | 신규 `sql.md`와 batch 삭제가 비밀값·운영 절차를 훼손하지 않음 |
| PR 처리 | PR #3에 새 변경을 얹지 않고 새 branch에서 새 PR 생성 |

### 3.4 원본 local main 및 PRD audit worktree

**판정 목표:** 과거의 작업을 보존하면서 현재 main에 중복 반영하지 않는다.

| 분류 | 처리 |
|---|---|
| 이미 `origin/main`에 포함된 코드 | 중복으로 표시하고 원본 삭제는 별도 승인 후 결정 |
| 아직 유효한 문서 | `docs/03_planning/` 또는 `docs/06_quality/`로 현재 기준 갱신 후 이관 |
| 실패한 실험·생성물 | 근거와 함께 discard 후보로 등록, 승인 전 삭제 금지 |
| 비밀정보·로컬 설정 | Git/문서 이관 금지, 보안 검토 후 별도 관리 |

---

## 4. 새 작업 단위 생성 규칙

각 retain 항목은 다음 형식의 독립 PRD를 가진다.

```text
ID: MON-<AREA>-<NNN>
문제: 재현 가능한 현재 동작과 영향
목표: 변경 후 보장할 API/DB/운영 계약
허용 경로: 변경 가능한 파일과 금지 경로
비기능 조건: 성능, 동시성, RBAC, 감사, rollback
테스트: focused test, full backend, frontend build, browser/Oracle 조건
증거: 명령, commit, pass/fail count, 환경 범위
제외: 운영 배포·실제 알림·실제 DB DDL 등 별도 승인 필요 범위
```

이 규칙은 여러 worktree의 작업을 하나의 대형 PR 또는 기존 stale PR에 혼합하는 것을 방지한다.

---

## 5. 정리 완료 기준

다음 다섯 조건이 충족되어야 worktree 정리 또는 stale PR 종료를 실행할 수 있다.

1. 대상 diff의 모든 파일이 `retain`, `rework`, `discard` 중 하나로 분류됨
2. retain 변경은 clean branch의 새 PR로 재구성되었거나 이미 main 반영이 확인됨
3. discard 변경은 생성물/중복/실험임을 입증하는 기록이 남음
4. current `origin/main` clean QA 결과가 보존됨
5. 사용자 승인 없이 원본 worktree, branch, PR, local settings를 삭제하지 않음
