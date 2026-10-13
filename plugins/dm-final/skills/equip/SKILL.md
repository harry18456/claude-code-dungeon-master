---
name: equip
description: 換裝備：武器、弓、頭、身、手、腳。只由玩家觸發。
argument-hint: "[裝備名稱，例如 彎刀、獵人的短弓、守衛的鎖甲]"
disable-model-invocation: true
allowed-tools: Bash(uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" equip *)
---

以下結果已在你看到前由引擎執行：

!`uv run --no-project "${CLAUDE_PLUGIN_ROOT}/gamectl.py" equip $ARGUMENTS`

把上面那一行原樣回報給玩家，再用一句話描述艾玲換裝的樣子。不要描述場景，不要改任何檔案。
