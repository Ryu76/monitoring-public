# Agent 서버 등록 및 인증 API 구현 계획서

현재 스켈레톤 코드로만 존재하는 Agent 연동 API(등록 및 인증)를 실제 DB와 연동하여 동작하도록 구현합니다.

## User Review Required
> [!IMPORTANT]
> Agent가 자신을 증명하기 위한 인증 방식으로 **`X-Agent-Uid` HTTP 헤더**를 사용하려고 합니다. 발급된 `agent_uid`를 해당 헤더에 담아 전송하면, 중앙 서버가 DB(`mon_agent`)에서 해당 UID와 상태(`status_code`)를 확인하여 데이터 수신 여부를 결정합니다. 이 방식에 동의하시는지 확인 부탁드립니다.

## Open Questions
> [!NOTE]
> 서버 등록 시 동일한 `host_name`과 `mgmt_ip`를 가진 서버가 이미 존재한다면, 에러를 반환할까요 아니면 기존 서버에 Agent 정보만 새로 연결(또는 업데이트)하도록 할까요? 본 계획에서는 **새로운 Server 레코드를 무조건 생성**하는 것으로 초안을 잡았으나, 원하시는 정책이 있다면 알려주세요.
> 
> *사용자 피드백 반영: 동일 서버(host_name + mgmt_ip) 존재 시, 신규 생성하지 않고 에이전트 정보를 연결 및 업데이트하도록 반영 완료.*

## Proposed Changes

### [NEW] [agent.py](../backend/app/schemas/agent.py)
Agent 요청 및 응답을 검증할 Pydantic 스키마를 신규 작성합니다.
- `AgentEnrollRequest`: `host_name`, `os_type_code`, `mgmt_ip`, `agent_version`, `install_path`, `run_account` 필드 포함.
- `AgentEnrollResponse`: `agent_uid`, `server_uid`, `status_code` 반환.

### [MODIFY] [dependencies.py](../backend/app/api/dependencies.py)
Agent 전용 인증 의존성 함수(`verify_agent`)를 추가합니다.
- `Header(alias="X-Agent-Uid")` 값을 읽어 DB의 `mon_agent` 테이블에서 조회합니다.
- Agent가 존재하지 않거나, `status_code`가 `'APPROVED'`(승인됨)가 아닌 경우 `401 Unauthorized` 또는 `403 Forbidden` 예외를 발생시킵니다.

### [MODIFY] [router.py](../backend/app/api/agent/v1/router.py)
실제 DB 연동 로직을 구현하고 인증을 적용합니다.
- `POST /enroll`: 
  - 전달받은 정보를 바탕으로 `mon_server` 테이블에 신규 서버를 Insert 합니다 (`server_name`은 `host_name` 사용, `server_uid`는 UUID 생성).
  - 동일 서버 존재 시 기존 서버 및 기존 에이전트 정보를 갱신하고 `agent_uid`를 재발급합니다.
  - `mon_agent` 테이블에 에이전트를 Insert 합니다 (`agent_uid` UUID 생성, `status_code='PENDING'`).
  - 생성된 UID들을 반환합니다.
- `POST /heartbeat`, `POST /metrics/bulk`, `GET /config`:
  - `Depends(verify_agent)`를 추가하여 승인된 Agent만 접근할 수 있도록 보안을 강화합니다.

## Verification Plan
1. Swagger UI(`/docs`)를 통해 `/agent/v1/enroll` API에 더미 데이터를 전송하여 정상적으로 UUID가 발급되고 DB에 저장되는지 확인합니다.
2. 발급받은 `agent_uid`를 헤더에 포함하지 않고 `/agent/v1/heartbeat` 호출 시 `401/403` 에러가 발생하는지 확인합니다.
3. DB에서 해당 Agent의 `status_code` to `'APPROVED'`로 변경한 뒤 정상적으로 통신이 성공하는지 검증합니다.
