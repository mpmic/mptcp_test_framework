# result_management.py

import json
import logging
from pathlib import Path
from typing import ClassVar

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from tabulate import tabulate

from utils.config import RESULT_DIR, config, config_to_dict
from utils.logging import setup_class_logger


@setup_class_logger
class ResultManager:
    __logger: ClassVar[logging.Logger]

    def __init__(self):
        self.results = {}
        self.checkpointing_enabled = config.test.get("checkpoint", False)
        self.result_file = RESULT_DIR.parent.parent / "checkpoint.json"
        self.config_dict = {
            "name": config.name,
            "network_env": config.network_env,
            "topology": config_to_dict(config.topology),
            "schedulers": config_to_dict(config.schedulers),
            # "congestion_controls": config_to_dict(config.congestion_controls),
            "test": config_to_dict(config.test),
            "results_dir": config.results.dir,
        }

        self._load_results()

    def _verify_results(self, checkpointed_results):
        config_without_schedulers = {
            key: value
            for key, value in self.config_dict.items()
            if key not in ["schedulers"]
        }

        checkpointed_results_filtered = {
            key: value
            for key, value in checkpointed_results.items()
            if key not in ["schedulers", "results"]
        }

        if config_without_schedulers != checkpointed_results_filtered:
            return False

        # Verify scheduler params same
        current_schedulers = {
            scheduler_dict["name"]: scheduler_dict.get("params", {})
            for scheduler_dict in self.config_dict.get("schedulers", [])
        }
        checkpointed_schedulers = {
            scheduler_dict["name"]: scheduler_dict.get("params", {})
            for scheduler_dict in checkpointed_results.get("schedulers", [])
        }

        common_schedulers = set(current_schedulers.keys()) & set(
            checkpointed_schedulers.keys()
        )

        for scheduler_name in common_schedulers:
            if (
                current_schedulers[scheduler_name]
                != checkpointed_schedulers[scheduler_name]
            ):
                return False

        return True

    def _load_results(self):
        if not self.checkpointing_enabled or not self.result_file.exists():
            return

        with self.result_file.open("r") as f:
            checkpointed_results = json.load(f)

        if self._verify_results(checkpointed_results):
            self.results = {
                tuple(self._decode_key(key)): throughputs
                for key, throughputs in checkpointed_results.get("results", {}).items()
            }
        else:
            self.result_file.unlink(missing_ok=True)

    def add_result(self, scheduler, congestion_control, file_size, throughputs):
        key = (scheduler.name, congestion_control.name, file_size)
        self.results[key] = throughputs

        self.save_results()

    def save_results(self):
        if self.checkpointing_enabled:
            data = {
                **self.config_dict,
                "results": {
                    self._encode_key(scheduler, cc, file_size): throughputs
                    for (scheduler, cc, file_size), throughputs in self.results.items()
                },
            }
            with self.result_file.open("w") as f:
                json.dump(data, f, indent=4)

    def _encode_key(self, scheduler, cc, file_size):
        return f"{scheduler}|||{cc}|||{file_size}"

    def _decode_key(self, key):
        return key.split("|||")

    def is_test_completed(self, scheduler, congestion_control, file_size):
        key = (scheduler.name, congestion_control.name, file_size)
        return key in self.results

    def summarize_results(self):
        summary = {}

        for (scheduler, cc, file_size), throughputs in self.results.items():
            min_throughput = min(throughputs)
            max_throughput = max(throughputs)
            avg_throughput = sum(throughputs) / len(throughputs)

            summary[(scheduler, cc, file_size)] = {
                "min_throughput": min_throughput,
                "max_throughput": max_throughput,
                "avg_throughput": avg_throughput,
            }

        self.__logger.info("Test Results Summary:")

        table_data = []
        headers = [
            "Scheduler",
            "Congestion Control",
            "File Size",
            "Min Throughput (Mbps)",
            "Max Throughput (Mbps)",
            "Avg Throughput (Mbps)",
        ]

        for (scheduler, cc, file_size), metrics in summary.items():
            row = [
                scheduler,
                cc,
                file_size,
                f"{metrics['min_throughput']:.2f}",
                f"{metrics['max_throughput']:.2f}",
                f"{metrics['avg_throughput']:.2f}",
            ]
            table_data.append(row)

        table = tabulate(table_data, headers, tablefmt="grid")
        self.__logger.info(f"\n{table}\n")

    def plot_results(self):
        plot_configs = config.results.plot
        figsize = tuple(plot_configs.figsize)

        for file_size in set(key[2] for key in self.results.keys()):
            data = []
            labels = []

            for (scheduler, cc, fs), throughputs in self.results.items():
                if fs == file_size:
                    data.append(throughputs)
                    labels.append(f"{scheduler}-{cc}")

            # Create a DataFrame for Seaborn
            df = pd.DataFrame(data, index=labels).T

            plt.figure(figsize=figsize)
            sns.set(style="whitegrid")

            # Create a violin plot using Seaborn
            ax = sns.violinplot(
                data=df, palette="Set3", scale="width", inner="quartile", linewidth=1
            )

            # Customize the plot
            ax.set_xlabel("Scheduler-Congestion Control")
            ax.set_ylabel(plot_configs.ylabel)
            ax.set_title(
                f"{plot_configs.title} (Test Campaign: {config.name}, File Size: {file_size})"
            )
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right")

            # Add vertical grid lines for clarity
            for xtick in ax.get_xticks():
                ax.axvline(x=xtick, color="grey", linestyle="--", lw=0.5)

            # Add median and mean lines
            quartiles = df.quantile([0.25, 0.5, 0.75])
            for scheduler_cc, _ in df.items():
                qx = df.columns.get_loc(scheduler_cc)
                ax.vlines(
                    qx,
                    quartiles.iloc[0, qx],
                    quartiles.iloc[2, qx],
                    color="k",
                    linestyle="-",
                    lw=3,
                )
                ax.vlines(
                    qx,
                    quartiles.iloc[1, qx],
                    quartiles.iloc[1, qx],
                    color="k",
                    linestyle="-",
                    lw=3,
                )
                ax.scatter(
                    qx,
                    df[scheduler_cc].mean(),
                    marker="o",
                    color="white",
                    s=30,
                    zorder=3,
                )

            plot_file_path = RESULT_DIR / f"throughput_violinplot_{file_size}.png"
            plt.tight_layout()
            plt.savefig(plot_file_path)
            plt.close()
            self.__logger.info(f"Plot saved to {plot_file_path}")
