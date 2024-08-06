import os
import pathlib
import threading
import time

import numpy as np
import reles_ext_mpsched as mpsched
import torch
from env_ext import Env

# from env import Env
from naf_lstm import NAF_LSTM
from ounoise import OUNoise
from replay_memory import ReplayMemory, Transition
from torch.autograd import Variable

CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
TMP_DIR = CURRENT_DIR / "artifacts"


class Online_Agent(threading.Thread):
    """Class for Online Agent thread that calls evnironment step to perform agent<->enviornment interaction as expected in reinforcement
    learning. Adjusts the split factor using the policy network of the ReLes NN after every SI until the end of the MPTCP connection
    At the start of every MPTCP connection synchronize ReLes NN (NAF+stacked LSTM) with the "offline agent" using torch.load
    Saves collected experience in replay buffer for the offline agent to use for training

    :param fd: socket file descriptor
    :type fd: int
    :param cfg: contains all the neccessary training parameter read from config.ini
    :type cfg: configParser
    :param memory: replaymemory used for adding online experience
    :type memory: class:'ReplayMemory'
    :param event: event to inform the online agent of finished MPTCP connection and no need to perform new interactions
    :type event: class:'threading.event'
    :param explore: Whether or not to use action exploration
    :explore type: boolean
    """

    def __init__(self, fd, cfg, memory, event, explore=True):
        """Constructor Method"""
        threading.Thread.__init__(self)
        self.fd = fd
        self.cfg = cfg
        self.memory = memory
        self.agent_name = str((TMP_DIR / cfg.get("nafcnn", "agent")).resolve())
        self.ounoise = OUNoise(action_dimension=1)
        self.explore = explore
        self.max_flows = cfg.getint("env", "max_num_subflows")
        self.agent = torch.load(self.agent_name)
        mpsched.persist_state(fd)
        self.env = Env(
            fd=self.fd,
            time=self.cfg.getfloat("env", "time"),
            k=self.cfg.getint("env", "k"),
            alpha=self.cfg.getfloat("env", "alpha"),
            b=self.cfg.getfloat("env", "b"),
            c=self.cfg.getfloat("env", "c"),
            max_flows=self.max_flows,
        )
        self.event = event

    def run(self):
        """Override the run method from threading with the desired behaviour of the Online Agent class"""
        if True:
            self.event.wait()
            state = self.env.reset()
            # print(*(np.array(state)[self.max_flows : self.max_flows * 2, 7]))
            state = torch.FloatTensor(state).view(-1, 1, 8, 1)
            while True:
                start = time.time()
                if self.explore:
                    action = self.agent.select_action(state, self.ounoise)
                else:
                    action = self.agent.select_action(state)
                end = time.time()
                # print(action)
                # print(end - start)
                state_nxt, reward, done = self.env.step((action))
                # print(reward)
                if done or not self.event.is_set():
                    break
                # print(*(np.array(state_nxt)[self.max_flows : self.max_flows * 2, 7]))
                action = torch.FloatTensor(action)
                mask = torch.Tensor([not done])
                state_nxt = torch.FloatTensor(state_nxt).view(-1, 1, 8, 1)
                reward = torch.FloatTensor([float(reward)])
                self.memory.push(state, action, mask, state_nxt, reward)
                state = state_nxt

    def update_fd(self, fd):
        """Update the current file descriptor used in the Environment Class for reading information from subflows with socket options"""
        self.env.update_fd(fd)


class Offline_Agent(threading.Thread):
    """Class for Offline Agent that is solely resposible for training the ReLes neural network on already collected
    experience saved in the replay buffer.

    :param nn: path to pkl file to save updated NN parameters
    :type nn: string
    :param cfg: contains all the neccessary training parameter read from config.ini
    :type cfg: configParser
    :param memory: replaymemory used for reading training data to optimise the ReLes NN
    :type memory: class:'ReplayMemory'
    :param event: event indicating start/end of episode
    :type event: class:'threading.event'
    """

    def __init__(self, cfg, model, memory, event):
        """Constructor Method"""
        threading.Thread.__init__(self)
        self.memory = memory
        self.model = model
        # self.episode = cfg.getint("train","episode")
        self.batch_size = cfg.getint("train", "batch_size")
        self.event = event
        max_flows = cfg.getint("env", "max_num_subflows")

    def run(self):
        """Starts the training loop for the ReLes NN. Start of an episode is at the beggining of a new MPTCP connection and the end
        is defined at the tear down of said MPTCP connection.Saves updated model in pkl file using torch save for the online agent
        to read and update its paramters.
        """
        # subject to change
        agent = torch.load(self.model)
        print("start offline agent")
        while True:
            self.event.wait(timeout=60)
            if len(self.memory) > self.batch_size:
                # print("enough memory available")
                for __ in range(1):
                    transitions = self.memory.sample(self.batch_size)
                    batch = Transition(*zip(*transitions))
                    # print(agent.update_parameters(batch))
                    if not self.event.is_set():
                        torch.save(agent, self.model)
                        break
