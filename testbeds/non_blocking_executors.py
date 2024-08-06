from __future__ import annotations

import abc
import logging
import subprocess
import threading
from typing import IO, TYPE_CHECKING

from utils.logging import setup_class_logger

if TYPE_CHECKING:
    from logging import Logger

    import paramiko

    from testbeds.mininet_testbed import MininetMptcpHost
    from testbeds.physical_testbed import PhysicalHost


class NonBlockingExecutor(abc.ABC):
    def __init__(self, logger: Logger):
        self.logger = logger
        self.stdout_thread = None
        self.stderr_thread = None
        self.stdout = None
        self.stderr = None
        self.end_event = threading.Event()

    @abc.abstractmethod
    def read_stdout(self):
        pass

    @abc.abstractmethod
    def read_stderr(self):
        pass

    @abc.abstractmethod
    def wait(self):
        pass

    def start_logging(self):
        self.stdout_thread = threading.Thread(
            target=self._log_stream,
            args=(self.stdout, "stdout"),
            name=f"{self.logger.name}_stdout",
            daemon=True,
        )
        self.stderr_thread = threading.Thread(
            target=self._log_stream,
            args=(self.stderr, "stderr"),
            name=f"{self.logger.name}_stderr",
            daemon=True,
        )

        self.stdout_thread.start()
        self.stderr_thread.start()

    @abc.abstractmethod
    def _log_stream(self, stream, stream_type):
        pass

    @abc.abstractmethod
    def kill(self):
        pass

    @abc.abstractmethod
    def is_running(self):
        pass

    @property
    @abc.abstractmethod
    def pid(self) -> int:
        pass


@setup_class_logger
class SSHExecutor(NonBlockingExecutor):
    def __init__(self, host: PhysicalHost, cmd: str, logger: Logger):
        super().__init__(logger)
        self.ssh_client = host.ssh_client
        self.password = host.password
        self.venv_path = host.venv_path
        cmd = self.modify_command(cmd)
        pid, stdin, stdout, stderr = self._execute(cmd)
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self._pid = pid
        self.start_logging()

    def modify_command(self, command):
        if "sudo " in command:
            # Replace "sudo" with "echo {password} | sudo -S -E"
            command = command.replace("sudo ", f"echo {self.password} | sudo -S -E ")

        if self.venv_path is not None:
            # Replace "python3" with the virtual environment path
            command = command.replace("python3", f"{self.venv_path}/bin/python3")

        return command

    def _execute(self, cmd: str):
        command = f"echo $$; exec {cmd}"
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        pid = int(stdout.readline())
        return pid, stdin, stdout, stderr

    @property
    def pid(self) -> int:
        return self._pid

    def read_stdout(self):
        return self.stdout.read().decode("utf-8").strip()

    def read_stderr(self):
        return self.stderr.read().decode("utf-8").strip()

    def wait(self):
        return self.stdout.channel.recv_exit_status()

    def _log_stream(self, stream: paramiko.ChannelFile, stream_type: str):
        while not self.end_event.is_set():
            line = stream.readline().strip()
            if not line:
                break
            if stream_type == "stdout":
                self.logger.info(f"[{stream_type}] {line}")
            elif stream_type == "stderr":
                self.logger.error(f"[{stream_type}] {line}")

    def kill(self):
        self.ssh_client.exec_command(
            f"echo {self.password} | sudo -S -E kill -9 {self.pid}"
        )
        self.end_event.set()
        # kill logging threads also

    def is_running(self):
        _, stdout, _ = self.ssh_client.exec_command(f"ps -p {self.pid}")
        output = stdout.read().decode("utf-8")
        return str(self.pid) in output


@setup_class_logger
class PopenExecutor(NonBlockingExecutor):
    def __init__(self, host: MininetMptcpHost, cmd: str, logger: Logger):
        super().__init__(logger)
        self.host = host
        popen_obj = self.host.popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.popen_obj = popen_obj
        self.stdout = popen_obj.stdout
        self.stderr = popen_obj.stderr

        self.start_logging()

    @property
    def pid(self) -> int:
        return self.popen_obj.pid

    def read_stdout(self):
        stdout = self.popen_obj.stdout
        output = stdout.read() if stdout else None
        output = output.decode("utf-8") if isinstance(output, bytes) else output
        return output.strip() if output else None

    def read_stderr(self):
        stderr = self.popen_obj.stderr
        output = stderr.read() if stderr else None
        output = output.decode("utf-8") if isinstance(output, bytes) else output
        return output.strip() if output else None

    def wait(self):
        return self.popen_obj.wait()

    def _log_stream(self, stream: IO[str], stream_type: str):
        while not self.end_event.is_set():
            line = stream.readline().strip()
            if not line:
                break
            if stream_type == "stdout":
                self.logger.info(f"[{stream_type}] {line}")
            elif stream_type == "stderr":
                self.logger.error(f"[{stream_type}] {line}")

    def kill(self):
        self.host.cmdWithErrorCheck(f"sudo kill -9 {self.pid}")
        self.end_event.set()

    def is_running(self):
        return self.popen_obj.poll() is None
