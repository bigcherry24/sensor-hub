#!/usr/bin/env python3
"""
센서 데이터 브리지 — Dify 워크플로우 연동
- 1분마다 실행 (cron)
- DB에서 1분 집계 조회
- 변동 판정 → Dify Workflow API 호출
- 요약 및 알림 발송
"""

import os
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import requests

# 환경 변수 로드
load_dotenv('.env')

# 로깅 설정
log_dir = Path.home() / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'sensor-bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 부모 디렉토리 path 추가 (collector 모듈 import)
sys.path.insert(0, str(Path(__file__).parent.parent / 'collector'))
from models import SensorDB


class SensorBridge:
    """센서 데이터 → Dify 브리지"""

    def __init__(self, config_file='bridge_config.json'):
        self.config = self._load_config(config_file)

        # Dify Webhook URL 설정
        self.webhook_summary = os.getenv('DIFY_WEBHOOK_SUMMARY')
        self.webhook_alert = os.getenv('DIFY_WEBHOOK_ALERT')

        # 임계치
        self.temp_change_threshold = self.config['temp_change_threshold']  # °C
        self.distance_change_threshold = self.config['distance_change_threshold']  # cm
        self.temp_alert_threshold = self.config['temp_alert_threshold']  # °C
        self.distance_alert_threshold = self.config['distance_alert_threshold']  # cm

        # DB 초기화
        db_path = self.config.get('db_path', '../collector/sensor_data.db')
        self.db = SensorDB(db_path)

        logger.info(f"SensorBridge 초기화 (Webhook 모드)")

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
                'db_path': '../collector/sensor_data.db',
                'temp_change_threshold': 0.5,
                'distance_change_threshold': 3.0,
                'temp_alert_threshold': 30.0,
                'distance_alert_threshold': 5.0,
            }

    def get_recent_aggregations(self):
        """최근 1분 집계 조회"""
        try:
            cursor = self.db.conn.execute(
                '''SELECT minute, device, sensor, min, max, avg, change_count, sample_count
                   FROM agg_1min
                   ORDER BY minute DESC
                   LIMIT 10'''
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"집계 조회 실패: {e}")
            return []

    def has_significant_change(self, agg):
        """유의미한 변동 판정"""
        sensor = agg['sensor']
        change_count = agg['change_count']

        if sensor == 'temperature':
            # 변동 횟수가 2회 이상이면 유의미
            return change_count >= 2
        elif sensor == 'distance':
            # 변동 횟수가 3회 이상이면 유의미
            return change_count >= 3
        elif sensor == 'humidity':
            # 습도는 항상 보냄
            return True

        return False

    def has_alert_condition(self, agg):
        """임계치 초과 판정"""
        sensor = agg['sensor']
        max_val = agg['max']

        if sensor == 'temperature' and max_val > self.temp_alert_threshold:
            logger.warning(f"⚠️ 온도 경보: {max_val}°C > {self.temp_alert_threshold}°C")
            return True

        if sensor == 'distance' and max_val < self.distance_alert_threshold:
            logger.warning(f"⚠️ 거리 경보: {max_val}cm < {self.distance_alert_threshold}cm")
            return True

        return False

    def call_dify_webhook(self, aggregations, is_alert=False):
        """Dify Webhook으로 데이터 전송

        Args:
            aggregations: 최근 1분 집계 리스트
            is_alert: True면 긴급 알림 워크플로우
        """
        try:
            # Webhook URL 선택
            webhook_url = self.webhook_alert if is_alert else self.webhook_summary
            workflow_name = 'alert' if is_alert else 'summary'

            if not webhook_url:
                logger.error(f"Dify Webhook URL 없음: {workflow_name}")
                return None

            # 현재 시간 (분 단위)
            now = datetime.now(timezone.utc)
            period_str = now.strftime('%Y-%m-%d %H:%M')

            # Payload 구성 (Webhook이 기대하는 형식)
            payload = {
                'period': period_str,
                'events': aggregations,
                'alert_type': 'emergency' if is_alert else 'summary'
            }

            logger.info(f"Dify Webhook 호출: {workflow_name} ({period_str})")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(webhook_url, json=payload, timeout=30)

            if response.status_code == 200:
                logger.info(f"✅ Webhook 응답 성공")
                return response.json()
            else:
                logger.error(f"❌ Webhook 응답 실패: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Webhook 요청 타임아웃")
            return None
        except Exception as e:
            logger.error(f"Webhook 호출 실패: {e}")
            return None

    def process_minute(self):
        """1분 처리 (cron에서 호출)"""
        logger.info("=" * 60)
        logger.info("브리지 1분 처리 시작")

        try:
            # 최근 집계 조회
            aggregations = self.get_recent_aggregations()

            if not aggregations:
                logger.warning("처리할 집계 데이터 없음")
                return

            # 최근 1분 집계만 처리
            latest_minute = aggregations[0]['minute']
            recent_aggs = [agg for agg in aggregations if agg['minute'] == latest_minute]

            if not recent_aggs:
                logger.info("최근 1분 집계 없음")
                return

            logger.info(f"처리: {latest_minute} ({len(recent_aggs)}개 센서)")

            # 각 센서 집계 처리
            alert_aggs = []
            summary_aggs = []

            for agg in recent_aggs:
                device = agg['device']
                sensor = agg['sensor']

                logger.info(f"  📊 {device}/{sensor}: min={agg['min']:.1f}, max={agg['max']:.1f}, avg={agg['avg']:.1f}, changes={agg['change_count']}")

                # 임계치 초과 확인
                if self.has_alert_condition(agg):
                    alert_aggs.append(agg)
                    logger.warning(f"    ⚠️  경보 조건 만족")
                # 유의미한 변동 확인
                elif self.has_significant_change(agg):
                    summary_aggs.append(agg)
                    logger.info(f"    📈 유의미한 변동 감지")
                else:
                    logger.info(f"    ➡️  변동 없음")

            # 경보 발송 (우선순위)
            if alert_aggs:
                logger.warning(f"🚨 경보 발송: {len(alert_aggs)}개 센서")
                self.call_dify_webhook(alert_aggs, is_alert=True)

            # 요약 발송
            if summary_aggs:
                logger.info(f"📨 요약 발송: {len(summary_aggs)}개 센서")
                self.call_dify_webhook(summary_aggs, is_alert=False)

            logger.info("브리지 1분 처리 완료")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"처리 중 오류: {e}")
            logger.info("=" * 60)

    def run(self):
        """지금 바로 실행 (테스트용)"""
        logger.info("테스트 모드: 지금 바로 처리")
        self.process_minute()

    def close(self):
        """리소스 정리"""
        try:
            self.db.close()
            logger.info("브리지 종료")
        except Exception as e:
            logger.warning(f"정리 중 오류: {e}")


def main():
    bridge = SensorBridge('bridge_config.json')

    # 테스트 모드 또는 cron 모드
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        bridge.run()
    else:
        # cron에서 호출될 때 (인자 없음)
        bridge.process_minute()

    bridge.close()


if __name__ == '__main__':
    main()
