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
from bs4 import BeautifulSoup
from chromadb.config import Settings
import contextvars
from datetime import datetime, timedelta # <-- SỬA: Thêm timedelta
from typing import List, Tuple, Optional, Union
from pydantic import BaseModel, Field
import chainlit as cl
from chainlit import Image as ClImage
from chainlit import Video as ClVideo, Text as ClText
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
import calendar
from typing import Any
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger # <--- MỚI: Thêm CronTrigger
from chainlit.element import CustomElement # <-- 🚀 THÊM DÒNG NÀY
# --- MỚI: Thêm các import bị thiếu cho RAG/Agent ---
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
# ----------------------------------------------------

GLOBAL_MESSAGE_QUEUE: Optional[Queue] = None   # "Tổng đài" (chỉ 1)
ACTIVE_SESSION_QUEUES = {}                     # (SỬA) { user_id_str: [queue1, queue2] }
POLLER_STARTED = False                         # Cờ để khởi động Tổng đài (1 lần)                      # Cờ để khởi động Tổng đài (1 lần)
# =========================================================
# 📦 Env
# =========================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# Push-noti config (có thể đưa vào .env)
PUSH_API_URL = "https://ocrm.oshima.vn/api/method/createpushnoti"
PUSH_API_TOKEN = os.getenv("OCRMPUSH_TOKEN", "1773d804508a47b:d3ca2affa83ccab")
PUSH_DEFAULT_URL = "https://ocrm.oshima.vn/app/server-script/tao%20pushnoti"
# (Ngay dưới SEARCH_API_URL)
SEARCH_API_URL = "https://ocrm.oshima.vn/api/method/searchlistproductnew" # <-- Dòng đã có
DETAIL_API_URL = "https://ocrm.oshima.vn/api/method/getproductdetail" # <-- 🚀 THÊM DÒNG NÀY
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
SEARCH_API_URL = "https://ocrm.oshima.vn/api/method/searchlistproductnew" # <-- 🚀 THÊM DÒNG NÀY (Nhớ thay URL nếu cần)
GETUSER_API_URL = os.getenv("GETUSER_API_URL", "https://ocrm.oshima.vn/api/method/getuserocrm")
CHART_API_URL = "https://ocrm.oshima.vn/api/method/salesperson" # <-- Khai báo thẳng URL ở đây
CHANGEPASS_API_URL="https://ocrm.oshima.vn/api/method/changepassword"
# 2. Thư mục toàn cục cho file public (không đổi)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
# Thư mục này sẽ chứa file upload của *tất cả* user
# Chúng ta sẽ phân tách bằng tên file (uuid)
PUBLIC_FILES_DIR = os.path.join(PUBLIC_DIR, "files")
os.makedirs(PUBLIC_FILES_DIR, exist_ok=True)

# 3. Thư mục MỚI chứa TẤT CẢ dữ liệu riêng của người dùng
USER_DATA_ROOT = os.path.join(BASE_DIR, "user_data")
os.makedirs(USER_DATA_ROOT, exist_ok=True)



# 5. Các thư mục con (SESSIONS, VECTOR) sẽ được tạo động theo user_id
# (Thêm vào khoảng dòng 100)

# --- 🚀 THÊM DÒNG NÀY (Theo cách của bạn) 🚀 ---

# --- 🚀 KẾT THÚC THÊM DÒNG 🚀 ---

CHANGEPASS_API_URL = os.getenv("CHANGEPASS_API_URL", "")

# Thư mục sessions và CSDL
USER_SESSIONS_ROOT = os.path.join(USER_DATA_ROOT, "sessions")
os.makedirs(USER_SESSIONS_ROOT, exist_ok=True)

USERS_DB_FILE = os.path.join(USER_DATA_ROOT, "users.sqlite")

# Vector DB TẬP TRUNG (1 DB duy nhất cho tất cả user)
SHARED_VECTOR_DB_DIR = os.path.join(USER_DATA_ROOT, "shared_vector_db")
os.makedirs(SHARED_VECTOR_DB_DIR, exist_ok=True)

# Fact Dict vẫn tách riêng
USER_FACT_DICTS_ROOT = os.path.join(USER_DATA_ROOT, "fact_dictionaries")
os.makedirs(USER_FACT_DICTS_ROOT, exist_ok=True)

# NEW: timeout giây
PUSH_TIMEOUT = int(os.getenv("PUSH_TIMEOUT", "15"))

# Timezone VN
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Cache vectorstore toàn cục (chỉ khởi tạo 1 lần)
_SHARED_VECTORSTORE_CL = None
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
# (Dán vào khoảng dòng 130)

# --- 🚀 BẮT ĐẦU: CẤU HÌNH AVATAR HELPER (V47) 🚀 ---
def _sanitize_email_for_path(email: str) -> str:
    """
    (MỚI - GIỐNG NICEGUI)
    Chuyển email thành tên thư mục an toàn.
    Ví dụ: "user@domain.com" -> "user_domain_com"
    """
    # Thay @ và . bằng _
    safe_name = re.sub(r"[@\.]", "_", email)
    # Xóa các ký tự không an toàn còn lại
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", safe_name)
    return safe_name.lower()  # Lowercase để tránh phân biệt chữ hoa/thường


def get_user_fact_dict_path(user_email: str) -> str:
    """
    (MỚI - GIỐNG NICEGUI)
    Lấy đường dẫn file JSON từ điển fact của user.
    Dùng EMAIL làm định danh.
    """
    safe_name = _sanitize_email_for_path(user_email)
    user_dir = os.path.join(USER_FACT_DICTS_ROOT, safe_name)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "fact_map.json")
# ==================== PATCH 3: TỐI ƯU HÓA TỐC ĐỘ TÌM KIẾM ====================
# Thêm vào đầu file (sau các import, khoảng dòng 50)

# Cache collection để tránh gọi .get() nhiều lần
_FILE_LIST_CACHE = {}
_CACHE_TIMEOUT = 5  # seconds


def _get_cached_file_list(vectorstore: Chroma, user_email: str) -> list:
    """
    (MỚI - OPTIMIZATION)
    Lấy danh sách file với cache 5 giây để tránh query Chroma liên tục.
    """
    global _FILE_LIST_CACHE
    import time
    
    cache_key = f"{user_email}_files"
    now = time.time()
    
    # Kiểm tra cache
    if cache_key in _FILE_LIST_CACHE:
        cached_data, cached_time = _FILE_LIST_CACHE[cache_key]
        if (now - cached_time) < _CACHE_TIMEOUT:
            print(f"[Cache HIT] Dùng cache cho {user_email}")
            return cached_data
    
    # Cache miss -> Query Chroma
    print(f"[Cache MISS] Query Chroma cho {user_email}")
    file_list = list_active_files(vectorstore)
    _FILE_LIST_CACHE[cache_key] = (file_list, now)
    
    return file_list
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
        await cl.Message(content="Lỗi: Không tìm thấy thông tin user sau khi đăng nhập.",).send()
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

    # SỬA LỖI: Dòng 374-380 (app.py)

    user_dict = cl.user_session.get("user")
    if not user_dict:
        await cl.Message(content="❌ Lỗi: Không tìm thấy thông tin user.").send()
        return

    # SỬA: user_dict là object User (không phải dict), dùng .identifier thay vì .get()
    user_email = user_dict.identifier if hasattr(user_dict, 'identifier') else "unknown@example.com"
    user_email = user_email.lower()  # Chuẩn hóa email (lowercase)

    cl.user_session.set("user_email", user_email)  # Lưu email vào session
    print(f"✅ [on_chat_start] User email: {user_email}")
    
    # --- KHỞI TẠO SHARED VECTORSTORE (1 DB DUY NHẤT CHO TẤT CẢ USER) ---
    global _SHARED_VECTORSTORE_CL
    
    if _SHARED_VECTORSTORE_CL is None:
        print("[Shared DB] Đang khởi tạo Shared VectorStore lần đầu...")
        _SHARED_VECTORSTORE_CL = Chroma(
            persist_directory=SHARED_VECTOR_DB_DIR,
            embedding_function=embeddings,
            collection_name="shared_memory"
        )
        print(f"✅ [Shared DB] Shared VectorStore đã khởi tạo tại {SHARED_VECTOR_DB_DIR}")
    else:
        print(f"[Shared DB] Sử dụng lại Shared VectorStore đã có (user: {user_email})")
    
    # Lưu vào session
    cl.user_session.set("vectorstore", _SHARED_VECTORSTORE_CL)
    retriever = _SHARED_VECTORSTORE_CL.as_retriever(search_kwargs={"k": 100})
    cl.user_session.set("retriever", retriever)
    
    print(f"✅ VectorStore cho user '{user_email}' đã sẵn sàng tại {SHARED_VECTOR_DB_DIR} (mode=Similarity K=100)")
    
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
def _delete_note_by_content_db(
    vectorstore: Chroma, 
    llm: ChatOpenAI, # <-- 1. THÊM LLM
    content_query: str, 
    dry_run: bool = False
) -> Union[int, List[str]]:
    """
    (NÂNG CẤP LẦN 4: LLM Filter - Theo yêu cầu của user)
    B1: Vector Search (Tìm gần giống).
    B2: Lọc rác (Python).
    B3: Dùng LLM lọc thông minh (Giải quyết nhiễu ngữ nghĩa).
    """
    try:
        # --- BƯỚC 1: TÌM GẦN GIỐNG (VECTOR SEARCH) ---
        query_vector = embeddings.embed_query(content_query)
        results = vectorstore._collection.query(
            query_embeddings=[query_vector],
            n_results=20, # Lấy 20 ứng viên
            include=["documents"]
        )
        
        ids_to_process = results.get("ids", [[]])[0]
        docs_to_process = results.get("documents", [[]])[0]
        
        if not ids_to_process:
            return [] if dry_run else 0
            
        # --- BƯỚC 2: LỌC BỎ RÁC BẰNG PYTHON (Lọc cơ bản) ---
        # (Lọc bỏ FACT, FILE, v.v... để LLM không bị nhiễu)
        candidate_notes = []
        for doc_id, content in zip(ids_to_process, docs_to_process):
            if not content: continue
            if content.startswith("[FILE]") or \
               content.startswith("[IMAGE]") or \
               content.startswith("[REMINDER_") or \
               content.startswith("[ERROR_PROCESSING_FILE]") or \
               content.startswith("[FILE_UNSUPPORTED]") or \
               content.startswith("Trích từ tài liệu:") or \
               content.startswith("[WEB_LINK]") or \
               content.startswith("Link video YouTube đã lưu:") or \
               content.startswith("Link trang web đã lưu:") or \
               content.startswith("FACT:"):
                continue
            # Đây là ghi chú văn bản thuần túy -> thêm vào danh sách ứng viên
            candidate_notes.append({"id": doc_id, "doc": content})

        if not candidate_notes:
            return [] if dry_run else 0 # Không có ứng viên nào

        # --- BƯỚC 3: DÙNG LLM LỌC THÔNG MINH (Ý của bạn) ---
        # (Hàm này chạy sync, dùng llm.invoke)
        filtered_results = _llm_filter_for_deletion(
            llm, content_query, candidate_notes
        )
        
        if not filtered_results:
            return [] if dry_run else 0 # LLM đã lọc hết

        # --- BƯỚC 4: TRẢ VỀ KẾT QUẢ ĐÃ LỌC ---
        if dry_run:
            print(f"[NoteDB] DryRun (LLM): Tìm thấy {len(filtered_results)} ghi chú cho: '{content_query}'")
            return [r['doc'] for r in filtered_results]
        else:
            ids_to_delete = [r['id'] for r in filtered_results]
            vectorstore._collection.delete(ids=ids_to_delete)
            print(f"[NoteDB] Đã xóa {len(ids_to_delete)} ghi chú (LLM): '{content_query}'")
            return len(ids_to_delete)
        
    except Exception as e:
        print(f"❌ Lỗi _delete_note_by_content_db (LLM):")
        traceback.print_exc()
        return [] if dry_run else 0
    
    
