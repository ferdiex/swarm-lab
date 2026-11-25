"""
params.py - every parameter a team can set in team.json, with its manual
entry (swarm man), and the loader of team.json (JSON with // comments).

Each entry: default, range [low, high] (or choices), the layer of the agent
it acts on, what it does, and what happens when it goes up or down.
"""
import json
import re

# parameters renamed or removed since the first versions (to tell old team.json
# files what changed, instead of "unknown parameter")
RENAMED = {"signals.beacon_timeout": "signals.relay_timeout", "signals.max_chain": "signals.join_relays"}
REMOVED = {"color": "teams no longer choose a color: the match gives each team a hat, blue at "
                    "home (left U) and orange away (right U). Delete the \"color\" line"}

P = {}


def _p(key, default, rng, layer, what, up="", down="", choices=None):
    P[key] = {"default": default, "range": rng, "choices": choices, "layer": layer,
              "what": what, "up": up, "down": down}


# --- signals --------------------------------------------------------------------
_p("signals.light_on_food", True, None, "5 food",
   "A robot on its food becomes a beacon: it lights its green body LED.",
   "true: robots that see the green light can go straight to the food, the rival's too.",
   "false: your food is invisible to cameras; only sound (if on) and relays recruit.")
_p("signals.sound_on_food", True, None, "5 food",
   "A beacon (a robot on its food) also sounds. Relays do not. Sound is shared: every "
   "robot hears the sum of all sounds, and nobody can tell which team made them.",
   "true: helps your robots near the food, and the rival's robots near it too.",
   "false: silent; the rival cannot use your sound.")
_p("signals.follow_light", True, None, "3 light",
   "Steer towards robots with an LED on (green body or red ring) seen by the camera "
   "(which teams: COMPLETE 1 in agent.py).",
   "true: fast recruitment when a light is in view (60 cm, +-40 deg).",
   "false: lights are ignored; robots rely on sound and exploration.")
_p("signals.follow_sound", True, None, "2 sound",
   "Follow the loudness by run and tumble when it is louder than usual.",
   "true: robots close to sounding robots (~25 cm) find them.",
   "false: sound is ignored.")
_p("signals.relays", True, None, "3 light",
   "A robot that is blocked next to a light stops outside the food and lights its red "
   "LED ring: a relay. Relays pass the light on to robots that cannot see the food.",
   "true: the light reaches farther, but stopped robots can plug the U.",
   "false: nobody stops outside the food; robots keep pushing.")
_p("signals.join_relays", True, None, "3 light",
   "May a robot become a relay next to another relay (red), or only next to a "
   "beacon (green)? With true, relays line up one behind another without limit.",
   "relays also form next to relays: long lines of relays.",
   "relays form only next to a beacon; a robot that meets a relay goes round it.")
_p("signals.join_dist", 0.13, [0.06, 0.25], "3 light",
   "Distance [m] to a relay at which a robot stops and becomes a relay too.",
   "larger: relays farther apart, more robots stop early.",
   "smaller: robots get closer before stopping.")
_p("signals.park_time", 1.5, [0.5, 5.0], "3 light",
   "Seconds a robot must stay blocked next to a light before it becomes a relay.",
   "larger: robots push longer before stopping.",
   "smaller: robots stop sooner (more relays, more plugs).")
_p("signals.relay_timeout", 0.0, [0.0, 120.0], "4 relay",
   "Unstick: a relay that has been stopped longer than this [s] gives up, switches its "
   "LED ring off and explores again. 0: never (a relay stays a relay forever).",
   "relays guide longer, but a plug lasts longer.",
   "plugs dissolve quickly, but relays leave before they help. Careful: 0 is not "
   "'smaller', it means never.")
_p("signals.unstick_ignore", 8.0, [0.0, 30.0], "4 relay, 3 light, 2 sound",
   "Seconds a robot that just gave up as a relay ignores lights and sounds, so it "
   "does not go back to the same plug at once.",
   "it wanders away longer before paying attention again.",
   "(0) it may go straight back to the same plug.")
_p("signals.make_room", False, None, "5 food",
   "A beacon (on its food) that feels someone behind it and has room ahead moves "
   "deeper into the U, so the ones behind can get in.",
   "the U fills from the back.",
   "robots stop where they first touch the food, often at the mouth of the U.")

# --- behavior -------------------------------------------------------------------
_p("behavior.speed", 1.0, [0.3, 1.0], "0 explore",
   "Cruise speed, as a fraction of the maximum (the maximum is the same for every team).",
   "faster: covers more floor, more collisions.",
   "slower: fewer collisions, slower to arrive.")
_p("behavior.wall_follow", 0.3, [0.0, 1.0], "1 wall",
   "Probability per step of starting to follow a wall it touches (for 5-10 s). "
   "Following walls is what takes robots round the U into its opening.",
   "larger: more wall following.",
   "smaller (0): never follows walls; bounces off them.")
