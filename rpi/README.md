# 라즈베리파이 센서 퍼블리셔

DHT22 온도/습도 센서 + HC-SR04 초음파 거리 센서를 읽어 MQTT로 발행하는 퍼블리셔입니다.

## 하드웨어 구성

### 센서 배선

**DHT22 (GPIO 4)**
```
VCC  ── 3.3V
GND  ── GND
신호 ── GPIO 4 + 4.7kΩ 풀업 저항 (VCC ↔ GPIO 4)
```

**HC-SR04 (GPIO 17, 27)**
```
VCC   ── 5V
GND   ── GND
TRIG  ── GPIO 17 (3.3V)
ECHO  ── GPIO 27 (분압 회로로 5V → 3.3V 변환)
        └─ 1kΩ (ECHO) + 2kΩ (GND) 분압 권장
```

## 사전 설정

### 1. Mosquitto 브로커 설치 (라즈베리파이)

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 2. 의존성 설치

```bash
cd ~/sensor-hub/rpi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**주의:** 라즈베리파이의 기본 Python 패키지에는 `RPi.GPIO`가 포함되어 있을 수 있습니다.

### 3. 설정 파일 수정

```json
{
  "device_name": "raspberrypi",
  "mqtt_host": "localhost",
  "mqtt_port": 1883,
  "mqtt_user": null,
  "mqtt_password": null,
  "publish_interval": 10,
  "temp_threshold": 0.5,
  "distance_threshold": 3
}
```

| 항목 | 설명 |
|---|---|
| `device_name` | MQTT 토픽에 표시되는 디바이스 이름 |
| `mqtt_host` | MQTT 브로커 주소 (같은 파이면 `localhost`) |
| `mqtt_port` | MQTT 포트 (기본 1883) |
| `publish_interval` | 정기 발행 주기 (초) |
| `temp_threshold` | 온도 즉시 발행 임계값 (°C) |
| `distance_threshold` | 거리 즉시 발행 임계값 (cm) |

## 실행

### 수동 실행 (테스트)

```bash
cd ~/sensor-hub/rpi
source venv/bin/activate
python3 publisher.py
```

### systemd 서비스 등록 (자동 시작)

```bash
# 서비스 파일 복사
sudo cp sensor-publisher.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable sensor-publisher
sudo systemctl start sensor-publisher

# 상태 확인
sudo systemctl status sensor-publisher

# 로그 확인
sudo journalctl -u sensor-publisher -f
```

## MQTT 토픽 명세

퍼블리셔는 다음 토픽에 메시지를 발행합니다:

| 토픽 | 메시지 포맷 | 발행 주기 |
|---|---|---|
| `home/raspberrypi/status` | `{"device":"...", "status":"online\|offline", "ts":"..."}` | 연결 시, Last Will |
| `home/raspberrypi/sensor/temperature` | `{"device":"...", "sensor":"temperature", "value":24.5, "unit":"°C", "ts":"..."}` | 10초 주기 또는 변동 |
| `home/raspberrypi/sensor/humidity` | `{"device":"...", "sensor":"humidity", "value":65.2, "unit":"%", "ts":"..."}` | 10초 주기 |
| `home/raspberrypi/sensor/distance` | `{"device":"...", "sensor":"distance", "value":12.3, "unit":"cm", "ts":"..."}` | 10초 주기 또는 변동 |

## 테스트

### MQTT 메시지 구독 (다른 PC에서)

```bash
mosquitto_sub -h <라즈베리파이_IP> -t 'home/+/sensor/#'
```

예상 출력:
```
home/raspberrypi/sensor/temperature {"device":"raspberrypi","sensor":"temperature","value":24.5,"unit":"°C","ts":"2026-10-14T21:30:45.123456Z"}
home/raspberrypi/sensor/humidity {"device":"raspberrypi","sensor":"humidity","value":65.2,"unit":"%","ts":"2026-10-14T21:30:45.456789Z"}
home/raspberrypi/sensor/distance {"device":"raspberrypi","sensor":"distance","value":12.3,"unit":"cm","ts":"2026-10-14T21:30:46.789012Z"}
```

### 로그 확인

```bash
tail -f /var/log/sensor-publisher.log
```

## 주의 사항

1. **DHT22 읽기 간격:** 최소 2초 필요 (너무 자주 읽으면 체크섬 오류 발생)
2. **HC-SR04 분압:** ECHO 신호는 5V이므로 분압 회로 필수 (GPIO 손상 방지)
3. **권한:** `sensor-publisher.service`는 `pi` 사용자로 실행되므로 GPIO 접근 권한 필요

## 문제 해결

### DHT22 연결 오류
```
DHT22 센서 초기화 실패: ...
```
→ GPIO 핀 번호, 배선, 풀업 저항 확인

### HC-SR04 거리 이상
```
HC-SR04: ECHO 신호 수신 타임아웃
```
→ 센서 배선, ECHO 분압 회로 확인

### MQTT 연결 실패
```
MQTT 연결 실패: ...
```
→ Mosquitto 설치 및 시작 확인: `sudo systemctl status mosquitto`

## 다음 단계

1. **수집기 (collector.py)** — 서버에서 MQTT 메시지 수신 및 DB 저장
2. **브리지 (bridge.py)** — 1분 집계 및 Dify 워크플로우 호출
3. **Dify 요약 워크플로우** — LLM으로 센서 데이터 요약 및 알림 발송
