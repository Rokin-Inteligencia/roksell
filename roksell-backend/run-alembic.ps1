# Roda migracoes Alembic (use este script se o comando 'alembic' nao for reconhecido no PowerShell)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
& $py -m alembic @args
