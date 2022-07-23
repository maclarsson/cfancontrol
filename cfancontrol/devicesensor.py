from typing import ContextManager

from liquidctl.driver.kraken3 import KrakenX3
from liquidctl.driver.hydro_platinum import HydroPlatinum

from .sensor import Sensor
from .log import LogManager


class AIODeviceSensor(Sensor, ContextManager):

    def __init__(self, aio_device, device_name: str) -> None:
        super().__init__()
        self.is_valid = False
        self.current_temp = 0.0
        self.sensor_name = device_name
        init_args = {}
        if device_name == "Kraken X3":
            self.device: KrakenX3 = aio_device
        elif device_name == "H100i Pro XT":
            self.device: HydroPlatinum = aio_device
            init_args = {"pump_mode": "quiet"}
        else:
            self.device = None
        if self.device is not None:
            try:
                self.device.connect()
                LogManager.logger.info(f"{device_name} connected")
                self.device.initialize(**init_args)
                self.is_valid = True
                LogManager.logger.info(f"{device_name} successfully initialized")
            except Exception as err:
                LogManager.logger.exception(f"Error opening {device_name}")
                raise RuntimeError(f"Cannot initialize AIO device '{device_name}'")
        else:
            LogManager.logger.warning(f"{device_name} not connected")

    def __enter__(self):
        if self.device:
            LogManager.logger.debug(f"Context manager for device {self.sensor_name} started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        LogManager.logger.debug(f"Closing context for device {self.sensor_name}")
        if self.is_valid:
            self.device.disconnect()
            del self.device
            self.is_valid = False
            LogManager.logger.info(f"{self.sensor_name} disconnected and reference removed")
        return None

    def get_temperature(self) -> float:
        raise NotImplementedError()

    def get_signature(self) -> list:
        raise NotImplementedError()


class KrakenX3Sensor(AIODeviceSensor):

    def __init__(self, device: KrakenX3):
        super(KrakenX3Sensor, self).__init__(device, "Kraken X3")

    def get_temperature(self) -> float:
        LogManager.logger.debug(f"Reading temperature from {self.sensor_name} sensor")
        self.current_temp = 0.0
        if self.is_valid:
            ret = self.device._read()
            part1 = int(ret[15])
            part2 = int(ret[16])
            LogManager.logger.debug(f"{self.sensor_name} read-out: {ret}")
            if (0 <= part1 <= 100) and (0 <= part2 <= 90):
                self.current_temp = float(part1) + float(part2 / 10)
            else:
                LogManager.logger.warning(f"Invalid sensor data from {self.sensor_name}: {part1}.{part2}")
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, self.device.description, self.device.product_id, self.sensor_name]


class HydroPlatinumSensor(AIODeviceSensor):
    # Details: https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py

    def __init__(self, device: HydroPlatinum):
        self.device_description: str = device.description
        self.device_name = "Corsair Hydro "
        self.device_model = self.device_description.split(self.device_name, 1)[1]
        super(HydroPlatinumSensor, self).__init__(device, self.device_model)

    def get_temperature(self) -> float:
        LogManager.logger.debug(f"Reading temperature from {self.sensor_name} sensor")
        self.current_temp = 0.0
        if self.is_valid:
            res = self.device._send_command(0b00, 0xff)
            part1 = int(res[8])
            part2 = int(res[7])
            LogManager.logger.debug(f"{self.sensor_name} read-out: {res}")
            if (0 <= part1 <= 100) and (0 <= part2 <= 255):
                self.current_temp = float(part1) + float(part2 / 255)
            else:
                LogManager.logger.warning(f"Invalid sensor data from {self.sensor_name}: {part1}.{part2}")
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, self.device.description, self.device.product_id, self.sensor_name]