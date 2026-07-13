# Nexus Mon Backend API Specification

> 작성일: 2026-07-10  
> 기준 코드: `backend/app/main.py`, `backend/app/api/**`, `backend/app/schemas/**`  
> Base URL: `http://localhost:8000`

---

## 1. 개요

Nexus Mon 백엔드는 FastAPI 기반으로 구성되어 있으며 API는 크게 세 영역으로 나뉜다.

| API 그룹 | Prefix | 사용 주체 | 설명 |
|---|---|---|---|
| Agent API | `/agent/v1` | Agent Daemon | Agent 등록, 인증 기반 하트비트/지표 수신, 수집 설정 제공 |
| Web API | `/api/v1` | Vue Frontend | 대시보드, 서버, Agent, 이벤트, 인시던트 조회/조작 |
| Admin API | `/api/v1/admin` | 관리자 UI/운영 도구 | 로그인, 사용자 관리, 공통 코드 조회 |

---

## 2. 공통 규약

### 2.1 Content-Type

JSON 요청:

```http
Content-Type: application/json
```

관리자 로그인:

```http
Content-Type: application/x-www-form-urlencoded
```

### 2.2 날짜/시간 형식

요청 및 응답의 날짜/시간은 ISO 8601 문자열을 사용한다.

예:

```text
2026-07-10T02:24:41.530546
2026-07-10T02:24:41.530546+00:00
```

### 2.3 공통 성공 응답 패턴

대부분의 Agent/Web API는 다음 구조를 사용한다.

```json
{
  "success": true,
  "data": {}
}
```

일부 처리성 API는 다음 구조를 사용한다.

```json
{
  "success": true,
  "message": "..."
}
```

Admin CRUD API는 다음 구조를 사용한다.

```json
{
  "success": true,
  "code": "UPDATED",
  "message": "...",
  "data": {}
}
```

### 2.4 공통 오류 응답

FastAPI 기본 오류 형식을 사용한다.

```json
{
  "detail": "Error message"
}
```

Agent API의 일부 서버 오류는 다음처럼 상세 객체를 반환한다.

```json
{
  "detail": {
    "success": false,
    "code": "METRICS_FAILED",
    "message": "..."
  }
}
```

### 2.5 주요 HTTP 상태 코드

| Status | 의미 |
|---|---|
| `200 OK` | 요청 성공 |
| `201 Created` | 리소스 생성 성공 |
| `400 Bad Request` | 잘못된 요청 또는 중복 데이터 |
| `401 Unauthorized` | 인증 실패 |
| `403 Forbidden` | 권한 없음 또는 비활성 계정/Agent |
| `404 Not Found` | 대상 리소스 없음 |
| `422 Unprocessable Entity` | 요청 body/query/path 검증 실패 |
| `500 Internal Server Error` | 서버 처리 중 오류 |

---

## 3. 인증 방식

### 3.1 Agent API 인증

Agent 등록 API를 제외한 Agent API는 `X-Agent-Uid` 헤더를 사용한다.

```http
X-Agent-Uid: {agent_uid}
```

검증 규칙:

1. `mon_agent.agent_uid`와 일치하는 Agent를 조회한다.
2. Agent가 없으면 `401 Unauthorized`.
3. Agent의 `status_code`가 `APPROVED`가 아니면 `403 Forbidden`.
4. 인증 성공 시 해당 Agent 기준으로 heartbeat/metrics/config를 처리한다.

### 3.2 Admin API 인증

관리자 로그인 후 JWT Bearer Token을 사용한다.

```http
Authorization: Bearer {access_token}
```

적용 대상:

- `/api/v1/admin/users/*`
- `/api/v1/admin/codes/*`

미적용:

- `/api/v1/admin/auth/login`

### 3.3 Web API 인증

현재 구현 기준 `/api/v1/dashboard`, `/api/v1/servers`, `/api/v1/agents`, `/api/v1/events`, `/api/v1/incidents`는 JWT 의존성이 적용되어 있지 않다. 운영 배포 전 접근 제어 정책을 확정해야 한다.

---

## 4. Agent API

Prefix:

```text
/agent/v1
```

### 4.1 Agent 최초 등록

```http
POST /agent/v1/enroll
```

Agent가 최초 실행될 때 서버와 Agent 정보를 등록한다. 동일한 `host_name + mgmt_ip` 서버가 이미 있으면 기존 서버를 재사용/갱신하고 Agent를 연결 또는 갱신한다.

