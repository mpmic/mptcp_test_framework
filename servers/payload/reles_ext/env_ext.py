import time

import numpy as np
import reles_ext_mpsched as mpsched


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
        self.path_mask = [
            [0] for _ in range(self.max_num_flows)
        ]  # path mask for ordering from user space to kernel space

    def adjust(self, state):
        """Converts the raw observations collected with mpsched socket api into appropriate values for state information and reward
        calculation

        :param state: Raw observations from socket api with mpsched extension
        :type state: list
        :return: State parameters
        :rtype: list
        """
        for i in range((self.max_num_flows)):
            if len(self.tp[i]) == self.k:
                self.tp[i].pop(0)
                self.rtt[i].pop(0)
                self.cwnd[i].pop(0)
                self.rr[i].pop(0)
                self.in_flight[i].pop(0)
            self.tp[i].append(0)
            self.rtt[i].append(0)
            self.cwnd[i].append(0)
            self.rr[i].append(0)
            self.in_flight[i].append(0)
        for i in range(len(state)):
            if len(self.last) < self.max_num_flows:
                self.last.append([0, 0, 0, 0, 0])
            if state[i][5] == 16842762:
                self.path_mask[0] = i
                k = 0
            elif state[i][5] == 33685514:
                self.path_mask[1] = i
                k = 1
            elif state[i][5] == 50528266:
                self.path_mask[2] = i
                k = 2
            else:  # if not intf 1 or intf 2 skip
                continue

            self.tp[k][-1] = np.abs(state[i][0] - self.last[i][0]) * 1.44
            self.rtt[k][-1] = (state[i][1]) / 1000
            self.cwnd[k][-1] = (state[i][2] + self.last[i][2]) / 2
            self.rr[k][-1] = np.abs(state[i][3] - self.last[i][3])
            self.in_flight[k][-1] = np.abs(state[i][4] - self.last[i][4])
        self.last = state
        return np.concatenate((self.tp, self.rtt, self.cwnd, self.rr, self.in_flight))

    def reward(self):
        """Calculates the reward of the last SI using the ReLes reward function which consideres multiple QoS parameters
        After making measruements of path parameters with mpsched call adjust to apply changes to the Environments' state variables
        that are used for the reward calculation

        :return: Reward value
        :type: float
        """
        rewards = sum(np.array(self.tp)[:, self.k - 1])
        if rewards != 0:
            rewards = rewards - (1 / rewards) * self.alpha * sum(
                np.array(self.rtt)[:, self.k - 1] * (np.array(self.tp)[:, self.k - 1])
            )
            rewards = rewards - self.b * (
                1 / sum(np.array(self.tp)[:, self.k - 1])
            ) * sum(
                np.array(self.rr)[:, self.k - 1] * (np.array(self.tp)[:, self.k - 1])
            )
        else:
            rewards = 0
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
            for m in range((self.max_num_flows)):
                if len(self.tp[m]) == self.k:
                    self.tp[m].pop(0)
                    self.rtt[m].pop(0)
                    self.cwnd[m].pop(0)
                    self.rr[m].pop(0)
                    self.in_flight[m].pop(0)
                self.tp[m].append(0)
                self.rtt[m].append(0)
                self.cwnd[m].append(0)
                self.rr[m].append(0)
                self.in_flight[m].append(0)
            for j in range(len(subs)):
                if len(self.last) < (self.max_num_flows):
                    self.last.append([0, 0, 0, 0, 0])
                if subs[j][5] == 16842762:  # 2785061056 ,16842762
                    self.path_mask[0] = j
                    k = 0
                elif subs[j][5] == 33685514:  # 3892357312 ,33685514
                    self.path_mask[1] = j
                    k = 1
                elif subs[j][5] == 50528266:  # 2868947136,50528266
                    self.path_mask[2] = j
                    k = 2
                else:  # if not intf 1 or intf 2 skip
                    continue
                self.tp[k][-1] = np.abs(subs[j][0] - self.last[j][0]) * 1.44
                self.rtt[k][-1] = subs[j][1] / 1000
                self.cwnd[k][-1] = (subs[j][2] + self.last[j][2]) / 2
                self.rr[k][-1] = np.abs(subs[j][3] - self.last[j][3])
                self.in_flight[k][-1] = np.abs(subs[j][4] - self.last[j][4])
            self.last = subs
            time.sleep((self.time) / 10)
        return np.concatenate((self.tp, self.rtt, self.cwnd, self.rr, self.in_flight))

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
