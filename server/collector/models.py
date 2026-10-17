import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SensorDB:
    """SQLite 센서 데이터 관리"""

    def __init__(self, db_path='sensor_data.db'):
        self.db_path = Path(db_path)
        self.conn = None
        self.initialize()

    def initialize(self):
        """DB 초기화 및 스키마 생성"""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # 외래키 지원
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
            logger.info(f"SensorDB 초기화 완료: {self.db_path}")
        except Exception as e:
            logger.error(f"DB 초기화 실패: {e}")
            raise

    def _create_schema(self):
        """schema.sql 실행"""
        schema_file = Path(__file__).parent / 'schema.sql'
        try:
            with open(schema_file) as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)
            self.conn.commit()
            logger.debug("스키마 생성/확인 완료")
        except FileNotFoundError:
            logger.error(f"schema.sql 파일 없음: {schema_file}")
            raise

    def insert_reading(self, device: str, sensor: str, value: float, unit: str, ts: str):
        """센서 데이터 저장"""
        try:
            self.conn.execute(
                '''INSERT INTO readings (ts, device, sensor, value, unit)
                   VALUES (?, ?, ?, ?, ?)''',
                (ts, device, sensor, value, unit)
            )
            self.conn.commit()
            logger.debug(f"저장: {device}/{sensor}={value}{unit}")
        except Exception as e:
            logger.error(f"센서 데이터 저장 실패: {e}")
            self.conn.rollback()

    def get_readings_for_minute(self, device: str, sensor: str, minute_str: str):
        """특정 분의 센서 데이터 조회"""
        try:
            cursor = self.conn.execute(
                '''SELECT ts, value FROM readings
                   WHERE device = ? AND sensor = ?
                   AND strftime('%Y-%m-%d %H:%M:00', ts) = ?
                   ORDER BY ts ASC''',
                (device, sensor, minute_str)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"센서 데이터 조회 실패: {e}")
            return []

    def insert_aggregation(self, minute: str, device: str, sensor: str,
                          min_val: float, max_val: float, avg_val: float,
                          change_count: int, sample_count: int):
        """1분 집계 데이터 저장"""
        try:
            self.conn.execute(
                '''INSERT OR REPLACE INTO agg_1min
                   (minute, device, sensor, min, max, avg, change_count, sample_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (minute, device, sensor, min_val, max_val, avg_val, change_count, sample_count)
            )
            self.conn.commit()
            logger.debug(f"집계 저장: {minute} {device}/{sensor} min={min_val:.1f} max={max_val:.1f} avg={avg_val:.1f}")
        except Exception as e:
            logger.error(f"집계 저장 실패: {e}")
            self.conn.rollback()

    def get_aggregation(self, minute: str, device: str, sensor: str):
        """1분 집계 데이터 조회"""
        try:
            cursor = self.conn.execute(
                '''SELECT minute, device, sensor, min, max, avg, change_count, sample_count
                   FROM agg_1min
                   WHERE minute = ? AND device = ? AND sensor = ?''',
                (minute, device, sensor)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"집계 조회 실패: {e}")
            return None

    def get_last_aggregation(self, device: str, sensor: str):
        """최근 1분 집계 조회"""
        try:
            cursor = self.conn.execute(
                '''SELECT minute, device, sensor, min, max, avg, change_count, sample_count
                   FROM agg_1min
                   WHERE device = ? AND sensor = ?
                   ORDER BY minute DESC
                   LIMIT 1''',
                (device, sensor)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"최근 집계 조회 실패: {e}")
            return None

    def insert_event(self, event_type: str, device: str, ts: str,
                    sensor: str = None, value: float = None, unit: str = None,
                    message: str = None):
        """이벤트 로그 저장"""
        try:
            self.conn.execute(
                '''INSERT INTO events (ts, event_type, device, sensor, value, unit, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (ts, event_type, device, sensor, value, unit, message)
            )
            self.conn.commit()
            logger.info(f"이벤트 기록: {event_type} - {device}/{sensor}")
        except Exception as e:
            logger.error(f"이벤트 저장 실패: {e}")
            self.conn.rollback()

    def cleanup_old_data(self):
        """오래된 데이터 삭제 (30일 초과 원본, 1년 초과 집계)"""
        try:
            deleted_readings = self.conn.execute(
                "DELETE FROM readings WHERE ts < datetime('now', '-30 days')"
            ).rowcount

            deleted_agg = self.conn.execute(
                "DELETE FROM agg_1min WHERE minute < datetime('now', '-1 year')"
            ).rowcount

            self.conn.commit()
            logger.info(f"정리 완료: readings {deleted_readings}건, agg_1min {deleted_agg}건")
        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")
            self.conn.rollback()

    def get_db_stats(self):
        """DB 통계 조회"""
        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM readings")
            reading_count = cursor.fetchone()[0]

            cursor = self.conn.execute("SELECT COUNT(*) FROM agg_1min")
            agg_count = cursor.fetchone()[0]

            cursor = self.conn.execute(
                "SELECT device, sensor, COUNT(*) as count FROM readings GROUP BY device, sensor"
            )
            details = [dict(row) for row in cursor.fetchall()]

            return {
                'total_readings': reading_count,
                'total_aggregations': agg_count,
                'details': details
            }
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}

    def close(self):
        """DB 연결 종료"""
        try:
            if self.conn:
                self.conn.close()
            logger.info("DB 연결 종료")
        except Exception as e:
            logger.warning(f"DB 종료 중 오류: {e}")