인증: 없음

#### Request Body

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---:|:---:|---|---|
| `host_name` | string | Y | max 255 | 호스트명 |
| `os_type_code` | string | Y | max 30 | OS 유형 코드. 예: `WINDOWS`, `LINUX` |
| `os_name` | string | N | max 100 | OS 이름 |
| `os_version` | string | N | max 100 | OS 버전 |
| `mgmt_ip` | string | Y | max 45 | 관리 IP |
| `service_ip` | string | N | max 45 | 서비스 IP |
| `agent_version` | string | N | max 50 | Agent 버전 |
| `install_path` | string | N | max 500 | 설치 경로 |
| `run_account` | string | N | max 100 | 실행 계정 |

#### Request Example

```json
{
  "host_name": "DESKTOP-O8UT0PU",
  "os_type_code": "WINDOWS",
  "os_name": "Windows",
  "os_version": "10.0.19045",
  "mgmt_ip": "127.0.0.1",
  "service_ip": "127.0.0.1",
  "agent_version": "1.0.0",
  "install_path": "E:\\monitor",
  "run_account": "HODI"
}
```

#### Success Response

Status: `201 Created`

```json
{
  "success": true,
  "code": "ENROLLED",
  "message": "Agent enrolled",
  "data": {
    "agent_uid": "c1b3ae12-7b42-45d3-b016-3312a73c9bcc",
    "server_uid": "d284f876-5d68-42db-9ac7-03be5733672a",
    "server_id": 1,
    "agent_id": 1,
    "status_code": "APPROVED"
  }
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `422` | 필수 필드 누락 또는 길이 제한 위반 |
| `500` | DB 저장 중 오류 |

---

### 4.2 Agent 하트비트 수신

```http
POST /agent/v1/heartbeat
```

Agent 생존 상태와 로컬 스풀 대기 건수를 수신한다.

인증: `X-Agent-Uid`

#### Headers

```http
X-Agent-Uid: {agent_uid}
Content-Type: application/json
```

#### Request Body

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---:|:---:|---|---|
| `agent_version` | string | N | null | Agent 버전 |
| `local_queue_count` | integer | N | 0 | Agent 로컬 스풀 대기 건수. 0 이상 |
| `collector_statuses` | object | N | null | Collector별 상태 |

#### Request Example

```json
{
  "agent_version": "1.0.0",
  "local_queue_count": 0,
  "collector_statuses": null
}
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "OK",
  "message": "Heartbeat received"
}
```

#### Side Effects

- `mon_agent_heartbeat_hist`에 하트비트 이력 저장
- `mon_agent_status_curr`를 `NORMAL` 상태로 갱신
- `mon_agent.last_connected_at`, `updated_at`, `agent_version` 갱신

#### Error Responses

| Status | 조건 |
|---|---|
| `401` | `X-Agent-Uid`가 없거나 등록된 Agent가 없음 |
| `403` | Agent 상태가 `APPROVED`가 아님 |
| `422` | `local_queue_count`가 음수 등 body 검증 실패 |
| `500` | DB 저장 중 오류 |

---

### 4.3 지표 Bulk 수신

```http
POST /agent/v1/metrics/bulk
```

Agent가 수집한 CPU/MEM/DISK/NET 등의 지표를 batch 단위로 전송한다.

인증: `X-Agent-Uid`

#### Headers

```http
X-Agent-Uid: {agent_uid}
Content-Type: application/json
```

#### Request Body

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---:|:---:|---|---|
| `batch_uid` | string | Y | max 40 | 배치 고유 ID |
| `sequence` | integer | Y | >= 0 | 배치 시퀀스 |
| `collected_at` | datetime | Y | ISO 8601 | 배치 수집 시각 |
| `items` | array | Y | min 1 | 지표 목록 |

#### Metric Item

| 필드 | 타입 | 필수 | 제약/기본값 | 설명 |
|---|---:|:---:|---|---|
| `metric_code` | string | Y | max 60 | 지표 코드 |
| `dimension_key` | string | N | default `-`, max 60 | 차원 키 |
| `dimension_value` | string | N | default `-`, max 200 | 차원 값 |
| `metric_value` | number | N | null | 숫자 지표 값 |
| `string_value` | string | N | max 1000 | 문자열 지표 값 |
| `status_code` | string | N | max 30 | 지표 상태 |
| `quality_code` | string | N | max 30 | 품질 코드 |
| `collected_at` | datetime | Y | ISO 8601 | 개별 지표 수집 시각 |

#### Request Example

```json
{
  "batch_uid": "6aee86cf-d714-459f-9711-f4bb725d0400",
  "sequence": 0,
  "collected_at": "2026-07-10T02:24:41.530546+00:00",
  "items": [
    {
      "metric_code": "CPU_USAGE_PCT",
      "dimension_key": "-",
      "dimension_value": "-",
      "metric_value": 48.8,
      "string_value": null,
      "status_code": "OK",
      "quality_code": "GOOD",
      "collected_at": "2026-07-10T02:24:41.530546+00:00"
    },
    {
      "metric_code": "MEM_USAGE_PCT",
      "dimension_key": "-",
      "dimension_value": "-",
      "metric_value": 58.3,
      "string_value": null,
      "status_code": "OK",
      "quality_code": "GOOD",
      "collected_at": "2026-07-10T02:24:41.530546+00:00"
    }
  ]
}
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "OK",
  "message": "Metrics received",
  "received_count": 2
}
```

#### Processing Rules

1. Agent 인증을 먼저 수행한다.
2. 동일 batch 안에서 같은 현재값 키가 중복되면 최신 `collected_at` 값만 사용한다.
   - 중복 판단 키: `metric_code + dimension_key + dimension_value`
3. `mon_metric_curr`에 현재값을 UPSERT한다.
4. `mon_agent.last_connected_at`, `updated_at`을 갱신한다.
5. 현재 구현에서는 `mon_metric_hist` INSERT가 임시 비활성화되어 있다.

#### Error Responses

| Status | 조건 |
|---|---|
| `401` | Agent 인증 실패 |
| `403` | Agent 승인 상태 아님 |
| `422` | `items` 빈 배열, 필수 필드 누락, 타입 오류 |
| `500` | DB 저장 중 오류 |

---

### 4.4 Agent 수집 설정 조회

```http
GET /agent/v1/config
```

Agent가 수집 주기와 활성 collector 정보를 조회한다.

인증: `X-Agent-Uid`

#### Headers

```http
X-Agent-Uid: {agent_uid}
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "OK",
  "data": {
    "collect_interval_sec": 30,
    "heartbeat_interval_sec": 60,
    "metrics_batch_size": 100,
    "enabled_collectors": [
      "cpu",
      "memory",
      "disk",
      "network",
      "process"
    ]
  }
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `401` | Agent 인증 실패 |
| `403` | Agent 승인 상태 아님 |

