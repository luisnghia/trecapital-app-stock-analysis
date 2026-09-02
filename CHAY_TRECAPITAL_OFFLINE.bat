@echo off
setlocal
cd /d "%~dp0"
title Trecapital - Phan tich chuyen sau doanh nghiep

if not exist "data_cache" mkdir "data_cache"

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Goi offline nay can Python 3.11 da cai tren Windows.
    pause
    exit /b 1
)

python -c "import streamlit, pandas" >nul 2>nul
if errorlevel 1 (
    echo Chua co du thu vien. Dang cai tu goi wheel offline kem theo...
    call CAI_THU_VIEN_MOT_LAN.bat /silent
    if errorlevel 1 (
        echo [LOI] Khong cai duoc thu vien offline.
        pause
        exit /b 1
    )
)

echo Dang khoi dong Trecapital offline...
python -m streamlit run app.py --server.headless false

endlocal
