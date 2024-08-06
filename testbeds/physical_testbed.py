# physical_testbed.py

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import ClassVar, List, Optional

import paramiko
from paramiko import SSHClient
from scp import SCPClient

from testbeds.non_blocking_executors import NonBlockingExecutor, SSHExecutor
from utils.config import MAIN_DIR, config
from utils.logging import setup_class_logger

from .itestbed import CommandExecutionError, IHost, ITestbed


@setup_class_logger
class PhysicalHost(IHost):
    __logger: ClassVar[logging.Logger]

    def __init__(
        self, hostname, username, password=None, ssh_key=None, store_location=None
    ):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_key = ssh_key

        self._store_location = store_location or "/tmp"
        self._store_location = self._store_location + "/MPTCP_Testbench_files/"

        self.venv_path = None

        self.ssh_client = self._establish_ssh_connection()
        self._transfer_project_files()

    def _establish_ssh_connection(self):
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=self.hostname,
            username=self.username,
            password=self.password,
            key_filename=self.ssh_key,
        )
        self.__logger.info("Established SSH Connection with %s", self.hostname)

        return ssh_client

    def _delete_project_files(self):
        self.__logger.info(f"Deleting project files from host {self.hostname}")
        self.cmdWithErrorCheck(f"rm -rf {self.store_location}")

    def _transfer_project_files(self):
        scp = SCPClient(self.ssh_client.get_transport())

        # Create the remote directory if it doesn't exist
        self.cmdWithErrorCheck(f"mkdir -p {self.store_location}")

        # Transfer the necessary folders to the remote host
        folders_to_transfer = [
            "schedulers",
            "servers",
            "clients",
        ]
        for folder in folders_to_transfer:
            local_path = MAIN_DIR / folder
            remote_path = Path(self.store_location) / folder
            scp.put(str(local_path), recursive=True, remote_path=str(remote_path))

        # Transfer the requirements.txt file to the remote host
        local_requirements_path = MAIN_DIR / "requirements.txt"
        remote_requirements_path = Path(self.store_location) / "requirements.txt"
        scp.put(str(local_requirements_path), remote_path=str(remote_requirements_path))

        scp.close()

    def setup_venv(self):
        # Check if .venv exists, create it if not present
        venv_path = Path(self.store_location) / ".venv"
        venv_exists = self.cmdWithErrorCheck(
            f"test -d {venv_path} && echo 'exists' || echo 'not exists'"
        )
        if venv_exists.strip() == "not exists":
            self.__logger.info(
                f"Creating virtual environment (.venv) on host {self.hostname}"
            )
            self.cmdWithErrorCheck(f"python3 -m venv {venv_path}")

        self.venv_path = venv_path

        # Install requirements inside the virtual environment
        remote_requirements_path = "requirements.txt"
        self.__logger.info(f"Installing requirements on host {self.hostname}")
        output = self.cmdWithErrorCheck(
            f"cd {self.store_location} && sudo python3 -m pip install -r {remote_requirements_path} && cd -"
        )
        self.__logger.debug(f"Pip installation successful!")

    def mptcpized_cmd(self, command):
        # Prefix the command with mptcpize run
        mptcpized_full_cmd = f"mptcpize run {command}"
        # Execute the command with error checking
        return self.cmdWithErrorCheck(mptcpized_full_cmd)

    def cmdWithErrorCheck(self, command):
        self.__logger.debug(f"Host {self.hostname} executing command: {command}")

        if "sudo " in command:
            # Replace "sudo" with "echo {password} | sudo -S -E"
            command = command.replace("sudo ", f"echo {self.password} | sudo -S -E ")

        if self.venv_path is not None:
            # Replace "python3" with the virtual environment path
            command = command.replace("python3", f"{self.venv_path}/bin/python3")

        full_command = f'bash -c "{command}"'
        stdin, stdout, stderr = self.ssh_client.exec_command(full_command)

        # Wait for the command to complete and get the exit status
        exit_status = stdout.channel.recv_exit_status()

        # Read the output and error streams
        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        if exit_status != 0:
            error_msg = f"Command '{command}' failed with exit status {exit_status}."
            if error:
                error_msg += f" Error: {error}"
            self.__logger.error(error_msg)
            raise CommandExecutionError(error_msg)

        return output

    def cmdWithErrorCheckNonBlocking(self, command: str) -> NonBlockingExecutor:
        self.__logger.debug(
            f"Host {self.hostname} executing command: {command} [NON-BLOCKING]"
        )

        return SSHExecutor(self, command, self.__logger)

    def ip_address(self) -> List[str]:
        command = "ip -o addr show"
        output = self.cmdWithErrorCheck(command)
        ips = re.findall(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output)
        # Filter out the loopback address
        ips = [ip for ip in ips if ip != "127.0.0.1"]
        return ips

    def set_system_commands(self, cmd, cwd=None):
        self.__logger.debug(f"Running {cmd} on the host {self.hostname}")

        if cwd:
            cmd = f"cd {cwd} && {cmd}"

        try:
            self.cmdWithErrorCheck(cmd)
        except Exception as e:
            raise CommandExecutionError(e)

    @property
    def store_location(self) -> Path:
        return Path(self._store_location)


@setup_class_logger
class PhysicalTestbed(ITestbed):
    __logger: ClassVar[logging.Logger]

    def __init__(self):
        self.client_config = config.topology.physical.client
        self.server_config = config.topology.physical.server
        self.client_host: Optional[PhysicalHost] = None
        self.server_host: Optional[PhysicalHost] = None

    def setup_network(self):
        self.__logger.info("Setting up the physical testbed network")

        # Create instances of PhysicalHost for the client and server
        self.client_host = PhysicalHost(
            hostname=self.client_config.hostname,
            username=self.client_config.username,
            password=self.client_config.get("password", None),
            ssh_key=self.client_config.get("ssh_key", None),
            store_location=self.client_config.get("store_location", None),
        )
        self.server_host = PhysicalHost(
            hostname=self.server_config.hostname,
            username=self.server_config.username,
            password=self.server_config.get("password", None),
            ssh_key=self.server_config.get("ssh_key", None),
            store_location=self.server_config.get("store_location", None),
        )

        # Configure .venv on the client and server hosts
        self.client_host.setup_venv()
        self.server_host.setup_venv()

        return self.client_host, self.server_host

    def teardown_network(self):
        self.__logger.info("Tearing down the physical testbed network")

        # Delete the project files from the client and server hosts
        # self.client_host._delete_project_files()
        # self.server_host._delete_project_files()

        # Close the SSH connections to the client and server hosts
        if self.client_host:
            self.client_host.ssh_client.close()

        if self.server_host:
            self.server_host.ssh_client.close()

    def disable_mptcp(self):
        for host in [self.server_host, self.client_host]:
            if host:
                host.set_system_commands("sudo sysctl -w net.mptcp.mptcp_enabled=0")

    def enable_mptcp(self):
        for host in [self.server_host, self.client_host]:
            if host:
                host.set_system_commands("sudo sysctl -w net.mptcp.mptcp_enabled=1")
