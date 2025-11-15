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
# --- 🚀 THÊM DÒNG NÀY (Theo cách của bạn) 🚀 ---
CHART_API_URL = "https://ocrm.oshima.vn/api/method/salesperson" # <-- Khai báo thẳng URL ở đây
# --- 🚀 KẾT THÚC THÊM DÒNG 🚀 ---

CHANGEPASS_API_URL = os.getenv("CHANGEPASS_API_URL", "")

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

# (Ngay dưới CHART_API_URL)
SEARCH_API_URL = "https://ocrm.oshima.vn/api/method/searchlistproductnew" # <-- 🚀 THÊM DÒNG NÀY (Nhớ thay URL nếu cần)

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
# (Dán vào khoảng dòng 130)

# --- 🚀 BẮT ĐẦU: CẤU HÌNH AVATAR HELPER (V47) 🚀 ---

# 1. Định nghĩa Avatar 1 LẦN DUY NHẤT
BOT_AVATAR = cl.Avatar(
    name="Trợ lý", # Tên sẽ hiển thị khi di chuột
    path="/public/bot_avatar.png" # Đường dẫn web (luôn bắt đầu từ /public)
)

async def send_bot_message(
    content: str, 
    actions: list = None, 
    elements: list = None,
    author_name: str = None # (Tùy chọn) Nếu muốn đè tên, vd: "Trợ lý ⏰"
):
    """
    Hàm helper MỚI: Tự động gửi tin nhắn với avatar Bot đã định nghĩa.
    """
    
    # (MỚI) Cho phép đổi tên author nếu cần
    final_avatar = BOT_AVAT
    if author_name:
        final_avatar = cl.Avatar(
            name=author_name,
            path=BOT_AVAT.path 
        )

    # 2. Tạo tin nhắn
    msg = cl.Message(
        content=content,
        author_avatar=final_avatar # <-- Luôn dùng avatar này
    )
    
    # 3. Gán (nếu có)
    if actions:
        msg.actions = actions
    if elements:
        msg.elements = elements
    
    # 4. Gửi
    await msg.send()

# --- 🚀 KẾT THÚC: CẤU HÌNH AVATAR HELPER 🚀 ---

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
    """(NÂNG CẤP) (SYNC) Tìm file/image (không phân biệt dấu) bằng Python.
    (SỬA LỖI: Dùng 'all words' (set.issubset) thay vì 'in' (substring).)"""
    
    # 1. Lấy tất cả file/image từ CSDL
    all_files = list_active_files(vectorstore) # (Hàm này đã có)
    if not all_files:
        return []
    
    found = []
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (Smarter Python Search) 🚀 ---
    
    # 2. Chuẩn bị query words (không dấu, chữ thường, tách riêng)
    # (Biến thành một 'set' các từ)
    safe_query_words = set(unidecode.unidecode(name_query).lower().split())
    if not safe_query_words:
        return []
        
    # 3. Lọc bằng Python
    for file_item in all_files:
        
        # 3a. Lấy tên file (không dấu)
        safe_name = unidecode.unidecode(file_item['original_name']).lower()
        
        # 3b. Lấy ghi chú (không dấu)
        safe_note = unidecode.unidecode(file_item['note']).lower()
        
        # 3c. (MỚI) Gộp tên + ghi chú thành một chuỗi văn bản
        # (Thêm dấu cách để "57dd620.jpg" và "luu" không dính liền)
        searchable_text = safe_name + " " + safe_note
        
        # 3d. (MỚI) Chia nhỏ văn bản thành một 'set' các từ
        searchable_words = set(searchable_text.split())
        
        # 3e. (SỬA) Kiểm tra xem TẤT CẢ query words (is subset)
        #     có nằm trong tập hợp (tên + ghi chú) không.
        if safe_query_words.issubset(searchable_words):
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            found.append(file_item)
            
    print(f"[FileFinder] Đã lọc {len(all_files)} -> còn {len(found)} (Query: '{name_query}')")
    return found

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




def _push_task_notification(internal_session_id: str, task_title: str, task_id: int):
    """(SYNC) Hàm này được Scheduler gọi để push thông báo Task."""
    print(f"[TaskPush] Đang push cho Task ID: {task_id} ({task_title})")
    
    # Chỉ push, không quản lý leo thang
    _do_push(internal_session_id, f"Đến hạn công việc: {task_title}")
# =========================================================
# =========================================================
# 📇 MỚI: Quản lý Từ điển Fact (Fact Dictionary)
# =========================================================
# (DÁN HÀM NÀY VÀO KHOẢNG DÒNG 1078, 
#  NGAY TRƯỚC HÀM get_user_fact_dict_path)

def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')
def get_user_fact_dict_path(user_id_str: str) -> str:
    """Lấy đường dẫn file JSON từ điển fact của user."""
    safe_name = _sanitize_user_id_for_path(user_id_str)
    # Lưu file từ điển trong thư mục riêng của user
    user_dir = get_user_vector_dir(user_id_str) 
    return os.path.join(user_dir, "fact_map.json")

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

# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 918)
async def call_llm_to_classify(llm: ChatOpenAI, question: str, existing_keys: List[str]) -> str:
    """
    (SỬA LỖI 35: PROMPT V29 - SỬA LỖI 'UNKNOWN' - THEO Ý USER)
    Giải quyết lỗi v27 (ví dụ: 'doanh so 2023' -> 'unknown').
    Làm rõ QUY TẮC SỐ 3: Bắt buộc LLM phải tạo key mới nếu không khớp,
    thay vì trả về 'unknown'.
    """
    
    valid_keys = sorted(list(set(k for k in existing_keys if k and isinstance(k, str))))
    keys_str = ", ".join([f"'{k}'" for k in valid_keys])
    if not keys_str:
        keys_str = "(chưa có key nào)"
        
    # --- 🚀 BẮT ĐẦU PROMPT MỚI (v29) 🚀 ---
    prompt_text = f"""
    Bạn là một chuyên gia Phân loại Danh mục (Category Classifier).
    Nhiệm vụ: Tìm 1 'fact_key' CHÍNH XÁC NHẤT cho 'Query' (câu hỏi) dưới đây.

    Query: "{question}"
    
    Các Danh mục (fact_key) HIỆN CÓ:
    [{keys_str}]

    NHIỆM VỤ CỦA BẠN:

    BƯỚC 1: Tạo một 'ideal_key' (danh mục lý tưởng, dạng snake_case)
    tóm tắt CHUNG NHẤT cho Query.
    (Ví dụ: "xem ds anh" -> ideal_key: 'anh')
    (Ví dụ: "doanh so 2023" -> ideal_key: 'doanh_so')

    BƯỚC 2: So sánh 'ideal_key' (bạn vừa tạo ở B1) với
    [Các Danh mục HIỆN CÓ].
    
    - TRƯỜNG HỢP 1 (Ưu tiên): Nếu 'ideal_key' (ví dụ: 'anh')
      là một phần (hoặc rất giống) với một key HIỆN CÓ 
      (ví dụ: 'anh_du_lich')
      -> BẠN PHẢI TRẢ VỀ key HIỆN CÓ (ví dụ: 'anh_du_lich').
      
    - TRƯỜNG HỢP 2: Nếu 'ideal_key' (ví dụ: 'anh_du_lich')
      ĐÃ TỒN TẠI trong [Các Danh mục HIỆN CÓ]
      -> Trả về 'ideal_key' đó (ví dụ: 'anh_du_lich').
      
    - TRƯỜNG HỢP 3 (BẮT BUỘC): Nếu 'ideal_key' (ví dụ: 'doanh_so')
      HOÀN TOÀN KHÁC BIỆT với TẤT CẢ key HIỆN CÓ
      -> BẠN BẮT BUỘC PHẢI trả về 'ideal_key' MỚI đó (ví dụ: 'doanh_so').
      
    QUAN TRỌNG:
    - KHÔNG BAO GIỜ được trả về 'unknown' hoặc 'general_query' 
      chỉ vì 'ideal_key' của bạn không nằm trong danh sách HIỆN CÓ.
    - CHỈ trả về 'general_query' nếu Query quá chung chung (ví dụ: 'xem', 'hi').
    
    QUY TẮC TRẢ LỜI:
    - Chỉ trả về 1 'fact_key' (danh mục)
    - KHÔNG GIẢI THÍCH.
    """
    # --- 🚀 KẾT THÚC PROMPT MỚI 🚀 ---
    
    try:
        resp = await llm.ainvoke(prompt_text)
        fact_key = resp.content.strip().strip("`'\"").replace(" ", "_")
        fact_key = re.sub(r"[^a-z0-9_]", "", fact_key.lower())
        
        if not fact_key:
            return "general_query"
            
        print(f"[call_llm_to_classify] (Prompt v29) Query: '{question}' -> Key: '{fact_key}'")
        return fact_key
        
    except Exception as e:
        print(f"❌ Lỗi call_llm_to_classify: {e}")
        return "general_query"
    
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


# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1210)
def _save_image_and_note(
    vectorstore: Chroma,
    src_path: str, 
    user_text: str, 
    original_name: str,
    fact_key: str = "general"
) -> Tuple[str, str]:
    """
    (SỬA LỖI METADATA v2) Copy ảnh và ghi 1 dòng note [IMAGE]
    VỚI METADATA (fact_key + file_type).
    """
    name = original_name or os.path.basename(src_path) or f"image-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or '.jpg'}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name) 
    shutil.copyfile(src_path, dst)
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI 🚀 ---
    note_text = f"[IMAGE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    # (MỚI) Thêm file_type
    metadata = {"fact_key": fact_key, "file_type": "image"}
    
    vectorstore.add_texts(texts=[note_text], metadatas=[metadata])
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    
    return dst, name

# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1235)
def _save_file_and_note(
    vectorstore: Chroma,
    src_path: str, 
    original_name: Optional[str], 
    user_text: str,
    fact_key: str = "general",
    file_type: str = "file" # <-- THÊM THAM SỐ NÀY
) -> Tuple[str, str]:
    """
    (SỬA LỖI METADATA v2) Copy file và ghi 1 dòng note [FILE]
    VỚI METADATA (fact_key + file_type).
    """
    name = original_name or os.path.basename(src_path) or f"file-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or ''}"
    
    dst = os.path.join(PUBLIC_FILES_DIR, safe_name)
    shutil.copyfile(src_path, dst)
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI 🚀 ---
    note_text = f"[FILE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    # (MỚI) Dùng file_type được truyền vào
    metadata = {"fact_key": fact_key, "file_type": file_type}
    
    vectorstore.add_texts(texts=[note_text], metadatas=[metadata])
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    
    return dst, name

