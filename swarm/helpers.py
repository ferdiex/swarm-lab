"""
helpers.py - small building blocks for agent.py.

Wheel speeds are fractions of the maximum speed (the same for every team):
+1 full speed forward, -1 full speed backward. A side is +1 for left
(counterclockwise) and -1 for right.

  forward(speed)          both wheels forward
  stop()                  both wheels stopped
  spin(side, speed)       turn on the spot
  braitenberg(ir)         obstacle avoidance: wheel speeds from the 8 IR sensors
  follow_wall(ir, side)   keep a wall on one side
  start_maneuver(...)     a fixed sequence of wheel speeds for some seconds
  maneuver(...)           the current step of that sequence, or None
  turn_around(...)        a maneuver: half a turn on the spot
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_BR = json.load(open(os.path.join(HERE, "data", "braitenberg_avoidance.json")))
_WL, _WR = np.array(_BR["left_weights"]), np.array(_BR["right_weights"])
_BL, _BRB = _BR.get("left_bias", 0.3), _BR.get("right_bias", 0.3)
_REF = max(abs(_BL), abs(_BRB))

# e-puck geometry, to know how long a turn takes
MAX_SPEED = 0.08          # m/s, every robot of every team
AXLE = 0.052              # m, distance between the wheels

# IR sensor index -> side. 0 and 7 look ahead, 3 and 4 behind.
#   right side: 0 (front right), 1, 2 (right), 3 (back right)
#   left side:  7 (front left), 6, 5 (left), 4 (back left)
RIGHT = (0, 1, 2)
LEFT = (7, 6, 5)
FRONT = (0, 7)
REAR = (3, 4)


def forward(speed=1.0):
    return speed, speed


def stop():
    return 0.0, 0.0


def spin(side, speed=0.6):
    """Turn on the spot: side +1 left, -1 right."""
    return -speed * side, speed * side


def front(ir):
    """How close the nearest obstacle ahead is (0: nothing, 1: touching)."""
    return max(ir[0], ir[7], 0.7 * ir[1], 0.7 * ir[6])


def rear(ir):
    return max(ir[3], ir[4])


def braitenberg(ir):
    """Obstacle avoidance (Braitenberg vehicle): each IR sensor slows the wheel
    on the other side, so the robot turns away from what it feels."""
    ir = np.asarray(ir)
    vl = float(np.clip((_WL @ ir + _BL) / _REF, -1, 1))
    vr = float(np.clip((_WR @ ir + _BRB) / _REF, -1, 1))
    return vl, vr


def follow_wall(ir, side, memory, dt):
    """Keep the wall on one side (side -1: wall on the right, +1: on the left)
    at a fixed distance; at its end, turn round it. Returns wheel speeds, or
    None when the wall has been lost for more than 2.5 s."""
    p = ir
    if side < 0:
        s_near, f_near = max(0.7 * p[1], p[2]), max(p[0], p[7], 0.7 * p[1])
    else:
        s_near, f_near = max(0.7 * p[6], p[5]), max(p[0], p[7], 0.7 * p[6])
    if f_near > 0.3:                                  # wall ahead: turn away from it
        return spin(-side, 0.4)
    if s_near < 0.05:                                 # wall lost: its end, wrap round it
        memory["wall_lost"] = memory.get("wall_lost", 0.0) + dt
        if memory["wall_lost"] > 2.5:
            return None
        return (0.8, 0.25) if side < 0 else (0.25, 0.8)
    memory["wall_lost"] = 0.0
    k = float(np.clip(1.6 * (0.35 - s_near), -0.6, 0.6))   # >0: too far from the wall
    vl, vr = 0.8 * (1 + k), 0.8 * (1 - k)
    return (vl, vr) if side < 0 else (vr, vl)


def start_maneuver(memory, t, steps):
    """Run a fixed sequence of wheel speeds: steps = [(seconds, (left, right)), ...]."""
    plan, t0 = [], t
    for seconds, wheels in steps:
        t0 += seconds
        plan.append((t0, wheels))
    memory["maneuver"] = plan


def maneuver(memory, t):
    """Wheel speeds of the maneuver in progress, or None when there is none."""
    plan = memory.get("maneuver")
    while plan and t >= plan[0][0]:
        plan.pop(0)
    if not plan:
        memory["maneuver"] = None
        return None
    return plan[0][1]


def turn_time(angle, speed=0.6):
    """Seconds needed to turn `angle` radians on the spot at `speed`."""
    return abs(angle) / (2 * speed * MAX_SPEED / AXLE)


def turn_around(memory, t, side=1):
    """Half a turn on the spot (a maneuver)."""
    start_maneuver(memory, t, [(turn_time(math.pi), spin(side))])
    return spin(side)
