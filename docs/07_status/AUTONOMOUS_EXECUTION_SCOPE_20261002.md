# 통합관제 자동 연속 실행 승인 범위

- 기준일: 2026-10-02
- 사용자 지시: 남은 과정을 재질문/수동 재실행 요구 없이 계속 실행하고 종료 후 알림.
- 범위: MASTER_PRD_BACKLOG P0/P1/P2 잔여 구현·검증, P3 분리 PRD와 안전한 로컬 구현, 문서·dirty 변경 분류, 실제 로컬 backend/browser/worker QA.
- 작업공간: `E:\python\monitoring-worktrees\ai-pro-backlog-closure-20261002`
- 브랜치: `ai-pro/backlog-closure-20261002`
- 시작 기준선: `b717a41`
- 원본 `E:\python\monitoring` 및 기존 dirty worktree는 보존하고 읽기 전용 대조만 한다.

## 실행과 검증

1. Antigravity CLI Google AI Pro를 sandbox/accept-edits/non-interactive print 방식의 단일 writer로 실행한다.
2. 각 단계 후 Conda `monitor_backend` 전체 backend/agent 테스트, compile, frontend build, browser, dependency audit, tracked/untracked whitespace를 독립 수행한다.
3. Hermes `gpt-6.1-sol` high 독립 read-only QA가 생산 코드 연결, 공개 계약, 실제 증거와 외부 차단의 정당성을 확인한다.
4. 단계 타임아웃·일반 실패는 checkpoint와 diff를 보존하고 다음 tick에서 자동 복구한다. 3회 단위의 실패도 다른 안전 작업 후 자동 재검증 주기로 돌린다.
5. 5분 주기의 script-only watchdog이 작업 중복을 잠금으로 막고 다음 단계를 자동 기동한다. 작업 중 stdout은 비우고 최종 결과/실제 실행 차단만 알린다.
6. 프로젝트 완료와 로컬 검증 완료는 다르다. Oracle·실제 알림·UAT·정책 승인·운영 인수는 실제 증거 없으면 BLOCKED다.

## 금지 범위

- 운영 Oracle 접속·DDL/DML/purge, 실제 Agent·알림 발송·배포·서비스 등록
- credentials/.env/암호화 키 읽기·복사·출력, 평문 비밀정보 저장
- 자동 commit/stage/push/merge, GitHub PR/branch 변경, reset/clean/stash/worktree 삭제
- 다른 프로젝트/GateMigration 재개, 글로벌 패키지·OS·보안 설정 변경
- 권한 정책 임의 확정, 테스트 약화, mock 결과를 실제 환경 검증으로 표시

## 상태와 중지

- 상태·단계별 로그: `C:\Users\HODI\AppData\Local\hermes\automation\monitoring-20261002`
- controller: `C:\Users\HODI\AppData\Local\hermes\scripts\monitoring_backlog_continuation.py`
- cron: `d3dab0a32224`
- 초기 검증: backend **61 passed / 9 warnings**, frontend build PASS, 기존 mocked browser **1 passed**.
- 초기 npm audit: axios high severity 1개. 첫 단계에서 작은 호환 업데이트·회귀 검증으로 처리한다.
- 최종 중지/알림은 cron origin delivery를 사용한다. 실제 완료 전 완료 선언하지 않는다.
