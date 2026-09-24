---
name: rest
description: 休息補血。玩家說要休息、睡一下、回血、包紮傷口時使用。
allowed-tools: Bash(bash dice.sh *)
---

休息一晚，回復的 d4 已經骰好了：

!`bash dice.sh d4`

照順序做：

1. 讀 state.json。
2. 把上面那行骰子結果原樣列給玩家看，不要自己改數字，也不要再骰一次。
3. HP 加上骰出的點數，最多加到 max_hp。
4. 改寫 state.json 的 hp，改完才繼續。
5. 用兩三句描述休息的場景，最後報 HP 現在多少，再問玩家「你要做什麼？」，給兩到四個選項。
