#!/usr/bin/python3

import os
import sys

def get_robot_def(team, id, uniform_num, forms):
    translations = [
        ["-3.80 0.045  0",
         "-2.25 0.045 -1",
         "-2.25 0.045  1",
         "-0.65 0.045 -0.3",
         "-0.65 0.045  0.3"],
        [" 3.80 0.045  0",
         " 2.25 0.045  1",
         " 2.25 0.045 -1",
         " 0.65 0.045  0.3",
         " 0.65 0.045 -0.3"]
    ]
    rotations = [
        ["0 1 0  0",
         "0 1 0 -1.5708",
         "0 1 0 -1.5708",
         "0 1 0 -1.5708",
         "0 1 0 -1.5708"],
        ["0 1 0  3.1415",
         "0 1 0  1.5708",
         "0 1 0  1.5708",
         "0 1 0  1.5708",
         "0 1 0  1.5708"]
    ]
    name = [
        ["R0","R1","R2","R3","R4"],
        ["B0","B1","B2","B3","B4"]
    ]
    maxspeed = ["45","52.5","52.5","63.75","63.75"]
    maxtorque = ["0.8","1.2","1.2","0.4","0.4"]
    mass = ["2.5","2.0","2.0","1.5","1.5"]
    appearance = ["DarkRed", "DarkBlue"]
    role = ["GK","D1","D2","F1","F2"]
    is_red = ["TRUE", "FALSE"]
    is_red2 = ["FALSE", "TRUE"]
    ids = ["0","31","227","364","437"]

    colors = [
        "0.02745 0.11765 0.31373",
        "1.00000 0.58039 0.00000",
        "1.00000 1.00000 1.00000",
        "1.00000 0.22353 0.31765",
        "0.00000 0.95294 1.00000",
        "0.00000 0.28627 1.00000",
        "1.00000 0.22353 0.31765",
        "0.00000 0.95294 1.00000",
        "0.00000 0.28627 1.00000",
        "1.00000 0.22353 0.31765",
        "1.00000 0.94510 0.00000",
        "1.00000 0.94510 0.00000",
    ]
    body_colors = [
        "1.00000 0.94510 0.00000",
        "1.00000 0.58039 0.00000",
        "1.00000 1.00000 1.00000",
        "0.00000 0.28627 1.00000",
        "0.00000 0.95294 1.00000",
        "1.00000 1.00000 1.00000",
        "1.00000 0.22353 0.31765",
        "0.02745 0.11765 0.31373",
        "0.00000 0.28627 1.00000",
        "0.02745 0.11765 0.31373",
        "1.00000 0.94510 0.00000",
        "0.08235 0.77255 0.96863",
    ]

    uniformnum = str(uniform_num)

    def_list = [
        "\nDEF DEF_ROBOT"+name[team][id]+" SoccerRobot_"+forms[id]+" {",
        "\n  translation "+translations[team][id],
        "\n  rotation "+rotations[team][id],
        "\n  name \""+name[team][id]+"\"",
        "\n  customData \"0 0\"",
        "\n  controller \"soccer_robot\"",
        "\n  maxSpeed "+maxspeed[id],
        "\n  slipNoise 0",
        "\n  maxTorque "+maxtorque[id],
        "\n  teamColor "+body_colors[int(uniformnum)-1],
        "\n  bodyPhysics Physics {",
        "\n    density -1",
        "\n    mass "+mass[id],
        "\n    centerOfMass [",
        "\n      0 -0.03 0",
        "\n    ]",
        "\n  }",
        "\n  bodyContactMaterial \"body\"",
        "\n  wheelContactMaterial \"wheel\"",
        "\n  patches [",
        "\n    SoccerRobotNumberPatch_"+forms[id]+" {",
        "\n      role \""+role[id]+"\"",
        "\n      isTeamTagRed "+is_red[team],
        "\n      uniformnum "+uniformnum,
        "\n      color "+colors[int(uniformnum)-1],
        "\n    }",
        "\n    SoccerRobotIDPatch {",
        "\n      id "+ids[id],
        "\n      isTeamTagRed "+is_red[team],
        "\n      name \"id_patch_red\"",
        "\n    }",
        "\n    SoccerRobotIDPatch {",
        "\n      id "+ids[id],
        "\n      isTeamTagRed "+is_red2[team],
        "\n      name \"id_patch_blue\"",
        "\n    }",
        "\n  ]",
        "\n  camBody [",
        "\n    DEF DEF_CAMBODY"+name[team][id]+" SoccerRobotCamBody {",
        "\n      height 0.095",
        "\n      bodySize 0.18",
        "\n      distanceToPatch 0.001",
        "\n    }",
        "\n  ]",
        "\n}"
    ]
    def_str = ""
    for i in range(len(def_list)):
        def_str += def_list[i]

    return def_str


forms = [[],[]]
uniform_num = [0,0]
uniform_num[0] = int(input("team_A_uniform_num (1~12): "))
while uniform_num[0] > 12 or uniform_num[0] < 1:
    print('Please retry')
    uniform_num[0] = int(input("team_A_uniform_num (1~12): "))

while True:
    cond = False
    forms[0] = input("team_A_Formation (example: LCCHB, It means GK:L/D1:C/D2:C/F1:H/F2:B) \n: ")
    if len(forms[0]) == 5:
        cond = True
        for i in range(5):
            if not forms[0][i] in ['B','C','H','L']:
                cond = False
    if cond:
        break
    else:
        print('Please retry')

uniform_num[1] = int(input("team_B_uniform_num (1~12): "))
while uniform_num[1] > 12 or uniform_num[1] < 1:
    print('Please retry')
    uniform_num[1] = int(input("team_B_uniform_num (1~12): "))

while True:
    cond = False
    forms[1] = input("team_B_Formation (example: BBHLC, It means GK:B/D1:B/D2:H/F1:L/F2:C) \n: ")
    if len(forms[1]) == 5:
        cond = True
        for i in range(5):
            if not forms[1][i] in ['B','C','H','L']:
                cond = False
    if cond:
        break
    else:
        print('Please retry')

print("team_A:", uniform_num[0], forms[0])
print("team_B:", uniform_num[1], forms[1])

file_path = "./aiwc_"+forms[0]+"vs"+forms[1]+".wbt"
if os.path.isfile(file_path):
    os.remove(file_path)
with open(file_path, "a") as fa:
    with open("./.aiwc.txt", "r") as fr:
        while True:
            line = fr.readline()
            if not line: break
            fa.write(line)
    for team in range(2):
        for id in range(5):
            add = get_robot_def(team, id, uniform_num[team], forms[team])
            fa.write(add)