def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Tạo một text splitter tiêu chuẩn."""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )

# (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 1280)
def _load_and_process_document(
    vectorstore: Chroma,
    src_path: str, 
    original_name: str, 
    mime_type: str, 
    user_note: str,
    fact_key: str = "general"
) -> Tuple[int, str]:
    """
    (SỬA LỖI METADATA v2 - THEO Ý USER)
    1. Lưu Chunks (CÓ file_type).
    2. Lưu bản ghi [FILE] (CÓ fact_key + file_type).
    """
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI (THEO Ý USER) 🚀 ---
    # 0. (MỚI) Lấy file_type đơn giản (dùng helper vừa tạo)
    simple_file_type = _get_simple_file_type(mime_type, src_path)
    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
    
    text_content = ""
    metadata_note = f"Trích từ tài liệu: {original_name} | Ghi chú của người dùng: {user_note}"

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
            # --- 🚀 SỬA LỖI (FILE KHÔNG HỖ TRỢ) 🚀 ---
            note = f"[FILE_UNSUPPORTED] path={src_path} | name={original_name} | note={user_note}"
            metadata = {"fact_key": fact_key, "file_type": simple_file_type} # <-- SỬA
            vectorstore.add_texts(texts=[note], metadatas=[metadata])
            
            # Gọi hàm helper (SỬA: truyền simple_file_type)
            _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key, simple_file_type)
            return 0, original_name
            # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---

        if not text_content.strip():
            raise ValueError("File rỗng hoặc không thể trích xuất nội dung.")

        # 2. Cắt nhỏ (Chunking) (không đổi)
        text_splitter = _get_text_splitter()
        chunks = text_splitter.split_text(text_content)
        chunks_with_metadata = [
            f"{metadata_note}\n\n[NỘI DUNG CHUNK]:\n{chunk}"
            for chunk in chunks
        ]

        # --- 🚀 SỬA LỖI (LƯU CHUNKS) 🚀 ---
        # 4. Lưu Chunks (KHÔNG CÓ fact_key, nhưng PHẢI CÓ file_type)
        # (Vì chunks chỉ dùng để tra cứu nội dung, không cần fact_key)
        chunk_metadatas = [{"file_type": simple_file_type} for _ in chunks_with_metadata]
        vectorstore.add_texts(
            texts=chunks_with_metadata, 
            metadatas=chunk_metadatas # <-- SỬA: Thêm metadata (chỉ file_type)
        )
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
        # 5. Lưu bản ghi [FILE] (SỬA: truyền simple_file_type)
        # (Bản ghi này có cả fact_key và file_type)
        _save_file_and_note(vectorstore, src_path, original_name, user_note, fact_key, simple_file_type)
        
        return len(chunks_with_metadata), original_name

    except Exception as e:
        print(f"[ERROR] _load_and_process_document failed: {e}")
        
        # --- 🚀 SỬA LỖI (LƯU LỖI) 🚀 ---
        error_note = f"[ERROR_PROCESSING_FILE] name={original_name} | note={user_note} | error={e}"
        metadata = {"fact_key": fact_key, "file_type": simple_file_type} # <-- SỬA
        vectorstore.add_texts(texts=[error_note], metadatas=[metadata])
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
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

    await cl.Message(content=f"🗂️ **Danh sách {len(items)} file đã lưu:**").send()
    for it in items:
        safe_href = f"/public/files/{it['saved_name']}"
        safe_name = html.escape(it['original_name'])
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI HIỂN THỊ 🚀 ---
        display_content = "" # Biến hiển thị mới
        
        if it['type'] == '[IMAGE]':
            # (MỚI) Hiển thị TÊN + ẢNH
            display_content = f"**{safe_name}** {it['type']}\n![{safe_name}]({safe_href})"
        else:
            # (CŨ) Chỉ hiển thị TÊN
            display_content = f"**[{safe_name}]({safe_href})** {it['type']}"

        body = (
            f"{display_content}\n" # <-- SỬA DÒNG NÀY
            f"• Ghi chú: *{it['note']}*\n"
            f"• ID: `{it['doc_id']}`"
        )
        # --- 🚀 KẾT THÚC SỬA LỖI HIỂN THỊ 🚀 ---
        
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
def _build_clean_context_for_llm(docs_goc_content: list) -> str:
    """Helper: (SỬA LỖI 20) Tạo context SẠCH (chỉ name+note)
    để LLM chọn ra người chiến thắng."""
    
    clean_parts = []
    
    for i, content in enumerate(docs_goc_content):
        # 1. Tìm các phần chúng ta MUỐN GIỮ LẠI
        type_tag = "[IMAGE]" # (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 3080)
def _build_clean_context_for_llm(docs_goc_content: list) -> str:
    """Helper: (SỬA LỖI METADATA) Tạo context SẠCH
    cho LLM (từ văn bản thuần túy).
    """
    clean_parts = []
    
    for i, content in enumerate(docs_goc_content):
        
        # --- 🚀 BẮT ĐẦU SỬA LOGIC 🚀 ---
        
        # 1. Bỏ qua các chuỗi metadata cũ (nếu còn sót)
        if "| fact_key=" in content or content.startswith(("FACT:", "[REMINDER_")):
             continue
             
        # 2. Xử lý [IMAGE]/[FILE] (nếu có)
        type_tag = "[TEXT]" # Mặc định
        name_str = ""
        note_str = ""
        
        if content.startswith(("[IMAGE]", "[FILE]")):
            type_tag = "[IMAGE]" if "[IMAGE]" in content else "[FILE]"
            name_match = re.search(r"name=([^|]+)", content)
            note_match = re.search(r"note=([^|]+)", content)
            
            name_str = name_match.group(1).strip() if name_match else f"file_{i}"
            note_str = note_match.group(1).strip() if note_match else "(không ghi chú)"
        
        else: # Đây là [TEXT]
            # Dùng chính nội dung làm "tên" (an toàn)
            name_str = content.strip()
            # Bỏ qua note (vì nó là nội dung)
            note_str = "" 
            
        # 3. Xây dựng chuỗi "sạch"
        # (Quan trọng) Chúng ta dùng 'name' làm ID
        
        # (SỬA) Nếu là [TEXT], chỉ cần trả về Tag
        if type_tag == "[TEXT]":
            clean_parts.append(f"<{name_str}>{name_str}</{name_str}>")
        else:
            clean_parts.append(f"<{name_str}>{type_tag} | note={note_str}</{name_str}>")
        
        # --- 🚀 KẾT THÚC SỬA LOGIC 🚀 ---
        
    return "\n".join(clean_parts)
# (Tìm hàm _is_general_query, khoảng dòng 3080, và THAY THẾ TOÀN BỘ)
async def _is_general_query(llm: ChatOpenAI, query: str, fact_key: str) -> bool:
    """
    (SỬA LỖI 26: V2 - TỐI ƯU HÓA THÔNG MINH)
    Sửa lỗi 'anh du lich ha long' bị đánh dấu 'GENERAL'.
    Chỉ đánh dấu 'GENERAL' nếu query không có từ chi tiết thừa.
    """
    try:
        # 1. Chuẩn hóa
        query_clean = unidecode.unidecode(query.lower().strip())
        key_clean = fact_key.replace("_", " ").lower().strip()
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI LOGIC TỐI ƯU (V2) 🚀 ---
        
        # 2. (Tối ưu) Kiểm tra
        if key_clean in query_clean:
            # Lấy các từ thừa (ví dụ: "xem", "ha long")
            extra_words_str = query_clean.replace(key_clean, "").strip()
            
            # Xóa các "stop word" (từ vô nghĩa)
            extra_words_str = extra_words_str.replace("xem", "").replace("tim", "").strip()
            extra_words_str = extra_words_str.replace("hinh", "").replace("anh", "").strip()
            
            # Kiểm tra xem có còn "từ chi tiết" (như 'ha long') không
            if not extra_words_str:
                # Nếu không còn từ nào -> Đây là GENERAL
                print(f"[_is_general_query] Tối ưu V2: Query khớp chính xác. Đánh dấu GENERAL.")
                return True
            else:
                # Nếu còn từ (ví dụ: "ha long") -> Đây là SPECIFIC
                print(f"[_is_general_query] Tối ưu V2: Query có từ chi tiết ('{extra_words_str}').")
                print(f"[_is_general_query] -> Bỏ qua tối ưu. Hỏi LLM...")
                # (KHÔNG return True nữa, để cho LLM ở bước 3 quyết định)
        
        # --- 🚀 KẾT THÚC SỬA LỖI LOGIC TỐI ƯU 🚀 ---

        # 3. Nếu tối ưu thất bại -> Hỏi LLM (an toàn)
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
    
    
# (Dán hàm MỚI này vào khoảng dòng 3170, ngay trước hoi_thong_tin)
def _build_rag_filter_from_query(query: str) -> Optional[dict]:
    """(MỚI) Helper: Phân tích query để tạo bộ lọc metadata."""
    # (Dùng unidecode để tìm "tai lieu" (tiếng Việt không dấu))
    q_low = unidecode.unidecode(query.lower())
    
    file_type_keywords = {
        "excel": ["excel", "xlsx", "xls", "trang tinh", "spreadsheet"],
        "word": ["word", "docx", "doc", "van ban", "tai lieu"],
        "pdf": ["pdf"],
        "image": ["anh", "hinh", "image", "jpg", "png", "jpeg"],
        "text": ["text", "txt", "ghi chu", "note"],
    }
    
    # 1. Tìm loại file CỤ THỂ
    # (Chỉ tìm nếu có từ "file" hoặc "danh sach" (để tránh "xem ảnh"))
    if "file" in q_low or "danh sach" in q_low or "ds" in q_low or "tai lieu" in q_low:
         for f_type, keywords in file_type_keywords.items():
            for kw in keywords:
                if kw in q_low:
                    print(f"[_build_rag_filter] Phát hiện lọc theo file_type: {f_type}")
                    return {"file_type": f_type}
                    
    # 2. Tìm (chỉ) ảnh
    if q_low.startswith(("xem anh", "tim anh", "ds anh", "xem hinh", "tim hinh")):
         print(f"[_build_rag_filter] Phát hiện lọc (chỉ) ảnh: image")
         return {"file_type": "image"}
         
    # 3. Không phát hiện
    return None    
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

    @tool("luu_thong_tin", args_schema=LuuThongTinSchema)
    async def luu_thong_tin(noi_dung: str):
        """
        (SỬA LỖI 38: CHUNKING TEXT - SỬA LỖI B9)
        1. (CŨ) Dùng Cache/LLM Classifier để lấy fact_key.
        2. (MỚI) Dùng TextSplitter để chia nhỏ (chunk) 'noi_dung'
        (nếu nó quá dài).
        3. Lưu các CHUNKS (chứ không phải 1 file) vào CSDL.
        """
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic") 
        user_id_str = cl.user_session.get("user_id_str") 

        if not all([vectorstore, llm, user_id_str]):
            return "❌ Lỗi: Thiếu (vectorstore, llm, user_id_str)."

        try:
            text = (noi_dung or "").strip()
            if not text: return "⚠️ Không có nội dung để lưu."
            
            # --- BƯỚC A: KIỂM TRA CACHE (Logic cache không đổi) ---
            fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
            existing_keys = list(set(fact_dict.values()))
            user_note_clean_for_cache = text.strip().lower() 
            fact_key = fact_dict.get(user_note_clean_for_cache)
            
            if fact_key:
                print(f"[luu_thong_tin] (Cache HIT) Query: '{text}' -> Key: '{fact_key}'")
            else:
                print(f"[luu_thong_tin] (Cache MISS) Đang gọi LLM (Classifier v29 - Sẽ sửa ở B2) để phân loại: '{text}'")
                fact_key = await call_llm_to_classify(llm, text, existing_keys) 
                fact_dict[user_note_clean_for_cache] = fact_key
                await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
                print(f"[luu_thong_tin] LLM trả về key: '{fact_key}'. Đã cập nhật cache.")
            
            # --- 🚀 BƯỚC B: CHIA NHỎ (CHUNKING) (LOGIC MỚI) 🚀 ---
            
            # 1. (MỚI) Dùng splitter (đã có ở global)
            text_splitter = _get_text_splitter()
            chunks = text_splitter.split_text(text)
            
            if not chunks:
                return "⚠️ Văn bản rỗng sau khi chia nhỏ, không lưu gì cả."
            
            print(f"[luu_thong_tin] Đã chia nhỏ văn bản thành {len(chunks)} chunks.")

            # 2. (MỚI) Chuẩn bị metadata
            metadata_base = {"fact_key": fact_key, "file_type": "text"}
            metadatas_list = [metadata_base.copy() for _ in chunks]
            
            # 3. (MỚI) Ghi CHUNKS vào CSDL
            await asyncio.to_thread(
                vectorstore.add_texts,
                texts=chunks,
                metadatas=metadatas_list
            )
            
            # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
            
            # (Lấy chunk đầu tiên để hiển thị)
            preview_text = chunks[0]
            if len(preview_text) > 100:
                preview_text = preview_text[:100] + "..."
                
            msg = f"✅ ĐÃ LƯU ({len(chunks)} chunks): {preview_text} (Key: {fact_key})"
            return msg
            
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ LỖI LƯU: {e}"

    @tool(args_schema=DatLichSchema)
    async def dat_lich_nhac_nho(noi_dung_nhac: str, thoi_gian: str, escalate: bool = False) -> str:
        """
        Lên lịch một thông báo nhắc nhở.
        """
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic") 
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI (User-based) 🚀 ---
        user_id_str = cl.user_session.get("user_id_str") # <-- Lấy User ID
        
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy llm_logic." 
        if not user_id_str: return "❌ LỖI: Không tìm thấy 'user_id_str'. Vui lòng F5."
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
        try:
            ensure_scheduler()
            dt_when = None 
            # (Xóa dòng internal_session_id, chúng ta dùng user_id_str)
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."
            
            noti_text = (noi_dung_nhac or "").strip()
            if not noti_text: return "❌ Lỗi: Cần nội dung nhắc."
            
            facts_list = await _extract_fact_from_llm(llm, noti_text)

            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if repeat_sec > 0:
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                job_id = f"reminder-interval-{user_id_str}-{uuid.uuid4().hex[:6]}" # <-- SỬA
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60) # <-- SỬA
                
                texts_to_save = [f"[REMINDER_INTERVAL] every={repeat_sec}s | {noti_text} | job_id={job_id}"] + facts_list
                await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                
                return f"🔁 ĐÃ LÊN LỊCH LẶP: '{noti_text}' • mỗi {repeat_sec} giây"
            
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                job_id = f"reminder-cron-{user_id_str}-{uuid.uuid4().hex[:6]}" # <-- SỬA
                SCHEDULER.add_job(_do_push, trigger=cron["trigger"], id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60) # <-- SỬA
                
                texts_to_save = [f"[REMINDER_CRON] type={cron['type']} | {thoi_gian} | {noti_text} | job_id={job_id}"] + facts_list
                await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                
                return f"📅 ĐÃ LÊN LỊCH ({cron['type']}): '{noti_text}' • {thoi_gian}"
            
            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian)
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
            
            if escalate:
                job_id = f"first-{user_id_str}-{uuid.uuid4().hex[:6]}" # <-- SỬA
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_first_fire_escalation_job, trigger=trigger, id=job_id, args=[user_id_str, noti_text, 5], replace_existing=False, misfire_grace_time=60) # <-- SỬA
                
                texts_to_save = [f"[REMINDER_ESCALATE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"] + facts_list
                await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                
                return f"⏰ ĐÃ LÊN LỊCH (Leo thang): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
            else:
                job_id = f"reminder-{user_id_str}-{uuid.uuid4().hex[:6]}" # <-- SỬA
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)
                SCHEDULER.add_job(_do_push, trigger=trigger, id=job_id, args=[user_id_str, noti_text], replace_existing=False, misfire_grace_time=60) # <-- SỬA
                
                texts_to_save = [f"[REMINDER_ONCE] when={_fmt_dt(dt_when)} | {noti_text} | job_id={job_id}"] + facts_list
                await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                
                return f"⏰ ĐÃ LÊN LỊCH (1 lần): '{noti_text}' • lúc {_fmt_dt(dt_when)}"
        except Exception as e:
            return f"❌ Lỗi khi tạo nhắc: {e}"
    # (THAY THẾ TOÀN BỘ TOOL NÀY - KHOẢNG DÒNG 3185)
    @tool
    async def hoi_thong_tin(cau_hoi: str):
        """
        (SỬA LỖI 49 - TOOL MẶC ĐỊNH CỦA AGENT_ASK)
        (ƯU TIÊN CUỐI) Sử dụng tool này cho TẤT CẢ các yêu cầu HỎI,
        TÌM KIẾM, XEM, hoặc 'cho tôi' thông tin.
        Tool này dùng để tìm GHI CHÚ (NOTE), FILE, ẢNH CÓ LỌC,
        thông tin SERVER, PASSWORD, v.v.
        (Ví dụ: 'xem ảnh du lịch', 'cho thong tin CH-SQLDB-WIN2k19-01').
        Sử dụng tool này NẾU các tool chuyên biệt khác (như 
        get_product_detail hoặc xem_danh_sach_file) KHÔNG KHỚP.
        """
        try:
            # --- Lấy các dependencies ---
            llm = cl.user_session.get("llm_logic")
            vectorstore = cl.user_session.get("vectorstore")
            user_id_str = cl.user_session.get("user_id_str")
            
            if not all([llm, vectorstore, user_id_str]):
                return "❌ Lỗi: Thiếu (llm, vectorstore, user_id_str)."

            print(f"[hoi_thong_tin] Đang RAG (Sửa lỗi 37) với query: '{cau_hoi}'")

            # --- 🚀 BƯỚC 1: (MỚI) TÌM BỘ LỌC CỨNG (file_type) 🚀 ---
            filter_metadata = _build_rag_filter_from_query(cau_hoi)
            target_fact_key = "" 
            
            # --- 🚀 BƯỚC 2: (CŨ) TÌM FACT_KEY (Nếu B1 thất bại) 🚀 ---
            if filter_metadata is None:
                print(f"[hoi_thong_tin] B1 (Mới): Không phát hiện file_type.")
                
                # --- 🚀 BƯỚC 2a: (MỚI) KIỂM TRA CACHE 🚀 ---
                fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                existing_keys = list(set(fact_dict.values()))
                
                query_clean_for_cache = cau_hoi.strip().lower()
                target_fact_key = fact_dict.get(query_clean_for_cache) # <-- 1. ĐỌC CACHE
                
                if target_fact_key:
                    # 2. CACHE HIT
                    print(f"[hoi_thong_tin] B2 (Cache HIT) Query: '{cau_hoi}' -> Key: '{target_fact_key}'")
                else:
                    # 3. CACHE MISS
                    print(f"[hoi_thong_tin] B2 (Cache MISS) Đang gọi LLM (Classifier v29)...")
                    target_fact_key = await call_llm_to_classify(llm, cau_hoi, existing_keys) 
                    print(f"[hoi_thong_tin] B2b: LLM trả về key: '{target_fact_key}'.")
                    
                    # 4. LƯU VÀO CACHE
                    fact_dict[query_clean_for_cache] = target_fact_key
                    await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
                # --- 🚀 KẾT THÚC BƯỚC 2a 🚀 ---
                
                # (MỚI) Gán bộ lọc
                filter_metadata = {"fact_key": target_fact_key}
            else:
                print(f"[hoi_thong_tin] B1 (Mới): ĐÃ PHÁT HIỆN LỌC CỨNG. Bỏ qua LLM Classifier.")
                target_fact_key = filter_metadata.get("file_type", "N/A") # Dùng để báo cáo

            # --- BƯỚC 3: GỌI RAG (LỌC KEY) ---
            # (Phần code còn lại của hàm hoi_thong_tin giữ nguyên
            #  từ "print(f"[hoi_thong_tin] B3:..." cho đến hết)
            
            print(f"[hoi_thong_tin] B3: Đang tìm vector (RAG) VỚI BỘ LỌC METADATA: {filter_metadata}")
            
            query_vector = await asyncio.to_thread(embeddings.embed_query, cau_hoi)
            results = await asyncio.to_thread(
                vectorstore._collection.query,
                query_embeddings=[query_vector],
                n_results=20, 
                where=filter_metadata,
                include=["documents"]
            )
            
            docs_goc_content = results.get("documents", [[]])[0]
            run_specific_filter = False
            
            if not docs_goc_content:
                print(f"⚠️ [hoi_thong_tin] B3 (Lọc Key) không tìm thấy gì cho '{target_fact_key}'.")
                return f"ℹ️ Không tìm thấy mục nào khớp (đã lọc theo key/type '{target_fact_key}')"

            print(f"[hoi_thong_tin] B4: RAG tìm thấy {len(docs_goc_content)} ứng viên.")

            # --- BƯỚC 4: KIỂM TRA CHUNG/CỤ THỂ (ĐÃ CẬP NHẬT) ---
            if not run_specific_filter:
                if _build_rag_filter_from_query(cau_hoi) is not None:
                    print(f"[hoi_thong_tin] B4a (Mới): Đã lọc cứng (file_type), chuyển sang B5b (SPECIFIC).")
                    run_specific_filter = True
                else:
                    is_general = await _is_general_query(llm, cau_hoi, target_fact_key)
                    if is_general:
                        # --- BƯỚC 5a (GENERAL) (Không đổi) ---
                        print(f"[hoi_thong_tin] B5a (GENERAL): Hiển thị tất cả {len(docs_goc_content)} mục.")
                        found_elements = False
                        for content_goc in docs_goc_content:
                            displayed = await _display_rag_result(content_goc)
                            if displayed: found_elements = True
                        
                        if found_elements:
                            return f"✅ Đã hiển thị tất cả các mục tìm thấy cho danh mục '{target_fact_key}'."
                        else:
                            return f"ℹ️ Đã tìm thấy {len(docs_goc_content)} mục cho '{target_fact_key}', nhưng không có mục nào có thể hiển thị."
                    else:
                        run_specific_filter = True 

            # --- BƯỚC 5b (SPECIFIC) (ĐÃ CẬP NHẬT) ---
            if run_specific_filter:
                print(f"[hoi_thong_tin] B5b (SPECIFIC): Đang phân tích loại chunks...")

                # 1. (MỚI) Kiểm tra xem kết quả (chunks) có phải là GHI CHÚ (TEXT) không
                is_text_qa = False
                for doc in docs_goc_content:
                    # Nếu bất kỳ chunk nào KHÔNG phải là tag [FILE]/[IMAGE]
                    # (tức là nó là [TEXT] hoặc chunk từ file)
                    if not doc.startswith(("[IMAGE]", "[FILE]")):
                        is_text_qa = True
                        break
                
                # --- 🚀 BƯỚC 5b.1: LOGIC MỚI (RAG Q&A - THEO Ý USER) 🚀 ---
                if is_text_qa:
                    print("[hoi_thong_tin] B5b (Logic: RAG Q&A) - Phát hiện Ghi chú/Text.")
                    
                    # 1. Gộp TẤT CẢ các chunk thô lại
                    context_tho = "\n---\n".join(docs_goc_content)
                    
                    if not context_tho.strip():
                        print(f"⚠️ [hoi_thong_tin] B5b (Lỗi): Context thô bị rỗng.")
                        return "ℹ️ Đã tìm thấy các mục, nhưng nội dung của chúng bị rỗng."

                    print(f"[hoi_thong_tin] B6: Gửi context ({len(context_tho)} chars) cho LLM để TRẢ LỜI...")
                    
                    # 2. (MỚI) Tạo prompt RAG (trả lời câu hỏi)
                    custom_prompt = f"""
                    Bạn là một trợ lý thông tin, nhiệm vụ của bạn là trả lời câu hỏi của người dùng (Query)
                    CHỈ DỰA VÀO thông tin được cung cấp trong (Context).
                    
                    Context (Nội dung các ghi chú/file đã lưu):
                    ---
                    {context_tho}
                    ---
                    
                    Query (Câu hỏi của người dùng): "{cau_hoi}"
                    
                    Nhiệm vụ:
                    1. Đọc kỹ Query.
                    2. Tìm thông tin CHÍNH XÁC trong Context để trả lời Query.
                    3. Trả lời trực tiếp vào vấn đề. KHÔNG giải thích, KHÔNG thêm thông tin ngoài lề.
                    4. Nếu Context không chứa thông tin để trả lời, HÃY trả về một chuỗi rỗng.
                    
                    Câu trả lời (dựa trên Context):
                    """
                    
                    # 3. Gọi LLM
                    resp = await llm.ainvoke(custom_prompt)
                    llm_answer = resp.content.strip()

                    print(f"[hoi_thong_tin] B7 (RAG): LLM trả về câu trả lời: '{llm_answer}'")
                    
                    # 4. Trả về kết quả
                    if not llm_answer:
                        return f"ℹ️ Tôi tìm thấy {len(docs_goc_content)} mục liên quan, nhưng không tìm thấy câu trả lời chính xác cho '{cau_hoi}' trong đó."
                    else:
                        return llm_answer # Trả về thẳng câu trả lời
                
                # --- 🚀 BƯỚC 5b.2: LOGIC CŨ (LỌC TÊN FILE/ẢNH) 🚀 ---
                else:
                    print("[hoi_thong_tin] B5b (Logic: Lọc Tên) - Chỉ phát hiện [FILE]/[IMAGE].")
                    
                    context_sach = _build_clean_context_for_llm(docs_goc_content)
                    
                    if not context_sach:
                        # (Code fallback cũ giữ nguyên)
                        print(f"⚠️ [hoi_thong_tin] B5b (Lỗi Lọc Tên): Context sạch bị rỗng.")
                        found_elements = False
                        for content_goc in docs_goc_content:
                            displayed = await _display_rag_result(content_goc)
                            if displayed: found_elements = True
                        if found_elements:
                            return f"✅ (Fallback Lọc Tên) Đã hiển thị TẤT CẢ các mục tìm thấy cho '{target_fact_key}'."
                        else:
                            return f"ℹ️ Đã tìm thấy {len(docs_goc_content)} mục (FILE/IMAGE?), nhưng không thể lọc Tên."
                    
                    print(f"[hoi_thong_tin] B6 (Lọc Tên): Gửi context (sạch) cho LLM...")
                    
                    # (Prompt lọc tên cũ giữ nguyên)
                    custom_prompt = f"""
                    Yêu cầu của người dùng (Query): "{cau_hoi}"
                    Danh sách các mục đã lưu (Context):
                    {context_sach}
                    Nhiệm vụ:
                    1. Đọc Query.
                    2. Tìm mục (hoặc các mục) trong Context khớp nhất với Query.
                    3. Trả về CHÍNH XÁC TÊN của mục đó (là phần text nằm giữa <...> và </...>)
                    4. Nếu tìm thấy nhiều, trả về mỗi name trên một dòng.
                    5. Nếu không tìm thấy, trả về một chuỗi rỗng.
                    6. KHÔNG giải thích. Chỉ trả về Name.
                    Tên (Name) của mục khớp:
                    """
                    
                    resp = await llm.ainvoke(custom_prompt)
                    llm_response_text = resp.content.strip()

                    print(f"[hoi_thong_tin] B7 (Lọc Tên): LLM (đã lọc) trả về Names: '{llm_response_text}'")

                    if not llm_response_text:
                        return "ℹ️ Tôi tìm thấy các mục liên quan, nhưng không có mục nào khớp chính xác với yêu cầu của bạn."
                    
                    winning_names = [name.strip() for name in llm_response_text.split('\n') if name.strip()]
                    print(f"[hoi_thong_tin] B8 (Lọc Tên): Các 'name' thắng cuộc: {winning_names}")
            
                    found_elements = False
                    
                    # (Vòng lặp B9 cũ giữ nguyên)
                    for content_goc in docs_goc_content:
                        goc_name = ""
                        if content_goc.startswith(("[IMAGE]", "[FILE]")):
                            goc_name_match = re.search(r"name=([^|]+)", content_goc)
                            if not goc_name_match: continue 
                            goc_name = goc_name_match.group(1).strip()
                        else:
                            # (SỬA LOGIC B9: Nếu là text, goc_name là chính nó)
                            goc_name = content_goc.strip()
                        
                        if goc_name in winning_names:
                            print(f"[hoi_thong_tin] B9 (Rematch): Khớp! Đang hiển thị: {goc_name}")
                            displayed = await _display_rag_result(content_goc)
                            if displayed:
                                found_elements = True
                    
                    if found_elements:
                        return f"✅ Đã tìm và lọc (bằng Lọc Tên) {len(winning_names)} mục khớp."
                    else:
                        # (Sửa lỗi B9: Nếu nó tìm thấy text nhưng không match, báo lỗi này)
                        print(f"⚠️ [hoi_thong_tin] B9 (Lỗi Rematch Lọc Tên): LLM đã chọn '{winning_names}' nhưng không thể Rematch/Hiển thị.")
                        return "ℹ️ LLM (Lọc Tên) đã chọn, nhưng không thể Rematch/Hiển thị. (Lỗi logic B9)"
            
            # --- 🚀 KẾT THÚC SỬA LỖI 42 🚀 ---

        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi RAG (Sửa lỗi 37): {e}"

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
        (SỬA LỖI 49 - THEO Ý USER)
        CHỈ SỬ DỤNG nếu người dùng yêu cầu xem "TẤT CẢ", "TOÀN BỘ",
        hoặc "danh sách đầy đủ" file/ảnh.
        (Ví dụ: 'xem tất cả file', 'show all files').
        TUYỆT ĐỐI KHÔNG DÙNG cho các câu hỏi có từ khóa lọc
        (ví dụ: 'xem ảnh du lịch', 'xem file 2022').
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
    async def dat_lich_cong_viec(noi_dung: str, thoi_gian: str, mo_ta: Optional[str] = None) -> str:
        """
        Lên lịch một CÔNG VIỆC (task) cần hoàn thành.
        Công việc này có thể được xem và đánh dấu 'hoàn thành'.
        """
        user_id_str = cl.user_session.get("user_id_str")
        internal_session_id = cl.user_session.get("chainlit_internal_id")
        
        # --- 1. (MỚI) LẤY LLM VÀ VECTORSTORE ---
        vectorstore = cl.user_session.get("vectorstore")
        llm = cl.user_session.get("llm_logic")
        
        if not user_id_str or not internal_session_id:
            return "❌ Lỗi: Mất user_id hoặc internal_session_id. Vui lòng F5."
        if not vectorstore: return "❌ Lỗi: Không tìm thấy vectorstore."
        if not llm: return "❌ Lỗi: Không tìm thấy llm_logic."
        # --- KẾT THÚC BƯỚC 1 ---
            
        try:
            ensure_scheduler()
            if not SCHEDULER: return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."

            task_text = (noi_dung or "").strip()
            if not task_text: return "❌ Lỗi: Cần nội dung công việc."
            
            # (Logic xử lý thời gian giữ nguyên)
            dt_when = None
            recurrence_rule = None
            trigger = None
            job_id_suffix = f"{internal_session_id}-{uuid.uuid4().hex[:6]}"
            
            cron = detect_cron_schedule(thoi_gian)
            if cron:
                recurrence_rule = f"cron:{cron['type']}:{thoi_gian}"
                trigger = cron["trigger"]
                temp_job = SCHEDULER.add_job(_do_push, trigger=trigger, id=f"temp-{job_id_suffix}")
                dt_when = temp_job.next_run_time
                SCHEDULER.remove_job(temp_job.id)
            
            repeat_sec = parse_repeat_to_seconds(thoi_gian)
            if not dt_when and repeat_sec > 0:
                recurrence_rule = f"interval:{repeat_sec}s"
                trigger = IntervalTrigger(seconds=repeat_sec, timezone=VN_TZ)
                dt_when = datetime.now(VN_TZ) + timedelta(seconds=repeat_sec)

            if not dt_when:
                recurrence_rule = "once"
                dt_when = await parse_when_to_dt(thoi_gian)
                trigger = DateTrigger(run_date=dt_when, timezone=VN_TZ)

            if not dt_when or not trigger:
                return f"❌ Lỗi: Không thể phân tích thời gian '{thoi_gian}'"

            # (Logic lưu CSDL và Scheduler giữ nguyên)
            task_id = await asyncio.to_thread(
                _add_task_to_db, user_id_str, task_text, mo_ta, dt_when, recurrence_rule, None
            )
            job_id = f"taskpush-{task_id}-{job_id_suffix}"
            SCHEDULER.add_job(
                _push_task_notification, 
                trigger=trigger, 
                id=job_id, 
                args=[internal_session_id, task_text, task_id],
                replace_existing=False, 
                misfire_grace_time=60
            )
            
            conn = _get_user_db_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE user_tasks SET scheduler_job_id = ? WHERE id = ?", (job_id, task_id))
            conn.commit()
            conn.close()

            # --- 2. (MỚI) TỰ ĐỘNG TẠO FACT ---
            # (Tạo fact sau khi đã lưu CSDL thành công)
            try:
                facts_list = await _extract_fact_from_llm(llm, task_text)
                if facts_list:
                    # Lưu cả nội dung gốc và fact (giống luu_thong_tin)
                    texts_to_save = [task_text] + facts_list
                    await asyncio.to_thread(vectorstore.add_texts, texts_to_save)
                    print(f"[Task] Đã lưu FACT cho task: {task_text}")
            except Exception as e_fact:
                print(f"⚠️ Lỗi khi lưu FACT cho task: {e_fact}")
            # --- KẾT THÚC BƯỚC 2 ---

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
    
    # === MỚI: Định nghĩa Tool bằng Dict (Rule + Tool Object) ===
    
    base_tools_data = {
        # --- Hành động (Ưu tiên) ---
        # --- 🚀 THÊM KHỐI NÀY VÀO ĐÂY 🚀 ---
       # (QUY TẮC 1 - ƯU TIÊN CAO: CHI TIẾT)
       
        "get_product_detail": {
            "rule": "(CHI TIẾT SP - ƯU TIÊN 1) Nếu 'input' CHỨA mã/model sản phẩm (ví dụ: 'w451', 'H007-001', '541') HOẶC hỏi về *thông tin cụ thể* (ví dụ: 'thông số', 'mô tả', 'ưu điểm') -> Dùng `get_product_detail`",
            "tool": get_product_detail
        },
        
        # (SỬA LẠI QUY TẮC 2 - ƯU TIÊN THẤP)
        "searchlistproductnew": {
            "rule": "(DANH SÁCH SP - ƯU TIÊN 2) Nếu 'input' chỉ hỏi *danh sách chung* (ví dụ: 'danh sách máy cắt cỏ', 'tìm máy khoan') VÀ *KHÔNG* chứa mã/model sản phẩm cụ thể (đã được xử lý ở Ưu tiên 1) -> Dùng `searchlistproductnew`.",
            "tool": searchlistproductnew
        },
        # --- 🚀 KẾT THÚC THÊM 🚀 ---
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
            # (SỬA LỖI 40: Làm cho quy tắc này SIÊU NGHIÊM NGẶT)
            # Xóa ví dụ "ghi chú lại" (vì nó gây nhầm lẫn)
            "rule": "(LƯU) CHỈ DÙNG nếu 'input' BẮT ĐẦU BẰNG một từ khóa LƯU rõ ràng. "
                    "Các từ khóa BẮT BUỘC (phải có dấu hai chấm): 'lưu:', 'note:', 'save:', 'ghi chú:'."
                    "(Ví dụ: 'lưu: pass server là 123', 'note: tôi thích ăn phở')."
                    "NẾU KHÔNG BẮT ĐẦU BẰNG CÁC TỪ KHÓA NÀY -> TUYỆT ĐỐI KHÔNG DÙNG TOOL NÀY.",
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
        # (XÓA HOẶC COMMENT LẠI KHỐI NÀY - khoảng dòng 4045)
        # "tim_file_de_tai_ve": {
        #     "rule": "(FILE - TẢI VỀ) Nếu 'input' yêu cầu 'tải file', 'lấy link file' (thường là 1 file) -> Dùng `tim_file_de_tai_ve`.",
        #     "tool": tim_file_de_tai_ve
        # },
        # --- 🚀 KẾT THÚC BƯỚC 1 🚀 ---
        # (THAY THẾ QUY TẮC NÀY - khoảng dòng 4050)
       "xem_danh_sach_file": {
            "rule": "(FILE - DỰ PHÒNG) CHỈ SỬ DỤNG nếu 'input' yêu cầu 'xem TẤT CẢ file', 'toàn bộ file', 'danh sách ĐẦY ĐỦ' (VÀ KHÔNG CHỨA TỪ KHÓA LỌC như 'excel', 'word', 'hợp đồng') -> Dùng `xem_danh_sach_file`.",
            "tool": xem_danh_sach_file
        },
        # (THAY THẾ QUY TẮC NÀY - khoảng dòng 4055)
        "hoi_thong_tin": {
            # (SỬA LỖI 40: Mở rộng để "bắt" tất cả các câu hỏi)
            "rule": "(HỎI/XEM/TÌM - ƯU TIÊN CAO) Dùng cho TẤT CẢ các câu HỎI, TÌM KIẾM, hoặc yêu cầu 'cho tôi', 'lấy cho tôi'."
                    "(Ví dụ: 'cho toi ghi chú server thong tin', 'pass là gì', 'tìm file', 'tôi thích ăn gì?')."
                    "Nếu input KHÔNG PHẢI là lệnh LƯU (bắt đầu bằng 'lưu:') hoặc XÓA (chứa 'xóa') -> HÃY DÙNG TOOL NÀY.",
            "tool": hoi_thong_tin
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
            # (SỬA) Làm quy tắc này nghiêm ngặt hơn, chỉ tập trung vào EMAIL
            "rule": "(ADMIN) Nếu 'input' yêu cầu 'tra cứu user HỆ THỐNG' hoặc 'xem thông tin EMAIL CỤ THỂ' (ví dụ: 'check email user@oshima.vn') -> Dùng `lay_thong_tin_user`.",
            "tool": lay_thong_tin_user
        }
    }

    # === Kết thúc định nghĩa Dict ===

    # (MỚI) Lấy cờ admin từ session (đã được set ở on_start_after_login)
    is_admin = cl.user_session.get("is_admin", False)
    
    # 1. Gộp dict
    final_tools_data = {}
    is_admin = cl.user_session.get("is_admin", False)
    
    intent_options = ["ASKING", "SAVING", "DELETING", "DEBUG"]
    if is_admin:
        intent_options.append("ADMIN")
        
    intent_list_str = ", ".join([f"'{opt}'" for opt in intent_options])

    # 1.2. Tạo Prompt cho Master Router
    master_router_prompt_text = f"""
        Bạn là một Bộ phân loại ý định (Intent Classifier).
        Nhiệm vụ của bạn là đọc 'input' của người dùng và phân loại
        nó vào MỘT trong các 'Intent' sau: {intent_list_str}.

        QUY TẮC PHÂN LOẠI:
        - 'ASKING': Nếu người dùng HỎI, TÌM, XEM, 'cho tôi', 'lấy cho tôi'
        thông tin (ví dụ: 'pass là gì', 'tìm file', 'mô tả w451', 'xem danh sách').
        - 'SAVING': Nếu người dùng yêu cầu LƯU, TẠO, 'lưu:', 'note:', 'ghi chú:',
        'đặt lịch', 'thêm công việc'.
        - 'DELETING': Nếu người dùng yêu cầu XÓA, HỦY, BỎ
        (ví dụ: 'xóa file 2022', 'hủy lịch nhắc').
        - 'ADMIN': Nếu người dùng yêu cầu quản trị HỆ THỐNG
        (ví dụ: 'danh sách user', 'đổi pass user@...').
        - 'DEBUG': Nếu người dùng yêu cầu gỡ lỗi (ví dụ: 'push thử').
        
        VÍ DỤ (RẤT QUAN TRỌNG):
        - Input: "cho thong tin ghi chu CH-SQLDB-WIN2k19-01" -> Intent: "ASKING"
        - Input: "cho thong tin CH-SQLDB-WIN2k19-01" -> Intent: "ASKING"
        - Input: "xoa ghi chu abc" -> Intent: "DELETING"
        - Input: "note: abc" -> Intent: "SAVING"
        - Input: "xem danh sách user" -> Intent: "ADMIN"

        Chỉ trả về MỘT TỪ (Intent). KHÔNG GIẢI THÍCH.
    """
    
    master_router_prompt = ChatPromptTemplate.from_messages([
        ("system", master_router_prompt_text),
        ("human", "{input}"),
    ])
    
    # 1.3. Tạo Master Router Chain
    # (Chain này chỉ trả về 1 chuỗi: "ASKING", "SAVING", v.v.)
    master_router_chain = master_router_prompt | llm_logic | StrOutputParser()
    
    # 1.4. Lưu Master Router vào session
    cl.user_session.set("master_router_chain", master_router_chain)
    print("✅ [Sửa lỗi 44] (1/6) Master Router đã sẵn sàng.")

    # === BƯỚC 2: TẠO CÁC SUB-AGENT CHUYÊN BIỆT ===
    
    # 2.1. Phân loại tool vào các nhóm
    ask_tools_data = {
        "get_product_detail": base_tools_data["get_product_detail"],
        "searchlistproductnew": base_tools_data["searchlistproductnew"],
        "goi_chart_dashboard": base_tools_data["goi_chart_dashboard"],
        "hien_thi_web": base_tools_data["hien_thi_web"],
        "xem_viec_chua_hoan_thanh": base_tools_data["xem_viec_chua_hoan_thanh"],
        "xem_viec_da_hoan_thanh": base_tools_data["xem_viec_da_hoan_thanh"],
        "xem_lich_nhac": base_tools_data["xem_lich_nhac"],
        "xem_danh_sach_file": base_tools_data["xem_danh_sach_file"],
        "hoi_thong_tin": base_tools_data["hoi_thong_tin"],
        "xem_bo_nho": base_tools_data["xem_bo_nho"],
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
    
    # (admin_tools_data đã được định nghĩa ở trên)

    # 2.2. Helper (function lồng) để tạo Agent
    def _create_agent(llm: ChatOpenAI, tools_dict: dict, agent_name: str) -> AgentExecutor:
        """
        (SỬA LỖI v45) Helper nội bộ: Tạo AgentExecutor.
        Quan trọng: Lấy các "rule" từ tools_dict và 
        chèn chúng vào system prompt để LLM có hướng dẫn.
        """
        tools_list = [data["tool"] for data in tools_dict.values()]
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI (CHÈN QUY TẮC) 🚀 ---
        
        # 1. Xây dựng chuỗi quy tắc
        rule_lines = [
            f"- {tool_name}: {data['rule']}" 
            for tool_name, data in tools_dict.items()
        ]
        rules_str = "\n".join(rule_lines)

        # 2. Tạo System Prompt (Đã chèn quy tắc)
        system_prompt_text = f"""
        Bạn là một Agent chuyên biệt cho '{agent_name}'.
        Nhiệm vụ của bạn là đọc 'input' và chọn MỘT tool
        phù hợp nhất từ danh sách tool của bạn.

        ĐÂY LÀ CÁC QUY TẮC TUYỆT ĐỐI BẠN PHẢI TUÂN THEO:
        (Hãy đọc kỹ 'input' và so sánh với các quy tắc sau)
        
        {rules_str}
        
        QUAN TRỌNG: Chỉ gọi tool. KHÔNG trả lời trực tiếp.
        """
        
        # 3. Tạo Prompt Template
        agent_sys_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_text),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
        
        agent = create_openai_tools_agent(
            llm=llm,
            tools=tools_list,
            prompt=agent_sys_prompt, # <-- Dùng prompt mới
        )
        return AgentExecutor( 
            agent=agent, 
            tools=tools_list, 
            verbose=True,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            max_iterations=1 # Quan trọng
        )

    # 2.3. Tạo và Lưu các Sub-Agent
    agent_ASK = _create_agent(llm_logic, ask_tools_data, "ASKING")
    cl.user_session.set("agent_ASK", agent_ASK)
    print("✅ [Sửa lỗi 44] (2/6) agent_ASK đã sẵn sàng.")

    agent_SAVE = _create_agent(llm_logic, save_tools_data, "SAVING")
    cl.user_session.set("agent_SAVE", agent_SAVE)
    print("✅ [Sửa lỗi 44] (3/6) agent_SAVE đã sẵn sàng.")
    
    agent_DELETE = _create_agent(llm_logic, delete_tools_data, "DELETING")
    cl.user_session.set("agent_DELETE", agent_DELETE)
    print("✅ [Sửa lỗi 44] (4/6) agent_DELETE đã sẵn sàng.")
    
    agent_DEBUG = _create_agent(llm_logic, debug_tools_data, "DEBUG")
    cl.user_session.set("agent_DEBUG", agent_DEBUG)
    print("✅ [Sửa lỗi 44] (5/6) agent_DEBUG đã sẵn sàng.")
    
    if is_admin:
        agent_ADMIN = _create_agent(llm_logic, admin_tools_data, "ADMIN")
        cl.user_session.set("agent_ADMIN", agent_ADMIN)
        print("🔑 [Sửa lỗi 44] (6/6) agent_ADMIN (Admin) đã sẵn sàng.")

    # (Chúng ta không cần agent_executor (cũ) nữa)
    
    # --- 🚀 KẾT THÚC SỬA LỖI 44 🚀 ---

    # --- 11. Kết thúc (Giữ nguyên) ---
    await cl.Message(
        content="🧠 **Trợ lý (v44) đã sẵn sàng**. Hãy nhập câu hỏi để bắt đầu!"
    ).send()
    
    all_elements = cl.user_session.get("elements", [])
    cl.user_session.set("elements", all_elements)

# =========================================================
def _to_video_url(v: str) -> str:
    if not v:
        return ""
    s = str(v).strip()
    if not s:
        return ""

    # Nếu là thẻ iframe -> lấy src
    if s.startswith("<iframe"):
        m = re.search(r'src="([^"]+)"', s, flags=re.I)
        return m.group(1) if m else ""

    # Chuẩn hóa YouTube (để ClVideo phát được)
    s = s.replace("&amp;", "&")
    try:
        if "youtube.com/watch" in s or "youtu.be/" in s or "youtube.com/embed/" in s:
            # ClVideo có thể phát link watch/youtu.be trực tiếp
            if "youtube.com/embed/" in s:
                vid = s.split("/embed/")[1].split("?")[0]
                return f"https://www.youtube.com/watch?v={vid}"
            return s
    except Exception:
        pass

    # File video trực tiếp
    low = s.lower()
    if low.endswith((".mp4", ".webm", ".ogg")):
        return s

    # Mặc định
    return s
# (DÁN HÀM MỚI NÀY VÀO KHOẢNG DÒNG 4300, NGAY TRƯỚC @cl.on_message)
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
# (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 4330)
@cl.on_message
async def on_message(message: cl.Message):
    """
    (SỬA LỖI 45: Xóa bỏ check 'agent_executor' cũ)
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
        chat_history = cl.user_session.get("chat_history", []) # <-- THÊM LẠI DÒNG NÀY
        try:
            user_id_str_esc = cl.user_session.get("user_id_str")
            if user_id_str_esc in ACTIVE_ESCALATIONS:
                if not ACTIVE_ESCALATIONS[user_id_str_esc].get("acked"):
                    ACTIVE_ESCALATIONS[user_id_str_esc]["acked"] = True
                    print(f"[Escalation] ACK dừng leo thang cho USER {user_id_str_esc}")
        except Exception as e:
            print(f"[Escalation] Lỗi khi ack: {e}")

        # ----- 3) LOGIC XỬ LÝ -----
        ai_output = None
        loading_msg_to_remove = None
        elements = message.elements or []
        vectorstore = cl.user_session.get("vectorstore")

        # --- 🚀 BẮT ĐẦU SỬA LỖI 33 (Ý TƯỞNG CỦA BẠN) 🚀 ---

        if elements and vectorstore:
            # NHÁNH A: XỬ LÝ FILE/IMAGE (LOGIC MỚI)
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

                    # BƯỚC A: LẤY GHI CHÚ
                    if text and num_files > 0:
                        # (MỚI) DÙNG LLM TÁCH GHI CHÚ
                        print(f"[FactKey] (Tách) Đang gọi LLM tách ghi chú: '{text}' cho {num_files} file.")
                        notes_for_files = await _llm_split_notes(llm, text, num_files)
                    else:
                        # (FALLBACK) Dùng tên file (logic cũ của tôi)
                        print("[FactKey] (Fallback) Không có ghi chú, dùng tên file.")
                        notes_for_files = [os.path.splitext(el.name)[0].replace("-", " ").replace("_", " ") for el in elements]

                    # BƯỚC B: LẶP QUA TỪNG FILE + GHI CHÚ ĐÃ TÁCH
                    # (Dùng zip để gán file 1 -> note 1, file 2 -> note 2)
                    for el, user_note_for_file in zip(elements, notes_for_files):
                        try:
                            user_note_clean = user_note_for_file.strip().lower()
                            
                            # BƯỚC C: LẤY KEY CHO TỪNG FILE
                            existing_keys = list(set(fact_dict.values()))
                            
                            print(f"[FactKey] (File: {el.name}) Đang gọi LLM (v27) phân loại ghi chú: '{user_note_for_file}'")
                            # (Gọi v27 - đã sửa ở Bước 1)
                            fact_key = await call_llm_to_classify(llm, user_note_for_file, existing_keys)
                            
                            # Cập nhật cache (trong vòng lặp, để key mới có thể được dùng cho file sau)
                            fact_dict[user_note_clean] = fact_key
                            print(f"[FactKey] (File: {el.name}) LLM trả về: '{fact_key}'.")
                            
                            # BƯỚC D: LƯU FILE (với note và key TƯƠNG ỨNG)
                            if "image" in getattr(el, "mime", ""):
                                _, name = await asyncio.to_thread(
                                    _save_image_and_note, vectorstore, el.path, user_note_for_file, el.name, fact_key
                                )
                                saved_files_summary_lines.append(f"✅ Đã lưu ảnh: **{name}** (Ghi chú: '{user_note_for_file}' | Key: {fact_key})")
                            else:
                                chunks, name = await asyncio.to_thread(
                                    _load_and_process_document, vectorstore, el.path, el.name, el.mime, user_note_for_file, fact_key
                                )
                                if chunks > 0:
                                    saved_files_summary_lines.append(f"✅ Đã xử lý file: **{name}** ({chunks} chunks | Key: {fact_key})")
                                else:
                                    saved_files_summary_lines.append(f"✅ Đã lưu file: **{name}** (Key: {fact_key})")
                                    
                        except Exception as e_file:
                            saved_files_summary_lines.append(f"❌ Lỗi xử lý file {getattr(el,'name','?')}: {e_file}")

                    # BƯỚC E: LƯU CACHE (1 LẦN)
                    await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
                    
                    ai_output = (
                        f"**Kết quả xử lý file (đã tách riêng):**\n\n"
                        + "\n".join(saved_files_summary_lines)
                    )

            except Exception as e_branch_a:
                ai_output = f"❌ Lỗi nghiêm trọng khi xử lý file: {e_branch_a}"
                traceback.print_exc()

        # --- 🚀 KẾT THÚC SỬA LỖI 33 🚀 ---

        else:
            # --- 🚀 BẮT ĐẦU SỬA LỖI 44 (SỬ DỤNG ROUTER 2 BƯỚC) 🚀 ---
            # NHÁNH B: XỬ LÝ TEXT (LOGIC MỚI)
            try:
                loading_msg_to_remove = await cl.Message(author="Trợ lý", content="Đang phân tích ý định...").send()
                
                # === BƯỚC 1: GỌI MASTER ROUTER (GPT BRAIN) ===
                master_router_chain = cl.user_session.get("master_router_chain")
                if not master_router_chain:
                    ai_output = "❌ Lỗi: Mất Master Router (v44). Vui lòng F5."
                else:
                    print(f"[Router v44] B1: Đang gọi Master Router phân loại: '{text}'")
                    
                    intent = await master_router_chain.ainvoke({"input": text})
                    intent = intent.strip().upper() # (Vd: "ASKING")
                    
                    print(f"[Router v44] B1: Master Router trả về Intent: '{intent}'")
                    await loading_msg_to_remove.remove() # Xóa tin nhắn "Đang phân tích..."
                    
                    # === BƯỚC 2: GỌI SUB-AGENT CHUYÊN BIỆT ===
                    target_agent = None
                    if intent == "ASKING":
                        target_agent = cl.user_session.get("agent_ASK")
                    elif intent == "SAVING":
                        target_agent = cl.user_session.get("agent_SAVE")
                    elif intent == "DELETING":
                        target_agent = cl.user_session.get("agent_DELETE")
                    elif intent == "ADMIN":
                        target_agent = cl.user_session.get("agent_ADMIN")
                    elif intent == "DEBUG":
                        target_agent = cl.user_session.get("agent_DEBUG")
                    else:
                        ai_output = f"⚠️ Lỗi: Master Router trả về Intent không xác định: '{intent}'"

                    if target_agent:
                        
                        # --- 🚀 BẮT ĐẦU SỬA LỖI (DỊCH INTENT - V46) 🚀 ---
                        
                        # 1. (MỚI) Tạo map dịch
                        intent_map_vn = {
                            "ASKING": "Hỏi/Tìm",
                            "SAVING": "Lưu/Tạo",
                            "DELETING": "Xóa/Hủy",
                            "ADMIN": "Quản trị",
                            "DEBUG": "Gỡ lỗi"
                        }
                        
                        # 2. (MỚI) Lấy tên tiếng Việt (hoặc dùng tên gốc nếu không khớp)
                        intent_vn = intent_map_vn.get(intent, intent) 
                        
                        # 3. (SỬA) Dùng 'intent_vn' và văn bản mới theo yêu cầu của bạn
                        loading_msg_to_remove = await cl.Message(
                            author="Trợ lý", 
                            content=f"Đang thực hiện tác vụ (Ý định: {intent_vn})..."
                        ).send()
                        
                        # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---
                        
                        payload = {"input": text}
                        result = await target_agent.ainvoke(payload) # <-- Gọi Agent chuyên biệt
                        
                        # (Logic giải nén kết quả (giống như cũ))
                        steps = result.get("intermediate_steps") or []
                        if steps and isinstance(steps[-1], tuple) and len(steps[-1]) > 1:
                            obs = steps[-1][1]
                            ai_output = obs.strip() if isinstance(obs, str) and obs.strip() else str(obs)
                        else:
                            ai_output = result.get("output", "⚠️ Không có phản hồi (output rỗng).")
                    
                    elif not ai_output: # (Nếu intent không hợp lệ VÀ chưa có lỗi)
                        ai_output = f"⚠️ Lỗi: Không tìm thấy Agent cho Intent '{intent}'."
            
            except Exception as e_branch_b:
                ai_output = f"❌ Lỗi gọi agent (v44): {e_branch_b}"
            # --- 🚀 KẾT THÚC SỬA LỖI 44 🚀 ---

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