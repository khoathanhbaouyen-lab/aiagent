# postgres_utils.py
# PostgreSQL Connection Utilities

import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "oshima_ai")

# Connection Pool
_connection_pool: Optional[SimpleConnectionPool] = None

def get_postgres_connection_string() -> str:
    """
    Tạo PostgreSQL connection string cho SQLAlchemy và các thư viện khác.
    Format: postgresql://user:password@host:port/database
    """
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def get_asyncpg_connection_string() -> str:
    """
    Tạo connection string cho asyncpg (dùng bởi langchain-postgres).
    Format: postgresql+asyncpg://user:password@host:port/database
    """
    return f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def init_connection_pool(min_conn: int = 1, max_conn: int = 20):
    """
    Khởi tạo connection pool cho PostgreSQL.
    """
    global _connection_pool
    try:
        _connection_pool = SimpleConnectionPool(
            min_conn,
            max_conn,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        print(f"✅ [PostgreSQL] Connection pool đã khởi tạo (min={min_conn}, max={max_conn})")
    except Exception as e:
        print(f"❌ [PostgreSQL] Lỗi khởi tạo connection pool: {e}")
        raise

def get_connection():
    """
    Lấy connection từ pool.
    """
    global _connection_pool
    if _connection_pool is None:
        init_connection_pool()
    return _connection_pool.getconn()

def release_connection(conn):
    """
    Trả connection về pool.
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.putconn(conn)

def close_connection_pool():
    """
    Đóng connection pool.
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        print("✅ [PostgreSQL] Connection pool đã đóng")

def execute_query(query: str, params: tuple = None, fetch: bool = False):
    """
    Thực thi SQL query với connection pool.
    
    Args:
        query: SQL query string
        params: Tuple parameters cho query
        fetch: True nếu cần fetch results (SELECT), False nếu INSERT/UPDATE/DELETE
    
    Returns:
        List of dict (nếu fetch=True), None otherwise
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            else:
                conn.commit()
                return None
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ [PostgreSQL] Lỗi thực thi query: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def init_pgvector_extension():
    """
    Khởi tạo pgvector extension trong PostgreSQL.
    """
    try:
        execute_query("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✅ [PostgreSQL] pgvector extension đã được kích hoạt")
    except Exception as e:
        print(f"❌ [PostgreSQL] Lỗi khởi tạo pgvector: {e}")
        print("⚠️  Đảm bảo bạn đã cài đặt pgvector extension trong PostgreSQL")
        raise

def test_connection() -> bool:
    """
    Test kết nối PostgreSQL.
    
    Returns:
        True nếu kết nối thành công, False otherwise
    """
    try:
        result = execute_query("SELECT version();", fetch=True)
        if result:
            print(f"✅ [PostgreSQL] Kết nối thành công: {result[0]['version'][:50]}...")
            return True
        return False
    except Exception as e:
        print(f"❌ [PostgreSQL] Kết nối thất bại: {e}")
        return False
