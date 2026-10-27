# SeatMate 운영 Oracle 반영용 SQL 초안

> 작성 기준: `ai-pro/holiday-closures` 기능 브랜치의 실제 Rust 코드 (`closure_handlers.rs`, `restriction_group_handlers.rs`, `stats_handlers.rs`, `oracle_ops.rs`)를 검토해 작성했습니다.
>
> **중요:** 이 문서는 운영 DB에 실행한 기록이 아닙니다. 현재 기능 브랜치에서 휴관일·이용제한 그룹·통계 카탈로그의 신규 쓰기 경로는 Oracle 모드에서 `oracle_read_only`로 차단됩니다. 즉, 아래 DDL/DML과 애플리케이션의 Oracle 저장소 구현을 별도 검토·승인·배포하기 전에는 운영 영속 기능이 켜지지 않습니다.

## 1. 현재 코드가 실제로 사용하는 기존 운영 객체

읽기 통계와 기존 단건 이용제한 기능에서 확인된 객체입니다.

| 목적 | 현재 객체 / 호출 |
|---|---|
| 회원 원장 조회 | `HD_MEMBER` (`USER_ID`, `USER_NM`, `BIRTH_DAY`, `SEX`, `BLK_START_TIME`, `BLK_END_TIME` 등) |
| 좌석 이용 로그 | `HD_SEAT_LOG` (`CONFIRM_IN_TIME`, `CONFIRM_OUT_TIME`, `USER_ID`, `SEAT_ID`, `RSRV_IDX`, `OUT_TYPE` 등) |
| 좌석/열람실 정보 | `HD_SEAT_INFO`, `HD_CLASS_INFO`, `HD_SEAT_TRUE_TIME_LOG` |
| 예약 | `HD_RSRV` |
| 단건 이용제한 등록 | `SEATMATE_PKG.SP_SET_BLACK_LIST_MEMBER(:USER_ID, :ADMIN_ID, :HOLD_DAYS, :MEMO)` |
| 단건 이용제한 해제 | `SEATMATE_PKG.SP_CANCEL_BLACK_LIST(:USER_ID, :ADMIN_ID, :MEMO)` |

신규 기능은 외부 회원 시스템을 원장으로 유지해야 하므로 `HD_MEMBER`의 회원 기본정보를 직접 수정하지 않습니다. 이용제한 적용은 기존 패키지 프로시저를 재사용하고, 그룹 정의·실행 이력만 SeatMate 운영 보조 테이블에 기록하는 방식이 안전합니다.

---

## 2. 실행 전 읽기 전용 사전 점검

아래는 **조회 전용**입니다. 실제 스키마 소유자를 확정하고 동일 이름 객체 충돌 여부를 확인한 후에만 다음 단계로 진행합니다.

```sql
-- 접속 계정 / Oracle 버전 확인
SELECT USER AS current_user FROM dual;
SELECT banner FROM v$version WHERE banner LIKE 'Oracle%';

-- 현재 접속 계정, 접근 가능한 소유자, 동의어를 함께 확인
SELECT owner, table_name
FROM all_tables
WHERE table_name IN (
  'HD_MEMBER', 'HD_SEAT_LOG', 'HD_SEAT_INFO', 'HD_CLASS_INFO', 'HD_SEAT_TRUE_TIME_LOG', 'HD_RSRV',
  'SM_CLOSURE_DATE', 'SM_RESTRICTION_GROUP', 'SM_RESTRICTION_GROUP_SEX',
  'SM_MEMBER_RESTRICTION', 'SM_REPORT_CATALOG', 'SM_OPERATION_AUDIT'
)
ORDER BY owner, table_name;

SELECT owner, synonym_name, table_owner, table_name
FROM all_synonyms
WHERE synonym_name IN (
  'HD_MEMBER', 'HD_SEAT_LOG', 'HD_SEAT_INFO', 'HD_CLASS_INFO', 'HD_SEAT_TRUE_TIME_LOG', 'HD_RSRV'
)
ORDER BY owner, synonym_name;

-- 신규 오브젝트가 이미 존재하는지 확인
SELECT object_type, object_name, status
FROM user_objects
WHERE object_name IN (
  'SM_CLOSURE_DATE', 'SM_RESTRICTION_GROUP', 'SM_RESTRICTION_GROUP_SEX',
  'SM_MEMBER_RESTRICTION', 'SM_REPORT_CATALOG', 'SM_OPERATION_AUDIT',
  'SQ_SM_CLOSURE_DATE', 'SQ_SM_RESTRICTION_GROUP', 'SQ_SM_MEMBER_RESTRICTION',
  'TR_SM_CLOSURE_DATE_BI', 'TR_SM_RESTRICTION_GROUP_BI', 'TR_SM_MEMBER_RESTRICTION_BI'
)
ORDER BY object_type, object_name;

-- 기존 이용제한 패키지의 실행 권한과 시그니처 확인
SELECT owner, object_name, procedure_name
FROM all_procedures
WHERE object_name = 'SEATMATE_PKG'
  AND procedure_name IN ('SP_SET_BLACK_LIST_MEMBER', 'SP_CANCEL_BLACK_LIST')
ORDER BY owner, procedure_name;
```

