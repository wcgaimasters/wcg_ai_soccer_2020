#!/usr/bin/env python3

import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant, Game, Frame
except ImportError as err:
    print('general_check-variables: \'participant\' module cannot be imported:', err)
    raise

# shortcuts
X = Frame.X
Y = Frame.Y
Z = Frame.Z
TH = Frame.TH
ACTIVE = Frame.ACTIVE
TOUCH = Frame.TOUCH
BALL_POSSESSION = Frame.BALL_POSSESSION

class CheckVariables(Participant):
    def init(self, info):
        # Here you have the information of the game (virtual init() in random_walk.cpp)
        # List: game_time, number_of_robots
        #       field, goal, penalty_area, goal_area, resolution Dimension: [x, y]
        #       ball_radius, ball_mass,
        #       robot_size, robot_height, axle_length, robot_body_mass, ID: [0, 1, 2, 3, 4]
        #       wheel_radius, wheel_mass, sliders_mass ID: [0, 1, 2, 3, 4]
        #       max_linear_velocity, max_torque, codewords, ID: [0, 1, 2, 3, 4]
        self.game_time = info['game_time']
        self.number_of_robots = info['number_of_robots']

        self.field = info['field']
        self.goal = info['goal']
        self.penalty_area = info['penalty_area']
        self.goal_area = info['goal_area']
        self.resolution = info['resolution']

        self.ball_radius = info['ball_radius']
        self.ball_mass = info['ball_mass']

        self.robot_size = info['robot_size']
        self.robot_height = info['robot_height']
        self.axle_length = info['axle_length']
        self.robot_body_mass = info['robot_body_mass']

        self.wheel_radius = info['wheel_radius']
        self.wheel_mass = info['wheel_mass']

        self.max_linear_velocity = info['max_linear_velocity']
        self.max_torque = info['max_torque']
        self.codewords = info['codewords']

        # Print received constant variables to the console
        self.printConsole("======================================================")
        self.printConsole("Game Time: {} seconds".format(self.game_time))
        self.printConsole("# of robots: {} robots".format(self.number_of_robots))
        self.printConsole("======================================================")
        self.printConsole("Field Dimensions: {} m long, {} m wide".format(self.field[X], self.field[Y]))
        self.printConsole("Goal Dimensions: {} m deep, {} m wide".format(self.goal[X], self.goal[Y]))
        self.printConsole("Penalty Area Dimensions: {} m long, {} m wide".format(self.penalty_area[X], self.penalty_area[Y]))
        self.printConsole("Goal Area Dimensions: {} m long, {} m wide".format(self.goal_area[X], self.goal_area[Y]))
        self.printConsole("Image Resolution: {} x {}".format(self.resolution[X], self.resolution[Y]))
        self.printConsole("======================================================")
        self.printConsole("Ball Radius: {} m".format(self.ball_radius))
        self.printConsole("Ball Mass: {} kg".format(self.ball_mass))
        self.printConsole("======================================================")
        for i in range(self.number_of_robots):
            self.printConsole("Robot {}:".format(i))
            self.printConsole("  size: {} m x {} m".format(self.robot_size[i], self.robot_size[i]))
            self.printConsole("  height: {} m".format(self.robot_height[i]))
            self.printConsole("  axle length: {} m".format(self.axle_length[i]))
            self.printConsole("  body mass: {} kg".format(self.robot_body_mass[i]))
            self.printConsole("  wheel radius: {} m".format(self.wheel_radius[i]))
            self.printConsole("  wheel mass: {} kg".format(self.wheel_mass[i]))
            self.printConsole("  max linear velocity: {} m/s".format(self.max_linear_velocity[i]))
            self.printConsole("  max torque: {} N*m".format(self.max_torque[i]))
            self.printConsole("  codeword: {}".format(self.codewords[i]))
            self.printConsole("======================================================")
        
        self.set_default_formation()

    def update(self, frame):
        if (frame.reset_reason == Game.GAME_START):
            self.printConsole("Game started : {}".format(frame.time))
        elif (frame.reset_reason == Game.SCORE_MYTEAM):
            self.printConsole("My team scored : {}".format(frame.time))
            self.printConsole("Current Score: {}".format(frame.score))
        elif (frame.reset_reason == Game.SCORE_OPPONENT):
            self.printConsole("Opponent scored : {}".format(frame.time))
            self.printConsole("Current Score: {}".format(frame.score))
        elif (frame.reset_reason == Game.HALFTIME):
            self.printConsole("Halftime")
        elif (frame.reset_reason == Game.EPISODE_END):
            self.printConsole("Episode ended")
        elif (frame.reset_reason == Game.GAME_END):
            self.printConsole("Game ended.")
            return

        self.printConsole("Halftime passed? {}".format(frame.half_passed))

        if (frame.game_state == Game.STATE_KICKOFF):
            self.printConsole("Kickoff [My kickoff? {}]".format(frame.ball_ownership))
        elif (frame.game_state == Game.STATE_GOALKICK):
            self.printConsole("Goalkick [My goalkick? {}]".format(frame.ball_ownership))
        elif (frame.game_state == Game.STATE_CORNERKICK):
            self.printConsole("Cornerkick [My cornerkick? {}]".format(frame.ball_ownership))
        elif (frame.game_state == Game.STATE_PENALTYKICK):
            self.printConsole("Penaltykick [My penaltykick? {}]".format(frame.ball_ownership))

        # Check the coordinates
        myteam = frame.coordinates[Frame.MY_TEAM]
        opponent = frame.coordinates[Frame.OP_TEAM]
        ball = frame.coordinates[Frame.BALL]

        self.printConsole("======================================================")
        self.printConsole("Ball: ({}, {}, {})".format(ball[X], ball[Y], ball[Z]))
        self.printConsole("======================================================")

        # Try replace 'myteam' with 'opponent' to check opponent robots' state
        for i in range(self.number_of_robots):
            self.printConsole("Robot {}:".format(i))
            self.printConsole("  position: ({}, {}, {})".format(myteam[i][X], myteam[i][Y], myteam[i][Z]))
            self.printConsole("  orientation: {}".format(myteam[i][TH]))
            self.printConsole("  activeness: {}".format(myteam[i][ACTIVE]))
            self.printConsole("  touch: {}".format(myteam[i][TOUCH]))
            self.printConsole("  ball possession: {}".format(myteam[i][BALL_POSSESSION]))
            self.printConsole("======================================================")

    def finish(self, frame):
        # save your data if necessary before the program terminates
        print("finish() method called")

if __name__ == '__main__':
    participant = CheckVariables()
    participant.run()