import logging
import logging.config
from logging.handlers import RotatingFileHandler


class LogManager:

    LOGGER_NAME: str = 'cfancontrol'
    log_file: str = ''
    log_level: int = 0
    log_file_handler: logging.handlers.RotatingFileHandler
    log_console_handler: logging.StreamHandler
    logger: logging.Logger

    @classmethod
    def init_logging(cls, log_file: str, log_level: int):
        LogManager.log_level = log_level
        LogManager.log_file = log_file

        cls.logger = logging.getLogger(LogManager.LOGGER_NAME)
        cls.logger.addHandler(LogManager.get_file_handler())
        cls.logger.addHandler(LogManager.get_console_handler())
        cls.set_log_level(log_level)
        LogManager.logger.debug(f"Logger initialized with log level: {log_level}")

    @staticmethod
    def get_file_handler() -> logging.FileHandler:
        log_file_handler = logging.handlers.RotatingFileHandler(LogManager.log_file, maxBytes=2097152, backupCount=3)
        # log_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s:%(message)s"))
        log_file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(module)-20s: %(funcName)-30s: %(lineno)-4d : %(message)s"))
        return log_file_handler

    @staticmethod
    def get_console_handler() -> logging.StreamHandler:
        log_console_handler = logging.StreamHandler()
        log_console_handler.setFormatter(logging.Formatter("[%(levelname)-8s] %(module)-20s: %(message)s"))
        return log_console_handler

    @classmethod
    def set_log_level(cls, log_level: int):
        cls.logger.log(cls.logger.level, f"Setting logging to level {log_level}")
        cls.logger.setLevel(log_level)