> `v$version` 또는 `ALL_*` 뷰 권한이 없으면 권한 오류를 정상으로 보고, DBA에게 조회 결과만 요청합니다. 운영 데이터 조회·변경을 위해 권한을 넓히지 않습니다.

---

## 3. Oracle 11g 호환 신규 운영 테이블 DDL (승인 후 1회)

- `IDENTITY`, `JSON` 타입, `FETCH FIRST`는 Oracle 11g에서 사용하지 않습니다.
- 키는 시퀀스와 `BEFORE INSERT` 트리거로 생성합니다.
- JSON 메타데이터는 `CLOB`에 저장하되, JSON 문법 검증은 애플리케이션에서 수행합니다.
- 아래 `SM_*`는 기존 `HD_*` 원장과 분리된 **SeatMate 운영 보조 테이블**입니다.

```sql
CREATE TABLE SM_CLOSURE_DATE (
    CLOSURE_ID       NUMBER(19)      NOT NULL,
    CLOSURE_DATE     DATE            NOT NULL,
    DESCRIPTION      VARCHAR2(500 CHAR),
    SOURCE_TYPE      VARCHAR2(20 CHAR) NOT NULL,
    SOURCE_METADATA  CLOB,
    ACTIVE_YN        CHAR(1)         DEFAULT 'Y' NOT NULL,
    CREATED_BY       VARCHAR2(100 CHAR) NOT NULL,
    CREATED_AT       DATE            DEFAULT SYSDATE NOT NULL,
    UPDATED_BY       VARCHAR2(100 CHAR),
    UPDATED_AT       DATE,
    CONSTRAINT PK_SM_CLOSURE_DATE PRIMARY KEY (CLOSURE_ID),
    CONSTRAINT UQ_SM_CLOSURE_DATE UNIQUE (CLOSURE_DATE),
    CONSTRAINT CK_SM_CLOSURE_SOURCE CHECK (SOURCE_TYPE IN ('manual', 'range', 'rule')),
    CONSTRAINT CK_SM_CLOSURE_ACTIVE CHECK (ACTIVE_YN IN ('Y', 'N'))
);

CREATE INDEX IX_SM_CLOSURE_DATE_ACTIVE
    ON SM_CLOSURE_DATE (ACTIVE_YN, CLOSURE_DATE);

CREATE SEQUENCE SQ_SM_CLOSURE_DATE START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

CREATE OR REPLACE TRIGGER TR_SM_CLOSURE_DATE_BI
BEFORE INSERT ON SM_CLOSURE_DATE
FOR EACH ROW
BEGIN
  IF :NEW.CLOSURE_ID IS NULL THEN
    SELECT SQ_SM_CLOSURE_DATE.NEXTVAL INTO :NEW.CLOSURE_ID FROM dual;
  END IF;
END;
/

CREATE TABLE SM_RESTRICTION_GROUP (
    GROUP_ID          NUMBER(19)       NOT NULL,
    GROUP_NAME        VARCHAR2(100 CHAR) NOT NULL,
    ENABLED_YN        CHAR(1)          DEFAULT 'Y' NOT NULL,
    AGE_MIN           NUMBER(3),
    AGE_MAX           NUMBER(3),
    HOLD_DAYS         NUMBER(5)        NOT NULL,
    MEMO              VARCHAR2(200 CHAR),
    ACTIVE_YN         CHAR(1)          DEFAULT 'Y' NOT NULL,
    CREATED_BY        VARCHAR2(100 CHAR) NOT NULL,
    CREATED_AT        DATE             DEFAULT SYSDATE NOT NULL,
    UPDATED_BY        VARCHAR2(100 CHAR),
    UPDATED_AT        DATE,
    CONSTRAINT PK_SM_RESTRICTION_GROUP PRIMARY KEY (GROUP_ID),
    CONSTRAINT CK_SM_RG_ENABLED CHECK (ENABLED_YN IN ('Y', 'N')),
    CONSTRAINT CK_SM_RG_ACTIVE CHECK (ACTIVE_YN IN ('Y', 'N')),
    CONSTRAINT CK_SM_RG_AGE CHECK (AGE_MIN IS NULL OR AGE_MAX IS NULL OR AGE_MIN <= AGE_MAX),
    CONSTRAINT CK_SM_RG_AGE_MAX CHECK (NVL(AGE_MIN, 0) BETWEEN 0 AND 150 AND NVL(AGE_MAX, 150) BETWEEN 0 AND 150),
    CONSTRAINT CK_SM_RG_HOLD_DAYS CHECK (HOLD_DAYS BETWEEN 1 AND 36500)
);

CREATE UNIQUE INDEX UX_SM_RG_NAME_ACTIVE
    ON SM_RESTRICTION_GROUP (CASE WHEN ACTIVE_YN = 'Y' THEN GROUP_NAME END);

CREATE SEQUENCE SQ_SM_RESTRICTION_GROUP START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

CREATE OR REPLACE TRIGGER TR_SM_RESTRICTION_GROUP_BI
BEFORE INSERT ON SM_RESTRICTION_GROUP
FOR EACH ROW
BEGIN
  IF :NEW.GROUP_ID IS NULL THEN
    SELECT SQ_SM_RESTRICTION_GROUP.NEXTVAL INTO :NEW.GROUP_ID FROM dual;
  END IF;
END;
/

CREATE TABLE SM_RESTRICTION_GROUP_SEX (
    GROUP_ID          NUMBER(19) NOT NULL,
    SEX_VALUE         VARCHAR2(20 CHAR) NOT NULL,
    CREATED_AT        DATE DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_SM_RESTRICTION_GROUP_SEX PRIMARY KEY (GROUP_ID, SEX_VALUE),
    CONSTRAINT FK_SM_RG_SEX_GROUP FOREIGN KEY (GROUP_ID)
      REFERENCES SM_RESTRICTION_GROUP (GROUP_ID)
);

CREATE TABLE SM_MEMBER_RESTRICTION (
    RESTRICTION_ID    NUMBER(19) NOT NULL,
    GROUP_ID          NUMBER(19),
    USER_ID           VARCHAR2(100 CHAR) NOT NULL,
    ACTION_TYPE       VARCHAR2(20 CHAR) NOT NULL,
    HOLD_DAYS         NUMBER(5),
    EFFECTIVE_FROM    DATE,
    EFFECTIVE_TO      DATE,
    STATUS            VARCHAR2(20 CHAR) DEFAULT 'APPLIED' NOT NULL,
    ADMIN_ID          VARCHAR2(100 CHAR) NOT NULL,
    MEMO              VARCHAR2(200 CHAR),
    CREATED_AT        DATE DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_SM_MEMBER_RESTRICTION PRIMARY KEY (RESTRICTION_ID),
    CONSTRAINT FK_SM_MEMBER_RESTRICTION_GROUP FOREIGN KEY (GROUP_ID)
      REFERENCES SM_RESTRICTION_GROUP (GROUP_ID),
    CONSTRAINT CK_SM_MEMBER_RESTR_ACTION CHECK (ACTION_TYPE IN ('APPLY', 'CANCEL')),
    CONSTRAINT CK_SM_MEMBER_RESTR_STATUS CHECK (STATUS IN ('APPLIED', 'CANCELLED', 'FAILED'))
);

CREATE INDEX IX_SM_MEMBER_RESTRICTION_01
    ON SM_MEMBER_RESTRICTION (GROUP_ID, USER_ID, CREATED_AT);

CREATE SEQUENCE SQ_SM_MEMBER_RESTRICTION START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

CREATE OR REPLACE TRIGGER TR_SM_MEMBER_RESTRICTION_BI
BEFORE INSERT ON SM_MEMBER_RESTRICTION
FOR EACH ROW
BEGIN
  IF :NEW.RESTRICTION_ID IS NULL THEN
    SELECT SQ_SM_MEMBER_RESTRICTION.NEXTVAL INTO :NEW.RESTRICTION_ID FROM dual;
  END IF;
END;
/

CREATE TABLE SM_REPORT_CATALOG (
    REPORT_ID         VARCHAR2(100 CHAR) NOT NULL,
    REPORT_NAME       VARCHAR2(200 CHAR) NOT NULL,
    DESCRIPTION       VARCHAR2(500 CHAR),
    ENDPOINT          VARCHAR2(200 CHAR) NOT NULL,
    CATEGORY          VARCHAR2(100 CHAR),
    ENABLED_YN        CHAR(1) DEFAULT 'Y' NOT NULL,
    UPDATED_BY        VARCHAR2(100 CHAR),
    UPDATED_AT        DATE,
    CONSTRAINT PK_SM_REPORT_CATALOG PRIMARY KEY (REPORT_ID),
    CONSTRAINT CK_SM_REPORT_ENABLED CHECK (ENABLED_YN IN ('Y', 'N'))
);

CREATE TABLE SM_OPERATION_AUDIT (
    AUDIT_ID          NUMBER(19) NOT NULL,
    ACTION_TYPE       VARCHAR2(100 CHAR) NOT NULL,
    TARGET_TYPE       VARCHAR2(100 CHAR) NOT NULL,
    TARGET_KEY        VARCHAR2(200 CHAR),
    ADMIN_ID          VARCHAR2(100 CHAR) NOT NULL,
    DETAIL_JSON       CLOB,
    CREATED_AT        DATE DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_SM_OPERATION_AUDIT PRIMARY KEY (AUDIT_ID)
);

CREATE INDEX IX_SM_OPERATION_AUDIT_01
    ON SM_OPERATION_AUDIT (TARGET_TYPE, TARGET_KEY, CREATED_AT);

CREATE SEQUENCE SQ_SM_OPERATION_AUDIT START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

CREATE OR REPLACE TRIGGER TR_SM_OPERATION_AUDIT_BI
BEFORE INSERT ON SM_OPERATION_AUDIT
FOR EACH ROW
BEGIN
  IF :NEW.AUDIT_ID IS NULL THEN
    SELECT SQ_SM_OPERATION_AUDIT.NEXTVAL INTO :NEW.AUDIT_ID FROM dual;
  END IF;
END;
/
```

