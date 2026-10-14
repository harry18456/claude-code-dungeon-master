"""tools/build_report.py — turn a campaign into a report page (HTML).

Usage:
  uv run --no-project tools/build_report.py <game_dir> [--turns <dir>] [-o report.html]

  game_dir   directory holding state.json, scenes/ and .game/{events,rolls,story}.jsonl
  --turns    optional directory produced by tools/run_turns.sh:
             inputs.txt, turn_NN.json (claude -p JSON output) and
             turn_NN.state.json (state.json after that turn)

The page keeps three layers apart:
  - the table talk: what the player typed and what the DM told, from
    .game/story.jsonl (the story hook) or, for headless runs, the --turns
    directory. Quoted as told, every ticket checked against the ledger; never
    a source of numbers.
  - what the engine did: events.jsonl and rolls.jsonl. Every number on the
    page comes from these files or from state.json.
  - what the world holds: item texts, people, the ending, from the engine's own
    data (engine/core.py, scenes/).
The page follows the claude.ai Artifact page contract (no html/head/body tags,
:root tokens with a dark and a light theme, nothing wider than a phone except
tables inside their own scroll box), so /report can publish it as it is.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys

TICKET = re.compile(r"[\[［]R:(r-[0-9a-f]{6})=(\d+)[\]］]")
PROJECT = pathlib.Path(__file__).resolve().parents[1]
META_COMMANDS = ("/report", "/bgm", "/recap")   # talk about the game, not the adventure

# Moonlight over the Drunken Moon tavern: indigo night, moon-white text, lantern
# amber, jade for tickets that match and sealing-wax red for tickets that do not.
# Dark first; a dawn palette for light themes, under both the system setting and
# an explicit data-theme, as the Artifact viewer expects.
LIGHT = ("color-scheme: light; --night: #eef1f8; --card: #ffffff; --moon: #1b2140; --mist: #57607e;"
         " --line: #d4daea; --lantern: #9a6300; --jade: #1f7a60; --wax: #b3261e; --wax-bg: #fbe3e0;")
CSS = (
    ":root { color-scheme: dark; --night: #161b33; --card: #1e2547; --moon: #e8ecf6; --mist: #a3adcb;"
    " --line: #323c66; --lantern: #f0b44c; --jade: #5cc8a6; --wax: #ff8a7a; --wax-bg: #4b2436;"
    ' --tale: "LXGW WenKai TC", "Kaiti TC", DFKai-SB, BiauKai, serif;'
    ' --sans: system-ui, -apple-system, "Segoe UI", "Noto Sans TC", "Microsoft JhengHei", sans-serif;'
    ' --mono: "JetBrains Mono", ui-monospace, Consolas, monospace; }'
    ' @media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { ' + LIGHT + " } }"
    ' :root[data-theme="light"] { ' + LIGHT + " }"
    " body { margin: 0; background: var(--night); color: var(--moon); font: 15px/1.75 var(--sans);"
    " padding-inline: 16px; padding-block: 28px 56px; }"
    " main { max-width: 46rem; margin-inline: auto; display: grid; gap: 44px; }"
    " header, section { display: grid; gap: 14px; }"
    " h1, h2 { font-family: var(--tale); font-weight: 700; margin: 0; text-wrap: balance; }"
    " h1 { font-size: 2.2rem; line-height: 1.25; letter-spacing: .04em; }"
    " h2 { font-size: 1.35rem; color: var(--lantern); letter-spacing: .04em; }"
    " p { margin: 0; }"
    " .eyebrow { font-size: .78rem; letter-spacing: .16em; color: var(--lantern); }"
    " .meta, .gear, .route, .check, .note { color: var(--mist); }"
    " .meta { font-size: .9rem; } .gear { font-size: .9rem; } .check { font-size: .78rem; }"
    " .sheet { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px; display: grid; gap: 12px; }"
    " .hp { display: flex; align-items: center; gap: 10px; font-variant-numeric: tabular-nums; }"
    " .hp span { color: var(--mist); font-size: .85rem; }"
    " .hp .bar { flex: 1; height: 10px; border-radius: 5px; background: var(--line); overflow: hidden; }"
    " .hp .bar i { display: block; height: 100%; background: var(--lantern); }"
    " .status { display: flex; flex-wrap: wrap; gap: 6px 22px; margin: 0; }"
    " .status div { display: flex; gap: 6px; align-items: baseline; }"
    " .status dt { color: var(--mist); font-size: .85rem; } .status dd { margin: 0; font-weight: 600; }"
    " .turn { display: grid; grid-template-columns: 4.6rem minmax(0, 1fr); gap: 0 14px; }"
    " .turn .n { font-family: var(--mono); font-size: .78rem; color: var(--lantern); padding-top: 5px; white-space: nowrap; }"
    " .turn .body { display: grid; gap: 10px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }"
    " .said { color: var(--mist); } .said b { color: var(--lantern); font-weight: 600; margin-right: 8px; }"
    " .said code { font-family: var(--mono); color: var(--moon); }"
    " .tale { font-family: var(--tale); font-size: 1.08rem; line-height: 1.95; display: grid; gap: 10px; }"
    " .dice { font-family: var(--mono); font-size: .8rem; line-height: 1.6; background: var(--card);"
    " border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; display: grid; gap: 2px; overflow-x: auto; }"
    " .facts { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; list-style: none; }"
    " .facts li { font-size: .8rem; line-height: 1.5; padding: 2px 9px; border: 1px solid var(--line); border-radius: 999px; color: var(--mist); }"
    " .facts li.hurt { color: var(--wax); border-color: var(--wax); }"
    " .facts li.gain { color: var(--jade); border-color: var(--jade); }"
    " .clue { font-family: var(--tale); border-left: 2px solid var(--lantern); padding-left: 10px; }"
    " abbr { font-family: var(--mono); font-size: .85em; text-decoration: none; }"
    " abbr.ok { color: var(--jade); } abbr.bad { color: var(--wax); background: var(--wax-bg); padding: 0 3px; border-radius: 3px; }"
    " .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: 10px; }"
    " .tile { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }"
    " .tile b { display: block; font-family: var(--mono); font-size: 1.35rem; font-variant-numeric: tabular-nums; }"
    " .tile span { color: var(--mist); font-size: .82rem; }"
    " .chart { width: 100%; height: auto; display: block; }"
    " .chart .axis { stroke: var(--line); } .chart .line { stroke: var(--lantern); fill: none; stroke-width: 2; }"
    " .chart .dot { fill: var(--lantern); } .chart .down { fill: var(--wax); }"
    " .chart text { fill: var(--mist); font: 11px var(--mono); }"
    " .route b { color: var(--moon); font-weight: 600; }"
    " .items, .people { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }"
    " .items li, .people li { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; }"
    " .items b, .people b { color: var(--lantern); font-weight: 600; margin-right: 8px; }"
    " .epilogue { font-family: var(--tale); font-size: 1.12rem; line-height: 1.95; }"
    " details { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }"
    " summary { cursor: pointer; color: var(--lantern); font-weight: 600; }"
    " details[open] > summary { margin-bottom: 12px; }"
    " details section + section { margin-top: 18px; }"
    " .scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }"
    " table { border-collapse: collapse; width: 100%; font-size: .85rem; }"
    " th, td { padding: 6px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }"
    " th { color: var(--mist); font-weight: 600; white-space: nowrap; } tr:last-child td { border-bottom: 0; }"
    " td.num, td.id { font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }"
    " .proof { display: grid; gap: 4px; color: var(--mist); font-size: .88rem; padding-left: 1.2em; margin: 0; }"
    " :focus-visible { outline: 2px solid var(--lantern); outline-offset: 2px; }"
    " @media (max-width: 480px) { .turn { grid-template-columns: minmax(0, 1fr); } .turn .n { padding: 0; } h1 { font-size: 1.8rem; } }"
)


# ---------------------------------------------------------------- reading files

def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def engine():
    """The engine module, for item texts, people and the hero sheet; None if unavailable."""
    try:
        sys.path.insert(0, str(PROJECT))
        from engine import core
        return core
    except Exception:
        return None


def load_story(game_dir):
    """Turns from .game/story.jsonl (written by .claude/hooks/story.py), regrouped by prompt_id.

    Each turn: what the player typed, everything the DM displayed in order, and
    how many engine events existed when the turn ended. A prompt with no Stop
    record (still running, or a slash command whose ! expansion failed) is not a
    turn. When the last message never reached MessageDisplay (claude -p cancels
    background hooks at exit), Stop's last_assistant_message fills it in."""
    groups, order, seq = {}, [], 0
    for r in read_jsonl(game_dir / ".game" / "story.jsonl"):
        pid = r.get("prompt_id")
        if not pid:  # an older Claude Code without prompt_id: a player line opens the next turn
            seq += r.get("kind") == "player"
            pid = f"seq-{seq}"
        g = groups.get(pid)
        if g is None:
            g = groups[pid] = {"player": None, "before": None, "messages": {}, "stop": None}
            order.append(pid)
        kind = r.get("kind")
        if kind == "player" and g["player"] is None:
            g["player"] = r.get("text") or ""
            g["before"] = r.get("events")
        elif kind == "dm":
            g["messages"].setdefault(r.get("message_id") or "?", {})[int(r.get("index") or 0)] = r.get("text") or ""
        elif kind == "stop":
            g["stop"] = r  # block mode may stop twice; the last one is the turn's end
    turns = []
    for pid in order:
        g = groups[pid]
        if g["stop"] is None:
            continue
        parts = ["".join(text for _, text in sorted(batches.items())).strip() for batches in g["messages"].values()]
        narration = "\n\n".join(p for p in parts if p)
        last = (g["stop"].get("text") or "").strip()
        if last and last not in narration:
            narration = f"{narration}\n\n{last}".strip()
        turns.append({"player": g["player"] or "", "narration": narration,
                      "events_before": int(g["before"]) if g["before"] is not None else None,
                      "events_total": int(g["stop"].get("events") or 0)})
    return turns


