@echo off
REM Script đơn giản - chỉ gọi run.py

cd /d %~dp0

REM Kích hoạt venv nếu có
if exist ".venv311\Scripts\activate.bat" (
    call .venv311\Scripts\activate.bat
)

REM Chạy run.py - nó sẽ khởi động cả API server và Chainlit
python run.py

pause
