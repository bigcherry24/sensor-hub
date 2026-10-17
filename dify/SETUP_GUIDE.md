# Dify 워크플로우 구성 가이드 (v1.15.0)

두 개의 워크플로우를 Dify에 구성합니다:
1. **Sensor Summary** - 1분 요약 (정상 범위)
2. **Sensor Alert** - 긴급 경보 (임계치 초과)

---

## 📋 사전 준비

### 1. Dify 설정 확인

```bash
# Dify 서버 접속
http://your-dify-server:5000/

# 버전 확인
설정 → 정보 → Version 1.15.0
```

### 2. 알림 채널 API 키 준비

#### Slack 웹훅 URL
```
Slack → 앱 생성 → Incoming Webhooks
예: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

#### Telegram Bot
```bash
# BotFather와 대화
/newbot → MyBot → 토큰 받기
예: 123456789:ABCDefGHIjklmnoPQRstuvwxyz1234567890

# 채팅 ID 확인
curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq
```

#### Email (선택)
```
SMTP 서버: smtp.gmail.com
포트: 587
계정: your-email@gmail.com
앱 비밀번호: (Gmail 설정에서 생성)
```

---

## 🔧 Step 1: Sensor Summary 워크플로우 생성

### 1-1. 앱 생성

```
1. Dify 대시보드
2. "Create blank app" → "Workflow"
3. 앱 이름: "Sensor Summary"
4. 설명: "1분 센서 데이터 요약 및 알림"
5. "Create" 클릭
```

### 1-2. 입력 변수 설정 (User Input 노드)

**Start 노드 클릭 → Variables 추가:**

| 변수명 | 타입 | 필수 | 설명 | 입력 방식 |
|---|---|---|---|---|
| period | String | Yes | 시간 (예: 2026-10-17 17:35) | 텍스트 입력 |
| events | Object | Yes | 센서 집계 데이터 배열 | **JSON code field** |
| alert_type | String | No | 경보 타입 (summary/emergency) | 텍스트 입력 |

**주의:** `events`는 Object 타입이므로 **JSON code input field**로 나타납니다.
Bridge.py에서 JSON 배열 형식으로 전송합니다:
```json
[
  {
    "device": "raspberrypi",
    "sensor": "temperature",
    "min": 24.1,
    "max": 24.8,
    "avg": 24.5,
    "change_count": 2,
    "sample_count": 10
  }
]
```

### 1-3. 노드 추가

#### Node 1: Code (데이터 검증)
```
타입: Code
언어: Python 3
코드: (아래 붙여넣기)
```

**Python 코드:**
```python
# 입력 데이터 검증 및 포맷팅
import json

validated_events = []

for event in events:
    if isinstance(event, dict):
        validated_events.append({
            'device': event.get('device', 'unknown'),
            'sensor': event.get('sensor', 'unknown'),
            'min': float(event.get('min', 0)),
            'max': float(event.get('max', 0)),
            'avg': float(event.get('avg', 0)),
            'change_count': int(event.get('change_count', 0)),
            'sample_count': int(event.get('sample_count', 0))
        })

# 센서 요약 생성
summary_text = ""
for event in validated_events:
    summary_text += f"{event['device']}/{event['sensor']}: "
    summary_text += f"min={event['min']:.1f}, max={event['max']:.1f}, "
    summary_text += f"avg={event['avg']:.1f}, changes={event['change_count']}\n"

result = {
    'validated': True,
    'event_count': len(validated_events),
    'summary_text': summary_text,
    'events': validated_events
}
```

#### Node 2: LLM (요약 생성)
```
타입: LLM
모델: gpt-4
온도: 0.7
최대 토큰: 500

시스템 프롬프트:
"당신은 센서 데이터 분석가입니다.
라즈베리파이의 온도, 습도, 거리 센서 데이터를 분석하고 요약합니다.
요약은 3줄 이내로 작성합니다.
이상 징후가 있으면 맨 앞에 ⚠️ 표시합니다."

프롬프트:
"다음 센서 데이터를 분석하고 3줄로 요약하세요:

시간: {{period}}
데이터:
{{code_validate.summary_text}}"
```

#### Node 3: HTTP (Slack 발송)
```
타입: HTTP Request
메소드: POST
URL: {{env.SLACK_WEBHOOK_URL}}

Headers:
- Content-Type: application/json

Body (JSON):
{
  "text": "🌡️ 센서 요약 ({{period}})",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "{{llm_summary}}"
      }
    },
    {
      "type": "divider"
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": "이벤트: {{code_validate.event_count}}개"
        }
      ]
    }
  ]
}
```

#### Node 4: HTTP (Telegram 발송)
```
타입: HTTP Request
메소드: POST
URL: https://api.telegram.org/bot{{env.TELEGRAM_BOT_TOKEN}}/sendMessage

