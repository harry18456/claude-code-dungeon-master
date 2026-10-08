"""gamectl.py — the project's trusted game CLI, used by Skills through `!` expansion.

Every command goes through engine/core.py, so it shares the same commit
path as the MCP server. No model involvement.

Usage: uv run --no-project gamectl.py <status|rest|save|load|log|report|newgame|cheat> [args]
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from engine import core  # noqa: E402

try:  # Windows consoles default to cp950
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def scene_title(scene_id):
    try:
        return core.scene_card(scene_id)["visible"].get("title", scene_id)
    except core.EngineError:
        return scene_id


def cmd_status():
    st = core.load_state()
    hero = core.hero_sheet(st)
    gear = "、".join(f"{k}:{v}" for k, v in hero["equipment"].items() if v)
    print(f"HP {st['hp']}/{st['max_hp']} | AC {hero['ac']} | 銅幣 {st['copper']} | {scene_title(st['location'])} | "
          f"第 {st.get('turn', 0)} 回合 | 武器：{hero['melee']['weapon']} {hero['melee']['damage']}"
          + (f"，{hero['ranged']['weapon']}（箭 {hero['arrows']}）" if hero.get("ranged") else "")
          + f" | 裝備：{gear} | 背包：{'、'.join(st.get('inventory', [])) or '空'} | 目標：{core.objective(st)}")


def cmd_equip(*args):
    name = " ".join(a for a in args if a.strip())
    if not name:
        raise core.EngineError("要裝備什麼？例如：equip 彎刀")
    res = core.op_equip(core.load_state(), name)
    hero = res["hero"]
    line = f"已裝備 {res['item']}（{res['slot']}）"
    if res.get("previous"):
        line += f"，{res['previous']}收進背包"
    line += f"。AC {hero['ac']}，近戰 {hero['melee']['weapon']} {hero['melee']['damage']}"
    if hero.get("ranged"):
        line += f"，遠程 {hero['ranged']['weapon']} {hero['ranged'].get('damage', '')}（箭 {hero['arrows']}）"
    print(line)


def cue(name):
    """Play a sound cue. Skills run gamectl through `!` expansion, which is not a
    tool call, so the PostToolUse sound hook never sees these rolls."""
    try:
        import subprocess
        sound = core.ROOT / ".claude" / "hooks" / "sound.py"
        if not sound.exists():  # installed as a plugin: hooks/ sits at the plugin root
            sound = core.ROOT / "hooks" / "sound.py"
        subprocess.run([sys.executable, str(sound), name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except Exception:
        pass


def cmd_rest():
    res = core.op_rest(core.load_state())
    if res.get("roll"):
        cue("dice")
        print(f"短休結算完成：{res['dice']}（上限 {core.load_state()['max_hp']}）。（結算編號 {res['resolution_id']}）")
    else:
        print(f"已是滿血，HP 維持 {res['hp_after']}／{core.load_state()['max_hp']}，沒有擲骰。（結算編號 {res['resolution_id']}）")
    if res.get("log_warning"):
        print(f"警告：{res['log_warning']}")


def _slot(args):
    """Skills pass `quick $ARGUMENTS`; the last non-empty word wins."""
    words = [a for a in args if a.strip()]
    return words[-1] if words else "quick"


def cmd_save(*args):
    res = core.op_save(core.load_state(), _slot(args))
    st = core.load_state()
    print(f"已存檔：{res['slot']}（HP {st['hp']}/{st['max_hp']}，{scene_title(st['location'])}，第 {st.get('turn', 0)} 回合）")


def cmd_load(*args):
    res = core.op_load(core.load_state(), _slot(args))
    print(f"已讀檔：{res['slot']}。")
    cmd_status()


def cmd_log(n="10"):
    try:
        count = int(n)
    except (TypeError, ValueError):
        raise core.EngineError("log 的數量必須是 1 到 100 的整數")
    if not 1 <= count <= 100:
        raise core.EngineError("log 的數量必須是 1 到 100 的整數")
    if not core.EVENTS.exists():
        print("(尚無事件紀錄)")
        return
    lines = core.EVENTS.read_text(encoding="utf-8").strip().splitlines()
    for line in lines[-count:]:
        e = json.loads(line)
        kind = e.get("kind")
        if kind == "attack":
            strikes = e.get("strikes") or []
            extra = (f"用{e.get('weapon', '')}對 {e.get('target_name')} 攻擊骰 {e['attack']['value']}+{e['attack']['modifier']} "
                     f"{'重擊' if e.get('crit') else '命中' if e.get('hit') else '未命中'}"
                     + (f"，傷害 {e.get('damage')}，對方 HP {e.get('enemy_hp_after')}" if e.get("hit") else "")
                     + (f"；敵人出手 {len(strikes)} 次，{sum(1 for s in strikes if s.get('hit'))} 次命中" if strikes else "")
                     + f"；艾玲 HP {e.get('player_hp_after')}")
        elif kind == "equip":
            extra = f"裝備 {e.get('item')}，AC {e.get('ac')}"
        elif kind == "check":
            extra = (f"{e.get('rule_name')}：{e.get('target_title')}"
                     + (f"，d20 {e['roll']['value']} 對 DC {e.get('dc')}" if e.get("roll") else "")
                     + f"，{'成功' if e.get('success') else '失敗'}")
        elif kind == "move":
            extra = f"{e.get('from')} → {e.get('to')}" + ("，撤退時被追擊" if e.get("retreat") else "")
        elif kind == "rest":
            extra = f"HP {e.get('hp_before')} → {e.get('hp_after')}"
        elif kind in ("save", "load"):
            extra = f"slot={e.get('slot')}"
        else:
            extra = ""
        down = "；倒地，回到酒館" if e.get("player_down") else ""
        print(f"[{kind}] {extra}{down}")


def cmd_report():
    st = core.load_state()
    rolls = []
    if core.ROLLS.exists():
        rolls = [json.loads(l) for l in core.ROLLS.read_text(encoding="utf-8").splitlines() if l.strip()]
    events = []
    if core.EVENTS.exists():
        events = [json.loads(l) for l in core.EVENTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    attacks = [e for e in events if e.get("kind") == "attack"]
    checks = [e for e in events if e.get("kind") == "check"]
    print(json.dumps({
        "state": {k: st.get(k) for k in core.GAME_FIELDS},
        "version": st.get("version"),
        "rolls": rolls,
        "events": events,
        "totals": {
            "rolls": len(rolls), "attacks": len(attacks),
            "hits": sum(1 for e in attacks if e.get("hit")),
            "checks": len(checks), "check_successes": sum(1 for e in checks if e.get("success")),
            "downs": int(st.get("flags", {}).get("downed", 0)),
            "ending": next((k for k in ("ending_truth", "ending_peace", "ending_fight") if st.get("flags", {}).get(k)), None),
        },
    }, ensure_ascii=False, indent=2))


def cmd_newgame():
    res = core.op_newgame()
    print(f"新遊戲開始。（結算編號 {res['resolution_id']}）")
    cmd_status()


def cmd_cheat():
    res = core.op_cheat(core.load_state())
    print(f"（作弊）HP 已補滿：{res['hp_after']} / {res['hp_after']}")


if __name__ == "__main__":
    cmds = {"status": cmd_status, "rest": cmd_rest, "save": cmd_save, "load": cmd_load,
            "log": cmd_log, "report": cmd_report, "newgame": cmd_newgame, "cheat": cmd_cheat,
            "equip": cmd_equip}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(1)
    try:
        cmds[sys.argv[1]](*sys.argv[2:])
    except core.EngineError as exc:
        print(f"無法執行：{exc}")
        sys.exit(2)
    except TypeError as exc:
        print(f"參數錯誤：{exc}")
        sys.exit(2)
