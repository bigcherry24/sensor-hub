# 센서 허브 프로젝트 진행 현황

> 최종 업데이트: 2026-10-18

---

## 📊 5단계 구현 현황

| 단계 | 항목 | 상태 | 설명 |
|---|---|---|---|
| **1** | Raspberry Pi Publisher | ✅ 완료 | DHT22, HC-SR04 센서 데이터 수집 및 MQTT 발행 |
| **2** | MQTT 브로커 (Mosquitto) | ✅ 완료 | ACL 설정, 사용자 인증 구성 |
| **3** | Server Collector + SQLite | ✅ 완료 | MQTT 구독, DB 저장, 1분 집계 |
| **4** | Bridge + Dify 연동 | ✅ 완료 | DB 읽기 → Dify Workflow 호출 |
| **5** | Dify 워크플로우 | ✅ 완료 | 2개 워크플로우 DSL 작성 |

---

## 🔧 최근 변경 내역 (2026-10-17~18)

### Bridge.py 수정

```python
# ✅ events를 Object(dict) 형식으로 변환
events_dict = {
    'items': aggregations,     # 센서 집계 배열
    'count': len(aggregations),
    'timestamp': period_str
}

payload = {
    'inputs': {
        'period': period_str,
        'events': events_dict,  # ← Dict 형식
        'alert_type': '...'
    }
}

# ✅ Payload 전문을 로그로 출력 (디버깅)
logger.info(f"📤 Payload 전문:\n{json.dumps(payload, indent=2, default=str)}")
```

### Dify Code 노드 형식 (최종)

```python
def main(period, events, alert_type):
    """입력 데이터 처리"""
    
    # events에서 배열 추출
    if isinstance(events, dict) and 'items' in events:
        aggregations = events['items']
    elif isinstance(events, list):
        aggregations = events
    else:
        aggregations = []
    
    # ... 로직 ...
    
    # ✅ "result" 키로 감싸야 Output Variables에 매핑됨
    return {
        "result": {
            'validated': True,
            'event_count': len(aggregations),
            'summary_text': summary_text,
            'events': aggregations
        }
    }
```

### Dify User Input 노드 설정

| 변수명 | 타입 | 입력 방식 | 설명 |
|---|---|---|---|
| period | String | 텍스트 입력 | 시간 (예: 2026-10-17 13:46) |
| events | **Object** | **JSON code field** | events['items']로 배열 추출 |
| alert_type | String | 텍스트 입력 | summary 또는 emergency |

---

## 📋 현재 디렉토리 구조

```
sensor-hub/
├── rpi/                          # Raspberry Pi 센서 발행
│   ├── publisher.py
│   ├── sensors/
│   │   ├── dht.py
│   │   └── distance.py
│   ├── config.json
│   └── requirements.txt
│
├── server/                        # 서버측 수집 및 처리
│   ├── collector/
│   │   ├── collector.py
│   │   ├── models.py
│   │   ├── schema.sql
│   │   ├── collector_config.json
│   │   ├── check_db.py
│   │   └── sensor_data.db
│   │
│   └── bridge/
│       ├── bridge.py             # Dify 연동
│       ├── bridge_config.json
│       ├── .env.example
│       ├── README.md
│       └── requirements.txt
│
└── dify/                          # Dify 워크플로우
    ├── summary-workflow.yml       # 1분 요약 워크플로우
    ├── alert-workflow.yml         # 긴급 경보 워크플로우
    ├── SETUP_GUIDE.md             # Dify 구성 가이드
    └── scratchpad.md              # 이 파일
```

---

## 🚀 다음 단계 (작업 예정)

### Phase A: Dify 워크플로우 수동 구성 (긴급)

**Sensor Summary 워크플로우:**
```
1. [✅] YAML/DSL 작성 완료
2. [ ] Dify UI에서 수동 구성
   - Start 노드 (User Input) 추가
   - Code 노드 (code_validate) 추가
   - LLM 노드 추가
   - Condition 노드 추가
   - HTTP 노드 (Slack/Telegram/Email) 추가
   - End 노드 추가
3. [ ] 환경 변수 설정 (Slack, Telegram, Email)
4. [ ] API 키 발급 및 .env 설정
5. [ ] 수동 테스트 (curl로 API 호출)
```

**Sensor Alert 워크플로우:**
```
1. [✅] YAML/DSL 작성 완료
2. [ ] Dify UI에서 수동 구성 (Summary와 동일한 방식)
```

