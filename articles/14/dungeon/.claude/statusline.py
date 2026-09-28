# .claude/statusline.py
# 狀態列：Claude Code 更新畫面時執行這支程式，印出的每一行顯示在輸入框下面。
# 遊戲的數字一律讀檔案（state.json、.game/rolls.log），不靠 DM 講。
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")                 # Windows 預設不是 UTF-8，中文會亂碼
ROOT = pathlib.Path(__file__).resolve().parent.parent    # dungeon 資料夾

try:                                                     # Claude Code 從 stdin 餵進來的 session 資訊
    session = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
except ValueError:
    session = {}


def bar(value, total, width=10):
    filled = max(0, min(width, round(width * value / total))) if total else 0
    return "█" * filled + "░" * (width - filled)


# 第一行：角色狀態，讀 state.json
try:
    st = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    print(f"{st['name']}  HP {bar(st['hp'], st['max_hp'])} {st['hp']}/{st['max_hp']}"
          f"  銅幣 {st['copper']}  {st['location']}")
except (OSError, ValueError, KeyError):
    print("讀不到 state.json")

# 第二行：最近一骰讀帳本，模型和 context 用量讀 session
last = "還沒骰過"
ledger = ROOT / ".game" / "rolls.log"
if ledger.exists():
    rows = [r for r in ledger.read_text(encoding="utf-8").splitlines() if r.strip()]
    if rows:
        roll_id, spec, total = rows[-1].split()[:3]
        last = f"最近一骰 {spec} = {total}"
model = session.get("model", {}).get("display_name", "?")
pct = (session.get("context_window") or {}).get("used_percentage")
context = f"{pct:.0f}%" if isinstance(pct, (int, float)) else "--"
print(f"{last}  │  {model}  context {context}")