def load_turns(turns_dir):
    """Turns from a headless run directory (tools/run_turns.sh)."""
    if not turns_dir:
        return []
    inputs = []
    ip = turns_dir / "inputs.txt"
    if ip.exists():
        inputs = ip.read_text(encoding="utf-8").splitlines()
    turns = []
    for p in sorted(turns_dir.glob("turn_*.json")):
        if p.name.endswith(".state.json"):
            continue
        n = int(re.search(r"(\d+)", p.stem).group(1))
        data = read_json(p, {})
        after = read_json(turns_dir / f"turn_{n:02d}.state.json", {})
        turns.append({
            "n": n,
            "input": inputs[n - 1] if n - 1 < len(inputs) else "",
            "narration": data.get("result") or "",
            "cost": data.get("total_cost_usd"),
            "version_after": int(after.get("version", 0)) if after else None,
        })
    return turns


def scenes_dir(game_dir):
    """The run's own copy of scenes/ when it has one (headless reports), else the project's."""
    own = game_dir / "scenes"
    return own if own.is_dir() else PROJECT / "scenes"


def scene_title(game_dir, scene_id):
    card = read_json(scenes_dir(game_dir) / f"{scene_id}.json")
    return (card or {}).get("visible", {}).get("title", scene_id)


# ---------------------------------------------------------------- what the engine did