---

## 5. Web API

Prefix:

```text
/api/v1
```

현재 구현 기준 Web API는 별도 JWT 의존성이 없다.

### 5.1 Dashboard Summary 조회

```http
GET /api/v1/dashboard/summary
```

대시보드 KPI 요약을 조회한다.

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": {
    "total_servers": 1,
    "normal": 0,
    "warning": 0,
    "critical": 0,
    "unknown": 1,
    "total_agents": 1,
    "online_agents": 1,
    "open_events": 0
  }
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---:|---|
| `total_servers` | integer | 사용 중인 서버 수 |
| `normal` | integer | NORMAL 상태 서버 수 |
| `warning` | integer | WARNING 상태 서버 수 |
| `critical` | integer | CRITICAL 상태 서버 수 |
| `unknown` | integer | UNKNOWN 상태 서버 수 |
| `total_agents` | integer | 전체 Agent 수 |
| `online_agents` | integer | `agent_status = NORMAL` Agent 수 |
| `open_events` | integer | OPEN 이벤트 수 |

---

### 5.2 서버 목록 조회

```http
GET /api/v1/servers
```

사용 중인 서버 목록과 종합 상태를 조회한다.

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "server_id": 1,
      "server_uid": "d284f876-5d68-42db-9ac7-03be5733672a",
      "server_name": "DESKTOP-O8UT0PU",
      "host_name": "DESKTOP-O8UT0PU",
      "mgmt_ip": "127.0.0.1",
      "os_type_code": "WINDOWS",
      "composite_status": "UNKNOWN"
    }
  ]
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---:|---|
| `server_id` | integer | 서버 PK |
| `server_uid` | string | 서버 고유 UID |
| `server_name` | string | 서버명 |
| `host_name` | string | 호스트명 |
| `mgmt_ip` | string | 관리 IP |
| `os_type_code` | string | OS 유형 코드 |
| `composite_status` | string | 서버 종합 상태. 상태가 없으면 `UNKNOWN` |

