# [Day 27] Claude Code!奏樂~

艾玲站在北邊舊路的岔路口，前面有個帶刀的男人守著往林子的小徑。今天要來過他這一關。

不過在過關之前，我們先來做一件從 Day 11 就想做的事：幫冒險配樂。遊戲一開始就放一首曲子，換場景就換一首，結束時再把音樂關掉。這會用到兩個還沒教過的 Hook 事件 `SessionEnd`、`FileChanged`，還有 Day 21 教過的 `SessionStart` 的另一種用法。另外，音效從 Day 11 開始一個一個加上去，今天會再加幾個，順便把所有音效整理成一張表。

今天要做三件事：

1. **配樂**：準備五首曲子和一張「哪個場景放哪一首」的對照表，再用三個 Hook 決定什麼時候放、什麼時候換、什麼時候關。
2. **音效總表**：把每個聲音什麼時候響、由誰負責播放，整理成一張表，包含今天新加的五個聲音。
3. **過岔路口**：打架、說服、聲東擊西或潛行繞過去，四種方法都走得通；另外，守路的人身上還帶著白狼下的命令。

![pixel art：地城領主坐在長桌後，桌上有紙卷、小銅鈴、水晶球、攤開的書、骰塔、二十面骰、黃銅機械手臂和齒輪、沙漏、藥水、一疊被圓石壓平的紙、蠟燭，桌子左邊靠著掃帚，右後方站著拿長矛的守衛，牆上有記事板和自己寫字的羽毛筆，左邊柱子掛著金色面具，右邊柱子貼著三張紅蠟便條紙，地上有鐵鏈和上鎖的寶箱，桌前坐著學徒，學徒的小書桌上有一本扣著銅鎖的薄冊子，學徒和寶箱之間有一個綁著麻繩的木箱，左下角有一本攤開的厚手冊，右下角有一座黃銅天秤，左邊柱子旁靠著一把魯特琴](assets/00-cover.png)

## 換上 Day 27 的地城

照下面的步驟換上去：

