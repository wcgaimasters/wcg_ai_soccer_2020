import json
import socket
import sys
from pynput import keyboard


class Frame():
    def __init__(self):
        self.time = None
        self.score = None
        self.reset_reason = None
        self.game_state = None
        self.subimages = None
        self.coordinates = None
        self.half_passed = None
        self.end_of_frame = False

    # coordinates
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

class Game():
    # reset_reason
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

    # game_state
    STATE_DEFAULT = 0
    STATE_KICKOFF = 1
    STATE_GOALKICK = 2
    STATE_CORNERKICK = 3
    STATE_PENALTYKICK = 4


class Participant():
    def __init__(self):
        self.host = sys.argv[1]
        self.port = int(sys.argv[2])
        self.key = sys.argv[3]
        self.datapath = sys.argv[4]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))


    def send(self, message, arguments=[]):
        message = 'aiwc.' + message + '("%s"' % self.key
        for argument in arguments:
            if isinstance(argument, str):  # string
                message += ', "%s"' % argument
            else:  # number
                message += ', %s' % argument
        message += ')'
        try:
            self.socket.sendall(message.encode())
        except socket.error:
            self.socket.close()
            exit(0)

    def receive(self):
        try:
            data = self.socket.recv(4096)
        except socket.error:
            self.socket.close()
            exit(0)
        if not data:  # the connection was likely closed because the simulation terminated
            exit(0)
        return data.decode()

    def create_frame_object(self, f):
        # initiate empty frame
        frame = Frame()
        if 'time' in f:
            frame.time = f['time']
        if 'score' in f:
            frame.score = f['score']
        if 'reset_reason' in f:
            frame.reset_reason = f['reset_reason']
        if 'game_state' in f:
            frame.game_state = f['game_state']
        if 'ball_ownership' in f:
            frame.ball_ownership = f['ball_ownership']
        if 'half_passed' in f:
            frame.half_passed = f['half_passed']
        if 'subimages' in f:
            frame.subimages = f['subimages']
            # TODO
            # Comment the next lines if you don't need to use the image information
            # for s in frame.subimages:
            #    received_subimages.append(SubImage(s['x'],
            #                                       s['y'],
            #                                       s['w'],
            #                                       s['h'],
            #                                       s['base64'].encode('utf8')))
            # self.image.update_image(received_subimages)
        if 'coordinates' in f:
            frame.coordinates = f['coordinates']
        if 'EOF' in f:
            frame.end_of_frame = f['EOF']

        return frame

    def init_keyboard(self):
        if self.keyboard:
            self.key_store = set()
            self.k = ''
            self.cn = 0
            self.init_values()
            self.send_controll_number()

            def handleKeyPress(key):
                try:  # single-char keys
                    self.key_store.add(key.char)
                    self.k = key.char
                except:  # other keys
                    self.key_store.add(key.name)
                    self.k = key.name

            def handleKeyRelease(key):
                try:
                    if key.char in self.key_store:
                        self.key_store.remove(key.char)
                except:
                    if key.name in self.key_store:
                        self.key_store.remove(key.name)

            listener = keyboard.Listener(on_press=handleKeyPress, on_release=handleKeyRelease)
            listener.start() # start to listen on a separate thread

    def init_values(self):
        self.rnd = 0
        self.sc = 1
        self.c_speeds = [0, 0, 0, 0]

    def set_wheel_velocity(self, left_wheel, right_wheel):
        ratio_l = 1
        ratio_r = 1
        max_linear_velocities = [1.8,2.1,2.1,2.55,2.55]
        max_linear_velocity = max_linear_velocities[self.cn]

        if (left_wheel > max_linear_velocity or right_wheel > max_linear_velocity):
            diff = max(left_wheel, right_wheel) - max_linear_velocity
            left_wheel -= diff
            right_wheel -= diff
        if (left_wheel < -max_linear_velocity or right_wheel < -max_linear_velocity):
            diff = min(left_wheel, right_wheel) + max_linear_velocity
            left_wheel -= diff
            right_wheel -= diff

        return left_wheel, right_wheel

    def set_speeds(self, speeds):
        if self.keyboard:
            wheels = 0,0
            kick, jump = 0, 0
            if 'up' in self.key_store:
                self.rnd = 1
            elif 'down' in self.key_store:
                self.rnd = -1
            else:
                self.rnd = 0
            if 'left' in self.key_store:
                wheels = -0.25,0.25
            elif 'right' in self.key_store:
                wheels = 0.25,-0.25
            else:
                wheels = 0,0
            if 'e' in self.key_store:
                self.sc = min(2.2,self.sc + 0.2)
            else:
                self.sc = max(1, self.sc - 0.2)
            if 's' in self.key_store:
                kick = 5
            elif 'd' in self.key_store:
                kick = 10
            if 'w' in self.key_store:
                jump = 10
            elif 'z' in self.key_store and self.cn == 0:
                jump = 2
            elif 'x' in self.key_store and self.cn == 0:
                jump = 1
            elif 'c' in self.key_store and self.cn == 0:
                jump = 3
            if self.k in ['1','2','3','4','5']:
                if int(self.k)-1 != self.cn:
                    self.cn = int(self.k) - 1
                    self.send_controll_number()
                    self.init_values()

            self.k = ''

            if self.rnd != 0:
                wheels = self.set_wheel_velocity(self.rnd*(self.sc + wheels[0]), self.rnd*(self.sc + wheels[1]))

            self.c_speeds = wheels[0], wheels[1], kick, jump

            speeds[4 * self.cn : 4 * self.cn + 4] = self.c_speeds

        self.send('set_speeds', speeds)

    def set_default_formation(self, formation = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]):
        self.send('default_formation', formation)
        
    def set_team_color(self, color):
        self.send('team_color', color)

    def send_controll_number(self):
        self.send('cont_num', [self.cn])

    def send_comment(self, commentary):
        self.send('commentate', commentary)

    def send_report(self, report):
        self.send('report', report)

    def printConsole(self, message):
        print(message)
        sys.__stdout__.flush()

    def check_frame(self, frame):  # you should override this method
        if frame.reset_reason == Game.GAME_END:
            return False
        return True

    def init(self, info):  # you should override this method
        print("init() method called")

    def update(self, frame):  # you should override this method
        print("update() method called")

    def finish(self, frame):  # you should override this method
        print("finish() method called")

    def run(self):
        self.send('get_info')
        info = self.receive()

        self.init(json.loads(info))

        self.keyboard = json.loads(info)['keyboard']

        self.init_keyboard()

        self.send('ready')
        data = ''
        while True:
            data += self.receive()
            if data and data[-1] == '}':  # make sure we received complete frame
                # data could contain multiple concatenated frames
                try:
                    frames = json.loads("[{}]".format(data.replace('}{', '},{')))
                    finished = False
                    for frame in frames:
                        frameObject = self.create_frame_object(frame)
                        if frame and self.check_frame(frameObject):  # return False if we need to quit
                            self.update(frameObject)
                        else:
                            self.finish(frameObject)
                            finished = True
                            break

                    if finished:
                        break
                except ValueError:
                    sys.stderr.write("Error: participant.py: Invalid JSON object.\n")
                data = ''