---

### 5.3 서버 상세 조회

```http
GET /api/v1/servers/{server_id}
```

서버 기본 정보와 최신 현재 지표 목록을 조회한다.

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `server_id` | integer | Y | 서버 ID |

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": {
    "server_id": 1,
    "server_name": "DESKTOP-O8UT0PU",
    "host_name": "DESKTOP-O8UT0PU",
    "mgmt_ip": "127.0.0.1",
    "os_type_code": "WINDOWS",
    "os_name": "Windows",
    "os_version": "10.0.19045",
    "metrics": [
      {
        "metric_code": "CPU_USAGE_PCT",
        "dimension_key": "-",
        "dimension_value": "-",
        "metric_value": 48.8,
        "collected_at": "2026-07-10T02:24:41.530546"
      },
      {
        "metric_code": "MEM_USAGE_PCT",
        "dimension_key": "-",
        "dimension_value": "-",
        "metric_value": 58.3,
        "collected_at": "2026-07-10T02:24:41.530546"
      }
    ]
  }
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | 서버가 존재하지 않음 |
| `422` | `server_id` 타입 오류 |

---

### 5.4 Agent 목록 조회

```http
GET /api/v1/agents
```

Agent 목록과 현재 상태, 연결 서버 정보를 조회한다.

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "agent_id": 1,
      "agent_uid": "c1b3ae12-7b42-45d3-b016-3312a73c9bcc",
      "server_id": 1,
      "host_name": "DESKTOP-O8UT0PU",
      "mgmt_ip": "127.0.0.1",
      "status_code": "APPROVED",
      "agent_version": "1.0.0",
      "agent_status": "NORMAL",
      "last_heartbeat_at": "2026-07-10T02:18:27.898546"
    }
  ]
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---:|---|
| `agent_id` | integer | Agent PK |
| `agent_uid` | string | Agent 인증 UID |
| `server_id` | integer | 연결 서버 ID |
| `host_name` | string/null | 서버 호스트명 |
| `mgmt_ip` | string/null | 서버 관리 IP |
| `status_code` | string | Agent 승인 상태. 예: `APPROVED`, `REVOKED` |
| `agent_version` | string/null | Agent 버전 |
| `agent_status` | string | 현재 Agent 상태. 상태가 없으면 `UNKNOWN` |
| `last_heartbeat_at` | string/null | 마지막 하트비트 시각 |

---

### 5.5 Agent 승인

```http
PUT /api/v1/agents/{agent_id}/approve
```

Agent 상태를 `APPROVED`로 변경한다.

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `agent_id` | integer | Y | Agent ID |

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "message": "Agent 1 approved"
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | Agent가 존재하지 않음 |
| `422` | `agent_id` 타입 오류 |

---

### 5.6 Agent 철회

```http
PUT /api/v1/agents/{agent_id}/revoke
```

Agent 상태를 `REVOKED`로 변경한다. 이후 해당 Agent는 `X-Agent-Uid` 인증을 통과하지 못한다.

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `agent_id` | integer | Y | Agent ID |

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "message": "Agent 1 revoked"
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | Agent가 존재하지 않음 |
| `422` | `agent_id` 타입 오류 |

---

### 5.7 이벤트 목록 조회

```http
GET /api/v1/events
```

이벤트 목록을 조회한다. `status` query parameter를 사용해 상태별 필터링이 가능하다.

#### Query Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `status` | string | N | 이벤트 상태 필터. 예: `OPEN`, `CLOSED` |

#### Request Example

```http
GET /api/v1/events?status=OPEN
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "event_uid": "8b5a7c1e-2f4c-4c78-bd70-0e09f9c1b111",
      "rule_id": 1,
      "server_id": 1,
      "target_type_code": "SERVER",
      "severity_code": "WARNING",
      "status_code": "OPEN",
      "title": "[WARNING] CPU 사용률 초과",
      "message": "CPU_USAGE_PCT value is 88.2",
      "first_occurred_at": "2026-07-10T02:24:41.530546",
      "last_occurred_at": "2026-07-10T02:25:11.530546",
      "recovered_at": null,
      "occurrence_count": 2
    }
  ]
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---:|---|
| `event_uid` | string | 이벤트 UID |
| `rule_id` | integer/null | 이벤트 룰 ID |
| `server_id` | integer/null | 서버 ID |
| `target_type_code` | string | 대상 유형. 예: `SERVER`, `AGENT` |
| `severity_code` | string | 심각도. 예: `WARNING`, `CRITICAL`, `FATAL` |
| `status_code` | string | 상태. 예: `OPEN`, `CLOSED` |
| `title` | string | 이벤트 제목 |
| `message` | string | 이벤트 메시지 |
| `first_occurred_at` | string/null | 최초 발생 시각 |
| `last_occurred_at` | string/null | 마지막 발생 시각 |
| `recovered_at` | string/null | 복구 시각 |
| `occurrence_count` | integer/null | 발생 횟수 |

---

### 5.8 이벤트 ACK 처리

```http
PUT /api/v1/events/{event_uid}/ack
```

운영자가 이벤트를 확인했음을 기록한다. 이벤트 상태를 `CLOSED`로 바꾸지는 않는다.

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `event_uid` | string | Y | 이벤트 UID |

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "message": "Event 8b5a7c1e-2f4c-4c78-bd70-0e09f9c1b111 acknowledged"
}
```

#### Side Effects

- `mon_event.ack_at`을 현재 시각으로 갱신한다.

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | 이벤트가 존재하지 않음 |

---

### 5.9 인시던트 목록 조회

```http
GET /api/v1/incidents
```

장애 인시던트 목록을 조회한다.

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "incident_id": 1,
      "incident_title": "DB 장애",
      "status_code": "OPEN",
      "impact_code": "HIGH",
      "cause_code": "UNKNOWN",
      "detected_at": "2026-07-10T02:24:41.530546",
      "resolved_at": null
    }
  ]
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---:|---|
| `incident_id` | integer | 인시던트 ID |
| `incident_title` | string | 인시던트 제목 |
| `status_code` | string/null | 상태 코드 |
| `impact_code` | string/null | 영향도 코드 |
| `cause_code` | string/null | 원인 코드 |
| `detected_at` | string/null | 감지 시각 |
| `resolved_at` | string/null | 해결 시각 |

---

## 6. Admin API

Prefix:

```text
/api/v1/admin
```

### 6.1 관리자 로그인

```http
POST /api/v1/admin/auth/login
```

OAuth2 Password Form 형식으로 로그인하고 JWT access token을 발급받는다.

인증: 없음

#### Request Form

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `username` | string | Y | 로그인 ID |
| `password` | string | Y | 비밀번호 |

#### Request Example

