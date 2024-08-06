from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from utils.logging import setup_class_logger

from .ischeduler import RLScheduler

# schedulers/reinforcement_learning_scheduler.py


if TYPE_CHECKING:
    import logging
    from typing import ClassVar

    from testbeds.itestbed import IHost


@setup_class_logger
class FALCONScheduler(RLScheduler):
    __logger: ClassVar[logging.Logger]

    _CURRENT_DIR = Path(__file__).resolve().parent
    _FALCON_KO_DIR = _CURRENT_DIR / "custom/falcon"

    def __init__(self, client: IHost, server: IHost, params):
        super().__init__(name="falcon", client=client, server=server)
        self.params = params

    def load(self):
        cmds = [
            "make",
            f"sudo insmod mptcp_{self.syscall_name}.ko",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "falcon",
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "File exists" in error_msg:
                        self.__logger.warning(error_msg)
                    else:
                        raise

    def unload(self):
        cmds = [
            "make clean",
            f"sudo rmmod mptcp_{self.syscall_name}",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "falcon",
                    )
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


@setup_class_logger
class RELESScheduler(RLScheduler):
    __logger: ClassVar[logging.Logger]
    _CURRENT_DIR = Path(__file__).resolve().parent
    _RELES_KO_DIR = _CURRENT_DIR / "custom/reles"

    def __init__(self, client, server, params):
        super().__init__(name="reles", client=client, server=server)
        self.params = params

    def load(self):
        cmds = [
            "make",
            f"sudo insmod mptcp_{self.syscall_name}.ko",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location / "schedulers" / "custom" / "reles",
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "File exists" in error_msg:
                        self.__logger.warning(error_msg)
                    else:
                        raise

    def unload(self):
        cmds = [
            "make clean",
            f"sudo rmmod mptcp_{self.syscall_name}",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location / "schedulers" / "custom" / "reles",
                    )
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


@setup_class_logger
class FALCONExtScheduler(RLScheduler):
    __logger: ClassVar[logging.Logger]

    _CURRENT_DIR = Path(__file__).resolve().parent
    _FALCON_EXT_KO_DIR = _CURRENT_DIR / "custom/falcon_ext"

    def __init__(self, client: IHost, server: IHost, params):
        super().__init__(name="falcon_ext", client=client, server=server)
        self.params = params

    def load(self):
        cmds = [
            "make",
            f"sudo insmod mptcp_{self.syscall_name}.ko",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "falcon_ext",
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "File exists" in error_msg:
                        self.__logger.warning(error_msg)
                    else:
                        raise

    def unload(self):
        cmds = [
            "make clean",
            f"sudo rmmod mptcp_{self.syscall_name}",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "falcon_ext",
                    )
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


@setup_class_logger
class RELESExtScheduler(RLScheduler):
    __logger: ClassVar[logging.Logger]

    _CURRENT_DIR = Path(__file__).resolve().parent
    _RELES_EXT_KO_DIR = _CURRENT_DIR / "custom/reles_ext"

    def __init__(self, client, server, params):
        super().__init__(name="reles_ext", client=client, server=server)
        self.params = params

    def load(self):
        cmds = [
            "make",
            f"sudo insmod mptcp_{self.syscall_name}.ko",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "reles_ext",
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "File exists" in error_msg:
                        self.__logger.warning(error_msg)
                    else:
                        raise

    def unload(self):
        cmds = [
            "make clean",
            f"sudo rmmod mptcp_{self.syscall_name}",
        ]
        for cmd in cmds:
            for executor in self.executors:
                try:
                    executor.set_system_commands(
                        cmd,
                        cwd=executor.store_location
                        / "schedulers"
                        / "custom"
                        / "reles_ext",
                    )
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
