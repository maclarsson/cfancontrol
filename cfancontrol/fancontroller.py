import threading
from typing import Dict, Optional, List, ContextManager

import liquidctl.driver.commander_pro
from liquidctl import find_liquidctl_devices

from .log import LogManager


class FanController(ContextManager):

    @classmethod
    def get_commander(cls) -> Optional[liquidctl.driver.commander_pro.CommanderPro]:
        devices = find_liquidctl_devices()
        for dev in devices:
            if 'Commander' in dev.description:
                LogManager.logger.info("Fan controller 'Commander Pro' found")
                return dev
        return None

    def __init__(self) -> None:
        self.is_valid = False
        self._lock = threading.Lock()
        self.commander = self.get_commander()
        if self.commander:
            try:
                self.commander.connect()
                LogManager.logger.info("Fan controller connected")
                init_message = self.commander.initialize()
                self.is_valid = True
                self.commander.disconnect()
                LogManager.logger.info(f"Fan controller successfully initialized {init_message}")
            except Exception as err:
                LogManager.logger.exception(f"Error in opening fan controller")
                raise RuntimeError("Cannot initialize fan controller")
            finally:
                self.commander.disconnect()
        else:
            LogManager.logger.critical("Fan controller not found -> STOPPING!")
            raise RuntimeError("No Commander Pro controller found")

    def __enter__(self):
        if self.commander:
            LogManager.logger.debug(f"Context manager for 'Commander Pro' started")
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        LogManager.logger.debug(f"Closing context for fan controller")
        if self.is_valid:
            self.commander.disconnect()
            del self.commander
            self.is_valid = False
            LogManager.logger.info("Fan controller disconnected and reference removed")
        return None

    def detect_channels(self) -> List[str]:
        channel_list = []
        LogManager.logger.info("Detecting fan channels of fan controller")
        if self.is_valid:
            try:
                fan_modes = self._safe_call_controller_function(lambda: self.commander._data.load(key='fan_modes', default=[0] * self.commander._fan_count))
                LogManager.logger.debug(f"Following fan channels detected: {fan_modes}")
                for i, fan_mode in enumerate(fan_modes):
                    if fan_mode == 0x02:
                        channel = f"fan{i + 1}"
                        channel_list.append(channel)
            except Exception:
                LogManager.logger.exception("Error in detecting fan channels")
        LogManager.logger.debug(f"Channels: {channel_list}")
        return channel_list

    def get_channel_speed(self, channel: str) -> int:
        if self.is_valid:
            fan_index = int(channel[-1]) - 1
            LogManager.logger.debug(f"Getting fan speed for channel '{channel}' with index {fan_index}")
            try:
                rpm = self._safe_call_controller_function(lambda: self.commander._get_fan_rpm(fan_num=fan_index))
                return rpm
            except Exception as err:
                LogManager.logger.exception(f"Problem in getting speed for channel '{channel}'")
        return 0

    def set_channel_speed(self, channel: str, new_pwm: int, pwm_percent: int, temperature: float) -> bool:
        if self.is_valid:
            LogManager.logger.info(f"Setting fan speed of channel '{channel}' to PWM {new_pwm} / {str(pwm_percent)}% for temperature {temperature}°C")
            try:
                self._safe_call_controller_function(lambda: self.commander.set_fixed_speed(channel=channel, duty=pwm_percent))
                return True
            except Exception as err:
                LogManager.logger.exception(f"Problem in setting speed for channel {channel}")
        return False

    def stop_channel(self, channel: str):
        if self.is_valid:
            LogManager.logger.info(f"Stopping channel '{channel}'")
            try:
                self._safe_call_controller_function(lambda: self.commander.set_fixed_speed(channel=channel, duty=0))
                LogManager.logger.debug("Channel stopped")
                return True
            except Exception as err:
                LogManager.logger.exception(f"Problem in stopping channel '{channel}'")

    def _safe_call_controller_function(self, function):
        self._lock.acquire()
        try:
            self.commander.connect()
            result = function()
        except Exception:
            raise
        finally:
            self.commander.disconnect()
            self._lock.release()
        return result
