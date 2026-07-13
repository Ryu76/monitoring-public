# Agent 데몬 (Phase 1) 및 백기 작업 처리기 / 스케줄러 (Phase 2) 구현 계획서

에이전트로부터 지표 데이터를 주기적으로 수집하여 저장하고, 임계값을 검사하여 경보를 발행하는 전체 시스템 파이프라인(Phase 1 & 2)을 구축합니다. 또한, 관리자의 수동 승인 단계를 생략하고 에이전트 등록 시 바로 승인(`APPROVED`)되도록 처리하여 승인 관련 대기 및 인터페이스 복잡성을 줄입니다.

## User Review Required

> [!IMPORTANT]
> - **자동 승인 정책 적용**: 기존에 `PENDING` 상태로 등록된 후 관리자의 수동 승인을 거쳐야 `verify_agent` 인증을 통과했던 프로세스를, 최초 등록 시 즉시 `APPROVED` 상태로 등록되도록 변경합니다. 이에 따라 웹 화면에서의 승인 대기 단계 및 관련 버튼 인터페이스 요구가 제거됩니다.
> - **의존성 모듈 설치**: 수집 데몬(Agent) 작동을 위해 `psutil` 라이브러리가 필요합니다. 사용자 동의하에 가상환경에 설치를 진행하겠습니다.

## Proposed Changes

### [MODIFY] [dependencies.py](file:///e:/monitor/backend/app/api/dependencies.py)
- 에이전트 자동 승인 정책에 따라 테스트 및 인증 로직 검증 부분을 정렬합니다.

### [MODIFY] [router.py](file:///e:/monitor/backend/app/api/agent/v1/router.py)
- `/enroll` API 호출 시 새롭게 등록되거나 갱신되는 `Agent` 레코드의 `status_code`를 `'PENDING'`이 아닌 `'APPROVED'`로 저장하도록 변경합니다.
- `AgentStatusCurr` 테이블의 초기 상태를 `'NORMAL'`로 인서트합니다.

---

### [NEW] Agent Daemon Component (Phase 1)
에이전트 데몬을 관리하기 위한 폴더인 `e:\monitor\agent`를 신규 생성하고 아래 구조로 작성합니다.

#### [NEW] [config.py](file:///e:/monitor/agent/config.py)
- 중앙 API 엔드포인트 URL, 수집 주기, 로컬 SQLite 경로, 에이전트 메타데이터 정의.

#### [NEW] [spool.py](file:///e:/monitor/agent/spool.py)
- SQLite local queue DB (`spool.db`) 테이블 생성 및 입출력 제어.
- 네트워크 단절 시 수집된 메트릭을 SQLite에 저장(Buffering)하고, API 접속이 재개되면 Bulk API(`/agent/v1/metrics/bulk`)를 통해 순차 재전송하는 Failover 로직 구현.

#### [NEW] [collectors/base.py](file:///e:/monitor/agent/collectors/base.py)
- 공통 수집기 추상 베이스 클래스 정의.

#### [NEW] [collectors/common.py](file:///e:/monitor/agent/collectors/common.py)
- `psutil` 기반의 시스템 자원 수집 구현: CPU 사용률 (`CPU_USAGE_PCT`), 가용 메모리 (`MEM_AVAILABLE_BYTES`), 메모리 사용률 (`MEM_USAGE_PCT`), 디스크 가용량 (`DISK_AVAILABLE_BYTES`), 디스크 사용률 (`DISK_USAGE_PCT`) 등.

#### [NEW] [collectors/windows.py](file:///e:/monitor/agent/collectors/windows.py)
- Windows 서비스 상태 감시 및 이벤트 로그 수집 관련 스텁/윈도우 환경 전용 수집 로직 작성.

#### [NEW] [collectors/linux.py](file:///e:/monitor/agent/collectors/linux.py)
- Linux 서비스(`systemd`) 수집 관련 스텁 작성.

#### [NEW] [agent.py](file:///e:/monitor/agent/agent.py)
- 메인 루프 실행 엔진: 최초 기동 시 `/enroll`을 통해 인증받은 후, 지정된 주기(예: 30초)마다 수집기를 돌려 데이터를 확보하고, 중앙 서버에 Bulk 전송 시도. 실패 시 Spool에 백업.

---

### [NEW] Backend Worker & Scheduler Component (Phase 2)
백엔드 연동 비동기 처리 및 주기 배치 처리를 담당하는 서비스를 구현합니다.

#### [NEW] [worker.py](file:///e:/monitor/backend/app/worker.py)
- **임계치 검사 엔진**: 수집 이력(`mon_metric_hist`) 또는 최신값(`mon_metric_curr`)과 이벤트 룰 정의(`mon_event_rule`)를 비교하여 임계값 초과 시 `mon_event` 테이블에 이벤트를 자동으로 개설(`status_code='OPEN'`)하고, 정상 범위 복귀 시 자동으로 닫기(`status_code='CLOSED'`) 처리를 진행합니다.

#### [NEW] [scheduler.py](file:///e:/monitor/backend/app/scheduler.py)
- **Agent 미수신 감지**: `mon_agent_status_curr` 테이블을 검사하여 최종 하트비트 시각이 2분을 경과한 에이전트를 감지해 연결 끊김 이벤트를 생성합니다.

---

## Verification Plan

### Automated & Manual Tests
1. **API 승인 로직 테스트**:
   - `/agent/v1/enroll` 호출 시 즉시 `APPROVED`로 등록되며, 승인 과정 없이 바로 `/agent/v1/heartbeat` API를 통해 200 OK 응답을 획득하는지 검증합니다.
2. **에이전트 기동 테스트**:
   - 에이전트(`agent.py`)를 가동하여 로컬 환경의 자원을 수집하고 중앙 API 서버로 주기 전송하는 로그를 모니터링합니다.
3. **로컬 스풀 검증**:
   - 중앙 API 서버를 임시 중지한 상태에서 에이전트가 로컬 SQLite(`spool.db`)에 데이터를 정상 보관하는지 확인하고, API 서버 재기동 시 일괄 전송 후 SQLite의 대기 데이터가 완전 삭제되는지 점검합니다.
4. **Worker 및 Scheduler 검증**:
   - 임계치 규칙을 넘는 더미 데이터를 밀어 넣어 `mon_event`에 이벤트가 자동 적재되는지 점검합니다.
