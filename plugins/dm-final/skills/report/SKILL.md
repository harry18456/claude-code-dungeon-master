---
name: report
description: 產出這場冒險的日誌與戰報。冒險結束或告一段落時使用：把引擎的事實紀錄潤成日誌，並把戰報發布成 Artifact。只由玩家觸發。
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" report)
---

以下是引擎的機械紀錄（state、rolls、events），由 `gamectl.py` 讀出。同一個指令也把戰報寫成了 `.game/report.html`：

!`uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" report`

照順序做：

1. 把上面的事實潤成三到五段冒險日誌，繁體中文。
   - 每一個數字都必須來自上面的紀錄。沒發生的事不得敘述；三次攻擊都未命中，就不能寫成「艱難地擊敗了對手」。
   - 紀錄是空的，就如實寫「這場冒險尚未真正展開」。
   - 不要重複列票根，也不要輸出單顆骰值。
   - 最後一句收束。若 flags 裡有 ending_truth、ending_peace 或 ending_fight，用它決定結局怎麼寫；ending_truth 優先。
2. 把戰報發布成 Artifact：先用 Read 讀完整份 `.game/report.html`，再用 Artifact 工具發布這個檔案。`icon` 填 `book`，`description` 用一句話寫這場冒險怎麼結束。戰報裡的數字全部來自引擎，不要改檔案內容。發布出去的頁面預設只有玩家自己看得到。發布成功後，把連結放在日誌最後，並告訴玩家：要給別人看，從頁面的分享選單打開。
3. 這個環境沒有 Artifact 工具、工具被權限擋下、或發布失敗：在日誌最後告訴玩家，戰報在 `.game/report.html`，用瀏覽器打開就能看。
