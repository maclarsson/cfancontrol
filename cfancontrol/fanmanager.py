import os
import signal
import threading
from contextlib import ExitStack
from typing import Optional, List, Dict

from .log import LogManager
from .settings import Environment, Config
from .fancontroller import FanController
from .fancurve import FanCurve, FanMode
from .pwmfan import PWMFan
from .sensor import Sensor, DummySensor
from .sensormanager import SensorManager
from .devicesensor import AIODeviceSensor
from .profilemanager import ProfileManager


class FanManager:

    _is_running: bool
    _controller: FanController
    _interval: float
    manager_thread: threading.Thread
    _channels: Dict[str, PWMFan]

    def __init__(self):
        self._interval = Config.interval
        self._signals = Signals()
        self._callback = None
        self.manager_thread: Optional[threading.Thread] = None

        # register system signals to react to
        signal.signal(signal.SIGTERM, self._signals.sigterm)
        signal.signal(signal.SIGQUIT, self._signals.sigterm)
        signal.signal(signal.SIGINT, self._signals.sigterm)
        signal.signal(signal.SIGHUP, self._signals.sigterm)

        self._stack = ExitStack()

        # identify system sensors from fan manager
        SensorManager.identify_system_sensors()
        self._sensors: List[Sensor] = SensorManager.system_sensors

        # get all profiles
        ProfileManager.enum_profiles(Environment.settings_path)

        # get active channels from controller
        self._controller: FanController = FanController()
        self._controller_channels = self._controller.detect_channels()
        self.reset_channels(self._controller_channels)

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        try:
            for sensor in self._sensors:
                if isinstance(sensor, AIODeviceSensor):
                    self._stack.enter_context(sensor)
            self._stack.enter_context(self._controller)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self._stack is not None:
            self._stack.close()
        return None

    def get_controller(self) -> Optional[FanController]:
        return self._controller

    def reset_channels(self, channels: List[str]):
        self._channels = dict()
        for channel in channels:
            self._channels[channel] = PWMFan(channel, FanCurve.zero_rpm_curve(), DummySensor())

    def set_callback(self, callback):
        self._callback = callback

    def run(self) -> bool:

        self.tick()
        aborted: bool = False
        while not self._signals.wait_for_term_queued(self._interval):
            try:
                self.tick()
            except Exception:
                LogManager.logger.exception(f"Unhandled exception in fan manager")
                LogManager.logger.critical("Aborting manager")
                self._is_running = False
                aborted = True
                break

        for channel, fan in self._channels.items():
            self._controller.stop_channel(channel)
            fan.pwm = 0

        self._signals.reset()

        if self._callback:
            self._callback(aborted)

        return aborted

    def toggle_manager(self, mode: bool):
        if mode:
            self.start()
        else:
            self.stop()

    def start(self):
        LogManager.logger.info("Starting fan manager")
        if not self.is_manager_running():
            LogManager.logger.info("Creating fan manager thread")
            self.manager_thread = threading.Thread(target=self.run)
            self.manager_thread.start()
        else:
            LogManager.logger.warning("Cannot start fan manager - fan manager is already running")

    def stop(self):
        if self.is_manager_running():
            LogManager.logger.info("Stopping fan manager")
            self._signals.sigterm(None, None)
            self.manager_thread.join()

    def is_manager_running(self) -> bool:
        if self.manager_thread is not None and self.manager_thread.is_alive():
            return True
        else:
            return False

    def tick(self) -> None:
        if self.is_manager_running():
            for channel, fan in self._channels.items():
                if fan:
                    update, new_pwm, pwm_percent, temperature = fan.update_pwm()
                    if update:
                        if self._controller.set_channel_speed(channel, new_pwm, pwm_percent, temperature):
                            fan.set_current_pwm(new_pwm)
                else:
                    LogManager.logger.warning(f"No fan for channel {channel} available")

    def update_interval(self, interval: float):
        self._interval = interval

    def apply_fan_mode(self, channel: str, sensor: int, curve_data: FanCurve, profile=None):
        # fan: PWMFan = self._controller.get_pwm_fan(channel)
        fan: PWMFan = self._channels.get(channel)
        if fan:
            fan.temp_sensor = self._sensors[sensor]
            fan.fan_curve = curve_data
            self.tick()
            if profile:
                self.save_profile(profile)

    def get_pwm_fan(self, channel: str):
        return self._channels.get(channel)

    def get_channel_status(self, channel: str) -> (bool, int, int, int, float):
        fan: PWMFan = self._channels.get(channel)
        if fan:
            speed = self._controller.get_channel_speed(channel)
            return True, fan.fan_curve.get_fan_mode(), fan.get_current_pwm(), fan.get_current_pwm_as_percentage(), speed, fan.get_current_temp()
        return False, FanMode.Off, 0, 0, 0, 0.0

    def get_channel_sensor(self, channel: str) -> int:
        fan: PWMFan = self._channels.get(channel)
        if fan:
            return self._sensors.index(fan.temp_sensor)
        return 0

    def get_channel_fancurve(self, channel: str) -> Optional[FanCurve]:
        fan: PWMFan = self._channels.get(channel)
        if fan:
            return fan.fan_curve
        return None

    @staticmethod
    def load_profile(file_name: str) -> str:
        profile_name = ProfileManager.add_profile(file_name)
        return profile_name

    def save_profile(self, profile_name: str) -> (bool, str):
        success, saved_profile = ProfileManager.save_profile(profile_name, self.serialize_to_json())
        return success, saved_profile

    def set_profile(self, profile_name: str) -> (bool, str):
        self.reset_channels(self._controller_channels)
        if profile_name:
            profile_data = ProfileManager.get_profile_data(profile_name)
            if profile_data:
                Config.profile_file = ProfileManager.profiles[profile_name]
                self.deserialize_from_json(profile_data)
                self.tick()
                return True, os.path.basename(Config.profile_file)
        Config.profile_file = ''
        self.tick()
        return False, ''

    def serialize_to_json(self):
        channel_dict: Dict[str, dict] = dict()
        for channel, fan in self._channels.items():
            channel_dict[channel] = {"curve": fan.fan_curve.get_graph_points_from_curve(), "sensor": fan.temp_sensor.get_signature()}
        return channel_dict

    def deserialize_from_json(self, profile_data: dict):
        if profile_data:
            for channel, fan in self._channels.items():
                channel_config = profile_data.get(channel)
                if channel_config:
                    sensor_config = channel_config["sensor"]
                    sensor = [s for s in self._sensors if s.get_signature() == sensor_config]
                    if sensor:
                        fan.temp_sensor = sensor[0]
                        fan.fan_curve.set_curve_from_graph_points(channel_config["curve"])


class Signals:

    def __init__(self):
        self._term_event = threading.Event()

    def sigterm(self, signum, stackframe):
        self._term_event.set()

    def reset(self):
        self._term_event.clear()

    def wait_for_term_queued(self, seconds: float) -> bool:
        is_set = self._term_event.wait(seconds)
        if is_set:
            return True
        return False
