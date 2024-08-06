# schedulers/scheduler_factory.py

from .built_in_scheduler import (
    BLESTScheduler,
    ECFScheduler,
    LATEScheduler,
    MinRTTScheduler,
    RedundantScheduler,
    RoundRobinScheduler,
)
from .reinforcement_learning_scheduler import (
    FALCONExtScheduler,
    FALCONScheduler,
    RELESExtScheduler,
    RELESScheduler,
)


class SchedulerFactory:
    @staticmethod
    def create_scheduler(scheduler_config, client, server):
        scheduler_name = scheduler_config["name"]
        scheduler_params = scheduler_config.get("params", {})

        if scheduler_name in ("MinRTTScheduler", "DefaultScheduler"):
            return MinRTTScheduler(client=client, server=server)
        elif scheduler_name == "RoundRobinScheduler":
            return RoundRobinScheduler(client=client, server=server)
        elif scheduler_name == "ECFScheduler":
            return ECFScheduler(client=client, server=server)
        elif scheduler_name == "BLESTScheduler":
            return BLESTScheduler(client=client, server=server)
        elif scheduler_name == "RedundantScheduler":
            return RedundantScheduler(client=client, server=server)
        elif scheduler_name == "FALCONScheduler":
            return FALCONScheduler(
                client=client, server=server, params=scheduler_params
            )
        elif scheduler_name == "RELESScheduler":
            return RELESScheduler(client=client, server=server, params=scheduler_params)
        elif scheduler_name == "FALCONExtScheduler":
            return FALCONExtScheduler(
                client=client, server=server, params=scheduler_params
            )
        elif scheduler_name == "RELESExtScheduler":
            return RELESExtScheduler(
                client=client, server=server, params=scheduler_params
            )
        elif scheduler_name == "LATEScheduler":
            return LATEScheduler(client=client, server=server)
        else:
            raise ValueError(f"Unsupported scheduler: {scheduler_name}")

    @staticmethod
    def create_schedulers(schedulers, client, server):
        return [
            SchedulerFactory.create_scheduler(scheduler, client, server)
            for scheduler in schedulers
        ]
