@echo off
REM Script khởi động cả Chainlit và API Server

echo ========================================
echo  KHOI DONG HE THONG
echo ========================================
echo.

REM Kích hoạt virtual environment nếu có
if exist ".venv311\Scripts\activate.bat" (
    echo [0/4] Kich hoat virtual environment...
    call .venv311\Scripts\activate.bat
    echo   - OK! Virtual environment da active
    echo.
)

REM Kiểm tra flask-cors đã cài chưa
echo [1/4] Kiem tra dependencies...
pip show flask-cors >nul 2>&1
if errorlevel 1 (
    echo   - Cai dat flask-cors...
    pip install flask-cors
)
echo   - OK! Dependencies da san sang
echo.

REM Khởi động API Server ở cửa sổ mới
echo [2/4] Khoi dong API Server (port 8001)...
start "API Server" cmd /k "cd /d %~dp0 && if exist .venv311\Scripts\activate.bat (call .venv311\Scripts\activate.bat) && python api_server.py"
timeout /t 2 /nobreak >nul
echo   - OK! API Server dang chay
echo.

REM Khởi động Chainlit
echo [3/4] Khoi dong Chainlit (port 8000)...
echo ========================================
echo.
chainlit run app.py -w

REM Nếu Chainlit tắt, hỏi có muốn tắt API Server không
echo.
echo Chainlit da tat. Ban co muon tat API Server khong?
pause
taskkill /FI "WINDOWTITLE eq API Server*" /T /F >nul 2>&1
