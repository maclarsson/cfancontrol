from typing import Optional, List, Dict

import liquidctl    # liquidctl module
import sensors      # PySensors module

from .settings import Environment
from .sensor import Sensor, DummySensor
from .hwsensor import HwSensor
from .devicesensor import KrakenX3Sensor, HydroPlatinumSensor
from .nvidiasensor import NvidiaSensor
from .log import LogManager


class SensorManager(object):
    # initialize list of sensors with dummy sensor
    system_sensors: List = [DummySensor()]

    @staticmethod
    def identify_system_sensors():
        # get sensors via PySensors and libsensors.so (part of lm_sensors) -> config in /.config/cfancontrol/sensors3.conf or /etc/sensors3.conf
        sensors.init(bytes(Environment.sensors_config_file, "utf-8"))
        try:
            for chip in sensors.iter_detected_chips():
                LogManager.logger.info(f"System sensor found {repr({'name': chip.prefix.decode('utf-8'), 'chip': repr(chip)})}")
                for feature in chip:
                    # is it a temp sensor on the chip
                    if feature.type == 2:
                        name = feature.name
                        label = feature.label
                        if name == label:
                            # no label set for feature, so add prefix
                            label = chip.prefix.decode('utf-8') + "_" + feature.label
                        LogManager.logger.debug(f"Adding feature {repr({'chip': chip.prefix.decode('utf-8'), 'feature name': name, 'label': label})}")
                        SensorManager.system_sensors.append(HwSensor(str(chip), chip.path.decode('utf-8'), name, label))
        finally:
            sensors.cleanup()

        # append sensors for AIOs
        devices = liquidctl.find_liquidctl_devices()
        for dev in devices:
            if type(dev) == liquidctl.driver.kraken3.KrakenX3:
                LogManager.logger.info(f"AIO device found {repr({'device': dev.description})}")
                SensorManager.system_sensors.append(KrakenX3Sensor(dev))
            elif type(dev) == liquidctl.driver.hydro_platinum.HydroPlatinum:
                LogManager.logger.info(f"AIO device found {repr({'device': dev.description})}")
                SensorManager.system_sensors.append(HydroPlatinumSensor(dev))

        # append sensors of GPUs (if found)
        nvidia_gpus: List[NvidiaSensor] = NvidiaSensor.detect_gpus()
        for gpu in nvidia_gpus:
            LogManager.logger.info(f"nVidia GPU found {repr({'id': gpu.index, 'device': gpu.device_name})}")
            SensorManager.system_sensors.append(gpu)

    @staticmethod
    def get_system_sensor(signature: list) -> Optional[Sensor]:
        for sensor in SensorManager.system_sensors:
            sensor_signature = sensor.get_signature()
            if signature == sensor_signature:
                return sensor
        return None


