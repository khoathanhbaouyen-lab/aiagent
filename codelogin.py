# app.py
# (PHIÊN BẢN HOÀN CHỈNH - ĐÃ GỘP VÀ SỬA LỖI)

import os
import re
import json
import uuid
import base64
import html
import shutil
import sqlite3 # <-- MỚI: Cho CSDL User
import traceback
from werkzeug.security import generate_password_hash, check_password_hash # <-- MỚI: Băm mật khẩu
import pandas as pd
import docx # từ python-docx
import pypdf
import unidecode
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from chromadb.config import Settings
import contextvars
from datetime import datetime, timedelta # <-- SỬA: Thêm timedelta
from typing import List, Tuple, Optional, Union
from pydantic import BaseModel, Field
import chainlit as cl
from chainlit import Image as ClImage
from chainlit import File as ClFile
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from apscheduler.triggers.interval import IntervalTrigger
from langchain.tools import tool
import requests
from langchain.agents import AgentExecutor
from langchain.agents import create_openai_tools_agent
from dateutil import parser as dtparser  # pip install python-dateutil
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # pip install apscheduler
from apscheduler.triggers.date import DateTrigger
import pytz  # pip install pytz
import asyncio
from asyncio import Queue
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger # <--- MỚI: Thêm CronTrigger

# --- MỚI: Thêm các import bị thiếu cho RAG/Agent ---
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
# ----------------------------------------------------

GLOBAL_MESSAGE_QUEUE: Optional[Queue] = None   # "Tổng đài" (chỉ 1)
ACTIVE_SESSION_QUEUES = {}                     # "Danh sách thuê bao" {session_id: queue}
POLLER_STARTED = False                         # Cờ để khởi động Tổng đài (1 lần)
# =========================================================
# 📦 Env
# =========================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# Push-noti config (có thể đưa vào .env)
PUSH_API_URL = "https://ocrm.oshima.vn/api/method/createpushnoti"
PUSH_API_TOKEN = os.getenv("OCRMPUSH_TOKEN", "1773d804508a47b:d3ca2affa83ccab")
PUSH_DEFAULT_URL = "https://ocrm.oshima.vn/app/server-script/tao%20pushnoti"

# NEW: chọn cách gửi body: "data" (raw JSON string) hoặc "json" (requests.json)
PUSH_SEND_MODE = "form"

# NEW: verify SSL (đặt 0 nếu máy có chứng chỉ nội bộ)
PUSH_VERIFY_TLS = os.getenv("PUSH_VERIFY_TLS", "true").strip().lower() not in ("0", "false", "no")

# (Tuỳ chọn) In cấu hình khi khởi động để debug
print(f"[PUSH] url={PUSH_API_URL} verify_tls={PUSH_VERIFY_TLS} token_head={PUSH_API_TOKEN[:6]}***")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- SỬA LỖI & CẤU TRÚC LẠI ĐƯỜNG DẪN ---
# 1. Thư mục toàn cục cho Scheduler (không đổi)
GLOBAL_MEMORY_DIR = os.path.join(BASE_DIR, "memory_db")
JOBSTORE_DB_FILE = os.path.join(GLOBAL_MEMORY_DIR, "jobs.sqlite")
os.makedirs(GLOBAL_MEMORY_DIR, exist_ok=True)

# 2. Thư mục toàn cục cho file public (không đổi)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
# Thư mục này sẽ chứa file upload của *tất cả* user
# Chúng ta sẽ phân tách bằng tên file (uuid)
PUBLIC_FILES_DIR = os.path.join(PUBLIC_DIR, "files")
os.makedirs(PUBLIC_FILES_DIR, exist_ok=True)

# 3. Thư mục MỚI chứa TẤT CẢ dữ liệu riêng của người dùng
USER_DATA_ROOT = os.path.join(BASE_DIR, "user_data")
os.makedirs(USER_DATA_ROOT, exist_ok=True)

# 4. Thư mục CSDL User (MỚI)
USERS_DB_FILE = os.path.join(USER_DATA_ROOT, "users.sqlite")

# 5. Các thư mục con (SESSIONS, VECTOR) sẽ được tạo động theo user_id
# (Thêm vào khoảng dòng 100)
GETUSER_API_URL = os.getenv("GETUSER_API_URL", "https://ocrm.oshima.vn/api/method/getuserocrm")
CHANGEPASS_API_URL = os.getenv("CHANGEPASS_API_URL", "")
CHANGEPASS_API_URL="https://ocrm.oshima.vn/api/method/changepassword"
USER_SESSIONS_ROOT = os.path.join(USER_DATA_ROOT, "sessions")
USER_VECTOR_DB_ROOT = os.path.join(USER_DATA_ROOT, "vector_db")
os.makedirs(USER_SESSIONS_ROOT, exist_ok=True)
os.makedirs(USER_VECTOR_DB_ROOT, exist_ok=True)
# ----------------------------------------------
# (Thêm dòng này vào gần dòng 170)
USER_FACT_DICTS_ROOT = os.path.join(USER_DATA_ROOT, "fact_dictionaries")
os.makedirs(USER_FACT_DICTS_ROOT, exist_ok=True)


# NEW: timeout giây
PUSH_TIMEOUT = int(os.getenv("PUSH_TIMEOUT", "15"))

# Timezone VN
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Global Scheduler (khởi tạo 1 lần)
SCHEDULER: Optional[AsyncIOScheduler] = None
# Cấu hình nơi lưu trữ job (database)
jobstores = {
    'default': SQLAlchemyJobStore(url=f'sqlite:///{JOBSTORE_DB_FILE}')
}

# Theo dõi các “escalating reminders” đang chạy theo từng session
ACTIVE_ESCALATIONS = {}  # { internal_session_id: { "repeat_job_id": str, "acked": bool } }

# =========================================================
# 🔐 MỚI: Quản lý CSDL User (SQLite + Werkzeug)
# =========================================================
# (Thêm vào khoảng dòng 1040)

# (THAY THẾ HÀM NÀY - khoảng dòng 1040)

# (THAY THẾ HÀM NÀY - khoảng dòng 1040)

def _call_get_users_api() -> List[dict]:
    """
    (SYNC) Gọi API getuserocrm. 
    Trả về list user hoặc ném ra Exception nếu thất bại.
    (SỬA LỖI: Ưu tiên tìm key 'data' theo cấu trúc mới)
    """
    headers = {
        "Authorization": f"token {PUSH_API_TOKEN}",
    }
    print("📞 [Sync] Đang gọi API lấy danh sách user (dùng GET)...")
    try:
        resp = PUSH_SESSION.get( 
            GETUSER_API_URL,
            headers=headers,
            timeout=(3.05, PUSH_TIMEOUT),
            verify=PUSH_VERIFY_TLS,
        )
        
        if 200 <= resp.status_code < 300:
            data = resp.json()
            
            # --- LOGIC XỬ LÝ ĐÃ CẬP NHẬT (Ưu tiên 'data') ---

            # 1. (MỚI) Xử lý cấu trúc {'data': [...]} (Theo thông tin mới nhất)
            if isinstance(data, dict) and 'data' in data:
                # Đảm bảo "data" là list, nếu không cũng trả về rỗng
                print("✅ [Sync] API trả về cấu trúc {'data': [...]}. Đang xử lý...")
                return data['data'] if isinstance(data['data'], list) else []

            # 2. (Standard Frappe) {"message": [...]}
            if isinstance(data, dict) and 'message' in data:
                # Đảm bảo "message" là list, nếu không cũng trả về rỗng
                print("✅ [Sync] API trả về cấu trúc {'message': [...]}. Đang xử lý...")
                return data['message'] if isinstance(data['message'], list) else []

            # 3. (Standard API) [...] (bao gồm cả mảng rỗng [])
            if isinstance(data, list):
                print("✅ [Sync] API trả về cấu trúc mảng [...]. Đang xử lý...")
                return data

            # 4. Xử lý lỗi trong log: {}
            if isinstance(data, dict) and not data:
                print("⚠️ [Sync] API trả về {} (dict rỗng). Coi như danh sách trống.")
                return [] # Trả về mảng rỗng (an toàn)

            # 5. Nếu không khớp 4 trường hợp trên -> Báo lỗi
            raise ValueError(f"API trả về dữ liệu không mong đợi (không phải list, dict 'data', dict 'message', hay dict rỗng): {str(data)[:200]}")
            
        else:
            # Ném lỗi nếu API thất bại (4xx, 5xx)
            raise requests.RequestException(f"API Error {resp.status_code}: {resp.text[:300]}")
            
    except Exception as e:
        print(f"❌ [Sync] Lỗi nghiêm trọng khi gọi API User: {e}")
        raise # Ném lỗi ra để hàm sync_users bắt
    
    
    
@cl.password_auth_callback
async def auth_callback(email: str, password: str) -> Optional[cl.User]:
    """
    Đây là hàm xác thực MỚI, được Chainlit 2.x gọi tự động.
    """
    print(f"[Auth] Chainlit đang thử đăng nhập cho: {email}")
    
    # 1. Gọi hàm CSDL cũ của chúng ta
    user_data = await asyncio.to_thread(authenticate_user, email, password)
    
    if user_data:
        # 2. Đăng nhập thành công: Trả về một đối tượng cl.User
        # Chainlit sẽ tự động lưu user này vào session và cookie
        print(f"[Auth] Đăng nhập thành công cho: {email}")
        return cl.User(identifier=user_data["email"])
    else:
        # 3. Đăng nhập thất bại
        print(f"[Auth] Đăng nhập thất bại cho: {email}")
        return None
    
# (THAY THẾ HÀM NÀY - khoảng dòng 172)

@cl.on_chat_start
async def on_start_after_login():
    """
    Hàm này CHỈ CHẠY SAU KHI @cl.password_auth_callback thành công.
    (CẬP NHẬT: Lấy thêm 'name' vào session)
    """
    
    # 1. Lấy user object
    user = cl.user_session.get("user")
    if not user:
        await cl.Message(content="Lỗi: Không tìm thấy thông tin user sau khi đăng nhập.").send()
        return

    print(f"[Session] Đã đăng nhập. Bắt đầu setup cho: {user.identifier}")
    # --- 🚀 BẮT ĐẦU SỬA LỖI (THÊM 5 DÒNG NÀY VÀO ĐÂY) 🚀 ---
    # ID này dùng để phân biệt các tab/kết nối của CÙNG 1 user
    # (Dùng cho Hàng đợi và Nhắc leo thang)
    internal_session_id = str(uuid.uuid4())
    cl.user_session.set("chainlit_internal_id", internal_session_id)
    print(f"✅ [Session] Đã tạo Internal ID (Tab ID): {internal_session_id}")
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    # --- 🚀 BẮT ĐẦU CẬP NHẬT 🚀 ---
    # 1b. Lấy quyền Admin VÀ TÊN từ CSDL
    try:
        user_db_data = await asyncio.to_thread(get_user_by_email, user.identifier)
        
        is_admin = (user_db_data and user_db_data.get('is_admin') == 1)
        # Lấy tên (hoặc chuỗi rỗng nếu không có)
        user_name = (user_db_data and user_db_data.get('name')) or "" 
        
        cl.user_session.set("is_admin", is_admin)
        cl.user_session.set("user_name", user_name) # <-- LƯU TÊN VÀO SESSION
        
        if is_admin:
            print(f"🔑 [Session] User {user.identifier} LÀ ADMIN (Name: '{user_name}').")
        else:
             print(f"[Session] User {user.identifier} là user thường (Name: '{user_name}').")
             
    except Exception as e:
        print(f"❌ [Session] Lỗi khi kiểm tra quyền/tên admin: {e}")
        cl.user_session.set("is_admin", False)
        cl.user_session.set("user_name", "") # Đặt là rỗng nếu lỗi
    # --- 🚀 KẾT THÚC CẬP NHẬT 🚀 ---

    # 2. Khởi tạo Tổng đài (như cũ)
    global GLOBAL_MESSAGE_QUEUE, POLLER_STARTED
    if GLOBAL_MESSAGE_QUEUE is None:
        try:
            GLOBAL_MESSAGE_QUEUE = asyncio.Queue()
            print("✅ [Global] Hàng đợi TỔNG ĐÀI đã được khởi tạo.")
        except Exception as e:
            print(f"❌ [Global] Lỗi khởi tạo Hàng đợi Tổng: {e}")
            
    if not POLLER_STARTED:
        try:
            asyncio.create_task(global_broadcaster_poller())
            POLLER_STARTED = True
            print("✅ [Global] Đã khởi động TỔNG ĐÀI (Broadcaster).")
        except Exception as e:
            print(f"❌ [Global] Lỗi khởi động Tổng đài: {e}")

    # 3. Gọi hàm setup chat chính
    await setup_chat_session(user)
    
    
async def call_maybe_async(fn, *args, **kwargs):
    """Gọi hàm sync/async đều được: nếu sync thì bọc bằng cl.make_async."""
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return await cl.make_async(fn)(*args, **kwargs)
def _get_user_db_conn():
    """Tạo kết nối CSDL user."""
    return sqlite3.connect(USERS_DB_FILE)

# (THAY THẾ HÀM NÀY - khoảng dòng 204)
# (THAY THẾ HÀM NÀY - khoảng dòng 290)

def _update_user_db_schema():
    """Helper: Đảm bảo cột is_admin, is_active VÀ name tồn tại (dùng PRAGMA)."""
    conn = None
    try:
        conn = _get_user_db_conn()
        cursor = conn.cursor()
        
        # 1. Lấy thông tin schema
        cursor.execute("PRAGMA table_info(users);")
        columns = [row[1] for row in cursor.fetchall()] # row[1] là tên cột
        
        # 2. Kiểm tra 'is_admin'
        if 'is_admin' not in columns:
            print("⚠️ [Auth] Phát hiện CSDL cũ, đang thêm cột 'is_admin'...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0 NOT NULL")
            conn.commit()
            print("✅ [Auth] Đã thêm cột 'is_admin'.")
            
        # 3. Kiểm tra 'is_active'
        if 'is_active' not in columns:
            print("⚠️ [Auth] Phát hiện CSDL cũ, đang thêm cột 'is_active'...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 0 NOT NULL")
            conn.commit()
            print("✅ [Auth] Đã thêm cột 'is_active'.")
            
        # 4. (MỚI) Kiểm tra 'name'
        if 'name' not in columns:
            print("⚠️ [Auth] Phát hiện CSDL cũ, đang thêm cột 'name'...")
            cursor.execute("ALTER TABLE users ADD COLUMN name TEXT") # Mặc định là NULL
            conn.commit()
            print("✅ [Auth] Đã thêm cột 'name'.")
            
    except Exception as e_pragma:
        print(f"❌ [Auth] Lỗi khi kiểm tra schema CSDL 'users': {e_pragma}")
    finally:
        if conn: 
            conn.close()
            
# (THAY THẾ HÀM NÀY - khoảng dòng 226)
# (Dán hàm mới này vào khoảng dòng 370)

def _update_task_db_schema():
    """Helper: Đảm bảo cột description tồn tại trong user_tasks."""
    conn = None
    try:
        conn = _get_user_db_conn()
        cursor = conn.cursor()
        
        # 1. Lấy thông tin schema
        cursor.execute("PRAGMA table_info(user_tasks);")
        columns = [row[1] for row in cursor.fetchall()] # row[1] là tên cột
        
        # 2. (MỚI) Kiểm tra 'description'
        if 'description' not in columns:
            print("⚠️ [Auth/Task] Phát hiện CSDL cũ, đang thêm cột 'description' vào 'user_tasks'...")
            cursor.execute("ALTER TABLE user_tasks ADD COLUMN description TEXT") # Mặc định là NULL
            conn.commit()
            print("✅ [Auth/Task] Đã thêm cột 'description'.")
            
    except Exception as e_pragma:
        print(f"❌ [Auth/Task] Lỗi khi kiểm tra schema CSDL 'user_tasks': {e_pragma}")
    finally:
        if conn: 
            conn.close()
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 226)

def init_user_db():
    """
    Khởi tạo bảng users VÀ THÊM CỘT is_admin, is_active, name.
    (SỬA LỖI: CHỈ chạy sync blocking NẾU CSDL không tồn tại.)
    """
    
    # --- BƯỚC 1: Kiểm tra xem file CSDL đã tồn tại chưa ---
    db_existed = os.path.exists(USERS_DB_FILE)
    if db_existed:
        print(f"ℹ️ [Auth] Đã phát hiện file CSDL: {USERS_DB_FILE}")
    else:
        print(f"⚠️ [Auth] KHÔNG tìm thấy file CSDL. Sẽ tạo mới VÀ chạy sync blocking.")
    # ---------------------------------------------------

    conn = _get_user_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        login_token TEXT,
        token_expiry DATETIME,
        is_admin INTEGER DEFAULT 0 NOT NULL,
        is_active INTEGER DEFAULT 0 NOT NULL,
        name TEXT
    );
    """)
    conn.commit()
    conn.close()
    # === MỚI: Thêm bảng cho Checklist Công việc ===
    conn = _get_user_db_conn() # Mở lại kết nối
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date DATETIME NOT NULL,
        is_completed INTEGER DEFAULT 0 NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        recurrence_rule TEXT,
        scheduler_job_id TEXT 
    );
    """)
    conn.commit()
    conn.close()
    # === Kết thúc thêm bảng ===
    
    # Chạy hàm helper để cập nhật schema (dòng này đã có sẵn)
    _update_user_db_schema()
    _update_task_db_schema() # <-- THÊM DÒNG NÀY
    
    print(f"✅ [Auth] CSDL User đã sẵn sàng (có cột is_admin, is_active, name) tại {USERS_DB_FILE}")
    
    # --- BƯỚC 2: CHỈ chạy sync blocking nếu CSDL LÀ MỚI ---
    if not db_existed:
        try:
            print("🔄 [Startup Sync] CSDL mới, đang chạy đồng bộ lần đầu tiên (blocking)...")
            # Gọi hàm sync (blocking) NGAY LẬP TỨC
            _sync_users_from_api_sync()
            print("✅ [Startup Sync] Đồng bộ lần đầu hoàn tất.")
        except Exception as e_startup_sync:
            print(f"❌ [Startup Sync] Lỗi đồng bộ lần đầu: {e_startup_sync}")
    else:
        print("ℹ️ [Startup Sync] CSDL đã tồn tại, bỏ qua sync blocking (Scheduler sẽ chạy sau 5s).")
    # ----------------------------------------------------


