# main.py
from clients.client_factory import ClientFactory
from congestion_control.congestion_control_factory import CongestionControlFactory
from result_management.result_manager import ResultManager
from schedulers.scheduler_factory import SchedulerFactory
from servers.server_factory import ServerFactory
from testbeds.testbed_factory import TestbedFactory
from utils.config import config
from utils.logging import MAIN_LOGGER


def main():
    # Create the testbed based on the configuration [PhysicalTestbed / MininetTestbed]
    testbed = TestbedFactory.create_testbed()

    # Set up the network and get the client and server hosts [PhysicalHost / MininetHost]
    client_host, server_host = testbed.setup_network()

    testbed.enable_mptcp()

    # Get the list of schedulers from the YAML list of string of schedulers, with executor mapped [IScheduler]
    schedulers = SchedulerFactory.create_schedulers(
        schedulers=config.schedulers, client=client_host, server=server_host
    )

    # Get the list of congestion control params from the YAML list of string of CCs, with executor mapped [ICongestionControl]
    congestion_controls = CongestionControlFactory.create_congestion_controls(
        config.congestion_controls, client=client_host, server=server_host
    )

    # Get all the file sizes
    file_sizes = config.test.file_size

    # Set up a Result Manager object
    result_manager = ResultManager()

    # Run tests for each combination of scheduler, file size, and congestion control
    for scheduler in schedulers:
        # Load and set the scheduler
        with scheduler:
            for congestion_control in congestion_controls:
                # Load and set the congestion control
                with congestion_control:
                    for file_size in file_sizes:
                        # Checkpointing
                        if (
                            result_manager.checkpointing_enabled
                            and result_manager.is_test_completed(
                                scheduler, congestion_control, file_size
                            )
                        ):
                            MAIN_LOGGER.info(
                                f"Skipping test for scheduler '{scheduler.name}', congestion control '{congestion_control.name}', file size {file_size}, checkpointed!"
                            )
                            continue

                        MAIN_LOGGER.info(
                            f"Starting test for scheduler '{scheduler.name}', congestion control '{congestion_control.name}', and file size {file_size}"
                        )
                        # Create the server
                        server = ServerFactory.create_server(scheduler, server_host)

                        with server:
                            # Create the client, run the test
                            client = ClientFactory.create_client(
                                scheduler, client_host, server_host
                            )
                            results = client.run_test(file_size)

                            # Save results somewhere.
                            result_manager.add_result(
                                scheduler, congestion_control, file_size, results
                            )

    # Collect and plot the results
    result_manager.plot_results()

    # Summarize results
    result_manager.summarize_results()

    # Tear down the network
    testbed.teardown_network()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        MAIN_LOGGER.error(e, exc_info=True)