def _find_tasks_by_title_db(user_email: str, title_query: str) -> List[dict]:
    """
    (NÂNG CẤP) (SYNC) Chỉ TÌM (không xóa) các công việc CHƯA HOÀN THÀNH.
    (SỬA LỖI: Dùng unidecode để tìm kiếm không phân biệt dấu.)
    """
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (Accent-insensitive) 🚀 ---
    conn = _get_user_db_conn()
    
    # 1. (MỚI) Đăng ký hàm unidecode với SQLite
    # (Chỉ có tác dụng trên 'conn' này)
    try:
        conn.create_function("unidecode", 1, unidecode.unidecode)
        use_unidecode = True
        print("[TaskFinder] Đã đăng ký unidecode (tìm kiếm không dấu).")
    except Exception as e:
        print(f"⚠️ Lỗi khi đăng ký unidecode (sẽ dùng LIKE): {e}")
        use_unidecode = False
        
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 2. (MỚI) Chuẩn bị query và params
    if use_unidecode:
        # Query thông minh (không phân biệt dấu)
        query = "SELECT id, title, description FROM user_tasks WHERE user_email = ? AND unidecode(title) LIKE ? AND is_completed = 0"
        # Chuẩn bị query (cũng không dấu, và thêm %%)
        safe_query_param = f"%{unidecode.unidecode(title_query)}%"
        params = (user_email.lower(), safe_query_param)
    else:
        # Query cũ (dự phòng)
        query = "SELECT id, title, description FROM user_tasks WHERE user_email = ? AND title LIKE ? AND is_completed = 0"
        params = (user_email.lower(), f"%{title_query}%")
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    
    cursor.execute(query, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks


def _find_reminders_by_text_db(text_query: str) -> List[dict]:
    """(MỚI) (SYNC) Chỉ TÌM (không xóa) các job trong Scheduler."""
    
    if not SCHEDULER:
        return []
        
    found = []
    try:
        jobs = SCHEDULER.get_jobs()
        for job in jobs:
            try:
                job_text = job.args[1]
                
                # --- 🚀 BẮT ĐẦU SỬA LỖI (Accent-insensitive) 🚀 ---
                # Chuyển cả hai về không dấu, chữ thường
                safe_query = unidecode.unidecode(text_query).lower()
                safe_job_text = unidecode.unidecode(job_text).lower()
                
                if safe_query in safe_job_text:
                # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
                    found.append({"id": job.id, "text": job_text})
            except (IndexError, TypeError):
                continue
    except Exception as e:
        print(f"❌ Lỗi _find_reminders_by_text_db: {e}")

    return found

def _find_files_by_name_db(vectorstore: Chroma, name_query: str) -> List[dict]:
    """
    (OPTIMIZATION V2 - NHANH HƠN 5-10 LẦN)
    Tìm file/image bằng cách:
    1. Lấy TẤT CẢ file từ Chroma (1 query duy nhất - NHANH)
    2. Lọc bằng Python (không gọi LLM - NHANH)
    3. Sắp xếp theo timestamp
    """
    try:
        user_email = cl.user_session.get("user_email", "unknown")
        
        # BƯỚC 1: Lấy tất cả file (1 query) - NHANH + FILTER theo user_id
        data = vectorstore._collection.get(
            where={
                "$and": [
                    {"user_id": user_email},
                    {"file_type": {"$ne": "text"}}
                ]
            },
            include=["metadatas"]  # Không cần documents để tiết kiệm băng thông
        )
        
        ids = data.get("ids", [])
        metadatas = data.get("metadatas", [])
        
        if not ids:
            print(f"[FileFinder OPTIMIZED] Không tìm thấy file nào trong DB")
            return []
        
        # BƯỚC 2: Chuẩn bị query (không dấu, lowercase, tách từ)
        safe_query_words = set(unidecode.unidecode(name_query).lower().split())
        if not safe_query_words:
            return []
        
        # BƯỚC 3: Lọc bằng Python (NHANH - không gọi LLM)
        found = []
        for doc_id, metadata in zip(ids, metadatas):
            if not metadata:
                continue
                
            content = metadata.get("original_content", "")
            if not content:
                continue
            
            # Parse nhanh bằng regex
            name_match = re.search(r"name=([^|]+)", content)
            note_match = re.search(r"note=([^|]+)", content)
            path_match = re.search(r"path=([^|]+)", content)
            
            if not path_match:
                continue
            
            file_name = name_match.group(1).strip() if name_match else ""
            user_note = note_match.group(1).strip() if note_match else ""
            
            # Gộp tên + ghi chú (không dấu, lowercase)
            searchable_text = unidecode.unidecode(f"{file_name} {user_note}").lower()
            searchable_words = set(searchable_text.split())
            
            # Kiểm tra: TẤT CẢ query words phải có trong (tên + ghi chú)
            if safe_query_words.issubset(searchable_words):
                file_path = path_match.group(1).strip()
                saved_name = os.path.basename(file_path)
                file_type_str = metadata.get("file_type", "file")
                ts_str = metadata.get("timestamp", "1970-01-01T00:00:00+00:00")
                
                type_tag = f"[{file_type_str.upper()}]"
                if file_type_str == "image":
                    type_tag = "[IMAGE]"
                
                found.append({
                    "doc_id": doc_id,
                    "file_path": file_path,
                    "saved_name": saved_name,
                    "original_name": file_name,
                    "note": user_note,
                    "type": type_tag,
                    "timestamp_str": ts_str
                })
        
        # BƯỚC 4: Sắp xếp (mới -> cũ)
        found_sorted = sorted(found, key=lambda x: x["timestamp_str"], reverse=True)
        
        # --- BƯỚC 5: LLM SMART FILTER (Lọc chính xác) ---
        if len(found_sorted) > 1:
            # Chỉ dùng LLM khi có nhiều hơn 1 kết quả
            llm = cl.user_session.get("llm_logic")
            if llm:
                try:
                    # Chuẩn bị candidates cho LLM filter
                    candidates_for_llm = [
                        {
                            "id": item["doc_id"],
                            "name": item["original_name"],
                            "note": item["note"]
                        }
                        for item in found_sorted
                    ]
                    
                    filtered_candidates = _llm_filter_for_selection(llm, name_query, candidates_for_llm)
                    
                    # Map kết quả LLM trả về với found_sorted
                    filtered_ids = {item["id"] for item in filtered_candidates}
                    found_sorted = [item for item in found_sorted if item["doc_id"] in filtered_ids]
                    
                    print(f"[LLM Filter Selection] Đã lọc -> còn {len(found_sorted)} (Query: '{name_query}')")
                except Exception as e:
                    print(f"⚠️ LLM Filter lỗi, dùng kết quả Python: {e}")
        
        print(f"[FileFinder OPTIMIZED] Đã lọc {len(ids)} -> còn {len(found_sorted)} (Query: '{name_query}')")
        return found_sorted
        
    except Exception as e:
        print(f"❌ Lỗi _find_files_by_name_db: {e}")
        import traceback
        traceback.print_exc()
        return []



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

# THAY ĐỔI: Hàm helper sanitize (giữ nguyên)
def _sanitize_user_id_for_path(user_email: str) -> str:
    """Biến email thành ID an toàn (dùng cho metadata)."""
    safe_name = re.sub(r"[@\.]", "_", user_email)
    return re.sub(r"[^a-zA-Z0-9_\-]", "", safe_name).lower()

# =========================================================
# ️ MỚI: Quản lý Checklist Công việc (Tasks)
def _llm_filter_for_deletion(
    llm: ChatOpenAI, 
    query: str, 
    candidates: List[dict] # List of {"id": str, "doc": str}
) -> List[dict]:
    """(MỚI) Dùng LLM (sync) để lọc lại kết quả vector search cho việc xóa."""
    
    if not candidates:
        return []
        
    # 1. Tạo danh sách ứng viên
    candidate_list_str = "\n".join([
        f"<item index='{i}'>{item['doc']}</item>" 
        for i, item in enumerate(candidates)
    ])
    
    # 2. Tạo prompt (Theo ý của bạn)
    prompt = f"""Bạn là một bộ lọc thông minh.

Yêu cầu xóa của người dùng (Query): "{query}"

Danh sách các ghi chú ứng viên (Context):
{candidate_list_str}

Nhiệm vụ của bạn:
1. So sánh Query với TỪNG item trong Context.
2. Chỉ trả về (chính xác, không thêm thắt) nội dung của các item NÀO THỰC SỰ KHỚP với Query (về ngữ nghĩa, không phân biệt dấu).
3. Nếu không có item nào khớp, trả về một chuỗi rỗng.
4. KHÔNG giải thích. Chỉ trả về nội dung khớp, mỗi cái trên một dòng.

Ví dụ 1:
Query: "mo trang web"
Context:
<item index='0'>mở trang web https://ocrm...</item>
<item index='1'>tôi thich an coc</item>

Output:
mở trang web https://ocrm...

Ví dụ 2:
Query: "an coc"
Context:
<item index='0'>mở trang web https://ocrm...</item>
<item index='1'>tôi thich an coc</item>

Output:
tôi thich an coc

Ví dụ 3:
Query: "ghi chu linh tinh"
Context:
<item index='0'>mở trang web https://ocrm...</item>
<item index='1'>tôi thich an coc</item>

Output:
(chuỗi rỗng)
"""
    
    try:
        # 3. Gọi LLM (sync)
        resp = llm.invoke(prompt)
        llm_output_text = resp.content.strip()
        
        if not llm_output_text:
            return []
            
        # 4. Lọc lại
        # Lấy các dòng mà LLM trả về
        llm_approved_docs = [line.strip() for line in llm_output_text.split('\n') if line.strip()]
        
        final_list = []
        for candidate in candidates:
            # Nếu nội dung của ứng viên có trong danh sách LLM duyệt -> giữ lại
            if candidate['doc'] in llm_approved_docs:
                final_list.append(candidate)
                
        print(f"[LLM Filter] Đã lọc {len(candidates)} -> còn {len(final_list)} (Query: '{query}')")
        return final_list
        
    except Exception as e:
        print(f"❌ Lỗi _llm_filter_for_deletion: {e}")
        # An toàn: trả về rỗng nếu LLM lỗi
        return []

# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 850)

def _llm_filter_for_selection(
    llm: ChatOpenAI,
    query: str,
    candidates: List[dict] # List of {"id": str, "name": str, "note": str, "metadata": dict}
) -> List[dict]:
    """(MỚI) Dùng LLM (sync) để lọc KẾT QUẢ TÌM KIẾM (cho file/ảnh)
    dựa trên query của user, giải quyết nhiễu (ví dụ: query '2024'
    khớp với 'note' của file '2025').
    """
    if not candidates:
        return []
        
    # 1. Tạo danh sách ứng viên (dùng ID làm key)
    candidate_list_str = "\n".join([
        f"<item id='{item['id']}'>Tên: {item['name']} | Ghi chú: {item['note']}</item>"
        for item in candidates
    ])
    
    # 2. Tạo prompt (Theo logic bạn yêu cầu)
    prompt = f"""Bạn là một bộ lọc thông minh (Smart Filter).
Nhiệm vụ của bạn là LỌC danh sách (Context) dựa trên Yêu cầu (Query).

Yêu cầu (Query): "{query}"

Danh sách ứng viên (Context):
{candidate_list_str}

QUY TẮC LỌC:
1. Đọc kỹ Query.
2. Chỉ giữ lại những item nào mà PHẦN TÊN (Name) khớp với Query.
3. BỎ QUA những item chỉ khớp ở PHẦN GHI CHÚ (Note).

VÍ DỤ RẤT QUAN TRỌNG:
Query: "xem file 2024"
Context:
<item id='abc'>Tên: file ns 2024 | Ghi chú: luu file 2024...</item>
<item id='xyz'>Tên: file ns 2025 | Ghi chú: luu file 2024...</item>

Output (Chỉ trả về ID):
abc

Query: "luu file"
Context:
<item id='abc'>Tên: file ns 2024 | Ghi chú: luu file 2024...</item>
<item id='xyz'>Tên: file ns 2025 | Ghi chú: luu file 2024...</item>

Output (Chỉ trả về ID):
abc
xyz

Query: "file ns 2025"
Context:
<item id='abc'>Tên: file ns 2024 | Ghi chú: luu file 2024...</item>
<item id='xyz'>Tên: file ns 2025 | Ghi chú: luu file 2024...</item>

Output (Chỉ trả về ID):
xyz

Output (Chỉ trả về các ID, mỗi ID một dòng. KHÔNG GIẢI THÍCH):
"""
    
    try:
        # 3. Gọi LLM (sync)
        resp = llm.invoke(prompt)
        llm_output_text = resp.content.strip()
        
        if not llm_output_text:
            return []
            
        # 4. Lọc lại
        llm_approved_ids = set([line.strip() for line in llm_output_text.split('\n') if line.strip()])
        
        final_list = []
        for candidate in candidates:
            if candidate['id'] in llm_approved_ids:
                final_list.append(candidate)
                
        print(f"[LLM Filter Selection] Đã lọc {len(candidates)} -> còn {len(final_list)} (Query: '{query}')")
        return final_list
        
    except Exception as e:
        print(f"❌ Lỗi _llm_filter_for_selection: {e}")
        # An toàn: trả về danh sách GỐC nếu LLM lỗi
        print("⚠️ [LLM Filter Selection] Lỗi, trả về danh sách gốc (chưa lọc).")
        return candidates
    
    
    
    
def _find_notes_for_deletion(
    vectorstore: Chroma, 
    llm: ChatOpenAI, 
    content_query: str
) -> List[dict]:
    """
    (SỬA TÊN) Nhiệm vụ: Chỉ TÌM (không xóa).
    B1: Vector Search (Tìm gần giống).
    B2: Lọc rác (Python).
    B3: Dùng LLM lọc thông minh.
    Trả về: List[dict] (ví dụ: [{"id": "abc", "doc": "..."}])
    """
    try:
        # --- BƯỚC 1: TÌM GẦN GIỐNG (VECTOR SEARCH) ---
        query_vector = embeddings.embed_query(content_query)
        results = vectorstore._collection.query(
            query_embeddings=[query_vector],
            n_results=20, # Lấy 20 ứng viên
            include=["documents"]
        )
        
        ids_to_process = results.get("ids", [[]])[0]
        docs_to_process = results.get("documents", [[]])[0]
        
        if not ids_to_process:
            return []
            
        # --- BƯỚC 2: LỌC BỎ RÁC BẰNG PYTHON (Lọc cơ bản) ---
        candidate_notes = []
        for doc_id, content in zip(ids_to_process, docs_to_process):
            if not content: continue
            if content.startswith("[FILE]") or \
               content.startswith("[IMAGE]") or \
               content.startswith("[REMINDER_") or \
               content.startswith("[ERROR_PROCESSING_FILE]") or \
               content.startswith("[FILE_UNSUPPORTED]") or \
               content.startswith("Trích từ tài liệu:") or \
               content.startswith("[WEB_LINK]") or \
               content.startswith("Link video YouTube đã lưu:") or \
               content.startswith("Link trang web đã lưu:") or \
               content.startswith("FACT:"):
                continue
            candidate_notes.append({"id": doc_id, "doc": content})

        if not candidate_notes:
            return [] # Không có ứng viên nào

        # --- BƯỚC 3: DÙNG LLM LỌC THÔNG MINH ---
        filtered_results = _llm_filter_for_deletion(
            llm, content_query, candidate_notes
        )
        
        if not filtered_results:
            return [] # LLM đã lọc hết

        # --- BƯỚC 4: TRẢ VỀ DANH SÁCH ỨNG VIÊN ---
        print(f"[NoteFinder] (LLM): Tìm thấy {len(filtered_results)} ghi chú cho: '{content_query}'")
        return filtered_results
        
    except Exception as e:
        print(f"❌ Lỗi _find_notes_for_deletion (LLM):")
        traceback.print_exc()
        return []
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
# (THAY THẾ HÀM NÀY - khoảng dòng 730)
def _get_tasks_from_db(
    user_email: str, 
    status: str = "uncompleted",
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None   
) -> List[dict]:
    """
    (SỬA LỖI V94 - SẮP XẾP THEO NGÀY TẠO)
    Lấy danh sách công việc.
    status: 'uncompleted', 'completed', 'all'
    """
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # (Bảng 'user_tasks' đã có 'created_at' (dòng 403))
    base_query = "SELECT id, title, description, due_date, recurrence_rule, is_completed, created_at FROM user_tasks WHERE user_email = ?"
    params = [user_email.lower()]
    
    if status == "uncompleted":
        base_query += " AND is_completed = 0"
    elif status == "completed":
        base_query += " AND is_completed = 1"
    
    if start_date:
        base_query += " AND due_date >= ?"
        params.append(start_date)
        
    if end_date:
        safe_end_date = end_date.replace(hour=23, minute=59, second=59)
        base_query += " AND due_date <= ?" 
        params.append(safe_end_date)
        
    # --- 🚀 SỬA LỖI V94 (SẮP XẾP THEO YÊU CẦU CỦA BẠN) 🚀 ---
    if status == "uncompleted":
        # CHƯA HOÀN THÀNH: Sắp xếp theo HẠN CHÓT (Cũ nhất lên đầu)
        base_query += " ORDER BY due_date ASC"
    else:
        # ĐÃ HOÀN THÀNH (hoặc ALL): Sắp xếp theo NGÀY TẠO (Mới nhất lên đầu)
        base_query += " ORDER BY created_at DESC"
    # --- 🚀 KẾT THÚC SỬA LỖI V94 🚀 ---
        
    cursor.execute(base_query, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def _get_task_status_db(task_id: int) -> bool:
    """(MỚI) (SYNC) Kiểm tra xem task đã hoàn thành chưa. 
    Trả về True = Hoàn thành, False = Chưa hoàn thành.
    """
    conn = None
    try:
        conn = _get_user_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT is_completed FROM user_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # row[0] là 0 (chưa hoàn thành) hoặc 1 (đã hoàn thành)
            return row[0] == 1 
            
        # Nếu không tìm thấy task (ví dụ: đã bị xóa),
        # coi như "hoàn thành" để dừng vòng lặp
        return True 
        
    except Exception as e:
        print(f"❌ Lỗi _get_task_status_db (ID: {task_id}): {e}")
        if conn: conn.close()
        return True # An toàn: Lỗi CSDL -> dừng vòng lặp
    
    
# (Dán hàm mới này vào khoảng dòng 472)
def _delete_task_db(user_email: str, vectorstore: Chroma, query: str) -> int:
    """(SYNC) Tìm và xóa task dựa trên query (ID hoặc nội dung)."""
    conn = _get_user_db_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    deleted_count = 0
    
    # 1. Tìm theo ID
    task_id_match = re.search(r"\b\d+\b", query)
    if task_id_match:
        task_id = int(task_id_match.group(0))
        # Xóa theo ID (sẽ tự hủy job)
        if _delete_task_db_by_id(task_id, user_email):
            deleted_count += 1

    # 2. Tìm theo Nội dung (chỉ nếu chưa xóa được gì)
    if deleted_count == 0:
        # Tương tự như _delete_task_by_title_db cũ
        title_query = query
        query_sql = "SELECT id FROM user_tasks WHERE user_email = ? AND title LIKE ? AND is_completed = 0"
        params = (user_email.lower(), f"%{title_query}%")
        
        cursor.execute(query_sql, params)
        tasks_to_delete = cursor.fetchall()
        
        for task in tasks_to_delete:
            if _delete_task_db_by_id(task['id'], user_email):
                deleted_count += 1
                
    conn.close()
    return deleted_count
def remove_job_by_id_or_content(scheduler: AsyncIOScheduler, vectorstore: Chroma, query: str) -> int:
    """(SYNC) Tìm và xóa job/reminder dựa trên ID hoặc nội dung."""
    if not SCHEDULER: return 0
    
    deleted_count = 0
    jobs_to_remove = []
    
    # 1. Tìm theo ID job
    try:
        if SCHEDULER.get_job(query.strip()):
            jobs_to_remove.append(SCHEDULER.get_job(query.strip()))
    except Exception:
        pass # ID không khớp

    # 2. Tìm theo nội dung nhắc
    query_low = query.lower().strip()
    for job in SCHEDULER.get_jobs():
        if job.id and job.id.startswith("reminder-"):
            try:
                job_text = job.args[1]
                if query_low in job_text.lower():
                    jobs_to_remove.append(job)
            except (IndexError, TypeError):
                continue
    
    # 3. Xóa các job và dọn dẹp vectorstore
    job_ids_removed = set()
    for job in jobs_to_remove:
        if job.id not in job_ids_removed:
            try:
                # 3a. Hủy khỏi Scheduler
                SCHEDULER.remove_job(job.id)
                job_ids_removed.add(job.id)
                deleted_count += 1
                
                # 3b. Xóa khỏi Vectorstore (dựa trên job_id)
                regex_pattern = f"job_id={job.id}"
                
                # (SỬA LỖI: Cần dùng query để tìm doc_id trong vectorstore)
                def _get_doc_ids_sync():
                     return vectorstore._collection.get(where_document={"$contains": regex_pattern})

                existing_docs = _get_doc_ids_sync()
                ids_to_delete = existing_docs.get("ids", [])
                
                if ids_to_delete:
                    vectorstore._collection.delete(ids=ids_to_delete)
                    print(f"[RemDB] Đã dọn dẹp vectorstore cho job: {job.id}")
            except Exception as e:
                print(f"[RemDB] Lỗi khi xóa job {job.id}: {e}")
                
    return deleted_count

# --- HÀM CŨ ĐÃ SỬA ---
def _delete_task_db_by_id(task_id: int, user_email: str) -> bool:
    """(SYNC) Xóa một công việc (và hủy lịch job) khỏi CSDL. (Dùng cho hàm mới)."""
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
# (THAY THẾ HÀM NÀY - khoảng dòng 778)
async def ui_show_uncompleted_tasks(
    start_date: Optional[datetime] = None, # <-- MỚI
    end_date: Optional[datetime] = None,   # <-- MỚI
    filter_title: str = ""                 # <-- MỚI
):
    """(SỬA LỖI) Hiển thị công việc (lọc theo ngày/tiêu đề)."""
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        await cl.Message(content="❌ Lỗi: Không tìm thấy user_id_str.").send()
        return

    # Sửa: Gọi hàm CSDL với filters
    tasks = await asyncio.to_thread(
        _get_tasks_from_db, 
        user_id_str, 
        status="uncompleted",
        start_date=start_date,
        end_date=end_date
    )
    
    # (MỚI) Xây dựng tiêu đề
    if filter_title:
        title = f"📝 **{len(tasks)} công việc chưa hoàn thành (cho '{filter_title}'):**"
    else:
         title = f"📝 **Danh sách {len(tasks)} công việc chưa hoàn thành:**"

    if not tasks:
        if filter_title:
            await cl.Message(content=f"🎉 Bạn không có công việc nào chưa hoàn thành (cho '{filter_title}')!").send()
        else:
            await cl.Message(content="🎉 Bạn không có công việc nào chưa hoàn thành!").send()
        return

    await cl.Message(content=title).send() # <-- SỬA: Dùng title
    
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
        # --- 🚀 BẮT ĐẦU SỬA LỖI (ĐỔI TÊN HÀM) 🚀 ---
        # Gọi hàm xóa theo ID (đã có ở dòng 769)
        ok = await asyncio.to_thread(_delete_task_db_by_id, task_id, user_id_str)
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
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




# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 865)
def _push_task_notification(
    internal_session_id: str, 
    task_title: str, 
    task_id: int, 
    repeat_min: Optional[int] # <-- NHẬN THAM SỐ MỚI
):
    """
    (SỬA LỖI V90) (SYNC) 
    Hàm này được Scheduler gọi để push thông báo Task.
    1. Kiểm tra CSDL xem task_id đã hoàn thành chưa.
    2. Nếu CHƯA:
       a. Push thông báo.
       b. Nếu có repeat_min, lên lịch GỌI LẠI CHÍNH HÀM NÀY 
          sau 'repeat_min' phút.
    3. Nếu RỒI: Dừng vòng lặp (không làm gì cả).
    """
    print(f"[TaskPush] Đang kiểm tra Task ID: {task_id} ({task_title})")
    
    # 1. (MỚI) Kiểm tra CSDL
    # (Hàm _get_task_status_db đã được thêm ở Bước 1)
    is_completed = _get_task_status_db(task_id)
    
    if is_completed:
        print(f"[TaskPush] Task ID: {task_id} đã hoàn thành. Dừng vòng lặp nhắc lại.")
        return # Dừng
        
    # 2. (CHƯA HOÀN THÀNH) Push thông báo
    print(f"[TaskPush] Task ID: {task_id} CHƯA hoàn thành. Đang Push...")
    _do_push(internal_session_id, f"Đến hạn công việc: {task_title}")
    
    # 3. (MỚI) Lên lịch kiểm tra lặp lại (nếu có)
    if repeat_min and repeat_min > 0:
        if not SCHEDULER:
            print("[TaskPush] Lỗi: Không tìm thấy SCHEDULER để lặp lại.")
            return
            
        try:
            next_run_dt = datetime.now(VN_TZ) + timedelta(minutes=repeat_min)
            new_job_id = f"taskpush-check-{task_id}-{uuid.uuid4().hex[:6]}"
            
            print(f"[TaskPush] Đã lên lịch kiểm tra lặp lại cho Task ID: {task_id} sau {repeat_min} phút (Job: {new_job_id})")
            
            # Lên lịch gọi lại CHÍNH NÓ (tạo vòng lặp)
            SCHEDULER.add_job(
                _push_task_notification, 
                trigger=DateTrigger(run_date=next_run_dt, timezone=VN_TZ),
                id=new_job_id,
                # Truyền lại tất cả tham số
                args=[internal_session_id, task_title, task_id, repeat_min], 
                replace_existing=False,
                misfire_grace_time=60
            )
        except Exception as e_sched:
            print(f"❌ Lỗi khi lên lịch lặp lại cho Task {task_id}: {e_sched}")
# =========================================================
# =========================================================
# 📇 MỚI: Quản lý Từ điển Fact (Fact Dictionary)
# =========================================================
# (DÁN HÀM NÀY VÀO KHOẢNG DÒNG 1078, 
#  NGAY TRƯỚC HÀM get_user_fact_dict_path)

def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')


# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1085)
def load_user_fact_dict(user_id_str: str) -> dict:
    """Tải từ điển fact của user từ file JSON.
    (SỬA LỖI: Di dời file hỏng để tránh bị ghi đè mất dữ liệu).
    """
    path = get_user_fact_dict_path(user_id_str)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi đọc fact dict {user_id_str}: {e}")
            
            # --- 🚀 BẮT ĐẦU SỬA LỖI (CHỐNG MẤT DỮ LIỆU) 🚀 ---
            # Di dời file hỏng để tránh bị ghi đè mất
            try:
                # (Chúng ta đã dời hàm _timestamp lên trước)
                bad_file_path = f"{path}.{_timestamp()}.corrupted"
                os.rename(path, bad_file_path)
                print(f"✅ Đã di dời file hỏng sang: {bad_file_path}")
            except Exception as e_rename:
                print(f"❌ Không thể di dời file hỏng: {e_rename}")
            # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            
    return {} # Trả về dict rỗng nếu lỗi hoặc không tồn tại

def save_user_fact_dict(user_id_str: str, data: dict):
    """Lưu từ điển fact của user vào file JSON."""
    path = get_user_fact_dict_path(user_id_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi lưu fact dict {user_id_str}: {e}")
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 1106)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 1106)
async def call_llm_to_classify(
    llm: ChatOpenAI, 
    question: str, 
    fact_map: dict # <-- SỬA: Nhận toàn bộ fact_map
) -> Tuple[str, str, str]:
    """
    (SỬA LỖI V88 - THEO YÊU CẦU CỦA USER)
    1. Nhận toàn bộ 'fact_map' làm context.
    2. Yêu cầu GPT ƯU TIÊN TÁI SỬ DỤNG 'Key'/'Label' đã có 
       thay vì "tạo" (invent) key mới.
    """
    
    # --- 🚀 BƯỚC 1: XÂY DỰNG CONTEXT TỪ FACT_MAP 🚀 ---
    existing_facts_str = "Context (Fact) hiện tại:\n(Không có)"
    try:
        if fact_map and isinstance(fact_map, dict):
            existing_facts_list = []
            seen_keys = set()
            
            # Chỉ lấy các key/label duy nhất
            for data in fact_map.values():
                if isinstance(data, dict):
                    key = data.get("key")
                    label = data.get("label")
                    if key and key not in seen_keys:
                        existing_facts_list.append(f"- Key: {key} (Label: {label})")
                        seen_keys.add(key)
                elif isinstance(data, str) and data not in seen_keys:
                    # Fallback cho cache cũ (chỉ lưu string)
                    label = data.replace("_", " ").title()
                    existing_facts_list.append(f"- Key: {data} (Label: {label})")
                    seen_keys.add(data)
            
            if existing_facts_list:
                existing_facts_str = "Context (Fact) hiện tại:\n" + "\n".join(sorted(existing_facts_list))
    except Exception as e_parse:
        print(f"⚠️ Lỗi parse fact_map (V88): {e_parse}")
        existing_facts_str = "Context (Fact) hiện tại:\n(Lỗi parse)"
        
    # --- 🚀 BƯỚC 2: TẠO PROMPT V88 (THEO Ý BẠN) 🚀 ---
    prompt_text = f"""
    Bạn là một chuyên gia Phân tích Query (Classifier).
    
    Query: "{question}"

    {existing_facts_str}

    NHIỆM VỤ:
    1. Đọc kỹ Query và Context (Fact) hiện tại.
    2. ƯU TIÊN 1 (Tái sử dụng): Nếu Query có vẻ thuộc về một "Fact" đã có trong Context, hãy TÁI SỬ DỤNG 'Key' và 'Label' của nó.
    3. ƯU TIÊN 2 (Tạo mới): Nếu Query không khớp với Context, hãy TẠO MỚI một 'Key' và 'Label' hợp lý.
    4. Trích xuất 'core_query_term' (từ khóa tìm kiếm chính, đã loại bỏ hành động và danh mục).

    QUY TẮC TRẢ VỀ:
    - Định dạng: `fact_key | Label Tiếng Việt | core_query_term`
    - KHÔNG GIẢI THÍCH.

    VÍ DỤ TÁI SỬ DỤNG (RẤT QUAN TRỌNG):
    Query: "xem ảnh phan thiet"
    Context (Fact) hiện tại:
    - Key: du_lich (Label: Du Lịch)
    - Key: cong_viec (Label: Công Việc)
    (GPT sẽ thấy 'phan thiet' liên quan đến 'du_lich')
    Output: du_lich | Du Lịch | anh phan thiet

    VÍ DỤ TẠO MỚI:
    Query: "pass server của tôi"
    Context (Fact) hiện tại:
    - Key: du_lich (Label: Du Lịch)
    (GPT thấy không liên quan)
    Output: server_thong_tin | Server Thông Tin | pass server
    
    VÍ DỤ LỌC (CHUNG):
    Query: "xem file trong cong viec"
    Context (Fact) hiện tại:
    - Key: du_lich (Label: Du Lịch)
    - Key: cong_viec (Label: Công Việc)
    (GPT thấy 'cong viec' khớp Context)
    Output: cong_viec | Công Việc | ALL

    Output (key | label | core_query_term):
    """
    # --- 🚀 KẾT THÚC PROMPT V88 🚀 ---
    
    try:
        resp = await llm.ainvoke(prompt_text)
        raw_output = resp.content.strip().strip("`'\"")
        
        fact_key = "general"
        fact_label = "General"
        core_query_term = question
        
        if "|" in raw_output:
            parts = raw_output.split("|")
            
            if len(parts) >= 3:
                key_part = parts[0].strip().replace(" ", "_")
                label_part = parts[1].strip()
                name_part = parts[2].strip()
                
                if key_part: fact_key = re.sub(r"[^a-z0-9_]", "", key_part.lower())
                if label_part: fact_label = label_part
                if name_part: core_query_term = name_part
                
            elif len(parts) == 2:
                key_part = parts[0].strip().replace(" ", "_")
                label_part = parts[1].strip()
                
                if key_part: fact_key = re.sub(r"[^a-z0-9_]", "", key_part.lower())
                if label_part: fact_label = label_part
                core_query_term = "ALL" 
        else:
            key_part = raw_output.replace(" ", "_")
            fact_key = re.sub(r"[^a-z0-9_]", "", key_part.lower())
            fact_label = fact_key
            core_query_term = "ALL" 
            
        if not fact_key: fact_key = "general"
        if not fact_label: fact_label = "General"
        if not core_query_term: core_query_term = question
        
        # (SỬA LỖI V88)
        print(f"[call_llm_to_classify] (Prompt V88) Query: '{question}' -> Key: '{fact_key}' | Label: '{fact_label}' | CoreQuery: '{core_query_term}'")
        return fact_key, fact_label, core_query_term
        
    except Exception as e:
        # (SỬA LỖI V88)
        print(f"❌ Lỗi call_llm_to_classify (V88): {e}")
        return "general", "General", question
    
    
    
    
# 🧠 LangChain + OpenAI + Vector (Đã sửa đổi)
# =========================================================
# Embeddings (toàn cục, vì nó không có state)
embeddings = OpenAIEmbeddings(
    api_key=OPENAI_API_KEY,
    model="text-embedding-3-small"
)
def get_shared_vectorstore_retriever() -> Tuple[Chroma, Any]:
    """
    (MỚI - 1 DB CHUNG)
    Khởi tạo Vectorstore CHUNG cho TẤT CẢ user.
    Filter theo metadata['user_id'] khi query.
    """
    global _SHARED_VECTORSTORE, _SHARED_RETRIEVER, embeddings
    
    # Nếu đã khởi tạo rồi -> trả về cache
    if _SHARED_VECTORSTORE is not None and _SHARED_RETRIEVER is not None:
        return _SHARED_VECTORSTORE, _SHARED_RETRIEVER
    
    if embeddings is None:
        raise ValueError("Lỗi: Embeddings chưa được khởi tạo (OPENAI_API_KEY có thể bị thiếu).")
    
    # Khởi tạo 1 lần duy nhất
    _SHARED_VECTORSTORE = Chroma(
        persist_directory=SHARED_VECTOR_DB_DIR,
        embedding_function=embeddings,
        collection_name="shared_memory"  # Collection chung
    )
    
    # Retriever không filter (sẽ filter sau khi query)
    _SHARED_RETRIEVER = _SHARED_VECTORSTORE.as_retriever(search_kwargs={"k": 100})
    
    print(f"✅ Shared VectorStore đã sẵn sàng tại {SHARED_VECTOR_DB_DIR}")
    return _SHARED_VECTORSTORE, _SHARED_RETRIEVER


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
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1210)
def _save_image_and_note(
    vectorstore: Chroma,
    src_path: str, 
    user_text: str, 
    original_name: str,
    fact_key: str = "general",
    fact_label: str = "General" 
) -> Tuple[str, str]:
    """
    (SỬA LỖI V94 - THÊM TIMESTAMP)
    """
    name = original_name or os.path.basename(src_path) or f"image-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or '.jpg'}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name) 
    shutil.copyfile(src_path, dst)
    
    original_content_str = f"[IMAGE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    vector_text_str = f"{fact_label} | {name} | {user_text.strip() or '(no note)'}"
    
    user_email = cl.user_session.get("user_email", "unknown")
    
    metadata = {
        "user_id": user_email,
        "fact_key": fact_key, 
        "fact_label": fact_label, 
        "file_type": "image",
        "original_content": original_content_str, 
        "entry_type": "file_master",
        "timestamp": datetime.now(VN_TZ).isoformat() # <-- 🚀 SỬA LỖI V94
    }
    
    vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
    
    return dst, name

# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1700)
def _save_file_and_note(
    vectorstore: Chroma,
    src_path: str, 
    original_name: Optional[str], 
    user_text: str,
    fact_key: str = "general",
    fact_label: str = "General", 
    file_type: str = "file" 
) -> Tuple[str, str]:
    """
    (SỬA LỖI V94 - THÊM TIMESTAMP)
    (SỬA LỖI V100 - FIX EXTENSION)
    """
    name = original_name or os.path.basename(src_path) or f"file-{uuid.uuid4().hex[:6]}"
    
    # V100: Lấy extension từ name HOẶC src_path (fallback)
    ext = os.path.splitext(name)[1]
    if not ext:  # Nếu name không có ext, lấy từ src_path
        ext = os.path.splitext(src_path)[1]
    
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name)
    shutil.copyfile(src_path, dst)
    
    original_content_str = f"[FILE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    vector_text_str = f"{fact_label} | {name} | {user_text.strip() or '(no note)'}"
    
    user_email = cl.user_session.get("user_email", "unknown")
    
    metadata = {
        "user_id": user_email,
        "fact_key": fact_key, 
        "fact_label": fact_label, 
        "file_type": file_type,
        "original_content": original_content_str, 
        "entry_type": "file_master",
        "timestamp": datetime.now(VN_TZ).isoformat() # <-- 🚀 SỬA LỖI V94
    }
    
    vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
    
    return dst, name
