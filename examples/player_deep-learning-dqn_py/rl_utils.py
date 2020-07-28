#!/usr/bin/python3

# Author(s): Luiz Felipe Vecchietti, Kyujin Choi, Taeyoung Kim
# Maintainer: Kyujin Choi (nav3549@kaist.ac.kr)

import os
import sys

import math
import numpy as np
import torch
import matplotlib.pyplot as plt
from torch.autograd import Variable

import helper

#reset_reason
NONE = 0
GAME_START = 1
SCORE_MYTEAM = 2
SCORE_OPPONENT = 3
GAME_END = 4
DEADLOCK = 5
GOALKICK = 6
CORNERKICK = 7
PENALTYKICK = 8
HALFTIME = 9
EPISODE_END = 10

#game_state
STATE_DEFAULT = 0
STATE_BACKPASS = 1
STATE_GOALKICK = 2
STATE_CORNERKICK = 3
STATE_PENALTYKICK = 4

#coordinates
MY_TEAM = 0
OP_TEAM = 1
BALL = 2
X = 0
Y = 1
Z = 2
TH = 3
ACTIVE = 4
TOUCH = 5
BALL_POSSESSION = 6

#robot_index
GK_INDEX = 0
D1_INDEX = 1
D2_INDEX = 2
F1_INDEX = 3
F2_INDEX = 4

USE_CUDA = torch.cuda.is_available()
FLOAT = torch.cuda.FloatTensor if USE_CUDA else torch.FloatTensor
LONG = torch.cuda.LongTensor if USE_CUDA else torch.LongTensor

def predict_ball_velocity(cur_ball, prev_ball, ts):
    vx = (cur_ball[X] - prev_ball[X])/ts
    vy = (cur_ball[Y] - prev_ball[Y])/ts
    vd = math.atan2(vy, vx)
    vr = math.sqrt(math.pow(vx, 2) + math.pow(vy, 2))
    return [vd*180/math.pi, vr]

def predict_robot_velocity(cur_posture, prev_posture, index, ts):
    vx = (cur_posture[index][X] - prev_posture[index][X])/ts
    vy = (cur_posture[index][Y] - prev_posture[index][Y])/ts
    vd = math.atan2(vy, vx)
    vr = math.sqrt(math.pow(vx, 2) + math.pow(vy, 2))
    return [vd*180/math.pi, vr]

def get_state(cur_posture, prev_posture, cur_posture_opp, prev_posture_opp, cur_ball, prev_ball, field, goal, max_linear_velocity):
    # state: relative position to the ball and robot orientation
    states = [[] for _ in range(5)]
    pxx = field[X] + goal[X]
    pyy = field[Y] + goal[Y]
    for i in range(5):
        states[i] =[round((cur_ball[X] - cur_posture[i][X] )/pxx, 2), round((cur_ball[Y] - cur_posture[i][Y] )/pyy, 2),  round(cur_posture[i][TH], 2)]

    return states

def get_reward(cur_posture, prev_posture, cur_ball, prev_ball, field, id):
    dist_robot2ball = helper.distance(cur_posture[id][X] , cur_ball[X], cur_posture[id][Y], cur_ball[Y])

    return -(1-math.exp(-1*dist_robot2ball))

def get_action(robot_id, action_number):
    # 7 actions: kick, jump, go forwards, go backwards, rotate right, rotate left, stop

    SPEEDS = [[ 1.5,  1.5, 10.0,  0.0],
              [ 1.5,  1.5,  0.0, 10.0],
              [ 1.5,  1.5,  0.0,  0.0],
              [-1.5, -1.5,  0.0,  0.0],
              [ 0.0,  0.0,  0.0,  0.0],
              [ 1.0, -1.0,  0.0,  0.0],
              [-1.0,  1.0,  0.0,  0.0]]


    speeds = [0 for _ in range(20)]

    speeds[4*robot_id + 0] = SPEEDS[action_number][0]
    speeds[4*robot_id + 1] = SPEEDS[action_number][1]
    speeds[4*robot_id + 2] = SPEEDS[action_number][2]
    speeds[4*robot_id + 3] = SPEEDS[action_number][3]

    return speeds

class Logger():
    def __init__(self):

        self.episode = []
        self.m_episode = []
        self.value = []
        self.mean_value = []

    def update(self, episode, value, num):

        self.episode.append(episode)
        self.value.append(value)
        self.num = num
        if len(self.value) >= self.num :
            self.m_episode.append(episode - self.num/2)
            self.mean_value.append(np.mean(self.value[-self.num:]))

    def plot(self, name):
        plt.title(str(name))
        plt.plot(self.episode, self.value, c = 'lightskyblue', label='total_reward') 
        plt.plot(self.m_episode, self.mean_value, c = 'b', label='Average_Total_Reward') 
        if len(self.episode) <= 10:
            plt.legend(loc=1)
        png_path = os.path.dirname(os.path.realpath(__file__)) + '/TOTAL_'+str(name)+'.png'
        plt.savefig(png_path)