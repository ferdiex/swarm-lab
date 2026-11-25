"""
view.py - 2D drawing of a match: the arena on the left, the score and the
race curve (robots in their U over time) on the right.

Live window keys: space pause / resume, + and - faster / slower, q quit.
"""
import math

import numpy as np

HAT_RGB = {"blue": "#1f77b4", "orange": "#ff7f0e"}
LED_RGB = {"green": "#22c40f", "red": "#e0201b"}
NOT_COUNTING = "#d9d9d9"


class MatchView:
    def __init__(self, match, figsize=(13.6, 7.65)):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        self.plt, self.m = plt, match
        self.fig = plt.figure(figsize=figsize, dpi=100)
        self.ax = self.fig.add_axes([0.01, 0.02, 0.56, 0.96])
        self.axs = self.fig.add_axes([0.60, 0.50, 0.38, 0.46])
        self.axc = self.fig.add_axes([0.63, 0.09, 0.34, 0.30])
        h, ax = match.half, self.ax
        ax.add_patch(Rectangle((-h, -h), 2 * h, 2 * h, fill=False, lw=3, color="#b02a37"))
        for x, y, wd, ht in match.wall_rects:
            ax.add_patch(Rectangle((x, y), wd, ht, color="#8a8a8a"))
        for (x0, x1, y0, y1), rf in zip(match.food_rects, match.u_refl):
            ax.add_patch(Rectangle((min(x0, x1), y0), abs(x1 - x0), y1 - y0,
                                   color="#222222" if rf < 0.3 else "#8f8f8f", alpha=0.9))
        for k, team in enumerate(match.teams):                 # whose U is whose
            if team is None:
                continue
            x0, x1, y0, y1 = match.boxes[match.own_u[k]]
            ax.text((x0 + x1) / 2, y1 + 0.03, team.name, ha="center", fontsize=10,
                    color=HAT_RGB.get(team.hat, "k"), fontweight="bold")
        ax.set_xlim(-h - 0.03, h + 0.03)
        ax.set_ylim(-h - 0.03, h + 0.03)
        ax.set_aspect("equal")
        ax.axis("off")
        self.dyn = []
        self.keys = False                                        # the live window shows its keys
        self.speed = lambda: 1
        self.paused = lambda: False

    def draw(self):
        from matplotlib.patches import Circle
        for art in self.dyn:
            art.remove()
        self.dyn = []
        m, ax = self.m, self.ax
        for i in range(m.n):
            x, y, yaw = m.pose(i)
            team = m.teams[m.team_of[i]]
            col = HAT_RGB.get(team.hat, "k")
            h = m.handles[i]
            final = m.t >= m.duration - 1e-9
            counts = m.in_u(i, m.own_u[m.team_of[i]])
            if h["sound"]:                                       # sound radiating
                for k in range(3):
                    ph = (m.t * 0.8 + k / 3) % 1.0
                    self.dyn.append(ax.add_patch(Circle((x, y), 0.045 + 0.18 * ph, fill=False, alpha=0.5,
                                                        lw=1.6 * (1 - ph) + 0.3, color="#555555")))
            if h["led"] == "green":                              # green body LED: the body glows
                self.dyn.append(ax.add_patch(Circle((x, y), 0.064, color=LED_RGB["green"], alpha=0.45,
                                                    lw=0, zorder=4)))
            elif h["led"] == "red":                              # red LED ring: a red ring
                self.dyn.append(ax.add_patch(Circle((x, y), 0.047, fill=False, ec=LED_RGB["red"], lw=4.5,
                                                    zorder=5)))
            if final and not counts:                             # at the end: it does not count
                self.dyn.append(ax.add_patch(Circle((x, y), 0.037, color=NOT_COUNTING, ec=col, lw=2, zorder=6)))
            else:
                self.dyn.append(ax.add_patch(Circle((x, y), 0.037, color=col, ec="#333333", lw=0.8, zorder=6)))
            self.dyn += ax.plot([x, x + 0.037 * math.cos(yaw)], [y, y + 0.037 * math.sin(yaw)],
                                color="black", lw=1.2, zorder=7)
        s = m.summary()
        a = self.axs
        a.clear()
        a.axis("off")
        final = m.t >= m.duration - 1e-9
        a.text(0, 1.0, (f"FINAL   {m.duration:.0f} s   seed {m.seed}" if final else
                        f"time {m.t:5.0f} / {m.duration:.0f} s   seed {m.seed}"), fontsize=15,
               fontweight="bold", va="top", color="#b02a37" if final else "black")
        for k, tag in enumerate(("a", "b")):
            team = m.teams[k]
            if team is None:
                continue
            y0 = 0.74 - 0.30 * k
            a.add_patch(self.plt.Rectangle((0, y0 - 0.20), 0.05, 0.20, color=HAT_RGB.get(team.hat, "k"),
                                           transform=a.transAxes))
            side = "home" if team.hat == "blue" else "away"
            a.text(0.08, y0, f"{team.name}  ({team.hat} hat, {side})", fontsize=14, fontweight="bold", va="top")
            a.text(0.08, y0 - 0.09, f"{s[tag + '_in_u']:2d}/{m.robots_per_team} in its U   "
                   f"{s[tag + '_stopped_outside']:2d} stopped outside", fontsize=12, va="top")
            if final:
                first = s[tag + "_first_s"]
                t5 = s[tag + "_time_to_5"]
                a.text(0.08, y0 - 0.16, f"first in: {'-' if first is None else f'{first:.0f} s'}   "
                       f"5 in: {'-' if t5 is None else f'{t5:.0f} s'}   "
                       f"in the rival's U: {s[tag + '_in_rival_u']}", fontsize=10.5, va="top")
            if m.failed[k]:
                a.text(0.08, y0 - 0.18, "ERROR: " + s[tag + "_error"][:60], fontsize=9, color="#b02a37", va="top")
        if final:
            a.text(0, 0.18, "Only the robots inside their U count. Gray robots do not count.",
                   fontsize=11, fontweight="bold", color="#b02a37", va="top")
        a.text(0, 0.10, "green glow: beacon (body LED)   red ring: relay (LED ring)   gray waves: sound",
               fontsize=9.5, color="#333333", va="top")
        if self.keys:
            a.text(0, 0.02, f"space: pause   + / -: speed (x{self.speed()})   q: quit"
                   + ("   PAUSED" if self.paused() else ""), fontsize=9.5, color="#333333", va="top")
        hist = np.array(m.history) if m.history else np.zeros((1, 3))
        c = self.axc
        c.clear()
        for k in range(2):
            if m.teams[k] is not None:
                c.plot(hist[:, 0], hist[:, 1 + k], color=HAT_RGB.get(m.teams[k].hat, "k"), lw=2.5,
                       label=m.teams[k].name)
        c.set_xlim(0, m.duration)
        c.set_ylim(0, m.robots_per_team + 0.5)
        c.set_xlabel("time [s]")
        c.set_title("robots in their U", fontsize=11)
        c.legend(loc="upper left", fontsize=9, frameon=False)
        c.spines[["top", "right"]].set_visible(False)

    def save(self, path):
        self.draw()
        self.fig.savefig(path)


def live(match):
    """Live window. Returns when the window is closed."""
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    view = MatchView(match)
    ctl = {"pause": False, "steps": 2}
    view.keys = True
    view.speed = lambda: ctl["steps"] // 2 if ctl["steps"] >= 2 else 0.5
    view.paused = lambda: ctl["pause"]

    def on_key(ev):
        if ev.key == " ":
            ctl["pause"] = not ctl["pause"]
        elif ev.key in ("+", "="):
            ctl["steps"] = min(ctl["steps"] * 2, 32)
        elif ev.key == "-":
            ctl["steps"] = max(ctl["steps"] // 2, 1)
        elif ev.key == "q":
            plt.close(view.fig)

    view.fig.canvas.mpl_connect("key_press_event", on_key)

    def update(_):
        if not ctl["pause"]:
            for _ in range(ctl["steps"]):
                if match.t < match.duration - 1e-9:
                    match.step()
        view.draw()
        return []

    anim = FuncAnimation(view.fig, update, interval=50, blit=False, cache_frame_data=False)  # noqa: F841
    plt.show()
