import math
import numpy

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

class Goalkeeper:

    def __init__(self, field, goal, penalty_area, goal_area, robot_size, max_linear_velocity):
        self.field = field
        self.goal = goal
        self.penalty_area = penalty_area
        self.goal_area = goal_area
        self.robot_size = robot_size
        self.max_linear_velocity = max_linear_velocity

    def move(self, id, idx_d, idx_a, cur_posture, cur_posture_opp, previous_ball, cur_ball, predicted_ball):
        # speed list: left wheel, right wheel, front slider, bottom slider
        speeds = [0,0,0,0]

        ball_dist = helper.distance(cur_posture[id][X], cur_ball[X],
                                    cur_posture[id][Y], cur_ball[Y])
        min_x = -self.field[X]/2                        # = -3.9
        max_x = -self.field[X]/2 + self.penalty_area[X] # = -3
        min_y = -self.goal_area[Y]/2                    # = -0.5
        max_y = self.goal_area[Y]/2                     # = 0.5

        if helper.ball_is_own_goal(predicted_ball, self.field, self.goal_area):
            x = cur_ball[X]
            y = cur_ball[Y]
        elif helper.ball_is_own_penalty(predicted_ball, self.field, self.penalty_area):
            x = min_x
            y = max_y
        elif helper.ball_is_own_field(predicted_ball):
            x = -3
            y = 0
        elif helper.ball_is_opp_goal(predicted_ball, self.field, self.goal_area):
            x = cur_posture[1][X]
            y = cur_posture[1][Y]
        elif helper.ball_is_opp_penalty(predicted_ball, self.field, self.penalty_area):
            x = cur_posture_opp[4][X]
            y = cur_posture_opp[4][Y]
        else: # ball is opp field
            x = max_x
            y = max_y

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Defender_1:

    def __init__(self, field, goal, penalty_area, goal_area, robot_size, max_linear_velocity):
        self.field = field
        self.goal = goal
        self.penalty_area = penalty_area
        self.goal_area = goal_area
        self.robot_size = robot_size
        self.max_linear_velocity = max_linear_velocity

    def move(self, id, idx_d, idx_a, cur_posture, cur_posture_opp, previous_ball, cur_ball, predicted_ball):
        speeds = [0,0,0,0]

        ball_dist = helper.distance(cur_posture[id][X], cur_ball[X],
                                    cur_posture[id][Y], cur_ball[Y])
        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0

        if helper.ball_is_own_goal(predicted_ball, self.field, self.goal_area):
            x = -1.5
            y = 1.5
        elif helper.ball_is_own_penalty(predicted_ball, self.field, self.penalty_area):
            x = 1.5
            y = 1.5
        elif helper.ball_is_own_field(predicted_ball):
            x = 1.5
            y = -1.5
        elif helper.ball_is_opp_goal(predicted_ball, self.field, self.goal_area):
            x = 1.5
            y = 0
        elif helper.ball_is_opp_penalty(predicted_ball, self.field, self.penalty_area):
            x = 0
            y = 1.5
        else: # ball is opp field
            x = 0
            y = 0

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Defender_2:

    def __init__(self, field, goal, penalty_area, goal_area, robot_size, max_linear_velocity):
        self.field = field
        self.goal = goal
        self.penalty_area = penalty_area
        self.goal_area = goal_area
        self.robot_size = robot_size
        self.max_linear_velocity = max_linear_velocity

    def move(self, id, idx_d, idx_a, cur_posture, cur_posture_opp, previous_ball, cur_ball, predicted_ball):
        speeds = [0,0,0,0]

        ball_dist = helper.distance(cur_posture[id][X], cur_ball[X],
                                    cur_posture[id][Y], cur_ball[Y])
        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0

        if helper.ball_is_own_goal(predicted_ball, self.field, self.goal_area):
            x = -1.5
            y = -1.5
            speeds[2] = 0
        elif helper.ball_is_own_penalty(predicted_ball, self.field, self.penalty_area):
            x = -1.5
            y = -1.5
            speeds[2] = 2
        elif helper.ball_is_own_field(predicted_ball):
            x = -1.5
            y = -1.5
            speeds[2] = 4
        elif helper.ball_is_opp_goal(predicted_ball, self.field, self.goal_area):
            x = -1.5
            y = -1.5
            speeds[2] = 6
        elif helper.ball_is_opp_penalty(predicted_ball, self.field, self.penalty_area):
            x = -1.5
            y = -1.5
            speeds[2] = 8
        else: # ball is opp field
            x = -1.5
            y = -1.5
            speeds[2] = 10

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Forward_1:

    def __init__(self, field, goal, penalty_area, goal_area, robot_size, max_linear_velocity):
        self.field = field
        self.goal = goal
        self.penalty_area = penalty_area
        self.goal_area = goal_area
        self.robot_size = robot_size
        self.max_linear_velocity = max_linear_velocity
        
    def move(self, id, idx_d, idx_a, cur_posture, cur_posture_opp, previous_ball, cur_ball, predicted_ball):
        speeds = [0,0,0,0]

        ball_dist = helper.distance(cur_posture[id][X], cur_ball[X],
                                    cur_posture[id][Y], cur_ball[Y])
        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0

        if helper.ball_is_own_goal(predicted_ball, self.field, self.goal_area):
            x = -0.5
            y = 1
            speeds[3] = 0
        elif helper.ball_is_own_penalty(predicted_ball, self.field, self.penalty_area):
            x = -0.5
            y = 1
            speeds[3] = 2
        elif helper.ball_is_own_field(predicted_ball):
            x = -0.5
            y = 1
            speeds[3] = 4
        elif helper.ball_is_opp_goal(predicted_ball, self.field, self.goal_area):
            x = -0.5
            y = 1
            speeds[3] = 6
        elif helper.ball_is_opp_penalty(predicted_ball, self.field, self.penalty_area):
            x = -0.5
            y = 1
            speeds[3] = 8
        else: # ball is opp field
            x = -0.5
            y = 1
            speeds[3] = 10

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Forward_2:

    def __init__(self, field, goal, penalty_area, goal_area, robot_size, max_linear_velocity):
        self.field = field
        self.goal = goal
        self.penalty_area = penalty_area
        self.goal_area = goal_area
        self.robot_size = robot_size
        self.max_linear_velocity = max_linear_velocity
        
    def move(self, id, idx_d, idx_a, cur_posture, cur_posture_opp, previous_ball, cur_ball, predicted_ball):
        speeds = [0,0,0,0]

        ball_dist = helper.distance(cur_posture[id][X], cur_ball[X],
                                    cur_posture[id][Y], cur_ball[Y])
        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0

        if helper.ball_is_own_goal(predicted_ball, self.field, self.goal_area):
            x = -0.5
            y = -1
        elif helper.ball_is_own_penalty(predicted_ball, self.field, self.penalty_area):
            x = -0.5
            y = -1
        elif helper.ball_is_own_field(predicted_ball):
            x = -0.5
            y = -1
        elif helper.ball_is_opp_goal(predicted_ball, self.field, self.goal_area):
            x = -0.5
            y = -1
        elif helper.ball_is_opp_penalty(predicted_ball, self.field, self.penalty_area):
            x = -0.5
            y = -1
        else: # ball is opp field
            x = -0.5
            y = -1

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds
