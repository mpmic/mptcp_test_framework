from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import List

    from testbeds.non_blocking_executors import NonBlockingExecutor


class CommandExecutionError(Exception):
    pass


class ITestbed(ABC):
    @abstractmethod
    def setup_network(self):
        """
        Set up the network topology for the testbed.
        """
        pass

    # @abstractmethod
    # def run_test(self, scheduler):
    #     """
    #     Run the MPTCP test using the specified scheduler.

    #     Args:
    #         scheduler (IScheduler): The scheduler to use for the test.

    #     Returns:
    #         dict: The test results.
    #     """
    #     pass

    @abstractmethod
    def teardown_network(self):
        """
        Tear down the network topology and clean up resources.
        """
        pass

    @abstractmethod
    def disable_mptcp(self):
        pass

    @abstractmethod
    def enable_mptcp(self):
        pass

    # @abstractmethod
    # def collect_results(self):
    #     """
    #     Collect the test results from the testbed.

    #     Returns:
    #         dict: The collected test results.
    #     """
    #     pass

    # @abstractmethod
    # def plot_results(self, results):
    #     """
    #     Plot the test results.

    #     Args:
    #         results (dict): The test results to plot.
    #     """
    #     pass


class IHost(ABC):
    @abstractmethod
    def mptcpized_cmd(self, command):
        pass

    @abstractmethod
    def cmdWithErrorCheck(self, command):
        pass

    @abstractmethod
    def cmdWithErrorCheckNonBlocking(self, command: str) -> NonBlockingExecutor:
        pass

    @abstractmethod
    def set_system_commands(self, cmd, cwd=None):
        pass

    @abstractmethod
    def ip_address(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def store_location(self) -> Path:
        pass
