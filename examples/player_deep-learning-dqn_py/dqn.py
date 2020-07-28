#!/usr/bin/python3

# Author(s): Luiz Felipe Vecchietti, Kyujin Choi, Taeyoung Kim
# Maintainer: Kyujin Choi (nav3549@kaist.ac.kr)

from networks import Agent
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from copy import deepcopy
import numpy as np

import helper
import os
from episode_memory import Memory
import random

CHECKPOINT= os.path.join(os.path.dirname(__file__), 'models/policy.pt')

def update_target_model(net, target_net):
    target_net.load_state_dict(net.state_dict())

class DQN:
    def __init__(self, n_agents, dim_obs, dim_act, load=False, play=False):
        self.n_agents = n_agents
        self._iterations = 0
        self.update_steps = 100 # Update Target Network
        self.epsilon_steps = 20000 # Decrease epsilon
        self.play = play
        if self.play == True:
            self.epsilon = 0 # Greedy choice if play is True
        else:
            self.epsilon = 0.95 # Initial epsilon value      
        self.final_epsilon = 0.05 # Final epsilon value
        self.dec_epsilon =  0.025 # Decrease rate of epsilon for every generation

        self.observation_steps = 300 # Number of iterations to observe before training every generation
        self.save_num = 10000 # Save checkpoint # default: 100
        self.batch_size = 64
        self.discount_factor = 0.99

        self.num_inputs = dim_obs
        self.act_size = dim_act
        self.memory = Memory(50000) # replay buffer
        self.net = Agent(self.num_inputs, self.act_size)
        self.target_net = Agent(self.num_inputs, self.act_size)
        self.load = load
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.load == True:
            self.net.load_state_dict(torch.load(CHECKPOINT, map_location=torch.device(self.device)))
            helper.printConsole("loading variables...")
        
        update_target_model(self.net, self.target_net)
        self.net.train()
        self.target_net.train()
        self.net.to(self.device)
        self.target_net.to(self.device)
        self.gamma = 0.99
        self.grad_norm_clip = 10
        self.loss = 0
        self.lr = 0.0001
        self.optimizer = optim.Adam(self.net.parameters(), lr=self.lr)    

    def select_action(self, state):

        state = torch.Tensor(state).to(self.device)
        
        qvalue = self.net(state)
        qvalue = qvalue.cpu().data.numpy()
        
        pick_random = int(np.random.rand() <= self.epsilon)
        random_actions = random.randrange(self.act_size)
        picked_actions = pick_random * random_actions + (1 - pick_random) * np.argmax(qvalue)
        return picked_actions

    def store_experience(self, state, next_state, act, rew):
        # Store transition in the replay buffer.
        self.memory.push(state, next_state, act, rew)

    def update_policy(self):

        batch = self.memory.sample(self.batch_size)

        states = torch.Tensor(batch.state).to(self.device)
        next_states = torch.Tensor(batch.next_state).to(self.device)
        actions = torch.Tensor(batch.action).long().to(self.device)
        rewards = torch.Tensor(batch.reward).to(self.device)

        q_values = self.net(states).squeeze(1)
        max_next_q_values = self.target_net(next_states).squeeze(1).max(1)[0]

        one_hot_action = torch.zeros(self.batch_size, q_values.size(-1)).to(self.device)
        one_hot_action.scatter_(1, actions.unsqueeze(1), 1)
        chosen_q_values = torch.sum(q_values.mul(one_hot_action), dim=1)

        target = rewards + self.discount_factor * max_next_q_values

        td_error = (chosen_q_values - target.detach())
        loss = (td_error ** 2).sum() 
        self.loss = loss.cpu().data.numpy()
        
        self.optimizer.zero_grad()
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(self.net.parameters(), self.grad_norm_clip)
        self.optimizer.step()
        
        if self._iterations  % self.update_steps == 0: 
            update_target_model(self.net, self.target_net)
            helper.printConsole("Updated target model.")

        if self._iterations  % self.epsilon_steps == 0: 
            self.epsilon = max(self.epsilon - self.dec_epsilon, self.final_epsilon)
            helper.printConsole("New Episode! New Epsilon:" + str(self.epsilon))

        return self.loss        

    def save_checkpoint(self, iteration):
        if iteration % self.save_num ==0:
            self.net.save_model(self.net, CHECKPOINT)
            helper.printConsole("Saved Checkpoint.")

    def print_loss(self, loss, iteration):
        if self._iterations % 100 == 0: # Print information every 100 iterations
            helper.printConsole("======================================================")
            helper.printConsole("Epsilon: " + str(self.epsilon))
            helper.printConsole("iterations: " + str(self._iterations))
            helper.printConsole("Loss: " + str(loss))
            helper.printConsole("======================================================")

    def update(self):
        if len(self.memory) > self.observation_steps:
            self._iterations += 1
            loss = self.update_policy()
            self.print_loss(loss, self._iterations)  