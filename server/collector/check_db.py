#!/usr/bin/env python3
"""
SQLite DB 상태 확인 스크립트
collector.py가 제대로 데이터를 저장하고 있는지 확인
"""

from models import SensorDB
import json

def main():
    db = SensorDB('sensor_data.db')

    print("=" * 60)
    print("📊 센서 데이터 수집 상태 확인")
    print("=" * 60)
    print()

    # 통계
    stats = db.get_db_stats()
    print(f"📈 데이터 통계:")
    print(f"   ├─ 원본 센서 데이터 (readings): {stats['total_readings']:,}건")
    print(f"   ├─ 1분 집계 데이터 (agg_1min): {stats['total_aggregations']:,}건")
    print()

    if stats['details']:
        print(f"📍 수집된 센서:")
        for detail in stats['details']:
            print(f"   ├─ {detail['device']}/{detail['sensor']}: {detail['count']:,}건")
        print()
    else:
        print("⚠️  아직 데이터가 수집되지 않았습니다.")
        print("   퍼블리셔가 실행 중인지 확인하세요.")
        print()

    # 최근 집계 확인
    print(f"📋 최근 1분 집계:")
    try:
        cursor = db.conn.execute(
            "SELECT minute, device, sensor, min, max, avg, sample_count FROM agg_1min ORDER BY minute DESC LIMIT 5"
        )
        rows = cursor.fetchall()

        if rows:
            for row in rows:
                print(f"   ├─ {row[0]} {row[1]}/{row[2]}")
                print(f"   │  min={row[3]:.1f}, max={row[4]:.1f}, avg={row[5]:.1f}, samples={row[6]}")
            print()
        else:
            print("   (집계 데이터 없음)")
            print()
    except Exception as e:
        print(f"   (조회 오류: {e})")
        print()

    # 최근 원본 데이터 확인
    print(f"📝 최근 원본 데이터:")
    try:
        cursor = db.conn.execute(
            "SELECT ts, device, sensor, value, unit FROM readings ORDER BY ts DESC LIMIT 5"
        )
        rows = cursor.fetchall()

        if rows:
            for row in rows:
                print(f"   ├─ {row[0]} {row[1]}/{row[2]} = {row[3]}{row[4]}")
            print()
        else:
            print("   (원본 데이터 없음)")
            print()
    except Exception as e:
        print(f"   (조회 오류: {e})")
        print()

    print("=" * 60)

    db.close()


if __name__ == '__main__':
    main()