def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Tạo một text splitter tiêu chuẩn."""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )

# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1270)
def _load_and_process_document(
    vectorstore: Chroma,
    src_path: str, 
    original_name: str, 
    mime_type: str, 
    user_note: str,
    fact_key: str = "general",
    fact_label: str = "General" 
) -> Tuple[int, str]:
    """
    (SỬA LỖI V94 - THÊM TIMESTAMP)
    1. (V94) Thêm timestamp vào CHUNKS.
    2. (V94) Thêm timestamp vào FILE_UNSUPPORTED/ERROR.
    """
    
    simple_file_type = _get_simple_file_type(mime_type, src_path)
    metadata_note = f"Trích từ tài liệu: {original_name} | Ghi chú của người dùng: {user_note}"
    text_content = ""
    
    # (SỬA LỖI V94) Lấy timestamp 1 lần và user_email
    current_timestamp_iso = datetime.now(VN_TZ).isoformat()
    user_email = cl.user_session.get("user_email", "unknown")

    try:
        # 1. Đọc nội dung (logic không đổi)
        if "excel" in mime_type or src_path.endswith((".xlsx", ".xls")):
            df_dict = pd.read_excel(src_path, sheet_name=None)
            all_text = []
            for sheet_name, df in df_dict.items():
                md_table = df.to_markdown(index=False) 
                all_text.append(f"--- Sheet: {sheet_name} ---\n{md_table}")
            text_content = "\n\n".join(all_text)
        elif "pdf" in mime_type:
            reader = pypdf.PdfReader(src_path)
            all_text = [page.extract_text() or "" for page in reader.pages]
            text_content = "\n".join(all_text)
        elif "wordprocessingml" in mime_type or src_path.endswith(".docx"):
            doc = docx.Document(src_path)
            all_text = [p.text for p in doc.paragraphs]
            text_content = "\n".join(all_text)
        elif "text" in mime_type or src_path.endswith((".txt", ".md", ".py", ".js")):
            with open(src_path, "r", encoding="utf-8") as f:
                text_content = f.read()
        else:
            # --- (FILE KHÔNG HỖ TRỢ) ---
            original_content_str = f"[FILE_UNSUPPORTED] path={src_path} | name={original_name} | note={user_note}"
            vector_text_str = f"{fact_label} | {original_name} | {user_note} | File không hỗ trợ"
            metadata = {
                "user_id": user_email,
                "fact_key": fact_key, 
                "fact_label": fact_label, 
                "file_type": simple_file_type,
                "original_content": original_content_str,
                "entry_type": "file_master",
                "timestamp": current_timestamp_iso # <-- 🚀 SỬA LỖI V94
            }
            vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
            
            # (Hàm _save_file_and_note đã được sửa V94)
            _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key, fact_label, simple_file_type) 
            return 0, original_name
            
        if not text_content.strip():
            raise ValueError("File rỗng hoặc không thể trích xuất nội dung.")

        # 2. Cắt nhỏ (Chunking) (không đổi)
        text_splitter = _get_text_splitter()
        chunks = text_splitter.split_text(text_content)
        chunks_with_metadata = [
            f"{metadata_note}\n\n[NỘI DUNG CHUNK]:\n{chunk}"
            for chunk in chunks
        ]

        # --- (LƯU CHUNKS) ---
        chunk_metadatas = [{
            "user_id": user_email,
            "file_type": simple_file_type, 
            "fact_label": fact_label, 
            "fact_key": fact_key,
            "entry_type": "file_chunk",
            "timestamp": current_timestamp_iso # <-- 🚀 SỬA LỖI V94
        } for _ in chunks_with_metadata] 
        
        vectorstore.add_texts(
            texts=chunks_with_metadata, 
            metadatas=chunk_metadatas
        )
        # --- KẾT THÚC LƯU CHUNKS ---
        
        # 5. Lưu bản ghi [FILE] (Hàm này đã được sửa V94)
        _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key, fact_label, simple_file_type)
        
        return len(chunks_with_metadata), original_name

    except Exception as e:
        print(f"[ERROR] _load_and_process_document failed: {e}")
        
        # --- (LƯU LỖI) ---
        original_content_str = f"[ERROR_PROCESSING_FILE] name={original_name} | note={user_note} | error={e}"
        vector_text_str = f"{fact_label} | {original_name} | {user_note} | Lỗi xử lý file"
        metadata = {
            "user_id": user_email,
            "fact_key": fact_key, 
            "fact_label": fact_label, 
            "file_type": simple_file_type,
            "original_content": original_content_str,
            "entry_type": "file_master",
            "timestamp": current_timestamp_iso # <-- 🚀 SỬA LỖI V94
        }
        vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
        # --- KẾT THÚC LƯU LỖI ---
        
        raise
# =========================================================
# 🧩 Tiện ích xem bộ nhớ (Đã sửa đổi)
# =========================================================
def dump_all_memory_texts(vectorstore: Chroma) -> str: # <-- SỬA
    """SỬA ĐỔI: Nhận vectorstore của user."""
    try:
        user_email = cl.user_session.get("user_email", "unknown")
        raw = vectorstore._collection.get(
            where={"user_id": user_email},
            include=["documents"]
        )
        docs = raw.get("documents", []) or []
        if not docs:
            return "📭 Bộ nhớ đang trống. Chưa lưu gì cả."
        return "\n".join([f"{i+1}. {d}" for i, d in enumerate(docs)])
    except Exception as e:
        return f"⚠️ Không đọc được bộ nhớ: {e}"

# ==================== PATCH 5: TỐI ƯU HÓA HÀM LIST_ACTIVE_FILES ====================
# THAY THẾ hàm list_active_files (khoảng dòng 2132)

def list_active_files(vectorstore: Chroma) -> list[dict]:
    """
    (OPTIMIZATION V2)
    Quét ChromaDB lấy file/ảnh (NHANH - chỉ 1 query).
    """
    out = []
    try:
        user_email = cl.user_session.get("user_email", "unknown")
        
        # OPTIMIZATION: Chỉ lấy metadatas (không cần documents) + FILTER theo user_id
        data = vectorstore._collection.get(
            where={
                "$and": [
                    {"user_id": user_email},
                    {"file_type": {"$ne": "text"}}
                ]
            },
            include=["metadatas"]  # Không cần documents
        )
        
        ids = data.get("ids", [])
        metadatas = data.get("metadatas", [])
        
        for doc_id, metadata in zip(ids, metadatas):
            if not metadata:
                continue
            
            content = metadata.get("original_content")
            if not content:
                continue

            # Parse nhanh
            path_match = re.search(r"path=([^|]+)", content)
            name_match = re.search(r"name=([^|]+)", content)
            note_match = re.search(r"note=([^|]+)", content)

            if not path_match:
                continue

            file_path = path_match.group(1).strip()
            file_name = name_match.group(1).strip() if name_match else "unknown"
            user_note = note_match.group(1).strip() if note_match else "(không có)"
            
            saved_name = os.path.basename(file_path)
            file_type_str = metadata.get("file_type", "file")
            
            type_tag = f"[{file_type_str.upper()}]"
            if file_type_str == "image":
                type_tag = "[IMAGE]"
            elif file_type_str == "text":
                continue
            
            ts_str = metadata.get("timestamp", "1970-01-01T00:00:00+00:00")
            
            out.append({
                "doc_id": doc_id,
                "file_path": file_path,
                "saved_name": saved_name,
                "original_name": file_name,
                "note": user_note,
                "type": type_tag,
                "timestamp_str": ts_str
            })
            
    except Exception as e:
        print(f"[ERROR] Lỗi list_active_files: {e}")
        import traceback
        traceback.print_exc()
        
    # Sắp xếp theo timestamp (mới nhất lên đầu)
    return sorted(out, key=lambda x: x["timestamp_str"], reverse=True)



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
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 900)
async def ui_show_all_memory():
    """(SỬA LỖI V94 - SẮP XẾP THEO TIMESTAMP)
    Hiển thị tất cả ghi chú (trừ file/image) 
    với nút xóa, MỚI NHẤT LÊN ĐẦU.
    """
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
    
    # Phải chạy sync
    def _get_docs_sync():
        return vectorstore._collection.get(
            where={"file_type": "text"}, # <-- (V94) Chỉ lấy text
            include=["documents", "metadatas"]
        )
    
    raw_data = await asyncio.to_thread(_get_docs_sync)
    
    ids = raw_data.get("ids", [])
    docs = raw_data.get("documents", [])
    metadatas = raw_data.get("metadatas", []) # (V94) Lấy metadatas
    
    if not docs:
        await cl.Message(content="📭 Bộ nhớ đang trống. Chưa lưu gì cả.").send()
        return

    notes_found = 0
    await cl.Message(content="📝 **Các ghi chú đã lưu (Văn bản - Mới nhất lên đầu):**").send()
    
    # --- 🚀 SỬA LỖI V94 (SẮP XẾP) 🚀 ---
    # (Dùng helper V94 đã tạo ở Bước 1)
    sorted_results = _helper_sort_results_by_timestamp(ids, docs, metadatas)
    
    for doc_id, content, metadata in sorted_results:
    # --- 🚀 KẾT THÚC SỬA LỖI V94 🚀 ---
    
        if not content: continue
        
        # (Bộ lọc này giữ nguyên, mặc dù 'where' đã lọc)
        if content.startswith(("[FILE]", "[IMAGE]", "[REMINDER_", 
           "[ERROR_PROCESSING_FILE]", "[FILE_UNSUPPORTED]", 
           "Trích từ tài liệu:", "FACT:")):
            continue
        
        notes_found += 1
        
        # (Phần UI (Popup) giữ nguyên)
        msg = cl.Message(content="") 
        actions = [
            cl.Action(
                name="delete_note", 
                payload={"doc_id": doc_id, "message_id": msg.id},
                label="🗑️ Xóa"
            )
        ]
        
        if len(content) > 150 or "\n" in content:
            summary = "• " + (content.split('\n', 1)[0] or content).strip()[:150] + "..."
            msg.content = summary
            actions.append(
                cl.Action(
                    name="show_note_detail", 
                    payload={"doc_id": doc_id},
                    label="📄 Xem chi tiết"
                )
            )
        else:
            msg.content = f"• {content}"
        
        msg.actions = actions
        await msg.send()

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
    
# (Dán khối code này vào khoảng dòng 3700)

def _get_current_month_dates():
    """Helper: Lấy ngày đầu và ngày cuối của tháng hiện tại."""
    today = datetime.now(VN_TZ).date()
    # Ngày đầu tháng
    first_day = today.replace(day=1)
    # Ngày cuối tháng
    _, last_day_num = calendar.monthrange(today.year, today.month)
    last_day = today.replace(day=last_day_num)
    
    return first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")

class ChartDashboardSchema(BaseModel):
    query: str = Field(..., description="Câu hỏi của người dùng về dashboard, ví dụ: 'phân tích dashboard', 'tóm tắt doanh số tháng này'")

@tool("goi_chart_dashboard", args_schema=ChartDashboardSchema)
async def goi_chart_dashboard(query: str) -> str:
    """
    (SỬA LỖI) Lấy dữ liệu từ API Chart Dashboard (dùng URL hardcoded),
    phân tích bằng LLM và trả về tóm tắt.
    """
    llm = cl.user_session.get("llm_logic")
    if not llm: return "❌ Lỗi: Không tìm thấy llm_logic."

    try:
        # --- 🚀 BẮT ĐẦU SỬA LỖI (DÙNG API HARDCODED) 🚀 ---
        # 1. Kiểm tra xem URL đã được khai báo chưa
        if not CHART_API_URL:
            return "❌ Lỗi: Biến CHART_API_URL chưa được khai báo (khoảng dòng 111)."
            
        url = CHART_API_URL # <-- SỬA: Dùng URL đã khai báo
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---

        # 2. Lấy ngày
        from_date, to_date = _get_current_month_dates()
        
        # 3. Chuẩn bị gọi API
        headers = {"Authorization": f"token {PUSH_API_TOKEN}"}
        params = {"from_date": from_date, "to_date": to_date}

        print(f"📞 [ChartDashboard] Đang gọi API: {url} với params: {params}")

        # 4. Gọi API (Phải chạy sync trong thread)
        def _call_api_sync():
            resp = PUSH_SESSION.get(
                url,
                headers=headers,
                params=params, 
                timeout=(3.05, PUSH_TIMEOUT),
                verify=PUSH_VERIFY_TLS,
            )
            if 200 <= resp.status_code < 300:
                return resp.json()
            else:
                return {"error": f"API Error {resp.status_code}", "details": resp.text[:300]}
        
        api_data = await asyncio.to_thread(_call_api_sync)
        
        # 5. Chuyển data thành JSON string
        data_str = json.dumps(api_data, indent=2, ensure_ascii=False)

        # 6. Tạo Prompt phân tích
        prompt = f"""Bạn là một trợ lý phân tích dữ liệu kinh doanh cao cấp.
        Dưới đây là dữ liệu báo cáo thô (dạng JSON) từ API (từ {from_date} đến {to_date}):
        
        {data_str}

        Câu hỏi/Yêu cầu của người dùng: "{query}"

        Nhiệm vụ của bạn là phân tích dữ liệu JSON trên và trả về một bản tóm tắt/phân tích ngắn gọn.
        (Nếu dữ liệu trả về có 'error', hãy báo lỗi đó cho người dùng).
        """

        # 7. Gọi LLM để phân tích
        resp_llm = await llm.ainvoke(prompt)
        analysis = resp_llm.content.strip()
        
        return f"📊 **Phân tích Dashboard (từ {from_date} đến {to_date}):**\n\n{analysis}"

    except Exception as e:
        return f"❌ Lỗi khi phân tích dashboard: {e}"
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
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI (THÊM BỘ LỌC NÀY) 🚀 ---
        # Bỏ qua các job hệ thống (sync) và job của checklist (taskpush)
        if jid.startswith("sync_users_job") or \
           jid.startswith("taskpush-") or \
           jid.startswith("temp-"):
            continue
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            
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
# (DÁN 2 HÀM HELPER MỚI NÀY VÀO - KHOẢNG DÒNG 1140)

def _get_start_of_day(dt: datetime) -> datetime:
    """Helper: Lấy 00:00:00 của một ngày (trong VN_TZ)."""
    return VN_TZ.localize(datetime(dt.year, dt.month, dt.day, 0, 0, 0))

def _get_end_of_day(dt: datetime) -> datetime:
    """Helper: Lấy 23:59:59 của một ngày (trong VN_TZ)."""
    return VN_TZ.localize(datetime(dt.year, dt.month, dt.day, 23, 59, 59))
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
# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 1200)

def _get_simple_file_type(mime_type: str, path: str = "") -> str:
    """(MỚI) Helper: Chuyển mime_type/path thành 1 key đơn giản."""
    mime = (mime_type or "").lower()
    ext = (path or "").lower()
    
    if "image" in mime or ext.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "image"
    if "pdf" in mime or ext.endswith(".pdf"):
        return "pdf"
    if "excel" in mime or "spreadsheet" in mime or ext.endswith((".xlsx", ".xls")):
        return "excel"
    if "word" in mime or "document" in mime or ext.endswith((".docx", ".doc")):
        return "word"
    if "text" in mime or ext.endswith((".txt", ".md", ".py", ".js", ".json")):
        return "text"
    return "file" # Chung chung
# --- Helper: Logic lõi của Scheduler (Sync) ---

def _cancel_escalation(user_id_str: str): # <-- SỬA: Nhận user_id_str
    """
    (SỬA LẠI) Chỉ dọn dẹp bộ nhớ. 
    Lệnh 'remove_job' sẽ được _tick_job_sync xử lý.
    """
    st = ACTIVE_ESCALATIONS.pop(user_id_str, None) # <-- SỬA: Dùng user_id_str
    if st:
        print(f"[Escalation] Đã dọn dẹp in-memory cho {user_id_str}")
        
def _tick_job_sync(user_id_str, text, repeat_job_id): # <-- SỬA: Nhận user_id_str
    """
    (SỬA LẠI) Hàm sync để APScheduler gọi (cho escalation).
    """
    try:
        st = ACTIVE_ESCALATIONS.get(user_id_str) # <-- SỬA: Dùng user_id_str
        if not st or st.get("acked"):
            try:
                if SCHEDULER:
                    SCHEDULER.remove_job(repeat_job_id)
                print(f"[Escalation] Tick: Job {repeat_job_id} đã ack/mồ côi. ĐANG XÓA.")
            except Exception as e:
                print(f"[Escalation] Info: Job {repeat_job_id} đã bị xóa (lỗi: {e}).")
            ACTIVE_ESCALATIONS.pop(user_id_str, None) # <-- SỬA: Dùng user_id_str
            return
            
        print(f"[Escalation] Tick: Gửi nhắc (sync) cho {user_id_str}")
        _do_push(user_id_str, text) # <-- SỬA: Dùng user_id_str
        
    except Exception as e:
        print(f"[ERROR] _tick_job_sync crashed: {e}")

def _first_fire_escalation_job(user_id_str, text, every_sec): # <-- SỬA: Nhận user_id_str
    """
    Hàm (sync) được gọi cho LẦN ĐẦU TIÊN của 1 lịch leo thang.
    """
    try:
        print(f"[Escalation] First fire (sync) for {user_id_str} at {datetime.now(VN_TZ)}")
        _do_push(user_id_str, text) # <-- SỬA: Dùng user_id_str
        _schedule_escalation_after_first_fire(user_id_str, text, every_sec) # <-- SỬA
    except Exception as e:
        print(f"[ERROR] _first_fire_escalation_job crashed: {e}")

def _schedule_escalation_after_first_fire(user_id_str: str, noti_text: str, every_sec: int): # <-- SỬA
    """(SỬA LỖI) Lên lịch lặp lại (escalation) bằng hàm sync-safe."""
    repeat_job_id = f"repeat-{user_id_str}-{uuid.uuid4().hex[:6]}" # <-- SỬA
    ACTIVE_ESCALATIONS[user_id_str] = {"repeat_job_id": repeat_job_id, "acked": False} # <-- SỬA
    trigger = IntervalTrigger(seconds=every_sec, timezone=VN_TZ)
    if SCHEDULER:
        SCHEDULER.add_job(
           _tick_job_sync,
            trigger=trigger,
            id=repeat_job_id,
            args=[user_id_str, noti_text, repeat_job_id], # <--- SỬA
            replace_existing=False,
            misfire_grace_time=10,
        )
        print(f"[Escalation] Đã bật lặp mỗi {every_sec}s với job_id={repeat_job_id} cho User {user_id_str}") # <-- SỬA

def _do_push(user_id_str: str, noti_text: str):
    """
    (SỬA LẠI) Hàm (sync) thực thi push (Kiến trúc Tổng đài).
    (SỬA LỖI: Thêm 'user' vào payload API theo yêu cầu)
    """
    ts = datetime.now(VN_TZ).isoformat()
    
    # 1. Gửi tin nhắn vào Hàng đợi Tổng (Internal UI push)
    try:
        if GLOBAL_MESSAGE_QUEUE:
            GLOBAL_MESSAGE_QUEUE.put_nowait({
                "author": "Trợ lý ⏰",
                "content": f"⏰ Nhắc: {noti_text}\n🕒 {ts}",
                "target_user_id": user_id_str 
            })
            print(f"[Push/Queue] Đã gửi tin nhắn vào TỔNG ĐÀI cho User: {user_id_str}.")
        else:
            print("[Push/Queue] LỖI: GLOBAL_MESSAGE_QUEUE is None.")
            
    except Exception as e:
        print(f"[Push/Queue] Lỗi put_nowait (Tổng đài): {e}")

    # 2. Gọi API Frappe
    big_md = "# ⏰ **NHẮC VIỆC**\n\n## " + noti_text + "\n\n**🕒 " + ts + "**"
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (THÊM 'user') 🚀 ---
    payload = { 
        "subject": "🔔 Nhắc việc", 
        "notiname": big_md, 
        "url": PUSH_DEFAULT_URL,
        "for_user": user_id_str # <-- (MỚI) THÊM TRƯỜNG 'user' MANG THEO EMAIL
    }
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    
    ok, status, text = _call_push_api_frappe(payload)
    if ok:
        # (Cập nhật log để dễ theo dõi)
        print(f"[Push/API] OK status={status} (đã gửi 'user': {user_id_str})") 
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
# (DÁN HÀM HELPER MỚI NÀY VÀO - KHOẢNG DÒNG 2270)

def _convert_to_watch_url(url: str) -> str:
    """Helper: Chuyển đổi link embed/short của Youtube thành link 'watch'."""
    url = url.strip()
    
    # 1. Xử lý link 'embed'
    if "youtube.com/embed/" in url:
        video_id = url.split("/embed/")[-1].split("?")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
        
    # 2. Xử lý link 'short' (youtu.be)
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
        
    # 3. Trả về link gốc nếu không khớp
    return url
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
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1945)
async def display_interactive_list(where_clause: dict, title: str):
    """
    (SỬA LỖI V94 - SẮP XẾP THEO TIMESTAMP)
    Hàm "Trái Tim" (V61)
    1. (Cũ) Lấy "documents" (cho text) VÀ "metadatas" (cho file/image).
    2. (MỚI) Sắp xếp kết quả bằng helper V94.
    3. Hiển thị (MỚI NHẤT LÊN ĐẦU).
    """
    
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return 0 
    
    user_email = cl.user_session.get("user_email", "unknown")
    
    # Gộp filter user_id với where_clause
    if where_clause:
        combined_where = {
            "$and": [
                {"user_id": user_email},
                where_clause
            ]
        }
    else:
        combined_where = {"user_id": user_email}

    try:
        await cl.Message(content=f"**{title} (Mới nhất lên đầu)**").send() # <-- (V94) Thêm
        
        results = await asyncio.to_thread(
            vectorstore._collection.get, 
            where=combined_where,
            include=["documents", "metadatas"] 
        )
        if results is None: results = {}
        
        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        if not ids:
            await cl.Message(content="📭 Không tìm thấy mục nào khớp với bộ lọc này.").send()
            return 0

        found_count = 0
        
        # --- 🚀 SỬA LỖI V94 (SẮP XẾP) 🚀 ---
        sorted_results = _helper_sort_results_by_timestamp(ids, docs, metadatas)
        
        for doc_id, document_text, metadata in sorted_results:
        # --- 🚀 KẾT THÚC SỬA LỖI V94 🚀 ---
            
            if not metadata: metadata = {}
            file_type = metadata.get("file_type", "text")
            
            msg = cl.Message(content="")
            
            edit_action = cl.Action(
                name="edit_item_placeholder",
                payload={"doc_id": doc_id},
                label="✏️ Sửa"
            )
            actions = []
            
            # (Logic Hiển thị File/Ảnh (V76) giữ nguyên)
            if file_type != "text":
                content = metadata.get("original_content")
                if not content:
                    msg.content = f"Lỗi: {file_type} (ID: {doc_id}) thiếu 'original_content' trong metadata."
                    await msg.send()
                    continue
                try:
                    path_match = re.search(r"path=([^|]+)", content)
                    name_match = re.search(r"name=([^|]+)", content)
                    note_match = re.search(r"note=([^|]+)", content)
                    if not path_match: continue
                    
                    full_path = path_match.group(1).strip()
                    saved_name = os.path.basename(full_path)
                    safe_href = f"/public/files/{saved_name}"
                    
                    goc_name = name_match.group(1).strip() if name_match else "N/A"
                    goc_note = note_match.group(1).strip() if note_match else "(không ghi chú)"
                    safe_name = html.escape(goc_name)
                    
                    display_content = ""
                    if file_type == 'image':
                        display_content = f"**{safe_name}** [IMAGE]\n![{safe_name}]({safe_href})"
                    else:
                        display_content = f"**[{safe_name}]({safe_href})** [{file_type.upper()}]"
                    
                    msg.content = f"{display_content}\n• Ghi chú: *{goc_note}*\n• ID: `{doc_id}`"
                    actions = [
                        cl.Action(
                            name="delete_file",
                            payload={"doc_id": doc_id, "file_path": full_path, "message_id": msg.id},
                            label="🗑️ Xóa File"
                        ),
                        edit_action
                    ]
                except Exception as e_file:
                    msg.content = f"Lỗi parse file: {e_file}"
            
            # (Logic Hiển thị Text (V76) giữ nguyên)
            else:
                content = document_text 
                if content.startswith(("[REMINDER_", "FACT:", "[FILE_UNSUPPORTED]", "[ERROR_PROCESSING_FILE]")):
                    continue
                
                summary = content
                if len(summary) > 200 or "\n" in summary:
                     summary = (content.split('\n', 1)[0] or content).strip()[:200] + "..."
                msg.content = f"**Ghi chú:** {summary}\n• ID: `{doc_id}`"
                actions = [
                    cl.Action(
                        name="delete_note", 
                        payload={"doc_id": doc_id, "message_id": msg.id},
                        label="🗑️ Xóa Ghi chú"
                    ),
                    edit_action
                ]
            
            # 2d. Gửi tin nhắn
            msg.actions = actions
            await msg.send()
            found_count += 1

        return found_count
        
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi display_interactive_list: {e}").send()
        return 0
    
    
@cl.action_callback("edit_item_placeholder")
async def _on_edit_item_placeholder(action: cl.Action):
    """(MỚI V61) Placeholder cho tính năng "Sửa"."""
    await cl.Message(
        content="ℹ️ Tính năng 'Sửa' (Edit) đang được phát triển. "
                "Hiện tại, bạn có thể 'Xóa' và upload/lưu lại."
    ).send()
    
@cl.action_callback("show_category_items")
async def _on_show_category_items(action: cl.Action):
    """(MỚI V61) Xử lý khi bấm nút "Label" (Danh mục)."""
    try:
        fact_key = action.payload.get("fact_key")
        fact_label = action.payload.get("fact_label", fact_key)
        
        if not fact_key:
             await cl.Message(content="❌ Lỗi: Không nhận được fact_key.").send()
             return
             
        # Gọi hàm "Trái Tim"
        await display_interactive_list(
            where_clause={"fact_key": fact_key},
            title=f"Danh sách các mục trong: {fact_label} (Key: {fact_key})"
        )
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi _on_show_category_items: {e}").send()
            
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
            
            # --- 🚀 BẮT ĐẦU SỬA LỖI (User-based) 🚀 ---
            target_user_id = msg_data.get("target_user_id")
            if not target_user_id:
                print("⚠️ [Tổng đài] Nhận được tin nhắn nhưng không có target_user_id. Bỏ qua.")
                GLOBAL_MESSAGE_QUEUE.task_done()
                continue
                
            print(f"[Tổng đài] Nhận được tin nhắn cho USER: {target_user_id}.")

            # Lấy TẤT CẢ các queue (tất cả các tab) của user đó
            queues_for_user = ACTIVE_SESSION_QUEUES.get(target_user_id, [])
            
            if queues_for_user:
                print(f"[Tổng đài] Đang phát cho {len(queues_for_user)} tab của user {target_user_id}...")
                for target_queue in queues_for_user:
                    if target_queue:
                        await target_queue.put(msg_data)
            # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            
            GLOBAL_MESSAGE_QUEUE.task_done()
            
        except asyncio.CancelledError:
            print("[Tổng đài] Đã dừng.")
            break
        except Exception as e:
            print(f"[Tổng đài/ERROR] Bị lỗi: {e}")
            await asyncio.sleep(2)

async def session_receiver_poller():
    """(MỚI) HÀM THUÊ BAO - Chạy 1 lần cho MỖI TAB."""
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (User-based) 🚀 ---
    my_queue = asyncio.Queue()
    user_id_str = cl.user_session.get("user_id_str", None)
    
    if not user_id_str:
        print("❌ [Thuê bao] LỖI NGHIÊM TRỌNG: Không tìm thấy user_id_str khi bắt đầu poller.")
        return

    try:
        # Đảm bảo user có 1 list trong dict
        if user_id_str not in ACTIVE_SESSION_QUEUES:
            ACTIVE_SESSION_QUEUES[user_id_str] = []
            
        # Thêm queue (tab) này vào danh sách của user
        ACTIVE_SESSION_QUEUES[user_id_str].append(my_queue)
        print(f"✅ [Thuê bao] Đã ĐĂNG KÝ cho User {user_id_str} (Tổng số tab: {len(ACTIVE_SESSION_QUEUES[user_id_str])})")
        
        while True:
            msg_data = await my_queue.get()
            print(f"[Thuê bao] {user_id_str} đã nhận được tin nhắn.")
            content = msg_data.get("content", "")
            
            await cl.Message(
                author=msg_data.get("author", "Bot"),
                content=content
            ).send()
            
            my_queue.task_done()
            
    except asyncio.CancelledError:
        print(f"[Thuê bao] {user_id_str} đã dừng.")
    except Exception as e:
        print(f"[Thuê bao/ERROR] {user_id_str} bị lỗi: {e}")
    finally:
        # Xóa queue (tab) này khỏi danh sách của user
        if user_id_str in ACTIVE_SESSION_QUEUES:
            if my_queue in ACTIVE_SESSION_QUEUES[user_id_str]:
                ACTIVE_SESSION_QUEUES[user_id_str].remove(my_queue)
                print(f"[Thuê bao] Đã HỦY ĐĂNG KÝ cho User {user_id_str} (Còn lại: {len(ACTIVE_SESSION_QUEUES[user_id_str])} tab)")
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---

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
'''
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
'''
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
    (SỬA LỖI 2: Hiển thị tên file cho ảnh)
    """
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
        
    items = await asyncio.to_thread(list_active_files, vectorstore)
    
    if not items:
        await cl.Message(content="📭 Bộ nhớ file của bạn đang trống.").send()
        return

    # Phân loại: ảnh riêng, file riêng
    images_list = [it for it in items if it['type'] == '[IMAGE]']
    files_list = [it for it in items if it['type'] != '[IMAGE]']
    
    await cl.Message(content=f"🗂️ **My Drive** • {len(images_list)} ảnh • {len(files_list)} file").send()
    
    # Hiển thị ảnh dạng Google Drive grid
    if images_list:
        # Chuẩn bị dữ liệu cho ImageGrid
        images_data = []
        valid_images = []
        
        for it in images_list:
            # Skip nếu file không tồn tại trên disk
            if not os.path.exists(it['file_path']):
                print(f"[WARNING] File không tồn tại, skip: {it['file_path']}")
                continue
                
            safe_href = f"/public/files/{it['saved_name']}"
            images_data.append({
                "name": it['original_name'],
                "note": it['note'],
                "url": safe_href,
                "path": it['file_path'],
                "doc_id": it['doc_id'],
                "file_path": it['file_path']
            })
            valid_images.append(it)
        
        # Gửi ImageGrid với nút xóa API
        el = cl.CustomElement(
            name="ImageGrid",
            props={"title": f"📸 Ảnh ({len(valid_images)})", "images": images_data, "showActions": False},
            display="inline",
        )
        await cl.Message(content="", elements=[el]).send()
    
    # Hiển thị file dạng FileGrid
    if files_list:
        files_data = []
        valid_files = []
        
        for it in files_list:
            # Skip nếu file không tồn tại
            if not os.path.exists(it['file_path']):
                print(f"[WARNING] File không tồn tại, skip: {it['file_path']}")
                continue
                
            safe_href = f"/public/files/{it['saved_name']}"
            files_data.append({
                "name": it['original_name'],
                "note": it['note'],
                "type": it['type'],
                "url": safe_href,
                "doc_id": it['doc_id'],
                "file_path": it['file_path']
            })
            valid_files.append(it)
        
        # Gửi FileGrid với nút xóa API
        el = cl.CustomElement(
            name="FileGrid",
            props={"title": f"📁 Tài liệu ({len(valid_files)})", "files": files_data, "showActions": False},
            display="inline",
        )
        await cl.Message(content="", elements=[el]).send()
        
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

# (Dán Tool mới này vào)

class SearchProductSchema(BaseModel):
    # (Đây là phần "chỉ thị" cho LLM biết phải trích xuất cái gì)
    searchText: str = Field(..., description="Tên hoặc mã sản phẩm cần tìm. Ví dụ: 'máy cắt cỏ' hoặc 'máy cắt cỏ oshima w451'")

class SearchProductSchema(BaseModel):
    # (Schema cũ, chỉ lấy searchText)
    searchText: str = Field(..., description="Tên chung của sản phẩm cần tìm. Ví dụ: 'máy cắt cỏ'")
# (Dán hàm MỚI này vào, ngay trước searchlistproductnew)

