from abc import ABC, abstractmethod


class IServer(ABC):
    @abstractmethod
    def serve(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @abstractmethod
    def killall(self):
        pass

    def __enter__(self):
        self.killall()
        self.serve()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kill()
        self.killall()
