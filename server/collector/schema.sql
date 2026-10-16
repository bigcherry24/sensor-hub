-- SQLite 센서 데이터 스키마

-- 1. 원본 센서 데이터 (30일 보존)
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP NOT NULL,           -- 센서 읽은 시간 (ISO8601)
    device TEXT NOT NULL,            -- raspberrypi 등
    sensor TEXT NOT NULL,            -- temperature, humidity, distance
    value REAL NOT NULL,             -- 24.5, 65.2, 12.3
    unit TEXT NOT NULL,              -- °C, %, cm
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 원본 데이터 인덱스
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);
CREATE INDEX IF NOT EXISTS idx_readings_device ON readings(device);
CREATE INDEX IF NOT EXISTS idx_readings_sensor ON readings(sensor);
CREATE INDEX IF NOT EXISTS idx_readings_ts_device_sensor ON readings(ts, device, sensor);

-- 3. 1분 집계 데이터 (1년 보존)
CREATE TABLE IF NOT EXISTS agg_1min (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    minute TIMESTAMP NOT NULL,       -- 분 단위 (예: 2026-10-17 06:49:00)
    device TEXT NOT NULL,            -- raspberrypi
    sensor TEXT NOT NULL,            -- temperature, humidity, distance
    min REAL NOT NULL,               -- 최솟값
    max REAL NOT NULL,               -- 최댓값
    avg REAL NOT NULL,               -- 평균값
    change_count INTEGER NOT NULL,   -- 값이 몇 번 바뀌었는가 (임계값 판정용)
    sample_count INTEGER NOT NULL,   -- 이 분에 수집된 샘플 수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 집계 데이터 인덱스
CREATE INDEX IF NOT EXISTS idx_agg_1min_minute ON agg_1min(minute);
CREATE INDEX IF NOT EXISTS idx_agg_1min_device ON agg_1min(device);
CREATE INDEX IF NOT EXISTS idx_agg_1min_sensor ON agg_1min(sensor);
CREATE INDEX IF NOT EXISTS idx_agg_1min_minute_device_sensor ON agg_1min(minute, device, sensor);

-- 5. 이벤트 로그 (경고, 임계값 초과 등)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,        -- threshold_exceeded, offline, etc
    device TEXT NOT NULL,
    sensor TEXT,
    value REAL,
    unit TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_device ON events(device);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- 6. 메타데이터 (마지막 처리 시간, 통계 등)
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 데이터 유지보수용 트리거 (자동 삭제)
-- SQLite에서는 자동 DELETE는 지원 안 함.
-- collector.py에서 주기적으로 정리:
-- DELETE FROM readings WHERE ts < datetime('now', '-30 days');
-- DELETE FROM agg_1min WHERE minute < datetime('now', '-1 year');
