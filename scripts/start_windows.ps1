$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Host.UI.RawUI.WindowTitle = 'Bible Engine // Oracle'
$Log = Join-Path $Root 'bible-engine-startup.log'
Set-Content $Log @('Bible Engine startup log',('Started: '+(Get-Date).ToString('s')),('Folder: '+$Root))

function Step([string]$Label,[scriptblock]$Action){
  Write-Host $Label -ForegroundColor DarkYellow
  Add-Content $Log ('>>> '+$Label)

  # Native programs legitimately write diagnostics/progress to stderr. Under
  # ErrorActionPreference=Stop PowerShell can otherwise abort after the first
  # stderr line and hide the actual Python traceback. Let the native process
  # finish, preserve its complete output, then judge only its exit code.
  $oldPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  try {
    & $Action 2>&1 | Tee-Object -FilePath $Log -Append
    $rc=$LASTEXITCODE
  } finally {
    $ErrorActionPreference=$oldPreference
  }
  if($rc -ne 0){ throw "$Label failed with exit code $rc." }
}

function Probe([scriptblock]$Action){
  # Preflight checkers use non-zero exit codes to mean "not installed yet" and
  # may explain that status on stderr. That is expected control flow, not a
  # PowerShell exception. Suppress their output, allow the process to finish,
  # and return only its native exit code to the caller.
  $oldPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  try {
    & $Action *> $null
    $rc=$LASTEXITCODE
  } finally {
    $ErrorActionPreference=$oldPreference
  }
  return [int]$rc
}

function Fail([string]$Message){
  Write-Host ''
  Write-Host '========================================' -ForegroundColor Red
  Write-Host '         BIBLE ENGINE FAILED' -ForegroundColor Red
  Write-Host '========================================' -ForegroundColor Red
  Write-Host $Message -ForegroundColor Red
  Add-Content $Log ('ERROR: '+$Message)
  if(Test-Path $Log){
    Write-Host ''
    Write-Host 'Last startup log lines:' -ForegroundColor DarkYellow
    Get-Content $Log -Tail 35 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
  }
  Write-Host "Log: $Log"
  try{Start-Process notepad.exe -ArgumentList ('"'+$Log+'"')|Out-Null}catch{}
  Write-Host ''
  Write-Host 'This window will stay open.'
}

Write-Host ''
Write-Host '╔══════════════════════════════════════╗' -ForegroundColor DarkYellow
Write-Host '║       BIBLE ENGINE // ORACLE        ║' -ForegroundColor DarkYellow
Write-Host '╚══════════════════════════════════════╝' -ForegroundColor DarkYellow
Write-Host "Folder: $Root"
Write-Host 'Model: gpt-5.6-luna // medium'
Write-Host ''

