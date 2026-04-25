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
echo   dist\pms_api.exe        -- standalone API server
echo   dist\pms_editor.exe     -- desktop editor
echo   dist\deploy\            -- deployment package (copy to target machine)
echo.
echo To deploy:
echo   1. Copy dist\deploy\ to the target machine
echo   2. Edit config.yaml
echo   3. Run install_service.bat as Administrator
echo   4. Launch pms_editor.exe to manage memories
echo.
endlocal
