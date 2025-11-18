# 📖 Hướng Dẫn Deploy trên Server Ubuntu

## 🎯 Mục tiêu
Từ server Ubuntu, lấy code từ GitHub về và setup để chạy ứng dụng.

---

## ⚡ Cách 1: Chạy Script Tự Động (Khuyến nghị)

### Bước 1: SSH vào server
```bash
ssh ubuntu@124.158.10.34
```

### Bước 2: Tạo và chạy script
```bash
# Tạo file script
cat > ~/deploy.sh << 'SCRIPT_END'
#!/bin/bash
set -e

echo "🚀 Bắt đầu deploy..."

# Tạo thư mục
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"

# Clone từ GitHub
if [ -d ".git" ]; then
    git pull origin main
else
    git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .
fi

# Chạy setup
chmod +x setup_server.sh
bash setup_server.sh

# Tạo systemd service
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

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable oshima-ai

echo "✅ Hoàn tất! Nhớ cấu hình .env file trước khi start service"
SCRIPT_END

# Chạy script
chmod +x ~/deploy.sh
bash ~/deploy.sh
```

### Bước 3: Cấu hình .env
```bash
cd ~/"AI Agent"
nano .env
```

Cập nhật các giá trị:
```env
OPENAI_API_KEY=sk-your-actual-key-here
CHAINLIT_AUTH_SECRET=your-random-secret-key
```

### Bước 4: Khởi động service
```bash
sudo systemctl start oshima-ai
sudo systemctl status oshima-ai
```

---

## 🔧 Cách 2: Chạy Từng Bước Thủ Công

### Bước 1: SSH vào server
```bash
ssh ubuntu@124.158.10.34
```

### Bước 2: Tạo thư mục
```bash
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"
```

### Bước 3: Clone code từ GitHub
```bash
git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .
```

### Bước 4: Chạy script setup
```bash
chmod +x setup_server.sh
bash setup_server.sh
```

Script này sẽ tự động:
- ✅ Cài đặt Python 3.11
- ✅ Cài đặt PostgreSQL 17 + pgvector
- ✅ Tạo database `oshima_ai`
- ✅ Tạo virtual environment `.venv311`
- ✅ Cài đặt Python packages
- ✅ Tạo file `.env` mẫu
- ✅ Tạo các thư mục cần thiết

### Bước 5: Cấu hình .env
```bash
nano .env
```

Cập nhật:
```env
# OpenAI API (BẮT BUỘC)
OPENAI_API_KEY=sk-your-actual-key-here

# Chainlit (BẮT BUỘC)
CHAINLIT_AUTH_SECRET=your-random-secret-key-here

# PostgreSQL (đã được setup tự động)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oshima_ai
POSTGRES_USER=oshima_user
POSTGRES_PASSWORD=oshima_pass_2024

# Ports
API_SERVER_PORT=8001
CHAINLIT_PORT=8000
```

Lưu file: `Ctrl+X`, `Y`, `Enter`

### Bước 6: Tạo systemd service
```bash
sudo nano /etc/systemd/system/oshima-ai.service
```

Paste nội dung sau:
```ini
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
```

Lưu và thoát: `Ctrl+X`, `Y`, `Enter`

### Bước 7: Khởi động service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (tự động khởi động khi reboot)
sudo systemctl enable oshima-ai

# Start service
sudo systemctl start oshima-ai

# Kiểm tra status
sudo systemctl status oshima-ai
```

---

## 🔍 Kiểm tra và Quản lý

### Xem logs
```bash
# Xem logs real-time
sudo journalctl -u oshima-ai -f

# Xem logs gần đây (100 dòng)
sudo journalctl -u oshima-ai -n 100
```

### Quản lý service
```bash
# Restart
sudo systemctl restart oshima-ai

# Stop
sudo systemctl stop oshima-ai

# Start
sudo systemctl start oshima-ai

# Status
sudo systemctl status oshima-ai
```

### Kiểm tra ứng dụng
```bash
# Kiểm tra port 8000 (Chainlit)
curl http://localhost:8000

# Kiểm tra port 8001 (API)
curl http://localhost:8001
```

---

## 🔄 Update Code Mới

Khi có code mới trên GitHub:

```bash
cd ~/"AI Agent"
git pull origin main
sudo systemctl restart oshima-ai
```

---

## 🌐 Truy cập từ bên ngoài

Sau khi deploy thành công:

- **Chainlit UI**: http://124.158.10.34:8000
- **API Server**: http://124.158.10.34:8001

### Mở firewall (nếu cần)
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw reload
```

---

## 🐛 Xử lý lỗi

### Service không start
```bash
# Xem logs chi tiết
sudo journalctl -u oshima-ai -n 50

# Kiểm tra .env file
cat ~/"AI Agent"/.env

# Test chạy thủ công
cd ~/"AI Agent"
source .venv311/bin/activate
python run.py
```

### PostgreSQL không kết nối được
```bash
# Kiểm tra PostgreSQL
sudo systemctl status postgresql

# Test kết nối
sudo -u postgres psql -d oshima_ai -c "SELECT version();"
```

### Port đã được sử dụng
```bash
# Tìm process đang dùng port
sudo lsof -i :8000
sudo lsof -i :8001

# Kill process (thay <PID> bằng số thực tế)
sudo kill -9 <PID>
```

---

## ✅ Checklist

- [ ] SSH vào server thành công
- [ ] Đã clone code từ GitHub
- [ ] Đã chạy setup_server.sh
- [ ] Đã cấu hình .env với credentials thực tế
- [ ] Đã tạo systemd service
- [ ] Service đã start và chạy thành công
- [ ] Có thể truy cập http://124.158.10.34:8000
- [ ] Firewall đã mở ports (nếu cần)

---

**Chúc bạn deploy thành công! 🎉**

