import logging
from typing import ClassVar

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from tabulate import tabulate

from utils.config import RESULT_DIR, config
from utils.logging import setup_class_logger


@setup_class_logger
class LinkTestResultManager:
    __logger: ClassVar[logging.Logger]

    def __init__(self):
        self.link_test_results = []

    def add_result(self, result):
        self.link_test_results = result

    def summarize_results(self):
        table_data = []
        headers = [
            "Client IP",
            "Server IP",
            "Bandwidth (Mbps)",
            "Mean RTT (ms)",
            "Jitter (ms)",
            "Packet Loss (%)",
        ]

        for result in self.link_test_results:
            row = [
                result["client_ip"],
                result["server_ip"],
                result["bandwidth"],
                result["mean_rtt"],
                result["jitter"],
                result["packet_loss"],
            ]
            table_data.append(row)

        table = tabulate(table_data, headers, tablefmt="grid")

        self.__logger.info("Link Test Results Summary:")
        self.__logger.info(f"\n{table}\n")

    def plot_results(self):
        plot_configs = config.results.plot
        figsize = tuple(plot_configs.figsize)

        # Create a DataFrame from the link test results
        df = pd.DataFrame(self.link_test_results)

        # Create a violin plot for bandwidth
        plt.figure(figsize=figsize)
        sns.violinplot(x="client_ip", y="bandwidth", data=df)
        plt.xlabel("Link")
        plt.ylabel("Bandwidth (Mbps)")
        plt.title("Bandwidth Distribution")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(RESULT_DIR / "bandwidth_plot.png")
        plt.close()

        # Create a violin plot for mean RTT
        plt.figure(figsize=figsize)
        sns.violinplot(x="client_ip", y="mean_rtt", data=df)
        plt.xlabel("Link")
        plt.ylabel("Minimum RTT (ms)")
        plt.title("Minimum RTT Distribution")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(RESULT_DIR / "mean_rtt_plot.png")
        plt.close()

        # Create a violin plot for jitter
        plt.figure(figsize=figsize)
        sns.violinplot(x="client_ip", y="jitter", data=df)
        plt.xlabel("Link")
        plt.ylabel("Jitter (ms)")
        plt.title("Jitter Distribution")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(RESULT_DIR / "jitter_plot.png")
        plt.close()

        # Create a violin plot for packet loss
        plt.figure(figsize=figsize)
        sns.violinplot(x="client_ip", y="packet_loss", data=df)
        plt.xlabel("Link")
        plt.ylabel("Packet Loss (%)")
        plt.title("Packet Loss Distribution")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(RESULT_DIR / "packet_loss_plot.png")
        plt.close()