def create_user(email: str, password: str) -> Tuple[bool, str]:
    """Tạo user mới. Trả về (True/False, Thông báo)."""
    if not email or not password:
        return False, "Email và mật khẩu không được rỗng."
    try:
        conn = _get_user_db_conn()
        cursor = conn.cursor()
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.lower(), hashed_pw))
        conn.commit()
        conn.close()
        return True, "Tạo tài khoản thành công."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Email này đã tồn tại."
    except Exception as e:
        conn.close()
        return False, f"Lỗi khi tạo tài khoản: {e}"

# (THAY THẾ HÀM NÀY - khoảng dòng 269)

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Kiểm tra email/password VÀ TRẠNG THÁI is_active.
    Trả về dict user nếu đúng, None nếu sai.
    """
    try:
        conn = _get_user_db_conn()
        conn.row_factory = sqlite3.Row # Trả về dạng dict
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            # --- MỚI: KIỂM TRA IS_ACTIVE ---
            if user["is_active"] == 1:
                return dict(user) # Đăng nhập thành công
            else:
                # Mật khẩu đúng, nhưng tài khoản bị khóa
                print(f"[Auth] Lỗi: User {email} đăng nhập (đúng pass) nhưng tài khoản đã bị VÔ HIỆU HÓA (is_active=0).")
                return None # Thất bại
        
        # Mật khẩu sai hoặc user không tồn tại
        return None
        
    except Exception as e:
        print(f"[Auth] Lỗi authenticate_user: {e}")
        return None
    
    
    
def get_user_by_email(email: str) -> Optional[dict]:
    """(MỚI) Lấy thông tin user (dạng dict) từ CSDL bằng email."""
    try:
        conn = _get_user_db_conn()
        conn.row_factory = sqlite3.Row # Trả về dạng dict
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        print(f"[Auth] Lỗi get_user_by_email: {e}")
        return None

# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 350)

def _get_note_by_id_db(vectorstore: Chroma, doc_id: str) -> Optional[str]:
    """(SYNC) Lấy nội dung văn bản đầy đủ của 1 doc_id."""
    try:
        result = vectorstore._collection.get(
            ids=[doc_id],
            include=["documents"]
        )
        docs = result.get("documents", [])
        if docs:
            return docs[0]
        return None
    except Exception as e:
        print(f"❌ Lỗi _get_note_by_id_db: {e}")
        return None
def _delete_task_by_title_db(user_email: str, title_query: str) -> int:
    """(SYNC) Tìm và xóa (các) công việc CHƯA HOÀN THÀNH khớp với tên."""
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Tìm tất cả các task CHƯA HOÀN THÀNH khớp với query
    # (Dùng LIKE để khớp một phần, ví dụ "báo cáo" sẽ khớp "hoàn thành báo cáo")
    query = "SELECT id FROM user_tasks WHERE user_email = ? AND title LIKE ? AND is_completed = 0"
    params = (user_email.lower(), f"%{title_query}%")
    
    cursor.execute(query, params)
    tasks_to_delete = cursor.fetchall()
    
    if not tasks_to_delete:
        conn.close()
        return 0 # Không tìm thấy gì

    deleted_count = 0
    # 2. Lặp qua và xóa từng cái (để nó hủy job scheduler)
    for task in tasks_to_delete:
        task_id = task['id']
        # Gọi hàm xóa an toàn (_delete_task_db) mà chúng ta đã có
        if _delete_task_db(task_id, user_email):
            deleted_count += 1
            
    conn.close() # _delete_task_db tự mở/đóng, nhưng ta đóng ở đây cho chắc
    print(f"[TaskDB] Đã xóa {deleted_count} công việc bằng tên: '{title_query}'")
    return deleted_count
# (Dán hàm MỚI này vào khoảng dòng 520)

# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 520)
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 520)

def _delete_note_by_content_db(vectorstore: Chroma, content_query: str) -> int:
    """(SYNC) Tìm và xóa ghi chú (text) gần giống nhất trong ChromaDB."""
    try:
        # 1. Tìm 1 văn bản gần giống nhất (query)
        #    NHƯNG phải lọc ra các loại đặc biệt
        results = vectorstore._collection.query(
            query_texts=[content_query],
            n_results=1,
            where={
                "$and": [
                    # --- SỬA LỖI SYNTAX $not ---
                    # $not là toán tử logic, nó phải bọc ngoài field
                    {"$not": {"document": {"$regex": r"^\[FILE\]"}}},
                    {"$not": {"document": {"$regex": r"^\[IMAGE\]"}}},
                    {"$not": {"document": {"$regex": r"^\[REMINDER_"}}},
                    {"$not": {"document": {"$regex": r"^\[ERROR_"}}},
                    {"$not": {"document": {"$regex": r"^\[FILE_UNSUPPORTED\]"}}},
                    {"$not": {"document": {"$regex": r"^Trích từ tài liệu:"}}},
                    {"$not": {"document": {"$regex": r"^FACT:"}}}
                    # --- KẾT THÚC SỬA LỖI ---
                ]
            }
        )
        
        ids_to_delete = results.get("ids", [[]])[0] # Lấy list ID của query 1
        
        if not ids_to_delete:
            return 0
            
        # 2. Xóa
        vectorstore._collection.delete(ids=ids_to_delete)
        print(f"[NoteDB] Đã xóa {len(ids_to_delete)} ghi chú (vector query): '{content_query}'")
        return len(ids_to_delete)
        
    except Exception as e:
        # In lỗi đầy đủ để debug
        import traceback
        print(f"❌ Lỗi _delete_note_by_content_db:")
        traceback.print_exc()
        return 0 # Trả về 0 nếu lỗi
# (Dán hàm MỚI này vào khoảng dòng 550)

def _delete_reminder_by_text_db(text_query: str) -> int:
    """(SYNC) Tìm và xóa các job trong Scheduler khớp với nội dung."""
    
    if not SCHEDULER:
        return 0
        
    deleted_count = 0
    try:
        jobs = SCHEDULER.get_jobs()
        # Cần duyệt qua 1 list cố định vì ta sẽ thay đổi list gốc
        for job in list(jobs):
            # Job của chúng ta lưu text trong job.args[1]
            try:
                job_text = job.args[1]
                # So sánh (không phân biệt chữ hoa/thường, khớp một phần)
                if text_query.lower() in job_text.lower():
                    # Gọi hàm remove_reminder an toàn (đã có ở dòng 1020)
                    ok, msg = remove_reminder(job.id, job.args[0])
                    if ok:
                        deleted_count += 1
            except (IndexError, TypeError):
                # Job này không phải job nhắc nhở (ví dụ: sync_users_job)
                continue
                
    except Exception as e:
        print(f"❌ Lỗi _delete_reminder_by_text_db: {e}")
        return 0
        
    print(f"[RemDB] Đã xóa {deleted_count} nhắc nhở khớp với: '{text_query}'")
    return deleted_count
def _change_user_password_sync(email: str, new_password: str) -> Tuple[bool, str]:
    """
    (SYNC) Cập nhật mật khẩu (đã băm) cho một user.
    (SỬA ĐỔI: Gọi API đồng bộ bên ngoài sau khi thành công.)
    """
    if not email or not new_password:
        return False, "❌ Lỗi: Email và mật khẩu mới không được rỗng."
    
    if len(new_password) < 6:
        return False, "❌ Lỗi: Mật khẩu mới phải có ít nhất 6 ký tự."
        
    conn = None # Khai báo conn ở ngoài để
    
    try:
        new_hashed_pw = generate_password_hash(new_password)
        
        conn = _get_user_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (new_hashed_pw, email.lower())
        )
        
        updated_rows = cursor.rowcount
        conn.commit() # Commit CSDL local
        conn.close()  # Đóng CSDL local
        
        if updated_rows > 0:
            # --- MỚI: CSDL local OK -> Bắt đầu gọi API đồng bộ ---
            print(f"[ChangePass] CSDL local đã cập nhật cho {email}. Đang gọi API đồng bộ...")
            
            # Gọi hàm API (sync) chúng ta vừa tạo
            api_ok, api_status, api_text = _call_change_password_api(email.lower(), new_password)
            
            if api_ok:
                msg = f"✅ Đã đổi mật khẩu cho {email} (Cả local & API Sync OK)."
            else:
                msg = f"⚠️ Đã đổi mật khẩu cho {email} (Local OK), nhưng API Sync THẤT BẠI (Status: {api_status}, Resp: {api_text[:100]})."
            
            return True, msg
            # ----------------------------------------------------
        else:
            return False, f"⚠️ Không tìm thấy user nào có email: {email}. (Chưa làm gì cả)."
            
    except Exception as e:
        if conn: conn.close()
        return False, f"❌ Lỗi CSDL nghiêm trọng khi đổi mật khẩu: {e}"
    
    
def create_login_token(user_id: int) -> str:
    """Tạo, lưu và trả về một token đăng nhập 3 ngày.""" # <-- Sửa
    conn = _get_user_db_conn()
    cursor = conn.cursor()
    token = uuid.uuid4().hex
    expiry = datetime.now() + timedelta(days=3) # <-- SỬA Ở ĐÂY
    cursor.execute(
        "UPDATE users SET login_token = ?, token_expiry = ? WHERE id = ?",
        (token, expiry, user_id)
    )
    conn.commit()
    conn.close()
    return token

def validate_login_token(token: str) -> Optional[dict]:
    """Kiểm tra token và ngày hết hạn. Trả về user dict nếu hợp lệ."""
    try:
        conn = _get_user_db_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE login_token = ? AND token_expiry > ?",
            (token, datetime.now())
        )
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        print(f"[Auth] Lỗi validate_login_token: {e}")
        return None

def _sanitize_user_id_for_path(user_email: str) -> str:
    """Biến email thành tên thư mục an toàn."""
    # Thay @ và . bằng _
    safe_name = re.sub(r"[@\.]", "_", user_email)
    # Xóa các ký tự không an toàn còn lại
    return re.sub(r"[^a-zA-Z0-9_\-]", "", safe_name)

# =========================================================
# ️ MỚI: Quản lý Checklist Công việc (Tasks)
# =========================================================

def _add_task_to_db(
    user_email: str, 
    title: str, 
    description: Optional[str], # <-- THÊM VÀO
    due_date: datetime, 
    recurrence_rule: Optional[str],
    scheduler_job_id: Optional[str]
) -> int:
    """(SYNC) Thêm một công việc mới vào CSDL và trả về ID của nó."""
    conn = _get_user_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_tasks 
        (user_email, title, description, due_date, recurrence_rule, scheduler_job_id, is_completed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (user_email.lower(), title, description, due_date, recurrence_rule, scheduler_job_id) # <-- THÊM VÀO
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"[TaskDB] Đã lưu Task ID: {new_id} cho {user_email}")
    return new_id

def _mark_task_complete_db(task_id: int, user_email: str) -> bool:
    """(SYNC) Đánh dấu một công việc là đã hoàn thành."""
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Lấy thông tin job_id trước khi xóa
    cursor.execute("SELECT scheduler_job_id FROM user_tasks WHERE id = ? AND user_email = ?", (task_id, user_email.lower()))
    task = cursor.fetchone()
    
    if task and task['scheduler_job_id']:
        # 2. Hủy lịch push trong Scheduler
        try:
            if SCHEDULER:
                SCHEDULER.remove_job(task['scheduler_job_id'])
            print(f"[TaskDB] Đã hủy Job Scheduler: {task['scheduler_job_id']}")
        except Exception as e:
            print(f"[TaskDB] Lỗi khi hủy job {task['scheduler_job_id']}: {e} (Có thể job đã chạy)")

    # 3. Đánh dấu hoàn thành trong CSDL
    cursor.execute(
        "UPDATE user_tasks SET is_completed = 1, scheduler_job_id = NULL WHERE id = ? AND user_email = ?",
        (task_id, user_email.lower())
    )
    updated_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"[TaskDB] Đã đánh dấu hoàn thành Task ID: {task_id}")
    return updated_rows > 0

def _get_tasks_from_db(user_email: str, status: str = "uncompleted") -> List[dict]:
    """
    (SYNC) Lấy danh sách công việc của user.
    status: 'uncompleted', 'completed', 'all'
    """
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    base_query = "SELECT id, title, description, due_date, recurrence_rule, is_completed FROM user_tasks WHERE user_email = ?"
    params = [user_email.lower()]
    
    if status == "uncompleted":
        base_query += " AND is_completed = 0"
    elif status == "completed":
        base_query += " AND is_completed = 1"
    # (Nếu là 'all', không thêm gì)
        
    base_query += " ORDER BY due_date ASC"
        
    cursor.execute(base_query, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

# (Dán hàm mới này vào khoảng dòng 472)
def _delete_task_db(task_id: int, user_email: str) -> bool:
    """(SYNC) Xóa một công việc (và hủy lịch job) khỏi CSDL."""
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Lấy thông tin job_id trước khi xóa
    cursor.execute("SELECT scheduler_job_id FROM user_tasks WHERE id = ? AND user_email = ?", (task_id, user_email.lower()))
    task = cursor.fetchone()
    
    if task and task['scheduler_job_id']:
        # 2. Hủy lịch push trong Scheduler
        try:
            if SCHEDULER:
                SCHEDULER.remove_job(task['scheduler_job_id'])
            print(f"[TaskDB] Đã hủy Job Scheduler (khi xóa): {task['scheduler_job_id']}")
        except Exception as e:
            print(f"[TaskDB] Lỗi khi hủy job {task['scheduler_job_id']}: {e} (Có thể job đã chạy)")

    # 3. Xóa vĩnh viễn khỏi CSDL
    cursor.execute(
        "DELETE FROM user_tasks WHERE id = ? AND user_email = ?",
        (task_id, user_email.lower())
    )
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"[TaskDB] Đã XÓA vĩnh viễn Task ID: {task_id}")
    return deleted_rows > 0


# =========================================================
# 💬 Action Callbacks (UI) - (Bắt đầu từ dòng 2390)
# =========================================================
# (Đổi tên hàm và thêm nút Xóa)
async def ui_show_uncompleted_tasks():
    """(MỚI) Hiển thị tất cả công việc CHƯA HOÀN THÀNH."""
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    # Sửa: Gọi hàm CSDL với status='uncompleted'
    tasks = await asyncio.to_thread(_get_tasks_from_db, user_id_str, status="uncompleted")
    
    if not tasks:
        await cl.Message(content="🎉 Bạn không có công việc nào chưa hoàn thành!").send()
        return

    await cl.Message(content=f"📝 **Danh sách {len(tasks)} công việc chưa hoàn thành:**").send()
    
    for task in tasks:
        due_date_str = task['due_date']
        try:
            due_date_dt = dtparser.parse(due_date_str)
            due_date_str = _fmt_dt(due_date_dt)
        except Exception:
            pass
            
        description = task.get('description')
        desc_str = f" - *{description}*" if description else ""
        
        msg_content = f"**{task['title']}** (Hạn: `{due_date_str}`){desc_str}"
        msg = cl.Message(content=msg_content)

        # --- NÂNG CẤP NÚT BẤM ---
        actions = [
            cl.Action(
                name="complete_task", 
                payload={"task_id": task["id"], "message_id": msg.id},
                label="✅ Hoàn thành"
            ),
            cl.Action(
                name="delete_task", # <-- THÊM NÚT XÓA
                payload={"task_id": task["id"], "message_id": msg.id},
                label="🗑️ Xóa"
            )
        ]
        # --- KẾT THÚC NÂNG CẤP ---
        
        msg.actions = actions
        await msg.send()
        
# (Dán hàm MỚI này vào khoảng dòng 2440)
async def ui_show_completed_tasks():
    """(MỚI) Hiển thị tất cả công việc ĐÃ HOÀN THÀNH."""
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    # Sửa: Gọi hàm CSDL với status='completed'
    tasks = await asyncio.to_thread(_get_tasks_from_db, user_id_str, status="completed")
    
    if not tasks:
        await cl.Message(content="📭 Bạn chưa hoàn thành công việc nào.").send()
        return

    await cl.Message(content=f"✅ **Danh sách {len(tasks)} công việc đã hoàn thành:**").send()
    
    for task in tasks:
        due_date_str = task['due_date']
        try:
            due_date_dt = dtparser.parse(due_date_str)
            due_date_str = _fmt_dt(due_date_dt)
        except Exception:
            pass
            
        description = task.get('description')
        desc_str = f" - *{description}*" if description else ""
        
        # Sửa: Hiển thị khác (không có Hạn chót, thêm [XONG])
        msg_content = f"**[XONG] {task['title']}**{desc_str}"
        msg = cl.Message(content=msg_content)

        # --- NÂNG CẤP NÚT BẤM ---
        actions = [
            cl.Action(
                name="delete_task", # <-- CHỈ CÓ NÚT XÓA
                payload={"task_id": task["id"], "message_id": msg.id},
                label="🗑️ Xóa"
            )
        ]
        # --- KẾT THÚC NÂNG CẤP ---
        
        msg.actions = actions
        await msg.send()
# (Dán hàm MỚI này vào khoảng dòng 2465)
@cl.action_callback("delete_task")
async def _on_delete_task(action: cl.Action):
    """(MỚI) Xử lý khi bấm nút 'Xóa' công việc."""
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    task_id = action.payload.get("task_id")
    message_id = action.payload.get("message_id") 
    
    if not task_id:
        await cl.Message(content="❌ Lỗi: Không nhận được task_id.").send()
        return

    try:
        ok = await asyncio.to_thread(_delete_task_db, task_id, user_id_str)
        if ok:
            if message_id:
                try:
                    msg_to_remove = cl.Message.get(message_id)
                    if msg_to_remove:
                        await msg_to_remove.remove()
                except Exception as e_remove:
                    print(f"Lỗi khi xóa message {message_id}: {e_remove}")
            
            await cl.Message(content=f"🗑️ Đã xóa công việc!").send()
        else:
            await cl.Message(content=f"⚠️ Không thể xóa công việc (ID: {task_id}).").send()
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi khi xóa công việc: {e}").send()
        
        
@cl.action_callback("complete_task")
async def _on_complete_task(action: cl.Action):
    """(MỚI) Xử lý khi bấm nút 'Hoàn thành' công việc."""
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    # --- SỬA LỖI Ở ĐÂY ---
    task_id = action.payload.get("task_id")
    message_id = action.payload.get("message_id") # <-- Lấy ID tin nhắn
    
    if not task_id:
        await cl.Message(content="❌ Lỗi: Không nhận được task_id.").send()
        return

    try:
        ok = await asyncio.to_thread(_mark_task_complete_db, task_id, user_id_str)
        if ok:
            # Dùng message_id để xóa tin nhắn gốc
            if message_id:
                try:
                    msg_to_remove = cl.Message.get(message_id)
                    if msg_to_remove:
                        await msg_to_remove.remove()
                except Exception as e_remove:
                    print(f"Lỗi khi xóa message {message_id}: {e_remove}")
            
            await cl.Message(content=f"✅ Đã hoàn thành công việc!").send()
        else:
            await cl.Message(content=f"⚠️ Không thể cập nhật công việc (ID: {task_id}).").send()
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi khi hoàn thành công việc: {e}").send()
    # --- KẾT THÚC SỬA LỖI ---




def _push_task_notification(internal_session_id: str, task_title: str, task_id: int):
    """(SYNC) Hàm này được Scheduler gọi để push thông báo Task."""
    print(f"[TaskPush] Đang push cho Task ID: {task_id} ({task_title})")
    
    # Chỉ push, không quản lý leo thang
    _do_push(internal_session_id, f"Đến hạn công việc: {task_title}")
# =========================================================
# =========================================================
# 📇 MỚI: Quản lý Từ điển Fact (Fact Dictionary)
# =========================================================

def get_user_fact_dict_path(user_id_str: str) -> str:
    """Lấy đường dẫn file JSON từ điển fact của user."""
    safe_name = _sanitize_user_id_for_path(user_id_str)
    # Lưu file từ điển trong thư mục riêng của user
    user_dir = get_user_vector_dir(user_id_str) 
    return os.path.join(user_dir, "fact_map.json")

def load_user_fact_dict(user_id_str: str) -> dict:
    """Tải từ điển fact của user từ file JSON."""
    path = get_user_fact_dict_path(user_id_str)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi đọc fact dict {user_id_str}: {e}")
    return {} # Trả về dict rỗng nếu lỗi hoặc không tồn tại

def save_user_fact_dict(user_id_str: str, data: dict):
    """Lưu từ điển fact của user vào file JSON."""
    path = get_user_fact_dict_path(user_id_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi lưu fact dict {user_id_str}: {e}")

async def call_llm_to_classify(llm: ChatOpenAI, question: str, existing_keys: List[str]) -> str:
    """
    Gọi LLM để phân loại câu hỏi thành một fact_key (mới hoặc cũ).
    """
    # Lọc ra các key duy nhất và hợp lệ
    valid_keys = sorted(list(set(k for k in existing_keys if k and isinstance(k, str))))
    keys_str = ", ".join([f"'{k}'" for k in valid_keys])
    if not keys_str:
        keys_str = "(chưa có key nào)"
        
    prompt_text = f"""Bạn là một chuyên gia phân loại 'fact_key'.

