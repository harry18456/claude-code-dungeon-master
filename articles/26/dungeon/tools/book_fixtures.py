"""tools/book_fixtures.py — the engine's real answers, for the tests of the book mod.

    uv run --no-project tools/book_fixtures.py           write .claude/skills/book/hooks/fixtures.ts
    uv run --no-project tools/book_fixtures.py --check   say whether that file is up to date

The mod in .claude/skills/book only draws what `gamectl.py book` prints, and its
tests (`claude plugin test`) answer in the engine's place. These fixtures are that
answer, taken from op_book itself, so a change to its shape shows up in the mod's
tests and not on the player's screen. tests/test_book.py fails while the file is stale.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import core  # noqa: E402

OUT = ROOT / ".claude" / "skills" / "book" / "hooks" / "fixtures.ts"
# name -> (what the player just did, how the state differs from a new game)
STATES = {
    "TAVERN": ("a new game", {}),
    "CELLAR": ("down in the cellar for the first time",
               {"location": "cellar", "visited": ["tavern", "cellar"], "version": 1}),
    "BACK": ("back in the tavern, two things learned",
             {"visited": ["tavern", "cellar"], "version": 9, "flags": {"cloaked_talked": True, "cellar_cleared": True}}),
}


def render() -> str:
    seed = json.loads(core.SEED.read_text(encoding="utf-8"))
    lines = ["// Written by tools/book_fixtures.py from op_book in engine/core.py. Run the tool; do not edit.", ""]
    for name, (what, changes) in STATES.items():
        st = {"visited": [seed["location"]], **seed, **changes}
        book = json.dumps(core.op_book(st), ensure_ascii=False)
        lines += [f"// {what}", f"export const {name} = {json.dumps(book, ensure_ascii=False)}", ""]
    return "\n".join(lines)


def main(argv):
    if "--check" in argv:
        stale = not OUT.exists() or OUT.read_text(encoding="utf-8") != render()
        print("stale: run uv run --no-project tools/book_fixtures.py" if stale else "up to date")
        return 1 if stale else 0
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
