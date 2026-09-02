@echo off
setlocal
cd /d "%~dp0"
title Cai thu vien Trecapital

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Goi nay can Python 3.11 da cai tren Windows.
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [LOI] Can Python 3.11.
    python --version
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

if exist "offline_wheels" (
    echo Dang cai thu vien OFFLINE tu thu muc offline_wheels...
    python -m pip install --no-index --find-links "%~dp0offline_wheels" -r requirements.txt
) else (
    echo Goi Lite khong kem offline_wheels de giam dung luong.
    echo Dang cai requirements tu PyPI. Buoc nay can Internet mot lan duy nhat.
    python -m pip install -r requirements.txt
)

if errorlevel 1 (
    echo [LOI] Cai thu vien that bai. Hay dam bao Python 3.11 64-bit va pip hoat dong.
    if /I not "%~1"=="/silent" pause
    exit /b 1
)

echo Cai dat hoan tat. Sau do app co the chay local bang CHAY_TRECAPITAL_OFFLINE.bat.
if /I not "%~1"=="/silent" pause
endlocal
exit /b 0
