# 진행 상황 (PROGRESS)

## 상태
- **현재 상태**: READY_FOR_REVIEW
- **최종 업데이트 (KST)**: 2026-09-17 17:05:00

## 변경 사항
- **실제 변경 파일**:
  - `docs/03_planning/AI_PRO_PRD_CODE_AUDIT.md` (새로 생성하여 기존 PRD 목록의 전수 검사 결과 기입)
  - `backend/tests/test_security.py` (보안 관련 헬퍼 함수 순수 로직 테스트 추가)
  - `PROGRESS.md` (현재 파일)

## 검증 내역
- **실제로 종료된 검증 명령과 결과**:
  1. `pytest backend/tests/test_security.py -v` : 2 passed (성공)
  2. `python -m compileall backend/app` : 성공 (문법 오류 없음)
  3. `git diff --check` : 성공 (공백 에러 등 없음)

## 차단 요인 (Blockers)
- 기존 AI Pro 작업이 PRD 백로그를 준수하지 않고 뼈대만 작성한 후 완료로 표기하여 전면적인 재구현이 필요함
- 현재 API와 Worker가 동일한 애플리케이션 라이프사이클에 강결합되어 있으며(JOB-001 위반), JWT 인증이 주요 웹 API에서 강제되지 않음(SEC-001 위반)
- Agent 통신에서 ACK 및 재시도, Spool에 대한 보존 테스트가 부재하며 이력 저장(mon_metric_hist) 로직이 주석 처리됨

## 다음 우선순위 3개
1. **SEC-001 & SEC-002 구현**: Web API 엔드포인트에 `Depends(auth)` 적용 및 역할 기반 권한 제어 적용, SYS_AUDIT_LOG에 상세 이력(before-after) 기록
2. **JOB-001 구현**: FastAPI 애플리케이션 시작 프로세스에서 백그라운드 Worker/Scheduler 분리 (독립적인 구동 스크립트 작성)
3. **ING-001 & ING-002 구현**: `receive_metrics` 엔드포인트 내 Batch 멱등성 보장 로직 및 Timestamp-monotonic UPSERT 로직 적용
