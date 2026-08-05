$ErrorActionPreference = "Stop"

# The repository is copied from Z: before prepare/run. Installers and API files
# stay on the Windows disk and never use the shared folder for signaling.
$root = "C:\SBSEGVerifierVM"
$repo = "$root\repo"
$sharedRoot = "Z:\"
$installerRoot = "$root\installers"
$inputDb = "$root\input.db"
$outputDb = "$root\output.db"
$screenshotsZip = "$root\screenshots.zip"

# HttpListener does not provide convenience methods for JSON or files, so these
# small helpers write complete synchronous responses and close them immediately.
function Send-Json($Context, [int]$Status, $Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 10 -Compress))
    $Context.Response.StatusCode = $Status
    $Context.Response.ContentType = "application/json"
    $Context.Response.ContentLength64 = $bytes.Length
    $Context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $Context.Response.Close()
}

function Write-Log([string]$Message) {
    Write-Host $Message
}

function Read-Json($Request) {
    $reader = [IO.StreamReader]::new($Request.InputStream, $Request.ContentEncoding)
    $body = $reader.ReadToEnd()
    $reader.Close()
    return $body | ConvertFrom-Json
}

function Save-Body($Request, [string]$Path) {
    $file = [IO.File]::Create($Path)
    $Request.InputStream.CopyTo($file)
    $file.Close()
}

function Send-File($Context, [string]$Path, [string]$ContentType) {
    if (-not (Test-Path $Path)) {
        Send-Json $Context 404 @{ ok = $false; error = "result is not available" }
        return
    }
    $bytes = [IO.File]::ReadAllBytes($Path)
    $Context.Response.StatusCode = 200
    $Context.Response.ContentType = $ContentType
    $Context.Response.ContentLength64 = $bytes.Length
    $Context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $Context.Response.Close()
}

function Sync-Repository {
    # Mirror source into a normal Windows directory. Running tools directly on
    # the Samba-backed Z: drive is slower and can confuse file watching/locking.
    Write-Log "Synchronizing repository"
    New-Item -ItemType Directory -Force -Path $repo | Out-Null
    & robocopy.exe $sharedRoot $repo /MIR /R:2 /W:1 /XD .git .vm .venv __pycache__ | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
}

function Get-Uv {
    # uv is VM infrastructure, not a verifier installer. Download it once and
    # reuse the executable on the persistent Windows disk.
    $uv = "$root\bin\uv.exe"
    if (-not (Test-Path $uv)) {
        Write-Log "Downloading uv"
        New-Item -ItemType Directory -Force -Path "$root\bin" | Out-Null
        $archive = "$root\uv.zip"
        Invoke-WebRequest -UseBasicParsing `
            -Uri "https://github.com/astral-sh/uv/releases/download/0.11.25/uv-x86_64-pc-windows-msvc.zip" `
            -OutFile $archive
        Expand-Archive -Force $archive "$root\bin"
        Remove-Item -Force $archive
        Write-Log "Finished downloading uv"
    }
    if (-not (Test-Path $uv)) {
        throw "uv.exe could not be installed"
    }
    return $uv
}

function Import-TestCertificates {
    # The desktop readers must trust the same repository test roots used when
    # generating the signed PDFs.
    Write-Log "Importing test certificates"
    Get-ChildItem "$repo\src\certs\cert-*" | Where-Object {
        $_.Extension -in @(".cer", ".der")
    } | ForEach-Object {
        & certutil.exe -addstore -f Root $_.FullName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "failed to trust certificate $($_.Name)"
        }
    }
}

