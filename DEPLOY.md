# 🚀 Hướng Dẫn Deploy OSHIMA AI lên Ubuntu Server

## Tổng quan

Hướng dẫn này sẽ giúp bạn deploy project OSHIMA AI lên Ubuntu server tại địa chỉ `124.158.10.34`.

## 📋 Yêu cầu

- Ubuntu Server 20.04 LTS hoặc 22.04 LTS
- Quyền sudo trên server
- SSH access đến server
- Git đã được cài đặt trên máy local

---

## 🎯 Phương pháp 1: Deploy tự động (Khuyến nghị)

### Bước 1: Push code lên GitHub

```bash
# Đảm bảo bạn đang ở thư mục project
cd "I:\AI GPT"

# Thêm remote GitHub (nếu chưa có)
git remote add github https://github.com/khoathanhbaouyen-lab/aiagent.git

# Commit các thay đổi
git add .
git commit -m "Initial commit for deployment"

# Push lên GitHub
git push github main
# Hoặc nếu branch hiện tại là master:
# git push github master
```

### Bước 2: Deploy lên server

**Trên Windows (PowerShell):**

```powershell
# Cài đặt Git Bash hoặc sử dụng WSL
# Hoặc chạy script deploy.sh qua Git Bash

# Nếu dùng WSL:
wsl bash deploy.sh 124.158.10.34 ubuntu
```

**Hoặc SSH trực tiếp vào server và chạy:**

```bash
# SSH vào server
ssh ubuntu@124.158.10.34

# Tạo thư mục AI Agent
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"

# Clone repository
git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .

# Chạy script setup
chmod +x setup_server.sh
bash setup_server.sh
```

---

## 🔧 Phương pháp 2: Deploy thủ công

### Bước 1: Chuẩn bị trên máy local

```bash
# Đảm bảo code đã được push lên GitHub
git push github main
```

### Bước 2: SSH vào server

```bash
ssh ubuntu@124.158.10.34
```

### Bước 3: Cài đặt môi trường

```bash
# Tạo thư mục project
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"

# Clone repository
git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .

# Chạy script setup
chmod +x setup_server.sh
bash setup_server.sh
```

### Bước 4: Cấu hình .env

```bash
nano .env
```

Cập nhật các giá trị sau:

```env
# OpenAI API
OPENAI_API_KEY=sk-your-actual-openai-key

# PostgreSQL (đã được cấu hình tự động)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oshima_ai
POSTGRES_USER=oshima_user
POSTGRES_PASSWORD=oshima_pass_2024

# Chainlit
CHAINLIT_AUTH_SECRET=your-random-secret-key-here

# API Server
API_SERVER_PORT=8001
CHAINLIT_PORT=8000

# Firebase (Optional)
FIREBASE_CREDENTIALS_PATH=firebase-admin-key.json
```

### Bước 5: Tạo Systemd Service

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

Lưu và thoát (Ctrl+X, Y, Enter)

### Bước 6: Khởi động service

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

## 🔍 Kiểm tra và quản lý

### Xem logs

```bash
# Xem logs real-time
sudo journalctl -u oshima-ai -f

# Xem logs gần đây
sudo journalctl -u oshima-ai -n 100
```

### Quản lý service

```bash
# Restart service
sudo systemctl restart oshima-ai

# Stop service
sudo systemctl stop oshima-ai

# Start service
sudo systemctl start oshima-ai

# Check status
sudo systemctl status oshima-ai
```

### Kiểm tra ports

```bash
# Kiểm tra port 8000 (Chainlit)
curl http://localhost:8000

# Kiểm tra port 8001 (API Server)
curl http://localhost:8001
```

---

## 🌐 Cấu hình Firewall

Nếu server có firewall (ufw), mở các ports cần thiết:

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 8000/tcp  # Chainlit
sudo ufw allow 8001/tcp  # API Server
sudo ufw reload
```

---

## 🔗 Truy cập ứng dụng

Sau khi deploy thành công, bạn có thể truy cập:

- **Chainlit UI**: http://124.158.10.34:8000
- **API Server**: http://124.158.10.34:8001

---

## 🔄 Update code mới

Khi có code mới trên GitHub:

```bash
# SSH vào server
ssh ubuntu@124.158.10.34

# Vào thư mục project
cd ~/"AI Agent"

# Pull code mới
git pull origin main

# Restart service
sudo systemctl restart oshima-ai
```

---

## 🐛 Troubleshooting

### Service không start

```bash
# Kiểm tra logs
sudo journalctl -u oshima-ai -n 50

# Kiểm tra .env file
cat ~/"AI Agent"/.env

# Kiểm tra Python environment
cd ~/"AI Agent"
source .venv311/bin/activate
python --version
```

### PostgreSQL không kết nối được

```bash
# Kiểm tra PostgreSQL status
sudo systemctl status postgresql

# Kiểm tra kết nối
sudo -u postgres psql -d oshima_ai -c "SELECT version();"
```

### Port đã được sử dụng

```bash
# Kiểm tra process đang dùng port
sudo lsof -i :8000
sudo lsof -i :8001

# Kill process nếu cần
sudo kill -9 <PID>
```

---

## 📞 Hỗ trợ

Nếu gặp vấn đề, vui lòng kiểm tra:
1. Logs của service: `sudo journalctl -u oshima-ai -f`
2. File .env có đúng credentials không
3. PostgreSQL đã được cài đặt và chạy chưa
4. Firewall có chặn ports không

---

## ✅ Checklist

- [ ] Code đã được push lên GitHub
- [ ] SSH vào server thành công
- [ ] Đã chạy setup_server.sh
- [ ] Đã cấu hình .env với credentials thực tế
- [ ] Systemd service đã được tạo và enable
- [ ] Service đã start và chạy thành công
- [ ] Có thể truy cập http://124.158.10.34:8000
- [ ] Firewall đã mở ports cần thiết

---

**Chúc bạn deploy thành công! 🎉**