### Phase B: end-to-end 테스트

```bash
# Bridge 로컬 테스트
python3 /home/aurakim/workspace/sotDocMngPrj/server/bridge/bridge.py --test

# 실제 데이터로 테스트
crontab -e  # 1분 단위 실행 등록

# 로그 확인
tail -f ~/logs/sensor-bridge.log
```

### Phase C: 운영 설정

```bash
# systemd 타이머 등록
sudo systemctl enable sensor-bridge.timer
sudo systemctl start sensor-bridge.timer

# 또는 cron 등록
*/1 * * * * /usr/bin/python3 /path/to/bridge.py >> /var/log/sensor-bridge.log 2>&1
```

---

## ⚠️ 주의사항

### 1. Dify User Input 노드 설정

❌ **Array 타입이 없습니다** (Array[File]만 존재)
✅ **Object 타입** (JSON code field)를 사용하고, events['items']로 배열 접근

### 2. Code 노드 형식

❌ 단순 스크립트 형식
✅ `def main(param1, param2):` 함수 형식 필수

### 3. Return 값 매핑

❌ `return {'key': 'value'}`
✅ `return {"result": {...}}` (Output Variable 이름과 일치)

### 4. Bridge.py 환경 변수

```bash
# server/bridge/.env 설정 필수
DIFY_BASE_URL=https://your-dify-server:port
DIFY_SUMMARY_API_KEY=app-xxxxx
DIFY_ALERT_API_KEY=app-yyyyy
```

### 5. Dify 워크플로우 공유

현재 YAML/DSL 형식으로 작성되었으나, **Dify UI에서 수동으로 구성**해야 합니다.
(YAML import 기능 미확인)

---

## 📌 주요 GitHub 커밋

| 커밋 | 내용 |
|---|---|
| [34cc67f](https://github.com/bigcherry24/sensor-hub/commit/34cc67f) | Dify 워크플로우 YAML 생성 |
| [51f1686](https://github.com/bigcherry24/sensor-hub/commit/51f1686) | Webhook Trigger 시도 (실패) |
| [0def517](https://github.com/bigcherry24/sensor-hub/commit/0def517) | API 방식으로 복원 |
| [520538a](https://github.com/bigcherry24/sensor-hub/commit/520538a) | events를 dict로 변환 |
| [0876b00](https://github.com/bigcherry24/sensor-hub/commit/0876b00) | Code 노드 변수 감지 개선 |
| [debe5bb](https://github.com/bigcherry24/sensor-hub/commit/debe5bb) | main() 함수 형식 적용 |
| [0d69c82](https://github.com/bigcherry24/sensor-hub/commit/0d69c82) | return {"result": {...}} 형식 적용 |

---

## 📚 참고 자료

- [Dify 공식 문서](https://docs.dify.ai/)
- [Dify 워크플로우 가이드](https://docs.dify.ai/guides/workflow)
- [docToolchain 문서](https://doctoolchain.org/)
- [Platty 가이드](https://github.com/paradigmshift-labs/platty/blob/main/guide/ko/)

---

## 💡 일일 작업 체크리스트

### [Day 1] 2026-10-18

- [x] Bridge.py events 형식 수정 (dict로 변환)
- [x] Code 노드 변수 감지 로직 추가
- [x] main() 함수 형식으로 변경
- [x] return {"result": {...}} 형식 적용
- [ ] **다음: Dify UI에서 워크플로우 수동 구성**

### [Day 2] 예정

- [ ] Sensor Summary 워크플로우 구성
- [ ] Sensor Alert 워크플로우 구성
- [ ] 환경 변수 설정 (Slack, Telegram, Email)
- [ ] 수동 테스트

### [Day 3] 예정

- [ ] end-to-end 통합 테스트
- [ ] 로그 검증
- [ ] systemd 타이머 등록

---

## 🎯 최종 목표

```
Raspberry Pi 센서 데이터
    ↓
MQTT 발행 (10초/임계치 초과)
    ↓
Server Collector (구독 + 저장)
    ↓
SQLite DB (1분 집계)
    ↓
Bridge (변동/경보 감지)
    ↓
Dify Workflow (LLM 요약)
    ↓
Slack/Telegram/Email (알림 발송)
```

✅ **구현 완료** → 다음: Dify 워크플로우 수동 구성

---

**작성자:** Claude Haiku 4.5  
**마지막 업데이트:** 2026-10-18  
**상태:** 진행 중 (Phase A: Dify 워크플로우 구성 대기)
