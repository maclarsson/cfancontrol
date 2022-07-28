import threading
from typing import ContextManager, Optional

from liquidctl.driver.kraken3 import KrakenX3
from liquidctl.driver.hydro_platinum import HydroPlatinum

from .sensor import Sensor
from .log import LogManager


class AIODeviceSensor(Sensor, ContextManager):

    is_valid: bool
    device: Optional[any]
    device_name: str
    sensor_name: str

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.is_valid = False
        self.current_temp = 0.0
        # self.sensor_name = device_name
        if not hasattr(self, "device"):
            self.device = None
        if self.device:
            try:
                self.device.connect()
                self.is_valid = True
                self.device.disconnect()
                LogManager.logger.info(f"AIO device initialized {repr({'device': self.sensor_name})}")
            except BaseException:
                self.is_valid = False
                LogManager.logger.exception(f"Error in initializing AIO device {repr({'device': self.sensor_name})}")

    def __enter__(self):
        if self.device:
            return self
        else:
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_valid:
            self.device.disconnect()
            del self.device
            self.is_valid = False
            LogManager.logger.debug(f"AIO Device disconnected and reference removed {repr({'device': self.sensor_name})}")
        return None

    def get_temperature(self) -> float:
        raise NotImplementedError()

    def get_signature(self) -> list:
        raise NotImplementedError()

    def _safe_call_aio_function(self, function):
        self._lock.acquire()
        try:
            self.device.connect()
            result = function()
        except Exception:
            raise
        finally:
            self.device.disconnect()
            self._lock.release()
        return result


class KrakenX3Sensor(AIODeviceSensor):

    def __init__(self, device: KrakenX3):
        self.device = device
        self.device_name = device.description
        self.sensor_name = "Kraken X3"
        super(KrakenX3Sensor, self).__init__()

    def get_temperature(self) -> float:
        self.current_temp = 0.0
        if self.is_valid:
            try:
                ret = self._safe_call_aio_function(lambda: self.device._read())
                part1 = int(ret[15])
                part2 = int(ret[16])
                if (0 <= part1 <= 100) and (0 <= part2 <= 90):
                    self.current_temp = float(part1) + float(part2 / 10)
                    LogManager.logger.trace(f"Getting sensor temperature {repr({'sensor': self.sensor_name, 'temperature': round(self.current_temp, 1)})}")
                else:
                    LogManager.logger.warning(f"Invalid sensor data {repr({'sensor': self.sensor_name, 'part 1': part1, 'part 2': part2})}")
            except BaseException:
                LogManager.logger.exception(f"Unexpected error in getting sensor data {repr({'sensor': self.sensor_name})}")
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, self.device_name, self.device.product_id, self.sensor_name]


class HydroPlatinumSensor(AIODeviceSensor):
    # Details: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py

    def __init__(self, device: HydroPlatinum):
        self.device = device
        self.device_name = device.description
        device_prefix = "Corsair Hydro "
        self.sensor_name = self.device_name.split(device_prefix, 1)[1]
        super(HydroPlatinumSensor, self).__init__()

    def get_temperature(self) -> float:
        self.current_temp = 0.0
        if self.is_valid:
            try:
                ret = self._safe_call_aio_function(lambda: self.device._send_command(0b00, 0xff))
                part1 = int(ret[8])
                part2 = int(ret[7])
                if (0 <= part1 <= 100) and (0 <= part2 <= 255):
                    self.current_temp = float(part1) + float(part2 / 255)
                    LogManager.logger.trace(f"Getting sensor temperature {repr({'sensor': self.sensor_name, 'temperature': round(self.current_temp, 1)})}")
                else:
                    LogManager.logger.warning(f"Invalid sensor data {repr({'sensor': self.sensor_name, 'part 1': part1, 'part 2': part2})}")
            except ValueError as verr:
                LogManager.logger.error(f"Problem in getting sensor data {repr({'sensor': self.sensor_name, 'error': repr(verr)})}")
            except BaseException:
                LogManager.logger.exception(f"Unexpected error in getting sensor data {repr({'sensor': self.sensor_name})}")
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, self.device_name, self.device.product_id, self.sensor_name]
