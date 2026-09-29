# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3"]
# ///
# .claude/mcp/dice.py
# dungeon 的骰子 server：只有一個工具 roll。
# 每骰一次，照 Day 13 的格式在 .game/rolls.log 記一行，回傳結果和票根。
import datetime
import pathlib
import random
import re
import secrets

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROOT = pathlib.Path(__file__).resolve().parents[2]      # dungeon 資料夾
LEDGER = ROOT / ".game" / "rolls.log"

mcp = MCPServer("dungeon")


@mcp.tool()
def roll(dice: str) -> str:
    """擲骰子。dice 寫 d20、d6+1 這種格式（N 面骰，加上固定加值）。
    回傳結果和票根 [R:編號=結果]，報結果時連票根一起原樣貼給玩家。"""
    m = re.fullmatch(r"d(\d+)(?:\+(\d+))?", dice.strip())
    if not m or int(m.group(1)) < 2:
        raise ToolError(f"看不懂的骰子：{dice}。請用 d20、d6+1 這種寫法")   # 這段說明會交給 DM
    sides, bonus = int(m.group(1)), int(m.group(2) or 0)
    face = random.randint(1, sides)
    total = face + bonus
    roll_id = secrets.token_hex(4)                     # 這一骰的編號，8 個字

    LEDGER.parent.mkdir(exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:     # 記進帳本
        f.write(f"{roll_id} {dice} {total} {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")

    shown = f"{face}" if bonus == 0 else f"{face} + {bonus} = {total}"
    return f"{dice}: {shown} [R:{roll_id}={total}]"


if __name__ == "__main__":
    mcp.run(transport="stdio")
