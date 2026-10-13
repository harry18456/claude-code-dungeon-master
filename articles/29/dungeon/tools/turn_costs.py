"""tools/turn_costs.py — what each headless turn cost and how long it took, from run_turns.sh output.

    uv run --no-project tools/turn_costs.py <outdir> [<outdir> ...]

Each <outdir> is a folder run_turns.sh wrote (turn_NN.json inside). For every
turn: the model, the cost of that turn (the JSON's total_cost_usd is a running
total over the resumed session, so the turn's own cost is the difference), the
wall time and the tokens. One table per folder, then one line per folder with
the sums, so two folders played with different settings compare side by side.
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")


def turns(out: pathlib.Path) -> list[dict]:
    rows, before = [], 0.0
    for path in sorted(out.glob("turn_[0-9][0-9].json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        total = float(r.get("total_cost_usd") or 0.0)
        usage = r.get("usage") or {}
        model = ", ".join(sorted((r.get("modelUsage") or {}).keys())) or "?"
        rows.append({
            "turn": path.stem[-2:], "model": model,
            "cost": total - before, "seconds": (r.get("duration_ms") or 0) / 1000,
            "in": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
            "out": usage.get("output_tokens", 0), "steps": r.get("num_turns", 0),
        })
        before = total
    return rows


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    totals = []
    for arg in argv[1:]:
        out = pathlib.Path(arg)
        rows = turns(out)
        print(f"\n{out.name}")
        print("| 回合 | 模型 | 這回合費用 | 秒 | 輸入 token | 輸出 token | 步數 |\n|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['turn']} | {r['model']} | ${r['cost']:.3f} | {r['seconds']:.0f} | {r['in']:,} | {r['out']:,} | {r['steps']} |")
        totals.append((out.name, sum(r["cost"] for r in rows), sum(r["seconds"] for r in rows), len(rows)))
    print("\n| 跑法 | 回合數 | 總費用 | 總秒數 | 每回合 |\n|---|---|---|---|---|")
    for name, cost, secs, n in totals:
        print(f"| {name} | {n} | ${cost:.2f} | {secs:.0f} | ${cost / max(n, 1):.3f}，{secs / max(n, 1):.0f} 秒 |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