def _get_detail_field(data: dict, key: str):
    """(MỚI) Helper: Lấy data chi tiết, bất kể nó nằm ở root, 'data', hay 'message'."""
    if not data or not isinstance(data, dict):
        return None
    
    # 1. Thử ở Root
    val = data.get(key)
    if val: return val
    
    # 2. Thử trong 'data'
    data_nested = data.get("data")
    if data_nested and isinstance(data_nested, dict):
        val = data_nested.get(key)
        if val: return val

    # 3. Thử trong 'message'
    msg_nested = data.get("message")
    if msg_nested and isinstance(msg_nested, dict):
        val = msg_nested.get(key)
        if val: return val
        
    return None # Không tìm thấy
@tool("searchlistproductnew", args_schema=SearchProductSchema)
async def searchlistproductnew(searchText: str) -> str:
    """
    (TOOL 1 - DANH SÁCH) Gọi API 'searchlistproductnew'
    Tự động lặp qua các trang (pageNum) để lấy TẤT CẢ sản phẩm
    và hiển thị TOÀN BỘ danh sách.
    """
    print(f"📞 [SearchList] (Tool 1) Đang tìm danh sách chung cho: '{searchText}'")
    
    # 1. Kiểm tra URL
    if not SEARCH_API_URL:
        return "❌ Lỗi: Biến SEARCH_API_URL chưa được khai báo."

    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        return "❌ Lỗi: Mất user_id_str. Vui lòng F5."
            
    # 2. Vòng lặp Pagination (Dùng 2 hàm global _call_api_sync và _parse_product_list)
    all_products = []
    pageNum = 1
    MAX_PAGES = 20 
    
    base_params = {
        "searchText": searchText, "user": user_id_str, "filterdata": "{}",
        "customer": "", "guest": "", "cartname": "", "minprice": 0,
        "maxprice": 9999999999, "sortBy": "", "listCheckedCategory": "",
        "listCheckedBrands": "", "listCheckItemGroupCrm": "", 
        "listCheckDocQuyen": "", "warehouse": "", "typeOrder": ""
    }

    print(f"📞 [SearchList] Bắt đầu lặp trang API cho: '{searchText}'")

    while pageNum <= MAX_PAGES:
        current_params = base_params.copy()
        current_params['pageNum'] = str(pageNum)
        
        api_data = await asyncio.to_thread(_call_api_sync, SEARCH_API_URL, current_params)
        
        if isinstance(api_data, dict) and "error" in api_data:
            print(f"⚠️ Lỗi API ở trang {pageNum}. Dừng lặp.")
            break 

        current_page_products = _parse_product_list(api_data)
        
        if not current_page_products:
            print(f"✅ [SearchList] Trang {pageNum} trả về rỗng. Đã lấy hết sản phẩm.")
            break 
            
        all_products.extend(current_page_products)
        pageNum += 1
        
    print(f"✅ [SearchList] Đã lấy tổng cộng {len(all_products)} sản phẩm.")

    # 3. Phân tích và Tóm tắt kết quả (Hiển thị đầy đủ)
    try:
        if not all_products:
            return f"ℹ️ Không tìm thấy sản phẩm nào khớp với: '{searchText}'."

        total_found = len(all_products) 
        summary_lines = []
        for i, product in enumerate(all_products):
            name = product.get('item_name', product.get('name', 'N/A'))
            code = product.get('itemcode', product.get('item_code', product.get('code', 'N/A')))
            price = product.get('price', 0)
            
            summary_lines.append(f"• **{name}** (Mã: `{code}`) - Giá: {price:,.0f} VND")

        result_str = f"✅ Tìm thấy {total_found} sản phẩm khớp với '{searchText}':\n"
        result_str += "\n".join(summary_lines)
        
        return result_str

    except Exception as e_parse:
        return f"⚠️ Lỗi khi phân tích kết quả: {e_parse}\n\nDữ liệu thô: {str(api_data)[:300]}"

# (Dán 2 hàm này vào khoảng dòng 3770)

def _call_api_sync(url: str, api_params: dict):
    """(MỚI - GLOBAL) Worker gọi API (dùng PUSH_SESSION)"""
    try:
        resp = PUSH_SESSION.get(
            url, headers={"Authorization": f"token {PUSH_API_TOKEN}"}, 
            params=api_params, 
            timeout=(3.05, PUSH_TIMEOUT), verify=PUSH_VERIFY_TLS,
        )
        if 200 <= resp.status_code < 300:
            return resp.json()
        else:
            return {"error": f"API Error {resp.status_code}", "details": resp.text[:300]}
    except Exception as e:
        return {"error": "Lỗi kết nối Python", "details": str(e)}

def _parse_product_list(api_data: Union[dict, list]) -> list:
    """(MỚI - GLOBAL) Worker phân tích cấu trúc JSON của API tìm kiếm"""
    try:
        if isinstance(api_data, dict) and "data" in api_data and \
           isinstance(api_data["data"], dict) and "listproduct" in api_data["data"]:
            return api_data["data"]["listproduct"] # Cấu trúc { data: { listproduct: [...] } }
        elif isinstance(api_data, dict) and "message" in api_data:
            return api_data["message"] # Cấu trúc { message: [...] }
        elif isinstance(api_data, dict) and "data" in api_data and isinstance(api_data["data"], list):
            return api_data["data"] # Cấu trúc { data: [...] }
        elif isinstance(api_data, list):
            return api_data # Cấu trúc [...]
        return [] # Không tìm thấy
    except Exception:
        return [] # Lỗi phân tích

def _format_clean_data_as_markdown(
    clean_data_list: List[dict], 
) -> List[str]: # <-- SỬA: Trả về List[str]
    """
    (CẬP NHẬT) Chuyển đổi data sạch thành một DANH SÁCH
    các chuỗi Markdown (mỗi sản phẩm 1 chuỗi) để dùng cho Carousel.
    """
    
    # (Hàm _html_to_markdown_parser không đổi)
    
    final_markdown_strings = [] # <-- MỚI: Danh sách kết quả
    
    if not clean_data_list:
        return [] # Trả về danh sách rỗng

    for i, item in enumerate(clean_data_list):
        
        output_lines = [] # <-- MỚI: Reset cho mỗi sản phẩm
        
        item_name = item.get("item_name", "N/A")
        item_code = item.get("item_code", "N/A")
        
        # Tiêu đề cho card
        output_lines.append(f"### {i+1}. {item_name} (Mã: `{item_code}`)")
        output_lines.append("---") # Phân cách
        
        # 1. Mô tả
        description_html = item.get("description")
        description_md = _html_to_markdown_parser(description_html)
        if description_md:
            output_lines.append("")
            output_lines.append("**Mô tả:**")
            output_lines.append(description_md)

        # 2. Ưu điểm
        advantages_html = item.get("advantages")
        advantages_md = _html_to_markdown_parser(advantages_html)
        if advantages_md:
            output_lines.append("")
            output_lines.append("**Ưu điểm nổi bật:**")
            output_lines.append(advantages_md)

        # 3. Thông số kỹ thuật
        specifications_html = item.get("specifications")
        specifications_md = _html_to_markdown_parser(specifications_html)
        if specifications_md:
            output_lines.append("")
            output_lines.append("**Thông số kỹ thuật:**")
            output_lines.append(specifications_md)
        
        # 4. Video
        video_url = item.get("video")
        if video_url and video_url.strip().startswith("http"):
             output_lines.append("")
             output_lines.append("**Video:**")
             output_lines.append(video_url.strip())
        
        # Thêm chuỗi Markdown của sản phẩm này vào danh sách tổng
        final_markdown_strings.append("\n".join(output_lines))
        
    return final_markdown_strings
# (Dán Tool 2 này vào)
# (Xóa tool 'get_product_detail' cũ và thay bằng tool này)
def _html_to_markdown_parser(html_str: str) -> str:
    """
    (MỚI) Dùng BeautifulSoup để dịch HTML thô từ API
    sang Markdown sạch.
    """
    if not html_str or not html_str.strip():
        return ""
        
    try:
        soup = BeautifulSoup(html_str, 'html.parser')
        output_lines = []

        # 1. Ưu tiên: Xử lý Bảng (<table>)
        table = soup.find('table')
        if table:
            headers = []
            # Lấy headers (thường trong <thead> nhưng API này dùng <tbody>)
            th_list = table.find_all('th')
            if th_list:
                headers = [th.get_text(strip=True) for th in th_list]
            
            # Nếu không có <th>, thử lấy <td> của dòng đầu tiên
            if not headers:
                 first_row_tds = table.find('tr').find_all('td')
                 if len(first_row_tds) == 2: # Giả định là bảng 2 cột
                     headers = [h.get_text(strip=True) for h in first_row_tds]
                     # Bỏ qua dòng header khi lặp rows
                     all_rows = table.find_all('tr')[1:]
                 else: # Không parse được header
                     all_rows = table.find_all('tr')
            else:
                all_rows = table.find_all('tr')[1:] # Bỏ qua dòng header th

            if headers:
                output_lines.append("| " + " | ".join(headers) + " |")
                output_lines.append("| " + " | ".join(['---'] * len(headers)) + " |")

            # Lấy các dòng nội dung
            for row in all_rows:
                cells = [td.get_text(strip=True) for td in row.find_all('td')]
                if cells:
                    output_lines.append("| " + " | ".join(cells) + " |")
            
            return "\n".join(output_lines)

        # 2. Xử lý Danh sách (<ul> <li>)
        ul_list = soup.find_all('ul')
        if ul_list:
            for li in soup.find_all('li'):
                # Giữ nguyên emoji/icon nếu có và làm sạch text
                text = li.get_text(strip=True)
                # (Logic giữ emoji - hơi phức tạp, tạm thời dùng text)
                
                # Sửa lỗi: Lấy luôn cả <strong>
                clean_text = ' '.join(li.stripped_strings)
                output_lines.append(f"- {clean_text}")
            return "\n".join(output_lines)
            
        # 3. Xử lý Đoạn văn (<p>)
        p_list = soup.find_all('p')
        if p_list:
            for p in p_list:
                text = p.get_text(strip=True)
                if text:
                    output_lines.append(f"- {text}")
            return "\n".join(output_lines)

        # 4. Fallback: Nếu không phải 3 dạng trên, chỉ lấy text
        return soup.get_text(strip=True, separator="\n")

    except Exception as e:
        print(f"⚠️ Lỗi _html_to_markdown_parser: {e}. Trả về text thô.")
        # Trả về text thô (đã strip) nếu parse lỗi
        try:
            return BeautifulSoup(html_str, 'html.parser').get_text(strip=True)
        except:
            return "" # Trả về rỗng nếu lỗi nặng
# (THAY THẾ CLASS NÀY - khoảng dòng 3945)
class DetailSearchSchema(BaseModel):
    query: str = Field(..., description="Toàn bộ câu hỏi của người dùng về một SẢN PHẨM (product) cụ thể. "
                                       "Ví dụ: 'thông số máy cắt cỏ w451', 'ưu điểm của H007-0104'. "
                                       "KHÔNG dùng cho ghi chú server (ví dụ: 'CH-SQLDB...').")
    
# (Tìm hàm này trong app.py, khoảng dòng 3950, và THAY THẾ TOÀN BỘ)
@tool("get_product_detail", args_schema=DetailSearchSchema)
async def get_product_detail(query: str) -> str:
    """
    (TOOL 2 - TỐI ƯU HÓA 5.0 - CAROUSEL)
    Trả về một chuỗi JSON đặc biệt để on_message
    có thể render dưới dạng Carousel (scroll ngang).
    (SỬA LỖI 6.0: Lấy 'avatarproduct' và ghép URL)
    """
    print(f"📞 [SmartDetail] (Tool 2) Bắt đầu. Query gốc: '{query}'")
    
    # 1. Lấy các biến session (Giữ nguyên)
    llm = cl.user_session.get("llm_logic") 
    user_id_str = cl.user_session.get("user_id_str")
    if not all([llm, user_id_str, SEARCH_API_URL, DETAIL_API_URL]):
        return "❌ Lỗi: Cấu hình hệ thống bị thiếu (LLM, UserID hoặc API URL)."

    # --- BƯỚC 1: TÁCH TỪ KHÓA (Giữ nguyên) ---
    searchText = ""
    try:
        print(f"📞 [SmartDetail] Bước 1a: Dùng LLM trích xuất searchText từ query...")
        prompt_extract = f"""
        Câu hỏi của người dùng: "{query}"
        Nhiệm vụ: Trích xuất TÊN SẢN PHẨM (hoặc MÃ SẢN PHẨM) từ câu hỏi trên để dùng cho tìm kiếm API.
        QUY TẮC:
        - Chỉ trả về TÊN/MÃ sản phẩm (ví dụ: 'máy cắt cỏ oshima 541', 'H007-0077').
        - Bỏ qua các từ chỉ hành động (như 'mô tả', 'thông số', 'cho tôi', 'xem').
        - KHÔNG giải thích.
        Tên/Mã sản phẩm:
        """
        resp_extract = await llm.ainvoke(prompt_extract)
        searchText = resp_extract.content.strip().strip("`'\"")
        if not searchText:
            return f"❌ Lỗi (Bước 1a): LLM không thể trích xuất tên sản phẩm từ '{query}'."
        print(f"📞 [SmartDetail] Bước 1b: LLM đã trích xuất searchText = '{searchText}'")
    except Exception as e_step1:
        return f"❌ Lỗi nghiêm trọng (Bước 1a - LLM Extract): {e_step1}"

    # --- BƯỚC 2: TÌM SẢN PHẨM (Giữ nguyên) ---
    search_params = {
        "searchText": searchText, "user": user_id_str, "filterdata": "{}", "customer": "", "guest": "0", 
        "cartname": "", "minprice": 0, "maxprice": 9999999999, "sortBy": "", 
        "listCheckedCategory": "", "listCheckedBrands": "", "listCheckItemGroupCrm": "", 
        "listCheckDocQuyen": "", "warehouse": "", "typeOrder": "",
        "pageNum": "1" , "warehouse":"Kho Hà Nội - O"
    }
    print(f"📞 [SmartDetail] Bước 2: Gọi Search API với search_params='{search_params}'")
    api_data = await asyncio.to_thread(_call_api_sync, SEARCH_API_URL, search_params)
    print(f"📞 [SmartDetail] data api'{api_data}'")
    if isinstance(api_data, dict) and "error" in api_data:
        return f"❌ Lỗi khi tìm kiếm (Bước 2): {api_data.get('details')}"
    all_products = _parse_product_list(api_data)
    if not all_products:
        return f"ℹ️ Không tìm thấy sản phẩm nào khớp với: '{searchText}'."
    
    # --- BƯỚC 3: LẤY CHI TIẾT (ĐÃ SỬA LỖI IMAGE) ---
    print(f"📞 [SmartDetail] Bước 3: Tìm thấy {len(all_products)} sản phẩm. Đang gọi {len(all_products)} API chi tiết CÙNG LÚC...")
    all_clean_data = [] 
    try:
        api_tasks = []
        products_to_process = [] 
        for product in all_products:
            item_code = product.get('itemcode')
            if not item_code: continue
            detail_params = {"prodcutname": item_code, "user": user_id_str}
            api_tasks.append(asyncio.to_thread(_call_api_sync, DETAIL_API_URL, detail_params))
            products_to_process.append(product)
        if not api_tasks:
            return "❌ Lỗi: Đã tìm thấy sản phẩm nhưng không có 'itemcode' nào hợp lệ."
            
        results = await asyncio.gather(*api_tasks)
        
        print(f"📞 [SmartDetail] Bước 3.5: Đã lấy {len(results)} chi tiết. Đang trích xuất...")
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI (GỘP TỪ LẦN TRƯỚC) 🚀 ---
        for product, detail_data_item in zip(products_to_process, results):
            if not (isinstance(detail_data_item, dict) and "error" in detail_data_item):
                
                # --- 🚀 LOGIC GHÉP URL (ĐÃ SỬA THEO YÊU CẦU CỦA BẠN) 🚀 ---
                relative_path = product.get('avatarproduct') # 1. Lấy 'avatarproduct'
                full_image_url = None # 2. Mặc định là None
                
                if relative_path:
                    # 3. Chỉ ghép nếu nó là đường dẫn (không phải http)
                    if not relative_path.startswith('http'):
                        # 4. Xử lý lỗi double slash (//files/ hoặc /files/)
                        if relative_path.startswith('//'):
                            relative_path = relative_path[1:] # //files/ -> /files/
                        elif not relative_path.startswith('/'):
                            relative_path = '/' + relative_path # files/ -> /files/
                        
                        # 5. Ghép URL
                        full_image_url = f"https://ocrm.oshima.vn{relative_path}"
                
                # --- 🚀 KẾT THÚC LOGIC GHÉP URL 🚀 ---

                clean_item = {
                    # --- Dữ liệu từ Search (product) ---
                    "item_name": product.get('item_name', 'N/A'),
                    "item_code": product.get('itemcode', 'N/A'),
                    "image": full_image_url, # <-- 🚀 SỬA: Dùng URL đã ghép
                    "url": product.get('url'),     # <-- Giữ nguyên (từ lần trước)
                    "category": product.get('category'), # <-- Giữ nguyên (từ lần trước)
                    
                    # --- Dữ liệu từ Detail (detail_data_item) ---
                    "description": _get_detail_field(detail_data_item, "description22"),
                    "advantages": _get_detail_field(detail_data_item, "product_advantages"),
                    "specifications": _get_detail_field(detail_data_item, "product_specifications"),
                    "video": _get_detail_field(detail_data_item, "testvideo")
                }
                all_clean_data.append(clean_item)
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
    except Exception as e_step3:
        return f"❌ Lỗi nghiêm trọng (Bước 3 - Parallel Detail): {e_step3}"
    
    if not all_clean_data:
        return f"❌ Lỗi: Đã tìm thấy {len(all_products)} sản phẩm nhưng không thể lấy chi tiết."

    # --- BƯỚC 4 (SỬA LẠI TỪ LẦN TRƯỚC): ĐÓNG GÓI DỮ LIỆU SẠCH (RAW) ---
    print(f"📞 [SmartDetail] Bước 4 (Carousel): Đóng gói {len(all_clean_data)} sản phẩm (dữ liệu thô) thành JSON...")
    try:
        # 1. Tạo payload
        json_payload = {
            "search_text_vn": searchText, 
            "products": all_clean_data  # <-- 🚀 TRUYỀN DỮ LIỆU SẠCH (LIST[DICT])
        }
        
        # 2. Đóng gói và trả về "chuỗi ma thuật"
        json_string = json.dumps(json_payload, ensure_ascii=False)
        return f"<CAROUSEL_PRODUCTS>{json_string}</CAROUSEL_PRODUCTS>"
        
    except Exception as e_step4:
        return f"❌ Lỗi khi format (Bước 4 Carousel): {e_step4}"
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
# (DÁN CLASS MỚI NÀY VÀO KHOẢNG DÒNG 3500)
class TimCongViecSchema(BaseModel):
    thoi_gian: str = Field(..., description="Mô tả thời gian (ví dụ: 'hôm nay', 'ngày mai', 'tuần này', 'tháng 11')")
    
class PushThuSchema(BaseModel):
    noidung: str = Field(description="Nội dung thông báo để push ngay")
# (THAY THẾ CLASS NÀY - khoảng dòng 3690)
class LayThongTinUserSchema(BaseModel):
    email: str = Field(..., description="Địa chỉ email CỤ THỂ (ví dụ: 'user@example.com') của user HỆ THỐNG (trong CSDL) cần tra cứu.")
class HienThiWebSchema(BaseModel):
    url: str = Field(..., description="URL đầy đủ (ví dụ: https://...) của trang web hoặc video cần nhúng.")
# -----------------------------------------------------------
def save_pending_action(tool_name: str, args: dict):
    """Lưu lệnh đang chờ (deletion) vào session để đợi xác nhận."""
    try:
        data = {
            "tool_name": tool_name,
            "args": args,
            "timestamp": datetime.now().isoformat()
        }
        cl.user_session.set("pending_deletion", data)
        
        # --- DEBUG ---
        data_check = cl.user_session.get("pending_deletion")
        print(f"✅ [Debug] save_pending_action: Đã LƯU vào session: {data_check}")
        # --- KẾT THÚC DEBUG ---
        
    except Exception as e:
        print(f"❌ [Debug] LError khi save_pending_action: {e}")
# (Tìm hàm _clean_context_for_llm (khoảng dòng 3080) và THAY THẾ)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3030)
def _build_clean_context_for_llm(
    docs_goc_content: list, 
    ids_goc: list # <-- (SỬA LỖI 65) Thêm ids_goc
) -> str:
    """Helper: (SỬA LỖI 65) Tạo context SẠCH
    Dùng DOC_ID (UUID) làm TAG để so khớp tuyệt đối.
    """
    clean_parts = []
    
    # (SỬA) Lặp qua cả 3 list
    for i, (content, doc_id) in enumerate(zip(docs_goc_content, ids_goc)):
        
        # --- 🚀 BẮT ĐẦU SỬA LOGIC 🚀 ---
        
        # 1. Bỏ qua các chuỗi metadata cũ
        if "| fact_key=" in content or content.startswith(("FACT:", "[REMINDER_")):
             continue
             
        # 2. Xử lý [IMAGE]/[FILE] (nếu có)
        type_tag = "[TEXT]" 
        note_str = ""
        
        if content.startswith(("[IMAGE]", "[FILE]")):
            type_tag = "[IMAGE]" if "[IMAGE]" in content else "[FILE]"
            note_match = re.search(r"note=([^|]+)", content)
            note_str = note_match.group(1).strip() if note_match else "(không ghi chú)"
        
        else: # Đây là [TEXT]
            note_str = content.strip() # Dùng chính nội dung
            
        # 3. Xây dựng chuỗi "sạch"
        # (SỬA) Dùng DOC_ID (ví dụ: <b48f1f15...>) làm TAG
        clean_parts.append(f"<{doc_id}>{type_tag} | note={note_str}</{doc_id}>")
        
        # --- 🚀 KẾT THÚC SỬA LOGIC 🚀 ---
        
    return "\n".join(clean_parts)

# (Tìm hàm _is_general_query, khoảng dòng 3080, và THAY THẾ TOÀN BỘ)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3080)
async def _is_general_query(llm: ChatOpenAI, query: str, fact_key: str) -> bool:
    """
    (SỬA LỖI 64: TỐI ƯU HÓA V3 - NGHIÊM NGẶT)
    Nếu phát hiện "từ chi tiết" (extra_words_str) -> Buộc SPECIFIC.
    """
    try:
        # 1. Chuẩn hóa
        query_clean = unidecode.unidecode(query.lower().strip())
        key_clean = fact_key.replace("_", " ").lower().strip()
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI LOGIC TỐI ƯU (V3) 🚀 ---
        
        # 2. (Tối ưu) Kiểm tra
        if key_clean in query_clean:
            extra_words_str = query_clean.replace(key_clean, "").strip()
            
            # Xóa các "stop word"
            extra_words_str = extra_words_str.replace("xem", "").replace("tim", "").strip()
            extra_words_str = extra_words_str.replace("hinh", "").replace("anh", "").strip()
            extra_words_str = extra_words_str.replace("file", "").replace("ds", "").strip() # (Bổ sung)
            
            if not extra_words_str:
                # Nếu không còn từ nào -> Đây là GENERAL
                print(f"[_is_general_query] Tối ưu V3: Query khớp chính xác. Đánh dấu GENERAL.")
                return True
            else:
                # Nếu còn từ (ví dụ: "nhan su") -> Đây là SPECIFIC
                print(f"[_is_general_query] Tối ưu V3: Query có từ chi tiết ('{extra_words_str}').")
                print(f"[_is_general_query] -> BUỘC LỌC (SPECIFIC). (Bỏ qua LLM B3)")
                return False # <-- (SỬA LỖI 64 NẰM Ở ĐÂY)
        
        # --- 🚀 KẾT THÚC SỬA LỖI LOGIC TỐI ƯU 🚀 ---

        # 3. Nếu tối ưu thất bại -> Hỏi LLM (an toàn)
        # (Ví dụ: query 'tôi thích ăn gì?' -> key 'so_thich' (key không có trong query))
        prompt = f"""Bạn là một chuyên gia phân loại ý định.
        
        Câu hỏi của người dùng (Query): "{query}"
        Danh mục (Category): "{fact_key}" (Nghĩa là: "{key_clean}")

        Nhiệm vụ: Câu hỏi này là yêu cầu CHUNG (lấy tất cả) 
        hay yêu cầu CỤ THỂ (lọc 1 cái)?

        Ví dụ 1:
        Query: "xem anh gia dinh"
        Category: "anh_gia_dinh"
        -> Ý định: CHUNG (lấy tất cả 'anh_gia_dinh')
        Output: GENERAL

        Ví dụ 2:
        Query: "anh noi quy gia dinh"
        Category: "anh_gia_dinh"
        -> Ý định: CỤ THỂ (lọc 'noi quy' từ 'anh_gia_dinh')
        Output: SPECIFIC
        
        Ví dụ 3 (QUAN TRỌNG):
        Query: "anh du lich ha long"
        Category: "anh_du_lich"
        -> Ý định: CỤ THỂ (lọc 'ha long' từ 'anh_du_lich')
        Output: SPECIFIC

        Trả lời CHÍNH XÁC một từ: 'GENERAL' (chung) hoặc 'SPECIFIC' (cụ thể).
        """
        
        resp = await llm.ainvoke(prompt)
        result = resp.content.strip().upper()
        
        print(f"[_is_general_query] LLM (Bước 3) phân loại: '{result}'")
        return (result == "GENERAL")
        
    except Exception as e:
        print(f"❌ Lỗi _is_general_query: {e}. Mặc định là SPECIFIC.")
        return False # An toàn: mặc định là lọc (SPECIFIC)
    
    
