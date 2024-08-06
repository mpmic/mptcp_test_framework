import json
import logging
import subprocess
import threading
from typing import ClassVar

from result_management.link_test_result_manager import LinkTestResultManager
from testbeds.testbed_factory import TestbedFactory
from utils.logging import setup_class_logger


@setup_class_logger
class LinkTester:
    __logger: ClassVar[logging.Logger]

    def __init__(self, client_host, server_host):
        self.client_host = client_host
        self.server_host = server_host
        self.results = []

    def run_tcp_test(self, client_ip, server_ip, duration=120):
        server_cmd = f"iperf3 -s -B {server_ip}"
        client_cmd = f"iperf3 -c {server_ip} -B {client_ip} -t {duration} -J"

        # Start the iperf3 server on the server host
        server_process = self.server_host.cmdWithErrorCheckNonBlocking(server_cmd)

        # Run the iperf3 client on the client host and capture the output
        client_output = self.client_host.cmdWithErrorCheck(client_cmd)

        # Terminate the iperf3 server
        server_process.kill()

        # Parse the JSON output to extract bandwidth and minimum RTT
        json_output = json.loads(client_output)
        bandwidth = (
            json_output["end"]["sum_received"]["bits_per_second"] / 1e6
        )  # Convert to Mbps
        mean_rtt = (
            json_output["end"]["streams"][0]["sender"]["mean_rtt"] / 1000
        )  # Convert to milliseconds

        return bandwidth, mean_rtt

    def run_udp_test(self, client_ip, server_ip, bandwidth, duration=120):
        server_cmd = f"iperf3 -s -B {server_ip}"
        client_cmd = (
            f"iperf3 -c {server_ip} -B {client_ip} -t {duration} -u -b {bandwidth}M -J"
        )

        # Start the iperf3 server on the server host
        server_process = self.server_host.cmdWithErrorCheckNonBlocking(server_cmd)

        # Run the iperf3 client on the client host and capture the output
        client_output = self.client_host.cmdWithErrorCheck(client_cmd)

        # Terminate the iperf3 server
        server_process.kill()

        # Parse the JSON output to extract jitter and packet loss
        json_output = json.loads(client_output)
        jitter = json_output["end"]["sum"]["jitter_ms"]  # Already in milliseconds
        packet_loss = json_output["end"]["sum"]["lost_percent"]

        return jitter, packet_loss

    def run_tests(self):
        # Get the list of interfaces with an IP address on the client and server
        client_interfaces = self.client_host.ip_address()
        server_interfaces = self.server_host.ip_address()

        # Iterate over all combinations of client and server interfaces
        for client_ip in client_interfaces:
            for server_ip in server_interfaces:
                # Run the TCP test for the current interface combination
                bandwidth, mean_rtt = self.run_tcp_test(client_ip, server_ip)

                # Run the UDP test for the current interface combination using the average bandwidth from the TCP test
                jitter, packet_loss = self.run_udp_test(client_ip, server_ip, bandwidth)

                # Store the test results
                self.results.append(
                    {
                        "client_ip": client_ip,
                        "server_ip": server_ip,
                        "bandwidth": bandwidth,
                        "mean_rtt": mean_rtt,
                        "jitter": jitter,
                        "packet_loss": packet_loss,
                    }
                )

                # Log the results
                self.__logger.info(f"Client IP - {client_ip}, Server IP - {server_ip}")
                self.__logger.info(f"Bandwidth: {bandwidth:.2f} Mbps")
                self.__logger.info(f"Average RTT: {mean_rtt:.2f} ms")
                self.__logger.info(f"Jitter: {jitter:.2f} ms")
                self.__logger.info(f"Packet Loss: {packet_loss:.2f}%")
                self.__logger.info("---")

        return self.results


def main():
    # Create the testbed based on the configuration
    testbed = TestbedFactory.create_testbed()

    # Set up the network and get the client and server hosts
    client_host, server_host = testbed.setup_network()

    # Disable MPTCP on the client and server hosts
    testbed.disable_mptcp()

    # Create an instance of the LinkTester class
    link_tester = LinkTester(client_host, server_host)

    # Create an instance of the ResultManager
    result_manager = LinkTestResultManager()

    # Run the link tests
    results = link_tester.run_tests()

    # Add the results to the ResultManager
    result_manager.add_result(results)

    # Plot the results
    result_manager.summarize_results()

    # Enable MPTCP on the client and server hosts
    testbed.enable_mptcp()

    # Tear down the network
    testbed.teardown_network()


if __name__ == "__main__":
    main()
