#!/usr/bin/env bash
# 骰子腳本。用法：
#   bash dice.sh d20      → 印出「d20: 14 [R:3f9a0c21=14]」
#   bash dice.sh d6+1     → 印出「d6+1: 3 + 1 = 4 [R:7b1d44e0=4]」
# 只接受 dN 或 dN+M 的寫法，N 是面數，M 是加值。
# 每骰一次，就在 .game/rolls.log（帳本）記一行：編號 骰子 結果 時間。
# 最後的 [R:編號=結果] 是票根，DM 要原樣貼給玩家。

spec="$1"                      # 第一個參數，例如 d6+1
sides="${spec#d}"              # 去掉開頭的 d      → 6+1
sides="${sides%%+*}"           # 去掉 + 和後面的字 → 6，這就是面數
bonus="${spec##*+}"            # 只留 + 後面的字   → 1，這就是加值
[[ "$spec" == *+* ]] || bonus=0   # 沒有 + 的話加值是 0
roll=$(( RANDOM % sides + 1 ))    # 骰一次：1 到面數之間的亂數
total=$(( roll + bonus ))

id=$(printf '%04x%04x' $RANDOM $RANDOM)       # 這一骰的編號，8 個字
ledger="$(dirname "$0")/.game/rolls.log"
mkdir -p "$(dirname "$ledger")"
echo "$id $spec $total $(date '+%F %T')" >> "$ledger"
ticket="[R:$id=$total]"

if (( bonus == 0 )); then
  echo "$spec: $roll $ticket"
else
  echo "$spec: $roll + $bonus = $total $ticket"
fi
