# servers/reinforcement_learning_server.py

import logging
import time
from typing import ClassVar

from servers.iserver import IServer
from utils.config import config
from utils.logging import setup_class_logger


@setup_class_logger
class FALCONServer(IServer):
    __logger: ClassVar[logging.Logger]

    def __init__(self, server_host, server_params):
        self.server_host = server_host
        self.execution_instance = None
        self.server_params = server_params
        self.payload_location = (
            server_host.store_location / "servers" / "payload" / "falcon"
        )

    def serve(self):
        port = config.test.get("server_port", None)
        debug = self.server_params.get("server_debug", False)
        continue_train = self.server_params.get("continue_train", None)

        cmd = f"sudo mptcpize run python3 {self.payload_location}/falcon_server_payload.py --ip {self.server_host.ip_address()[0]}"

        if port:
            cmd += f" --port {port}"

        if debug:
            cmd += f" --debug"

        if continue_train:
            cmd += f" --continue_train {int(continue_train)}"

        self.execution_instance = self.server_host.cmdWithErrorCheckNonBlocking(cmd)
        self.__logger.info(
            f"FALCON server started with PID: {self.execution_instance.pid}"
        )
        time.sleep(15)

    def kill(self):
        if self.execution_instance:
            self.execution_instance.kill()
            self.__logger.info("FALCON server stopped")

    def killall(self):
        cmd = f'sudo pkill -f ".*server_payload.py.*"'
        self.__logger.debug(f"Killing all instances of .*server_payload.py")
        try:
            self.server_host.cmdWithErrorCheck(cmd)
        except Exception as e:
            self.__logger.warning(f"Error encountered in killall: {e}")


@setup_class_logger
class RELESServer(IServer):
    __logger: ClassVar[logging.Logger]

    def __init__(self, server_host, server_params):
        self.server_host = server_host
        self.execution_instance = None
        self.server_params = server_params
        self.payload_location = (
            server_host.store_location / "servers" / "payload" / "reles"
        )

    def serve(self):
        port = config.test.get("server_port", None)
        debug = self.server_params.get("server_debug", False)
        continue_train = self.server_params.get("continue_train", None)

        cmd = f"python3 {self.payload_location}/reles_server_payload.py --ip {self.server_host.ip_address()[0]}"

        if port:
            cmd += f" --port {port}"

        if debug:
            cmd += f" --debug"

        if continue_train:
            cmd += f" --continue_train {int(continue_train)}"

        self.execution_instance = self.server_host.cmdWithErrorCheckNonBlocking(cmd)
        self.__logger.info(
            f"RELES server started with PID: {self.execution_instance.pid}"
        )
        time.sleep(7)

    def kill(self):
        if self.execution_instance:
            self.execution_instance.kill()
            self.__logger.info("RELES server stopped")

    def killall(self):
        cmd = f'sudo pkill -f ".*server_payload.py.*"'
        self.__logger.debug(f"Killing all instances of server_payload.py")
        try:
            self.server_host.cmdWithErrorCheck(cmd)
        except Exception as e:
            self.__logger.warning(f"Error encountered in killall: {e}")


@setup_class_logger
class FALCONExtServer(IServer):
    __logger: ClassVar[logging.Logger]

    def __init__(self, server_host, server_params):
        self.server_host = server_host
        self.execution_instance = None
        self.server_params = server_params
        self.payload_location = (
            server_host.store_location / "servers" / "payload" / "falcon_ext"
        )

    def serve(self):
        port = config.test.get("server_port", None)
        debug = self.server_params.get("server_debug", False)
        continue_train = self.server_params.get("continue_train", None)

        cmd = f"sudo mptcpize run python3 {self.payload_location}/falcon_ext_server_payload.py --ip {self.server_host.ip_address()[0]}"

        if port:
            cmd += f" --port {port}"
        if debug:
            cmd += f" --debug"
        if continue_train:
            cmd += f" --continue_train {int(continue_train)}"

        self.execution_instance = self.server_host.cmdWithErrorCheckNonBlocking(cmd)
        self.__logger.info(
            f"FALCON_EXT server started with PID: {self.execution_instance.pid}"
        )
        time.sleep(
            15
        )

    def kill(self):
        if self.execution_instance:
            self.execution_instance.kill()
            self.__logger.info("FALCON_EXT server stopped")

    def killall(self):
        cmd = f'sudo pkill -f ".*server_payload.py.*"'
        self.__logger.debug(f"Killing all instances of .*server_payload.py")
        try:
            self.server_host.cmdWithErrorCheck(cmd)
        except Exception as e:
            self.__logger.warning(f"Error encountered in killall: {e}")


@setup_class_logger
class RELESExtServer(IServer):
    __logger: ClassVar[logging.Logger]

    def __init__(self, server_host, server_params):
        self.server_host = server_host
        self.execution_instance = None
        self.server_params = server_params
        self.payload_location = (
            server_host.store_location / "servers" / "payload" / "reles_ext"
        )

    def serve(self):
        port = config.test.get("server_port", None)
        debug = self.server_params.get("server_debug", False)
        continue_train = self.server_params.get("continue_train", None)

        cmd = f"python3 {self.payload_location}/reles_ext_server_payload.py --ip {self.server_host.ip_address()[0]}"

        if port:
            cmd += f" --port {port}"
        if debug:
            cmd += f" --debug"
        if continue_train:
            cmd += f" --continue_train {int(continue_train)}"

        self.execution_instance = self.server_host.cmdWithErrorCheckNonBlocking(cmd)
        self.__logger.info(
            f"RELES_EXT server started with PID: {self.execution_instance.pid}"
        )
        time.sleep(7)

    def kill(self):
        if self.execution_instance:
            self.execution_instance.kill()
            self.__logger.info("RELES_EXT server stopped")

    def killall(self):
        cmd = f'sudo pkill -f ".*server_payload.py.*"'
        self.__logger.debug(f"Killing all instances of .*server_payload.py")
        try:
            self.server_host.cmdWithErrorCheck(cmd)
        except Exception as e:
            self.__logger.warning(f"Error encountered in killall: {e}")
