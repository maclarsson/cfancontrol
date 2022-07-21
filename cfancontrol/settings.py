import os
import logging
from xdg.BaseDirectory import xdg_config_home, xdg_state_home
from typing import Dict

import yaml

from .log import LogManager
from cfancontrol import __version__ as VERSION


class Environment(object):

    APP_NAME: str = "cfancontrol"
    APP_FANCY_NAME: str = "Commander²"
    APP_VERSION: str = VERSION
    LOG_FILE: str = 'cfancontrol.log'
    CONFIG_FILENAME: str = 'config.yaml'

    is_root: bool = False
    log_path: str = ''
    log_full_name: str = ''
    settings_path: str = ''
    config_full_name: str = ''
    pid_path: str = ''

    @staticmethod
    def prepare_environment():
        if os.geteuid() == 0:
            Environment.is_root = True
            Environment.log_path = "/var/log"
            Environment.settings_path = os.path.join("/etc", Environment.APP_NAME)
            Environment.pid_path = "/var/run"
        else:
            Environment.log_path = os.path.join(xdg_state_home, Environment.APP_NAME)
            Environment.settings_path = os.path.join(xdg_config_home, Environment.APP_NAME)
            Environment.pid_path = f"/var/run/user/{os.geteuid()}"
        if not os.path.isdir(Environment.log_path):
            os.makedirs(Environment.log_path, mode=0o755, exist_ok=True)
        if not os.path.isdir(Environment.settings_path):
            os.makedirs(Environment.settings_path, mode=0o755, exist_ok=True)
        Environment.log_full_name = os.path.join(Environment.log_path, Environment.LOG_FILE)
        Environment.config_full_name = os.path.join(Environment.settings_path, Environment.CONFIG_FILENAME)


class Config(object):
    interval: float = 10.0
    auto_start: bool = False
    profile_file: str = ''
    log_level: int = logging.INFO
    theme: str = 'light'

    @classmethod
    def from_arguments(cls, **kwargs):
        for attr in kwargs:
            setattr(cls, attr, kwargs[attr])
        if cls.profile_file:
            if os.path.isfile(os.path.expanduser(cls.profile_file)):
                cls.profile_file = os.path.expanduser(cls.profile_file)
            else:
                cls.profile_file = ''
                cls.auto_start = False
        else:
            cls.auto_start = False

    @classmethod
    def get_settings(cls) -> Dict:
        return {name: value for name, value in vars(cls).items() if not callable(getattr(cls, name)) and not name.startswith("__")}

    @classmethod
    def load_settings(cls):
        if Environment.config_full_name:
            cls._load_from_file(Environment.config_full_name)

    @classmethod
    def _load_from_file(cls, file_name: str):
        if file_name is not None and os.path.isfile(file_name):
            LogManager.logger.debug(f'Loading configuration from {file_name}')
            with open(file_name) as config_file:
                config = yaml.safe_load(config_file)
                if config:
                    cls.from_arguments(**config)

    @classmethod
    def save_settings(cls):
        if Environment.config_full_name:
            cls._save_to_file(Environment.config_full_name)

    @classmethod
    def _save_to_file(cls, file_name: str):
        if file_name is not None:
            LogManager.logger.debug(f'Saving configuration: {repr(cls.get_settings())}')
            with open(file_name, 'w') as config_file:
                yaml.safe_dump(cls.get_settings(), config_file)
