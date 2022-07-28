import os
import signal
import threading
from contextlib import ExitStack
from typing import Optional, List, Dict

from .log import LogManager
from .settings import Environment, Config
from .fancontroller import ControllerManager, FanController, CommanderProController
from .fancurve import FanCurve, FanMode
from .pwmfan import PWMFan
from .sensor import Sensor
from .sensormanager import SensorManager
from .devicesensor import AIODeviceSensor
from .profilemanager import ProfileManager


class FanManager:

    _is_running: bool
    _active_controller: Optional[FanController]
    _fan_controller: Dict[int, FanController]
    _interval: float
    manager_thread: threading.Thread

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

        # identify fan controllers
        ControllerManager.identify_fan_controllers()
        self._fan_controller = {i: j for i, j in enumerate(ControllerManager.fan_controller)}
        if not self.has_controller():
            Config.auto_start = False

    def __enter__(self):
        self._stack = ExitStack()
        try:
            for sensor in self._sensors:
                if isinstance(sensor, AIODeviceSensor):
                    self._stack.enter_context(sensor)
            for controller in self._fan_controller.values():
                self._stack.enter_context(controller)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self._stack is not None:
            self._stack.close()
        return None

    def get_active_controller(self) -> Optional[FanController]:
        return self._active_controller

    def set_controller(self, index: int) -> bool:
        if self._fan_controller.get(index):
            self._active_controller = self._fan_controller[index]
            return True
        else:
            self._active_controller = FanController()
            LogManager.logger.warning(f"Fan controller with index '{index}' not found in the system")
            return False

    def has_controller(self) -> bool:
        if self._fan_controller:
            return True
        return False

    def controller_count(self) -> int:
        if self._fan_controller:
            return len(self._fan_controller)
        return 0

    def get_controller_names(self) -> List[str]:
        return [c.get_name() for c in self._fan_controller.values()]

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
                LogManager.logger.critical("Aborting fan manager")
                self._is_running = False
                aborted = True
                break

        try:
            for controller in self._fan_controller.values():
                controller.stop_all_channels()
        except BaseException:
            LogManager.logger.exception("Error while stopping fan channels")

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
        if not self.is_manager_running():
            self.manager_thread = threading.Thread(target=self.run)
            self.manager_thread.start()
            LogManager.logger.info("Fan manager thread started")
        else:
            LogManager.logger.warning("Cannot start fan manager - fan manager thread is already running")

    def stop(self):
        if self.is_manager_running():
            self._signals.sigterm(None, None)
            self.manager_thread.join()
            LogManager.logger.info("Fan manager thread stopped")

    def is_manager_running(self) -> bool:
        if self.manager_thread is not None and self.manager_thread.is_alive():
            return True
        else:
            return False

    def tick(self) -> None:
        if self.is_manager_running():
            for controller in self._fan_controller.values():
                for channel, fan in controller.channels.items():
                    update, new_pwm, new_percent, temperature = fan.update_pwm(controller.get_channel_speed(channel))
                    if update:
                        if controller.set_channel_speed(channel, new_pwm, fan.get_current_pwm_as_percentage(), new_percent, temperature):
                            fan.set_current_pwm(new_pwm)

    def update_interval(self, interval: float):
        self._interval = interval

    def apply_fan_mode(self, channel: str, sensor: int, curve_data: FanCurve, profile=None):
        fan: PWMFan = self._active_controller.channels.get(channel)
        if fan:
            fan.temp_sensor = self._sensors[sensor]
            fan.fan_curve = curve_data
            self.tick()
            if profile:
                self.save_profile(profile)

    def get_active_channels(self) -> int:
        return len(self._active_controller.channels)

    def get_pwm_fan(self, channel: str):
        return self._active_controller.channels.get(channel)

    def get_channel_status(self, channel: str) -> (bool, FanMode, int, int, int, float):
        return self._active_controller.get_channel_status(channel)

    def get_channel_sensor(self, channel: str) -> int:
        fan: PWMFan = self._active_controller.channels.get(channel)
        if fan:
            return self._sensors.index(fan.temp_sensor)
        return 0

    def get_channel_fancurve(self, channel: str) -> Optional[FanCurve]:
        fan: PWMFan = self._active_controller.channels.get(channel)
        if fan:
            return fan.fan_curve
        return None

    @staticmethod
    def load_profile(file_name: str) -> str:
        profile_name = ProfileManager.add_profile(file_name)
        return profile_name

    def save_profile(self, profile_name: str) -> (bool, str):
        success, saved_profile = ProfileManager.save_profile(profile_name, self._serialize_profile_to_json())
        return success, saved_profile

    def set_profile(self, profile_name: str) -> (bool, str):
        for controller in self._fan_controller.values():
            controller.reset_channels(self._sensors[0])
        if profile_name:
            profile_data = ProfileManager.get_profile_data(profile_name)
            if profile_data:
                Config.profile_file = ProfileManager.profiles[profile_name]
                self._deserialize_profile_from_json(profile_data)
                self.tick()
                return True, os.path.basename(Config.profile_file)
        Config.profile_file = ''
        self.tick()
        return False, ''

    def _serialize_profile_to_json(self) -> Dict[str, dict]:
        profile_dict: Dict[str, any] = dict()
        profile_dict["version"] = "1"
        controllers_list: List[dict] = list()
        index = 0
        for controller in self._fan_controller.values():
            channel_dict: Dict[str, dict] = dict()
            for channel, fan in controller.channels.items():
                channel_dict[channel] = {"curve": fan.fan_curve.get_graph_points_from_curve(), "sensor": fan.temp_sensor.get_signature()}
            controller_dict: Dict[str, any] = dict()
            controller_dict["id"] = index
            controller_dict["name"] = controller.get_name()
            controller_dict["class"] = controller.__class__.__name__
            controller_dict["channels"] = channel_dict
            controllers_list.append(controller_dict)
            index += 1
        profile_dict["controllers"] = controllers_list
        return profile_dict

    def _deserialize_profile_from_json(self, profile_data: dict):
        if profile_data:
            version = profile_data.get("version")
            if version == "1":
                saved_controllers_list = profile_data.get("controllers")
                for index, controller in self._fan_controller.items():
                    if len(saved_controllers_list) > index:
                        saved_controller = saved_controllers_list[index]
                        if saved_controller:
                            if saved_controller["class"] == controller.__class__.__name__:
                                saved_channels = saved_controller.get("channels")
                                self._deserialize_channel_config(saved_channels, controller.channels)
                                continue
            else:
                for index, controller in self._fan_controller.items():
                    if type(controller) == CommanderProController:
                        self._deserialize_channel_config(profile_data, controller.channels)

    def _deserialize_channel_config(self, saved_channels, controller_channels):
        if saved_channels:
            for channel, fan in controller_channels.items():
                channel_config = saved_channels.get(channel)
                if channel_config:
                    sensor_config = channel_config["sensor"]
                    sensor = [s for s in self._sensors if s.get_signature() == sensor_config]
                    if sensor:
                        fan.temp_sensor = sensor[0]
                        fan.fan_curve.set_curve_from_graph_points(channel_config["curve"])
                        continue


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
