@echo off
REM Dockur runs this file once near the end of unattended Windows setup.
REM PowerShell's execution policy is bypassed because these repository scripts
REM are local OEM setup files and are not code-signed.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"

REM Return the PowerShell result to Dockur so setup failures remain visible.
exit /b %ERRORLEVEL%
