"""tools/trim_world.py — cut a dungeon folder down to the part of the world the reader has reached.

Every day's snapshot ships the final engine and data, which would publish the
later scenes, the endings and the Day 30 easter eggs long before the story
gets there. Run this on a copy of the dungeon folder before publishing a
Day 16-25 snapshot. The first act keeps the tavern, the cellar and upstairs;
it removes the old road, the wolf camp, the bandit and the white wolf, the
letter under the girl's pillow (from 1c she talks about it, but it stays
locked), their items, the endings in quest.json and the book in the new
game's bag. It also hides what the rats' letter and
portrait say through the strange glasses, and takes the later gear and
clues out of rules.md when the folder has one (Day 18 on).

The tavern keeps its exit to the old road, locked by a flag nothing sets
(chapter2_open), so the reader still sees a road that is closed for now. The
engine checks the lock before it reads the destination, so the old road's
scene file does not need to exist.

    uv run --no-project tools/trim_world.py <dungeon_dir> [--level 1a|1b|1c|1d|2a|2b|3a]   trim in place, then check
    uv run --no-project tools/trim_world.py <dungeon_dir> --check           check only
    uv run --no-project tools/trim_world.py <dir> --level 1c --tooling      only the sounds and commands below

Sounds and commands: until Day 27 the sounds the articles have not taught yet
(open, close, stop, down, buzz) go, with their lines in manifest.json and
CREDITS.md; until Day 30 so do gamectl's report and equip. --tooling does
only this part, on a dungeon folder or on the dm plugin (its hooks/ sit at
the plugin root), so a snapshot that is already trimmed can be cleaned too.
Running it twice changes nothing.

Levels:
  1a  Day 16-17: nobody can learn the road yet, so the exit keeps its own hint
  1b  Day 18-21: the cloaked man can tell the road, so the hint and the
      objective say it is not yet time to leave
  1c  Day 22-24: as 1b, but the girl tells you about the letter under her
      pillow and asks you to read it. The letter stays there: searching for
      it needs a flag nothing sets (letter_ready), so the engine answers with
      her line instead, and what the letter says is still cut
  1d  Day 25: as 1c, but the letter can be read: searching under her pillow
      gives 鎮長的信, and its clue goes into the book. The check then allows
      the words the letter says
  2a  Day 26: act 2 opens. The old road is there with the wreck (the manifest,
      the bow and the arrows) and the man guarding the fork, who can be fought,
      talked round, slipped past or paid. The path into the woods is locked by
      a flag nothing sets (chapter3_open): the camp, the white wolf, the orders
      note the guard carries (Day 27), the scimitar he drops and the endings are
      still cut
  2b  Day 27: as 2a, but the guard at the fork carries the white wolf's orders
      note and drops his scimitar, and the sounds are back. The path into the
      woods stays locked: the camp is Day 28
  3a  Day 28-29: act 3 opens. The camp, the white wolf, his pendant and his
      sword are there, and he can be fought, persuaded or robbed. Nothing ends
      the game: persuading him only sets wolf_listened, beating him drops his
      sword and coins, and the three endings, the epilogues and the thin book
      are cut until Day 30

Edits are made on the text, so the file layout stays as it was, and each JSON
file is checked against the same edit done on the parsed JSON. When the data
no longer looks the way this script expects, it stops instead of guessing.
The check at the end also scans the data for words that belong to later days.
"""
import ast
import copy
import json
import pathlib
import re
import sys

try:  # Windows consoles default to cp950
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

