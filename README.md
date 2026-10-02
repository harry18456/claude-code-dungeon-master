# 30 天建立 Claude Code 地城領主

2026 iThome 鐵人賽（Claude AI 組）的文章與實作。用 Claude Code 從零做一個 AI 地城領主，一天加一樣東西，邊做邊學。

## 這個系列在做什麼

Claude Code 跟地城領主/地下城主（Dungeon Master）有什麼關係！？
實際上沒什麼關係。

想寫 Claude Code 教學，又不想無趣地一個一個介紹功能，
那就乾脆做成一個小遊戲，邊做、邊玩、邊學吧！

接下來 30 天我會先用 Claude Code 做出一個最陽春的 AI 地城領主，一天加一樣東西——CLAUDE.md、Skill、MCP、Hook——把它慢慢養成一個有模有樣的 DM。

## 進度

| Day | 標題 | 大綱 | 帶得走什麼 | 狀態 |
|---|---|---|---|---|
| 1 | [裝好 Claude Code，來開第一局吧!](articles/01/day01.md) | Claude 與 Claude Code 是什麼、方案與介面、安裝登入、選模型與 effort、空資料夾開一局玩七回合 | 裝得起來、知道模型和 effort 怎麼選以及各花多少錢、看到一個沒有骰子的 DM 怎麼編數字 | 已完成 |
| 2 | [梅拉不見了：對話存在哪裡、怎麼拿回來](articles/02/day02.md) | 重開一局梅拉不見；session 存在 `~/.claude/projects/` 的 `.jsonl`；`--resume`、`-c` 拿回來；換資料夾、換電腦、30 天清理三個常見問題 | 對話是本機檔案，resume 是補救不是設計；世界設定該住在檔案裡 | 已完成 |
| 3 | [把世界寫進 CLAUDE.md，梅拉不用 resume 也在](articles/03/day03.md) | CLAUDE.md 是什麼、Global／Project／Local 三層、把 Day 1 的世界寫進去、開新局直接認得梅拉、`/context` 看它讀了什麼、`@` 引用其他檔案 | 不變的設定住檔案；它是提示不是規則引擎；會變的數字要另找地方 | 已完成 |
| 4 | [讓 Claude Code 紀錄血量與骰骰子吧！](articles/04/day04.md) | 內建工具 Read／Bash／Edit；HP 搬進 `state.json`；骰子改用終端機指令 `$RANDOM`；`Ctrl+O` 看工具細節；auto mode 自動放行 | 會變的數字住檔案，交給 Claude Code 讀寫；每次動手畫面上都看得到；CLAUDE.md 是請它做，不是強制 | 已完成 |
| 5 | [我不依我不依（地上打滾），我要回到上一個動作：/rewind](articles/05/day05.md) | 接回昨天那局打死巨鼠；搜地窖只撿到 1 枚就倒帶重刷；checkpoint 存在哪（`.jsonl` 與 `file-history/`）、對話是一棵樹；`/rewind` 六個選項；`/branch` | 每句話都是存檔點，檔案和對話可以分開倒；bash 和手動改的檔案倒不回來 | 已完成 |
| 6 | [休息一晚回血：把偶爾才用的規則做成 Skill](articles/06/day06.md) | Skill 是什麼、資料夾結構、Agent Skills 標準的六個欄位與 Claude Code 的擴充；寫 `/rest`；打 `/rest` 與說「我想睡一覺」讓 DM 自己叫；`/context` 對 token；skill-creator | 永遠要記得的放 CLAUDE.md，要用再拿出來的做 Skill；description 決定會不會被自動挑中 | 已完成 |
| 7 | [誰允許 DM 動手的？權限模式與 allow／deny](articles/07/day07.md) | 權限模式（Manual／Accept edits／Plan／Auto，加 dontAsk、bypassPermissions）、`Shift+Tab`；把骰子做成 `dice.sh`；Manual 模式看確認框；`/permissions`、allow／ask／deny、`.claude/settings.json`；信任對話框；deny 擋 `Edit(CLAUDE.md)`、allow 只放行 `bash dice.sh`；Auto 模式分類器的審查順序 | 權限規則由 Claude Code 強制執行，不是由模型；deny 永遠贏；allow 只是不問，不是一定做 | 已完成 |
| 8 | [/roll d20+2：讓 Skill 吃參數，骰子在進對話之前就骰好](articles/08/day08.md) | Skill 參數 `$ARGUMENTS`、`argument-hint`；`` !`指令` `` 展開：內容進對話之前先跑完指令；`!` 指令要對上 allow 規則、CLAUDE.md 不能跟 Skill 打架 | 指令展開讓骰子一定發生，不是請 Claude Code 去跑；證據翻 `.jsonl`，`Ctrl+O` 看不到 | 已完成 |
| 9 | [這個 Skill 誰能叫？只有我能作弊！](articles/09/day09.md) | `disable-model-invocation`（只有你能叫）、`user-invocable: false`（只有 Claude Code 能叫）、`allowed-tools`（Skill 自己帶權限）；用 `/context` 看哪些 description 進了對話 | 擋的是「誰啟動這個流程」，不是「這件事做不到」；`allowed-tools` 只管那一輪，deny 永遠贏 | 已完成 |
| 10 | [十天了，先別急著加東西：用 Plan Mode 整理資料夾](articles/10/day10.md) | 前九天回顧；Plan Mode（`Shift+Tab`、`/plan`、`Ctrl+G`）；同一個請求比較 Sonnet 5 和 Opus 5.5 的計畫；改計畫；auto mode 的 `[Self-Modification]` 擋下自我放寬權限；`git init` | 計畫是拿來看的，不是照單全收；實測推翻 `Write(path)` deny 有效這個說法；批准計畫不等於它只做計畫裡的事 | 已完成 |
| 11 | [中秋節，讓 Claude Code 自己叫你：第一個 Hook](articles/11/day11.md) | Hook 跟前十天的差別；三層結構（事件、matcher、handler）與五種 `type`；`play.ps1` 播 Windows 內建音效、`.ps1` 存 UTF-8 with BOM；`Stop` 講完話叮一聲；`/hooks` 看設定與來源；exit code 的意義；骰子聲的兩條路：`UserPromptExpansion` 接玩家、`PostToolUse` 讀 `tool_input.skill` 接 DM | Hook 由 Claude Code 執行，模型管不著；`!` 展開不是工具呼叫，`PostToolUse` 看不到；聲音只代表 Skill 被叫了，不代表骰子成功 | 已完成 |
| 12 | [請個守衛站崗：HP 可以改，但改成 80 不行](articles/12/day12.md) | 還沒守衛時，藥水劇情讓 DM 把 HP 上限改成 80；權限只看改哪個檔、不看改成什麼；`PreToolUse` 收到的 JSON，`Edit` 要先組出改完的樣子；`guard.ps1` 檢查 hp 與 max_hp，exit 2 擋下並把理由交給 DM；deny `Edit(./.claude/**)` 保護守衛；`/hooks` 看 PreToolUse 的 exit code 規則 | 權限管路徑、Hook 管內容；exit 2 的理由模型看得到，其他 exit code 只給你看、不會擋；守衛壞掉等於沒有守衛，寫完要實測；守衛只看 Edit 和 Write | 已完成 |
| 13 | [每顆骰子都有票根：DM 講完話，Hook 對一次帳](articles/13/day13.md) | `!` 展開的骰子 Hook 看不到，紀錄從 `dice.sh` 自己做：每骰一次寫帳本 `.game/rolls.log`、印票根 `[R:編號=結果]`；CLAUDE.md 要求連票根一起貼、最後一行「骰子：」；`Stop` 收到的 `last_assistant_message` 只有最後一段；`audit.ps1` 對帳，用 JSON 輸出 `systemMessage` 只警告不擋；deny `Edit(./.game/**)` 保護帳本；在外面骰一顆讓警告跳出來，DM 說沒看到 | 規則是請求、查帳是確認；`systemMessage` 只給你看，模型不知道；查帳只對數字、不懂劇情，沒骰也沒票根抓不到 | 已完成 |
| 14 | [HP 還剩多少？看畫面最下面：狀態列](articles/14/day14.md) | 狀態列跟 Hook 的差別；新腳本從今天起改用 Python，用 uv 安裝與執行；`statusline.py` 讀 `state.json` 和帳本最後一行，再從 stdin 的 session JSON 拿模型與 context 用量；`settings.json` 加 `statusLine`、`uv run --no-project`；更新時機與 `refreshInterval`；使用者層和專案層只取一個 | 遊戲的數字從檔案讀，不靠 DM 講；狀態列只給你看，不進對話也不花 token，但擋不了任何事；同一時間只有一個狀態列，專案層蓋過使用者層 | 已完成 |
| 15 | [把骰子交給工具：第一個 MCP server](articles/15/day15.md) | MCP 是什麼、跟 Skill 的差別；先接官方的時間 server（`claude mcp add`、三種範圍、`/mcp`）；host／client／server 與 stdio、Streamable HTTP；用官方 Python SDK 2.x 寫最小的骰子 server（`# /// script` 宣告依賴、`MCPServer`、`@mcp.tool()`、`ToolError`）、`.mcp.json`、第一次啟動的核准畫面；CLAUDE.md、`/roll`、`/rest` 改叫 roll 工具，骰子聲改接 `PostToolUse` 的 `mcp__dungeon__roll`，`dice.sh` 退場 | 提供工具的是 server，Claude Code 是 host；工具清單、呼叫、回傳的格式統一，所以誰寫的 server 都能接；`PostToolUse` 只在工具成功時觸發，骰子聲響了就代表真的骰了；錯誤說明寫清楚，DM 才有辦法自己找出路；做成 MCP 主要是為了教學，DM 還是可以不叫工具 | 已完成 |
| 16 | [換上遊戲引擎：一刀下去，命中、扣血、反擊不用 Claude Code DM 算](articles/16/day16.md) | 換上先寫好的遊戲引擎（`engine/`、`data/`、`scenes/`、`gamectl.py`）；同一個 MCP server 開四個工具：`get_state`、`roll`、`resolve_attack`、`rest`，都回傳 JSON（`dice`、`effects`、`resolution_id`、`version`）；數值改照精簡版 D&D 5e；照步驟換上引擎、`state.json` 改用場景代號；CLAUDE.md、`/roll`、`/rest` 改叫引擎，allow 新工具、deny 引擎檔案；`PostToolUse` 讀 `tool_response` 播命中或落空、`async` 放到背景跑；實際砍一刀：一次呼叫算完命中、傷害、兩隻巨鼠的反擊並寫檔；票根改記骰面、帳本換成 `rolls.jsonl`、查帳換成 `audit.py`；戰鬥中休息被引擎拒絕 | 要算數的事交給程式，DM 只照結果說故事；一個 server 可以開多個工具，回傳 JSON 讓 DM 和 Hook 都讀得懂；引擎先寫 `state.json` 再寫紀錄，紀錄壞了結果照樣算數；不確定剛才的動作有沒有成立，先查 `get_state` 再決定要不要重來；`state.json` 還有兩個人在寫，DM 還能用 `Edit` 改錢、位置和旗標 | 已完成 |
| 17 | [收回 Claude Code DM 的鑰匙：偷看不到地圖，也改不了存檔](articles/17/day17.md) | 場景檔分成 `visible`、`judge_only` 兩層，DM 只能用 `get_current_scene` 看到前一半；`move_to` 自己判斷鎖住的出口、埋伏和追擊；deny `Edit(state.json)`、`Read(./scenes/**)`，`Read`、`Grep`、`Glob` 都碰不到，`Glob` 連檔名都找不到；`guard.py` 掛在 `PreToolUse` 擋 Bash、PowerShell，用 JSON 的 `permissionDecision` 回 deny；`/cheat` 改走引擎、正式遊戲停用；`world-lore` 只留公開傳聞；換完要開新對話；買麥酒這種動到錢的事，DM 照實說還記不進帳 | CLAUDE.md 讓 DM 不想改，deny 讓 DM 改不了；deny 只管 Claude Code 的檔案工具，Bash 要靠 Hook 擋；Hook 可以 exit 2 擋，也可以 exit 0 印 JSON 擋，JSON 還能改成 `ask`；`!` 展開失敗時訊息不會送出，DM 根本收不到；檔案改了，舊對話的 context 不會跟著變 | 已完成 |
| 18 | [麥酒記進帳，再請一位裁判：第一個 Subagent](articles/18/day18.md) | 規則書 `rules.md`：九個動詞、DC、優勢和劣勢；引擎開放 `resolve_check`，DM 只選動詞和對象，引擎擲骰、算結果、寫檔；買麥酒記進帳；`roll`、`/roll` 下架，改用只有玩家能叫的 `/check`；Subagent 是什麼、跟 Skill 和 fork 的差別；寫第一個子代理 `rules-judge`（`.claude/agents/`、`name`、`description`、內文就是系統提示，`model`、`effort` 等欄位選填）；DM 說「等裁判」再用 `Agent` 委派，互動模式下裁判在背景跑，`/tasks` 看紀錄、`@agent-名字` 直接指定 | 數字交給引擎，DM 只選規則；裁判看不到前面的劇情，判完只交回結果，也不佔 DM 的 context；沒寫 `tools` 的子代理會繼承全部工具，內文寫「不得擲骰」只是請求；裁判叫得太勤，每回合多等一則訊息 | 已完成 |

大綱採滾動式調整，寫到哪裡更新到哪裡。

## 目錄

| 路徑 | 內容 |
|---|---|
| `articles/NN/dayNN.md` | 每天一篇文章，圖片放同層的 `assets/` |
| `articles/NN/dungeon/` | 那一天結束時 `dungeon` 資料夾的內容，照著做可以對答案 |

## 要跟著做的話

- Claude 訂閱方案 Pro 以上，或有儲值的 [Claude Console](https://platform.claude.com/) 帳號。免費方案不能用 Claude Code。
- 一個編輯器。我用 VS Code 加它內建的終端機，作業系統是 Windows。其他組合也可以，指令要自己換。
- 安裝步驟在 [Day 1](articles/01/day01.md)。

## 用語

讀者看得到的文字一律用「地城領主」，這是台灣桌遊出版社的譯法。送進模型的 prompt、腳本與保存下來的原始輸出保留當時的寫法，不回頭改，才能跟畫面對得上。

## 報名資訊

| 欄位 | 內容 |
|---|---|
| 參賽主題 | Claude AI |
| 參賽題目 | 30 天建立 Claude Code 地城領主 |

主題與題目報名後不可修改，文章標題與系列名以此為準。