# (Dán hàm MỚI HOÀN TOÀN này vào, ngay trước hàm hoi_thong_tin)
async def _display_rag_result(content_goc: str) -> bool:
    """
    (MỚI) Helper: Phân tích một chuỗi 'content' từ RAG
    và hiển thị nó (Ảnh, File, Video, Link, Text) ra UI.
    Trả về True nếu hiển thị thành công.
    """
    
    # --- 1. Xử lý [IMAGE] / [FILE] (có cấu trúc) ---
    if content_goc.startswith(("[IMAGE]", "[FILE]")):
        try:
            goc_name_match = re.search(r"name=([^|]+)", content_goc)
            goc_note_match = re.search(r"note=([^|]+)", content_goc)
            path_match = re.search(r"path=([^|]+)", content_goc)

            if not path_match: return False # Bắt buộc phải có path
            
            goc_name = goc_name_match.group(1).strip() if goc_name_match else "N/A"
            goc_note = goc_note_match.group(1).strip() if goc_note_match else "(không ghi chú)"
            full_path = path_match.group(1).strip()
            saved_name = os.path.basename(full_path)
            safe_href = f"/public/files/{saved_name}"
            safe_name = html.escape(goc_name)

            if "[IMAGE]" in content_goc:
                await cl.Message(
                    content=f"**Ảnh đã lưu:** {safe_name}\n*Ghi chú: {goc_note}*\n![{safe_name}]({safe_href})"
                ).send()
                return True
            else: # [FILE]
                await cl.Message(
                    content=f"**File đã lưu:** [{safe_name}]({safe_href})\n*Ghi chú: {goc_note}*"
                ).send()
                return True
        except Exception as e:
            print(f"❌ Lỗi hiển thị [IMAGE]/[FILE]: {e}")
            return False

    # --- 2. Xử lý [WEB_LINK] / Link... (dạng text) ---
    if content_goc.startswith(("[WEB_LINK]", "Link video YouTube", "Link trang web")):
        try:
            # (Tìm URL, kể cả khi nó nằm trong |note=...|)
            url_match = re.search(r"(https?://[^\s|]+)", content_goc)
            if not url_match: return False
            
            url = url_match.group(1).strip()
            is_youtube = ("youtube.com" in url) or ("youtu.be" in url)
            
            if is_youtube:
                watch_url = _convert_to_watch_url(url)
                video_element = ClVideo(url=watch_url, name="Video", display="inline")
                await cl.Message(
                    content=f"**Video đã lưu:** {watch_url}",
                    elements=[video_element],
                ).send()
                return True
            else: # Web link
                await cl.Message(
                    content=f"**Trang web đã lưu:** [{url}]({url})"
                ).send()
                return True
        except Exception as e:
            print(f"❌ Lỗi hiển thị [WEB_LINK]: {e}")
            return False

    # --- 3. Bỏ qua các chuỗi hệ thống ---
    if content_goc.startswith(("[REMINDER_", "FACT:", "[FILE_UNSUPPORTED]", "[ERROR_PROCESSING_FILE]", "Trích từ tài liệu:")):
        return False

    # --- 4. Hiển thị Ghi chú (Văn bản thuần túy) ---
    try:
        # Đảm bảo nó không phải là chuỗi rỗng
        if content_goc and content_goc.strip():
            await cl.Message(
                content=f"**Ghi chú đã lưu:**\n```\n{content_goc}\n```"
            ).send()
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Lỗi hiển thị Ghi chú: {e}")
        return False
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 3280)
async def _display_rag_result(content_goc: str) -> bool:
    """
    (MỚI) Helper: Phân tích một chuỗi 'content' từ RAG
    và hiển thị nó (Ảnh, File, Video, Link, Text) ra UI.
    Trả về True nếu hiển thị thành công.
    (SỬA LỖI 28: Thêm bộ lọc cho 'fact_key=' và các metadata khác)
    (SỬA LỖI 29: Bỏ block code ``` khi hiển thị text)
    """
    
    # --- 0. (MỚI) Bỏ qua tất cả metadata ---
    if "| fact_key=" in content_goc:
        # Nếu chuỗi này chứa tag | fact_key=
        # (Chúng ta giả định đây là metadata và không hiển thị)
        return False
        
    # --- 1. Xử lý [IMAGE] / [FILE] ---
    if content_goc.startswith(("[IMAGE]", "[FILE]")):
        try:
            goc_name_match = re.search(r"name=([^|]+)", content_goc)
            goc_note_match = re.search(r"note=([^|]+)", content_goc)
            path_match = re.search(r"path=([^|]+)", content_goc)

            if not path_match: return False # Bắt buộc phải có path
            
            goc_name = goc_name_match.group(1).strip() if goc_name_match else "N/A"
            goc_note = goc_note_match.group(1).strip() if goc_note_match else "(không ghi chú)"
            full_path = path_match.group(1).strip()
            saved_name = os.path.basename(full_path)
            safe_href = f"/public/files/{saved_name}"
            safe_name = html.escape(goc_name)

            if "[IMAGE]" in content_goc:
                await cl.Message(
                    content=f"**Ảnh đã lưu:** {safe_name}\n*Ghi chú: {goc_note}*\n![{safe_name}]({safe_href})"
                ).send()
                return True
            else: # [FILE]
                await cl.Message(
                    content=f"**File đã lưu:** [{safe_name}]({safe_href})\n*Ghi chú: {goc_note}*"
                ).send()
                return True
        except Exception as e:
            print(f"❌ Lỗi hiển thị [IMAGE]/[FILE]: {e}")
            return False

    # --- 2. Xử lý [WEB_LINK] / Link... ---
    if content_goc.startswith(("[WEB_LINK]", "Link video YouTube", "Link trang web")):
        try:
            url_match = re.search(r"(https?://[^\s|]+)", content_goc)
            if not url_match: return False
            
            url = url_match.group(1).strip()
            is_youtube = ("youtube.com" in url) or ("youtu.be" in url)
            
            if is_youtube:
                watch_url = _convert_to_watch_url(url)
                video_element = ClVideo(url=watch_url, name="Video", display="inline")
                await cl.Message(
                    content=f"**Video đã lưu:** {watch_url}",
                    elements=[video_element],
                ).send()
                return True
            else: # Web link
                await cl.Message(
                    content=f"**Trang web đã lưu:** [{url}]({url})"
                ).send()
                return True
        except Exception as e:
            print(f"❌ Lỗi hiển thị [WEB_LINK]: {e}")
            return False

    # --- 3. Bỏ qua các chuỗi hệ thống ---
    if content_goc.startswith(("[REMINDER_", "FACT:", "[FILE_UNSUPPORTED]", "[ERROR_PROCESSING_FILE]", "Trích từ tài liệu:")):
        return False

    # --- 4. Hiển thị Ghi chú (Văn bản thuần túy) ---
    try:
        if content_goc and content_goc.strip():
            
            # --- 🚀 BẮT ĐẦU SỬA LỖI (THEO YÊU CẦU CỦA BẠN) 🚀 ---
            # (Bỏ dấu ```)
            await cl.Message(
                content=f"**Ghi chú đã lưu:**\n\n{content_goc}"
            ).send()
            # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Lỗi hiển thị Ghi chú: {e}")
        return False
# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 2990)
def _helper_sort_results_by_timestamp(
    ids: List[str], 
    docs: List[str], 
    metadatas: List[dict]
) -> List[tuple[str, str, dict]]:
    """
    (MỚI - V94) Helper: Sắp xếp kết quả Chroma
    theo 'timestamp' (mới nhất lên đầu).
    """
    temp_results_list = []
    
    # 1. Gộp 3 list lại
    for doc_id, content, metadata in zip(ids, docs, metadatas):
        ts_str = "1970-01-01T00:00:00+00:00" # Mốc Unix (cho data cũ)
        
        # (Sửa lỗi V91 - Chống None)
        if metadata and metadata.get("timestamp"):
            ts_str = metadata.get("timestamp")
        
        temp_results_list.append({
            "id": doc_id, 
            "content": content, 
            "metadata": metadata, 
            "timestamp_str": ts_str
        })
    
    # 2. Sắp xếp (mới nhất -> cũ nhất)
    try:
        sorted_temp_list = sorted(
            temp_results_list, 
            key=lambda x: x["timestamp_str"], 
            reverse=True
        )
    except Exception as e_sort:
        print(f"⚠️ Lỗi khi sắp xếp timestamp (V94 Helper): {e_sort}. Dùng danh sách gốc.")
        sorted_temp_list = temp_results_list

    # 3. Trả về dạng list of tuples
    return [
        (item["id"], item["content"], item["metadata"]) 
        for item in sorted_temp_list
    ]
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 3000)
def _build_rag_filter_from_query(query: str) -> Optional[dict]:
    """(SỬA LỖI V89)
    Thay vì .startswith (quá khắt khe), dùng regex
    để tìm TỪ KHÓA (word) 'anh'/'hinh'/'file'.
    (SỬA LỖI 77)
    Thay vì lọc theo file_type (gây nhiễu),
    chúng ta lọc theo 'entry_type': 'file_master'.
    """
    
    q_low = unidecode.unidecode(query.lower())
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI V89 (Regex) 🚀 ---
    
    # 1. (SỬA) Ưu tiên: Tìm (chỉ) ảnh
    # (Tìm từ 'anh' hoặc 'hinh' đứng riêng lẻ)
    if re.search(r"\b(anh|hinh|images?|imgs?)\b", q_low):
         print(f"[_build_rag_filter] (Sửa lỗi V89) Phát hiện lọc (chỉ) ảnh GỐC (Regex).")
         return {
             "$and": [
                 {"file_type": "image"},
                 {"entry_type": "file_master"}
             ]
         }

    # 2. (SỬA) Tìm file GỐC
    file_keywords = [
        "file", "excel", "xlsx", "xls", "trang tinh", 
        "word", "docx", "doc", "van ban", 
        "pdf", "tai lieu", "danh sach", "ds"
    ]
    
    # (Dùng regex \b(word)\b để tìm từ riêng lẻ)
    if any(re.search(r"\b" + re.escape(kw) + r"\b", q_low) for kw in file_keywords):
         print(f"[_build_rag_filter] (Sửa lỗi V89) Phát hiện lọc file GỐC (master) (Regex).")
         # (Lấy TẤT CẢ các loại file GỐC, trừ Ghi chú)
         return {"entry_type": "file_master"}
    # --- 🚀 KẾT THÚC SỬA LỖI V89 🚀 ---
         
    # 3. Không phát hiện
    return None

class XoaCongViecSchema(BaseModel):
        noi_dung_cong_viec: str = Field(..., description="Nội dung/Tiêu đề của công việc cần xóa, ví dụ: 'hoàn thành báo cáo'")
        # (Đã xóa force_delete)
@tool("xoa_cong_viec", args_schema=XoaCongViecSchema)
async def xoa_cong_viec(noi_dung_cong_viec: str) -> str:
    """
    (LOGIC MỚI) Tìm và HIỂN THỊ TẤT CẢ công việc (task) khớp
    với nút xóa riêng cho từng mục.
    """
    user_id_str = cl.user_session.get("user_id_str")
    if not user_id_str:
        return "❌ Lỗi: Mất user_id. Vui lòng F5."

    # B1. TÌM (Dùng hàm SQL LIKE cũ)
    tasks_found = await asyncio.to_thread(
        _find_tasks_by_title_db, user_id_str, noi_dung_cong_viec
    )
    if not tasks_found:
        return f"ℹ️ Không tìm thấy công việc nào (chưa hoàn thành) khớp với '{noi_dung_cong_viec}'."
        
    # B2. HIỂN THỊ (Gửi tin nhắn thông báo)
    await cl.Message(
        content=f"✅ Tôi tìm thấy {len(tasks_found)} công việc khớp với '{noi_dung_cong_viec}':"
    ).send()
    
    # B3. LẶP VÀ GỬI TỪNG MỤC
    for task in tasks_found:
        task_id = task['id']
        content = task['title']
        description = task.get('description')
        desc_str = f" - *{description}*" if description else ""
        
        # 3a. Tạo tin nhắn (chưa gửi)
        msg = cl.Message(content=f"• **{content}**{desc_str}")
        
        # 3b. Tạo nút Xóa (Trỏ về callback 'delete_task' đã có)
        actions = [
            cl.Action(
                name="delete_task", # <-- Gọi callback 'delete_task' đã có
                payload={"task_id": task_id, "message_id": msg.id},
                label="🗑️ Xóa công việc này"
            )
        ]
        
        # 3c. Gán action và gửi
        msg.actions = actions
        await msg.send()
        
    # B4. Trả về thông báo cho Agent
    return f"✅ Đã hiển thị {len(tasks_found)} kết quả khớp với các nút xóa."
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
class XoaGhiChuSchema(BaseModel):
        noi_dung_ghi_chu: str = Field(..., description="Nội dung/từ khóa của ghi chú (note) cần xóa")
        # (Không còn force_delete ở đây)
@tool("xoa_ghi_chu", args_schema=XoaGhiChuSchema)
async def xoa_ghi_chu(noi_dung_ghi_chu: str) -> str:
    """
    (LOGIC MỚI) Tìm và HIỂN THỊ TẤT CẢ ghi chú khớp
    (dùng LLM filter) với nút xóa riêng cho từng mục.
    """
    vectorstore = cl.user_session.get("vectorstore")
    llm = cl.user_session.get("llm_logic") 
    
    if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
    if not llm: return "❌ Lỗi: Không tìm thấy llm_logic (cần cho việc lọc)."

    # --- BẮT ĐẦU LOGIC MỚI ---
    
    # B1. TÌM (Dùng hàm _find_... bạn đã có)
    # (Hàm này đã chạy to_thread bên trong tool rồi nên ta await)
    docs_found = await asyncio.to_thread(
        _find_notes_for_deletion,
        vectorstore,
        llm,
        noi_dung_ghi_chu
    )
    
    if not docs_found:
        return f"ℹ️ Không tìm thấy ghi chú văn bản nào (đã lọc bằng LLM) khớp với '{noi_dung_ghi_chu}'."
        
    # B2. HIỂN THỊ (Gửi tin nhắn thông báo)
    await cl.Message(
        content=f"✅ Tôi tìm thấy {len(docs_found)} ghi chú (đã lọc bằng LLM) khớp với '{noi_dung_ghi_chu}':"
    ).send()
    
    # B3. LẶP VÀ GỬI TỪNG MỤC
    # (Đây là logic giống hệt ui_show_all_memory)
    for item in docs_found:
        doc_id = item['id']
        content = item['doc']
        
        # 3a. Tạo tin nhắn (chưa gửi)
        msg = cl.Message(content="")
        
        # 3b. Tạo nút Xóa (Trỏ về message_id của chính nó)
        actions = [
            cl.Action(
                name="delete_note", # <-- Gọi callback 'delete_note' đã có
                payload={"doc_id": doc_id, "message_id": msg.id},
                label="🗑️ Xóa ghi chú này"
            )
        ]
        
        # 3c. Hiển thị nội dung (Tóm tắt nếu quá dài)
        if len(content) > 150 or "\n" in content:
            summary = "• " + (content.split('\n', 1)[0] or content).strip()[:150] + "..."
            msg.content = summary
            
            # Thêm nút "Xem chi tiết" (giống ui_show_all_memory)
            actions.append(
                cl.Action(
                    name="show_note_detail",
                    payload={"doc_id": doc_id},
                    label="📄 Xem chi tiết"
                )
            )
        else:
            msg.content = f"• {content}"

        # 3d. Gán action và gửi
        msg.actions = actions
        await msg.send()
        
    # B4. Trả về thông báo cho Agent
    return f"✅ Đã hiển thị {len(docs_found)} kết quả khớp với các nút xóa."
class XoaNhacNhoSchema(BaseModel):
    noi_dung_nhac_nho: str = Field(..., description="Nội dung của nhắc nhở cần xóa")
    # (Đã xóa force_delete)

