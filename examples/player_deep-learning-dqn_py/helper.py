import sys
import math

def distance(x1, x2, y1, y2):
    return math.sqrt(math.pow(x1 - x2, 2) + math.pow(y1 - y2, 2))

def printConsole(message):
    print(message)
    sys.__stdout__.flush()