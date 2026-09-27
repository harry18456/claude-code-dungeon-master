# .claude\hooks\audit.ps1
# Stop：DM 講完話時對帳。只警告，不擋。
#   1. 回覆裡的每張票根 [R:編號=結果]，帳本裡都要有，而且結果一樣。
#   2. 上次對帳之後新骰的每一顆，回覆裡都要有它的票根。
# 對不上就印出 systemMessage：只有玩家看得到，DM 不會知道。
# 這個檔要存成 UTF-8 with BOM。
[Console]::InputEncoding  = New-Object Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false

$in     = [Console]::In.ReadToEnd() | ConvertFrom-Json
$game   = Join-Path $PSScriptRoot "..\..\.game"
$ledger = Join-Path $game "rolls.log"
$cursor = Join-Path $game "audit.cursor"
if (-not (Test-Path $ledger)) { exit 0 }                 # 還沒骰過

$lines = @(Get-Content $ledger -Encoding UTF8 | Where-Object { $_ })
$book  = @{}                                             # 帳本：編號 → 結果
foreach ($l in $lines) { $f = $l -split ' '; $book[$f[0]] = $f[2] }

$done = 0                                                # 上次對帳時帳本有幾行
if (Test-Path $cursor) { $done = [int](Get-Content $cursor) }
$new = @($lines | Select-Object -Skip $done)             # 這回合新骰的
Set-Content $cursor $lines.Count

$reply = [string]$in.last_assistant_message
$warn  = @()
foreach ($m in [regex]::Matches($reply, '\[R:([^=\]\s]+)=([^\]\s]+)\]')) {
  $id = $m.Groups[1].Value; $v = $m.Groups[2].Value
  if (-not $book.ContainsKey($id)) { $warn += "票根 $id 不在帳本裡" }
  elseif ($book[$id] -ne $v)       { $warn += "票根 $id 寫 $v，帳本記的是 $($book[$id])" }
}
foreach ($l in $new) {
  $f = $l -split ' '
  if (-not $reply.Contains("[R:$($f[0])=")) { $warn += "這回合骰了 $($f[1]) 得 $($f[2])，回覆裡沒有它的票根 $($f[0])" }
}

if ($warn) {
  @{ systemMessage = "查帳警告：" + ($warn -join "；") } | ConvertTo-Json -Compress
}
exit 0