function Configure-Readers {
    Write-Log "Configuring desktop readers"
    # Adobe must use the Windows certificate store used above.
    foreach ($product in @("Adobe Acrobat", "Acrobat Reader")) {
        $base = "HKCU\Software\Adobe\$product\DC"
        reg.exe add "$base\Security\cASPKI\cMSCAPI_DirectoryProvider" /v iMSStoreTrusted /t REG_DWORD /d 0x62 /f | Out-Null
        reg.exe add "$base\Security\PPKHandler" /v bCertStoreImportEnable /t REG_DWORD /d 1 /f | Out-Null
    }

    # Edge first-run dialogs block GUI automation.
    reg.exe add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v HideFirstRunExperience /t REG_DWORD /d 1 /f | Out-Null
    reg.exe add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v BrowserSignin /t REG_DWORD /d 0 /f | Out-Null
    reg.exe add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v SyncDisabled /t REG_DWORD /d 1 /f | Out-Null
}

function Install-Reader($Installer) {
    # Existing applications are left untouched. A different version is only
    # reported later as a warning; it does not trigger reinstallation.
    Write-Log "Starting installation: $($Installer.slug)"
    try {
        if (Test-Path $Installer.exe) {
            Write-Log "$($Installer.slug) is already installed"
            return
        }
        if (-not $Installer.available) {
            throw "installer was not supplied: $($Installer.slug)"
        }
        $path = "$installerRoot\$($Installer.slug)$($Installer.installer_extension)"
        $program = $path
        $arguments = @($Installer.install_args)
        if ($Installer.installer_extension -eq ".msi") {
            $program = "msiexec.exe"
            $arguments = @("/i", $path) + $arguments
        }
        $process = Start-Process `
            -FilePath $program `
            -ArgumentList $arguments `
            -Wait `
            -PassThru
        if ($process.ExitCode -notin @(0, 1641, 3010)) {
            throw "$($Installer.slug) installer exited with $($process.ExitCode)"
        }
        if (-not (Test-Path $Installer.exe)) {
            throw "$($Installer.slug) executable was not found after installation"
        }
    } finally {
        Write-Log "Installation ended: $($Installer.slug)"
    }
}

function Prepare-Guest($Request) {
    # prepare is the only operation that creates/updates the Python environment
    # and installs applications. run assumes prepare has already succeeded.
    Sync-Repository
    $uv = Get-Uv
    Write-Log "Preparing Python environment"
    # uv writes progress to stderr. PowerShell must not turn those normal
    # progress lines into terminating errors while we stream them to the CLI.
    $ErrorActionPreference = "Continue"
    & $uv sync --locked --no-dev --project $repo 2>&1 | ForEach-Object {
        Write-Log "$_"
    }
    $uvExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($uvExitCode -ne 0) {
        throw "uv sync failed with exit code $uvExitCode"
    }
    Import-TestCertificates
    Configure-Readers

    $warnings = @()
    foreach ($installer in $Request.installers) {
        Install-Reader $installer
        $actual = [Diagnostics.FileVersionInfo]::GetVersionInfo($installer.exe).FileVersion
        if ($actual -ne $installer.version) {
            $warnings += "$($installer.slug) version differs: expected $($installer.version), got $actual"
        }
    }
    return $warnings
}

function Run-Readers($Request) {
    # Use the repository's normal database path so the existing verifier code
    # needs no VM-specific database handling.
    Sync-Repository
    if (-not (Test-Path $inputDb)) {
        throw "database was not uploaded"
    }

    $database = "$repo\src\signed_files.db"
    Copy-Item -Force $inputDb $database
    Remove-Item -Force -ErrorAction SilentlyContinue $outputDb, $screenshotsZip
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$repo\src\screenshots"
    $uv = Get-Uv

    foreach ($verifier in $Request.verifiers) {
        # Every selected reader updates the same database sequentially.
        if (-not (Test-Path $verifier.exe)) {
            throw "$($verifier.slug) is not installed"
        }
        Write-Log "Starting verifier: $($verifier.slug)"
        try {
            $arguments = @(
                "run", "--project", $repo, "python", "$repo\src\main.py",
                "run", $verifier.slug, "--mode", $Request.mode
            )
            # Verifier commands can also write ordinary status output to
            # stderr; stream it and use the process exit code for failure.
            $ErrorActionPreference = "Continue"
            & $uv @arguments 2>&1 | ForEach-Object {
                Write-Log "$_"
            }
            $verifierExitCode = $LASTEXITCODE
            $ErrorActionPreference = "Stop"
            if ($verifierExitCode -ne 0) {
                throw "$($verifier.slug) verification failed with exit code $verifierExitCode"
            }
        } finally {
            Write-Log "Verifier ended: $($verifier.slug)"
        }
    }

    Copy-Item -Force $database $outputDb
    # Screenshots are returned separately because the host expects their normal
    # src/screenshots directory layout.
    if ((Test-Path "$repo\src\screenshots") -and (Get-ChildItem "$repo\src\screenshots")) {
        Compress-Archive -Force -Path "$repo\src\screenshots\*" -DestinationPath $screenshotsZip
    }
}

