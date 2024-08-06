from __future__ import annotations

import typing
from abc import ABC, abstractmethod

from utils.logging import setup_class_logger

if typing.TYPE_CHECKING:
    from testbeds.itestbed import IHost


class IScheduler(ABC):

    @property
    @abstractmethod
    def set_scheduler(self):
        pass

    @property
    @abstractmethod
    def load(self):
        pass

    @property
    @abstractmethod
    def unload(self):
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
class BaseScheduler(IScheduler):
    def __init__(self, name, client: IHost, server: IHost, syscall_name=None):
        super().__init__()
        self._name = name
        self._syscall_name = syscall_name or name
        self.client = client
        self.server = server
        self.executors = [self.client, self.server]

    def __enter__(self):
        self.load()
        self.set_scheduler()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload()

    def _execute(self, cmd):
        self.__logger.debug(f"Executing command {cmd} on {self.executors}")
        for executor in self.executors:
            executor.set_system_commands(cmd)

    def load(self):
        cmd = f"sudo modprobe mptcp_{self.syscall_name}"
        self.__logger.info(f"Loading scheduler {self.name} on all executors")
        self._execute(cmd)

    def unload(self):
        cmd = f"sudo rmmod mptcp_{self.syscall_name}"
        self.__logger.info(f"Unloading scheduler {self.name} on all executors")

        for executor in self.executors:
            try:
                executor.set_system_commands(cmd)
            except Exception as e:
                error_msg = str(e)
                if "is not currently loaded" in error_msg:
                    self.__logger.warning(
                        f"Scheduler {self.name} was not loaded on {executor}"
                    )
                else:
                    self.__logger.error(
                        f"Error while unloading scheduler {self.name} on {executor}: {error_msg}"
                    )

    def set_scheduler(self):
        cmd = f"sudo sysctl -w net.mptcp.mptcp_scheduler={self.syscall_name}"
        self._execute(cmd)

    @property
    def name(self):
        return self._name

    @property
    def syscall_name(self):
        return self._syscall_name


class BuiltInScheduler(BaseScheduler):
    pass


class RLScheduler(BaseScheduler):
    pass
