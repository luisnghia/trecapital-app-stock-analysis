@echo off
setlocal
cd /d "%~dp0"
title Cai thu vien Trecapital mot lan

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai Python 3.11 truoc.
    pause
    exit /b 1
)

echo Dang cai thu vien theo requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai. Kiem tra ket noi Internet va thu lai.
    pause
    exit /b 1
)

echo.
echo Cai dat hoan tat. Tu lan sau chi can double-click CHAY_TRECAPITAL_OFFLINE.bat.
pause
endlocal
