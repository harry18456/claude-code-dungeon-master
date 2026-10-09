#!/usr/bin/env bash
# Play the dungeon headless: one `claude -p` call per line of an inputs file,
# resumed into the same session, in an ISOLATED copy of this project.
#
#   bash tools/run_turns.sh <inputs.txt> [outdir]
#
# Env: MODEL (default sonnet), DM_TMPDIR (temp root; see below),
#      KEEP_STATE=1 to play on from the current state.json instead of newgame,
#      DUNGEON_FIXED_ROLLS to pin dice (see engine/core.py).
#
# Why the copy: Claude Code loads every CLAUDE.md / .claude/ it finds in the
# directories ABOVE the working directory. A copy under your home directory
# would inherit ~/.claude/CLAUDE.md as project instructions. The runner picks
# a temp root whose ancestors carry none of those files and refuses otherwise.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
INPUTS="${1:?usage: bash tools/run_turns.sh <inputs.txt> [outdir]}"
INPUTS="$(cd "$(dirname "$INPUTS")" && pwd)/$(basename "$INPUTS")"   # absolute: we cd away below
OUT="${2:-$HERE/reports/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p -- "$OUT"; OUT="$(cd "$OUT" && pwd)"
MODEL="${MODEL:-sonnet}"

ancestor_offenders() {  # prints CLAUDE.md / .claude / .mcp.json found above <dir>
  local d="$1" out="" p
  while :; do
    p="$(dirname "$d")"; [ "$p" = "$d" ] && break; d="$p"
    for f in CLAUDE.md CLAUDE.local.md .claude .mcp.json; do
      [ -e "$d/$f" ] && out="$out $d/$f"
    done
  done
  printf '%s' "$out"
}
real_path() {  # Git Bash mounts /tmp under the home dir; look at the real path
  if command -v cygpath >/dev/null 2>&1; then
    local m; m="$(cygpath -m "$1")"
    printf '/%s%s' "$(printf '%s' "${m%%:*}" | tr 'A-Z' 'a-z')" "${m#*:}"
  else
    printf '%s' "$1"
  fi
}
temp_root() {
  local root="${DM_TMPDIR:-}" c
  if [ -z "$root" ]; then
    for c in "${TMPDIR:-/tmp}" /c/tmp/dm-isolated /var/tmp/dm-isolated; do
      mkdir -p -- "$c" 2>/dev/null || continue
      c="$(real_path "$c")"
      [ -z "$(ancestor_offenders "$c")" ] && { root="$c"; break; }
    done
  else
    mkdir -p -- "$root"; root="$(real_path "$root")"
  fi
  [ -n "$root" ] || { echo "no clean temp root; set DM_TMPDIR" >&2; return 2; }
  local off; off="$(ancestor_offenders "$root")"
  [ -z "$off" ] || { echo "refusing to run under $root; an ancestor would be loaded as instructions:$off" >&2; return 2; }
  printf '%s' "$root"
}

RUN="$(mktemp -d "$(temp_root)/dm-run.XXXXXX")"
trap 'rm -rf -- "$RUN"' EXIT
# copy the project without git history, runtime records or old reports
(cd "$HERE" && tar --exclude=.git --exclude=.game --exclude=reports --exclude=__pycache__ --exclude=hooklogs -cf - .) | (cd "$RUN" && tar -xf -)
cd "$RUN"
export PYTHONUTF8=1
# headless runs are silent unless asked: sound effects are printed instead of played
export DUNGEON_SOUND_DRY="${DUNGEON_SOUND_DRY:-1}"
if [ "${KEEP_STATE:-0}" != "1" ]; then
  uv run --no-project gamectl.py newgame >/dev/null
fi
# The copy is a new folder, so the MCP server's first start here is slow (uv
# builds a fresh environment, Python compiles the SDK) and turn 1 can miss
# Claude Code's 30 s connect timeout. Start it once now; it exits on EOF.
uv run --no-project engine/server.py < /dev/null > /dev/null 2>&1 || true
cp "$INPUTS" "$OUT/inputs.txt"

SID=""; i=0
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  i=$((i+1)); NN=$(printf "%02d" "$i")
  echo ">> turn $NN: ${line:0:40}"
  args=(-p "$line" --model "$MODEL" --setting-sources project
        --strict-mcp-config --mcp-config .mcp.json
        --allowedTools "mcp__dungeon__* Skill Agent Bash(uv run --no-project gamectl.py *) Read Grep Glob"
        --permission-prompts none)
  [ -n "$SID" ] && args+=(--resume "$SID")
  # MSYS path conversion must be off for `claude` (it rewrites "/rest" into a
  # Git path) but on for native Python; so it is set per command, not exported.
  if [ "${STREAM:-0}" = "1" ]; then
    # STREAM=1 keeps every event (tool calls, subagent hand-backs, hook events)
    # in turn_NN.jsonl and extracts the final result into turn_NN.json.
    args+=(--output-format stream-json --verbose --include-hook-events)
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" claude "${args[@]}" < /dev/null > "$OUT/turn_$NN.jsonl" || {
      echo "claude failed on turn $NN; see $OUT/turn_$NN.jsonl" >&2; exit 1; }
    uv run --no-project python - "$OUT/turn_$NN.jsonl" "$OUT/turn_$NN.json" <<'PY'
import json, pathlib, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
result = None
for line in src.read_text(encoding="utf-8").splitlines():
    if line.strip():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result":
            result = obj
dst.write_text(json.dumps(result or {}, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  else
    args+=(--output-format json)
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" claude "${args[@]}" < /dev/null > "$OUT/turn_$NN.json" || {
      echo "claude failed on turn $NN; see $OUT/turn_$NN.json" >&2; exit 1; }
  fi
  SID="$(uv run --no-project python -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8')).get('session_id',''))" "$OUT/turn_$NN.json")"
  cp state.json "$OUT/turn_$NN.state.json"
done < "$INPUTS"

# keep what the game wrote: the state, the engine records and story.py's log
mkdir -p "$OUT/game/.game"
cp state.json "$OUT/game/state.json"
cp -r .game/. "$OUT/game/.game/" 2>/dev/null || true
echo "story: $OUT/game/.game/story.jsonl"