@tool("xoa_nhac_nho", args_schema=XoaNhacNhoSchema)
async def xoa_nhac_nho(noi_dung_nhac_nho: str) -> str:
    """
    (LOGIC MỚI) Tìm và HIỂN THỊ TẤT CẢ lịch nhắc khớp
    với nút xóa riêng cho từng mục.
    """
    
    # B1. TÌM (Dùng hàm tìm cũ)
    reminders_found = await asyncio.to_thread(
        _find_reminders_by_text_db, noi_dung_nhac_nho
    )
    if not reminders_found:
        return f"ℹ️ Không tìm thấy lịch nhắc nào (đang chạy) khớp với '{noi_dung_nhac_nho}'."
        
    # B2. HIỂN THỊ (Gửi tin nhắn thông báo)
    await cl.Message(
        content=f"✅ Tôi tìm thấy {len(reminders_found)} lịch nhắc khớp với '{noi_dung_nhac_nho}':"
    ).send()
    
    # B3. LẶP VÀ GỬI TỪNG MỤC
    for reminder in reminders_found:
        job_id = reminder['id']
        content = reminder['text']
        
        # 3a. Tạo tin nhắn (chưa gửi)
        msg = cl.Message(content=f"• **{content}** (JobID: `{job_id}`)")
        
        # 3b. Tạo nút Xóa (Trỏ về callback 'delete_reminder' đã có)
        actions = [
            cl.Action(
                name="delete_reminder", # <-- Gọi callback 'delete_reminder' đã có
                payload={"job_id": job_id, "message_id": msg.id},
                label="🗑️ Hủy lịch nhắc này"
            )
        ]
        
        # 3c. Gán action và gửi
        msg.actions = actions
        await msg.send()
        
    # B4. Trả về thông báo cho Agent
    return f"✅ Đã hiển thị {len(reminders_found)} kết quả khớp với các nút xóa."
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3535)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3535)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3535)
@tool("luu_thong_tin", args_schema=LuuThongTinSchema)
async def luu_thong_tin(noi_dung: str):
    """
    (SỬA LỖI V97 - FIX LỖI BOOKMARK CHO TEXT)
    1. (MỚI) Bỏ qua logic tóm tắt.
    2. (CŨ) Dùng GPT (V88) chỉ để lấy fact_key, fact_label, VÀ core_query_term.
    3. (MỚI) Ép sử dụng text_splitter để chia nhỏ (chunk)
       và lưu NỘI DUNG GỐC (không phải tóm tắt).
    (SỬA - THÊM user_id VÀO METADATA)
    """
    # Lấy dependencies từ session
    vectorstore = cl.user_session.get("vectorstore")
    llm = cl.user_session.get("llm_logic") 
    user_id_str = cl.user_session.get("user_id_str") 

    if not all([vectorstore, llm, user_id_str]):
        return "❌ Lỗi: Thiếu (vectorstore, llm, user_id_str)."

    try:
        # --- 🚀 BẮT ĐẦU SỬA LỖI V97 🚀 ---
        # 1. Lấy nội dung GỐC (original text)
        original_text = (noi_dung or "").strip()
        if not original_text: return "⚠️ Không có nội dung để lưu."
        
        # 2. (CŨ) Gọi GPT V88 để phân loại
        #    (CHỈ GỬI PHẦN TIÊU ĐỀ - 200 ký tự đầu)
        fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
        
        # (OPTIMIZATION) Chỉ gửi 200 ký tự đầu (tiêu đề) lên LLM để tiết kiệm token
        text_for_classification = original_text
        if len(original_text) > 200:
            # Lấy 200 ký tự đầu, cắt ở cuối từ để tránh cắt giữa chừng
            text_for_classification = original_text[:200].rsplit(' ', 1)[0] + "..."
            print(f"[luu_thong_tin] (OPTIMIZATION) Text dài {len(original_text)} chars, chỉ gửi {len(text_for_classification)} chars (tiêu đề) cho LLM phân loại.")
        else:
            print(f"[luu_thong_tin] Đang gọi GPT (V88) để phân loại ghi chú (dài {len(original_text)} chars)...")

        fact_key, fact_label, core_query_term = await call_llm_to_classify(
            llm, text_for_classification, fact_dict
        )
        print(f"[luu_thong_tin] (Sửa lỗi V97) GPT (V88) trả về: Key='{fact_key}', Label='{fact_label}', CoreQuery='{core_query_term}'")
        
        # --- 🚀 BƯỚC B: LƯU NỘI DUNG (OPTIMIZATION - NHANH) 🚀 ---
        # STRATEGY: Với text dài, lưu NGUYÊN 1 CHUNK (không chia nhỏ)
        # để tăng tốc embedding (giống NiceGUI)
        
        current_timestamp_iso = datetime.now(VN_TZ).isoformat()
        user_email = cl.user_session.get("user_email", "unknown")
        
        metadata_base = {
            "user_id": user_email,
            "fact_key": fact_key,
            "fact_label": fact_label,
            "file_type": "text",
            "timestamp": current_timestamp_iso,
        }
        
        # OPTIMIZATION: Không chia nhỏ, lưu nguyên 1 chunk
        # → Nhanh hơn 5-10 lần (chỉ 1 embedding call thay vì 6)
        chunks = [original_text]
        metadatas_list = [metadata_base]
        
        print(f"[luu_thong_tin] (OPTIMIZATION) Lưu NGUYÊN 1 chunk ({len(original_text)} chars) - Không chia nhỏ để tăng tốc.")
        
        # 3. Ghi CHUNKS (NỘI DUNG GỐC) vào Vectorstore
        await asyncio.to_thread(
            vectorstore.add_texts,
            texts=chunks, # <-- Lưu 1 chunk (nội dung gốc nguyên)
            metadatas=metadatas_list
        )
        print(f"[luu_thong_tin] ✅ (OPTIMIZATION) Đã lưu 1 chunk vào shared DB (user_id={user_email}).")
        
        # --- 🚀 BƯỚC C: LƯU VÀO CACHE (FACT_MAP) (Giữ nguyên) 🚀 ---
        if core_query_term and core_query_term.strip().lower() != "all":
            cache_key = core_query_term.strip().lower()
            fact_dict[cache_key] = {"key": fact_key, "label": fact_label} 
            await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
            print(f"[luu_thong_tin] Đã cập nhật cache: '{cache_key}' -> '{fact_key}'")
        else:
            print(f"[luu_thong_tin] Bỏ qua cập nhật cache vì CoreQuery là '{core_query_term}'")
        
        return (
            f"✅ Đã lưu ghi chú thành công!\n\n"
            f"**Chủ đề:** {fact_label}\n"
            f"**Số ký tự:** {len(original_text)}\n"
            f"**Tối ưu:** Lưu 1 chunk nguyên (nhanh gấp 5-10 lần)"
        )
        
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"❌ LỖI LƯU (V97): {e}"
    
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
    
    # NOTE: Vectorstore đã được khởi tạo ở on_chat_start (Shared DB)
    # Không cần khởi tạo lại ở đây
    
    # Lấy retriever từ session
    retriever = cl.user_session.get("retriever")
    if not retriever:
        print("❌ Lỗi: Không tìm thấy retriever trong session")
        await cl.Message(content="❌ Lỗi: Không tìm thấy retriever").send()
        return
    
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
    
    

    

    

    

    
    
    @tool("hien_thi_web", args_schema=HienThiWebSchema)
    async def hien_thi_web(url: str) -> str:
        """
        (SỬA LỖI 3 TRONG 1)
        1) Sửa RAG: Lưu 2 ghi chú (expansion) để dễ tìm.
        2) Sửa YouTube: Dùng cl.Video để hiển thị.
        3) Sửa Web: Cố gắng nhúng bằng <iframe> an toàn. Nếu bị chặn -> trả link Markdown.
        """
        try:
            if not url or not url.startswith(("http://", "https://")):
                return "⚠️ Lỗi: Thiếu URL hợp lệ (bắt đầu bằng http/https)."

            url_to_embed = url.strip()
            is_youtube = ("youtube.com" in url_to_embed) or ("youtu.be" in url_to_embed)

            # --- 1) RAG expansions: lưu 2 ghi chú ---
            vectorstore = cl.user_session.get("vectorstore")
            if vectorstore:
                texts_to_save = [f"[WEB_LINK] {url_to_embed}"]
                if is_youtube:
                    texts_to_save.append(f"Link video YouTube đã lưu: {url_to_embed}")
                else:
                    texts_to_save.append(f"Link trang web đã lưu: {url_to_embed}")

                # Chạy add_texts trong thread để không block event loop
                await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                print(f"[hien_thi_web] Đã lưu {len(texts_to_save)} expansion cho: {url_to_embed}")
            else:
                print("⚠️ [hien_thi_web] Không tìm thấy vectorstore trong session, bỏ qua bước lưu.")

            # --- 2) Hiển thị nội dung ---
            if is_youtube:
                # Chuẩn hoá URL YouTube về dạng watch
                watch_url = _convert_to_watch_url(url_to_embed)
                video_element = ClVideo(url=watch_url, name="YouTube", display="inline")
                await cl.Message(
                    content=f"▶️ Đang hiển thị video: {watch_url}",
                    elements=[video_element],
                ).send()
                return f"✅ Đã nhúng video: {watch_url}"

            # --- 3) Web thường: thử nhúng iframe an toàn ---
            # Nhiều site sẽ chặn iframe. Ta thử trước; nếu lỗi hiển thị hoặc bị CSP/X-Frame, sẽ fallback sang link.
            safe_url = html.escape(url_to_embed, quote=True)
            iframe_html = f"""
    <div style="position:relative;padding-top:56.25%;height:0;overflow:hidden;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.12)">
    <iframe
        src="{safe_url}"
        title="Web Embed"
        loading="lazy"
        referrerpolicy="no-referrer"
        sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
        style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:12px"
    ></iframe>
    </div>
    <p style="margin-top:10px">
    Nếu khung trên không hiển thị do website chặn nhúng, bạn có thể mở trực tiếp: 
    <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>
    </p>
    """.strip()

            try:
                await cl.Message(
                    content="🌐 Đang thử nhúng trang web:",
                    elements=[ClText(name="Web Embed", content=iframe_html, mime="text/html", display="inline")],
                ).send()
                return f"✅ Đã gửi khung nhúng cho: {url_to_embed}"
            except Exception as e:
                # Fallback: chỉ đưa link Markdown
                await cl.Message(
                    content=(
                        "**Lưu ý:** Website này không thể nhúng trong ứng dụng vì chính sách bảo mật (CSP/X-Frame-Options).\n\n"
                        f"Bạn có thể mở trực tiếp: [{safe_url}]({safe_url})"
                    )
                ).send()
                return f"✅ Đã lưu link trang web (fallback do iframe bị chặn): {safe_url}. Chi tiết: {e}"

        except Exception as e:
            return f"❌ Lỗi khi nhúng URL: {e}"

    
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

    
    # (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 3611)
    @tool(args_schema=DatLichSchema)
    async def dat_lich_nhac_nho(noi_dung_nhac: str, thoi_gian: str, escalate: bool = False) -> str:
        """
        Lên lịch một thông báo nhắc nhở.
        (SỬA LỖI V94 - THÊM TIMESTAMP)
        """
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic") 
        user_id_str = cl.user_session.get("user_id_str") 
        
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy llm_logic." 
        if not user_id_str: return "❌ LỖI: Không tìm thấy 'user_id_str'. Vui lòng F5."
        
        try:
            ensure_scheduler()
            dt_when = None 
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."
            
            noti_text = (noi_dung_nhac or "").strip()
            if not noti_text: return "❌ Lỗi: Cần nội dung nhắc."
            
            facts_list = await _extract_fact_from_llm(llm, noti_text)
            
            # (SỬA LỖI V94) Lấy timestamp 1 lần
            current_timestamp_iso = datetime.now(VN_TZ).isoformat()
            
            # (SỬA LỖI V94) Metadata chung
            common_metadata = {
                "file_type": "text", # Giả định là text
                "timestamp": current_timestamp_iso
            }

            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if repeat_sec > 0:
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                job_id = f"reminder-interval-{user_id_str}-{uuid.uuid4().hex[:6]}"
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60)
                
                texts_to_save = [f"[REMINDER_INTERVAL] every={repeat_sec}s | {noti_text} | job_id={job_id}"] + facts_list
                # (SỬA LỖI V94) Thêm metadatas
                metadatas_to_save = [common_metadata.copy() for _ in texts_to_save]
                await asyncio.to_thread(vectorstore.add_texts, texts=texts_to_save, metadatas=metadatas_to_save)
                
                return f"🔁 ĐÃ LÊN LỊCH LẶP: '{noti_text}' • mỗi {repeat_sec} giây"
            
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                job_id = f"reminder-cron-{user_id_str}-{uuid.uuid4().hex[:6]}"
                SCHEDULER.add_job(_do_push, trigger=cron["trigger"], id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60)
                
                texts_to_save = [f"[REMINDER_CRON] type={cron['type']} | {thoi_gian} | {noti_text} | job_id={job_id}"] + facts_list
                # (SỬA LỖI V94) Thêm metadatas
                metadatas_to_save = [common_metadata.copy() for _ in texts_to_save]
                await asyncio.to_thread(vectorstore.add_texts, texts=texts_to_save, metadatas=metadatas_to_save)
                
                return f"📅 ĐÃ LÊN LỊCH ({cron['type']}): '{noti_text}' • {thoi_gian}"
            
            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian)
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
            
            if escalate:
                job_id = f"first-{user_id_str}-{uuid.uuid4().hex[:6]}"
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_first_fire_escalation_job, trigger=trigger, id=job_id, args=[user_id_str, noti_text, 5], replace_existing=False, misfire_grace_time=60)
                
                texts_to_save = [f"[REMINDER_ESCALATE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"] + facts_list
                # (SỬA LỖI V94) Thêm metadatas
                metadatas_to_save = [common_metadata.copy() for _ in texts_to_save]
                await asyncio.to_thread(vectorstore.add_texts, texts=texts_to_save, metadatas=metadatas_to_save)
                
                return f"⏰ ĐÃ LÊN LỊCH (Leo thang): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
            else:
                job_id = f"reminder-{user_id_str}-{uuid.uuid4().hex[:6]}"
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60)
                
                texts_to_save = [f"[REMINDER_ONCE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"] + facts_list
                # (SỬA LỖI V94) Thêm metadatas
                metadatas_to_save = [common_metadata.copy() for _ in texts_to_save]
                await asyncio.to_thread(vectorstore.add_texts, texts=texts_to_save, metadatas=metadatas_to_save)
                
                return f"⏰ ĐÃ LÊN LỊCH (1 lần): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
        except Exception as e:
            return f"❌ Lỗi khi tạo nhắc: {e}"
        
    # (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3185)
    # (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3213)
    # (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 3213)
    @tool
    async def hoi_thong_tin(cau_hoi: str):
        """
        (SỬA LỖI V96 - TỐI ƯU RAG)
        1. (Cũ - V95) Giữ logic "Ưu tiên" cho 'xem danh muc'.
        2. (MỚI - V96) Khi thực hiện tìm kiếm (SPECIFIC),
        sẽ dùng CÂU HỎI GỐC (ví dụ: 'tôi thích ăn gì?')
        để tìm vector (thay vì dùng CoreQuery 'an gi'),
        giúp tăng độ chính xác của ngữ nghĩa.
        """
        try:
            # --- Lấy các dependencies ---
            llm = cl.user_session.get("llm_logic")
            vectorstore = cl.user_session.get("vectorstore")
            user_id_str = cl.user_session.get("user_id_str")
            
            if not all([llm, vectorstore, user_id_str]):
                return "❌ Lỗi: Thiếu (llm, vectorstore, user_id_str)."

            print(f"[hoi_thong_tin] Đang RAG (Sửa lỗi V96) với query: '{cau_hoi}'")
            
            # --- 🚀 BẮT ĐẦU SỬA LỖI V95 (ƯU TIÊN LỆNH 'DANH MỤC') 🚀 ---
            try:
                q_low_norm = unidecode.unidecode(cau_hoi.lower())
                
                if "danh muc" in q_low_norm and (
                    "xem" in q_low_norm or "tat ca" in q_low_norm or "liet ke" in q_low_norm
                ):
                    print(f"[hoi_thong_tin] (Sửa lỗi V95) PHÁT HIỆN LỆNH ƯU TIÊN: '{cau_hoi}'. Đang chạy logic 'show_category_items'...")
                    
                    fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                    
                    if not fact_dict: return "ℹ️ Bạn chưa lưu danh mục nào (Từ điển fact đang trống)."
                    labels_to_keys = {}
                    for d in fact_dict.values():
                        if isinstance(d, dict) and d.get('label') and d.get('key') != 'danh_muc':
                            labels_to_keys[d.get('label')] = d.get('key')
                        elif isinstance(d, str) and d != 'danh_muc' and d != 'general':
                            label = d.replace("_", " ").title()
                            labels_to_keys[label] = d
                    if not labels_to_keys: return "ℹ️ Bạn chưa lưu danh mục nào (Từ điển fact đang trống)."
                    actions = []
                    for label, key in sorted(labels_to_keys.items()):
                        actions.append(
                            cl.Action(
                                name="show_category_items",
                                label=f"📁 {label}",
                                payload={"fact_key": key, "fact_label": label}
                            )
                        )
                    await cl.Message(
                        content="✅ **Các danh mục (Label) hiện tại của bạn:**\n(Bấm để xem chi tiết)",
                        actions=actions
                    ).send()
                    
                    return "✅ Đã hiển thị danh sách danh mục (Label) dưới dạng nút bấm."
                    
            except Exception as e_prio:
                print(f"⚠️ Lỗi khi check ưu tiên 'danh muc' (V95): {e_prio}. Tiếp tục RAG...")
            # --- 🚀 KẾT THÚC SỬA LỖI V95 🚀 ---


            # --- 🚀 BƯỚC 1: TÌM BỘ LỌC METADATA (file_type) 🚀 ---
            file_type_filter = _build_rag_filter_from_query(cau_hoi) 
            
            # --- 🚀 BƯỚC 2: OPTIMIZATION - FAST PATH (V99) 🚀 ---
            # Nếu câu hỏi là Q&A đơn giản (KHÔNG có từ "danh mục", "tất cả", "file", "ảnh")
            # → SKIP call_llm_to_classify để tăng tốc (tiết kiệm 1-1.5s)
            import re
            q_low = cau_hoi.lower()
            
            # Kiểm tra từ ĐẦY ĐỦ (dùng word boundary) để tránh match nhầm
            has_list_keywords = bool(re.search(r'\b(tat ca|tất cả|toan bo|toàn bộ|danh sach|danh sách|list|ds)\b', q_low))
            
            is_simple_qa = (
                not file_type_filter  # Không hỏi về file/ảnh
                and "danh muc" not in q_low
                and not has_list_keywords  # Không có từ khóa liệt kê
            )
            
            if is_simple_qa:
                # FAST PATH: SKIP phân loại, đi thẳng vector search
                print(f"[hoi_thong_tin] (V99) ⚡ FAST PATH: Q&A đơn giản, SKIP call_llm_to_classify")
                target_fact_key = "general"
                target_fact_label = "General"
                core_search_query = cau_hoi  # Dùng câu hỏi gốc
                is_general_query = False  # Luôn là SPECIFIC (Q&A)
            else:
                # SLOW PATH: Gọi LLM phân loại đầy đủ
                print(f"[hoi_thong_tin] (V99) 🐌 SLOW PATH: Câu hỏi phức tạp, gọi call_llm_to_classify")
                fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                
                print(f"[hoi_thong_tin] B2 (Sửa lỗi V96) Đang gọi V88 (có fact_map) để lấy Key, Label, CoreQuery...")
                
                target_fact_key, target_fact_label, core_search_query = await call_llm_to_classify(
                    llm, cau_hoi, fact_dict
                )
                is_general_query = (core_search_query.upper() == "ALL" or not core_search_query.strip())
            
            # --- 🚀 BƯỚC 3: XỬ LÝ "DANH MUC" (FAST PATH bỏ qua) 🚀 ---
            if not is_simple_qa and target_fact_key == "danh_muc":
                print(f"[hoi_thong_tin] Xử lý đặc biệt cho 'danh_muc' (Fallback V61).")
                fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                if not fact_dict: return "ℹ️ Bạn chưa lưu danh mục nào (Từ điển fact đang trống)."
                labels_to_keys = {}
                for d in fact_dict.values():
                    if isinstance(d, dict) and d.get('label') and d.get('key') != 'danh_muc':
                        labels_to_keys[d.get('label')] = d.get('key')
                    elif isinstance(d, str) and d != 'danh_muc' and d != 'general':
                        label = d.replace("_", " ").title()
                        labels_to_keys[label] = d
                if not labels_to_keys: return "ℹ️ Bạn chưa lưu danh mục nào (Từ điển fact đang trống)."
                actions = []
                for label, key in sorted(labels_to_keys.items()):
                    actions.append(
                        cl.Action(
                            name="show_category_items",
                            label=f"📁 {label}",
                            payload={"fact_key": key, "fact_label": label}
                        )
                    )
                await cl.Message(
                    content="✅ **Các danh mục (Label) hiện tại của bạn:**\n(Bấm để xem chi tiết)",
                    actions=actions
                ).send()
                return "✅ Đã hiển thị danh sách danh mục (Label) dưới dạng nút bấm."
            
            # --- 🚀 BƯỚC 4: XÂY DỰNG BỘ LỌC (SỬA LỖI V90 + THÊM user_id) 🚀 ---
            user_email = cl.user_session.get("user_email", "unknown")
            where_clause = {}
            final_filter_list = [
                {"user_id": user_email}  # LỌC THEO USER TRƯỚC
            ]
            
            is_general_query = (core_search_query.upper() == "ALL" or not core_search_query.strip())
            
            if is_general_query:
                # --- (1) LỌC CHUNG (GENERAL) ---
                print("[hoi_thong_tin] B4 (Sửa lỗi V90): Lọc CHUNG (General). Sẽ dùng fact_key.")
                if file_type_filter: final_filter_list.append(file_type_filter) 
                if target_fact_key and target_fact_key != 'general':
                    final_filter_list.append({'fact_key': target_fact_key})
                    if target_fact_label and target_fact_label.lower() != 'general':
                        final_filter_list.append({'fact_label': target_fact_label})
            else:
                # --- (2) LỌC CỤ THỂ (SPECIFIC) ---
                print("[hoi_thong_tin] B4 (Sửa lỗi V90): Lọc CỤ THỂ (Specific). SẼ KHÔNG dùng fact_key.")
                if file_type_filter: final_filter_list.append(file_type_filter)
            
            print(f"[hoi_thong_tin] B4: Bộ lọc metadata (V90) cuối cùng: {final_filter_list}")
            
            if len(final_filter_list) > 1: where_clause = {"$and": final_filter_list}
            elif len(final_filter_list) == 1: where_clause = final_filter_list[0]
            else: where_clause = None
            final_where_for_chroma = where_clause if where_clause else None

            # --- 🚀 BƯỚC 5: THỰC THI (Logic cũ) 🚀 ---
            if is_general_query:
                # --- BƯỚC 5a (GENERAL) ---
                print(f"[hoi_thong_tin] B5a (GENERAL): Đang gọi display_interactive_list (vì CoreQuery là 'ALL').")
                if not target_fact_label: target_fact_label = target_fact_key.replace("_", " ").title()
                
                found = await display_interactive_list(
                    where_clause=final_where_for_chroma, 
                    title=f"Danh sách các mục trong: {target_fact_label} (Key: {target_fact_key})"
                )
                return f"✅ Đã hiển thị {found} mục tìm thấy cho danh mục '{target_fact_label}'."
            else:
                
                # --- 🚀 BẮT ĐẦU SỬA LỖI V96 (THEO YÊU CẦU CỦA BẠN) 🚀 ---
                
                # --- BƯỚC 5b (SPECIFIC) (SỬA LỖI V96) ---
                # (Logic V96: Dùng 'cau_hoi' (gốc) để tìm vector
                #  vì nó giàu ngữ nghĩa hơn 'core_search_query'.)
                search_vector_query = cau_hoi 
                print(f"[hoi_thong_tin] B5b (SPECIFIC / Sửa lỗi V96): Đang tìm vector BẰNG CÂU HỎI GỐC: '{search_vector_query}'")
                # (Log 'core_search_query' chỉ để debug)
                print(f"[hoi_thong_tin] (Debug V96) CoreQuery (chỉ để lọc) là: '{core_search_query}'")
                
                # --- 🚀 KẾT THÚC SỬA LỖI V96 🚀 ---

                final_where_doc_for_chroma = None 
                print(f"[hoi_thong_tin] B5c (Sửa lỗi V96): Passing to Chroma: (Query: '{search_vector_query}', Where: {final_where_for_chroma}, Where_Doc: {final_where_doc_for_chroma})")
                
                query_vector = await asyncio.to_thread(embeddings.embed_query, search_vector_query)
                results = await asyncio.to_thread(
                    vectorstore._collection.query,
                    query_embeddings=[query_vector],
                    n_results=20, 
                    where=final_where_for_chroma, 
                    where_document=final_where_doc_for_chroma, 
                    include=["documents", "metadatas"] 
                )
                
                docs_goc_content = results.get("documents", [[]])[0] 
                docs_goc_metadatas = results.get("metadatas", [[]])[0] 
                ids_goc = results.get("ids", [[]])[0] 
                
                if not docs_goc_content:
                    return f"ℹ️ Đã tìm (Query V96: '{search_vector_query}', Filter: Where={final_where_for_chroma}) nhưng không tìm thấy."
                
                final_results_to_display = _helper_sort_results_by_timestamp(
                    ids_goc, docs_goc_content, docs_goc_metadatas
                )
                print(f"[hoi_thong_tin] (Sửa lỗi V94) Đã sắp xếp {len(final_results_to_display)} kết quả bằng helper (mới nhất lên đầu).")
                
                # --- B6. PHÂN LOẠI HIỂN THỊ (SỬA LỖI V91) ---
                has_text_in_final_results = False
                for _, content, metadata in final_results_to_display:
                    file_type = "text" 
                    if metadata: 
                        file_type = metadata.get("file_type", "text")
                    else:
                        print("⚠️ [hoi_thong_tin] B6 (Sửa lỗi V91): Phát hiện metadata=None, giả định là 'text'.")
                    if file_type == "text":
                        has_text_in_final_results = True
                        break 
                
                # B7. QUYẾT ĐỊNH HIỂN THỊ
                if bool(file_type_filter) and not has_text_in_final_results:
                    candidates_for_llm_filter = []
                    for doc_id, _, metadata in final_results_to_display: 
                        if not metadata: continue 
                        file_type = metadata.get("file_type", "text")
                        if file_type == "text": continue 
                        content = metadata.get("original_content")
                        if not content: continue
                        try:
                            name_match = re.search(r"name=([^|]+)", content)
                            note_match = re.search(r"note=([^|]+)", content)
                            goc_name = name_match.group(1).strip() if name_match else "N/A"
                            goc_note = note_match.group(1).strip() if note_match else "(không ghi chú)"
                            candidates_for_llm_filter.append({
                                "id": doc_id, "name": goc_name, "note": goc_note, "metadata": metadata 
                            })
                        except Exception: continue 
                    print(f"[hoi_thong_tin] B7: Đã có {len(candidates_for_llm_filter)} ứng viên file/ảnh. Đang gọi LLM Filter (Selection)...")
                    
                    final_filtered_results = await asyncio.to_thread(
                        _llm_filter_for_selection, llm, cau_hoi, candidates_for_llm_filter
                    )
                    
                    print(f"[hoi_thong_tin] B7 (Sửa lỗi): Hiển thị {len(final_filtered_results)} (Đã qua LLM Filter).")
                    
                    if not final_filtered_results:
                        return f"ℹ️ Đã tìm thấy {len(candidates_for_llm_filter)} ứng viên, nhưng Bộ lọc LLM (Smart Filter) đã loại bỏ chúng (vì không khớp TÊN file)."
                    
                    # V102: Phân loại ảnh theo fact_key và file
                    from collections import defaultdict
                    images_by_fact_key = defaultdict(list)
                    files = []
                    
                    for item in final_filtered_results:
                        doc_id = item['id']; metadata = item['metadata']
                        content = metadata.get("original_content"); file_type = metadata.get("file_type", "file")
                        fact_key = metadata.get("fact_key", None)  # Lấy fact_key từ metadata
                        
                        # Debug: In ra fact_key để kiểm tra
                        print(f"[DEBUG] doc_id={doc_id}, fact_key={fact_key}, file_type={file_type}")
                        
                        try:
                            path_match = re.search(r"path=([^|]+)", content)
                            name_match = re.search(r"name=([^|]+)", content)
                            note_match = re.search(r"note=([^|]+)", content)
                            if not path_match: continue
                            
                            full_path = path_match.group(1).strip()
                            saved_name = os.path.basename(full_path)
                            goc_name = name_match.group(1).strip() if name_match else "N/A"
                            goc_note = note_match.group(1).strip() if note_match else "(không ghi chú)"
                            
                            # Nếu không có fact_key, dùng tên file làm key
                            if not fact_key:
                                fact_key = goc_name
                            
                            if file_type == 'image':
                                # Group ảnh theo fact_key
                                images_by_fact_key[fact_key].append({
                                    "doc_id": doc_id,
                                    "path": full_path,
                                    "name": goc_name,
                                    "note": goc_note,
                                    "saved_name": saved_name,
                                    "fact_key": fact_key
                                })
                            else:
                                files.append({
                                    "doc_id": doc_id,
                                    "path": full_path,
                                    "name": goc_name,
                                    "note": goc_note,
                                    "file_type": file_type,
                                    "saved_name": saved_name
                                })
                        except Exception as e_parse:
                            print(f"[hoi_thong_tin] Lỗi parse item: {e_parse}")
                            continue
                    
                    # V102: Hiển thị mỗi fact_key thành 1 album riêng
                    print(f"[DEBUG] Tổng số fact_key groups: {len(images_by_fact_key)}")
                    for fact_key, images_list in images_by_fact_key.items():
                        print(f"[DEBUG] fact_key='{fact_key}', số ảnh={len(images_list)}")
                        
                        if len(images_list) >= 2:
                            # Chuẩn bị dữ liệu cho ImageGrid
                            images_data = []
                            actions = []
                            for img in images_list:
                                # Skip nếu file không tồn tại
                                if not os.path.exists(img['path']):
                                    print(f"[WARNING] File không tồn tại, skip: {img['path']}")
                                    continue
                                    
                                safe_href = f"/public/files/{img['saved_name']}"
                                images_data.append({
                                    "name": img['name'],
                                    "note": img['note'],
                                    "url": safe_href,
                                    "path": img['path'],
                                    "doc_id": img['doc_id'],
                                    "file_path": img['path']
                                })
                                
                                # Hidden action cho delete
                                actions.append(cl.Action(
                                    name="delete_file",
                                    value="delete",
                                    payload={"doc_id": img['doc_id'], "file_path": img['path']},
                                    label=f"DEL_{img['doc_id']}",
                                    description=f"Delete {img['name']}"
                                ))
                            
                            # Tên album: Nếu fact_key giống tên file đầu tiên -> dùng tên đó, không thì format
                            if fact_key == images_list[0]['name']:
                                fact_label = fact_key  # Dùng tên file gốc
                            else:
                                fact_label = fact_key.replace("_", " ").title()
                            
                            print(f"[DEBUG] Hiển thị album: '{fact_label}' với {len(images_list)} ảnh")
                            
                            # Gửi ImageGrid custom element
                            el = cl.CustomElement(
                                name="ImageGrid",
                                props={"title": f"📸 {fact_label} ({len(images_list)} ảnh)", "images": images_data},
                                display="inline",
                            )
                            await cl.Message(content="", elements=[el]).send()
                            
                            # Gửi actions riêng cho từng ảnh trong album
                            for idx, img in enumerate(images_list, 1):
                                msg = cl.Message(content=f"_{idx}. {img['name']}_")
                                msg.actions = [
                                    cl.Action(name="delete_file", payload={"doc_id": img['doc_id'], "file_path": img['path']}, label=f"🗑️ {idx}"),
                                    cl.Action(name="edit_item_placeholder", payload={"doc_id": img['doc_id']}, label=f"✏️ {idx}")
                                ]
                                await msg.send()
                        elif len(images_list) == 1:
                            # 1 ảnh: hiển thị bình thường
                            img = images_list[0]
                            safe_href = f"/public/files/{img['saved_name']}"
                            safe_name = html.escape(img['name'])
                            
                            msg = cl.Message(
                                content=f"**{safe_name}** [IMAGE]\n![{safe_name}]({safe_href})\n• Ghi chú: *{img['note']}*\n• ID: `{img['doc_id']}`"
                            )
                            msg.actions = [
                                cl.Action(name="delete_file", payload={"doc_id": img['doc_id'], "file_path": img['path']}, label="🗑️ Xóa"),
                                cl.Action(name="edit_item_placeholder", payload={"doc_id": img['doc_id']}, label="✏️ Sửa")
                            ]
                            await msg.send()
                    
                    # Hiển thị files (nếu có)
                    for f in files:
                        safe_href = f"/public/files/{f['saved_name']}"
                        safe_name = html.escape(f['name'])
                        
                        msg = cl.Message(
                            content=f"**[{safe_name}]({safe_href})** [{f['file_type'].upper()}]\n• Ghi chú: *{f['note']}*\n• ID: `{f['doc_id']}`"
                        )
                        msg.actions = [
                            cl.Action(name="delete_file", payload={"doc_id": f['doc_id'], "file_path": f['path']}, label="🗑️ Xóa"),
                            cl.Action(name="edit_item_placeholder", payload={"doc_id": f['doc_id']}, label="✏️ Sửa")
                        ]
                        await msg.send()
                    
                    # Return rỗng để Agent không hiển thị thêm message
                    return ""
                
                else: 
                    print(f"[hoi_thong_tin] B7 (Sửa lỗi V93): Gửi {len(final_results_to_display)} context (ĐÃ SẮP XẾP) cho RAG Q&A (Prompt V93)...")
                    
                    final_context_list = [content for _, content, _ in final_results_to_display if content]
                    context_tho = "\n---\n".join(final_context_list)
                    if not context_tho.strip(): return "ℹ️ Đã lọc, nhưng nội dung của chúng bị rỗng."
                    
                    print(f"[hoi_thong_tin] B8: Gửi context ({len(context_tho)} chars) cho LLM để TRẢ LỜI...")
                    
                    custom_prompt = f"""
                    Bạn là một trợ lý thông tin CỰC KỲ THÔNG MINH. Nhiệm vụ của bạn là trả lời câu hỏi của người dùng (Input) dựa trên (Context).

                    Context:
                    {context_tho}
                    
                    Input: {cau_hoi}

                    QUY TẮC PHÂN TÍCH (RẤT QUAN TRỌNG):
                    1. Context đã được SẮP XẾP THEO THỜI GIAN. 
                    Thông tin MỚI NHẤT nằm ở TRÊN CÙNG (Đầu tiên).
                    2. Nếu Context chứa thông tin MÂU THUẪN (ví dụ: "tôi thích ăn phở" VÀ "tôi thích ăn bún bò"), 
                    hãy ƯU TIÊN TUYỆT ĐỐI thông tin đầu tiên (mới nhất).
                    3. Chỉ trả lời dựa trên thông tin MỚI NHẤT (Đầu tiên) nếu có mâu thuẫn.
                    4. Nếu context không có thông tin, hãy nói "Tôi không tìm thấy thông tin này trong context."

                    Ví dụ Context (Đã sắp xếp):
                    tôi CHỈ thích ăn phở
                    ---
                    tôi thích ăn bún bò
                    ---
                    tôi thích ăn cơm
                    
                    Input: tôi thích ăn gì?
                    Câu trả lời (ĐÚNG): Bạn CHỈ thích ăn phở.
                    
                    Input: {cau_hoi}
                    Câu trả lời (dựa trên thông tin MỚI NHẤT):
                    """
                    
                    resp = await llm.ainvoke(custom_prompt)
                    llm_answer = resp.content.strip()
                    
                    if not llm_answer or "không có thông tin" in llm_answer.lower() or "không tìm thấy" in llm_answer.lower():
                        print(f"LLM RAG Q&A (V93) trả về không có gì: {llm_answer}")
                        return f"ℹ️ Tôi tìm thấy {len(final_results_to_display)} mục liên quan, nhưng không tìm thấy câu trả lời chính xác cho '{cau_hoi}' trong đó."
                    else:
                        return llm_answer
                    
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi RAG (Sửa lỗi V96): {e}"
    
    @tool
    async def xem_lich_nhac() -> str:
        """
        Hiển thị tất cả các lịch nhắc (reminders)
        đang hoạt động trong UI.
        """
        try: await ui_show_active_reminders()
        except Exception as e: return f"❌ Lỗi khi hiển thị lịch: {e}"
        return "✅ Đã liệt kê các lịch nhắc đang hoạt động."
 
    @tool("tim_kiem_file")
    async def tim_kiem_file(tu_khoa: str):
        """
        🔍 TÌM KIẾM file/ảnh cụ thể theo TÊN, NĂM, hoặc CHỦ ĐỀ.
        
        ✅ DÙNG KHI user muốn TÌM file CỤ THỂ:
        - "cho tôi file 2022" → tu_khoa = "2022"
        - "cho tôi file ds 2022" → tu_khoa = "ds 2022"
        - "tìm ảnh du lịch" → tu_khoa = "du lịch"
        - "file báo cáo tháng 5" → tu_khoa = "báo cáo tháng 5"
        
        ❌ KHÔNG DÙNG khi user muốn xem TẤT CẢ file (dùng xem_danh_sach_file)
        
        Trả về file/ảnh khớp nhất (có LLM smart filter).
        """
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic")
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy LLM."
        
        try:
            # B1. TÌM bằng Python filter (dùng hàm có sẵn)
            candidates = await asyncio.to_thread(
                _find_files_by_name_db, vectorstore, tu_khoa
            )
            
            if not candidates:
                return f"⚠️ Không tìm thấy file/ảnh nào khớp với '{tu_khoa}'."
            
            # B2. Nếu có NHIỀU kết quả → LLM lọc chọn 1
            if len(candidates) > 1:
                print(f"[tim_kiem_file] Tìm thấy {len(candidates)} candidates, dùng LLM chọn best match...")
                
                list_str = "\n".join([
                    f"{i+1}. {c.get('original_name', 'Unknown')} (timestamp: {c.get('timestamp', 'N/A')})"
                    for i, c in enumerate(candidates[:10])  # Chỉ show 10 đầu
                ])
                
                filter_prompt = f"""User tìm kiếm: "{tu_khoa}"

Danh sách file tìm thấy:
{list_str}

Chọn file KHỚP NHẤT (trả về số thứ tự 1-{min(len(candidates), 10)}). 
Nếu không chắc chắn, chọn file CÓ NĂM/NGÀY khớp hoặc tên gần giống nhất.
Chỉ trả về 1 số, không giải thích."""

                resp = await llm.ainvoke(filter_prompt)
                choice_text = resp.content.strip()
                
                try:
                    choice_idx = int(choice_text) - 1
                    if 0 <= choice_idx < len(candidates):
                        best_match = candidates[choice_idx]
                        print(f"[tim_kiem_file] LLM chọn #{choice_idx+1}: {best_match.get('original_name')}")
                    else:
                        print(f"[tim_kiem_file] LLM trả về index ngoài range, lấy đầu tiên")
                        best_match = candidates[0]
                except:
                    print(f"[tim_kiem_file] LLM không trả về số, lấy đầu tiên")
                    best_match = candidates[0]
            else:
                best_match = candidates[0]
            
            # B3. Trả về link/ảnh
            saved_path = best_match.get("file_path", "")
            original_name = best_match.get("original_name", tu_khoa)
            is_image = best_match.get("type") == "[IMAGE]"
            
            if not saved_path:
                return f"❌ Không tìm thấy đường dẫn file cho '{original_name}'."
            
            # V100: FIX - Nếu file thiếu extension, copy sang tên mới
            orig_ext = os.path.splitext(original_name)[1]
            if orig_ext and not saved_path.endswith(orig_ext):
                # File hiện tại thiếu extension → Copy sang file mới
                saved_path_with_ext = saved_path + orig_ext
                
                if os.path.isfile(saved_path) and not os.path.exists(saved_path_with_ext):
                    try:
                        import shutil
                        shutil.copy2(saved_path, saved_path_with_ext)
                        print(f"[tim_kiem_file] V100: Đã copy file sang tên có extension: {saved_path_with_ext}")
                        saved_path = saved_path_with_ext
                    except Exception as e:
                        print(f"[tim_kiem_file] V100: Lỗi khi copy file: {e}")
                elif os.path.exists(saved_path_with_ext):
                    # File có extension đã tồn tại
                    saved_path = saved_path_with_ext
            
            # DEBUG: Log path để kiểm tra
            print(f"[tim_kiem_file] DEBUG: saved_path='{saved_path}'")
            print(f"[tim_kiem_file] DEBUG: os.path.isfile()={os.path.isfile(saved_path) if saved_path else False}")
            
            if not os.path.isfile(saved_path):
                return f"❌ File '{original_name}' không tồn tại (path: {saved_path})."
            
            # V100: Dùng Chainlit Element thay vì Markdown link để tránh ZIP
            try:
                # Tạo Chainlit File element với tên file gốc
                file_element = cl.File(
                    name=original_name,  # Tên file gốc (có extension)
                    path=saved_path,     # Path đầy đủ
                    display="inline"     # Hiển thị inline
                )
                
                # Gửi file element
                await cl.Message(
                    content=f"Tìm thấy file: **{original_name}**",
                    elements=[file_element]
                ).send()
                
                # Return rỗng để Agent không hiển thị thêm message
                return ""
                
            except Exception as e:
                # Fallback: Dùng URL cũ nếu Element lỗi
                print(f"[tim_kiem_file] Lỗi tạo File element: {e}")
                saved_name = os.path.basename(saved_path)
                file_url = f"/public/files/{saved_name}"
                safe_name = html.escape(original_name)
                
                if is_image:
                    return f"Tìm thấy ảnh: \n![{safe_name}]({file_url})"
                else:
                    return f"Tìm thấy file: **[{safe_name}]({file_url})**"
                
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi khi tìm file (V98): {e}"

    # (THAY THẾ CLASS NÀY - khoảng dòng 3515)
    class XoaFileSchema(BaseModel):
        noi_dung_can_xoa: str = Field(..., description="Nội dung hoặc tên của file/ảnh (để XÓA)")

    # (THAY THẾ TOÀN BỘ HÀM NÀY - khoảng dòng 3521)
    @tool("xoa_file_da_luu", args_schema=XoaFileSchema)
    async def xoa_file_da_luu(noi_dung_can_xoa: str) -> str:
        """
        (SỬA) Tìm và HIỂN THỊ TẤT CẢ file/ảnh đã lưu khớp
        với nút xóa riêng cho từng mục (giống xoa_ghi_chu).
        (SỬA: Hiển thị preview ảnh nếu là [IMAGE])
        """
        vectorstore = cl.user_session.get("vectorstore")
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."

        # B1. TÌM (Dùng hàm Python + unidecode)
        # --- 🚀 SỬA: Dùng biến mới 🚀 ---
        files_found = await asyncio.to_thread(
            _find_files_by_name_db, vectorstore, noi_dung_can_xoa
        )
        
        if not files_found:
            # --- 🚀 SỬA: Dùng biến mới 🚀 ---
            return f"ℹ️ Không tìm thấy file/ảnh nào khớp với '{noi_dung_can_xoa}'."
            
        # B2. HIỂN THỊ (Gửi tin nhắn thông báo)
        await cl.Message(
            # --- 🚀 SỬA: Dùng biến mới 🚀 ---
            content=f"✅ Tôi tìm thấy {len(files_found)} file/ảnh khớp với '{noi_dung_can_xoa}':"
        ).send()
        
        # --- 🚀 KẾT THÚC SỬA 🚀 ---
        
        # B3. LẶP VÀ GỬI TỪNG MỤC (Code bên dưới giữ nguyên)
        for item in files_found:
            doc_id = item['doc_id']
            file_path = item['file_path']
            content = item['original_name']
            
            # 3a. (MỚI) Chuẩn bị hiển thị (Markdown)
            safe_href = f"/public/files/{item['saved_name']}"
            safe_name = html.escape(content)
            display_content = ""

            if item['type'] == '[IMAGE]':
                # (MỚI) Hiển thị TÊN + ẢNH
                display_content = f"**{safe_name}** [IMAGE]\n![{safe_name}]({safe_href})"
            else:
                # (CŨ) Chỉ hiển thị TÊN
                display_content = f"**{safe_name}** [FILE]"

            # 3b. Tạo tin nhắn (chưa gửi)
            # (SỬA) Dùng display_content
            msg = cl.Message(
                content=f"{display_content}\n• Ghi chú: *{item['note']}*"
            )
            
            # 3c. Tạo nút Xóa (Trỏ về callback 'delete_file' đã có)
            actions = [
                cl.Action(
                    name="delete_file", # <-- Gọi callback 'delete_file' đã có
                    payload={"doc_id": doc_id, "file_path": file_path, "message_id": msg.id},
                    label="🗑️ Xóa file này"
                )
            ]
            
            # 3d. Gán action và gửi
            msg.actions = actions
            await msg.send()
            
        # B4. Trả về thông báo cho Agent
        return f"✅ Đã hiển thị {len(files_found)} kết quả khớp với các nút xóa."
    
    
    @tool("xem_danh_sach_file")
    async def xem_danh_sach_file() -> str:
        """
        ⚠️ QUAN TRỌNG: CHỈ dùng khi user muốn xem TẤT CẢ file KHÔNG LỌC.
        
        SỬ DỤNG KHI:
        - "xem tất cả file"
        - "show all files/images"
        - "danh sách đầy đủ"
        
        ❌ KHÔNG DÙNG KHI:
        - Có BẤT KỲ từ khóa lọc nào (năm, tên, chủ đề): "file 2022", "ảnh du lịch", "ds 2022"
        - User muốn TÌM file cụ thể → Dùng `tim_kiem_file` thay thế
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
    # (THAY THẾ CLASS NÀY - khoảng dòng 4316)
    class DatLichCongViecSchema(BaseModel):
        noi_dung: str = Field(..., description="Nội dung công việc, ví dụ: 'Hoàn thành báo cáo'")
        thoi_gian: str = Field(..., description="Thời gian đến hạn: '1 phút nữa', '20:15', 'mai 8h', 'thứ 3 hàng tuần 9h'")
        mo_ta: Optional[str] = Field(None, description="Mô tả chi tiết cho công việc")
        # --- 🚀 THÊM DÒNG NÀY (SỬA LỖI V90) 🚀 ---
        repeat_until_completed_min: Optional[int] = Field(None, description="Nếu đặt (ví dụ: 30), sẽ nhắc lại mỗi 30 phút cho đến khi được đánh dấu 'hoàn thành'.")

    # (THAY THẾ HÀM NÀY - khoảng dòng 4330)
    @tool(args_schema=DatLichCongViecSchema)
    async def dat_lich_cong_viec(
        noi_dung: str, 
        thoi_gian: str, 
        mo_ta: Optional[str] = None,
        repeat_until_completed_min: Optional[int] = None # <-- NHẬN THAM SỐ MỚI
    ) -> str:
        """
        Lên lịch một CÔNG VIỆC (task) cần hoàn thành.
        Công việc này có thể được xem và đánh dấu 'hoàn thành'.
        (SỬA LỖI V90: Hỗ trợ lặp lại cho đến khi hoàn thành).
        """
        user_id_str = cl.user_session.get("user_id_str")
        internal_session_id = cl.user_session.get("chainlit_internal_id")
        
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic")
        
        if not user_id_str or not internal_session_id:
            return "❌ Lỗi: Mất user_id hoặc internal_session_id. Vui lòng F5."
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy llm_logic."
            
        try:
            ensure_scheduler()
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."

            task_text = (noi_dung or "").strip()
            if not task_text: return "❌ Lỗi: Cần nội dung công việc."
            
            dt_when = None
            recurrence_rule = None
            trigger = None
            job_id_suffix = f"{internal_session_id}-{uuid.uuid4().hex[:6]}"
            
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                recurrence_rule = f"cron:{cron['type']}:{thoi_gian}"
                trigger = cron["trigger"]
                # (SỬA LỖI V90) Không thể dùng lặp lại (cron) 
                # VÀ lặp cho đến khi hoàn thành (repeat_min)
                if repeat_until_completed_min:
                    return f"❌ Lỗi: Bạn không thể dùng 'lặp lại hàng tuần/tháng' ({thoi_gian}) CÙNG LÚC với 'nhắc lại mỗi {repeat_until_completed_min} phút'."
                
                temp_job = SCHEDULER.add_job(_do_push, trigger=trigger, id=f"temp-{job_id_suffix}")
                dt_when = temp_job.next_run_time
                SCHEDULER.remove_job(temp_job.id)
            
            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if not dt_when and repeat_sec > 0:
                recurrence_rule = f"interval:{repeat_sec}s"
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                dt_when = datetime.now(VN_TZ) + timedelta(seconds=repeat_sec)
                
                if repeat_until_completed_min:
                    return f"❌ Lỗi: Bạn không thể dùng 'lặp lại mỗi {repeat_sec} giây' CÙNG LÚC với 'nhắc lại mỗi {repeat_until_completed_min} phút'."

            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian)
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)

            if not dt_when or not trigger:
                return f"❌ Lỗi: Không thể phân tích thời gian '{thoi_gian}'"

            # (Logic lưu CSDL và Scheduler)
            task_id = await asyncio.to_thread(
                _add_task_to_db, user_id_str, task_text, mo_ta, dt_when, recurrence_rule, None
            )
            job_id = f"taskpush-{task_id}-{job_id_suffix}"
            
            # --- 🚀 BẮT ĐẦU SỬA LỖI V90 (TRUYỀN THAM SỐ) 🚀 ---
            SCHEDULER.add_job(
                _push_task_notification, 
                trigger=trigger, 
                id=job_id, 
                # Truyền repeat_until_completed_min vào args
                args=[internal_session_id, task_text, task_id, repeat_until_completed_min],
                replace_existing=False, 
                misfire_grace_time=60
            )
            # --- 🚀 KẾT THÚC SỬA LỖI V90 🚀 ---
            
            conn = _get_user_db_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE user_tasks SET scheduler_job_id = ? WHERE id = ?", (job_id, task_id))
            conn.commit()
            conn.close()

            # (Logic tạo FACT giữ nguyên)
            try:
                facts_list = await _extract_fact_from_llm(llm, task_text)
                if facts_list:
                    texts_to_save = [task_text] + facts_list
                    await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                    print(f"[Task] Đã lưu FACT cho task: {task_text}")
            except Exception as e_fact:
                print(f"⚠️ Lỗi khi lưu FACT cho task: {e_fact}")

            # (Sửa thông báo trả về)
            msg = f"✅ Đã lên lịch công việc: '{task_text}' (Hạn: {_fmt_dt(dt_when)})"
            if repeat_until_completed_min:
                msg += f" (Sẽ nhắc lại mỗi {repeat_until_completed_min} phút nếu chưa hoàn thành)."
            return msg
            
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
    
    # (DÁN TOOL MỚI NÀY VÀO KHOẢNG DÒNG 4650)
    @tool("tim_cong_viec_theo_ngay", args_schema=TimCongViecSchema)
    async def tim_cong_viec_theo_ngay(thoi_gian: str) -> str:
        """
        (MỚI) Tìm và hiển thị các công việc (tasks) CHƯA HOÀN THÀNH
        dựa trên một khoảng thời gian (ví dụ: 'ngày mai', 'hôm nay').
        """
        llm = cl.user_session.get("llm_logic")
        if not llm:
            return "❌ Lỗi: Không tìm thấy llm_logic."
            
        try:
            # 1. Dùng LLM để lấy ngày
            # (Chúng ta dùng _llm_parse_dt, nó rất giỏi việc này)
            dt_target = await _llm_parse_dt(llm, thoi_gian)
            
            # 2. Xác định khoảng (bắt đầu, kết thúc)
            # (Mặc định là lọc trong 1 ngày)
            start_dt = _get_start_of_day(dt_target)
            end_dt = _get_end_of_day(dt_target)
            
            # (Sửa logic cho "tuần này" hoặc "tháng này" nếu LLM hiểu)
            low_q = thoi_gian.lower()
            now = datetime.now(VN_TZ)
            
            if "tuần này" in low_q or "tuan nay" in low_q:
                start_dt = _get_start_of_day(now - timedelta(days=now.weekday()))
                end_dt = _get_end_of_day(start_dt + timedelta(days=6))
            elif "tháng này" in low_q or "thang nay" in low_q:
                start_dt = _get_start_of_day(now.replace(day=1))
                last_day_num = calendar.monthrange(now.year, now.month)[1]
                end_dt = _get_end_of_day(now.replace(day=last_day_num))
            
            # 3. Gọi hàm UI (đã được nâng cấp)
            await ui_show_uncompleted_tasks(
                start_date=start_dt,
                end_date=end_dt,
                filter_title=thoi_gian
            )
            
            return f"✅ Đã hiển thị các công việc từ {_fmt_dt(start_dt)} đến {_fmt_dt(end_dt)}."

        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi khi tìm công việc: {e}"
    # (DÁN TOOL MỚI NÀY VÀO KHOẢNG DÒNG 4650)
    @tool("tim_cong_viec_qua_han")
    async def tim_cong_viec_qua_han() -> str:
        """
        (MỚI) Tìm và hiển thị các công việc (tasks) CHƯA HOÀN THÀNH
        có ngày HẠN CHÓT (Due Date) ĐÃ QUA (quá hạn).
        """
        now_vn = datetime.now(VN_TZ)
        
        # Lấy ngày hôm nay (00:00:00) làm mốc so sánh
        today_start = _get_start_of_day(now_vn)
        
        try:
            # Gọi hàm UI (đã được nâng cấp) với bộ lọc:
            # - start_date = None (không cần)
            # - end_date = 'Hết ngày hôm qua' (Tất cả việc đến trước hôm nay)
            yesterday_end = _get_end_of_day(now_vn - timedelta(days=1))
            
            await ui_show_uncompleted_tasks(
                start_date=None, # Bỏ qua Start Date
                end_date=yesterday_end, # Lọc tất cả task có Due Date đến hết ngày hôm qua
                filter_title="Quá Hạn"
            )
            
            return "✅ Đã hiển thị các công việc Quá Hạn (có hạn chót đến hết ngày hôm qua)."

        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi khi tìm công việc Quá Hạn: {e}"
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
    
    # (THÊM TOOL MỚI NÀY VÀO ĐÂY - khoảng dòng 2100)
    
    # (MỚI) Định nghĩa tool cơ bản và tool admin
    # (THAY THẾ TOÀN BỘ KHỐI NÀY - khoảng dòng 2290)

    # === MỚI: Định nghĩa Tool bằng Dict (Rule + Tool Object) ===
    
    # === MỚI: Định nghĩa Tool bằng Dict (Rule + Tool Object) ===
    
    base_tools_data = {
        "get_product_detail": {
            "rule": "(CHI TIẾT SP - ƯU TIÊN 1) Nếu 'input' CHỨA mã/model sản phẩm (ví dụ: 'w451', 'H007-001', '541') HOẶC hỏi về *thông tin cụ thể* (ví dụ: 'thông số', 'mô tả', 'ưu điểm') -> Dùng `get_product_detail`",
            "tool": get_product_detail
        },
        "searchlistproductnew": {
            "rule": "(DANH SÁCH SP - ƯU TIÊN 2) Nếu 'input' chỉ hỏi *danh sách chung* (ví dụ: 'danh sách máy cắt cỏ', 'tìm máy khoan') VÀ *KHÔNG* chứa mã/model sản phẩm cụ thể (đã được xử lý ở Ưu tiên 1) -> Dùng `searchlistproductnew`.",
            "tool": searchlistproductnew
        },
        "goi_chart_dashboard": {
            "rule": "(PHÂN TÍCH) Nếu 'input' yêu cầu 'phân tích', 'tóm tắt' báo cáo, 'doanh số', 'dashboard', 'chart' -> Dùng `goi_chart_dashboard`.",
            "tool": goi_chart_dashboard
        },
        "hien_thi_web": {
            "rule": "(NHÚNG) Nếu 'input' yêu cầu 'nhúng', 'hiển thị web', 'mở video' VÀ CHỨA 'http' (VÀ KHÔNG PHẢI LỆNH XÓA) -> Dùng `hien_thi_web`.",
            "tool": hien_thi_web
        },
        "xoa_file_da_luu": {
            "rule": "(XÓA FILE) CHỈ DÙNG KHI 'input' CHỨA TỪ 'xóa' hoặc 'hủy' (theo Master Rule). Ví dụ: 'xóa file 2022' -> Dùng `xoa_file_da_luu`.",
            "tool": xoa_file_da_luu
        },
        "xoa_cong_viec": {
            "rule": "(XÓA CÔNG VIỆC) Nếu 'input' yêu cầu 'xóa công việc', 'hủy task', 'bỏ việc' -> Dùng `xoa_cong_viec`.",
            "tool": xoa_cong_viec
        },
        "xoa_ghi_chu": {
            "rule": "(XÓA GHI CHÚ) Nếu 'input' yêu cầu 'xóa ghi chú', 'xóa note' (VÀ KHÔNG PHẢI 'xóa file') -> Dùng `xoa_ghi_chu`.",
            "tool": xoa_ghi_chu
        },
        "xoa_nhac_nho": {
            "rule": "(XÓA NHẮC NHỞ) Nếu 'input' yêu cầu 'xóa nhắc nhở', 'hủy lịch nhắc', 'bỏ nhắc' -> Dùng `xoa_nhac_nho`.",
            "tool": xoa_nhac_nho
        },
        "luu_thong_tin": {
            "rule": "(LƯU - ƯU TIÊN 1) CHỈ DÙNG nếu 'input' BẮT ĐẦU BẰNG 'lưu:', 'note:', 'save:', 'ghi chú:'."
                    "(Ví dụ: 'lưu: pass server là 123')."
                    "NẾU KHỚP VỚI QUY TẮC NÀY, HÃY CHỌN NGAY LẬP TỨC.",
            "tool": luu_thong_tin
        },
        "dat_lich_cong_viec": {
            "rule": "(TẠO CÔNG VIỆC - ƯU TIÊN 2) Nếu 'input' là 'công việc', 'task' "
                    "(VÀ KHÔNG bắt đầu bằng 'lưu:', 'note:') -> Dùng `dat_lich_cong_viec`.",
            "tool": dat_lich_cong_viec
        },
        "dat_lich_nhac_nho": {
            "rule": "(TẠO NHẮC NHỞ - ƯU TIÊN 2) Nếu 'input' là 'nhắc nhở', 'nhắc tôi', 'đặt lịch' "
                    "(VÀ KHÔNG bắt đầu bằng 'lưu:', 'note:') -> Dùng `dat_lich_nhac_nho`.\n"
                    "   - (Cho Nhắc nhở) Nếu user nói 'nhắc lại' -> đặt `escalate=True`.",
            "tool": dat_lich_nhac_nho
        },
        # (Sửa lỗi V95)
        "hoi_thong_tin": {
            "rule": "(HỎI/LỌC - ƯU TIÊN 1) Dùng cho TẤT CẢ các câu HỎI, TÌM KIẾM CÓ LỌC."
                    "(Ví dụ: 'xem ghi chú server', 'tìm file excel', 'cho tôi pass', 'tôi thích ăn gì?', 'ds file trong cong viec', 'xem ds hình', 'cho ảnh vũng tàu', 'xem danh muc','cho hình','lấy ...','gửi...')."
                    "Tool này là tool HỎI/TÌM chính.",
            "tool": hoi_thong_tin
        },
        "tim_cong_viec_qua_han": {
            "rule": "(LỌC TASK - ƯU TIÊN 1A) Nếu 'input' yêu cầu 'xem công việc', 'xem task' VÀ CÓ TỪ KHÓA 'QUÁ HẠN', 'TRỄ' -> Dùng `tim_cong_viec_qua_han`.",
            "tool": tim_cong_viec_qua_han
        },
        "tim_cong_viec_theo_ngay": {
            "rule": "(LỌC TASK - ƯU TIÊN 1B) Nếu 'input' yêu cầu 'xem công việc', 'xem task' VÀ CÓ LỌC THỜI GIAN (ví dụ: 'ngày mai', 'hôm nay', 'tuần này') -> Dùng `tim_cong_viec_theo_ngay`.",
            "tool": tim_cong_viec_theo_ngay
        },
        "xem_viec_chua_hoan_thanh": {
            "rule": "(XEM TẤT CẢ TASK - ƯU TIÊN 2) Nếu 'input' chỉ yêu cầu 'xem công việc', 'xem checklist' (VÀ KHÔNG CÓ LỌC THỜI GIAN) -> Dùng `xem_viec_chua_hoan_thanh`.",
            "tool": xem_viec_chua_hoan_thanh
        },
        "xem_viec_da_hoan_thanh": {
            "rule": "(XEM TASK ĐÃ XONG - ƯU TIÊN 2) Nếu 'input' yêu cầu 'xem việc ĐÃ HOÀN THÀNH', 'xem việc đã xong' -> Dùng `xem_viec_da_hoan_thanh`.",
            "tool": xem_viec_da_hoan_thanh
        },
        "xem_lich_nhac": {
            "rule": "(XEM LỊCH NHẮC - ƯU TIÊN 2) Nếu 'input' yêu cầu 'xem lịch nhắc', 'xem nhắc nhở' (phân biệt rõ với 'công việc') -> Dùng `xem_lich_nhac`.",
            "tool": xem_lich_nhac
        },
        "xem_bo_nho": {
            "rule": "(XEM NOTE ĐẦY ĐỦ - ƯU TIÊN 2) CHỈ DÙNG nếu 'input' yêu cầu 'TẤT CẢ GHI CHÚ', 'TOÀN BỘ NOTE'."
                    "(Ví dụ: 'xem tất cả ghi chú', 'liệt kê toàn bộ note')."
                    "PHẢI CÓ TỪ 'ghi chú' hoặc 'note'. KHÔNG DÙNG cho 'tất cả danh mục' hay 'tất cả file'.",
            "tool": xem_bo_nho
        },
        "tim_kiem_file": {
            "rule": "(TÌM FILE CỤ THỂ - ƯU TIÊN 1) Nếu 'input' yêu cầu TÌM/LẤY file/ảnh CỤ THỂ với TỪ KHÓA."
                    "(Ví dụ: 'cho tôi file 2022', 'tìm ảnh du lịch', 'file ds 2022', 'lấy file báo cáo')."
                    "DÙNG KHI: Có từ khóa tìm kiếm (năm, tên, chủ đề).",
            "tool": tim_kiem_file
        },
        "xem_danh_sach_file": {
            "rule": "(XEM TẤT CẢ FILE - ƯU TIÊN 2) CHỈ DÙNG nếu 'input' yêu cầu 'TẤT CẢ FILE', 'TOÀN BỘ ẢNH' KHÔNG CÓ TỪ KHÓA LỌC."
                    "(Ví dụ: 'xem tất cả file', 'liệt kê toàn bộ file', 'show all files')."
                    "❌ KHÔNG DÙNG khi có từ khóa lọc: 'file 2022', 'ảnh du lịch', 'ds hình', 'ds file trong công việc' → Dùng `hoi_thong_tin` hoặc `tim_kiem_file`.",
            "tool": xem_danh_sach_file
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
            "rule": "(ADMIN) Nếu 'input' yêu cầu 'tra cứu user HỆ THỐNG' hoặc 'xem thông tin EMAIL CỤ THỂ' (ví dụ: 'check email user@oshima.vn') -> Dùng `lay_thong_tin_user`.",
            "tool": lay_thong_tin_user
        }
    }

    # 1.2. Tạo 1 danh sách tool "phẳng"
    all_tools_list = []
    all_tools_list.extend([data["tool"] for data in base_tools_data.values()])
    
    # 1.3. Lấy cờ admin và gộp tool admin (nếu có)
    is_admin = cl.user_session.get("is_admin", False)
    if is_admin:
        all_tools_list.extend([data["tool"] for data in admin_tools_data.values()])

    # === BƯỚC 2: TẠO "SIÊU PROMPT" (THEO Ý TƯỞNG CỦA BẠN) ===

    # 2.1. Helper để tạo chuỗi quy tắc (phân nhóm)
    def build_rules_string(tools_data_dict):
        return "\n".join([
            f"- {tool_name}: {data['rule']}" 
            for tool_name, data in tools_data_dict.items()
        ])

    # 2.2. Phân loại tool vào các nhóm (để chèn vào prompt)
    ask_tools_data = {
        "get_product_detail": base_tools_data["get_product_detail"],
        "searchlistproductnew": base_tools_data["searchlistproductnew"],
        "goi_chart_dashboard": base_tools_data["goi_chart_dashboard"],
        "hien_thi_web": base_tools_data["hien_thi_web"],
        "hoi_thong_tin": base_tools_data["hoi_thong_tin"],
        "tim_cong_viec_qua_han": base_tools_data["tim_cong_viec_qua_han"],
        "tim_cong_viec_theo_ngay": base_tools_data["tim_cong_viec_theo_ngay"],
        "xem_viec_chua_hoan_thanh": base_tools_data["xem_viec_chua_hoan_thanh"],
        "xem_viec_da_hoan_thanh": base_tools_data["xem_viec_da_hoan_thanh"],
        "xem_lich_nhac": base_tools_data["xem_lich_nhac"],
        "xem_bo_nho": base_tools_data["xem_bo_nho"],
        "tim_kiem_file": base_tools_data["tim_kiem_file"],
        "xem_danh_sach_file": base_tools_data["xem_danh_sach_file"],
    }
    
    save_tools_data = {
        "luu_thong_tin": base_tools_data["luu_thong_tin"],
        "dat_lich_cong_viec": base_tools_data["dat_lich_cong_viec"],
        "dat_lich_nhac_nho": base_tools_data["dat_lich_nhac_nho"],
    }
    
    delete_tools_data = {
        "xoa_file_da_luu": base_tools_data["xoa_file_da_luu"],
        "xoa_cong_viec": base_tools_data["xoa_cong_viec"],
        "xoa_ghi_chu": base_tools_data["xoa_ghi_chu"],
        "xoa_nhac_nho": base_tools_data["xoa_nhac_nho"],
    }
    
    debug_tools_data = {
        "xem_tu_dien_fact": base_tools_data["xem_tu_dien_fact"],
        "push_thu": base_tools_data["push_thu"],
    }
    
    # 2.3. Tạo chuỗi quy tắc cho từng nhóm
    ask_rules = build_rules_string(ask_tools_data)
    save_rules = build_rules_string(save_tools_data)
    delete_rules = build_rules_string(delete_tools_data)
    debug_rules = build_rules_string(debug_tools_data)
    admin_rules = build_rules_string(admin_tools_data) if is_admin else ""

    # 2.4. Tạo "Siêu Prompt" (Prompt chính)
    all_tools_list = []
    all_tools_list.extend([data["tool"] for data in base_tools_data.values()])
    # (Xây dựng các khối Intent dựa trên quyền admin)
    intent_options = ["ASKING", "SAVING", "DELETING", "DEBUG"]
    if is_admin:
        intent_options.append("ADMIN")
        
    intent_list_str = ", ".join([f"'{opt}'" for opt in intent_options])

    admin_block = f"""
