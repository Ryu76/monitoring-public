# 통합 관제 로컬 E2E 검증 계획

## 목적

Agent → Backend → 개발용 DB → Web UI 흐름을 검증하되, 운영 Oracle·운영 데이터·외부 알림 채널에는 접속하지 않는다.

## 사전 조건

1. 전용 개발 DB 또는 일회성 로컬 컨테이너를 사용한다. 운영 DB 호스트·계정·서비스명은 사용하지 않는다.
2. DB/JWT/초기 관리자 값은 승인된 비밀 저장소 또는 암호화된 로컬 설정에서만 주입한다. 평문 `.env`는 저장소에 두지 않는다.
3. `docker compose config`를 placeholder 값으로 검증한 뒤에만 컨테이너 기동을 검토한다.
4. 백엔드, Agent, 프론트엔드는 서로 다른 로컬 포트를 사용하고, 외부 공개 바인딩은 하지 않는다.
5. 시작 전 worktree·실행 명령·테스트 데이터 범위를 기록한다.

## 단계별 검증

| 단계 | 목적 | 성공 기준 | 금지 사항 |
| --- | --- | --- | --- |
| 1. 정적 기준선 | Python/TypeScript 오류 확인 | backend·agent compile, frontend production build 통과 | DB 연결 |
| 2. 비밀 설정 계약 | 누락 시 fail-closed 확인 | 필수 값이 없으면 backend 설정 로드 실패 | 실제 비밀 출력 |
| 3. 개발 DB 기동 | 개발 DB 한정 연결 | health check 및 스키마 준비 확인 | 운영 DB DDL/쓰기 |
| 4. Backend health | API 프로세스 기동 검증 | `/health` 200 응답 | 외부 공개 |
| 5. Agent 계약 | enroll, pending 차단, approved 수집 경로 | 승인 전 401/403, 승인 후 test metric 수신 | 실제 서버 Agent 설치 |
| 6. UI E2E | 대시보드 표시·로그인 가드 확인 | 브라우저에서 mock/dev 데이터 표시 | 운영 계정 로그인 |
| 7. 복수 주기 | 수집 일관성 | 최소 3회 수집의 current/history 일관성 | 운영 데이터 적재 |

## 현재 차단 상태

- 암호화된 개발용 설정과 전용 개발 DB가 아직 준비되지 않았다.
- Agent 승인·DB 적재·브라우저 E2E 실행 증거가 없다.
- 따라서 3단계 이후는 명시적인 개발 DB 승인 전에는 실행하지 않는다.

## 기록 규칙

- 각 단계의 명령, 종료 코드, 검증 시각을 `PROGRESS.md`에 남긴다.
- `READY_FOR_REVIEW` 상태와 사람이 검토한 diff가 없으면 완료로 표시하지 않는다.
- 비밀값, DB 연결 문자열, 토큰, 쿠키는 로그·보고서·Git diff에 기록하지 않는다.