> Oracle DDL은 자동 커밋됩니다. 따라서 위 스크립트는 운영 변경 창에서 DBA 검토 및 백업 확인 후 실행해야 합니다. DDL 완료 후 테이블/인덱스/시퀀스/트리거는 `USER_OBJECTS`로 각각 확인합니다.

---

## 4. 휴관일 데이터 변경 쿼리

### 4.1 휴관일 단건 등록 또는 병합

```sql
MERGE INTO SM_CLOSURE_DATE target
USING (
  SELECT
    TO_DATE(:closure_date, 'YYYY-MM-DD') AS closure_date,
    :description AS description,
    :source_type AS source_type,
    :source_metadata AS source_metadata,
    :admin_id AS admin_id
  FROM dual
) source
ON (target.CLOSURE_DATE = source.closure_date)
WHEN MATCHED THEN UPDATE SET
  target.DESCRIPTION = source.description,
  target.SOURCE_TYPE = source.source_type,
  target.SOURCE_METADATA = source.source_metadata,
  target.ACTIVE_YN = 'Y',
  target.UPDATED_BY = source.admin_id,
  target.UPDATED_AT = SYSDATE
WHEN NOT MATCHED THEN INSERT (
  CLOSURE_ID, CLOSURE_DATE, DESCRIPTION, SOURCE_TYPE, SOURCE_METADATA,
  ACTIVE_YN, CREATED_BY, CREATED_AT
) VALUES (
  SQ_SM_CLOSURE_DATE.NEXTVAL, source.closure_date, source.description,
  source.source_type, source.source_metadata, 'Y', source.admin_id, SYSDATE
);

INSERT INTO SM_OPERATION_AUDIT (
  AUDIT_ID, ACTION_TYPE, TARGET_TYPE, TARGET_KEY, ADMIN_ID, DETAIL_JSON, CREATED_AT
) VALUES (
  SQ_SM_OPERATION_AUDIT.NEXTVAL, 'UPSERT', 'CLOSURE_DATE', :closure_date,
  :admin_id, :source_metadata, SYSDATE
);
```

