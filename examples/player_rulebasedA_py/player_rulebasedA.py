#!/usr/bin/python3


import random
import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant, Game, Frame
except ImportError as err:
    print('player_random-walk: \'participant\' module cannot be imported:', err)
    raise

import helper
from players import Goalkeeper, Defender_1, Defender_2, Forward_1, Forward_2

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

class TestPlayer(Participant):
    def init(self, info):
        self.field = info['field']
        self.max_linear_velocity = info['max_linear_velocity']
        self.robot_size = info['robot_size'][0]
        self.goal = info['goal']
        self.penalty_area = info['penalty_area']
        self.goal_area = info['goal_area']
        self.number_of_robots = info['number_of_robots']
        self.end_of_frame = False
        self._frame = 0 
        self.speeds = [0 for _ in range(20)]
        self.cur_posture = []
        self.cur_posture_opp = []
        self.cur_ball = []
        self.previous_ball = []
        self.predicted_ball = []
        self.previous_frame = Frame()
        self.gk_index = 0
        self.d1_index = 1
        self.d2_index = 2
        self.f1_index = 3
        self.f2_index = 4
        self.GK = Goalkeeper(self.field, self.goal, self.penalty_area, 
                                self.goal_area, self.robot_size,
                                self.max_linear_velocity[self.gk_index])
        self.D1 = Defender_1(self.field, self.goal, self.penalty_area, 
                                self.goal_area, self.robot_size,
                                self.max_linear_velocity[self.d1_index])
        self.D2 = Defender_2(self.field, self.goal, self.penalty_area, 
                                self.goal_area, self.robot_size,
                                self.max_linear_velocity[self.d2_index])
        self.F1 = Forward_1(self.field, self.goal, self.penalty_area, 
                                self.goal_area, self.robot_size,
                                self.max_linear_velocity[self.f1_index])
        self.F2 = Forward_2(self.field, self.goal, self.penalty_area,
                                self.goal_area, self.robot_size,
                                self.max_linear_velocity[self.f2_index])

        self.game_state = 0

                                #   X ,    Y ,    TH
        self.default_formation =[-3.80,  0.00, 1.57,     # GK
                                 -2.25,  1.00, 0.00,     # D1
                                 -2.25, -1.00, 0.00,     # D2
                                 -0.65,  0.30, 0.00,     # F1
                                 -0.65, -0.30, 0.00]     # F2

        self.set_default_formation(self.default_formation)

    def get_coord(self, received_frame):
        self.cur_ball = received_frame.coordinates[BALL]
        self.cur_posture = received_frame.coordinates[MY_TEAM]
        self.cur_posture_opp = received_frame.coordinates[OP_TEAM]
        self.game_state = received_frame.game_state

    def update(self, received_frame):

        if received_frame.end_of_frame:
	    
            self._frame += 1

            if (self._frame == 1):
                self.previous_frame = received_frame
                self.get_coord(received_frame)
                self.previous_ball = self.cur_ball

            self.get_coord(received_frame)
            self.predicted_ball = helper.predict_ball(self.cur_ball, self.previous_ball, 2)
            self.idx_d = helper.find_closest_robot(self.cur_ball, self.cur_posture, [1,2])
            self.idx_a = helper.find_closest_robot(self.cur_ball, self.cur_posture_opp, [3,4])

            #(update the robots wheels)
            # Robot Functions
            self.speeds[4 * self.gk_index : 4 * self.gk_index + 4] = self.GK.move(self.gk_index, 
                                                                                self.idx_d, self.idx_a, 
                                                                                self.cur_posture, self.cur_posture_opp,
                                                                                self.previous_ball, self.cur_ball, self.predicted_ball)
            self.speeds[4 * self.d1_index : 4 * self.d1_index + 4] = self.D1.move(self.d1_index, 
                                                                                self.idx_d, self.idx_a,
                                                                                self.cur_posture, self.cur_posture_opp,
                                                                                self.previous_ball, self.cur_ball, self.predicted_ball)
            self.speeds[4 * self.d2_index : 4 * self.d2_index + 4] = self.D2.move(self.d2_index, 
                                                                                self.idx_d, self.idx_a,
                                                                                self.cur_posture, self.cur_posture_opp,
                                                                                self.previous_ball, self.cur_ball, self.predicted_ball)
            self.speeds[4 * self.f1_index : 4 * self.f1_index + 4] = self.F1.move(self.f1_index, 
                                                                                self.idx_d, self.idx_a,
                                                                                self.cur_posture, self.cur_posture_opp,
                                                                                self.previous_ball, self.cur_ball, self.predicted_ball)
            self.speeds[4 * self.f2_index : 4 * self.f2_index + 4] = self.F2.move(self.f2_index, 
                                                                                self.idx_d, self.idx_a,
                                                                                self.cur_posture, self.cur_posture_opp,
                                                                                self.previous_ball, self.cur_ball, self.predicted_ball)

            self.set_speeds(self.speeds)

            self.previous_frame = received_frame
            self.previous_ball = self.cur_ball
            self.end_of_frame = False

if __name__ == '__main__':
    player = TestPlayer()
    player.run()