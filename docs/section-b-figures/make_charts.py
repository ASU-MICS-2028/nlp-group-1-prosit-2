# Makes the charts in docs/section-b-figures/ (Section B). Every number is one written in docs/section-b.md; figure 8 comes from eval/results/browser_check_2026-11-14.
# uv run --with matplotlib python docs/section-b-figures/make_charts.py docs/section-b-figures
import sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "Poppins" in f: fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Poppins", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#888", "axes.titlesize": 10.5, "axes.titleweight": "bold", "figure.dpi": 200})
OUT = sys.argv[1]
BLUE, ORANGE, GREEN, GREY, RED = "#2F6FD0", "#E8702A", "#3A9A5B", "#B8B8B8", "#C0392B"

def save(fig, n): fig.tight_layout(); fig.savefig(f"{OUT}/{n}.png", facecolor="white"); plt.close(fig)

def bars(ax, labels, vals, colors, fmt, xmax=None, title=None):
    y = range(len(labels))[::-1]
    ax.barh(list(y), vals, color=colors, height=0.6)
    for yi, v in zip(y, vals): ax.text(v + (xmax or max(vals)) * 0.01, yi, fmt(v), va="center", fontsize=9)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels); ax.set_xlim(0, (xmax or max(vals)) * 1.15)
    if title: ax.set_title(title, loc="left")

# Fig 3: the safety choices that won
fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.3))
bars(a, ["Text check", "Real-path check"], [5, 0], [GREY, GREEN], str, 18, "Attack paths let through (of 18)")
bars(b, ["Plain subprocess", "Docker sandbox"], [5, 15], [GREY, GREEN], str, 16, "Code attacks blocked (of 16)")
save(fig, "fig3_safety")

# Fig 4: retrieval
fig, ax = plt.subplots(figsize=(6, 2.2))
bars(ax, ["Dense (MiniLM), chosen", "Hybrid", "BM25", "Random"], [95, 87, 74, 17], [BLUE, GREY, GREY, GREY], lambda v: f"{v}%", 100,
     "Right recipe in the top 3 (111 labelled questions)")
save(fig, "fig4_retrieval")

# Fig 5: agent vs one call
fig, ax = plt.subplots(figsize=(7, 2.8))
groups = ["Every test", "Shared expenses\nleft out for both", "One call given full\nmarks on shared expenses"]
agent, one = [96.0, 95.7, 96.0], [84.0, 87.6, 88.4]
alo, ahi = [95.3, 95.0, 95.3], [96.9, 96.6, 96.9]; olo, ohi = [81.2, 87.2, 88.0], [88.5, 87.7, 88.5]
x = range(3); w = 0.36
for off, vals, lo, hi, c, lab in [(-w / 2, agent, alo, ahi, BLUE, "Agent (3 runs)"), (w / 2, one, olo, ohi, ORANGE, "One call (4 rounds)")]:
    xs = [i + off for i in x]
    ax.bar(xs, vals, w, color=c, label=lab, yerr=[[v - l for v, l in zip(vals, lo)], [h - v for v, h in zip(vals, hi)]], capsize=3, ecolor="#444")
    for xi, v, h in zip(xs, vals, hi): ax.text(xi, h + 0.6, f"{v}%", ha="center", fontsize=8.5)
ax.set_ylim(70, 100); ax.set_xticks(list(x)); ax.set_xticklabels(groups, fontsize=8.5); ax.set_ylabel("Hidden tests passed (%)")
ax.legend(frameon=False, loc="upper right", fontsize=8.5, ncol=2, bbox_to_anchor=(1, 1.12))
save(fig, "fig5_agent_vs_one_call")

