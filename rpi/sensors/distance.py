import logging
import time
from gpiozero import DistanceSensor

logger = logging.getLogger(__name__)


class HC_SR04Reader:
    """HC-SR04 초음파 거리 센서 (gpiozero 사용)

    - TRIG: GPIO 17 (신호 송신)
    - ECHO: GPIO 27 (신호 수신)
    - 5회 측정 후 중간값 사용 (노이즈 제거)
    """

    def __init__(self, trig_pin=17, echo_pin=27, samples=5, timeout=1.0):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.samples = samples
        self.timeout = timeout

        try:
            # gpiozero DistanceSensor 생성
            # (echo_pin, trigger_pin 순서)
            self.sensor = DistanceSensor(echo=echo_pin, trigger=trig_pin, queue_len=1)
            logger.info(f"HC-SR04 센서 초기화 완료 (TRIG={trig_pin}, ECHO={echo_pin})")
        except Exception as e:
            logger.error(f"HC-SR04 센서 초기화 실패: {e}")
            raise

    def read(self):
        """거리 읽기 (중간값 필터)

        Returns:
            float: 거리 (cm), 실패 시 None
        """
        measurements = []

        for i in range(self.samples):
            try:
                # gpiozero는 거리를 미터(m)로 반환
                distance_m = self.sensor.distance
                if distance_m is not None and distance_m > 0:
                    distance_cm = distance_m * 100  # m → cm
                    measurements.append(distance_cm)
            except Exception as e:
                logger.warning(f"HC-SR04 읽기 시도 {i+1}/{self.samples} 실패: {e}")

            time.sleep(0.1)  # 측정 간 대기

        if not measurements:
            logger.error(f"HC-SR04: {self.samples}회 모두 실패")
            return None

        # 중간값 선택 (노이즈 제거)
        measurements.sort()
        median = measurements[len(measurements) // 2]

        logger.debug(f"HC-SR04: 측정값={[f'{m:.1f}' for m in measurements]}, 중간값={median:.1f}cm")
        return median

    def close(self):
        """센서 리소스 해제"""
        try:
            self.sensor.close()
            logger.info("HC-SR04 센서 종료")
        except Exception as e:
            logger.warning(f"HC-SR04 센서 종료 중 오류: {e}")
