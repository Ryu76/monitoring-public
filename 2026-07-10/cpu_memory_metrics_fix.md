# 2026-07-10 CPU/Memory Metrics Display Fix

## 요청
- `http://localhost:5173/servers` 화면에서 CPU, Memory 사용량이 보이지 않는 원인 확인
- 데몬 수집 문제인지, 백엔드 수신/저장 문제인지 구분
- 화면에서 정상 확인 가능하도록 수정

## 확인 결과
- 데몬 수집기는 정상 동작함
  - `agent/collectors/common.py`에서 `CPU_USAGE_PCT`, `MEM_USAGE_PCT` 수집 확인
  - 로컬 `spool.db`에 CPU/MEM/DISK/NET 메트릭이 누적되어 있었음
- 백엔드 상세 API는 최초 확인 시 `metrics: []`를 반환함
  - `GET /api/v1/servers/1`
- 실제 원인은 백엔드 저장 실패
  - `mon_metric_hist` INSERT 중 `ORA-14400` 파티션 오류 발생
  - 같은 트랜잭션 안의 `mon_metric_curr` 저장까지 롤백되어 화면용 현재값이 비어 있었음
- 추가로 현재값 저장 단계에서 두 문제가 더 확인됨
  - 배치 안의 같은 `metric_code + dimension_key + dimension_value`가 여러 수집 시각으로 들어오면 현재값 PK 중복 발생
  - ORM 모델의 `metric_value`가 `Integer`라 CPU/MEM 소수점 값 저장 실패

## 수정 내용
- `backend/app/api/agent/v1/router.py`
  - `/agent/v1/metrics/bulk` 배치 dedup 기준을 현재값 PK 기준으로 변경
  - 같은 metric/dimension 조합은 가장 최신 `collected_at` 값만 저장
  - `mon_metric_hist` 저장을 임시 비활성화
  - 히스토리 파티션 오류가 `mon_metric_curr` 저장을 막지 않도록 조치
- `backend/app/models/resource.py`
  - `MetricCurrent.metric_value` 타입을 `Float`로 변경
  - `MetricHistory.metric_value` 타입을 `Float`로 변경

## 검증
- 백엔드 상세 API 확인
  - `GET http://localhost:8000/api/v1/servers/1`
  - CPU/MEM 현재값 반환 확인
- Vite 프록시 경유 확인
  - `GET http://localhost:5173/api/v1/servers/1`
  - `CPU_USAGE_PCT`, `MEM_USAGE_PCT` 반환 확인
- 에이전트 스풀 확인
  - `spool.db` 대기 건수 0건 확인
  - 누적 데이터 flush 완료
- 프론트엔드 빌드 확인
  - `npm run build` 성공
  - 번들 크기 경고만 있으며 빌드 실패 없음

## 남은 작업
- `mon_metric_hist`의 2026년 이후 파티션을 DB에 생성한 뒤 히스토리 INSERT를 다시 활성화해야 함
- 장기 추세 차트가 히스토리 테이블을 사용하게 되면 파티션 보정이 필수