LEVELS = ("1a", "1b", "1c", "1d", "2a", "2b", "3a")
LEVEL_DAY = {"1a": 16, "1b": 18, "1c": 22, "1d": 25, "2a": 26, "2b": 27, "3a": 28}   # the first day each level is published
ACT2 = ("2a", "2b")
ACT3 = ("3a",)
# What the articles teach later. The sounds come back on Day 27 with the full sound table;
# /report is Day 30, and /equip is not part of the series, so it waits for the whole game too.
LATER_SOUNDS = ["open", "close", "stop", "down", "buzz"]
LATER_COMMANDS = ["report", "equip"]
SOUNDS_DAY = 27
COMMANDS_DAY = 30
CN_COUNT = "零一二三四五六七八九十"
DOWN_DOC = "  player_down -> down at the end\n"
DOWN_CODE = '    if result.get("player_down"):\n        out.append("down")\n'
BUZZER = re.compile(r"\n    try:  # the buzzer.*?\n    except Exception:\n        pass", re.S)
TEXT_EDITS = [   # (where, old, new, the first day the old text is true)
    ("hooks/audit.py", "stated in Day 13 and Day 29.", "stated in Day 13.", 29),
    ("hooks/story.py", "so /report can show an adventure and not only a ledger",
     "so the log keeps the adventure and not only a ledger", 30),
    (".claude/skills/book/hooks/register.tsx", "/load, /newgame and /equip change",
     "/load and /newgame change", 30),
]
LATER_SCENES = ["old_road", "wolf_camp"]
LATER_ACTORS = ["bandit", "white_wolf"]
# what act 2 keeps: the road and the guard at the fork; the camp and the wolf wait for Day 28
ACT2_SCENES = ["wolf_camp"]
ACT2_ACTORS = ["white_wolf"]
ACT2_ITEMS = ["hero_book", "scimitar", "longsword", "wolf_orders", "wolf_pendant"]
ACT2B_ITEMS = ["hero_book", "longsword", "wolf_pendant"]   # 2b hands over the orders note and the scimitar
ACT3_ITEMS = ["hero_book"]   # 3a keeps everything but the easter-egg book
# the white wolf without an ending: talked round he only listens, beaten he only falls
WOLF_CONVINCED = ('"on_convinced": [{"set_flag": "ending_peace"}, {"if": ["knows_son"], "set_flag": "ending_truth"}, {"set_flag": "ending"}],',
                  '"on_convinced": [{"set_flag": "wolf_listened"}],')
WOLF_DOWN = ('"on_down": [{"set_flag": "ending_fight"}, {"set_flag": "ending"}, {"copper": "+20"}, {"item": "白狼的長劍"}]',
             '"on_down": [{"set_flag": "wolf_down"}, {"copper": "+20"}, {"item": "白狼的長劍"}]')
LATER_ITEMS = ["hero_book", "scimitar", "longsword", "shortbow",
               "wolf_orders", "wolf_pendant", "mayor_letter", "manifest"]
RAT_ITEMS = ["squeak_letter", "rat_portrait"]   # what they say through the glasses is a Day 30 easter egg
BOOK = "一本薄薄的書"
LETTER_TAIL = ("逃的時候她在貨堆旁撿到一封那個領頭的人掉的信。她不識字，"
               "只知道這是唯一能查出那些人是誰的東西，一直壓在枕頭下，不敢給任何人看。現在她想請你念給她聽。")
CHAPTER_FLAG = "chapter2_open"   # nothing in act 1 sets it, so the old road stays locked
WOODS_FLAG = "chapter3_open"     # nothing in act 2 sets it either: the path into the woods stays shut
WOODS_EXIT = '"wolf_camp": {"title": "岔路往林子裡的小徑", "guarded_by": "bandit", "locked_hint": "守路的人擋在岔路口"}'
WOODS_LOCKED = ('"wolf_camp": {"title": "岔路往林子裡的小徑", "requires": ["' + WOODS_FLAG
                + '"], "guarded_by": "bandit", "locked_hint": "守路的人擋在岔路口；就算過了他，林子裡的路也還沒摸清楚"}')
# the guard without the note he carries for Day 27, and without the scimitar he drops
BANDIT_LOOK = ("守在岔路口的帶刀男人，腰帶上塞著一張字條", "守在岔路口的帶刀男人")
BANDIT_LOOT = ('"wallet": "d6", "loot": "白狼的命令字條",', '"wallet": "d6",')
BANDIT_DOWN = ('"on_down": [{"set_flag": "road_cleared"}, {"copper": "+5"}, {"item": "彎刀"}]',
               '"on_down": [{"set_flag": "road_cleared"}, {"copper": "+5"}]')
