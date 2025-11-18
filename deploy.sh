#!/bin/bash
# =========================================================
# OSHIMA AI - Deployment Script for Ubuntu Server
# =========================================================
# Script này sẽ deploy project lên Ubuntu server
# Usage: bash deploy.sh [server_ip] [server_user]
# Example: bash deploy.sh 124.158.10.34 ubuntu
# =========================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER_IP="${1:-124.158.10.34}"
SERVER_USER="${2:-ubuntu}"
PROJECT_DIR="AI Agent"
GIT_REPO="https://github.com/khoathanhbaouyen-lab/aiagent.git"

echo -e "${GREEN}=============================================="
echo "  🚀 OSHIMA AI - Server Deployment"
echo "==============================================${NC}"
echo ""
echo "Server: ${SERVER_USER}@${SERVER_IP}"
echo "Project Directory: ~/${PROJECT_DIR}"
echo ""

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa ] && [ ! -f ~/.ssh/id_ed25519 ]; then
    echo -e "${YELLOW}⚠️  No SSH key found. Generating one...${NC}"
    ssh-keygen -t ed25519 -C "deploy@oshima-ai" -f ~/.ssh/id_ed25519 -N ""
    echo -e "${GREEN}✅ SSH key generated. Please add it to server:${NC}"
    echo "   ssh-copy-id ${SERVER_USER}@${SERVER_IP}"
    echo ""
    read -p "Press Enter after adding SSH key to server..."
fi

echo -e "${GREEN}[1/5] Testing SSH connection...${NC}"
ssh -o ConnectTimeout=10 -o BatchMode=yes ${SERVER_USER}@${SERVER_IP} exit 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cannot connect to server. Please check:${NC}"
    echo "   1. Server IP is correct: ${SERVER_IP}"
    echo "   2. SSH key is added to server"
    echo "   3. Firewall allows SSH (port 22)"
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"
echo ""

echo -e "${GREEN}[2/5] Creating project directory on server...${NC}"
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    mkdir -p ~/"AI Agent"
    cd ~/"AI Agent"
    echo "✅ Directory ready"
ENDSSH
echo ""

echo -e "${GREEN}[3/5] Cloning/Updating repository on server...${NC}"
ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
    cd ~/"AI Agent"
    if [ -d ".git" ]; then
        echo "📥 Updating existing repository..."
        git pull origin main || git pull origin master
    else
        echo "📥 Cloning repository..."
        git clone ${GIT_REPO} .
    fi
    echo "✅ Repository updated"
ENDSSH
echo ""

echo -e "${GREEN}[4/5] Running setup script on server...${NC}"
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    cd ~/"AI Agent"
    chmod +x setup_ubuntu.sh
    bash setup_ubuntu.sh
ENDSSH
echo ""

echo -e "${GREEN}[5/5] Creating systemd service...${NC}"
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    cd ~/"AI Agent"
    
    # Create systemd service file
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

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable oshima-ai
    echo "✅ Systemd service created"
ENDSSH
echo ""

echo -e "${GREEN}=============================================="
echo "  ✅ Deployment Complete!"
echo "==============================================${NC}"
echo ""
echo "📝 Next steps:"
echo "   1. SSH to server: ssh ${SERVER_USER}@${SERVER_IP}"
echo "   2. Edit .env file: cd ~/'AI Agent' && nano .env"
echo "   3. Add your credentials (OPENAI_API_KEY, etc.)"
echo "   4. Start service: sudo systemctl start oshima-ai"
echo "   5. Check status: sudo systemctl status oshima-ai"
echo ""
echo "🔗 Access URLs:"
echo "   - Chainlit UI: http://${SERVER_IP}:8000"
echo "   - API Server: http://${SERVER_IP}:8001"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: sudo journalctl -u oshima-ai -f"
echo "   - Restart: sudo systemctl restart oshima-ai"
echo "   - Stop: sudo systemctl stop oshima-ai"
echo ""
echo "=============================================="

