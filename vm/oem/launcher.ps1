$ErrorActionPreference = "Stop"
$root = "C:\SBSEGVerifierVM"
$sharedWorker = "Z:\vm\oem\worker.ps1"

# This script runs at every automatic login through the HKLM Run entry created
# by bootstrap.ps1. The repository share can appear a little later than login.
$deadline = (Get-Date).AddMinutes(5)
while (-not (Test-Path $sharedWorker)) {
    # Dockur normally creates Z:. Reconnect it if Windows has not done so yet.
    if (-not (Test-Path "Z:\")) {
        & net.exe use Z: \\host.lan\Data /persistent:yes | Out-Null
    }
    if ((Get-Date) -ge $deadline) {
        throw "repository share did not become ready: $sharedWorker"
    }
    Start-Sleep -Seconds 2
}

$localWorker = "$root\worker.ps1"

# Keep this launcher alive as a tiny supervisor. If the worker crashes or is
# stopped, copy the newest repository version and start it again after a short
# delay. This also makes worker edits take effect without reinstalling Windows.
while ($true) {
    try {
        Copy-Item -Force $sharedWorker $localWorker
        Write-Host "Starting SBSEG verifier worker"
        # Start the worker in its own visible console. This supervisor remains
        # hidden, waits for that process, and restarts it when it exits.
        $worker = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList @(
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $localWorker
            ) `
            -WindowStyle Normal `
            -PassThru
        $worker.WaitForExit()
        Write-Warning "SBSEG verifier worker exited with code $($worker.ExitCode)"
    } catch {
        Write-Warning "Could not start SBSEG verifier worker: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds 2
}