LETTER_FLAG = "letter_ready"     # nothing sets it either: from 1c the letter is in sight but stays put until Day 25
LETTER_WAIT = "女孩一手按住枕頭，搖搖頭：「現在還不行。」"
LETTER_RULE = ('"search": {"dc": 12, "requires": ["girl_trusts"], "requires_hint": "女孩擋在床前，不讓你碰她的東西",\n'
               '                   "once": "clue_letter", "once_hint": "信已經在你手上了",\n'
               '                   "success": [{"item": "鎮長的信"}, {"set_flag": "clue_letter"}, {"set_flag": "knows_son"}], "fail": []}')
LETTER_RULE_LOCKED = ('"search": {"dc": 12, "requires": ["girl_trusts", "' + LETTER_FLAG + '"], "requires_hint": "'
                      + LETTER_WAIT + '",\n                   "success": [], "fail": []}')
LETTER_ASK = ('"interact": {"requires": ["girl_trusts"], "requires_hint": "她還不信任你，不會把信交出來",\n'
              '                     "forbids": ["clue_letter"], "forbids_hint": "信已經在你手上了",\n'
              '                     "success": [{"item": "鎮長的信"}, {"set_flag": "clue_letter"}, {"set_flag": "knows_son"}]}')
LETTER_ASK_LOCKED = ('"interact": {"requires": ["girl_trusts", "' + LETTER_FLAG + '"], "requires_hint": "' + LETTER_WAIT
                     + '",\n                     "success": []}')
ROAD_HINT = "你還不知道商隊走的是哪條路"
NOT_YET_HINT = "現在還不是出發的時候，鎮上的事還沒弄清楚"
ROAD_EXIT = '"old_road": {"title": "出鎮往北邊舊路", "requires": ["knows_road"], "locked_hint": "' + ROAD_HINT + '"}'
ROAD_OBJECTIVE = "走北邊舊路，找商隊的下落"
NOT_YET_OBJECTIVE = "先把鎮上的事弄清楚，再出發去北邊舊路"
RULES_DROP = ["| 彎刀 |", "| 白狼的長劍 |", "| 獵人的短弓 |"]
RULES_DROP_ACT2 = ["| 彎刀 |", "| 白狼的長劍 |"]
RULES_DROP_ACT2B = ["| 白狼的長劍 |"]
RULES_EDITS = [
    ("短劍是靈巧武器，用敏捷：攻擊 +4，傷害 d6+2。彎刀用力量：攻擊 +3，傷害 d8+1。弓用敏捷。",
     "短劍是靈巧武器，用敏捷：攻擊 +4，傷害 d6+2。"),
    ("拿到信、拿到商隊清單、做完委託，看對象。", "做完委託，看對象。"),
    ("物件的 DC 寫在場景裡：雜物堆 12，商隊貨車 15。", "物件的 DC 寫在場景裡，例如雜物堆 12。"),
    ("| 奇怪的眼鏡 | 頭 | 看得懂老鼠寫的字 | 偷女孩 |", "| 奇怪的眼鏡 | 頭 | 不明 | 偷女孩 |"),
]
FORBIDDEN = ["兒啊", "隔壁洞的小花", "看得懂老鼠", "鎮長", "回家吧", "白狼的長劍", "彎刀", "短弓",
             "商隊貨車", "商隊清單", "薄薄的書", "ending_", "wolf_camp", "bandit", "white_wolf"]
ACT2_WORDS = ["短弓", "商隊貨車", "商隊清單", "bandit"]   # act 2 may say these; wolf_camp stays as the locked exit's key
ACT2_ALLOWED = ACT2_WORDS + ["wolf_camp"]
ACT2B_ALLOWED = ACT2_ALLOWED + ["彎刀"]
ACT3_ALLOWED = ACT2B_ALLOWED + ["white_wolf", "白狼的長劍"]
LETTER_WORDS = ["鎮長", "回家吧"]   # what the mayor's letter says; allowed once 1d hands it over
LETTER_ITEM = "mayor_letter"
RULES_LETTER = ("做完委託，看對象。", "拿到信、做完委託，看對象。")
RULES_WEAPONS_ACT2 = ("短劍是靈巧武器，用敏捷：攻擊 +4，傷害 d6+2。", "短劍是靈巧武器，用敏捷：攻擊 +4，傷害 d6+2。弓用敏捷。")   # 1d keeps the letter, not the manifest


