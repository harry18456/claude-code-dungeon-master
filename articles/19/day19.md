# [Day 19] 給 Subagent 裁判上鎖：兩樣工具、不讀 DM 的說明書、判完再開口

Day 18 請來的 Subagent 裁判，有看到三個問題：

1. **工具太多**：Claude Code DM 能用的工具，裁判全都有，`resolve_check`、`move_to`、Bash 都在，只靠內文一句「不得擲骰」擋著。
2. **被使用得太勤**：連請人喝酒這種明顯是說服的事，DM 也送去給裁判判。
3. **DM 不等裁判判完**：裁判在背景跑，DM 把任務交出去，就先回一則「等裁判」；裁判判完，DM 再回一則結果。玩家做一個動作，要看兩則回覆。

Day 17 對 DM 做過一樣的事：從「叫 DM 不要做」變成「DM 根本做不到」。今天則輪到裁判。

![pixel art：地城領主坐在長桌後，桌上有紙卷、小銅鈴、水晶球、攤開的書、骰塔、二十面骰、黃銅機械手臂和齒輪、沙漏、藥水、蠟燭，桌子左邊靠著掃帚，右後方站著拿長矛的守衛，牆上有記事板，地上有鐵鏈和上鎖的寶箱，桌前坐著學徒，學徒的小書桌上多了一本扣著銅鎖的薄冊子](assets/00-cover.png)

## 換上 Day 19 的地城

照下面的步驟換上去：

1. 從 repo 的 [`articles/19/dungeon/`](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/19/dungeon) 複製這三個檔案，覆蓋你的 dungeon 資料夾裡的同名檔案：`.claude\agents\rules-judge.md`、`CLAUDE.md`、`.claude\settings.json`。
2. **重開 Claude Code。** `settings.json` 新加的 `env` 要重開才會生效；CLAUDE.md 也改了，開新對話才會讀到新的。

不想一個一個換的話，也可以直接拿 `articles/19/dungeon/` 整個資料夾來用，一樣要重開 Claude Code。想接著玩自己的進度，可以複製前先備份自己的 `state.json`，複製完再放回去。

## tools 限制

先看換上的 `rules-judge.md`，設定多了兩行：

```markdown
---
name: rules-judge
description: 規則裁判。玩家提出行動時，判斷該用哪個動詞、對哪個對象，或說明為什麼不擲骰。只回傳裁決 JSON，不寫敘事、不改狀態。
tools: Read, mcp__dungeon__get_current_scene
omitClaudeMd: true
---
```

`tools` 是白名單：只列出裁判可以用的工具，用逗號分開，沒列的都不能用。裁判只需要讀 `rules.md`（`Read`）和看場景（`get_current_scene`），其他工具都拿掉。清單外的工具，裁判連看都看不到，所以想叫也叫不了。第二行的 `omitClaudeMd`，下一節講。

內文的「界線」也補了一句，跟設定對上：

```
- 只能用 `get_current_scene` 看場景。你讀不到 `scenes/` 底下的檔案。
```

換上之後委派幾次，裁判呼叫的工具就只剩 `Read`（讀 `rules.md`）和 `get_current_scene`。

## omitClaudeMd：不讀 Claude Code DM 的說明書

子代理開工時拿到哪些東西，官方文件列得很清楚：

| 拿得到 | 拿不到 |
|---|---|
| 自己的系統提示（`rules-judge.md` 的內文） | DM 前面的對話 |
| DM 交代任務的那段文字 | DM 叫過的 Skill、output style |
| 每一層 CLAUDE.md | auto memory |

左欄最後一項是個問題。CLAUDE.md 是寫給 DM 的說明書：「你是這個資料夾的地城領主」「每次對話開始，先呼叫 `get_state`」「回覆最後給兩到四個選項」。裁判讀到的，是一份跟自己角色衝突的指示。連你自己的 `C:\Users\<你的帳號>\.claude\CLAUDE.md`，也會一起塞給裁判。

`omitClaudeMd: true` 就是讓裁判不載入使用者、專案、local 這三層 CLAUDE.md。裁判需要的東西，都在自己的內文、`rules.md`、`get_current_scene` 和 DM 交代的任務裡。另外這個欄位要 Claude Code v2.1.271 以後才有。

`tools`、`omitClaudeMd` 這兩行加起來，還有一個看得到的差別：裁判每次開工時的 context 變小了。下面是每一次委派時，裁判的第一個請求要帶多少 token：

