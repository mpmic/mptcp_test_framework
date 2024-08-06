import time

import numpy as np
import reles_mpsched as mpsched


class Env:
    """Evnironment class for agent interaction.

    :param fd: socket file descriptor
    :type fd: int
    :param time: Stater Interval (SI). usually 3~4 RTTs
    :type time: int
    :param k: Number of past timesteps used in the stacked LSTM
    :type k: int
    :param alpha: first parameter of reward function to scale BDP (reduce bufferbloat|min->favors fast paths)
    :type alpha: float
    :param beta: second parameter of reward function to scale number of loss packets (reflects network congetsion|min->favors less congested paths)
    :type beta: float
    """

    def __init__(self, fd, time, k, alpha, b, c, max_flows):
        """Constructor method"""
        self.fd = fd
        self.time = time
        self.k = k
        self.alpha = alpha
        self.b = b
        self.c = c
        self.num_segments = 10
        self.max_num_flows = max_flows

        self.last = [[0] * 5 for _ in range(self.max_num_flows)]
        self.tp = [
            [] for _ in range(self.max_num_flows)
        ]  # num of segments out (MSS=1440B)
        self.rtt = [[] for _ in range(self.max_num_flows)]  # snapshot of rtt
        self.dRtt = [[] for _ in range(self.max_num_flows)]
        self.cwnd = [[] for _ in range(self.max_num_flows)]  # cwnd sender
        self.rr = [
            [] for _ in range(self.max_num_flows)
        ]  # number of unacked packets (in flight)
        self.in_flight = [
            [] for _ in range(self.max_num_flows)
        ]  # number of TOTAL retransmissions

    def adjust(self, state):
        """Converts the raw observations collected with mpsched socket api into appropriate values for state information and reward
        calculation

        :param state: Raw observations from socket api with mpsched extension
        :type state: list
        :return: State parameters
        :rtype: list
        """
        for i in range(len(state)):  # in range 2 if len sate < 2 etc.
            if len(self.tp[i]) == self.k:
                self.tp[i].pop(0)
                self.rtt[i].pop(0)
                self.dRtt[i].pop(0)
                self.cwnd[i].pop(0)
                self.rr[i].pop(0)
                self.in_flight[i].pop(0)
            if len(self.last) < self.max_num_flows:
                # if not all subflows appeared yet set rest to 0
                for _ in range(self.max_num_flows - len(self.last)):
                    self.last.append([0, 0, 0, 0, 0])
            if len(state) < self.max_num_flows:
                for _ in range(self.max_num_flows - len(state)):
                    state.append([0, 0, 0, 0, 0])
            self.tp[i].append(np.abs(state[i][0] - self.last[i][0]) * 1.44)
            self.rtt[i].append((state[i][1]) / 1000)
            self.dRtt[i].append(state[i][1] - self.last[i][1])
            self.cwnd[i].append((state[i][2] + self.last[i][2]) / 2)
            self.rr[i].append(np.abs(state[i][3] - self.last[i][3]))
            self.in_flight[i].append(
                np.abs(state[i][4] - self.last[i][4])
            )  # look at wording in reles paper
        self.last = state
        return [
            self.tp[0],
            self.tp[1],
            self.rtt[0],
            self.rtt[1],
            self.cwnd[0],
            self.cwnd[1],
            self.rr[0],
            self.rr[1],
            self.in_flight[0],
            self.in_flight[1],
        ]

    def reward(self):
        """Calculates the reward of the last SI using the ReLes reward function which consideres multiple QoS parameters
        After making measruements of path parameters with mpsched call adjust to apply changes to the Environments' state variables
        that are used for the reward calculation

        :return: Reward value
        :type: float
        """
        rewards = (self.tp[0][self.k - 1]) + (self.tp[1][self.k - 1])
        if rewards != 0:
            rewards = rewards - (1 / rewards) * self.alpha * (
                (
                    self.rtt[0][self.k - 1] * self.tp[0][self.k - 1]
                    + self.rtt[1][self.k - 1] * self.tp[1][self.k - 1]
                )
            )
        else:
            rewards = 0
        rewards = rewards - self.b * (
            self.in_flight[0][self.k - 1] + self.in_flight[1][self.k - 1]
        )

        return rewards

    def reset(self):
        """Initialization of the Environment variables with the first k measurments where k is the number of past timesteps used in
        the stacked LSTM part of the NAF Q-network

        :return: State parameters
        :rtype: list
        """
        self.last = mpsched.get_sub_info(self.fd)
        # record k measurements
        for i in range(self.k):
            subs = mpsched.get_sub_info(self.fd)
            for j in range(self.max_num_flows):
                if len(self.tp[j]) == self.k:
                    self.tp[j].pop(0)
                    self.rtt[j].pop(0)
                    self.dRtt[j].pop(0)
                    self.cwnd[j].pop(0)
                    self.rr[j].pop(0)
                    self.in_flight[j].pop(0)
                if len(self.last) < (self.max_num_flows):
                    for _ in range(self.max_num_flows - len(self.last)):
                        self.last.append([0, 0, 0, 0, 0])
                if len(subs) < self.max_num_flows:
                    for _ in range(self.max_num_flows - len(subs)):
                        subs.append([0, 0, 0, 0, 0])
                self.tp[j].append(np.abs(subs[j][0] - self.last[j][0]) * 1.44)
                self.rtt[j].append((subs[j][1] / 1000))
                self.dRtt[j].append(np.abs(subs[j][1] - self.last[j][1]))
                self.cwnd[j].append((subs[j][2] + self.last[j][2]) / 2)
                self.rr[j].append(np.abs(subs[j][3] - self.last[j][3]))
                self.in_flight[j].append(np.abs(subs[j][4] - self.last[j][4]))
            self.last = subs
            time.sleep((self.time) / 10)
        return [
            self.tp[0],
            self.tp[1],
            self.rtt[0],
            self.rtt[1],
            self.cwnd[0],
            self.cwnd[1],
            self.rr[0],
            self.rr[1],
            self.in_flight[0],
            self.in_flight[1],
        ]

    def update_fd(self, fd):
        self.fd = fd

    def step(self, action):
        """Performs all neccessary actions to transition the Environment from SI t into t+1.
        Actions include among other things:
        -setting the split factor for the kernel scheduler using socket api with mpsched extension
        -calculated the reward of the action of state t using reward method
        -wait SI until the begin of the next state t+1
        -take measurement of the new path characteristics after taking action t using socket api with mpsched extension
        -adjust the current environment variables using adjust method

        :param action: split factor derived using the current policy network of the ReLes NAF NN
        :type action: list
        :return: state observation of the next state t+1,reward value and boolean indication whether bulk transfer is over
        :rtype: list,float,boolean
        """

        splits = []
        A = [self.fd]

        for k in range(self.max_num_flows):
            kaction = (action[0][k] + 1) / 2  # high = 10 low = 1
            kaction *= self.num_segments - 1
            kaction += 1
            splits.append(int(np.round(kaction)))
        A = list(np.concatenate((A, splits)))
        # print(*splits)

        mpsched.set_seg(A)

        time.sleep(self.time)
        state_nxt = mpsched.get_sub_info(self.fd)
        # print(state_nxt)
        done = False
        if not state_nxt:
            done = True
        state_nxt = self.adjust(state_nxt)
        reward = self.reward()

        return state_nxt, reward, done
