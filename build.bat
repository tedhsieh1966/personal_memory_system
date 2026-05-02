@echo off
setlocal

echo ============================================================
echo  Personal Memory System -- Release Build
echo ============================================================
echo.

echo [1/3] Building executables (PyInstaller)...
.venv\Scripts\python.exe build.py
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)
echo.

echo [2/3] Assembling deployment package...
.venv\Scripts\python.exe build_installer.py
if %errorlevel% neq 0 (
    echo ERROR: Installer assembly failed.
    exit /b 1
)
echo.

echo [3/3] Done.
echo.
echo Output:
echo   dist\pms_server.exe     -- HTTP server (bundled inside installer)
echo   dist\pms_editor.exe     -- desktop editor (bundled inside installer)
echo   dist\pms_manager.exe    -- CLI service manager (bundled inside installer)
echo   dist\pms_installer.exe  -- run this on the target machine to install PMS
echo.
echo To deploy:
echo   1. Copy dist\pms_installer.exe to the target machine
echo   2. Run pms_installer.exe as Administrator
echo.
endlocal