_p("behavior.wander_min", 2.0, [0.5, 10.0], "0 explore",
   "Shortest time [s] between two random turns while exploring.",
   "larger: longer straight runs.",
   "smaller: more turning, more local search.")
_p("behavior.wander_max", 6.0, [1.0, 20.0], "0 explore",
   "Longest time [s] between two random turns while exploring.",
   "larger: longer straight runs.",
   "smaller: more turning, more local search.")
_p("behavior.stuck_time", 1.5, [0.5, 5.0], "0 explore",
   "Seconds with an obstacle right ahead before the robot backs up and turns (escape).",
   "larger: pushes longer against obstacles.",
   "smaller: escapes sooner.")
_p("behavior.light_gain", 1.5, [0.5, 3.0], "3 light",
   "How hard the robot steers towards a light (per radian of bearing).",
   "larger: sharper turns towards the light.",
   "smaller: smoother approach, may overshoot.")
_p("behavior.light_avoid", 0.35, [0.0, 1.0], "3 light",
   "Close to a light (< 25 cm), how much obstacle avoidance is blended into the "
   "steering (0: none, 1: only avoidance).",
   "larger: avoids neighbors more, pushes less.",
   "smaller: pushes towards the light through the crowd.")
_p("behavior.sound_local", 1.15, [1.0, 2.0], "2 sound",
   "The sound is followed only when it is this many times louder than the usual "
   "level (the quietest 1-s level of the last 10 s).",
   "larger: only very near sounds are followed.",
   "smaller: robots react to faint changes (mostly noise).")

# --- experiment (practice runs; the tournament uses its own fixed settings) ---------
_p("experiment.robots", 10, [1, 15], "-",
   "Robots per team in swarm run / swarm eval (the tournament uses 15).")
_p("experiment.arena", 1.5, [1.2, 2.0], "-",
   "Side of the square arena [m] (the tournament uses 2.0).")
_p("experiment.duration", 150.0, [30.0, 300.0], "-",
   "Simulated seconds per run (the tournament uses 300).")
_p("experiment.seeds", "1-10", None, "-",
   "Seeds for swarm eval, e.g. 1-10 or 1,3,5. Same seed = same start positions and noise.")
_p("experiment.rival", "none", None, "-",
   "Rival team: 'none' (your team alone: the cleanest way to study the jam), 'sparring' "
   "(the red team that comes with swarm-lab, the template unchanged) or the path to a team folder.")


# --- team.json ------------------------------------------------------------------

def strip_comments(text):
    """Remove // comments (outside strings) so json can read the file."""
    out = []
    for line in text.splitlines():
        in_str, esc, cut = False, False, None
        for k, ch in enumerate(line):
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = not in_str
            elif ch == "/" and not in_str and line[k + 1:k + 2] == "/":
                cut = k
                break
        out.append(line if cut is None else line[:cut])
    text = "\n".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", text)          # allow a trailing comma


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def defaults():
    return {k: e["default"] for k, e in P.items()}


def load_team(path):
    """Read team.json: returns (flat params with defaults filled in, problems).
    Problems are strings; an unreadable file raises ValueError."""
    with open(path) as f:
        raw = f.read()
    try:
        data = json.loads(strip_comments(raw))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: line {e.lineno}, column {e.colno}: {e.msg}") from None
    flat = flatten(data)
    problems = []
    params = defaults()
    for key, v in flat.items():
        if key.startswith("evolve.") or key.startswith("_"):
            params[key] = v
            continue
        if key in REMOVED:
            problems.append(f"'{key}': {REMOVED[key]}")
            continue
        if key not in P:
            if key in RENAMED:
                problems.append(f"'{key}' is now called '{RENAMED[key]}' (see: swarm man {RENAMED[key].split('.')[-1]})")
            else:
                problems.append(f"unknown parameter '{key}' (typo? see: swarm man)")
            continue
        e = P[key]
        d = e["default"]
        if isinstance(d, bool):
            if not isinstance(v, bool):
                problems.append(f"{key} must be true or false, not {v!r}")
                continue
        elif isinstance(d, (int, float)) and not isinstance(d, bool):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                problems.append(f"{key} must be a number, not {v!r}")
                continue
            lo, hi = e["range"]
            if not lo <= v <= hi:
                problems.append(f"{key} = {v} is outside its range [{lo}, {hi}]")
                continue
            if isinstance(d, int):
                v = int(round(v))
        if e["choices"] and v not in e["choices"]:
            problems.append(f"{key} = {v!r}: choose one of {', '.join(e['choices'])}")
            continue
        params[key] = v
    return params, problems


# --- swarm man ------------------------------------------------------------------

GROUPS = [("signals", "signals: what the robots show and how they react to it"),
          ("behavior", "behavior: how the robots move"),
          ("experiment", "experiment: practice runs (swarm run, swarm eval)")]


def _labels(e):
    d = e["default"]
    if isinstance(d, bool):
        return "if true: ", "if false:", ("true: ", "false: ")
    return "if larger: ", "if smaller:", ("larger: ", "smaller: ", "faster: ", "slower: ", "smaller (0): ")


