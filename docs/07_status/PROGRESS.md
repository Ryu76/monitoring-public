# 통합 관제 개발 진행 기록

## 2026-09-17 4차 구현 QA 및 완료 (사실 기반 최종 점검)

### 실제 실행 명령 및 QA 결과
- `python -m pytest backend/tests`
  - Pass/Fail Count: 18 passed, 0 failed (7 warnings)
  - 내용: SEC, JOB, ING, MON, OPS, INC 변경 사항 및 글로벌 dependency override 오염 문제 수정, 예외 경로 및 트랜잭션 정상 검증 완료
- `npm run build` (frontend 디렉토리)
  - 성공적으로 Vite 빌드 완료
  - 브라우저 자동화 도구가 없어 End-to-End UI 상호작용 검증은 불가능하며, Build 및 Structural evidence만 확인됨.

### PRD ID별 상태 (엄격한 E2E 검증 기준 적용)

| ID | Status | Note |
|---|---|---|
| **SEC-001** (JWT/RBAC) | `implemented` | 단위 테스트 통과(18개 중 일부). Role enforcement 확인. |
| **SEC-002** (Audit Log) | `implemented` | 트랜잭션 롤백 방어 검증 완료. |
| **JOB-001** (Worker Separation) | `implemented` | main/worker_main 분리 및 스케줄러 독립 실행 확인. |
| **ING-001** (Batch Idempotency) | `implemented` | MetricReceiptLedger 적용 중복 삽입 방지 검증 완료. |
| **ING-002** (Monotonic Upsert) | `implemented` | timestamp 기반 current 지표 역전 방지 완료. |
| **ING-003** (Agent ACK spool) | `implemented` | 파일 기반 Spool 동작 확인 테스트 통과. |
| **ING-004** (History partition) | `partial` | 코드 상 분할 로직은 작성되었으나, SQLite Mock을 사용 중이므로 실제 Oracle Partition 기능의 End-to-End 증명이 불가능. 외부 DB 필수. |
| **MON-001** (Check Definition) | `implemented` | Process/Service/Port 타겟 CRUD 및 Agent 연동 규격 테스트 통과. |
| **MON-002** (Resource Collector) | `implemented` | 백엔드 수집기 연동 테스트 완료. |
| **MON-003** (기간 조회·ServerDetail) | `implemented` | 기간 한정(30일) 쿼리 및 UI 규격(history) 확인. |
| **MON-004** (Dashboard & UI) | `partial` | API 연동 규격 코드와 빌드 통과는 확인했으나, 브라우저 자동화가 없어 E2E UI 동작 증명은 없음 (Build/Structural evidence만 존재). |
| **OPS-001** (Server Group/Tag) | `implemented` | Server 모델 확장 및 Filter API 테스트 통과. |
| **ALT-001** (Alert Policy/Outbox) | `partial` | Outbox Pending/Processing/Failed/Success 상태, Max Retry, History 기록 로직과 TEST 채널 Adapter를 테스트(test_alt_001.py)로 100% 검증함. 단, 실제 Email/Slack 발송은 외부 계정/Credential이 필요하여 Mock 처리됨 (E2E 발송 증명 불가). |
| **INC-001** (Incident Actions) | `implemented` | 조치 내역 등록 시 인시던트 연쇄 상태 변경(OPEN) 검증 완료. |

### 다음 운영 전환 조건
- **운영 DB(Oracle) 통합 테스트**: ING-004 (Partition) 및 대량 데이터 성능 테스트를 위해 실제 Oracle DB 환경 배포 필요.
- **알림 채널 연동(Credential)**: ALT-001의 외부 서비스(Slack Webhook, SMTP 이메일) 발송을 위한 프로덕션 Credential 주입 및 발송망 방화벽 허용.
- **Frontend E2E 테스트**: Playwright 또는 Cypress 등 브라우저 자동화 도구를 통한 전체 대시보드 및 상세 페이지의 사용자 시나리오(E2E) QA 진행.
- **보안 및 규정 컴플라이언스 점검**: 실 운영 전 보안 취약점 진단 및 감사 로그 적재 주기 검토.
