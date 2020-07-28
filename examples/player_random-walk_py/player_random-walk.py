#!/usr/bin/python3

import random
import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant
except ImportError as err:
    print('player_random-walk: \'participant\' module cannot be imported:', err)
    raise

class RandomWalkPlayer(Participant):
    def init(self, info):
        self.number_of_robots = info['number_of_robots']
        self.max_linear_velocity = info['max_linear_velocity']

                                #   X ,    Y ,    TH
        self.default_formation =[-3.20,  0.00, 0.00,     # GK
                                 -2.00,  0.30, 0.00,     # D1
                                 -2.00, -0.30, 0.00,     # D2
                                 -1.00,  1.00, 0.00,     # F1
                                 -1.00, -1.00, 0.00]     # F2

        self.set_default_formation(self.default_formation)

    def update(self, frame):
        speeds = []
        for i in range(self.number_of_robots):
            speeds.append(random.uniform(-self.max_linear_velocity[i], self.max_linear_velocity[i]))
            speeds.append(random.uniform(-self.max_linear_velocity[i], self.max_linear_velocity[i]))
            speeds.extend([0,0])
        self.set_speeds(speeds)

if __name__ == '__main__':
    player = RandomWalkPlayer()
    player.run()
