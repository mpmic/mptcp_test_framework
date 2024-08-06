import statistics
import time

import falcon_ext_mpsched as mpsched
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
        self.fd = fd
        self.time = time
        self.num_segments = 20
        self.k = 8
        self.max_num_flows = max_flows
        self.alpha = 0.3
        self.b = 0.5

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

    def adjust(self, state):
        for m in range(self.max_num_flows):
            # adjust initial values to represent worst case for each characteristic (e.g RTT->inf) s.t path is unfavorable for decision
            self.tp[m] = 0
            self.rtt[m] = 0
            self.cwnd[m] = 0
            self.rr[m] = 0
            self.in_flight[m] = 0
            self.packet_loss[m] = 0
            self.send_wnd[m] = 0
        for i in range(len(state)):
            if len(self.last) < (len(state)):
                self.last.append([0, 0, 0, 0, 0, 0])
            if state[i][5] == 16842762:  # 2785061056 ,16842762
                self.path_mask[0] = i
                k = 0
            elif state[i][5] == 33685514:  # 3892357312 ,33685514
                self.path_mask[1] = i
                k = 1
            elif state[i][5] == 50528266:  # 2868947136,50528266
                self.path_mask[2] = i
                k = 2
            else:  # if not intf 1 or intf 2 skip
                continue
            self.tp[k] = (
                np.abs(state[i][0] - self.last[i][0]) * 1440
            )  # 1440 is MSS taken from kernel information sudo dmesg
            self.rtt[k] = state[i][1] / 1000
            if self.rtt[k] != 0:
                self.rtts[k].append(self.rtt[k])
            else:
                self.rtts[k].append(self.mean_RTT[k])
            self.mean_RTT[k] = statistics.fmean(self.rtts[k])

            self.cwnd[k] = state[i][2] / self.rtt[k]
            self.rr[k] = np.abs(state[i][3] - self.last[i][3]) / self.rtt[k]
            self.in_flight[k] = np.abs(state[i][4] - self.last[i][4])
            self.send_wnd[k] = state[i][6] / (self.rtt[k] * 1000)
            if self.tp[k] != 0:
                self.packet_loss[k] = (self.in_flight[k] / self.tp[k]) * 100
            else:
                self.packet_loss[k] = 0
            # print(state[i][5])
        self.last = state
        return (
            list(np.concatenate((self.rtt, self.cwnd, self.rr, self.send_wnd))),
            list(np.concatenate((self.packet_loss, self.mean_RTT))),
        )

    def reward(self):
        """Calculates the reward of FALCON which is the Throughput of all subflows since the last measurment

        :return: Reward value
        :type: float
        """
        rewards = sum(np.array(self.tp))
        if rewards != 0:
            rewards = rewards - (1 / rewards) * self.alpha * sum(
                np.array(self.rtt) * (np.array(self.tp))
            )
            rewards = rewards - self.b * (1 / sum(np.array(self.tp))) * sum(
                np.array(self.rr) * (np.array(self.tp))
            )
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
                self.rtt[m] = 0
                self.cwnd[m] = 0
                self.rr[m] = 0
                self.in_flight[m] = 0
                self.packet_loss[m] = 0
                self.send_wnd[m] = 0
            for j in range(len(subs)):
                if len(self.last) < (len(subs)):
                    self.last.append([0, 0, 0, 0, 0, 0])
                if subs[j][5] == 16842762:  # 2785061056 ,16842762
                    self.path_mask[0] = j
                    k = 0
                elif subs[j][5] == 33685514:  # 3892357312 ,33685514
                    self.path_mask[1] = j
                    k = 1
                elif subs[j][5] == 50528266:  # 2868947136,50528266
                    self.path_mask[2] = j
                    k = 2
                else:
                    continue
                self.tp[k] = (np.abs(subs[j][0] - self.last[j][0])) * 1440
                self.rtt[k] = subs[j][1] / 1000
                self.cwnd[k] = subs[j][2] / self.rtt[k]
                self.rr[k] = np.abs(subs[j][3] - self.last[j][3]) / self.rtt[k]
                self.in_flight[k] = np.abs(subs[j][4] - self.last[j][4])
                self.send_wnd[k] = subs[j][6] / (self.rtt[k] * 1000)
                if self.tp[k] != 0:
                    self.packet_loss[k] = (self.in_flight[k] / self.tp[k]) * 100
                else:
                    self.packet_loss[k] = 0
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
        active[self.path_mask[action]] = int(1)
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
