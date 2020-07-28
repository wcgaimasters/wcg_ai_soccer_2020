#!/usr/bin/env python3

import errno
import json
import math
import os
import random
import select
import socket
import string
import subprocess
import sys
import time
import collections

from controller import Supervisor, Speaker, Keyboard

from player import Game
from image_frame_buffer import ImageFrameBuffer

import constants


def random_string(length):
    """Generate a random string with the combination of lowercase and uppercase letters."""
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(length))


def get_key(rpc):
    """The key is the first argument of the RPC."""
    first = rpc.find('"') + 1
    return rpc[first:rpc.find('"', first)]


def get_robot_name(color, id):
    name = constants.DEF_ROBOT_PREFIX
    if color == constants.TEAM_RED:
        name += 'R'
    elif color == constants.TEAM_BLUE:
        name += 'B'
    else:
        sys.stderr.write("Error: get_robot_name: Invalid team color.\n")
    name += str(id)
    return name


def get_role_name(role):
    if role == constants.TEAM_RED:
        return 'team red'
    if role == constants.TEAM_BLUE:
        return 'team blue'
    sys.stderr.write("Error: get_role_name: Invalid role.\n")
    return ''


class TcpServer:
    def __init__(self, host, port):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setblocking(False)
        self.server.bind((host, port))
        self.server.listen(5)
        self.connections = [self.server]
        self.unprocessedData = {}
        self.unprocessedData[self.server.fileno()] = ''

    def send_to_all(self, message):  # send message to all clients
        for client in self.connections:
            if client == self.server:
                continue
            self.send(client, message)

    def send(self, client, message):  # send message to a single client
        if client.fileno() == -1:  # was closed
            return
        try:
            client.sendall(message.encode())
        except ConnectionAbortedError:
            self.connections.remove(client)

    def spin(self, game_supervisor):  # handle asynchronous requests from clients
        def cleanup(s):
            print('Cleanup')
            if s in self.connections:
                self.connections.remove(s)
            s.close()
        while True:
            readable, writable, exceptional = select.select(self.connections, [], self.connections, 0)
            if not readable and not writable and not exceptional:
                return
            for s in readable:
                if s is self.server:
                    connection, client_address = s.accept()
                    connection.setblocking(False)
                    self.connections.append(connection)
                    self.unprocessedData[connection.fileno()] = ''
                    print('Accepted ', client_address)
                else:
                    success = True
                    data = ''
                    try:
                        while True:
                            d = s.recv(4096)
                            if not d:
                                break
                            data += d.decode()
                    except socket.error as e:
                        if e.args[0] == errno.EWOULDBLOCK:
                            success = True
                        else:
                            if e.args[0] != 10053:  # WSAECONNABORTED
                                print('Error caught: ', e.args[0])
                            success = False
                    if data and success:
                        self.unprocessedData[s.fileno()] = \
                            game_supervisor.callback(s, self.unprocessedData[s.fileno()] + data)
                    else:
                        print('Closing')
                        cleanup(s)
            for s in exceptional:
                print('Exceptional')
                cleanup(s)


