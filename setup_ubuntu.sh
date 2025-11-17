#!/bin/bash
# =========================================================
# OSHIMA AI - Ubuntu Setup Script (First-time Installation)
# =========================================================
# Chạy script này sau khi git clone lần đầu trên Ubuntu
# Usage: bash setup_ubuntu.sh
# =========================================================

set -e  # Exit on error

echo "=============================================="
echo "  🚀 OSHIMA AI - Ubuntu First-Time Setup"
echo "=============================================="
echo ""

# 1. Update system
echo "📦 [1/8] Updating system packages..."
sudo apt update
sudo apt upgrade -y

# 2. Install Python 3.11
echo "🐍 [2/8] Installing Python 3.11..."
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# 3. Install PostgreSQL 17
echo "🐘 [3/8] Installing PostgreSQL 17..."
sudo apt install -y wget gnupg2
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-17 postgresql-contrib-17

# 4. Install pgvector extension
echo "📊 [4/8] Installing pgvector extension..."
sudo apt install -y postgresql-server-dev-17 build-essential git
cd /tmp
if [ ! -d "pgvector" ]; then
    git clone https://github.com/pgvector/pgvector.git
fi
cd pgvector
make clean
make OPTFLAGS=""
sudo make install
cd -

# 5. Setup PostgreSQL
echo "🔧 [5/8] Configuring PostgreSQL..."

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE oshima_ai;" || echo "Database already exists"
sudo -u postgres psql -c "CREATE USER oshima_user WITH PASSWORD 'oshima_pass_2024';" || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE oshima_ai TO oshima_user;"
sudo -u postgres psql -c "ALTER DATABASE oshima_ai OWNER TO oshima_user;"

# Enable pgvector extension
sudo -u postgres psql -d oshima_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Allow remote connections (optional)
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/17/main/postgresql.conf
echo "host    all             all             0.0.0.0/0               md5" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf

# Restart PostgreSQL
sudo systemctl restart postgresql

echo "✅ PostgreSQL configured!"
echo "   Database: oshima_ai"
echo "   User: oshima_user"
echo "   Password: oshima_pass_2024"

# 6. Create Python virtual environment
echo "🐍 [6/8] Creating Python virtual environment..."
cd "$(dirname "$0")"
python3.11 -m venv .venv311
source .venv311/bin/activate

# 7. Install Python dependencies
echo "📚 [7/8] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 8. Create .env file
echo "⚙️ [8/8] Creating .env file..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOL'
# =========================================================
# OSHIMA AI - Environment Variables
# =========================================================

# OpenAI API
OPENAI_API_KEY=your-openai-api-key-here

# PostgreSQL Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oshima_ai
POSTGRES_USER=oshima_user
POSTGRES_PASSWORD=oshima_pass_2024

# Chainlit
CHAINLIT_AUTH_SECRET=your-secret-key-here

# API Server
API_SERVER_PORT=8001
CHAINLIT_PORT=8000

# Firebase (Optional - for push notifications)
FIREBASE_CREDENTIALS_PATH=firebase-admin-key.json

# Frappe/ERPNext API (Optional)
FRAPPE_API_URL=https://your-frappe-site.com
FRAPPE_API_KEY=your-frappe-api-key
FRAPPE_API_SECRET=your-frappe-secret
EOL
    echo "✅ Created .env file. Please update with your actual credentials!"
else
    echo "ℹ️ .env file already exists"
fi

# 9. Create directories
echo "📁 Creating required directories..."
mkdir -p data/uploads data/exports data/sessions
mkdir -p memory memory_db saved_files saved_images sessions
mkdir -p public/files public/elements
mkdir -p user_data vector_db ui_inbox users

# 10. Initialize database tables
echo "🗄️ Initializing database tables..."
python3 << 'PYEOF'
import os
os.environ.setdefault('POSTGRES_HOST', 'localhost')
os.environ.setdefault('POSTGRES_PORT', '5432')
os.environ.setdefault('POSTGRES_DB', 'oshima_ai')
os.environ.setdefault('POSTGRES_USER', 'oshima_user')
os.environ.setdefault('POSTGRES_PASSWORD', 'oshima_pass_2024')

# Import and run migrations
try:
    from migrate_to_postgres import migrate_all
    print("Running database migrations...")
    migrate_all()
    print("✅ Database initialized!")
except Exception as e:
    print(f"⚠️ Migration skipped: {e}")
    print("Database will be initialized on first run.")
PYEOF

# Done!
echo ""
echo "=============================================="
echo "  ✅ Setup Complete!"
echo "=============================================="
echo ""
echo "📝 Next steps:"
echo "   1. Edit .env file with your actual credentials"
echo "   2. Add firebase-admin-key.json (if using Firebase)"
echo "   3. Run: source .venv311/bin/activate"
echo "   4. Run: python run.py"
echo ""
echo "🔗 Access URLs:"
echo "   - Chainlit UI: http://localhost:8000"
echo "   - API Server: http://localhost:8001"
echo ""
echo "=============================================="