1. 從 repo 的 [`articles/27/dungeon/`](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/27/dungeon) 複製這些到你的 dungeon 資料夾：`bgm\` 整個資料夾（五首曲子、`tracks.json`、`CREDITS.md`）、`.claude\hooks\bgm.py`、`.claude\skills\bgm\`，和 `.claude\hooks\sounds\` 裡的 `open.wav`、`close.wav`、`stop.wav`、`down.wav`、`buzz.wav`。
2. 這幾個檔案直接用 repo 的版本覆蓋：`.claude\settings.json`、`.claude\hooks\sound.py`、`.claude\hooks\audit.py`、`.claude\hooks\sounds\manifest.json`、`.claude\hooks\sounds\CREDITS.md`、`data\actors.json`、`data\items.json`、`rules.md`、`tools\run_turns.sh`（headless 跑的時候不放音樂）。
3. 重開 Claude Code。重開的時候就會聽到開門聲和酒館的曲子。

不想聽音樂的話，可以打 `/bgm off`；或是在啟動 Claude Code 之前，先設好環境變數 `DUNGEON_BGM=0`，整套配樂就完全不會啟動。音量用 `DUNGEON_BGM_VOLUME` 調整，範圍是 0 到 1000，預設是 500。

## 五首曲子和一張對照表

`bgm\` 資料夾裡有五首 mp3，都是我用生成式音樂工具做的，再用 ffmpeg 把每一首的音量調成一樣大，頭尾各加上 1.5 秒的淡入、淡出：

| 檔案 | 用在 | 長度 |
|---|---|---|
| `tavern.mp3` | 醉月酒館、二樓 | 62 秒循環 |
| `cellar.mp3` | 舊地窖 | 93 秒循環 |
| `road.mp3` | 北邊舊路 | 120 秒循環 |
| `camp.mp3` | 之後的場景 | 120 秒循環 |
| `ending.mp3` | 結局 | 45 秒，只播一次 |

哪個場景要放哪一首，寫在 `bgm\tracks.json`：

```json
{
  "scenes": {
    "tavern": "tavern",
    "upstairs": "tavern",
    "cellar": "cellar",
    "old_road": "road"
  },
  "ending": "ending"
}
```

`scenes` 裡左邊是場景的代號，右邊是曲子的名字，二樓和酒館共用同一首；最後的 `ending` 是結局要放的曲子。想換配樂，只要改這張表就好，不用動到程式。

## 三個 Hook：開始時放、換場景時換、結束時關

負責播音樂的是 `.claude\hooks\bgm.py`。這支腳本可以帶三種參數，每一種交給一個 Hook 事件來觸發：

| 事件 | 什麼時候觸發 | `bgm.py` 做什麼 |
|---|---|---|
| `SessionStart` | 對話開始 | `start`：看 `state.json` 裡艾玲在哪裡，放那個場景的曲子 |
| `FileChanged` | `state.json` 有變動 | `sync`：場景變了就換一首，沒變就繼續放 |
| `SessionEnd` | 對話結束 | `stop`：把正在播放音樂的程式關掉 |

`settings.json` 裡是這樣寫的：

```json
"SessionStart": [
  {
    "hooks": [
      { "type": "command", "command": "uv run --no-project .claude/hooks/recap.py" },
      { "type": "command", "command": "uv run --no-project .claude/hooks/bgm.py start", "async": true },
      { "type": "command", "command": "uv run --no-project .claude/hooks/sound.py open" }
    ]
  }
],
"SessionEnd": [
  {
    "hooks": [
      { "type": "command", "command": "uv run --no-project .claude/hooks/bgm.py stop", "timeout": 5 },
      { "type": "command", "command": "uv run --no-project .claude/hooks/sound.py close", "timeout": 5 }
    ]
  }
],
"FileChanged": [
  {
    "matcher": "state.json",
    "hooks": [
      { "type": "command", "command": "uv run --no-project .claude/hooks/bgm.py sync", "timeout": 15 }
    ]
  }
]
```

這段設定有三個地方要特別說明。

**`SessionStart` 的 `async: true`**。Day 21 的前情提要也是由 `SessionStart` 觸發，它印出來的字要放進對話裡，所以 Claude Code 會等它跑完。但放音樂就不用等了，加上 Day 16 用過的 `async: true`，讓它在背景跑，遊戲開始時才不會被拖慢。

**`FileChanged` 盯的是檔案，不是工具**。Day 16 的音效是用 `PostToolUse` 觸發的，引擎的工具一跑完，聲音就會響。那換曲為什麼不也這樣做？因為 `/newgame` 和 `/load` 不是工具呼叫：這兩個 Skill 是用 Day 8 的 `!` 展開去跑 `gamectl.py`，直接改掉 `state.json`，`PostToolUse` 根本看不到。`FileChanged` 則是直接盯著檔案：不管是誰改了 `state.json`，Claude Code 自己寫的、Bash 跑的，還是 `!` 展開跑的，都會觸發。`matcher` 寫的是檔名，用 `|` 可以接好幾個，但不能用正規表示式。Hook 會從 stdin 收到兩個欄位：`file_path` 是哪一個檔案，`event` 是發生了什麼事（`change` 是修改、`add` 是新增、`unlink` 是刪除）。

**`SessionEnd` 預設只給 1.5 秒**。對話結束時，Claude Code 不會等太久：所有 `SessionEnd` 的 Hook 加起來，預設只有 1.5 秒可以跑。關音樂和播關門聲都要花一點時間，所以兩個都設了 `timeout: 5`；只要有 Hook 設了比較長的 `timeout`，Claude Code 就會把總共能等的時間，拉長到最長的那一個。另外，`SessionEnd` 沒辦法擋下對話結束，印出來的 JSON 也會直接被丟掉，所以只能拿來做結束前的收拾。

重開 Claude Code，打 `/hooks` 看一眼：`SessionStart` 底下三個，`SessionEnd` 兩個，`FileChanged` 一個，盯的是 `state.json`。

![打 /hooks 打開的清單，最上面寫 18 hooks on 9 events：PreToolUse 一個 guard、PostToolUse 一個 sound、UserPromptSubmit／UserPromptExpansion／MessageDisplay 各一個 story；SessionStart 三個：recap、bgm、sound；Stop 三個：sound、audit、story；SessionEnd 兩個：bgm、sound；FileChanged 一個 bgm，matcher 是 state.json；另外幾行標著 [User] 和 [Plugin] 的是我自己電腦的全域設定和 plugin，你的清單不會有](assets/01-hooks-menu.png)

真正播放音樂的，是另外開的一支程式。`bgm.py start` 把播放器開成一支獨立的程式之後，自己就先結束，不用等音樂放完；播放器的程式編號（PID）記在 `.game\bgm.json`，`sync` 和 `stop` 再照這個編號去把它關掉。至於用什麼播放：Windows 用系統內建的 winmm 播 mp3，macOS 用 `afplay`，Linux 則要裝了 `ffplay` 或 `mpv` 才有聲音。

目前有一個已知的限制：如果 Claude Code 當掉，`SessionEnd` 就不會跑，音樂會一直放下去，要等下次打開 Claude Code 時才會被關掉，或是打 `/bgm off` 手動關掉。

## /bgm：讓玩家自己開關音樂

```yaml
---
name: bgm
description: 開或關背景音樂。只由玩家觸發。
argument-hint: "[on|off]"
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project .claude/hooks/bgm.py toggle *)
---
```

打 `/bgm off`，會在 `.game\` 裡建一個 `bgm_off` 檔案，同時關掉播放器；之後 `SessionStart` 和 `FileChanged` 看到這個檔案，就不會再放音樂。打 `/bgm on` 會刪掉這個檔案，音樂馬上接著放。這個 Skill 跟 Day 9 的 `/cheat` 一樣設了 `disable-model-invocation: true`，只有玩家能叫，DM 不能自己決定開關音樂。

## 音效總表

音效是一路慢慢加上來的：Day 11 讓 DM 講完話時響一聲 Windows 內建的 chimes；Day 16 換成自己找的音效檔，加上擲骰、命中、落空和休息的聲音；Day 17 換場景時會響開門聲。今天再加五個：對話開始的開門聲、對話結束的關門聲、DM 講完話的收尾聲（取代 chimes）、HP 歸零的倒下聲，還有查帳抓到 DM 時的嗡嗡聲。全部整理成一張總表：

| 聲音 | 檔案 | 什麼時候響 | 誰播的 |
|---|---|---|---|
| 骰子 | `dice.wav` | 每擲一次骰：攻擊、檢定、休息補血 | `PostToolUse`（`sound.py --result`） |
| 命中、落空 | `hit.wav`、`miss.wav` | 每一次攻擊，不管是你打敵人，還是敵人打你 | `PostToolUse` |
| 營火 | `rest.wav` | 休息 | `PostToolUse` |
| 開門 | `door.wav` | 換場景，或檢定的結果把你帶到別的地方 | `PostToolUse` |
| 倒下 | `down.wav` | HP 歸零 | `PostToolUse` |
| 嗡 | `buzz.wav` | 查帳抓到 DM 的票根對不上 | `Stop`（`audit.py`） |
| 開門、關門 | `open.wav`、`close.wav` | 對話開始、對話結束 | `SessionStart`、`SessionEnd` |
| 收尾 | `stop.wav` | DM 講完話 | `Stop`（原本是 Windows 內建的 chimes） |

`sound.py --result` 會從 `PostToolUse` 的 `tool_response`（Day 16 講過）讀出引擎的結果，再看結果的種類（`kind`），決定要播哪些聲音、照什麼順序播：

- **攻擊**：每出手一次，就播一組「骰子聲，再接命中或落空」。
- **換場景**：先播離開時被敵人追擊的那幾組，再播開門聲，最後是進門時被偷襲的那幾組。
- **檢定**：先播自己擲骰的聲音（買酒這種不擲骰的就沒有）；結果把你帶到別的地方，就播開門聲；最後是對方反擊的那幾組。
- **休息**：先播營火聲，有擲骰再加上骰子聲。

不管是哪一種，最後只要艾玲倒下，就再加一聲倒下聲。這些規則全部寫在 `sounds_for()` 這個函式裡，一種結果對應一個 `if`。

## 實際玩看看過劇情的效果

守路的人擋在往林子的小徑前面。目前打架、說服、聲東擊西、潛行繞過去，引擎都會接受(寫在規則書 `rules.md`)。說服：

> 你走到那個帶刀的男人面前，說自己是來找商隊下落的，請他讓路。他的手一直沒離開刀柄，眼神在你身上打量。他低頭看了看你手上，沉默了一陣子，風吹過草叢沙沙響。
>
> 然後他側身讓開，往林子的方向偏了偏頭。「他在林子裡等你。」

他腰帶上那張字條不會主動給你。打倒他會掉出來，或是趁他不注意偷過來。我偷到了，上面寫著：

> 「只攔車，不准傷人。那一箱收件人是鎮長的，一定要拿到。——白狼」

女孩說過，那晚白狼沒有殺人，只把貨箱搬走。現在才知道，這是白狼給手下的命令；他們真正要的，是收件人寫著鎮長的那一箱。

回到今天的主題：配樂到底有沒有跟著換？看 `.game\bgm.log`。下面是艾玲出鎮走上舊路那一刻的紀錄：`FileChanged` 發現 `state.json` 裡的場景變了，`sync` 就把曲子換成 `road.mp3`：

```
10:54:21 play road once=False pid=42180
10:54:21 mci open rc=0 file=road.mp3
10:54:22 mci play rc=0 once=False volume=500
```

## 目前還有什麼問題嗎？

過了岔路口，林子裡的小徑一路通往白狼的營地。明天就走進營地去見白狼，順便來算一算：這場冒險玩到現在，到底花了多少錢。

今天結束時 `dungeon` 資料夾的完整內容在 [articles/27/dungeon](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/27/dungeon)，給大家參考。

## 目前學會的 Claude Code 機制

- ✅ [Day 1](https://ithelp.ithome.com.tw/articles/10410444)：安裝與登入、四種介面；`/model`、`/effort`、`/usage`
- ✅ [Day 2](https://ithelp.ithome.com.tw/articles/10410920)：session：`.jsonl`、`--resume`、`-c`、`/resume`、`cleanupPeriodDays`
- ✅ [Day 3](https://ithelp.ithome.com.tw/articles/10412229)：CLAUDE.md：三層、`@` 匯入、`/init`；`/context`
- ✅ [Day 4](https://ithelp.ithome.com.tw/articles/10412897)：內建工具：Read／Bash／Edit；`Ctrl+O`
- ✅ [Day 5](https://ithelp.ithome.com.tw/articles/10413695)：checkpoint：`/rewind`、`/branch`
- ✅ [Day 6](https://ithelp.ithome.com.tw/articles/10414052)：Skill：`SKILL.md`、`description`、skill-creator
- ✅ [Day 7](https://ithelp.ithome.com.tw/articles/10414950)：權限：權限模式、`Shift+Tab`、`/permissions`、allow／ask／deny、`settings.json`
- ✅ [Day 8](https://ithelp.ithome.com.tw/articles/10415525)：Skill：`$ARGUMENTS`、`argument-hint`、`!` 展開
- ✅ [Day 9](https://ithelp.ithome.com.tw/articles/10415783)：Skill：`disable-model-invocation`、`user-invocable`、`allowed-tools`
- ✅ [Day 10](https://ithelp.ithome.com.tw/articles/10416355)：Plan Mode：`/plan`、`Ctrl+G`
- ✅ [Day 11](https://ithelp.ithome.com.tw/articles/10416813)：Hook：`Stop`、`UserPromptExpansion`、`PostToolUse`、`matcher`、`if`、`/hooks`
- ✅ [Day 12](https://ithelp.ithome.com.tw/articles/10417400)：Hook：`PreToolUse`、exit 2、`tool_input`、`Edit|Write`、UTF-8 with BOM；deny 保護 Hook
- ✅ [Day 13](https://ithelp.ithome.com.tw/articles/10417813)：Hook：`last_assistant_message`、`systemMessage`；帳本與票根
- ✅ [Day 14](https://ithelp.ithome.com.tw/articles/10418294)：狀態列：`statusLine`、`refreshInterval`；`uv run`
- ✅ [Day 15](https://ithelp.ithome.com.tw/articles/10418977)：MCP：host／client／server、stdio、Streamable HTTP、`claude mcp add`、`.mcp.json`、`/mcp`、`mcp__server__tool`、`ToolError`；`uvx`
- ✅ [Day 16](https://ithelp.ithome.com.tw/articles/10419326)：MCP：多個工具、回傳 JSON 與錯誤；Hook：`tool_response`、`async`
- ✅ [Day 17](https://ithelp.ithome.com.tw/articles/10419772)：權限：`Read(path)` deny；Hook：`PreToolUse` 擋 Bash、`permissionDecision`；`!` 展開失敗
- ✅ [Day 18](https://ithelp.ithome.com.tw/articles/10420242)：Subagent：`.claude/agents/`、`name`、`description`、`Agent`、背景執行、`@agent-名字`、`/tasks`
- ✅ [Day 19](https://ithelp.ithome.com.tw/articles/10420547)：Subagent：`tools`、`omitClaudeMd`、`subagents/`；`env`、`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`
- ✅ [Day 20](https://ithelp.ithome.com.tw/articles/10420976)：auto memory：`MEMORY.md`、`type`、`/memory`、`autoMemoryEnabled`
- ✅ [Day 21](https://ithelp.ithome.com.tw/articles/10421396)：Hook：`SessionStart`、`startup`／`resume`／`clear`／`compact`／`fork`、`source`、`additionalContext`；`/clear`、`/compact`
- ✅ [Day 22](https://ithelp.ithome.com.tw/articles/10421723)：output style：`.claude/output-styles/`、`keep-coding-instructions`、`outputStyle`、`/output-style`
- ✅ [Day 23](https://ithelp.ithome.com.tw/articles/10422123)：headless：`claude -p`、`--output-format json`、`--resume`、`--allowedTools`、`--permission-prompts`、`--setting-sources`、`--strict-mcp-config`；Hook：`UserPromptSubmit`、`MessageDisplay`、`prompt_id`
- ✅ [Day 24](https://ithelp.ithome.com.tw/articles/10422460)：plugin：`plugin.json`、`hooks/hooks.json`、`${CLAUDE_PLUGIN_ROOT}`、`CLAUDE_PROJECT_DIR`、`dm:` 前綴、`mcp__plugin_dm_dungeon__`、`claude plugin validate`、`--plugin-dir`；marketplace：`marketplace.json`、`/plugin install --marketplace`、`enabledPlugins`、`extraKnownMarketplaces`
- ✅ [Day 25](https://ithelp.ithome.com.tw/articles/10422629)：mod：`hooks/register.tsx`、`on(事件, 條件, 函式)`、`session.start`、`turn.start`、`tool.call`、`turn.complete`、`command.run`、`ui.render`、`$.command.register`、`$.ui.open`、`$.process.run`、`$.prompt.fill`、`claude plugin test`、`@skills-dir`；`"tui": "fullscreen"`、`/tui`
- ✅ [Day 26](https://ithelp.ithome.com.tw/articles/10422877)：Skill 觸發率：該叫／不該叫的句子、多跑幾次算比例、`description` 改前改後；`claude plugin eval`、`tool_used`、`tools/skill_rate.py`
- ✅ Day 27：Hook：`SessionEnd`、`reason`、`FileChanged`、`file_path`、`event`、`SessionStart` 的 `async`
