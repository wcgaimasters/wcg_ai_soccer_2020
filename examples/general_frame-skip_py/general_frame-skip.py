#!/usr/bin/env python3

import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant, Game, Frame
except ImportError as err:
    print('general_frame-skip: \'participant\' module cannot be imported:', err)
    raise

from time import sleep

import threading
try:
    import queue
except ImportError:
    import Queue as queue

# shortcuts
X = Frame.X
Y = Frame.Y
Z = Frame.Z
TH = Frame.TH
ACTIVE = Frame.ACTIVE
TOUCH = Frame.TOUCH
BALL_POSSESSION = Frame.BALL_POSSESSION

class FrameSkip(Participant):
    def init(self, info):
        self.q = queue.Queue()

        self.behavior_thread = threading.Thread(target=self.frame_skip)
        self.behavior_thread.start()
        
        self.set_default_formation()

    def frame_skip(self):
        # this function runs in the behavior thread to do operations
        local_queue = queue.Queue()
        while True:
            local_queue.put(self.q.get())
            while not self.q.empty():
                local_queue.put(self.q.get())
            self.q.task_done()

            # you can ignore all frames but the most recent one,
            # or keep only resetting frames,
            # or do whatever you want.

            # this example keeps only the most recent frame.
            frame = local_queue.get()
            while not local_queue.empty():
                frame = local_queue.get()
            self.choose_behavior_which_takes_really_long_time(frame)

            if(frame.reset_reason == Game.GAME_END):
                break;

    def choose_behavior_which_takes_really_long_time(self, frame):
        if(frame.reset_reason == Game.GAME_END):
            return

        # heavy operations
        sleep(3)

        # now send data to the server.
        self.printConsole("Long operation ended.")
        return

    def update(self, frame):
        self.q.put(frame)

    def finish(self, frame):
        self.behavior_thread.join()


if __name__ == '__main__':
    participant = FrameSkip()
    participant.run()