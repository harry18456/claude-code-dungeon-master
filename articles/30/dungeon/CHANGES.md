# 變更說明

照著文章做到某一天的人，翻這裡看那一天的資料夾跟前一天差在哪。只列「不教、但你要改」的東西；文章教的內容不重複。

## Day 16：引擎接手骰子、戰鬥、休息

- 新增 `engine/`（MCP server 與規則引擎）、`gamectl.py`、`data/`、`scenes/`。引擎程式碼完整提供，文章只講當天用到的工具。引擎的 server 跟 Day 15 的骰子 server 一樣用官方的 MCP Python SDK 2.x，走 `2026-07-28` 版協定；檔案開頭宣告 `mcp>=2,<3`，uv 會自動安裝。規則引擎 `core.py` 和 `gamectl.py` 只用標準函式庫。換上前先跑一次 `uv sync --script engine/server.py` 暖機，Claude Code 第一次啟動 server 時才不會等到逾時。
- `.mcp.json` 的 `dungeon` 從 Day 15 的 `uv run --script .claude/mcp/dice.py` 改成引擎：`uv run --no-project engine/server.py`。`.claude/mcp/dice.py` 刪掉。工具名 `mcp__dungeon__roll` 不變，參數也一樣是 `dice`（例如 `d20+2`），Day 15 接在它上面的 hook 照樣觸發。新增 `get_state`、`resolve_attack`。
- 票根與帳本換成引擎的格式：id 從 8 位 hex 變成 `r-` 加 6 位 hex，數字從總和改成骰面（例如 `[R:r-c632a9=18]`），帳本從 `.game/rolls.log` 換成 `.game/rolls.jsonl`（一行一顆骰子的 JSON）。改記骰面，是因為修正值改由引擎加：headless 實跑時 DM 把總和寫進票根，查帳全部對不上。
- 工具回傳改成 JSON，每一個都帶 `dice` 欄位：一行是一次擲骰或出手，後面接票根。CLAUDE.md 的票根規則改成「回覆最後寫一行『骰子：』，下一行起原樣貼上 `dice`」。`/roll` 的 SKILL.md 只改一句：把回傳的 `dice` 那一行原樣報給玩家。
- 規則數值改由引擎決定（D&D 精簡版）：CLAUDE.md 手寫的「短劍攻擊 +2、傷害 d6+1、防禦 12」和巨鼠的數值拿掉，改成以 `get_state` 回傳的 `hero` 為準（短劍攻擊 +4、傷害 d6+2、AC 13）。地窖裡是兩隻巨鼠，代號 `giant_rat`、`giant_rat_2`。
- `state.json` 新增欄位：`enemies`（敵人剩餘 HP，取代 Day 10 放在 `flags` 的 `giant_rat_hp`）、`equipment`、`arrows`、`turn`、`version`、`last_result`、`recent_results`。原有的 `hp`、`max_hp`、`copper`、`location`、`inventory`、`flags` 名稱不變。舊存檔缺這些欄位也讀得了，引擎會補預設值。
- `location` 改存場景代號：`醉月酒館` → `tavern`、`舊地窖` → `cellar`、`二樓` → `upstairs`。引擎要靠代號對照 `scenes/`。
- HP 和敵人的血量改由引擎管，DM 不能再改 `hp`。錢、位置、物品、flags 這天還是 DM 改，Day 17 才收走。CLAUDE.md 同一條補一句：引擎回傳 `effects` 裡列的變化（例如撿到的東西）已經寫好了，不用再改。實跑時巨鼠掉信，DM 想自己再改一次 inventory。
- `/rest` 改叫引擎的 `rest` 工具（Day 15 是請 DM 叫 `roll` 骰 d4 再自己改 HP）：擲生命骰加體質、補 HP、寫檔一次做完，戰鬥中回錯誤。SKILL.md 拿掉 `!` 和 `allowed-tools`，步驟改成：先呼叫 `get_state` 確認艾玲在哪裡，再呼叫 `rest`，描述，最後在「骰子：」底下貼回傳的 `dice`。第一步是實跑補的：新 session 直接打 `/rest`，DM 沒查狀態就把酒館描述成地窖。原本是 `!` 展開 `uv run --no-project gamectl.py rest`；2026-09-29 對照實測，玩家用說的（「想再休息一下」）時 DM 可以連 Skill 都不叫，`!` 根本不會展開，休息就沒經過引擎；改成工具後 DM 會呼叫 `rest`，滿血也記一筆。`gamectl.py rest` 留給終端機用。
- `settings.json` 的 allow 加上 `mcp__dungeon__get_state`、`mcp__dungeon__resolve_attack`、`mcp__dungeon__rest`（`Bash(bash dice.sh *)` 在 Day 15 就拿掉了）。
- `settings.json` 的 deny 加上 `Edit(./engine/**)`、`Edit(./data/**)`、`Edit(./scenes/**)`、`Edit(./gamectl.py)`：Day 15 的 `dice.py` 在 `.claude/` 底下，受 Day 12 的 deny 保護；引擎搬到根目錄，要另外保護，DM 才改不了骰子怎麼骰。
- 音效與查帳換成 Python，這天 matcher 本來就要改。`play.ps1` 換成 `.claude/hooks/sound.py`（`skill-sound.ps1` 在 Day 15 已經刪了）。PostToolUse 的 matcher 從 `mcp__dungeon__roll` 擴成 `mcp__dungeon__roll|mcp__dungeon__resolve_attack|mcp__dungeon__rest`，腳本讀 `tool_response` 決定播骰子聲、命中或落空、休息的營火，並加上 `async: true`，一回合好幾次出手時不擋 DM。骰子聲從 Windows 的 ding 換成 `.claude/hooks/sounds/` 的 CC0 音效（來源見同目錄的 `CREDITS.md`）；Stop 的提示音照舊是 Windows 的 chimes（`sound.py chimes`）。Stop 的查帳從 `audit.ps1` 換成 `.claude/hooks/audit.py`，改讀引擎的帳本。
- Day 12 的 `guard.ps1` 這天不動，Day 17 才退役。`/cheat` 也不動，還是直接改 `state.json` 的 hp：它只有玩家能叫，本來就是繞過規則的作弊碼，Day 17 改走引擎。
- 狀態列換成引擎版：Day 14 的 `statusline.py` 讀 `.game/rolls.log` 的最後一行，帳本換成 `rolls.jsonl` 之後會壞。新版直接向引擎要 HP、AC、位置和目標。模型名稱和 context 用量不再顯示。
- 要從 Day 15 的存檔接著玩：`location` 改成代號、刪掉 `flags.giant_rat_hp`、`inventory` 裡的「短劍」拿掉（短劍改由 `equipment` 管）。或直接 `uv run --no-project gamectl.py newgame` 重開。
- Python 從 Day 14 起由 uv 提供，這天不用另外裝。

## Day 17：引擎接管世界

