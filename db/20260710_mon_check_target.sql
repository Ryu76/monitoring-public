-- Server-specific process, service, and port check targets.
-- Run as the application schema user, for example example_db_user.

BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE mon_check_target (
            check_target_id NUMBER NOT NULL PRIMARY KEY,
            server_id NUMBER NOT NULL,
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            use_yn CHAR(1) DEFAULT ''Y'' NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN
            RAISE;
        END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE mon_check_result_hist (
            check_result_id NUMBER NOT NULL PRIMARY KEY,
            server_id NUMBER NOT NULL,
            agent_id NUMBER,
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            metric_code VARCHAR2(60) NOT NULL,
            metric_value NUMBER,
            string_value VARCHAR2(1000),
            status_code VARCHAR2(30),
            collected_at TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL
        )
    ';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN
            RAISE;
        END IF;
END;
/

INSERT INTO mon_metric_def (
    metric_code,
    metric_name,
    category_code,
    value_type_code,
    unit_code,
    agg_type_code,
    windows_support_yn,
    linux_support_yn,
    use_yn,
    created_at
)
SELECT
    'PROCESS_STATUS',
    'Process Running Status',
    'PROCESS',
    'FLOAT',
    'BOOLEAN',
    'LAST',
    'Y',
    'Y',
    'Y',
    SYSTIMESTAMP
FROM dual
WHERE NOT EXISTS (
    SELECT 1 FROM mon_metric_def WHERE metric_code = 'PROCESS_STATUS'
);

COMMIT;
