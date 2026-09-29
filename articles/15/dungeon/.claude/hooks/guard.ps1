# .claude\hooks\guard.ps1
# PreToolUse（matcher Edit|Write）：Claude Code 要改 state.json 之前，
# 先組出「改完的樣子」，hp 不合理就用 exit 2 擋下來。
# 這個檔要存成 UTF-8 with BOM，Windows PowerShell 5.1 才讀得懂中文。
[Console]::InputEncoding  = New-Object Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
$MaxHp = 12                                    # 艾玲的 HP 上限，寫死在守衛裡

function Block($why) {                         # 理由寫進 stderr，exit 2 擋下
  [Console]::Error.WriteLine("守衛擋下這次修改：$why。state.json 沒有被改。")
  exit 2
}

try {
  $in    = [Console]::In.ReadToEnd() | ConvertFrom-Json
  $state = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\state.json"))
  $path  = $in.tool_input.file_path
  if (-not $path -or [IO.Path]::GetFullPath($path) -ne $state) { exit 0 }   # 不是 state.json 就不管

  # 1. 組出改完的樣子
  if ($in.tool_name -eq "Write") {
    $after = $in.tool_input.content
  } else {
    $now = [IO.File]::ReadAllText($state)
    $old = $in.tool_input.old_string
    $new = $in.tool_input.new_string
    $n = 0
    if ($old) { $n = ([regex]::Matches($now, [regex]::Escape($old))).Count }
    if ($n -eq 0) { Block "找不到要換掉的文字，組不出改完的樣子" }
    if ($in.tool_input.replace_all) {
      $after = $now.Replace($old, $new)
    } elseif ($n -gt 1) {
      Block "要換掉的文字出現 $n 次，組不出改完的樣子"
    } else {
      $i = $now.IndexOf($old, [StringComparison]::Ordinal)
      $after = $now.Substring(0, $i) + $new + $now.Substring($i + $old.Length)
    }
  }

  # 2. 改完的樣子要是合法的 JSON
  try { $s = $after | ConvertFrom-Json } catch { Block "改完不是合法的 JSON" }

  # 3. 檢查 hp 和 max_hp
  $hp = $s.hp
  if (-not ($hp -is [int] -or $hp -is [long])) { Block "hp 必須是整數（這次是 '$hp'）" }
  if ($hp -lt 0 -or $hp -gt $MaxHp)            { Block "hp 必須在 0 到 $MaxHp 之間（這次是 $hp）" }
  if (-not ($s.max_hp -is [int]) -or $s.max_hp -ne $MaxHp) { Block "max_hp 必須維持 $MaxHp（這次是 '$($s.max_hp)'）" }
  exit 0
} catch {
  Block "守衛自己出錯了（$($_.Exception.Message)），先擋下來"
}
