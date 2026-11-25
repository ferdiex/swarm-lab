"""
agent.py - the controller of every robot of your team.
swarm-lab template version 4 (swarm check compares it with the installed one)

The simulator calls act(percepts, memory, params) 10 times per simulated
second for each of your robots. All robots of the team run this same code;
each one has its own `memory` (a dict that is kept between calls).

percepts (what the robot senses; nothing else is available):
  ir        8 proximity values 0..1 (0: nothing within 7 cm, 1: touching).
            0 front right, 1 right-front, 2 right, 3 back right,
            4 back left, 5 left, 6 left-front, 7 front left
  ground    3 raw floor readings: ~855 floor, ~470 gray U, ~170 black U
  on_food   True when the robot stands on ITS OWN food (its team's U)
  hat       my hat in this match: "blue" at home (left U) or "orange" away
            (right U). It changes from match to match: never write the color.
  sound     loudness of all the robots sounding, both teams together
            (about 0.5 per sounding robot far away, more when one is close)
  leds      robots with an LED on that the camera sees (60 cm, +-40 deg),
            nearest first; each one: {"bearing": rad (+ left), "distance": m,
            "hat": its hat ("blue" or "orange"),
            "led": "green" (body LED: a beacon on its food) or "red" (LED ring: a relay)}
  time, dt  seconds since the start, seconds per step (0.1)

memory: memory["rng"] is this robot's random number generator (use it, not
the random module, so that runs repeat with the same seed); memory["id"].

params: the values of team.json (flat keys, e.g. params["signals.relays"]).

act() returns {"left": -1..1, "right": -1..1, "led": "off"/"green"/"red",
"sound": bool}: wheel speeds as fractions of the maximum speed, the LED that
other cameras will see (the green body LED or the red LED ring of the e-puck)
and whether the robot sounds.

Two roles use the signals (swarm man signals):
  beacon  on its own food: green body LED and sound
  relay   stopped outside the food, blocked next to a light: red LED ring, silent

The base behavior is built in layers (subsumption): each layer, from the
top, either decides what to do or lets the layer below decide.

  5 food     on my food: go in until blocked, stop, be a beacon (green, sound)
  4 relay    I am a relay: stay stopped with the red LED ring on
  3 light    a lit LED in view: go towards it; blocked next to it: become a relay
  2 sound    louder than usual: follow the loudness (run and tumble)
  1 wall     now and then, follow a touched wall for a few seconds
  0 explore  avoid obstacles, turn at random, escape when stuck

There are 4 sections to complete below (# >>> COMPLETE n ... # <<< COMPLETE n).
The template runs as it is; complete at least 2 of them. `swarm check` tells
you which ones you changed.
"""
from swarm.helpers import (braitenberg, follow_wall, forward, front, maneuver, rear, spin,
                           start_maneuver, stop, turn_around, LEFT, RIGHT)


def act(percepts, memory, params):
    if "state" not in memory:
        start(memory, params)
    t, dt = percepts["time"], percepts["dt"]
    memory["t_no_signal"] += dt

    wheels = (layer_food(percepts, memory, params)
              or layer_relay(percepts, memory, params)
              or layer_light(percepts, memory, params)
              or layer_sound(percepts, memory, params)
              or layer_wall(percepts, memory, params)
              or layer_explore(percepts, memory, params))
    return {"left": wheels[0], "right": wheels[1], "led": memory["led"], "sound": memory["sound"]}


def start(memory, params):
    memory.update(state="explore", led="off", sound=False,
                  t_relay=0.0, t_food=0.0, blocked=0.0,
                  ignore_signals_until=-1.0, t_no_signal=0.0, unstuck=0,
                  loud=[], sound_levels=[], tumble_until=-1.0, t_klino=-10.0,
                  next_wander=memory["rng"].uniform(params["behavior.wander_min"], params["behavior.wander_max"]),
                  wall_until=-1.0, wall_side=1, t_front=0.0, maneuver=None)


def be_beacon(memory, params):
    """On my food: LED green and sound (each one if team.json allows it)."""
    memory["led"] = "green" if params["signals.light_on_food"] else "off"
    memory["sound"] = bool(params["signals.sound_on_food"])


def be_relay(memory):
    """Stopped outside the food: red LED ring, silent."""
    memory["led"], memory["sound"] = "red", False


def signals_off(memory):
    memory["led"], memory["sound"] = "off", False