def _strip(text, prefixes):
    for pre in prefixes:
        if text.startswith(pre):
            return text[len(pre):]
    return text


def _range(e):
    if e["choices"]:
        return "one of: " + ", ".join(e["choices"])
    if e["range"]:
        return f"from {e['range'][0]} to {e['range'][1]}"
    return "true or false" if isinstance(e["default"], bool) else "text"


SHORT = {
    "signals.light_on_food": "on the food, be a beacon: green body LED",
    "signals.sound_on_food": "a beacon also sounds",
    "signals.follow_light": "go towards lit LEDs (green or red)",
    "signals.follow_sound": "follow the loudness",
    "signals.relays": "blocked next to a light: stop and be a relay (red LED ring)",
    "signals.join_relays": "become a relay next to a relay too (not only a beacon)",
    "signals.join_dist": "how close to a relay before stopping next to it",
    "signals.park_time": "how long blocked next to a light before becoming a relay",
    "signals.relay_timeout": "how long a relay waits before giving up (0: never)",
    "signals.unstick_ignore": "after giving up, how long to ignore signals",
    "signals.make_room": "a beacon moves deeper into the U when someone is behind",
    "behavior.speed": "cruise speed: 1.0 is the maximum, 8 cm/s",
    "behavior.wall_follow": "chance per step of following a wall it touches",
    "behavior.wander_min": "shortest time between random turns",
    "behavior.wander_max": "longest time between random turns",
    "behavior.stuck_time": "how long against an obstacle before backing up",
    "behavior.light_gain": "how hard to steer towards a light (per radian off course)",
    "behavior.light_avoid": "near a light: 0 push straight to it, 1 only avoid neighbors",
    "behavior.sound_local": "how much louder than usual before following the sound",
    "experiment.robots": "robots per team (tournament: 15)",
    "experiment.arena": "arena side (tournament: 2.0)",
    "experiment.duration": "seconds per run (tournament: 300)",
    "experiment.seeds": "seeds for swarm eval, e.g. 1-10 or 1,3,5",
    "experiment.rival": "none, sparring or a team folder",
}


UNITS = {
    "signals.light_on_food": "yes/no", "signals.sound_on_food": "yes/no",
    "signals.follow_light": "yes/no", "signals.follow_sound": "yes/no", "signals.relays": "yes/no",
    "signals.join_relays": "yes/no", "signals.join_dist": "m", "signals.park_time": "s",
    "signals.relay_timeout": "s", "signals.unstick_ignore": "s", "signals.make_room": "yes/no",
    "behavior.speed": "x 8 cm/s", "behavior.wall_follow": "chance 0-1", "behavior.wander_min": "s",
    "behavior.wander_max": "s", "behavior.stuck_time": "s", "behavior.light_gain": "per rad",
    "behavior.light_avoid": "mix 0-1", "behavior.sound_local": "times",
    "experiment.robots": "robots", "experiment.arena": "m", "experiment.duration": "s",
    "experiment.seeds": "", "experiment.rival": "",
}


def short(key):
    return SHORT[key]


def overview():
    out = ["swarm man - the manual of the parameters of team.json", "",
           "  swarm man <name>     one parameter in detail, e.g.  swarm man park_time",
           "  swarm man layers     how the agent decides what to do (read this first)",
           "  swarm man signals    beacons (green), relays (red) and hats (blue, orange)",
           "  swarm man jam        how robots get stuck",
           "  swarm man percepts   what a robot senses;   also: action, memory", ""]
    out.append("parameter        default  unit        what it is")
    for prefix, title in GROUPS:
        out += ["", title]
        for k, e in P.items():
            if k.startswith(prefix + "."):
                name = k.split(".", 1)[1]
                out.append(f"  {name:15s} {json.dumps(e['default']):8s} {UNITS[k]:11s} {short(k)}")
    return "\n".join(out)


def man(key=None):
    if key is None:
        return overview()
    keys = [k for k in P if key == k or k.endswith("." + key)] or [k for k in P if key in k]
    if not keys:
        return f"no parameter matches '{key}'. The list: swarm man"
    out = []
    for k in keys:
        e = P[k]
        up_label, down_label, prefixes = _labels(e)
        out += [k,
                f"    used by layer:  {e['layer']}   (swarm man layers)",
                f"    default:        {json.dumps(e['default'])} {UNITS[k]}".rstrip(),
                f"    values:         {_range(e)}",
                f"    what it does:   {_wrap(e['what'], 20)}"]
        if e["up"]:
            out.append(f"    {up_label:15s} {_wrap(_strip(e['up'], prefixes), 20)}")
        if e["down"]:
            out.append(f"    {down_label:15s} {_wrap(_strip(e['down'], prefixes), 20)}")
        out.append("")
    return "\n".join(out)


def _wrap(text, indent, width=88):
    import textwrap
    lines = textwrap.wrap(text, width - indent)
    return ("\n" + " " * indent).join(lines)
