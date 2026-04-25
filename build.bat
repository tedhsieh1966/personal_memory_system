@echo off
echo Building PMS API executable...
.venv\Scripts\python.exe build.py

if %errorlevel% neq 0 (
    echo Error: API build failed!
    exit /b 1
)

echo Building installer package...
.venv\Scripts\python.exe build_installer.py

if %errorlevel% neq 0 (
    echo Error: Installer build failed!
    exit /b 1
)

echo Build completed successfully!
