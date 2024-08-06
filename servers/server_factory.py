# servers/server_factory.py

from __future__ import annotations

from typing import TYPE_CHECKING

from schedulers.ischeduler import BuiltInScheduler
from schedulers.reinforcement_learning_scheduler import (
    FALCONExtScheduler,
    FALCONScheduler,
    RELESExtScheduler,
    RELESScheduler,
)
from servers.default_server import DefaultServer
from servers.reinforcement_learning_server import (
    FALCONExtServer,
    FALCONServer,
    RELESExtServer,
    RELESServer,
)

if TYPE_CHECKING:
    from servers.iserver import IServer


class ServerFactory:
    @staticmethod
    def create_server(scheduler, server_host) -> IServer:
        if isinstance(scheduler, BuiltInScheduler):
            return DefaultServer(server_host)
        elif isinstance(scheduler, FALCONScheduler):
            return FALCONServer(server_host, server_params=scheduler.params)
        elif isinstance(scheduler, RELESScheduler):
            return RELESServer(server_host, server_params=scheduler.params)
        elif isinstance(scheduler, FALCONExtScheduler):
            return FALCONExtServer(server_host, server_params=scheduler.params)
        elif isinstance(scheduler, RELESExtScheduler):
            return RELESExtServer(server_host, server_params=scheduler.params)
        else:
            raise ValueError(f"Unsupported scheduler type: {type(scheduler)}")