== NHÓM 'ADMIN' ==
(Nếu Ý định là 'ADMIN', chỉ chọn 1 tool từ đây)
{admin_rules}
""" if is_admin else ""

    # (Đây là Prompt cuối cùng, thực hiện logic 2 bước của bạn)
    system_prompt_text = f"""
Bạn là một Agent điều phối thông minh.
Nhiệm vụ của bạn là đọc 'input' của người dùng và chọn MỘT tool duy nhất để thực thi.

Hãy làm theo logic 2 BƯỚC sau:

BƯỚC 1: Xác định Ý định (Intent)
Đọc 'input' và xác định xem nó thuộc Ý định nào sau đây: {intent_list_str}.
- 'ASKING': Nếu người dùng HỎI, TÌM, XEM, 'cho tôi', 'lấy cho tôi'.
- 'SAVING': (ƯU TIÊN) Nếu người dùng yêu cầu LƯU, TẠO, hoặc LÊN LỊCH (ví dụ: 'lưu:', 'note:', 'đặt lịch', 'nhắc tôi').
- 'DELETING': Nếu người dùng yêu cầu XÓA, HỦY, BỎ.
- 'ADMIN': Nếu người dùng yêu cầu quản trị HỆ THỐNG (ví dụ: 'danh sách user', 'đổi pass user@...').
- 'DEBUG': Nếu người dùng yêu cầu gỡ lỗi (ví dụ: 'push thử').

