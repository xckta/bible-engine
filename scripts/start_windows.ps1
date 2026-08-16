$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Host.UI.RawUI.WindowTitle = 'Bible Engine'
$Log = Join-Path $Root 'bible-engine-startup.log'

function Write-Log([string]$Text) {
    $Text | Tee-Object -FilePath $Log -Append
}

function Fail([string]$Message) {
    if ([string]::IsNullOrWhiteSpace($Message)) { $Message = 'Unknown startup error. See the startup log.' }
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Red
    Write-Host '         BIBLE ENGINE FAILED' -ForegroundColor Red
    Write-Host '========================================' -ForegroundColor Red
    Write-Host $Message -ForegroundColor Red
    Write-Host ''
    Write-Host "Log: $Log"
    Add-Content -Path $Log -Value "ERROR: $Message"
    try { Start-Process notepad.exe -ArgumentList ('"' + $Log + '"') | Out-Null } catch {}
    Write-Host ''
    Write-Host 'This window will stay open. Copy the error or the log into ChatGPT.'
    return $false
}

function Invoke-Captured([string]$Label, [string]$CommandLine, [int]$TimeoutSeconds = 10) {
    Write-Host $Label
    Add-Content -Path $Log -Value (">>> " + $CommandLine)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $env:ComSpec
    $psi.Arguments = '/d /s /c "' + $CommandLine + '"'
    $psi.WorkingDirectory = $Root
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()

    if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
        try { $p.Kill() } catch {}
        throw "$Label timed out after $TimeoutSeconds seconds."
    }

    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    if ($stdout) { Add-Content -Path $Log -Value $stdout.TrimEnd() }
    if ($stderr) { Add-Content -Path $Log -Value $stderr.TrimEnd() }

    if ($p.ExitCode -ne 0) {
        $detail = ($stderr + "`n" + $stdout).Trim()
        if (-not $detail) { $detail = "exit code $($p.ExitCode)" }
        throw "$Label failed: $detail"
    }

    return ($stdout + "`n" + $stderr).Trim()
}

function Invoke-Visible([string]$Label, [scriptblock]$Action) {
    Write-Host $Label
    Add-Content -Path $Log -Value (">>> " + $Label)
    & $Action 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Set-Content -Path $Log -Value @(
    'Bible Engine startup log',
    ('Started: ' + (Get-Date).ToString('s')),
    ('Folder: ' + $Root)
)

Write-Host ''
Write-Host '========================================'
Write-Host '             BIBLE ENGINE'
Write-Host '========================================'
Write-Host "Folder: $Root"
Write-Host 'Model: gpt-5.6-luna'
Write-Host 'Reasoning: medium'
Write-Host ''

try {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $py) { throw 'Python 3.11 or newer was not found on PATH.' }

    $pyCommand = $py.Source
    $pythonVersion = Invoke-Captured 'Checking Python...' ('"' + $pyCommand + '" --version') 10
    Write-Host "  $pythonVersion"

    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creating local Python environment...'
        & $pyCommand -m venv .venv 2>&1 | Tee-Object -FilePath $Log -Append
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
    }

    Invoke-Visible 'Checking Python packages...' { & $venvPython -m pip install -q --upgrade pip }
    Invoke-Visible 'Installing/updating Bible Engine...' { & $venvPython -m pip install -q -e . }

    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codex) {
        Write-Host 'Codex CLI is not installed. Installing it...'
        $npm = Get-Command npm -ErrorAction SilentlyContinue
        if (-not $npm) {
            throw 'Codex CLI is required, and Node.js/npm is not installed. Install Node.js, then run this launcher again.'
        }
        & $npm.Source install -g '@openai/codex@latest' 2>&1 | Tee-Object -FilePath $Log -Append
        if ($LASTEXITCODE -ne 0) { throw 'npm could not install the Codex CLI.' }
        $env:Path = $env:Path + ';' + (Join-Path $env:APPDATA 'npm')
        $codex = Get-Command codex -ErrorAction SilentlyContinue
        if (-not $codex) { throw 'Codex installed, but Windows still cannot find the codex command. Close this window and run the launcher again.' }
    }

    Write-Host "Codex command: $($codex.Source)"
    Add-Content -Path $Log -Value ('Codex command: ' + $codex.Source)
    $codexVersion = Invoke-Captured 'Checking Codex...' 'codex --version' 10
    Write-Host "  $codexVersion"
    Write-Host '  Authentication will be used by the first real Codex request; startup no longer probes codex login status.'

    Write-Host 'Checking Bible corpus...'
    & $venvPython 'scripts\check_corpus.py' 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) {
        Invoke-Visible 'Downloading the complete WEB and ASV Bibles...' { & $venvPython 'scripts\fetch_public_domain.py' }
        Invoke-Visible 'Loading the complete Bible corpus...' { & $venvPython 'scripts\seed_public_domain.py' }
        Invoke-Visible 'Verifying the complete Bible corpus...' { & $venvPython 'scripts\check_corpus.py' }
    }

    Invoke-Visible 'Checking Bible Engine application...' { & $venvPython -c "import app.main; print('Application import OK')" }

    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 8000 is already in use. Close the older Bible Engine/server window and run this launcher again.' }

    Write-Host ''
    Write-Host 'READY' -ForegroundColor Green
    Write-Host 'Starting Bible Engine at http://127.0.0.1:8000'
    Write-Host 'Keep this window open while using the app.'
    Write-Host 'Press Ctrl+C here to stop it.'
    Write-Host ''
    Add-Content -Path $Log -Value 'Starting Uvicorn on http://127.0.0.1:8000'

    Start-Process -FilePath (Join-Path $Root '.venv\Scripts\pythonw.exe') -ArgumentList 'scripts\open_browser.py' -WorkingDirectory $Root | Out-Null

    # Uvicorn writes normal INFO startup messages to stderr. Do not merge stderr into
    # PowerShell's error stream here or ErrorActionPreference=Stop can mistake a healthy
    # server startup for an exception. Let the native process own the console directly.
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    $serverExitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference

    Add-Content -Path $Log -Value ("Uvicorn exited with code $serverExitCode at " + (Get-Date).ToString('s'))
    if ($serverExitCode -ne 0) {
        throw "Bible Engine server exited with code $serverExitCode."
    }
}
catch {
    [void](Fail $_.Exception.Message)
}
