import statistics
import time

import falcon_mpsched as mpsched
import numpy as np


class Env:
    """Evnironment class for agent interaction.

    :param fd: socket file descriptor
    :type fd: int
    :param time: State Interval (SI). usually 3~4 RTTs
    :type time: int
    :param k: Number of past timesteps used in the stacked LSTM
    :param k: int
    :param max_flows: Maximum possible number of available subflows
    :type max_flows: int
    """

    def __init__(self, fd, time, max_flows):
        """Constructor method"""
        self.fd = fd
        self.time = time
        self.k = 8
        self.max_num_flows = max_flows

        # only works for 2 subflows with this declaration
        self.last = [[0] * 5 for _ in range(self.max_num_flows)]
        self.tp = [
            0
        ] * self.max_num_flows  # number of segs sent(Max number of subflows)
        self.rtt = [0] * self.max_num_flows  # snapshot of rtt
        self.drtt = [0] * self.max_num_flows  # ratio of RTT deviation to mean RTTT
        self.cwnd = [0] * self.max_num_flows  # cwnd
        self.rr = [0] * self.max_num_flows  # number of packets in flight
        self.in_flight = [
            0
        ] * self.max_num_flows  # number of total retransmission (packets_lost)
        self.packet_loss = [
            0
        ] * self.max_num_flows  # packet loss in percent compared to segs_out(tp)
        self.send_wnd = [0] * self.max_num_flows  # SWND in bytes
        self.rtts = [[] for _ in range(self.max_num_flows)]
        self.mean_RTT = [
            0
        ] * self.max_num_flows  # current mean RTT of paths to calculate deviation to current RTT
        self.path_mask = [
            0
        ] * self.max_num_flows  # path mask for ordering from user space to kernel space
        self.rtt_deviation = [
            0
        ] * self.max_num_flows  # deviation of mean rtt to current rtt

    def adjust(self, state):
        """Converts the raw observations collected with mpsched socket api into appropriate values for state information and reward
        calculation

        :param state: Raw observations from socket api with mpsched extension
        :type state: list

        :return: All values for state infomration from socket api measurments as well as current network condition
        :type: list
        """
        for m in range(self.max_num_flows):
            # adjust initial values to represent worst case for each characteristic (e.g RTT->inf) s.t path is unfavorable for decision
            self.tp[m] = 0
            self.rtt[m] = 32000
            self.cwnd[m] = 0
            self.rr[m] = 32000
            self.in_flight[m] = 0
            self.packet_loss[m] = 0
            self.send_wnd[m] = 0
        for i in range(len(state)):
            if len(self.last) < (len(state)):
                self.last.append([0, 0, 0, 0, 0, 0])
            self.tp[i] = (
                np.abs(state[i][0] - self.last[i][0]) * 1440
            )  # 1440 is MSS taken from kernel information sudo dmesg
            self.rtt[i] = state[i][1] / 1000
            if self.rtt[i] != 32000:
                self.rtts[i].append(self.rtt[i])
            else:
                self.rtts[i].append(self.mean_RTT[i])
            self.mean_RTT[i] = statistics.fmean(self.rtts[i])
            if self.mean_RTT[i] != 0:
                self.rtt_deviation[i] = self.rtt[i] / self.mean_RTT[i]
            self.cwnd[i] = state[i][2] / self.rtt[i]
            self.rr[i] = np.abs(state[i][3] - self.last[i][3]) / self.rtt[i]
            self.in_flight[i] = np.abs(state[i][4] - self.last[i][4])
            self.send_wnd[i] = state[i][6] / (self.rtt[i] * 1000)
            if self.tp[i] != 0:
                self.packet_loss[i] = (self.in_flight[i] * 1440 / self.tp[i]) * 100
            else:
                self.packet_loss[i] = 0
            # print(state[i][5])
        self.last = state
        return (
            list(np.concatenate((self.rtt, self.cwnd, self.rr, self.send_wnd))),
            list(np.concatenate((self.packet_loss, self.mean_RTT, self.rtt_deviation))),
        )  # net char used packetloss,mean rtt and deviation

    def reward(self):
        """Calculates the reward of FALCON which is the Throughput of all subflows since the last measurment

        :return: Reward value
        :type: float
        """
        if self.rtt != 0:
            rewards = (sum(self.tp)) / (sum(self.rtt) / 2)
        else:
            rewards = 0
        return rewards

    def reset(self):
        """Initialization of the Environment variables with the last of k measurments where k is a user defined parameter

        :return: State parameters
        :rtype: list
        """
        self.last = mpsched.get_sub_info(self.fd)
        self.rtts = [[] for _ in range(self.max_num_flows)]
        self.mean_RTT = [0] * self.max_num_flows
        for i in range(self.k):
            subs = mpsched.get_sub_info(self.fd)
            for m in range(self.max_num_flows):
                self.tp[m] = 0
                self.rtt[m] = 32000
                self.cwnd[m] = 0
                self.rr[m] = 32000
                self.in_flight[m] = 0
                self.packet_loss[m] = 0
                self.send_wnd[m] = 0
            for j in range(len(subs)):
                if len(self.last) < (len(subs)):
                    self.last.append([0, 0, 0, 0, 0, 0])
                self.tp[j] = (np.abs(subs[j][0] - self.last[j][0])) * 1440
                self.rtt[j] = subs[j][1] / 1000
                self.cwnd[j] = subs[j][2] / self.rtt[j]
                self.rr[j] = np.abs(subs[j][3] - self.last[j][3]) / self.rtt[j]
                self.in_flight[j] = np.abs(subs[j][4] - self.last[j][4])
                self.send_wnd[j] = subs[j][6] / (self.rtt[j] * 1000)
                if self.tp[j] != 0:
                    self.packet_loss[j] = (self.in_flight[j] * 1440 / self.tp[j]) * 100
                else:
                    self.packet_loss[j] = 0
                # print(subs[j][5])
            self.last = subs
        return list(np.concatenate((self.rtt, self.cwnd, self.rr, self.send_wnd)))

    def update_fd(self, fd):
        self.fd = fd

    def step(self, action):
        """Performs all neccessary actions to transition the Environment into the next state.
        Actions include among other things:
        -setting the desired subflow in the kernel scheduler using socket api with mpsched extension
        -calculated the reward of the action using reward method
        -take measurement of the new path characteristics after taking action using socket api with mpsched extension
        -adjust the current environment variables using adjust method

        :param action: output of the DQN with position of desired subflow set to one
        :type action: list
        :return: state observation of the next state t+1,reward value, flag to signal end and current network conditions
        :rtype: list,float,boolean,list
        """
        active = [int(0)] * self.max_num_flows
        active[action] = int(1)
        A = [self.fd]

        A = list(np.concatenate((A, active)))

        # print(active)
        mpsched.set_seg(A)

        state_nxt = mpsched.get_sub_info(self.fd)
        # print(state_nxt)
        done = False
        if not state_nxt:
            done = True

        state_nxt, cond = self.adjust(state_nxt)

        reward = self.reward()
        # print(reward)

        return state_nxt, reward, done, cond