def summarize(e):
    kind = e.get("kind")

    def strikes_text(strikes):
        if not strikes:
            return ""
        hits = sum(1 for x in strikes if x.get("hit"))
        crits = sum(1 for x in strikes if x.get("crit"))
        return f"；敵人出手 {len(strikes)} 次，{hits} 次命中" + (f"（{crits} 次重擊）" if crits else "")

    if kind == "attack":
        s = (f"用{e.get('weapon', '')}對{e.get('target_name')}出手：攻擊骰 {e['attack']['value']}+{e['attack']['modifier']}"
             f"={e['attack']['total']} 對 AC {e.get('target_ac', e.get('target_defense'))}，"
             f"{'重擊' if e.get('crit') else '命中' if e.get('hit') else '失手' if e.get('fumble') else '未命中'}")
        if e.get("attack_mode") in ("advantage", "disadvantage"):
            s += f"（{'優勢' if e['attack_mode'] == 'advantage' else '劣勢'}）"
        if e.get("hit"):
            s += f"，傷害 {e.get('damage')}，對方 HP {e.get('enemy_hp_before')}→{e.get('enemy_hp_after')}"
            if e.get("enemy_defeated"):
                s += "，倒下"
        s += strikes_text(e.get("strikes"))
    elif kind == "check":
        s = f"{e.get('rule_name')}：{e.get('target_title')}"
        if e.get("roll"):
            s += f"，d20 {e['roll']['value']}{e['roll']['modifier']:+d} 對 DC {e.get('dc')}"
            if e.get("mode") in ("advantage", "disadvantage"):
                s += f"（{'優勢' if e['mode'] == 'advantage' else '劣勢'}）"
        s += "，成功" if e.get("success") else "，失敗"
        if e.get("effects"):
            s += "（" + "、".join(e["effects"]) + "）"
        s += strikes_text(e.get("strikes"))
    elif kind == "move":
        s = f"移動 {e.get('from')} → {e.get('to')}"
        r = e.get("retreat")
        if isinstance(r, dict):
            r = [r]
        if r:
            s += "；撤退時被追擊" + strikes_text(r).lstrip("；")
        elif e.get("strikes"):
            s += strikes_text(e.get("strikes"))
    elif kind == "rest":
        s = f"休息：HP {e.get('hp_before')}→{e.get('hp_after')}"
    elif kind == "equip":
        s = f"換裝 {e.get('item')}，AC {e.get('ac')}"
    elif kind == "roll":
        s = f"擲骰 d{e['roll']['sides']}：{e['roll']['value']}（{e['roll']['purpose']}）"
    elif kind in ("save", "load"):
        s = f"{'存檔' if kind == 'save' else '讀檔'} {e.get('slot')}"
    else:
        s = kind or "?"
    if e.get("player_down"):
        s += "；倒地，醒來在酒館"
    if e.get("log_warning"):
        s += "（日誌寫入曾失敗）"
    return s


