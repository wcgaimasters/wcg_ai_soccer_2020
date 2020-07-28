import math

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

def degree2radian(deg):
    return deg * math.pi / 180

def radian2degree(rad):
    return rad * 180 / math.pi

def wrap_to_pi(theta):
    while (theta > math.pi):
        theta -= 2 * math.pi
    while (theta < -math.pi):
        theta += 2 * math.pi
    return theta

def distance(x1, x2, y1, y2):
    return math.sqrt(math.pow(x1 - x2, 2) + math.pow(y1 - y2, 2))

def predict_ball(cur_ball, previous_ball, prediction_step):
    dx = cur_ball[X] - previous_ball[X]
    dy = cur_ball[Y] - previous_ball[Y]
    predicted_ball = [cur_ball[X] + prediction_step*dx, cur_ball[Y] + prediction_step*dy]
    return predicted_ball

def find_closest_robot(cur_ball, cur_posture, robot_list):
    min_idx = 0
    min_dist = 9999.99

    all_dist = []

    for i in robot_list:
        measured_dist = distance(cur_ball[X], cur_posture[i][X],
                                    cur_ball[Y], cur_posture[i][Y])
        all_dist.append(measured_dist)
        if (measured_dist < min_dist):
            min_dist = measured_dist
            min_idx = i

    idx = min_idx
    return idx

def shoot_chance(self, id, cur_posture, ball):
    d2b = distance(ball[X], cur_posture[id][X],
                                ball[Y],cur_posture[id][Y])
    dx = ball[X] - cur_posture[id][X]
    dy = ball[Y] - cur_posture[id][Y]

    gy = self.goal_area[Y]

    if (dx < 0) or (d2b > self.field[Y]/2):
        return False

    y = (self.field[X]/2 - ball[X])*dy/dx + cur_posture[id][Y]

    if (abs(y) < gy/2):
        return True
    elif (ball[X] < 2.5) and (self.field[Y] - gy/2 < abs(y) < self.field[Y] + gy/2):
        return True
    else:
        return False

def set_wheel_velocity(max_linear_velocity, left_wheel, right_wheel):
    ratio_l = 1
    ratio_r = 1

    if (left_wheel > max_linear_velocity or right_wheel > max_linear_velocity):
        diff = max(left_wheel, right_wheel) - max_linear_velocity
        left_wheel -= diff
        right_wheel -= diff
    if (left_wheel < -max_linear_velocity or right_wheel < -max_linear_velocity):
        diff = min(left_wheel, right_wheel) + max_linear_velocity
        left_wheel -= diff
        right_wheel -= diff

    return left_wheel, right_wheel
    
def in_penalty_area(self, obj, team):
    # team 0 : own, 1 : opp
    if (abs(obj[Y]) > self.penalty_area[Y] / 2):
        return False

    if (team == 0):
        return (obj[X] < -self.field[X] / 2 + self.penalty_area[X])
    else:
        return (obj[X] > self.field[X] / 2 - self.penalty_area[X])

def ball_is_own_goal(predicted_ball, field, goal_area):
    return (-field[X]/2 <= predicted_ball[X] <= -field[X]/2 + goal_area[X] and
            -goal_area[Y]/2 <= predicted_ball[Y] <= goal_area[Y]/2)

def ball_is_own_penalty(predicted_ball, field, penalty_area):
    return (-field[X]/2 <= predicted_ball[X] <= -field[X]/2 + penalty_area[X] and
        -penalty_area[Y]/2 <= predicted_ball[Y] <=  penalty_area[Y]/2)

def ball_is_own_field(predicted_ball):
    return (predicted_ball[X] <= 0)

def ball_is_opp_goal(predicted_ball, field, goal_area):
    return (field[X]/2  - goal_area[X] <= predicted_ball[X] <= field[X]/2 and
            -goal_area[Y]/2 <= predicted_ball[Y] <= goal_area[Y]/2)

def ball_is_opp_penalty(predicted_ball, field, penalty_area):
    return (field[X]/2  - penalty_area[X] <= predicted_ball[X] <= field[X]/2 and
            -penalty_area[Y]/2 <= predicted_ball[Y] <= penalty_area[Y]/2)

def ball_is_opp_field(predicted_ball):
    return (predicted_ball[X] > 0)


def direction_angle(self, id, x, y, cur_posture):
    dx = x - cur_posture[id][X]
    dy = y - cur_posture[id][Y]

    return ((math.pi / 2) if (dx == 0 and dy == 0) else math.atan2(dy, dx))

