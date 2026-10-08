---
name: recap
description: 回顧最近發生的事。玩家問「剛才發生什麼」「我做到哪了」，或你需要整理已發生的事實時使用。
allowed-tools: Bash(uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" log *)
---

以下是引擎紀錄的最近十筆事件，由 `gamectl.py` 讀出：

!`uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" log 10`

只根據上面的事件做簡短回顧，兩三句就好。不要補入紀錄裡沒有的骰值、傷害、HP、角色動機或內幕。