def facts(e, game_dir):
    """Short labels for one event: (css class, text). Internal flags stay out."""
    kind, out = e.get("kind"), []
    if kind == "move":
        out.append(("", f"{scene_title(game_dir, e.get('from'))} → {scene_title(game_dir, e.get('to'))}"))
    elif kind == "attack":
        verdict = "重擊" if e.get("crit") else "命中" if e.get("hit") else "失手" if e.get("fumble") else "落空"
        out.append(("", f"攻擊{e.get('target_name')}：{verdict}" + (f"，傷害 {e.get('damage')}" if e.get("hit") else "")))
    elif kind == "check" and e.get("rule") == "interact":
        out.append(("", e.get("target_title") or ""))   # buying, taking a job: the deed is the label
    elif kind == "check" and e.get("rule_name"):
        target = "" if e.get("target") == "here" else e.get("target_title") or ""
        out.append(("", f"{e.get('rule_name')}{target}：{'成功' if e.get('success') else '失敗'}"))
    elif kind == "rest":
        out.append(("gain", f"休息：HP {e.get('hp_before')} → {e.get('hp_after')}"))
    elif kind == "roll":
        out.append(("", f"擲骰 {e.get('spec', '')}：{e.get('total', '')}"))
    elif kind in ("save", "load"):
        out.append(("", f"{'存檔' if kind == 'save' else '讀檔'} {e.get('slot')}"))
    elif kind == "equip":
        out.append(("", f"換上 {e.get('item')}"))
    elif kind == "newgame":
        out.append(("", "新的冒險開始"))
    for eff in e.get("effects") or []:
        eff = str(eff)
        if eff.startswith("旗標"):
            continue
        coins = re.search(r"銅幣 (\d+) → (\d+)", eff)
        if "受到" in eff or "倒地" in eff or (coins and int(coins.group(2)) < int(coins.group(1))):
            out.append(("hurt", eff))
        elif eff.startswith("獲得") or coins:
            out.append(("gain", eff))
        else:
            out.append(("", eff))
    return out


# ---------------------------------------------------------------- the page

