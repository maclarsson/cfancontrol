import os
from typing import Optional

from .sensor import Sensor
from .log import LogManager


class HwSensor(Sensor):

    def __init__(self, chip_name: str, sensor_path: str, feature: str, feature_label: str) -> None:
        super().__init__()
        self.chip_name = chip_name
        self.sensor_folder = sensor_path
        self.sensor_name = feature_label
        self.sensor_feature = feature
        self.sensor_file = os.path.join(self.sensor_folder, feature + "_input")
        self.current_temp = 0.0

    def get_temperature(self) -> float:
        temp, success = self.get_sensor_data()
        if success:
            LogManager.logger.debug(f"Getting sensor temperature {repr({'sensor': self.sensor_name, 'temperature': temp})}")
            if self.current_temp == 0.0 or (10.0 < temp < 99.0):
                self.current_temp = temp
            else:
                LogManager.logger.warning(f"Sensor temperature data out of range {repr({'sensor': self.sensor_name, 'last temp': self.current_temp, 'new temp': temp})}")
        return self.current_temp

    def get_sensor_data(self) -> (float, bool):
        value: float = 0.0
        ret = False
        raw = self.get_file_data(self.sensor_file)
        if raw:
            value = float(raw) / 1000
            ret = True
        else:
            LogManager.logger.warning(f"Invalid sensor data {repr({'sensor': self.sensor_name, 'sensor file': self.sensor_file, 'data': raw})}")
        return value, ret

    def get_signature(self) -> list:
        return [self.__class__.__name__, self.chip_name, self.sensor_folder, self.sensor_feature, self.sensor_name]

    def get_file_data(self, file_name: str) -> Optional[str]:
        value: str = None
        try:
            with open(file_name, 'r') as file:
                value = file.read().strip()
        except OSError:
            LogManager.logger.exception(f"Error getting sensor data {repr({'sensor': self.sensor_name, 'sensor file': file_name})}")
        return value

