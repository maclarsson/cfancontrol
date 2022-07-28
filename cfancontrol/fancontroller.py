import threading
import time
from typing import Dict, Optional, List, ContextManager

import liquidctl.driver.commander_pro
import liquidctl.driver.hydro_platinum
from liquidctl import find_liquidctl_devices

from .log import LogManager
from .pwmfan import PWMFan
from .fancurve import FanCurve, FanMode
from .sensor import Sensor, DummySensor


class FanController(ContextManager):

    RPM_STEP: int = 10
    RPM_INTERVAL: float = 0.025

    channels: Dict[str, PWMFan]
    is_valid: bool
    device: Optional[any]
    device_name: str

    def __init__(self):
        self._lock = threading.Lock()
        self.channels = {}
        self.is_valid = False
        if not hasattr(self, "device"):
            self.device = None
            self.device_name = "<none>"
        if self.device:
            try:
                self.device_name = self.device.description
                self.device.connect()
                self.device.disconnect()
                self.is_valid = True
                self.detect_channels()
                LogManager.logger.info(f"Fan controller initialized {repr({'controller': self.device_name})}")
            except BaseException:
                self.is_valid = False
                LogManager.logger.exception(f"Error in initializing fan controller {repr({'controller': self.device_name})}")
            finally:
                self.device.disconnect()

    def __enter__(self):
        if self.device:
            return self
        else:
            return None

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.is_valid:
            self.device.disconnect()
            del self.device
            self.is_valid = False
            LogManager.logger.debug(f"Fan controller disconnected and reference removed {repr({'controller': self.device_name})}")

    def get_name(self) -> str:
        return self.device_name

    def is_initialized(self) -> bool:
        return self.is_valid

    def detect_channels(self):
        return []

    def reset_channels(self, sensor: Sensor):
        for channel in self.channels:
            self.channels[channel] = PWMFan(channel, FanCurve.zero_rpm_curve(), sensor)

    def get_channel_status(self, channel: str) -> (bool, FanMode, int, int, int, float):
        fan: PWMFan = self.channels.get(channel)
        if fan:
            speed = self.get_channel_speed(channel)
            return True, *fan.get_fan_status(), speed
        return False, FanMode.Off, 0, 0, 0, 0.0

    def get_channel_speed(self, channel: str) -> int:
        pass

    def set_channel_speed(self, channel: str, new_pwm: int, current_percent: int, new_percent: int, temperature: float) -> bool:
        if self.is_valid:
            LogManager.logger.info(f"Setting fan speed {repr({'controller': self.device.description, 'channel': channel, 'pwm': new_pwm, 'duty': new_percent, 'temperature': round(temperature, 1)})}")
            if self._set_channel_speed_smoothly(channel, current_percent, new_percent):
                return True
        return False

    def stop_all_channels(self) -> bool:
        result = True
        for channel, fan in self.channels.items():
            result = result and self.stop_channel(channel, fan.get_current_pwm_as_percentage())
            fan.pwm = 0
        return result

    def stop_channel(self, channel: str, current_percent: int) -> bool:
        if self.is_valid:
            LogManager.logger.info(f"Stopping fan {repr({'controller': self.device.description, 'channel': channel})}")
            if self._set_channel_speed_smoothly(channel, current_percent, 0):
                return True
        return False

    def _set_channel_speed_smoothly(self, channel: str, current_percent: int, new_percent: int) -> bool:
        try:
            if new_percent >= current_percent:
                factor = 1
            else:
                factor = -1
            steps = int(((new_percent - current_percent) * factor) / self.RPM_STEP) + 1
            for i in range(1, steps):
                duty = int(current_percent + i * factor * self.RPM_STEP)
                LogManager.logger.trace(f"Adjusting fan speed {repr({'controller': self.device.description, 'channel': channel, 'duty': duty})}")
                self._safe_call_controller_function(lambda: self.device.set_fixed_speed(channel=channel, duty=duty))
                time.sleep(self.RPM_INTERVAL)
            LogManager.logger.trace(f"Adjusting fan speed {repr({'controller': self.device.description, 'channel': channel, 'duty': new_percent})}")
            self._safe_call_controller_function(lambda: self.device.set_fixed_speed(channel=channel, duty=new_percent))
            return True
        except BaseException:
            LogManager.logger.exception(f"Error in setting fan speed {repr({'controller': self.device.description, 'channel': channel})}")
        return False

    def _safe_call_controller_function(self, function):
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


