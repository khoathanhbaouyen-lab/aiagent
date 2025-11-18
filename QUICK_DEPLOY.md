# ⚡ Hướng Dẫn Deploy Nhanh lên Server Ubuntu

## Server: 124.158.10.34

### Bước 1: SSH vào server

```bash
ssh ubuntu@124.158.10.34
```

### Bước 2: Clone và setup

```bash
# Tạo thư mục AI Agent
mkdir -p ~/"AI Agent"
cd ~/"AI Agent"

# Clone từ GitHub
git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .

# Chạy script setup tự động
chmod +x setup_server.sh
bash setup_server.sh
```

### Bước 3: Cấu hình .env

```bash
nano .env
```

Cập nhật:
- `OPENAI_API_KEY` - API key của bạn
- `CHAINLIT_AUTH_SECRET` - Secret key bất kỳ

### Bước 4: Tạo systemd service

```bash
sudo nano /etc/systemd/system/oshima-ai.service
```

Paste:

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

[Install]
WantedBy=multi-user.target
```

### Bước 5: Khởi động

```bash
sudo systemctl daemon-reload
sudo systemctl enable oshima-ai
sudo systemctl start oshima-ai
sudo systemctl status oshima-ai
```

### Truy cập

- Chainlit: http://124.158.10.34:8000
- API: http://124.158.10.34:8001

### Xem logs

```bash
sudo journalctl -u oshima-ai -f
```

