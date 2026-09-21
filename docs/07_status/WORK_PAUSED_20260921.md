# 통합 관제 작업 중지 보고서

- **기록 시각:** 2026-09-21 09:45 (로컬 시스템 시각)
- **상태:** `PAUSED` — 사용자 지시에 따라 추가 구현·AI Pro 실행·병합·배포를 중지함
- **작업 경로:** `E:\python\monitoring-worktrees\ai-pro-integrated-full-implementation`
- **브랜치:** `ai-pro/integrated-full-implementation`
- **기준 커밋:** `557bb35 wip: preserve production correctness remediation for review`

> 이 문서는 2026-09-21 중지 시점의 사실 기반 상태를 기록한다. 이전 `PROGRESS.md`의 과거 테스트 통과 기록은 해당 당시 증적이며, 현재 미커밋 보정 diff의 품질 상태를 의미하지 않는다.

## 1. 중지 조치 확인

| 대상 | 확인 결과 |
|---|---|
| Hermes background process | 활성 프로세스 `0`개 |
| AI Pro approved-PRD scheduler | `paused` / `enabled=false` |
| hourly progress scheduler | `paused` / `enabled=false` |
| 추가 구현·테스트·커밋·push | 본 문서 기록 이후 수행하지 않음 |

스케줄러 두 개는 이미 중지 상태였으며, 활성 실행은 확인되지 않았다. 재개는 사용자의 명시적 지시 후에만 수행한다.

## 2. Git / PR 상태