Câu hỏi của người dùng: "{question}"
Các fact_key hiện có: [{keys_str}]

Nhiệm vụ của bạn:
1. Đọc kỹ câu hỏi.
2. Quyết định xem nó có khớp với một trong các fact_key HIỆN CÓ hay không.
   (Ví dụ: nếu câu hỏi là 'tôi thích uống gì' và key 'so_thich_do_uong' đã tồn tại, HÃY DÙNG LẠI key 'so_thich_do_uong').
3. Nếu không khớp, hãy TẠO RA một fact_key MỚI, ngắn gọn, dùng gạch dưới (snake_case) để mô tả câu hỏi này (ví dụ: 'vat_nuoi', 'so_thich_an_uong', 'dia_chi_cong_ty').
4. Chỉ trả về 1 fact_key (ví dụ: 'so_thich_an_uong') và KHÔNG CÓ BẤT KỲ GIẢI THÍCH NÀO.
"""
    try:
        resp = await llm.ainvoke(prompt_text)
        # Dọn dẹp output của LLM
        fact_key = resp.content.strip().strip("`'\"").replace(" ", "_")
        # Đảm bảo nó là snake_case
        fact_key = re.sub(r"[^a-z0-9_]", "", fact_key.lower())
        
        if not fact_key:
            return "general_query" # Key dự phòng
            
        return fact_key
        
    except Exception as e:
        print(f"Lỗi call_llm_to_classify: {e}")
        return "general_query" # Key dự phòng
    
# 🧠 LangChain + OpenAI + Vector (Đã sửa đổi)
# =========================================================
# Embeddings (toàn cục, vì nó không có state)
embeddings = OpenAIEmbeddings(
    api_key=OPENAI_API_KEY,
    model="text-embedding-3-small"
)

# --- SỬA ĐỔI: Không khởi tạo vectorstore/retriever toàn cục ---
# Chúng sẽ được khởi tạo theo user sau khi đăng nhập.

def get_user_vector_dir(user_id_str: str) -> str:
    """Lấy đường dẫn thư mục vector DB của user (và tạo nếu chưa có)."""
    safe_user_dir = _sanitize_user_id_for_path(user_id_str)
    user_dir = os.path.join(USER_VECTOR_DB_ROOT, safe_user_dir)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

# THAY THẾ TOÀN BỘ HÀM NÀY (khoảng dòng 214)
# THAY THẾ TOÀN BỘ HÀM NÀY (khoảng dòng 214)

def get_user_vectorstore_retriever(user_id_str: str) -> Tuple[Chroma, any]:
    """MỚI: Khởi tạo Vectorstore và Retriever cho 1 user cụ thể."""
    persist_directory = get_user_vector_dir(user_id_str)
    
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
        collection_name="memory"
    )
    # QUAY LẠI CÀI ĐẶT GỐC (K=5).
    # "threshold" quá nghiêm ngặt.
    # "mmr" cũng không cần thiết.
    # Hãy để Retriever lấy 5 kết quả GẦN NHẤT.
    # GPT (RAG) sẽ quyết định xem chúng có hữu ích hay không.
    retriever = vectorstore.as_retriever(search_kwargs={"k": 20})
    
    print(f"✅ VectorStore cho user '{user_id_str}' đã sẵn sàng tại {persist_directory} (mode=Similarity K=20)")
    return vectorstore, retriever

# ---------------------------------------------------------

print("🤖 [Global Setup] Khởi tạo môi trường...")

# =========================================================
# 💬 Quản lý nhiều hội thoại (lưu file) - (Đã sửa đổi)
# =========================================================
def get_user_sessions_dir(user_id_str: str) -> str:
    """Lấy đường dẫn thư mục session của user (và tạo nếu chưa có)."""
    safe_user_dir = _sanitize_user_id_for_path(user_id_str)
    user_dir = os.path.join(USER_SESSIONS_ROOT, safe_user_dir)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def session_file_path(user_id_str: str, session_id: str) -> str:
    """SỬA ĐỔI: Lấy đường dẫn file session CỦA USER."""
    user_dir = get_user_sessions_dir(user_id_str)
    return os.path.join(user_dir, f"{session_id}.json")

def save_chat_history(user_id_str: str, session_id: str, chat_history: list):
    """SỬA ĐỔI: Thêm user_id_str."""
    try:
        path = session_file_path(user_id_str, session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu hội thoại {user_id_str}/{session_id}: {e}")

def load_chat_history(user_id_str: str, session_id: str) -> list:
    """SỬA ĐỔI: Thêm user_id_str."""
    path = session_file_path(user_id_str, session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi khi đọc hội thoại {user_id_str}/{session_id}: {e}")
    return []

def delete_session(user_id_str: str, session_id: str) -> bool:
    """SỬA ĐỔI: Thêm user_id_str."""
    path = session_file_path(user_id_str, session_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
# (THAY THẾ HÀM NÀY - khoảng dòng 621)
def list_sessions(user_id_str: str) -> List[dict]:
    """
    SỬA ĐỔI: Lấy danh sách session CỦA USER.
    Đọc file JSON để lấy tin nhắn đầu tiên làm label.
    Trả về List[dict] với 'session_id' và 'label'.
    """
    user_dir = get_user_sessions_dir(user_id_str)
    sessions_data = []
    
    for f in os.listdir(user_dir):
        if not f.endswith(".json"):
            continue
            
        file_path = os.path.join(user_dir, f)
        session_id = f[:-5] # "session_2025..."
        label = session_id # Tên dự phòng
        mod_time = 0
        
        try:
            mod_time = os.path.getmtime(file_path)
            
            # --- MỚI: Đọc file JSON để lấy label ---
            with open(file_path, "r", encoding="utf-8") as json_file:
                chat_history = json.load(json_file)
                
                # Tìm tin nhắn 'user' đầu tiên
                first_user_message = "" # Bắt đầu rỗng
                if isinstance(chat_history, list):
                    for msg in chat_history:
                        role = (msg.get("role") or "").lower()
                        content = (msg.get("content") or "").strip()
                        if role == "user" and content:
                            first_user_message = content
                            break
                
                if not first_user_message:
                    first_user_message = "(Hội thoại trống)"
                
                # Cắt ngắn nếu quá dài
                if len(first_user_message) > 50:
                    label = first_user_message[:50] + "..."
                else:
                    label = first_user_message
            # --- KẾT THÚC ĐỌC FILE ---
            
            sessions_data.append({
                "session_id": session_id,
                "label": label,
                "mod_time": mod_time
            })
            
        except Exception as e:
            # Nếu lỗi (ví dụ file rỗng), vẫn thêm vào
            print(f"Lỗi khi đọc session {file_path}: {e}")
            sessions_data.append({
                "session_id": session_id,
                "label": label, # Dùng tên dự phòng
                "mod_time": mod_time
            })
    
    # Sắp xếp theo thời gian (mới nhất trước)
    sorted_sessions = sorted(sessions_data, key=lambda x: x["mod_time"], reverse=True)
    return sorted_sessions

# =========================================================
# 🖼️ & 🗂️ Lưu ảnh / file + ghi chú vào vectorstore (Đã sửa đổi)
# =========================================================
def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')

# TÌM VÀ THAY THẾ HÀM NÀY (khoảng dòng 527)
def _save_image_and_note(
    vectorstore: Chroma,
    src_path: str, 
    user_text: str, 
    original_name: str,
    fact_key: str = "general" # <-- THÊM VÀO
) -> Tuple[str, str]:
    """
    (SỬA LỖI) Copy ảnh vào ./public/files và ghi 1 dòng note [IMAGE]
    VỚI ĐẦY ĐỦ METADATA (name=, path=, note=, fact_key=).
    """
    name = original_name or os.path.basename(src_path) or f"image-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or '.jpg'}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name) 
    shutil.copyfile(src_path, dst)
    
    # THÊM fact_key VÀO ĐÂY
    note = f"[IMAGE] path={dst} | name={name} | note={user_text.strip() or '(no note)'} | fact_key={fact_key}"
    vectorstore.add_texts([note])
    
    return dst, name

# TÌM VÀ THAY THẾ HÀM NÀY (khoảng dòng 551)
def _save_file_and_note(
    vectorstore: Chroma,
    src_path: str, 
    original_name: Optional[str], 
    user_text: str,
    fact_key: str = "general" # <-- THÊM VÀO
) -> Tuple[str, str]:
    """
    Copy file bất kỳ vào ./public/files và ghi 1 dòng note [FILE] vào vectorstore.
    Trả về (dst_path, stored_name) để hiển thị.
    """
    name = original_name or os.path.basename(src_path) or f"file-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or ''}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name)
    shutil.copyfile(src_path, dst)
    
    # THÊM fact_key VÀO ĐÂY
    note = f"[FILE] path={dst} | name={name} | note={user_text.strip() or '(no note)'} | fact_key={fact_key}"
    vectorstore.add_texts([note])
    return dst, name

def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Tạo một text splitter tiêu chuẩn."""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )

# TÌM VÀ THAY THẾ HÀM NÀY (khoảng dòng 590)
def _load_and_process_document(
    vectorstore: Chroma,
    src_path: str, 
    original_name: str, 
    mime_type: str, 
    user_note: str,
    fact_key: str = "general" # <-- THÊM VÀO
) -> Tuple[int, str]:
    """
    Đọc, xử lý, cắt nhỏ và lưu nội dung tài liệu vào vectorstore CỦA USER.
    (Đã thêm fact_key)
    Trả về (số lượng chunks, tên file).
    """
    
    text_content = ""
    # THÊM fact_key VÀO ĐÂY
    metadata_note = f"Trích từ tài liệu: {original_name} | Ghi chú của người dùng: {user_note} | fact_key={fact_key}"

    try:
        # 1. Đọc nội dung dựa trên loại file
        if "excel" in mime_type or src_path.endswith((".xlsx", ".xls")):
            # ... (giữ nguyên logic đọc excel)
            df_dict = pd.read_excel(src_path, sheet_name=None)
            all_text = []
            for sheet_name, df in df_dict.items():
                md_table = df.to_markdown(index=False) 
                all_text.append(f"--- Sheet: {sheet_name} ---\n{md_table}")
            text_content = "\n\n".join(all_text)
            
        elif "pdf" in mime_type:
            # ... (giữ nguyên logic đọc pdf)
            reader = pypdf.PdfReader(src_path)
            all_text = [page.extract_text() or "" for page in reader.pages]
            text_content = "\n".join(all_text)
            
        elif "wordprocessingml" in mime_type or src_path.endswith(".docx"):
            # ... (giữ nguyên logic đọc docx)
            doc = docx.Document(src_path)
            all_text = [p.text for p in doc.paragraphs]
            text_content = "\n".join(all_text)
            
        elif "text" in mime_type or src_path.endswith((".txt", ".md", ".py", ".js")):
            # ... (giữ nguyên logic đọc text)
            with open(src_path, "r", encoding="utf-8") as f:
                text_content = f.read()
                
        else:
            # THÊM fact_key VÀO ĐÂY
            note = f"[FILE_UNSUPPORTED] path={src_path} | name={original_name} | note={user_note} | fact_key={fact_key}"
            vectorstore.add_texts([note])
            # Vẫn lưu file (truyền fact_key)
            _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key) # <-- SỬA
            return 0, original_name

        if not text_content.strip():
            raise ValueError("File rỗng hoặc không thể trích xuất nội dung.")

        # 2. Cắt nhỏ (Chunking)
        text_splitter = _get_text_splitter()
        chunks = text_splitter.split_text(text_content)
        
        # 3. Thêm metadata (nguồn gốc) vào mỗi chunk (đã chứa fact_key)
        chunks_with_metadata = [
            f"{metadata_note}\n\n[NỘI DUNG CHUNK]:\n{chunk}"
            for chunk in chunks
        ]

        # 4. Lưu vào Vectorstore CỦA USER
        vectorstore.add_texts(chunks_with_metadata)
        
        # 5. Vẫn copy file vào 'public/files' để lưu trữ (truyền fact_key)
        _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key) # <-- SỬA
        
        return len(chunks_with_metadata), original_name

    except Exception as e:
        print(f"[ERROR] _load_and_process_document failed: {e}")
        # THÊM fact_key VÀO ĐÂY
        error_note = f"[ERROR_PROCESSING_FILE] name={original_name} | note={user_note} | error={e} | fact_key={fact_key}"
        vectorstore.add_texts([error_note])
        raise
    
# =========================================================
# 🧩 Tiện ích xem bộ nhớ (Đã sửa đổi)
# =========================================================
def dump_all_memory_texts(vectorstore: Chroma) -> str: # <-- SỬA
    """SỬA ĐỔI: Nhận vectorstore của user."""
    try:
        raw = vectorstore._collection.get()
        docs = raw.get("documents", []) or []
        if not docs:
            return "📭 Bộ nhớ đang trống. Chưa lưu gì cả."
        return "\n".join([f"{i+1}. {d}" for i, d in enumerate(docs)])
    except Exception as e:
        return f"⚠️ Không đọc được bộ nhớ: {e}"

def list_active_files(vectorstore: Chroma) -> list[dict]: # <-- SỬA
    """SỬA ĐỔI: Quét ChromaDB của user."""
    out = []
    try:
        data = vectorstore._collection.get(
            where_document={"$or": [
                {"$contains": "[FILE]"},
                {"$contains": "[IMAGE]"}
            ]},
            include=["documents"]
        )
        
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        
        for doc_id, content in zip(ids, docs):
            if not content: continue
            
            path_match = re.search(r"path=([^|]+)", content)
            name_match = re.search(r"name=([^|]+)", content)
            note_match = re.search(r"note=([^|]+)", content)

            file_path = path_match.group(1).strip() if path_match else "unknown"
            file_name = name_match.group(1).strip() if name_match else "unknown"
            user_note = note_match.group(1).strip() if note_match else "(không có)"
            
            # SỬA: path bây giờ là /public/files/tên_đã_uuid
            saved_name = os.path.basename(file_path)
            
            out.append({
                "doc_id": doc_id,
                "file_path": file_path, # Đường dẫn tuyệt đối trên disk server
                "saved_name": saved_name, # Tên file trong /public/files
                "original_name": file_name,
                "note": user_note,
                "type": "[IMAGE]" if "[IMAGE]" in content else "[FILE]"
            })
            
    except Exception as e:
        import traceback
        print("[ERROR] Lỗi nghiêm trọng trong list_active_files:")
        print(traceback.format_exc())
        
    return sorted(out, key=lambda x: (x["original_name"]))


