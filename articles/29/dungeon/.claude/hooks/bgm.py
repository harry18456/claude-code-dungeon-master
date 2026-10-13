"""bgm.py — background music driven by hooks.

  bgm.py start          SessionStart: play the track for the current scene
  bgm.py sync           FileChanged(state.json): switch when the scene or the ending changed
  bgm.py stop           SessionEnd:   kill the player
  bgm.py toggle on|off  /bgm skill
  bgm.py player <file> [--once] [--volume N]   internal, the detached process

settings.json runs it as `uv run --no-project .claude/hooks/bgm.py ...`.

The player is a separate, detached process so the hook itself returns at
once. Its pid lives in .game/bgm.json; a stale pid is killed before a new
player starts, and SessionEnd kills it too. If Claude Code dies without
running SessionEnd, the music stops at the next start or at /bgm off.

Windows plays through winmm (MCI), macOS through afplay, Linux through
ffplay or mpv when present. Anything else stays silent and exits 0.

sync hangs on FileChanged, not PostToolUse: /newgame and /load rewrite
state.json through `!` expansion, which is no tool call, and a watcher
sees every writer. A lock in .game/bgm.lock keeps two syncs from racing.
Env: DUNGEON_BGM=0 disables everything; DUNGEON_BGM_VOLUME 0–1000 (default 500).
"""
import contextlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

DEFAULT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def paths(root):
    game = root / ".game"
    return {"state": root / "state.json", "bgm": game / "bgm.json", "off": game / "bgm_off",
            "tracks": root / "bgm" / "tracks.json", "dir": root / "bgm", "log": game / "bgm.log", "lock": game / "bgm.lock"}


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def log(root, msg):
    try:
        p = paths(root)["log"]
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


# ---------------------------------------------------------------- decisions

def desired_track(state, tracks, bgm_state):
    """(track name or None, play_once). The ending plays once, then silence."""
    flags = (state or {}).get("flags", {})
    if flags.get("ending"):
        if bgm_state.get("ending_played"):
            return None, False
        return tracks.get("ending"), True
    return tracks.get("scenes", {}).get((state or {}).get("location")), False


# ---------------------------------------------------------------- processes

def alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x100000, False, int(pid))  # SYNCHRONIZE
        if not h:
            return False
        rc = k.WaitForSingleObject(h, 0)
        k.CloseHandle(h)
        return rc == 0x102  # WAIT_TIMEOUT: still running
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def kill(pid):
    if alive(pid):
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError:
            pass


def spawn_player(root, file, once, volume):
    if os.environ.get("DUNGEON_BGM_DRY"):
        return 0
    args = [sys.executable, str(pathlib.Path(__file__).resolve()), "player", str(file), "--volume", str(volume)]
    if once:
        args.append("--once")
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(args, **kwargs).pid


def volume():
    try:
        return max(0, min(1000, int(os.environ.get("DUNGEON_BGM_VOLUME", "500"))))
    except ValueError:
        return 500


# ---------------------------------------------------------------- commands

def cmd_stop(root):
    p = paths(root)
    bgm = read_json(p["bgm"], {})
    kill(bgm.get("pid"))
    bgm.update({"pid": None, "track": None})
    write_json(p["bgm"], bgm)
    return "背景音樂已停止"


@contextlib.contextmanager
def sync_lock(root, wait=5.0, stale=10.0):
    """One sync at a time. Two racing syncs would both kill the old player and
    both spawn a new one; the pid of the first would be lost and it would play on."""
    lock = paths(root)["lock"]
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + wait
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    lock.unlink()  # left behind by a sync that died
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                break  # better a rare double than no music at all
            time.sleep(0.05)
        except OSError:
            break
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def cmd_sync(root, force=False):
    with sync_lock(root):
        return _sync(root, force)


