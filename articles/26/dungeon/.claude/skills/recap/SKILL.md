---
name: recap
description: 回顧最近發生的事。玩家問「剛才發生什麼」「我做到哪了」「我忘了誰說過什麼」，或你需要整理已發生的事實時使用。就算是剛開局、你覺得沒什麼好回顧，也先用這個 Skill，由引擎的紀錄回答。玩家問某個人或某樣東西的事（信寫什麼、傳聞是什麼）不算回顧。
allowed-tools: Bash(uv run --no-project gamectl.py log *)
---

以下是引擎紀錄的最近十筆事件，由 `gamectl.py` 讀出：

!`uv run --no-project gamectl.py log 10`

只根據上面的事件做簡短回顧，兩三句就好。不要補入紀錄裡沒有的骰值、傷害、HP、角色動機或內幕。
