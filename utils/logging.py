import logging as _logging
import re
import time
from pathlib import Path
from typing import Dict

import mininet.log
from mininet.log import lg

from .config import RESULT_DIR, config

class PasswordMaskingFormatter(_logging.Formatter):
    def __init__(self, *args, client_password=None, server_password=None, **kwargs):
        super().__init__(*args, **kwargs)
        password_pattern = r"({client_password}|{server_password})".format(
            client_password=re.escape(client_password or ""),
            server_password=re.escape(server_password or ""),
        )
        self.password_regex = re.compile(password_pattern)

    def format(self, record):
        msg = super().format(record)
        msg = self.password_regex.sub("****", msg)
        return msg


class _LoggerSetup:
    def __init__(self):
        self.logging_handlers: Dict[str, _logging.Handler] = dict()
        self.physial_config = config.topology.get("physical", None)

        self._create_file_handler()
        self._create_stdout_handler()

        # Set up Mininet with the same handlers
        lg.handlers = list(self.logging_handlers.values())

        mininet.log.setLogLevel(str(config.logging.file_level).lower())

    def _create_file_handler(self):
        if "file" in self.logging_handlers:
            return

        # Create formatters
        file_formatter = PasswordMaskingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]",
            client_password=(
                self.physial_config.client.get("password", None)
                if self.physial_config
                else None
            ),
            server_password=(
                self.physial_config.server.get("password", None)
                if self.physial_config
                else None
            ),
        )

        # Define the log file path
        log_file_path = RESULT_DIR / "system.log"

        # Create and configure a file handler for DEBUG level
        file_handler = _logging.FileHandler(log_file_path)
        file_level = _logging.getLevelName(config.logging.file_level)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)

        self.logging_handlers["file"] = file_handler

    def _create_stdout_handler(self):
        if "stdout" in self.logging_handlers:
            return

        stdout_formatter = PasswordMaskingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            client_password=(
                self.physial_config.client.get("password", None)
                if self.physial_config
                else None
            ),
            server_password=(
                self.physial_config.server.get("password", None)
                if self.physial_config
                else None
            ),
        )

        # Create and configure a stream handler for STDOUT
        stdout_handler = _logging.StreamHandler()
        stdout_level = _logging.getLevelName(config.logging.stdout_level)
        stdout_handler.setLevel(stdout_level)
        stdout_handler.setFormatter(stdout_formatter)

        self.logging_handlers["stdout"] = stdout_handler

    def setup_logger(self, name: str):
        # Save the current logger class
        current_logger_class = _logging.getLoggerClass()

        try:
            # Temporarily set the logger class to the default
            _logging.setLoggerClass(_logging.Logger)

            # Create the logger
            logger = _logging.getLogger(name)
            logger.setLevel(_logging.DEBUG)

            # Add handlers to the logger if they haven't been added yet
            if not logger.hasHandlers():
                for handler in self.logging_handlers.values():
                    logger.addHandler(handler)
        finally:
            # Restore the original logger class
            _logging.setLoggerClass(current_logger_class)

        return logger


_LOGGER_SETUP = _LoggerSetup()
_ALL_LOGGERS = []
MAIN_LOGGER = _LOGGER_SETUP.setup_logger("MainLogger")


def setup_class_logger(cls):
    cls_name = cls.__name__
    mangled_logger_name = f"_{cls_name}__logger"
    class_logger = _LOGGER_SETUP.setup_logger(cls.__name__)
    _ALL_LOGGERS.append(class_logger)
    setattr(cls, mangled_logger_name, class_logger)
    return cls


class LoggerMetaclass(type):
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        mangled_logger_name = f"_{name}__logger"
        setattr(
            new_class,
            mangled_logger_name,
            _LOGGER_SETUP.setup_logger(new_class.__name__),
        )
        return new_class
