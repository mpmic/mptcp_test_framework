import itertools
import multiprocessing
import os
import pathlib
import pickle
import statistics
import threading
import time
from copy import deepcopy
from functools import partial

import bayesian_changepoint_detection.online_changepoint_detection as oncd
import falcon_ext_mpsched as mpsched
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from bayes_online import BayesOnline

# from env import Env
from DQN import DQN_Agent
from env_ext import Env
from replay_memory import ReplayMemory, Transition
from torch.autograd import Variable
from torch.optim import Adam

CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
TMP_DIR = CURRENT_DIR / "artifacts"


class Online_Agent(threading.Thread):
    """Online Agent thread that runs parallel to scheduling/sending data
    Derives scheduling policy based on K-shot optimized meta models depending on current network characteristics
    Meta Models are called from files that are created in Offline Agent (slower loop)

    :param fd: socket file descriptor
    :type fd: int
    :param cfg: contains all the neccessary training parameter read from config.ini
    :type cfg: configParser
    :param event: event to inform the online agent of finished MPTCP connection and no need to perform new interactions
    :type event: class:'threading.event'
    """

    def __init__(self, fd, cfg, event):
        threading.Thread.__init__(self)
        self.fd = fd
        self.cfg = cfg
        self.memory = str((TMP_DIR / cfg.get("replaymemory", "memory")).resolve())
        self.agent_name = str((TMP_DIR / cfg.get("dqn", "agent")).resolve()) + "/"
        self.agent = 0
        self.env = Env(
            fd=self.fd,
            time=self.cfg.getfloat("env", "time"),
            max_flows=cfg.getint("train", "max_num_flows"),
        )
        self.batch_size = cfg.getint("train", "batch_size")
        self.event = event
        self.k = cfg.get("dqn", "k")

        self.num_ranges = cfg.getint("train", "num_ranges")
        self.max_flows = cfg.getint("train", "max_num_flows")
        self.num_char = cfg.getint("train", "num_characteristics")
        loss_range1 = np.array(
            list((map(float, cfg.get("train", "loss_range").split(","))))
        )  # .reshape((2,2))
        rtt_range1 = np.array(
            list((map(float, cfg.get("train", "rtt_range").split(","))))
        )  # .reshape((2,2))
        file_range1 = np.array(
            list((map(float, cfg.get("train", "file_range").split(","))))
        )  # file range in MB

        self.R_s = [
            loss_range1,
            loss_range1,
            rtt_range1,
            rtt_range1,
            file_range1,
            file_range1,
        ]
        self.path_char = [0] * (
            cfg.getint("train", "max_num_flows")
            * cfg.getint("train", "num_characteristics")
        )
        self.done = False
        self.ft_replay_memory = ReplayMemory(
            self.batch_size
        )  # replay memory for fine tune
        self.fft = 0  # first fine tune after starting testing
        self.current_file_size = [0] * self.max_flows

    def run(self):
        """Override the run method from threading with the desired behaviour of the Online Agent class"""
        detected_change = 0
        index = "".join(str(x) for x in self.path_char)
        self.agent = torch.load(self.agent_name + index + ".pkl")
        self.fft = 0
        while True:
            self.event.wait()
            det = []
            for i in range(self.num_char * self.max_flows):
                det.append(BayesOnline())
            state = self.env.reset()
            start = time.time()
            # if not self.done:
            # print(*(state[0 : self.max_flows]))
            count = 0
            while True:
                action = self.agent.select_action(torch.FloatTensor(state).unsqueeze(0))
                end = time.time()
                active = [0] * self.max_flows
                active[action] = 1
                # if not self.done:
                # print(end - start)
                # print(*active)
                state_nxt, reward, self.done, cond = self.env.step((action))
                start = time.time()

                if self.done or (not self.event.is_set()):
                    self.fft += 1
                    break
                cond = np.concatenate((cond, self.current_file_size))
                # print(cond)
                # if not self.done:
                # print(*(state_nxt[0 : self.max_flows]))

                # print(self.agent.train_steps)
                mask = not self.done
                if len(self.ft_replay_memory) >= 32:
                    if self.fft == 11:
                        index = "".join(str(x) for x in self.path_char)
                        self.agent = torch.load(self.agent_name + index + ".pkl")
                        if len(self.ft_replay_memory) >= self.batch_size:
                            # print("first fine tune for static scenario")
                            transitions = self.ft_replay_memory.sample(self.batch_size)
                            batch = Transition(*zip(*transitions))
                            loss = self.agent.train(batch, int(self.k))
                            # print(loss)
                            self.fft = 12
                    self.ft_replay_memory = ReplayMemory(self.batch_size)

                self.ft_replay_memory.push(
                    torch.FloatTensor(state).unsqueeze(0),
                    torch.Tensor([float(action)]),
                    torch.FloatTensor([mask]),
                    torch.FloatTensor(state_nxt).unsqueeze(0),
                    torch.FloatTensor([float(reward)]),
                )

                df = pd.DataFrame.from_dict(
                    {
                        "state": pd.Series(state),
                        "action": pd.Series(action),
                        "mask": pd.Series(mask),
                        "next state": pd.Series(state_nxt),
                        "reward": pd.Series(reward),
                        "condition": pd.Series(self.path_char),
                    },
                    orient="index",
                )

                df.to_csv(self.memory, mode="a+", index=False, header=False)

                for m in range(self.num_char * self.max_flows):
                    det[m].update(cond[m])
                    prob = det[m].get_probabilities(
                        32
                    )  # changepoint over the last 32 points (batch_size)
                    if len(prob) >= 1 and np.any(prob[1:] > 0.95):
                        det[m] = BayesOnline()
                        detected_change = 1
                if detected_change:
                    detected_change = 0
                    last_path_char = self.path_char
                    for i in range(len(self.R_s)):
                        for k in range(self.num_ranges):
                            if self.R_s[i][0::2][k] <= cond[i] <= self.R_s[i][1::2][k]:
                                self.path_char[i] = k
                    if np.any(last_path_char != self.path_char):
                        index = "".join(str(x) for x in self.path_char)
                        self.agent = torch.load(self.agent_name + index + ".pkl")
                        if len(self.ft_replay_memory) > self.batch_size:
                            transitions = self.ft_replay_memory.sample(self.batch_size)
                            batch = Transition(*zip(*transitions))
                            loss = self.agent.train(batch, int(self.k))

                # print(self.path_char)
                state = state_nxt

    def update_fd(self, fd):
        """Update the current file descriptor used in the Environment Class for reading information from subflows with socket options"""
        self.env.update_fd(fd)

    def update_cfile_size(self, size):
        """Update the current file size that is being transfered per HTTP Get request"""
        for i in range(self.max_flows):
            self.current_file_size[i] = size


