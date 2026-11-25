"""
swarm - command line of swarm-lab.

  swarm new my_team                      a team folder from the template
  swarm check my_team                    installation, team.json, agent.py and its COMPLETE sections
  swarm man [name]                       the manual of the parameters (and percepts, action)
  swarm run my_team [--live]             one run (live 2D view with --live)
  swarm eval my_team [--seeds 1-10]      several seeds: CSV tables and a figure

Run, eval: --rival none|sparring|FOLDER, --robots, --arena, --duration and
--seeds override the "experiment" section of team.json.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_seeds(text):
    out = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


# --- new -------------------------------------------------------------------------
NAME_RULE = "up to 10 letters, digits or _"


def team_name_ok(folder):
    import re
    return re.fullmatch(r"[A-Za-z0-9_]{1,10}", os.path.basename(os.path.abspath(folder))) is not None


def template_version(path):
    """The number in the line 'swarm-lab template version N' of an agent.py, or None."""
    import re
    m = re.search(r"swarm-lab template version (\d+)", open(path).read())
    return int(m.group(1)) if m else None


def cmd_new(a):
    if os.path.exists(a.folder):
        sys.exit(f"{a.folder} already exists; choose another name")
    if not team_name_ok(a.folder):
        sys.exit(f"'{os.path.basename(a.folder)}' is not a valid team name: {NAME_RULE}")
    shutil.copytree(os.path.join(HERE, "template"), a.folder,
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(f"created {a.folder}/ with team.json and agent.py")
    name = os.path.basename(os.path.abspath(a.folder))
    print(f'"{name}" is your team\'s name: it appears in the view and in the tournament')
    print(f"(to rename the team, rename the folder)   next: swarm check {a.folder}")


# --- sections to complete ----------------------------------------------------------
def complete_regions(text, keep_comments=True):
    """{n: text between '# >>> COMPLETE n' and '# <<< COMPLETE n'} (whitespace-normalized).
    keep_comments=False drops comment lines and end-of-line comments (to look at the code)."""
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        s = line.strip()
        if not keep_comments and not s.startswith("# >>>") and not s.startswith("# <<<"):
            s = s.split("#", 1)[0].strip()
        if s.startswith("# >>> COMPLETE"):
            cur, buf = int(s.split()[3].rstrip(":")), []
        elif s.startswith("# <<< COMPLETE") and cur is not None:
            out[cur] = " ".join(" ".join(buf).split())
            cur = None
        elif cur is not None:
            buf.append(s)
    return out


def complete_status(agent_path):
    """For each section 1-4: 'changed', 'as in the template' or 'markers missing'."""
    tmpl = complete_regions(open(os.path.join(HERE, "template", "agent.py")).read())
    mine = complete_regions(open(agent_path).read())
    out = {}
    for n in sorted(tmpl):
        if n not in mine:
            out[n] = "markers missing (keep the >>> COMPLETE / <<< COMPLETE lines)"
        elif mine[n] != tmpl[n]:
            out[n] = "changed"
        else:
            out[n] = "as in the template"
    return out


# --- check -----------------------------------------------------------------------
def cmd_check(a):
    ok = True

    def line(good, text):
        nonlocal ok
        ok = ok and good is not False
        mark = {True: "ok  ", False: "FAIL", None: "warn"}[good]
        print(f"  [{mark}] {text}")

    print("installation")
    line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (3.9 or newer)")
    for mod in ("numpy", "pybullet", "matplotlib"):
        try:
            __import__(mod)
            from importlib import metadata
            try:
                ver = metadata.version(mod)
            except metadata.PackageNotFoundError:
                ver = ""
            line(True, f"{mod} {ver}".strip())
        except Exception as e:                                   # noqa: BLE001
            line(False, f"{mod}: {e}")
    if a.folder is None:
        print("\nno team folder given (swarm check my_team)")
        return 0 if ok else 1
    print(f"\nteam {a.folder}")
    tj, ag = os.path.join(a.folder, "team.json"), os.path.join(a.folder, "agent.py")
    name = os.path.basename(os.path.abspath(a.folder))
    line(team_name_ok(a.folder), f"team name '{name}' ({NAME_RULE}; it is the folder's name)")
    for f in (tj, ag):
        line(os.path.isfile(f), f"{f} exists")
    if not ok:
        return 1
    from . import params as P
    try:
        prm, problems = P.load_team(tj)
        line(True, "team.json reads")
    except ValueError as e:
        line(False, f"team.json: {e}")
        return 1
    for pr in problems:
        line(False, f"team.json: {pr}")
    print("\nagent.py")
    from .match import Team, Match
    try:
        team = Team(a.folder)
        line(True, "agent.py loads and has act()")
    except Exception as e:                                       # noqa: BLE001
        line(False, f"agent.py does not load: {type(e).__name__}: {e}")
        return 1
    st = complete_status(ag)
    mine_v = template_version(ag)
    tmpl_v = template_version(os.path.join(HERE, "template", "agent.py"))
    if mine_v != tmpl_v:
        line(False, f"agent.py comes from template version {mine_v or 'unknown'}; the installed one is "
                    f"version {tmpl_v}. Start again with: swarm new <new folder>, then copy your "
                    f"team.json values and your COMPLETE sections by hand")
        return 1
    for n, s in st.items():
        print(f"         COMPLETE {n}: {s}")
    filled = sum(s == "changed" for s in st.values())
    line(filled >= 2 if filled >= 2 else None, f"{filled} of 4 COMPLETE sections changed (at least 2 required)")
    for n, text in complete_regions(open(ag).read(), keep_comments=False).items():
        if "..." in text:
            line(False, f"COMPLETE {n} still has a ... to fill in")
    import ast
    written = {n.value for n in ast.walk(ast.parse(open(ag).read()))
               if isinstance(n, ast.Constant) and n.value in ("blue", "orange")}
    for color in sorted(written):
        line(None, f'agent.py has "{color}" written in its code: your hat changes from match '
                   f'to match, use percepts["hat"]')
    print("\nshort run (alone, 10 s)")
    m = Match(team, None, robots=prm["experiment.robots"], arena=prm["experiment.arena"], duration=10.0, seed=1)
    t0 = time.time()
    m.run()
    wall = time.time() - t0
    err = m.failed[0]
    m.close()
    if err:
        line(False, "agent.py failed during the run:\n" + err)
    else:
        line(True, f"runs without errors ({wall:.1f} s for 10 simulated s)")
        n = len(parse_seeds(prm["experiment.seeds"]))
        est = (wall / 10 * prm["experiment.duration"] + 1.0) * n
        print(f"         estimate: swarm eval with {n} seeds takes ~{est / 60:.0f} min on one core, alone"
              f" (twice as long with a rival; --jobs N divides it by N)")
    print("\nall good" if ok else "\nfix the FAIL lines above")
    return 0 if ok else 1


# --- man -------------------------------------------------------------------------
TOPICS = {
    "layers": """layers: how the agent decides what to do (subsumption, Brooks 1986)

