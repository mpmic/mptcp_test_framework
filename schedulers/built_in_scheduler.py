# schedulers/built_in_scheduler.py

from pathlib import Path

from utils.logging import setup_class_logger

from .ischeduler import BuiltInScheduler


@setup_class_logger
class MinRTTScheduler(BuiltInScheduler):
    def __init__(self, client, server):
        super().__init__(
            name="minrtt", client=client, server=server, syscall_name="default"
        )

    def load(self):
        pass

    def unload(self):
        pass


@setup_class_logger
class RoundRobinScheduler(BuiltInScheduler):
    def __init__(self, client, server):
        super().__init__(
            name="roundrobin", client=client, server=server, syscall_name="rr"
        )


@setup_class_logger
class ECFScheduler(BuiltInScheduler):
    def __init__(self, client, server):
        super().__init__(name="ecf", client=client, server=server)


@setup_class_logger
class BLESTScheduler(BuiltInScheduler):
    def __init__(self, client, server):
        super().__init__(name="blest", client=client, server=server)


@setup_class_logger
class RedundantScheduler(BuiltInScheduler):
    def __init__(self, client, server):
        super().__init__(name="redundant", client=client, server=server)


@setup_class_logger
class LATEScheduler(BuiltInScheduler):

    _CURRENT_DIR = Path(__file__).resolve().parent
    _LATE_KO_DIR = _CURRENT_DIR / "custom/late"

    def __init__(self, client, server):
        super().__init__(name="late", client=client, server=server)

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
                        cwd=executor.store_location / "schedulers" / "custom" / "late",
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
                        cwd=executor.store_location / "schedulers" / "custom" / "late",
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