- `settings.json` 的 deny 加上 `Edit(state.json)` 與 `Read(./scenes/**)`。其他幾條早就加了：`Edit(./.claude/**)` 在 Day 12、`Edit(./.game/**)` 在 Day 13，`Edit(./engine/**)`、`Edit(./data/**)`、`Edit(./scenes/**)`、`Edit(./gamectl.py)` 在 Day 16。從今天起 DM 改不了狀態、讀不到場景資料。
- 新工具 `get_current_scene`、`move_to`，`roll` 和 `resolve_attack` 照留。`location` 只會因為 `move_to` 改變：引擎檢查出口是否相鄰、是否解鎖，走進地窖時巨鼠伏擊，戰鬥中離開會被每隻敵人追擊一次。PostToolUse 的 matcher 加上 `mcp__dungeon__move_to`，移動有開門聲，伏擊或追擊再接骰子聲。
- `.claude/hooks/guard.py`（PreToolUse，matcher `Bash|PowerShell`）擋 shell 路徑寫入這些檔案，也擋用 `cat`、`python -c` 讀 `scenes/`。uv 算直譯器：`uv run python -c`、`echo … | uv run -` 和 heredoc 一樣擋。
- `/cheat` 改成 `!` 展開 `uv run --no-project gamectl.py cheat`。正式遊戲預設停用：要建 `.game/dev` 檔案或設 `DUNGEON_DEV=1` 才會生效。
- `world-lore` 只留公開索引。Day 9 寫進去的內幕搬到 `scenes/*.json` 的 `judge_only`，DM 讀不到，玩家要靠場景互動發現。改完要開新對話：舊對話的 context 還留著 Day 9 的內幕。
- Day 12 的 `guard.ps1`（PreToolUse，matcher `Edit|Write`）退役：DM 已經改不了 `state.json`，那支檢查 HP 範圍的守衛沒有東西可檢查了。擋 shell 的工作交給上面的 `guard.py`。
- 非戰鬥檢定的後果（撿到錢、拿到東西、旗標）引擎還沒接手，Day 18–19 才接上。這兩天之間 DM 骰完只能敘述。CLAUDE.md 多一條：買賣、接委託、領報酬、塞錢這類事，照實跟玩家說這筆帳還記不進去。沒有這條時，headless 實跑的 DM 把麥酒端上桌、銅幣沒扣，還自己編了個「要等你接委託才結帳」的理由。
- 這天能玩的範圍：酒館與地窖之間移動、打巨鼠、休息。二樓只能打趴守衛硬上（梅拉會翻臉），舊路要等 Day 18 說服披斗篷的人或女孩之後才開。

## Day 18：resolve_check 與第一個子代理

- 新增 `rules.md`：公開的規則書，九個動詞、DC、優勢劣勢、戰鬥。DM 和裁判照這份選動詞。
- 新工具 `resolve_check(rule_id, target_id)`：引擎檢查前置條件、決定 DC、擲骰、套用既定後果。DM 與裁判都不決定 DC，也不能指定傷害、扣款或旗標。買東西、接委託、領報酬、塞錢都是對物件 `interact`，Day 17「帳記不進去」那條 CLAUDE.md 規則拿掉。
- 同一組（規則, 目標）失敗後，引擎會擋掉直接重試；移動、休息或倒地後才清除。
- `roll` 工具與 `/roll` 下架：每顆骰子都在某個結算裡。玩家要自己點名檢定改用 `/check 動詞 對象`（只有玩家能叫）。
- 新增 `.claude/agents/rules-judge.md`。這天還沒寫 `tools`，裁判會繼承 DM 能用的全部工具；CLAUDE.md 的「裁決」一節要 DM 把創意方法一律交給裁判。
- `.claude/agents/` 是新資料夾，要重開 Claude Code 才會載入裁判。
- `settings.json`：allow 加 `mcp__dungeon__resolve_check`、拿掉 `roll`；deny 加 `Edit(rules.md)`；PostToolUse 的 matcher 把 `roll` 換成 `resolve_check`。
- CLAUDE.md 的「骰子：」與選項規則移到最後一節「敘述」：放在「裁決」前面時，實測 DM 有兩回合漏貼「骰子：」。選項也改成不寫代號。
- DC 與後果寫在 `scenes/*.json` 的 `judge_only.features`，`data/rules.json` 只有預設值。想改難度就改場景檔，不用動程式。

## Day 19：給裁判上鎖

- `rules-judge.md` 加 `tools: Read, mcp__dungeon__get_current_scene`：Day 18 的裁判手上有 `resolve_check`、`move_to`、Bash、Edit 等 23 個工具，內文的「不得擲骰」只是請求。
- 同一個檔加 `omitClaudeMd: true`：子代理預設會載入每一層 CLAUDE.md，包括寫給 DM 的那份和使用者自己的。裁判需要的都在自己的內文、`rules.md`、`get_current_scene` 和 DM 交代的任務裡。兩項加起來，裁判每次開工的 context 從約 22,500 token 降到約 3,200。要 Claude Code v2.1.271 以後。
- `settings.json` 加 `env`：`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`。互動模式預設讓子代理在背景跑，DM 會先回一則「等裁判」，裁決回來再回一則；設了之後裁判改在前景跑，DM 等它判完一次講完。代價是這個專案的背景工作全部關掉（`run_in_background`、自動轉背景、`Ctrl+B`）。
- CLAUDE.md 的「裁決」改成明顯的自己判，只有拿不準的創意行動才委派：Day 18 連「請人喝酒」都送裁判，每送一次多一次模型呼叫、多等十幾秒。
- settings.json 的 deny 和 `guard.py` 對子代理一樣有效：裁判用 Read 或 Bash 讀 `scenes/` 都會被擋。

## Day 20：筆記不是存檔

- CLAUDE.md 的「狀態與世界由引擎持有」多一條：auto memory 只記玩家的偏好和玩法；HP、錢、位置、物品、旗標、劇情進度不寫進筆記，玩家要求也不寫；筆記和 `get_state` 對不上時以引擎為準，並告訴玩家哪一條筆記過期了。
- 沒有這條時，玩家明講「把 HP、銅幣寫進筆記」，各試三次：Opus 5.5 都不寫，Sonnet 5.5 有兩次寫了，Haiku 4.5 三次都寫了，其中一次把 HP 上限寫成 25。加了之後三種模型都是三次不寫（Claude Code 2.1.289）。
- 筆記存在使用者資料夾的 `.claude/projects/<專案>/memory/`，不跟著這個資料夾走。下載這份遊戲的人拿不到別人的筆記，所以遊戲要用到的東西都放在 CLAUDE.md 和引擎裡。
- DM 用 shell 刪筆記檔會被 `guard.py` 擋下，因為筆記的路徑裡也有 `.claude/`。DM 只改得了索引 `MEMORY.md`；要刪乾淨，請用 `/memory` 打開筆記資料夾自己刪。
- 這天沒有改程式，也沒有改 `settings.json`。
- 跟每日文章對齊（2026-10-05）：最終版的 CLAUDE.md 補回 Day 17、18 文章實測後加的三句：`move_to` 會結算「走進去時的伏擊」；`effects` 列的變化引擎已經寫好，沒列的就是沒變；選項「用玩家看得懂的話寫，不要寫代號」（實測時 DM 寫出 `marlda_quest` 這種代號）。

## Day 21：存讀檔