BƯỚC 2: Chọn Tool từ Nhóm tương ứng
Sau khi đã xác định Ý định ở Bước 1, hãy chọn MỘT tool từ nhóm quy tắc tương ứng dưới đây.

== NHÓM 'ASKING' ==
(Nếu Ý định là 'ASKING', chỉ chọn 1 tool từ đây)
{ask_rules}

== NHÓM 'SAVING' ==
(Nếu Ý định là 'SAVING', chỉ chọn 1 tool từ đây)
{save_rules}

== NHÓM 'DELETING' ==
(Nếu Ý định là 'DELETING', chỉ chọn 1 tool từ đây)
{delete_rules}
{admin_block}
== NHÓM 'DEBUG' ==
(Nếu Ý định là 'DEBUG', chỉ chọn 1 tool từ đây)
{debug_rules}

QUAN TRỌNG: Chỉ gọi tool. KHÔNG trả lời trực tiếp.
"""
    
    # === BƯỚC 3: TẠO AGENT DUY NHẤT ===
    
    agent_sys_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_text),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(
        llm=llm_logic,
        tools=all_tools_list, # <-- Danh sách phẳng 30+ tool
        prompt=agent_sys_prompt, # <-- Siêu prompt 2 bước
    )
    
    # (Tạo 1 agent duy nhất)
    main_agent_executor = AgentExecutor( 
        agent=agent, 
        tools=all_tools_list, 
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        max_iterations=1 # Vẫn chỉ chạy 1 vòng
    )

    # === BƯỚC 4: LƯU AGENT DUY NHẤT VÀO SESSION ===
    cl.user_session.set("main_agent", main_agent_executor)
    print("✅ [HYBRID AGENT] Đã tạo 1 Agent duy nhất (1 LLM Call) theo logic 2 bước.")

    # (Kết thúc thay thế)
    # ---------------------------------------------------------
    
    # --- 11. Kết thúc (Giữ nguyên) ---
    await cl.Message(
        content="🧠 **Trợ lý (Hybrid V96) đã sẵn sàng**. Hãy nhập câu hỏi để bắt đầu!"
    ).send()
    
    all_elements = cl.user_session.get("elements", [])
    cl.user_session.set("elements", all_elements)
# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 4300, NGAY TRƯỚC @cl.on_message)
# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 4300, 
#  NGAY TRƯỚC HÀM _llm_split_notes)

async def _llm_batch_split_classify(
    llm: ChatOpenAI, 
    user_note: str, 
    num_files: int
) -> List[dict]:
    """
    (MỚI - SỬA LỖI 79)
    Một lệnh gọi GPT duy nhất để TÁCH và PHÂN LOẠI
    cho 'Smart Mode' (khi không có 'vào mục').
    Trả về list of dicts: 
    [{"name": "...", "key": "...", "label": "..."}, ...]
    """
    
    prompt = f"""
    Ghi chú của người dùng: "{user_note}"
    Số lượng file đã upload: {num_files}

    Nhiệm vụ: 
    1. Phân tích Ghi chú để tìm ra ngữ cảnh chung (ví dụ: 'công việc').
    2. Tách Ghi chú thành chính xác {num_files} TÊN (name) riêng lẻ.
    3. Trả về MỖI file trên MỘT DÒNG theo định dạng:
       `Ten file da tach | fact_key (snake_case) | Fact Label (Tieng Viet)`

    QUY TẮC:
    - Phải trả về ĐÚNG {num_files} dòng.
    - PHẢI áp dụng ngữ cảnh chung (ví dụ: 'cong viec') cho TẤT CẢ các dòng.
    - KHÔNG giải thích.

    Ví dụ 1:
    Ghi chú: "luu file ns 2024 và ns 2025 vao cong viec"
    Số lượng file: 2
    Output:
    file ns 2024 | cong_viec | Công Việc
    file ns 2025 | cong_viec | Công Việc

    Ví dụ 2:
    Ghi chú: "anh cccd mat truoc va mat sau vao ho so ca nhan"
    Số lượng file: 2
    Output:
    anh cccd mat truoc | ho_so_ca_nhan | Hồ Sơ Cá Nhân
    anh cccd mat sau | ho_so_ca_nhan | Hồ Sơ Cá Nhân
    
    Ví dụ 3 (Fallback - Không có ngữ cảnh):
    Ghi chú: "hai file linh tinh"
    Số lượng file: 2
    Output:
    hai file linh tinh 1 | general | General
    hai file linh tinh 2 | general | General
    """
    
    results = []
    try:
        resp = await llm.ainvoke(prompt)
        lines = [line.strip() for line in resp.content.strip().split('\n') if line.strip()]
        
        if len(lines) == num_files:
            print(f"✅ [LLM Batch Split] (Sửa lỗi 79) GPT đã tách và phân loại {len(lines)} mục.")
            for line in lines:
                parts = line.split("|")
                if len(parts) >= 3:
                    results.append({
                        "name": parts[0].strip(),
                        "key": parts[1].strip(),
                        "label": parts[2].strip()
                    })
                else:
                    # Lỗi parse dòng
                    results.append({"name": line, "key": "general", "label": "General"})
            return results
        
        # Nếu GPT trả về sai số lượng -> Fallback
        print(f"⚠️ [LLM Batch Split] (Sửa lỗi 79) GPT trả về {len(lines)} dòng (mong đợi {num_files}). Dùng fallback.")

    except Exception as e:
        print(f"❌ Lỗi _llm_batch_split_classify: {e}. Dùng fallback.")

    # Trả về list rỗng để kích hoạt fallback
    return []


async def _llm_split_notes(llm: ChatOpenAI, user_note: str, num_files: int) -> List[str]:
    """
    (MỚI - THEO Ý TƯỞNG CỦA USER)
    Dùng LLM để tách ghi chú chung thành các ghi chú con
    tương ứng với số lượng file.
    """
    # Nếu chỉ có 1 file, không cần tách
    if num_files == 1:
        return [user_note]
        
    prompt = f"""
    Ghi chú của người dùng: "{user_note}"
    Số lượng file đã upload: {num_files}

    Nhiệm vụ: Tách "Ghi chú của người dùng" thành chính xác {num_files} phần ghi chú riêng lẻ, 
    tương ứng với {num_files} file theo đúng thứ tự.

    QUAN TRỌNG:
    - Trả về MỖI ghi chú trên MỘT DÒNG.
    - KHÔNG giải thích.
    - Nếu không thể tách (ví dụ: ghi chú chung chung), 
      hãy lặp lại ghi chú gốc {num_files} lần.

    Ví dụ 1:
    Ghi chú: "luu 2 anh du lich vũng tàu và ha long"
    Số lượng file: 2
    Output:
    anh du lich vung tau
    anh du lich ha long

    Ví dụ 2:
    Ghi chú: "file hop dong, file bao gia"
    Số lượng file: 2
    Output:
    file hop dong
    file bao gia
    
    Ví dụ 3 (Fallback):
    Ghi chú: "ảnh du lịch của tôi"
    Số lượng file: 2
    Output:
    ảnh du lịch của tôi
    ảnh du lịch của tôi
    """
    try:
        resp = await llm.ainvoke(prompt)
        lines = [line.strip() for line in resp.content.strip().split('\n') if line.strip()]
        
        # Kiểm tra: Nếu LLM trả về đúng số lượng
        if len(lines) == num_files:
            print(f"✅ [LLM Split] Đã tách '{user_note}' -> {lines}")
            return lines
            
        # Fallback: Nếu LLM trả về sai
        print(f"⚠️ [LLM Split] Tách thất bại (trả về {len(lines)}), dùng fallback.")
        return [user_note] * num_files 
        
    except Exception as e:
        print(f"❌ Lỗi _llm_split_notes: {e}. Dùng fallback.")
        return [user_note] * num_files
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 4310)
# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 4310)
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 4310)
@cl.on_message
async def on_message(message: cl.Message):
    """
    (SỬA LỖI V95 - HYBRID AGENT)
    1. Xóa logic (Nhánh A/Nhánh B) cũ.
    2. Xóa logic Master Router.
    3. Chỉ gọi 1 Agent duy nhất ('main_agent').
    4. Giữ lại logic xử lý file (nếu có) VÀ logic xử lý Carousel.
    """
    import json
    import traceback
    try:
        # ----- 0) Tiền xử lý (Không đổi) -----
        text = (message.content or "").strip()
        user = cl.user_session.get("user")
        if not user:
            await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất thông tin user. Vui lòng F5.").send()
            return
        user_id_str = user.identifier
        session_id = cl.user_session.get("session_id")
        if not session_id:
            await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất session_id. Vui lòng F5.").send()
            return

        print(f"[on_message] User={user_id_str} Session={session_id} text={text!r}")
        chat_history = cl.user_session.get("chat_history", []) 
        try:
            user_id_str_esc = cl.user_session.get("user_id_str")
            if user_id_str_esc in ACTIVE_ESCALATIONS:
                if not ACTIVE_ESCALATIONS[user_id_str_esc].get("acked"):
                    ACTIVE_ESCALATIONS[user_id_str_esc]["acked"] = True
                    print(f"[Escalation] ACK dừng leo thang cho USER {user_id_str_esc}")
        except Exception as e:
            print(f"[Escalation] Lỗi khi ack: {e}")

        # ----- 3) LOGIC XỬ LÝ (MỚI - V95) -----
        ai_output = None
        loading_msg_to_remove = None
        elements = message.elements or []
        vectorstore = cl.user_session.get("vectorstore")
        
        # 3.1. (MỚI) XỬ LÝ FILE (NẾU CÓ)
        # (Nếu có file, chúng ta vẫn xử lý riêng như V79)
        if elements and vectorstore:
            # NHÁNH A: XỬ LÝ FILE/IMAGE (LOGIC CŨ V79 - KHÔNG ĐỔI)
            try:
                loading_msg_to_remove = await cl.Message(content=f"⏳ Đang xử lý {len(elements)} file/ảnh...").send()
                llm = cl.user_session.get("llm_logic")
                if not llm:
                    ai_output = "❌ Lỗi: Không tìm thấy LLM (llm_logic) khi lưu file."
                else:
                    
                    fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                    saved_files_summary_lines = []
                    num_files = len(elements)
                    
                    notes_for_files = []
                    keys_for_files = []
                    labels_for_files = []
                    clean_names_for_files = []
                    
                    album_match = re.match(r"^(.*?)\s+(vào mục|vào)\s+(.*?)\s*$", text, re.IGNORECASE | re.DOTALL)
                    
                    existing_keys = []
                    for d in fact_dict.values():
                        if isinstance(d, dict):
                            existing_keys.append(d.get('key', 'general'))
                        elif isinstance(d, str):
                            existing_keys.append(d)
                    existing_keys = list(set(existing_keys))
                    
                    if album_match:
                        # --- NHÁNH A.1: CHẾ ĐỘ ALBUM (Giữ nguyên Sửa lỗi 78) ---
                        print(f"✅ [Album Mode] Phát hiện 'vào mục'. Đang gọi LLM phân tích: '{text}'")
                        album_prompt = f"""
Bạn là một trợ lý phân tích. Câu lệnh của người dùng có 2 phần: (A) Tên/ghi chú của file, và (B) Danh mục muốn lưu vào.
Câu lệnh: "{text}"
Ví dụ 1:
Câu lệnh: "lưu ds 2022 vào cong viec cua toi"
Output:
Doanh số 2022 | cong_viec | Công Việc
Ví dụ 2:
Câu lệnh: "anh cccd mt vào thong tin ca nhan"
Output:
Ảnh CCCD mặt trước | thong_tin_ca_nhan | Thông Tin Cá Nhân
Nhiệm vụ: Trả về 3 phần (Tên File Đã Mở Rộng | fact_key | fact_label).
KHÔNG giải thích. Chỉ trả về 1 dòng theo định dạng `Name | Key | Label`.
Output:
"""
                        resp = await llm.ainvoke(album_prompt)
                        raw_output = resp.content.strip().strip("`'\"")
                        summary_name = "File đã lưu"
                        forced_key = "general"
                        forced_label = "General"
                        
                        if "|" in raw_output:
                            parts = raw_output.split("|")
                            if len(parts) >= 3:
                                summary_name = parts[0].strip() or summary_name
                                forced_key = parts[1].strip() or forced_key
                                forced_label = parts[2].strip() or forced_label

                        print(f"✅ [Album Mode] LLM đã phân tích: Key='{forced_key}' | Label='{forced_label}'")
                        try:
                            key_name_raw = album_match.group(3).strip()
                            note_part_raw = album_match.group(1).strip()
                            fact_dict[text.strip().lower()] = {"key": forced_key, "label": forced_label}
                            fact_dict[key_name_raw.strip().lower()] = {"key": forced_key, "label": forced_label}
                            fact_dict[note_part_raw.strip().lower()] = {"key": forced_key, "label": forced_label}
                            print(f"[Album Mode] Đã cập nhật cache (3 keys) cho Key: '{forced_key}'")
                        except Exception: 
                            fact_dict[text.strip().lower()] = {"key": forced_key, "label": forced_label}
                            print(f"[Album Mode] Đã cập nhật cache (1 key) cho Key: '{forced_key}'")

                        keys_for_files = [forced_key] * num_files
                        labels_for_files = [forced_label] * num_files
                        notes_for_files = [text] * num_files 
                        note_part_to_split = album_match.group(1).strip() 
                        print(f"✅ [Album Mode] (Sửa lỗi 78) Đang gọi _llm_split_notes để tách tên từ: '{note_part_to_split}'")
                        clean_names_for_files = await _llm_split_notes(llm, note_part_to_split, num_files)
                        
                        if len(clean_names_for_files) != num_files:
                            clean_names_for_files = [f"{summary_name} ({i+1})" for i in range(num_files)]
                            print(f"⚠️ [Album Mode] (Sửa lỗi 78) Tách tên thất bại, dùng tên chung: '{summary_name}'")

                    else:
                        # --- NHÁNH A.2: CHẾ ĐỘ SMART (SỬA LỖI 79) ---
                        print(f"[Smart Mode] (Sửa lỗi 79) Không phát hiện 'vào mục'. Đang gọi Batch Split...")
                        batch_results = []
                        if text:
                            batch_results = await _llm_batch_split_classify(llm, text, num_files)
                        
                        if batch_results:
                            print("✅ [Smart Mode] (Sửa lỗi 79) Batch Split thành công.")
                            for res in batch_results:
                                clean_names_for_files.append(res["name"])
                                keys_for_files.append(res["key"])
                                labels_for_files.append(res["label"])
                                notes_for_files.append(text)
                                fact_dict[res["name"].strip().lower()] = {"key": res["key"], "label": res["label"]}
                        else:
                            print("⚠️ [Smart Mode] (Sửa lỗi 79) Batch Split thất bại. Quay về logic Fallback (N+1 call).")
                            if text and num_files > 0:
                                notes_for_files = await _llm_split_notes(llm, text, num_files)
                                clean_names_for_files = notes_for_files
                            else:
                                notes_for_files = [os.path.splitext(el.name)[0].replace("-", " ").replace("_", " ") for el in elements]
                                clean_names_for_files = notes_for_files
                            
                            labels_for_files = [] 
                            for temp_note in notes_for_files:
                                temp_note_clean = temp_note.strip().lower()
                                cached_data = fact_dict.get(temp_note_clean)
                                fact_key, fact_label = None, None
                                if isinstance(cached_data, dict):
                                    fact_key = cached_data.get("key"); fact_label = cached_data.get("label")
                                elif isinstance(cached_data, str):
                                    fact_key = cached_data
                                if not fact_key or not fact_label:
                                    fact_key, fact_label, _ = await call_llm_to_classify(llm, temp_note, existing_keys) 
                                    fact_dict[temp_note_clean] = {"key": fact_key, "label": fact_label} 
                                keys_for_files.append(fact_key)
                                labels_for_files.append(fact_label) 
                    
                    # BƯỚC B: LẶP QUA TỪNG FILE (LOGIC V85)
                    for i, (el, user_note_for_file, fact_key_for_file, fact_label_for_file, clean_name_for_file) in enumerate(zip(elements, notes_for_files, keys_for_files, labels_for_files, clean_names_for_files)): 
                        # (THAY THẾ KHỐI LOGIC NÀY - KHOẢNG DÒNG 4468 TRONG on_message)
                        try:
                            display_name = clean_name_for_file
                            if (not text) and (not clean_name_for_file) and num_files > 1:
                                display_name = f"{el.name} ({i+1})"
                            
                            # --- 🚀 BẮT ĐẦU SỬA LỖI V97 (FIX BOOKMARK) 🚀 ---
                            
                            # BƯỚC C.1: KIỂM TRA Ý ĐỊNH (ĐỌC/LƯU)
                            user_intent_text = text.lower()
                            keywords_for_chunking = ["đọc", "doc", "phan tich", "index", "noi dung", "chunk"]
                            
                            # (MỚI) Mặc định là KHÔNG chunk
                            should_chunk_file = False
                            
                            # (MỚI) Chỉ chunk nếu GHI CHÚ GỐC có từ khóa
                            if any(keyword in user_intent_text for keyword in keywords_for_chunking):
                                should_chunk_file = True
                            
                            # (MỚI - V97) KIỂM TRA LOẠI FILE
                            simple_type = _get_simple_file_type(el.mime, el.path)

                            # BƯỚC C.2: CHỌN HÀM PHÙ HỢP
                            
                            if simple_type == "image":
                                # (1) LƯU ẢNH (Không đổi)
                                _, name = await asyncio.to_thread(
                                    _save_image_and_note, 
                                    vectorstore, 
                                    el.path, 
                                    user_note_for_file, # user_text (note=)
                                    display_name,       # original_name (name=)
                                    fact_key_for_file,
                                    fact_label_for_file 
                                )
                                saved_files_summary_lines.append(f"✅ Đã xử lý ảnh: **{name}** (Ghi chú: '{user_note_for_file}' | Label: {fact_label_for_file})")
                            
                            # (SỬA LỖI V97) THÊM 'simple_type != "text"'
                            elif should_chunk_file and simple_type != "text":
                                # (2) LƯU + ĐỌC FILE (Logic cũ - Dành cho file nhỏ)
                                print(f"ℹ️ [Chunker V97] Phát hiện từ khóa '{user_intent_text}'. Đang gọi _load_and_process_document...")
                                chunks, name = await asyncio.to_thread(
                                    _load_and_process_document, 
                                    vectorstore, 
                                    el.path, 
                                    display_name,       # original_name (name=)
                                    el.mime, 
                                    user_note_for_file, # user_note (ghi chú)
                                    fact_key_for_file,
                                    fact_label_for_file
                                )
                                if chunks > 0:
                                    saved_files_summary_lines.append(f"✅ Đã XỬ LÝ & ĐỌC file: **{name}** ({chunks} chunks | Label: {fact_label_for_file})")
                                else:
                                    # (Trường hợp này _load_and_process_document tự gọi _save_file_and_note)
                                    saved_files_summary_lines.append(f"✅ Đã LƯU (nhưng không đọc được): **{name}** (Label: {fact_label_for_file})")
                            
                            else:
                                # (3) (MỚI) CHỈ LƯU FILE (Bookmark)
                                # (Hoặc nếu là file .txt nhưng không có từ khóa 'đọc')
                                if simple_type == "text" and not should_chunk_file:
                                    print(f"ℹ️ [Chunker V97] File .txt nhưng KHÔNG có từ khóa 'đọc'. Chỉ lưu Bookmark...")
                                else:
                                    print(f"ℹ️ [Chunker V97] KHÔNG phát hiện từ khóa. Chỉ gọi _save_file_and_note (Bookmark)...")
                                
                                _, name = await asyncio.to_thread(
                                    _save_file_and_note,
                                    vectorstore,
                                    el.path,
                                    display_name,
                                    user_note_for_file,
                                    fact_key_for_file,
                                    fact_label_for_file,
                                    simple_type
                                )
                                saved_files_summary_lines.append(f"✅ Đã LƯU (Bookmark): **{name}** (Ghi chú: '{user_note_for_file}' | Label: {fact_label_for_file})")

                            # --- 🚀 KẾT THÚC SỬA LỖI V97 🚀 ---
                                    
                        except Exception as e_file:
                            saved_files_summary_lines.append(f"❌ Lỗi xử lý file {getattr(el,'name','?')}: {e_file}")

                    # BƯỚC E: LƯU CACHE (1 LẦN)
                    await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict) 
                    ai_output = (
                        f"**Kết quả xử lý file:**\n\n"
                        + "\n".join(saved_files_summary_lines)
                    )

            except Exception as e_branch_a:
                ai_output = f"❌ Lỗi nghiêm trọng khi xử lý file: {e_branch_a}"
                traceback.print_exc()
        
        else:
            # NHÁNH B: XỬ LÝ TEXT (LOGIC MỚI - V95)
            try:
                loading_msg_to_remove = await cl.Message(author="Trợ lý", content="Đang phân tích...").send()
                
                # 1. Lấy Agent duy nhất
                main_agent = cl.user_session.get("main_agent")
                if not main_agent:
                    ai_output = "❌ Lỗi: Mất Main Agent (V95). Vui lòng F5."
                else:
                    print(f"[Agent V95] B1: Đang gọi Main Agent (1 Call) cho: '{text}'")
                    
                    # 2. Gọi Agent
                    payload = {"input": text}
                    result = await main_agent.ainvoke(payload) 
                    
                    # 3. Lấy kết quả
                    steps = result.get("intermediate_steps") or []
                    if steps and isinstance(steps[-1], tuple) and len(steps[-1]) > 1:
                        obs = steps[-1][1]
                        ai_output = obs.strip() if isinstance(obs, str) and obs.strip() else str(obs)
                    else:
                        ai_output = result.get("output", "⚠️ Không có phản hồi (output rỗng).")
            
            except Exception as e_branch_b:
                ai_output = f"❌ Lỗi gọi agent (V95): {e_branch_b}"
            # --- KẾT THÚC XỬ LÝ TEXT ---

        # ----- 4) TRẢ LỜI & LƯU (Không đổi) -----
        if loading_msg_to_remove:
            await loading_msg_to_remove.remove()
        if ai_output is None:
            ai_output = "⚠️ Lỗi: Bot không tạo ra phản hồi (ai_output is None)."

        # === LOGIC CAROUSEL (Không đổi) ===
        if ai_output.startswith("<CAROUSEL_PRODUCTS>") and ai_output.endswith("</CAROUSEL_PRODUCTS>"):
            try:
                json_string = ai_output.removeprefix("<CAROUSEL_PRODUCTS>").removesuffix("</CAROUSEL_PRODUCTS>")
                data = json.loads(json_string)
                norm_products = data.get("products", []) 
                search_text_from_tool = data.get("search_text_vn", text) 

                if not norm_products:
                    raise ValueError("Không tìm thấy 'products' trong JSON carousel")
                
                title = f"Dưới đây là {len(norm_products)} sản phẩm khớp với '{search_text_from_tool}':"

                el = cl.CustomElement(
                    name="ProductGrid",
                    props={"title": title, "products": norm_products},
                    display="inline",
                )
                await cl.Message(content="", elements=[el]).send()
                ai_output = f"[ProductGrid] Đã hiển thị {len(norm_products)} sản phẩm cho '{search_text_from_tool}'"

            except Exception as e_carousel:
                print(f"❌ Lỗi render Carousel: {e_carousel}")
                traceback.print_exc()
                await cl.Message(content=f"Lỗi hiển thị: {e_carousel}\n\nDữ liệu thô: {ai_output[:500]}...").send()

        elif ai_output.startswith("\n<iframe") and ai_output.endswith("</iframe>\n"):
            await cl.Message(content=ai_output, language="html").send()

        else:
            await cl.Message(content=ai_output).send()

        # Lưu history
        chat_history.append({"role": "user", "content": text})
        chat_history.append({"role": "assistant", "content": ai_output})
        cl.user_session.set("chat_history", chat_history)
        await asyncio.to_thread(save_chat_history, user_id_str, session_id, chat_history)

    except Exception as e_main:
        await cl.Message(content=f"⚠️ Lỗi không mong muốn (main): {e_main}").send()
        import traceback
        traceback.print_exc()

# (Hàm @cl.action_callback("play_video") và các hàm khác giữ nguyên...)
@cl.action_callback("play_video")
async def on_play_video(action: cl.Action):
    """
    Khi người dùng bấm nút '▶ Phát video – {item_code}',
    ta phát đúng video của sản phẩm tương ứng.
    """
    try:
        idx = int(action.value)
        items = cl.user_session.get("last_search_items") or []
        if idx < 0 or idx >= len(items):
            await cl.Message(content="⚠️ Không tìm thấy sản phẩm để phát video.").send()
            return

        it = items[idx]
        vurl = _to_video_url(it.get("video"))
        if not vurl:
            await cl.Message(content="⚠️ Sản phẩm này chưa có video hợp lệ.").send()
            return

        await cl.Message(
            content=f"Video: **{it.get('item_name','')}**",
            elements=[ClVideo(name="Video", url=vurl, display="inline")],
        ).send()

        await action.remove()  # ẩn nút vừa bấm (tùy thích)

    except Exception as e:
        await cl.Message(content=f"❌ Lỗi phát video: {e}").send()        
        
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