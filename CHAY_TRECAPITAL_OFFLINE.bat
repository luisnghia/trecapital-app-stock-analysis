@echo off
setlocal
cd /d "%~dp0"
title Trecapital - Phan tich chuyen sau doanh nghiep

if not exist "data_cache" mkdir "data_cache"

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Hay cai Python 3.11, sau do chay lai file nay.
    pause
    exit /b 1
)

python -c "import streamlit, pandas" >nul 2>nul
if errorlevel 1 (
    echo [LOI] May chua co du thu vien Python can thiet.
    echo Chay file CAI_THU_VIEN_MOT_LAN.bat khi co Internet, sau do co the dung offline.
    pause
    exit /b 1
)

echo Dang khoi dong Trecapital offline...
python -m streamlit run app.py --server.headless false

endlocal
