# 30 天建立 Claude Code 地城領主

2026 iThome 鐵人賽（Claude AI 組）的文章與實作。用 Claude Code 從零做一個 AI 地城領主，一天加一樣東西，邊做邊學。

## 這個系列在做什麼

Claude Code 跟地城領主/地下城主（Dungeon Master）有什麼關係！？
實際上沒什麼關係。

想寫 Claude Code 教學，又不想無趣地一個一個介紹功能，
那就乾脆做成一個小遊戲，邊做、邊玩、邊學吧！

接下來 30 天我會先用 Claude Code 做出一個最陽春的 AI 地城領主，一天加一樣東西——CLAUDE.md、Skill、MCP、Hook——把它慢慢養成一個有模有樣的 DM。

## 進度

| Day | 標題 | 大綱 | 帶得走什麼 | 狀態 |
|---|---|---|---|---|
| 1 | [裝好 Claude Code，來開第一局吧!](articles/01/day01.md) | Claude 與 Claude Code 是什麼、方案與介面、安裝登入、選模型與 effort、空資料夾開一局玩七回合 | 裝得起來、知道模型和 effort 怎麼選以及各花多少錢、看到一個沒有骰子的 DM 怎麼編數字 | 已完成 |
| 2 | [梅拉不見了：對話存在哪裡、怎麼拿回來](articles/02/day02.md) | 重開一局梅拉不見；session 存在 `~/.claude/projects/` 的 `.jsonl`；`--resume`、`-c` 拿回來；換資料夾、換電腦、30 天清理三個常見問題 | 對話是本機檔案，resume 是補救不是設計；世界設定該住在檔案裡 | 已完成 |
| 3 | [把世界寫進 CLAUDE.md，梅拉不用 resume 也在](articles/03/day03.md) | CLAUDE.md 是什麼、Global／Project／Local 三層、把 Day 1 的世界寫進去、開新局直接認得梅拉、`/context` 看它讀了什麼、`@` 引用其他檔案 | 不變的設定住檔案；它是提示不是規則引擎；會變的數字要另找地方 | 已完成 |
| 4 | [讓 Claude Code 紀錄血量與骰骰子吧！](articles/04/day04.md) | 內建工具 Read／Bash／Edit；HP 搬進 `state.json`；骰子改用終端機指令 `$RANDOM`；`Ctrl+O` 看工具細節；auto mode 自動放行 | 會變的數字住檔案，交給 Claude Code 讀寫；每次動手畫面上都看得到；CLAUDE.md 是請它做，不是強制 | 已完成 |
| 5 | [我不依我不依（地上打滾），我要回到上一個動作：/rewind](articles/05/day05.md) | 接回昨天那局打死巨鼠；搜地窖只撿到 1 枚就倒帶重刷；checkpoint 存在哪（`.jsonl` 與 `file-history/`）、對話是一棵樹；`/rewind` 六個選項；`/branch` | 每句話都是存檔點，檔案和對話可以分開倒；bash 和手動改的檔案倒不回來 | 已完成 |
| 6 | 待定 | Skill：把「休息」做成 `/rest` | | 撰寫中 |
| 7–30 | 待定 | 一天加一樣東西：MCP、Hook…… | | 未開始 |

大綱採滾動式調整，寫到哪裡更新到哪裡。

## 目錄

| 路徑 | 內容 |
|---|---|
| `articles/NN/dayNN.md` | 每天一篇文章，圖片放同層的 `assets/` |
| `articles/NN/dungeon/` | 那一天結束時 `dungeon` 資料夾的內容，照著做可以對答案 |

## 要跟著做的話

- Claude 訂閱方案 Pro 以上，或有儲值的 [Claude Console](https://platform.claude.com/) 帳號。免費方案不能用 Claude Code。
- 一個編輯器。我用 VS Code 加它內建的終端機，作業系統是 Windows。其他組合也可以，指令要自己換。
- 安裝步驟在 [Day 1](articles/01/day01.md)。

## 用語

讀者看得到的文字一律用「地城領主」，這是台灣桌遊出版社的譯法。送進模型的 prompt、腳本與保存下來的原始輸出保留當時的寫法，不回頭改，才能跟畫面對得上。

## 報名資訊

| 欄位 | 內容 |
|---|---|
| 參賽主題 | Claude AI |
| 參賽題目 | 30 天建立 Claude Code 地城領主 |

主題與題目報名後不可修改，文章標題與系列名以此為準。
