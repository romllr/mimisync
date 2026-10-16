$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$linuxRoot = (& wsl.exe --exec wslpath -a -u $projectRoot).Trim()
if ($LASTEXITCODE -ne 0) { throw "Instale WSL2 Ubuntu e habilite CUDA antes de continuar." }
& wsl.exe --cd $linuxRoot --exec test -x .venv/bin/python
if ($LASTEXITCODE -ne 0) { throw "No Ubuntu/WSL, execute bash scripts/setup-backend.sh neste checkout." }
$env:MIMISYNC_WSL_PROJECT = $linuxRoot
& npm run desktop
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar o desktop. Consulte a saída acima." }
