from abc import ABC, abstractmethod


class IClient(ABC):
    @abstractmethod
    def run_test(self, server_ip, file_size, n_iterations):
        pass
