# 센서 허브: 라즈베리파이 → 서버 → Dify 알림 시스템

**라즈베리파이**에서 센서 데이터를 수집하여 **MQTT로 발행**하고, **서버에서 수집/집계**한 후 **Dify로 요약 및 알림**하는 end-to-end 시스템입니다.

## 🎯 구성도

```
[라즈베리파이]
  DHT22 (온도/습도)
  HC-SR04 (거리)
         │
         ├─ GPIO 읽기
         │
         └─ publisher.py
                │
                ├─ MQTT publish (10초 + 변동 시)
                │
                ▼
          [MQTT 브로커]
          (Mosquitto)
                │
                ├─ subscribe
                │
                ▼
          [서버: Collector]
                │
                ├─ readings 테이블 (원본, 30일)
                ├─ agg_1min 테이블 (집계, 1년)
                │
                └─ 1분마다 집계
                     │
                     ▼
          [서버: Bridge]
                │
                ├─ Dify Workflow API 호출
                │
                ▼
          [Dify (자체 호스팅)]
                │
                ├─ Code 노드 (수치 계산)
                ├─ LLM 노드 (요약 생성)
                ├─ Condition (이상 판정)
                │
                ▼
          [알림 채널]
          ├─ Slack
          ├─ Telegram
          └─ Email
```

---

## 📦 프로젝트 구조

```
sensor-hub/
├── CLAUDE.md                    프로젝트 지침
├── README.md                    이 파일
│
├── rpi/                         라즈베리파이 퍼블리셔
│   ├── sensors/
│   │   ├── dht.py              DHT22 읽기
│   │   └── distance.py         HC-SR04 읽기
│   ├── publisher.py            MQTT 퍼블리셔
│   ├── config.json             설정
│   ├── requirements.txt         의존성
│   ├── sensor-publisher.service systemd 서비스
│   └── README.md               설정 가이드
│
├── server/                      서버 (수집/브리지)
│   ├── collector/
│   │   ├── collector.py        MQTT 수집기
│   │   ├── models.py           DB 관리 클래스
│   │   ├── schema.sql          SQLite 스키마
│   │   ├── collector_config.json 설정
│   │   └── README.md           실행 가이드
│   ├── bridge/                 (다음 단계)
│   │   ├── bridge.py
│   │   ├── .env.example
│   │   └── requirements.txt
│   ├── docker-compose.yml      (옵션)
│   └── requirements.txt         서버 전체 의존성
│
├── shared/                      라즈베리파이 + 서버 공유
│   ├── mqtt_topics.json        토픽 정의
│   └── message_schema.py       메시지 스키마 (진행 중)
│
└── dify/                        (다음 단계)
    ├── summary-workflow.yml    1분 요약 워크플로우
    ├── alert-workflow.yml      긴급 알림 워크플로우
    └── prompts.md              프롬프트 문서
```

---

## 🚀 빠른 시작

### 라즈베리파이

```bash
# 저장소 클론
git clone https://github.com/bigcherry24/sensor-hub.git
cd sensor-hub/rpi

# 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 테스트
python3 publisher.py

# 자동 시작 등록
sudo cp sensor-publisher.service /etc/systemd/system/
sudo systemctl enable sensor-publisher
sudo systemctl start sensor-publisher
```

자세히: [rpi/README.md](rpi/README.md)

---

### 서버 (Ubuntu/Debian)

#### 1단계: MQTT 브로커 설치

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# ACL 설정 (선택)
# → 참고: rpi/README.md의 "MQTT ACL 설정" 섹션
```

#### 2단계: Collector 실행

```bash
# 저장소 클론
git clone https://github.com/bigcherry24/sensor-hub.git
cd sensor-hub/server

# 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 수집기 실행
cd collector
python3 collector.py