# =========================================================
# 🧠 Trích FACT (SỬ DỤNG LLM) - (Hàm mới)
# =========================================================
async def _extract_fact_from_llm(llm: ChatOpenAI, noi_dung: str) -> List[str]:
    """
    Sử dụng LLM để tự động phân loại văn bản thành "Fact" (sự thật).
    Thay thế cho hàm _extract_facts() thủ công.
    """
    
    # Prompt yêu cầu LLM phân loại
    prompt_template = f"""Bạn là một chuyên gia trích xuất "Fact" (sự thật) từ văn bản.

Văn bản của người dùng: "{noi_dung}"

Nhiệm vụ của bạn:
1. Phân tích văn bản.
2. Nếu nó chứa một thông tin cốt lõi (tên, sđt, sở thích, địa chỉ, thông tin cá nhân, vật nuôi, v.v.), hãy tạo một "fact_key" (dạng snake_case, ví dụ: 'ho_ten', 'so_thich_an_uong', 'vat_nuoi').
3. Trả về một chuỗi duy nhất theo định dạng: "FACT: fact_key = [Văn bản gốc của người dùng]"

VÍ DỤ:
- Input: "tôi tên là Nam" -> Output: "FACT: ho_ten = tôi tên là Nam"
- Input: "tôi thích ăn phở" -> Output: "FACT: so_thich_an_uong = tôi thích ăn phở"
- Input: "tôi thích nuôi chó" -> Output: "FACT: vat_nuoi = tôi thích nuôi chó"
- Input: "sđt của tôi là 0909" -> Output: "FACT: so_dien_thoai = sđt của tôi là 0909"
- Input: "hôm nay trời đẹp" -> Output: "KHONG_CO_FACT"
- Input: "chào bạn" -> Output: "KHONG_CO_FACT"

Bạn CHỈ được trả lời bằng chuỗi fact (ví dụ: "FACT: ho_ten = tôi tên là Nam") hoặc chuỗi "KHONG_CO_FACT".
KHÔNG được giải thích.
"""
    try:
        # Gọi LLM
        resp = await llm.ainvoke(prompt_template)
        result_str = resp.content.strip()
        
        # 4. Xử lý kết quả
        if result_str.startswith("FACT:") and "=" in result_str:
            print(f"[Debug LLM Fact] LLM đã trích xuất: {result_str}")
            return [result_str] # Trả về một danh sách (list) chứa 1 fact
        else:
            print(f"[Debug LLM Fact] LLM không tìm thấy fact (hoặc trả về: {result_str})")
            return [] # Trả về danh sách rỗng

    except Exception as e:
        print(f"❌ Lỗi khi gọi LLM trích xuất fact: {e}")
        return [] # Trả về danh sách rỗng nếu có lỗi

# =========================================================
# 🔔 Push API & Scheduler Helpers (GỘP TỪ CODE CŨ)
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 872)

async def ui_show_all_memory():
    """(MỚI) Hiển thị tất cả ghi chú (trừ file/image) với nút xóa."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
    
    # Phải chạy sync
    def _get_docs_sync():
        return vectorstore._collection.get(include=["documents"])
    
    raw_data = await asyncio.to_thread(_get_docs_sync)
    
    ids = raw_data.get("ids", [])
    docs = raw_data.get("documents", [])
    
    if not docs:
        await cl.Message(content="📭 Bộ nhớ đang trống. Chưa lưu gì cả.").send()
        return

    notes_found = 0
    await cl.Message(content="📝 **Các ghi chú đã lưu (Văn bản):**").send()
    
    for doc_id, content in zip(ids, docs):
        if not content: continue
        
        # --- BỘ LỌC ĐẦY ĐỦ ---
        if content.startswith("[FILE]") or \
           content.startswith("[IMAGE]") or \
           content.startswith("[REMINDER_") or \
           content.startswith("[ERROR_PROCESSING_FILE]") or \
           content.startswith("[FILE_UNSUPPORTED]") or \
           content.startswith("Trích từ tài liệu:") or \
           content.startswith("FACT:"):
            continue
        
        notes_found += 1
        
        # --- SỬA LỖI UI (DÙNG POPUP) ---
        
        # 1. Tạo tin nhắn (chưa gửi)
        msg = cl.Message(content="") 
        
        # 2. Nút Xóa (Luôn có)
        actions = [
            cl.Action(
                name="delete_note", 
                payload={"doc_id": doc_id, "message_id": msg.id},
                label="🗑️ Xóa"
            )
        ]
        
        # 3. Logic hiển thị (Ngắn / Dài)
        # (Đặt 150 ký tự, hoặc nếu có xuống dòng)
        if len(content) > 150 or "\n" in content:
            # GHI CHÚ DÀI: Hiển thị tóm tắt và thêm nút "Xem chi tiết"
            summary = "• " + (content.split('\n', 1)[0] or content).strip()[:150] + "..."
            msg.content = summary
            
            # Thêm nút MỚI để mở Popup
            actions.append(
                cl.Action(
                    name="show_note_detail", # Gọi callback mới
                    payload={"doc_id": doc_id},    # Chỉ cần doc_id
                    label="📄 Xem chi tiết"
                )
            )
        else:
            # GHI CHÚ NGẮN: Hiển thị đầy đủ
            msg.content = f"• {content}"

        # 4. Gán action và gửi
        msg.actions = actionsds
        await msg.send()
        # --- KẾT THÚC SỬA LỖI UI ---

    if notes_found == 0:
         await cl.Message(content="📭 Không tìm thấy ghi chú văn bản nào (chỉ có file/lịch nhắc).").send()
         
         
# --- Helper: Retry cho Push API ---
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    from importlib import import_module
    Retry = import_module("requests.packages.urllib3.util.retry").Retry

def make_retry():
    try:
        return Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["POST"]),
        )
    except TypeError:
        return Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            method_whitelist=frozenset(["POST"]),
        )

PUSH_SESSION = requests.Session()
_retry = make_retry()
PUSH_SESSION.mount("http://",  HTTPAdapter(max_retries=_retry))
PUSH_SESSION.mount("https://", HTTPAdapter(max_retries=_retry))

def _call_push_api_frappe(payload: dict) -> tuple[bool, int, str]:
    """Gọi Frappe createpushnoti. Trả về (ok, status_code, text)."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {PUSH_API_TOKEN}",
    }
    try:
        resp = PUSH_SESSION.post(
            PUSH_API_URL,
            json=payload,
            headers=headers,
            timeout=(3.05, PUSH_TIMEOUT),
            verify=PUSH_VERIFY_TLS,
        )
        return (200 <= resp.status_code < 300), resp.status_code, (resp.text or "")
    except Exception as e:
        return False, -1, f"exception: {e}"

# (THÊM HÀM MỚI NÀY - khoảng dòng 920)

def _call_change_password_api(emailid: str, newpass: str) -> tuple[bool, int, str]:
    """(MỚI) Gọi API bên ngoài để đồng bộ đổi mật khẩu."""
    
    # Kiểm tra xem URL đã được cấu hình chưa
    if not CHANGEPASS_API_URL:
        print("⚠️ [ChangePass] Bỏ qua: Biến CHANGEPASS_API_URL chưa được cài đặt trong .env.")
        return False, 0, "url_not_configured"
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {PUSH_API_TOKEN}", # Dùng chung token của Push
    }
    
    # Payload theo yêu cầu của bạn (emailid, newpass)
    payload = {
        "emailid": emailid,
        "newpass": newpass
    }
    
    print(f"📞 [ChangePass] Đang gọi API đồng bộ pass cho: {emailid}...")
    
    try:
        resp = PUSH_SESSION.post( # Dùng chung PUSH_SESSION (đã có retry)
            CHANGEPASS_API_URL,
            json=payload, # Gửi dạng JSON
            headers=headers,
            timeout=(3.05, PUSH_TIMEOUT),
            verify=PUSH_VERIFY_TLS,
        )
        return (200 <= resp.status_code < 300), resp.status_code, (resp.text or "")
    except Exception as e:
        return False, -1, f"exception: {e}"
    
    
# --- Helper: Quản lý Scheduler ---
def ensure_scheduler():
    """Khởi động scheduler (1 lần) VỚI LƯU TRỮ BỀN BỈ."""
    global SCHEDULER
    if SCHEDULER is None:
        try:
            SCHEDULER = AsyncIOScheduler(
                jobstores=jobstores,
                timezone=str(VN_TZ),
                job_defaults={"max_instances": 3, "coalesce": False}
            )
            SCHEDULER.start()
            print(f"[Scheduler] Đã khởi động với JobStore tại: {JOBSTORE_DB_FILE}")
            # Lên lịch đồng bộ User
            SCHEDULER.add_job(
                _sync_users_from_api_sync, # Hàm worker (sync)
                trigger='interval',        # Kiểu lặp
                minutes=1,                 # Thời gian lặp
                id='sync_users_job',       # Tên job (để không bị trùng)
                replace_existing=True,
                next_run_time=datetime.now(VN_TZ) + timedelta(seconds=5) # Chạy lần đầu sau 5s
            )
            print("✅ [Scheduler] Đã lên lịch đồng bộ User (mỗi 3 phút).")
        except Exception as e:
            print(f"[Scheduler] LỖI NGHIÊM TRỌNG KHI KHỞI ĐỘNG: {e}")
            print("[Scheduler] LỖI: Có thể bạn cần xóa file 'memory_db/jobs.sqlite' nếu cấu trúc DB thay đổi.")
            SCHEDULER = None
            
def _fmt_dt(dt):
    try:
        return dt.astimezone(VN_TZ).strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return str(dt)

def _job_kind(job_id: str, trigger) -> str:
    if job_id.startswith("reminder-cron-"):
        return "cron (tuần/tháng/ngày)"
    if job_id.startswith("first-"):
        return "một lần (leo thang)"
    if job_id.startswith("repeat-"):
        return "lặp (leo thang 5s)"
    if job_id.startswith("reminder-"):
        t = trigger.__class__.__name__.lower()
        if "interval" in t: return "lặp theo khoảng"
        if "date" in t:     return "một lần"
    return trigger.__class__.__name__

def list_active_reminders() -> list[dict]:
    out = []
    try:
        if not SCHEDULER:
            ensure_scheduler()
            if not SCHEDULER:
                 return []
        jobs = SCHEDULER.get_jobs()
    except Exception as e:
        print(f"[REM] get_jobs error: {e}")
        jobs = []
    for job in jobs:
        jid = job.id or ""
        trig = job.trigger
        kind = _job_kind(jid, trig)
        sess = None; text = ""
        try:
            args = job.args or []
            if len(args) >= 2:
                sess = args[0]
                text = args[1]
        except Exception:
            pass

        esc_active = False
        if sess and sess in ACTIVE_ESCALATIONS:
            esc_active = not ACTIVE_ESCALATIONS[sess].get("acked", False)

        out.append({
            "id": jid,
            "kind": kind,
            "next_run": _fmt_dt(job.next_run_time) if job.next_run_time else None,
            "text": text,
            "session_id": sess,
            "escalation_active": esc_active,
        })
    return sorted(out, key=lambda x: (x["text"], x["kind"], x["next_run"] or ""))

def remove_reminder(job_id: str, session_id: Union[str, None] = None) -> Tuple[bool, str]:
    """Hủy 1 job theo id. Nếu có session_id: tắt luôn leo thang."""
    try:
        if SCHEDULER:
            SCHEDULER.remove_job(job_id)
        msg = f"🗑️ Đã xóa lịch: {job_id}"
        if session_id:
            try:
                _cancel_escalation(session_id)
                msg += " • (đã tắt leo thang nếu đang bật)"
            except Exception as e:
                msg += f" • (tắt leo thang lỗi: {e})"
        return True, msg
    except Exception as e:
        return False, f"❌ Không xóa được {job_id}: {e}"

def _sanitize_filename(text: str) -> str:
    """Biến một chuỗi bất kỳ thành tên file an toàn."""
    if not text:
        return "empty"
    text = text[:60]
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"[\s\n\t]+", "_", text).strip('_')
    try:
        import unidecode
        text = unidecode.unidecode(text)
    except ImportError:
        pass
    return text or "sanitized"

# --- Helper: Parse thời gian ---
VN_DOW = {
    "thứ 2": "mon", "thu 2": "mon", "thứ hai": "mon", "thu hai": "mon", "t2": "mon",
    "thứ 3": "tue", "thu 3": "tue", "thứ ba": "tue",  "thu ba": "tue",  "t3": "tue",
    "thứ 4": "wed", "thu 4": "wed", "thứ tư": "wed",  "thu tu": "wed",  "t4": "wed",
    "thứ 5": "thu", "thu 5": "thu", "thứ năm": "thu", "thu nam": "thu", "t5": "thu",
    "thứ 6": "fri", "thu 6": "fri", "thứ sáu": "fri", "thu sau": "fri", "t6": "fri",
    "thứ 7": "sat", "thu 7": "sat", "thứ bảy": "sat", "thu bay": "sat", "t7": "sat",
    "chủ nhật": "sun", "chu nhat": "sun", "cn": "sun",
}

def _parse_hm(txt: str) -> tuple[int, int]:
    """Rút hour:minute từ chuỗi (8h, 08:30, 8h30, 20h05...). Mặc định 08:00."""
    txt = txt.strip()
    m = re.search(r"(\d{1,2})[:hH](\d{2})", txt)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        return max(0, min(23, hh)), max(0, min(59, mm))
    m = re.search(r"\b(\d{1,2})h\b", txt)
    if m:
        hh = int(m.group(1)); return max(0, min(23, hh)), 0
    m = re.search(r"\b(\d{1,2})\b", txt)  # chỉ giờ
    if m:
        hh = int(m.group(1)); return max(0, min(23, hh)), 0
    return 8, 0  # default 08:00

def detect_cron_schedule(thoi_gian: str):
    """
    Trả về dict {'type': 'weekly'/'monthly'/'daily', 'trigger': CronTrigger(...)}
    nếu phát hiện câu dạng: 'thứ 4 hàng tuần 8:30', 'ngày 1 hàng tháng 09:00', 'mỗi ngày 7h'.
    """
    low = (thoi_gian or "").lower().strip()

    if ("hàng tuần" in low) or ("hang tuan" in low):
        dow = None
        for k, v in VN_DOW.items():
            if k in low:
                dow = v; break
        if dow:
            hh, mm = _parse_hm(low)
            trig = CronTrigger(day_of_week=dow, hour=hh, minute=mm, timezone=VN_TZ)
            return {"type": "weekly", "trigger": trig}

    if ("hàng tháng" in low) or ("hang thang" in low):
        m = re.search(r"ngày\s*(\d{1,2})|ngay\s*(\d{1,2})", low)
        if m:
            day = int(m.group(1) or m.group(2))
            day = max(1, min(31, day))
            hh, mm = _parse_hm(low)
            trig = CronTrigger(day=day, hour=hh, minute=mm, timezone=VN_TZ)
            return {"type": "monthly", "trigger": trig}

    if ("mỗi ngày" in low) or ("moi ngay" in low) or ("hàng ngày" in low) or ("hang ngay" in low):
        hh, mm = _parse_hm(low)
        trig = CronTrigger(hour=hh, minute=mm, timezone=VN_TZ)
        return {"type": "daily", "trigger": trig}

    return None

def parse_repeat_to_seconds(text: str) -> int:
    if not text:
        return 0
    t = (text or "").lower().strip()
    m = re.search(r"(mỗi|moi|lặp lại|lap lai)\s+(\d+)\s*(giây|giay|phút|phut|giờ|gio|s|m|h)\b", t)
    m2 = re.search(r"(every)\s+(\d+)\s*(s|m|h)\b", t)
    unit = None; val = None
    if m:
        val = int(m.group(2)); unit = m.group(3)
    elif m2:
        val = int(m2.group(2)); unit = m2.group(3)
    else:
        return 0

    if unit in ("giây","giay","s"):
        return val
    if unit in ("phút","phut","m"):
        return val * 60
    if unit in ("giờ","gio","h"):
        return val * 3600
    return 0
# (Thêm hàm mới này vào khoảng dòng 1150)
# (Thêm hàm mới này vào khoảng dòng 1150)

async def _llm_parse_dt(llm: ChatOpenAI, when_str: str) -> datetime:
    """
    (MỚI) Dùng LLM (GPT) để phân tích thời gian tự nhiên của người dùng.
    """
    now_vn = datetime.now(VN_TZ)
    prompt = f"""
    Bây giờ là: {now_vn.isoformat()} ( múi giờ Asia/Ho_Chi_Minh)
    
    Nhiệm vụ của bạn là phân tích chuỗi thời gian tự nhiên của người dùng và chuyển nó thành một chuỗi ISO 8601 ĐẦY ĐỦ.
    Chỉ trả về chuỗi ISO (ví dụ: '2025-11-07T10:00:00+07:00') và KHÔNG CÓ BẤT KỲ GIẢI THÍCH NÀO.
    
    Input: "{when_str}"
    Output:
    """
    try:
        resp = await llm.ainvoke(prompt)
        iso_str = resp.content.strip().strip("`'\"")
        
        # Dùng dtparser để parse chuỗi ISO 8601 mà LLM trả về
        dt = dtparser.isoparse(iso_str)
        print(f"[LLM Parse] GPT đã phân tích '{when_str}' -> '{iso_str}'")
        return dt.astimezone(VN_TZ) # Đảm bảo đúng timezone
        
    except Exception as e:
        print(f"❌ Lỗi _llm_parse_dt: {e}. Trả về 'now + 1 min'")
        return now_vn + timedelta(minutes=1)
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 1163)
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 1163)

async def parse_when_to_dt(when_str: str) -> datetime: # <-- THÊM ASYNC
    """
    (ĐÃ SỬA LỖI)
    Chuyển tiếng Việt tự nhiên -> datetime (Asia/Ho_Chi_Minh).
    Ưu tiên các logic đơn giản (trong 1 phút, 1 giờ),
    nếu thất bại, dùng LLM để phân tích thời gian phức tạp.
    """
    text_raw = (when_str or "").strip().lower()
    if not text_raw:
        raise ValueError("Thiếu thời gian nhắc")
    now = datetime.now(VN_TZ)
    text_raw = re.sub(r"\s+", " ", text_raw).strip()

    # 1. Logic đơn giản (giữ nguyên)
    m = re.search(r"(trong\s+)?(\d+)\s*(phút|min|phut)\s*(nữa|nua)?", text_raw)
    if m:
        plus_min = int(m.group(2))
        return now + timedelta(minutes=plus_min)

    # (SỬA LỖI) Chỉ khớp 'giờ' nếu KHÔNG đi kèm 'sáng/chiều/tối/mai'
    if "sáng" not in text_raw and "chieu" not in text_raw and "tối" not in text_raw and "mai" not in text_raw and "nay" not in text_raw:
        m = re.search(r"(trong\s+)?(\d+)\s*(giờ|gio|g|tiếng|tieng|h)\s*(nữa|nua)?", text_raw)
        if m:
            plus_hour = int(m.group(2))
            return now + timedelta(hours=plus_hour)

    # 2. Logic phức tạp -> Dùng LLM (GPT)
    llm = cl.user_session.get("llm_logic")
    if not llm:
        print("⚠️ Lỗi parse_when_to_dt: Không tìm thấy llm_logic. Dùng fallback.")
        return now + timedelta(minutes=1)
    
    # Gọi helper LLM mới (phải await)
    dt_guess = await _llm_parse_dt(llm, text_raw)
    return dt_guess

# --- Helper: Logic lõi của Scheduler (Sync) ---