### 4.2 휴관일 비활성화 (삭제 대신 보존)

```sql
UPDATE SM_CLOSURE_DATE
SET ACTIVE_YN = 'N',
    UPDATED_BY = :admin_id,
    UPDATED_AT = SYSDATE
WHERE CLOSURE_DATE = TO_DATE(:closure_date, 'YYYY-MM-DD')
  AND ACTIVE_YN = 'Y';

INSERT INTO SM_OPERATION_AUDIT (
  AUDIT_ID, ACTION_TYPE, TARGET_TYPE, TARGET_KEY, ADMIN_ID, DETAIL_JSON, CREATED_AT
) VALUES (
  SQ_SM_OPERATION_AUDIT.NEXTVAL, 'DEACTIVATE', 'CLOSURE_DATE', :closure_date,
  :admin_id, :detail_json, SYSDATE
);
```

### 4.3 예약/좌석 배정 전 휴관일 판정 (읽기 전용)

`SEATMATE_PKG.SP_RSRV`와 `SP_ALLOT` 내부 또는 API 호출 직전에 아래 판정을 추가합니다. 휴관일이면 예약/배정 프로시저를 호출하지 않아야 합니다.

```sql
SELECT CASE WHEN EXISTS (
  SELECT 1
  FROM SM_CLOSURE_DATE
  WHERE CLOSURE_DATE = TRUNC(:target_datetime)
    AND ACTIVE_YN = 'Y'
) THEN 1 ELSE 0 END AS is_closed
FROM dual;
```