| 항목 | 현재 값 |
|---|---|
| 작업 트리 | dirty — tracked modified files 13개 |
| `origin/main` 대비 | behind 0 / ahead 12 |
| Pull request | [#1](https://github.com/Ryu76/monitoring/pull/1), `OPEN` |
| GitHub mergeable 표시 | `MERGEABLE` |
| GitHub status checks | 등록/보고된 check 없음 |
| 병합 승인 | **금지** |

`MERGEABLE`은 Git 충돌이 없다는 GitHub 표기일 뿐이다. 아래 compile gate 실패와 미검증 운영 통합 항목이 있으므로 병합 가능 상태가 아니다.

## 3. 보존된 미커밋 보정 범위

다음 13개 파일의 diff를 중지 시점 그대로 보존한다. 사용자 재개 전에는 reset, stash, commit, push, merge를 수행하지 않는다.

- `backend/alembic/versions/20260918_1028_c2a445586611_add_missing_oracle_tables.py`
- `backend/app/api/agent/v1/router.py`
- `backend/app/api/web/v1/extension.py`
- `backend/app/core/config.py`
- `backend/app/db_init.py`
- `backend/app/main.py`
- `backend/app/models/resource.py`
- `backend/app/schemas/extension.py`
- `backend/app/worker_main.py`
- `backend/preflight.py`
- `backend/tests/test_db_url_safety.py`
- `backend/tests/test_history_failure.py`
- `backend/tests/test_oracle_migration.py`

보정 의도는 Oracle 11g migration/ID generator, ingestion receipt-history 원자성 및 stale snapshot, P3 RBAC/audit, structured DB URL, runtime DDL 제거, worker compose/entrypoint, 회귀 테스트 강화이다. 이 diff는 아직 검증 완료 산출물이 아니다.

## 4. 중지 시점 검증 결과

### 통과

```text
git diff --check
```

- whitespace 오류 없음.

### 실패 — 병합 차단

```text
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend \
  python -m compileall -q backend
```

결과:

```text
backend/app/api/agent/v1/router.py, line 473
IndentationError: unexpected indent
```

따라서 backend pytest는 app import 단계에서 막히므로, 현재 diff에 대한 전체 테스트 통과 주장은 유효하지 않다.

추가로 직전 직접 pytest 실행에서 다음 회귀가 재현되었다.

```text
3 failed, 42 passed, 9 warnings
```

- reserved-character DB URL 테스트의 config reload/monkeypatch 경로 불일치
- stale snapshot 감지 뒤 current deletion이 계속될 수 있는 제어 흐름 결함
- 동일 batch 내 current metric의 중복 INSERT로 인한 unique-constraint 실패

## 5. 재개 시 최소 안전 순서

1. `backend/app/api/agent/v1/router.py`의 473행 indentation 오류부터 한 가지 변경으로 복구한다.
2. stale snapshot 분기가 delete/watermark 변경을 건너뛰는지 focused regression test로 증명한다.
3. 동일 batch duplicate current metric 처리 회귀를 복구하고 테스트한다.
4. Oracle 11g migration의 legacy generator가 `MAX(PK)+1`부터 생성되는지 및 신규/기존 객체 소유 경계를 검토한다.
5. 아래 전체 gate를 직접 실행하고 실제 pass/fail count를 기록한다.

```text
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m pytest backend/tests -q
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m compileall -q backend
git diff --check
```

6. Oracle endpoint·암호화된 설정 및 Docker daemon은 별도 운영 승인/환경이 있을 때만 fail-closed 방식으로 검증한다.
7. 독립 코드리뷰와 최종 QA가 모두 통과하기 전에는 PR #1을 병합하지 않는다.

## 6. 중지 시점 결론

- 작업은 **중지됨**.
- 미커밋 diff는 **보존됨**.
- PR #1은 **열려 있으나 병합 금지**.
- 현재 산출물은 **compile 실패** 상태이며 완료·배포·운영 적용으로 표현할 수 없다.

## 7. 중지 후 사용자 승인 수동 보정 (2026-09-21)

사용자의 명시적 요청에 따라, scheduler는 계속 중지한 채 코딩 작업자가 문서 5절의 최소 복구 범위만 보정했다. 기존 미커밋 변경은 reset, stash, commit, push, merge 없이 보존했다.

### 보정 내용

- `backend/app/api/agent/v1/router.py`
  - `db.execute(...)` 호출의 문법 오류를 복구했다.
  - stale replace-set snapshot이 current 삭제나 watermark 변경 전에 제외되도록 했다.
  - replace-set watermark가 request envelope이 아니라 해당 metric item들의 최대 `collected_at`을 사용하도록 했다.
  - 동일 batch 내 같은 current PK가 중복 INSERT되지 않도록 transaction-local current cache를 추가했다. history는 각 관측을 모두 유지한다.
- `backend/tests/test_history_failure.py`
  - stale snapshot이 여러 current dimension과 watermark를 보존하는 회귀 테스트를 추가했다.
  - 동일 batch duplicate current PK의 latest-current / all-history 동작을 검증하는 회귀 테스트를 추가했다.
- `backend/tests/test_db_url_safety.py`
  - reserved-character password를 실제 fixture 값으로 검증하도록 수정했다.

### 독립 재검증 결과

```text
PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m pytest backend/tests -q
46 passed, 9 warnings

PYTHONPATH=backend conda run --no-capture-output -n monitor_backend python -m compileall -q backend
exit 0

git diff --check
exit 0
```

이 보정은 기존 compile blocker 및 문서화된 3개 SQLite regression을 해소한 범위의 증적이다. Oracle endpoint/migration 실적용, Docker topology, 실제 외부 알림, 실제 backend 연동 browser E2E 및 독립 merge review는 여전히 수행되지 않았으므로 PR #1 병합 금지 상태는 유지한다. AI Pro scheduler와 progress scheduler 역시 `paused` 상태를 유지한다.

## 8. Push 직전 독립 리뷰에서 확인된 추가 병합 차단 위험

2026-09-21의 read-only 독립 리뷰는 `backend/app/api/agent/v1/router.py`의 replace-set snapshot watermark 처리에 **동시성 경합 위험**을 확인했다.

- watermark를 일반 조회한 뒤 Python에서 비교하고, 그 후 current를 delete/replace한다.
- `(server_id, metric_code)`에 대한 row lock, version check, conditional compare-and-set이 없다.
- 두 요청이 교차하면, 먼저 조회한 이전 snapshot이 나중에 더 최신 snapshot의 current/watermark를 덮어쓸 가능성이 있다.

serial SQLite regression과 backend pytest 46개 통과는 이 interleaving을 검증하지 않는다. 이 항목은 **feature branch에 WIP 보존 커밋을 올리는 것을 막지는 않지만**, Oracle/운영 배포 및 PR #1 병합을 막는 `HIGH` 위험이다. 재개 시 transaction-safe conditional watermark acquisition 또는 per-metric serialization과 2-session concurrency regression test가 필요하다.

같은 리뷰에서 Oracle migration 테스트가 현재 source-text assertion 위주라 실제 Oracle 11g DDL 렌더/실행 문법을 증명하지 못한다는 검증 공백도 확인됐다. 이는 현재 확인된 문법 결함은 아니지만, Oracle 적용 전 offline DDL render 또는 승인된 Oracle 호환 환경 검증이 필요하다.