def build(game_dir, turns_dir):
    core = engine()
    state = read_json(game_dir / "state.json", {})
    events = read_jsonl(game_dir / ".game" / "events.jsonl")
    rolls = read_jsonl(game_dir / ".game" / "rolls.jsonl")
    ledger = {r["roll_id"]: r for r in rolls}
    flags = state.get("flags", {})

    def esc(s):
        return html.escape(str(s), quote=True)

    def mark(text):
        def sub(m):
            rid, val = m.group(1), int(m.group(2))
            rec = ledger.get(rid)
            ok = rec is not None and int(rec["value"]) == val
            title = f"{rec['purpose']}，引擎值 {rec['value']}" if rec else "引擎沒有這張票根"
            return f'<abbr class="{"ok" if ok else "bad"}" title="{esc(title)}">[R:{rid}={val}]</abbr>'
        return TICKET.sub(sub, esc(text))

    def rich(text):
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", mark(text))

    # ---- turns: story hook first, headless run next, bare events last
    story = load_story(game_dir)
    headless = load_turns(turns_dir)
    turns, cursor = [], 0
    if story:
        for t in story:
            start = t["events_before"] if t["events_before"] is not None else cursor
            start = max(cursor, min(start, len(events)))
            end = max(start, min(t["events_total"], len(events)))
            turns.append({"player": t["player"], "narration": t["narration"], "events": events[start:end]})
            cursor = end
    elif headless:
        prev = 0
        for t in headless:
            after = t["version_after"] if t["version_after"] is not None else prev
            turns.append({"player": t["input"], "narration": t["narration"], "cost": t["cost"],
                          "events": [e for e in events if prev < int(e.get("version", 0)) <= after]})
            prev = after
        cursor = len(events)
    # events nobody talked about: before the story began, or after its last turn
    told = {id(e) for t in turns for e in t["events"]}
    untold = [e for e in events if id(e) not in told]
    if not turns:
        turns = [{"player": "", "narration": "", "events": [e]} for e in events]
        untold = []

    for t in turns:
        ids = {e.get("resolution_id") for e in t["events"]}
        t["rolls"] = [r for r in rolls if r.get("resolution_id") in ids]
        found = TICKET.findall(t["narration"])
        t["matched"] = [(i, v) for i, v in found if i in ledger and int(ledger[i]["value"]) == int(v)]
        t["bad"] = [(i, v) for i, v in found if i not in ledger or int(ledger[i]["value"]) != int(v)]
        t["missing"] = [r for r in t["rolls"] if r["roll_id"] not in {i for i, _ in found}] if t["narration"] else []

    # ---- the hero
    ch = read_json(PROJECT / "data" / "character.json", {}) or {}
    name, title = state.get("name") or ch.get("name", "艾玲"), ch.get("title", "")
    hp, max_hp = int(state.get("hp", 0) or 0), int(state.get("max_hp", 0) or 0)
    sheet, ac, objective = {}, None, None
    if core:
        try:
            sheet = core.hero_sheet(state)
            ac = sheet.get("ac")
            objective = core.objective(state)
        except Exception:
            sheet = {}
    ending_label = ("真相" if flags.get("ending_truth") else "和平收場" if flags.get("ending_peace")
                    else "戰鬥收場" if flags.get("ending_fight") else "尚未結束")
    status = [("AC", ac if ac is not None else "?"), ("銅幣", state.get("copper")),
              ("位置", scene_title(game_dir, state.get("location", "?"))), ("回合", state.get("turn", 0)),
              ("結局", ending_label)]
    gear = []
    if sheet:
        melee = sheet.get("melee") or {}
        if melee:
            gear.append(f"武器 {melee.get('weapon')} {melee.get('damage')}")
        labels = {"ranged": "弓", "head": "頭", "body": "身", "hands": "手", "feet": "腳"}
        for slot, label in labels.items():
            item = (sheet.get("equipment") or {}).get(slot)
            if item:
                gear.append(f"{label} {item}")

    out = ['<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
           "<title>醉月冒險戰報</title>",
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=LXGW+WenKai+TC:wght@400;700'
           '&family=JetBrains+Mono:wght@400;600&display=swap">',
           "<style>" + CSS + "</style>",
           "<main>",
           "<header>",
           '<p class="eyebrow">醉月酒館 · 戰役報告</p>',
           "<h1>醉月冒險戰報</h1>",
           f'<p class="meta">{esc(name)}{"·" + esc(title) if title else ""} · '
           f"產生時間 {esc(datetime.datetime.now().isoformat(timespec='minutes'))}</p>",
           '<div class="sheet">',
           f'<div class="hp"><span>HP</span><div class="bar"><i style="width:{round(100 * hp / max_hp) if max_hp else 0}%"></i></div>'
           f"<b>{hp}/{max_hp}</b></div>",
           '<dl class="status">' + "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in status) + "</dl>",
           (f'<p class="gear">{esc(" · ".join(gear))}</p>' if gear else ""),
           "</div>",
           "</header>"]

    # ---- the journey
    out.append("<section><h2>旅程</h2>")
    if untold and turns and untold[0] is events[0]:
        out.append(turn_html("紀錄之前", "", "", untold, [], game_dir, esc, rich, mark))
        untold = []
    n = 0
    for t in turns:
        if t["player"].startswith(META_COMMANDS) and not t["events"]:
            continue
        n += 1
        verdict = ""
        if t["narration"] and (t["matched"] or t["bad"] or t["missing"]):
            verdict = f"票根 {len(t['matched'])} 張相符"
            if t["bad"]:
                verdict += f"，{len(t['bad'])} 張不符"
            if t["missing"]:
                verdict += f"，本回合有 {len(t['missing'])} 顆骰子沒出現在敘述裡"
        out.append(turn_html(f"第 {n} 回合", t["player"], t["narration"], t["events"], [verdict] if verdict else [],
                             game_dir, esc, rich, mark, name))
    if untold:
        out.append(turn_html("之後", "", "", untold, [], game_dir, esc, rich, mark))
    out.append("</section>")

    # ---- the record
    attacks = [e for e in events if e.get("kind") == "attack"]
    strikes = [s for e in events for s in (e.get("strikes") or []) if isinstance(s, dict)]
    checks = [e for e in events if e.get("kind") == "check" and e.get("roll")]
    def ratio(hits, total):
        return f"{hits}/{total}" if total else "—"

    tiles = [("出手", len(attacks)), ("命中", ratio(sum(bool(e.get("hit")) for e in attacks), len(attacks))),
             ("重擊", sum(bool(e.get("crit")) for e in attacks)),
             ("造成傷害", sum(int(e.get("damage") or 0) for e in attacks if e.get("hit"))),
             ("承受傷害", sum(int((s.get("damage") or {}).get("amount") or 0) for s in strikes if s.get("hit"))),
             ("檢定成功", ratio(sum(bool(e.get("success")) for e in checks), len(checks))),
             ("倒地", int(flags.get("downed", 0) or 0))]
    defeated = [e.get("target_name") for e in attacks if e.get("enemy_defeated")]
    out.append("<section><h2>戰績</h2>")
    out.append('<div class="tiles">' + "".join(f'<div class="tile"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v in tiles) + "</div>")
    if defeated:
        out.append(f'<p class="note">打倒：{esc("、".join(defeated))}</p>')
    out.append(hp_chart(events, max_hp or 12, esc))
    route = []
    for e in events:
        loc = e.get("location_after")
        if loc and (not route or route[-1] != loc):
            route.append(loc)
    if len(route) > 1:
        out.append('<p class="route">路線：' + " → ".join(f"<b>{esc(scene_title(game_dir, r))}</b>" for r in route) + "</p>")
    out.append("</section>")

    # ---- what was found
    clues = []
    for e in events:
        for c in e.get("revealed") or []:
            if c not in clues:
                clues.append(c)
    bag = sheet.get("inventory") or [{"name": i, "desc": None} for i in state.get("inventory", [])]
    people = []
    if core:
        try:
            actors = core.data("actors")
        except Exception:
            actors = {}
        marks = [("convinced", "說動了"), ("bribed", "收了錢"), ("passed", "被你繞過"), ("stole", "被你偷過"),
                 ("alert", "起了戒心"), ("hostile", "翻臉")]
        for aid, actor in actors.items():
            tags = [label for key, label in marks if flags.get(f"{key}:{aid}")]
            if flags.get(f"down:{aid}"):
                tags.append("倒下" if actor.get("lethal") else "被打趴")
            if tags:
                people.append((actor.get("name", aid), "、".join(tags)))
    if clues or bag or people:
        out.append("<section><h2>發現</h2>")
        for c in clues:
            out.append(f'<p class="clue">{esc(c)}</p>')
        if bag:
            out.append('<ul class="items">' + "".join(
                f"<li><b>{esc(i['name'])}</b>{esc(i['desc'] or '')}</li>" for i in bag) + "</ul>")
        if people:
            out.append('<ul class="people">' + "".join(f"<li><b>{esc(p)}</b>{esc(s)}</li>" for p, s in people) + "</ul>")
        out.append("</section>")

    # ---- the ending
    out.append("<section><h2>結局</h2>")
    epilogue = None
    if flags.get("ending"):
        for path in sorted(scenes_dir(game_dir).glob("*.json")):
            for flag, text in ((read_json(path, {}) or {}).get("judge_only", {}).get("epilogue") or {}).items():
                if epilogue is None and flags.get(flag):
                    epilogue = text
    if epilogue:
        out.append(f'<p class="epilogue">{esc(epilogue)}</p>')
    else:
        out.append('<p class="epilogue">旅程還沒結束。</p>')
        if objective:
            out.append(f'<p class="note">目前的目標：{esc(objective)}</p>')
    out.append("</section>")

    # ---- the ledger, folded
    out.append("<details><summary>引擎帳本：事件、骰子與這份報告能證明什麼</summary>")
    out.append('<section><h2>事件紀錄</h2><div class="scroll"><table><tr><th>#</th><th>種類</th><th>內容</th><th>骰子</th></tr>')
    for e in events:
        ids = [r["roll_id"] for r in rolls if r.get("resolution_id") == e.get("resolution_id")]
        out.append(f'<tr><td class="num">{esc(e.get("version"))}</td><td>{esc(e.get("kind"))}</td><td>{esc(summarize(e))}</td>'
                   f'<td class="id">{esc(" ".join(ids))}</td></tr>')
    out.append("</table></div></section>")
    out.append('<section><h2>骰子帳本</h2><div class="scroll"><table><tr><th>roll_id</th><th>用途</th><th>骰</th><th>值</th><th>來源</th></tr>')
    for r in rolls:
        out.append(f'<tr><td class="id">{esc(r["roll_id"])}</td><td>{esc(r["purpose"])}</td><td class="num">d{esc(r["sides"])}</td>'
                   f'<td class="num">{esc(r["value"])}</td><td>{"釘住（測試）" if r.get("source") == "fixed" else "引擎亂數"}</td></tr>')
    out.append("</table></div></section>")
    fixed = sum(1 for r in rolls if r.get("source") == "fixed")
    told_turns = [t for t in turns if t["narration"] and not (t["player"].startswith(META_COMMANDS) and not t["events"])]
    out.append('<section><h2>這份報告能證明什麼</h2><ul class="proof">')
    out.append(f"<li>{len(rolls)} 顆骰子全部由引擎產生並記帳；其中 {fixed} 顆是測試用的釘住值。</li>")
    out.append(f"<li>{len(events)} 筆事件寫在 state.json 提交之後的衍生日誌；數字以 state.json 為準。</li>")
    if told_turns:
        m = sum(len(t["matched"]) for t in told_turns)
        b = sum(len(t["bad"]) for t in told_turns)
        mis = sum(len(t["missing"]) for t in told_turns)
        out.append(f"<li>{len(told_turns)} 回合的敘述裡有 {m} 張票根與帳本相符，{b} 張不符，{mis} 顆骰子沒被敘述。</li>")
        out.append("<li>旅程裡的敘述是 DM（模型）寫的，照原文引用；每一張票根都對過帳本，數字以引擎為準。</li>")
    cost = max((t.get("cost") or 0 for t in headless), default=0)  # cumulative in a resumed session
    if cost:
        out.append(f"<li>模型費用合計約 {cost:.3f} 美元。</li>")
    out.append("<li>它不能證明模型每次都選對規則、敘述在語意上忠實，或沒有票根的數字是真的。那些要靠人讀。</li></ul></section>")
    out.append("</details>")
    out.append("</main>")
    return "\n".join(o for o in out if o)


def split_tale(text):
    """(story paragraphs, dice lines). The 骰子： block becomes its own box; the
    closing 你要做什麼？ question and its options are left out of the chronicle."""
    tale, dice, in_dice = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("你要做什麼"):
            break
        if s in ("骰子：", "骰子:"):
            in_dice = True
            continue
        if in_dice:
            if TICKET.search(s) or s.startswith("（本回合無擲骰）"):
                dice.append(s)
                continue
            in_dice = False
            if not s:
                continue
        if s == "---":
            continue
        tale.append(line)
    paragraphs = [p.strip() for p in "\n".join(tale).split("\n\n") if p.strip()]
    return paragraphs, dice


def turn_html(label, player, narration, events, notes, game_dir, esc, rich, mark, name="艾玲"):
    out = [f'<article class="turn"><div class="n">{esc(label)}</div><div class="body">']
    if player:
        said = f"<code>{esc(player)}</code>" if player.startswith("/") else esc(player)
        out.append(f'<p class="said"><b>{esc(name)}</b>{said}</p>')
    paragraphs, dice = split_tale(narration)
    if paragraphs:
        out.append('<div class="tale">' + "".join(f"<p>{rich(p)}</p>" for p in paragraphs) + "</div>")
    if dice:
        out.append('<div class="dice">' + "".join(f"<span>{mark(d)}</span>" for d in dice) + "</div>")
    chips = [f for e in events for f in facts(e, game_dir)]
    if chips:
        out.append('<ul class="facts">' + "".join(f'<li class="{c}">{esc(t)}</li>' if c else f"<li>{esc(t)}</li>"
                                                   for c, t in chips) + "</ul>")
    for e in events:
        for c in e.get("revealed") or []:
            out.append(f'<p class="clue">{esc(c)}</p>')
    for note in notes:
        out.append(f'<p class="check">查核：{esc(note)}</p>')
    out.append("</div></article>")
    return "".join(out)


def hp_chart(events, max_hp, esc):
    """HP after each engine event: a line, lantern dots, red dots where she went down."""
    points = []
    for i, e in enumerate(events, 1):
        if not isinstance(e.get("player_hp_after"), int):
            continue
        # a knock-down keeps the HP she woke up with: the line touches 0 first, at the same event
        if e.get("player_down"):
            points.append((i, 0, True))
        points.append((i, int(e["player_hp_after"]), False))
    if len(points) < 2:
        return ""
    w, h, left, right, top, bottom = 600, 150, 34, 12, 14, 24
    span = max(1, points[-1][0] - points[0][0])

    def xy(i, hp):
        x = left + (i - points[0][0]) * (w - left - right) / span
        y = top + (1 - max(0, min(hp, max_hp)) / max_hp) * (h - top - bottom)
        return round(x, 1), round(y, 1)

    line = " ".join(f"{x},{y}" for x, y in (xy(i, hp) for i, hp, _ in points))
    dots = "".join(f'<circle class="{"down" if down else "dot"}" cx="{xy(i, hp)[0]}" cy="{xy(i, hp)[1]}" r="{4 if down else 2.5}"/>'
                   for i, hp, down in points)
    y0, ymax = xy(points[0][0], 0)[1], xy(points[0][0], max_hp)[1]
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="每個事件之後的 HP">'
            f'<line class="axis" x1="{left}" y1="{y0}" x2="{w - right}" y2="{y0}"/>'
            f'<line class="axis" x1="{left}" y1="{ymax}" x2="{w - right}" y2="{ymax}" stroke-dasharray="3 4"/>'
            f'<text x="4" y="{ymax + 4}">{max_hp}</text><text x="4" y="{y0 + 4}">0</text>'
            f'<text x="{left}" y="{h - 6}">事件 {points[0][0]}</text>'
            f'<text x="{w - right}" y="{h - 6}" text-anchor="end">事件 {points[-1][0]}</text>'
            f'<polyline class="line" points="{line}"/>{dots}</svg>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("--turns")
    ap.add_argument("-o", "--output", default="report.html")
    a = ap.parse_args()
    game_dir = pathlib.Path(a.game_dir)
    turns_dir = pathlib.Path(a.turns) if a.turns else None
    out = pathlib.Path(a.output)
    out.write_text(build(game_dir, turns_dir), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
