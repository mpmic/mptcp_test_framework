from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from utils.logging import setup_class_logger

if TYPE_CHECKING:
    import logging
    from typing import ClassVar
    from testbeds.itestbed import IHost

from servers.iserver import IServer
from utils.config import config


@setup_class_logger
class DefaultServer(IServer):
    __logger: ClassVar[logging.Logger]

    def __init__(self, server_host: IHost):
        self.server_host = server_host
        self.execution_instance = None
        self.process = None
        self.payload_location = (
            server_host.store_location / "servers" / "payload" / "default"
        )

    def serve(self):
        port = config.test.get("server_port", None)
        debug = config.test.get("server_debug", False)
        cmd = f"sudo mptcpize run python3 {self.payload_location}/server_payload.py --ip {self.server_host.ip_address()[0]}"

        if port:
            cmd += f" --port {port}"

        if debug:
            cmd += f" --debug"

        self.execution_instance = self.server_host.cmdWithErrorCheckNonBlocking(cmd)
        self.__logger.info("Server started with PID: %s", self.execution_instance.pid)
        time.sleep(5)

    def kill(self):
        if self.execution_instance:
            self.execution_instance.kill()

    def killall(self):
        cmd = f'sudo pkill -f ".*server_payload.py.*"'
        self.__logger.debug(f"Killing all instances of server_payload.py")
        try:
            self.server_host.cmdWithErrorCheck(cmd)
        except Exception as e:
            self.__logger.warning(f"Error encountered in killall: {e}")