class Mismatch(Exception):
    pass


def fix_commas(text):
    """Drop the comma a removed last entry leaves behind, and close emptied objects on one line."""
    return re.sub(r"\{\s*\n\s*\}", "{}", re.sub(r",(\s*[}\]])", r"\1", text))


def drop_lines(text, needles):
    lines = text.split("\n")
    kept = [ln for ln in lines if not any(n in ln for n in needles)]
    if len(lines) - len(kept) != len(needles):
        raise Mismatch(f"expected to drop {len(needles)} lines, dropped {len(lines) - len(kept)}")
    return "\n".join(kept)


def drop_block(text, first, last):
    """Drop the lines from the one equal to `first` through the next one equal to `last`."""
    lines = text.split("\n")
    try:
        start = lines.index(first)
        end = lines.index(last, start + 1)
    except ValueError as exc:
        raise Mismatch(f"block {first.strip()!r} not found") from exc
    return "\n".join(lines[:start] + lines[end + 1:])


def replace_once(text, old, new, what):
    if text.count(old) != 1:
        raise Mismatch(f"{what} changed or was already trimmed")
    return text.replace(old, new)


def edit(path, text_edit, json_edit):
    """Apply the same change to the text and to the parsed JSON; they must agree."""
    text = path.read_text(encoding="utf-8")
    expected = copy.deepcopy(json.loads(text))
    json_edit(expected)
    result = fix_commas(text_edit(text))
    if json.loads(result) != expected:
        raise Mismatch(f"{path.name}: the text edit does not match the JSON edit")
    path.write_text(result, encoding="utf-8", newline="\n")


