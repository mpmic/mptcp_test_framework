import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from gym import spaces
from torch.autograd import Variable
from torch.optim import SGD, Adam

# NAF network from github.com/ikostrikov/pytorch-ddpg-naf with addition of stacked LSTM to adjust with 8 past time steps


def MSELoss(input, target):
    return torch.sum((input - target) ** 2) / input.data.nelement()


def soft_update(target, source, tau):
    for target_param, param in zip(target.parameters(), source.parameters()):
        target_param.data.copy_(target_param.data * (1.0 - tau) + param.data * tau)


def hard_update(target, source):
    for target_param, param in zip(target.parameters(), source.parameters()):
        target_param.data.copy_(param.data)


class Policy(nn.Module):
    def __init__(self, hidden_size, num_inputs, action_space):
        super(Policy, self).__init__()
        self.action_space = action_space
        num_outputs = action_space
        # LSTM implementation using wuyifan18 Deeplog git
        self.hidden_size = hidden_size
        self.hidden_lstm = 16

        self.lstm0 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm1 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm2 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm3 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm4 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm5 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm6 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm7 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm8 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        self.lstm9 = nn.LSTM(
            1, self.hidden_lstm, 2, batch_first=True
        )  # 2 layers stacked LSTM
        # self.fc = nn.Linear(hidden_size,10)

        self.bn0 = nn.BatchNorm1d(self.hidden_lstm * 10)
        self.bn0.weight.data.fill_(1)
        self.bn0.bias.data.fill_(0)

        self.linear1 = nn.Linear(self.hidden_lstm * 10, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.bn1.weight.data.fill_(1)
        self.bn1.bias.data.fill_(0)

        self.linear2 = nn.Linear(hidden_size, hidden_size)
        self.bn2 = nn.BatchNorm1d(hidden_size)
        self.bn2.weight.data.fill_(1)
        self.bn2.bias.data.fill_(0)

        self.V = nn.Linear(hidden_size, 1)
        self.V.weight.data.mul_(0.1)
        self.V.bias.data.mul_(0.1)

        self.mu = nn.Linear(hidden_size, num_outputs)
        self.mu.weight.data.mul_(0.1)
        self.mu.bias.data.mul_(0.1)

        self.L = nn.Linear(hidden_size, num_outputs**2)
        self.L.weight.data.mul_(0.1)
        self.L.bias.data.mul_(0.1)

        self.tril_mask = Variable(
            torch.tril(torch.ones(num_outputs, num_outputs), diagonal=-1).unsqueeze(0)
        )
        self.diag_mask = Variable(
            torch.diag(torch.diag(torch.ones(num_outputs, num_outputs))).unsqueeze(0)
        )

    def forward(self, inputs):
        # LSTM implmentation

        x, u = inputs

        self.h0 = torch.zeros(2, x.size(1), self.hidden_lstm)
        self.c0 = torch.zeros(2, x.size(1), self.hidden_lstm)
        # lstm input 3D (samples,time steps,features)
        # in our case this would be (1,8,10)
        # or possibly (1,8,1) wiht 10 stacked LSTM using 3-D tensor
        x1, _ = self.lstm0(x[0, :, :, :], (self.h0, self.c0))
        x1 = x1[:, -1, :]
        x2, _ = self.lstm1(x[1, :, :, :], (self.h0, self.c0))
        x2 = x2[:, -1, :]
        x3, _ = self.lstm2(x[2, :, :, :], (self.h0, self.c0))
        x3 = x3[:, -1, :]
        x4, _ = self.lstm3(x[3, :, :, :], (self.h0, self.c0))
        x4 = x4[:, -1, :]
        x5, _ = self.lstm4(x[4, :, :, :], (self.h0, self.c0))
        x5 = x5[:, -1, :]
        x6, _ = self.lstm5(x[5, :, :, :], (self.h0, self.c0))
        x6 = x6[:, -1, :]
        x7, _ = self.lstm6(x[6, :, :, :], (self.h0, self.c0))
        x7 = x7[:, -1, :]
        x8, _ = self.lstm7(x[7, :, :, :], (self.h0, self.c0))
        x8 = x8[:, -1, :]
        x9, _ = self.lstm8(x[8, :, :, :], (self.h0, self.c0))
        x9 = x9[:, -1, :]
        x10, _ = self.lstm9(x[9, :, :, :], (self.h0, self.c0))
        x10 = x10[:, -1, :]

        x = torch.cat([x1, x2, x3, x4, x5, x6, x7, x8, x9, x10], dim=-1)

        # x = self.bn0(x)
        x = torch.relu(self.linear1(x))
        x = torch.relu(self.linear2(x))

        V = self.V(x)
        mu = torch.tanh(self.mu(x))  # ,dim=1)

        Q = None
        if u is not None:
            num_outputs = mu.size(1)
            L = self.L(x).view(-1, num_outputs, num_outputs)
            L = L * self.tril_mask.expand_as(L) + torch.exp(
                L
            ) * self.diag_mask.expand_as(L)
            P = torch.bmm(L, L.transpose(2, 1))
            u_mu = (u - mu).unsqueeze(2)
            A = -0.5 * torch.bmm(torch.bmm(u_mu.transpose(2, 1), P), u_mu)[:, :, 0]
            Q = A + V

        return mu, Q, V


class NAF_LSTM:
    def __init__(self, gamma, tau, hidden_size, num_inputs, action_space):
        self.action_space = action_space
        self.num_inputs = num_inputs

        self.model = Policy(hidden_size, num_inputs, action_space)
        self.target_model = Policy(hidden_size, num_inputs, action_space)
        self.optimizer = Adam(self.model.parameters(), lr=1e-3)

        self.gamma = gamma
        self.tau = tau

        hard_update(self.target_model, self.model)

    def select_action(self, state, exploration=None):
        self.model.eval()
        mu, _, _ = self.model((Variable(state), None))
        self.model.train()
        mu = mu.data
        if exploration is not None:
            mu += torch.Tensor(exploration.noise())

        return mu.clamp(-1, 1)

    def update_parameters(self, batch):
        state_batch = Variable(
            torch.cat(batch.state, dim=1)
        )  # torch.stack(batch.state).transpose(0,1))
        next_state_batch = Variable(torch.cat(batch.next_state, dim=1))
        action_batch = Variable(torch.cat(batch.action))
        reward_batch = Variable(torch.cat(batch.reward))
        mask_batch = Variable(torch.cat(batch.mask))

        _, _, next_state_values = self.target_model((next_state_batch, None))

        reward_batch = torch.unsqueeze(reward_batch, 1)
        mask_batch = mask_batch.unsqueeze(1)
        expected_state_action_values = reward_batch + (
            next_state_values * self.gamma * mask_batch
        )

        _, state_action_values, _ = self.model((state_batch, action_batch))

        loss = MSELoss(state_action_values, expected_state_action_values)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1)
        self.optimizer.step()

        soft_update(self.target_model, self.model, self.tau)

        return loss.item(), 0  # for plotting the loss
