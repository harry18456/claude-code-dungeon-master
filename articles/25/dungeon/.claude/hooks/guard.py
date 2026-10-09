"""PreToolUse guard — keep shell commands away from the world's files.

Permission rules cover Claude Code's own file tools. A shell command can
reach the same files by another route, so this hook reads the actual
command and denies:

  * writes to state.json, .game/, scenes/, data/, engine/, gamectl.py,
    rules.md, CLAUDE.md or .claude/ by redirection, copy/move/delete,
    in-place edit, or an inline interpreter
  * reads or copies of scenes/ (the judge-only half lives there)

Everything else passes. Listing file names is allowed. The trusted path is
`uv run --no-project gamectl.py ...`, which never matches a write pattern.

Code handed to an interpreter is judged by the whole command, in any order:
`python -c ...`, `uv run python -c ...`, `echo ... | uv run -` and a heredoc
all count. uv runs Python too, so it is on the interpreter list.
"""
import json
import re
import sys

try:  # Windows consoles default to cp950
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

PROTECTED = r"(?:state\.json|\.game[\\/]|scenes[\\/]|data[\\/]|engine[\\/]|gamectl\.py|rules\.md|CLAUDE\.md|\.claude[\\/])"
SCENES = r"scenes[\\/]\S*"

WRITE_PATTERNS = [
    r">>?\s*\S*" + PROTECTED,                                        # echo x > state.json
    r"\b(cp|mv|rm|touch|tee|sed\s+-i|install)\b[^|;&]*" + PROTECTED,  # cp/mv/rm/tee/sed -i
    r"\b(Set-Content|Out-File|Add-Content|Remove-Item|Move-Item|Copy-Item|New-Item|Clear-Content)\b[^|;&]*" + PROTECTED,
]
READ_PATTERNS = [
    r"\b(cat|type|head|tail|more|less|grep|rg|awk|sed|cut|strings|xxd|od|cp|copy|Get-Content|gc|Select-String|Copy-Item)\b[^|;&]*" + SCENES,
]
INTERPRETER = r"\b(python|python3|py|uv|uvx|node|perl|ruby)\b"
CODE_WRITES = (r"write_text|write_bytes|json\.dump|os\.replace|os\.rename|unlink|remove\(|"
               r"open\s*\([^)]*['\"][waxr]\+?['\"]|shutil\.|Path\([^)]*\)\.write")


def runs_code_that(cmd: str, pattern: str) -> bool:
    """An interpreter anywhere in the command and the pattern anywhere: covers -c, pipes and heredocs."""
    return bool(re.search(INTERPRETER, cmd, re.IGNORECASE) and re.search(pattern, cmd, re.IGNORECASE))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # never break the session on a malformed payload
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not cmd:
        sys.exit(0)

    reason = None
    if any(re.search(p, cmd, re.IGNORECASE) for p in WRITE_PATTERNS) or runs_code_that(cmd, CODE_WRITES):
        reason = ("遊戲的狀態、場景、資料與引擎程式不能用 shell 直接改。狀態只會因為引擎工具或 "
                  "uv run --no-project gamectl.py 的結算而改變。")
    elif any(re.search(p, cmd, re.IGNORECASE) for p in READ_PATTERNS) or runs_code_that(cmd, SCENES):
        reason = "scenes/ 底下是地城領主看不到的世界資料。要知道場景內容請呼叫 get_current_scene。"

    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
