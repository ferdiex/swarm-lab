"""
match.py - one match: two teams of e-pucks, each racing to its own U.

Arena: a square (1.2-2 m) with a U-shaped enclosure near the left and the
right wall, both opening to the center. The inside of the left U is gray and
the inside of the right U is black. Team A's food is the left U and team B's
the right one (swap=True exchanges them). Start positions are random but
mirrored left-right: every robot of B is as far from its U as its twin of A.

team_b may be None: team A alone in the arena (practice).

Each robot is controlled by its team's agent.py:

    act(percepts, memory, params) -> {"left", "right", "led", "sound"}

Hats: the match puts a colored hat on every robot, like a home and an away
shirt: blue for the team whose food is the left U (home), orange for the
team whose food is the right U (away). A robot knows its own hat
(percepts["hat"]). Signals are the LEDs of a real e-puck 1: the green body
LED (a beacon on its food) and the red LED ring (a relay). The camera
reports, for each robot with an LED on in view, its hat and which LED is on.

called 10 times per simulated second. The agent only gets its percepts (see
make_percepts); it never sees positions or the rival's state.

If an agent raises an error, all robots of its team stop (wheels, LED and
sound off) for the rest of the match and the error is recorded.
"""
import importlib.util
import math
import os
import traceback

import numpy as np

from . import params as P
from .helpers import MAX_SPEED

HERE = os.path.dirname(os.path.abspath(__file__))
WHEEL_RADIUS = 0.02
HZ = 10.0
FOV = math.radians(40)           # camera half-angle (the real e-puck camera is about 56 deg wide)
LIGHT_RANGE = 0.6                # m
U_WIDTH, U_DEPTH, U_WALL = 0.40, 0.34, 0.02
GRAY_REFL, BLACK_REFL = 0.55, 0.20
BLACK_MAX, GRAY_MAX = 320.0, 650.0      # ground readings: below BLACK_MAX black, below GRAY_MAX gray
STOPPED_WINDOW, STOPPED_DIST = 10.0, 0.02
LEDS = ("off", "green", "red")         # off, green body LED (beacon), red LED ring (relay)
HATS = ("blue", "orange")              # hat of the team whose food is the left U, the right U

_LOUD = np.loadtxt(os.path.join(HERE, "data", "sound_loudness_2292.csv"), delimiter=",", skiprows=1)


def loudness(d):
    """Relative loudness at distance d [m], measured on e-puck 2292: halves from
    5 to 30 cm and is flat beyond (room reverberation)."""
    return float(np.interp(100 * d, _LOUD[:, 0], _LOUD[:, 1]))


def normalize_ir(raw):
    """Raw IR -> 0..1 proximity (0: nothing within 7 cm, 1: touching)."""
    from .sim.sensors import IR_LOOKUP
    far = IR_LOOKUP[-1, 1]
    thr = far * (1 + 3 * IR_LOOKUP[-1, 2])
    out = np.zeros(8)
    for k, r in enumerate(raw):
        if r > thr:
            d = float(np.interp(r, IR_LOOKUP[::-1, 1], IR_LOOKUP[::-1, 0]))
            out[k] = np.clip(1 - d / 0.07, 0, 1)
    return out


class Team:
    """A team folder: team.json (parameters) and agent.py (act)."""

    def __init__(self, folder, name=None):
        self.folder = os.path.abspath(folder)
        self.name = name or os.path.basename(self.folder.rstrip("/"))
        self.params, self.problems = P.load_team(os.path.join(self.folder, "team.json"))
        self.hat = None                    # set by the match: blue (left U) or orange (right U)
        self.agent = load_module(os.path.join(self.folder, "agent.py"), f"agent_{self.name}_{id(self)}")
        if not hasattr(self.agent, "act"):
            raise ValueError(f"{self.folder}/agent.py has no function act(percepts, memory, params)")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sparring_folder():
    return os.path.join(HERE, "sparring")


