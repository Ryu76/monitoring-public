# 통합 관제 개발 진행 기록

## 작업 정책

- 작업 종료 시각: **2026-09-16 09:00 KST**
- 자동 commit, push, deploy, 운영 DB 쓰기·DDL은 수행하지 않는다.
- 운영 DB·인증 정보·`.env`는 생성하거나 수정하지 않는다.
- `READY_FOR_REVIEW` 결과와 실제 테스트 로그가 있을 때만 기능 완료로 표기한다.

## 2026-09-15 기준선

### 확인된 상태

- 백엔드·에이전트 Python 정적 컴파일: 통과.
- 프론트엔드 초기 빌드는 `vue-tsc` 누락으로 실패했다.
- `npm ci`로 lockfile 기준 의존성을 복구했다.
- 복구 후 `npm run build` 성공: Vite 프로덕션 번들 생성 완료.
- 번들 경고: 초기 JavaScript chunk가 500 kB를 넘는다. 기능 실패는 아니며 코드 분할 검토 대상이다.
- 로컬 백엔드(8000), 프론트엔드(5173/5174), 에이전트 실행 프로세스는 확인되지 않았다.
- 자동화 테스트 파일은 발견되지 않았다. Agent → API → DB → UI E2E 검증도 미완료다.

### 2026-09-15 프론트엔드 번들 분할 작업

- 별도 worktree `E:/python/monitoring-worktrees/frontend-code-splitting`에서 `frontend/src/router/index.ts`의 6개 화면 import를 lazy dynamic import로 전환했다.
- route path/name/meta와 `beforeEach` 로그인 가드는 변경하지 않았다.
- 검증: 저장소 루트에서 `npm --prefix frontend run build` 성공.
- 결과: 초기 entry JavaScript가 **683.37 kB → 99.46 kB**로 감소했고, 화면별 chunk가 생성됐다.
- 남은 경고: `ServerDetail` lazy chunk가 519.91 kB로 아직 500 kB를 넘는다. 초기 로드 차단은 해소됐지만, 해당 화면 내부 의존성 추가 분할은 별도 low-risk PRD가 필요하다.
- 상태: **READY_FOR_REVIEW**. worktree 변경은 아직 commit/merge하지 않았다.

### 2026-09-15 설정 보안 fail-closed 작업

- 별도 worktree `E:/python/monitoring-worktrees/security-config`에서 DB/JWT/초기 관리자 값의 소스 fallback을 제거하고, 값이 없으면 설정 로드가 실패하도록 변경했다.
- Docker Compose의 정적 비밀값을 승인된 secret source에서 주입해야 하는 필수 변수 계약으로 교체했다.
- `backend/.env.example`에는 실제 값이 없는 placeholder만 추가했다.
- 회귀 검증: `backend/tests/test_config.py`에서 명시적 test 값 수용과 필수 설정 누락 시 fail-closed를 자동화했다.
- 검증: `python -W error::DeprecationWarning -m unittest discover -s backend/tests -p 'test_*.py' -v` 2건 통과, Python compile 통과, placeholder 값으로 `docker compose config --quiet` 통과.
- 상태: **READY_FOR_REVIEW**. worktree 변경은 아직 commit/merge하지 않았다.

### AI Pro 전용 실행 경로 준비

- 전용 worktree `E:/python/monitoring-worktrees/server-detail-vendor-split`와 로컬 Harness root를 초기화했다. Harness는 이 worktree만 allowlist로 허용한다.
- 첫 low-risk PRD `monitoring-20260915-001`은 `.harness/inbox/`에 **draft**로 작성했다. ECharts/vendor chunk 분리에 한정하며 `frontend/vite.config.ts`만 수정 가능하다.
- AI Pro executor는 `agy`의 Google AI Pro 로그인 세션을 사용한다. `--dangerously-skip-permissions`를 제거하고 `--sandbox`, 28분 print timeout을 적용했다.
- sandbox 기반 실제 AI Pro smoke call은 `AI_PRO_SANDBOX_READY`를 반환했고, Harness 회귀 테스트 7건과 Python compile이 통과했다.
- no-agent runner job `e54ac5fb9a1b`가 20분 간격으로 승인 PRD 하나만 실행하도록 예약됐다. 보고 job과 별개이며, `2026-09-16 09:00 KST` 이후에는 내장 deadline guard가 실행을 거부한다.
- **현재 코드 실행 대기 상태:** draft를 사람이 `approved/`로 직접 옮기기 전에는 AI Pro 호출·코드 변경을 시작하지 않는다.

### 현재 우선순위

1. `ServerDetail` chunk의 원인을 확인하고, API·UI 계약 변경 없이 추가 분할 가능한지 분석한다.
2. `docs/LOCAL_E2E_VALIDATION_PLAN.md` 기준으로 개발 DB 승인 전 수행 가능한 정적·계약 검증을 보강한다.
3. DB·Agent·UI 통합 실행은 암호화된 자격 증명과 명시적 로컬 개발 DB 승인 전에는 시작하지 않는다.

### 현재 차단 요인

- Backend 전용 가상환경과 암호화된 로컬 설정 파일이 없다.
- Oracle/운영 DB 연결, Agent 등록·승인, 실제 지표 적재, 브라우저 E2E 증거가 없다.
- 프론트엔드 build는 통과했으나 번들 크기 경고가 남아 있다.
