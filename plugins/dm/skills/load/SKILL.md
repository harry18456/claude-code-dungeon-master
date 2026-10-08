---
name: load
description: 從存檔槽讀回遊戲狀態。只由玩家明確觸發。
argument-hint: "[存檔名稱，預設 quick]"
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" load *)
---

以下結果已在你看到前由引擎執行：

!`uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" load quick $ARGUMENTS`

讀檔之後，這段對話裡在存檔點之後發生的事都不算數。先呼叫 `get_state` 與 `get_current_scene`，再用兩三句描述艾玲現在在哪、狀態如何，最後問玩家「你要做什麼？」，給兩到四個選項。不要引用讀檔前的骰值或事件。
