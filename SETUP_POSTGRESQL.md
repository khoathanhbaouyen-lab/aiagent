# setup_postgresql.md
# Hướng Dẫn Setup PostgreSQL + pgvector cho Oshima AI

## Bước 1: Cài Đặt PostgreSQL

### Windows
1. Download PostgreSQL từ: https://www.postgresql.org/download/windows/
2. Chạy installer, chọn port 5432 (default)
3. Đặt password cho user `postgres`
4. Hoàn thành cài đặt

### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

## Bước 2: Cài Đặt pgvector Extension

### Windows
1. Download pgvector prebuilt binary từ: https://github.com/pgvector/pgvector/releases
2. Giải nén và copy file `.dll` vào thư mục `lib` của PostgreSQL
3. Copy file `.sql` vào thư mục `share/extension`

### macOS/Linux
```bash
# Clone repository
git clone --branch v0.6.0 https://github.com/pgvector/pgvector.git
cd pgvector

# Build and install
make
sudo make install

# Hoặc dùng package manager (macOS)
brew install pgvector
```

## Bước 3: Tạo Database

Mở PostgreSQL command line (`psql`):

```bash
# Windows: Tìm "SQL Shell (psql)" trong Start Menu
# macOS/Linux: 
psql -U postgres
```

Trong psql, chạy các lệnh sau:

```sql
-- Tạo database
CREATE DATABASE oshima_ai;

-- Kết nối vào database
\c oshima_ai

-- Kích hoạt pgvector extension
CREATE EXTENSION vector;

-- Kiểm tra extension đã cài đặt
\dx

-- Thoát
\q
```

## Bước 4: Cấu Hình .env File

Mở file `.env` và cập nhật thông tin PostgreSQL:

```env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_actual_password_here
POSTGRES_DB=oshima_ai
```

**⚠️ LƯU Ý**: Thay `your_actual_password_here` bằng password bạn đã đặt khi cài PostgreSQL.

## Bước 5: Test Kết Nối

Chạy script Python để test kết nối:

```bash
python -c "from postgres_utils import test_connection; test_connection()"
```

Nếu thành công, bạn sẽ thấy:
```
✅ [PostgreSQL] Kết nối thành công: PostgreSQL 15.x...
```

## Bước 6: Migration Dữ Liệu (Tùy Chọn)

Nếu bạn đã có dữ liệu trong SQLite và muốn chuyển sang PostgreSQL:

```bash
python migrate_to_postgres.py
```

Script sẽ tự động:
- Tạo các bảng cần thiết
- Migrate users từ `users.sqlite`
- Migrate chat history từ `chainlit_history.db`
- Báo cáo kết quả migration

## Bước 7: Chạy Ứng Dụng

```bash
python run.py
```

Ứng dụng sẽ tự động:
- Kết nối PostgreSQL (hoặc fallback sang SQLite nếu lỗi)
- Khởi tạo pgvector cho vector storage
- Sử dụng PostgreSQL cho chat history và user authentication

## Kiểm Tra Dữ Liệu

Để kiểm tra dữ liệu trong PostgreSQL, dùng psql:

```sql
-- Kết nối database
psql -U postgres -d oshima_ai

-- Xem danh sách users
SELECT email, name, is_admin FROM app_users;

-- Xem danh sách threads
SELECT id, name, user_identifier, created_at FROM threads;

-- Xem vector embeddings
SELECT COUNT(*) FROM langchain_pg_embedding;

-- Thoát
\q
```

## Troubleshooting

### Lỗi: "could not connect to server"
- Kiểm tra PostgreSQL service đang chạy
- Windows: Services → PostgreSQL 15
- macOS/Linux: `sudo systemctl status postgresql`

### Lỗi: "extension 'vector' does not exist"
- pgvector chưa được cài đặt đúng
- Xem lại Bước 2

### Lỗi: "authentication failed"
- Kiểm tra password trong `.env` file
- Thử kết nối bằng psql để verify password

### Fallback sang SQLite
Nếu PostgreSQL không hoạt động, ứng dụng tự động fallback sang SQLite:
- User auth: `user_data/users.sqlite`
- Chat history: `memory_db/chainlit_history.db`
- Vector store: `user_data/shared_vector_db/`

## Performance Tuning (Production)

Sau khi migration thành công, tối ưu PostgreSQL:

```sql
-- Tăng connection pool
ALTER SYSTEM SET max_connections = 200;

-- Tối ưu memory
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';

-- Restart PostgreSQL để áp dụng
-- Windows: Services → Restart PostgreSQL
-- Linux: sudo systemctl restart postgresql
```

## Backup & Restore

### Backup
```bash
pg_dump -U postgres -d oshima_ai -F c -f oshima_ai_backup.dump
```

### Restore
```bash
pg_restore -U postgres -d oshima_ai -c oshima_ai_backup.dump
```

## Support

Nếu gặp vấn đề:
1. Kiểm tra logs PostgreSQL
2. Xem file `app.py` logs khi khởi động
3. Test kết nối bằng `test_connection()`

---
**Hoàn thành!** Hệ thống của bạn đã sẵn sàng với PostgreSQL + pgvector.
