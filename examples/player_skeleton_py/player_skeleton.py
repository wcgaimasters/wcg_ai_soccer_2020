#!/usr/bin/python3

import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant
except ImportError as err:
    print('player_skeleton: \'participant\' module cannot be imported:', err)
    raise

class SkeletonPlayer(Participant):
    def init(self, info):
        self.number_of_robots = info['number_of_robots']
        self.max_linear_velocity = info['max_linear_velocity']

        self.set_default_formation()

    def update(self, frame):
        speeds = []
        for i in range(self.number_of_robots):
            speeds.append(self.max_linear_velocity[i])
            speeds.append(self.max_linear_velocity[i])
            speeds.extend([0,0])
        self.set_speeds(speeds)

if __name__ == '__main__':
    player = SkeletonPlayer()
    player.run()
