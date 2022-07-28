import logging
import logging.config
from logging.handlers import RotatingFileHandler

TRACE_LEVEL: int = 5


class ExtendedLogger(logging.Logger):

    def __init__(self, name: str):
        super().__init__(name)
        logging.addLevelName(TRACE_LEVEL, 'TRACE')
        setattr(logging, 'TRACE', TRACE_LEVEL)

        self.addHandler(self.get_file_handler())
        self.addHandler(self.get_console_handler())

    @staticmethod
    def get_file_handler() -> logging.FileHandler:
        log_file_handler = logging.handlers.RotatingFileHandler(LogManager.log_file, maxBytes=1048576, backupCount=2)
        log_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s | %(module)-20s | %(funcName)-30s | %(lineno)-4d | %(message)s"))
        return log_file_handler

    @staticmethod
    def get_console_handler() -> logging.StreamHandler:
        log_console_handler = logging.StreamHandler()
        log_console_handler.setFormatter(logging.Formatter("[%(levelname)-8s] %(module)-20s | %(message)s"))
        return log_console_handler

    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)


class LogManager:

    LOGGER_NAME: str = 'cfancontrol'

    log_file: str = ''
    log_level: int = 0
    log_file_handler: logging.handlers.RotatingFileHandler
    log_console_handler: logging.StreamHandler
    logger: ExtendedLogger

    @classmethod
    def init_logging(cls, log_file: str, log_level: int):
        LogManager.log_level = log_level
        LogManager.log_file = log_file

        logging.setLoggerClass(ExtendedLogger)
        cls.logger = logging.getLogger(LogManager.LOGGER_NAME)

        LogManager.logger.debug(f"Logger initialized with log level: {log_level}")

    @classmethod
    def set_log_level(cls, log_level: int):
        cls.logger.log(cls.logger.level, f"Setting logging to level {log_level}")
        cls.logger.setLevel(log_level)

