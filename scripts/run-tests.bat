@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "ROOT_DIR=%~dp0.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"
if "%CONDA_ENV%"=="" set "CONDA_ENV=monitor_backend"
set "RUN_BACKEND=1"
set "RUN_FRONTEND=1"
set "INSTALL=0"

:parse_args
if "%~1"=="" goto run_tasks
set "KNOWN=0"
if /I "%~1"=="all" (
  set "RUN_BACKEND=1"
  set "RUN_FRONTEND=1"
  set "KNOWN=1"
)
if /I "%~1"=="backend" (
  set "RUN_BACKEND=1"
  set "RUN_FRONTEND=0"
  set "KNOWN=1"
)
if /I "%~1"=="frontend" (
  set "RUN_BACKEND=0"
  set "RUN_FRONTEND=1"
  set "KNOWN=1"
)
if "%~1"=="--install" (
  set "INSTALL=1"
  set "KNOWN=1"
)
if "%~1"=="-h" goto usage
if "%~1"=="--help" goto usage
if "%KNOWN%"=="0" (
  echo Invalid argument: %~1
  echo Usage: %~nx0 [all^|backend^|frontend] [--install]
  exit /b 2
)
shift /1
goto parse_args

:run_tasks
if "%RUN_BACKEND%"=="1" (
  where conda >nul 2>&1 || (
    echo Required command not found: conda
    exit /b 1
  )
  if "%INSTALL%"=="1" (
    call conda run --no-capture-output -n "%CONDA_ENV%" python -m pip install -r "%ROOT_DIR%\backend\requirements.txt" pytest
    if errorlevel 1 exit /b 1
  )
  set "PYTHONPATH=%ROOT_DIR%\backend"
  call conda run --no-capture-output -n "%CONDA_ENV%" python -m pytest "%ROOT_DIR%\backend\tests" -q
  if errorlevel 1 exit /b 1
  call conda run --no-capture-output -n "%CONDA_ENV%" python -m compileall -q "%ROOT_DIR%\backend"
  if errorlevel 1 exit /b 1
)

if "%RUN_FRONTEND%"=="1" (
  where node >nul 2>&1 || (
    echo Required command not found: node
    exit /b 1
  )
  where npm >nul 2>&1 || (
    echo Required command not found: npm
    exit /b 1
  )
  pushd "%ROOT_DIR%\frontend" || exit /b 1
  if "%INSTALL%"=="1" (
    call npm ci
    if errorlevel 1 (
      popd
      exit /b 1
    )
  )
  if not exist "node_modules\.bin\vue-tsc.cmd" (
    echo Frontend dependencies are missing; rerun with --install.
    popd
    exit /b 1
  )
  call npm run build
  if errorlevel 1 (
    popd
    exit /b 1
  )
  call npm run test:e2e
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)

exit /b 0

:usage
echo Usage: %~nx0 [all^|backend^|frontend] [--install]
echo Set CONDA_ENV to select the backend Conda environment.
exit /b 0
