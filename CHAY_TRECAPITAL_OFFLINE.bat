@echo off
setlocal
cd /d "%~dp0"
title Trecapital - Phan tich chuyen sau doanh nghiep

if not exist "data_cache" mkdir "data_cache"

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Goi Lite nay can Python 3.11 64-bit da cai tren Windows.
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [LOI] Can Python 3.11. Hien tai lenh python dang tro toi phien ban khac.
    python --version
    pause
    exit /b 1
)

python -c "import streamlit, pandas, requests, plotly, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo [CAN CAI THU VIEN] May chua co day du thu vien Trecapital.
    echo Dang chay trinh cai dat mot lan...
    call CAI_THU_VIEN_MOT_LAN.bat /silent
    if errorlevel 1 (
        echo [LOI] Khong cai duoc thu vien.
        echo Goi Lite khong kem Python/offline_wheels de giam dung luong.
        echo Neu may dang offline, hay ket noi Internet mot lan de cai requirements hoac dung moi truong Trecapital da cai truoc do.
        pause
        exit /b 1
    )
)

echo Dang khoi dong Trecapital local...
python -m streamlit run app.py --server.headless false

endlocal
