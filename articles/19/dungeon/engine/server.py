# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3"]
# ///
"""engine/server.py — MCP server for the dungeon engine (stdio, official MCP Python SDK 2.x).

Claude Code spawns this process from .mcp.json with `uv run --no-project
engine/server.py`; uv reads the dependency block above and installs the SDK.
The SDK speaks the protocol (2026-07-28, and older versions for older
clients). This file only declares the tools and hands every call to core.py;
validation errors come back as tool errors (isError) with nothing written.

Only the tools listed in EXPOSED are announced. The list grows with the
series: D16 dice, attack and state; D17 scenes and movement; D18 checks.

The tool table and call_tool() use the standard library only, so the tests
can import this module without the SDK; the SDK is imported in main().
"""
import json
import sys
from typing import Annotated, Literal

try:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    from engine import core
except ImportError:  # pragma: no cover - run as a script from the engine dir
    import core  # type: ignore

ID = {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$"}

TOOLS = {
    "roll": {
        "description": "擲一次骰子並記入帳本。dice 寫 d20、d20+2、2d6 這種格式；purpose 可寫這次擲骰的用途。"
                       "回傳的 dice 欄位是一行結果，後面接票根 [R:<roll_id>=<骰面>]，照原樣貼給玩家。攻擊請用 resolve_attack。",
        "inputSchema": {"type": "object",
                        "properties": {"dice": {"type": "string", "minLength": 2, "maxLength": 16,
                                                "description": "骰子，例如 d20+2"},
                                       "purpose": {"type": "string", "minLength": 1, "maxLength": 64,
                                                   "description": "用途，例如 search_rubble（可省略）"}},
                        "required": ["dice"], "additionalProperties": False},
    },
    "rest": {
        "description": "休息一晚：引擎擲生命骰加體質補 HP、寫入紀錄，回傳 hp_before、hp_after 與 dice。滿血就不擲骰。"
                       "戰鬥中會被拒絕。休息的場景請先用 get_state 看 location。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_state": {
        "description": "查詢艾玲目前的狀態（HP、銅幣、位置、物品、旗標、敵人剩餘 HP）與最後一筆已提交的結算結果。"
                       "工具呼叫失敗、回應遺失或不確定剛才的動作有沒有成立時，先呼叫它確認，不要重送動作。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_current_scene": {
        "description": "取得玩家目前所在場景的公開資訊：描述、在場的人（actors：態度、是否倒下、接受的動詞）、出口（含是否可走）、物件（features）與可用規則、已揭露的線索。只回傳玩家看得到的部分。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "move_to": {
        "description": "把玩家移到相鄰的場景。引擎會檢查出口是否存在與是否解鎖；離開有敵人的場景會被追擊一次。敘事上讓玩家離開目前地點時必須呼叫它。",
        "inputSchema": {"type": "object", "properties": {"scene": {**ID, "description": "目標場景代號，例如 cellar"}},
                        "required": ["scene"], "additionalProperties": False},
    },
    "resolve_attack": {
        "description": "對場景裡任何人結算一次完整攻擊：d20 加攻擊加值對 AC，骰面 20 重擊、1 必失手；命中骰傷害扣對方 HP。"
                       "戰鬥開始後，每個還站著的敵人都會在你行動後出手。mode=ranged 用弓：敵人還沒近身的第一箭不會被反擊，近身再射有劣勢，每箭耗一支箭。"
                       "敵人會倒下，普通人只是被打趴但從此敵意。受保護的人（小孩）會被拒絕。"
                       "艾玲 HP 歸零會直接倒地：醒來在酒館、扣 10 銅幣、HP 補滿。全部一次結算並寫入紀錄，照回傳的數字敘述。",
        "inputSchema": {"type": "object",
                        "properties": {"target": {**ID, "description": "對象代號，例如 giant_rat、guard"},
                                       "mode": {"type": "string", "enum": ["melee", "ranged"], "description": "近戰（預設）或遠程"}},
                        "required": ["target"], "additionalProperties": False},
    },
    "resolve_check": {
        "description": "對場景裡的人或物件做一次規則檢定或互動：引擎依對象的態度與籌碼算 DC、擲 d20、套用既定的成功或失敗後果並寫入紀錄。"
                       "對人：persuade、steal、provoke，守著路的人還有 sneak、distract（target_id 用 actors 的代號）。"
                       "對物件：search、interact（target_id 用 features 的代號）。"
                       "規則沒寫但合理無害的小動作用 rule_id=improvise、target_id=here：只擲骰，不改變世界。"
                       "失敗過的同一組（動詞,對象）要換方法、休息或離開再回來才能再試。",
        "inputSchema": {"type": "object",
                        "properties": {"rule_id": {**ID, "description": "規則代號"}, "target_id": {**ID, "description": "目標代號"}},
                        "required": ["rule_id", "target_id"], "additionalProperties": False},
    },
}

# No bare `roll` in the release: every die is rolled inside a resolution
# (attack, check, rest), so it always has a consequence and a ticket. Days
# 16–17 expose `roll` (the Day 16 list is get_state, roll, resolve_attack, rest);
# it stays defined above for them.
EXPOSED = ["get_state", "get_current_scene", "move_to", "resolve_attack", "resolve_check", "rest"]  # Day 18


def call_tool(name, args):
    if name not in EXPOSED:
        return {"error": f"unknown tool: {name}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    schema = TOOLS[name]["inputSchema"]
    expected, required = set(schema["properties"]), set(schema.get("required", []))
    if not required <= set(args) <= expected:
        return {"error": f"{name} 需要的參數是 {sorted(required)}（可選 {sorted(expected - required)}），收到 {sorted(args)}"}
    if name == "roll":
        return core.op_roll(core.load_state(), args["dice"], args.get("purpose"))
    if name == "get_state":
        return core.op_get_state(core.load_state())
    if name == "rest":
        return core.op_rest(core.load_state())
    if name == "get_current_scene":
        return core.op_get_current_scene(core.load_state())
    if name == "move_to":
        return core.op_move_to(core.load_state(), args["scene"])
    if name == "resolve_attack":
        return core.op_resolve_attack(core.load_state(), args["target"], args.get("mode", "melee"))
    if name == "resolve_check":
        return core.op_resolve_check(core.load_state(), args["rule_id"], args["target_id"])
    return {"error": f"unknown tool: {name}"}


def run_tool(name, args):
    """call_tool, with engine errors and bugs turned into {"error": ...} instead of crashes."""
    try:
        return call_tool(name, args)
    except core.EngineError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # engine bugs surface as tool errors, not crashes
        return {"error": f"{type(exc).__name__}: {exc}"}


def build_server():
    """The SDK server with one tool per EXPOSED name. Each answers with the engine's JSON as text."""
    from pydantic import Field
    from mcp.server.mcpserver import MCPServer
    from mcp.types import CallToolResult, TextContent

    def answer(name, args):
        result = run_tool(name, args)
        text = json.dumps(result, ensure_ascii=False)
        if isinstance(result, dict) and "error" in result:
            # isError with the engine's own words (a raised ToolError would get an English prefix):
            # the PostToolUse sound stays quiet and nothing was written
            return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)
        return text

    def field(schema):  # the same limits as TOOLS, so the SDK checks what call_tool checks
        keys = {"minLength": "min_length", "maxLength": "max_length", "pattern": "pattern", "description": "description"}
        return Field(**{keys[k]: v for k, v in schema.items() if k in keys})

    props = {name: TOOLS[name]["inputSchema"]["properties"] for name in TOOLS}
    Id = lambda tool, key: Annotated[str, field(props[tool][key])]  # noqa: E731

    def roll(dice: Annotated[str, field(props["roll"]["dice"])],
             purpose: Annotated[str | None, field(props["roll"]["purpose"])] = None):
        return answer("roll", {"dice": dice} if purpose is None else {"dice": dice, "purpose": purpose})

    def get_state():
        return answer("get_state", {})

    def rest():
        return answer("rest", {})

    def get_current_scene():
        return answer("get_current_scene", {})

    def move_to(scene: Id("move_to", "scene")):
        return answer("move_to", {"scene": scene})

    def resolve_attack(target: Id("resolve_attack", "target"),
                       mode: Annotated[Literal["melee", "ranged"],
                                       Field(description=props["resolve_attack"]["mode"]["description"])] = "melee"):
        return answer("resolve_attack", {"target": target, "mode": mode})

    def resolve_check(rule_id: Id("resolve_check", "rule_id"), target_id: Id("resolve_check", "target_id")):
        return answer("resolve_check", {"rule_id": rule_id, "target_id": target_id})

    handlers = {f.__name__: f for f in (roll, get_state, rest, get_current_scene, move_to, resolve_attack, resolve_check)}
    server = MCPServer("dungeon", version="2.0.0", log_level="WARNING")
    for name in EXPOSED:
        server.add_tool(handlers[name], name=name, description=TOOLS[name]["description"], structured_output=False)
    return server


def main():
    try:
        server = build_server()
    except ImportError:
        sys.exit("engine/server.py 需要官方的 MCP Python SDK 2.x。用 uv 執行（uv run --no-project engine/server.py），"
                 "或先安裝：python -m pip install \"mcp>=2,<3\"")
    server.run("stdio")


if __name__ == "__main__":
    main()
