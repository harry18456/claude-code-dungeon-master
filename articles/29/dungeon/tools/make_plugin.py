"""tools/make_plugin.py — pack everything a plugin can carry, and the rest as an adventure folder.

A plugin can carry skills, subagents, hooks, output styles and MCP servers, so the
plugin gets all of them: the dm-voice output style, the rules judge, every skill,
the hooks with their sounds, and the dungeon engine with its MCP server, scenes,
data and rules book. The adventure folder keeps only what a plugin cannot carry:
CLAUDE.md, the permission rules, the status line, the env setting and the save,
which starts as a new game.

    uv run --no-project tools/make_plugin.py <out_dir> [--adventure <dir>]

<out_dir> becomes a marketplace: .claude-plugin/marketplace.json plus
plugins/dm/. With --adventure, <dir> gets this dungeon without the plugin's
parts; its settings.json names the marketplace and enables the plugin, so
Claude Code offers to install it when someone opens the folder.

Inside a plugin some names change: the MCP server's tools become
mcp__plugin_dm_dungeon__<tool>, and gamectl.py is reached through
${CLAUDE_PLUGIN_ROOT}. The plugin's copies are rewritten for that; the dungeon's
own files stay as they are.
"""
import json
import pathlib
import re
import shutil
import sys

try:  # Windows consoles default to cp950
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = "dm"
SERVER = "dungeon"
MARKETPLACE = "dungeon-master"
REPO = "harry18456/claude-code-dungeon-master"
DESCRIPTION = ("地城領主：說話方式 dm-voice、規則裁判、存讀檔、前情提要、查帳、守衛、日誌和音效，"
               "加上 dungeon 引擎、MCP server、場景和規則書。CLAUDE.md、權限和存檔放在你的冒險資料夾。")
HOOK_SCRIPTS = ["audit.py", "guard.py", "recap.py", "sound.py", "story.py"]
GAME_FILES = ["gamectl.py", "rules.md"]           # moved from the dungeon root to the plugin root
GAME_DIRS = ["engine", "data", "scenes"]
SKIP = {".git", ".game", "reports", "__pycache__", "hooklogs"}
ADVENTURE_SKIP = {"tools", ".mcp.json", "settings.local.json"}  # the dungeon's own tools and server config

TOOLS = (f"mcp__{SERVER}__", f"mcp__plugin_{PLUGIN}_{SERVER}__")
GAMECTL = ("uv run --no-project gamectl.py", 'uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py"')
JUDGE = [("tools: Read, ", "tools: "), ("讀 `rules.md`，", "讀最後面附的規則書，")]
CLAUDE_MD = [("`/save`、`/load`", "`/dm:save`、`/dm:load`"), ("`/check ", "`/dm:check "),
             ("交給 rules-judge 子代理", "交給 dm:rules-judge 子代理"),
             ("全文在 rules.md", "全文在 `dm:rules` Skill"),
             ("動詞從 `rules.md` 的九個選", "動詞從規則書（`dm:rules`）的九個選")]
MOVED_RULES = ("rules.md", "./engine/", "./data/", "./scenes/", "./gamectl.py")
PLUGIN_DENY = ["Edit(~/.claude/plugins/**)", "Read(~/.claude/plugins/**/scenes/**)"]
RULES_SKILL = ("---\nname: rules\n"
               "description: 規則書全文（精簡版 D&D）：九個動詞（resolve_check 的 rule_id）、DC、戰鬥、裝備。"
               "要挑動詞或查規則時讀這個。\n---\n\n")


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_text(path):
    return path.read_text(encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text, pairs, where):
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"{where}: expected one {old!r}")
        text = text.replace(old, new)
    return text


def plugin_names(text):
    """Tool names and gamectl calls as they are inside the plugin."""
    return text.replace(*TOOLS).replace(*GAMECTL)


def skill_dirs():
    """Every skill of the dungeon; a folder that is its own plugin (a mod) is not a skill."""
    base = ROOT / ".claude" / "skills"
    return sorted(p for p in base.iterdir()
                  if (p / "SKILL.md").exists() and not (p / ".claude-plugin").exists())


def plugin_hooks(settings):
    """The project's hooks, pointed at the scripts inside the plugin."""
    hooks = json.loads(json.dumps(settings["hooks"]))
    for groups in hooks.values():
        for group in groups:
            if "matcher" in group:
                group["matcher"] = group["matcher"].replace(*TOOLS)
            for h in group["hooks"]:
                new = re.sub(r"\.claude/hooks/([\w-]+\.py)", r'"${CLAUDE_PLUGIN_ROOT}/hooks/\1"', h["command"])
                if new == h["command"]:
                    raise SystemExit(f"hook does not run a script from .claude/hooks/: {h['command']}")
                script = re.search(r"hooks/([\w-]+\.py)", new).group(1)
                if script not in HOOK_SCRIPTS:
                    raise SystemExit(f"hook runs {script}, which the plugin does not carry")
                h["command"] = new
    return {"hooks": hooks}


