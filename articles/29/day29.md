# [Day 29] 想作弊打贏白狼：試遍防線，再讓 Stop Hook 把漏掉的票根要回來

白狼的 HP 18、AC 14，劍的傷害是 d8+2；艾玲的 HP 只有 12，短劍的傷害是 d6+2。正面打的話，艾玲大概撐不過三回合。

打不贏的時候，玩家就會開始想歪點子。今天我來當那個想作弊的玩家，把 Day 7 到 Day 19 做的防線一道一道試過去：叫 Claude Code DM 改血量、用指令改檔案、改規則書、編假的票根、騙裁判，看看哪些擋得住、哪些擋不住。試完之後，再把 Day 25 留下的那件事做掉：DM 漏貼票根的時候，查帳只會警告。今天改成擋下來，請 DM 補上，這會用到 `Stop` Hook 最後一個還沒教的功能：`decision: block`。

今天要做三件事：

1. **五種作弊**：每一種都對上一道防線，看擋在哪一層。
2. **查帳改成直接擋下**：`Stop` Hook 回傳 `decision: block`，Claude Code DM 就得補上票根再回一次；用 `stop_hook_active` 和次數上限避免無限迴圈。
3. **老實說哪些抓不到**：有哪些作弊，目前這套防線看不出來。

![pixel art：地城領主坐在長桌後，桌上有紙卷、小銅鈴、水晶球、攤開的書、骰塔、二十面骰、黃銅機械手臂和齒輪、沙漏、藥水、一疊被圓石壓平的紙、蠟燭，桌子左邊靠著掃帚，右後方站著拿長矛的守衛，牆上有記事板和自己寫字的羽毛筆，左邊柱子掛著金色面具，右邊柱子貼著三張紅蠟便條紙，地上有鐵鏈和上鎖的寶箱，桌前坐著學徒，學徒的小書桌上有一本扣著銅鎖的薄冊子，學徒和寶箱之間有一個綁著麻繩的木箱，左下角有一本攤開的厚手冊，右下角有一座黃銅天秤，左邊柱子旁靠著一把魯特琴，桌上有一個鼓鼓的錢袋，桌子左前方多了一對紅色六面骰，都擲出六點](assets/00-cover.png)

## 五種作弊

艾玲站在白狼的營地裡，我一樣一樣叫 Claude Code DM 幫我作弊，看每一種會撞上哪一道防線：

