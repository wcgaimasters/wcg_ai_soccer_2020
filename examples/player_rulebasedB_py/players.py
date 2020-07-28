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

        # default desired position
        x_default = -self.field[X] / 2 + self.robot_size / 2 + 0.05
        y_default = max(min(cur_ball[Y], (self.goal[Y] / 2 - self.robot_size / 2)),
                -self.goal[Y] / 2 + self.robot_size / 2)

        # if the robot is inside the goal, try to get out
        if (cur_posture[id][X] < -self.field[X] / 2):
            if (cur_posture[id][Y] < 0):
                x = x_default
                y = cur_posture[id][Y] + 0.2
            else:
                x = x_default
                y = cur_posture[id][Y] - 0.2
        # if the goalkeeper is outside the penalty area
        elif (not helper.in_penalty_area(self, cur_posture[id], 0)):
            # return to the desired position
            x = x_default
            y = y_default
        # if the goalkeeper is inside the penalty area
        else:
            # if the ball is inside the penalty area
            if (helper.in_penalty_area(self, cur_ball, 0)):
                # if the ball is behind the goalkeeper
                if (cur_ball[X] < cur_posture[id][X]):
                    # if the ball is not blocking the goalkeeper's path
                    if (abs(cur_ball[Y] - cur_posture[id][Y]) > 2 * self.robot_size):
                        # try to get ahead of the ball
                        x = cur_ball[X] - self.robot_size
                        y = cur_posture[id][Y]
                    else:
                        # just give up and try not to make a suicidal goal
                        speeds[0], speeds[1] = helper.turn_angle(self, id, math.pi /2, cur_posture)
                        return speeds
                # if the ball is ahead of the goalkeeper
                else:
                    desired_th = helper.direction_angle(self, id, cur_ball[X], cur_ball[Y], cur_posture)
                    rad_diff = helper.wrap_to_pi(desired_th - cur_posture[id][TH])
                    # if the robot direction is too away from the ball direction
                    if (rad_diff > math.pi / 3):
                        # give up kicking the ball and block the goalpost
                        x = x_default
                        y = y_default
                    else:
                        # try to kick the ball away from the goal
                        x = cur_ball[X]
                        y = cur_ball[Y]
                        if cur_posture[id][BALL_POSSESSION]:
                            speeds[2] = 10
            # if the ball is not in the penalty area
            else:
                # if the ball is within alert range and y position is not too different
                if cur_ball[X] < -self.field[X] / 2 + 1.5 * self.penalty_area[X] and \
                   abs(cur_ball[Y]) < 1.5 * self.penalty_area[Y] / 2 and \
                   abs(cur_ball[Y] - cur_posture[id][Y]) < 0.2:
                    speeds[0], speeds[1] = helper.turn_to(self, id, cur_ball[X], cur_ball[Y], cur_posture)
                    return speeds
                # otherwise
                else:
                    x = x_default
                    y = y_default

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Defender:

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

        # if the robot is inside the goal, try to get out
        if (cur_posture[id][X] < -self.field[X] / 2):
            if (cur_posture[id][Y] < 0):
                x = -0.7 * self.field[X] / 2
                y = cur_posture[id][Y] + 0.2
            else:
                x = -0.7 * self.field[X] / 2
                y = cur_posture[id][Y] - 0.2
        # the defender may try to shoot if condition meets
        elif (id == idx_d and helper.shoot_chance(self, id, cur_posture, cur_ball) and cur_ball[X] < 0.3 * self.field[X] / 2):
            x = cur_ball[X]
            y = cur_ball[Y]
            if cur_posture[id][BALL_POSSESSION]:
                speeds[2] = 10
        # if this defender is closer to the ball than the other defender
        elif (id == idx_d):
            # ball is on our side
            if (cur_ball[X] < 0):
                # if the robot can push the ball toward opponent's side, do it
                if (cur_posture[id][X] < cur_ball[X] - 0.05):
                    x = cur_ball[X]
                    y = cur_ball[Y]
                    if cur_posture[id][BALL_POSSESSION]:
                        speeds[2] = 10
                else:
                    # otherwise go behind the ball
                    if (abs(cur_ball[Y] - cur_posture[id][Y]) > 0.3):
                        x = max(cur_ball[X] - 0.5, -self.field[X] / 2 + self.robot_size / 2)
                        y = cur_ball[Y]
                    else:
                        x = max(cur_ball[X] - 0.5, -self.field[X] / 2 + self.robot_size / 2)
                        y = cur_posture[id][Y]
            else:
                x = -0.7 * self.field[X] / 2
                y = cur_ball[Y]
        # if this defender is not closer to the ball than the other defender
        else:
            # ball is on our side
            if (cur_ball[X] < 0):
                # ball is on our left
                if (cur_ball[Y] > self.goal[Y] / 2 + 0.15):
                    x = max(cur_ball[X] - 0.5, -self.field[X] / 2 + self.robot_size / 2 + 0.1)
                    y = self.goal[Y] / 2 + 0.15
                # ball is on our right
                elif (cur_ball[Y] < -self.goal[Y] / 2 - 0.15):
                    x = max(cur_ball[X] - 0.5, -self.field[X] / 2 + self.robot_size / 2 + 0.1)
                    y = -self.goal[Y] / 2 - 0.15
                # ball is in center
                else:
                    x = max(cur_ball[X] - 0.5, -self.field[X] / 2 + self.robot_size / 2 + 0.1)
                    y = cur_ball[Y]
            else:
                # ball is on right side
                if (cur_ball[Y] < 0):
                    x = -0.7 * self.field[X] / 2
                    y = min(cur_ball[Y] + 0.5, self.field[Y] / 2 - self.robot_size / 2)
                # ball is on left side
                else:
                    x = -0.7 * self.field[X] / 2
                    y = max(cur_ball[Y] - 0.5, -self.field[Y] / 2 + self.robot_size / 2)

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds

class Forward:

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

        # if the ball is coming toward the robot, seek for shoot chance
        if (id == idx_a and helper.ball_coming_toward_robot(id, cur_posture, previous_ball, cur_ball)):
            dx = cur_ball[X] - previous_ball[X]
            dy = cur_ball[Y] - previous_ball[Y]
            pred_x = predicted_ball[X]
            steps = (cur_posture[id][Y] - cur_ball[Y]) / dy

            # if the ball will be located in front of the robot
            if (pred_x > cur_posture[id][X]):
                pred_dist = pred_x - cur_posture[id][X]
                # if the predicted ball location is close enough
                if (pred_dist > 0.1 and pred_dist < 0.3 and steps < 10):
                    # find the direction towards the opponent goal and look toward it
                    goal_angle = helper.direction_angle(self, id, self.field[X] / 2, 0, cur_posture)
                    speeds[0], speeds[1] = helper.turn_angle(self, id, goal_angle, cur_posture)
                    return speeds
        # if the robot is blocking the ball's path toward opponent side
        if cur_ball[X] > -0.3 * self.field[X] / 2 and \
           cur_ball[X] < 0.3 * self.field[X] / 2 and \
           cur_posture[id][X] > cur_ball[X] + 0.1 and \
           abs(cur_posture[id][Y] - cur_ball[Y]) < 0.3:
            if cur_ball[Y] < 0:
                x = cur_posture[id][X] - 0.25
                y = cur_ball[Y] + 0.75
            else:
                x = cur_posture[id][X] - 0.25
                y = cur_ball[Y] - 0.75
        # if the robot can shoot from current position
        elif (id == idx_a and helper.shoot_chance(self, id, cur_posture, cur_ball)):
            x = predicted_ball[X]
            y = predicted_ball[Y]
            if cur_posture[id][BALL_POSSESSION]:
                speeds[2] = 10
        # if this forward is closer to the ball than the other forward
        elif (id == idx_a):
            if (cur_ball[X] > -0.3 * self.field[X] / 2):
                # if the robot can push the ball toward opponent's side, do it
                if (cur_posture[id][X] < cur_ball[X] - 0.05):
                    x = cur_ball[X]
                    y = cur_ball[Y]
                    if cur_posture[id][BALL_POSSESSION]:
                        speeds[2] = 10
                else:
                    # otherwise go behind the ball
                    if (abs(cur_ball[Y] - cur_posture[id][Y]) > 0.3):
                        x = cur_ball[X] - 0.2
                        y = cur_ball[Y]
                    else:
                        x = cur_ball[X] - 0.2
                        y = cur_posture[id][Y]
            else:
                x = -0.1 * self.field[X] / 2
                y = cur_ball[Y]
        # if this forward is not closer to the ball than the other forward
        else:
            if (cur_ball[X] > -0.3 * self.field[X] / 2):
                # ball is on our right
                if (cur_ball[Y] < 0):
                    x = cur_ball[X] - 0.25
                    y = self.goal[Y] / 2
                # ball is on our left
                else:
                    x = cur_ball[X] - 0.25
                    y = -self.goal[Y] / 2
            else:
                # ball is on right side
                if (cur_ball[Y] < 0):
                    x = -0.1 * self.field[X] / 2
                    y = min(-cur_ball[Y] - 0.5, self.field[Y] / 2 - self.robot_size / 2)
                # ball is on left side
                else:
                    x = -0.1 * self.field[X] / 2
                    y = max(-cur_ball[Y] + 0.5, -self.field[Y] / 2 + self.robot_size / 2)

        speeds[0], speeds[1] = helper.go_to(self, id, x, y, cur_posture, cur_ball)
        return speeds