```http
POST /api/v1/admin/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin-password
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "OK",
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user_info": {
    "user_id": 1,
    "login_id": "admin",
    "user_name": "Administrator",
    "dept_name": "OPS",
    "position_name": "Manager",
    "email": "admin@example.com"
  }
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `401` | ID/PW 불일치 |
| `403` | 비활성 계정 또는 `use_yn != Y` |
| `422` | form 필드 누락 |

---

### 6.2 관리자 사용자 생성

```http
POST /api/v1/admin/users/
```

관리자 사용자를 생성한다.

인증: `Authorization: Bearer {token}`

#### Request Body

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---:|:---:|---|---|
| `login_id` | string | Y | - | 로그인 ID |
| `user_name` | string | Y | - | 사용자명 |
| `password` | string | Y | - | 비밀번호 |
| `dept_name` | string | N | null | 부서명 |
| `position_name` | string | N | null | 직위명 |
| `email` | string | N | null | 이메일 |
| `phone` | string | N | null | 전화번호 |
| `status_code` | string | N | `ACTIVE` | 상태 코드 |
| `use_yn` | string | N | `Y` | 사용 여부 |

#### Request Example

```json
{
  "login_id": "ops01",
  "user_name": "Ops User",
  "password": "secret-password",
  "dept_name": "Operations",
  "position_name": "Engineer",
  "email": "ops01@example.com",
  "phone": "010-0000-0000",
  "status_code": "ACTIVE",
  "use_yn": "Y"
}
```

#### Success Response

Status: `201 Created`

```json
{
  "success": true,
  "code": "CREATED",
  "message": "User created",
  "data": {
    "user_id": 2
  }
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `400` | `login_id` 중복 |
| `401` | JWT 없음/유효하지 않음 |
| `403` | 비활성 사용자 |
| `422` | 요청 body 검증 실패 |

---

### 6.3 관리자 사용자 목록 조회

```http
GET /api/v1/admin/users/
```

인증: `Authorization: Bearer {token}`

#### Success Response

Status: `200 OK`

```json
[
  {
    "login_id": "admin",
    "user_name": "Administrator",
    "dept_name": "Operations",
    "position_name": "Manager",
    "email": "admin@example.com",
    "phone": "010-0000-0000",
    "status_code": "ACTIVE",
    "use_yn": "Y",
    "user_id": 1,
    "last_login_at": "2026-07-10T02:24:41.530546",
    "created_at": "2026-07-10T02:24:41.530546"
  }
]
```

---

### 6.4 관리자 사용자 상세 조회

```http
GET /api/v1/admin/users/{user_id}
```

인증: `Authorization: Bearer {token}`

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `user_id` | integer | Y | 사용자 ID |

#### Success Response

Status: `200 OK`

```json
{
  "login_id": "admin",
  "user_name": "Administrator",
  "dept_name": "Operations",
  "position_name": "Manager",
  "email": "admin@example.com",
  "phone": "010-0000-0000",
  "status_code": "ACTIVE",
  "use_yn": "Y",
  "user_id": 1,
  "last_login_at": "2026-07-10T02:24:41.530546",
  "created_at": "2026-07-10T02:24:41.530546"
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | 사용자 없음 |
| `422` | `user_id` 타입 오류 |

---

### 6.5 관리자 사용자 수정

```http
PUT /api/v1/admin/users/{user_id}
```

인증: `Authorization: Bearer {token}`

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `user_id` | integer | Y | 사용자 ID |

#### Request Body

모든 필드는 선택값이다. 전달된 필드만 수정한다.

| 필드 | 타입 | 설명 |
|---|---:|---|
| `user_name` | string | 사용자명 |
| `password` | string | 새 비밀번호 |
| `dept_name` | string | 부서명 |
| `position_name` | string | 직위명 |
| `email` | string | 이메일 |
| `phone` | string | 전화번호 |
| `status_code` | string | 상태 코드 |
| `use_yn` | string | 사용 여부 |

#### Request Example

```json
{
  "user_name": "Ops User Updated",
  "email": "ops01-updated@example.com",
  "status_code": "ACTIVE",
  "use_yn": "Y"
}
```

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "UPDATED",
  "message": "User updated",
  "data": null
}
```

#### Error Responses

| Status | 조건 |
|---|---|
| `404` | 사용자 없음 |
| `422` | 요청 body 검증 실패 |

---

### 6.6 관리자 사용자 삭제

```http
DELETE /api/v1/admin/users/{user_id}
```

실제 삭제가 아니라 사용자 비활성화 처리다.

인증: `Authorization: Bearer {token}`

#### Path Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `user_id` | integer | Y | 사용자 ID |

#### Success Response

Status: `200 OK`

```json
{
  "success": true,
  "code": "DELETED",
  "message": "User disabled",
  "data": null
}
```

#### Side Effects

- `use_yn = 'N'`
- `status_code = 'INACTIVE'`
- `updated_at`, `updated_by` 갱신

#### Error Responses

| Status | 조건 |
|---|---|
| `400` | 자기 자신 삭제 시도 |
| `404` | 사용자 없음 |

---

### 6.7 공통 코드 그룹 조회

```http
GET /api/v1/admin/codes/groups
```

인증: `Authorization: Bearer {token}`

#### Success Response

Status: `200 OK`

```json
[
  {
    "group_code": "AGENT_STATUS",
    "group_name": "Agent Status",
    "description": "Agent status code group",
    "use_yn": "Y",
    "created_at": "2026-07-10T02:24:41.530546"
  }
]
```

---

### 6.8 공통 코드 조회

```http
GET /api/v1/admin/codes/
```

인증: `Authorization: Bearer {token}`

#### Query Parameters

| 이름 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `group_code` | string | N | 특정 코드 그룹 필터 |

#### Request Example

```http
GET /api/v1/admin/codes/?group_code=AGENT_STATUS
```

#### Success Response

Status: `200 OK`

```json
[
  {
    "code": "NORMAL",
    "group_code": "AGENT_STATUS",
    "code_name": "Normal",
    "sort_order": 1,
    "description": "정상",
    "use_yn": "Y",
    "created_at": "2026-07-10T02:24:41.530546"
  }
]
```

---

## 7. Health Check

`main.py`에 직접 등록된 상태 확인 API다.

### 7.1 Health Check

```http
GET /health
```

#### Success Response

Status: `200 OK`

```json
{
  "status": "ok",
  "message": "Monitoring API is running"
}
```

---

## 8. 현재 구현상 특이사항

### 8.1 중복 라우터 파일

`backend/app/api/web/v1/dashboard.py`, `backend/app/api/web/v1/servers.py` 파일도 존재하지만 `backend/app/main.py`에는 `backend/app/api/web/v1/router.py`만 `/api/v1`에 등록되어 있다. 따라서 현재 실제 서비스 기준 명세는 `web/v1/router.py`를 기준으로 한다.

### 8.2 지표 이력 저장

`/agent/v1/metrics/bulk`는 `MetricHistory` 객체를 만들지만 `db.add(hist)`가 주석 처리되어 있다. 이유는 `mon_metric_hist` 파티션 오류(`ORA-14400`)가 현재값 저장을 롤백시키는 것을 방지하기 위해서다.

영향:

- 서버 상세 화면의 현재 지표는 정상 동작한다.
- 히스토리 기반 추세 API/차트는 별도 파티션 정비 후 활성화해야 한다.

### 8.3 Web API 접근 제어

현재 Web API는 JWT 인증 없이 호출 가능하다. 운영 환경에서는 다음 중 하나를 선택해야 한다.

- Web API에도 `get_current_user` 의존성 적용
- Reverse proxy 또는 네트워크 레벨 접근 제어
- 조회 API 공개, 조작 API만 인증 적용

### 8.4 API 문서 자동 확인

FastAPI 기본 Swagger UI는 백엔드 실행 중 다음 주소에서 확인할 수 있다.

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

---

## 9. 엔드포인트 전체 목록

| Group | Method | Path | 인증 | 설명 |
|---|---|---|---|---|
| Health | GET | `/health` | 없음 | API 상태 확인 |
| Agent | POST | `/agent/v1/enroll` | 없음 | Agent 최초 등록 |
| Agent | POST | `/agent/v1/heartbeat` | `X-Agent-Uid` | 하트비트 수신 |
| Agent | POST | `/agent/v1/metrics/bulk` | `X-Agent-Uid` | 지표 Bulk 수신 |
| Agent | GET | `/agent/v1/config` | `X-Agent-Uid` | Agent 수집 설정 조회 |
| Web | GET | `/api/v1/dashboard/summary` | 없음 | 대시보드 KPI 조회 |
| Web | GET | `/api/v1/servers` | 없음 | 서버 목록 조회 |
| Web | GET | `/api/v1/servers/{server_id}` | 없음 | 서버 상세/현재 지표 조회 |
| Web | GET | `/api/v1/agents` | 없음 | Agent 목록 조회 |
| Web | PUT | `/api/v1/agents/{agent_id}/approve` | 없음 | Agent 승인 |
| Web | PUT | `/api/v1/agents/{agent_id}/revoke` | 없음 | Agent 철회 |
| Web | GET | `/api/v1/events` | 없음 | 이벤트 목록 조회 |
| Web | PUT | `/api/v1/events/{event_uid}/ack` | 없음 | 이벤트 ACK 처리 |
| Web | GET | `/api/v1/incidents` | 없음 | 인시던트 목록 조회 |
| Admin | POST | `/api/v1/admin/auth/login` | 없음 | 관리자 로그인 |
| Admin | POST | `/api/v1/admin/users/` | Bearer JWT | 사용자 생성 |
| Admin | GET | `/api/v1/admin/users/` | Bearer JWT | 사용자 목록 조회 |
| Admin | GET | `/api/v1/admin/users/{user_id}` | Bearer JWT | 사용자 상세 조회 |
| Admin | PUT | `/api/v1/admin/users/{user_id}` | Bearer JWT | 사용자 수정 |
| Admin | DELETE | `/api/v1/admin/users/{user_id}` | Bearer JWT | 사용자 비활성화 |
| Admin | GET | `/api/v1/admin/codes/groups` | Bearer JWT | 공통 코드 그룹 조회 |
| Admin | GET | `/api/v1/admin/codes/` | Bearer JWT | 공통 코드 조회 |
