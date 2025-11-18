#!/bin/bash
# =========================================================
# Script tự động deploy từ máy local lên server Ubuntu
# Có thể sử dụng password hoặc SSH key
# =========================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
SERVER_IP="${1:-124.158.10.34}"
SERVER_USER="${2:-ubuntu}"
SERVER_PASS="${3:-}"

PROJECT_DIR="AI Agent"
GIT_REPO="https://github.com/khoathanhbaouyen-lab/aiagent.git"

echo -e "${GREEN}=============================================="
echo "  🚀 OSHIMA AI - Auto Deploy"
echo "==============================================${NC}"
echo ""
echo "Server: ${SERVER_USER}@${SERVER_IP}"
echo "Project: ~/${PROJECT_DIR}"
echo ""

# Check if sshpass is installed (for password authentication)
USE_PASSWORD=false
if [ -n "$SERVER_PASS" ]; then
    if ! command -v sshpass &> /dev/null; then
        echo -e "${YELLOW}⚠️  sshpass not found. Installing...${NC}"
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            sudo apt-get update && sudo apt-get install -y sshpass
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            brew install hudochenkov/sshpass/sshpass
        else
            echo -e "${RED}❌ Please install sshpass manually or use SSH key${NC}"
            exit 1
        fi
    fi
    USE_PASSWORD=true
    export SSHPASS="$SERVER_PASS"
fi

# Function to run SSH command
ssh_cmd() {
    if [ "$USE_PASSWORD" = true ]; then
        sshpass -e ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "$1"
    else
        ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "$1"
    fi
}

# Function to copy file via SCP
scp_cmd() {
    if [ "$USE_PASSWORD" = true ]; then
        sshpass -e scp -o StrictHostKeyChecking=no "$1" ${SERVER_USER}@${SERVER_IP}:"$2"
    else
        scp -o StrictHostKeyChecking=no "$1" ${SERVER_USER}@${SERVER_IP}:"$2"
    fi
}

# Test connection
echo -e "${GREEN}[1/7] Testing SSH connection...${NC}"
if ssh_cmd "exit" 2>/dev/null; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to server${NC}"
    exit 1
fi
echo ""

# Create project directory
echo -e "${GREEN}[2/7] Creating project directory...${NC}"
ssh_cmd "mkdir -p ~/'${PROJECT_DIR}'"
echo -e "${GREEN}✅ Directory created${NC}"
echo ""

# Clone or update repository
echo -e "${GREEN}[3/7] Cloning/Updating repository...${NC}"
ssh_cmd "cd ~/'${PROJECT_DIR}' && if [ -d .git ]; then git pull origin main || git pull origin master; else git clone ${GIT_REPO} .; fi"
echo -e "${GREEN}✅ Repository updated${NC}"
echo ""

# Copy setup script if needed
echo -e "${GREEN}[4/7] Preparing setup script...${NC}"
ssh_cmd "cd ~/'${PROJECT_DIR}' && chmod +x setup_server.sh"
echo -e "${GREEN}✅ Setup script ready${NC}"
echo ""

# Run setup (this will take a while)
echo -e "${GREEN}[5/7] Running setup script on server...${NC}"
echo -e "${YELLOW}⏳ This may take 10-15 minutes...${NC}"
ssh_cmd "cd ~/'${PROJECT_DIR}' && bash setup_server.sh" || {
    echo -e "${YELLOW}⚠️  Setup script may have warnings, continuing...${NC}"
}
echo ""

# Create systemd service
echo -e "${GREEN}[6/7] Creating systemd service...${NC}"
ssh_cmd "sudo tee /etc/systemd/system/oshima-ai.service > /dev/null << 'EOFSERVICE'
[Unit]
Description=OSHIMA AI Application
After=network.target postgresql.service

[Service]
Type=simple
User=${SERVER_USER}
WorkingDirectory=/home/${SERVER_USER}/${PROJECT_DIR}
Environment=\"PATH=/home/${SERVER_USER}/${PROJECT_DIR}/.venv311/bin\"
ExecStart=/home/${SERVER_USER}/${PROJECT_DIR}/.venv311/bin/python run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE
sudo systemctl daemon-reload
sudo systemctl enable oshima-ai"

echo -e "${GREEN}✅ Systemd service created${NC}"
echo ""

# Final instructions
echo -e "${GREEN}[7/7] Deployment preparation complete!${NC}"
echo ""
echo -e "${YELLOW}=============================================="
echo "  ⚠️  IMPORTANT: Next Steps"
echo "==============================================${NC}"
echo ""
echo "1. SSH vào server:"
echo "   ssh ${SERVER_USER}@${SERVER_IP}"
echo ""
echo "2. Cấu hình file .env:"
echo "   cd ~/'${PROJECT_DIR}'"
echo "   nano .env"
echo ""
echo "   Cập nhật các giá trị:"
echo "   - OPENAI_API_KEY=sk-your-key"
echo "   - CHAINLIT_AUTH_SECRET=your-secret"
echo ""
echo "3. Khởi động service:"
echo "   sudo systemctl start oshima-ai"
echo "   sudo systemctl status oshima-ai"
echo ""
echo "4. Truy cập ứng dụng:"
echo "   - Chainlit: http://${SERVER_IP}:8000"
echo "   - API: http://${SERVER_IP}:8001"
echo ""
echo -e "${GREEN}=============================================="

