# Optional PowerShell launcher:  powershell -ExecutionPolicy Bypass -File run.ps1
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$main = Join-Path $here "main.py"
if (-not (Test-Path $main)) { Write-Host "main.py not found next to run.ps1"; Read-Host "Press Enter"; exit 1 }
$env:HAFT_APP_ROOT = $here
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $main } else { & python $main }
if ($LASTEXITCODE -ne 0) { Read-Host "Press Enter" }
