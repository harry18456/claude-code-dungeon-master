"""Hook handler — play short sounds; decide which one from the hook payload.

  sound.py <name> [pause]              play sounds/<name>.wav (or C:\\Windows\\Media\\<name>.wav)
  sound.py --result                    PostToolUse on an engine tool: pick from the result

--result reads tool_response and plays one sequence, in the order of the
dice lines: every swing (yours or an enemy's) is dice then hit / miss.
  attack -> your swing, then each counter
  move   -> retreat strikes, door, ambush strikes
  check  -> dice when the check itself rolled (buying an ale does not),
            door when the world moved the player, then each strike
  rest   -> rest (the campfire), then dice when a die was rolled

Windows plays with winsound; macOS/Linux use afplay, paplay or aplay when
present; otherwise silence. Never blocks longer than the clip plus the
pause, and never fails the hook. DUNGEON_SOUND_DRY=1 prints names instead.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

try:  # Windows pipes default to the locale (cp950 here); the hook payload is UTF-8
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

HERE = pathlib.Path(__file__).resolve().parent


def find(name):
    for p in (HERE / "sounds" / f"{name}.wav",
              pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Media" / f"{name}.wav"):
        if p.exists():
            return p
    return None


def play(name, pause=0.0):
    if os.environ.get("DUNGEON_SOUND_DRY"):
        print(name)
        return
    path = find(name)
    try:
        if path is not None:
            try:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME)
            except ImportError:
                for player in (["afplay"], ["paplay"], ["aplay", "-q"]):
                    if shutil.which(player[0]):
                        subprocess.run(player + [str(path)], timeout=10, check=False)
                        break
    except Exception:
        pass  # a sound must never break the game
    if pause > 0:
        time.sleep(pause)


def read_payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def parse_result(tool_response):
    """The engine's JSON result, however the hook wrapped it."""
    if isinstance(tool_response, dict) and "kind" in tool_response:
        return tool_response
    text = None
    if isinstance(tool_response, str):
        text = tool_response
    elif isinstance(tool_response, dict) and isinstance(tool_response.get("content"), list):
        text = "".join(c.get("text", "") for c in tool_response["content"] if isinstance(c, dict))
    elif isinstance(tool_response, list):
        text = "".join(c.get("text", "") for c in tool_response if isinstance(c, dict))
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def swing(hit):
    """One d20 against an AC, like one line under 骰子：."""
    return ["dice", "hit" if hit else "miss"]


def swings(strikes):
    return [name for s in strikes for name in swing(s.get("hit"))]


def strike_roll_ids(strikes):
    ids = set()
    for s in strikes:
        ids.add((s.get("roll") or {}).get("roll_id"))
        ids.update(r.get("roll_id") for r in s.get("damage_rolls") or [])
    return ids


def sounds_for(result):
    if not result or "error" in result:
        return []
    kind = result.get("kind")
    strikes = [s for s in result.get("strikes") or [] if isinstance(s, dict)]
    out = []
    if kind == "attack":
        out = swing(result.get("hit")) + swings(strikes)
    elif kind == "move":
        # a parting bite comes before the door, an ambush after it
        away = [s for s in strikes if str((s.get("roll") or {}).get("purpose", "")).startswith("retreat")]
        out = swings(away) + ["door"] + swings([s for s in strikes if s not in away])
    elif kind == "rest":
        out = ["rest"] + (["dice"] if result.get("roll") else [])
    elif kind in ("roll", "check"):
        # the check's own dice, if any (buying an ale rolls none), then whoever strikes back
        taken = strike_roll_ids(strikes)
        own = [r for r in result.get("rolls") or [] if isinstance(r, dict) and r.get("roll_id") not in taken]
        if kind == "roll" or own:
            out.append("dice")
        if any(str(e).startswith("被帶到") for e in result.get("effects", [])):
            out.append("door")
        out += swings(strikes)
    return out


def main(argv):
    if len(argv) >= 2 and argv[1] == "--result":
        payload = read_payload()
        for name in sounds_for(parse_result(payload.get("tool_response"))):
            play(name, 0.15 if name in ("hit", "miss") else 0.0)  # a breath between swings
        return 0
    name = argv[1] if len(argv) > 1 else "ding"
    pause = float(argv[2]) if len(argv) > 2 else 0.0
    play(name, pause)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
