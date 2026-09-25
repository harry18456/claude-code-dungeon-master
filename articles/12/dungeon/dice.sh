#!/usr/bin/env bash
# 骰子腳本。用法：
#   bash dice.sh d20      → 印出「d20: 14」
#   bash dice.sh d6+1     → 印出「d6+1: 3 + 1 = 4」
# 只接受 dN 或 dN+M 的寫法，N 是面數，M 是加值。

spec="$1"                      # 第一個參數，例如 d6+1
sides="${spec#d}"              # 去掉開頭的 d      → 6+1
sides="${sides%%+*}"           # 去掉 + 和後面的字 → 6，這就是面數
bonus="${spec##*+}"            # 只留 + 後面的字   → 1，這就是加值
[[ "$spec" == *+* ]] || bonus=0   # 沒有 + 的話加值是 0
roll=$(( RANDOM % sides + 1 ))    # 骰一次：1 到面數之間的亂數

if (( bonus == 0 )); then
  echo "$spec: $roll"
else
  echo "$spec: $roll + $bonus = $(( roll + bonus ))"
fi
