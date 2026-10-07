"""story.py — keep the table talk: what the player said and what the DM answered.

The engine records what happened (events, dice). This hook records how it was
told, so /report can show an adventure and not only a ledger. It reads only
fields Claude Code hands to hooks, never the transcript file, which is written
asynchronously and may lag behind at Stop time:

  UserPromptSubmit     prompt                           -> {"kind": "player"}
  UserPromptExpansion  prompt, e.g. "/rest"             -> {"kind": "player"}
  MessageDisplay       message_id, index, final, delta  -> {"kind": "dm"}     async: the text never waits
  Stop                 last_assistant_message           -> {"kind": "stop"}   turn boundary and fallback

Every record carries prompt_id, the id Claude Code gives all hooks of one
player input, so a turn can be put back together even when records arrive out
of order. The player record and Stop note how many engine events exist, which
ties each turn to its slice of the ledger. Records are appended to .game/story.jsonl under a lock, because
MessageDisplay hooks run side by side. /newgame clears the file.

It never prints (UserPromptSubmit stdout would become context for the DM) and
never fails: a lost line of story must not break the game.
"""
import contextlib
import json
import os
import pathlib
import sys
import time

try:  # Windows pipes default to the locale (cp950 here); the payload is UTF-8
    sys.stdin.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME = ROOT / ".game"
STORY = GAME / "story.jsonl"
LOCK = GAME / "story.lock"


@contextlib.contextmanager
def locked(wait=3.0, stale=10.0):
    fd, deadline = None, time.time() + wait
    while fd is None:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > stale:
                    LOCK.unlink()  # left behind by a hook that died
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                break  # better an unlocked line than a lost one
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            with contextlib.suppress(OSError):
                LOCK.unlink()


def count_lines(path):
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def record(payload):
    if payload.get("agent_id"):  # a subagent talking to the DM, not to the player
        return None
    event = payload.get("hook_event_name")
    base = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "session_id": payload.get("session_id"),
            "prompt_id": payload.get("prompt_id")}
    if event in ("UserPromptSubmit", "UserPromptExpansion"):
        text = (payload.get("prompt") or "").strip()
        return {**base, "kind": "player", "text": text, "events": count_lines(GAME / "events.jsonl")} if text else None
    if event == "MessageDisplay":
        return {**base, "kind": "dm", "message_id": payload.get("message_id"), "index": int(payload.get("index") or 0),
                "final": bool(payload.get("final")), "text": payload.get("delta") or ""}
    if event == "Stop":
        return {**base, "kind": "stop", "text": payload.get("last_assistant_message") or "",
                "events": count_lines(GAME / "events.jsonl")}
    return None


def main():
    try:
        rec = record(json.load(sys.stdin))
        if rec:
            GAME.mkdir(parents=True, exist_ok=True)
            with locked():
                with STORY.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # the story is a keepsake, never a reason to stop the game
    return 0


if __name__ == "__main__":
    sys.exit(main())