def _cancel_escalation(internal_session_id: str):
    """
    (SỬA LẠI) Chỉ dọn dẹp bộ nhớ. 
    Lệnh 'remove_job' sẽ được _tick_job_sync xử lý.
    """
    st = ACTIVE_ESCALATIONS.pop(internal_session_id, None)
    if st:
        print(f"[Escalation] Đã dọn dẹp in-memory cho {internal_session_id}")

def _tick_job_sync(sid, text, repeat_job_id):
    """
    (SỬA LẠI) Hàm sync để APScheduler gọi (cho escalation).
    Đây là nơi duy nhất được phép 'remove_job'.
    """
    try:
        st = ACTIVE_ESCALATIONS.get(sid)
        if not st or st.get("acked"):
            try:
                if SCHEDULER:
                    SCHEDULER.remove_job(repeat_job_id)
                print(f"[Escalation] Tick: Job {repeat_job_id} đã ack/mồ côi. ĐANG XÓA.")
            except Exception as e:
                print(f"[Escalation] Info: Job {repeat_job_id} đã bị xóa (lỗi: {e}).")
            ACTIVE_ESCALATIONS.pop(sid, None)
            return
            
        print(f"[Escalation] Tick: Gửi nhắc (sync) cho {sid}")
        _do_push(sid, text)
        
    except Exception as e:
        print(f"[ERROR] _tick_job_sync crashed: {e}")

def _first_fire_escalation_job(sid, text, every_sec):
    """
    Hàm (sync) được gọi cho LẦN ĐẦU TIÊN của 1 lịch leo thang.
    Nó sẽ tự lên lịch lặp lại (escalation) sau khi chạy.
    """
    try:
        print(f"[Escalation] First fire (sync) for {sid} at {datetime.now(VN_TZ)}")
        _do_push(sid, text) 
        _schedule_escalation_after_first_fire(sid, text, every_sec)
    except Exception as e:
        print(f"[ERROR] _first_fire_escalation_job crashed: {e}")

def _schedule_escalation_after_first_fire(internal_session_id: str, noti_text: str, every_sec: int):
    """(SỬA LỖI) Lên lịch lặp lại (escalation) bằng hàm sync-safe."""
    repeat_job_id = f"repeat-{internal_session_id}-{uuid.uuid4().hex[:6]}"
    ACTIVE_ESCALATIONS[internal_session_id] = {"repeat_job_id": repeat_job_id, "acked": False}
    trigger = IntervalTrigger(seconds=every_sec, timezone=VN_TZ)
    if SCHEDULER:
        SCHEDULER.add_job(
           _tick_job_sync,
            trigger=trigger,
            id=repeat_job_id,
            args=[internal_session_id, noti_text, repeat_job_id], # <--- SỬA: Thêm repeat_job_id
            replace_existing=False,
            misfire_grace_time=10,
        )
        print(f"[Escalation] Đã bật lặp mỗi {every_sec}s với job_id={repeat_job_id}")

def _do_push(internal_session_id: str, noti_text: str):
    """
    (SỬA LẠI) Hàm (sync) thực thi push (Kiến trúc Tổng đài).
    1. Gửi tin nhắn vào HÀNG ĐỢI TỔNG (GLOBAL_MESSAGE_QUEUE).
    2. Gọi API Frappe.
    """
    ts = datetime.now(VN_TZ).isoformat()
    
    # 1. Gửi tin nhắn vào Hàng đợi Tổng
    try:
        if GLOBAL_MESSAGE_QUEUE:
            GLOBAL_MESSAGE_QUEUE.put_nowait({
                "author": "Trợ lý ⏰",
                "content": f"⏰ Nhắc: {noti_text}\n🕒 {ts}"
            })
            print(f"[Push/Queue] Đã gửi tin nhắn vào TỔNG ĐÀI.")
        else:
            print("[Push/Queue] LỖI: GLOBAL_MESSAGE_QUEUE is None.")
            
    except Exception as e:
        print(f"[Push/Queue] Lỗi put_nowait (Tổng đài): {e}")

    # 2. Gọi API Frappe
    escalate_active = bool(ACTIVE_ESCALATIONS.get(internal_session_id) and
                           not ACTIVE_ESCALATIONS[internal_session_id].get("acked"))
    big_md = "# ⏰ **NHẮC VIỆC**\n\n## " + noti_text + "\n\n**🕒 " + ts + "**"
    payload = { "subject": "🔔 Nhắc việc", "notiname": big_md, "url": PUSH_DEFAULT_URL, }
    ok, status, text = _call_push_api_frappe(payload)
    if ok:
        print(f"[Push/API] OK status={status}")
    else:
        print(f"[Push/API] FAIL status={status} body={text[:300]}")

@cl.action_callback("delete_note")
async def _on_delete_note(action: cl.Action):
    """(MỚI) Xử lý xóa một ghi chú văn bản từ ChromaDB."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return

    doc_id = action.payload.get("doc_id")
    message_id = action.payload.get("message_id") # <-- LẤY ID TIN NHẮN
    
    if not doc_id:
        await cl.Message(content="❌ Lỗi: Không nhận được doc_id.").send()
        return

    try:
        # Dùng to_thread để xóa (I/O)
        await asyncio.to_thread(vectorstore._collection.delete, ids=[doc_id])
        await cl.Message(content=f"✅ Đã xóa ghi chú: {doc_id}").send()
        
        # --- SỬA LỖI UI ---
        # Xóa tin nhắn gốc khỏi UI bằng ID
        if message_id:
            try:
                msg_to_remove = cl.Message.get(message_id)
                if msg_to_remove:
                    await msg_to_remove.remove()
            except Exception as e_remove:
                print(f"Lỗi khi xóa message {message_id}: {e_remove}")
        # --- KẾT THÚC SỬA LỖI ---

    except Exception as e:
        await cl.Message(content=f"❌ Lỗi khi xóa ghi chú: {e}").send()
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 985)

@cl.action_callback("show_note_detail")
async def _on_show_note_detail(action: cl.Action):
    """(MỚI) Xử lý bấm nút 'Xem chi tiết', GỬI TIN NHẮN MỚI."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return

    doc_id = action.payload.get("doc_id")
    if not doc_id:
        await cl.Message(content="❌ Lỗi: Không nhận được doc_id.").send()
        return

    try:
        # Lấy nội dung đầy đủ (dùng thread)
        content = await asyncio.to_thread(_get_note_by_id_db, vectorstore, doc_id)
        
        if content:
            # --- SỬA LỖI: Không dùng Modal, Gửi tin nhắn mới ---
            await cl.Message(
                content=f"**Chi tiết Ghi chú (ID: {doc_id}):**\n```\n{content}\n```"
            ).send()
            # --- KẾT THÚC SỬA LỖI ---
        else:
            await cl.Message(content=f"❌ Lỗi: Không tìm thấy nội dung cho ID: {doc_id}").send()
            
    except Exception as e:
        # (Giữ lại traceback để debug nếu có lỗi khác)
        print(f"❌ Lỗi nghiêm trọng trong _on_show_note_detail (ID: {doc_id}):")
        traceback.print_exc() 
        await cl.Message(content=f"❌ Lỗi khi mở dschi tiết (Debug): {str(e)}").send()
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 872)

async def ui_show_all_memory():
    """(MỚI) Hiển thị tất cả ghi chú (trừ file/image) với nút xóa."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
    
    # Phải chạy sync
    def _get_docs_sync():
        return vectorstore._collection.get(include=["documents"])
    
    raw_data = await asyncio.to_thread(_get_docs_sync)
    
    ids = raw_data.get("ids", [])
    docs = raw_data.get("documents", [])
    
    if not docs:
        await cl.Message(content="📭 Bộ nhớ đang trống. Chưa lưu gì cả.").send()
        return

    notes_found = 0
    await cl.Message(content="📝 **Các ghi chú đã lưu (Văn bản):**").send()
    
    for doc_id, content in zip(ids, docs):
        if not content: continue
        
        # --- BỘ LỌC ĐẦY ĐỦ ---
        if content.startswith("[FILE]") or \
           content.startswith("[IMAGE]") or \
           content.startswith("[REMINDER_") or \
           content.startswith("[ERROR_PROCESSING_FILE]") or \
           content.startswith("[FILE_UNSUPPORTED]") or \
           content.startswith("Trích từ tài liệu:") or \
           content.startswith("FACT:"):
            continue
        
        notes_found += 1
        
        # --- SỬA LỖI UI (DÙNG POPUP) ---
        
        # 1. Tạo tin nhắn (chưa gửi)
        msg = cl.Message(content="") 
        
        # 2. Nút Xóa (Luôn có)
        actions = [
            cl.Action(
                name="delete_note", 
                payload={"doc_id": doc_id, "message_id": msg.id},
                label="🗑️ Xóa"
            )
        ]
        
        # 3. Logic hiển thị (Ngắn / Dài)
        # (Đặt 150 ký tự, hoặc nếu có xuống dòng)
        if len(content) > 150 or "\n" in content:
            # GHI CHÚ DÀI: Hiển thị tóm tắt và thêm nút "Xem chi tiết"
            summary = "• " + (content.split('\n', 1)[0] or content).strip()[:150] + "..."
            msg.content = summary
            
            # Thêm nút MỚI để mở Popup
            actions.append(
                cl.Action(
                    name="show_note_detail", # Gọi callback mới
                    payload={"doc_id": doc_id},    # Chỉ cần doc_id
                    label="📄 Xem chi tiết"
                )
            )
        else:
            # GHI CHÚ NGẮN: Hiển thị đầy đủ
            msg.content = f"• {content}"

        # 4. Gán action và gửi
        msg.actions = actions # <-- Đảm bảo đây là 'actions' (không phải 'actionsds')
        await msg.send()
        # --- KẾT THÚC SỬA LỖI UI ---

    if notes_found == 0:
         await cl.Message(content="📭 Không tìm thấy ghi chú văn bản nào (chỉ có file/lịch nhắc).").send()
# --- Helper: Broadcaster/Poller (Tổng đài/Thuê bao) ---
async def global_broadcaster_poller():
    """(MỚI) HÀM TỔNG ĐÀI - Chạy 1 lần duy nhất."""
    print("✅ [Tổng đài] Global Broadcaster đã khởi động.")
    while True:
        try:
            if GLOBAL_MESSAGE_QUEUE is None:
                await asyncio.sleep(2)
                continue

            msg_data = await GLOBAL_MESSAGE_QUEUE.get()
            print(f"[Tổng đài] Nhận được tin nhắn. Đang phát cho {len(ACTIVE_SESSION_QUEUES)} thuê bao...")

            if ACTIVE_SESSION_QUEUES:
                active_ids = list(ACTIVE_SESSION_QUEUES.keys()) 
                for session_id in active_ids:
                    target_queue = ACTIVE_SESSION_QUEUES.get(session_id)
                    if target_queue:
                        await target_queue.put(msg_data)
            
            GLOBAL_MESSAGE_QUEUE.task_done()
            
        except asyncio.CancelledError:
            print("[Tổng đài] Đã dừng.")
            break
        except Exception as e:
            print(f"[Tổng đài/ERROR] Bị lỗi: {e}")
            await asyncio.sleep(2)

async def session_receiver_poller():
    """(MỚI) HÀM THUÊ BAO - Chạy 1 lần cho MỖI TAB."""
    current_internal_id = cl.user_session.get("chainlit_internal_id", "unknown")
    my_queue = asyncio.Queue()
    
    try:
        ACTIVE_SESSION_QUEUES[current_internal_id] = my_queue
        print(f"✅ [Thuê bao] Đã ĐĂNG KÝ cho session {current_internal_id}")
        
        while True:
            msg_data = await my_queue.get()
            print(f"[Thuê bao] {current_internal_id} đã nhận được tin nhắn.")
            content = msg_data.get("content", "")
            
            await cl.Message(
                author=msg_data.get("author", "Bot"),
                content=content
            ).send()
            
            my_queue.task_done()
            
    except asyncio.CancelledError:
        print(f"[Thuê bao] {current_internal_id} đã dừng.")
    except Exception as e:
        print(f"[Thuê bao/ERROR] {current_internal_id} bị lỗi: {e}")
    finally:
        ACTIVE_SESSION_QUEUES.pop(current_internal_id, None)
        print(f"[Thuê bao] Đã HỦY ĐĂNG KÝ cho session {current_internal_id}")

# --- Helper: Quyền thông báo (Browser) ---
async def ensure_notification_permission():
    js = r"""
