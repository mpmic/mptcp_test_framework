import pickle
import random
import threading
from collections import namedtuple

Transition = namedtuple(
    "Transition", ("state", "action", "mask", "next_state", "reward")
)


class ReplayMemory(object):
    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, *args):
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = Transition(*args)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        result = random.sample(self.memory, batch_size)
        return result

    def __len__(self):
        return len(self.memory)