- 狀態列在 session 還沒開口時，最前面加「▶ 打「開始」開新局」或「▶ 打「繼續」接上次」，跟 `SessionStart` 的 `recap.py`（前情提要）同一天上。Day 16～20 的狀態列沒有這個提示：那時還沒有前情提要，從舊存檔遷移過來的 `turn` 是 0，會誤顯示「開新局」。
- 新 Skill `/save [名稱]`、`/load [名稱]`（只有玩家能叫）、`/recap`。存檔在 `.game/saves/<名稱>.json`，預設 `quick`。
- Day 5 的 `/rewind` 只還原 Claude Code 自己用 Edit 改的檔案。Day 17 起 DM 改不了 `state.json`，只剩引擎在寫，`/rewind` 就倒不回去了（Day 16 時 DM 還會用 Edit 改它，倒得回 `state.json`，倒不回 `.game/`）。要回到過去用 `/load`；對話用 `/rewind` 的 Restore conversation 一起倒回去。
- 讀檔會把 `version` 往前推而不是倒回去，所以查帳 hook 不會把存檔前的骰子當成這回合的。
- Skill 裡的指令寫成 `uv run --no-project gamectl.py save quick $ARGUMENTS`：沒帶參數時存 `quick`，帶了就用最後一個字。這樣 Skill 的 `allowed-tools: Bash(uv run --no-project gamectl.py save *)` 兩種情況都對得上。settings.json 不另外放行 `gamectl.py save`、`load`、`log`：Skill 自己帶權限就夠了，多放行只會讓 DM 用 Bash 讀檔、蓋存檔不用審。CLAUDE.md 另有一條「存讀檔只由玩家觸發」。

## Day 22：DM 的腔調

- 新增 `.claude/output-styles/dm-voice.md`，`settings.json` 用 `outputStyle` 指定它。只改主線 DM 的說話方式；rules-judge 子代理不受影響。
- dm-voice 多一條：HP、銅幣有變動才提，融進敘事；沒變動就不提，也不另外寫一句報帳。實拍時 DM 在故事後面加了「你的 HP 還是 7/12，銅幣還是 123」；加了這條之後，固定骰值跑三次都沒再出現。
- `/output-style 名稱` 和 `/config` 的選單都把選擇寫進 `.claude/settings.local.json`，比專案的 `settings.json` 優先。想讓所有人都用 dm-voice，要寫在 `settings.json`。
- 快照用 `tools/trim_world.py --level 1c`：女孩會說出枕頭下的信、請你念給她聽，但搜那封信要一個沒有東西會設的旗標 `letter_ready`，引擎回她的話「現在還不行」。信的內容和鎮長的信照樣剪掉，Day 25 才給。

## Day 23：headless 與戰役報告

- 新 Skill `/report`（只有玩家能叫）：把 `uv run --no-project gamectl.py report` 吐出的機械紀錄潤成冒險日誌。同一個指令也用 `tools/build_report.py` 把戰報寫成 `.game/report.html`，DM 讀完整份檔案後用 Artifact 工具發布，連結放在日誌最後。發布前 Claude Code 會問玩家；沒有 Artifact 工具或玩家不同意時，只告訴玩家本機檔案在哪。
- `tools/run_turns.sh <inputs.txt> [outdir]`：把一個輸入檔逐行用 `claude -p` 跑完，同一個 session 接續，在隔離的暫存副本裡執行，最後把 `state.json`、`.game/`、每回合的輸出與報告放進 `reports/<時間>/`。
- `tools/build_report.py <game_dir> [--turns <dir>] [-o report.html]`：從檔案產生戰役報告。有逐回合輸出時，會把敘述裡的票根跟帳本對照，標出相符、不符、沒被敘述的骰子。報告裡沒有任何數字來自模型。
- 發布成 claude.ai Artifact：在 Claude Code 裡說「把 reports/<時間>/report.html 發布成 Artifact」，或在遊戲裡打 `/report`。帳號不支援就只留本機 HTML。戰報頁面照 Artifact 的頁面規格寫：不自帶 `<html>`、`<head>`、`<body>`（發布時平台會包上），但保留 `<meta charset>` 讓本機也打得開；顏色是 `:root` 的變數，有深色模式；表格在自己的容器裡橫向捲動，手機上頁面本身不會左右滑。
- 新 hook `.claude/hooks/story.py`：把玩家說的話和 DM 說的故事記進 `.game/story.jsonl`，戰報才有故事可寫。它只用 Claude Code 交給 hook 的欄位：UserPromptSubmit 和 UserPromptExpansion 的 `prompt`、MessageDisplay 的 `delta`、Stop 的 `last_assistant_message`，再用每個 hook 都有的 `prompt_id` 串成同一回合。它不讀對話紀錄檔：官方文件寫明那個檔是非同步寫入，Stop 的時候可能還沒寫完。MessageDisplay 設成 `async: true`，畫面上的字不用等它；`claude -p` 結束時會砍掉還沒跑完的背景 hook，最後一段由 Stop 補上。玩家那一行和 Stop 都記下當時有幾筆引擎事件，戰報靠這個把每一回合對到自己那段帳本。`/newgame` 會清掉這個檔。
- 戰報改成戰役紀事：角色卡；旅程（玩家的話、DM 的故事、骰子框、引擎事實的小標籤、發現的線索）；戰績與 HP 曲線；發現（線索、背包物品和它們的文字、人物關係）；結局。事件紀錄和骰子帳本收進可以摺起來的附錄。故事照原文引用，票根照樣對帳，數字只來自引擎。
- 查帳也讀 `story.jsonl` 裡同一回合較早的 DM 訊息：`last_assistant_message` 只有最後一則，寫在工具呼叫之前的票根以前會被當成漏貼。
- 要跑 `run_turns.sh` 需要 Git Bash（Windows）或任何 bash，以及已登入的 Claude Code。它會花模型額度。
- runner 開第一回合前，先把 MCP server 啟動一次再關掉。暫存副本是新的資料夾，uv 要重建環境、Python 要編譯 SDK，第一次啟動比較慢，第一回合可能超過 Claude Code 30 秒的連線時限（2026-10-07 實拍遇過：第一回合連不上引擎，後面五句台詞全部對不上）。
- 跑的時候會印 `Ignoring 14 permissions.allow entries … this workspace has not been trusted`：暫存副本沒被信任，專案的 allow 規則被忽略，所以 runner 用 `--allowedTools` 直接給。這是正常的。hooks 與 MCP server 照常運作（查帳 hook 的 `audit_cursor.json` 會出現在結果裡）。

## Day 24：打包成 plugin

