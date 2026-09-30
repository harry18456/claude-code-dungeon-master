---
name: roll
description: 擲骰。玩家說要骰 d20、骰個 d6+1、擲骰檢定時使用。
argument-hint: "[骰子，例如 d20+2]"
---

玩家要骰 $ARGUMENTS。呼叫 dungeon 的 roll 工具骰這一顆，dice 填 $ARGUMENTS。

把工具回傳的 `dice` 那一行原樣報給玩家，不要自己改數字，也不要再骰一次。然後用一句話說這個結果在目前情境下代表什麼。
