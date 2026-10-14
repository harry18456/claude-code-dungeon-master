"""tools/skill_rate.py — how often the DM calls a Skill on its own, measured the Day 23 way.

Each query in the set is played as ONE turn from the same saved start (a fresh
game, or KEEP_STATE=1 for the current state.json), headless, in an isolated
copy of this folder, and the run's events say whether the DM called the Skill.
Every query is tried several times, because the DM does not always do the same
thing twice. The report is a table: query, expected, hits/runs.

    uv run --no-project tools/skill_rate.py <set.json> [--runs 3] [--model sonnet] [--out <dir>]

The set is a JSON list of {"skill": "rest", "should": true, "query": "..."}.
Each turn goes through tools/run_turns.sh, so the same flags, the same
isolation and the same cold-start fix apply. A query's turns are independent:
the DM never sees the other queries.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent.parent
BASH = next((p for p in (r"C:\Program Files\Git\bin\bash.exe", "/usr/bin/bash", "/bin/bash") if pathlib.Path(p).exists()), "bash")


def skills_called(jsonl: pathlib.Path) -> list[str]:
    names = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        for block in obj.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                names.append(str(block.get("input", {}).get("skill", "")))
    return names


def one_turn(query: str, model: str, out: pathlib.Path) -> list[str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    # run_turns.sh copies the inputs file into its output folder, so it must not already be there
    inputs = out.parent / (out.name + ".txt")
    inputs.write_text(query + "\n", encoding="utf-8")
    env = {**os.environ, "STREAM": "1", "MODEL": model, "PYTHONUTF8": "1"}
    subprocess.run([BASH, str(HERE / "tools" / "run_turns.sh"), str(inputs), str(out)],
                   env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return skills_called(out / "turn_01.jsonl")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    queries = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    runs = int(argv[argv.index("--runs") + 1]) if "--runs" in argv else 3
    model = argv[argv.index("--model") + 1] if "--model" in argv else "sonnet"
    out = pathlib.Path(argv[argv.index("--out") + 1]) if "--out" in argv else \
        HERE / "reports" / ("skill-rate-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, q in enumerate(queries, 1):
        hits = 0
        for r in range(1, runs + 1):
            called = one_turn(q["query"], model, out / f"q{i:02d}-r{r}")
            hit = q["skill"] in called
            hits += hit
            print(f"q{i:02d} r{r} {'HIT ' if hit else 'miss'} {called} | {q['query'][:36]}", file=sys.stderr)
        ok = (hits == runs) if q["should"] else (hits == 0)
        rows.append({**q, "hits": hits, "runs": runs, "ok": ok})

    (out / "report.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"| Skill | 該叫 | 句子 | 叫了幾次 |\n|---|---|---|---|")
    for row in rows:
        print(f"| /{row['skill']} | {'是' if row['should'] else '否'} | {row['query']} | {row['hits']}/{row['runs']} {'' if row['ok'] else '✗'} |")
    good = sum(1 for r in rows if r["ok"])
    print(f"\n{good}/{len(rows)} 句照預期；report: {out / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
