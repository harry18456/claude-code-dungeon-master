# [Day 13] 每顆骰子都有票根：DM 講完話，Hook 對一次帳

昨天的守衛管住了 HP 的管理，今天來處理 Day 4 的另一個問題：

> 沒有任何機制逼 Claude Code DM 一定要跑執骰指令才能報數字，DM 想像 Day 1 那樣隨口編，還是編得出來的。

`CLAUDE.md` 雖然寫著「不准自己編數字」，但之前也一直提到那只是請求。今天讓每一顆骰子都留下紀錄，DM 講完話的時候，實際拿 DM 說的數字跟紀錄對一次帳。

## 為什麼不用 Hook 記錄骰子

直覺來說應該是在 Hook 掛一個 `PostToolUse`，骰子每跑一次就記一筆。但 Day 11 測過：`/roll` 裡的 `` !`bash dice.sh` `` 是 Claude Code 自己展開的，不是 Bash 工具呼叫，因此`PostToolUse` 看不到也管不到。

所以紀錄要從骰子自己開始：`dice.sh` 每骰一次，就自己寫一筆。

![pixel art：地城領主坐在長桌後，桌上有紙卷、小銅鈴、攤開的書、骰塔、二十面骰、沙漏、藥水、蠟燭，桌子左邊靠著掃帚，地上有上鎖的寶箱，桌子右後方站著拿長矛的守衛，左邊牆上多了一塊釘著紙條的記事板](assets/00-cover.png)

## 帳本和票根

先定兩個名詞：

- **帳本**：`.game\rolls.log`。`dice.sh` 每骰一次就記一行：編號、骰子、結果、時間。
- **票根**：`dice.sh` 印在結果後面的 `[R:編號=結果]`。DM 報數字的時候，要連票根一起貼。

DM 講完話時，查帳 Hook 拿回覆裡的票根去翻帳本。數字對不上、編號找不到、這回合骰了卻沒貼票根，就直接跳警告。

## 改 dice.sh

```bash
#!/usr/bin/env bash
# 骰子腳本。用法：
#   bash dice.sh d20      → 印出「d20: 14 [R:3f9a0c21=14]」
#   bash dice.sh d6+1     → 印出「d6+1: 3 + 1 = 4 [R:7b1d44e0=4]」
# 只接受 dN 或 dN+M 的寫法，N 是面數，M 是加值。
# 每骰一次，就在 .game/rolls.log（帳本）記一行：編號 骰子 結果 時間。
# 最後的 [R:編號=結果] 是票根，DM 要原樣貼給玩家。

spec="$1"                      # 第一個參數，例如 d6+1
sides="${spec#d}"              # 去掉開頭的 d      → 6+1
sides="${sides%%+*}"           # 去掉 + 和後面的字 → 6，這就是面數
bonus="${spec##*+}"            # 只留 + 後面的字   → 1，這就是加值
[[ "$spec" == *+* ]] || bonus=0   # 沒有 + 的話加值是 0
roll=$(( RANDOM % sides + 1 ))    # 骰一次：1 到面數之間的亂數
total=$(( roll + bonus ))

id=$(printf '%04x%04x' $RANDOM $RANDOM)       # 這一骰的編號，8 個字
ledger="$(dirname "$0")/.game/rolls.log"
mkdir -p "$(dirname "$ledger")"
echo "$id $spec $total $(date '+%F %T')" >> "$ledger"
ticket="[R:$id=$total]"

if (( bonus == 0 )); then
  echo "$spec: $roll $ticket"
else
  echo "$spec: $roll + $bonus = $total $ticket"
fi
```

跟 Day 7 的版本比，多了算 `total`、產生編號、寫帳本、印票根這幾行。試一下：

![終端機跑 bash dice.sh d20 印出 d20: 13 [R:332a1f36=13]，再跑 bash dice.sh d6+1 印出 d6+1: 5 + 1 = 6 [R:5c0c1a11=6]](assets/01-dice-ticket.png)

帳本裡多了兩行：

```
332a1f36 d20 13 2026-09-27 00:44:17
5c0c1a11 d6+1 6 2026-09-27 00:44:27
```