def trim(root, level):
    scenes, data = root / "scenes", root / "data"
    act3 = level in ACT3
    act2 = level in ACT2 or act3
    hint = ROAD_HINT if level == "1a" else NOT_YET_HINT

    for sid in [] if act3 else ACT2_SCENES if act2 else LATER_SCENES:
        (scenes / f"{sid}.json").unlink(missing_ok=True)

    if act3:
        # the camp without its endings: the three ending clues and the epilogues go
        def camp_text(t):
            t = drop_lines(t, ['"flag": "ending_truth"', '"flag": "ending_peace"', '"flag": "ending_fight"'])
            return drop_block(t, '    "epilogue": {', "    }")

        def camp_json(d):
            j = d["judge_only"]
            j["clues"] = [c for c in j["clues"] if not str(c.get("flag", "")).startswith("ending_")]
            del j["epilogue"]
        edit(scenes / "wolf_camp.json", camp_text, camp_json)
    elif act2:
        # the road is open; the path into the woods at its far end is not
        def road_json(d):
            ex = d["visible"]["exits"]["wolf_camp"]
            ex["requires"] = [WOODS_FLAG]
            ex["locked_hint"] = "守路的人擋在岔路口；就算過了他，林子裡的路也還沒摸清楚"
        edit(scenes / "old_road.json", lambda t: replace_once(t, WOODS_EXIT, WOODS_LOCKED, "old_road.json's path into the woods"),
             road_json)
    else:
        locked_exit = ('"old_road": {"title": "出鎮往北邊舊路", "requires": ["knows_road", "' + CHAPTER_FLAG
                       + '"], "locked_hint": "' + hint + '"}')

        def tavern_json(d):
            ex = d["visible"]["exits"]["old_road"]
            ex["requires"] = ["knows_road", CHAPTER_FLAG]
            ex["locked_hint"] = hint
        edit(scenes / "tavern.json", lambda t: replace_once(t, ROAD_EXIT, locked_exit, "tavern.json's old road exit"),
             tavern_json)

    def upstairs_text(t):
        if level == "1d" or act2:  # the letter can be read: nothing upstairs is cut
            return t
        if level == "1c":  # she mentions the letter; it stays under the pillow, and what it says is cut
            t = replace_once(t, LETTER_RULE, LETTER_RULE_LOCKED, "upstairs.json: the letter's search rule")
            t = replace_once(t, LETTER_ASK, LETTER_ASK_LOCKED, "upstairs.json: asking for the letter")
            return drop_lines(t, ['"flag": "clue_letter"'])
        t = replace_once(t, LETTER_TAIL, "", "upstairs.json: the girl's line about the letter")
        t = drop_lines(t, ['"letter": {"title"', '"flag": "clue_letter"'])
        return drop_block(t, '      "letter": {', "      }")

    def upstairs_json(d):
        if level == "1d" or act2:
            return
        clues =[c for c in d["judge_only"]["clues"] if c["flag"] != "clue_letter"]
        if level == "1c":
            d["judge_only"]["features"]["letter"]["search"] = {
                "dc": 12, "requires": ["girl_trusts", LETTER_FLAG], "requires_hint": LETTER_WAIT,
                "success": [], "fail": []}
            d["judge_only"]["features"]["letter"]["interact"] = {
                "requires": ["girl_trusts", LETTER_FLAG], "requires_hint": LETTER_WAIT, "success": []}
        else:
            del d["visible"]["features"]["letter"]
            del d["judge_only"]["features"]["letter"]
            for c in clues:
                c["text"] = c["text"].replace(LETTER_TAIL, "")
        d["judge_only"]["clues"] = clues
    edit(scenes / "upstairs.json", upstairs_text, upstairs_json)

    if act3:
        def actors_text(t):
            for old, new in (WOLF_CONVINCED, WOLF_DOWN):
                t = replace_once(t, old, new, f"actors.json: the wolf's {old[:14]}")
            return t

        def actors_json(d):
            w = d["white_wolf"]
            w["on_convinced"] = [{"set_flag": "wolf_listened"}]
            w["on_down"] = [{"set_flag": "wolf_down"}, {"copper": "+20"}, {"item": "白狼的長劍"}]
        edit(data / "actors.json", actors_text, actors_json)
    elif act2:
        def actors_text(t):
            t = drop_block(t, '  "white_wolf": {', "  }")
            if level == "2a":
                for old, new in (BANDIT_LOOK, BANDIT_LOOT, BANDIT_DOWN):
                    t = replace_once(t, old, new, f"actors.json: the guard's {old[:12]}")
            return t

        def actors_json(d):
            del d["white_wolf"]
            if level == "2a":
                b = d["bandit"]
                b["look"] = BANDIT_LOOK[1]
                del b["loot"]
                b["on_down"] = [o for o in b["on_down"] if "item" not in o]
        edit(data / "actors.json", actors_text, actors_json)
    else:
        def actors_json(d):
            for aid in LATER_ACTORS:
                del d[aid]
        edit(data / "actors.json", lambda t: drop_block(t, '  "bandit": {', "  }"), actors_json)

    if act3:
        later_items = list(ACT3_ITEMS)
    elif act2:
        later_items = list(ACT2_ITEMS if level == "2a" else ACT2B_ITEMS)
    else:
        later_items = [i for i in LATER_ITEMS if level != "1d" or i != LETTER_ITEM]

    def items_text(t):
        d = json.loads(t)
        for iid in RAT_ITEMS:
            t = replace_once(t, '"desc": "' + d[iid]["desc"] + '"', '"desc": "' + d[iid]["desc_locked"] + '"',
                             f"items.json: what {iid} says")
        return drop_lines(t, [f'  "{i}":' for i in later_items])

    def items_json(d):
        for iid in later_items:
            del d[iid]
        for iid in RAT_ITEMS:
            d[iid]["desc"] = d[iid]["desc_locked"]
    edit(data / "items.json", items_text, items_json)

    def seed_json(d):
        d["inventory"].remove(BOOK)
    edit(data / "seed_state.json",
         lambda t: replace_once(t, f'"inventory": ["{BOOK}"]', '"inventory": []', "seed_state.json's bag"), seed_json)

    later_flags = ['"ending_truth"', '"ending_peace"', '"ending_fight"'] + ([] if act2 else ['"passed:bandit"'])

    def quest_text(t):
        t = drop_lines(t, later_flags)
        if level != "1a" and not act2:
            t = replace_once(t, f'"text": "{ROAD_OBJECTIVE}"', f'"text": "{NOT_YET_OBJECTIVE}"',
                             "quest.json's road objective")
        return t

    def quest_json(d):
        d[:] = [r for r in d if not any(f.strip('"') in r.get("all", []) + r.get("any", []) for f in later_flags)]
        if level != "1a" and not act2:
            for r in d:
                if r.get("text") == ROAD_OBJECTIVE:
                    r["text"] = NOT_YET_OBJECTIVE
    edit(data / "quest.json", quest_text, quest_json)

    rules = root / "rules.md"
    if rules.exists():
        t = drop_lines(rules.read_text(encoding="utf-8"),
                       [] if act3 else RULES_DROP_ACT2B if level == "2b" else RULES_DROP_ACT2 if act2 else RULES_DROP)
        for old, new in RULES_EDITS:
            if act2 and old.startswith(("拿到信", "物件的 DC")):
                continue   # the manifest and the wreck are in play
            if (level == "2b" or act3) and old.startswith("短劍是靈巧武器"):
                continue   # the scimitar is in play
            if act2 and new == RULES_WEAPONS_ACT2[0]:
                new = RULES_WEAPONS_ACT2[1]
            if level == "1d" and new == RULES_LETTER[0]:
                new = RULES_LETTER[1]
            t = replace_once(t, old, new, f"rules.md: {old[:16]}")
        rules.write_text(t, encoding="utf-8", newline="\n")

    trim_tooling(root, LEVEL_DAY[level])