while (-not (Test-Path $sharedRoot)) {
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $installerRoot | Out-Null

# These HKCU values must be applied by the interactive auto-login user.
reg.exe add "HKCU\Control Panel\Desktop" /v LogPixels /t REG_DWORD /d 96 /f | Out-Null
reg.exe add "HKCU\Control Panel\Desktop" /v Win8DpiScaling /t REG_DWORD /d 1 /f | Out-Null
Add-Type -AssemblyName System.Windows.Forms

$listener = [Net.HttpListener]::new()
$listener.Prefixes.Add("http://+:8765/")
$listener.Start()
Write-Host "SBSEG verifier worker listening on port 8765"

# The API is deliberately single-threaded: prepare and run are synchronous, and
# the host performs only one VM operation at a time.
while ($true) {
    $context = $listener.GetContext()
    $method = $context.Request.HttpMethod
    $path = $context.Request.Url.AbsolutePath.TrimEnd([char]"/")

    try {
        # Readiness also reports the desktop values checked by `vm start`.
        if ($method -eq "GET" -and $path -eq "/health") {
            $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $dpi = (Get-ItemProperty "HKCU:\Control Panel\Desktop" -Name LogPixels).LogPixels
            Send-Json $context 200 @{
                ok = $true
                message = "ready"
                warnings = @()
                user = $env:USERNAME
                dpi = $dpi
                screen_width = $screen.Width
                screen_height = $screen.Height
            }
        } elseif ($method -eq "PUT" -and $path.StartsWith("/installers/")) {
            # Keep the extension because MSI packages must run through msiexec.
            $name = $path.Substring("/installers/".Length)
            if ($name -notmatch "^[a-z_]+\.(exe|msi)$") {
                throw "invalid installer name"
            }
            Save-Body $context.Request "$installerRoot\$name"
            Send-Json $context 200 @{ ok = $true; message = "installer uploaded"; warnings = @() }
        } elseif ($method -eq "PUT" -and $path -eq "/database") {
            # The next /run copies this raw SQLite file into the local repo.
            Save-Body $context.Request $inputDb
            Send-Json $context 200 @{ ok = $true; message = "database uploaded"; warnings = @() }
        } elseif ($method -eq "POST" -and $path -eq "/prepare") {
            # The JSON body contains installer paths, arguments, and versions.
            $warnings = @(Prepare-Guest (Read-Json $context.Request))
            Send-Json $context 200 @{ ok = $true; message = "prepare completed"; warnings = $warnings }
        } elseif ($method -eq "POST" -and $path -eq "/run") {
            # This response remains open until every selected verifier finishes.
            Run-Readers (Read-Json $context.Request)
            Send-Json $context 200 @{ ok = $true; message = "run completed"; warnings = @() }
        } elseif ($method -eq "GET" -and $path -eq "/database") {
            # Results exist only after a fully successful /run.
            Send-File $context $outputDb "application/vnd.sqlite3"
        } elseif ($method -eq "GET" -and $path -eq "/screenshots") {
            Send-File $context $screenshotsZip "application/zip"
        } else {
            Send-Json $context 404 @{ ok = $false; error = "endpoint not found" }
        }
    } catch {
        Send-Json $context 500 @{ ok = $false; error = $_.Exception.Message }
    }
}