class Offline_Agent(multiprocessing.Process):
    """Class for Offline Agent that reads the Online Experience csv and partitions the experience into groups of replay memories.
    For each partitioned group based on network characteristics and ranges a meta learning algortihm based on reptile meta learner is
    performed. The meta models created are then saved as the initial parameters of a DQN which will be used in the Online Agent
    when a change in network condition is observed

    :param cfg: contains all the neccessary training parameter read from config.ini
    :type cfg: configParser
    :param event: event indicating start/end of episode
    :type event: class:'threading.event'
    """

    def __init__(self, cfg, event):
        """Constructor Method"""
        multiprocessing.Process.__init__(self)
        self.memory_name = str((TMP_DIR / cfg.get("replaymemory", "memory")).resolve())
        self.nn = str((TMP_DIR / cfg.get("dqn", "agent")).resolve()) + "/"
        self.cfg = cfg
        self.episode = cfg.getint("train", "episode")
        self.batch_size = cfg.getint("train", "batch_size")
        self.event = event
        self.interval = cfg.getint("train", "interval")
        self.k = cfg.getint("dqn", "k")
        self.gamma = cfg.getfloat("dqn", "gamma")

        self.num_range = cfg.getint("train", "num_ranges")
        self.max_flows = cfg.getint("train", "max_num_flows")
        self.num_char = cfg.getint("train", "num_characteristics")

        self.meta_batch_size = cfg.getint("meta", "batch_size")

        loss_range1 = np.array(
            list((map(float, cfg.get("train", "loss_range").split(","))))
        ).reshape((2, 2))
        rtt_range1 = np.array(
            list((map(float, cfg.get("train", "rtt_range").split(","))))
        ).reshape((2, 2))
        file_range1 = np.array(
            list((map(float, cfg.get("train", "file_range").split(","))))
        )  # file range in MB

        self.R_s = [
            loss_range1,
            loss_range1,
            rtt_range1,
            rtt_range1,
            file_range1,
            file_range1,
        ]
        self.path_char = [0] * (
            cfg.getint("train", "max_num_flows")
            * cfg.getint("train", "num_characteristics")
        )

        path_char1 = list(
            itertools.product(list(range(0, self.num_range)), repeat=self.num_char)
        )
        self.ALL_CHAR = np.array(
            list(map(list, (itertools.product(path_char1, repeat=self.max_flows))))
        ).reshape((-1, self.max_flows * self.num_char))
        self.replay_memory = []
        for i in range(len(self.ALL_CHAR)):
            self.replay_memory.append(
                ReplayMemory(cfg.getint("replaymemory", "capacity"))
            )

    def run(self):
        """Override the run method from threading with the desired behaviour of the Online Agent class"""
        outer_batch_size = 32
        n_iterations = 30000  # number of meta gradient steps of falcon and also update interavl of meta models
        outer_step_size0 = (
            0.1  # starting step size of meta weights adapts to number of iterations
        )
        checkpoint = 0
        weights_before = None
        Exp = [[0]]
        print("start server")
        while True:
            print("start training meta models")
            if os.path.exists(self.memory_name):
                Exp = pd.read_csv(self.memory_name, header=None)
                if checkpoint >= len(Exp):
                    Exp = [[0]]
                else:
                    Exp = pd.read_csv(
                        self.memory_name, header=None, skiprows=checkpoint
                    )
                    checkpoint += len(Exp[0])
            t = 5
            while len(Exp[0]) != 1:
                # every 6th enrtry is the network condition
                self.path_char = np.array(
                    Exp.iloc[t, : (self.max_flows * self.num_char)]
                )
                self.path_char = [float(x) for x in self.path_char]
                combination_index = self.ALL_CHAR.tolist().index(self.path_char)
                self.replay_memory[combination_index].push(
                    torch.Tensor(
                        Exp.iloc[t - 5][0 : (5 * self.max_flows)].astype(float)
                    ).unsqueeze(0),
                    torch.FloatTensor([float(Exp.iloc[t - 4][0])]),
                    torch.Tensor([bool(Exp.iloc[t - 3][0])]),
                    torch.Tensor(
                        Exp.iloc[t - 2][0 : (5 * self.max_flows)].astype(float)
                    ).unsqueeze(0),
                    torch.FloatTensor([float(Exp.iloc[t - 1][0])]),
                )
                t += 6
                if t >= len(Exp[0]):
                    break

            # reptile learning loop using openai/research/reptile as reference
            # do n_iteration for ever partitioned group to create all meta models
            for k in range(len(self.ALL_CHAR)):
                number_of_convergence_points = 0
                index = "".join(str(x) for x in self.ALL_CHAR[k])
                agent_name = self.nn + index + ".pkl"
                agent = torch.load(agent_name)
                for i in range(n_iterations):
                    weights_before = deepcopy(agent.policy_network.state_dict())
                    if len(self.replay_memory[k]) > self.batch_size * 1000:
                        transitions = self.replay_memory[k].sample(self.batch_size)
                        batch = Transition(*zip(*transitions))
                        loss = agent.train(batch, self.k)
                        # print(loss)
                        weights_after = agent.policy_network.state_dict()

                        outer_step_size = outer_step_size0 * (1 - i / n_iterations)

                        for name in weights_before:
                            weights_before[name] += outer_step_size * (
                                weights_after[name] - weights_before[name]
                            )
                        # hard update policy and traget network with new meta gradient as starting point
                        # for the next k step of optimization in the following episode
                        agent.update_state_dict(weights_before, i)

                torch.save(agent, agent_name)
            time.sleep(5)
