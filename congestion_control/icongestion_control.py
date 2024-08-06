# congestion_control/icongestion_control.py
from __future__ import annotations

import re
import typing
from abc import ABC, abstractmethod

from testbeds.itestbed import CommandExecutionError
from utils.logging import setup_class_logger

if typing.TYPE_CHECKING:
    import logging

    from testbeds.itestbed import IHost


class ICongestionControl(ABC):
    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def unload(self):
        pass

    @abstractmethod
    def set_congestion_control(self):
        pass

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def syscall_name(self):
        pass


@setup_class_logger
class BaseCongestionControl(ICongestionControl):
    __logger: typing.ClassVar[logging.Logger]

    def __init__(self, name, client: IHost, server: IHost, syscall_name=None):
        super().__init__()
        self._name = name
        self._syscall_name = syscall_name or name
        self.client = client
        self.server = server
        self.executors = [self.client, self.server]

    def __enter__(self):
        self.load()
        self.set_congestion_control()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload()

    def _execute(self, cmd):
        for executor in self.executors:
            executor.set_system_commands(cmd)

    def load(self):
        cmd = f"sudo modprobe mptcp_{self.syscall_name}"
        self._execute(cmd)

    def unload(self):
        cmd = f"sudo rmmod mptcp_{self.syscall_name}"
        module_in_use_pattern = re.compile(r"ERROR: Module mptcp_\w+ is in use")
        try:
            self._execute(cmd)
        except CommandExecutionError as e:
            if module_in_use_pattern.search(str(e)):
                self.__logger.warning(
                    f"Unable to unload {self.name} module as it's still in use. This is not necessarily an error."
                )
            else:
                raise

    def set_congestion_control(self):
        cmd = f"sudo sysctl -w net.ipv4.tcp_congestion_control={self.syscall_name}"
        self._execute(cmd)

    @property
    def name(self):
        return self._name

    @property
    def syscall_name(self):
        return self._syscall_name