def check(root):
    """Every name the trimmed data points at must still exist, the chapter lock must hold,
    and no file may still mention something that belongs to a later day."""
    scenes = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (root / "scenes").glob("*.json")}
    actors = json.loads((root / "data" / "actors.json").read_text(encoding="utf-8"))
    items = json.loads((root / "data" / "items.json").read_text(encoding="utf-8"))
    seed = json.loads((root / "data" / "seed_state.json").read_text(encoding="utf-8"))
    names = {it["name"] for it in items.values()}
    problems = []

    def outcomes(where, seq):
        for o in seq or []:
            if "item" in o and o["item"] not in names:
                problems.append(f"{where}: item {o['item']} is gone")
            if "strike" in o and o["strike"] not in actors:
                problems.append(f"{where}: actor {o['strike']} is gone")
            if "move" in o and o["move"] not in scenes:
                problems.append(f"{where}: scene {o['move']} is gone")
            if o.get("set_flag") in (CHAPTER_FLAG, WOODS_FLAG):
                problems.append(f"{where}: sets {o['set_flag']}, which would open a missing scene")
            if o.get("set_flag") == LETTER_FLAG:
                problems.append(f"{where}: sets {LETTER_FLAG}, which would hand over a letter that is cut")

    for sid, card in scenes.items():
        vis = card["visible"]
        for aid in vis.get("actors", []):
            if aid not in actors:
                problems.append(f"{sid}: actor {aid} is gone")
        for target, ex in vis.get("exits", {}).items():
            if target not in scenes and not ({CHAPTER_FLAG, WOODS_FLAG} & set(ex.get("requires", []))):
                problems.append(f"{sid}: exit to {target} leads nowhere")
            if ex.get("guarded_by") and ex["guarded_by"] not in actors:
                problems.append(f"{sid}: guard {ex['guarded_by']} is gone")
        for fid, rules in card.get("judge_only", {}).get("features", {}).items():
            if fid not in vis.get("features", {}):
                problems.append(f"{sid}: feature {fid} has no visible side")
            for rule in rules.values():
                outcomes(f"{sid}.{fid}", rule.get("success"))
                outcomes(f"{sid}.{fid}", rule.get("fail"))
        outcomes(f"{sid}.on_all_down", card.get("judge_only", {}).get("on_all_down", {}).get("outcomes"))
    for aid, a in actors.items():
        loot = a.get("loot") or []
        for name in [loot] if isinstance(loot, str) else loot:
            if name not in names:
                problems.append(f"actor {aid}: loot {name} is gone")
        for key, seq in a.items():
            if key.startswith("on_"):
                outcomes(f"actor {aid}.{key}", seq)
        # the guard keeps the id of the scene he guards (it gives him his guard verbs), even
        # when that scene is cut and the exit to it is locked for the act
        locked_ahead = any(WOODS_FLAG in ex.get("requires", []) and ex.get("guarded_by") == aid
                           for card in scenes.values() for ex in card["visible"].get("exits", {}).values())
        if a.get("guards") and a["guards"] not in scenes and not locked_ahead:
            problems.append(f"actor {aid}: guards {a['guards']}, which is gone")
    for name in seed.get("inventory", []):
        if name not in names:
            problems.append(f"seed_state: item {name} is gone")
    for slot, iid in seed.get("equipment", {}).items():
        if iid and iid not in items:
            problems.append(f"seed_state: {slot} {iid} is gone")
    act2 = "old_road" in scenes
    act2b = act2 and "scimitar" in items
    act3 = "wolf_camp" in scenes
    allowed = ACT3_ALLOWED if act3 else ACT2B_ALLOWED if act2b else ACT2_ALLOWED
    forbidden = [w for w in FORBIDDEN if not (LETTER_ITEM in items and w in LETTER_WORDS)
                 and not (act2 and w in allowed)]
    files = sorted((root / "data").glob("*.json")) + sorted((root / "scenes").glob("*.json")) + [root / "rules.md"]
    for path in files:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            for word in forbidden:
                if word in text:
                    problems.append(f"{path.relative_to(root).as_posix()}: still mentions {word}")
    return problems


