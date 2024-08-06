from __future__ import annotations

import json
import re
import time
import typing

from clients.iclient import IClient
from testbeds.itestbed import CommandExecutionError
from utils.config import MAIN_DIR, config
from utils.logging import setup_class_logger

if typing.TYPE_CHECKING:
    import logging

    from testbeds.itestbed import IHost


@setup_class_logger
class DefaultClient(IClient):
    __logger: typing.ClassVar[logging.Logger]

    def __init__(self, client_host: IHost, server_host: IHost):
        self.client_host = client_host
        self.server_host = server_host
        self.payload_location = (
            client_host.store_location / "clients" / "payload" / "default"
        )

    def run_test(self, file_size, max_retries=2, retry_interval=30):
        num_iterations = config.test.num_iterations
        client_bind_ip = self.client_host.ip_address()[0]
        server_ip = self.server_host.ip_address()[0]
        port = config.test.get("server_port", None)
        debug = config.test.get("server_debug", False)

        cmd = f"sudo mptcpize run python3 {self.payload_location}/client_payload.py --server_ip {server_ip} --client_bind_ip {client_bind_ip}"

        if port:
            cmd += f" --server_port {port}"

        if debug:
            cmd += f" --debug"

        cmd += f" --filesize {file_size}"
        cmd += f" --iterations {num_iterations}"

        attempt = 0

        while attempt <= max_retries:
            try:
                output = self.client_host.cmdWithErrorCheck(cmd)
                # self.__logger.debug(f"Command succeeded: {output}")
                break

            except CommandExecutionError as e:
                self.__logger.exception(
                    f"Attempt {attempt + 1}: Command failed with error: {e}"
                )
                if attempt == max_retries:
                    self.__logger.error(
                        f"All {max_retries + 1} attempts failed. Raising error."
                    )
                    raise
                else:
                    self.__logger.info(f"Retrying in {retry_interval} seconds...")
                    time.sleep(retry_interval)
                    attempt += 1

        throughputs = self.parse_output(output)
        return throughputs

    def parse_output(self, output):
        throughputs = []
        match = re.search(
            r"JSON_OUTPUT_START\s*({.*})\s*JSON_OUTPUT_END", output, re.DOTALL
        )
        if match:
            json_str = match.group(1).strip()
            json_obj = json.loads(json_str)
            throughputs = json_obj.get("throughputs", [])
        return throughputs