- `audit.py`、`recap.py`、`story.py` 先找往上兩層的 `gamectl.py`；找不到的話（裝成 plugin 時，腳本放在 plugin 的資料夾裡），改用 Claude Code 交給 Hook 的 `CLAUDE_PROJECT_DIR`。`recap.py` 另外改跑 plugin 根目錄的 `gamectl.py`。放在專案裡時行為不變。
- 引擎放在 plugin 裡時（根目錄有 `.claude-plugin/plugin.json`），`state.json` 和 `.game/` 改寫到專案資料夾：先看 `CLAUDE_PROJECT_DIR`，沒有就用工作目錄。2026-10-08 實測：Skill 的 `!` 指令在專案資料夾執行，沒有 `CLAUDE_PROJECT_DIR`；MCP server 和 Hook 兩個都有。MCP server 啟動時把自己的路徑寫進 `.game/engine_root.txt`，冒險資料夾的狀態列照著它找到引擎（只寫在有 `.claude/statusline.py` 的資料夾，plugin 裝成 user 範圍時，其他專案不會多出檔案）；還沒寫之前，狀態列印「等 dungeon 引擎啟動」。`gamectl.py` 的音效改找 plugin 根目錄的 `hooks/sound.py`。放在專案裡時行為不變（`tests/test_plugin_mode.py`）。
- plugin 不放進最終版。Day 24 的候選版用 `tools/make_plugin.py` 組出 `plugins/dm/` 和 marketplace，發布在投稿 repo 的根目錄：marketplace 叫 `dungeon-master`，安裝代號 `dm@dungeon-master`。能放的都放進 plugin：dm-voice、rules-judge、所有 Skill（save、load、recap、check、rest、cheat、world-lore，加上產生的 rules）、五支 Hook 和音效、引擎和 MCP server（plugin 自己的 `.mcp.json`）、場景、資料、規則書、`gamectl.py`。最終版還是專案資料夾，不用裝 plugin。
- plugin 帶不走的只剩：permissions 的 allow／deny、CLAUDE.md、狀態列、env、存檔。plugin 的 `settings.json` 只認 `agent` 和 `subagentStatusLine`。裝成 plugin 之後名稱多一個前綴：`/dm:save`、`dm:rules-judge`、`dm:dm-voice`，MCP 工具變成 `mcp__plugin_dm_dungeon__<工具>`；`make_plugin.py` 會改寫 plugin 裡的 Skill、裁判和 `hooks.json`，以及冒險資料夾的 allow。讀專案外的檔案要經過同意，所以規則書全文接在裁判的說明後面，也做成 `dm:rules` Skill 給 DM。冒險資料夾的 deny 改成 `Edit(~/.claude/plugins/**)` 和 `Read(~/.claude/plugins/**/scenes/**)`。

## Day 25：完整冒險

- 五個場景：醉月酒館 → 舊地窖（巨鼠、雜物堆）、二樓（逃難的女孩、鎮長的信）、北邊舊路（白狼的手下、商隊殘骸）、白狼的營地（結局）。
- 任務線：接梅拉的委託 → 清掉地窖的巨鼠 → 領 50 銅幣。守衛讓路（說服、潛行或推酒桶）→ 二樓的女孩說出商隊走的路 → 她枕頭下的信揭露白狼的身分。角落的披斗篷人（請他喝一杯）是另一條知道舊路的方法。
- 兩種結局：打倒白狼（`ending_fight`），或拿著證據說服他（`ending_peace`）。信把說服的 DC 從 18 降到 12，商隊清單降到 15。
- 倒地：HP 歸零醒來在酒館，扣 10 銅幣（不為負），HP 補滿，敵人受的傷保留；每次倒地只結算一次。離開有敵人的場景會被追擊一次；進地窖時活著的巨鼠會先咬一口。
- 新 Skill `/newgame`（只有玩家能叫）：先把目前進度存到 `before-newgame`，再重開。
- 2026-10-08 d25-candidate：從 d24 加上冒險手冊（`.claude/skills/book/` 的 mod 和測試、引擎的 `visited`、`op_book`、`scene_title`、`gamectl.py book`、場景檔的 `map` 和線索的 `journal`、`tools/book_fixtures.py`）、`.claude/settings.json` 的 `"tui": "fullscreen"`、CLAUDE.md 的「選項用「- 」條列，不要編號」，和 `/newgame`（快照版不提那本薄薄的書）。`gamectl.py` 只套手冊的部分，沒帶 Day 30 的 HTML 戰報。
- `tools/trim_world.py` 加 `--level 1d`：二樓不剪，枕頭下的信搜得到（`鎮長的信`、`clue_letter`、`knows_son`），`rules.md` 留「拿到信」；檢查在有 `mayor_letter` 時放行信上的字（鎮長、回家吧）。
- 2026-10-09：`tools/trim_world.py` 加上音效和指令的清理（`--tooling` 只做這部分，也能用在 dm plugin）。Day 27 前拿掉文章還沒教的音效：`open`、`close`、`stop` 從沒播過，倒下聲（`player_down`）和查帳的 `buzz` 有在播但沒解釋；連同 `manifest.json`、`CREDITS.md` 那幾筆。Day 30 前拿掉 `gamectl.py` 的 `report`（Day 30 才教）和 `equip`（系列沒排）。也改掉提到後面幾天的註解（`audit.py` 的 Day 29、`story.py` 的 `/report`、手冊 mod 的 `/equip`）。已套用到投稿 repo 的 Day 16～24 快照、dm plugin（升 1.0.1）和 live 地城。
- 2026-10-09：`tools/trim_world.py` 加 `--level 2a`（Day 26，第二幕開場）：舊路、殘骸（清單、短弓、箭）、守岔路口的手下都在，手下可打可談可繞可塞錢；往林子的小徑用沒人會設的 `chapter3_open` 鎖住（提示「就算過了他，林子裡的路也還沒摸清楚」）；剪掉營地、白狼、手下的字條（`look` 不提字條、`loot` 拿掉）、他掉的彎刀、長劍、墜子、薄書、結局；規則書保留短弓和清單那幾句。檢查放行「短弓」「商隊清單」「商隊貨車」「bandit」，手下的 `guards` 指到被鎖住的出口不算錯。
- 2026-10-09：`tools/trim_world.py` 加 `--level 2b`（Day 27）：同 2a，但手下帶著白狼的命令字條（`look`、`loot` 照原樣）、倒下掉彎刀，規則書留彎刀那幾句；`SOUNDS_DAY = 27` 所以十個音效都回來。林子小徑照樣用 `chapter3_open` 鎖住，營地是 Day 28。檢查放行「彎刀」。
- 2026-10-09：`tools/trim_world.py` 加 `--level 3a`（Day 28～29，第三幕開場）：營地、白狼（可打、可說服、可偷）、墜子（偷到設 `knows_son`）、長劍都在；不給結局：白狼的 `on_convinced` 改成只設 `wolf_listened`、`on_down` 改成設 `wolf_down`＋錢＋長劍，營地的三條結局線索和 `epilogue` 整段刪掉，quest 的三條結局和薄書照舊剪。檢查放行 `white_wolf`、`白狼的長劍`。
- 2026-10-09：新工具 `tools/turn_costs.py`（Day 28）：讀 `run_turns.sh` 的輸出資料夾，列每回合的模型、費用（`total_cost_usd` 是累計，取差）、秒數、token、步數，多個資料夾並排比總和。`tools/skill_rate.py`（Day 26）：句子集每句跑一回合數次，算 DM 叫 Skill 的比例。
- 2026-10-09：信多一條路（使用者實玩卡關：搜信失敗後鎖住，「請女孩拿」對不到動詞）。`upstairs.json` 的 letter 加 `interact` 規則：`requires girl_trusts`、不擲骰、效果同搜成功、`forbids clue_letter`。裁判不用改，它本來就只對動詞。`CLAUDE.md` 裁決第 3 條補：一個方法被擋就看物件還列了哪些規則，剛失敗的那組休息或換場景能再試。`trim_world.py` 的 1c 連同鎖住這條（`LETTER_ASK`／`LETTER_ASK_LOCKED`），1a／1b 整塊刪掉照舊。實測：DM 看到兩條規則會直接選不擲骰的 `interact`，搜枕頭的 DC 12 變擺設，接受（信是劇情必經）。只進最終版，候選版不回頭改。
- 2026-10-09：手冊 mod 五樣（使用者：「AI 給的選項不能選，還要自己打字」）。(1) DM 回覆結尾「你要做什麼？」後面的「- 」選項變成輸入框上方的按鈕，快捷鍵 a～d（數字留給出口），按下 `$.prompt.fill` 填進輸入框；DM 還在講時不顯示，新回合清掉。(2) `/book send` 切換：開著時按選項直接 `$.prompt.submit({ asUser: true })` 送出，存在 `$.store`，跨 session 有效。(3) 查帳搬進 mod：`tool.call` 記下引擎發的票根，`turn.complete` 拿 DM 回覆比對，沒發過的、發了沒貼的，回覆一結束就紅字列在輸入框上方（Day 13 的 Stop Hook 查帳照舊，兩邊獨立）。(4) 玩家的話像行動（有「我／去／打／搜……」又不是問句）而這回合 DM 沒呼叫任何引擎工具，黃字提示「這回合 DM 沒問引擎，世界沒有變」。(5) `TurnDuration` 那一行換成「✻ 字 · N 秒 · 擲了 N 次骰 · 問了引擎 N 次」，沒擲骰也沒問引擎就照原樣。選項文字先濾掉控制字元和零寬字元才進輸入框。mod 測試 21 個。
- 2026-10-09：手冊 mod 也能住在 dm plugin 裡：`tool.call` 的條件改成 `/^mcp__(plugin_dm_)?dungeon__/`；啟動 `gamectl.py book` 時，工作目錄沒有 `gamectl.py` 就用 `$.plugin.root/gamectl.py`（plugin 裡它在根目錄；引擎在 plugin 模式下照舊把存檔寫進專案）。README 的已知限制補：兩道查帳、選項按鈕、同一組失敗的鎖與信的兩條路。
- 2026-10-09：`bgm.py` 住在 plugin 裡時（`hooks/` 旁邊有 `.claude-plugin/plugin.json`），`state.json` 和 `.game/` 改到 `CLAUDE_PROJECT_DIR` 或工作目錄（跟引擎同一條規則）；曲子照舊在腳本旁的 `bgm/`，`--root` 底下有 `bgm/` 時優先用它（測試用）。
- 2026-10-09：結局謝幕。`turn.complete` 看到手冊從沒結束變成結束（`over`），自動開一次手冊窗格、切到線索頁；之後不再自動開。hook 開的窗格必須拿焦點（`focus: false` 會被主機拒絕，整個 hook 被跳過），Esc 關掉就把鍵盤還給輸入框。線索頁本來就會捲（窗格的 body 是引擎管的捲動視窗），不用另外做。
- 內幕都在 `scenes/*.json` 的 `judge_only`，玩家與 DM 都只能靠互動解鎖。想改劇情或難度就改場景檔；`tests/test_content.py` 會檢查旗標、出口與規則有沒有對上。

