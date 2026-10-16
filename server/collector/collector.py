#!/usr/bin/env python3
"""
센서 수집기 — MQTT 메시지 수신 및 SQLite 저장
- home/+/sensor/# 구독
- 센서 데이터 검증 및 저장
- 1분 단위 집계 계산
- 오래된 데이터 자동 정리
"""

import json
import logging
import time
import signal
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import paho.mqtt.client as mqtt

from models import SensorDB


# 로깅 설정
log_dir = Path.home() / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'sensor-collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SensorCollector:
    """MQTT 센서 데이터 수집기"""

    def __init__(self, config_file='collector_config.json'):
        self.config = self._load_config(config_file)
        self.mqtt_host = self.config['mqtt_host']
        self.mqtt_port = self.config['mqtt_port']
        self.mqtt_user = self.config.get('mqtt_user')
        self.mqtt_password = self.config.get('mqtt_password')

        # DB 초기화
        db_path = self.config.get('db_path', 'sensor_data.db')
        self.db = SensorDB(db_path)

        # 1분 집계 추적 (메모리)
        self.minute_data = defaultdict(list)  # {(device, sensor, minute): [values]}
        self.minute_change_count = defaultdict(int)  # {(device, sensor, minute): count}
        self.last_values = {}  # {(device, sensor): last_value}

        # MQTT 클라이언트
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # 마지막 정리 시간
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 3600  # 1시간마다

        # 마지막 통계 시간
        self.last_stats_time = time.time()
        self.stats_interval = 600  # 10분마다

        logger.info(f"SensorCollector 초기화: {self.mqtt_host}:{self.mqtt_port}")

    def _load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file) as f:
                config = json.load(f)
            logger.info(f"설정 로드: {config_file}")
            return config
        except FileNotFoundError:
            logger.warning(f"설정 파일 없음: {config_file}. 기본값 사용.")
            return {
                'mqtt_host': 'localhost',
                'mqtt_port': 1883,
                'mqtt_user': None,
                'mqtt_password': None,
                'db_path': 'sensor_data.db',
                'topics': ['home/+/sensor/#'],
            }

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """MQTT 연결 콜백"""
        if reason_code == 0:
            logger.info(f"MQTT 브로커 연결 성공: {self.mqtt_host}:{self.mqtt_port}")
            # 토픽 구독
            topics = self.config.get('topics', ['home/+/sensor/#'])
            for topic in topics:
                client.subscribe(topic, qos=1)
                logger.info(f"구독: {topic}")
        else:
            logger.error(f"MQTT 연결 실패: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """MQTT 연결 해제 콜백"""
        logger.warning(f"MQTT 브로커 연결 해제: {reason_code}")

    def _on_message(self, client, userdata, msg):
        """MQTT 메시지 수신 콜백"""
        try:
            payload = json.loads(msg.payload.decode())
            self._process_message(msg.topic, payload)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {msg.topic} = {msg.payload}")
        except Exception as e:
            logger.error(f"메시지 처리 중 오류: {e}")

    def _process_message(self, topic: str, payload: dict):
        """센서 메시지 검증 및 저장"""
        # 필수 필드 확인
        required_fields = ['device', 'sensor', 'value', 'unit', 'ts']
        if not all(field in payload for field in required_fields):
            logger.warning(f"필드 누락: {topic} = {payload}")
            return

        device = payload['device']
        sensor = payload['sensor']
        value = payload['value']
        unit = payload['unit']
        ts = payload['ts']

        # 센서값 타입 확인
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"센서값 타입 오류: {device}/{sensor} = {value}")
            return

        # DB 저장
        try:
            self.db.insert_reading(device, sensor, value, unit, ts)

            # 1분 집계용 메모리에 기록
            self._track_for_aggregation(device, sensor, value, ts)

            # 변화 추적 (임계값 판정용)
            self._track_change(device, sensor, value)

        except Exception as e:
            logger.error(f"데이터 저장 실패: {e}")

    def _track_for_aggregation(self, device: str, sensor: str, value: float, ts: str):
        """1분 집계 데이터 추적"""
        try:
            # ts에서 분 단위 추출 (예: 2026-10-17T06:49:12Z → 2026-10-17 06:49:00)
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            minute_str = dt.strftime('%Y-%m-%d %H:%M:00')

            key = (device, sensor, minute_str)
            self.minute_data[key].append(value)
        except Exception as e:
            logger.error(f"집계 추적 실패: {e}")

    def _track_change(self, device: str, sensor: str, value: float):
        """센서값 변화 추적 (변화 횟수 계산용)"""
        key = (device, sensor)

        if key not in self.last_values:
            self.last_values[key] = value
        else:
            if self.last_values[key] != value:
                # 변화 횟수 증가
                minute_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:00')
                agg_key = (device, sensor, minute_str)
                self.minute_change_count[agg_key] += 1
                self.last_values[key] = value

    def calculate_and_save_aggregations(self):
        """1분 집계 계산 및 저장"""
        now = datetime.utcnow()
        current_minute = now.strftime('%Y-%m-%d %H:%M:00')

        # 지난 분의 데이터만 집계 (현재 분은 진행 중)
        previous_minute = (now - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:00')

        try:
            for (device, sensor, minute_str), values in list(self.minute_data.items()):
                # 지난 분만 저장
                if minute_str != current_minute and values:
                    min_val = min(values)
                    max_val = max(values)
                    avg_val = sum(values) / len(values)
                    change_count = self.minute_change_count.get((device, sensor, minute_str), 0)
                    sample_count = len(values)

                    self.db.insert_aggregation(
                        minute_str, device, sensor,
                        min_val, max_val, avg_val,
                        change_count, sample_count
                    )

                    # 메모리에서 제거
                    del self.minute_data[(device, sensor, minute_str)]
                    if (device, sensor, minute_str) in self.minute_change_count:
                        del self.minute_change_count[(device, sensor, minute_str)]

        except Exception as e:
            logger.error(f"집계 계산 실패: {e}")

    def connect(self):
        """MQTT 브로커 연결"""
        try:
            if self.mqtt_user and self.mqtt_password:
                self.client.username_pw_set(self.mqtt_user, self.mqtt_password)

            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.client.loop_start()
            logger.info("MQTT 연결 시작...")
        except Exception as e:
            logger.error(f"MQTT 연결 실패: {e}")
            raise

    def disconnect(self):
        """MQTT 연결 해제"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT 연결 해제")
        except Exception as e:
            logger.warning(f"MQTT 연결 해제 중 오류: {e}")

    def run(self):
        """메인 루프"""
        logger.info("센서 수집기 시작")

        try:
            self.connect()
            time.sleep(2)  # 연결 안정화

            while True:
                now = time.time()

                # 1분마다 집계 계산
                self.calculate_and_save_aggregations()

                # 1시간마다 오래된 데이터 정리
                if now - self.last_cleanup_time > self.cleanup_interval:
                    self.db.cleanup_old_data()
                    self.last_cleanup_time = now

                # 10분마다 통계 출력
                if now - self.last_stats_time > self.stats_interval:
                    stats = self.db.get_db_stats()
                    logger.info(f"DB 통계: readings={stats.get('total_readings', 0)}, "
                               f"agg_1min={stats.get('total_aggregations', 0)}")
                    self.last_stats_time = now

                time.sleep(5)  # 5초마다 체크

        except KeyboardInterrupt:
            logger.info("사용자에 의해 종료 요청")
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        """리소스 정리"""
        logger.info("리소스 정리 중...")
        try:
            self.disconnect()
            self.db.close()
            logger.info("센서 수집기 종료")
        except Exception as e:
            logger.error(f"정리 중 오류: {e}")


def signal_handler(sig, frame):
    """시그널 핸들러"""
    logger.info("신호 수신: 프로그램 종료")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    collector = SensorCollector('collector_config.json')
    collector.run()