(async () => {
  try {
    if (!('Notification' in window)) return 'no-support';
    if (Notification.permission === 'granted') return 'granted';
    const r = await Notification.requestPermission();
    return r;
  } catch (e) { return 'error:' + String(e); }
})();
"""
    try:
        res = await cl.run_js(js)
        print("[Notify] permission =", res)
    except Exception as e:
        print("[Notify] request permission error:", e)

# =========================================================
# 🚀 ĐỊNH NGHĨA CLASS AGENT TÙY CHỈNH
# =========================================================
# (HÀM ĐÃ SỬA - khoảng dòng 1445)

class CleanAgentExecutor(AgentExecutor):
    """
    (SỬA LẠI) AgentExecutor tùy chỉnh: chỉ chạy 1 vòng và trả về
    kết quả thô (Observation) từ tool, không cho LLM nói thêm.
    """
    async def ainvoke(self, input_data: dict, **kwargs):
        # (SỬA LỖI: Thêm lại max_iterations để DỪNG VÒNG LẶP VÔ HẠN)
        # Gộp kwargs để đảm bảo max_iterations được set
        merged_kwargs = {"max_iterations": 2, **kwargs}
        
        result = await super().ainvoke(input_data, **merged_kwargs) # <-- SỬA DÒNG NÀY
        steps = result.get("intermediate_steps") or []
        
        # Sửa lỗi logic: Luôn ưu tiên kết quả tool (obs) nếu có
        if steps and isinstance(steps[-1], tuple) and len(steps[-1]) > 1:
            obs = steps[-1][1] 
            if isinstance(obs, str) and obs.strip():
                return {"output": obs.strip()} 
        return {"output": result.get("output", "⚠️ Không có phản hồi.")}

# =========================================================
# (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 1630)

def _sync_users_from_api_sync():
    """
    (SYNC) Worker (ĐÃ CẬP NHẬT)
    (SỬA LỖI: Thêm logic đồng bộ cột 'name'.)
    """
    print("🔄 [Sync] Bắt đầu phiên đồng bộ user (có check admin, active, name)...")
    
    # 1. Gọi API (blocking)
    try:
        api_users_list = _call_get_users_api()
        if not api_users_list or not isinstance(api_users_list, list):
            print("⚠️ [Sync] API không trả về danh sách user hợp lệ. Bỏ qua.")
            return
        print(f"✅ [Sync] API trả về {len(api_users_list)} users.")
    except Exception as e:
        print(f"❌ [Sync] Không thể lấy user từ API: {e}. Dừng đồng bộ.")
        return

    created = 0
    updated = 0
    skipped = 0
    invalid = 0 
    conn = None
    
    try:
        # 2. Mở kết nối CSDL
        conn = _get_user_db_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 3. Lấy TẤT CẢ user local vào bộ nhớ
        # (SỬA) Thêm 'name' vào select
        cursor.execute("SELECT email, password_hash, is_admin, is_active, name FROM users")
        local_users = {
            row['email'].lower(): {
                "hash": row['password_hash'], 
                "is_admin": row['is_admin'],
                "is_active": row['is_active'],
                "name": row['name'] # <-- THÊM VÀO
            } for row in cursor.fetchall()
        }

        # 4. Duyệt qua danh sách API
        for api_user in api_users_list:
            
            # 4.1. Đọc đúng key từ API
            email = api_user.get('email')
            api_plain_password = api_user.get('password_hash') 
            api_admin_val = str(api_user.get('is_admin')).lower() 
            api_active_val = str(api_user.get('is_active')).lower()
            
            # --- 🚀 BẮT ĐẦU THÊM LOGIC NAME 🚀 ---
            # Thử lấy 'full_name' trước, nếu không có thì thử 'name'
            api_name = api_user.get('full_name') or api_user.get('name') or ""
            # --- 🚀 KẾT THÚC LOGIC NAME 🚀 ---
            
            is_admin_flag = 1 if api_admin_val in ("1", "true") else 0
            is_active_flag = 1 if api_active_val in ("1", "true") else 0

            # 4.2. Kiểm tra
            if not email or not api_plain_password:
                invalid += 1
                continue
            
            email_low = email.lower()
            
            if email_low not in local_users:
                # 4.3. TẠO MỚI (SỬA: Thêm 'name')
                new_hashed_pw = generate_password_hash(api_plain_password)
                
                cursor.execute(
                    "INSERT INTO users (email, password_hash, is_admin, is_active, name) VALUES (?, ?, ?, ?, ?)", 
                    (email_low, new_hashed_pw, is_admin_flag, is_active_flag, api_name) # <-- THÊM 'api_name'
                )
                created += 1
                
                local_users[email_low] = {
                    "hash": new_hashed_pw, 
                    "is_admin": is_admin_flag, 
                    "is_active": is_active_flag,
                    "name": api_name # <-- THÊM VÀO
                }
                
            else:
                # 4.4. KIỂM TRA UPDATE (SỬA: Thêm 'name_changed')
                local_data = local_users[email_low]
                local_hash = local_data["hash"]
                local_is_admin = local_data["is_admin"]
                local_is_active = local_data["is_active"]
                local_name = local_data["name"] # <-- THÊM VÀO
                
                password_changed = not check_password_hash(local_hash, api_plain_password) 
                admin_changed = (local_is_admin != is_admin_flag)
                active_changed = (local_is_active != is_active_flag)
                name_changed = (local_name != api_name) # <-- THÊM VÀO

                if password_changed or admin_changed or active_changed or name_changed: # <-- SỬA
                    
                    new_hashed_pw = generate_password_hash(api_plain_password) if password_changed else local_hash
                    
                    cursor.execute(
                        "UPDATE users SET password_hash = ?, is_admin = ?, is_active = ?, name = ? WHERE email = ?", # <-- SỬA
                        (new_hashed_pw, is_admin_flag, is_active_flag, api_name, email_low) # <-- SỬA
                    )
                    updated += 1
                else:
                    skipped += 1

        # 5. Commit
        conn.commit()
        print(f"✅ [Sync] Đồng bộ hoàn tất: {created} tạo mới, {updated} cập nhật (pass/admin/active/name), {skipped} bỏ qua, {invalid} API không hợp lệ.")

    except Exception as e:
        print(f"❌ [Sync] Lỗi CSDL khi đang đồng bộ: {e}")
        import traceback
        traceback.print_exc() 
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
init_user_db()
# =========================================================
async def ui_show_active_reminders():
    items = list_active_reminders()
    if not items:
        await cl.Message(content="📭 Hiện không có lịch nhắc nào đang hoạt động.").send()
        return
    await cl.Message(content="📅 **Các lịch nhắc đang hoạt động:**").send()
    for it in items:
        esc = " • 🔁 *đang leo thang*" if it["escalation_active"] else ""
        nr = it["next_run"] or "—"
        body = (
            f"**{it['text']}**\n"
            f"• loại: *{it['kind']}*{esc}\n"
            f"• chạy tiếp: `{nr}`\n"
            f"• job_id: `{it['id']}`"
        )
        actions = [
                cl.Action(
                    name="delete_reminder",
                    payload={"job_id": it["id"], "session_id": it["session_id"]},
                    label="🗑️ Hủy lịch này"
                )
            ]
        await cl.Message(content=body, actions=actions).send()

# (Tìm hàm ui_show_active_files và THAY THẾ bằng hàm này)
async def ui_show_active_files():
    """
    SỬA LỖI TREO (8): Dùng cl.run_sync cho list_active_files
    """
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
        
    # --- SỬA LỖI TREO (8) ---
    items = await asyncio.to_thread(list_active_files, vectorstore)
    
    if not items:
        await cl.Message(content="📭 Bộ nhớ file của bạn đang trống.").send()
        return

    await cl.Message(content=f"🗂️ **Danh sách {len(items)} file đã lưu:**").send()
    for it in items:
        safe_href = f"/public/files/{it['saved_name']}"
        safe_name = html.escape(it['original_name'])
        
        if it['type'] == '[IMAGE]':
            link_html = f"![{safe_name}]({safe_href})"
        else:
            link_html = f"**[{safe_name}]({safe_href})**"

        body = (
            f"{link_html} {it['type']}\n"
            f"• Ghi chú: *{it['note']}*\n"
            f"• ID: `{it['doc_id']}`"
        )
        actions = [
                cl.Action(
                    name="delete_file",
                    payload={"doc_id": it["doc_id"], "file_path": it["file_path"]}, 
                    label="🗑️ Xóa file này"
                )
            ]
        await cl.Message(content=body, actions=actions).send()
        
@cl.action_callback("delete_reminder")
async def _on_delete_reminder(action: cl.Action):
    data = action.payload
    if not data:
        await cl.Message(content="❌ Lỗi: Không nhận được payload khi hủy lịch.").send()
        return
    job_id = data.get("job_id")
    sess   = data.get("session_id")
    ok, msg = remove_reminder(job_id, sess)
    await cl.Message(content=msg).send()

# (Tìm hàm _on_delete_file và THAY THẾ bằng hàm này)
@cl.action_callback("delete_file")
async def _on_delete_file(action: cl.Action):
    """
    SỬA LỖI TREO (9) & (10): Dùng cl.run_sync cho I/O (Chroma và os.remove)
    """
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return

    data = action.payload
    if not data:
        await cl.Message(content="❌ Lỗi: Không nhận được payload khi hủy file.").send()
        return

    doc_id = data.get("doc_id")
    file_path = data.get("file_path") # Đường dẫn trên disk
    msg = ""

    try:
        # --- SỬA LỖI TREO (9) ---
        await asyncio.to_thread(vectorstore._collection.delete, ids=[doc_id])
        msg += f"✅ Đã xóa metadata: {doc_id}\n"
    except Exception as e:
        msg += f"❌ Lỗi xóa metadata: {e}\n"
        
    try:
        if os.path.exists(file_path):
            # --- SỬA LỖI TREO (10) ---
            await asyncio.to_thread(os.remove, file_path)
            msg += f"✅ Đã xóa file: {file_path}"
        else:
            msg += f"⚠️ Không tìm thấy file trên đĩa: {file_path}"
    except Exception as e:
        msg += f"❌ Lỗi xóa file: {e}"

    await cl.Message(content=msg).send()


# =========================================================
# 🚀 HÀM MỚI: Tách riêng phần cài đặt chat
# (Hàm này sẽ được gọi SAU KHI đăng nhập thành công)
# =========================================================

# --- MỚI: Định nghĩa Schema cho Tool ở phạm vi toàn cục ---
class DatLichSchema(BaseModel):
    noi_dung_nhac: str = Field(..., description="Nội dung nhắc, ví dụ: 'Đi tắm'")
    thoi_gian: str = Field(..., description="Thời gian tự nhiên: '1 phút nữa', '20:15', 'mai 8h'")
    escalate: bool = Field(False, description="Nếu True: nhắc 1 lần đúng giờ, rồi lặp 5s nếu chưa phản hồi")

class LuuThongTinSchema(BaseModel):
    noi_dung: str = Field(..., description="Nội dung thông tin (văn bản) cần lưu trữ. KHÔNG dùng cho URL hoặc website.")
    
    
class DoiMatKhauSchema(BaseModel):
    email: str = Field(..., description="Email của user cần đổi mật khẩu")
    new_password: str = Field(..., description="Mật khẩu mới (dạng text thô) cho user đó")
class PushThuSchema(BaseModel):
    noidung: str = Field(description="Nội dung thông báo để push ngay")
class LayThongTinUserSchema(BaseModel):
    email: str = Field(..., description="Email của user cần tra cứu thông tin (ví dụ: 'user@example.com')")

class HienThiWebSchema(BaseModel):
    url: str = Field(..., description="URL đầy đủ (ví dụ: https://...) của trang web hoặc video cần nhúng.")
# -----------------------------------------------------------

async def setup_chat_session(user: cl.User):
    """
    (CẬP NHẬT) Sửa lời chào để hiển thị tên user
    """
    
    user_id_str = user.identifier
    cl.user_session.set("user_id_str", user_id_str)
    
    # --- 🚀 BẮT ĐẦU CẬP NHẬT LỜI CHÀO 🚀 ---
    # Lấy tên đã lưu từ on_start_after_login
    user_name = cl.user_session.get("user_name", "") 
    
    if user_name:
        # Nếu có tên, hiển thị: Anh Khoa (onsm@oshima.vn)
        display_name = f"**{user_name} ({user_id_str})**"
    else:
        # Nếu không có tên, hiển thị như cũ: onsm@oshima.vn
        display_name = f"**{user_id_str}**"
    # --- 🚀 KẾT THÚC CẬP NHẬT LỜI CHÀO 🚀 ---

    # --- 1. Khởi tạo Session ID và Lịch sử Chat ---
    session_id = f"session_{_timestamp()}"
    session_id = f"session_{_timestamp()}" # Tạo ID session mới
    chat_history = []                     # Bắt đầu lịch sử mới
    
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_history", chat_history)
    
    print(f"✅ [Session] Đã tạo session_id mới: {session_id}")
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---

    # --- 4. Hiển thị danh sách hội thoại CỦA USER ---
    sessions = await asyncio.to_thread(list_sessions, user_id_str)
    
    # --- 4. Hiển thị danh sách hội thoại CỦA USER ---
    sessions = await asyncio.to_thread(list_sessions, user_id_str)
    actions = [
        cl.Action(name="new_chat", label="✨ Cuộc trò chuyện mới", payload={"session_id": "new"}),
        cl.Action(name="show_session_list", label="🗂️ Tải hội thoại cũ", payload={})
    ]
    
    # (SỬA LỜI CHÀO Ở ĐÂY)
    await cl.Message(
        content=f"✅ **Hệ thống đã sẵn sàng cho {display_name}**\n\n"
                "Bạn có thể bắt đầu hội thoại hoặc chọn lại phiên cũ bên dưới 👇",
        actions=actions
    ).send()

    # --- 5. Khởi tạo LLMs ---
    llm_logic = ChatOpenAI(model="gpt-4.1-mini", temperature=0, api_key=OPENAI_API_KEY)
    llm_vision = ChatOpenAI(model="gpt-4.1-mini", temperature=0, api_key=OPENAI_API_KEY)
    cl.user_session.set("llm_logic", llm_logic)
    cl.user_session.set("llm_vision", llm_vision)
    
    # --- 6. Khởi động Poller cho session này ---
    poller_task = asyncio.create_task(session_receiver_poller())
    cl.user_session.set("poller_task", poller_task)
    print("✅ Kết nối OpenAI OK.")
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (THÊM KHỐI NÀY) 🚀 ---
    # (MỚI) 6b. Khởi tạo Vectorstore & Retriever cho USER
    try:
        vectorstore, retriever = await asyncio.to_thread(
            get_user_vectorstore_retriever, user_id_str
        )
        cl.user_session.set("vectorstore", vectorstore)
        cl.user_session.set("retriever", retriever)
    except Exception as e_vec:
        print(f"❌ Lỗi nghiêm trọng khi khởi tạo Vectorstore: {e_vec}")
        await cl.Message(content=f"❌ Lỗi khởi tạo Vectorstore: {e_vec}").send()
        return # Dừng setup nếu không có vectorstore

    # --- 7. RAG Chain (TỔNG HỢP) ---
    rag_prompt = ChatPromptTemplate.from_template(
        "Bạn là một trợ lý RAG (truy xuất-tăng cường). Nhiệm vụ của bạn là trả lời câu hỏi của người dùng (input) CHỈ dựa trên thông tin trong (context) được cung cấp."
        "\n\nContext:\n{context}\n\nCâu hỏi: {input}"
    )
    document_chain = create_stuff_documents_chain(llm_logic, rag_prompt)
    cl.user_session.set("document_chain", document_chain)
    
    # --- 8. Retrieval Chain ---
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    cl.user_session.set("retrieval_chain", retrieval_chain)

    # --- 9. Tools (Định nghĩa các tool VỚI ĐẦY ĐỦ DOCSTRING) ---
    class XoaCongViecSchema(BaseModel):
        noi_dung_cong_viec: str = Field(..., description="Nội dung/Tiêu đề của công việc cần xóa, ví dụ: 'hoàn thành báo cáo'")

    @tool("xoa_cong_viec", args_schema=XoaCongViecSchema)
    async def xoa_cong_viec(noi_dung_cong_viec: str) -> str:
        """
        Xóa một (hoặc nhiều) công việc CHƯA HOÀN THÀNH
        dựa theo nội dung/tiêu đề của nó.
        """
        user_id_str = cl.user_session.get("user_id_str")
        if not user_id_str:
            return "❌ Lỗi: Mất user_id. Vui lòng F5."
        try:
            deleted_count = await asyncio.to_thread(
                _delete_task_by_title_db, 
                user_id_str, 
                noi_dung_cong_viec
            )
            if deleted_count > 0:
                return f"✅ Đã xóa {deleted_count} công việc khớp với '{noi_dung_cong_viec}'."
            else:
                return f"⚠️ Không tìm thấy công việc nào (chưa hoàn thành) khớp với '{noi_dung_cong_viec}'."
        except Exception as e:
            return f"❌ Lỗi khi xóa công việc: {e}"

    class XoaGhiChuSchema(BaseModel):
        noi_dung_ghi_chu: str = Field(..., description="Nội dung/từ khóa của ghi chú (note) cần xóa")

    @tool("xoa_ghi_chu", args_schema=XoaGhiChuSchema)
    async def xoa_ghi_chu(noi_dung_ghi_chu: str) -> str:
        """
        Xóa một (hoặc nhiều) ghi chú (note) văn bản
        dựa theo nội dung của nó.
        """
        vectorstore = cl.user_session.get("vectorstore")
        if not vectorstore:
            return "❌ Lỗi: Không tìm thấy vectorstore."
        try:
            deleted_count = await asyncio.to_thread(
                _delete_note_by_content_db, 
                vectorstore,
                noi_dung_ghi_chu
            )
            if deleted_count > 0:
                return f"✅ Đã xóa {deleted_count} ghi chú khớp với '{noi_dung_ghi_chu}'."
            else:
                return f"⚠️ Không tìm thấy ghi chú (text) nào khớp với '{noi_dung_ghi_chu}'."
        except Exception as e:
            return f"❌ Lỗi khi xóa ghi chú: {e}"

    class XoaNhacNhoSchema(BaseModel):
        noi_dung_nhac_nho: str = Field(..., description="Nội dung của nhắc nhở cần xóa")

    @tool("xoa_nhac_nho", args_schema=XoaNhacNhoSchema)
    async def xoa_nhac_nho(noi_dung_nhac_nho: str) -> str:
        """
        Xóa một (hoặc nhiều) lịch nhắc nhở (reminder)
        đang hoạt động dựa theo nội dung của nó.
        """
        try:
            deleted_count = await asyncio.to_thread(
                _delete_reminder_by_text_db, 
                noi_dung_nhac_nho
            )
            if deleted_count > 0:
                return f"✅ Đã xóa {deleted_count} lịch nhắc khớp với '{noi_dung_nhac_nho}'."
            else:
                return f"⚠️ Không tìm thấy lịch nhắc nào khớp với '{noi_dung_nhac_nho}'."
        except Exception as e:
            return f"❌ Lỗi khi xóa lịch nhắc: {e}"
    
    # (Dán Schema này vào gần dòng 1880, cùng với các Schema khác)
    

    # (Dán Tool MỚI này vào gần dòng 2280, TRƯỚC các tool Admin)

    # --- (DÁN TOOL MỚI VÀO ĐÂY) ---
    @tool("hien_thi_web", args_schema=HienThiWebSchema)
    async def hien_thi_web(url: str) -> str:
        """
        Nhúng (embed) một trang web hoặc video (như Youtube)
        vào màn hình chat bằng cách sử dụng iframe.
        """
        try:
            # (File của bạn đã import 'html' ở dòng 8)
            
            # Đặc biệt xử lý Youtube embed
            if "youtube.com/embed/" in url:
                # Trả về Markdown cho iframe
                response_md = f"""
                    Đây là video bạn yêu cầu:
                    <iframe 
                        width="560" 
                        height="315" 
                        src="{html.escape(url)}" 
                        title="YouTube video player" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowfullscreen>
                    </iframe>
                    """
                return response_md
            else:
                # Trả về link Markdown thông thường cho các URL khác
                return f"Đây là nội dung web bạn yêu cầu: [{url}]({html.escape(url)})"
                
        except Exception as e:
            return f"❌ Lỗi khi nhúng URL: {e}"
    # --- (KẾT THÚC DÁN TOOL MỚI) ---
    
    @tool("xem_bo_nho")
    async def xem_bo_nho(show: str = "xem") -> str:
        """
        Liệt kê toàn bộ ghi chú (TEXT) đã lưu 
        và hiển thị nút xóa cho từng ghi chú trong UI.
        """
        try:
            await ui_show_all_memory()
        except Exception as e:
            return f"❌ Lỗi khi hiển thị bộ nhớ: {e}"
        return "✅ Đã liệt kê các ghi chú văn bản trong bộ nhớ."

    @tool
    async def xem_tu_dien_fact(xem: str = "xem"):
        """
        (ADMIN/DEBUG) Hiển thị "Từ điển Fact" 
        (bộ nhớ cache câu hỏi -> key) của user.
        """
        user_id_str = cl.user_session.get("user_id_str")
        if not user_id_str: return "❌ Lỗi: Không tìm thấy user_id_str."
        try:
            fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
            if not fact_dict: return "📭 Từ điển fact của bạn đang trống."
            header = "📖 **Từ điển Fact (Câu hỏi -> Key):**\n"
            items = [f"• `{q}` ➔ `{k}`" for q, k in fact_dict.items()]
            return header + "\n".join(sorted(items))
        except Exception as e:
            return f"❌ Lỗi khi đọc từ điển fact: {e}"

    @tool("luu_thong_tin", args_schema=LuuThongTinSchema)
    async def luu_thong_tin(noi_dung: str):
        """
        Lưu một mẩu thông tin (văn bản) vào bộ nhớ vector (ChromaDB)
        của người dùng. Tự động phân loại fact bằng LLM.
        """
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic") 
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy LLM (llm_logic)."
        try:
            text = (noi_dung or "").strip()
            if not text: return "⚠️ Không có nội dung để lưu."
            facts_list = await _extract_fact_from_llm(llm, text)
            texts_goc = [text]
            fact_keys_to_delete = [] 
            fact_key_pattern = re.compile(r"^FACT:\s*([^=]+?)\s*=")
            for fact_str in facts_list:
                match = fact_key_pattern.search(fact_str)
                if match:
                    fact_key = match.group(1).strip()
                    if fact_key: fact_keys_to_delete.append(fact_key)
                texts_goc.append(fact_str)
            deleted_count = 0
            if fact_keys_to_delete:
                def _delete_old_facts():
                    nonlocal deleted_count
                    for key in fact_keys_to_delete:
                        try:
                            regex_pattern = f"FACT: {key} ="
                            existing_docs = vectorstore._collection.get(where_document={"$regex": regex_pattern})
                            ids_to_delete = existing_docs.get("ids", [])
                            if ids_to_delete:
                                vectorstore._collection.delete(ids=ids_to_delete)
                                deleted_count += len(ids_to_delete)
                        except Exception as e:
                            print(f"[Debug] Lỗi khi xóa 'FACT' ({key}): {e}")
                await asyncio.to_thread(_delete_old_facts)
            tat_ca_texts = list(set(texts_goc))
            await asyncio.to_thread(vectorstore.add_texts, tat_ca_texts)
            msg = f"✅ ĐÃ LƯU: {text}"
            if facts_list: msg += f" (Đã phân loại Fact: {facts_list[0]})"
            if deleted_count > 0: msg += f" (và đã xóa {deleted_count} 'FACT' cũ)."
            return msg
        except Exception as e:
            return f"❌ LỖI LƯU: {e}"

    @tool(args_schema=DatLichSchema)
    async def dat_lich_nhac_nho(noi_dung_nhac: str, thoi_gian: str, escalate: bool = False) -> str:
        """
        Lên lịch một thông báo nhắc nhở.
        """
        vectorstore = cl.user_session.get("vectorstore")
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        try:
            ensure_scheduler()
            internal_session_id = cl.user_session.get("chainlit_internal_id")
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."
            if not internal_session_id: return "❌ LỖI: Không tìm thấy 'chainlit_internal_id'. Vui lòng F5."
            noti_text = (noi_dung_nhac or "").strip()
            if not noti_text: return "❌ Lỗi: Cần nội dung nhắc."
            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if repeat_sec > 0:
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                job_id = f"reminder-interval-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[internal_session_id, noti_text], replace_existing=False, misfire_grace_time=60)
                await asyncio.to_thread(vectorstore.add_texts, [f"[REMINDER_INTERVAL] every={repeat_sec}s | {noti_text} | job_id={job_id}"])
                return f"🔁 ĐÃ LÊN LỊCH LẶP: '{noti_text}' • mỗi {repeat_sec} giây"
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                job_id = f"reminder-cron-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                SCHEDULER.add_job(_do_push, trigger=cron["trigger"], id=job_id, args=[internal_session_id, noti_text], replace_existing=False, misfire_grace_time=60)
                await asyncio.to_thread(vectorstore.add_texts, [f"[REMINDER_CRON] type={cron['type']} | {thoi_gian} | {noti_text} | job_id={job_id}"])
                return f"📅 ĐÃ LÊN LỊCH ({cron['type']}): '{noti_text}' • {thoi_gian}"
            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian) # <-- THÊM AWAIT
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
            if escalate:
                job_id = f"first-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_first_fire_escalation_job, trigger=trigger, id=job_id, args=[internal_session_id, noti_text, 5], replace_existing=False, misfire_grace_time=60)
                await asyncio.to_thread(vectorstore.add_texts, [f"[REMINDER_ESCALATE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"])
                return f"⏰ ĐÃ LÊN LỊCH (Leo thang): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
            else:
                job_id = f"reminder-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[internal_session_id, noti_text], replace_existing=False, misfire_grace_time=60)
                await asyncio.to_thread(vectorstore.add_texts, [f"[REMINDER_ONCE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"])
                return f"⏰ ĐÃ LÊN LỊCH (1 lần): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
        except Exception as e:
            return f"❌ Lỗi khi tạo nhắc: {e}"

    @tool
    async def hoi_thong_tin(cau_hoi: str):
        """
        Hỏi một câu hỏi và tìm câu trả lời từ bộ nhớ (RAG).
        Chỉ dùng khi người dùng HỎI THÔNG TIN (ví dụ: 'tôi thích ăn gì?').
        """
        try:
            user_id_str = cl.user_session.get("user_id_str")
            retriever = cl.user_session.get("retriever")
            document_chain = cl.user_session.get("document_chain")
            llm = cl.user_session.get("llm_logic")
            if not all([user_id_str, retriever, document_chain, llm]):
                return "❌ Lỗi: Phiên làm việc bị thiếu thông tin (user, retriever, chain, llm). Vui lòng F5."
            fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
            cau_hoi_clean = cau_hoi.strip().lower()
            fact_key = fact_dict.get(cau_hoi_clean)
            if fact_key is None:
                print(f"[Debug] Fact key cache MISS cho: '{cau_hoi_clean}'")
                existing_keys = list(set(fact_dict.values()))
                fact_key = await call_llm_to_classify(llm, cau_hoi, existing_keys)
                if fact_key:
                    fact_dict[cau_hoi_clean] = fact_key
                    await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
                    print(f"[Debug] LLM đã phân loại và LƯU: '{cau_hoi_clean}' -> '{fact_key}'")
                else: fact_key = "general_query"
            else: print(f"[Debug] Fact key cache HIT: '{cau_hoi_clean}' -> '{fact_key}'")
            search_query = f"FACT: {fact_key} = | {fact_key}"
            print(f"[Debug] Đang tìm RAG với query: '{search_query}'")
            docs = await retriever.ainvoke(search_query)
            resp = await document_chain.ainvoke({"context": docs, "input": cau_hoi})
            return resp or "Tôi chưa có thông tin đó."
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi truy xuất thông tin: {e}"

    @tool("xem_lich_nhac")
    async def xem_lich_nhac() -> str:
        """
        Hiển thị tất cả các lịch nhắc (reminders)
        đang hoạt động trong UI.
        """
        try: await ui_show_active_reminders()
        except Exception as e: return f"❌ Lỗi khi hiển thị lịch: {e}"
        return "✅ Đã liệt kê các lịch nhắc đang hoạt động."

    @tool
    async def tim_file_de_tai_ve(ten_goc_cua_file: str):
        """
        Tìm một file hoặc ảnh đã lưu dựa theo TÊN GỐC
        và trả về link/ảnh để tải về.
        """
        retriever = cl.user_session.get("retriever")
        if not retriever: return "❌ Lỗi: Không tìm thấy retriever."
        try:
            results = await retriever.ainvoke(f"file hoặc ảnh có tên {ten_goc_cua_file}")
            found_path_url = None; found_name = ten_goc_cua_file; is_image = False 
            for doc in results:
                content = doc.page_content
                if ten_goc_cua_file.lower() in content.lower() and ("[FILE]" in content or "[IMAGE]" in content):
                    path_match = re.search(r"path=([^|]+)", content)
                    name_match = re.search(r"name=([^|]+)", content)
                    if path_match and name_match:
                        full_path = path_match.group(1).strip()
                        saved_name = os.path.basename(full_path)
                        found_name = name_match.group(1).strip() 
                        is_image = "[IMAGE]" in content
                        found_path_url = f"/public/files/{saved_name}" 
                        break 
            if found_path_url:
                safe_href = found_path_url; safe_name = html.escape(found_name)
                if is_image: return f"Tìm thấy ảnh: \n![{safe_name}]({safe_href})"
                else: return f"Tìm thấy file: **[{safe_name}]({safe_href})**"
            else: return f"⚠️ Không tìm thấy file hoặc ảnh nào khớp với tên '{ten_goc_cua_file}'."
        except Exception as e: return f"❌ Lỗi khi tìm file: {e}"

    @tool("xem_danh_sach_file")
    async def xem_danh_sach_file() -> str:
        """
        Hiển thị tất cả các file và ảnh đã được lưu 
        trong bộ nhớ (UI).
        """
        try: await ui_show_active_files()
        except Exception as e: return f"❌ Lỗi khi hiển thị danh sách file: {e}"
        return "✅ Đã liệt kê danh sách file."

    @tool(args_schema=PushThuSchema)
    def push_thu(noidung: str):
        """
        (DEBUG) Gửi một thông báo push (thông báo)
        thử nghiệm ngay lập tức.
        """
        try:
            internal_session_id = cl.user_session.get("chainlit_internal_id")
            if not internal_session_id: return "❌ LỖI: Không tìm thấy 'chainlit_internal_id' (F5)."
            clean_text = (noidung or "").strip()
            _do_push(internal_session_id, clean_text or "Test push")
            return f"PUSH_THU_OK ({clean_text})"
        except Exception as e: return f"PUSH_THU_ERROR: {e}"

    # --- 🚀 BẮT ĐẦU CẬP NHẬT LOGIC TOOL (dòng 2060) 🚀 ---
    class DatLichCongViecSchema(BaseModel):
        noi_dung: str = Field(..., description="Nội dung công việc, ví dụ: 'Hoàn thành báo cáo'")
        thoi_gian: str = Field(..., description="Thời gian đến hạn: '1 phút nữa', '20:15', 'mai 8h', 'thứ 3 hàng tuần 9h'")
        mo_ta: Optional[str] = Field(None, description="Mô tả chi tiết cho công việc") # <-- THÊM DÒNG NÀY

    @tool(args_schema=DatLichCongViecSchema)
    async def dat_lich_cong_viec(noi_dung: str, thoi_gian: str, mo_ta: Optional[str] = None) -> str: # <-- THÊM mo_ta
        """
        Lên lịch một CÔNG VIỆC (task) cần hoàn thành.
        Công việc này có thể được xem và đánh dấu 'hoàn thành'.
        """
        user_id_str = cl.user_session.get("user_id_str")
        internal_session_id = cl.user_session.get("chainlit_internal_id")
        if not user_id_str or not internal_session_id:
            return "❌ Lỗi: Mất user_id hoặc internal_session_id. Vui lòng F5."
            
        try:
            ensure_scheduler()
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."

            task_text = (noi_dung or "").strip()
            if not task_text: return "❌ Lỗi: Cần nội dung công việc."
            
            # Xử lý thời gian (y hệt reminder)
            dt_when = None
            recurrence_rule = None
            trigger = None
            job_id_suffix = f"{internal_session_id}-{uuid.uuid4().hex[:6]}"
            
            # 1. Kiểm tra Cron (hàng tuần/tháng/ngày)
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                recurrence_rule = f"cron:{cron['type']}:{thoi_gian}"
                trigger = cron["trigger"]
                # Lấy lần chạy đầu tiên làm due_date
                temp_job = SCHEDULER.add_job(_do_push, trigger=trigger, id=f"temp-{job_id_suffix}")
                dt_when = temp_job.next_run_time
                SCHEDULER.remove_job(temp_job.id)
            
            # 2. Kiểm tra lặp lại (Interval)
            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if not dt_when and repeat_sec > 0:
                recurrence_rule = f"interval:{repeat_sec}s"
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                dt_when = datetime.now(VN_TZ) + timedelta(seconds=repeat_sec)

            # 3. Mặc định là 1 lần (DateTrigger)
            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian) # <-- THÊM AWAIT Ở ĐÂY
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)

            if not dt_when or not trigger:
                return f"❌ Lỗi: Không thể phân tích thời gian '{thoi_gian}'"

            # 4. Lưu vào CSDL trước
            # (Chúng ta cần task_id để tạo job_id)
            task_id = await asyncio.to_thread(
                _add_task_to_db, user_id_str, task_text, mo_ta, dt_when, recurrence_rule, None
            )
            # 5. Lên lịch Push
            job_id = f"taskpush-{task_id}-{job_id_suffix}"
            SCHEDULER.add_job(
                _push_task_notification, 
                trigger=trigger, 
                id=job_id, 
                args=[internal_session_id, task_text, task_id],
                replace_existing=False, 
                misfire_grace_time=60
            )
            
            # 6. Cập nhật lại CSDL với job_id
            conn = _get_user_db_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE user_tasks SET scheduler_job_id = ? WHERE id = ?", (job_id, task_id))
            conn.commit()
            conn.close()

            return f"✅ Đã lên lịch công việc: '{task_text}' (Hạn: {_fmt_dt(dt_when)})"
            
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi khi tạo công việc: {e}"
    @tool("xem_viec_chua_hoan_thanh")
    async def xem_viec_chua_hoan_thanh() -> str:
        """
        Hiển thị tất cả các CÔNG VIỆC (tasks)
        CHƯA hoàn thành trong UI.
        """
        try: 
            await ui_show_uncompleted_tasks() # <-- Sửa tên hàm
        except Exception as e: 
            return f"❌ Lỗi khi hiển thị danh sách công việc: {e}"
        return "✅ Đã liệt kê các công việc chưa hoàn thành."
    @tool("xem_viec_da_hoan_thanh")
    async def xem_viec_da_hoan_thanh() -> str:
        """
        Hiển thị tất cả các CÔNG VIỆC (tasks)
        ĐÃ hoàn thành trong UI.
        """
        try: 
            await ui_show_completed_tasks() # <-- Gọi hàm mới
        except Exception as e: 
            return f"❌ Lỗi khi hiển thị danh sách công việc đã hoàn thành: {e}"
        return "✅ Đã liệt kê các công việc đã hoàn thành."
    # (Tool xem_danh_sach_user của bạn bắt đầu từ đây...)
    @tool
    async def xem_danh_sach_user(xem: str = "xem"):
        """
        (CHỈ ADMIN) Lấy danh sách tất cả user và trạng thái admin
        từ cơ sở dữ liệu.
        """
        # 1. Kiểm tra quyền trong session
        is_admin = cl.user_session.get("is_admin", False)
        if not is_admin:
            return "❌ Lỗi: Bạn không có quyền thực hiện hành động này."

        # 2. Hàm sync để chạy trong thread
        def _get_users_sync():
            users_list = []
            try:
                conn = _get_user_db_conn()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # (SỬA) Thêm is_active
                cursor.execute("SELECT email, is_admin, is_active FROM users ORDER BY email")
                rows = cursor.fetchall()
                conn.close()
                
                for row in rows:
                    admin_tag = "🔑 ADMIN" if row['is_admin'] == 1 else ""
                    active_tag = "✅" if row['is_active'] == 1 else "⛔️"
                    users_list.append(f"• {active_tag} {row['email']} {admin_tag}")
                
                return f"👥 **Danh sách {len(users_list)} User:**\n(✅=Active, ⛔️=Inactive, 🔑=Admin)\n" + "\n".join(users_list)
                
            except Exception as e:
                return f"❌ Lỗi khi truy vấn CSDL user: {e}"

        # 3. Chạy hàm sync
        try:
            result = await asyncio.to_thread(_get_users_sync)
            return result
        except Exception as e_thread:
            return f"❌ Lỗi thread khi lấy user: {e_thread}"
    # (THÊM TOOL MỚI NÀY VÀO ĐÂY - khoảng dòng 2083)
    @tool("doi_mat_khau_user", args_schema=DoiMatKhauSchema)
    async def doi_mat_khau_user(email: str, new_password: str):
        """
        (CHỈ ADMIN) Đặt lại/Thay đổi mật khẩu cho một user
        bằng một mật khẩu mới.
        """
        # 1. Kiểm tra quyền trong session
        is_admin = cl.user_session.get("is_admin", False)
        if not is_admin:
            return "❌ Lỗi: Bạn không có quyền thực hiện hành động này."

        # 2. Chạy hàm sync
        try:
            ok, message = await asyncio.to_thread(
                _change_user_password_sync, 
                email, 
                new_password
            )
            return message
        except Exception as e_thread:
            return f"❌ Lỗi thread khi đổi mật khẩu: {e_thread}"
    # (THÊM TOOL MỚI NÀY VÀO ĐÂY - khoảng dòng 2100)
    @tool("lay_thong_tin_user", args_schema=LayThongTinUserSchema)
    async def lay_thong_tin_user(email: str):
        """
        (CHỈ ADMIN) Tra cứu và lấy thông tin chi tiết (như Tên)
        của một user cụ thể bằng email của họ.
        """
        # 1. Kiểm tra quyền admin
        is_admin = cl.user_session.get("is_admin", False)
        if not is_admin:
            return "❌ Lỗi: Bạn không có quyền thực hiện hành động này."

        # 2. Chạy hàm sync get_user_by_email
        try:
            # (Hàm get_user_by_email đã có sẵn ở dòng 313)
            user_data = await asyncio.to_thread(get_user_by_email, email)
            
            if not user_data:
                return f"⚠️ Không tìm thấy user nào có email: {email}"
            
            # Lấy thông tin
            user_name = user_data.get('name') or "(Chưa có tên)"
            user_email = user_data.get('email')
            is_active_str = "✅ Active" if user_data.get('is_active') == 1 else "⛔️ Inactive"
            is_admin_str = "🔑 ADMIN" if user_data.get('is_admin') == 1 else "Thường"
            
            return (
                f"✅ Thông tin user: {user_email}\n"
                f"• Tên: **{user_name}**\n"
                f"• Trạng thái: {is_active_str}\n"
                f"• Quyền: {is_admin_str}"
            )
            
        except Exception as e_thread:
            return f"❌ Lỗi thread khi lấy thông tin user: {e_thread}"
    # (MỚI) Định nghĩa tool cơ bản và tool admin
    # (THAY THẾ TOÀN BỘ KHỐI NÀY - khoảng dòng 2290)

    # === MỚI: Định nghĩa Tool bằng Dict (Rule + Tool Object) ===
    
    # (XÓA TOÀN BỘ base_tools_data CŨ VÀ DÁN KHỐI NÀY VÀO)
    
    # === MỚI: Định nghĩa Tool bằng Dict (Rule + Tool Object) ===
    
    base_tools_data = {
        # --- Hành động (Ưu tiên) ---
        
        # --- (MỚI) THÊM TOOL NÀY LÊN ĐẦU ---
        "hien_thi_web": {
            "rule": "(NHÚNG) Nếu 'input' yêu cầu 'nhúng', 'hiển thị web', 'mở video' (VÀ KHÔNG PHẢI LỆNH XÓA) -> Dùng `hien_thi_web`.",
            "tool": hien_thi_web
        },
        # --- (KẾT THÚC THÊM MỚI) ---
        
        "xoa_cong_viec": {
            "rule": "(XÓA CÔNG VIỆC) Nếu 'input' yêu cầu 'xóa công việc', 'hủy task', 'bỏ việc' -> Dùng `xoa_cong_viec`.",
            "tool": xoa_cong_viec
        },
        "xoa_ghi_chu": {
            "rule": "(XÓA GHI CHÚ) Nếu 'input' yêu cầu 'xóa ghi chú', 'xóa note' -> Dùng `xoa_ghi_chu`.",
            "tool": xoa_ghi_chu
        },
        "xoa_nhac_nho": {
            "rule": "(XÓA NHẮC NHỞ) Nếu 'input' yêu cầu 'xóa nhắc nhở', 'hủy lịch nhắc', 'bỏ nhắc' -> Dùng `xoa_nhac_nho`.",
            "tool": xoa_nhac_nho
        },
        "luu_thong_tin": {
            # --- (SỬA) SỬA LẠI RULE NÀY ---
            "rule": "(LƯU) Nếu 'input' YÊU CẦU LƯU (ví dụ: 'lưu lại', 'ghi chú') (VÀ KHÔNG PHẢI LỆNH XÓA HOẶC LỆNH NHÚNG) -> Dùng `luu_thong_tin`.",
            "tool": luu_thong_tin
        },
        "dat_lich_cong_viec": {
            "rule": "(TẠO CÔNG VIỆC) Nếu 'input' là 'công việc', 'task', 'checklist', 'việc cần làm' (VÀ KHÔNG phải 'xóa') -> Dùng `dat_lich_cong_viec`.",
            "tool": dat_lich_cong_viec
        },
        "dat_lich_nhac_nho": {
            "rule": "(TẠO NHẮC NHỞ) Nếu 'input' là 'nhắc nhở', 'nhắc tôi', 'đặt lịch' (VÀ KHÔNG phải 'xóa') -> Dùng `dat_lich_nhac_nho`.\n"
                    "   - (Cho Nhắc nhở) Nếu user nói 'nhắc lại', 'leo thang' -> BẮT BUỘC đặt `escalate=True`.",
            "tool": dat_lich_nhac_nho
        },
        # --- Tra cứu (Hỏi/Xem) ---
        "hoi_thong_tin": {
            "rule": "(HỎI) Nếu 'input' HỎI (VÀ KHÔNG PHẢI là các quy tắc Hành động) -> Dùng `hoi_thong_tin`.",
            "tool": hoi_thong_tin
        },
        "xem_viec_chua_hoan_thanh": {
            "rule": "(XEM) Nếu 'input' yêu cầu 'xem công việc', 'xem checklist', 'xem việc CHƯA LÀM' -> Dùng `xem_viec_chua_hoan_thanh`.",
            "tool": xem_viec_chua_hoan_thanh
        },
        "xem_viec_da_hoan_thanh": {
            "rule": "(XEM) Nếu 'input' yêu cầu 'xem việc ĐÃ HOÀN THÀNH', 'xem việc đã xong' -> Dùng `xem_viec_da_hoan_thanh`.",
            "tool": xem_viec_da_hoan_thanh
        },
        "xem_lich_nhac": {
            "rule": "(XEM) Nếu 'input' yêu cầu 'xem lịch nhắc', 'xem nhắc nhở' -> Dùng `xem_lich_nhac`.",
            "tool": xem_lich_nhac
        },
        "tim_file_de_tai_ve": {
            "rule": "(FILE) Nếu 'input' yêu cầu 'tìm file' (ví dụ: 'tìm file hợp đồng') -> Dùng `tim_file_de_tai_ve`.",
            "tool": tim_file_de_tai_ve
        },
        "xem_danh_sach_file": {
            "rule": "(FILE) Nếu 'input' yêu cầu 'xem TẤT CẢ file' -> Dùng `xem_danh_sach_file`.",
            "tool": xem_danh_sach_file
        },
        # --- Khác / Debug ---
        "xem_bo_nho": {
            "rule": "(KHÁC) Nếu 'input' yêu cầu 'xem bộ nhớ' (ghi chú text) -> Dùng `xem_bo_nho`.",
            "tool": xem_bo_nho
        },
        "xem_tu_dien_fact": {
            "rule": "(KHÁC) Nếu 'input' yêu cầu 'xem từ điển fact' (DEBUG) -> Dùng `xem_tu_dien_fact`.",
            "tool": xem_tu_dien_fact
        },
        "push_thu": {
            "rule": "(KHÁC) Nếu 'input' yêu cầu 'push thử' (DEBUG) -> Dùng `push_thu`.",
            "tool": push_thu
        }
    }
    # (KẾT THÚC THAY THẾ)
    
    admin_tools_data = {
        "doi_mat_khau_user": {
            "rule": "(ADMIN) Nếu 'input' yêu cầu 'đổi mật khẩu', 'reset pass' -> Dùng `doi_mat_khau_user`.",
            "tool": doi_mat_khau_user
        },
        "xem_danh_sach_user": {
            "rule": "(ADMIN) Nếu 'input' yêu cầu 'danh sách user', 'list user' -> Dùng `xem_danh_sach_user`.",
            "tool": xem_danh_sach_user
        },
        "lay_thong_tin_user": {
            "rule": "(ADMIN) Nếu 'input' hỏi 'thông tin', 'tên' của MỘT USER CỤ THỂ -> Dùng `lay_thong_tin_user`.",
            "tool": lay_thong_tin_user
        }
    }

    # === Kết thúc định nghĩa Dict ===

    # (MỚI) Lấy cờ admin từ session (đã được set ở on_start_after_login)
    is_admin = cl.user_session.get("is_admin", False)
    
    # 1. Gộp dict
    final_tools_data = {}
    if is_admin:
        print("🔑 [Agent] Đang thêm các tool ADMIN vào agent...")
        final_tools_data.update(admin_tools_data) # Admin lên đầu (ưu tiên)
        
    final_tools_data.update(base_tools_data) # Tool cơ bản

    # 2. Tạo danh sách Tool (list các object) cho Agent
    final_tools = [data["tool"] for data in final_tools_data.values()]
    
    # 3. Tạo danh sách Quy tắc (string) cho Prompt
    # (Đánh số thứ tự tự động)
    rule_strings = [f"{i+1}. {data['rule']}" for i, data in enumerate(final_tools_data.values())]
    dynamic_rules = "\n".join(rule_strings)

    # 4. Tạo danh sách tên tool (string) cho Prompt
    tool_name_list = ", ".join([f"`{name}`" for name in final_tools_data.keys()])

    # --- 10. Agent ---
    
    # (MỚI) Tạo prompt động VÀ ĐÃ SỬA LỖI MẬP MỜ
    # (THAY THẾ TOÀN BỘ NỘI DUNG BIẾN NÀY - khoảng dòng 2110)

    # (THAY THẾ TOÀN BỘ KHỐI NÀY - khoảng dòng 2355)

    agent_prompt_text = (
        f"Bạn là một bộ điều phối tool (Tool Dispatcher). Nhiệm vụ CỰC KỲ QUAN TRỌNG của bạn là phân tích 'input' của người dùng và CHỌN một tool từ danh sách: {tool_name_list}.\n"
        "\n"
        "BẠN KHÔNG ĐƯỢC PHÉP TRẢ LỜI TRỰC TIẾP (chat).\n"
        "BẠN CHỈ ĐƯỢC PHÉP GỌI TOOL.\n"
        "\n"
        "--- QUY TẮC CHỌN TOOL (BẮT BUỘC) ---\n"
        # --- (MỚI: TỰ ĐỘNG CHÈN QUY TẮC) ---
        f"{dynamic_rules}\n"
        # ------------------------------------
        "\n"
        "--- QUY TẮC TRẢ VỀ (QUAN TRỌNG) ---\n"
        "Nhiệm vụ của bạn KẾT THÚC ngay khi bạn gọi tool."
    )
    agent_prompt = ChatPromptTemplate.from_messages([
        ("system", agent_prompt_text), # <-- (SỬA) Dùng prompt động
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(
        llm=cl.user_session.get("llm_logic"),
        tools=final_tools, # <-- (SỬA) Dùng final_tools
        prompt=agent_prompt,
    )
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=final_tools, 
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True, #
    )
    cl.user_session.set("agent_executor", agent_executor)

    # --- 11. Kết thúc ---
    await cl.Message(
        content="🧠 **Trợ lý đã sẵn sàng**. Hãy nhập câu hỏi để bắt đầu!"
    ).send()
    
    all_elements = cl.user_session.get("elements", [])
    cl.user_session.set("elements", all_elements)

# =========================================================
# THAY THẾ TOÀN BỘ HÀM NÀY

# TÌM VÀ THAY THẾ TOÀN BỘ HÀM NÀY (khoảng dòng 2110)

@cl.on_message
async def on_message(message: cl.Message):
    """
    Phiên bản MỚI: (V12 - Sửa lỗi MẤT SESSION (agent_executor))
    - Lỗi là do Branch A (File) đã gọi `await cl.Message.send()`
      nhiều lần, làm hỏng session state.
    - Phiên bản này (V12) đảm bảo CHỈ CÓ 1 LỆNH .send() ở CUỐI HÀM.
    """
    
    try:
        # ----- 0) Tiền xử lý (LẤY CÁC BIẾN CẦN THIẾT) -----
        text = (message.content or "").strip()
        user = cl.user_session.get("user")
        if not user:
             await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất thông tin user. Vui lòng F5.").send()
             return
             
        user_id_str = user.identifier
        chat_history = cl.user_session.get("chat_history", [])
        session_id = cl.user_session.get("session_id")
        
        if not session_id:
            await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất session_id. Vui lòng F5.").send()
            return

        print(f"[on_message] User={user_id_str} Session={session_id} text={text!r}")

        # ----- 1) TỰ ĐỘNG DỪNG LEO THANG (Giữ nguyên) -----
        try:
            internal_session_id = cl.user_session.get("chainlit_internal_id")
            if internal_session_id in ACTIVE_ESCALATIONS:
                if not ACTIVE_ESCALATIONS[internal_session_id].get("acked"):
                    ACTIVE_ESCALATIONS[internal_session_id]["acked"] = True
                    print(f"[Escalation] Đã ACK (dừng) leo thang cho session {internal_session_id} do user phản hồi.")
        except Exception as e:
            print(f"[Escalation] Lỗi khi ack: {e}")
        # ---------------------------------------------------

        # ----- 2) LƯU TIN NHẮN USER (CHỈ 1 LẦN) -----
        chat_history.append({"role": "user", "content": text})

        # ----- 3) LOGIC XỬ LÝ (CHỌN NHÁNH) -----
        
        ai_output = None # Biến kết quả cuối cùng
        loading_msg = None # Biến tin nhắn tạm
        
        elements = message.elements
        vectorstore = cl.user_session.get("vectorstore")

        if elements and vectorstore:
            # --- NHÁNH A: XỬ LÝ FILE/IMAGE ---
            try:
                # 1. Gửi tin nhắn tạm (Sẽ bị xóa)
                loading_msg = await cl.Message(content=f"⏳ Đang xử lý {len(elements)} file/ảnh...").send()
                
                llm = cl.user_session.get("llm_logic")
                if not llm:
                    ai_output = "❌ Lỗi: Không tìm thấy LLM (llm_logic) khi lưu file."
                else:
                    # 2. Phân loại Fact Key
                    fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                    existing_keys = list(set(fact_dict.values()))
                    
                    user_note = text or "(không có ghi chú)"
                    user_note_clean = user_note.strip().lower()

                    fact_key = fact_dict.get(user_note_clean)
                    if fact_key is None:
                        print(f"[Debug] File Note Cache MISS: '{user_note_clean}'")
                        fact_key = await call_llm_to_classify(llm, user_note, existing_keys)
                        fact_dict[user_note_clean] = fact_key
                        await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
                        print(f"[Debug] File Note Classified: '{user_note_clean}' -> '{fact_key}'")
                    else:
                        print(f"[Debug] File Note Cache HIT: '{user_note_clean}' -> '{fact_key}'")

                    # (SỬA LỖI V12)
                    # KHÔNG .send() ở đây. Chỉ build một danh sách string.
                    saved_files_summary_lines = [] 
                    
                    # 3. Vòng lặp xử lý từng file
                    for el in elements:
                        try:
                            if "image" in el.mime:
                                # Gọi hàm helper ĐÃ SỬA (có fact_key)
                                _, name = await asyncio.to_thread(
                                    _save_image_and_note, vectorstore, el.path, user_note, el.name, fact_key
                                )
                                saved_files_summary_lines.append(f"✅ Đã lưu ảnh: **{name}**")
                            else:
                                # Gọi hàm helper ĐÃ SỬA (có fact_key)
                                chunks, name = await asyncio.to_thread(
                                    _load_and_process_document, vectorstore, el.path, el.name, el.mime, user_note, fact_key
                                )
                                if chunks > 0:
                                    saved_files_summary_lines.append(f"✅ Đã xử lý file: **{name}** ({chunks} chunks)")
                                else:
                                    saved_files_summary_lines.append(f"✅ Đã lưu file: **{name}** (chưa đọc)")

                        except Exception as e_file:
                            saved_files_summary_lines.append(f"❌ Lỗi xử lý file {el.name}: {e_file}")
                    
                    # 4. (SỬA LỖI V12)
                    # Tạo 1 chuỗi kết quả CUỐI CÙNG duy nhất
                    ai_output = (
                        f"**Kết quả xử lý file:** (Ghi chú: *{user_note}* | Key: *{fact_key}*)\n\n"
                        + "\n".join(saved_files_summary_lines)
                    )
            
            except Exception as e_branch_a:
                ai_output = f"❌ Lỗi nghiêm trọng khi xử lý file: {e_branch_a}"
                print(f"[ERROR] Branch A (File) crashed: {e_branch_a}")
                import traceback; traceback.print_exc()

        else:
            # --- NHÁNH B: XỬ LÝ TEXT (GỌI AGENT) ---
            try:
                agent = cl.user_session.get("agent_executor")
                if agent:
                    payload = {"input": text}
                    result = await agent.ainvoke(payload) # 'result' là dict phức tạp
                    
                    # --- 🚀 BẮT ĐẦU SỬA LỖI LOGIC 🚀 ---
                    
                    # ƯU TIÊN 1: Lấy kết quả từ tool (intermediate_steps)
                    steps = result.get("intermediate_steps") or []
                    if steps and isinstance(steps[-1], tuple) and len(steps[-1]) > 1:
                        # steps[-1] là (AgentAction, Observation)
                        # chúng ta lấy Observation (kết quả tool)
                        obs = steps[-1][1] 
                        if isinstance(obs, str) and obs.strip():
                            ai_output = obs.strip() # Đây là kết quả tool (ví dụ: "✅ Thông tin user...")
                        else:
                            ai_output = str(obs) # Chuyển đổi dự phòng
                    else:
                        # ƯU TIÊN 2: Lấy output (nếu tool không chạy, AI tự chat)
                        ai_output = result.get("output", "⚠️ Không có phản hồi (output rỗng).")
                    
                    # --- 🚀 KẾT THÚC SỬA LỖI LOGIC 🚀 ---
                        
                else:
                    ai_output = "✅ Đã đăng nhập. (LỖI: Không tìm thấy agent_executor, có thể setup_chat_session đã thất bại)"
            
            except Exception as e_branch_b:
                ai_output = f"❌ Lỗi gọi agent: {e_branch_b}"
                print(f"[ERROR] Branch B (Agent) crashed: {e_branch_b}")
                import traceback; traceback.print_exc()
        # ----- 4) TRẢ LỜI VÀ LƯU (THỐNG NHẤT) -----
        
        if loading_msg:
            await loading_msg.remove() # Xóa tin 'Đang xử lý...'
        
        if ai_output is None:
            ai_output = "⚠️ Lỗi: Bot không tạo ra phản hồi (ai_output is None)."

        # (SỬA LỖI V12)
        # CHỈ GỬI 1 LẦN DUY NHẤT Ở ĐÂY
        await cl.Message(content=ai_output).send()
        
        # 4b. Lưu vào history
        chat_history.append({"role": "assistant", "content": ai_output})
        
        # 4c. Lưu vào session và disk
        cl.user_session.set("chat_history", chat_history)
        await asyncio.to_thread(save_chat_history, user_id_str, session_id, chat_history)

    except Exception as e_main:
        await cl.Message(content=f"⚠️ Lỗi không mong muốn (main): {e_main}").send()
        import traceback
        traceback.print_exc()
        
@cl.on_chat_end
async def on_chat_end():
    session_id = cl.user_session.get("chainlit_internal_id", "unknown")
    try:
        task = cl.user_session.get("poller_task")
        if task:
            task.cancel()
            await asyncio.sleep(0.1) 
            print(f"[Session] Đã hủy task 'Thuê bao' cho {session_id}")
    except Exception as e:
        print(f"[Session] Lỗi khi on_chat_end: {e}")

# =========================================================
# 💬 Action Callbacks (UI)
# =========================================================
@cl.action_callback("new_chat")
async def on_new_chat(action: cl.Action):
    """Yêu cầu người dùng tải lại trang."""
    await cl.Message(content="✨ **Vui lòng làm mới (F5) trình duyệt của bạn để bắt đầu một cuộc trò chuyện mới.**").send()
    # Dòng "await cl.Reload().send()" đã bị xóa vì không còn được hỗ trợ

# (THAY THẾ HÀM NÀY - khoảng dòng 2480)
@cl.action_callback("show_session_list")
async def on_show_session_list(action: cl.Action):
    """
    SỬA LỖI (11): Dùng cl.run_sync cho list_sessions
    SỬA LỖI (User): Lấy tên hội thoại
    """
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    # SỬA: `sessions` bây giờ là List[dict]
    sessions = await asyncio.to_thread(list_sessions, user_id_str)
    
    if not sessions:
        await cl.Message(content="Không tìm thấy hội thoại cũ nào.").send()
        return

    # SỬA: Dùng dict để tạo label và payload
    actions = [
        cl.Action(
            name="load_specific_session",
            label=f"💬 {s['label']}", # <-- Dùng 'label' từ dict
            payload={"session_id": s['session_id']} # <-- Dùng 'session_id'
        ) 
        for s in sessions
    ]
    
    # (GIỮ NGUYÊN HÀNH VI CŨ: Gửi tin nhắn mới)
    # Lý do: Để không ghi đè mất nút "Cuộc trò chuyện mới"
    await cl.Message(
        content="Vui lòng chọn hội thoại để tải:", 
        actions=actions
    ).send()

async def replay_history(chat_history: list):
    """
    (SỬA LẠI) Phát lại lịch sử ra UI VÀ trả về danh sách
    các elements (tin nhắn) đã tạo.
    """
    new_elements = [] # <-- MỚI
    if not chat_history:
        msg = await cl.Message(content="(Hội thoại này chưa có nội dung)").send()
        new_elements.append(msg)
        return new_elements
    for m in chat_history:
        role = (m.get("role") or m.get("sender") or m.get("author") or "").lower()
        content = m.get("content") or m.get("text") or ""
        if not content:
            continue
        if role in ("user", "human"):
            msg = await cl.Message(author="Bạn", content=content).send()
            new_elements.append(msg)
        else:
            msg = await cl.Message(author="Trợ lý", content=content).send()
            new_elements.append(msg)
    return new_elements

# (Tìm hàm on_load_specific_session và THAY THẾ bằng hàm này)
@cl.action_callback("load_specific_session")
async def on_load_specific_session(action: cl.Action):
    """SỬA LỖI TREO (12): Dùng cl.run_sync cho load_chat_history"""
    
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return
        
    session_id = action.payload.get("session_id")
    if not session_id:
        await cl.Message(content="❌ Lỗi: Không nhận được session_id.").send()
        return

    # --- SỬA LỖI TREO (12) ---
    history = await asyncio.to_thread(load_chat_history, user_id_str, session_id) 
    
    if not history:
        await cl.Message(content=f"❌ Lỗi: Không tải được {session_id} hoặc file bị rỗng.").send()
        return

    try:
        all_elements = cl.user_session.get("elements", [])
        for el in all_elements:
            await el.remove()
        cl.user_session.set("elements", [])
    except Exception as e:
        print(f"Lỗi dọn dẹp UI: {e}")
    
    loading_msg = await cl.Message(content=f"✅ Đang tải hội thoại: **{session_id}**...").send()

    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_history", history)
    
    replayed_elements = await replay_history(history)
    
    new_elements_list = [loading_msg] + replayed_elements
    cl.user_session.set("elements", new_elements_list)