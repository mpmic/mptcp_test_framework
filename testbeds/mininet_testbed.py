# testbeds/mininet_testbed.py
from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional

from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import Host

from testbeds.non_blocking_executors import PopenExecutor
from utils.config import MAIN_DIR, config, config_to_dict
from utils.logging import setup_class_logger

from .itestbed import CommandExecutionError, IHost, ITestbed

if TYPE_CHECKING:
    from pathlib import Path


@setup_class_logger
class MininetMptcpHost(Host, IHost):
    __logger: ClassVar[logging.Logger]

    def __init__(self, name, **kwargs):
        super(MininetMptcpHost, self).__init__(name, **kwargs)
        self.configure_routing()

    def configure_routing(self):
        # Copy the mptcp_up script to /etc/network/if-up.d/
        self.__logger.info(f"Configuring routing for host: {self.name}")

        self.cmdWithErrorCheck(
            f"sudo cp {MAIN_DIR.absolute()}/routing_configuration_scripts/mptcp_up /etc/network/if-up.d/"
        )
        self.cmdWithErrorCheck("sudo chmod +x /etc/network/if-up.d/mptcp_up")

        # Copy the mptcp_down script to /etc/network/if-post-down.d/
        self.cmdWithErrorCheck(
            f"sudo cp {MAIN_DIR.absolute()}/routing_configuration_scripts/mptcp_down /etc/network/if-post-down.d/"
        )
        self.cmdWithErrorCheck("sudo chmod +x /etc/network/if-post-down.d/mptcp_down")

    def mptcpized_cmd(self, command):
        """
        Run a general command using mptcpize.
        The first argument is the command to run, followed by any arguments and keyword arguments.
        """
        # Prefix the command with mptcpize run
        mptcpized_full_cmd = f"mptcpize run {command}"
        # Execute the command with error checking
        return self.cmdWithErrorCheck(mptcpized_full_cmd)

    def cmdWithErrorCheck(self, command):
        # Append '; echo $?' to the command to capture its exit status
        self.__logger.debug(f"Host {self.name} executing command: {command}")
        command_with_status = f"{command}; echo $?"
        result = self.cmd(command_with_status)

        # Split the result by newline to separate command output from exit status
        *output_lines, exit_status = result.rstrip().split("\n")

        # Join the output lines back into a single string
        output = "\n".join(output_lines).strip()

        # Check the exit status
        if exit_status.strip() != "0":
            error_msg = f"Command '{command}' failed with exit status {exit_status}."
            if output:
                error_msg += f" Output: {output}"
            self.__logger.error(error_msg)
            raise CommandExecutionError(error_msg)

        # logger.debug(f"Command output: {output}")

        # Return the actual output of the command
        return output

    def cmdWithErrorCheckNonBlocking(self, command):
        self.__logger.debug(
            f"Host {self.name} executing command: {command} [NON-BLOCKING]"
        )

        return PopenExecutor(self, command, self.__logger)

    def ip_address(self) -> List[str]:
        return [
            self.IP(intf=interface)
            for interface in self.intfNames()
            if self.IP(intf=interface)
        ]

    def set_system_commands(self, cmd, cwd=None):
        self.__logger.debug(f"Running {cmd} on the local system")

        try:
            result = subprocess.run(
                cmd, check=True, shell=True, capture_output=True, text=True, cwd=cwd
            )
            output = result.stdout.strip()
            self.__logger.debug(f"sysctl output: {output}")
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.strip()
            self.__logger.debug(
                f"Failed to run system command, error output: {error_output}"
            )
            raise CommandExecutionError(error_output)

    @property
    def store_location(self) -> Path:
        return MAIN_DIR


@setup_class_logger
class MininetTestbed(ITestbed):
    __logger: ClassVar[logging.Logger]

    def __init__(self):
        self.net = Mininet()
        self.configured_links: Dict[str, TCLink] = {}
        self.client: Optional[MininetMptcpHost] = None
        self.server: Optional[MininetMptcpHost] = None

    def setup_network(self):
        # Create hosts
        self.server = self.net.addHost("server", cls=MininetMptcpHost)  # type: ignore
        self.client = self.net.addHost("client", cls=MininetMptcpHost)  # type: ignore
        self.link_params = {}

        for link_config in config_to_dict(config.topology.mininet.links):
            name = link_config.pop("name")
            link_config["params1"] = {"ip": link_config.pop("client_ip")}
            link_config["params2"] = {"ip": link_config.pop("server_ip")}

            self.link_params[name] = link_config

            self.configured_links[name] = self.net.addLink(
                self.client, self.server, cls=TCLink, **link_config
            )

        # Start the network
        self.net.start()

        # Force IP address on hosts
        self._force_ip_addresses()

        return self.client, self.server

    def _force_ip_addresses(self):
        # Set IP addresses for the interfaces

        # This is a bug fix for Hosts not complying to set IP before net.start
        for link_name, link in self.configured_links.items():
            params1 = self.link_params[link_name]["params1"]
            params2 = self.link_params[link_name]["params2"]
            self.client.setIP(params1["ip"], intf=link.intf1)
            self.server.setIP(params2["ip"], intf=link.intf2)

    def disable_mptcp(self):
        for host in [self.server, self.client]:
            if host:
                host.set_system_commands("sudo sysctl -w net.mptcp.mptcp_enabled=0")

    def enable_mptcp(self):
        for host in [self.server, self.client]:
            if host:
                host.set_system_commands("sudo sysctl -w net.mptcp.mptcp_enabled=1")

    def teardown_network(self):
        """
        Tear down the network topology and clean up resources.
        """
        self.net.stop()

    # def run_test(self, scheduler):
    #     # Implement the logic to run the test using the provided scheduler
    #     pass

    # def plot_results(self, results):
    #     # Implement the logic to plot the results
    #     pass