def hooks_dir(root):
    """.claude/hooks in a dungeon folder; hooks/ at the root of the dm plugin."""
    for hooks in (root / ".claude" / "hooks", root / "hooks"):
        if (hooks / "sound.py").exists():
            return hooks
    return None


def text_edit_path(root, where):
    if where.startswith("hooks/"):
        hooks = hooks_dir(root)
        return hooks / where[len("hooks/"):] if hooks else None
    return root / where


def rewrite(path, change):
    """Apply `change` to a text file, keeping its bytes otherwise as they were. True if it changed."""
    if path is None or not path.exists():
        return False
    old = path.read_bytes().decode("utf-8")
    new = change(old)
    if new != old:
        path.write_bytes(new.encode("utf-8"))
    return new != old


def drop_commands(src):
    """gamectl without its later commands: their functions, their table entries and the usage line."""
    names = {f"cmd_{c}" for c in LATER_COMMANDS}
    lines = src.split("\n")
    spans = [(n.lineno, n.end_lineno) for n in ast.parse(src).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    for first, last in sorted(spans, reverse=True):
        end = last
        while end < len(lines) and end - last < 2 and not lines[end].strip():
            end += 1   # the blank lines after the function go with it
        del lines[first - 1:end]
    src = "\n".join(lines)
    for c in LATER_COMMANDS:
        src = re.sub(rf'"{c}": cmd_{c},\s*', "", src)
        src = re.sub(rf',\s*"{c}": cmd_{c}(?=\s*\}})', "", src)
        src = re.sub(rf"\|{c}(?=[|>])", "", src, count=1)
    if not any(isinstance(n, ast.Name) and n.id == "json" for n in ast.walk(ast.parse(src))):
        src = src.replace("import json\n", "", 1)
    return src


def trim_tooling(root, day):
    """Take out the sounds and commands the articles have not taught by `day`. Running it
    again on a folder that is already clean changes nothing. Returns what it changed."""
    changed = []
    hooks = hooks_dir(root)
    if hooks and day < SOUNDS_DAY:
        sounds = hooks / "sounds"
        later = [f"{n}.wav" for n in LATER_SOUNDS]
        for name in later:
            if (sounds / name).exists():
                (sounds / name).unlink()
                changed.append(f"sounds/{name} removed")

        def manifest(text):
            entries = json.loads(text)
            kept = [e for e in entries if e.get("file") not in later]
            if kept == entries:
                return text
            return json.dumps(kept, ensure_ascii=False, indent=2) + ("\n" if text.endswith("\n") else "")

        def credits(text):
            kept = [ln for ln in text.split("\n") if not any(f"| {n} |" in ln for n in later)]
            count = sum(1 for ln in kept if ln.startswith("| ") and ".wav |" in ln)
            return re.sub(r"[一二三四五六七八九十]+個短音效", f"{CN_COUNT[count]}個短音效", "\n".join(kept))

        for path, change in ((sounds / "manifest.json", manifest), (sounds / "CREDITS.md", credits),
                             (hooks / "sound.py", lambda t: t.replace(DOWN_DOC, "").replace(DOWN_CODE, "")),
                             (hooks / "audit.py", lambda t: BUZZER.sub("", t))):
            if rewrite(path, change):
                changed.append(f"{path.relative_to(root).as_posix()} edited")
    if day < COMMANDS_DAY and rewrite(root / "gamectl.py", drop_commands):
        changed.append("gamectl.py: " + ", ".join(LATER_COMMANDS) + " removed")
    for where, old, new, from_day in TEXT_EDITS:
        path = text_edit_path(root, where)
        if day < from_day and rewrite(path, lambda t, o=old, n=new: t.replace(o, n)):
            changed.append(f"{path.relative_to(root).as_posix()} edited")
    return changed


def check_tooling(root, day):
    """Nothing the articles teach later is left, and every script still compiles."""
    problems = []
    hooks = hooks_dir(root)
    if hooks and day < SOUNDS_DAY:
        for name in (f"{n}.wav" for n in LATER_SOUNDS):
            if (hooks / "sounds" / name).exists():
                problems.append(f"sounds/{name} is still there")
            manifest = hooks / "sounds" / "manifest.json"
            if manifest.exists() and any(e.get("file") == name for e in json.loads(manifest.read_text(encoding="utf-8"))):
                problems.append(f"sounds/manifest.json still lists {name}")
            credits = hooks / "sounds" / "CREDITS.md"
            if credits.exists() and f"| {name} |" in credits.read_text(encoding="utf-8"):
                problems.append(f"sounds/CREDITS.md still lists {name}")
        if '"down"' in (hooks / "sound.py").read_text(encoding="utf-8"):
            problems.append("sound.py still plays down")
        audit = hooks / "audit.py"
        if audit.exists() and "buzz" in audit.read_text(encoding="utf-8"):
            problems.append("audit.py still buzzes")
    gamectl = root / "gamectl.py"
    if gamectl.exists() and day < COMMANDS_DAY:
        for c in LATER_COMMANDS:
            if f"cmd_{c}" in gamectl.read_text(encoding="utf-8"):
                problems.append(f"gamectl.py still has {c}")
    for where, old, _new, from_day in TEXT_EDITS:
        path = text_edit_path(root, where)
        if day < from_day and path is not None and path.exists() and old in path.read_text(encoding="utf-8"):
            problems.append(f"{path.relative_to(root).as_posix()} still says {old!r}")
    scripts = [gamectl] + (sorted(hooks.glob("*.py")) if hooks else [])
    for path in scripts:
        if path.exists():
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except SyntaxError as exc:
                problems.append(f"{path.relative_to(root).as_posix()} no longer compiles: {exc}")
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    root = pathlib.Path(argv[1]).resolve()
    level = argv[argv.index("--level") + 1] if "--level" in argv else "1a"
    if level not in LEVELS:
        print(f"unknown level {level}; use one of {', '.join(LEVELS)}")
        return 1
    tooling_only = "--tooling" in argv
    if "--check" not in argv:
        if tooling_only:
            for line in trim_tooling(root, LEVEL_DAY[level]) or ["nothing to take out"]:
                print(line)
        else:
            trim(root, level)
            print(f"trimmed {root} to level {level}")
    problems = ([] if tooling_only else check(root)) + check_tooling(root, LEVEL_DAY[level])
    for p in problems:
        print("PROBLEM:", p)
    if not problems:
        print("check: " + ("" if tooling_only else "every name the data points at exists, the old road "
                           "stays locked, nothing from later days; ") + "no sound or command from a later day")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