def ball_coming_toward_robot(id, cur_posture, prev_ball, cur_ball):
    x_dir = abs(cur_posture[id][X] - prev_ball[X]) \
        > abs(cur_posture[id][X] - cur_ball[X])
    y_dir = abs(cur_posture[id][Y] - prev_ball[Y]) \
        > abs(cur_posture[id][Y] - cur_ball[Y])

    # ball is coming closer
    if (x_dir and y_dir):
        return True
    else:
        return False

def go_to(self, id, x, y, cur_posture, cur_ball):
    scale, mult_lin, mult_ang, max_velocity = 1.4, 3.5, 0.4, False
    damping = 0.35
    ka = 0
    sign = 1
    # calculate how far the target position is from the robot
    dx = x - cur_posture[id][X]
    dy = y - cur_posture[id][Y]
    d_e = math.sqrt(math.pow(dx, 2) + math.pow(dy, 2))
    # calculate how much the direction is off
    desired_th = (math.pi / 2) if (dx == 0 and dy == 0) else math.atan2(dy, dx)
    d_th = desired_th - cur_posture[id][TH]
    while (d_th > math.pi):
        d_th -= 2 * math.pi
    while (d_th < -math.pi):
        d_th += 2 * math.pi

    # based on how far the target position is, set a parameter that
    # decides how much importance should be put into changing directions
    # farther the target is, less need to change directions fastly
    if (d_e > 1):
        ka = 17 / 90
    elif (d_e > 0.5):
        ka = 19 / 90
    elif (d_e > 0.3):
        ka = 21 / 90
    elif (d_e > 0.2):
        ka = 23 / 90
    else:
        ka = 25 / 90

    # if the target position is at rear of the robot, drive backward instead
    if (d_th > degree2radian(95)):
        d_th -= math.pi
        sign = -1
    elif (d_th < degree2radian(-95)):
        d_th += math.pi
        sign = -1

    # if the direction is off by more than 85 degrees,
    # make a turn first instead of start moving toward the target
    if (abs(d_th) > degree2radian(85)):
        left_wheel, right_wheel = set_wheel_velocity(self.max_linear_velocity, -mult_ang * d_th, mult_ang * d_th)
    # otherwise
    else:
        # scale the angular velocity further down if the direction is off by less than 40 degrees
        if (d_e < 5 and abs(d_th) < degree2radian(40)):
            ka = 0.1
        ka *= 4
        # set the wheel velocity
        # 'sign' determines the direction [forward, backward]
        # 'scale' scales the overall velocity at which the robot is driving
        # 'mult_lin' scales the linear velocity at which the robot is driving
        # larger distance 'd_e' scales the base linear velocity higher
        # 'damping' slows the linear velocity down
        # 'mult_ang' and 'ka' scales the angular velocity at which the robot is driving
        # larger angular difference 'd_th' scales the base angular velocity higher
        # if 'max_velocity' is true, the overall velocity is scaled to the point
        # where at least one wheel is operating at maximum velocity
        left_wheel, right_wheel = set_wheel_velocity(self.max_linear_velocity,
                                sign * scale * (mult_lin * (
                                            1 / (1 + math.exp(-3 * d_e)) - damping) - mult_ang * ka * d_th),
                                sign * scale * (mult_lin * (
                                            1 / (1 + math.exp(-3 * d_e)) - damping) + mult_ang * ka * d_th))
    return left_wheel, right_wheel

def turn_to(self, id, x, y, cur_posture):
    ka = 0.5
    tot = math.pi/360

    dx = x - cur_posture[id][X]
    dy = y - cur_posture[id][Y]
    desired_th = math.atan2(dy, dx)
    d_th = wrap_to_pi(desired_th - cur_posture[id][TH])

    if (d_th > degree2radian(90)):
        d_th -= math.pi
    elif (d_th < degree2radian(-90)):
        d_th += math.pi
    
    if (abs(d_th) < tot):
        ka = 0
    
    left_wheel, right_wheel = set_wheel_velocity(self.max_linear_velocity,
                                                                   -ka*d_th,
                                                                   ka*d_th)

    return left_wheel, right_wheel

def turn_angle(self, id, angle, cur_posture):
    ka = 0.5
    tot = math.pi/360

    desired_th = angle
    d_th = wrap_to_pi(desired_th - cur_posture[id][TH])

    if (d_th > degree2radian(90)):
        d_th -= math.pi
    elif (d_th < degree2radian(-90)):
        d_th += math.pi
    
    if (abs(d_th) < tot):
        ka = 0
    
    left_wheel, right_wheel = set_wheel_velocity(self.max_linear_velocity,
                                                                -ka*d_th, ka*d_th)
    
    return left_wheel, right_wheel