try{
  $py=Get-Command py -ErrorAction SilentlyContinue
  if(-not $py){$py=Get-Command python -ErrorAction SilentlyContinue}
  if(-not $py){throw 'Python 3.11+ was not found.'}
  $pyCommand=$py.Source

  Write-Host 'Checking Python...'
  & $pyCommand --version

  $venv=Join-Path $Root '.venv\Scripts\python.exe'
  if(-not(Test-Path $venv)){
    Step 'Creating local Python environment...' {& $pyCommand -m venv .venv}
  }
  Step 'Installing/updating Bible Engine...' {& $venv -m pip install -q -e '.[dev]'}

  $codex=Get-Command codex -ErrorAction SilentlyContinue
  if(-not $codex){
    $npm=Get-Command npm -ErrorAction SilentlyContinue
    if(-not $npm){throw 'Codex is missing and Node.js/npm is not installed.'}
    Step 'Installing Codex CLI...' {& $npm.Source install -g '@openai/codex@latest'}
    $env:Path=$env:Path+';'+(Join-Path $env:APPDATA 'npm')
  }
  Step 'Resolving native Codex executable...' {& $venv 'scripts\check_codex.py'}

  $corpusProbe = Probe {& $venv 'scripts\check_corpus.py'}
  if($corpusProbe -ne 0){
    Step 'Downloading public-domain Bible sources...' {& $venv 'scripts\fetch_public_domain.py'}
    Step 'Indexing Canon + Deuterocanon...' {& $venv 'scripts\seed_public_domain.py'}
    Step 'Verifying Bible corpus...' {& $venv 'scripts\check_corpus.py'}
  }else{
    Write-Host 'Bible corpus ready.' -ForegroundColor DarkGreen
  }

  $referenceProbe = Probe {& $venv 'scripts\check_reference_library.py'}
  if($referenceProbe -ne 0){
    Step 'Indexing Second Temple reference shelf...' {& $venv 'scripts\seed_reference_library.py'}
  }else{
    Write-Host 'Reference shelf ready.' -ForegroundColor DarkGreen
  }

  # The deep OSHB/Tischendorf corpus is the authoritative original-language source.
  # Build it first, then derive the compact Languages drawer cache from the same data.
  $deepOriginalProbe = Probe {& $venv 'scripts\check_original_lab.py'}
  if($deepOriginalProbe -ne 0){
    Step 'Installing deep Hebrew + Aramaic + Greek Lab + BDB/LXX witnesses...' {& $venv 'scripts\seed_original_lab.py'}
    Step 'Verifying deep Original Language Lab...' {& $venv 'scripts\check_original_lab.py'}
  }else{
    Write-Host 'Deep Original Language Lab ready.' -ForegroundColor DarkGreen
  }

  $compactOriginalProbe = Probe {& $venv 'scripts\check_original_languages.py'}
  if($compactOriginalProbe -ne 0){
    Step 'Synchronizing compact Languages drawer from deep corpus...' {& $venv 'scripts\sync_compact_originals.py'}
    Step 'Verifying compact Languages drawer...' {& $venv 'scripts\check_original_languages.py'}
  }else{
    Write-Host 'Compact Languages drawer ready.' -ForegroundColor DarkGreen
  }

  $graphProbe = Probe {& $venv 'scripts\check_intertext_graph.py'}
  if($graphProbe -ne 0){
    Step 'Building Intertextual Graph...' {& $venv 'scripts\seed_intertext_graph.py'}
    Step 'Verifying Intertextual Graph...' {& $venv 'scripts\check_intertext_graph.py'}
  }else{
    Write-Host 'Intertextual Graph ready.' -ForegroundColor DarkGreen
  }

  $witnessProbe = Probe {& $venv 'scripts\check_textual_witnesses.py'}
  if($witnessProbe -ne 0){
    Step 'Installing Textual Witness editions...' {& $venv 'scripts\seed_textual_witnesses.py'}
    Step 'Verifying Textual Witness editions...' {& $venv 'scripts\check_textual_witnesses.py'}
  }else{
    Write-Host 'Textual Witness Lab ready.' -ForegroundColor DarkGreen
  }

  Step 'Checking Oracle application...' {& $venv -c "import app.main; print('Application import OK')"}

  $listener=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  if($listener){throw 'Port 8000 is already in use. Close the older Bible Engine terminal first.'}

  Write-Host ''
  Write-Host 'ORACLE ONLINE' -ForegroundColor Green
  Write-Host 'http://127.0.0.1:8000'
  Write-Host 'Keep this terminal open. Ctrl+C stops the Oracle.'
  Write-Host ''

  Start-Process -FilePath (Join-Path $Root '.venv\Scripts\pythonw.exe') -ArgumentList 'scripts\open_browser.py' -WorkingDirectory $Root|Out-Null
  $old=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  try {
    & $venv -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    $rc=$LASTEXITCODE
  } finally {
    $ErrorActionPreference=$old
  }
  if($rc -ne 0){throw "Bible Engine server exited with code $rc."}
}catch{
  Fail $_.Exception.Message
}
