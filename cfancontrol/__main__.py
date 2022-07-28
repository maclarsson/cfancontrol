import os
import argparse
import logging
import sys

from pid import PidFile, PidFileAlreadyLockedError

from .settings import Environment, Config
from . import app as app
from .log import LogManager
from .fanmanager import FanManager
from .__init__ import __version__


def parse_settings() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["daemon", "gui"], help="mode to run cfancontrol (daemon or gui)")
    parser.add_argument("-a", "--autostart", action="store_true", dest="auto_start",
                        help="auto start fan manager (requires profile)")
    parser.add_argument("-i", "--interval", type=float, action="store", default=10.0,
                        dest="interval", help="update interval for fan manager")
    parser.add_argument("-p", "--profile", type=str, action="store", default=None, dest="profile_file",
                        help="profile file to load at startup")
    parser.add_argument("-l", "--loglevel", type=int, action="store", dest="log_level",
                        choices=[logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR],
                        default=logging.INFO, help="log level")
    parser.add_argument("-t", "--theme", type=str, action="store", dest="theme", choices=["light", "dark", "system"], default="system", help="application theme")
    parser.add_argument("-s", action="store_true", dest="load_settings", help="load settings from file")

    args = parser.parse_args()

    if args.load_settings:
        Config.load_settings()
    else:
        args_dict = vars(args)
        args_dict["auto_start"] = True
        args_dict.pop("load_settings")
        Config.from_arguments(**args_dict)

    return args


def main():
    Environment.prepare_environment()

    LogManager.init_logging(Environment.log_full_name, Config.log_level)

    args = parse_settings()

    LogManager.set_log_level(Config.log_level)
    LogManager.logger.info(f'Starting {Environment.APP_FANCY_NAME} version {__version__} with configuration: {repr(Config.get_settings())}')

    try:
        with PidFile(Environment.APP_NAME, piddir=Environment.pid_path) as pid:
            manager = FanManager()
            with manager:
                if args.mode == "gui":
                    app.main(manager, not Config.auto_start, Config.theme)
                else:
                    if not manager.has_controller():
                        LogManager.logger.critical(f"No supported fan controller found -> please check system configuration and restart {Environment.APP_FANCY_NAME}")
                        return
                    if not Config.profile_file or Config.profile_file == '':
                        LogManager.logger.critical(f"No profile file specified for daemon mode -> please us -p option to specify a profile")
                        return
                    manager.set_profile(os.path.splitext(os.path.basename(Config.profile_file))[0])
                    manager.toggle_manager(True)
                    manager.manager_thread.join()
    except PidFileAlreadyLockedError:
        if args.mode == "gui":
            app.warning_already_running()
        LogManager.logger.critical(f"PID file '{Environment.pid_path}/{Environment.APP_NAME}.pid' already exists - cfancontrol is already running or was not completed properly before -> STOPPING")
    except RuntimeError:
        LogManager.logger.exception(f"{Environment.APP_FANCY_NAME} stopped with runtime error")
    except BaseException:
        LogManager.logger.exception(f"{Environment.APP_FANCY_NAME} stopped with unknown error")
    else:
        LogManager.logger.info(f"{Environment.APP_FANCY_NAME} ended normally")


if __name__ == "__main__":
    main()
