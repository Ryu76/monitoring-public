# Nexus Mon — 통합 서버 모니터링 관제 시스템 전체 구현 보고서

> 최종 갱신: 2026-07-08

---

## 📑 목차

1. [프로젝트 전체 구조](#프로젝트-전체-구조)
2. [Phase 0 — 백엔드 API 기반](#phase-0--백엔드-api-기반-기-구현)
3. [Phase 1 — 에이전트 데몬](#phase-1--에이전트-데몬-수집기)
4. [Phase 2 — Worker & Scheduler](#phase-2--비동기-워커--스케줄러)
5. [Phase 3 — 관리자 포털 및 JWT 인증](#phase-3--관리자-포털-및-jwt-인증)
6. [Phase 4 — Web 관제 프론트엔드](#phase-4--web-관제-프론트엔드-vue-3)
7. [Phase 5 — 풀스택 통합 및 빌드 검증](#phase-5--풀스택-통합)
8. [구동 방법](#구동-방법)
9. [향후 작업](#향후-작업)

---

## 프로젝트 전체 구조

```
e:\monitor\
├── agent/                          # Phase 1: 수집 데몬
│   ├── agent.py                    # 메인 루프 (Enroll→Heartbeat→Collect)
│   ├── config.py                   # 에이전트 설정
│   ├── spool.py                    # SQLite 기반 Failover 큐
│   └── collectors/
│       ├── base.py                 # 추상 수집기
│       ├── common.py               # psutil CPU/MEM/DISK/NET 수집
│       ├── windows.py              # Windows 확장 스텁
│       └── linux.py                # Linux 확장 스텁
│
├── backend/                        # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py                 # 앱 진입점 + CORS + lifespan(워커 통합)
│   │   ├── worker.py               # Phase 2: 임계치 검사 엔진
│   │   ├── scheduler.py            # Phase 2: Agent 미수신 감지
│   │   ├── alert_worker.py         # Phase 2: 알림 처리기
│   │   ├── aggregator.py           # Phase 2: 시계열 집계기
│   │   ├── core/
│   │   │   ├── config.py           # DB/JWT 설정
│   │   │   ├── database.py         # SQLAlchemy 세션
│   │   │   ├── security.py         # Phase 3: bcrypt 해싱 + JWT 생성
│   │   │   └── audit.py            # Phase 3: 감사 로그 데코레이터
│   │   ├── models/
│   │   │   ├── server.py           # MON_SERVER, MON_SERVER_STATUS_CURR
│   │   │   ├── agent.py            # MON_AGENT, MON_AGENT_STATUS_CURR
│   │   │   ├── resource.py         # MON_METRIC_CURR, MON_METRIC_HIST
│   │   │   ├── event.py            # MON_EVENT, MON_EVENT_RULE, MON_INCIDENT
│   │   │   └── system.py           # SYS_USER, SYS_ROLE, SYS_CODE, SYS_AUDIT_LOG
│   │   ├── schemas/
│   │   │   ├── agent.py            # Agent API 스키마
│   │   │   └── admin.py            # Phase 3: 로그인/사용자/코드 스키마
│   │   └── api/
│   │       ├── dependencies.py     # verify_agent + get_current_user(JWT)
│   │       ├── agent/v1/router.py  # Agent 엔드포인트 (enroll/heartbeat/metrics/config)
│   │       ├── web/v1/router.py    # Phase 5: 통합 Web API (dashboard/servers/agents/events)
│   │       └── admin/v1/
│   │           ├── auth.py         # Phase 3: POST /login (JWT 발급)
│   │           ├── users.py        # Phase 3: Full CRUD (GET/POST/PUT/DELETE)
│   │           └── codes.py        # Phase 3: 공통코드 조회
│   └── requirements.txt
│
├── frontend/                       # Phase 4: Vue 3 + TypeScript SPA
│   ├── index.html                  # SEO 메타 + Google Fonts (Inter)
│   ├── vite.config.ts              # Phase 5: Vite Proxy 설정
│   └── src/
│       ├── main.ts                 # Vue 앱 초기화 + Router 등록
│       ├── api.ts                  # Phase 5: Axios 클라이언트 (JWT 인터셉터)
│       ├── style.css               # Glassmorphism + Dark Mode + Animations
│       ├── router/index.ts         # SPA 라우팅 + 인증 Guard
│       └── components/
│           ├── Login.vue           # Phase 5: JWT 로그인 화면
│           ├── Dashboard.vue       # Phase 5: KPI 카드 + 이벤트 테이블 (API 연동)
│           ├── ServerDetail.vue    # Phase 5: ECharts Gauge/Bar + 지표 테이블 (API 연동)
│           ├── AgentList.vue       # Phase 5: Approve/Revoke 실제 API 호출
│           └── EventList.vue       # Phase 5: 이벤트 OPEN/CLOSED 필터 + ACK
│
├── doc/
│   ├── walkthrough.md              # ← 이 문서
│   └── task.md
├── db/                             # DDL 스크립트
├── project_status_and_roadmap.md   # 로드맵
└── .env                            # 환경변수
```

---

## Phase 0 — 백엔드 API 기반 (기 구현)

이 프로젝트의 첫 번째 세션에서 구축된 백엔드 기반입니다.

### 구현 내역
| 파일 | 역할 |
|---|---|
| [main.py](file:///e:/monitor/backend/app/main.py) | FastAPI 앱 진입점, 라우터 등록 |
| [config.py](file:///e:/monitor/backend/app/core/config.py) | Oracle DB 접속 정보, JWT 시크릿, 만료 시간 |
| [database.py](file:///e:/monitor/backend/app/core/database.py) | SQLAlchemy 엔진 및 세션 팩토리 |
| [dependencies.py](file:///e:/monitor/backend/app/api/dependencies.py) | `get_db`, `verify_agent` 인증 의존성 |
| [agent/v1/router.py](file:///e:/monitor/backend/app/api/agent/v1/router.py) | enroll / heartbeat / metrics/bulk / config 엔드포인트 |
| models/*.py | Server, Agent, MetricCurrent, MetricHistory, Event, SysUser 등 ORM |

### Agent API 엔드포인트

| 엔드포인트 | 메서드 | 인증 | 동작 |
|---|---|---|---|
| `/agent/v1/enroll` | POST | ❌ | 서버+에이전트 등록 (중복 시 기존 재사용) |
| `/agent/v1/heartbeat` | POST | ✅ `X-Agent-Uid` | 하트비트 이력 저장 + 상태 갱신 |
| `/agent/v1/metrics/bulk` | POST | ✅ `X-Agent-Uid` | 지표 현재값 UPSERT + 이력 INSERT |
| `/agent/v1/config` | GET | ✅ `X-Agent-Uid` | 수집 설정 반환 |

### 검증 결과
SQLite 인메모리 테스트 환경에서 4가지 시나리오(신규등록, 재등록, 인증 미들웨어) 모두 통과:
```
Ran 4 tests in 0.691s — OK
```

---

## Phase 1 — 에이전트 데몬 수집기

### 구현 파일
| 파일 | 역할 |
|---|---|
| [agent.py](file:///e:/monitor/agent/agent.py) | 메인 루프: Enroll → Heartbeat(60s) → Collect+Send(30s) |
| [config.py](file:///e:/monitor/agent/config.py) | API 주소, 수집/하트비트 주기, UID 파일 경로 |
| [spool.py](file:///e:/monitor/agent/spool.py) | SQLite 기반 로컬 큐잉 (네트워크 단절 시 Failover) |
| [collectors/base.py](file:///e:/monitor/agent/collectors/base.py) | 추상 수집기 인터페이스 |
| [collectors/common.py](file:///e:/monitor/agent/collectors/common.py) | `psutil`로 CPU, 메모리, 디스크, 네트워크 수집 |

### 동작 흐름
```
1. 최초 기동 → /enroll API 호출 → agent_uid, server_uid 파일로 저장
2. 60초마다 → /heartbeat 전송 (생존 알림)
3. 30초마다 → psutil 수집 → spool.db에 임시 저장 → /metrics/bulk로 전송
4. 전송 실패 시 → spool에 보존 → 다음 주기에 일괄 재전송
```

---

## Phase 2 — 비동기 워커 & 스케줄러

`APScheduler`의 `BackgroundScheduler`를 사용하여 4개의 독립형 백그라운드 작업을 구현했습니다.

### 구현 파일
| 파일 | 주기 | 역할 |
|---|---|---|
| [worker.py](file:///e:/monitor/backend/app/worker.py) | 30초 | `mon_event_rule` 임계치 검사 → 이벤트 발생/복구 |
| [scheduler.py](file:///e:/monitor/backend/app/scheduler.py) | 1분 | Agent 하트비트 미수신(2분 초과) 감지 → OFFLINE 이벤트 |
| [alert_worker.py](file:///e:/monitor/backend/app/alert_worker.py) | 30초 | `mon_alert_policy` 기반 알림 발송 처리 |
| [aggregator.py](file:///e:/monitor/backend/app/aggregator.py) | 5분 | `mon_metric_curr` → `mon_metric_hist` 아카이빙 |

### 이벤트 판정 로직 (worker.py)
```
1. mon_event_rule 중 use_yn='Y'인 룰 조회
2. mon_metric_curr 스캔하여 각 룰의 compare_op과 threshold 비교
3. Fatal > Critical > Warning 순으로 심각도 결정
4. 기존 OPEN 이벤트가 있으면 → occurrence_count 증가 + 심각도 갱신
5. 없으면 → 신규 mon_event(OPEN) 생성
6. 정상 범위 복귀 시 → recover_threshold 확인 후 CLOSED 처리
```

### 통합 구동
`main.py`의 `lifespan` 이벤트를 통해 FastAPI 앱 기동 시 4개 워커가 자동 시작됩니다.

---

## Phase 3 — 관리자 포털 및 JWT 인증

### 구현 파일
| 파일 | 역할 |
|---|---|
| [security.py](file:///e:/monitor/backend/app/core/security.py) | `passlib(bcrypt)` 해싱, `PyJWT` 토큰 생성/검증 |
| [audit.py](file:///e:/monitor/backend/app/core/audit.py) | `@audit_log` 데코레이터 → `SYS_AUDIT_LOG` 자동 기록 |
| [schemas/admin.py](file:///e:/monitor/backend/app/schemas/admin.py) | LoginRequest, TokenResponse, UserCreate/Update/Response, CodeResponse |
| [auth.py](file:///e:/monitor/backend/app/api/admin/v1/auth.py) | `POST /api/v1/admin/auth/login` — JWT 발급 |
| [users.py](file:///e:/monitor/backend/app/api/admin/v1/users.py) | SysUser Full CRUD (GET list/detail, POST, PUT, DELETE) |
| [codes.py](file:///e:/monitor/backend/app/api/admin/v1/codes.py) | 공통코드 그룹/상세 조회 |
| [dependencies.py](file:///e:/monitor/backend/app/api/dependencies.py) | `get_current_user` JWT 의존성 추가 |

### Admin API 엔드포인트

| 엔드포인트 | 메서드 | 인증 | 동작 |
|---|---|---|---|
| `/api/v1/admin/auth/login` | POST | ❌ | ID/PW 검증 → JWT 발급 |
| `/api/v1/admin/users/` | GET | ✅ JWT | 사용자 목록 조회 |
| `/api/v1/admin/users/{id}` | GET | ✅ JWT | 사용자 상세 조회 |
| `/api/v1/admin/users/` | POST | ✅ JWT | 사용자 등록 (bcrypt 해싱) |
| `/api/v1/admin/users/{id}` | PUT | ✅ JWT | 사용자 정보 수정 |
| `/api/v1/admin/users/{id}` | DELETE | ✅ JWT | 사용자 논리 삭제 (비활성화) |
| `/api/v1/admin/codes/groups` | GET | ✅ JWT | 코드 그룹 목록 |
| `/api/v1/admin/codes/` | GET | ✅ JWT | 코드 상세 (group_code 필터) |

---

## Phase 4 — Web 관제 프론트엔드 (Vue 3)

### 기술 스택
- **Vue 3** + **TypeScript** + **Vite**
- **vue-router**: SPA 라우팅 + 인증 Guard
- **axios**: JWT 인터셉터 + 401 자동 로그아웃
- **ECharts** (`vue-echarts`): Gauge, Bar, Line 차트
- **lucide-vue-next**: 아이콘 패키지
- **Google Fonts (Inter)**: 프리미엄 타이포그래피

### UI/UX 디자인 특징
- **Glassmorphism**: `backdrop-filter: blur(12px)` + 반투명 카드
- **Dark Mode**: `#0f172a` 배경 + `radial-gradient` 조명 효과
- **Micro-Animations**: `fadeIn` + 카드 호버(translateY + shadow 변화)
- **Status Badges**: NORMAL(초록), WARNING(노랑), FATAL(빨강) 컬러 체계

### 구현 화면 (컴포넌트)

| 화면 | 파일 | 기능 |
|---|---|---|
| **로그인** | [Login.vue](file:///e:/monitor/frontend/src/components/Login.vue) | ID/PW → JWT 발급 → localStorage 저장 |
| **대시보드** | [Dashboard.vue](file:///e:/monitor/frontend/src/components/Dashboard.vue) | KPI 카드(서버수, 에이전트수, 장애건수) + 최근 이벤트 테이블 |
| **서버 상세** | [ServerDetail.vue](file:///e:/monitor/frontend/src/components/ServerDetail.vue) | 서버 선택 → CPU/MEM Gauge 차트 + Disk Bar 차트 + 전체 지표 테이블 |
| **에이전트 관리** | [AgentList.vue](file:///e:/monitor/frontend/src/components/AgentList.vue) | 에이전트 목록 + Approve/Revoke 버튼 (실제 PUT API 호출) |
| **이벤트 관리** | [EventList.vue](file:///e:/monitor/frontend/src/components/EventList.vue) | OPEN/CLOSED/ALL 필터 + ACK(확인처리) 버튼 |

### 라우팅 구조
```
/login      → Login.vue       (사이드바 없음, 전체 화면)
/           → Dashboard.vue   (사이드바 포함)
/servers    → ServerDetail.vue
/agents     → AgentList.vue
/events     → EventList.vue
```

---

## Phase 5 — 풀스택 통합

Phase 4에서 만든 프론트엔드 컴포넌트들이 하드코딩 상태였기 때문에, **실제 백엔드 API와 완전히 연동**하는 작업을 수행했습니다.

### 백엔드 보강
| 변경 | 설명 |
|---|---|
| [main.py](file:///e:/monitor/backend/app/main.py) | CORS 미들웨어 추가 + `lifespan`으로 4개 워커 자동 구동 |
| [web/v1/router.py](file:///e:/monitor/backend/app/api/web/v1/router.py) | 통합 Web API 전면 재작성 (dashboard/servers/agents/events) |
| [requirements.txt](file:///e:/monitor/backend/requirements.txt) | PyJWT, passlib, bcrypt, APScheduler 추가 |

### Web API 엔드포인트 (신규/재작성)

| 엔드포인트 | 메서드 | 동작 |
|---|---|---|
| `/api/v1/dashboard/summary` | GET | 서버/에이전트/이벤트 통합 KPI |
| `/api/v1/servers` | GET | 서버 목록 + 종합 상태 |
| `/api/v1/servers/{id}` | GET | 서버 상세 + 현재 지표 목록 |
| `/api/v1/agents` | GET | 에이전트 목록 + 하트비트 상태 |
| `/api/v1/agents/{id}/approve` | PUT | 에이전트 승인 |
| `/api/v1/agents/{id}/revoke` | PUT | 에이전트 차단 |
| `/api/v1/events` | GET | 이벤트 목록 (status 필터) |
| `/api/v1/events/{uid}/ack` | PUT | 이벤트 확인(ACK) 처리 |

### 프론트엔드 보강
| 변경 | 설명 |
|---|---|
| [api.ts](file:///e:/monitor/frontend/src/api.ts) | Axios 클라이언트 + JWT 자동 첨부 인터셉터 + 401 자동 로그아웃 |
| [vite.config.ts](file:///e:/monitor/frontend/vite.config.ts) | `/api`, `/agent`, `/health` 프록시 설정 |
| [index.html](file:///e:/monitor/frontend/index.html) | SEO 메타 태그 + Google Fonts (Inter) |
| [App.vue](file:///e:/monitor/frontend/src/App.vue) | 로그인 화면 레이아웃 분리 + 사용자 정보 표시 + 로그아웃 + Events 메뉴 추가 |
| [router/index.ts](file:///e:/monitor/frontend/src/router/index.ts) | Login/Events 경로 추가 + `beforeEach` 인증 Guard |
| 모든 .vue 컴포넌트 | 하드코딩 → `api.get/put` 실제 API 호출로 전면 교체 |

### 빌드 검증
```bash
> npm run build
✓ 2395 modules transformed.
✓ built in 5.89s — 성공
```

---

## 구동 방법

### 1. 백엔드 API 서버 (워커 포함 자동 시작)
```powershell
cd e:\monitor\backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
> main.py의 lifespan에 의해 worker, scheduler, alert_worker, aggregator가 자동 구동됩니다.

### 2. 프론트엔드 개발 서버
```powershell
cd e:\monitor\frontend
npm run dev
```
> `http://localhost:5173`으로 접속. Vite 프록시가 API를 `http://127.0.0.1:8000`으로 전달합니다.

### 3. 에이전트 데몬
```powershell
python e:\monitor\agent\agent.py
```
> 백엔드 서버가 먼저 실행 중이어야 합니다.

### 4. 최초 관리자 계정 생성 (DB 직접 또는 시딩 스크립트)
```bash
python e:\monitor\backend\seed_admin.py
```
> 스크립트 실행 시 `admin` 계정이 자동 생성되며 초기 비밀번호가 콘솔에 출력됩니다.

---

## Phase 6 — 고도화 및 부가 기능 완성 (최종 완료)

마지막 세션을 통해 사용자 편의성과 운영 환경을 고려한 마무리 작업이 적용되었습니다.

### 1. 보안 및 배포 강화
* **[seed_admin.py](file:///e:/monitor/backend/seed_admin.py)**: 최초 관리자를 안전하게 생성하는 시딩 스크립트를 구현했습니다.
* **[config.py](file:///e:/monitor/backend/app/core/config.py)**: `SECRET_KEY`를 하드코딩에서 분리하여 환경변수 기반으로 로드하도록 변경했습니다.
* **[docker-compose.yml](file:///e:/monitor/docker-compose.yml)**: Database(Oracle), Backend(FastAPI), Frontend(Vue)를 한 번에 기동할 수 있는 컨테이너 배포 스크립트를 구성했습니다.

### 2. UI/UX 테마 및 확장
* **다크/라이트 모드 토글**: `style.css`에 라이트 모드용 CSS 변수를 추가하고, `App.vue` 하단에 상태(localStorage 연동) 기반의 테마 전환 버튼(🌞 / 🌙)을 구현했습니다.
* **인시던트 UI**: `IncidentList.vue`를 작성하고 `/incidents` 라우팅을 추가하여, `MON_INCIDENT` 테이블 기반의 장애 조치 이력을 추적할 수 있도록 뷰를 신설했습니다.

### 3. 알림 채널 연동 (Notifier)
* **[notifier.py](file:///e:/monitor/backend/app/core/notifier.py)**: 향후 실제 채널 연동을 위해 Email, SMS, Slack Webhook 통신 인터페이스를 담당하는 래퍼(Wrapper) 모듈을 작성했습니다.
* **alert_worker.py 연동**: 30초 주기의 임계치 알림 워커가 `Notifier.dispatch()`를 호출하여 이벤트 발생 시 설정된 채널로 발송하도록 로직을 치환했습니다.

---

> 🎉 **통합 서버 모니터링 관제 시스템의 모든 요구사항(Phase 0 ~ Phase 6)이 성공적으로 구현되었습니다.**