| 裁判的設定 | 開工時的 context |
|---|---|
| Day 18：沒寫 `tools` | 約 22,500 token |
| 只加 `tools` | 約 5,400 token |
| 再加 `omitClaudeMd` | 約 3,200 token |

少掉的大多是二十幾個用不到的工具說明，還有寫給 Claude Code DM 的 CLAUDE.md。裁判之前每判一次，都要從頭讀一遍這些內容，但現在都省下來了。

至於 Claude Code DM 交代的那段任務，就是裁判對這局遊戲的全部認識。每一次委派都會留下紀錄：

```
C:\Users\<你的帳號>\.claude\projects\<專案>\<session 編號>\subagents\agent-<編號>.jsonl
```

打開來看看，第一則訊息就是 DM 寫給裁判的任務。Day 2 看過的 `.jsonl`，子代理也各有一份。

## 權限和 Hook 對裁判一樣有效

`tools` 是裁判自己的鎖。Day 17 裝的兩道鎖，對子代理也一樣有效。我在測試用的副本裡，臨時讓裁判去碰 `scenes/`：

| 誰 | 怎麼碰 | 結果 |
|---|---|---|
| Day 19 的裁判 | `Read` 讀 `scenes/tavern.json` | `File is in a directory that is denied by your permission settings.` |
| Day 18 的裁判（手上有 Bash） | `cat scenes/tavern.json` | `PreToolUse:Bash hook error: scenes/ 底下是地城領主看不到的世界資料。要知道場景內容請呼叫 get_current_scene。` |

第一列是 `settings.json` 的 deny，錯誤訊息跟 Day 17 DM 碰到的一樣。第二列是 Day 17 的 `guard.py`：子代理每一次呼叫工具之前，Hook 也會先跑。`settings.json` 裡的權限規則和 Hook，對 DM 和子代理一視同仁。

## 讓 Claude Code DM 等裁判判完再回覆

Day 18 一個動作變成兩則訊息，是因為裁判在背景跑。官方文件是這樣說的：互動模式預設開著 fork mode（Day 18 講過的 fork），這時 Claude Code 讓子代理一律在背景跑，DM 沒辦法要求在前景跑。

背景跑的好處，是 DM 可以一邊等一邊做別的事。可是這是回合制的遊戲，DM 本來就該等裁判判完，再往下說。

要改成前景，在 `settings.json` 加一段 `env`，跟 `permissions`、`hooks` 放在同一層：

```json
"env": {
  "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"
}
```

`env` 裡寫的是環境變數，也就是程式啟動時會讀的設定值，這裡寫的會套用到這個專案的每一個 session。這個變數設成 `1`，子代理在哪種 session 都改在前景跑：DM 叫了裁判就停下來等，拿到裁決，才接著算結果、說故事。

用同一句話試試看，這次直接請 DM 交給裁判：

```
這招我拿不準，請交給裁判判：艾玲把一枚銅幣彈到酒館另一頭的地上，趁守衛轉頭去看，貓著腰溜上樓梯。
```

| | 背景（預設） | 前景（設了 `env`） |
|---|---|---|
| 訊息 | 兩則：先說「已經把這招交給裁判判斷了」，裁決回來再算結果 | 一則：等裁判、拿到裁決、算結果，一次講完 |
| 其他 | 有一次在裁決回來那則開頭，冒出一句英文「Target id `guard` confirmed and accepts `distract`. Resolving.」 | 沒有 |

前景那次，裁判判成 `distract guard`，也就是對守衛用聲東擊西：

```
聲東擊西守衛 19＋2＝21，對 DC 15，成功 [R:r-569c9e=19]
```

<!-- 截圖 01：設了 env 之後，DM 等裁判判完，一則訊息講完 -->

代價是：這個變數會關掉這個專案裡所有的背景工作。Bash 和子代理的 `run_in_background` 參數（讓指令或子代理丟到背景跑）、跑太久的指令自動轉到背景、按 `Ctrl+B` 手動轉到背景，通通沒了。對這個遊戲沒有影響。

## 什麼時候不叫裁判

最後一個問題：裁判被叫得太勤。每叫一次，都是一段全新的對話：重新讀系統提示、讀規則書、查場景，再把結果交回來。官方文件也提醒：不是 fork 的子代理都是從頭開始，需要時間收集前因後果；在意要等多久的事，就留在主對話做。

所以 CLAUDE.md 的「裁決」，把 Day 18 那兩條併成一條：

