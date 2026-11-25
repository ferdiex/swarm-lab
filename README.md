# swarm-lab

Teams of simulated e-puck robots race to their own food. Final project of
the AI course (agents, Russell and Norvig): each team writes the agent of
its robots, fixes a jam, trains its parameters and plays a tournament.

The robots are PyBullet twins of the real e-puck 1, calibrated with
[epuck-remote](https://github.com/ferdiex/epuck-remote): motion, infrared
and ground sensors, control timing and loudness against distance.

## Status

Published: the simulator, `check`, `run`, `eval`, `man`, the team template
and the jam to fix. Still being debugged: **phase 1c, training with a
learning algorithm** (`swarm optimize` with local search or evolution, and
your own `fitness.py`). It will be published as soon as it is finished; you
will get it with `git pull`.

## Install

No installation possible? Use the Google Colab notebook (no live view; your
team folder is kept in Google Drive):
[open swarm-lab in Colab](https://colab.research.google.com/github/ferdiex/swarm-lab/blob/main/colab/swarm_lab.ipynb).

With conda (Windows, macOS and Linux; no compiler needed):

```bash
git clone https://github.com/ferdiex/swarm-lab.git
cd swarm-lab
conda env create -f environment.yml
conda activate swarm-lab
pip install -e .
swarm check
```

Updates during the course: `git pull` inside the `swarm-lab` folder.

## Commands

| command | what for |
|---|---|
| `swarm new my_team` | a team folder from the template |
| `swarm check my_team` | installation, `team.json`, `agent.py` and which COMPLETE sections are done |
| `swarm man [name]` | manual of every parameter; topics: `layers`, `signals`, `jam`, `percepts`, `action`, `memory` |
| `swarm run my_team --live` | one run in a live 2D window (space: pause, + and -: speed, q: quit) |
| `swarm run my_team --snapshot end.png` | one run without a window, picture of the end |
| `swarm eval my_team --seeds 1-10 --jobs 2` | several seeds: `runs.csv`, `robots.csv`, `summary.json`, `eval.png` |

The team's name is the name of its folder (`my_team` in these examples):
up to 10 letters, digits or `_`. It appears in the view and in the
tournament; to rename a team, rename its folder.

`run` and `eval` take the settings of the `experiment` section of
`team.json`; `--rival none|sparring|FOLDER`, `--robots`, `--arena`,
`--duration`, `--seeds` and `--swap` override them. `--jobs` runs that
many seeds at a time (one per core).

## The arena

A square arena (1.5 m for practice, 2 m in the tournament) with a U-shaped
enclosure at each side, open to the center. The inside of the left U is
gray, the inside of the right U black. Your team's food is the left U
(`--swap`: the right one); a robot only recognizes its own. Start positions
are random and mirrored left to right, so each robot of one team is as far
from its U as its twin of the other team.

## The team folder

- `team.json`: every parameter you can change without programming, one per
  line with a comment (`//` comments are allowed). `swarm man <name>`
  explains each one: what it does, the layer of the agent it acts on, its
  default and range, and what happens when it is larger or smaller.
- `agent.py`: `act(percepts, memory, params)`, called 10 times per simulated
  second for each robot. Returns the wheel speeds (-1..1), the LED
  (off, green, red) and whether the robot sounds. The base agent comes in
  layers (subsumption) with four sections to complete (`# >>> COMPLETE n` ...
  `# <<< COMPLETE n`).

Percepts, the only information an agent gets:

| percept | meaning |
|---|---|
| `ir` | 8 proximity values 0..1 (7 cm range) |
| `ground` | 3 floor readings: ~855 floor, ~470 gray U, ~170 black U |
| `on_food` | on its own team's U |
| `sound` | loudness of every robot sounding, both teams together, no direction |
| `hat` | my hat in this match: blue (home, left U) or orange (away, right U) |
| `leds` | robots with an LED on in view (60 cm, +-40 deg): bearing, distance, hat, LED (green or red) |
| `time`, `dt` | seconds since the start, seconds per step (0.1) |

Two roles use the signals, the LEDs of a real e-puck 1: a **beacon** is on
its own food (green body LED, sound) and a **relay** stopped outside the
food, blocked next to a light, to pass the light on (red LED ring, silent).
Sound is shared: nobody can tell which team is sounding.

**Hats.** Teams do not choose a color. Like home and away shirts, the match
puts a hat on every robot: blue for the team whose food is the left U (home)
and orange for the team whose food is the right U (away). In practice your
team plays at home unless you use `--swap`; in the tournament every match is
played on both sides. On real robots the hat would be a colored cover. A
robot knows its own hat (`percepts["hat"]`); never write the color in your
code. The camera reports the hat and the LED of every robot with an LED on
in view; following only your own team, spying on the rival or ignoring it
is up to your agent.

**Only the robots inside their U at the end count.** At the end, the live
view shows the robots that do not count in gray.

`swarm run --live` is for watching, `swarm eval` for measuring.

## What `swarm eval` measures

Per run and team: robots in their U at the end (center inside the U, or
ground sensors on its food), robots stopped outside their U (moved less than
2 cm in the last 10 s), robots in the rival's U, first arrival, time until 5
robots were in the U, seconds spent signaling outside the U, and the error if
the agent failed. Per robot (`robots.csv`): arrival time, where it ended,
whether it was stopped.

## Rules of the tournament (summary)

15 against 15 in the 2 m arena, 300 s, mirrored starts, hidden seeds; every
match twice, exchanging the U. Most robots in their U at the end wins; tie:
first to 5 robots. Only `team.json`, `agent.py` and `fitness.py` may change;
the agent only uses its percepts. If an agent raises an error, its robots
stop and the match goes on.

## Provenance

- `swarm/sim/` and `swarm/robots/`: the e-puck 1 twin of epuck-remote, the
  e-puck part of easabrain (measured from the Webots e-puck PROTO files by
  Cyberbotics, which are not redistributed).
- `swarm/data/sound_loudness_2292.csv`: loudness against distance measured
  on the real e-puck 2292 with epuck-remote.
- `swarm/data/braitenberg_avoidance.json`: obstacle-avoidance weights from
  the essim project.
- `swarm/data/jingle_synth.wav`: our own synthesis of Jingle Bells (James
  Lord Pierpont, 1857; public domain).

MIT license.
