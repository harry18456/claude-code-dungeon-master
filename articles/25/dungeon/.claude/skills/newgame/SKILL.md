---
name: newgame
description: 重新開始一場新冒險。只由玩家明確觸發。會先把目前進度存到 before-newgame 這個存檔槽。
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project gamectl.py newgame)
---

引擎已經重開新局（在你看到這段文字之前執行，不是你產生的）：

!`uv run --no-project gamectl.py newgame`

這段對話裡先前發生的事都不算數。先呼叫 `get_state` 與 `get_current_scene`，用三到五句描述醉月酒館的開場，介紹艾玲（HP 12、8 枚銅幣、一把短劍），最後問玩家「你要做什麼？」，給兩到四個選項。
