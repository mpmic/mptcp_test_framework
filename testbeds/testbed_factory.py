from __future__ import annotations

from typing import TYPE_CHECKING

from utils.config import config
from utils.logging import setup_class_logger

from .mininet_testbed import MininetTestbed
from .physical_testbed import PhysicalTestbed

if TYPE_CHECKING:
    import logging
    from typing import ClassVar


@setup_class_logger
class TestbedFactory:
    __logger: ClassVar[logging.Logger]

    @staticmethod
    def create_testbed():
        testbed_type = config.network_env

        if testbed_type == "mininet":
            TestbedFactory.__logger.info("Creating Mininet Testbed")
            return MininetTestbed()
        elif testbed_type == "physical":
            TestbedFactory.__logger.info("Creating Physical Testbed")
            return PhysicalTestbed()
        else:
            raise ValueError(f"Unsupported testbed type: {testbed_type}")