---

## 5. 연령·성별 이용제한 그룹 및 적용 쿼리

### 5.1 그룹 생성

```sql
INSERT INTO SM_RESTRICTION_GROUP (
  GROUP_ID, GROUP_NAME, ENABLED_YN, AGE_MIN, AGE_MAX, HOLD_DAYS, MEMO,
  ACTIVE_YN, CREATED_BY, CREATED_AT
) VALUES (
  SQ_SM_RESTRICTION_GROUP.NEXTVAL, :group_name, :enabled_yn,
  :age_min, :age_max, :hold_days, :memo,
  'Y', :admin_id, SYSDATE
);

-- 생성된 GROUP_ID는 애플리케이션에서 RETURNING 또는 SELECT로 획득한 뒤 성별을 등록합니다.
INSERT INTO SM_RESTRICTION_GROUP_SEX (GROUP_ID, SEX_VALUE, CREATED_AT)
VALUES (:group_id, :sex_value, SYSDATE);
```

### 5.2 그룹 활성/비활성화

```sql
UPDATE SM_RESTRICTION_GROUP
SET ENABLED_YN = :enabled_yn,
    UPDATED_BY = :admin_id,
    UPDATED_AT = SYSDATE
WHERE GROUP_ID = :group_id
  AND ACTIVE_YN = 'Y';

INSERT INTO SM_OPERATION_AUDIT (
  AUDIT_ID, ACTION_TYPE, TARGET_TYPE, TARGET_KEY, ADMIN_ID, DETAIL_JSON, CREATED_AT
) VALUES (
  SQ_SM_OPERATION_AUDIT.NEXTVAL, 'TOGGLE', 'RESTRICTION_GROUP', TO_CHAR(:group_id),
  :admin_id, :detail_json, SYSDATE
);
```

