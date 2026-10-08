"""engine/core.py — rules engine for the 醉月 dungeon. Standard library only.

Everything the model must not improvise lives here: dice, combat, checks,
scene transitions, and every write to state.json.

Rules (a trimmed 5e SRD, see rules.md):
  * every test is d20 + modifier against a target number; attacks against
    AC, checks against a DC of 10 / 15 / 20 by the target's attitude
  * six ability scores on the hero, fixed; proficiency +2 on attacks and on
    two skills; equipment adds AC, damage, advantage or disadvantage
  * advantage / disadvantage roll two d20 and keep the better / worse one;
    both together cancel out
  * a natural 20 doubles the damage dice, a natural 1 always misses
  * once combat is on in a scene, every hostile still standing acts after
    the hero's action; the first arrow at an unaware enemy is free; shooting
    with enemies on you is at disadvantage
  * every person is an ACTOR (data/actors.json); verbs apply to everyone by
    default and the model only ever picks verb and target

Commit contract (plan C3): validation errors raise EngineError before any
write; state.json is written atomically with the full result; the derived
logs never override it and a failure there only adds a log_warning.

Test fixture: DUNGEON_FIXED_ROLLS='{"attack:giant_rat":[18],"rest":[3]}'
pins the next values for rolls whose purpose contains the key, in order.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import secrets
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Installed as a plugin, the engine, scenes and data live in the plugin, while the game
# itself (state, saves, records) belongs to the folder Claude Code was opened in.
PLUGIN_MODE = (ROOT / ".claude-plugin" / "plugin.json").exists()
GAME_ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()) if PLUGIN_MODE else ROOT
STATE = GAME_ROOT / "state.json"
GAME = GAME_ROOT / ".game"
EVENTS = GAME / "events.jsonl"
ROLLS = GAME / "rolls.jsonl"
FIXED_USED = GAME / "fixed_rolls_used.json"
SAVES = GAME / "saves"
DATA = ROOT / "data"
SCENES = ROOT / "scenes"
SEED = DATA / "seed_state.json"
FIXED_ENV = "DUNGEON_FIXED_ROLLS"

KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
DIE = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")
MAX_SIDES = 100
MAX_PURPOSE = 128
RECENT_LIMIT = 30
DOWN_COPPER_COST = 10
HOME_SCENE = "tavern"
IMPROVISE_TARGET = "here"
IMPROVISE_RULE = "improvise"
IMPROVISE_DC = 10
GAME_FIELDS = ("name", "hp", "max_hp", "copper", "location", "inventory", "equipment", "arrows",
               "flags", "enemies", "turn")

ACTOR_VERBS = ("persuade", "provoke", "attack")
GUARD_VERBS = ("sneak", "distract")
SLOTS = ("weapon", "ranged", "head", "body", "hands", "feet")
# verb -> (ability, skill). Skills decide proficiency and equipment effects.
VERB_SKILL = {"persuade": ("cha", "persuasion"), "sneak": ("dex", "stealth"), "steal": ("dex", "sleight"),
              "distract": ("dex", "sleight"), "search": ("wis", "perception"), "improvise": (None, None)}
ATTITUDE_DC = {"friendly": 10, "neutral": 15, "wary": 20, "hostile": 20}
DC_MIN, DC_MAX = 10, 20


class EngineError(Exception):
    """Validation failure. Raised before any write happens."""


# ---------------------------------------------------------------- files

def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def read_json(path: pathlib.Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: pathlib.Path, obj) -> None:
    """Write obj via a sibling tmp file and os.replace, retrying the brief
    PermissionError Windows indexers cause. A persistent failure raises."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    delay = 0.02
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(delay)
            delay *= 2


