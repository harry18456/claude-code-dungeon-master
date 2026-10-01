"""Statusline — show the game's own state file, not the model's memory of it.

Claude Code renders every printed line as a row. Line 1: who and how she is doing. Line 2: what she carries.
Line 3, only in combat: every enemy still standing and its HP.
Lines are cut to the terminal width (COLUMNS) with an ellipsis.
"""
import os
import pathlib
import sys

try:  # Windows pipes default to the locale (cp950 here); print UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_BAG = 3


def cut(line):
    try:
        width = int(os.environ.get("COLUMNS", "0"))
    except ValueError:
        width = 0
    if width and len(line) > width:
        return line[:max(0, width - 1)] + "…"
    return line


try:
    from engine import core
    st = core.load_state()
    hero = core.hero_sheet(st)
    ch = core._character()
    try:
        title = core.scene_card(st["location"])["visible"].get("title", st["location"])
    except Exception:
        title = st.get("location", "?")
    bar_len = 10
    filled = max(0, min(bar_len, round(bar_len * st["hp"] / max(1, st["max_hp"]))))
    bar = "█" * filled + "░" * (bar_len - filled)
    line1 = (f"{st.get('name') or ch.get('name', '?')}·{ch.get('title', '')} | HP {st['hp']:>2}/{st['max_hp']} {bar} | "
             f"AC {hero['ac']} | 銅幣 {st['copper']} | {title} | 第 {st.get('turn', 0)} 回合")
    goal = core.objective(st)
    if goal:
        line1 += f" | 目標：{goal}"

    parts = [f"武器 {hero['melee']['weapon']} {hero['melee']['damage']}"]
    if hero.get("ranged"):
        r = hero["ranged"]
        parts.append(f"弓 {r['weapon']} {r.get('damage', '')}（箭 {hero['arrows']}）".replace("  ", " "))
    labels = {"head": "頭", "body": "身", "hands": "手", "feet": "腳"}
    for slot, label in labels.items():
        name = hero["equipment"].get(slot)
        if name:
            parts.append(f"{label} {name}")
    bag = list(st.get("inventory", []))
    if bag:
        shown = "、".join(bag[:MAX_BAG]) + (f" +{len(bag) - MAX_BAG}" if len(bag) > MAX_BAG else "")
        parts.append(f"背包 {shown}")
    else:
        parts.append("背包 空")
    line2 = " · ".join(parts)

    print(cut(line1))
    print(cut(line2))

    if st["flags"].get(f"combat:{st['location']}"):
        card = core.scene_card(st["location"])
        actors = core.data("actors")
        foes = [f"{actors[a]['name']} HP {core._actor_hp(st, a)}/{actors[a]['hp']}"
                for a in core._hostiles_present(st, card)]
        if foes:
            print(cut("⚔ 戰鬥中：" + "、".join(foes)))
except Exception as exc:
    print(f"[state unavailable: {type(exc).__name__}]")