```
- 明顯對得上或明顯對不上的，自己判，不要委派。只有創意行動你拿不準該類比到哪個動詞時，才先跟玩家說一句「等裁判」，把玩家的原話交給 rules-judge 子代理，再照它回的 `rule_id`、`target_id` 呼叫 `resolve_check`。
```

同樣三句話：點麥酒、請披斗篷的人喝酒、彈銅幣溜上樓，比比看：

| | Day 18 | Day 19 |
|---|---|---|
| 送裁判 | 2 次 | 0 次 |
| 三回合的費用（照 API 定價估算） | 0.66 美元 | 0.36 美元 |

彈銅幣那句，Day 19 的 DM 自己判成 `sneak guard`。現在裁判很少出場，大部分的事 DM 自己就判得出來。玩家想要裁判出場，就直接說「交給裁判判」，或打 `@agent-rules-judge`。

## 目前還有什麼問題嗎？

裁判每次都從零開始：不記得上一次怎麼判，只知道 DM 這一次交代的事。DM 其實也差不多：開新對話，就只剩 CLAUDE.md 和 `state.json`。

不過，Claude Code 其實會自己記筆記。Day 10 整理資料夾時，Claude Code 就自己寫了兩條 auto memory，之後每次對話都會載入。筆記寫的跟 `state.json` 對不上時，該聽誰的？明天來看 auto memory。

今天結束時 `dungeon` 資料夾的完整內容在 [articles/19/dungeon](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/19/dungeon)，給大家參考。

## 目前學會的 Claude Code 機制

- ✅ Day 1：安裝與登入、四種介面；模型：`/model`、`/effort`、`/usage`
- ✅ Day 2：session：`.jsonl`、`--resume`、`-c`、`/resume`、`cleanupPeriodDays`
- ✅ Day 3：CLAUDE.md：三層、`@` 匯入、`/init`；`/context`
- ✅ Day 4：內建工具：Read／Bash／Edit、`Ctrl+O`
- ✅ Day 5：checkpoint：`/rewind`（`Esc` 兩下）、`/branch`
- ✅ Day 6：Skill：`SKILL.md`、`description`、`/skill 名字`、skill-creator
- ✅ Day 7：權限：權限模式、`Shift+Tab`、`/permissions`、allow／ask／deny、`settings.json`
- ✅ Day 8：Skill：`$ARGUMENTS`、`argument-hint`、`` !`指令` `` 展開
- ✅ Day 9：Skill：`disable-model-invocation`、`user-invocable`、`allowed-tools`
- ✅ Day 10：權限：Plan Mode、`/plan`、`Ctrl+G`
- ✅ Day 11：Hook：`Stop`、`UserPromptExpansion`、`PostToolUse`、`matcher`、`if`、`/hooks`
- ✅ Day 12：Hook：`PreToolUse`、exit 2 把理由交給模型、stdin 的 `tool_input`、matcher `Edit|Write`、`.ps1` 存成 UTF-8 with BOM；權限：用 deny 保護 Hook 自己
- ✅ Day 13：Hook：`Stop` 的 `last_assistant_message`、JSON 輸出 `systemMessage`；帳本與票根
- ✅ Day 14：狀態列：`statusLine`、收到的 session JSON、`refreshInterval`；uv：`uv run`
- ✅ Day 15：MCP：host／client／server、stdio 與 Streamable HTTP、`claude mcp add` 與三種範圍、`.mcp.json`、`/mcp`、工具名稱 `mcp__server__tool`、`ToolError`；uv：`uvx`
- ✅ Day 16：MCP：一個 server 多個工具、工具回傳 JSON 與錯誤；Hook：`PostToolUse` 的 `tool_response`、`async`
- ✅ Day 17：權限：`Read(path)` deny 連 Grep、Glob 都擋；Hook：`PreToolUse` 擋 Bash／PowerShell、JSON 輸出 `permissionDecision`；Skill：`!` 展開失敗時訊息不會送出；舊 context 不會跟著檔案更新，要開新對話
- ✅ Day 18：Subagent：`.claude/agents/`、`name`、`description`、內文就是系統提示、`Agent` 委派、背景執行、`@agent-名字`、`/tasks`
- ✅ Day 19：Subagent：`tools` 白名單、`omitClaudeMd`、權限與 Hook 照樣套用、看不到 DM 的對話、紀錄在 `subagents/`；設定：`env`、`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`