### 5.3 대상 회원 미리보기 (읽기 전용)

나이는 코드 현재 동작과 일치하도록 `SYSDATE`의 연도에서 `BIRTH_DAY`의 앞 4자리를 뺀 연 나이입니다. 법정/만 나이 기준이 필요하면 정책을 별도로 확정해야 합니다.

```sql
SELECT
  hm.USER_ID,
  hm.USER_NM,
  SUBSTR(hm.BIRTH_DAY, 1, 4) AS birth_year,
  TO_CHAR(hm.SEX) AS sex,
  TO_NUMBER(TO_CHAR(SYSDATE, 'YYYY')) - TO_NUMBER(SUBSTR(hm.BIRTH_DAY, 1, 4)) AS age
FROM HD_MEMBER hm
WHERE hm.BIRTH_DAY IS NOT NULL
  AND REGEXP_LIKE(SUBSTR(hm.BIRTH_DAY, 1, 4), '^[0-9]{4}$')
  AND (:age_min IS NULL OR TO_NUMBER(TO_CHAR(SYSDATE, 'YYYY')) - TO_NUMBER(SUBSTR(hm.BIRTH_DAY, 1, 4)) >= :age_min)
  AND (:age_max IS NULL OR TO_NUMBER(TO_CHAR(SYSDATE, 'YYYY')) - TO_NUMBER(SUBSTR(hm.BIRTH_DAY, 1, 4)) <= :age_max)
  AND (
    NOT EXISTS (SELECT 1 FROM SM_RESTRICTION_GROUP_SEX s WHERE s.GROUP_ID = :group_id)
    OR EXISTS (
      SELECT 1
      FROM SM_RESTRICTION_GROUP_SEX s
      WHERE s.GROUP_ID = :group_id
        AND s.SEX_VALUE = TO_CHAR(hm.SEX)
    )
  )
ORDER BY hm.USER_ID;
```

### 5.4 이용제한 적용 — 기존 패키지 프로시저만 사용

`HD_MEMBER`의 차단 날짜를 직접 `UPDATE`하지 않습니다. 대상별로 기존 도메인 프로시저를 호출해야 이력/정책을 유지할 수 있습니다.

```sql
-- 한 명에 대한 호출 예시: 애플리케이션에서 바인드 변수로 실행
BEGIN
  SEATMATE_PKG.SP_SET_BLACK_LIST_MEMBER(
    :user_id,
    :admin_id,
    :hold_days,
    :memo
  );
END;
/

-- 성공한 각 대상에만 적용 이력을 남깁니다.
INSERT INTO SM_MEMBER_RESTRICTION (
  RESTRICTION_ID, GROUP_ID, USER_ID, ACTION_TYPE, HOLD_DAYS,
  EFFECTIVE_FROM, EFFECTIVE_TO, STATUS, ADMIN_ID, MEMO, CREATED_AT
) VALUES (
  SQ_SM_MEMBER_RESTRICTION.NEXTVAL, :group_id, :user_id, 'APPLY', :hold_days,
  TRUNC(SYSDATE), TRUNC(SYSDATE) + :hold_days, 'APPLIED', :admin_id, :memo, SYSDATE
);
```

> 그룹 일괄 적용은 **대상 미리보기 → 관리자 확인 → 대상별 프로시저 호출 → 성공/실패별 감사 기록** 순서로 애플리케이션 트랜잭션·오류 처리를 구현해야 합니다. 무조건적인 SQL `UPDATE HD_MEMBER` 또는 한 번에 다수 회원을 처리하는 익명 PL/SQL 블록은 사용하지 않습니다.

### 5.5 이용제한 해제

