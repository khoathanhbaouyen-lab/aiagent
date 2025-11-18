#!/bin/bash
# =========================================================
# Script chạy TRỰC TIẾP trên Ubuntu Server
# Copy toàn bộ script này và chạy trên server
# =========================================================

set -e  # Exit on error

echo "=============================================="
echo "  🚀 OSHIMA AI - Deploy từ GitHub"
echo "=============================================="
echo ""

# 1. Tạo thư mục AI Agent
echo "📁 [1/6] Tạo thư mục AI Agent..."
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"
echo "✅ Thư mục: $(pwd)"
echo ""

# 2. Clone hoặc pull từ GitHub
echo "📥 [2/6] Lấy code từ GitHub..."
if [ -d ".git" ]; then
    echo "   Repository đã tồn tại, đang pull code mới..."
    git pull origin main || git pull origin master
else
    echo "   Đang clone repository..."
    git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .
fi
echo "✅ Code đã được cập nhật"
echo ""

# 3. Chạy script setup
echo "⚙️ [3/6] Chạy script setup môi trường..."
chmod +x setup_server.sh
bash setup_server.sh
echo ""

# 4. Nhắc nhở cấu hình .env
echo "📝 [4/6] Cấu hình file .env..."
if [ ! -f ".env" ]; then
    echo "⚠️  File .env chưa tồn tại, đang tạo..."
    # File .env đã được tạo bởi setup_server.sh
fi

echo ""
echo "⚠️  QUAN TRỌNG: Bạn cần chỉnh sửa file .env với thông tin thực tế!"
echo "   Chạy lệnh: nano .env"
echo "   Cập nhật: OPENAI_API_KEY, CHAINLIT_AUTH_SECRET, v.v."
echo ""
read -p "Nhấn Enter sau khi đã cấu hình .env xong..."

# 5. Tạo systemd service
echo "🔧 [5/6] Tạo systemd service..."
sudo tee /etc/systemd/system/oshima-ai.service > /dev/null << 'EOF'
[Unit]
Description=OSHIMA AI Application
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/AI Agent
Environment="PATH=/home/ubuntu/AI Agent/.venv311/bin"
ExecStart=/home/ubuntu/AI Agent/.venv311/bin/python run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable oshima-ai
echo "✅ Systemd service đã được tạo"
echo ""

# 6. Khởi động service
echo "🚀 [6/6] Khởi động service..."
sudo systemctl start oshima-ai
sleep 3
sudo systemctl status oshima-ai --no-pager
echo ""

# Hoàn thành
echo "=============================================="
echo "  ✅ Deploy hoàn tất!"
echo "=============================================="
echo ""
echo "🔗 Truy cập ứng dụng:"
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "   - Chainlit UI: http://${SERVER_IP}:8000"
echo "   - API Server: http://${SERVER_IP}:8001"
echo ""
echo "📋 Các lệnh hữu ích:"
echo "   - Xem logs: sudo journalctl -u oshima-ai -f"
echo "   - Restart: sudo systemctl restart oshima-ai"
echo "   - Stop: sudo systemctl stop oshima-ai"
echo "   - Status: sudo systemctl status oshima-ai"
echo ""
echo "=============================================="

