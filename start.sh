#!/bin/bash
# Script khởi động cho Linux/Mac

cd "$(dirname "$0")"

# Kích hoạt venv nếu có
if [ -f ".venv311/bin/activate" ]; then
    source .venv311/bin/activate
fi

# Chạy run.py
python run.py
