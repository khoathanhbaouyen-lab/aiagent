# 🚀 Hướng Dẫn Deploy với Password

## Cách 1: Sử dụng Script Tự Động (Khuyến nghị)

### Trên Windows (PowerShell hoặc Git Bash)

```bash
# Chạy script với password
bash deploy_with_password.sh 124.158.10.34 ubuntu your_password_here
```

### Trên Linux/Mac

```bash
# Cài đặt sshpass nếu chưa có
# Ubuntu/Debian:
sudo apt-get install sshpass

# Mac:
brew install hudochenkov/sshpass/sshpass

# Chạy script
bash deploy_with_password.sh 124.158.10.34 ubuntu your_password_here
```

---

## Cách 2: Chạy Từng Bước Thủ Công

### Bước 1: Cài đặt sshpass (nếu chưa có)

**Windows:**
- Sử dụng WSL (Windows Subsystem for Linux)
- Hoặc cài đặt Git Bash và sshpass

**Linux:**
```bash
sudo apt-get install sshpass
```

**Mac:**
```bash
brew install hudochenkov/sshpass/sshpass
```

### Bước 2: Deploy với password

```bash
# Set password
export SSHPASS="your_password_here"

# Test connection
sshpass -e ssh ubuntu@124.158.10.34 "echo 'Connected!'"

# Clone code
sshpass -e ssh ubuntu@124.158.10.34 << 'ENDSSH'
    mkdir -p ~/"AI Agent"
    cd ~/"AI Agent"
    git clone https://github.com/khoathanhbaouyen-lab/aiagent.git .
ENDSSH

# Run setup
sshpass -e ssh ubuntu@124.158.10.34 << 'ENDSSH'
    cd ~/"AI Agent"
    chmod +x setup_server.sh
    bash setup_server.sh
ENDSSH
```

---

## Cách 3: Setup SSH Key (Không cần password - An toàn hơn)

### Bước 1: Tạo SSH key (trên máy local)

```bash
ssh-keygen -t ed25519 -C "deploy@oshima-ai"
# Nhấn Enter để dùng default location
# Nhấn Enter để không đặt passphrase (hoặc đặt nếu muốn)
```

### Bước 2: Copy key lên server

```bash
# Sử dụng password một lần để copy key
ssh-copy-id ubuntu@124.158.10.34

# Hoặc thủ công:
cat ~/.ssh/id_ed25519.pub | ssh ubuntu@124.158.10.34 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Bước 3: Test SSH không cần password

```bash
ssh ubuntu@124.158.10.34
# Nếu không hỏi password = thành công!
```

### Bước 4: Deploy (không cần password)

```bash
# Sử dụng script deploy.sh (không cần password)
bash deploy.sh 124.158.10.34 ubuntu
```

---

## ⚠️ Lưu ý Bảo mật

1. **Không commit password vào Git**
2. **Sử dụng SSH key thay vì password** (an toàn hơn)
3. **Nếu dùng password, chỉ dùng trong script local, không lưu vào file**

---

## 📋 Checklist

- [ ] Đã cài đặt sshpass (nếu dùng password)
- [ ] Đã test kết nối SSH
- [ ] Đã clone code từ GitHub
- [ ] Đã chạy setup_server.sh
- [ ] Đã cấu hình .env file
- [ ] Đã tạo systemd service
- [ ] Service đã start thành công

---

## 🔧 Troubleshooting

### Lỗi "sshpass: command not found"
```bash
# Ubuntu/Debian
sudo apt-get install sshpass

# Mac
brew install hudochenkov/sshpass/sshpass
```

### Lỗi "Permission denied"
- Kiểm tra username và password
- Kiểm tra user có quyền sudo không
- Thử với user khác (root, admin, etc.)

### Lỗi "Host key verification failed"
```bash
ssh-keygen -R 124.158.10.34
```

---

**Chúc bạn deploy thành công! 🎉**