## 自由度調整（第一次互動實玩之後）

- 實玩發現「揍梅拉」「偷守衛的錢」都被判成規則未涵蓋，什麼都沒發生。改成儘量放行、只擋三種事：不可能的（飛、變出錢）、越線的（折磨、傷害小孩、性暴力）、引擎拒絕的（鎖著、不在、做過）。
- 規則改成 9 條：拿掉沒用到的 `climb`、`force`，加 `steal`（偷竊，隱匿 DC）、`provoke`（動粗，不擲骰直接承受後果）、`improvise`（自由行動）。
- `improvise` 對固定目標 `here`，每個場景都有：只擲骰決定演得好不好，不改變任何狀態，可以重複。給「跳上桌子唱歌」這種事一顆骰子，又不讓模型發明後果。
- 新的壞事與後果：偷守衛（失敗罰 2 銅、守衛警戒）、偷披斗篷的人（成功拿到路線紙條、失敗他閉嘴）、塞 5 銅幣給守衛直接讓路、對梅拉動粗（扣血、扣錢、被丟進地窖，巨鼠在等）、對守衛動粗（被揍）、挑釁手下或白狼（先挨一下）。
- 引擎新增 `move` 後果（世界把你帶走，會觸發新場景的埋伏）。
- 子代理在這版 Claude Code 預設背景執行，委派裁判會變成兩則訊息。當時 CLAUDE.md 改成明顯的自己判、只有拿不準的創意行動才委派，收到回報只回一行中文。後來 Day 19 用 `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` 改成前景執行，「只回一行」那條就拿掉了。

## 系統化：合理就擲骰（第二次互動實玩之後）

- 白名單制拿掉。世界裡每個人都是 `data/actors.json` 的 actor，有防禦、HP、攻擊、錢包、態度；`npcs.json` 與 `enemies.json` 合併刪除。場景檔的 `npcs`／`enemies` 改成一個 `actors` 清單。
- 每個動詞對每個人預設可用：說服、偷、動粗、攻擊；守著路的人（`guards`）再加潛行、聲東擊西。`protected` 的人（女孩）只能說服，其他一律拒絕。
- DC 由引擎算：基準（說服 15、偷 15、潛行 13、聲東擊西 12）＋態度（友善 −3、中立 0、戒心或敵意 +3）＋警戒 +3 ＋籌碼（actor 的 `leverage`，例如信 −6）。上下限 8 到 20。回傳有 `dc`。
- 後果固定調色盤：`convinced:`、`passed:`、`alert:`、`hostile:`、`down:`、`stole:`、`bribed:` 七種前綴旗標，加上打人（`strike`，先骰命中對你的防禦 12）、罰錢（`fines`）、錢包骰（`wallet`）、身上的東西（`loot`）。actor 可以用 `on_convinced`、`on_down`、`on_provoke`、`on_attacked`、`on_stolen`、`on_persuade_fail` 加故事後果。
- 出口用 `guarded_by` 指向守路的人：他被說服、繞過、收錢或打趴，路就開。舊的 `guard_passed`、`road_passed` 旗標不再存在。
- 動粗改成對方先骰命中，不再必中。可以打普通人：打趴不打死，但他從此敵意；打趴守衛梅拉會翻臉，委託、報酬、買酒都沒了。
- 埋伏改成 actor 屬性（`ambush: true`，目前只有巨鼠）。
- `beast: true` 的動物只能攻擊或挑釁；`steal` 只出現在有 `wallet` 或 `loot` 的人身上。手下和白狼有錢包，偷得到。
- 新 Skill `/check 動詞 對象`：玩家自己點名檢定，直接走 `resolve_check`。
- **拿掉 `/roll` 與 `roll` 工具**：每顆骰子都在結算裡（檢定、攻擊、休息），裸骰沒有後果只會誤導。`roll` 工具的程式碼還留在引擎裡給 Day 15～17 用（`dice` 參數跟 Day 15 的骰子 server 一樣），最終版的 `EXPOSED` 不列它。
- **拿掉 `/cheat` 與 `world-lore`**：前者正式版本來就停用，留著只會回錯誤；後者的內容跟 CLAUDE.md 的公開世界重複。兩個都是 Day 9 的教學物件，留在 `master`。`gamectl.py cheat` 指令留給開發用。
- 最終版的 Skill：`/rest`、`/save`、`/load`、`/newgame`、`/recap`、`/report`、`/check`、`/bgm`。
- **主線目標**：`data/quest.json` 是一串依旗標判斷的規則，`engine.core.objective()` 回目前該做什麼。狀態列尾巴多「目標：…」，`get_state` 多 `objective`，`gamectl status` 也印。玩家沒事做時 DM 往那個方向提選項。
- **狀態列**：拿掉模型名稱。session 還沒有任何 API 呼叫時（`context_window.current_usage` 是 null），前面加「▶ 打「開始」開新局」或「▶ 打「繼續」接上次」，DM 回第一句後就消失。因為互動模式 Claude Code 不會自己先開口。
- **地窖改兩隻巨鼠**：第一次實玩一劍就結束太簡單。`giant_rat`（HP 6，會埋伏）加 `giant_rat_2`（HP 5，不埋伏）。`cellar_cleared` 改由場景的 `on_all_down` 在兩隻都倒下時設。想調難度，改 `data/actors.json` 的 `hp`、`damage` 就好。
- `SessionStart` 加 `recap.py`：把目前狀態和最近八筆事件當 `additionalContext` 塞給 DM，開新對話、resume、`/clear`、壓縮之後都會跑。互動模式 Claude Code 不會自己先開口，所以玩家還是要打第一句；打了之後 DM 直接回顧上次進度。這是 Day 13 記憶裡「SessionStart 前情提要」那個加碼。`initialUserMessage` 只在 `-p` 有效，互動模式用不到。
- 定案 C2 的字面沒動：一條路、DC 引擎算、後果固定、模型不碰數字。差別只在「允許的規則」從人一條條寫改成型別預設加場景例外。給 Codex 同步一句即可。

