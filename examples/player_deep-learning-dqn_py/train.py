#!/usr/bin/python3

# Author(s): Luiz Felipe Vecchietti, Kyujin Choi, Taeyoung Kim
# Maintainer: Kyujin Choi (nav3549@kaist.ac.kr)

import random
import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant, Game, Frame
except ImportError as err:
    print('player_random-walk: \'participant\' module cannot be imported:', err)
    raise

import math
import numpy as np

import helper
from dqn import DQN
from rl_utils import get_action, get_reward, get_state, Logger

#reset_reason
NONE = Game.NONE
GAME_START = Game.GAME_START
SCORE_MYTEAM = Game.SCORE_MYTEAM
SCORE_OPPONENT = Game.SCORE_OPPONENT
GAME_END = Game.GAME_END
DEADLOCK = Game.DEADLOCK
GOALKICK = Game.GOALKICK
CORNERKICK = Game.CORNERKICK
PENALTYKICK = Game.PENALTYKICK
HALFTIME = Game.HALFTIME
EPISODE_END = Game.EPISODE_END

#game_state
STATE_DEFAULT = Game.STATE_DEFAULT
STATE_KICKOFF = Game.STATE_KICKOFF
STATE_GOALKICK = Game.GOALKICK
STATE_CORNERKICK = Game.CORNERKICK
STATE_PENALTYKICK = Game.STATE_PENALTYKICK

#coordinates
MY_TEAM = Frame.MY_TEAM
OP_TEAM = Frame.OP_TEAM
BALL = Frame.BALL
X = Frame.X
Y = Frame.Y
Z = Frame.Z
TH = Frame.TH
ACTIVE = Frame.ACTIVE
TOUCH = Frame.TOUCH
BALL_POSSESSION = Frame.BALL_POSSESSION

#robot_index
GK_INDEX = 0 
D1_INDEX = 1 
D2_INDEX = 2 
F1_INDEX = 3 
F2_INDEX = 4

class Frame(object):
    def __init__(self):
        self.time = None
        self.score = None
        self.reset_reason = None
        self.game_state = None
        self.subimages = None
        self.coordinates = None
        self.half_passed = None

class Player(Participant):
    def init(self, info):
        self.field = info['field']
        self.max_linear_velocity = info['max_linear_velocity']
        self.goal = info['goal']
        self.number_of_robots = info['number_of_robots']
        self.end_of_frame = False
        self._frame = 0 
        self.speeds = [0 for _ in range(20)]
        self.cur_posture = []
        self.prev_posture = []
        self.cur_posture_opp = []
        self.cur_ball = []
        self.prev_ball = []
        self.set_default_formation()

        self.previous_frame = Frame()
        self.frame_skip = 2 # number of frames to skip
        self.obs_size = 3 # state size
        self.act_size = 7 # number of discrete actions

        # for RL
        self.number_of_agents = 1 # in this example, just F2 is trained
        self.action = 0
        self.previous_action = 0
        self.state = []
        self.previous_state = []
        self.reward = 0
        self.previous_reward = 0

        # RL algorithm class
        self.trainer = DQN(self.number_of_agents, self.obs_size, self.act_size)
        
        # log rewards
        self.total_reward = 0
        self.rew = np.zeros(4)
        # for logging rewards
        self.t = 0
        self.episode = 1
        self.plot_reward = Logger()
        self.save_png_interval = 10
        helper.printConsole("Initializing variables...")

    def get_coord(self, received_frame):
        self.cur_ball = received_frame.coordinates[BALL]
        self.cur_posture = received_frame.coordinates[MY_TEAM]
        self.cur_posture_opp = received_frame.coordinates[OP_TEAM]
        self.prev_posture = self.previous_frame.coordinates[MY_TEAM]
        self.prev_posture_opp = self.previous_frame.coordinates[OP_TEAM]
        self.prev_ball = self.previous_frame.coordinates[BALL]

    def update(self, received_frame):

        if received_frame.end_of_frame:
        
            self._frame += 1

            if (self._frame == 1):
                self.previous_frame = received_frame
                self.get_coord(received_frame)

            self.get_coord(received_frame)

            if self._frame % self.frame_skip == 1:
        
                # Get reward and state
                self.reward = get_reward(self.cur_posture, self.prev_posture, self.cur_ball, self.prev_ball, self.field, F2_INDEX)
                state = get_state(self.cur_posture, self.prev_posture, self.cur_posture_opp, self.prev_posture_opp, self.cur_ball, self.prev_ball, self.field, self.goal, self.max_linear_velocity) 

                # select next action / only training for F2 robot
                self.state = np.reshape([state[F2_INDEX]],(1, self.obs_size))
                self.action = self.trainer.select_action(self.state)
  
                self.total_reward += self.reward
                self.t += 1 

                # just store experiences if the F2 robot is active
                if self.cur_posture[F2_INDEX][ACTIVE]:
                    if self._frame == 1:
                        self.trainer.store_experience(self.state, self.state, self.previous_action, self.previous_reward)
                    else:
                        self.trainer.store_experience(self.previous_state, self.state, self.previous_action, self.previous_reward)

            else:
                self.action = self.previous_action

            # Set wheel speeds and send to the simulator
            self.speeds = get_action(F2_INDEX, self.action)
            self.set_speeds(self.speeds)

            # Training script: called every timestep  
            self.trainer.update()
                
            # save checkpoint
            self.trainer.save_checkpoint(self._frame)
            
            # logging training agent's reward and plot graph 
            if (received_frame.reset_reason > 1) :

                if self.t >= 10:
                    mean_total_reward = self.total_reward/(self.t)
                    self.plot_reward.update(self.episode, mean_total_reward, 5)
                    if self.episode % self.save_png_interval == 0:
                        self.plot_reward.plot('DQN-AGENT-REWARD') 
                    self.episode += 1
                # reset episode timesteps and total reward 
                self.t = 0
                self.total_reward = 0

            # save to update the replay buffer in the next state
            self.previous_state = self.state
            self.previous_action = self.action
            self.previous_reward = self.reward

            self.end_of_frame = False
            self.previous_frame = received_frame

if __name__ == '__main__':
    player = Player()
    player.run()