def _sync(root, force=False):
    p = paths(root)
    if os.environ.get("DUNGEON_BGM") == "0" or p["off"].exists():
        bgm = read_json(p["bgm"], {})
        if bgm.get("pid"):
            cmd_stop(root)
        return "背景音樂：關"
    state = read_json(p["state"], {})
    tracks = read_json(p["tracks"], {})
    bgm = read_json(p["bgm"], {})
    track, once = desired_track(state, tracks, bgm)
    dry = bool(os.environ.get("DUNGEON_BGM_DRY"))
    playing = bgm.get("track") if (dry or alive(bgm.get("pid"))) else None
    if track == playing and not force:
        return f"背景音樂：{track or '無'}（不變）"
    kill(bgm.get("pid"))
    if track is None:
        bgm.update({"pid": None, "track": None})
        write_json(p["bgm"], bgm)
        return "背景音樂：無"
    file = p["dir"] / f"{track}.mp3"
    if not file.exists():
        bgm.update({"pid": None, "track": None})
        write_json(p["bgm"], bgm)
        log(root, f"missing {file}")
        return f"背景音樂：找不到 {file.name}"
    pid = spawn_player(root, file, once, volume())
    bgm.update({"pid": pid, "track": track, "file": str(file), "once": once})
    if once and track == tracks.get("ending"):
        bgm["ending_played"] = True
    write_json(p["bgm"], bgm)
    log(root, f"play {track} once={once} pid={pid}")
    return f"背景音樂：{track}"


def cmd_toggle(root, arg):
    p = paths(root)
    if arg.strip().lower() in ("off", "關", "0"):
        p["off"].parent.mkdir(parents=True, exist_ok=True)
        p["off"].write_text("off", encoding="utf-8")
        cmd_stop(root)
        return "背景音樂：關（打 /bgm on 再開）"
    if p["off"].exists():
        p["off"].unlink()
    return cmd_sync(root, force=True)


# ---------------------------------------------------------------- the player

def _play_windows(file, once, vol):
    import ctypes
    winmm = ctypes.windll.winmm

    def mci(cmd):
        buf = ctypes.create_unicode_buffer(512)
        rc = winmm.mciSendStringW(cmd, buf, 511, 0)
        return rc, buf.value

    rc, _ = mci(f'open "{file}" type mpegvideo alias bgm')
    log(pathlib.Path(file).resolve().parents[1], f"mci open rc={rc} file={pathlib.Path(file).name}")
    if rc:
        return rc
    mci(f"setaudio bgm volume to {vol}")
    rc_play, _ = mci("play bgm" if once else "play bgm repeat")
    log(pathlib.Path(file).resolve().parents[1], f"mci play rc={rc_play} once={once} volume={vol}")
    if once:
        _, length = mci("status bgm length")
        time.sleep(int(length or 0) / 1000 + 0.5)
    else:
        while True:
            time.sleep(3600)
    mci("close bgm")
    return 0


def _play_cli(file, once, vol):
    if shutil.which("afplay"):
        cmd = ["afplay", "-v", f"{vol / 1000:.2f}", str(file)]
    elif shutil.which("ffplay"):
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(int(vol / 10)), str(file)]
    elif shutil.which("mpv"):
        cmd = ["mpv", "--no-video", "--really-quiet", f"--volume={int(vol / 10)}", str(file)]
    else:
        return 1
    while True:
        subprocess.run(cmd, check=False)
        if once:
            return 0


def cmd_player(file, once, vol):
    root = pathlib.Path(file).resolve().parents[1]
    try:
        rc = _play_windows(file, once, vol) if os.name == "nt" else _play_cli(file, once, vol)
        log(root, f"player exit rc={rc} file={pathlib.Path(file).name}")
    except Exception as exc:  # music must never crash anything
        log(root, f"player error {type(exc).__name__}: {exc}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0
    cmd = argv[1]
    root = DEFAULT_ROOT
    if "--root" in argv:
        root = pathlib.Path(argv[argv.index("--root") + 1]).resolve()
    if cmd == "player":
        file = argv[2]
        vol = int(argv[argv.index("--volume") + 1]) if "--volume" in argv else 500
        cmd_player(file, "--once" in argv, vol)
        return 0
    if cmd == "start":
        print(cmd_sync(root, force=True))
    elif cmd == "sync":
        print(cmd_sync(root))
    elif cmd == "stop":
        print(cmd_stop(root))
    elif cmd == "toggle":
        print(cmd_toggle(root, argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "on"))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