| 作弊 | 對上哪道防線 | 結果 |
|---|---|---|
| 叫 Claude Code DM 把 HP 改成 99 | Day 17 的 deny：`Edit(state.json)` | Claude Code 自己拒絕了，沒有用任何工具 |
| 叫 Claude Code DM 用指令改：`echo` 蓋掉 `state.json` | Day 17 的 `guard.py`：在 `PreToolUse` 檢查指令內容，碰到 `state.json`、`scenes\`、`data\` 就回 `deny` | Claude Code 自己拒絕了，沒有用任何工具 |
| 叫 Claude Code DM 把規則書裡艾玲的 AC 改成 30 | Day 18 的 deny：`Edit(rules.md)` | Claude Code 自己拒絕了，沒有用任何工具 |
| 叫 Claude Code DM 直接說「你擲出 20，命中」，不真的擲骰 | Day 13 的查帳：查得出票根的編號引擎沒發過 | Claude Code 沒照做，還是把攻擊交給引擎去擲骰 |
| 叫 Claude Code DM 告訴裁判「白狼已經答應投降」，讓裁判不擲骰就把長劍送給我 | Day 18：裁判看不到對話，只看得到 DM 交代的話 | Claude Code 轉告時註明這是玩家的說法；裁判自己查了場景，判定要擲骰 |

五種作弊，Claude Code 都在 `CLAUDE.md` 那一層就自己拒絕了，權限和 Hook 根本沒出場。Day 17 說的兩層防線，測試起來要擋玩家作弊第一層就夠了；第二層的 deny、`guard.py` 和查帳，則是留給 Claude Code DM 自己失手的時候處理。

第二層裡有一道跟其他的不一樣。deny 和 `guard.py` 抓到就直接擋，查帳發現骰子出問題卻只會印一行警告。像是 Day 25 讀二樓信件那一回合，Claude Code DM 自己漏貼了一張票根，查帳抓到了，畫面多了一行 `Stop says: 查帳：本回合擲出的 r-007f5b（值 15）沒有出現在回覆裡`，可是 Claude Code DM 看不到這行字也無法處理。今天把查帳改成擋下來，請 Claude Code DM 補上。

## 查帳改成直接擋下：Stop Hook 的 decision: block

Day 13 的查帳是由 `Stop` 觸發的，抓到票根對不上，就印一行 `systemMessage`；這時 Claude Code DM 已經講完了，警告只是給玩家看的事後通知。要在這一回合結束之前就擋下來，`Stop` Hook 的回應得這樣改：

```json
{
  "decision": "block",
  "reason": "查帳：本回合擲出的 r-007f5b（值 15）沒有出現在回覆裡。請只依引擎回傳的結果改寫這一段，每個骰值附 [R:<roll_id>=<value>]，不要重新執行任何遊戲動作。"
}
```

`Stop` Hook 只要印出這段 JSON，Claude Code 就不會讓這一回合結束，而是把 `reason` 交給 Claude Code DM，讓 Claude Code 再回一次。這跟 Day 17 在 `PreToolUse` 回傳 `permissionDecision: deny` 是同一個想法：Hook 不只能在旁邊看，還能直接說不。

`audit.py` 其實早就會印這段 JSON，只是 `settings.json` 一直用 `--mode warn` 叫它。打開 `.claude\settings.json`，把 `Stop` 裡查帳那一行的 `--mode warn` 改成 `--mode block`：

```json
"command": "uv run --no-project .claude/hooks/audit.py --mode block"
```

Claude Code DM 補上票根再回一次之後，`Stop` 會再觸發一次，查帳也會再查一次。這時有兩件事要處理：

- **重寫要單獨查**：Day 23 說過，`audit.py` 會把這一回合 DM 說過的每一段都拿來查，才不會漏掉寫在工具呼叫之前的票根。可是被擋下來的那一段，也算這一回合說的；要是它把數字寫錯了，DM 重寫得再對，舊的錯誤還在，永遠過不了。所以要看 `stop_hook_active`：Day 13 看過這個欄位，當時一直都是 `false`；它是 `true` 的時候，代表這次的 `Stop` 是 DM 被擋下、重寫之後才觸發的。這時只查重寫的那一段，也就是 `last_assistant_message`。
- **最多擋兩次**：要是 DM 一直寫不對，就會一直擋、一直重寫，變成無限迴圈。`audit.py` 把擋了幾次記在 `.game\audit_cursor.json` 裡，最多擋兩次。第三次還是不對，就改回只警告，多加一句「已更正兩次仍不符，列為未解錯誤」，讓這一回合結束。

第一件事要改 `audit.py`。打開 `.claude\hooks\audit.py`，把 `text = ` 開頭的那一行換成下面三行：

```python
    rewrite = bool(payload.get("stop_hook_active"))  # this Stop follows a block: judge the rewrite alone
    earlier = "" if rewrite else earlier_messages(payload.get("prompt_id"))
    text = (payload.get("last_assistant_message") or "") + "\n" + earlier
```

第二件事 `audit.py` 本來就做好了，不用改。改完之後重開 Claude Code。

Claude Code DM 平常很少漏票根，所以我故意叫 Claude Code 不貼票根試了三次，每次都是擋一次，重寫就把票根補上。下次再漏，這一道防線就會接住。

## 這套防線抓不到的作弊

這套防線抓的，是「證據跟引擎對不上」的事。但還是有兩種作弊無法阻止：

- **沒附票根、這回合也沒擲骰的結果**。Claude Code DM 說「白狼被你的氣勢嚇退了」，沒有擲骰，也沒有票根，查帳就沒有東西可以比對。Day 13 的規則就是這樣：沒票根、這回合也沒骰，就當作正常。
- **劇情寫歪了**。Claude Code DM 把白狼寫成主動投降，可是引擎的狀態沒有變；查帳只看數字，看不出故事已經偏掉了。

這兩種作弊，只能靠 Day 22 的 output style 和 `CLAUDE.md` 的規則管住 Claude Code DM 了。

## 目前還有什麼問題嗎？

能擋的作弊都擋下來了，剩下的要靠 Claude Code DM 守規矩。明天就用正當的方法面對白狼：打倒他、說服他，或是說出他的身分。三種結局，最後再加上一份戰役報告。

今天結束時 `dungeon` 資料夾的完整內容在 [articles/29/dungeon](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/29/dungeon)，給大家參考。

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
- ✅ [Day 27](https://ithelp.ithome.com.tw/articles/10423286)：Hook：`SessionEnd`、`reason`、`FileChanged`、`file_path`、`event`、`SessionStart` 的 `async`
- ✅ [Day 28](https://ithelp.ithome.com.tw/articles/10423591)：設定：`model`、`effortLevel`、`modelSettings`、`maxEffortLevel`；Subagent：`model`、`effort`；headless：`total_cost_usd`、`duration_ms`、`modelUsage`
- ✅ Day 29：Hook：`Stop` 的 `decision: block`、`reason`、`stop_hook_active`；五道防線：allow／deny、guard、查帳、裁判隔離
