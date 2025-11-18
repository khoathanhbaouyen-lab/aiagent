# 🤖 OSHIMA AI Agent

AI Agent application built with Chainlit, LangChain, and PostgreSQL.

## 📋 Features

- AI-powered chat interface using Chainlit
- Vector database with PostgreSQL + pgvector
- Task management and scheduling
- User authentication
- File upload and processing
- RESTful API server

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 17+
- pgvector extension

### Installation

1. Clone the repository:
```bash
git clone https://github.com/khoathanhbaouyen-lab/aiagent.git
cd aiagent
```

2. Run setup script (Ubuntu):
```bash
chmod +x setup_ubuntu.sh
bash setup_ubuntu.sh
```

3. Configure environment:
```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

4. Run the application:
```bash
source .venv311/bin/activate
python run.py
```

## 📖 Documentation

- [Deployment Guide](DEPLOY.md) - Hướng dẫn deploy lên Ubuntu server
- [Setup Guide](SETUP_GUIDE.md) - Hướng dẫn cài đặt chi tiết
- [PostgreSQL Setup](SETUP_POSTGRESQL.md) - Hướng dẫn cài đặt PostgreSQL

## 🌐 Access

- **Chainlit UI**: http://localhost:8000
- **API Server**: http://localhost:8001

## 📦 Requirements

See `requirements.txt` for Python dependencies.

## 🔧 Configuration

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=your-openai-api-key
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oshima_ai
POSTGRES_USER=oshima_user
POSTGRES_PASSWORD=your-password
CHAINLIT_AUTH_SECRET=your-secret-key
API_SERVER_PORT=8001
CHAINLIT_PORT=8000
```

## 📝 License

This project is private and proprietary.

## 👥 Contributors

- khoathanhbaouyen-lab
