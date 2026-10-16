# 센서 수집기 (Collector)

MQTT 메시지를 수신하여 SQLite DB에 저장하고, 1분 단위 집계를 계산합니다.

## 기능

- ✅ MQTT 구독 (`home/+/sensor/#`)
- ✅ 센서 데이터 검증 및 저장
- ✅ 1분 단위 자동 집계 (min/max/avg/변화횟수)
- ✅ 오래된 데이터 자동 정리 (30일/1년)
- ✅ DB 통계 및 로깅

## 구조

```
collector/
├── collector.py          메인 프로그램
├── models.py             DB 관리 클래스
├── schema.sql            SQLite 스키마
├── collector_config.json 설정 파일
└── README.md             이 파일
```

## 설치 및 실행

### 1. 의존성 설치

```bash
cd /home/server/sensor-hub/server
pip install -r requirements.txt
```

### 2. 설정 수정

```bash
nano collector/collector_config.json
```

주요 설정:
```json
{
  "mqtt_host": "localhost",        // MQTT 브로커 주소
  "mqtt_port": 1883,
  "mqtt_user": "collector",        // MQTT 계정 (ACL 설정 필요)
  "mqtt_password": "collector456",
  "db_path": "sensor_data.db",     // SQLite DB 파일 경로
  "topics": ["home/+/sensor/#"]    // 구독 토픽
}
```

### 3. 수동 실행 (테스트)

```bash
cd server/collector
python3 collector.py
```

예상 출력:
```
2026-10-17 06:49:12 [INFO] SensorCollector: MQTT 브로커 연결 성공
2026-10-17 06:49:12 [INFO] SensorCollector: 구독: home/+/sensor/#
2026-10-17 06:49:20 [DEBUG] SensorCollector: 저장: raspberrypi/temperature=24.5°C
2026-10-17 06:49:50 [DEBUG] SensorCollector: 집계 저장: 2026-10-17 06:49:00 raspberrypi/temperature ...
```

### 4. systemd 서비스 등록 (자동 시작)

```bash
sudo nano /etc/systemd/system/sensor-collector.service
```

```ini
[Unit]
Description=Sensor Collector (MQTT → SQLite)
After=network.target
Wants=mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sensor-hub/server/collector
ExecStart=/usr/bin/python3 /home/pi/sensor-hub/server/collector/collector.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
MemoryLimit=512M

[Install]
WantedBy=multi-user.target
```

등록 및 시작:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-collector
sudo systemctl start sensor-collector
sudo systemctl status sensor-collector
```

## DB 구조

### readings 테이블 (원본 데이터, 30일 보존)

| 열 | 타입 | 설명 |
|---|---|---|
| id | INTEGER | 자동 증가 ID |
| ts | TIMESTAMP | 센서 읽은 시간 (ISO8601) |
| device | TEXT | 디바이스명 (raspberrypi) |
| sensor | TEXT | 센서종류 (temperature\|humidity\|distance) |
| value | REAL | 센서값 |
| unit | TEXT | 단위 (°C\|%\|cm) |

```sql
SELECT * FROM readings
WHERE device = 'raspberrypi' AND sensor = 'temperature'
ORDER BY ts DESC LIMIT 10;
```

### agg_1min 테이블 (1분 집계, 1년 보존)

| 열 | 타입 | 설명 |
|---|---|---|
| id | INTEGER | 자동 증가 ID |
| minute | TIMESTAMP | 분 단위 (예: 2026-10-17 06:49:00) |
| device | TEXT | 디바이스명 |
| sensor | TEXT | 센서종류 |
| min | REAL | 최솟값 |
| max | REAL | 최댓값 |
| avg | REAL | 평균값 |
| change_count | INTEGER | 이 분에 값이 몇 번 바뀌었는가 |
| sample_count | INTEGER | 이 분에 수집된 샘플 수 |

```sql
-- 최근 1시간 집계
SELECT minute, device, sensor, min, max, avg, sample_count
FROM agg_1min
WHERE device = 'raspberrypi'
AND minute > datetime('now', '-1 hour')
ORDER BY minute DESC;
```

## 운영

### 로그 확인

```bash
# 실시간 로그
tail -f ~/logs/sensor-collector.log

# systemd 로그
sudo journalctl -u sensor-collector -f
```

### DB 조회

```bash
# SQLite 접속
sqlite3 sensor_data.db

# 통계
SELECT COUNT(*) FROM readings;
SELECT COUNT(*) FROM agg_1min;

# 최근 센서 데이터
SELECT * FROM readings ORDER BY ts DESC LIMIT 10;

# 최근 집계
SELECT * FROM agg_1min ORDER BY minute DESC LIMIT 10;
```

### 수동 정리

```python
from models import SensorDB

db = SensorDB('sensor_data.db')
db.cleanup_old_data()  # 30일 이상 원본 + 1년 이상 집계 삭제
print(db.get_db_stats())
```

## 트러블슈팅

### MQTT 연결 실패

```
MQTT 연결 실패: Connection refused
```

→ Mosquitto가 실행 중인지 확인:
```bash
sudo systemctl status mosquitto
sudo mosquitto_sub -h localhost -t 'home/+/sensor/#'
```

### 센서 데이터가 저장되지 않음

```bash
# 메시지 수신 확인
mosquitto_sub -h localhost -u collector -P collector456 -t 'home/+/sensor/#'

# DB 확인
sqlite3 sensor_data.db "SELECT COUNT(*) FROM readings;"
```

### DB 파일 손상

```bash
# 인덱스 재구성
sqlite3 sensor_data.db "VACUUM; PRAGMA integrity_check;"

# 필요시 초기화
rm sensor_data.db
# collector.py 재시작 (스키마 자동 생성)
```

## 다음 단계

1. **브리지 (bridge.py)** — 1분 집계를 읽어 Dify 호출
2. **Dify 워크플로우** — LLM 요약 및 알림 발송