class Match:
    def __init__(self, team_a, team_b=None, robots=10, arena=1.5, duration=150.0, seed=1, swap=False, target=5):
        import pybullet as p
        from .sim import world as W
        from .sim.sensors import EpuckSensors, FloorMap
        self.p, self.W = p, W
        self.teams = [team_a, team_b]
        self.robots_per_team, self.arena, self.duration = robots, arena, duration
        self.seed, self.swap, self.target = seed, swap, target
        self.rng = np.random.default_rng(seed)
        cfg = W.load_config()
        cfg["world"]["arena_size"] = arena
        cfg["world"]["wall_height"] = 0.09
        self.cfg, self.half = cfg, arena / 2
        self.client = W.setup_physics(cfg, gui=False)
        W.build_arena(cfg)
        self.u_walls, self.wall_rects, self.food_rects, self.boxes = [], [], [], []
        for side in (-1, 1):
            self._build_u(side)
        self.floor = FloorMap(cfg["floor"]["reflectance"])
        self.u_refl = [GRAY_REFL, BLACK_REFL]                  # left U gray, right U black
        self.u_band = [(BLACK_MAX, GRAY_MAX), (0.0, BLACK_MAX)]
        for (x0, x1, y0, y1), rf in zip(self.food_rects, self.u_refl):
            self.floor.add_rect(x0, x1, y0, y1, rf)
        self.own_u = [1, 0] if swap else [0, 1]                 # index of each team's U
        for k, team in enumerate(self.teams):
            if team is not None:
                team.hat = HATS[self.own_u[k]]
        er = cfg["epuck"]["ir_rays"]
        self.handles, self.sensors, self.team_of = [], [], []
        for k, (x, y, yaw) in self._starts(robots):
            h = W.load_epuck(cfg, lean=True)
            W.place_robot(h, cfg, x, y, yaw)
            h["led"], h["sound"] = "off", False
            self.handles.append(h)
            self.team_of.append(k)
            self.sensors.append(EpuckSensors(
                self.floor, noise=cfg["sensors"]["noise"],
                rng=np.random.default_rng(self.rng.integers(1 << 31)),
                n_rays=er["n_rays"], aperture=er["aperture"], gaussian_width=er["gaussian_width"]))
        self.ts = cfg["world"]["timestep"]
        self.n_phys = max(1, int(round(1.0 / HZ / self.ts)))
        for _ in range(30):
            p.stepSimulation()
        self.n = len(self.handles)
        self.memory = []
        for i in range(self.n):
            self.memory.append({"id": i, "rng": np.random.default_rng(self.rng.integers(1 << 31))})
        self.noise_rng = np.random.default_rng(seed + 2000)
        self.t = 0.0
        self.failed = [None, None]                              # error text per team
        self.arrived = [None] * self.n                          # first time on its own food
        self.on_food = [False] * self.n                         # on its own food at the last step
        self.signal_time = [0.0] * self.n                       # time signaling while not on the food
        self.track = [[] for _ in range(self.n)]                # (t, x, y) for the stopped test
        self.history = []                                       # (t, in U team A, in U team B)
        self.last_actions = [None] * self.n

    # --- arena ------------------------------------------------------------------
    def _build_u(self, side):
        W = self.W
        t, h = U_WALL / 2, 0.045
        w = U_WIDTH / 2 + t
        x_back = side * (self.half - 0.07)
        x_open = x_back - side * (U_DEPTH + t)
        xm, hx = (x_back + x_open) / 2, abs(x_open - x_back) / 2
        rgba = (0.82, 0.82, 0.82, 1.0)
        self.u_walls += [W._make_wall([x_back, 0, h], [t, w + t, h], color=rgba),
                         W._make_wall([xm, w, h], [hx, t, h], color=rgba),
                         W._make_wall([xm, -w, h], [hx, t, h], color=rgba)]
        self.wall_rects += [(x_back - t, -w - t, 2 * t, 2 * (w + t)),
                            (xm - hx, w - t, 2 * hx, 2 * t), (xm - hx, -w - t, 2 * hx, 2 * t)]
        self.food_rects.append((x_back - side * t, x_open, -(w - t), w - t))
        self.boxes.append((min(x_open, x_back), max(x_open, x_back), -w, w))

    def _starts(self, n):
        lim = self.half - 0.10

        def free(x, y):
            return all(not (x0 - 0.10 <= x <= x1 + 0.10 and y0 - 0.10 <= y <= y1 + 0.10)
                       for x0, x1, y0, y1 in self.boxes)
        pts, spacing, tries = [], 0.11, 0
        while len(pts) < 2 * n:
            tries += 1
            if tries % 20000 == 0:
                spacing = max(0.085, spacing - 0.01)
            x, y = self.rng.uniform(0.06, lim), self.rng.uniform(-lim, lim)
            if self.rng.random() < 0.5:
                x = -x
            cand = [(x, y), (-x, y)]
            if free(x, y) and abs(2 * x) > spacing and \
                    all(math.hypot(cx - px, cy - py) > spacing for cx, cy in cand for px, py, _ in pts):
                yaw = float(self.rng.uniform(-math.pi, math.pi))
                pts.append((float(x), float(y), yaw))
                pts.append((float(-x), float(y), math.pi - yaw))
        # team A takes the first of each mirrored pair and team B the twin; with
        # swap the twins exchange too, so each robot keeps the same distance to its own U
        a, b = (0, 1) if not self.swap else (1, 0)
        out = [(0, pts[2 * k + a]) for k in range(n)]
        if self.teams[1] is not None:
            out += [(1, pts[2 * k + b]) for k in range(n)]
        return out

    def pose(self, i):
        x, y, yaw = self.W.get_pose(self.handles[i])[:3]
        return x, y, yaw

    def in_u(self, i, u):
        """Robot i inside U number u: its center inside the U, or (for its own U)
        its ground sensors on the food, as at the mouth of the U."""
        x, y, _ = self.pose(i)
        x0, x1, y0, y1 = self.boxes[u]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
        return u == self.own_u[self.team_of[i]] and self.on_food[i]

    # --- perception ---------------------------------------------------------------
    def make_percepts(self, i, readings):
        """What robot i perceives: its own sensors only."""
        k = self.team_of[i]
        g = np.asarray(readings["ground"])
        lo, hi = self.u_band[self.own_u[k]]
        return {
            "ir": normalize_ir(readings["ir"]),               # 8 values 0..1 (see swarm man ir)
            "ground": g,                                      # 3 raw values: ~855 floor, ~470 gray, ~170 black
            "on_food": int(np.sum((g >= lo) & (g < hi))) >= 2,
            "hat": self.teams[k].hat,                         # my hat in this match: blue or orange
            "sound": self.hear(i),                            # loudness of all sounds together
            "leds": self.see_leds(i),                         # robots with their LED on in view, nearest first
            "time": self.t,
            "dt": 1.0 / HZ,
        }

    def hear(self, i):
        x, y, _ = self.pose(i)
        total = 0.0
        for j, h in enumerate(self.handles):
            if j == i or not h["sound"]:
                continue
            ox, oy, _ = self.pose(j)
            v = loudness(math.hypot(x - ox, y - oy))
            if self.p.rayTest([ox, oy, 0.04], [x, y, 0.04])[0][0] in self.u_walls:
                v *= 0.6                                      # a U wall in between muffles it
            total += v
        return total * (1 + self.noise_rng.normal(0, 0.2)) if total > 0 else 0.0

    def see_leds(self, i):
        x, y, yaw = self.pose(i)
        cx, cy = x + 0.045 * math.cos(yaw), y + 0.045 * math.sin(yaw)
        cand = []
        for j, h in enumerate(self.handles):
            if j == i or h["led"] == "off":
                continue
            ox, oy, _ = self.pose(j)
            d = math.hypot(ox - cx, oy - cy)
            if d > LIGHT_RANGE:
                continue
            b = (math.atan2(oy - cy, ox - cx) - yaw + math.pi) % (2 * math.pi) - math.pi
            if abs(b) > FOV:
                continue
            cand.append((d, b, j, ox, oy))
        if not cand:
            return []
        hits = self.p.rayTestBatch([[cx, cy, 0.03]] * len(cand), [[ox, oy, 0.02] for _, _, _, ox, oy in cand])
        out = []
        for (d, b, j, _, _), hit in zip(cand, hits):
            if hit[0] != self.handles[j]["id"]:
                continue
            out.append({"bearing": b, "distance": d,
                        "hat": self.teams[self.team_of[j]].hat, "led": self.handles[j]["led"]})
        out.sort(key=lambda e: e["distance"])
        return out

    # --- one control step -----------------------------------------------------------
    def step(self):
        W = self.W
        actions = []
        for i in range(self.n):
            k = self.team_of[i]
            if self.failed[k] is not None:
                actions.append(None)
                continue
            readings = self.sensors[i].read(self.handles[i])
            percepts = self.make_percepts(i, readings)
            self.on_food[i] = percepts["on_food"]
            if percepts["on_food"] and self.arrived[i] is None:
                self.arrived[i] = self.t
            try:
                act = self.teams[k].agent.act(percepts, self.memory[i], self.teams[k].params)
                actions.append(check_action(act))
            except Exception:
                self.failed[k] = traceback.format_exc(limit=-3)
                actions.append(None)
        for i, act in enumerate(actions):
            h = self.handles[i]
            if act is None or self.failed[self.team_of[i]] is not None:
                act = {"left": 0.0, "right": 0.0, "led": "off", "sound": False}
            self.last_actions[i] = act
            W.set_wheels(h, act["left"] * MAX_SPEED / WHEEL_RADIUS, act["right"] * MAX_SPEED / WHEEL_RADIUS)
            h["led"], h["led_on"], h["sound"] = act["led"], act["led"] != "off", act["sound"]
        for _ in range(self.n_phys):
            self.p.stepSimulation()
        self.t += self.n_phys * self.ts
        counts = [0, 0]
        for i in range(self.n):
            k = self.team_of[i]
            x, y, _ = self.pose(i)
            inside = self.in_u(i, self.own_u[k])
            counts[k] += inside
            h = self.handles[i]
            if (h["led"] != "off" or h["sound"]) and not inside:
                self.signal_time[i] += self.n_phys * self.ts
            tr = self.track[i]
            tr.append((self.t, x, y))
            while tr and tr[0][0] < self.t - STOPPED_WINDOW:
                tr.pop(0)
        self.history.append((self.t, counts[0], counts[1]))

    def run(self, callback=None):
        while self.t < self.duration - 1e-9:
            self.step()
            if callback:
                callback(self)
        return self.summary()

    # --- results ----------------------------------------------------------------------
    def stopped_outside(self, i):
        """Stopped (moved < 2 cm in the last 10 s) and not inside its own U."""
        tr = self.track[i]
        if self.t < STOPPED_WINDOW or not tr:
            return False
        _, x0, y0 = tr[0]
        _, x1, y1 = tr[-1]
        return math.hypot(x1 - x0, y1 - y0) < STOPPED_DIST and not self.in_u(i, self.own_u[self.team_of[i]])

    def time_to(self, k, target):
        for row in self.history:
            if row[1 + k] >= target:
                return round(row[0], 1)
        return None

    def robot_log(self):
        """One row per robot: what fitness.py and swarm eval work from."""
        rows = []
        for i in range(self.n):
            k = self.team_of[i]
            rows.append({"robot": i, "team": k,
                         "arrived_s": None if self.arrived[i] is None else round(self.arrived[i], 1),
                         "in_u": self.in_u(i, self.own_u[k]),
                         "in_rival_u": self.in_u(i, self.own_u[1 - k]),
                         "stopped_outside": self.stopped_outside(i),
                         "signal_outside_s": round(self.signal_time[i], 1)})
        return rows

    def summary(self):
        rows = self.robot_log()
        out = {"seed": self.seed, "swap": self.swap, "robots": self.robots_per_team,
               "arena": self.arena, "duration": self.duration}
        for k, tag in enumerate(("a", "b")):
            if self.teams[k] is None:
                continue
            r = [row for row in rows if row["team"] == k]
            arr = [row["arrived_s"] for row in r if row["arrived_s"] is not None]
            out.update({
                f"{tag}_team": self.teams[k].name,
                f"{tag}_in_u": sum(row["in_u"] for row in r),
                f"{tag}_in_rival_u": sum(row["in_rival_u"] for row in r),
                f"{tag}_stopped_outside": sum(row["stopped_outside"] for row in r),
                f"{tag}_first_s": min(arr) if arr else None,
                f"{tag}_time_to_{self.target}": self.time_to(k, self.target),
                f"{tag}_signal_outside_s": round(sum(row["signal_outside_s"] for row in r), 1),
                f"{tag}_error": (self.failed[k] or "").strip().splitlines()[-1] if self.failed[k] else "",
            })
        return out

    def close(self):
        try:
            self.p.disconnect(self.client)
        except Exception:
            pass


def check_action(act):
    """Accept the agent's action and clip it to the legal range."""
    if not isinstance(act, dict):
        raise TypeError(f"act() must return a dict with left, right, led, sound; it returned {act!r}")
    for key in ("left", "right"):
        if key not in act:
            raise KeyError(f"the action has no '{key}' wheel speed")
    left = float(np.clip(act["left"], -1, 1))
    right = float(np.clip(act["right"], -1, 1))
    if math.isnan(left) or math.isnan(right):
        raise ValueError("a wheel speed is NaN")
    led = act.get("led", "off") or "off"
    if led not in LEDS:
        raise ValueError(f"led must be one of {', '.join(LEDS)}, not {led!r}")
    return {"left": left, "right": right, "led": led, "sound": bool(act.get("sound", False))}
