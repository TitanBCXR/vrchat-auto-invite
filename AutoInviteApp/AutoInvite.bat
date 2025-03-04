@echo off
setlocal enabledelayedexpansion
title VRChat AutoInvite Launcher

echo ===================================
echo    VRChat AutoInvite Launcher
echo ===================================
echo.

REM Check if Python is installed and in PATH
echo Checking Python installation...
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
) else (
    where python3 >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=python3
    ) else (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please install Python 3.8 or higher from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        echo Press any key to exit...
        pause >nul
        exit /b 1
    )
)

echo Using %PYTHON_CMD% for execution
echo.

REM Run precheck
echo Running system checks...
%PYTHON_CMD% precheck.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Precheck failed. Please resolve the issues above before running the application.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
echo All checks passed! Starting VRChat AutoInvite...
echo.
%PYTHON_CMD% main.py

echo.
echo Application closed. Press any key to exit...
pause >nul
exit /b 0