@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"
wsl.exe --exec true >nul 2>&1
if errorlevel 1 (
  echo WSL2 nao encontrado. Veja o arquivo LEIA-ME-PRIMEIRO.txt.
  pause
  exit /b 1
)
for /f "delims=" %%P in ('wsl.exe --exec wslpath -a -u "%CD%"') do set "MIMISYNC_WSL_PROJECT=%%P"
if not defined MIMISYNC_WSL_PROJECT (
  echo Nao foi possivel localizar esta pasta no WSL.
  pause
  exit /b 1
)
wsl.exe --cd "%MIMISYNC_WSL_PROJECT%" --exec test -x .venv/bin/python
if errorlevel 1 (
  echo Prepare primeiro o backend. Consulte LEIA-ME-PRIMEIRO.txt.
  echo No Ubuntu, entre nesta pasta e execute: bash scripts/setup-backend.sh
  echo Caminho no Ubuntu: %MIMISYNC_WSL_PROJECT%
  pause
  exit /b 1
)
start "" "%~dp0Mimisync.exe"
popd
