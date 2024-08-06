from clients.default_client import DefaultClient
from schedulers.ischeduler import BaseScheduler


class ClientFactory:
    @staticmethod
    def create_client(scheduler, client_host, server_host):
        if isinstance(scheduler, BaseScheduler):
            return DefaultClient(client_host, server_host)
        else:
            raise ValueError(f"Unsupported scheduler type: {type(scheduler)}")
