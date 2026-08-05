$ErrorActionPreference = "Stop"

# This script runs once from install.bat during initial Windows installation.
# Per-login and frequently changed behavior belongs in launcher/worker instead.
$root = "C:\SBSEGVerifierVM"
New-Item -ItemType Directory -Force -Path $root | Out-Null

# The launcher is stored locally because Z: may not exist immediately at login.
Copy-Item -Force "$PSScriptRoot\launcher.ps1" "$root\launcher.ps1"

# Keep the console session available to PyAutoGUI.
powercfg.exe /change monitor-timeout-ac 0
powercfg.exe /change standby-timeout-ac 0
powercfg.exe /change hibernate-timeout-ac 0
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DisableLockWorkstation /t REG_DWORD /d 1 /f | Out-Null

# HttpListener requires both a URL reservation and an inbound firewall rule.
# Docker publishes this guest port only on the Linux host's loopback address.
& netsh.exe http delete urlacl url=http://+:8765/ | Out-Null
& netsh.exe http add urlacl url=http://+:8765/ user=sbseg | Out-Null
& netsh.exe advfirewall firewall delete rule name="SBSEG Verifier API" | Out-Null
& netsh.exe advfirewall firewall add rule name="SBSEG Verifier API" dir=in action=allow protocol=TCP localport=8765 | Out-Null

# The worker must run in the auto-logged-in desktop session. A service, WinRM,
# SSH, or docker exec process would not share the desktop driven by PyAutoGUI.
$runKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
New-ItemProperty `
    -Path $runKey `
    -Name "SBSEGVerifierWorker" `
    -PropertyType String `
    -Value 'powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\SBSEGVerifierVM\launcher.ps1"' `
    -Force | Out-Null
