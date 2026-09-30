"""Stop hook — check narrated dice tickets against the engine's committed results.

Three mechanical checks, nothing else (plan C6):
  1. a ticket [R:<roll_id>=<value>] names an id the engine never minted
  2. a ticket's value differs from the engine's value
  3. a roll committed this turn has no ticket in the reply

It does not try to understand prose. A narrated number with no ticket and
no new roll this turn is a known miss, stated in Day 13 and Day 29.

Modes: --mode warn (default) shows a systemMessage to the player;
       --mode block asks the DM to correct, at most 2 times per turn.
"""
import json
import pathlib
import re
import sys

try:  # Windows consoles default to cp950
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATE = ROOT / "state.json"
ROLLS = ROOT / ".game" / "rolls.jsonl"
CURSOR = ROOT / ".game" / "audit_cursor.json"
MAX_BLOCKS = 2
TICKET = re.compile(r"[\[［]R:(r-[0-9a-f]{6})=(\d+)[\]］]")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def known_rolls(state):
    """roll_id -> value from the authoritative recent results, then the derived ledger."""
    out = {}
    if ROLLS.exists():
        try:
            for line in ROLLS.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    out[r["roll_id"]] = r["value"]
        except (OSError, ValueError):
            pass
    for rec in state.get("recent_results", []):
        for r in rec.get("rolls", []):
            out[r["roll_id"]] = r["value"]
    return out


def main():
    mode = "warn"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    text = payload.get("last_assistant_message") or ""
    state = read_json(STATE, None)
    if not state:
        sys.exit(0)
    cursor = read_json(CURSOR, {})
    if not isinstance(cursor, dict):
        cursor = {}
    seen_version = int(cursor.get("version", 0))
    blocks = int(cursor.get("blocks", 0))
    current_version = int(state.get("version", 0))

    ledger = known_rolls(state)
    expected = {}
    for rec in state.get("recent_results", []):
        if int(rec.get("version", 0)) > seen_version:
            for r in rec.get("rolls", []):
                expected[r["roll_id"]] = r["value"]

    problems = []
    mentioned = set()
    for m in TICKET.finditer(text):
        rid, value = m.group(1), int(m.group(2))
        mentioned.add(rid)
        if rid not in ledger:
            problems.append(f"票根 {rid} 不存在於引擎紀錄")
        elif int(ledger[rid]) != value:
            problems.append(f"票根 {rid} 的真實值是 {ledger[rid]}，回覆寫成 {value}")
    for rid, value in expected.items():
        if rid not in mentioned:
            problems.append(f"本回合擲出的 {rid}（值 {value}）沒有出現在回覆裡")

    def save_cursor(version, count):
        CURSOR.parent.mkdir(parents=True, exist_ok=True)
        CURSOR.write_text(json.dumps({"version": version, "blocks": count}), encoding="utf-8")

    if not problems:
        save_cursor(current_version, 0)
        sys.exit(0)

    summary = "查帳：" + "；".join(problems)
    try:  # the buzzer: the DM got caught
        import subprocess
        # stdout of this hook must stay pure JSON, so the buzzer's output is dropped
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("sound.py")), "buzz"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except Exception:
        pass
    if mode == "block" and blocks < MAX_BLOCKS and not (payload.get("stop_hook_active") and blocks >= MAX_BLOCKS):
        save_cursor(seen_version, blocks + 1)
        print(json.dumps({
            "decision": "block",
            "reason": summary + "。請只依引擎回傳的結果改寫這一段，每個骰值附 [R:<roll_id>=<value>]，不要重新執行任何遊戲動作。",
        }, ensure_ascii=False))
        sys.exit(0)

    # warn mode, or block mode that reached its limit: tell the player, let the turn end
    save_cursor(current_version, 0)
    tail = "（已更正兩次仍不符，列為未解錯誤）" if mode == "block" else ""
    print(json.dumps({"systemMessage": summary + tail}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