Ten times per second, each robot asks its layers, from the top down,
"do you have something to do now?". The first layer that says yes drives the
wheels, and the layers below it are ignored for that step. They are not
stages that run one after the other: all of them are asked at every step,
and the highest one that has something to do wins.

  layer        it acts when...                    and then it...
  5 food       I am on my food                    goes in, stops: a beacon (green LED, sound)
  4 relay      I am a relay                       stays stopped with its red LED ring on
  3 light      I see a lit LED                    goes towards it; if blocked next to it,
                                                  becomes a relay (swarm man signals)
  2 sound      it is louder than usual            follows the loudness
  1 wall       I touch a wall (sometimes)         follows the wall for a few seconds
  0 explore    always                             wanders and avoids obstacles

Examples: a robot that sees a light while touching a wall goes to the light
(layer 3 is above layer 1). A relay (layer 4) ignores lights and sounds: it
only waits. In agent.py each layer is a function: layer_food, layer_relay,
layer_light, layer_sound, layer_wall, layer_explore. Each parameter says
which layer uses it (swarm man <name>).
""",
    "signals": """signals: beacons, relays and hats

A robot shows two signals, the ones of a real e-puck 1: its LEDs and sound.
Two roles use them:

  role     where                                     LED                 sound
  beacon   on its own food (its ground sensors       green body LED      yes
           see its team's U)
  relay    outside the food, stopped because it      red LED ring        no
           stayed blocked next to a light
  others   exploring, following a wall, a sound      off                 no
           or a light

A relay passes the light on to robots that cannot see the food:

    [ U: beacons (green) ]  relay (red)  relay (red)  ...

With join_relays true, a robot may become a relay next to another relay, so
relays can line up without limit. With false, only next to a beacon.

Hats: robots are not colored. Like home and away shirts, the match puts a
hat on every robot: BLUE for the team whose food is the left U (gray, home)
and ORANGE for the team whose food is the right U (black, away). Teams do
not choose it: in practice your team plays at home (blue) unless you use
--swap, and in the tournament every match is played twice, once on each
side. On real robots the hat would be a colored cover, as used with the
Khepera robots. A robot knows its own hat: percepts["hat"].

The camera of every robot reports, for each robot with an LED on in view:
its hat (whose it is) and its LED (beacon or relay). The microphone hears all
the sounds together and cannot tell whose they are. Robots do not see
states, only these signals.

Only the robots inside their U at the end count. A robot stopped at the
mouth of its U, a relay or one still exploring does not count.
""",
    "jam": """jam: how robots get stuck (the problem to fix)

1. The first robots reach their U, stop on the food and become beacons
   (green body LED, sound).
2. Other robots see the light and come. The mouth of the U gets crowded.
   A robot that stays blocked next to a light stops outside the food and
   becomes a relay (red LED ring), to pass the light on (swarm man signals).
3. In the template, once a robot is a relay it stays a relay until the end,
   and relays keep forming next to relays without any limit. Relays stopped
   at the mouth of the U plug it: the robots behind them cannot get in, so
   they become relays too, and the plug grows.
4. The beacons that did get in stop where they first touch the food, near
   the mouth, and leave the back of the U empty.

The life of a relay, and the parameters of each moment:

  moment                   parameter        the question it answers
  are there relays at all  relays           may a blocked robot become a relay?
  becoming a relay         join_dist        how close to a relay before stopping?
                           park_time        how long blocked next to a light?
  next to whom             join_relays      next to a relay too, or only a beacon?
  leaving                  relay_timeout    how long a relay before giving up?
  after leaving            unstick_ignore   how long to ignore lights and sounds?

To see it: swarm run my_team --live. To measure it: swarm eval my_team.
"stopped outside" counts the robots that moved less than 2 cm in the last
10 s and are not in their U. Some parameters prevent the jam: find them.
""",
    "percepts": """percepts (the dict agent.py receives)
    ir        8 proximity values 0..1 (0: nothing within 7 cm, 1: touching)
              0 front right, 1 right-front, 2 right, 3 back right,
              4 back left, 5 left, 6 left-front, 7 front left
              (helpers: RIGHT = (0, 1, 2), LEFT = (7, 6, 5), front(ir), rear(ir))
    ground    3 raw floor readings (left, center, right): ~855 plain floor,
              ~470 gray U (left), ~170 black U (right), with noise
    on_food   True when at least 2 ground sensors are on YOUR team's U
    hat       my hat in this match: "blue" at home (left U), "orange" away
              (right U). It changes between matches: never write the color.
    sound     loudness of every robot sounding, both teams together, no
              direction: ~0.5 per sounding robot beyond 30 cm, 1.0 at 5 cm,
              +-20 % noise; a U wall in between lowers it
    leds      robots with an LED on that the camera sees (60 cm, +-40 deg,
              not through walls or robots), nearest first. Each: bearing
              [rad, + left], distance [m], hat ("blue" or "orange") and led
              ("green": body LED, a beacon on its food; "red": LED ring, a relay)
    time      seconds since the start;  dt  seconds per step (0.1)
""",
    "action": """action (the dict act() returns)
    left, right   wheel speeds, -1..1 (fraction of the maximum, the same for all teams)
    led           "off", "green" (the body LED) or "red" (the LED ring). The base agent:
                  green as a beacon on its food, red as a relay. Every camera sees
                  it, with your hat
    sound         True: sound (everybody hears it, nobody knows whose it is)
""",
    "memory": """memory (the dict agent.py keeps per robot)
    memory["rng"]  this robot's random generator: memory["rng"].random(),
                   .uniform(a, b). Use it (not the random module) so that a run
                   repeats exactly with the same seed.
    memory["id"]   robot number. Anything else you store stays there.
""",
}


def cmd_man(a):
    from . import params as P
    if a.name in TOPICS:
        print(TOPICS[a.name])
        return 0
    print(P.man(a.name))
    return 0


# --- run / eval --------------------------------------------------------------------
def settings(a):
    """Experiment settings: team.json, overridden by the command line."""
    from . import params as P
    prm, problems = P.load_team(os.path.join(a.folder, "team.json"))
    if problems:
        sys.exit("team.json has problems (see swarm check):\n  " + "\n  ".join(problems))
    s = {k.split(".", 1)[1]: v for k, v in prm.items() if k.startswith("experiment.")}
    for k in ("robots", "arena", "duration", "seeds", "rival"):
        v = getattr(a, k, None)
        if v is not None:
            s[k] = v
    return s


def make_teams(folder, rival):
    from .match import Team, sparring_folder
    a = Team(folder)
    if rival in ("none", "", None):
        b = None
    elif rival == "sparring":
        b = Team(sparring_folder(), "sparring")
    else:
        b = Team(rival)
    return a, b


def one_run(args):
    """Worker: one seed. Returns (summary, robot log)."""
    folder, rival, s, seed, swap = args
    from .match import Match
    a, b = make_teams(folder, rival)
    m = Match(a, b, robots=s["robots"], arena=s["arena"], duration=s["duration"], seed=seed, swap=swap)
    res = m.run()
    log = m.robot_log()
    for row in log:
        row["seed"] = seed
    m.close()
    return res, log


def cmd_run(a):
    s = settings(a)
    seed = a.seed if a.seed is not None else parse_seeds(s["seeds"])[0]
    from .match import Match
    ta, tb = make_teams(a.folder, s["rival"])
    m = Match(ta, tb, robots=s["robots"], arena=s["arena"], duration=s["duration"], seed=seed, swap=a.swap)
    print(f"{ta.name} vs {tb.name if tb else 'nobody'}: {s['robots']} robots each, arena {s['arena']} m, "
          f"{s['duration']:.0f} s, seed {seed}")
    if a.live:
        from .view import live
        live(m)
    else:
        t0 = time.time()
        m.run()
        print(f"({time.time() - t0:.0f} s)")
    if a.snapshot:
        import matplotlib
        matplotlib.use("Agg")
        from .view import MatchView
        MatchView(m).save(a.snapshot)
        print("snapshot:", a.snapshot)
    print_summary(m.summary())
    for k, err in enumerate(m.failed):
        if err:
            print(f"\nERROR in {m.teams[k].name}/agent.py (its robots stopped):\n{err}")
    m.close()
    return 0


def print_summary(r):
    for tag in ("a", "b"):
        if f"{tag}_team" not in r:
            continue
        print(f"  {r[tag + '_team']:12s} in its U {r[tag + '_in_u']:2d}   stopped outside {r[tag + '_stopped_outside']:2d}"
              f"   in the rival's U {r[tag + '_in_rival_u']:2d}   first {r[tag + '_first_s']} s"
              f"   time to 5: {r[tag + '_time_to_5']} s")


def cmd_eval(a):
    s = settings(a)
    seeds = parse_seeds(s["seeds"])
    out = a.out or os.path.join("results", os.path.basename(os.path.abspath(a.folder)))
    os.makedirs(out, exist_ok=True)
    jobs = [(a.folder, s["rival"], s, sd, a.swap) for sd in seeds]
    print(f"{len(seeds)} seeds, {s['robots']} robots, arena {s['arena']} m, {s['duration']:.0f} s, "
          f"rival {s['rival']}, {a.jobs} at a time -> {out}/")
    t0 = time.time()
    results = []
    if a.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.jobs) as ex:
            for (res, log) in ex.map(one_run, jobs):
                results.append((res, log))
                print(f"  seed {res['seed']:3d}: in its U {res['a_in_u']:2d}, stopped outside "
                      f"{res['a_stopped_outside']:2d}  ({time.time() - t0:.0f} s)", flush=True)
    else:
        for j in jobs:
            res, log = one_run(j)
            results.append((res, log))
            print(f"  seed {res['seed']:3d}: in its U {res['a_in_u']:2d}, stopped outside "
                  f"{res['a_stopped_outside']:2d}  ({time.time() - t0:.0f} s)", flush=True)
    runs = [r for r, _ in results]
    robots = [row for _, log in results for row in log]
    write_csv(os.path.join(out, "runs.csv"), runs)
    write_csv(os.path.join(out, "robots.csv"), robots)
    summ = summarize(runs)
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump({"settings": s, "seeds": seeds, "summary": summ}, f, indent=2)
    figure(runs, s, os.path.join(out, "eval.png"))
    print("\nmean +- standard deviation over the seeds")
    for team, d in summ.items():
        print(f"  {team:12s} in its U {d['in_u_mean']:.2f} +- {d['in_u_sd']:.2f}   "
              f"stopped outside {d['stopped_outside_mean']:.2f} +- {d['stopped_outside_sd']:.2f}   "
              f"reached 5 in {d['reached_5']} of {len(runs)} runs")
    print(f"\ntables: {out}/runs.csv, {out}/robots.csv, {out}/summary.json   figure: {out}/eval.png")
    return 0


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def summarize(runs):
    import numpy as np
    out = {}
    for tag in ("a", "b"):
        if f"{tag}_team" not in runs[0]:
            continue
        name = runs[0][f"{tag}_team"]
        u = np.array([r[f"{tag}_in_u"] for r in runs], float)
        st = np.array([r[f"{tag}_stopped_outside"] for r in runs], float)
        out[name] = {"in_u_mean": float(u.mean()), "in_u_sd": float(u.std(ddof=1)) if len(u) > 1 else 0.0,
                     "stopped_outside_mean": float(st.mean()),
                     "stopped_outside_sd": float(st.std(ddof=1)) if len(st) > 1 else 0.0,
                     "reached_5": sum(r[f"{tag}_time_to_5"] is not None for r in runs),
                     "errors": sum(bool(r[f"{tag}_error"]) for r in runs)}
    return out


def figure(runs, s, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    seeds = [r["seed"] for r in runs]
    x = np.arange(len(runs))
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    u = [r["a_in_u"] for r in runs]
    st = [r["a_stopped_outside"] for r in runs]
    ax.bar(x - 0.2, u, 0.4, color="#2f6db5", label=f"in its U (mean {np.mean(u):.1f})")
    ax.bar(x + 0.2, st, 0.4, color="#d08a2a", label=f"stopped outside (mean {np.mean(st):.1f})")
    ax.set_xticks(x)
    ax.set_xticklabels([str(sd) for sd in seeds])
    ax.set_xlabel("seed")
    ax.set_ylabel("robots at the end")
    ax.set_ylim(0, s["robots"] + 0.5)
    ax.set_title(f"{runs[0]['a_team']}: {s['robots']} robots, {s['duration']:.0f} s, rival {s['rival']}", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --- main ------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(prog="swarm", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="a team folder from the template")
    p.add_argument("folder")
    p = sub.add_parser("check", help="installation, team.json, agent.py and its COMPLETE sections")
    p.add_argument("folder", nargs="?")
    p = sub.add_parser("man", help="manual of the parameters; topics: layers, signals, jam, percepts, action, memory")
    p.add_argument("name", nargs="?")
    for name in ("run", "eval"):
        p = sub.add_parser(name, help="one run" if name == "run" else "several seeds: tables and a figure")
        p.add_argument("folder")
        p.add_argument("--rival", help="none, sparring or a team folder (default: team.json)")
        p.add_argument("--robots", type=int, help="robots per team")
        p.add_argument("--arena", type=float, help="arena side [m]")
        p.add_argument("--duration", type=float, help="simulated seconds")
        p.add_argument("--swap", action="store_true", help="exchange the two U (your team gets the right one)")
        if name == "run":
            p.add_argument("--seed", type=int, help="default: the first seed of team.json")
            p.add_argument("--live", action="store_true", help="live 2D view")
            p.add_argument("--snapshot", metavar="PNG", help="save a picture of the end of the run")
        else:
            p.add_argument("--seeds", help="e.g. 1-10 or 1,3,5 (default: team.json)")
            p.add_argument("--jobs", type=int, default=1, help="runs at a time (one per core)")
            p.add_argument("--out", help="folder for the results (default: results/<team>)")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    return {"new": cmd_new, "check": cmd_check, "man": cmd_man, "run": cmd_run, "eval": cmd_eval}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