## D&D 精簡版（使用者：儘量貼齊 D&D）

- 規則改成 5 版 SRD 的精簡版，全文在 `rules.md`。骨架不變：d20 加修正對目標數字。
- 艾玲有六項能力值（固定不升級）、熟練 +2、熟練技能隱匿與說服。短劍是靈巧武器：攻擊 +4、傷害 d6+2。AC 10 加敏捷加護甲，初始 13。短休擲生命骰 d8 加體質。
- DC 改三檔：友善 10、中立 15、戒心或敵意 20。籌碼降一檔，請人喝酒給優勢，警戒給劣勢。優勢劣勢骰兩顆取高或取低，兩顆都有票根，兩個都有就抵銷。
- 骰面 20 重擊（傷害骰加倍）、骰面 1 必失手，雙方適用，檢定也適用。
- **戰鬥改成回合**：戰鬥開始後，每個還站著的敵人都在你行動後出手，做別的事（說服、偷、自由行動）也一樣。撤退每個敵人追擊一次。戰鬥中不能休息。地窖兩隻巨鼠現在會一起咬。
- **遠程**：`resolve_attack(target, mode="ranged")`。敵人還沒近身的第一箭不會被反擊，近身再射有劣勢，每箭耗一支箭。短弓和 10 支箭在商隊貨車裡。
- **裝備**：`data/items.json`，六個部位（武器、遠程、頭、身、手、腳），效果是 AC、傷害、技能優勢或劣勢。`/equip 名稱` 換裝走 `gamectl equip`，換下的收進背包。彎刀（手下掉）、白狼的長劍（白狼掉）、守衛的鎖甲（守衛掉）、皮手套（偷披斗篷的人）、軟底靴（跟梅拉買）。
- `state.json` 新增 `equipment`、`arrows`。`get_state` 新增 `hero`（AC、能力修正、裝備、近戰與遠程的攻擊加值與傷害）。狀態列顯示武器與 AC。
- 敵人數值照 5 版怪物調過：巨鼠 AC 12、HP 7、攻擊 +4、d4+1；手下 AC 12、HP 11、+3、d8+1；白狼 AC 14、HP 18、+5、d8+2。
- 不做：職業、等級、法術、先攻擲骰、死亡豁免、格子移動、機會攻擊、狀態效果。

## 音效全套（第二輪）

- `.claude/hooks/sounds/` 十個 CC0 短音效（Freesound，來源與裁切紀錄在 `CREDITS.md`、`manifest.json`）。原本來路不明的 `dice.wav` 換掉。
- `sound.py --result` 接在 `PostToolUse` 的所有引擎工具上，讀 `tool_response` 照「骰子：」底下的順序播：每一次出手（你的或敵人的）都是 `dice` 接 `hit`／`miss`；移動是撤退被追擊、`door`、進場偷襲；檢定有自己的骰才先響 `dice`（買酒不擲骰就不響），被丟去別的場景補 `door`，再接反擊；倒地最後補 `down`。`get_state`、`get_current_scene` 不響。一回合三隻敵人約 6 秒，所以這個 hook 用 `async: true`，DM 不用等音效播完才開口。
- `/rest`：改成 `rest` 工具（2026-09-29）之後，聲音跟其他工具一樣從 `PostToolUse` 的 `--result` 來：先 `rest`（營火），有擲骰再接 `dice`。原本玩家打的走 `UserPromptExpansion` matcher `rest`、DM 自己叫的走 `PostToolUse` matcher `Skill` 加 `--skill rest`（Day 11 那兩條路），兩條都拿掉，`sound.py --skill` 也刪了。
- `Stop` 換成 `stop.wav`；`SessionStart` 開門、`SessionEnd` 關門（`SessionEnd` 給 5 秒 timeout）。
- 查帳 hook 抓到票根不符時自己叫 `sound.py buzz`。
- `/rest` 還是 `!` 展開的時候，骰子聲由 `gamectl.py` 骰完自己播：`!` 展開不是工具呼叫，`PostToolUse` 看不到它。實玩時營火有聲、骰子沒聲才發現的。改成工具後不需要了，`gamectl.py rest` 在終端機跑仍會響一聲。

## 背景音樂（Day 11 的加碼）

- `bgm/` 五首 mp3（作者自製，見 `bgm/CREDITS.md`），`bgm/tracks.json` 決定場景對應。
- `.claude/hooks/bgm.py` 三個入口：`SessionStart` 開（`async: true`，不擋開局）、`FileChanged` 盯 `state.json` 做 `sync`（場景或結局變了才換曲）、`SessionEnd` 關。不掛 `PostToolUse`：`/newgame`、`/load` 走 `!` 展開改檔，不是工具呼叫，只有檔案監看看得到。`.game/bgm.lock` 讓兩次 sync 排隊，不會多開一個播放器。播放器是一個脫離的子程序，PID 記在 `.game/bgm.json`。
- Windows 走 winmm 的 MCI 播 mp3（可循環、可調音量），macOS `afplay`，Linux `ffplay`／`mpv`。都沒有就安靜。
- `/bgm on|off` Skill；`DUNGEON_BGM=0` 整個關；`DUNGEON_BGM_VOLUME` 調音量。
- 已知限制：Claude Code 當掉時 `SessionEnd` 不會跑，音樂會留到下次開局才被殺掉。

## 每個人身上都有東西（使用者的彩蛋）