Body (JSON):
{
  "chat_id": "{{env.TELEGRAM_CHAT_ID}}",
  "text": "🌡️ 센서 요약 ({{period}})\n\n{{llm_summary}}\n\n이벤트: {{code_validate.event_count}}개"
}
```

#### Node 5: HTTP (Email 발송) - 선택
```
타입: HTTP Request
메소드: POST
URL: {{env.SMTP_SERVER_URL}}

Body (JSON):
{
  "to": "{{env.EMAIL_RECIPIENT}}",
  "subject": "[센서] 1분 요약 - {{period}}",
  "body": "<html>...</html>"
}
```

### 1-4. 출력 설정

**End 노드 설정:**
```
Status: String
Summary: String
Sent Count: Number
```

### 1-5. 환경 변수 저장

```
설정 → 환경 변수 → 추가

SLACK_WEBHOOK_URL: https://hooks.slack.com/services/...
TELEGRAM_BOT_TOKEN: 123456789:ABC...
TELEGRAM_CHAT_ID: -1234567890
SMTP_SERVER_URL: (선택)
EMAIL_RECIPIENT: (선택)
```

### 1-6. API 키 복사

```
"API" 탭 클릭 → "API Key" 복사
예: app-5f8c9a2b1d4e6g9h2j3k4l5m
```

---

## 🔧 Step 2: Sensor Alert 워크플로우 생성

### 2-1 ~ 2-6: Step 1과 동일한 절차

**1-2 입력 변수 설정 (동일):**

| 변수명 | 타입 | 필수 | 입력 방식 |
|---|---|---|---|
| period | String | Yes | 텍스트 입력 |
| events | Object | Yes | **JSON code field** |
| alert_type | String | Yes | 텍스트 입력 |

**차이점:**
- 앱 이름: "Sensor Alert"
- Code 노드: 경보 포맷팅 (Red color)
- LLM 프롬프트: 긴급 메시지
- Slack: 빨간색 첨부 파일 (`"color": "#FF0000"`)
- Telegram: 🚨 이모지
- Email: `[긴급]` 제목 접두어

---

## 📁 최종 파일 저장

두 워크플로우 DSL을 저장하세요:

```bash
dify/
├── summary-workflow.yml    (Sensor Summary)
├── alert-workflow.yml      (Sensor Alert)
├── SETUP_GUIDE.md          (이 파일)
└── ENVIRONMENT_VARS.txt    (API 키 기록용)
```

---

## ✅ 테스트

### API 키 확인

```bash
# Sensor Summary API 키
DIFY_SUMMARY_KEY="app-xxxxx"

# Sensor Alert API 키
DIFY_ALERT_KEY="app-yyyyy"
```

### 수동 테스트

```bash
# Sensor Summary 호출
curl -X POST "http://your-dify-server:5000/v1/workflows/run" \
  -H "Authorization: Bearer $DIFY_SUMMARY_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    },
    "response_mode": "blocking",
    "user": "sensor-bridge"
  }'

# Sensor Alert 호출 (임계치 초과)
curl -X POST "http://your-dify-server:5000/v1/workflows/run" \
  -H "Authorization: Bearer $DIFY_ALERT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "period": "2026-10-17 17:35",
      "events": [
        {
          "device": "raspberrypi",
          "sensor": "temperature",
          "min": 28.0,
          "max": 32.5,
          "avg": 30.5,
          "change_count": 5,
          "sample_count": 10
        }
      ],
      "alert_type": "emergency"
    },
    "response_mode": "blocking",
    "user": "sensor-bridge"
  }'
```

### bridge.py에 API 키 설정

```bash
# server/bridge/.env 수정
DIFY_BASE_URL=http://192.168.0.100:5000
DIFY_SUMMARY_API_KEY=app-xxxxx
DIFY_ALERT_API_KEY=app-yyyyy
```

---

## 🚀 완성 체크리스트

- [ ] Sensor Summary 워크플로우 생성 및 테스트
- [ ] Sensor Alert 워크플로우 생성 및 테스트
- [ ] 환경 변수 설정 (Slack, Telegram, Email)
- [ ] API 키 발급 및 기록
- [ ] bridge.py .env 파일 업데이트
- [ ] cron 또는 systemd 타이머 등록
- [ ] end-to-end 통합 테스트

---

## 💡 트러블슈팅

### Dify API 호출 실패
```
ERROR: 401 Unauthorized
→ API 키 확인, DIFY_BASE_URL 확인
```

### Slack 메시지 수신 안 됨
```
ERROR: 403 Forbidden
→ 웹훅 URL 확인, 만료 여부 확인
```

### Telegram 메시지 수신 안 됨
```
ERROR: 404 Not Found
→ 봇 토큰, 채팅 ID 확인
```

---

**이제 모든 5단계가 완성되었습니다! 🎉**
