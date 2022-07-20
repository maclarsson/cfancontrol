import os
import json
import pprint
from typing import Optional, Dict, List

from .log import LogManager


class Profile(object):

    label: str
    file_name: str

    def __init__(self, label, file_name):
        self.label = label
        self.file_name = file_name


class ProfileManager(object):

    profiles_path: str
    profiles: Dict[str, str] = dict()

    @classmethod
    def enum_profiles(cls, profile_path):
        cls.profiles["<none>"] = ""
        cls.profiles_path = profile_path
        for profile in [f for f in os.listdir(profile_path) if f.endswith(".cfp")]:
            cls.profiles[os.path.splitext(os.path.basename(profile))[0]] = os.path.join(profile_path, profile)

    @classmethod
    def add_profile(cls, file_name) -> str:
        profile = os.path.splitext(os.path.basename(file_name))[0]
        cls.profiles[profile] = file_name
        return profile

    @classmethod
    def save_profile(cls, profile_name: str, profile_data: dict) -> (bool, str):
        file_name: str = os.path.join(cls.profiles_path, profile_name)
        success, file_name = cls._write_profile(file_name, profile_data)
        if success:
            return success, cls.add_profile(file_name)
        return success, ""

    @classmethod
    def remove_profile(cls, profile) -> bool:
        file_name = cls.profiles[profile]
        success = cls._delete_profile(file_name)
        if success:
            cls.profiles.pop(profile)
        return success

    @classmethod
    def get_profile_from_file_name(cls, file_name) -> str:
        profile = "<none>"
        profiles = [k for k, v in cls.profiles.items() if v == file_name]
        if profiles:
            profile = profiles[0]
        return profile

    @classmethod
    def get_file_name_from_profile(cls, profile) -> str:
        return cls.profiles[profile]

    @classmethod
    def get_profile_data(cls, profile_name: str) -> Optional[dict]:
        file_name = cls.profiles[profile_name]
        if file_name and file_name != '':
            profile_data = cls._read_profile(file_name)
            return profile_data
        return None

    @staticmethod
    def _read_profile(file_name: str) -> Optional[dict]:
        try:
            with open(file_name, 'r') as json_file:
                profile_data = json.load(json_file)
        except OSError:
            LogManager.logger.exception(f"OS error loading profile: {file_name}")
        except Exception:
            LogManager.logger.exception(f"Exception loading profile: {file_name}")
        else:
            return profile_data
        return None

    @staticmethod
    def _write_profile(file_name: str, profile_data: dict) -> [bool, str]:
        success = False
        if file_name is not None and file_name != '':
            if not file_name.endswith('.cfp'):
                file_name = file_name + '.cfp'
            try:
                LogManager.logger.info(f"Saving profile '{file_name}'")
                json_data = pprint.pformat(profile_data).replace("'", '"')
                with open(file_name, 'w') as json_file:
                    json_file.write(json_data)
                success = True
            except OSError:
                LogManager.logger.exception(f"OS error saving profile: '{file_name}'")
            except Exception:
                LogManager.logger.exception(f"Exception saving profile: '{file_name}"'')
        return success, file_name

    @staticmethod
    def _delete_profile(file_name: str) -> bool:
        success = False
        if os.path.isfile(file_name) and os.path.exists(file_name):
            try:
                os.remove(file_name)
                success = True
            except OSError:
                LogManager.logger.exception(f"OS error deleting profile: {file_name}")
            except Exception:
                LogManager.logger.exception(f"Exception deleting profile: {file_name}")
        return success
