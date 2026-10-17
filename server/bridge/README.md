# 센서 데이터 브리지

SQLite DB의 1분 집계 데이터를 읽어 **Dify Workflow로 전송**합니다.

## 기능

- ✅ 1분마다 실행 (cron)
- ✅ DB에서 최근 1분 집계 조회
- ✅ 변동 판정 (temperature, distance, humidity)
- ✅ 임계치 초과 감지 (긴급 경보)
- ✅ Dify Workflow API 호출 (요약/경보)

## 구조

```
bridge/
├── bridge.py              메인 프로그램
├── bridge_config.json    설정 파일
├── .env.example          환경 변수 예시
├── requirements.txt      의존성
└── README.md            이 파일
```

## 설치 및 설정

### 1. 의존성 설치

```bash
cd /home/server/sensor-hub/server/bridge
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 편집
nano .env
```

설정 값:
```
DIFY_BASE_URL=http://192.168.0.100:5000
DIFY_SUMMARY_API_KEY=<Dify 요약 워크플로우 API 키>
DIFY_ALERT_API_KEY=<Dify 경보 워크플로우 API 키>
```

### 3. 설정 파일 수정

```bash
nano bridge_config.json
```

| 설정 | 설명 | 기본값 |
|---|---|---|
| `db_path` | 센서 DB 경로 | `../collector/sensor_data.db` |
| `temp_change_threshold` | 온도 변동 임계값 (°C) | 0.5 |
| `distance_change_threshold` | 거리 변동 임계값 (cm) | 3.0 |
| `temp_alert_threshold` | 온도 경보 임계값 (°C) | 30.0 |
| `distance_alert_threshold` | 거리 경보 임계값 (cm) | 5.0 |

## 실행

### 테스트 모드 (지금 바로 실행)

```bash
python3 bridge.py --test
```

**출력 예:**
```
2026-10-17 17:35:00 [INFO] 브리지 1분 처리 시작
2026-10-17 17:35:00 [INFO]   📊 raspberrypi/temperature: min=24.1, max=24.8, avg=24.5, changes=2
2026-10-17 17:35:00 [INFO]     📈 유의미한 변동 감지
2026-10-17 17:35:00 [INFO] 📨 요약 발송: 1개 센서
2026-10-17 17:35:01 [INFO] ✅ Dify 응답 성공
```

### cron 등록 (자동 실행)

```bash
# crontab 편집
crontab -e

# 1분마다 실행
* * * * * /usr/bin/python3 /home/server/sensor-hub/server/bridge/bridge.py >> /var/log/sensor-bridge-cron.log 2>&1
```

**또는 systemd 타이머** (권장):

```bash
sudo nano /etc/systemd/system/sensor-bridge.service
```

```ini
[Unit]
Description=Sensor Data Bridge to Dify
After=network.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/server/sensor-hub/server/bridge
ExecStart=/usr/bin/python3 /home/server/sensor-hub/server/bridge/bridge.py
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/sensor-bridge.timer
```

```ini
[Unit]
Description=Run Sensor Bridge every minute
Requires=sensor-bridge.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Persistent=true

[Install]
WantedBy=timers.target
```

활성화:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-bridge.timer
sudo systemctl start sensor-bridge.timer
sudo systemctl status sensor-bridge.timer
```

## Dify 워크플로우

### 요약 워크플로우 (summary-workflow)

**입력:**
```json
{
  "inputs": {
    "period": "2026-10-17 17:35",
    "events": [
      {
        "device": "raspberrypi",
        "sensor": "temperature",
        "min": 24.1,
        "max": 24.8,
        "avg": 24.5,
        "change_count": 2,
        "sample_count": 10
      }
    ],
    "alert_type": "summary"
  }
}
```

**처리:**
1. Start 노드: inputs 필드에서 수신
2. Code 노드: 수치 검증
3. LLM 노드: "최근 1분 온도 변화: 24.1~24.8°C, 평균 24.5°C. 변동 2회."
4. Condition: 이상 판정 (⚠️)
5. HTTP 노드: Slack, Telegram, Email 발송

### 경보 워크플로우 (alert-workflow)

**입력:** 동일 (alert_type = "emergency")

**처리:**
1. Start 노드: inputs 필드에서 수신
2. 즉시 경보 포맷팅
3. 모든 채널 동시 발송 (🚨)

## 로그 확인

```bash
# 실시간 로그
tail -f ~/logs/sensor-bridge.log

# systemd 로그
sudo journalctl -u sensor-bridge.service -f
```

## 문제 해결

### Dify 연결 실패

```
ERROR: Dify 호출 실패: Connection refused
```

→ Dify 서버가 실행 중인지 확인:
```bash
curl http://192.168.0.100:5000/api/status
```

### API 키 오류

```
ERROR: Dify API 키 없음
```

→ .env 파일에 API 키가 설정되어 있는지 확인:
```bash
cat .env | grep DIFY_
```

### DB 파일 없음

```
ERROR: 센서 DB 초기화 실패
```

→ collector.py가 실행 중이고 데이터를 수집 중인지 확인:
```bash
ls -la ../collector/sensor_data.db
```

## 다음 단계

1. **Dify 워크플로우 구성** - LLM 요약 노드와 알림 채널 설정
2. **알림 채널 연동** - Slack, Telegram, Email 등록
3. **통합 테스트** - end-to-end 데이터 흐름 검증
