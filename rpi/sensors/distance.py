import logging
import time
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)


class HC_SR04Reader:
    """HC-SR04 초음파 거리 센서

    - TRIG: GPIO 17 (신호 송신, 10μs 펄스)
    - ECHO: GPIO 27 (신호 수신, 반향 시간 측정)
    - 5회 측정 후 중간값 사용 (노이즈 제거)
    """

    def __init__(self, trig_pin=17, echo_pin=27, samples=5, timeout=1.0):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.samples = samples
        self.timeout = timeout
        self.sound_speed = 34300  # cm/s (25°C 기준)

        # GPIO 설정 (BCM 모드)
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)

        # TRIG 초기값 LOW
        GPIO.output(self.trig_pin, GPIO.LOW)
        time.sleep(0.5)

        logger.info(f"HC-SR04 센서 초기화 완료 (TRIG={trig_pin}, ECHO={echo_pin})")

    def _single_read(self):
        """한 번의 거리 측정

        Returns:
            float: 거리 (cm), 실패 시 None
        """
        try:
            # TRIG 10μs 펄스 송신
            GPIO.output(self.trig_pin, GPIO.HIGH)
            time.sleep(0.00001)  # 10μs
            GPIO.output(self.trig_pin, GPIO.LOW)

            # ECHO 시작 시간 대기 (최대 timeout)
            start_time = time.time()
            while GPIO.input(self.echo_pin) == GPIO.LOW:
                if time.time() - start_time > self.timeout:
                    logger.warning("HC-SR04: ECHO 신호 수신 타임아웃 (LOW → HIGH)")
                    return None

            pulse_start = time.time()

            # ECHO 종료 시간 대기
            start_time = time.time()
            while GPIO.input(self.echo_pin) == GPIO.HIGH:
                if time.time() - start_time > self.timeout:
                    logger.warning("HC-SR04: ECHO 신호 수신 타임아웃 (HIGH → LOW)")
                    return None

            pulse_end = time.time()

            # 거리 계산: distance = (time * speed) / 2
            pulse_duration = pulse_end - pulse_start
            distance = (pulse_duration * self.sound_speed) / 2

            return distance

        except Exception as e:
            logger.error(f"HC-SR04 단일 측정 오류: {e}")
            return None

    def read(self):
        """거리 읽기 (중간값 필터)

        Returns:
            float: 거리 (cm), 실패 시 None
        """
        measurements = []

        for i in range(self.samples):
            distance = self._single_read()
            if distance is not None:
                measurements.append(distance)
            time.sleep(0.1)  # 측정 간 대기

        if not measurements:
            logger.error(f"HC-SR04: {self.samples}회 모두 실패")
            return None

        # 중간값 선택 (노이즈 제거)
        measurements.sort()
        median = measurements[len(measurements) // 2]

        logger.debug(f"HC-SR04: 측정값={measurements}, 중간값={median:.1f}cm")
        return median

    def close(self):
        """GPIO 리소스 해제"""
        try:
            GPIO.cleanup()
            logger.info("HC-SR04 센서 종료 (GPIO 정리 완료)")
        except Exception as e:
            logger.warning(f"HC-SR04 센서 종료 중 오류: {e}")