class GameSupervisor(Supervisor):
    def __init__(self):
        Supervisor.__init__(self)
        self.basicTimeStep = int(self.getBasicTimeStep())
        self.timeStep = constants.PERIOD_MS
        self.waitReady = 0
        self.report = None

        self.A_default_formation = [[-3.8,   0.0, math.pi / 2], [-2.25,  1.0, 0], [-2.25, -1.0, 0], [-0.65,  0.3, 0], [-0.65, -0.3, 0]]
        self.B_default_formation = [[-3.8,   0.0, math.pi / 2], [-2.25,  1.0, 0], [-2.25, -1.0, 0], [-0.65,  0.3, 0], [-0.65, -0.3, 0]]
        self.default_formation = [self.A_default_formation,self.B_default_formation]

        self.speeds_buffer = [[0 for _ in range(20)],[0 for _ in range(20)]]
        
        # slider
        self.fslider_count = [[0,0,0,0,0],[0,0,0,0,0]]
        self.fslider_trig = [[0,0,0,0,0],[0,0,0,0,0]]
        self.bslider_count = [[0,0,0,0,0],[0,0,0,0,0]]
        self.bslider_trig = [[0,0,0,0,0],[0,0,0,0,0]]
        self.t_brl = [[0,0,0,0,0],[0,0,0,0,0]]

        # speaker
        self.spk = self.getSpeaker("speaker")
        # ball_possession
        self.ball_possession = [[False] * constants.NUMBER_OF_ROBOTS, [False] * constants.NUMBER_OF_ROBOTS]
        # keyboard
        self.keyboard_control = [False, False]
        # view
        self.view = 0
        self.view_key = self.getKeyboard()
        Keyboard.enable(self.view_key, self.basicTimeStep)

        self.receiver = self.getReceiver(constants.NAME_RECV)
        self.receiver.enable(constants.RECV_PERIOD_MS)

        self.cameraA = self.getCamera(constants.NAME_CAMA)
        self.cameraA.enable(constants.CAM_PERIOD_MS)
        self.cameraB = self.getCamera(constants.NAME_CAMB)
        self.cameraB.enable(constants.CAM_PERIOD_MS)
        self.imageFrameBufferA = ImageFrameBuffer(self.cameraA, constants.SUBIMAGE_NX, constants.SUBIMAGE_NY)
        self.imageFrameBufferB = ImageFrameBuffer(self.cameraB, constants.SUBIMAGE_NX, constants.SUBIMAGE_NY)

        self.cameraANode = self.getFromDef(constants.DEF_CAMA)
        self.cameraBNode = self.getFromDef(constants.DEF_CAMB)
        self.viewpointNode = self.getFromDef(constants.DEF_AUDVIEW)
        # DEF_GRASS is not visible to cam a and cam b, optional
        grass = self.getFromDef(constants.DEF_GRASS)
        grass.setVisibility(self.cameraANode, False)
        grass.setVisibility(self.cameraBNode, False)
        # BALLSHAPE is visible only to viewpoint, ORANGESHAPE is to cam_a and cam_b, mandatory
        ball = self.getFromDef(constants.DEF_BALLSHAPE)
        orange = self.getFromDef(constants.DEF_ORANGESHAPE)
        ball.setVisibility(self.cameraANode, False)
        ball.setVisibility(self.cameraBNode, False)
        if orange:
            orange.setVisibility(self.viewpointNode, False)
        # Stadium is visible only to viewpoint, optional
        stadium = self.getFromDef(constants.DEF_STADIUM)
        if stadium:
            stadium.setVisibility(self.cameraANode, False)
            stadium.setVisibility(self.cameraBNode, False)
        # Robot's black body is visible only to robots
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                robot = self.getFromDef(get_robot_name(team, id))
                camBody = robot.getField('camBody')
                camBody0 = camBody.getMFNode(0)
                camBody0.setVisibility(self.viewpointNode, False)
        # Wall is visible only to robots
        wall = self.getFromDef(constants.DEF_WALL)
        if wall:
            wall.setVisibility(self.viewpointNode, False)
        # VisualWall is visible only to viewpoint, optional
        visual_wall = self.getFromDef(constants.DEF_VISWALL)
        if visual_wall:
            visual_wall.setVisibility(self.cameraANode, False)
            visual_wall.setVisibility(self.cameraBNode, False)
        # patches'
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                robot = self.getFromDef(get_robot_name(team, id))
                patches = robot.getField('patches')
                # number patch for decoration exists
                if patches.getCount() == 3:
                    number = patches.getMFNode(0)
                    id_red = patches.getMFNode(1)
                    id_blue = patches.getMFNode(2)
                    number.setVisibility(self.cameraANode, False)
                    number.setVisibility(self.cameraBNode, False)
                    id_red.setVisibility(self.viewpointNode, False)
                    id_red.setVisibility(self.cameraBNode, False)
                    id_blue.setVisibility(self.viewpointNode, False)
                    id_blue.setVisibility(self.cameraANode, False)
                else:  # no decorations
                    id_red = patches.getMFNode(0)
                    id_blue = patches.getMFNode(1)
                    id_red.setVisibility(self.viewpointNode, True)  # useless ?
                    id_red.setVisibility(self.cameraBNode, False)
                    id_blue.setVisibility(self.viewpointNode, False)
                    id_blue.setVisibility(self.cameraANode, False)

    ## basic ##
    def step(self, timeStep, runTimer=False):
        for i in range(0, timeStep, self.basicTimeStep):
            if Supervisor.step(self, self.basicTimeStep) == -1:
                return -1
            if runTimer:
                self.time += self.basicTimeStep
            self.update_label()
            self.change_view()

    def get_role(self, rpc):
        key = get_key(rpc)
        for role in constants.ROLES:
            if role in self.role_info and 'key' in self.role_info[role] and self.role_info[role]['key'] == key:
                return role
        sys.stderr.write("Error: get_role: invalid key.\n")
        return -1

    def callback(self, client, message):
        unprocessed = ''
        if not message.startswith('aiwc.'):
            print('Error, AIWC RPC messages should start with "aiwc.".')
            return unprocessed

        # Handle concatenated messages
        data = message.split('aiwc.')
        for command in data:
            if not command:
                continue
            if not command.endswith(')'):
                unprocessed += 'aiwc.' + command
                continue
            role = self.get_role(command)
            self.role_client[role] = client
            if command.startswith('get_info('):
                print('Server receive aiwc.get_info from ' + get_role_name(role))
                if role == constants.TEAM_RED:
                    self.tcp_server.send(client, json.dumps(self.role_info[constants.TEAM_RED]))
                else:
                    self.tcp_server.send(client, json.dumps(self.role_info[constants.TEAM_BLUE]))
            elif command.startswith('ready('):
                self.ready[role] = True
                if role == constants.TEAM_RED:
                    self.imageFrameBufferA.reset()
                elif role == constants.TEAM_BLUE:
                    self.imageFrameBufferB.reset()
                print('Server receive aiwc.ready from ' + get_role_name(role))
            elif command.startswith('set_speeds('):
                if role > constants.TEAM_BLUE:
                    sys.stderr.write("Error, cannot change robot speed.\n")
                    return unprocessed
                start = command.find('",') + 2
                end = command.find(')', start)
                speeds = command[start:end]
                speeds = [float(i) for i in speeds.split(',')]
                self.speeds_buffer[role] = speeds
                self.set_speeds(role, speeds)
            elif command.startswith('cont_num('):
                if role <=constants.TEAM_BLUE:
                    start = command.find('",') + 2
                    end = command.find(')', start)
                    cont_num = command[start:end]
                    self.light_control(role, cont_num)
            elif command.startswith('default_formation('):
                start = command.find('",') + 2
                end = command.find(')', start)
                formation = command[start:end]
                formation = [float(i) for i in formation.split(',')]
                self.check_fromation(role, formation)
            else:
                print('Server received unknown message', message)
        return unprocessed

    def publish_current_frame(self, reset_reason=None):
        frame_team_red = self.generate_frame(constants.TEAM_RED, reset_reason)
        frame_team_blue = self.generate_frame(constants.TEAM_BLUE, reset_reason)
        for role in constants.ROLES:
            if role in self.role_client:
                frame = frame_team_blue if role == constants.TEAM_BLUE else frame_team_red
                self.tcp_server.send(self.role_client[role], json.dumps(frame))

    def generate_frame(self, team, reset_reason=None):
        opponent = constants.TEAM_BLUE if team == constants.TEAM_RED else constants.TEAM_RED
        frame = {}
        frame['time'] = self.getTime()
        frame['score'] = [self.score[team], self.score[opponent]]
        frame['reset_reason'] = reset_reason if reset_reason else self.reset_reason
        if team == constants.TEAM_BLUE:
            if frame['reset_reason'] == constants.SCORE_RED_TEAM:
                frame['reset_reason'] = Game.SCORE_OPPONENT
            elif frame['reset_reason'] == constants.SCORE_BLUE_TEAM:
                frame['reset_reason'] = Game.SCORE_MYTEAM
        frame['game_state'] = self.game_state
        frame['ball_ownership'] = True if self.ball_ownership == team else False
        frame['half_passed'] = self.half_passed
        frame['subimages'] = []
        imageFrameBuffer = self.imageFrameBufferA if team == constants.TEAM_RED else self.imageFrameBufferB
        for subImage in imageFrameBuffer.update_image(self.getTime()):
            frame['subimages'].append(subImage)
        frame['coordinates'] = [None] * 3
        for t in constants.TEAMS:
            frame['coordinates'][t] = [None] * constants.NUMBER_OF_ROBOTS
            c = team if t == constants.TEAM_RED else opponent
            for id in range(constants.NUMBER_OF_ROBOTS):
                frame['coordinates'][t][id] = [None] * 7
                pos = self.get_robot_posture(c, id)
                frame['coordinates'][t][id][0] = pos[0] if team == constants.TEAM_RED else -pos[0]
                frame['coordinates'][t][id][1] = pos[1] if team == constants.TEAM_RED else -pos[1]
                frame['coordinates'][t][id][2] = pos[2]
                if team == constants.TEAM_RED:
                    frame['coordinates'][t][id][3] = pos[3]
                else:
                    frame['coordinates'][t][id][3] = pos[3] + constants.PI if pos[3] < 0 else pos[3] - constants.PI
                frame['coordinates'][t][id][4] = self.robot[c][id]['active']
                frame['coordinates'][t][id][5] = self.robot[c][id]['touch']
                frame['coordinates'][t][id][6] = self.robot[c][id]['ball_possession']
        frame['coordinates'][2] = [None] * 6
        frame['coordinates'][2][0] = self.ball_position[0] if team == constants.TEAM_RED else -self.ball_position[0]
        frame['coordinates'][2][1] = self.ball_position[1] if team == constants.TEAM_RED else -self.ball_position[1]
        frame['coordinates'][2][2] = self.ball_position[2]
        frame['EOF'] = True
        return frame

    ## check state ##
    def get_corner_ownership(self):
        ball_x = self.get_ball_position()[0]
        ball_y = self.get_ball_position()[1]
        robot_count = [0, 0]
        robot_distance = [0, 0]
        s_x = 1 if ball_x > 0 else -1
        s_y = 1 if ball_y > 0 else -1
        # count the robots and distance from the ball in the corner region of concern
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                if not self.robot[team][id]['active']:
                    continue
                robot_pos = self.get_robot_posture(team, id)
                x = robot_pos[0]
                y = robot_pos[1]
                # the robot is located in the corner region of concern
                if (s_x * x > constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH) and \
                   (s_y * y > constants.PENALTY_AREA_WIDTH / 2):
                    distance_squared = (x - ball_x) * (x - ball_x) + (y - ball_y) * (y - ball_y)
                    robot_count[team] += 1
                    robot_distance[team] += math.sqrt(distance_squared)
        # decision - team with more robots near the ball gets the ownership
        if robot_count[0] > robot_count[1]:
            return 0
        elif robot_count[1] > robot_count[0]:
            return 1
        else:  # tie breaker - team with robots (within the decision region) closer to the ball on average gets the ownership
            if robot_distance[0] < robot_distance[1]:
                return 0
            elif robot_distance[1] < robot_distance[0]:
                return 1
            else:  # a total tie - the attacker team gets an advantage
                return 0 if ball_x > 0 else 1

    def get_pa_ownership(self):
        ball_x = self.get_ball_position()[0]
        ball_y = self.get_ball_position()[1]
        robot_count = [0, 0]
        robot_distance = [0, 0]
        s_x = 1 if ball_x > 0 else -1
        # count the robots and distance from the ball in the penalty area of concern
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                if not self.robot[team][id]['active']:
                    continue
                robot_pos = self.get_robot_posture(team, id)
                x = robot_pos[0]
                y = robot_pos[1]
                # the robot is located in the corner region of concern
                if (s_x * x > constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH) and \
                   (abs(y) < constants.PENALTY_AREA_WIDTH / 2):
                    distance_squared = (x - ball_x) * (x - ball_x) + (y - ball_y) * (y - ball_y)
                    robot_count[team] += 1
                    robot_distance[team] += math.sqrt(distance_squared)
        # decision - team with more robots near the ball gets the ownership
        if robot_count[0] > robot_count[1]:
            return 0
        elif robot_count[1] > robot_count[0]:
            return 1
        else:  # tie breaker - team with robots (within the decision region) closer to the ball on average gets the ownership
            if robot_distance[0] < robot_distance[1]:
                return 0
            elif robot_distance[1] < robot_distance[0]:
                return 1
            else:  # a total tie - the attacker team gets an advantage
                return 0 if ball_x > 0 else 1

    def check_penalty_area(self):
        ball_x = self.get_ball_position()[0]
        ball_y = self.get_ball_position()[1]
        robot_count = [0, 0]
        # check if the ball is not in the penalty area
        if (abs(ball_x) < constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH) or \
           (abs(ball_y) > constants.PENALTY_AREA_WIDTH / 2):
            return False
        s_x = 1 if ball_x > 0 else -1
        # count the robots and distance from the ball in the penalty area of concern
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                if not self.robot[team][id]['active']:
                    continue
                robot_pos = self.get_robot_posture(team, id)
                x = robot_pos[0]
                y = robot_pos[1]
                # the robot is located in the penalty area of concern
                if (s_x * x > constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH) and \
                   (abs(y) < constants.PENALTY_AREA_WIDTH / 2):
                    robot_count[team] += 1
        if ball_x < 0:  # the ball is in Team Red's penalty area
            if robot_count[constants.TEAM_RED] > constants.PA_THRESHOLD_D:
                self.ball_ownership = constants.TEAM_BLUE
                return True
            if robot_count[constants.TEAM_BLUE] > constants.PA_THRESHOLD_A:
                self.ball_ownership = constants.TEAM_RED
                return True
        else:  # the ball is in Team Blue's penalty area
            if robot_count[constants.TEAM_BLUE] > constants.PA_THRESHOLD_D:
                self.ball_ownership = constants.TEAM_RED
                return True
            if robot_count[constants.TEAM_RED] > constants.PA_THRESHOLD_A:
                self.ball_ownership = constants.TEAM_BLUE
                return True
        return False

    def robot_in_field(self, team, id):
        robot_pos = self.get_robot_posture(team, id)
        x = robot_pos[0]
        y = robot_pos[1]
        if abs(y) < constants.GOAL_WIDTH / 2:
            if abs(x) > constants.FIELD_LENGTH / 2 + constants.GOAL_DEPTH:
                return False
            else:
                return True
        if abs(x) > constants.FIELD_LENGTH / 2:
            return False
        else:
            return True

    def ball_in_field(self):
        pos = self.get_ball_position()
        # checking with absolute values is sufficient since the field is symmetrical
        abs_x = abs(pos[0])
        abs_y = abs(pos[1])
        abs_z = abs(pos[2])

        if (abs_x > constants.FIELD_LENGTH / 2) and \
           (abs_y < constants.GOAL_WIDTH / 2) and \
           (abs_z >= 0.4):
            return False
        if (abs_x > constants.FIELD_LENGTH / 2 + constants.WALL_THICKNESS) and \
           (abs_y > constants.GOAL_WIDTH / 2 + constants.WALL_THICKNESS):
            return False
        if abs_y > constants.FIELD_WIDTH / 2 + constants.WALL_THICKNESS:
            return False
        # check triangular region at the corner
        cs_x = constants.FIELD_LENGTH / 2 - constants.CORNER_LENGTH
        cs_y = constants.FIELD_WIDTH / 2 + constants.WALL_THICKNESS
        ce_x = constants.FIELD_LENGTH / 2 + constants.WALL_THICKNESS
        ce_y = constants.FIELD_WIDTH / 2 - constants.CORNER_LENGTH
        if cs_x < abs_x and abs_x < ce_x:
            border_y = ce_y + (abs_x - ce_x) * (ce_y - cs_y) / (ce_x - cs_x)
            if abs_y > border_y:
                return False
        return True

    def any_object_nearby(self, target_x, target_y, target_r):
        # check ball position
        pos = self.get_ball_position()
        x = pos[0]
        y = pos[1]
        dist_sq = (target_x - x) * (target_x - x) + (target_y - y) * (target_y - y)
        # the ball is within the region
        if dist_sq < target_r * target_r:
            return True
        # check robot positions
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                pos = self.get_robot_posture(team, id)
                x = pos[0]
                y = pos[1]
                dist_sq = (target_x - x) * (target_x - x) + (target_y - y) * (target_y - y)
                # a robot is within the region
                if dist_sq < target_r * target_r:
                    return True

    ## get informations ##
    def get_robot_touch_ball(self):
        rc = [[False] * constants.NUMBER_OF_ROBOTS, [False] * constants.NUMBER_OF_ROBOTS]
        while self.receiver.getQueueLength() > 0:
            message = self.receiver.getData()
            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    if message[2 * id + team] == 1:
                        rc[team][id] = True
            self.receiver.nextPacket()
        return rc

    def flush_touch_ball(self):
        while self.receiver.getQueueLength() > 0:
            self.receiver.nextPacket()

    def get_robot_posture(self, team, id):
        position = self.robot[team][id]['node'].getPosition()
        orientation = self.robot[team][id]['node'].getOrientation()
        f = -1 if self.half_passed else 1
        x = position[0]
        y = -position[2]
        z = position[1]
        th = (constants.PI if self.half_passed else 0) + math.atan2(orientation[2], orientation[8]) + constants.PI / 2
        # Squeeze the orientation range to [-PI, PI]
        while th > constants.PI:
            th -= 2 * constants.PI
        while th < -constants.PI:
            th += 2 * constants.PI
        stand = orientation[4] > 0.8
        return [f * x, f * y, z, th, stand]

    def get_ball_position(self):
        f = -1 if self.half_passed else 1
        position = self.ball.getPosition()
        x = position[0]
        y = -position[2]
        z = position[1]
        return [f * x, f * y, z]

    def get_ball_velocity(self):
        v = self.ball.getVelocity()
        return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

    ## actions ##
    def relocate_ball(self, pos):
        node = self.ball
        x = constants.BALL_POSTURE[pos][0]
        z = constants.BALL_POSTURE[pos][1]
        f = -1 if self.half_passed else 1
        translation = [f * x, 0.2, f * -z]
        rotation = [0, 1, 0, 0]
        node.getField('translation').setSFVec3f(translation)
        node.getField('rotation').setSFRotation(rotation)
        node.resetPhysics()

    def reset_ball(self, x, z):
        f = -1.0 if self.half_passed else 1.0
        self.ball.getField('translation').setSFVec3f([f * x, 1.5 * constants.BALL_RADIUS, -f * z])
        self.ball.getField('rotation').setSFRotation([0, 1, 0, 0])
        self.ball.resetPhysics()

    def reset_robot(self, team, id, x, y, z, th):
        robot = self.getFromDef(get_robot_name(team, id))
        f = -1 if self.half_passed else 1
        translation = [f * x, y, f * -z]
        rotation = [0, 1, 0, th + (constants.PI if self.half_passed else 0)]

        al = robot.getField('axleLength').getSFFloat()
        h = robot.getField('height').getSFFloat()
        wr = robot.getField('wheelRadius').getSFFloat()

        lwTranslation = [-al / 2, (-h + 2 * wr) / 2, 0]
        rwTranslation = [al / 2, (-h + 2 * wr) / 2, 0]
        wheelRotation = [1, 0, 0, constants.PI / 2]

        robot.getField('translation').setSFVec3f(translation)
        robot.getField('rotation').setSFRotation(rotation)
        robot.getField('lwTranslation').setSFVec3f(lwTranslation)
        robot.getField('lwRotation').setSFRotation(wheelRotation)
        robot.getField('rwTranslation').setSFVec3f(rwTranslation)
        robot.getField('rwRotation').setSFRotation(wheelRotation)
        self.relocate_all(team, id)

        robot.resetPhysics()
        self.robot[team][id]['active'] = True
        self.robot[team][id]['touch'] = False
        self.robot[team][id]['ball_possession'] = False
        self.robot[team][id]['fall_time'] = self.time
        self.robot[team][id]['sentout_time'] = 0
        self.robot[team][id]['niopa_time'] = self.time  # not_in_opponent_penalty_area time
        self.robot[team][id]['ipa_time'] = self.time  # goalkeeper in_penalty_area time
        self.stop_robots()

    def reset(self, red_formation, blue_formation):
        # reset the ball
        if red_formation == constants.FORMATION_DEFAULT or red_formation == constants.FORMATION_KICKOFF:
            self.reset_ball(constants.BALL_POSTURE[constants.BALL_DEFAULT][0],
                            constants.BALL_POSTURE[constants.BALL_DEFAULT][1])
        elif red_formation == constants.FORMATION_GOALKICK_A:
            self.reset_ball(constants.BALL_POSTURE[constants.BALL_GOALKICK][0],
                            constants.BALL_POSTURE[constants.BALL_GOALKICK][1])
        elif red_formation == constants.FORMATION_GOALKICK_D:
            self.reset_ball(-constants.BALL_POSTURE[constants.BALL_GOALKICK][0],
                            constants.BALL_POSTURE[constants.BALL_GOALKICK][1])
        elif red_formation == constants.FORMATION_CAD_AD or red_formation == constants.FORMATION_CAD_DA:
            self.reset_ball(constants.BALL_POSTURE[constants.BALL_CORNERKICK][0],
                            constants.BALL_POSTURE[constants.BALL_CORNERKICK][1])
        elif red_formation == constants.FORMATION_CBC_AD or red_formation == constants.FORMATION_CBC_DA:
            self.reset_ball(constants.BALL_POSTURE[constants.BALL_CORNERKICK][0],
                            -constants.BALL_POSTURE[constants.BALL_CORNERKICK][1])
        elif red_formation == constants.FORMATION_CAD_AA or red_formation == constants.FORMATION_CAD_DD:
            self.reset_ball(-constants.BALL_POSTURE[constants.BALL_CORNERKICK][0],
                            -constants.BALL_POSTURE[constants.BALL_CORNERKICK][1])
        elif red_formation == constants.FORMATION_CBC_AA or red_formation == constants.FORMATION_CBC_DD:
            self.reset_ball(-constants.BALL_POSTURE[constants.BALL_CORNERKICK][0],
                            constants.BALL_POSTURE[constants.BALL_CORNERKICK][1])
        elif red_formation == constants.FORMATION_PENALTYKICK_A:
            self.reset_ball(constants.BALL_POSTURE[constants.BALL_PENALTYKICK][0],
                            constants.BALL_POSTURE[constants.BALL_PENALTYKICK][1])
        elif red_formation == constants.FORMATION_PENALTYKICK_D:
            self.reset_ball(-constants.BALL_POSTURE[constants.BALL_PENALTYKICK][0],
                            constants.BALL_POSTURE[constants.BALL_PENALTYKICK][1])

        # reset the robots
        for team in constants.TEAMS:
            if team == constants.TEAM_RED:
                s = 1
                a = 0
                formation = red_formation
                default_formation = self.default_formation[0]
            else:
                s = -1
                a = constants.PI
                formation = blue_formation
                default_formation = self.default_formation[1]

            if formation == 0: num = 5
            elif formation == 1: num = 3
            else: num = 0

            for id in range(num):
                self.reset_robot(team, id,
                                 default_formation[id][0] * s,
                                 constants.ROBOT_HEIGHT[id] / 2,
                                 default_formation[id][1] * s,
                                 default_formation[id][2] + a - constants.PI / 2)
            for id in range(num, constants.NUMBER_OF_ROBOTS):
                self.reset_robot(team, id,
                                 constants.ROBOT_FORMATION[formation][id][0] * s,
                                 constants.ROBOT_HEIGHT[id] / 2,
                                 constants.ROBOT_FORMATION[formation][id][1] * s,
                                 constants.ROBOT_FORMATION[formation][id][2] + a - constants.PI / 2)

        # reset recent touch
        self.recent_touch = [[False] * constants.NUMBER_OF_ROBOTS, [False] * constants.NUMBER_OF_ROBOTS]
        self.deadlock_time = self.time
        # flush touch packet
        self.flush_touch_ball()
        # reset slider
        self.relocate_all_every()

    def lock_all_robots(self, locked):
        for t in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                self.robot[t][id]['active'] = not locked
        if locked:
            self.relocate_all_every()

    def stop_robots(self):
        for t in constants.TEAMS:
            self.set_speeds(t, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def send_to_foulzone(self, team, id):
        f = -1 if self.half_passed else 1
        s = 1 if team == 0 else -1
        translation = [f * constants.ROBOT_FOUL_POSTURE[id][0] * s,
                       constants.ROBOT_HEIGHT[id] / 2,
                       f * -constants.ROBOT_FOUL_POSTURE[id][1] * s]
        angle = constants.PI if self.half_passed else 0
        angle += constants.ROBOT_FOUL_POSTURE[id][2]
        angle += 0 if team == 0 else constants.PI
        angle -= constants.PI / 2
        rotation = [0, 1, 0, angle]

        node = self.robot[team][id]['node']
        al = node.getField('axleLength').getSFFloat()
        h = node.getField('height').getSFFloat()
        wr = node.getField('wheelRadius').getSFFloat()
        lwTranslation = [-al / 2, (-h + 2 * wr) / 2, 0]
        rwTranslation = [al / 2, (-h + 2 * wr) / 2, 0]
        wheelRotation = [1, 0, 0, constants.PI / 2]
        
        node.getField('translation').setSFVec3f(translation)
        node.getField('rotation').setSFRotation(rotation)
        node.getField('customData').setSFString('0 0 0 0')
        node.getField('lwTranslation').setSFVec3f(lwTranslation)
        node.getField('lwRotation').setSFRotation(wheelRotation)
        node.getField('rwTranslation').setSFVec3f(rwTranslation)
        node.getField('rwRotation').setSFRotation(wheelRotation)
        self.relocate_all(team, id)
        node.resetPhysics()

    def return_to_field(self, team, id):
        robot = self.robot[team][id]['node']
        f = -1 if self.half_passed else 1
        s = 1 if team == 0 else -1
        translation = [f * self.default_formation[team][id][0] * s,
                       constants.ROBOT_HEIGHT[id] / 2,
                       f * -self.default_formation[team][id][1] * s]
        angle = constants.PI if self.half_passed else 0
        angle += self.default_formation[team][id][2]
        angle += 0 if team == 0 else constants.PI
        angle -= constants.PI / 2
        rotation = [0, 1, 0, angle]
        al = robot.getField('axleLength').getSFFloat()
        h = robot.getField('height').getSFFloat()
        wr = robot.getField('wheelRadius').getSFFloat()
        lwTranslation = [-al / 2, (-h + 2 * wr) / 2, 0]
        rwTranslation = [al / 2, (-h + 2 * wr) / 2, 0]
        wheelRotation = [1, 0, 0, constants.PI / 2]
        robot.getField('translation').setSFVec3f(translation)
        robot.getField('rotation').setSFRotation(rotation)
        robot.getField('lwTranslation').setSFVec3f(lwTranslation)
        robot.getField('lwRotation').setSFRotation(wheelRotation)
        robot.getField('rwTranslation').setSFVec3f(rwTranslation)
        robot.getField('rwRotation').setSFRotation(wheelRotation)
        self.relocate_all(team, id)
        robot.resetPhysics()

    ## label ##
    def update_label(self):
        seconds = self.time / 1000.0
        minutes = seconds // 60
        seconds -= minutes * 60
        if not self.half_passed:
            self.setLabel(1, '%d:%d' % (self.score[0], self.score[1]), 0.48, 0.9, 0.10, 0x00000000, 0, 'Arial')
            self.setLabel(0, '%d:%05.2f (1st half)' % (minutes, seconds), 0.45, 0.95, 0.1, 0x00000000, 0, 'Arial')
        else:
            minutes += self.add_minutes
            seconds += self.add_seconds
            self.setLabel(1, '%d:%d' % (self.score[1], self.score[0]), 0.48, 0.9, 0.10, 0x00000000, 0, 'Arial')
            self.setLabel(0, '%d:%05.2f (2nd half)' % (minutes, seconds), 0.45, 0.95, 0.1, 0x00000000, 0, 'Arial')

    ## camera ##
    def mark_half_passed(self):
        self.cameraANode.getField('rotation').setSFRotation([0, 0, 1, constants.PI])
        self.cameraBNode.getField('rotation').setSFRotation([0, 0, 1, 0])

    def episode_restart(self):
        self.cameraANode.getField('rotation').setSFRotation([0, 0, 1, 0])
        self.cameraBNode.getField('rotation').setSFRotation([0, 0, 1, constants.PI])

    ## speed ##
    def set_speeds(self, team, speeds):
        letter = 'R' if team == constants.TEAM_RED else 'B'
        def_robot_prefix = constants.DEF_ROBOT_PREFIX + letter
        for id in range(constants.NUMBER_OF_ROBOTS):
            robot = self.getFromDef(def_robot_prefix + str(id))
            if self.robot[team][id]['active']:
                fs_speed = self.check_fslider(speeds, team, id)
                bs_speed = self.check_bslider(speeds, team, id)
                robot.getField('customData').setSFString(
                    "%f %f %f %f" % (speeds[id * 4] / constants.WHEEL_RADIUS[id], speeds[id * 4 + 1] / constants.WHEEL_RADIUS[id],
                                        fs_speed, bs_speed)
                )
            else:
                robot.getField('customData').setSFString(
                    "%f %f %f %f" % (0, 0, 0, 0)
                )

    ## sliders ##
    def check_fslider(self, speeds, team, id):
        fs_speed = max(min(speeds[id * 4 + 2],10),0)
        t_frl = 4
        m_fs = 0.2
        if (self.fslider_trig[team][id] == 0) and (fs_speed > 0):
            self.fslider_trig[team][id] = 1

        if (self.fslider_trig[team][id] == 1):
            self.fslider_count[team][id] += 1
            if (self.fslider_count[team][id] <= 2):
                fs_speed = fs_speed
            elif (self.fslider_count[team][id] < t_frl):
                fs_speed = -3
            else:
                fs_speed = 0
                if (self.fslider_count[team][id] == t_frl):
                    self.relocate_fslider(team, id)
                elif (self.fslider_count[team][id] == 20):
                    self.fslider_count[team][id] = 0
                    self.fslider_trig[team][id] = 0

        robot_pos = self.get_robot_posture(team, id)
        if team == 0 and robot_pos[0] > 3 and abs(robot_pos[1]) < 0.9:
            fs_speed = 0
        if team == 1 and robot_pos[0] < -3 and abs(robot_pos[1]) < 0.9:
            fs_speed = 0

        robot = self.robot[team][id]['node']
        cond = (abs(robot.getField('fsTranslation').getSFVec3f()[2]) > 0.01)
        if (self.fslider_trig[team][id] == 0) and cond:
            self.relocate_fslider(team,id)

        return m_fs * fs_speed

    def relocate_fslider(self, team, id):
        robot = self.robot[team][id]['node']

        sliderRotation = [1, 0, 0, 0]
        fsTranslation = [0, 0, 0]

        robot.getField('fsTranslation').setSFVec3f(fsTranslation)
        robot.getField('fsRotation').setSFRotation(sliderRotation)
        robot.resetPhysics()

    def check_bslider(self, speeds, team, id):
        bs_speed = max(min(speeds[id * 4 + 3],10),0)
        t_brls = [
            [5,5,6,7,7,8,8,9,10,11,11],
            [5,5,6,7,7,8,8,9,10,10,11],
            [5,5,6,7,7,8,8,9,10,10,11],
            [5,5,6,7,7,7,8,9,10,10,11],
            [5,5,6,7,7,7,8,9,10,10,11]
        ]
        m_bs = 0.3
        if ((self.bslider_trig[team][id] == 0) and (bs_speed > 0)):
            self.bslider_trig[team][id] = 1
            self.t_brl[team][id] = t_brls[id][int(bs_speed)]

        if (self.bslider_trig[team][id] == 1):
            self.bslider_count[team][id] += 1
            if (self.bslider_count[team][id] <= 2):
                bs_speed = bs_speed
            elif (self.bslider_count[team][id] < self.t_brl[team][id]):
                bs_speed = -2
            else:
                bs_speed = 0
                if (self.bslider_count[team][id] == self.t_brl[team][id]):
                    self.relocate_bslider(team, id)
                elif (self.bslider_count[team][id] == 20):
                    self.bslider_count[team][id] = 0
                    self.bslider_trig[team][id] = 0

        robot = self.robot[team][id]['node']
        cond = (abs(robot.getField('bsTranslation').getSFVec3f()[1] + 0.037) > 0.0025)
        if (self.bslider_trig[team][id] == 0) and cond:
            self.relocate_bslider(team,id)

        return m_bs * bs_speed

    def relocate_bslider(self, team, id):
        robot = self.robot[team][id]['node']

        sliderRotation = [1, 0, 0, 0]
        bsTranslation = [0, -0.037, 0]

        robot.getField('bsTranslation').setSFVec3f(bsTranslation)
        robot.getField('bsRotation').setSFRotation(sliderRotation)
        robot.resetPhysics()

    def relocate_all(self, team, id):
        self.relocate_bslider(team, id)
        self.bslider_count[team][id] = 0
        self.relocate_fslider(team, id)
        self.fslider_count[team][id] = 0

    def relocate_all_every(self):
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                self.relocate_all(team, id)

    ## ball possession ##
    def get_ball_possession(self):
        rc = [[False] * constants.NUMBER_OF_ROBOTS, [False] * constants.NUMBER_OF_ROBOTS]
        for team in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                if self.robot_in_field(team, id):
                    rc[team][id] = self.check_ball_poss(team, id)
        return rc

    def check_ball_poss(self, team, id):
        ball_x = self.get_ball_position()[0]
        ball_y = self.get_ball_position()[1]
        ball_z = self.get_ball_position()[2]
        robot_pos = self.get_robot_posture(team, id)
        x = robot_pos[0]
        y = robot_pos[1]
        z = robot_pos[2]
        th = robot_pos[3]

        theta = th
        if (th > constants.PI):
            theta -= 2*constants.PI
        d_theta = abs(theta - math.atan2(ball_y-y, ball_x-x))
        if (d_theta > constants.PI):
            d_theta -= 2*constants.PI
        dist = math.sqrt((ball_y - y)*(ball_y - y)+(ball_x - x)*(ball_x - x))
        robot = self.robot[team][id]['node']
        v_r = robot.getVelocity()
        v_b = self.ball.getVelocity()
        v = [v_r[0] - v_b[0], v_r[1] - v_b[1]]
        speed = math.sqrt(v[0] * v[0] + v[1] * v[1])
        add = 0
        if (speed < 0.5):
            add = 0.5 * 0.13
        else:
            add = speed * 0.13
        d_range = constants.ROBOT_SIZE[id]/2 + constants.BALL_RADIUS + add
            
        if ((dist < d_range) and (abs(d_theta) < constants.PI/4) and (abs(z - ball_z) < 0.01)):
            return True
        else:
            return False

    ## viewpoint ##
    def change_view(self):
        pn = self.getFromDef("DEF_AUDVIEW")
        x = self.get_ball_position()[0]
        y = self.get_ball_position()[1]
        z = self.get_ball_position()[2]
        f = -1 if self.half_passed else 1
        orientation = [
                [-1.00,  0.00,  0.00,  0.150],
                [ 1.00,  0.00,  0.00,  4.710],
                [-0.20,  0.96,  0.20,  1.600],
                [ 0.20,  0.96,  0.20,  4.67],
                [-1.00,  0.00,  0.00,  6.960],
                [ 0.15, 0.977,  0.15,  4.690],
                [-0.15, 0.977,  0.15,  1.600],
                [-1.00,  0.00,  0.00,  0.891], # normal
        ]
        position = [
                [f * x, 1.11 + z - 0.06, 4.3 - f * y],
                [f * x, 4 + z - 0.06, - f * y],
                [3.3 + f * x, 1.56 + z - 0.06, - f * y],
                [-3.3 + f * x, 1.56 + z - 0.06, - f * y],
                [f * x, 1.5 + z - 0.06, 1.7 - f * y],
                [ 0.3, 0.85, 0],
                [-0.3, 0.85, 0],
                [ 0.00, 8.88, 7.30], # normal
        ]

        key = self.view_key.getKey()

        if key == ord('P'):
            pn.getField('orientation').setSFRotation(orientation[0])
            pn.getField('position').setSFVec3f(position[0])
            pn.getField('follow').setSFString("soccer_ball")
            self.view = 1
        elif key == ord('0'):
            pn.getField('orientation').setSFRotation(orientation[1])
            pn.getField('position').setSFVec3f(position[1])
            pn.getField('follow').setSFString("soccer_ball")
            self.view = 2
        elif key == ord('-'):
            pn.getField('orientation').setSFRotation(orientation[2])
            pn.getField('position').setSFVec3f(position[2])
            pn.getField('follow').setSFString("soccer_ball")
            self.view = 3
        elif key == ord('='):
            pn.getField('orientation').setSFRotation(orientation[3])
            pn.getField('position').setSFVec3f(position[3])
            pn.getField('follow').setSFString("soccer_ball")
            self.view = 4
        elif key == ord('O'):
            pn.getField('orientation').setSFRotation(orientation[4])
            pn.getField('position').setSFVec3f(position[4])
            pn.getField('follow').setSFString("soccer_ball")
            self.view = 5
        elif key == ord(']'):
            pn.getField('orientation').setSFRotation(orientation[5])
            pn.getField('position').setSFVec3f(position[5])
            pn.getField('follow').setSFString("")
            self.view = 6
        elif key == ord('['):
            pn.getField('orientation').setSFRotation(orientation[6])
            pn.getField('position').setSFVec3f(position[6])
            pn.getField('follow').setSFString("")
            self.view = 7
        elif key == ord('9'):
            pn.getField('orientation').setSFRotation(orientation[7])
            pn.getField('position').setSFVec3f(position[7])
            pn.getField('follow').setSFString("")
            self.view = 8

        if self.view != 0 and self.view < 6:
            cur_view = pn.getField('position').getSFVec3f()
            dx = abs(cur_view[0] - position[self.view-1][0])
            dy = abs(cur_view[2] - position[self.view-1][2])
            if dx > 0.5 or dy > 0.5:
                pn.getField('position').setSFVec3f(position[self.view-1])

    ## formation ##
    def check_fromation(self, role, l_formation):
        f0 = constants.ROBOT_FORMATION[0]
        formation = [[] for _ in range(constants.NUMBER_OF_ROBOTS)]
        for i in range(constants.NUMBER_OF_ROBOTS):
            formation[i] = l_formation[3*i:3*i+3]
        for i in range(constants.NUMBER_OF_ROBOTS):
            if formation[i] != f0[i]:
                if i == 0:
                    if ((formation[i][0] >= constants.FIELD_LENGTH/2 + constants.PENALTY_AREA_DEPTH) - constants.ROBOT_SIZE[i] or
                        abs(formation[i][1] >= constants.PENALTY_AREA_WIDTH/2 - constants.ROBOT_SIZE[i])):
                        formation[i] = f0[i]
                else:
                    dist = math.sqrt(formation[i][0]*formation[i][0] + formation[i][1]*formation[i][1])
                    if dist < 0.5+constants.ROBOT_SIZE[i] or formation[i][0] > -constants.ROBOT_SIZE[i]:
                        formation[i] = f0[i]

        self.default_formation[role] = formation
        self.ready2[role] = True

    def check_formation_ready(self):
        f0 = constants.ROBOT_FORMATION[0]
        sum_gap = 0
        for team in constants.TEAMS:
            df = self.default_formation[team]
            f = 1 if team == 0 else -1
            for id in range(constants.NUMBER_OF_ROBOTS-2):
                rp = self.get_robot_posture(team, id)
                sum_gap += abs(df[id][0]-f*rp[0]) + abs(df[id][1]-f*rp[1])
            if sum_gap < 0.01:
                self.ready[2 + team] = True

    ## speaker ##
    def sound_speaker(self, state):
        sounds = [
            "sounds/whistle.wav",
            "sounds/whistle_long.wav",
            "sounds/whistle_2.wav",
            "sounds/whistle_3.wav"
        ]
                    # left, right, sound, volume, pitch, balance, loop
        Speaker.playSound(self.spk, self.spk, sounds[state], 1, 1, 0, False)

    ## keyboard ##
    def light_control(self, team, num):
        for id in range(constants.NUMBER_OF_ROBOTS):
            robot = self.robot[team][id]['node']
            if id == int(num):
                slc = [0.5,0.5,0.5]
            else:
                slc = [0,0,0]
            robot.getField('slc').setSFColor(slc)

    def keyboard_light(self):
        for team in constants.TEAMS:
            if not self.keyboard_control[team]:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    robot = self.robot[team][id]['node']
                    robot.getField('slc').setSFColor([0,0,0])

    def run(self):
        config_file = open('../../config.json')
        config = json.loads(config_file.read())
        self.game_time = constants.DEFAULT_GAME_TIME_MS / constants.PERIOD_MS * constants.PERIOD_MS
        deadlock_flag = True
        if config['rule']:
            if config['rule']['game_time']:
                self.game_time = config['rule']['game_time'] * 1000 / constants.PERIOD_MS * constants.PERIOD_MS
                self.add_seconds = self.game_time / 1000.0
                self.add_minutes = self.add_seconds // 60
                self.add_seconds -= self.add_minutes * 60
            if not config['rule']['deadlock']:
                deadlock_flag = config['rule']['deadlock']
        else:
            print('"rule" section of \'config.json\' seems to be missing: using default options\n')
        print('Rules:\n')
        print('     game duration - ' + str(self.game_time / 1000) + ' seconds\n')
        print('          deadlock - ' + str(deadlock_flag) + '\n')

        # gets other options from 'config.json' (if no option is specified, default option is given)
        # automatic recording of the game (default: false)
        # automatic repetition of the game (default: false)
        player_infos = []
        repeat = False
        record = False
        record_path = ''
        if config['tool']:
            if config['tool']['repeat']:
                repeat = config['tool']['repeat']
            if repeat:  # if repeat is enabled, record is forced to be disabled
                print('Game repetition is enabled that the game recording will be disabled.\n')
            elif config['tool']['record']:
                record = config['tool']['record']
            if config['tool']['record_path']:
                record_path = config['tool']['record_path']

        path_prefix = '../../'
        team_name = {}
        self.role_info = {}
        self.role_client = {}
        self.ready = [False] * 4  # TEAM_RED, TEAM_BLUE, Default_formation_R/B
        self.ready2 = [False] * 2  # Default_formation_R/B

        # gets the teams' information from 'config.json'
        for team in constants.TEAMS:
            if team == constants.TEAM_RED:
                tc = 'team_a'
                tc_op = 'team_b'
            else:
                tc = 'team_b'
                tc_op = 'team_a'
            # my team
            name = ''
            rating = 0  # rating is disabled
            exe = ''
            data = ''
            keyboard = False
            if config[tc]:
                if config[tc]['name']:
                    name = config[tc]['name']
                if config[tc]['executable']:
                    exe = config[tc]['executable']
                if config[tc]['datapath']:
                    data = config[tc]['datapath']
                if config[tc]['keyboard']:
                    keyboard = config[tc]['keyboard']
            self.keyboard_control[team] = keyboard
            # opponent
            name_op = ''
            rating_op = 0  # rating is disabled
            if config[tc_op]:
                if config[tc_op]['name']:
                    name_op = config[tc_op]['name']
            player_infos.append({
                'name': name,
                'rating': rating,
                'exe': path_prefix + exe,
                'path_prefix': path_prefix + data,
                'role': team
            })

            if team == constants.TEAM_RED:
                print('Team A:\n')
            else:
                print('Team B:\n')
            print('  team name - ' + name + '\n')
            team_name[team] = name
            print('  executable - ' + exe + '\n')
            print('  data path - ' + data + '\n')
            print('  keyboard - ' + str(keyboard) + '\n\n')

            # create information for aiwc.get_info() in advance
            info = {}
            info['field'] = [constants.FIELD_LENGTH, constants.FIELD_WIDTH]
            info['goal'] = [constants.GOAL_DEPTH, constants.GOAL_WIDTH]
            info['penalty_area'] = [constants.PENALTY_AREA_DEPTH, constants.PENALTY_AREA_WIDTH]
            info['goal_area'] = [constants.GOAL_AREA_DEPTH, constants.GOAL_AREA_WIDTH]
            info['ball_radius'] = constants.BALL_RADIUS
            info['ball_mass'] = constants.BALL_MASS
            info['robot_size'] = constants.ROBOT_SIZE
            info['robot_height'] = constants.ROBOT_HEIGHT
            info['axle_length'] = constants.AXLE_LENGTH
            info['robot_body_mass'] = constants.ROBOT_BODY_MASS
            info['wheel_radius'] = constants.WHEEL_RADIUS
            info['wheel_mass'] = constants.WHEEL_MASS
            info['max_linear_velocity'] = constants.MAX_LINEAR_VELOCITY
            info['max_torque'] = constants.MAX_TORQUE
            info['resolution'] = [constants.RESOLUTION_X, constants.RESOLUTION_Y]
            info['number_of_robots'] = constants.NUMBER_OF_ROBOTS
            info['codewords'] = constants.CODEWORDS
            info['game_time'] = self.game_time / 1000
            info['team_info'] = [[['name_a', name], ['rating', rating]], [['name_b', name_op], ['rating', rating_op]]]
            info['key'] = random_string(constants.KEY_LENGTH)
            info['keyboard'] = keyboard
            self.role_info[team] = info

        a = random.randint(1,255)
        b = random.randint(1,255)
        c = random.randint(1,255)
        SERVER_IP = '127.'+str(a)+'.'+str(b)+'.'+str(c)
        self.tcp_server = TcpServer(SERVER_IP, constants.SERVER_PORT)
        self.ball = self.getFromDef(constants.DEF_BALL)
        self.time = 0
        self.kickoff_time = self.time
        self.score = [0, 0]
        self.half_passed = False
        self.reset_reason = Game.NONE
        self.game_state = Game.STATE_KICKOFF
        self.ball_ownership = constants.TEAM_RED  # red
        self.robot = [[0 for x in range(constants.NUMBER_OF_ROBOTS)] for y in range(2)]
        for t in constants.TEAMS:
            for id in range(constants.NUMBER_OF_ROBOTS):
                node = self.getFromDef(get_robot_name(t, id))
                self.robot[t][id] = {}
                self.robot[t][id]['node'] = node
                self.robot[t][id]['active'] = True
                self.robot[t][id]['touch'] = False
                self.robot[t][id]['ball_possession'] = False
                self.robot[t][id]['niopa_time'] = self.time  # not_in_opponent_penalty_area time
                self.robot[t][id]['ipa_time'] = self.time  # goalkeeper in_penalty_area time
        self.reset(constants.FORMATION_KICKOFF, constants.FORMATION_DEFAULT)
        self.lock_all_robots(True)
        self.robot[constants.TEAM_RED][4]['active'] = True

        self.keyboard_light()

        # start participants
        for player_info in player_infos:
            exe = player_info['exe']
            if not os.path.exists(exe):
                print('Participant controller not found: ' + exe)
            else:
                command_line = []
                if exe.endswith('.py'):
                    os.environ['PYTHONPATH'] += os.pathsep + os.path.join(os.getcwd(), 'player_py')
                    if sys.platform == 'win32':
                        command_line.append('python')
                command_line.append(exe)
                command_line.append(SERVER_IP)
                command_line.append(str(constants.SERVER_PORT))
                command_line.append(self.role_info[player_info['role']]['key'])
                command_line.append(player_info['path_prefix'])
                print(command_line)
                subprocess.Popen(command_line)
        self.started = False
        print('Waiting for player to be ready...')

        while True:
            sys.stdout.flush()
            self.tcp_server.spin(self)
            if not self.started:
                if all(self.ready):
                    if record:
                        print('Game recording is enabled.')
                        time_info = time.localtime()
                        record_fullpath = '{}/[{:04d}-{:02d}-{:02d}T{:02d}_{:02d}_{:02d}]{}_{}.mp4'.format(
                            record_path,
                            # [<year>-<month>-<day>T<hour>_<minute>_<seconds>]
                            time_info[0], time_info[1], time_info[2], time_info[3], time_info[4], time_info[5],
                            team_name[constants.TEAM_RED], team_name[constants.TEAM_BLUE]
                            )
                        self.movieStartRecording(record_fullpath, 1920, 1080, 0, 100, 1, False)
                    print('Starting match.')
                    self.started = True
                    self.ball_position = self.get_ball_position()
                    self.publish_current_frame(Game.GAME_START)
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    self.sound_speaker(constants.WHISTLE_LONG_SOUND)
                else:
                    if self.step(self.timeStep) == -1:
                        break
                    else:
                        self.waitReady += self.timeStep
                        if (self.waitReady == constants.WAIT_READY_MS):
                            print('Game could not be initiated. Need two players ready.')
                            return
                    ###### try to change
                    self.reset(constants.FORMATION_KICKOFF, constants.FORMATION_DEFAULT)
                    self.lock_all_robots(True)
                    self.robot[constants.TEAM_RED][4]['active'] = True
                    if all(self.ready2):
                        self.check_formation_ready()
                continue

            self.ball_position = self.get_ball_position()
            if self.time >= self.game_time:  # half of game over
                if self.half_passed:  # game over
                    self.sound_speaker(constants.WHISTLE_3_SOUND)
                    if repeat:
                        self.publish_current_frame(Game.EPISODE_END)
                        self.reset_reason = Game.EPISODE_END
                        self.stop_robots()
                        if self.step(constants.WAIT_END_MS) == -1:
                            break
                        self.half_passed = False
                        self.episode_restart()
                        self.ball_ownership = constants.TEAM_RED
                        self.game_state = Game.STATE_KICKOFF
                        self.time = 0
                        self.kickoff_time = self.time
                        self.score = [0, 0]
                        self.reset(constants.FORMATION_KICKOFF, constants.FORMATION_DEFAULT)
                        self.lock_all_robots(True)
                        self.robot[constants.TEAM_RED][4]['active'] = True
                        if self.step(constants.WAIT_STABLE_MS) == -1:
                            break
                        self.publish_current_frame(Game.GAME_START)
                    else:
                        self.publish_current_frame(Game.GAME_END)
                    self.stop_robots()
                    if self.step(constants.WAIT_END_MS) == -1:
                        break
                    self.tcp_server.spin(self)  # leave time to receive report
                    if not repeat:
                        break
                    else:
                        self.sound_speaker(constants.WHISTLE_LONG_SOUND)
                else:  # second half starts with a kickoff by the blue team (1)
                    self.sound_speaker(constants.WHISTLE_2_SOUND)
                    self.publish_current_frame(Game.HALFTIME)
                    self.stop_robots()
                    if self.step(constants.WAIT_END_MS) == -1:
                        break
                    self.half_passed = True
                    self.mark_half_passed()
                    self.ball_ownership = constants.TEAM_BLUE
                    self.game_state = Game.STATE_KICKOFF
                    self.time = 0
                    self.kickoff_time = self.time
                    self.reset(constants.FORMATION_DEFAULT, constants.FORMATION_KICKOFF)
                    self.lock_all_robots(True)
                    self.robot[constants.TEAM_BLUE][4]['active'] = True
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    self.publish_current_frame(Game.GAME_START)
                    self.sound_speaker(constants.WHISTLE_LONG_SOUND)
                continue

            self.publish_current_frame()
            self.reset_reason = Game.NONE

            # update ball possession statuses of robots
            ball_possession = self.get_ball_possession()
            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    self.robot[team][id]['ball_possession'] = ball_possession[team][id]
                    if ball_possession[team][id]:
                        self.ball_possession = ball_possession

            # update touch statuses of robots
            touch = self.get_robot_touch_ball()
            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    self.robot[team][id]['touch'] = touch[team][id]
                    if touch[team][id]:  # if any of the robots has touched the ball at this frame, update touch status
                        self.recent_touch = touch

            # check if any of robots has fallen
            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    # if a robot has fallen and could not recover for constants.FALL_TIME_MS, send the robot to foulzone
                    if self.robot[team][id]['active'] \
                       and self.time - self.robot[team][id]['fall_time'] >= constants.FALL_TIME_MS:
                        self.robot[team][id]['active'] = False
                        self.send_to_foulzone(team, id)
                        self.robot[team][id]['sentout_time'] = self.time
                    elif self.get_robot_posture(team, id)[4]:  # robot is standing properly
                        self.robot[team][id]['fall_time'] = self.time
            
            # check if any of robots has been left the field without send_to_foulzone()
            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    # an active robot is not in the field
                    if self.robot[team][id]['active'] and not self.robot_in_field(team, id):
                        # make the robot inactive and send out
                        self.robot[team][id]['active'] = False
                        self.send_to_foulzone(team, id)
                        self.robot[team][id]['sentout_time'] = self.time

            # check if any of robots are in the opponent's penalty area
            def is_in_opponent_goal(x, y):
                return (x > constants.FIELD_LENGTH / 2) and (abs(y) < constants.GOAL_WIDTH / 2)

            def is_in_opponent_penalty_area(x, y):
                return (x <= constants.FIELD_LENGTH / 2) \
                   and (x > constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH) \
                   and (abs(y) < constants.PENALTY_AREA_WIDTH / 2)

            for team in constants.TEAMS:
                for id in range(constants.NUMBER_OF_ROBOTS):
                    pos = self.get_robot_posture(team, id)
                    sign = 1 if team == constants.TEAM_RED else -1
                    x = sign * pos[0]
                    y = sign * pos[1]
                    # if a robot has been in the opponent's penalty area for more than constants.IOPA_TIME_LIMIT_MS seconds,
                    # the robot is relocated to the initial position
                    if is_in_opponent_goal(x, y) or is_in_opponent_penalty_area(x, y):
                        if self.time - self.robot[team][id]['niopa_time'] >= constants.IOPA_TIME_LIMIT_MS:
                            ix = sign * self.default_formation[team][id][0]
                            iy = sign * self.default_formation[team][id][1]
                            r = 1.5 * constants.ROBOT_SIZE[id]
                            # if any object is located within 1.5 * robot_size, the relocation is delayed
                            if not self.any_object_nearby(ix, iy, r):
                                self.return_to_field(team, id)
                                self.robot[team][id]['niopa_time'] = self.time
                    else:
                        self.robot[team][id]['niopa_time'] = self.time

            # check if the goalkeeper is in the own penalty area
            def is_in_goal(x, y):
                return (x < -constants.FIELD_LENGTH / 2) and (abs(y) < constants.GOAL_WIDTH / 2)

            def is_in_penalty_area(x, y):
                return (x >= -constants.FIELD_LENGTH / 2) and \
                       (x < -constants.FIELD_LENGTH / 2 + constants.PENALTY_AREA_DEPTH) and \
                       (abs(y) < constants.PENALTY_AREA_WIDTH / 2)

            for team in constants.TEAMS:
                pos = self.get_robot_posture(team, 0)
                sign = 1 if team == constants.TEAM_RED else -1
                x = sign * pos[0]
                y = sign * pos[1]
                # if the goalkeeper has been not in the penalty area for more than constants.GK_NIPA_TIME_LIMIT_MS seconds,
                # the robot is returned to the initial position
                if is_in_goal(x, y) or is_in_penalty_area(x, y):
                    self.robot[team][0]['ipa_time'] = self.time
                elif self.time - self.robot[team][0]['ipa_time'] >= constants.GK_NIPA_TIME_LIMIT_MS:
                    ix = sign * self.default_formation[team][0][0]
                    iy = sign * self.default_formation[team][0][1]
                    r = 1.5 * constants.ROBOT_SIZE[0]
                    # if any object is located within 1.5 * robot_size, the return is delayed
                    if not self.any_object_nearby(ix, iy, r):
                        self.robot[team][0]['active'] = True
                        self.return_to_field(team, 0)
                        self.robot[team][0]['ipa_time'] = self.time
            
            if self.game_state == Game.STATE_DEFAULT:
                ball_x = self.ball_position[0]
                ball_y = self.ball_position[1]
                ball_z = self.ball_position[2]
                if abs(ball_x) > constants.FIELD_LENGTH / 2 and abs(ball_y) < constants.GOAL_WIDTH / 2 and abs(ball_z) < 0.33:
                    goaler = constants.TEAM_RED if ball_x > 0 else constants.TEAM_BLUE
                    self.score[goaler] += 1
                    self.update_label()
                    self.stop_robots()
                    self.sound_speaker(constants.WHISTLE_SOUND)
                    if self.step(constants.WAIT_GOAL_MS) == -1:
                        break
                    self.game_state = Game.STATE_KICKOFF
                    self.ball_ownership = constants.TEAM_BLUE if ball_x > 0 else constants.TEAM_RED
                    self.kickoff_time = self.time
                    if self.ball_ownership == constants.TEAM_RED:
                        self.reset(constants.FORMATION_KICKOFF, constants.FORMATION_DEFAULT)
                    else:
                        self.reset(constants.FORMATION_DEFAULT, constants.FORMATION_KICKOFF)
                    self.lock_all_robots(True)
                    self.robot[self.ball_ownership][4]['active'] = True
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    self.sound_speaker(constants.WHISTLE_LONG_SOUND)
                    self.reset_reason = constants.SCORE_RED_TEAM if ball_x > 0 else constants.SCORE_BLUE_TEAM
                elif not self.ball_in_field():
                    self.sound_speaker(constants.WHISTLE_SOUND)
                    self.stop_robots()
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    # determine the ownership based on who touched the ball last
                    touch_count = [0, 0]
                    for team in constants.TEAMS:
                        for id in range(constants.NUMBER_OF_ROBOTS):
                            if self.recent_touch[team][id]:
                                touch_count[team] += 1
                    # if recent_touch_ was red team dominant, blue team gets the ball
                    if touch_count[constants.TEAM_RED] > touch_count[constants.TEAM_BLUE]:
                        self.ball_ownership = constants.TEAM_BLUE
                    elif touch_count[constants.TEAM_BLUE] > touch_count[constants.TEAM_RED]:  # the other way around
                        self.ball_ownership = constants.TEAM_RED
                    else:  # otherwise, the attacking team gets an advantage
                        self.ball_ownership = constants.TEAM_BLUE if ball_x < 0 else constants.TEAM_RED
                    # happened on the left side
                    if ball_x < 0:  # if the red gets the ball, proceed to goalkick
                        if self.ball_ownership == constants.TEAM_RED:
                            self.game_state = Game.STATE_GOALKICK
                            self.goalkick_time = self.time
                            self.reset(constants.FORMATION_GOALKICK_A, constants.FORMATION_GOALKICK_D)
                            self.lock_all_robots(True)
                            self.robot[self.ball_ownership][0]['active'] = True
                            self.reset_reason = constants.GOALKICK
                        else:  # otherwise, proceed to corner kick
                            self.game_state = Game.STATE_CORNERKICK
                            self.cornerkick_time = self.time
                            if ball_y > 0:  # upper left corner
                                self.reset(constants.FORMATION_CAD_AD, constants.FORMATION_CAD_AA)
                            else:  # lower left corner
                                self.reset(constants.FORMATION_CBC_AD, constants.FORMATION_CBC_AA)
                            self.lock_all_robots(True)
                            self.robot[self.ball_ownership][4]['active'] = True
                            self.reset_reason = constants.CORNERKICK
                    else:  # cornerkick happened on the right side
                        if self.ball_ownership == constants.TEAM_BLUE:  # if the blue gets the ball, proceed to goalkick
                            self.game_state = Game.STATE_GOALKICK
                            self.goalkick_time = self.time
                            self.reset(constants.FORMATION_GOALKICK_D, constants.FORMATION_GOALKICK_A)
                            self.lock_all_robots(True)
                            self.robot[self.ball_ownership][0]['active'] = True
                            self.reset_reason = constants.GOALKICK
                        else:  # otherwise, proceed to corenerkick
                            self.game_state = Game.STATE_CORNERKICK
                            self.cornerkick_time = self.time
                            if ball_y > 0:  # upper right corner
                                self.reset(constants.FORMATION_CBC_AA, constants.FORMATION_CBC_AD)
                            else:  # lower right corner
                                self.reset(constants.FORMATION_CAD_AA, constants.FORMATION_CAD_AD)
                            self.lock_all_robots(True)
                            self.robot[self.ball_ownership][4]['active'] = True
                            self.reset_reason = constants.CORNERKICK
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    self.sound_speaker(constants.WHISTLE_SOUND)

                # check if any of robots should return to the field
                for team in constants.TEAMS:
                    for id in range(constants.NUMBER_OF_ROBOTS):
                        # sentout time of 0 is an indicator that the robot is currently on the field
                        if self.robot[team][id]['sentout_time'] == 0:
                            continue
                        # if a robot has been sent out and constants.SENTOUT_DURATION_MS has passed,
                        # return the robot back to the field
                        if self.time - self.robot[team][id]['sentout_time'] >= constants.SENTOUT_DURATION_MS:
                            # if any object is located within 1.5 * robot_size, the return is delayed
                            s = 1 if team == constants.TEAM_RED else -1
                            x = self.default_formation[team][id][0] * s
                            y = self.default_formation[team][id][1] * s
                            r = 1.5 * constants.ROBOT_SIZE[id]
                            if not self.any_object_nearby(x, y, r):
                                self.robot[team][id]['active'] = True
                                self.return_to_field(team, id)
                                self.robot[team][id]['sentout_time'] = 0
                ball_x = self.get_ball_position()[0]
                if self.check_penalty_area():  # if the penalty area reset condition is met
                    # the ball ownership is already set by check_penalty_area()
                    self.sound_speaker(constants.WHISTLE_SOUND)
                    self.stop_robots()
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    if ball_x < 0 and self.ball_ownership == constants.TEAM_RED:
                        # proceed to goal kick by Team Red
                        self.game_state = Game.STATE_GOALKICK
                        self.reset_reason = constants.GOALKICK
                        self.goalkick_time = self.time
                        self.reset(constants.FORMATION_GOALKICK_A, constants.FORMATION_GOALKICK_D)
                        self.lock_all_robots(True)
                        self.robot[self.ball_ownership][0]['active'] = True
                    elif ball_x > 0 and self.ball_ownership == constants.TEAM_BLUE:
                        # proceed to goal kick by Team Blue
                        self.game_state = Game.STATE_GOALKICK
                        self.reset_reason = constants.GOALKICK
                        self.goalkick_time = self.time
                        self.reset(constants.FORMATION_GOALKICK_D, constants.FORMATION_GOALKICK_A)
                        self.lock_all_robots(True)
                        self.robot[self.ball_ownership][0]['active'] = True
                    elif ball_x < 0 and self.ball_ownership == constants.TEAM_BLUE:
                        # proceed to penalty kick by Team Blue
                        self.game_state = Game.STATE_PENALTYKICK
                        self.reset_reason = constants.PENALTYKICK
                        self.penaltykick_time = self.time
                        self.reset(constants.FORMATION_PENALTYKICK_D, constants.FORMATION_PENALTYKICK_A)
                        self.lock_all_robots(True)
                        self.robot[self.ball_ownership][4]['active'] = True
                    else:  # proceed to penalty kick by Team Red
                        self.game_state = Game.STATE_PENALTYKICK
                        self.reset_reason = constants.PENALTYKICK
                        self.penaltykick_time = self.time
                        self.reset(constants.FORMATION_PENALTYKICK_A, constants.FORMATION_PENALTYKICK_D)
                        self.lock_all_robots(True)
                        self.robot[self.ball_ownership][4]['active'] = True
                    if self.step(constants.WAIT_STABLE_MS) == -1:
                        break
                    self.sound_speaker(constants.WHISTLE_SOUND)

                if self.reset_reason == constants.NONE and deadlock_flag:
                    if self.get_ball_velocity() >= constants.DEADLOCK_THRESHOLD:
                        self.deadlock_time = self.time

                    elif self.time - self.deadlock_time >= constants.DEADLOCK_DURATION_MS:
                        self.sound_speaker(constants.WHISTLE_SOUND)
                        # if the ball is not moved fast enough for constants.DEADLOCK_DURATION_MS
                        ball_x = self.get_ball_position()[0]
                        ball_y = self.get_ball_position()[1]
                        # if the deadlock happened in special region
                        if abs(ball_x) > constants.FIELD_LENGTH / 2 - constants.PENALTY_AREA_DEPTH:
                            # if the deadlock happened inside the penalty area
                            if abs(ball_y) < constants.PENALTY_AREA_WIDTH / 2:
                                self.ball_ownership = self.get_pa_ownership()
                                self.stop_robots()
                                if self.step(constants.WAIT_STABLE_MS) == -1:
                                    break
                                if ball_x < 0 and self.ball_ownership == constants.TEAM_RED:  # proceed to goal kick by Team Red
                                    self.game_state = Game.STATE_GOALKICK
                                    self.reset_reason = constants.GOALKICK
                                    self.goalkick_time = self.time
                                    self.reset(constants.FORMATION_GOALKICK_A, constants.FORMATION_GOALKICK_D)
                                    self.lock_all_robots(True)
                                    self.robot[self.ball_ownership][0]['active'] = True
                                elif ball_x > 0 and self.ball_ownership == constants.TEAM_BLUE:
                                    # proceed to goal kick by Team Blue
                                    self.game_state = Game.STATE_GOALKICK
                                    self.reset_reason = constants.GOALKICK
                                    self.goalkick_time = self.time
                                    self.reset(constants.FORMATION_GOALKICK_D, constants.FORMATION_GOALKICK_A)
                                    self.lock_all_robots(True)
                                    self.robot[self.ball_ownership][0]['active'] = True
                                elif ball_x < 0 and self.ball_ownership == constants.TEAM_BLUE:
                                    # proceed to penalty kick by Team Blue
                                    self.game_state = Game.STATE_PENALTYKICK
                                    self.reset_reason = constants.PENALTYKICK
                                    self.penaltykick_time = self.time
                                    self.reset(constants.FORMATION_PENALTYKICK_D, constants.FORMATION_PENALTYKICK_A)
                                    self.lock_all_robots(True)
                                    self.robot[self.ball_ownership][4]['active'] = True
                                else:  # proceed to penalty kick by Team Red
                                    self.game_state = Game.STATE_PENALTYKICK
                                    self.reset_reason = constants.PENALTYKICK
                                    self.penaltykick_time = self.time
                                    self.reset(constants.FORMATION_PENALTYKICK_A, constants.FORMATION_PENALTYKICK_D)
                                    self.lock_all_robots(True)
                                    self.robot[self.ball_ownership][4]['active'] = True
                                if self.step(constants.WAIT_STABLE_MS) == -1:
                                    break
                                self.sound_speaker(constants.WHISTLE_SOUND)
                                self.deadlock_time = self.time

                            else:  # if the deadlock happened in the corner regions
                                # set the ball ownership
                                self.ball_ownership = self.get_corner_ownership()
                                self.stop_robots()
                                if self.step(constants.WAIT_STABLE_MS) == -1:
                                    break
                                self.game_state = Game.STATE_CORNERKICK
                                self.cornerkick_time = self.time
                                # determine where to place the robots and the ball
                                if ball_x < 0:  # on Team Red's side
                                    if ball_y > 0:  # on upper side
                                        if self.ball_ownership == constants.TEAM_RED:  # ball owned by Team Red
                                            self.reset(constants.FORMATION_CAD_DA, constants.FORMATION_CAD_DD)
                                        else:  # // ball owned by Team Blue
                                            self.reset(constants.FORMATION_CAD_AD, constants.FORMATION_CAD_AA)
                                    else:  # on lower side
                                        if self.ball_ownership == constants.TEAM_RED:  # ball owned by Team Red
                                            self.reset(constants.FORMATION_CBC_DA, constants.FORMATION_CBC_DD)
                                        else:  # ball owned by Team Blue
                                            self.reset(constants.FORMATION_CBC_AD, constants.FORMATION_CBC_AA)
                                else:  # on Team Blue's side
                                    if ball_y > 0:  # on upper side
                                        if self.ball_ownership == constants.TEAM_RED:  # ball owned by Team Red
                                            self.reset(constants.FORMATION_CBC_AA, constants.FORMATION_CBC_AD)
                                        else:  # ball owned by Team Blue
                                            self.reset(constants.FORMATION_CBC_DD, constants.FORMATION_CBC_DA)
                                    else:  # on lower side
                                        if self.ball_ownership == constants.TEAM_RED:  # ball owned by Team Red
                                            self.reset(constants.FORMATION_CAD_AA, constants.FORMATION_CAD_AD)
                                        else:  # ball owned by Team Blue
                                            self.reset(constants.FORMATION_CAD_DD, constants.FORMATION_CAD_DA)

                                self.lock_all_robots(True)
                                self.robot[self.ball_ownership][4]['active'] = True
                                if self.step(constants.WAIT_STABLE_MS) == -1:
                                    break
                                self.reset_reason = constants.CORNERKICK
                                self.deadlock_time = self.time
                                self.sound_speaker(constants.WHISTLE_SOUND)

                        else:  # if the deadlock happened in the general region, relocate the ball and continue the game
                            self.stop_robots()
                            if self.step(constants.WAIT_STABLE_MS) == -1:
                                break
                            # determine where to relocate and relocate the ball
                            if ball_x < 0:  # Team Red's region
                                if ball_y > 0:  # upper half
                                    self.relocate_ball(constants.BALL_RELOCATION_A)
                                else:  # lower half
                                    self.relocate_ball(constants.BALL_RELOCATION_B)
                            else:  # Team Blue's region
                                if ball_y > 0:  # upper half
                                    self.relocate_ball(constants.BALL_RELOCATION_C)
                                else:  # lower half
                                    self.relocate_ball(constants.BALL_RELOCATION_D)
                            self.flush_touch_ball()
                            if self.step(constants.WAIT_STABLE_MS) == -1:
                                break
                            self.reset_reason = constants.DEADLOCK
                            self.deadlock_time = self.time
                            self.sound_speaker(constants.WHISTLE_SOUND)

            elif self.game_state == Game.STATE_KICKOFF:
                if self.time - self.kickoff_time >= constants.KICKOFF_TIME_LIMIT_MS or self.robot[self.ball_ownership][4]['touch']:
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                else:
                    ball_x = self.ball_position[0]
                    ball_y = self.ball_position[1]
                    if ball_x * ball_x + ball_y * ball_y > constants.KICKOFF_BORDER * constants.KICKOFF_BORDER:
                        self.game_state = Game.STATE_DEFAULT
                        self.lock_all_robots(False)
                self.deadlock_time = self.time

            elif self.game_state == Game.STATE_GOALKICK:
                if self.time - self.goalkick_time >= constants.GOALKICK_TIME_LIMIT_MS:  # time limit has passed
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                elif self.robot[self.ball_ownership][0]['touch']:  # the goalie has touched the ball
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                self.deadlock_time = self.time
            elif self.game_state == Game.STATE_CORNERKICK:
                if self.time - self.cornerkick_time >= constants.CORNERKICK_TIME_LIMIT_MS:  # time limit has passed
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                else:  # a robot has touched the ball
                    for id in range(constants.NUMBER_OF_ROBOTS):
                        if self.robot[self.ball_ownership][id]['touch']:
                            self.game_state = Game.STATE_DEFAULT
                            self.lock_all_robots(False)
                self.deadlock_time = self.time
            elif self.game_state == Game.STATE_PENALTYKICK:
                if self.time - self.penaltykick_time >= constants.PENALTYKICK_TIME_LIMIT_MS:  # time limit has passed
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                elif self.robot[self.ball_ownership][4]['touch']:  # the attacker has touched the ball
                    self.game_state = Game.STATE_DEFAULT
                    self.lock_all_robots(False)
                self.deadlock_time = self.time
            if self.step(self.timeStep, runTimer=True) == -1:
                break

        if record:
            # Stop game recording
            print('Saving the recorded game as: {}'.format(record_fullpath))
            print('Please wait until the message \033[36m\"INFO: Video creation finished.\"\033[0m is shown.')
            sys.stdout.flush()
            self.movieStopRecording()


controller = GameSupervisor()
controller.run()
