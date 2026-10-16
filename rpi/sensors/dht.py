import logging
import time
import adafruit_dht
from adafruit_blinka.microcontroller.generic_linux.libgpiod_pin import Pin

logger = logging.getLogger(__name__)


class DHT22Reader:
    """DHT22 온도/습도 센서 (GPIO 4, 3핀 베어 센서)

    - 최소 2초 간격으로만 읽을 수 있음
    - 체크섬 오류 시 3회까지 재시도
    """

    def __init__(self, gpio_pin=4, retry_count=3, retry_delay=1.0):
        """
        Args:
            gpio_pin: GPIO 핀 번호 (기본값: 4)
            retry_count: 재시도 횟수
            retry_delay: 재시도 간격 (초)
        """
        self.gpio_pin = gpio_pin
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.last_read_time = 0
        self.min_interval = 2.0  # DHT22는 최소 2초 간격 필요

        try:
            # libgpiod 핀으로 생성
            pin = Pin(gpio_pin)
            self.sensor = adafruit_dht.DHT22(pin)
            logger.info(f"DHT22 센서 초기화 완료 (GPIO {gpio_pin})")
        except Exception as e:
            logger.error(f"DHT22 센서 초기화 실패: {e}")
            raise

    def read(self):
        """온도/습도 읽기

        Returns:
            dict: {"temperature": float, "humidity": float}
                  읽기 실패 시 None
        """
        now = time.time()
        elapsed = now - self.last_read_time

        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"DHT22 읽기 대기 중 ({wait_time:.1f}초)")
            time.sleep(wait_time)

        for attempt in range(1, self.retry_count + 1):
            try:
                temp = self.sensor.temperature
                humidity = self.sensor.humidity

                if temp is None or humidity is None:
                    raise ValueError("센서 값이 None")

                self.last_read_time = time.time()
                logger.debug(f"DHT22: 온도={temp:.1f}°C, 습도={humidity:.1f}%")
                return {"temperature": temp, "humidity": humidity}

            except Exception as e:
                logger.warning(f"DHT22 읽기 시도 {attempt}/{self.retry_count} 실패: {e}")

                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"DHT22 읽기 최종 실패 (3회 재시도 후)")
                    return None

        return None

    def close(self):
        """센서 리소스 해제"""
        try:
            self.sensor.exit()
            logger.info("DHT22 센서 종료")
        except Exception as e:
            logger.warning(f"DHT22 센서 종료 중 오류: {e}")
