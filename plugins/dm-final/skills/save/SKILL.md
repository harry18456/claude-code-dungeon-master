---
name: save
description: 把目前的遊戲狀態存進一個存檔槽。只由玩家明確觸發。
argument-hint: "[存檔名稱，預設 quick]"
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" save *)
---

以下結果已在你看到前由引擎執行：

!`uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" save quick $ARGUMENTS`

把上面那一行原樣回報給玩家。不要描述場景，不要改任何檔案。