- `data/actors.json` 每個角色都有 `loot`，女孩和巨鼠也有，`look` 裡露一點線索。受保護的女孩可以偷，還是不能打、不能動粗；巨鼠也能偷。
- 打倒的人身上沒被偷走的 `loot` 會掉給你，順便套用 `on_stolen`。這樣巨鼠的信不用靠 DC 20 的偷竊也拿得到。
- `data/items.json` 加上這些東西的文字。`hero.inventory` 會帶每一件的 `desc`；有 `needs` 的東西（老鼠的信、鼠臉畫像）要戴上奇怪的眼鏡才看得懂，沒戴時引擎只給 `desc_locked`，DM 拿不到內容。
- 新局背包裡多一本薄薄的書。
- 結局多一種：知道白狼是鎮長的兒子（讀過鎮長的信或偷到他的墜子，旗標 `knows_son`）再說服他，是「真相」結局。沒讀信的和平結局最後補一句提示你漏了什麼。
- 劇情補洞，全部圍著「回家」：女孩是商隊車夫的女兒，攔車那晚跟爸爸走散，撿到白狼掉的信（鎮長三年前寫的「那件事是我不對。回家吧。」）；她不識字，把信當成查出那些人是誰的唯一線索藏著，誰都不敢信；披斗篷的人是鎮長私下派來帶話的；那一箱是鎮長收的賄款；白狼要問父親「你信上說那件事是你不對。那這一箱是什麼？」。三個結局都讓車夫跟著貨車回來，女孩說出名字。
- 後果多一個 `if`：`{"if": ["knows_son"], "set_flag": "ending_truth"}`，旗標都成立才套用。

## 冒險手冊（mods）

- 新增 `.claude/skills/book/`：一個 mod，要 Claude Code 2.1.287 以上。輸入框上方多一列出口的數字鍵和明骰，`/book` 打開線索和地圖。放在專案的 `.claude/skills/` 底下、帶 `.claude-plugin/plugin.json` 的資料夾，Claude Code 會當成 plugin 載入（id 是 `book@skills-dir`），條件是從專案根目錄啟動、接受過信任。`claude --plugin-dir .claude/skills/book` 也能載入同一份。不載入時遊戲跟原來一樣。
- `state.json` 多一個欄位 `visited`：去過的場景，照第一次走到的順序。`move_to` 和被帶走（倒地回酒館、惹毛梅拉被丟進地窖）都會記。存檔一起存，讀檔一起還原。舊的狀態和舊存檔沒有這一欄，引擎用「從酒館走到目前位置最短的那條路」補上；這一欄被手動改壞（不是清單、漏了目前的場景）也照同樣的方式修好。`get_state` 回傳的 `state` 也帶這一欄。
- 新指令 `uv run --no-project gamectl.py book`：印出一份 JSON，有地圖、這個場景的出口、已經解開的線索、目前目標，和故事結束了沒（`over`）。唯讀，不產生結算。地圖的排版在引擎裡算好（`engine/core.py` 的 `_map_rows`），mod 只照格子畫。
- 場景檔的 `visible` 多一個 `map`，寫每個出口畫在哪一邊（`north`、`south`、`east`、`west`）。沒寫的出口由引擎挑第一個空著的邊。兩個場景之間只要有一個方向走得通，連線就畫成通的。
- 專案的 `.claude/settings.json` 加 `"tui": "fullscreen"`（2026-10-04 使用者要求），第一次玩就是全螢幕畫面，手冊停在對話右邊、可以用滑鼠點，不用自己打 `/tui fullscreen`。`tui` 這個設定放哪一層都有效，`settings.local.json` 加上 `"tui": "default"` 可以蓋掉（官方的值是 `fullscreen`／`default`，指令 `/tui fullscreen`／`/tui default`；全螢幕才收得到滑鼠）。
- 舊路岔路口的守路人，說服、繞過、打倒三種過法都各記一條線索，寫林子裡的小徑通往哪裡。原本只有說服會記，2026-10-04 使用者要三種一致。打倒那條用手冊自己的句子，不放「身上有 5 枚銅幣」這種一次性的細節。
- 場景檔的線索多一個 `journal`，有標的才進手冊。沒標的那些是場景狀態的描述（守衛盯著你、梅拉翻臉）和三個結局，DM 照樣拿得到。平常寫 `true`；同一個旗標在兩個場景都學得到、而線索文字只適合其中一處時，改寫成手冊要顯示的那句話（商隊清單在舊路的貨車和營地的貨箱都找得到，只有貨車那次有短弓）。
- 出口鎖著或有人守著，引擎的 `book` 一開始就知道（`open`、`hint`），但 mod 先不畫出來。DM 呼叫 `move_to` 被引擎拒絕之後，mod 才把那條路記成「試過、走不通」（`$.state` 的 `tried`，只在這次對話裡），出口後面多一個 `✕`，地圖的連線也換成 `─✕─`。所以地圖的每條連線都帶 `ends`，寫它連的是哪兩個場景。
- 地圖只畫去過的場景和它們的出口。出口另一頭還沒去過，就寫那個出口的名字，顏色比較暗；場景檔不在資料夾裡也一樣畫得出來，所以 `tools/trim_world.py` 剪過的快照不用改。地圖、出口列和選了之後填進輸入框的「我要去：…」，用的都是同一個名字（`op_book` 出口的 `label`），框裝不下就截短加「…」。原本還沒去過的畫 `？`，可是點下去會填出地名，使用者覺得奇怪，2026-10-04 改掉。
- `scene_card` 讀到壞掉的場景檔（不是 JSON、不是物件）改回引擎錯誤，不再讓整個指令掛掉；手冊遇到這種檔會略過。
- `CLAUDE.md` 給選項的那一條多一句「選項用『- 』條列，不要編號」：手冊載入時，空的輸入框按數字會選出口。
- `tools/set_python.py` 也會改 mod 裡的啟動指令（`register.tsx` 的 `ASK_ENGINE` 那一行）。
- 新工具 `tools/book_fixtures.py`：從引擎產生 mod 測試用的 `fixtures.ts`。`tests/test_book.py` 會比對這個檔和引擎現在的輸出，不一致就失敗。
- `tests/test_content.py` 的 Skill 清單改成只數有 `SKILL.md` 的資料夾；`book` 是 plugin，`/book` 是 mod 註冊的指令，不是 Skill。
- `.gitignore` 加上 `.claude/skills/*/.claude-plugin/types/`：Claude Code 載入 mod 時會在旁邊寫出型別宣告，那是產生的檔案。`tsconfig.json` 已經放進 mod 的資料夾，Claude Code 就不會另外產生一份。
- deny 規則和 `guard.py` 都不用改：`Edit(./.claude/**)` 和 `.claude/` 本來就涵蓋這個資料夾，DM 改不了玩家看到的畫面。
- 2026-10-08：轉圈那一行（`ui.render` 的 `Spinner`）在 DM 還在回覆時多一段「· 引擎擲了 N 次骰…」，N 是這一回合骰子行裡的票根數；還沒擲骰時不動，新回合歸零。照官方 mods 總覽的寫法，用 `next({ ...e, props })` 只改 `suffix`，畫面仍由 Claude Code 畫。mod 測試 15 個。

## 最終版（Day 30 下載版）

- 所有指令改用 `uv run --no-project`：`.mcp.json`、hooks、狀態列、allow 規則、Skill 的 `!` 指令與 `allowed-tools`。uv 自己找或下載 Python，不用管 `python` 還是 `python3`。Windows 上還比較快：`python` 會經過 Microsoft Store 的別名，實測狀態列從 247 ms 降到 154 ms。沒有 uv 的人跑 `tools/set_python.py python3` 換回直接呼叫直譯器。