```sql
BEGIN
  SEATMATE_PKG.SP_CANCEL_BLACK_LIST(
    :user_id,
    :admin_id,
    :memo
  );
END;
/

INSERT INTO SM_MEMBER_RESTRICTION (
  RESTRICTION_ID, GROUP_ID, USER_ID, ACTION_TYPE, STATUS, ADMIN_ID, MEMO, CREATED_AT
) VALUES (
  SQ_SM_MEMBER_RESTRICTION.NEXTVAL, :group_id, :user_id, 'CANCEL', 'CANCELLED',
  :admin_id, :memo, SYSDATE
);
```

---

## 6. 통계 카탈로그 데이터

### 6.1 최초 항목 등록

```sql
MERGE INTO SM_REPORT_CATALOG target
USING (
  SELECT 'daily_use' AS report_id, '일별 이용 현황' AS report_name,
         '일자별 전체 좌석 발권 및 인구통계 집계' AS description,
         '/api/stats/daily' AS endpoint, 'operations' AS category FROM dual
  UNION ALL SELECT 'hourly_admissions_use', '시간대별 입실/이용 현황', '시간대별 좌석 배정 및 이용 패턴', '/api/stats/hourly-in', 'operations' FROM dual
  UNION ALL SELECT 'weekday_distribution', '요일별 이용 분포', '요일별 평균 이용시간 및 집중 요일', '/api/stats/weekday-avg', 'patterns' FROM dual
  UNION ALL SELECT 'monthly_trend', '월별 이용 추이', '월별 총 이용 건수 및 추세', '/api/stats/monthly', 'patterns' FROM dual
  UNION ALL SELECT 'room_weekday', '열람실/요일별 이용 현황', '열람실별 요일 분배', '/api/stats/room-weekday', 'rooms' FROM dual
  UNION ALL SELECT 'reservation_conversion', '예약 전환율 분석', '예약 대비 실제 좌석 배정', '/api/stats/reservation-conversion', 'reservations' FROM dual
  UNION ALL SELECT 'forced_end_restriction_activity', '강제퇴실/이용제한 활동 분석', '강제 퇴실 및 제한 이력', '/api/stats/restriction-activity', 'compliance' FROM dual
  UNION ALL SELECT 'sex_by_period', '기간별 성별 이용 분석', '지정 기간 성별 이용 분포', '/api/stats/sex-period', 'demographics' FROM dual
  UNION ALL SELECT 'age_band_by_period', '기간별 연령대 이용 분석', '지정 기간 연령대별 이용 분포', '/api/stats/age-bands', 'demographics' FROM dual
  UNION ALL SELECT 'class_usage', '열람실별 이용 집계', '열람실별 총 이용 건수와 이용 시간', '/api/stats/class-usage', 'rooms' FROM dual
  UNION ALL SELECT 'occupancy_summary', '운영 및 좌석 점유율 종합', '전체 좌석 가동률 및 운영 지표', '/api/stats/operations-summary', 'overview' FROM dual
) source
ON (target.REPORT_ID = source.report_id)
WHEN MATCHED THEN UPDATE SET
  target.REPORT_NAME = source.report_name,
  target.DESCRIPTION = source.description,
  target.ENDPOINT = source.endpoint,
  target.CATEGORY = source.category
WHEN NOT MATCHED THEN INSERT (
  REPORT_ID, REPORT_NAME, DESCRIPTION, ENDPOINT, CATEGORY, ENABLED_YN
) VALUES (
  source.report_id, source.report_name, source.description, source.endpoint, source.category, 'Y'
);
```

### 6.2 등급 3 관리자에 의한 통계 항목 비활성화

```sql
UPDATE SM_REPORT_CATALOG
SET ENABLED_YN = 'N',
    UPDATED_BY = :admin_id,
    UPDATED_AT = SYSDATE
WHERE REPORT_ID = :report_id;

INSERT INTO SM_OPERATION_AUDIT (
  AUDIT_ID, ACTION_TYPE, TARGET_TYPE, TARGET_KEY, ADMIN_ID, DETAIL_JSON, CREATED_AT
) VALUES (
  SQ_SM_OPERATION_AUDIT.NEXTVAL, 'DISABLE', 'REPORT_CATALOG', :report_id,
  :admin_id, :detail_json, SYSDATE
);
```

---

## 7. 통계 조회 SQL 기준