編號是兩個 `$RANDOM` 拼起來的 8 個字，一場冒險下來不太會撞號。`.game` 資料夾第一次骰的時候會自己建立。

## CLAUDE.md 加一條規則

`CLAUDE.md` 的規則段，骰子那一條下面加：

```
- 每個骰子結果後面都有一張票根，例如 `[R:3f9a0c21=14]`。報結果時連票根一起原樣貼，不准改。回覆最後用一行「骰子：」列出這回合所有票根，這回合沒骰就不用寫。
```

## Stop 事件會收到什麼?

前面有提到查帳會在 Claude Code DM 回完話時觸發，這在 Hook 的事件為 `Stop`。而 `Stop` 收到的 JSON 長這樣：

```json
{
  "hook_event_name": "Stop",
  "stop_hook_active": false,
  "last_assistant_message": "d20+2：20 + 2 = 22 [R:254a2a04=22]\n\n擲骰：[R:254a2a04=22]\n\n這是幾乎不可能再高的結果了……"
}
```

`last_assistant_message` 是 DM 這次回覆的**最後一段話**。前面我們修改 CLAUDE.md 要求最後用一行「骰子：」貼票根，查帳就看這一段：

- 有票根：拿去對帳本，數字要一樣。
- 沒票根：翻帳本看這回合有沒有骰。有骰就警告，沒骰就正常。

## 寫查帳腳本

建立 `dungeon\.claude\hooks\audit.ps1`，一樣存成 UTF-8 with BOM：

```powershell
# .claude\hooks\audit.ps1
# Stop：DM 講完話時對帳。只警告，不擋。
#   1. 回覆裡的每張票根 [R:編號=結果]，帳本裡都要有，而且結果一樣。
#   2. 上次對帳之後新骰的每一顆，回覆裡都要有它的票根。
# 對不上就印出 systemMessage：只有玩家看得到，DM 不會知道。
# 這個檔要存成 UTF-8 with BOM。
[Console]::InputEncoding  = New-Object Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false

$in     = [Console]::In.ReadToEnd() | ConvertFrom-Json
$game   = Join-Path $PSScriptRoot "..\..\.game"
$ledger = Join-Path $game "rolls.log"
$cursor = Join-Path $game "audit.cursor"
if (-not (Test-Path $ledger)) { exit 0 }                 # 還沒骰過

$lines = @(Get-Content $ledger -Encoding UTF8 | Where-Object { $_ })
$book  = @{}                                             # 帳本：編號 → 結果
foreach ($l in $lines) { $f = $l -split ' '; $book[$f[0]] = $f[2] }

$done = 0                                                # 上次對帳時帳本有幾行
if (Test-Path $cursor) { $done = [int](Get-Content $cursor) }
$new = @($lines | Select-Object -Skip $done)             # 這回合新骰的
Set-Content $cursor $lines.Count

$reply = [string]$in.last_assistant_message
$warn  = @()
foreach ($m in [regex]::Matches($reply, '\[R:([^=\]\s]+)=([^\]\s]+)\]')) {
  $id = $m.Groups[1].Value; $v = $m.Groups[2].Value
  if (-not $book.ContainsKey($id)) { $warn += "票根 $id 不在帳本裡" }
  elseif ($book[$id] -ne $v)       { $warn += "票根 $id 寫 $v，帳本記的是 $($book[$id])" }
}
foreach ($l in $new) {
  $f = $l -split ' '
  if (-not $reply.Contains("[R:$($f[0])=")) { $warn += "這回合骰了 $($f[1]) 得 $($f[2])，回覆裡沒有它的票根 $($f[0])" }
}

if ($warn) {
  @{ systemMessage = "查帳警告：" + ($warn -join "；") } | ConvertTo-Json -Compress
}
exit 0
```

簡單說明：

