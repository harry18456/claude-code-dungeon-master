---
name: check
description: 玩家自己指定要對誰做什麼檢定：說服、偷、潛行、聲東擊西、動粗、搜索、互動、自由行動。走引擎的 resolve_check，結果會改變世界。
argument-hint: "[動詞] [對象]，例如 persuade guard、search rubble、improvise"
disable-model-invocation: true
allowed-tools: mcp__dungeon__resolve_check, mcp__dungeon__get_current_scene
---

玩家要做檢定：$ARGUMENTS

1. 第一個字是動詞，中文也可以：說服＝persuade、偷＝steal、潛行＝sneak、聲東擊西＝distract、動粗＝provoke、搜＝search、互動＝interact、自由＝improvise。第二個字是對象代號；對象是中文名字或不確定時，先呼叫 `get_current_scene` 對照 actors 與 features 的代號。只寫 improvise 時對象用 here。
2. 呼叫 `resolve_check(rule_id, target_id)`。引擎回錯誤就照錯誤訊息告訴玩家，列出可用的對象與動詞，不要自己換成別的動作。
3. 照回傳敘述：DC、骰值、成敗、`effects`、`revealed`、`strike`。最後寫一行「骰子：」，下一行起原樣貼上回傳的 `dice`。
4. 攻擊不走這裡。玩家寫 attack 就改呼叫 `resolve_attack(target)`。
