# .claude\hooks\skill-sound.ps1
# 用法：powershell -File skill-sound.ps1 <skill 名字> <wav 檔名>
# 給 PostToolUse matcher Skill 用：只有指定的 Skill 被 Claude Code 自己叫到才播。
param([string]$Skill = "roll", [string]$Name = "ding")

$raw = [Console]::In.ReadToEnd()
try { $j = $raw | ConvertFrom-Json } catch { exit 0 }

if ($j.tool_input.skill -eq $Skill) {
  & (Join-Path $PSScriptRoot "play.ps1") $Name
}
exit 0
