#!/bin/bash
# =========================================================
# Script deploy với password - Chạy trên máy local
# Usage: bash deploy_with_password.sh [IP] [USER] [PASSWORD]
# Example: bash deploy_with_password.sh 124.158.10.34 ubuntu mypassword
# =========================================================

set -e

SERVER_IP="${1:-124.158.10.34}"
SERVER_USER="${2:-ubuntu}"
SERVER_PASS="${3}"

if [ -z "$SERVER_PASS" ]; then
    echo "❌ Vui lòng cung cấp password!"
    echo ""
    echo "Usage: bash deploy_with_password.sh [IP] [USER] [PASSWORD]"
    echo "Example: bash deploy_with_password.sh 124.158.10.34 ubuntu mypassword"
    exit 1
fi

# Check sshpass
if ! command -v sshpass &> /dev/null; then
    echo "📦 Đang cài đặt sshpass..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y sshpass
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        echo "⚠️  Trên Windows, vui lòng cài đặt sshpass thủ công hoặc dùng WSL"
        exit 1
    fi
fi

export SSHPASS="$SERVER_PASS"

echo "=============================================="
echo "  🚀 Deploy lên server ${SERVER_IP}"
echo "=============================================="
echo ""

# Test connection
echo "[1/6] Kiểm tra kết nối..."
sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "echo '✅ Kết nối thành công'"
echo ""

# Create directory and clone
echo "[2/6] Tạo thư mục và clone code..."
sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    mkdir -p ~/"AI Agent"
    cd ~/"AI Agent"
    if [ -d ".git" ]; then
        echo "📥 Đang cập nhật code..."
        git pull origin main || git pull origin master
    else
        echo "📥 Đang clone từ GitHub..."
        git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .
    fi
    echo "✅ Code đã được cập nhật"
ENDSSH
echo ""

# Run setup
echo "[3/6] Chạy script setup (mất khoảng 10-15 phút)..."
sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    cd ~/"AI Agent"
    chmod +x setup_server.sh
    bash setup_server.sh
ENDSSH
echo ""

# Create systemd service
echo "[4/6] Tạo systemd service..."
sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << ENDSSH
    sudo tee /etc/systemd/system/oshima-ai.service > /dev/null << 'EOFSERVICE'
[Unit]
Description=OSHIMA AI Application
After=network.target postgresql.service

[Service]
Type=simple
User=${SERVER_USER}
WorkingDirectory=/home/${SERVER_USER}/AI Agent
Environment="PATH=/home/${SERVER_USER}/AI Agent/.venv311/bin"
ExecStart=/home/${SERVER_USER}/AI Agent/.venv311/bin/python run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE
    sudo systemctl daemon-reload
    sudo systemctl enable oshima-ai
    echo "✅ Service đã được tạo"
ENDSSH
echo ""

# Check .env file
echo "[5/6] Kiểm tra file .env..."
sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    cd ~/"AI Agent"
    if [ ! -f ".env" ]; then
        echo "⚠️  File .env chưa tồn tại, đã được tạo bởi setup script"
    else
        echo "✅ File .env đã tồn tại"
    fi
ENDSSH
echo ""

# Final instructions
echo "[6/6] Hoàn tất!"
echo ""
echo "=============================================="
echo "  ✅ Deploy hoàn tất!"
echo "=============================================="
echo ""
echo "📝 BƯỚC TIẾP THEO - Quan trọng:"
echo ""
echo "1. SSH vào server:"
echo "   ssh ${SERVER_USER}@${SERVER_IP}"
echo ""
echo "2. Cấu hình .env file:"
echo "   cd ~/'AI Agent'"
echo "   nano .env"
echo ""
echo "   Cập nhật:"
echo "   - OPENAI_API_KEY=sk-your-actual-key"
echo "   - CHAINLIT_AUTH_SECRET=your-secret-key"
echo ""
echo "3. Khởi động service:"
echo "   sudo systemctl start oshima-ai"
echo "   sudo systemctl status oshima-ai"
echo ""
echo "4. Truy cập:"
echo "   - Chainlit: http://${SERVER_IP}:8000"
echo "   - API: http://${SERVER_IP}:8001"
echo ""
echo "=============================================="