# --- 5 food ----------------------------------------------------------------------
def layer_food(percepts, memory, params):
    ir, t = percepts["ir"], percepts["time"]
    if memory["state"] == "food":
        if params["signals.make_room"] and rear(ir) > 0.3 and front(ir) < 0.15 and percepts["on_food"]:
            return forward(0.3)                       # someone behind, room ahead: move in
        return stop()
    if memory["state"] == "filling":                  # on the food: go on until blocked
        if front(ir) > 0.3 or t - memory["t_food"] > 8.0:
            memory["state"] = "food"
            return stop()
        return (0.5 * (1 + 0.6 * (ir[6] + ir[7] - ir[0] - ir[1])),
                0.5 * (1 + 0.6 * (ir[0] + ir[1] - ir[6] - ir[7])))
    if percepts["on_food"]:
        memory["state"], memory["t_food"] = "filling", t
        be_beacon(memory, params)                     # green: "here is the food"
        return stop()
    return None


# --- 4 relay -----------------------------------------------------------------------
def layer_relay(percepts, memory, params):
    if memory["state"] != "relay":
        return None
    memory["t_relay"] += percepts["dt"]               # how long I have been a relay

    # >>> COMPLETE 2: your own unstick.
    # How long I have been a relay --->  memory["t_relay"]   (seconds)
    # Missing: after how many seconds do I give up?
    # Hint: replace None with a number of seconds (swarm man relay_timeout
    # explains the same idea as a parameter).
    give_up_after = None                              # seconds; None: never give up
    if give_up_after is not None and memory["t_relay"] > give_up_after:
        return give_up(percepts, memory, params)
    # <<< COMPLETE 2

    timeout = params["signals.relay_timeout"]
    if timeout > 0 and memory["t_relay"] > timeout:
        return give_up(percepts, memory, params)
    return stop()


def give_up(percepts, memory, params):
    """Stop being a relay: LED ring off, turn away, explore, ignore signals for a while."""
    t, ir, rng = percepts["time"], percepts["ir"], memory["rng"]
    memory["state"] = "explore"
    signals_off(memory)
    memory["ignore_signals_until"] = t + params["signals.unstick_ignore"]
    memory["unstuck"] += 1

    # >>> COMPLETE 4: leave the cluster towards the side with fewer obstacles.
    # Now the robot turns to a random side (+1 left, -1 right) to get away.
    # The IR sensors of each side --->  RIGHT = (0, 1, 2)   LEFT = (7, 6, 5)
    # Hint: remove the # of the three lines below and replace ... with the
    # same sum for the LEFT side.
    side = 1 if rng.random() < 0.5 else -1
    # right = sum(ir[k] for k in RIGHT)        # how much my right side feels
    # left = ...                               # and my left side
    # side = 1 if right > left else -1         # +1: turn left, away from the right
    # <<< COMPLETE 4

    start_maneuver(memory, t, [(rng.uniform(0.8, 1.6), spin(side))])   # turn away first
    return spin(side)


def become_relay(memory):
    memory["state"], memory["t_relay"], memory["blocked"] = "relay", 0.0, 0.0
    be_relay(memory)
    return stop()


# --- 3 light -----------------------------------------------------------------------
def visible_lights(percepts, params):
    lights = percepts["leds"]

    # >>> COMPLETE 1: follow only the lights of my own team.
    # Now every lit LED attracts this robot, the rival's too, so it may end up
    # waiting as a relay at the rival's U.
    # Each light carries the hat of the robot that lights it: light["hat"].
    # My own hat in this match is --->  percepts["hat"]
    # Hint: remove the # of the line below and replace ... with MY OWN hat.
    # Do not write "blue" or "orange": my hat changes from match to match.
    # lights = [light for light in lights if light["hat"] == ...]
    # <<< COMPLETE 1

    return lights


def layer_light(percepts, memory, params):
    t, ir = percepts["time"], percepts["ir"]
    if not params["signals.follow_light"] or t < memory["ignore_signals_until"]:
        return None
    lights = visible_lights(percepts, params)
    if not lights:
        memory["blocked"] = 0.0
        return None
    light = lights[0]                                 # the nearest one
    memory["t_no_signal"] = 0.0
    memory["state"] = "light"
    b, dist = light["bearing"], light["distance"]
    beacon = light["led"] == "green"                  # that robot is on its food
    near = max(ir) > 0.25
    memory["blocked"] = memory["blocked"] + percepts["dt"] if near else 0.0
    park = params["signals.park_time"]
    # very close to a relay: stop next to it; towards a beacon: keep going
    # (there may be room on the food) unless really blocked
    join = dist < params["signals.join_dist"] and not beacon
    stuck = memory["blocked"] > (2 * park if beacon else park) and dist < 0.25
    if (join or stuck) and params["signals.relays"]:
        if not beacon and not params["signals.join_relays"]:   # only next to a beacon: go round
            rng = memory["rng"]
            memory["ignore_signals_until"] = t + rng.uniform(3, 6)
            memory["blocked"] = 0.0
            side = 1 if rng.random() < 0.5 else -1
            start_maneuver(memory, t, [(1.0, spin(side))])
            return spin(side)
        return become_relay(memory)
    k = params["behavior.light_gain"]
    att = (0.7 - k * b, 0.7 + k * b)
    if near:                                          # blend in the avoidance, do not obey it
        w = params["behavior.light_avoid"] if dist < 0.25 else 0.6
        av = braitenberg(ir)
        return (1 - w) * att[0] + w * av[0], (1 - w) * att[1] + w * av[1]
    return att


