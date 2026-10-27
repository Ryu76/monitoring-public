# PRD Acceptance Ledger (2026-10-02)

| ID | Status | Source (Code) | Test Evidence | External Prerequisite / Blocker |
|---|---|---|---|---|
| BASE-001 | implemented | `frontend/src/router/index.ts:3-8` and separate route chunks | `frontend/tests/e2e.spec.ts:5-121` (API intercepted) & `npm run build` PASS (browser-mocked.log) | None |
| BASE-002 | implemented | `backend/app/core/config.py`, `backend/app/core/database.py` | Pytest (`backend/tests/test_compose_structure.py`, `backend/tests/test_config.py` - SQLite fixtures) | None |
| BASE-003 | implemented | `backend/app/domain/check_targets.py`, `backend/app/api/web/v1/router.py:14,242,260` | Pytest (`backend/tests/test_check_target_values.py`) | None |
| DOC-001 | partial | `docs/03_planning`, `docs/07_status` | Directory structure inspection | Needs manual merge from other worktrees |
| SEC-001 | partial | `backend/app/api/dependencies.py` | Pytest (`backend/tests/test_sec_001.py` - 4 cases, SQLite fixtures) | 권한 매트릭스 확정 대기 |
| SEC-002 | partial | `backend/app/models/system.py:100`, `backend/app/core/audit.py:13` | Pytest (`backend/tests/test_audit.py`) | DB migration 설계 확정 대기 |
| AGT-001 | partial | `backend/app/api/agent/v1/router.py` | Pytest (`backend/tests/test_agt_001.py` - SQLite mocked)<br>**Unresolved Local**: automatic-approval (enrollment bypasses PENDING, sets APPROVED), reenrollment bypass (rotates UID & APPROVED), missing enrollment-to-approval negative tests | 등록 token/rotation 정책 결정 대기 |
| CFG-001 | implemented | `backend/app/core/config.py` | Pytest (`backend/tests/test_cfg_001.py` - SQLite fixtures) | None |
| JOB-001 | partial | `backend/app/worker_main.py`, `backend/app/aggregator.py` | Pytest (`backend/tests/test_worker_lifecycle.py` - local lock, API/Worker separation, graceful shutdown) | 실행 topology 확정 대기 |
| ING-001 | blocked | `backend/app/models/resource.py`, `backend/app/api/agent/v1/router.py` | Pytest (`test_agent_metrics.py::test_ing_001_batch_idempotency` - SQLite fixtures, migration assertions only) | 개발 Oracle 환경 필요 (historical 2026-09-21 read-only/additive/rollback evidence exists but is not current-code completion) |
| ING-002 | blocked | `backend/app/models/resource.py`, `backend/app/api/agent/v1/router.py` | Pytest (`test_agent_metrics.py::test_ing_002_monotonic_upsert`, `test_history_failure.py` - SQLite mocked tests) | ING-001 선행 |
| ING-003 | implemented | `agent/spool.py` | Pytest (`agent/test_spool.py::SpoolerTests::test_push_and_pop` - SQLite fixtures, **limited coverage**) | None |
| ING-004 | blocked | `backend/app/api/web/v1/router.py`, `backend/app/models/resource.py` | None | 개발 Oracle 승인 대기 |
| MON-001 | implemented | `backend/app/models/process.py` | Pytest (`backend/tests/test_mon_001.py` - 2 cases, SQLite fixtures) | None |
| MON-002 | implemented | `agent/collectors/common.py`, `backend/app/api/agent/v1/router.py` | Pytest (`agent/tests/test_resource_rates.py` - Real E2E wiring with psutil, reconnect handling; `backend/tests/test_agent_metrics.py` - backward compat definition schema update) | None |
| MON-003 | implemented | `backend/app/api/web/v1/router.py` | Pytest (`backend/tests/test_mon_003.py` - 1 case, SQLite fixtures) | None |
| MON-004 | implemented | `frontend/src/components/Dashboard.vue` | Frontend build PASS, Chromium intercepted API mocked evidence | Browser 검증 필요 (seeded DB) |
| OPS-001 | implemented | `backend/app/models/server.py`, `backend/app/api/web/v1/servers.py` | Pytest (`backend/tests/test_web_read_models.py` - read-model tests with limited filter fixture) | None |
| ALT-001 | implemented | `backend/app/alert_worker.py`, `backend/app/core/notifier.py` | Pytest (`backend/tests/test_alt_001.py` - 2 cases, SQLite fixtures, mocked transports) | Test channel 확정 대기 |
| INC-001 | implemented | `backend/app/models/event.py` | Pytest (`backend/tests/test_inc_001.py` - 1 case, SQLite fixtures) | None |

## Notes
- "implemented" means code exists and local tests pass. It does not imply external UAT/Oracle gates are cleared.
- "partial" means the feature is partially implemented or missing key requirements, either local gaps (marked **Unresolved Local**) or missing prerequisites.
- "blocked" means it requires external dependencies (Oracle, auth matrices) that are explicitly listed as missing.