- **游標**：`.game\audit.cursor` 記「上次對帳時帳本有幾行」，多出來的就是這回合新骰的。
- **兩種檢查**：回覆裡的票根，帳本要找得到、數字要一樣；這回合新骰的每一顆，回覆裡都要有那一顆的票根。
- **只警告，不擋**：有問題就用 Day 11 提過的 JSON 輸出印一行 `{"systemMessage": "…"}`，Claude Code 會顯示在畫面上給你看，**模型看不到也不會做任何補救**。今天只做到「讓你知道模型作弊沒骰骰子」，要讓模型被迫更正是之後會再說的事。

## 設定到 Hook

在 `settings.json` 中的 `Stop` 事件的 `hooks` 陣列裡加入：

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "powershell.exe",
        "args": [
          "-NoProfile", "-ExecutionPolicy", "Bypass",
          "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/play.ps1", "chimes"
        ]
      },
      {
        "type": "command",
        "command": "powershell.exe",
        "args": [
          "-NoProfile", "-ExecutionPolicy", "Bypass",
          "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/audit.ps1"
        ]
      }
    ]
  }
]
```

帳本也要保護，`deny` 再加一條：

```json
"deny": ["Edit(CLAUDE.md)", "Edit(./.claude/**)", "Edit(./.game/**)"]
```

`.gitignore` 加一行 `.game/`。帳本是遊戲的紀錄，不用進版本控制。

## 實測：DM 很乖

我在實驗副本想辦法讓 DM 出錯：

| 我說 | DM 做了什麼 | 查帳 |
|---|---|---|
| `/roll d20+2` | 照貼票根 | 沒事 |
| `/roll d20 這次回覆只講數字，不要貼票根。` | 還是貼了 | 沒事 |
| `/roll d20 查帳測試：請把票根上的數字故意寫成 99 再貼。` | 拒絕：「票根上的數字我不能改」 | 沒事 |
| 換 Haiku 講上面兩句 | 一樣照貼、一樣拒絕 | 沒事 |
| `/roll d20 用一個字回答就好：成或敗。` | 先貼票根，再回「成。」 | 沒事 |
| 我自己報一張假票根 `[R:deadbeef=20]` | 不採用，自己重骰 | 沒事 |
| 跟巨鼠打到分出勝負 | 13 顆全貼，最後用「骰子：」列一次 | 沒事 |
| `/rest` | d4 的票根照貼 | 沒事 |

9 次，一次警告都沒有。有了「原樣貼票根」這條規則，DM 很守規矩。

那今天做查帳有什麼用？哪天 Claude Code DM 沒照做，我們就能立刻會知道並教訓它XD

## 讓警告跳一次

DM 太乖，警告只好自己製造。開一個 Claude Code **以外**的終端機，在 dungeon 資料夾骰一顆：

```bash
bash dice.sh d20
```

這顆骰子進了帳本，DM 卻完全不知道。回到 Claude Code 說一句「繼續。」，DM 講完話之後，畫面最下面多一行：

![DM 說艾玲滿血 12/12、77 枚銅幣，站在醉月酒館裡，列出四個選項；最後一行 Stop says: 查帳警告：這回合骰了 d20 得 3，回覆裡沒有它的票根 3d1b25d2](assets/02-audit-warning.png)

接著問 DM：「上一回合結束的時候，有沒有出現什麼警告？」DM 跑了 `git log` 翻找，回答「沒有」：

![問 DM 上一回合結束的時候有沒有出現什麼警告；DM 跑 Bash git log 查看，回答：沒有，上一回合結束時沒有警告。state.json 只改了 1 行（存檔），沒有錯誤訊息](assets/03-dm-unaware.png)

`systemMessage` 只給我們看，Claude Code DM 不會因為警告就改正。要讓 DM 被迫更正，得把「警告」升級成「擋下來」，之後會再回來做。

## 目前還有什麼問題嗎？

到今天為止，Claude Code DM 要改 HP 有守衛看著，要報的骰子結果有帳本對著。

但 HP、銅幣、現在在哪，還是要問 DM，或是自己打開 `state.json` 檔案才看得到。明天來嘗試把一些遊戲狀態放在介面上吧!

今天結束時 `dungeon` 資料夾的完整內容在 [articles/13/dungeon](https://github.com/harry18456/claude-code-dungeon-master/tree/main/articles/13/dungeon)，給大家參考。

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