# Fig 6: data kept after a restart
fig, ax = plt.subplots(figsize=(6.4, 1.9))
rows = [("One call (Opus), 15 tasks", [1, 13, 1]), ("Agent, 30 checkable builds", [30, 0, 0])]
for i, (lab, (kept, lost, nochk)) in enumerate(rows[::-1]):
    tot = kept + lost + nochk; left = 0
    for n, c, name in [(kept, GREEN, "kept"), (lost, RED, "lost"), (nochk, GREY, "not checkable")]:
        if n: ax.barh(i, n / tot * 100, left=left, color=c, height=0.55); ax.text(left + n / tot * 50, i, f"{n} {name}", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold") if n / tot > 0.12 else None
        left += n / tot * 100
ax.set_yticks([0, 1]); ax.set_yticklabels([r[0] for r in rows[::-1]]); ax.set_xlim(0, 100); ax.set_xlabel("Share of builds (%)")
ax.set_title("Does a backend still have its data after a restart?", loc="left")
save(fig, "fig6_data_kept")

# Fig 7: ablation, score and cost
S = [("Questions + recipe search", 96.4, 96.1, 1.95), ("Full system (3 runs)", 96.0, 95.7, 1.91), ("Sonnet instead of Opus (3 runs)", 92.5, 92.0, 0.70),
     ("No self-testing step", 91.1, 95.6, 1.71), ("No questions", 90.1, 95.0, 1.80), ("Planner, Builder, Tester split", 87.0, 91.7, 4.06),
     ("Questions + plan (real clients)", 85.9, 90.6, 2.72), ("Haiku instead of Opus", 83.9, 87.8, 0.08)]
fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.4), gridspec_kw={"width_ratios": [2.2, 1]}, sharey=True)
y = list(range(len(S)))[::-1]; h = 0.38
a.barh([v + h / 2 for v in y], [s[1] for s in S], h, color=BLUE, label="All tasks")
a.barh([v - h / 2 for v in y], [s[2] for s in S], h, color="#9DBBEA", label="School left out")
for v, s in zip(y, S): a.text(s[1] + 0.3, v + h / 2, f"{s[1]}", va="center", fontsize=7.5); a.text(s[2] + 0.3, v - h / 2, f"{s[2]}", va="center", fontsize=7.5)
a.set_xlim(80, 100); a.set_yticks(y); a.set_yticklabels([s[0] for s in S], fontsize=8.5); a.set_xlabel("Hidden tests passed (%)")
a.legend(frameon=False, fontsize=8, loc="lower right"); a.set_title("Score", loc="left")
b.barh(y, [s[3] for s in S], 0.55, color=[ORANGE if s[3] > 2.5 else "#F2B48A" for s in S])
for v, s in zip(y, S): b.text(s[3] + 0.05, v, f"${s[3]:.2f}", va="center", fontsize=7.5)
b.set_xlim(0, 5); b.set_xlabel("Cost to build all 15 ($)"); b.set_title("Cost", loc="left")
save(fig, "fig7_ablation")

# Fig 8: one real build on the public link, Nov 14
steps = [("Message\nsent", 0), ("Writing the code", 6.2), ("Reached the\nbuilder", 10.5), ("Changing the code", 19.3),
         ("Testing it (19 passed)", 34.5), ("Putting it online", 39.6), ("Your backend is live", 53.0)]
fig, ax = plt.subplots(figsize=(7.2, 2.3))
cols = [GREY, BLUE, GREY, BLUE, ORANGE, GREEN]
for (lab, t), (_, t2), c in zip(steps, steps[1:], cols): ax.barh(0, t2 - t, left=t, color=c, height=0.5, edgecolor="white")
for i, (lab, t) in enumerate(steps):
    up = i % 2 == 0; ax.plot([t, t], [0.25, 0.55] if up else [-0.25, -0.55], color="#666", lw=0.7)
    ax.text(t, 0.6 if up else -0.6, f"{lab}\n{t:.1f} s", ha="center", fontsize=7.5, va="bottom" if up else "top")
ax.set_ylim(-1.3, 1.3); ax.set_xlim(-5, 59); ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.set_xlabel("Seconds after the build started")
save(fig, "fig8_live_build")
print("ok")
