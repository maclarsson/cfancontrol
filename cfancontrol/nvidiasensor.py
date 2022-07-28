import subprocess
from subprocess import CompletedProcess, CalledProcessError
from typing import List, Dict

from .sensor import Sensor
from .log import LogManager

SMI_DETECT_COMMAND: List[str] = ['sh', '-c', 'nvidia-smi --query-gpu=index,gpu_name --format=csv,noheader,nounits']
SMI_SATUS_COMMAND: List[str] = ['sh', '-c', 'nvidia-smi --query-gpu=index,gpu_name,temperature.gpu,utilization.gpu,fan.speed --format=csv,noheader,nounits']


class NvidiaSensor(Sensor):

    def __init__(self, index: int, device_name: str):
        super().__init__()
        self.index = index
        self.device_name = device_name
        self.device_description = device_name
        self.sensor_name = "nVidia GPU"
        self.current_temp = 0.0

    def get_temperature(self) -> float:
        try:
            command_result: CompletedProcess = subprocess.run(SMI_SATUS_COMMAND, capture_output=True, check=True, text=True)
            result_lines = str(command_result.stdout).splitlines()
            for line in result_lines:
                if not line.strip():
                    continue
                values = line.split(', ')
                if int(values[0]) == self.index:
                    temp = int(values[2])
                    if self.current_temp == 0.0 or (10.0 <= temp <= 100.0):
                        self.current_temp = float(temp)
                        LogManager.logger.trace(f"Getting sensor temperature {repr({'sensor': self.sensor_name, 'temperature': self.current_temp})}")
                    else:
                        LogManager.logger.warning(f"Sensor temperature data out of range {repr({'sensor': self.sensor_name, 'last temp': self.current_temp, 'new temp': temp})}")
        except CalledProcessError as cpe:
            LogManager.logger.warning(f"Problem getting sensor data {repr({'sensor': self.sensor_name, 'error': cpe.output})}")
        except BaseException:
            LogManager.logger.exception(f"Error getting sensor data {repr({'sensor': self.sensor_name})}")
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, self.device_description, self.index, self.sensor_name]

    @staticmethod
    def detect_gpus() -> List['NvidiaSensor']:
        detected_gpus = []
        try:
            command_result: CompletedProcess = subprocess.run(SMI_DETECT_COMMAND, capture_output=True, check=True, text=True)
            result_lines = str(command_result.stdout).splitlines()
            LogManager.logger.trace(f"Result of nVidia GPU detection: {result_lines}")
            for line in result_lines:
                if not line.strip():
                    continue
                values = line.split(', ')
                detected_gpus.append(NvidiaSensor(int(values[0]), values[1]))
        except CalledProcessError:
            LogManager.logger.trace(f"No nVidia GPU found")
        return detected_gpus