class ControllerManager(object):
    fan_controller: List[FanController] = []

    @staticmethod
    def identify_fan_controllers():
        devices = find_liquidctl_devices()
        index = 0
        for dev in devices:
            controller: FanController = FanController()
            if type(dev) == liquidctl.driver.commander_pro.CommanderPro:
                LogManager.logger.info(f"Fan controller found {repr({'index': index, 'controller': dev.description})}")
                controller = CommanderProController(dev)
            elif type(dev) == liquidctl.driver.hydro_platinum.HydroPlatinum:
                LogManager.logger.info(f"Fan controller found {repr({'index': index, 'controller': dev.description})}")
                controller = HydroPlatinumController(dev)
            if controller.is_initialized():
                ControllerManager.fan_controller.append(controller)
                index += 1


class CommanderProController(FanController, ContextManager):

    def __init__(self, device: liquidctl.driver.commander_pro.CommanderPro):
        self.device: liquidctl.driver.commander_pro.CommanderPro = device
        super().__init__()

    def detect_channels(self):
        if self.is_valid:
            try:
                fan_modes = self._safe_call_controller_function(lambda: self.device._data.load(key='fan_modes', default=[0] * self.device._fan_count))
                LogManager.logger.debug(f"Detected fan channels {repr({'controller': self.device.description, 'fan_modes': fan_modes})}")
                for i, fan_mode in enumerate(fan_modes):
                    if fan_mode == 0x02:
                        channel = f"fan{i + 1}"
                        self.channels[channel] = PWMFan(channel, FanCurve.zero_rpm_curve(), DummySensor())
            except BaseException:
                LogManager.logger.exception(f"Error in detecting fan channels {repr({'controller': self.device.description})}")

    def get_channel_speed(self, channel: str) -> int:
        if self.is_valid:
            fan_index = int(channel[-1]) - 1
            LogManager.logger.trace(f"Getting fan speed {repr({'controller': self.device.description, 'channel': channel, 'index': fan_index})}")
            try:
                rpm = self._safe_call_controller_function(lambda: self.device._get_fan_rpm(fan_num=fan_index))
                return rpm
            except Exception as err:
                LogManager.logger.exception(f"Error in getting fan speed {repr({'controller': self.device.description, 'channel': channel})}")
        return 0


class HydroPlatinumController(FanController, ContextManager):

    def __init__(self, device: liquidctl.driver.hydro_platinum.HydroPlatinum):
        self.channel_offsets = {'fan1': 14, 'fan2': 21, 'fan3': 42}
        self.device: liquidctl.driver.hydro_platinum.HydroPlatinum = device
        super().__init__()

    def detect_channels(self):
        if self.is_valid:
            for i in range(len(self.device._fan_names)):
                channel = f"fan{i + 1}"
                self.channels[channel] = PWMFan(channel, FanCurve.zero_rpm_curve(), DummySensor())
            LogManager.logger.debug(f"Detected fan channels {repr({'controller': self.device.description, 'channels': self.channels.keys()})}")

    def get_channel_speed(self, channel: str) -> int:
        if self.is_valid:
            LogManager.logger.trace(f"Getting fan speed {repr({'controller': self.device.description, 'channel': channel})}")
            try:
                res = self._safe_call_controller_function(lambda: self.device._send_command(0b00, 0xff))
                offset = self.channel_offsets[channel] + 1
                rpm = int.from_bytes(res[offset:offset+2], byteorder='little')
                return rpm
            except BaseException:
                LogManager.logger.exception(f"Error in getting fan speed {repr({'controller': self.device.description, 'channel': channel})}")
        return 0
