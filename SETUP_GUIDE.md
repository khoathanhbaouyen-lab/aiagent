# 🚀 OSHIMA AI - Ubuntu Setup Guide

## Hướng dẫn cài đặt trên Ubuntu Server (Lần đầu tiên)

### 📋 Yêu cầu hệ thống
- Ubuntu 20.04 LTS hoặc 22.04 LTS
- RAM: Tối thiểu 4GB (khuyến nghị 8GB+)
- Disk: Tối thiểu 20GB trống
- Quyền sudo

---

## ⚡ Cài đặt tự động (Khuyến nghị)

### 1. Clone code từ Git
```bash
git clone https://github.com/your-repo/oshima-ai.git
cd oshima-ai
```

### 2. Chạy script setup tự động
```bash
chmod +x setup_ubuntu.sh
bash setup_ubuntu.sh
```

Script sẽ tự động:
- ✅ Cài đặt Python 3.11
- ✅ Cài đặt PostgreSQL 17 + pgvector
- ✅ Tạo database `oshima_ai`
- ✅ Tạo virtual environment
- ✅ Cài đặt dependencies
- ✅ Tạo file `.env` mẫu
- ✅ Khởi tạo database tables

### 3. Cấu hình credentials
```bash
nano .env
```

Cập nhật các giá trị sau:
```env
OPENAI_API_KEY=sk-your-actual-key
CHAINLIT_AUTH_SECRET=your-random-secret-key
FRAPPE_API_URL=https://your-site.com
FRAPPE_API_KEY=your-key
FRAPPE_API_SECRET=your-secret
```

### 4. (Optional) Cấu hình Firebase Push Notifications
```bash
# Copy file credentials từ Firebase Console
nano firebase-admin-key.json
# Paste JSON content và lưu lại
```

### 5. Chạy ứng dụng
```bash
source .venv311/bin/activate
python run.py
```

Truy cập:
- **Chainlit UI**: http://your-server-ip:8000
- **API Server**: http://your-server-ip:8001

---

## 🔧 Cài đặt thủ công (Manual)

### Bước 1: Cài Python 3.11
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

### Bước 2: Cài PostgreSQL 17
```bash
# Add repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Install
sudo apt update
sudo apt install -y postgresql-17 postgresql-contrib-17
```

### Bước 3: Cài pgvector extension
```bash
sudo apt install -y postgresql-server-dev-17 build-essential git
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Bước 4: Setup Database
```bash
sudo -u postgres psql << EOF
CREATE DATABASE oshima_ai;
CREATE USER oshima_user WITH PASSWORD 'oshima_pass_2024';
GRANT ALL PRIVILEGES ON DATABASE oshima_ai TO oshima_user;
ALTER DATABASE oshima_ai OWNER TO oshima_user;
\c oshima_ai
CREATE EXTENSION vector;
EOF
```

### Bước 5: Clone code & setup Python
```bash
git clone https://github.com/your-repo/oshima-ai.git
cd oshima-ai
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
```

### Bước 6: Cấu hình .env
```bash
cp .env.example .env
nano .env
# Điền thông tin credentials
```

### Bước 7: Run
```bash
python run.py
```

---

## 🌐 Production Deployment

### 1. Setup Systemd Service
```bash
sudo nano /etc/systemd/system/oshima-ai.service
```

```ini
[Unit]
Description=OSHIMA AI Application
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/oshima-ai
Environment="PATH=/home/ubuntu/oshima-ai/.venv311/bin"
ExecStart=/home/ubuntu/oshima-ai/.venv311/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable & Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable oshima-ai
sudo systemctl start oshima-ai
sudo systemctl status oshima-ai
```

### 3. Setup Nginx Reverse Proxy
```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/oshima-ai
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Chainlit UI
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API Server
    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/oshima-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Setup SSL (Let's Encrypt)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 📊 Monitoring & Logs

### View logs
```bash
# Application logs
sudo journalctl -u oshima-ai -f

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-17-main.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Check status
```bash
sudo systemctl status oshima-ai
sudo systemctl status postgresql
sudo systemctl status nginx
```

---

## 🔄 Update từ Git

```bash
cd /home/ubuntu/oshima-ai
git pull origin main
source .venv311/bin/activate
pip install -r requirements.txt
sudo systemctl restart oshima-ai
```

---

## 🐛 Troubleshooting

### PostgreSQL connection error
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -h localhost -U oshima_user -d oshima_ai
```

### Port already in use
```bash
# Check what's using port 8000/8001
sudo lsof -i :8000
sudo lsof -i :8001

# Kill process if needed
sudo kill -9 <PID>
```

### Permission errors
```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/oshima-ai

# Fix permissions
chmod +x run.py
chmod +x setup_ubuntu.sh
```

---

## 📞 Support
- Email: support@oshima.vn
- Docs: https://docs.oshima.vn
