' Start backup-disk.ps1 with no console. WScript.Shell Run style 0 is
' hidden; powershell -WindowStyle Hidden still opens a window first.
If WScript.Arguments.Count < 1 Then WScript.Quit 1
action = WScript.Arguments(0)
If action <> "On" And action <> "Off" Then WScript.Quit 1
ps = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
script = "C:\ProgramData\backup-disk\backup-disk.ps1"
cmd = ps & " -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & script & """ -Action " & action
CreateObject("Wscript.Shell").Run cmd, 0, True