# 자동 시작 등록
sudo cp /path/to/sensor-collector.service /etc/systemd/system/
sudo systemctl enable sensor-collector
sudo systemctl start sensor-collector
```

자세히: [server/collector/README.md](server/collector/README.md)

---

## 📊 데이터 흐름

### 1️⃣ 센서 데이터 발행 (라즈베리파이)

```json
{
  "device": "raspberrypi",
  "sensor": "temperature",
  "value": 24.5,
  "unit": "°C",
  "ts": "2026-10-17T06:49:12Z"
}
```

→ MQTT: `home/raspberrypi/sensor/temperature`

### 2️⃣ 데이터 수집 (서버)

**readings 테이블**
```sql
ts                    | device       | sensor      | value | unit
2026-10-17T06:49:12Z | raspberrypi  | temperature | 24.5  | °C
2026-10-17T06:49:22Z | raspberrypi  | temperature | 24.6  | °C
2026-10-17T06:49:32Z | raspberrypi  | temperature | 24.5  | °C
```

### 3️⃣ 1분 집계 (서버)

**agg_1min 테이블**
```
minute                | device      | sensor      | min  | max  | avg  | change_count | sample_count
2026-10-17 06:49:00 | raspberrypi | temperature | 24.5 | 24.6 | 24.5 | 1            | 3
```

### 4️⃣ Dify로 요약 (다음 단계)

```
최근 1분 온도: 최소 24.5°C, 최대 24.6°C, 평균 24.5°C
거리: 최소 11.8cm, 최대 12.9cm, 평균 12.3cm, 변동 4회 ⚠️
```

---

## 🔧 설정 파일

### `rpi/config.json`

```json
{
  "device_name": "raspberrypi",
  "mqtt_host": "192.168.1.100",    // 서버 IP
  "mqtt_port": 1883,
  "mqtt_user": "raspberrypi",
  "mqtt_password": "sensor123",
  "publish_interval": 10,           // 10초
  "temp_threshold": 0.5,            // 0.5°C 변동 시 즉시 발행
  "distance_threshold": 3            // 3cm 변동 시 즉시 발행
}
```

### `server/collector/collector_config.json`

```json
{
  "mqtt_host": "localhost",
  "mqtt_port": 1883,
  "mqtt_user": "collector",
  "mqtt_password": "collector456",
  "db_path": "sensor_data.db",
  "topics": ["home/+/sensor/#"]
}
```

---

## 📈 진행 상황

| 단계 | 완료 | 항목 |
|---|---|---|
| 1 | ✅ | 센서 모듈 (DHT22, HC-SR04) |
| 2 | ✅ | MQTT 브로커 (Mosquitto) |
| 3 | ✅ | 퍼블리셔 (publisher.py) |
| 4 | ✅ | 수집기 (collector.py) + SQLite |
| 5 | 🔜 | 브리지 (bridge.py) + Dify 연동 |
| 6 | 🔜 | Dify 워크플로우 (요약, 알림) |
| 7 | 🔜 | 알림 채널 (Slack, Telegram, Email) |
| 8 | 🔜 | 통합 테스트 및 운영 |

---

## 🛠️ 개발 가이드

### 로컬 테스트

```bash
# 라즈베리파이 시뮬레이션 (가짜 메시지 발행)
python3 fake_publisher.py

# 수집기 테스트
python3 server/collector/collector.py

# DB 확인
sqlite3 server/collector/sensor_data.db "SELECT * FROM readings LIMIT 5;"
```

### Git 워크플로우

```bash
# 새 기능 브랜치
git checkout -b feature/bridge-implementation

# 변경사항 커밋
git add .
git commit -m "feat: bridge 구현"

# main에 병합
git push origin feature/bridge-implementation
# → GitHub에서 PR 생성
```

---

## 📖 참고

- [라즈베리파이 설정](rpi/README.md)
- [서버 수집기 설정](server/collector/README.md)
- [MQTT 토픽 정의](shared/mqtt_topics.json)
- [프로젝트 지침](CLAUDE.md)

---

## 📝 라이선스

MIT

---

## 🤝 기여

이슈, PR 환영합니다!

---

**마지막 업데이트:** 2026-10-17