# --- 2 sound -----------------------------------------------------------------------
def layer_sound(percepts, memory, params):
    t, dt, ir = percepts["time"], percepts["dt"], percepts["ir"]
    memory["loud"].append(percepts["sound"])
    del memory["loud"][:-20]                          # last 2 s
    if len(memory["loud"]) >= 10 and int(round(t / dt)) % 10 == 0:
        memory["sound_levels"].append(sum(memory["loud"][-10:]) / 10)   # 1-s mean, once per second
        del memory["sound_levels"][:-10]                                # last 10 s
    if not params["signals.follow_sound"] or t < memory["ignore_signals_until"]:
        return None
    heard = [v for v in memory["sound_levels"] if v > 0]
    if len(memory["loud"]) < 20 or not heard or percepts["sound"] <= 0:
        return None
    usual = min(heard)                                # the quietest 1-s level of the last 10 s
    now = sum(memory["loud"][-10:]) / 10
    before = sum(memory["loud"][-20:-10]) / 10
    near = max(ir) > 0.25
    if now < usual * params["behavior.sound_local"]:
        return None
    memory["t_no_signal"] = 0.0
    if t < memory["tumble_until"]:                    # tumbling: keep turning
        return spin(memory["side"])
    if now < before * 0.97 and t - memory["t_klino"] > 1.0:   # getting quieter: tumble
        rng = memory["rng"]
        memory["side"] = 1 if rng.random() < 0.5 else -1
        memory["tumble_until"] = t + rng.uniform(0.6, 1.6)
        memory["t_klino"] = t
        return spin(memory["side"])
    memory["state"] = "sound"                         # getting louder: run
    if near:
        av = braitenberg(ir)
        return 0.5 + 0.5 * av[0], 0.5 + 0.5 * av[1]
    return forward(1.0)


# --- 1 wall ------------------------------------------------------------------------
def layer_wall(percepts, memory, params):
    t, ir, rng = percepts["time"], percepts["ir"], memory["rng"]
    if memory.get("maneuver"):
        return None
    if memory["state"] == "wall":
        if t < memory["wall_until"]:
            w = follow_wall(ir, memory["wall_side"], memory, percepts["dt"])
            if w is not None:
                return w
        memory["state"] = "explore"
    near = max(ir) > 0.25
    if near and t > memory["wall_until"] + 2.0 and rng.random() < params["behavior.wall_follow"]:
        memory["state"], memory["wall_lost"] = "wall", 0.0
        memory["wall_until"] = t + rng.uniform(5, 10)
        right, left = max(ir[1], ir[2]), max(ir[5], ir[6])
        memory["wall_side"] = -1 if right >= left else 1   # -1: wall on my right
        return follow_wall(ir, memory["wall_side"], memory, percepts["dt"])
    return None


# --- 0 explore ---------------------------------------------------------------------
def layer_explore(percepts, memory, params):
    t, ir, rng = percepts["time"], percepts["ir"], memory["rng"]
    memory["state"] = "explore"
    m = maneuver(memory, t)                           # a turn in progress
    if m is not None:
        return m
    speed = params["behavior.speed"]

    # >>> COMPLETE 3: half a turn after a long time without any signal.
    # Seconds since I last followed a light or a sound --->  memory["t_no_signal"]
    # A robot exploring the wrong half of the arena could turn back.
    # Hint: replace None with a number of seconds (the half turn and the reset
    # of the counter are already written below).
    turn_back_after = None                            # seconds; None: never
    if turn_back_after is not None and memory["t_no_signal"] > turn_back_after:
        memory["t_no_signal"] = 0.0
        return turn_around(memory, t)
    # <<< COMPLETE 3

    # escape: an obstacle right ahead for too long -> back up, then turn
    memory["t_front"] = memory["t_front"] + percepts["dt"] if front(ir) > 0.6 else 0.0
    if memory["t_front"] > params["behavior.stuck_time"]:
        memory["t_front"] = 0.0
        side = 1 if rng.random() < 0.5 else -1
        start_maneuver(memory, t, [(0.6, (-0.6, -0.6)), (0.8, spin(side))])
        return -0.6, -0.6

    if max(ir) > 0.25:
        av = braitenberg(ir)
        return speed * av[0], speed * av[1]
    if t >= memory["next_wander"]:                    # now and then, a random turn
        side = 1 if rng.random() < 0.5 else -1
        start_maneuver(memory, t, [(0.6, spin(side))])
        memory["next_wander"] = t + rng.uniform(params["behavior.wander_min"], params["behavior.wander_max"])
        return spin(side)
    return forward(speed)
