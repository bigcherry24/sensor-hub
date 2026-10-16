#!/usr/bin/env python3
"""
라즈베리파이 센서 퍼블리셔
- DHT22 (온도/습도) + HC-SR04 (거리) → MQTT publish
- 10초 주기 + 임계값 초과 시 즉시 발행
- Last Will로 offline 상태 자동 발행
"""

import os
import json
import logging
import time
import signal
import sys
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from sensors.dht import DHT22Reader
from sensors.distance import HC_SR04Reader

os.makedirs(os.path.expanduser('~/logs'), exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.expanduser('~/logs/sensor-publisher.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SensorPublisher:
    """센서 데이터 MQTT 퍼블리셔"""

    def __init__(self, config_file='config.json'):
        self.config = self._load_config(config_file)
        self.device_name = self.config['device_name']
        self.mqtt_host = self.config['mqtt_host']
        self.mqtt_port = self.config['mqtt_port']
        self.mqtt_user = self.config.get('mqtt_user')
        self.mqtt_password = self.config.get('mqtt_password')

        # 발행 정책
        self.publish_interval = self.config['publish_interval']  # 10초
        self.temp_threshold = self.config['temp_threshold']      # 0.5°C
        self.distance_threshold = self.config['distance_threshold']  # 3cm

        # 마지막 발행 값
        self.last_temp = None
        self.last_humidity = None
        self.last_distance = None
        self.last_publish_time = 0

        # 센서 초기화
        self.dht = DHT22Reader(gpio_pin=4)  # GPIO 4
        self.distance = HC_SR04Reader(trig_pin=17, echo_pin=27)  # GPIO 17, 27

        # MQTT 클라이언트
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # Last Will 설정 (연결 끊김 시 자동으로 offline 발행)
        will_topic = f'home/{self.device_name}/status'
        will_payload = json.dumps({
            'device': self.device_name,
            'status': 'offline',
            'ts': datetime.utcnow().isoformat() + 'Z'
        })
        self.client.will_set(will_topic, will_payload, qos=1, retain=True)

        logger.info(f"SensorPublisher 초기화: {self.device_name}")

    def _load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file) as f:
                config = json.load(f)
            logger.info(f"설정 로드: {config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"설정 파일 없음: {config_file}. 기본값 사용.")
            return {
                'device_name': 'raspberrypi',
                'mqtt_host': 'localhost',
                'mqtt_port': 1883,
                'mqtt_user': None,
                'mqtt_password': None,
                'publish_interval': 10,      # 10초
                'temp_threshold': 0.5,       # 0.5°C
                'distance_threshold': 3,     # 3cm
            }

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """MQTT 연결 콜백"""
        if reason_code == 0:
            logger.info(f"MQTT 브로커 연결 성공: {self.mqtt_host}:{self.mqtt_port}")
            # 연결 후 online 상태 발행
            online_topic = f'home/{self.device_name}/status'
            online_payload = json.dumps({
                'device': self.device_name,
                'status': 'online',
                'ts': datetime.utcnow().isoformat() + 'Z'
            })
            client.publish(online_topic, online_payload, qos=1, retain=True)
        else:
            logger.error(f"MQTT 연결 실패: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """MQTT 연결 해제 콜백"""
        logger.warning(f"MQTT 브로커 연결 해제: {reason_code}")

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        """MQTT 발행 완료 콜백"""
        logger.debug(f"MQTT 메시지 발행 완료: mid={mid}")

    def connect(self):
        """MQTT 브로커에 연결"""
        try:
            if self.mqtt_user and self.mqtt_password:
                self.client.username_pw_set(self.mqtt_user, self.mqtt_password)

            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.client.loop_start()  # 백그라운드에서 연결 유지
            logger.info("MQTT 연결 시작...")
        except Exception as e:
            logger.error(f"MQTT 연결 실패: {e}")
            raise

    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT 연결 해제")
        except Exception as e:
            logger.warning(f"MQTT 연결 해제 중 오류: {e}")

    def _should_publish_temp(self, temp, humidity):
        """온도/습도 발행 여부 판정"""
        if self.last_temp is None:
            return True  # 첫 발행

        if abs(temp - self.last_temp) >= self.temp_threshold:
            logger.info(f"온도 변동 감지: {self.last_temp:.1f}°C → {temp:.1f}°C")
            return True

        return False

    def _should_publish_distance(self, distance):
        """거리 발행 여부 판정"""
        if self.last_distance is None:
            return True  # 첫 발행

        if abs(distance - self.last_distance) >= self.distance_threshold:
            logger.info(f"거리 변동 감지: {self.last_distance:.1f}cm → {distance:.1f}cm")
            return True

        return False

    def publish_sensor_data(self):
        """센서 데이터 읽기 및 MQTT 발행"""
        now = time.time()

        # 10초 주기 체크
        elapsed = now - self.last_publish_time
        if elapsed < self.publish_interval:
            return

        # DHT22 읽기
        dht_data = self.dht.read()
        if dht_data:
            temp = dht_data['temperature']
            humidity = dht_data['humidity']

            # 온도 발행 여부 판정
            if elapsed >= self.publish_interval or self._should_publish_temp(temp, humidity):
                topic = f'home/{self.device_name}/sensor/temperature'
                payload = json.dumps({
                    'device': self.device_name,
                    'sensor': 'temperature',
                    'value': round(temp, 1),
                    'unit': '°C',
                    'ts': datetime.utcnow().isoformat() + 'Z'
                })
                self.client.publish(topic, payload, qos=1)
                self.last_temp = temp
                self.last_publish_time = now
                logger.info(f"온도 발행: {temp:.1f}°C")

            # 습도 발행
            topic = f'home/{self.device_name}/sensor/humidity'
            payload = json.dumps({
                'device': self.device_name,
                'sensor': 'humidity',
                'value': round(humidity, 1),
                'unit': '%',
                'ts': datetime.utcnow().isoformat() + 'Z'
            })
            self.client.publish(topic, payload, qos=1)
            self.last_humidity = humidity
            logger.info(f"습도 발행: {humidity:.1f}%")
        else:
            logger.warning("DHT22 읽기 실패")

        # HC-SR04 읽기
        distance_data = self.distance.read()
        if distance_data:
            # 거리 발행 여부 판정
            if elapsed >= self.publish_interval or self._should_publish_distance(distance_data):
                topic = f'home/{self.device_name}/sensor/distance'
                payload = json.dumps({
                    'device': self.device_name,
                    'sensor': 'distance',
                    'value': round(distance_data, 1),
                    'unit': 'cm',
                    'ts': datetime.utcnow().isoformat() + 'Z'
                })
                self.client.publish(topic, payload, qos=1)
                self.last_distance = distance_data
                self.last_publish_time = now
                logger.info(f"거리 발행: {distance_data:.1f}cm")
        else:
            logger.warning("HC-SR04 읽기 실패")

    def run(self):
        """메인 루프"""
        logger.info("센서 퍼블리셔 시작")

        try:
            self.connect()

            # MQTT 연결 안정화 대기
            time.sleep(2)

            while True:
                try:
                    self.publish_sensor_data()
                    time.sleep(1)  # 1초마다 체크
                except Exception as e:
                    logger.error(f"발행 중 오류: {e}")
                    time.sleep(5)

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
            self.dht.close()
            self.distance.close()
            logger.info("센서 퍼블리셔 종료")
        except Exception as e:
            logger.error(f"정리 중 오류: {e}")


def signal_handler(sig, frame):
    """시그널 핸들러 (Ctrl+C 처리)"""
    logger.info("신호 수신: 프로그램 종료")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    publisher = SensorPublisher('config.json')
    publisher.run()
