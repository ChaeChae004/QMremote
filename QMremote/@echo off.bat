@echo off
title QMRemote Packaging
color 0A

echo ============================================
echo        QM Remote Monitor Packaging
echo ============================================
echo.

:: Python 경로 확인
echo Checking Python...
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH.
    pause
    exit /b
)

echo.
echo Cleaning old build/dist folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Starting PyInstaller build...
pyinstaller --onefile --windowed --clean --name QMRemote QMremote.py

echo.
echo ============================================
echo     Packaging Completed Successfully!
echo     Output File:
echo     dist\QMRemote.exe
echo ============================================
echo.

pause
