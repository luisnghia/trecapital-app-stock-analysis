@echo off
setlocal
cd /d "%~dp0"
title Cai thu vien Trecapital offline

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Goi nay can Python 3.11 da cai tren Windows.
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

if not exist "offline_wheels" (
    echo [LOI] Khong tim thay thu muc offline_wheels trong goi tai ve.
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

echo Dang cai thu vien HOAN TOAN OFFLINE tu thu muc offline_wheels...
python -m pip install --no-index --find-links "%~dp0offline_wheels" -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai thu vien offline that bai. Hay dam bao dang dung Python 3.11 64-bit.
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

echo Cai dat hoan tat.
if /I not "%~1"=="/silent" (
    echo Tu lan sau chi can double-click CHAY_TRECAPITAL_OFFLINE.bat.
    pause
)
endlocal
exit /b 0
