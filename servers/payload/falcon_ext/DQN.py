#!/usr/bin/env python3
# DQN Online Learning module that uses reptile META Learner
# initial DQN setup taken from ESE546 final project github.com/sheilsarda/ES546_Final_Project

import math
import os
import pickle
import random
from copy import deepcopy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from replay_memory import ReplayMemory, Transition
from torch.autograd import Variable
from torch.optim import SGD, Adam


class DQN_Network(nn.Module):
    def __init__(self, num_inputs, hidden_size, num_outputs):
        super(DQN_Network, self).__init__()
        self.num_inputs = num_inputs
        self.hidden_size = hidden_size
        self.num_outputs = num_outputs

        self.linear1 = nn.Linear(self.num_inputs, 64)
        self.linear3 = nn.Linear(64, 32)
        self.linear4 = nn.Linear(32, 16)
        self.linear5 = nn.Linear(16, self.num_outputs)

    def forward(self, state):
        out = F.relu(self.linear1(state))
        out = F.relu(self.linear3(out))
        out = F.relu(self.linear4(out))
        action = self.linear5(out)

        return action


class DQN_Agent:
    def __init__(self, num_inputs, hidden_size, num_outputs, gamma):
        self.policy_network = DQN_Network(num_inputs, hidden_size, num_outputs)
        self.target_network = DQN_Network(num_inputs, hidden_size, num_outputs)
        self.target_network.load_state_dict(self.policy_network.state_dict())

        self.num_outputs = num_outputs
        self.optimizer = Adam(self.policy_network.parameters(), lr=1e-3)
        self.gamma = gamma
        self.eps_l = 0.3
        self.eps_s = 0.1
        self.train_steps = 0

    def train(self, batch, k):
        batch_state = Variable(torch.cat(batch.state))
        batch_next_state = Variable(torch.cat(batch.next_state))
        batch_action = Variable(torch.cat(batch.action)).unsqueeze(1)
        batch_reward = Variable(torch.cat(batch.reward)).unsqueeze(1)
        batch_mask = Variable(torch.cat(batch.mask)).unsqueeze(1)
        # k-steps of adam

        for i in range(k):
            with torch.no_grad():
                q_val_next = self.target_network(batch_next_state)
                preds = (
                    batch_reward
                    + (1 - batch_mask)
                    * self.gamma
                    * torch.max(q_val_next, dim=1, keepdim=True)[0]
                )

            loss = F.mse_loss(
                self.policy_network(batch_state).gather(1, batch_action.long()), preds
            )
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        self.train_steps += 1

        return loss.item()

    def select_action(self, state):
        # epsilon greedy exploration
        random_n = random.random()

        eps_threshold = self.eps_l
        if self.train_steps >= 30000:
            eps_threshold = self.eps_s

        if random_n < eps_threshold:
            random_action = random.randint(0, self.num_outputs - 1)
            action = torch.tensor([random_action])
        else:
            with torch.no_grad():
                action = torch.argmax(self.policy_network(state), dim=1)
        return action.item()

    def update_state_dict(self, state_dict, iteration):
        self.policy_network.load_state_dict(state_dict)
        self.target_network.load_state_dict(state_dict)
        self.optimizer = Adam(self.policy_network.parameters(), lr=1e-3)