def _append(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def data(name: str) -> dict:
    return read_json(DATA / f"{name}.json", {}) or {}


def _valid_key(value, what: str) -> str:
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise EngineError(f"{what} 必須是 1–64 個英數字、底線或連字號")
    return value


def scene_card(scene_id: str) -> dict:
    _valid_key(scene_id, "場景代號")
    card = read_json(SCENES / f"{scene_id}.json")
    if not card:
        raise EngineError(f"沒有這個場景：{scene_id}")
    card.setdefault("visible", {})
    card.setdefault("judge_only", {})
    return card


def load_state() -> dict:
    st = read_json(STATE)
    if not st:
        raise EngineError("找不到 state.json；請先執行 uv run --no-project gamectl.py newgame")
    st.setdefault("flags", {})
    st.setdefault("enemies", {})
    st.setdefault("inventory", [])
    st.setdefault("equipment", dict(_character().get("equipment", {})))
    st.setdefault("arrows", int(_character().get("arrows", 0)))
    st.setdefault("turn", 0)
    st.setdefault("version", 0)
    return st


# ---------------------------------------------------------------- character, items

def _character() -> dict:
    ch = data("character")
    if not ch:
        raise EngineError("找不到 data/character.json")
    return ch


def _mods() -> dict:
    return {k: (int(v) - 10) // 2 for k, v in _character().get("abilities", {}).items()}


def _items() -> dict:
    return data("items")


def _find_item(name_or_id: str):
    """(item_id, item) for an id or a display name; None when unknown."""
    items = _items()
    if name_or_id in items:
        return name_or_id, items[name_or_id]
    for iid, it in items.items():
        if it.get("name") == name_or_id:
            return iid, it
    return None


def _equipment(st: dict) -> dict:
    eq = dict(_character().get("equipment", {}))
    eq.update(st.get("equipment") or {})
    return eq


def _equipped_items(st: dict) -> list:
    items = _items()
    return [items[i] for i in _equipment(st).values() if i and i in items]


def _player_ac(st: dict) -> int:
    ch = _character()
    return int(ch.get("base_ac", 10)) + _mods().get("dex", 0) + sum(int(it.get("ac", 0)) for it in _equipped_items(st))


def _weapon(st: dict, mode: str):
    """(item_id, item) for the hero's melee or ranged weapon. Fists when unarmed."""
    eq = _equipment(st)
    if mode == "ranged":
        iid = eq.get("ranged")
        if not iid:
            raise EngineError("沒有裝備遠程武器")
        item = _items().get(iid)
        ammo = item.get("ammo")
        if ammo and int(st.get(ammo, 0)) <= 0:
            raise EngineError(f"{item['name']}沒有{ammo and '箭'}了")
        return iid, item
    iid = eq.get("weapon")
    if iid and iid in _items():
        return iid, _items()[iid]
    return "fists", {"name": "拳頭", "damage": "d4", "slot": "weapon"}


def _attack_numbers(st: dict, mode: str):
    """(attack bonus, damage bonus, weapon id, weapon item)."""
    mods, ch = _mods(), _character()
    iid, item = _weapon(st, mode)
    ability = "dex" if (mode == "ranged" or item.get("finesse")) else "str"
    atk = int(ch.get("proficiency", 2)) + mods.get(ability, 0) + int(item.get("attack_bonus", 0))
    dmg = mods.get(ability, 0) + int(item.get("damage_bonus", 0))
    return atk, dmg, iid, item


def _skill_bonus(verb: str) -> int:
    ability, skill = VERB_SKILL.get(verb, (None, None))
    if ability is None:
        return 0
    ch = _character()
    bonus = _mods().get(ability, 0)
    if skill in ch.get("proficient_skills", []):
        bonus += int(ch.get("proficiency", 2))
    return bonus


def _gear_mode(st: dict, verb: str):
    """(advantage sources, disadvantage sources) from equipment for this verb's skill."""
    _, skill = VERB_SKILL.get(verb, (None, None))
    adv, dis = [], []
    for it in _equipped_items(st):
        if skill in it.get("advantage", []):
            adv.append(it["name"])
        if skill in it.get("disadvantage", []):
            dis.append(it["name"])
    return adv, dis


def _combine(adv: list, dis: list) -> str:
    if adv and not dis:
        return "advantage"
    if dis and not adv:
        return "disadvantage"
    return "normal"


# ---------------------------------------------------------------- dice

def parse_die(spec: str):
    m = DIE.match(str(spec).strip())
    if not m:
        raise EngineError(f"骰子寫法不對：{spec}（要像 d20、d6+1、2d4）")
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    if not 1 <= count <= 10 or not 2 <= sides <= MAX_SIDES:
        raise EngineError(f"骰子範圍不對：{spec}")
    return count, sides, bonus


def _fixed_value(purpose: str, sides: int):
    raw = os.environ.get(FIXED_ENV)
    if not raw:
        return None
    try:
        table = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(table, dict):
        return None
    used = read_json(FIXED_USED, {}) or {}
    if not isinstance(used, dict):
        used = {}
    for key, values in table.items():
        if not isinstance(values, list) or key.lower() not in purpose.lower():
            continue
        idx = int(used.get(key, 0))
        if idx >= len(values):
            continue
        value = values[idx]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= sides:
            continue
        used[key] = idx + 1
        atomic_write(FIXED_USED, used)
        return value
    return None


def _existing_roll_ids(st: dict) -> set:
    ids = set()
    if ROLLS.exists():
        try:
            for line in ROLLS.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    ids.add(json.loads(line).get("roll_id"))
        except (OSError, json.JSONDecodeError):
            pass
    for rec in st.get("recent_results", []):
        for r in rec.get("rolls", []):
            ids.add(r.get("roll_id"))
    return ids


class Resolution:
    """One game action. Collects rolls and effects until commit()."""

    def __init__(self, st: dict, kind: str):
        self.state = st
        self.kind = kind
        self.rolls = []
        self.effects = []
        self.revealed = []
        self.down = None
        self.strikes = []
        self.lines = []
        self._said = set()
        self._used = _existing_roll_ids(st)

    def say(self, text: str, rolls) -> None:
        """One plain line per swing or check for the DM to paste, ending in its tickets."""
        self.lines.append(" ".join([text] + [r["ticket"] for r in rolls]))
        self._said.update(r["roll_id"] for r in rolls)

    def roll(self, sides: int, purpose: str, modifier: int = 0) -> dict:
        if isinstance(sides, bool) or not isinstance(sides, int) or not 2 <= sides <= MAX_SIDES:
            raise EngineError(f"sides 必須是 2 到 {MAX_SIDES} 的整數")
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > MAX_PURPOSE:
            raise EngineError(f"purpose 必須是 1 到 {MAX_PURPOSE} 個字")
        purpose = purpose.strip()
        for _ in range(100):
            rid = "r-" + secrets.token_hex(3)
            if rid not in self._used:
                break
        else:
            raise EngineError("無法產生新的 roll_id")
        fixed = _fixed_value(purpose, sides)
        value = secrets.randbelow(sides) + 1 if fixed is None else fixed
        rec = {"roll_id": rid, "purpose": purpose, "sides": sides, "value": value,
               "modifier": int(modifier), "total": value + int(modifier),
               "ticket": f"[R:{rid}={value}]"}
        if fixed is not None:
            rec["source"] = "fixed"
        self.rolls.append(rec)
        self._used.add(rid)
        return rec

    def d20(self, purpose: str, bonus: int, mode: str = "normal"):
        """A d20 test. Advantage / disadvantage roll two and keep one; both dice are ticketed."""
        first = self.roll(20, purpose, bonus)
        if mode == "normal":
            return first, [first]
        second = self.roll(20, purpose, bonus)
        pick = max if mode == "advantage" else min
        chosen = pick(first, second, key=lambda r: r["value"])
        return chosen, [first, second]

    def damage(self, spec: str, purpose: str, bonus: int = 0, crit: bool = False):
        """Weapon damage: dice (doubled on a crit) plus a flat bonus, floor 1."""
        count, sides, flat = parse_die(spec)
        recs = [self.roll(sides, purpose) for _ in range(count * (2 if crit else 1))]
        return max(1, sum(r["value"] for r in recs) + flat + int(bonus)), recs


# ---------------------------------------------------------------- dice lines

STRIKE_VERB = {"ambush": "偷襲", "counter": "反擊", "retreat": "追擊", "provoke": "出手"}
AMOUNT_LABEL = {"copper": "銅幣", "arrows": "箭", "damage": "傷害"}


def _signed(n: int) -> str:
    return f"＋{n}" if n >= 0 else f"－{-n}"


def _expr(rolls: list, chosen: dict, mode: str = "normal") -> str:
    """8＋3＝11; 優勢 3、18 取 18＋2＝20. A zero bonus shows the face alone."""
    face = str(chosen["value"]) if not chosen["modifier"] else \
        f"{chosen['value']}{_signed(chosen['modifier'])}＝{chosen['total']}"
    if mode in ("advantage", "disadvantage") and len(rolls) == 2:
        tag = "優勢" if mode == "advantage" else "劣勢"
        return f"{tag} {rolls[0]['value']}、{rolls[1]['value']} 取 {face}"
    return face


def _verdict(r: dict, ok: bool, attack: bool = False) -> str:
    v = r["value"]
    if attack:
        return "重擊" if v == 20 else "命中" if ok else "大失手" if v == 1 else "落空"
    return "大成功" if v == 20 and ok else "成功" if ok else "大失敗" if v == 1 else "失敗"


def _dice_text(res: "Resolution") -> str:
    lines = list(res.lines)
    for r in res.rolls:  # a roll nobody described still gets its ticket pasted
        if r["roll_id"] not in res._said:
            lines.append(f"{r['purpose']} {r['value']} {r['ticket']}")
    return "\n".join(lines) or "（本回合無擲骰）"


# ---------------------------------------------------------------- commit

def commit(st: dict, result: dict) -> dict:
    st["version"] = int(st.get("version", 0)) + 1
    res = dict(result)
    res["resolution_id"] = "x-" + secrets.token_hex(4)
    res["version"] = st["version"]
    res["at"] = now()
    st["last_result"] = res
    recent = list(st.get("recent_results", []))
    recent.append({
        "resolution_id": res["resolution_id"], "version": res["version"], "kind": res.get("kind"),
        "rolls": [{"roll_id": r["roll_id"], "value": r["value"], "purpose": r["purpose"]}
                  for r in res.get("rolls", [])],
    })
    st["recent_results"] = recent[-RECENT_LIMIT:]
    atomic_write(STATE, st)
    warning = _write_logs(res)
    if warning:
        res["log_warning"] = warning
    return res


def _write_logs(res: dict):
    try:
        for r in res.get("rolls", []):
            _append(ROLLS, {**r, "resolution_id": res["resolution_id"],
                            "version": res["version"], "at": res["at"]})
        _append(EVENTS, {k: v for k, v in res.items() if k != "rolls"})
    except OSError as exc:
        return f"日誌寫入失敗：{type(exc).__name__}: {exc}"
    return None


# ---------------------------------------------------------------- actors

def _actor(actor_id: str) -> dict:
    _valid_key(actor_id, "角色代號")
    actor = data("actors").get(actor_id)
    if not actor:
        raise EngineError(f"沒有這個角色：{actor_id}")
    return actor


def _actor_hp(st: dict, actor_id: str) -> int:
    if actor_id in st["enemies"]:
        return int(st["enemies"][actor_id])
    return int(data("actors").get(actor_id, {}).get("hp", 0))


def _is_down(st: dict, actor_id: str) -> bool:
    return _actor_hp(st, actor_id) <= 0 or bool(st["flags"].get(f"down:{actor_id}"))


def _is_hostile(st: dict, actor_id: str) -> bool:
    return bool(data("actors").get(actor_id, {}).get("hostile")) or bool(st["flags"].get(f"hostile:{actor_id}"))


def _attitude(st: dict, actor_id: str) -> str:
    if _is_hostile(st, actor_id):
        return "hostile"
    return data("actors").get(actor_id, {}).get("attitude", "neutral")


def _in_scene(card: dict, actor_id: str) -> bool:
    return actor_id in card["visible"].get("actors", [])


def _verbs_for(st: dict, actor_id: str) -> list:
    actor = _actor(actor_id)
    if _is_down(st, actor_id):
        return []
    if actor.get("protected"):
        verbs = ["persuade"]            # never violence; a pickpocket is fine
    elif actor.get("beast"):
        verbs = ["attack", "provoke"]
    else:
        verbs = ["persuade", "provoke", "attack"]
    if actor.get("wallet") or actor.get("loot"):
        verbs.append("steal")
    if actor.get("guards"):
        verbs += list(GUARD_VERBS)
    return verbs


def _check_terms(st: dict, actor_id: str, verb: str):
    """(dc, mode, why) for a verb against an actor, from attitude, leverage, alert and gear."""
    actor, flags = _actor(actor_id), st["flags"]
    dc = ATTITUDE_DC.get(_attitude(st, actor_id), 15)
    adv, dis, why = [], [], []
    for flag, effect in (actor.get("leverage") or {}).items():
        if flags.get(flag):
            if effect == "advantage":
                adv.append(flag)
            else:
                dc -= 5
                why.append(f"籌碼 {flag}：DC 降一檔")
    if flags.get(f"alert:{actor_id}"):
        dis.append("alert")
        why.append("對方警戒：劣勢")
    gear_adv, gear_dis = _gear_mode(st, verb)
    adv += gear_adv
    dis += gear_dis
    why += [f"{g}：優勢" for g in gear_adv] + [f"{g}：劣勢" for g in gear_dis] + [f"{a}：優勢" for a in adv if a not in gear_adv]
    return max(DC_MIN, min(DC_MAX, dc)), _combine(adv, dis), why


def _guard_cleared(st: dict, actor_id: str) -> bool:
    flags = st["flags"]
    return _is_down(st, actor_id) or any(flags.get(f"{k}:{actor_id}") for k in ("passed", "convinced", "bribed"))


def _exit_open(st: dict, ex: dict) -> bool:
    flags = st["flags"]
    if any(not flags.get(f) for f in ex.get("requires", [])):
        return False
    any_of = ex.get("requires_any", [])
    if any_of and not any(flags.get(f) for f in any_of):
        return False
    guard = ex.get("guarded_by")
    if guard and not _guard_cleared(st, guard):
        return False
    return True


def _clear_tried(st: dict) -> None:
    for k in [k for k in st["flags"] if k.startswith("tried:")]:
        del st["flags"][k]


def _set_flag(res: Resolution, flag: str) -> None:
    st = res.state
    if not st["flags"].get(flag):
        st["flags"][flag] = True
        res.effects.append(f"旗標 {flag} 成立")
        _reveal(res, flag)


def _reveal(res: Resolution, flag: str) -> None:
    card = scene_card(res.state["location"])
    for clue in card["judge_only"].get("clues", []):
        if clue.get("flag") == flag and clue.get("text") not in res.revealed:
            res.revealed.append(clue["text"])


def _amount(res: Resolution, spec, purpose: str) -> int:
    if isinstance(spec, int) and not isinstance(spec, bool):
        return spec
    text = str(spec).strip()
    sign = -1 if text.startswith("-") else 1
    body = text.lstrip("+-")
    if body.isdigit():
        return sign * int(body)
    count, sides, flat = parse_die(body)
    recs = [res.roll(sides, purpose) for _ in range(count)]
    total = sum(r["value"] for r in recs) + flat
    res.say(f"{AMOUNT_LABEL.get(purpose.rsplit(':', 1)[-1], '骰')} {body} → {total}", recs)
    return sign * total


def _give_item(res: Resolution, name: str) -> None:
    st = res.state
    if name not in st["inventory"]:
        st["inventory"].append(name)
    res.effects.append(f"獲得物品：{name}")


# ---------------------------------------------------------------- combat

def _combat_flag(st: dict) -> str:
    return f"combat:{st['location']}"


def _hostiles_present(st: dict, card: dict) -> list:
    return [a for a in card["visible"].get("actors", []) if _is_hostile(st, a) and not _is_down(st, a)]


def _down_player(res: Resolution, cause: str) -> None:
    st = res.state
    before = st["copper"]
    st["copper"] = max(0, before - DOWN_COPPER_COST)
    st["hp"] = st["max_hp"]
    st["location"] = HOME_SCENE
    st["flags"]["downed"] = int(st["flags"].get("downed", 0)) + 1
    for k in [k for k in st["flags"] if k.startswith("combat:")]:
        del st["flags"][k]
    _clear_tried(st)
    res.down = {"cause": cause, "moved_to": HOME_SCENE, "copper_before": before,
                "copper_after": st["copper"], "hp_restored": st["hp"]}
    res.effects.append(f"倒地：醒來時在{HOME_SCENE}，銅幣 {before} → {st['copper']}，HP 補滿")


def _damage_player(res: Resolution, amount: int, cause: str) -> dict:
    st = res.state
    before = st["hp"]
    st["hp"] = max(0, before - int(amount))
    res.effects.append(f"受到 {amount} 點傷害，HP {before} → {st['hp']}")
    out = {"amount": int(amount), "hp_before": before, "hp_after": st["hp"]}
    if st["hp"] <= 0:
        _down_player(res, cause)
    return out


def _strike(res: Resolution, actor_id: str, purpose: str):
    """One attack by an actor against the hero. None when the actor is down."""
    st = res.state
    if res.down or _is_down(st, actor_id):
        return None
    actor = _actor(actor_id)
    ac = _player_ac(st)
    atk, _ = res.d20(f"{purpose}:{actor_id}", int(actor.get("attack_bonus", 0)))
    natural = atk["value"]
    hit = natural != 1 and (natural == 20 or atk["total"] >= ac)
    out = {"actor": actor_id, "actor_name": actor["name"], "roll": atk, "player_ac": ac,
           "hit": hit, "crit": natural == 20}
    res.effects.append(f"{actor['name']}出手" + ("，重擊！" if natural == 20 else "，打中了" if hit else "，落空"))
    st["flags"][_combat_flag(st)] = True   # before damage: going down clears every combat flag
    line = f"{actor['name']}{STRIKE_VERB.get(purpose, '出手')} {_expr([atk], atk)}，對你的 AC {ac}，{_verdict(atk, hit, attack=True)}"
    if hit:
        dmg, recs = res.damage(actor.get("damage", "d4"), f"{purpose}_damage:{actor_id}", crit=natural == 20)
        res.say(f"{line}，傷害 {dmg}", [atk] + recs)
        out["damage_rolls"] = recs
        out["damage"] = _damage_player(res, dmg, f"{purpose}:{actor_id}")
    else:
        res.say(line, [atk])
    res.strikes.append(out)
    return out


def _enemies_act(res: Resolution, card: dict, purpose: str = "counter", skip: str = None) -> list:
    """Every hostile still standing takes a swing. Called after the hero's action in combat."""
    outs = []
    already = {s["actor"] for s in res.strikes}  # an actor who already swung this action is done
    for aid in _hostiles_present(res.state, card):
        if res.down:
            break
        if aid == skip or aid in already:
            continue
        out = _strike(res, aid, purpose)
        if out:
            outs.append(out)
    return outs


def _loot(actor: dict) -> list:
    loot = actor.get("loot") or []
    return [loot] if isinstance(loot, str) else list(loot)


def _drop_loot(res: Resolution, actor_id: str) -> None:
    """What nobody stole off a downed actor falls to the hero, as if stolen."""
    st, actor = res.state, _actor(actor_id)
    if st["flags"].get(f"stole:{actor_id}") or not _loot(actor):
        return
    for name in _loot(actor):
        if name not in st["inventory"]:
            _give_item(res, name)
    _apply_outcomes(res, actor.get("on_stolen", []), f"looted:{actor_id}")


def _apply_outcomes(res: Resolution, outcomes, source: str) -> None:
    """Each outcome may carry "if": [flags]; it applies only when all are set."""
    st = res.state
    for o in outcomes or []:
        if res.down:
            break
        if any(not st["flags"].get(f) for f in o.get("if", [])):
            continue
        if "set_flag" in o:
            _set_flag(res, o["set_flag"])
        elif "clear_flag" in o:
            st["flags"].pop(o["clear_flag"], None)
            res.effects.append(f"旗標 {o['clear_flag']} 清除")
        elif "copper" in o:
            delta = _amount(res, o["copper"], f"{source}:copper")
            before = st["copper"]
            st["copper"] = max(0, before + delta)
            res.effects.append(f"銅幣 {before} → {st['copper']}")
        elif "arrows" in o:
            delta = _amount(res, o["arrows"], f"{source}:arrows")
            st["arrows"] = max(0, int(st.get("arrows", 0)) + delta)
            res.effects.append(f"箭 {st['arrows']} 支")
        elif "damage" in o:
            amount = _amount(res, o["damage"], f"{source}:damage")
            _damage_player(res, abs(amount), source)
        elif "item" in o:
            _give_item(res, o["item"])
        elif "strike" in o or "ambush" in o:
            _strike(res, o.get("strike") or o.get("ambush"), "ambush")
        elif "move" in o:
            _forced_move(res, o["move"])


def _forced_move(res: Resolution, target: str) -> None:
    st = res.state
    card = scene_card(target)
    st["flags"].pop(_combat_flag(st), None)
    st["location"] = target
    _clear_tried(st)
    res.effects.append(f"被帶到{card['visible'].get('title', target)}")
    _on_enter(res, card)


def _on_enter(res: Resolution, card: dict) -> None:
    """Hostile actors that ambush strike once when the hero walks in."""
    st = res.state
    for aid in card["visible"].get("actors", []):
        if res.down:
            break
        if data("actors").get(aid, {}).get("ambush") and _is_hostile(st, aid) and not _is_down(st, aid):
            _strike(res, aid, "ambush")


def _public(res: Resolution, out: dict) -> dict:
    st = res.state
    out["effects"] = res.effects
    out["revealed"] = res.revealed
    if res.strikes:
        out["strikes"] = res.strikes
    out["player_hp_after"] = st["hp"]
    out["copper_after"] = st["copper"]
    out["location_after"] = st["location"]
    out["combat"] = bool(st["flags"].get(_combat_flag(st)))
    if res.down:
        out["player_down"] = True
        out["down"] = res.down
    out["rolls"] = res.rolls
    # ready-made lines the DM pastes at the end; the first live run showed it
    # skipping tickets in busy rounds when it had to assemble them itself
    out["dice"] = _dice_text(res)
    return out


# ---------------------------------------------------------------- read-only ops

def objective(st: dict) -> str:
    flags = st.get("flags", {})
    for rule in read_json(DATA / "quest.json", []) or []:
        if all(flags.get(f) for f in rule.get("all", [])) and \
           (not rule.get("any") or any(flags.get(f) for f in rule["any"])):
            return rule.get("text", "")
    return ""


def _item_desc(st: dict, name: str):
    """What the hero reads on an item. Some texts need an item worn (the rat's
    letter needs the strange glasses); until then the DM only gets desc_locked."""
    found = _find_item(name)
    if not found:
        return None
    iid, item = found
    need = item.get("needs")
    if need and need not in _equipment(st).values():
        return item.get("desc_locked", "你看不懂。")
    return item.get("desc")


def hero_sheet(st: dict) -> dict:
    """What the hero can do right now: AC, attacks, equipment by name."""
    items, eq = _items(), _equipment(st)
    melee_atk, melee_dmg, _, melee = _attack_numbers(st, "melee")
    sheet = {
        "ac": _player_ac(st),
        "abilities": _mods(),
        "equipment": {slot: (items.get(iid, {}).get("name") if iid else None) for slot, iid in eq.items()},
        "melee": {"weapon": melee["name"], "attack_bonus": melee_atk, "damage": f"{melee['damage']}{melee_dmg:+d}"},
        "arrows": int(st.get("arrows", 0)),
        "inventory": [{"name": n, "desc": _item_desc(st, n)} for n in st.get("inventory", [])],
    }
    if eq.get("ranged"):
        try:
            r_atk, r_dmg, _, ranged = _attack_numbers(st, "ranged")
            sheet["ranged"] = {"weapon": ranged["name"], "attack_bonus": r_atk, "damage": f"{ranged['damage']}{r_dmg:+d}"}
        except EngineError as exc:
            sheet["ranged"] = {"weapon": items[eq["ranged"]]["name"], "unusable": str(exc)}
    return sheet


def op_get_state(st: dict) -> dict:
    return {"state": {k: st.get(k) for k in GAME_FIELDS},
            "hero": hero_sheet(st),
            "objective": objective(st),
            "version": st.get("version", 0),
            "last_result": st.get("last_result")}


def op_get_current_scene(st: dict) -> dict:
    card = scene_card(st["location"])
    vis, jo, flags = card["visible"], card["judge_only"], st["flags"]
    actors_data = data("actors")
    exits = []
    for xid, ex in vis.get("exits", {}).items():
        opened = _exit_open(st, ex)
        entry = {"id": xid, "title": ex.get("title", xid), "open": opened}
        if not opened and ex.get("locked_hint"):
            entry["hint"] = ex["locked_hint"]
        if ex.get("guarded_by"):
            entry["guarded_by"] = ex["guarded_by"]
        exits.append(entry)
    actors = []
    for aid in vis.get("actors", []):
        a = actors_data.get(aid, {})
        down = _is_down(st, aid)
        entry = {"id": aid, "name": a.get("name", aid), "look": a.get("look", ""),
                 "hostile": _is_hostile(st, aid), "attitude": _attitude(st, aid),
                 "down": down, "verbs": _verbs_for(st, aid)}
        if a.get("guards"):
            entry["guards"] = a["guards"]
        if a.get("protected"):
            entry["protected"] = True
        if down:
            entry["state"] = "倒下" if a.get("lethal") else "被打趴"
        actors.append(entry)
    features = []
    for fid, fe in vis.get("features", {}).items():
        entry = {"id": fid, "title": fe.get("title", fid), "rules": fe.get("rules", [])}
        if fe.get("hint"):
            entry["hint"] = fe["hint"]
        features.append(entry)
    features.append({"id": IMPROVISE_TARGET, "title": "其他自由行動（只擲骰看演得好不好，不改變世界）",
                     "rules": [IMPROVISE_RULE]})
    ending = None
    for flag, text in jo.get("epilogue", {}).items():
        if flags.get(flag):
            ending = text
            break
    return {
        "scene": st["location"],
        "title": vis.get("title", st["location"]),
        "description": vis.get("description", ""),
        "actors": actors,
        "exits": exits,
        "features": features,
        "clues": [c["text"] for c in jo.get("clues", []) if flags.get(c.get("flag"))],
        "combat": bool(flags.get(_combat_flag(st))),
        "game_over": bool(flags.get("ending")),
        "ending": ending,
    }


# ---------------------------------------------------------------- write ops

def op_resolve_attack(st: dict, target, mode: str = "melee") -> dict:
    if mode not in ("melee", "ranged"):
        raise EngineError("mode 只能是 melee 或 ranged")
    actor = _actor(target)
    card = scene_card(st["location"])
    if not _in_scene(card, target):
        raise EngineError(f"{actor['name']}不在目前的場景")
    if actor.get("protected"):
        raise EngineError(f"不能對{actor['name']}動手。這是越線的事，艾玲不做")
    if _is_down(st, target):
        raise EngineError(f"{actor['name']}已經{'倒下' if actor.get('lethal') else '被打趴'}了")
    atk_bonus, dmg_bonus, wid, weapon = _attack_numbers(st, mode)
    combat_before = bool(st["flags"].get(_combat_flag(st)))
    res = Resolution(st, "attack")
    roll_mode = "disadvantage" if (mode == "ranged" and combat_before) else "normal"
    atk, atk_rolls = res.d20(f"attack:{target}", atk_bonus, roll_mode)
    natural = atk["value"]
    hit = natural != 1 and (natural == 20 or atk["total"] >= int(actor["ac"]))
    out = {"kind": "attack", "target": target, "target_name": actor["name"], "mode": mode,
           "weapon": weapon["name"], "attack": atk, "attack_rolls": atk_rolls, "attack_mode": roll_mode,
           "attack_bonus": atk_bonus, "target_ac": int(actor["ac"]), "hit": hit,
           "crit": natural == 20, "fumble": natural == 1}
    if mode == "ranged" and weapon.get("ammo"):
        st[weapon["ammo"]] = int(st.get(weapon["ammo"], 0)) - 1
        out["arrows_left"] = st[weapon["ammo"]]
    if not actor.get("hostile"):
        _set_flag(res, f"hostile:{target}")
    hp_before = _actor_hp(st, target)
    hp_after = hp_before
    line = (f"{'射擊' if mode == 'ranged' else '攻擊'}{actor['name']} {_expr(atk_rolls, atk, roll_mode)}，"
            f"對 AC {int(actor['ac'])}，{_verdict(atk, hit, attack=True)}")
    if hit:
        dmg, recs = res.damage(weapon["damage"], f"damage:{target}", dmg_bonus, crit=natural == 20)
        res.say(f"{line}，傷害 {dmg}", atk_rolls + recs)
        hp_after = max(0, hp_before - dmg)
        st["enemies"][target] = hp_after
        out.update({"damage": dmg, "damage_rolls": recs})
    else:
        res.say(line, atk_rolls)
    out.update({"enemy_hp_before": hp_before, "enemy_hp_after": hp_after, "enemy_defeated": hp_after == 0})
    if hp_after == 0:
        _set_flag(res, f"down:{target}")
        res.effects.append(f"{actor['name']}{'倒下' if actor.get('lethal') else '被打趴'}")
        _drop_loot(res, target)
        _apply_outcomes(res, actor.get("on_down", []), f"down:{target}")
        group = card["judge_only"].get("on_all_down")
        if group and all(_is_down(st, a) for a in group.get("actors", [])):
            _apply_outcomes(res, group.get("outcomes", []), "all_down")
    else:
        _apply_outcomes(res, actor.get("on_attacked", []), f"attacked:{target}")
    first_arrow = mode == "ranged" and not combat_before
    st["flags"][_combat_flag(st)] = True
    if first_arrow:
        res.effects.append("敵人還沒近身，這一箭沒有反擊")
    elif not res.down:
        _enemies_act(res, card, "counter")
    if not _hostiles_present(st, card):
        st["flags"].pop(_combat_flag(st), None)
    st["turn"] = int(st.get("turn", 0)) + 1
    return commit(st, _public(res, out))


def op_move_to(st: dict, target) -> dict:
    _valid_key(target, "場景代號")
    cur = scene_card(st["location"])
    exits = cur["visible"].get("exits", {})
    if target not in exits:
        raise EngineError(f"從{cur['visible'].get('title', st['location'])}到不了 {target}")
    ex = exits[target]
    if not _exit_open(st, ex):
        raise EngineError(ex.get("locked_hint", "這條路現在走不了"))
    dest = scene_card(target)
    res = Resolution(st, "move")
    out = {"kind": "move", "from": st["location"], "to": target}
    if st["flags"].get(_combat_flag(st)):
        out["retreat"] = _enemies_act(res, cur, "retreat")
    if not res.down:
        st["flags"].pop(_combat_flag(st), None)
        st["location"] = target
        _clear_tried(st)
        _on_enter(res, dest)
    st["turn"] = int(st.get("turn", 0)) + 1
    return commit(st, _public(res, out))


def _check_feature(st: dict, res: Resolution, rules: dict, rule_id: str, target_id: str, card: dict) -> dict:
    feature = card["visible"]["features"][target_id]
    if rule_id not in feature.get("rules", []):
        raise EngineError(f"「{feature.get('title', target_id)}」不能用 {rules[rule_id]['name']}；"
                          f"可用：{', '.join(feature.get('rules', [])) or '（無）'}")
    spec = card["judge_only"].get("features", {}).get(target_id, {}).get(rule_id)
    if spec is None:
        raise EngineError(f"場景資料缺少 {target_id}.{rule_id} 的規則設定")
    flags = st["flags"]
    once = spec.get("once")
    if once and flags.get(once):
        raise EngineError(spec.get("once_hint", "這件事已經做過了"))
    if any(flags.get(f) for f in spec.get("forbids", [])):
        raise EngineError(spec.get("forbids_hint", "現在做不了這件事"))
    if any(not flags.get(f) for f in spec.get("requires", [])):
        raise EngineError(spec.get("requires_hint", "條件還不成立"))
    if int(spec.get("requires_copper", 0)) > int(st["copper"]):
        raise EngineError(f"銅幣不夠：需要 {spec['requires_copper']}，只有 {st['copper']}")
    tried_key = f"tried:{rule_id}:{target_id}"
    if flags.get(tried_key):
        raise EngineError("這個方法剛才已經失敗過。換個方法、休息，或離開再回來")
    out = {"kind": "check", "rule": rule_id, "rule_name": rules[rule_id]["name"],
           "target": target_id, "target_title": feature.get("title", target_id)}
    if rules[rule_id].get("check") is None:
        success, out["dc"], out["roll"] = True, None, None
    else:
        dc = int(spec.get("dc", 15))
        bonus = _skill_bonus(rule_id)
        adv, dis = _gear_mode(st, rule_id)
        mode = _combine(adv, dis)
        r, rolls = res.d20(f"check:{rule_id}:{target_id}", bonus, mode)
        success = r["value"] != 1 and (r["value"] == 20 or r["total"] >= dc)
        res.say(f"{rules[rule_id]['name']}{feature.get('title', target_id)} {_expr(rolls, r, mode)}，"
                f"對 DC {dc}，{_verdict(r, success)}", rolls)
        out.update({"dc": dc, "roll": r, "check_rolls": rolls, "mode": mode, "bonus": bonus,
                    "check": rules[rule_id].get("check")})
    out["success"] = success
    if success:
        _apply_outcomes(res, spec.get("success", []), f"{rule_id}:{target_id}")
    else:
        flags[tried_key] = True
        _apply_outcomes(res, spec.get("fail", []), f"{rule_id}:{target_id}")
    return out


def _check_actor(st: dict, res: Resolution, rules: dict, verb: str, actor_id: str) -> dict:
    actor = _actor(actor_id)
    flags = st["flags"]
    if verb == "attack":
        raise EngineError("攻擊請用 resolve_attack")
    verbs = _verbs_for(st, actor_id)
    if verb not in verbs:
        if actor.get("protected") and verb != "persuade":
            raise EngineError(f"不能對{actor['name']}做這件事。這是越線的事，艾玲不做")
        if _is_down(st, actor_id):
            raise EngineError(f"{actor['name']}已經倒下，不用再對他做什麼")
        raise EngineError(f"對{actor['name']}不能用{rules[verb]['name']}；可用：{', '.join(verbs)}")
    once = {"persuade": f"convinced:{actor_id}", "steal": f"stole:{actor_id}",
            "sneak": f"passed:{actor_id}", "distract": f"passed:{actor_id}"}.get(verb)
    if once and flags.get(once):
        raise EngineError({"persuade": f"{actor['name']}已經被你說動了",
                           "steal": f"{actor['name']}身上能摸的都摸過了"}.get(verb, f"你已經繞過{actor['name']}了"))
    tried_key = f"tried:{verb}:{actor_id}"
    if flags.get(tried_key):
        raise EngineError("這個方法剛才已經失敗過。換個方法、休息，或離開再回來")
    out = {"kind": "check", "rule": verb, "rule_name": rules[verb]["name"],
           "target": actor_id, "target_title": actor["name"], "attitude": _attitude(st, actor_id)}

    if verb == "provoke":
        out.update({"dc": None, "roll": None, "success": True})
        _set_flag(res, f"hostile:{actor_id}")
        if actor.get("on_provoke"):
            _apply_outcomes(res, actor["on_provoke"], f"provoke:{actor_id}")
        else:
            out["strike"] = _strike(res, actor_id, "provoke")
            if actor.get("fines") and not res.down:
                before = st["copper"]
                st["copper"] = max(0, before - int(actor["fines"]))
                res.effects.append(f"{actor['name']}罰你 {actor['fines']} 銅幣，{before} → {st['copper']}")
        return out

    dc, mode, why = _check_terms(st, actor_id, verb)
    bonus = _skill_bonus(verb)
    r, rolls = res.d20(f"check:{verb}:{actor_id}", bonus, mode)
    success = r["value"] != 1 and (r["value"] == 20 or r["total"] >= dc)
    res.say(f"{rules[verb]['name']}{actor['name']} {_expr(rolls, r, mode)}，對 DC {dc}，{_verdict(r, success)}", rolls)
    out.update({"dc": dc, "roll": r, "check_rolls": rolls, "mode": mode, "bonus": bonus, "why": why,
                "check": rules[verb].get("check"), "success": success})
    hostile = _is_hostile(st, actor_id)
    if verb == "persuade":
        if success:
            _set_flag(res, f"convinced:{actor_id}")
            _apply_outcomes(res, actor.get("on_convinced", []), f"convinced:{actor_id}")
        else:
            flags[tried_key] = True
            if actor.get("on_persuade_fail"):
                _apply_outcomes(res, actor["on_persuade_fail"], f"persuade_fail:{actor_id}")
            elif hostile:
                out["strike"] = _strike(res, actor_id, "provoke")
    elif verb in GUARD_VERBS:
        if success:
            _set_flag(res, f"passed:{actor_id}")
        else:
            flags[tried_key] = True
            _set_flag(res, f"alert:{actor_id}")
            if hostile:
                out["strike"] = _strike(res, actor_id, "provoke")
    elif verb == "steal":
        if success:
            if actor.get("wallet"):
                gain = _amount(res, "+" + str(actor["wallet"]), f"steal:{actor_id}:copper")
                before = st["copper"]
                st["copper"] = before + gain
                res.effects.append(f"銅幣 {before} → {st['copper']}")
            for name in _loot(actor):
                if name not in st["inventory"]:
                    _give_item(res, name)
            _set_flag(res, f"stole:{actor_id}")
            _apply_outcomes(res, actor.get("on_stolen", []), f"stolen:{actor_id}")
        else:
            flags[tried_key] = True
            _set_flag(res, f"alert:{actor_id}")
            if actor.get("fines") and not res.down:
                before = st["copper"]
                st["copper"] = max(0, before - int(actor["fines"]))
                res.effects.append(f"{actor['name']}抓到你的手，罰 {actor['fines']} 銅幣，{before} → {st['copper']}")
            if hostile:
                out["strike"] = _strike(res, actor_id, "provoke")
    return out


def op_resolve_check(st: dict, rule_id, target_id) -> dict:
    _valid_key(rule_id, "規則代號")
    _valid_key(target_id, "目標代號")
    rules = data("rules")
    if rule_id == "attack":
        raise EngineError("攻擊請用 resolve_attack")
    if rule_id not in rules:
        raise EngineError(f"沒有這條規則：{rule_id}；可用：{', '.join(k for k in rules if k != 'attack')}")
    card = scene_card(st["location"])
    res = Resolution(st, "check")
    if target_id == IMPROVISE_TARGET:
        if rule_id != IMPROVISE_RULE:
            raise EngineError(f"「{IMPROVISE_TARGET}」只接受 {IMPROVISE_RULE}；要對某個目標做事請用它的代號")
        r, rolls = res.d20(f"check:{IMPROVISE_RULE}:{IMPROVISE_TARGET}", 0)
        res.say(f"{rules[rule_id]['name']} {_expr(rolls, r)}，對 DC {IMPROVISE_DC}，"
                f"{_verdict(r, r['value'] >= IMPROVISE_DC)}", rolls)
        out = {"kind": "check", "rule": rule_id, "rule_name": rules[rule_id]["name"],
               "target": IMPROVISE_TARGET, "target_title": "自由行動", "dc": IMPROVISE_DC, "roll": r,
               "check_rolls": rolls, "check": rules[rule_id].get("check"),
               "success": r["value"] >= IMPROVISE_DC, "narrative_only": True}
    elif rule_id == IMPROVISE_RULE:
        raise EngineError(f"{IMPROVISE_RULE} 只能對「{IMPROVISE_TARGET}」用；對「{target_id}」請選它列出的規則")
    elif target_id in card["visible"].get("features", {}):
        out = _check_feature(st, res, rules, rule_id, target_id, card)
    elif _in_scene(card, target_id):
        out = _check_actor(st, res, rules, rule_id, target_id)
    else:
        options = list(card["visible"].get("features", {})) + list(card["visible"].get("actors", []))
        raise EngineError(f"這個場景沒有「{target_id}」；可用：{', '.join(options) or '（無）'}，或 here")
    if st["flags"].get(_combat_flag(st)) and not res.down:
        # the action may have moved the hero (thrown into the cellar): act with the scene she is in now
        _enemies_act(res, scene_card(st["location"]), "counter")
    st["turn"] = int(st.get("turn", 0)) + 1
    return commit(st, _public(res, out))


def op_roll(st: dict, dice, purpose=None) -> dict:
    """A bare roll such as d20+2 or 2d6, ticketed and logged like any other die.

    Days 15–17 of the series expose it as the `roll` tool, taking `dice` the way
    Day 15's own dice server did. The release does not: every die there lives in
    a resolution (attack, check, rest), so it always has a consequence."""
    if not isinstance(dice, str) or not dice.strip():
        raise EngineError("dice 要寫成 d20、d20+2、2d6 這種格式")
    spec = dice.strip().lower()
    count, sides, flat = parse_die(spec)
    res = Resolution(st, "roll")
    recs = [res.roll(sides, purpose or f"roll:{spec}") for _ in range(count)]
    total = sum(r["value"] for r in recs) + flat
    faces = "、".join(str(r["value"]) for r in recs)
    shown = f"{faces}{_signed(flat)}＝{total}" if flat else (f"{faces}＝{total}" if count > 1 else faces)
    res.say(f"{spec} {shown}", recs)
    return commit(st, _public(res, {"kind": "roll", "spec": spec, "total": total, "roll": recs[0]}))


def op_rest(st: dict) -> dict:
    card = scene_card(st["location"])
    if st["flags"].get(_combat_flag(st)) and _hostiles_present(st, card):
        raise EngineError("敵人還在旁邊，不能休息。先打完或先離開")
    res = Resolution(st, "rest")
    before = st["hp"]
    r = None
    heal = 0
    if before < st["max_hp"]:
        ch = _character()
        die, con = ch.get("hit_die", "d8"), _mods().get("con", 0)
        heal, recs = res.damage(die, "rest", con)
        r = recs[0]
        st["hp"] = min(st["max_hp"], before + heal)
        face = str(r["value"]) if not con else f"{r['value']}{_signed(con)}＝{heal}"
        res.say(f"休息 {die} {face}，HP {before} → {st['hp']}", recs)
    st["turn"] = int(st.get("turn", 0)) + 1
    _clear_tried(st)
    return commit(st, {"kind": "rest", "hp_before": before, "hp_after": st["hp"], "heal": heal,
                       "roll": r, "rolls": res.rolls, "dice": _dice_text(res)})


def op_equip(st: dict, name_or_id: str) -> dict:
    found = _find_item(str(name_or_id).strip())
    if not found:
        raise EngineError(f"沒有這件裝備：{name_or_id}")
    iid, item = found
    owned = iid in st["inventory"] or item["name"] in st["inventory"]
    eq = _equipment(st)
    if not owned and iid not in eq.values():
        raise EngineError(f"背包裡沒有{item['name']}")
    slot = item.get("slot")
    if slot not in SLOTS:
        raise EngineError(f"{item['name']}沒有可裝備的部位")
    previous = eq.get(slot)
    if previous == iid:
        raise EngineError(f"{item['name']}已經裝備著")
    for key in (iid, item["name"]):
        if key in st["inventory"]:
            st["inventory"].remove(key)
    if previous and previous in _items():
        st["inventory"].append(_items()[previous]["name"])
    eq[slot] = iid
    st["equipment"] = eq
    res = Resolution(st, "equip")
    res.effects.append(f"裝備 {item['name']}（{slot}）")
    if previous and previous in _items():
        res.effects.append(f"{_items()[previous]['name']}收進背包")
    out = {"kind": "equip", "item": item["name"], "slot": slot,
           "previous": _items().get(previous, {}).get("name") if previous else None,
           "ac": _player_ac(st), "hero": hero_sheet(st)}
    return commit(st, _public(res, out))


def slot_path(slot: str) -> pathlib.Path:
    _valid_key(slot, "存檔名稱")
    return SAVES / f"{slot}.json"


def op_save(st: dict, slot: str = "quick") -> dict:
    path = slot_path(slot or "quick")
    atomic_write(path, {k: st.get(k) for k in GAME_FIELDS + ("version",)})
    return commit(st, {"kind": "save", "slot": slot or "quick"})


def op_load(st: dict, slot: str = "quick") -> dict:
    path = slot_path(slot or "quick")
    saved = read_json(path)
    if not saved:
        raise EngineError(f"找不到存檔：{slot}")
    for k in GAME_FIELDS:
        if k in saved:
            st[k] = saved[k]
    _clear_tried(st)
    return commit(st, {"kind": "load", "slot": slot or "quick",
                       "saved_version": saved.get("version"),
                       "hp": st["hp"], "location": st["location"]})


def op_newgame() -> dict:
    seed = read_json(SEED)
    if not seed:
        raise EngineError("找不到 data/seed_state.json")
    if STATE.exists():
        try:
            op_save(load_state(), "before-newgame")
        except EngineError:
            pass
    for path in (ROLLS, EVENTS, FIXED_USED, GAME / "audit_cursor.json", GAME / "audit_blocks.json", GAME / "story.jsonl"):
        if path.exists():
            path.unlink()
    st = dict(seed)
    st["version"] = 0
    st["recent_results"] = []
    return commit(st, {"kind": "newgame"})


def op_cheat(st: dict) -> dict:
    if not (os.environ.get("DUNGEON_DEV") or (GAME / "dev").exists()):
        raise EngineError("作弊碼在正式遊戲停用。開發時建立 .game/dev 檔案，或設定 DUNGEON_DEV=1")
    before = st["hp"]
    st["hp"] = st["max_hp"]
    return commit(st, {"kind": "cheat", "hp_before": before, "hp_after": st["hp"]})
