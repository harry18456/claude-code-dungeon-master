# .claude\hooks\play.ps1
# 用法：powershell -File play.ps1 <wav 檔名>
# 從 C:\Windows\Media 播一個內建音效，播完就結束。
param([string]$Name = "ding")
$wav = Join-Path $env:WINDIR "Media\$Name.wav"
if (Test-Path $wav) {
  (New-Object Media.SoundPlayer $wav).PlaySync()
}
exit 0
