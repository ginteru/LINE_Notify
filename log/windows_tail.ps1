# PowerShellでtail
#   右クリック「PowerShellで実行」
$LOG = 'LINE_Notify.log'
PowerShell -command Get-Content -Path $LOG -Wait -Encoding UTF8 -Tail 20

# cf
#       https://qiita.com/yokra9/items/d95abda8a795d4e19e0e
#       https://it-engineer-info.com/language/powershell/tail-command