현재 API는 다음 테이블 관계를 이용합니다.

- 일별/성별/연령: `HD_SEAT_LOG HSL LEFT JOIN HD_MEMBER HM ON HM.USER_ID = HSL.USER_ID`
- 열람실/요일/시간대: `HD_SEAT_LOG HSL LEFT JOIN HD_SEAT_INFO HSI ON HSI.SEAT_ID = HSL.SEAT_ID LEFT JOIN HD_CLASS_INFO HCI ON HCI.CLASS_ID = HSI.CLASS_ID`
- 예약: `HD_RSRV`

### 기간별 성별 이용 통계

```sql
SELECT
  CASE
    WHEN hm.SEX IN ('1', '3', '5', '7') THEN 'M'
    WHEN hm.SEX IN ('2', '4', '6', '8') THEN 'F'
    ELSE 'UNKNOWN'
  END AS sex_group,
  COUNT(*) AS use_count,
  COUNT(DISTINCT hsl.USER_ID) AS unique_member_count
FROM HD_SEAT_LOG hsl
LEFT JOIN HD_MEMBER hm ON hm.USER_ID = hsl.USER_ID
WHERE hsl.CONFIRM_IN_TIME >= REPLACE(:start_date, '-', '') || '000000'
  AND hsl.CONFIRM_IN_TIME <= REPLACE(:end_date, '-', '') || '235959'
GROUP BY CASE
  WHEN hm.SEX IN ('1', '3', '5', '7') THEN 'M'
  WHEN hm.SEX IN ('2', '4', '6', '8') THEN 'F'
  ELSE 'UNKNOWN'
END
ORDER BY sex_group;
```

### 시간대별 이용 통계

```sql
SELECT
  SUBSTR(hsl.CONFIRM_IN_TIME, 9, 2) AS hour_of_day,
  COUNT(*) AS admission_count,
  COUNT(DISTINCT hsl.USER_ID) AS unique_member_count
FROM HD_SEAT_LOG hsl
WHERE hsl.CONFIRM_IN_TIME >= REPLACE(:start_date, '-', '') || '000000'
  AND hsl.CONFIRM_IN_TIME <= REPLACE(:end_date, '-', '') || '235959'
GROUP BY SUBSTR(hsl.CONFIRM_IN_TIME, 9, 2)
ORDER BY hour_of_day;
```

---

## 8. 운영 적용 순서와 검증

1. DBA/운영 담당자가 2절의 읽기 전용 사전 점검을 수행한다.
2. 스키마 소유자와 `HD_*`/`SEATMATE_PKG` 권한을 확정한다.
3. 승인된 변경 창에 3절 DDL을 **한 번만** 적용한다. Oracle DDL은 롤백되지 않는다.
4. 테스트용 관리자·테스트 회원으로 다음 DML을 각각 명시적 `ROLLBACK` 경계 안에서 검증한다. 시퀀스 번호는 롤백되어도 건너뛸 수 있다.
   - 휴관일 등록/조회/비활성화
   - 제한 그룹 생성/성별 조건 저장/대상 미리보기
   - 기존 `SEATMATE_PKG` 단건 제한 등록/해제 호출
   - 통계 카탈로그 비활성화 후 API 차단 확인
5. 애플리케이션에 Oracle 저장소 구현, API 연결, 감사 로그, 실패 보상 처리를 반영하고 전체 회귀 검증한다.
6. 운영 데이터에 제한 그룹을 실제 적용하기 전에는 대상 미리보기 결과와 관리자 승인 기록을 보관한다.

## 9. 현 상태 요약

- 이 문서의 SQL은 **운영 DB에 실행하지 않았습니다.**
- 현재 feature 브랜치는 휴관일·그룹·카탈로그를 메모리/데모 모드에서 제공하며, Oracle 신규 쓰기는 의도적으로 차단합니다.
- `HD_MEMBER` 기본 회원 원장 직접 변경은 범위에서 제외합니다.
- 운영 적용 전에는 Oracle 11g 데이터 사전 점검, 스키마 승인, 애플리케이션 Oracle 저장소 구현, 롤백 가능한 DML 검증이 필수입니다.