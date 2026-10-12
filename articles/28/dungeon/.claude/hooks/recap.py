"""SessionStart hook — hand the DM a recap of the saved game before the first prompt.

Interactive Claude Code never speaks first, so this cannot greet the
player; it makes sure that whatever the player types first, the DM already
knows where the game stands. Reads state.json and the last events through
gamectl (the trusted path), and returns them as additionalContext.
Also runs after compaction, when the DM has just forgotten most of the game.
"""
import json
import os
import pathlib
import subprocess
import sys

try:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAMECTL = ROOT / "gamectl.py"
if not GAMECTL.exists():  # installed as a plugin: gamectl.py is in the plugin, the game is the project folder
    GAMECTL = pathlib.Path(__file__).resolve().parents[1] / "gamectl.py"
    ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def run(*args):
    proc = subprocess.run([sys.executable, str(GAMECTL), *args], capture_output=True,
                          text=True, encoding="utf-8", cwd=ROOT, timeout=20)
    return proc.stdout.strip()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    source = payload.get("source", "startup")
    status = run("status")
    log = run("log", "8")
    if not status:
        sys.exit(0)
    try:  # a reset state.json with stale logs beside it is still a fresh game
        turn = int(json.loads((ROOT / "state.json").read_text(encoding="utf-8")).get("turn", 0))
    except Exception:
        turn = 0
    fresh = turn == 0 or log.startswith("(尚無事件紀錄)") or "[newgame]" in log.splitlines()[-1:]
    lines = [f"【前情提要，來源：{source}】", f"目前狀態：{status}"]
    if fresh:
        lines.append("這是一場新遊戲，還沒發生任何事。玩家第一次開口時，先用三到五句介紹醉月酒館的開場，再給選項。")
    else:
        lines.append("最近的事件（由引擎紀錄，可信）：")
        lines.append(log)
        lines.append("玩家第一次開口時，先用兩三句回顧上次玩到哪、艾玲現在在哪，再呼叫 get_current_scene 給選項。不要重述上面的骰值。")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "\n".join(lines)}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
