"""Smoke tests: python tests/test_smoke.py (about 30 s)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from swarm import params as P                              # noqa: E402
from swarm.cli import complete_regions, parse_seeds            # noqa: E402
from swarm.match import Match, Team, check_action, sparring_folder   # noqa: E402

TEMPLATE = os.path.join(ROOT, "swarm", "template")


def test_template_matches_registry():
    prm, problems = P.load_team(os.path.join(TEMPLATE, "team.json"))
    assert problems == [], problems
    assert prm == P.defaults(), "template team.json differs from the defaults in params.py"


def test_sparring_is_the_template():
    a = open(os.path.join(TEMPLATE, "agent.py")).read()
    b = open(os.path.join(sparring_folder(), "agent.py")).read()
    assert a == b, "swarm/sparring/agent.py must be a copy of swarm/template/agent.py"
    assert open(os.path.join(TEMPLATE, "team.json")).read() == \
        open(os.path.join(sparring_folder(), "team.json")).read()


def test_four_complete_sections():
    assert sorted(complete_regions(open(os.path.join(TEMPLATE, "agent.py")).read())) == [1, 2, 3, 4]


def test_action_clipping():
    a = check_action({"left": 3, "right": -2, "led": "red", "sound": 1})
    assert a == {"left": 1.0, "right": -1.0, "led": "red", "sound": True}
    try:
        check_action({"left": 0, "right": 0, "led": 2})
        raise AssertionError("a bad led must raise")
    except ValueError:
        pass


def test_old_team_json():
    import tempfile
    d = tempfile.mkdtemp()
    open(os.path.join(d, "team.json"), "w").write('{"color": "blue", "signals": {"beacon_timeout": 30}}')
    _, problems = P.load_team(os.path.join(d, "team.json"))
    assert any("relay_timeout" in pr for pr in problems), problems
    assert any("hat" in pr for pr in problems), problems


def test_hats():
    for swap, hats in ((False, ("blue", "orange")), (True, ("orange", "blue"))):
        a, b = Team(TEMPLATE, "template"), Team(sparring_folder(), "sparring")
        m = Match(a, b, robots=2, arena=1.5, duration=0.5, seed=1, swap=swap)
        assert (a.hat, b.hat) == hats
        pc = m.make_percepts(0, m.sensors[0].read(m.handles[0]))
        assert pc["hat"] == hats[0]
        m.close()


def test_template_version_and_names():
    from swarm.cli import team_name_ok, template_version
    assert template_version(os.path.join(TEMPLATE, "agent.py")) is not None
    assert team_name_ok("my_team") and team_name_ok("/x/Lobos_2")
    assert not team_name_ok("way_too_long_name") and not team_name_ok("mi-equipo")


def test_seeds():
    assert parse_seeds("1-3,7") == [1, 2, 3, 7]


def test_match_runs_and_repeats():
    out = []
    for _ in range(2):
        a, b = Team(TEMPLATE, "template"), Team(sparring_folder(), "sparring")
        m = Match(a, b, robots=4, arena=1.5, duration=10.0, seed=3)
        t0 = time.time()
        out.append(m.run())
        print(f"  4 vs 4, 10 s: {time.time() - t0:.1f} s")
        assert m.failed == [None, None], m.failed
        poses = [tuple(round(v, 6) for v in m.pose(i)) for i in range(m.n)]
        out.append(poses)
        m.close()
    assert out[0] == out[2] and out[1] == out[3], "the same seed must give the same run"


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