def plugin_mcp():
    """The dungeon's MCP server, started from the plugin's copy of the engine."""
    servers = json.loads(read_text(ROOT / ".mcp.json"))["mcpServers"]
    server = json.loads(json.dumps(servers[SERVER]))
    args = server["args"]
    if args.count("engine/server.py") != 1:
        raise SystemExit(f".mcp.json: expected engine/server.py in {args}")
    server["args"] = [a.replace("engine/server.py", "${CLAUDE_PLUGIN_ROOT}/engine/server.py") for a in args]
    return {"mcpServers": {SERVER: server}}


def copy_tree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP))


def make_plugin(out):
    claude = ROOT / ".claude"
    settings = json.loads(read_text(claude / "settings.json"))
    rules = read_text(ROOT / "rules.md")
    dst = out / "plugins" / PLUGIN
    if dst.exists():
        shutil.rmtree(dst)
    write_json(dst / ".claude-plugin" / "plugin.json", {
        "name": PLUGIN, "displayName": "Dungeon Master", "version": "1.0.0", "description": DESCRIPTION,
        "author": {"name": "harry18456", "url": "https://github.com/harry18456"},
        "homepage": f"https://github.com/{REPO}", "repository": f"https://github.com/{REPO}",
        "keywords": ["trpg", "dungeon-master", "game"]})
    copy_tree(claude / "output-styles", dst / "output-styles")
    for agent in sorted((claude / "agents").glob("*.md")):
        text = plugin_names(read_text(agent))
        if agent.stem == "rules-judge":  # the judge cannot Read outside the project, so the rules ride along
            text = replace_once(text, JUDGE, agent.name).rstrip("\n") + "\n\n---\n\n" + rules
        write_text(dst / "agents" / agent.name, text)
    for skill in skill_dirs():
        copy_tree(skill, dst / "skills" / skill.name)
        md = dst / "skills" / skill.name / "SKILL.md"
        write_text(md, plugin_names(read_text(md)))
    write_text(dst / "skills" / "rules" / "SKILL.md", RULES_SKILL + rules)
    for name in HOOK_SCRIPTS:
        (dst / "hooks").mkdir(parents=True, exist_ok=True)
        shutil.copy2(claude / "hooks" / name, dst / "hooks" / name)
    copy_tree(claude / "hooks" / "sounds", dst / "hooks" / "sounds")
    write_json(dst / "hooks" / "hooks.json", plugin_hooks(settings))
    for name in GAME_FILES:
        shutil.copy2(ROOT / name, dst / name)
    for name in GAME_DIRS:
        copy_tree(ROOT / name, dst / name)
    write_json(dst / ".mcp.json", plugin_mcp())
    left = [p for p in dst.rglob("*.md") if "uv run --no-project gamectl.py" in read_text(p) or TOOLS[0] in read_text(p)]
    if left:
        raise SystemExit(f"old names left in: {[str(p.relative_to(dst)) for p in left]}")
    write_json(out / ".claude-plugin" / "marketplace.json", {
        "name": MARKETPLACE, "description": "iThome 鐵人賽「30 天建立 Claude Code 地城領主」用到的 plugin",
        "owner": {"name": "harry18456", "url": "https://github.com/harry18456"},
        "plugins": [{"name": PLUGIN, "source": f"./plugins/{PLUGIN}", "description": DESCRIPTION}]})
    print(f"plugin: {dst}")


def in_plugin(rel):
    parts = rel.parts
    if parts[:1] and parts[0] in GAME_FILES + GAME_DIRS:
        return True
    return parts[:2] in ((".claude", "output-styles"), (".claude", "agents"), (".claude", "hooks"),
                         (".claude", "skills"))


def make_adventure(dst):
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"{dst} is not empty")
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if path.is_dir() or SKIP & set(rel.parts) or ADVENTURE_SKIP & {rel.parts[0], rel.name} or in_plugin(rel):
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst / rel)
    settings = json.loads(read_text(ROOT / ".claude" / "settings.json"))
    del settings["hooks"]
    perms = settings["permissions"]
    perms["allow"] = [r.replace(*TOOLS) for r in perms["allow"]]
    perms["deny"] = [r for r in perms["deny"] if not any(m in r for m in MOVED_RULES)] + PLUGIN_DENY
    settings["outputStyle"] = f"{PLUGIN}:dm-voice"
    settings["extraKnownMarketplaces"] = {MARKETPLACE: {"source": {"source": "github", "repo": REPO}}}
    settings["enabledPlugins"] = {f"{PLUGIN}@{MARKETPLACE}": True}
    write_json(dst / ".claude" / "settings.json", settings)
    write_text(dst / "CLAUDE.md", replace_once(read_text(ROOT / "CLAUDE.md"), CLAUDE_MD, "CLAUDE.md"))
    # a friend starts a new game: this dungeon's save point means nothing without its .game/ records
    write_json(dst / "state.json", json.loads(read_text(ROOT / "data" / "seed_state.json")))
    print(f"adventure: {dst}")


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__)
        return 1
    make_plugin(pathlib.Path(argv[1]).resolve())
    if "--adventure" in argv:
        make_adventure(pathlib.Path(argv[argv.index("--adventure") + 1]).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