- 音效改用 `.claude/hooks/sound.py`：先找專案裡的 `.claude/hooks/sounds/<名稱>.wav`，再找 `C:\Windows\Media`。Windows 用 `winsound` 播；macOS／Linux 有 `afplay`、`paplay`、`aplay` 就用，沒有就安靜結束。骰子聲是自己的 `dice.wav`（約 1 秒），接在引擎工具的 `PostToolUse`（現在是 `resolve_attack`、`resolve_check`、`move_to`；`roll` 拿掉之前也在內），這條路是真正的工具呼叫，一定會觸發；Day 11 的 `!` 展開兩條路在這裡不需要了。
- 引擎的 MCP server 改用官方 Python SDK 2.x（2026-09-28）。原本是標準函式庫手寫的 JSON-RPC，只會舊版的 `initialize` 握手：Claude Code 2.1.283 先用新版協定（`2026-07-28`）的 `server/discover` 問，被回「method not found」才退回 `2025-11-25`。改用 SDK 之後直接走新版，舊版 client 用 `initialize` 也連得上。工具說明、參數和回傳的 JSON 文字都沒變；只有參數格式錯時，錯誤訊息換成 SDK 的英文驗證訊息。工具表和 `call_tool()` 還是標準函式庫，測試不用裝 SDK 也能 import。`d16` 到 `d19` 的候選版一起換，每一版只差 `EXPOSED`。
- `README.md` 給下載的人看；`tools/inputs.example.txt` 是一份六回合的 headless 腳本。
- 里程碑標籤：`pre-d11`（Day 10 結束）、`d16`（Day 16 結束）、`d17`（Day 17 結束）、`d30`（最終可玩版）。`d16` 疊在分支 `d15-snapshot`（Day 15 結束）上面，`d17` 疊在 `d16` 上面，所以 `git diff d15-snapshot d16`、`git diff d16 d17` 就是那一天改了什麼。分支叫 `final`，標籤刻意不叫 final，避免 git 認不出你指的是哪一個。
- 09-24 最早做的兩個版本留在 `d16-old`、`d17-old`，當時還沒有 Day 11～15 的內容。
- 第一次 headless 六回合實跑抓到一個問題：引擎只回 `value` 和 `total` 時，DM 把加了修正的總和寫進票根（`[R:…=20]`，骰面其實是 18），查帳全部不符。修法：每顆骰子多回一個 `ticket` 欄位，DM 原樣貼。CLAUDE.md 與當時還在的 `/roll` 同步改。
- 骰子說明行：DM 自己在票根旁加括號說明，寫法每次不一樣，也沒說是什麼檢定。改由引擎在每個結算回傳 `dice`（取代原本只排票根的 `tickets`），一次出手或檢定一行，例如 `說服梅拉 8＋3＝11，對 DC 10，成功 [R:r-0a81bc=8]`、`巨鼠反擊 1＋4＝5，對你的 AC 13，大失手 [R:r-3c07f2=1]`。DM 在「骰子：」下面原樣貼上。headless 三回合實跑兩回合有骰，兩回合都一字不差貼上。
- 2026-10-09：plugin 多帶配樂（`hooks/bgm.py`、`bgm/`）和手冊 mod（`hooks/book/hooks/register.tsx`，`hooks.json` 用 `modules` 指過去）。mod 存的資料改掛在裝它的 plugin 名底下；`tool.call` 的條件同時接受 `mcp__dungeon__` 和 `mcp__plugin_<plugin>_dungeon__`。`--adventure` 匯出的冒險資料夾多了 `model`、`effortLevel`、`tui` 三個設定。
- 2026-10-14：完整版改成第二個 plugin `dm-final`（1.0.0）。Day 24 發布的 `dm`（1.0.1）留在當時那版：之後照順序學的人，到 Day 24 裝到的還是那一天的地城。`make_plugin.py` 保留 marketplace 原有的 entry，只換自己那一個；`/dm-final:bgm` 改指到 plugin 裡的 `hooks/bgm.py`；冒險資料夾的 allow 只留引擎的工具。
- 2026-10-14：照讀者的裝法（裝 `dm-final`、開新資料夾）從頭玩了一輪，修了這些：
  - `/report` 在 plugin 裡跑不起來：`gamectl.py report` 要用 `tools/build_report.py`，plugin 沒帶。`make_plugin.py` 現在把它放進 plugin 的 `tools/`。
  - 換場景不換曲：plugin 的 `hooks.json` 裡的 `FileChanged` matcher 不會讓 Claude Code 開始監看（寫在 `settings.json` 的會），所以 plugin 的 `bgm.py sync` 從來沒被叫過。`bgm.py` 多一個 `watch`，在 SessionStart 回傳 `watchPaths`（`state.json` 的完整路徑），plugin 的 `FileChanged` 從此就會觸發；`make_plugin.py` 只在 plugin 裡加這個 Hook。
  - 播放器自己的紀錄寫進了 plugin 的資料夾：`bgm.py player` 改收 `--root`，紀錄寫進冒險資料夾的 `.game/bgm.log`。
  - 狀態列在 MCP server 啟動前就畫第一次，只能顯示「等 dungeon 引擎啟動」：`.claude/statusline.py` 找不到 `.game/engine_root.txt`，或紙條指的版本已經刪掉時，改讀 Claude Code 自己的 `~/.claude/plugins/installed_plugins.json`（有 `CLAUDE_CONFIG_DIR` 就看那裡），找這個資料夾啟用的 plugin 裝在哪裡。
  - 手冊的謝幕沒有出現：結局那一回合，引擎的結算在回合中途就讓手冊重問一次引擎，回合結束時拿「之前」比對已經是 true。改用 `ended` 記下「上一回合結束時」故事有沒有說完。
  - 謝幕在窄的終端機看不到：mod 自己打開的窗格，Claude Code 要終端機 144 欄以上才畫出來（玩家打開過手冊、而且沒有自己關掉的話是 110 欄），不夠寬就等玩家打 `/book`。現在故事說完之後，輸入框上方那一列每回合都會留著「故事說完了。打 /report 可以寫成冒險日誌。」，手冊有沒有自己打開都看得到。
  - 戰報的 HP 折線圖沒有碰到 0：倒地那一筆事件記的是醒來補滿之後的 HP，兩次倒地都畫在 12。現在倒地的事件先在 0 畫一個紅點，同一個事件再回到醒來時的 HP。
  - 手冊的選項按鈕把字母寫了兩次（「a: a 跟梅拉打聽地窖的怪聲」）：按鈕自己會在前面畫出快捷鍵，標籤只放選項本身。
  - 手冊每回合那一行：舊的那一行重畫時，會換成最新一回合的骰數和引擎次數。現在每回合結束時記在 `tally`，照那一行的秒數取回自己的數字。
  - 換裝備：DM 只說「用 `/equip`」，玩家照做之後才發現要接裝備名稱；DM 也把換裝寫成選項，按下去只會把一句話送回給 DM。CLAUDE.md 改成要寫出完整指令 `/equip 裝備名稱`；手冊遇到含指令的選項，會把指令本身填進輸入框（`/book send` 開著也不送出），按 Enter 就換。plugin 裡的 CLAUDE.md、規則書和手冊的謝幕都換成 `/dm-final:equip`、`/dm-final:report`。
  - `/report` 的 Skill 原本寫「發布前 Claude Code 會問玩家同不同意」，實際上 `Artifact` 不會問（預設只有自己看得到），連預設權限模式也直接發布。改成告訴玩家頁面是私人的、怎麼分享；權限擋下或發布失敗時，才說戰報在 `.game/report.html`。
  - 倒地的效果寫成場景的名字：「醒來時在醉月酒館」，原本是代號 `tavern`。
