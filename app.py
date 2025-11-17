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
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash # <-- MỚI: Băm mật khẩu
import pandas as pd
import docx # từ python-docx
import pypdf
import unidecode
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma  # Keep for backward compatibility
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector as PGVectorStore
from langchain_openai import OpenAIEmbeddings
# from langchain_huggingface import HuggingFaceEmbeddings  # ⚠️ DISABLED: PyTorch conflict
from langchain_core.prompts import PromptTemplate
from postgres_utils import get_postgres_connection_string, init_connection_pool, test_connection, init_pgvector_extension
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
from chainlit.types import ThreadDict  # 🔥 V108: Import ThreadDict
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
POLLER_STARTED = False                         # Cờ để khởi động Tổng đài (1 lần)
NOTIFICATION_POLLER_STARTED = False            # Cờ để khởi động Task Notification Poller (1 lần)                      # Cờ để khởi động Tổng đài (1 lần)
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

# Cache vectorstore toàn cục (chỉ khởi tạo 1 lần) - Migrated to PostgreSQL
_SHARED_VECTORSTORE_CL = None
_PGVECTOR_COLLECTION_NAME = "shared_memory"
_PGVECTOR_TABLE_NAME = "langchain_pg_embedding"
# Global Scheduler (khởi tạo 1 lần)
SCHEDULER: Optional[AsyncIOScheduler] = None

# Cấu hình nơi lưu trữ job (database) - MIGRATED TO PostgreSQL
try:
    from postgres_utils import get_postgres_connection_string as pg_conn_str
    jobstores = {
        'default': SQLAlchemyJobStore(url=pg_conn_str())
    }
    print("✅ [APScheduler] Sử dụng PostgreSQL jobstore")
except Exception as e:
    print(f"⚠️ [APScheduler] Lỗi kết nối PostgreSQL: {e}. Fallback sang SQLite...")
    jobstores = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{JOBSTORE_DB_FILE}')
    }
    print(f"✅ [APScheduler] Sử dụng SQLite jobstore tại {JOBSTORE_DB_FILE}")

# Theo dõi các “escalating reminders” đang chạy theo từng session
ACTIVE_ESCALATIONS = {}  # { internal_session_id: { "repeat_job_id": str, "acked": bool } }

# Theo dõi task notifications đã được acknowledge (để ngừng nhắc lại)
TASK_ACK_STATUS = {}  # { "user_email:task_id": True/False }

# =========================================================
#  V108: DATA LAYER - CHAT HISTORY (MIGRATED TO PostgreSQL)
# =========================================================
try:
    from data_layer_postgres import PostgreSQLDataLayer
    cl_data_layer = PostgreSQLDataLayer()
    print("✅ [DataLayer] Sử dụng PostgreSQL")
except Exception as e:
    print(f"⚠️ [DataLayer] Lỗi kết nối PostgreSQL: {e}. Fallback sang SQLite...")
    from data_layer import SQLiteDataLayer
    cl_data_layer = SQLiteDataLayer(db_path="memory_db/chainlit_history.db")
    print("✅ [DataLayer] Sử dụng SQLite (Fallback)")

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

# 🚀 CACHE CHO GPT CLASSIFY (Tránh gọi GPT nhiều lần với cùng query)
_CLASSIFY_CACHE = {}  # { "query_hash": (fact_key, fact_label, core_query) }
_CLASSIFY_CACHE_TIMEOUT = 300  # 5 phút


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
    
# (THAY THẾ HÀM NÀY - khoảng dòng 172)

# 🚀 V106: CHAT PROFILES (Thay thế toggle mode cũ)
@cl.set_chat_profiles
async def chat_profile():
    """
    Định nghĩa 2 profiles: AGENT và SELL
    User chọn profile từ UI (góc trên bên phải)
    """
    return [
        cl.ChatProfile(
            name="AGENT",
            markdown_description="🤖 **Agent Mode** - Trợ lý thông minh với đầy đủ tools (ghi chú, lịch nhắc, file, ...)",
            icon="/public/logo_ai.png",
        ),
        cl.ChatProfile(
            name="SELL",
            markdown_description="🛍️ **Sell Mode** - Chuyên viên tư vấn bán hàng (sản phẩm, doanh số, khách hàng)",
            icon="/public/logo_ai.png",
        ),
    ]

@cl.on_chat_start
async def on_start_after_login():
    """
    Hàm này CHỈ CHẠY SAU KHI @cl.password_auth_callback thành công.
    (V106: Lấy chat profile để xác định mode)
    """
    
    # 🚀 V106: Lấy chat profile (AGENT hoặc SELL)
    chat_profile = cl.user_session.get("chat_profile")
    current_mode = "AGENT"  # Mặc định
    
    if chat_profile == "SELL":
        current_mode = "SELL"
        print(f"🛍️ [Session] User chọn SELL Mode")
    else:
        current_mode = "AGENT"
        print(f"🤖 [Session] User chọn AGENT Mode (default)")
    
    # Lưu mode vào session
    cl.user_session.set("mode", current_mode)
    
    # 🔥 V108: Lưu metadata cho chat history
    # Chainlit sẽ tự động lưu metadata này vào database
    thread = cl.user_session.get("thread")
    if thread:
        thread["metadata"] = {
            "chat_profile": current_mode,
            "created_at": datetime.now(VN_TZ).isoformat()
        }
    
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
    
    # --- KHỞI TẠO SHARED VECTORSTORE (MIGRATED TO PostgreSQL + pgvector) ---
    global _SHARED_VECTORSTORE_CL
    
    if _SHARED_VECTORSTORE_CL is None:
        print("[Shared DB] Đang khởi tạo Shared VectorStore lần đầu...")
        try:
            # Try PGVector first
            connection_string = get_postgres_connection_string()
            _SHARED_VECTORSTORE_CL = PGVectorStore(
                connection=connection_string,
                embeddings=embeddings,
                collection_name=_PGVECTOR_COLLECTION_NAME,
                use_jsonb=True,
            )
            print(f"✅ [PGVector] Shared VectorStore đã khởi tạo (PostgreSQL)")
        except Exception as e:
            print(f"⚠️ [PGVector] Lỗi: {e}. Fallback sang ChromaDB...")
            _SHARED_VECTORSTORE_CL = Chroma(
                persist_directory=SHARED_VECTOR_DB_DIR,
                embedding_function=embeddings,
                collection_name="shared_memory"
            )
            print(f"✅ [ChromaDB] Shared VectorStore đã khởi tạo tại {SHARED_VECTOR_DB_DIR}")
    else:
        print(f"[Shared DB] Sử dụng lại Shared VectorStore đã có (user: {user_email})")
    
    # Lưu vào session
    cl.user_session.set("vectorstore", _SHARED_VECTORSTORE_CL)
    retriever = _SHARED_VECTORSTORE_CL.as_retriever(search_kwargs={"k": 100})
    cl.user_session.set("retriever", retriever)
    
    print(f"✅ VectorStore cho user '{user_email}' đã sẵn sàng (mode=Similarity K=100)")
    
    # 2. Khởi tạo Tổng đài (như cũ)
    global GLOBAL_MESSAGE_QUEUE, POLLER_STARTED, NOTIFICATION_POLLER_STARTED
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
    
    if not NOTIFICATION_POLLER_STARTED:
        try:
            asyncio.create_task(task_notification_poller())
            NOTIFICATION_POLLER_STARTED = True
            print("✅ [Global] Đã khởi động TASK NOTIFICATION POLLER.")
        except Exception as e:
            print(f"❌ [Global] Lỗi khởi động Task Notification Poller: {e}")

    # 3. Hiển thị danh sách task thực từ database
    try:
        user_email = user.identifier.lower()
        import task_manager as tm
        
        # Lấy tasks sắp đến hạn (7 ngày tới)
        from datetime import datetime, timedelta
        start_date = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        end_date = (datetime.now(VN_TZ) + timedelta(days=7)).strftime("%Y-%m-%d")
        
        upcoming_tasks = await asyncio.to_thread(
            tm.get_tasks,
            user_email=user_email,
            status="pending",
            start_date=start_date,
            end_date=end_date
        )
        
        if upcoming_tasks:
            task_list = cl.TaskList()
            task_list.status = f"📋 Công việc sắp đến hạn ({len(upcoming_tasks)})"
            
            for task in upcoming_tasks[:5]:  # Chỉ hiển thị 5 task đầu
                due_date = task.get('due_date', '')
                priority = task.get('priority', 'medium')
                task_id = task.get('id')
                
                # Format due date
                try:
                    from datetime import datetime
                    dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                    due_str = dt.strftime('%d/%m %H:%M')
                except:
                    due_str = due_date[:16] if due_date else 'N/A'
                
                # Icon theo priority
                icon_map = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
                icon = icon_map.get(priority, '⚪')
                
                # Tạo action để mở popup edit task
                cl_task = cl.Task(
                    title=f"{icon} {task['title']} • {due_str}",
                    status=cl.TaskStatus.READY,
                    forId=f"task_{task_id}"  # ID để click vào sẽ trigger action
                )
                await task_list.add_task(cl_task)
            
            await task_list.send()
            print(f"✅ [TaskList] Hiển thị {len(upcoming_tasks[:5])} tasks sắp đến hạn")
        else:
            print("ℹ️ [TaskList] Không có task sắp đến hạn")
        
        # Gửi message với button để xem/edit tasks (LUÔN hiển thị)
        actions = [
            cl.Action(name="view_tasks", label="📋 Xem & Edit Tasks", payload={"action": "view_tasks"})
        ]
        await cl.Message(
            content="💡 _Click nút bên dưới để xem chi tiết và chỉnh sửa công việc_",
            actions=actions
        ).send()
            
    except Exception as e:
        print(f"⚠️ [TaskList] Lỗi khi load tasks: {e}")
    
    # 4. Gọi hàm setup chat chính
    await setup_chat_session(user)

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """
    🔥 V108: Chat History Resume
    Callback này được gọi khi user click vào một cuộc hội thoại cũ trong sidebar
    """
    print(f"📂 [Chat Resume] Loading thread: {thread.get('id', 'unknown')}")
    print(f"📂 [Chat Resume] Thread name: {thread.get('name', 'Untitled')}")
    print(f"📂 [Chat Resume] User ID: {thread.get('userId', 'unknown')}")
    
    # 1. Lấy user object
    user = cl.user_session.get("user")
    if not user:
        await cl.Message(content="❌ Lỗi: Không tìm thấy thông tin user khi resume chat.").send()
        return
    
    # 2. Tạo internal session ID mới cho tab này
    internal_session_id = str(uuid.uuid4())
    cl.user_session.set("chainlit_internal_id", internal_session_id)
    print(f"✅ [Chat Resume] Internal ID: {internal_session_id}")
    
    # 3. Lấy chat profile từ thread metadata (nếu có)
    metadata = thread.get("metadata", {})
    chat_profile = metadata.get("chat_profile", "AGENT")
    cl.user_session.set("mode", chat_profile)
    cl.user_session.set("chat_profile", chat_profile)
    print(f"🔄 [Chat Resume] Mode: {chat_profile}")
    
    # 4. Lấy quyền admin và tên user
    try:
        user_db_data = await asyncio.to_thread(get_user_by_email, user.identifier)
        is_admin = (user_db_data and user_db_data.get('is_admin') == 1)
        user_name = (user_db_data and user_db_data.get('name')) or ""
        
        cl.user_session.set("is_admin", is_admin)
        cl.user_session.set("user_name", user_name)
        print(f"👤 [Chat Resume] User: {user.identifier}, Admin: {is_admin}, Name: {user_name}")
    except Exception as e:
        print(f"❌ [Chat Resume] Lỗi khi lấy user data: {e}")
    
    # 5. Setup lại chat session (agent, vectorstore, etc.)
    await setup_chat_session(user)
    
    # 6. Gửi message thông báo đã load xong
    await cl.Message(
        content=f"✅ Đã tải lại cuộc hội thoại: **{thread.get('name', 'Untitled')}**"
    ).send()
    
    
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
    # === MỚI: Thêm bảng cho Checklist Công việc (V2: Priority + Tags + Assign) ===
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
        scheduler_job_id TEXT,
        priority TEXT DEFAULT 'medium',
        tags TEXT,
        assigned_to TEXT,
        assigned_by TEXT
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
# --- Các action callbacks khác (không dùng cho task nữa, task dùng CustomElement) ---




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
    (SỬA LỖI V88 - THEO YÊU CẦU CỦA USER + V105 CACHE)
    1. Nhận toàn bộ 'fact_map' làm context.
    2. Yêu cầu GPT ƯU TIÊN TÁI SỬ DỤNG 'Key'/'Label' đã có 
       thay vì "tạo" (invent) key mới.
    3. (V105) Cache kết quả để tránh gọi GPT nhiều lần
    """
    
    # --- 🚀 V105: CACHE CHECK 🚀 ---
    global _CLASSIFY_CACHE
    import time
    import hashlib
    
    # Tạo cache key từ question (hash để tránh key quá dài)
    cache_key = hashlib.md5(question.lower().strip().encode()).hexdigest()
    now = time.time()
    
    # Kiểm tra cache
    if cache_key in _CLASSIFY_CACHE:
        cached_data, cached_time = _CLASSIFY_CACHE[cache_key]
        if (now - cached_time) < _CLASSIFY_CACHE_TIMEOUT:
            fact_key, fact_label, core_query = cached_data
            print(f"[call_llm_to_classify] ⚡ CACHE HIT! Query: '{question[:50]}...' -> Key: '{fact_key}' (skip GPT)")
            return fact_key, fact_label, core_query
        else:
            # Cache hết hạn
            print(f"[call_llm_to_classify] ⏰ Cache expired ({now - cached_time:.0f}s), gọi lại GPT")
    
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
        
        # --- 🚀 V105: LƯU VÀO CACHE 🚀 ---
        _CLASSIFY_CACHE[cache_key] = ((fact_key, fact_label, core_query_term), now)
        print(f"[call_llm_to_classify] 💾 Saved to cache: '{question[:50]}...' -> '{fact_key}'")
        
        # (SỬA LỖI V88)
        print(f"[call_llm_to_classify] (Prompt V88) Query: '{question}' -> Key: '{fact_key}' | Label: '{fact_label}' | CoreQuery: '{core_query_term}'")
        return fact_key, fact_label, core_query_term
        
    except Exception as e:
        # (SỬA LỖI V88)
        print(f"❌ Lỗi call_llm_to_classify (V88): {e}")
        return "general", "General", question
    
    
    
    
# 🧠 LangChain + OpenAI + Vector (Đã sửa đổi)
# =========================================================
# 🚀 EMBEDDINGS OPTIMIZATION 🚀
# Fix: Tránh PyTorch circular import bằng cách dùng OpenAI với cache

USE_LOCAL_EMBEDDINGS = os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() == "true"

if USE_LOCAL_EMBEDDINGS:
    # ⚠️ LOCAL EMBEDDINGS BỊ LỖI CIRCULAR IMPORT (PyTorch)
    # Tạm thời disable, sẽ dùng giải pháp khác
    print("⚠️ [Embeddings] Local embeddings tạm thời disable (PyTorch conflict)")
    print("🌐 [Embeddings] Fallback sang OpenAI Embeddings với cache")
    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",
        show_progress_bar=False,
        chunk_size=100  # Batch 100 docs/request để tăng tốc
    )
else:
    print("🌐 [Embeddings] Sử dụng OpenAI Embeddings (API)")
    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",
        show_progress_bar=False,
        chunk_size=100
    )

# 🚀 PostgreSQL + pgvector Initialization
print("🔌 [PostgreSQL] Kiểm tra kết nối PostgreSQL...")
try:
    init_connection_pool(min_conn=2, max_conn=20)
    if test_connection():
        print("✅ [PostgreSQL] Kết nối thành công")
        init_pgvector_extension()
        print("✅ [pgvector] Extension đã được kích hoạt")
    else:
        print("❌ [PostgreSQL] Không thể kết nối. Fallback sang ChromaDB (SQLite)")
except Exception as e:
    print(f"❌ [PostgreSQL] Lỗi khởi tạo: {e}")
    print("⚠️  Fallback sang ChromaDB (SQLite)")
def get_shared_vectorstore_retriever() -> Tuple[Any, Any]:
    """
    (MỚI - 1 DB CHUNG - MIGRATED TO PostgreSQL + pgvector)
    Khởi tạo Vectorstore CHUNG cho TẤT CẢ user.
    Filter theo metadata['user_id'] khi query.
    """
    global _SHARED_VECTORSTORE, _SHARED_RETRIEVER, embeddings
    
    # Nếu đã khởi tạo rồi -> trả về cache
    if _SHARED_VECTORSTORE is not None and _SHARED_RETRIEVER is not None:
        return _SHARED_VECTORSTORE, _SHARED_RETRIEVER
    
    if embeddings is None:
        raise ValueError("Lỗi: Embeddings chưa được khởi tạo (OPENAI_API_KEY có thể bị thiếu).")
    
    try:
        # 🚀 Khởi tạo PGVector (PostgreSQL + pgvector)
        connection_string = get_postgres_connection_string()
        
        _SHARED_VECTORSTORE = PGVectorStore(
            connection=connection_string,
            embeddings=embeddings,
            collection_name=_PGVECTOR_COLLECTION_NAME,
            use_jsonb=True,  # Sử dụng JSONB cho metadata (tối ưu query)
        )
        
        # Retriever không filter (sẽ filter sau khi query)
        _SHARED_RETRIEVER = _SHARED_VECTORSTORE.as_retriever(search_kwargs={"k": 100})
        
        print(f"✅ [PGVector] Shared VectorStore đã sẵn sàng (PostgreSQL collection: {_PGVECTOR_COLLECTION_NAME})")
        return _SHARED_VECTORSTORE, _SHARED_RETRIEVER
        
    except Exception as e:
        print(f"❌ [PGVector] Lỗi khởi tạo: {e}")
        print("⚠️  Fallback sang ChromaDB (SQLite)...")
        
        # Fallback to ChromaDB
        _SHARED_VECTORSTORE = Chroma(
            persist_directory=SHARED_VECTOR_DB_DIR,
            embedding_function=embeddings,
            collection_name="shared_memory"  # Collection chung
        )
        
        _SHARED_RETRIEVER = _SHARED_VECTORSTORE.as_retriever(search_kwargs={"k": 100})
        
        print(f"✅ [ChromaDB] Shared VectorStore đã sẵn sàng tại {SHARED_VECTOR_DB_DIR} (Fallback mode)")
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
            fact_key = metadata.get("fact_key", "other")
            fact_label = metadata.get("fact_label", fact_key.replace("_", " ").title() if fact_key else "Other")
            
            out.append({
                "doc_id": doc_id,
                "file_path": file_path,
                "saved_name": saved_name,
                "original_name": file_name,
                "note": user_note,
                "type": type_tag,
                "timestamp_str": ts_str,
                "fact_key": fact_key,
                "fact_label": fact_label
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
    
    # Phải chạy sync - Lấy tất cả text, sau đó lọc chunk
    def _get_docs_sync():
        return vectorstore._collection.get(
            where={"file_type": "text"},
            include=["documents", "metadatas"]
        )
    
    raw_data = await asyncio.to_thread(_get_docs_sync)
    
    all_ids = raw_data.get("ids", [])
    all_docs = raw_data.get("documents", [])
    all_metadatas = raw_data.get("metadatas", [])
    
    # DEBUG: Gửi message để thấy log
    debug_msg = f"🔍 DEBUG: Tổng {len(all_docs)} docs text"
    await cl.Message(content=debug_msg).send()
    
    # In terminal
    print(f"\n{'='*60}")
    print(f"[DEBUG] ui_show_all_memory V1: Tổng {len(all_docs)} docs")
    for i in range(min(10, len(all_docs))):
        meta = all_metadatas[i]
        entry_type = meta.get('entry_type', 'N/A')
        print(f"[DEBUG] Doc #{i}: entry_type='{entry_type}', preview={all_docs[i][:60]}...")
    
    # Lọc bỏ chunks (chỉ giữ master: entry_type không phải file_chunk)
    ids, docs, metadatas = [], [], []
    chunk_count = 0
    for i, (doc_id, doc, meta) in enumerate(zip(all_ids, all_docs, all_metadatas)):
        entry_type = meta.get("entry_type", "")
        # Bỏ qua chunks (chỉ giữ text gốc và file_master)
        if entry_type != "file_chunk":
            ids.append(doc_id)
            docs.append(doc)
            metadatas.append(meta)
        else:
            chunk_count += 1
            if chunk_count <= 3:  # Chỉ log 3 chunk đầu
                print(f"[DEBUG] ❌ Filtered chunk #{chunk_count}: {doc[:60]}...")
    
    print(f"[DEBUG] ✅ Kept: {len(docs)} docs | ❌ Filtered: {chunk_count} chunks")
    print(f"{'='*60}\n")
    
    await cl.Message(content=f"🔍 Sau lọc: {len(docs)} ghi chú | Bỏ {chunk_count} chunks").send()
    
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
        
        # 🔍 Thêm nút debug xem chunks (chỉ cho parent_doc)
        entry_type = metadata.get("entry_type", "")
        if entry_type == "parent_doc":
            actions.append(
                cl.Action(
                    name="show_chunks_debug",
                    payload={"doc_id": doc_id},
                    label="🔍 Xem chunks"
                )
            )
        
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
        # Note: Chainlit không hỗ trợ xóa message đã gửi
        # Chỉ gửi thông báo xác nhận
        await cl.Message(content=f"✅ Đã xóa ghi chú: {doc_id}").send()

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
@cl.action_callback("edit_note")
async def _on_edit_note(action: cl.Action):
    """Xử lý chỉnh sửa ghi chú - Gửi form nhập liệu"""
    doc_id = action.payload.get("doc_id")
    current_content = action.payload.get("content", "")
    
    if not doc_id:
        await cl.Message(content="❌ Thiếu doc_id").send()
        return
    
    # Gửi message yêu cầu nhập nội dung mới
    await cl.Message(
        content=f"✏️ **Chỉnh sửa ghi chú** (ID: `{doc_id}`)\n\n"
                f"📝 Nội dung hiện tại:\n```\n{current_content}\n```\n\n"
                f"💬 Vui lòng nhập nội dung mới:"
    ).send()
    
    # Lưu doc_id vào session để xử lý sau
    cl.user_session.set("editing_note_id", doc_id)

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


@cl.action_callback("show_chunks_debug")
async def _on_show_chunks_debug(action: cl.Action):
    """🔍 DEBUG: Hiển thị danh sách chunks của parent để test Sentence Window."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return

    doc_id = action.payload.get("doc_id")
    if not doc_id:
        await cl.Message(content="❌ Lỗi: Không nhận được doc_id.").send()
        return

    try:
        # 1. Lấy parent document để xem parent_id
        parent_data = await asyncio.to_thread(
            vectorstore._collection.get,
            ids=[doc_id],
            include=["metadatas"]
        )
        
        if not parent_data or not parent_data.get("metadatas"):
            await cl.Message(content=f"❌ Không tìm thấy document ID: {doc_id}").send()
            return
            
        parent_meta = parent_data["metadatas"][0]
        parent_id = parent_meta.get("parent_id")
        entry_type = parent_meta.get("entry_type", "N/A")
        
        # 2. Nếu là parent_doc, tìm các search_chunk con
        if entry_type == "parent_doc" and parent_id:
            # ChromaDB không hỗ trợ nhiều điều kiện where → lọc sau
            chunks_data = await asyncio.to_thread(
                vectorstore._collection.get,
                where={"parent_id": parent_id},
                include=["documents", "metadatas"]
            )
            
            all_chunks = chunks_data.get("documents", [])
            all_metas = chunks_data.get("metadatas", [])
            
            # Lọc chỉ lấy search_chunk (bỏ parent_doc)
            chunks_content = []
            chunks_meta = []
            for doc, meta in zip(all_chunks, all_metas):
                if meta.get("entry_type") == "search_chunk":
                    chunks_content.append(doc)
                    chunks_meta.append(meta)
            
            if not chunks_content:
                await cl.Message(content=f"📝 Parent ID: `{parent_id}`\n\n⚠️ Không tìm thấy chunks con (có thể là ghi chú cũ trước khi có Sentence Window).").send()
                return
            
            # 3. Hiển thị danh sách chunks
            msg = f"🔍 **DEBUG: Sentence Window Chunks**\n\n"
            msg += f"📌 **Parent ID:** `{parent_id}`\n"
            msg += f"📄 **Entry Type:** `{entry_type}`\n"
            msg += f"🧩 **Số lượng chunks:** {len(chunks_content)}\n\n"
            msg += "---\n\n"
            
            for i, (chunk, meta) in enumerate(zip(chunks_content, chunks_meta), 1):
                chunk_idx = meta.get("chunk_index", "?")
                msg += f"**Chunk {i} (index: {chunk_idx}):**\n"
                msg += f"```\n{chunk[:200]}{'...' if len(chunk) > 200 else ''}\n```\n\n"
            
            await cl.Message(content=msg).send()
        else:
            await cl.Message(content=f"ℹ️ Document này không phải parent_doc.\n\n**Entry Type:** `{entry_type}`\n**Parent ID:** `{parent_id or 'N/A'}`").send()
            
    except Exception as e:
        print(f"❌ Lỗi trong _on_show_chunks_debug:")
        traceback.print_exc()
        await cl.Message(content=f"❌ Lỗi: {str(e)}").send()
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
        
        # --- 🚀 SỬA LỖI V94 (SẮP XẾP) + V107 (NOTEGRID) 🚀 ---
        sorted_results = _helper_sort_results_by_timestamp(ids, docs, metadatas)
        
        # Thu thập ghi chú text
        text_notes = []
        file_results = []
        
        for doc_id, document_text, metadata in sorted_results:
            if not metadata: metadata = {}
            file_type = metadata.get("file_type", "text")
            
            if file_type == "text":
                # Lọc bỏ các loại đặc biệt
                content = document_text
                if content.startswith(("[REMINDER_", "FACT:", "[FILE_UNSUPPORTED]", "[ERROR_PROCESSING_FILE]")):
                    continue
                
                text_notes.append({
                    "doc_id": doc_id,
                    "content": content,
                    "timestamp": metadata.get("timestamp", "")
                })
            else:
                file_results.append((doc_id, document_text, metadata))
        
        # Hiển thị ghi chú text
        if text_notes:
            if len(text_notes) > 1:
                # Dùng NoteGrid cho nhiều ghi chú
                notes_data = []
                for note in text_notes:
                    notes_data.append({
                        "doc_id": note["doc_id"],
                        "content": note["content"],
                        "timestamp": note["timestamp"]
                    })
                
                el = cl.CustomElement(
                    name="NoteGrid",
                    props={"title": f"📝 Ghi Chú ({len(text_notes)})", "notes": notes_data},
                    display="inline",
                )
                await cl.Message(content="", elements=[el]).send()
                found_count += len(text_notes)
            else:
                # Hiển thị ghi chú đơn lẻ (cũ)
                note = text_notes[0]
                content = note["content"]
                doc_id = note["doc_id"]
                
                summary = content
                if len(summary) > 200 or "\n" in summary:
                    summary = (content.split('\n', 1)[0] or content).strip()[:200] + "..."
                
                msg = cl.Message(content=f"**Ghi chú:** {summary}\n• ID: `{doc_id}`")
                msg.actions = [
                    cl.Action(
                        name="delete_note", 
                        payload={"doc_id": doc_id},
                        label="🗑️ Xóa"
                    ),
                    cl.Action(
                        name="edit_note",
                        payload={"doc_id": doc_id, "content": content},
                        label="✏️ Sửa"
                    ),
                    cl.Action(
                        name="show_note_detail",
                        payload={"doc_id": doc_id},
                        label="👁️ Chi tiết"
                    )
                ]
                await msg.send()
                found_count += 1
        
        # Hiển thị files/images (giữ nguyên logic cũ)
        for doc_id, document_text, metadata in file_results:
            
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
            
            # Gửi tin nhắn file/image
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
    """(SỬA LỖI - V103) Gọi hoi_thong_tin trực tiếp với fact_key filter."""
    try:
        fact_key = action.payload.get("fact_key")
        fact_label = action.payload.get("fact_label", fact_key)
        
        print(f"[show_category_items] Nhận được: fact_key='{fact_key}', fact_label='{fact_label}'")
        
        if not fact_key:
             await cl.Message(content="❌ Lỗi: Không nhận được fact_key.").send()
             return
        
        # Tìm tool hoi_thong_tin trong agent
        main_agent = cl.user_session.get("main_agent")
        if not main_agent:
            await cl.Message(content="❌ Lỗi: Mất Main Agent. Vui lòng F5.").send()
            return
        
        # Lấy tool hoi_thong_tin từ agent
        hoi_thong_tin_tool = None
        for tool in main_agent.tools:
            if tool.name == "hoi_thong_tin":
                hoi_thong_tin_tool = tool
                break
        
        if not hoi_thong_tin_tool:
            await cl.Message(content="❌ Lỗi: Không tìm thấy tool hoi_thong_tin.").send()
            return
        
        # LƯU fact_key vào session để hoi_thong_tin sử dụng
        cl.user_session.set("temp_fact_key_filter", fact_key)
        
        # Query đơn giản: chỉ cần "xem ds" là đủ (vì đã có fact_key filter)
        query = "xem ds file anh"
        
        await cl.Message(content=f"📁 Đang tải file/ảnh trong danh mục **{fact_label}**...").send()
        
        try:
            # Gọi trực tiếp tool (không qua agent để tránh nhầm lẫn)
            result = await hoi_thong_tin_tool.ainvoke({"cau_hoi": query})
            
            # Chỉ hiển thị message nếu có lỗi (ImageGrid/FileGrid đã được hiển thị)
            if result and isinstance(result, str) and ("❌" in result or "ℹ️" in result):
                await cl.Message(content=result).send()
        except Exception as e:
            await cl.Message(content=f"❌ Lỗi khi tải danh mục: {e}").send()
        finally:
            # XÓA fact_key filter sau khi dùng xong
            cl.user_session.set("temp_fact_key_filter", None)
            
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi _on_show_category_items: {e}").send()
            
async def ui_show_all_memory():
    """(MỚI) Hiển thị tất cả ghi chú (trừ file/image) với nút xóa - CHỈ LẤY MASTER."""
    vectorstore = cl.user_session.get("vectorstore")
    if not vectorstore:
        await cl.Message(content="❌ Lỗi: Không tìm thấy vectorstore.").send()
        return
    
    # Phải chạy sync - Lấy tất cả text, sau đó lọc chunk
    def _get_docs_sync():
        return vectorstore._collection.get(
            where={"file_type": "text"},
            include=["documents", "metadatas"]
        )
    
    raw_data = await asyncio.to_thread(_get_docs_sync)
    
    all_ids = raw_data.get("ids", [])
    all_docs = raw_data.get("documents", [])
    all_metadatas = raw_data.get("metadatas", [])
    
    # Lọc bỏ chunks (kiểm tra cả metadata và content)
    ids, docs, metadatas = [], [], []
    for i, (doc_id, doc, meta) in enumerate(zip(all_ids, all_docs, all_metadatas)):
        entry_type = meta.get("entry_type", "")
        
        # BỎ QUA CHUNKS - Kiểm tra cả metadata VÀ content
        is_chunk = (
            entry_type in ["file_chunk", "search_chunk"] or 
            "[NỘI DUNG CHUNK]" in doc or 
            doc.startswith("Trích từ tài liệu:")
        )
        
        if not is_chunk:
            ids.append(doc_id)
            docs.append(doc)
            metadatas.append(meta)
    
    if not docs:
        await cl.Message(content="📭 Bộ nhớ đang trống. Chưa lưu gì cả.").send()
        return

    notes_found = 0
    await cl.Message(content="📝 **Các ghi chú đã lưu (Văn bản - Mới nhất lên đầu):**").send()
    
    # Sắp xếp theo timestamp (nếu function helper có sẵn)
    try:
        sorted_results = _helper_sort_results_by_timestamp(ids, docs, metadatas)
    except:
        # Fallback: không sort
        sorted_results = list(zip(ids, docs, metadatas))
    
    for doc_id, content, metadata in sorted_results:
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
        
        # 🔍 Thêm nút debug xem chunks (chỉ cho parent_doc)
        entry_type = metadata.get("entry_type", "")
        if entry_type == "parent_doc":
            actions.append(
                cl.Action(
                    name="show_chunks_debug",
                    payload={"doc_id": doc_id},
                    label="🔍 Xem chunks"
                )
            )
        
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

async def task_notification_poller():
    """
    (MỚI) HÀM TASK NOTIFICATION POLLER - Đọc notification_queue và gửi đến users.
    Chạy 1 lần duy nhất cho toàn hệ thống.
    """
    global TASK_ACK_STATUS
    print("✅ [Task Notification] Task Notification Poller đã khởi động.")
    
    # Path to user database containing notification_queue
    user_db_path = os.path.join(BASE_DIR, "user_data", "users.sqlite")
    
    # Initialize notification_queue table if not exists
    try:
        conn = sqlite3.connect(user_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                task_title TEXT NOT NULL,
                task_description TEXT,
                notification_type TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        print("✅ [Task Notification] notification_queue table initialized.")
    except Exception as e:
        print(f"❌ [Task Notification] Error initializing table: {e}")
    
    while True:
        try:
            await asyncio.sleep(5)  # Poll every 5 seconds
            
            # Query pending notifications
            conn = sqlite3.connect(user_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, user_email, task_id, task_title, task_description, notification_type, created_at
                FROM notification_queue
                WHERE sent = 0
                ORDER BY created_at ASC
                LIMIT 50
            """)
            
            notifications = cursor.fetchall()
            
            if notifications:
                print(f"[Task Notification] Found {len(notifications)} pending notifications.")
            
            for notif in notifications:
                notif_id = notif['id']
                user_email = notif['user_email'].lower()
                task_id = notif['task_id']
                task_title = notif['task_title']
                task_description = notif['task_description']
                notification_type = notif['notification_type']
                created_at = notif['created_at']
                
                # Check if task has been acknowledged
                ack_key = f"{user_email}:{task_id}"
                if TASK_ACK_STATUS.get(ack_key):
                    # User đã phản hồi → Xóa notification và bỏ qua
                    cursor.execute("UPDATE notification_queue SET sent = 1 WHERE id = ?", (notif_id,))
                    conn.commit()
                    print(f"⏭️ [Task Notification] Task #{task_id} đã ACK bởi {user_email}, bỏ qua notification #{notif_id}")
                    continue
                
                # Check if user has active sessions
                queues_for_user = ACTIVE_SESSION_QUEUES.get(user_email, [])
                
                if queues_for_user:
                    # Build notification message
                    if notification_type == "REMIND":
                        icon = "🔔"
                        title_text = "Nhắc nhở công việc"
                    else:  # REPEAT
                        icon = "🔁"
                        title_text = "Công việc lặp lại"
                    
                    content = f"{icon} **{title_text}**\n\n"
                    content += f"**{task_title}**\n\n"
                    if task_description:
                        content += f"_{task_description}_\n\n"
                    content += f"⏰ _Thời gian: {created_at}_"
                    
                    # Send to all active sessions of this user
                    msg_data = {
                        "target_user_id": user_email,
                        "author": "Hệ thống",
                        "content": content
                    }
                    
                    print(f"[Task Notification] Sending notification #{notif_id} to {user_email} ({len(queues_for_user)} tabs)")
                    
                    for target_queue in queues_for_user:
                        if target_queue:
                            try:
                                await target_queue.put(msg_data)
                            except Exception as e:
                                print(f"❌ [Task Notification] Error sending to queue: {e}")
                    
                    # Mark as sent
                    cursor.execute("UPDATE notification_queue SET sent = 1 WHERE id = ?", (notif_id,))
                    conn.commit()
                    print(f"✅ [Task Notification] Notification #{notif_id} marked as sent.")
                else:
                    # User not online, leave notification in queue
                    print(f"⏳ [Task Notification] User {user_email} not online, notification #{notif_id} queued.")
            
            conn.close()
            
        except asyncio.CancelledError:
            print("[Task Notification] Đã dừng.")
            break
        except Exception as e:
            print(f"[Task Notification/ERROR] Bị lỗi: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

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
    (SỬA LỖI 3: Nhóm file theo fact_key với fact_label tiếng Việt)
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
    
    # Hiển thị file theo fact_key (nhóm thành albums)
    if files_list:
        from collections import defaultdict
        files_by_fact_key = defaultdict(list)
        
        # Nhóm file theo fact_key
        for it in files_list:
            # Skip nếu file không tồn tại
            if not os.path.exists(it['file_path']):
                print(f"[WARNING] File không tồn tại, skip: {it['file_path']}")
                continue
            
            fact_key = it.get('fact_key', 'other')
            files_by_fact_key[fact_key].append(it)
        
        # Hiển thị từng album (fact_key group)
        for fact_key, files_in_group in files_by_fact_key.items():
            # Chuẩn bị dữ liệu cho FileGrid
            files_data = []
            for it in files_in_group:
                safe_href = f"/public/files/{it['saved_name']}"
                files_data.append({
                    "name": it['original_name'],
                    "note": it['note'],
                    "type": it['type'],
                    "url": safe_href,
                    "doc_id": it['doc_id'],
                    "file_path": it['file_path']
                })
            
            # Lấy fact_label tiếng Việt
            fact_label = it.get('fact_label', fact_key.replace("_", " ").title())
            actual_count = len(files_data)
            
            # Bỏ qua nếu không có file nào sau khi filter
            if actual_count == 0:
                continue
            
            # Hiển thị FileGrid cho album này
            el = cl.CustomElement(
                name="FileGrid",
                props={
                    "title": f"📁 {fact_label} ({actual_count} file{'s' if actual_count > 1 else ''})",
                    "files": files_data,
                    "showActions": False
                },
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

@cl.action_callback("search_in_notes")
async def _on_search_in_notes(action: cl.Action):
    """
    Khi người dùng nhấn nút "🔍 Tìm thêm trong ghi chú"
    """
    query = action.payload.get("query") if action.payload else None
    if not query:
        await cl.Message(content="❌ Lỗi: Không nhận được query.").send()
        return
    
    await cl.Message(content=f"🔎 Đang tìm trong **ghi chú** với câu hỏi: *{query}*...").send()
    
    # Lưu flag vào session để hoi_thong_tin biết cần search notes
    cl.user_session.set("search_notes_mode", True)
    cl.user_session.set("search_notes_query", query)
    
    # Gọi agent để xử lý (thay vì gọi hoi_thong_tin trực tiếp)
    main_agent = cl.user_session.get("main_agent")
    if not main_agent:
        await cl.Message(content="❌ Lỗi: Mất Main Agent. Vui lòng F5.").send()
        cl.user_session.set("search_notes_mode", False)
        return
    
    try:
        payload = {"input": query}
        result = await main_agent.ainvoke(payload)
        
        # Lấy kết quả từ agent
        steps = result.get("intermediate_steps") or []
        if steps and isinstance(steps[-1], tuple) and len(steps[-1]) > 1:
            obs = steps[-1][1]
            ai_output = obs.strip() if isinstance(obs, str) and obs.strip() else str(obs)
        else:
            ai_output = result.get("output", "⚠️ Không có phản hồi.")
        
        # Hiển thị kết quả nếu có
        if ai_output and ai_output.strip() and ai_output.strip() != "⚠️ Không có phản hồi.":
            await cl.Message(content=ai_output).send()
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi khi tìm trong ghi chú: {e}").send()
    finally:
        # Reset flag
        cl.user_session.set("search_notes_mode", False)
        cl.user_session.set("search_notes_query", None)

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
    """(SỬA LỖI V89 + FILE TYPE DETECTION + V103: TẤT CẢ FILE/ẢNH)
    Thay vì .startswith (quá khắt khe), dùng regex
    để tìm TỪ KHÓA (word) 'anh'/'hinh'/'file'.
    
    THÊM: Phát hiện loại file cụ thể (word, excel, pdf)
    và lọc theo file_type trong metadata.
    
    THÊM V103: Phát hiện "tất cả", "ds", hoặc "file + ảnh" → lấy CẢ FILE VÀ IMAGE
    """
    
    q_low = unidecode.unidecode(query.lower())
    
    # --- 🚀 V103/V108: PHÁT HIỆN YÊU CẦU LẤY TẤT CẢ 🚀 ---
    # Case 1: Có từ "tất cả", "ds", "danh sách" (KHÔNG BAO GỒM "trong" - vì "trong danh mục" là lọc fact_key)
    is_all_request = bool(re.search(r'\b(tat ca|tất cả|all|ds|danh sach)\b', q_low))
    has_in_category = bool(re.search(r'\b(trong|vao|o|tai|of|in)\b', q_low))
    
    # Case 2: Có CẢ "file" VÀ "ảnh" trong cùng query → muốn lấy cả hai
    has_both_file_and_image = (
        bool(re.search(r'\b(file|tai lieu|tài liệu)\b', q_low)) and 
        bool(re.search(r'\b(anh|hinh|image)\b', q_low))
    )
    
    # V108: Nếu có "ds/xem/tất cả" + "trong" → KHÔNG filter entry_type (lấy cả text + file)
    if is_all_request and has_in_category:
        print(f"[_build_rag_filter] (V108) Phát hiện 'ds/xem TRONG danh mục' → KHÔNG lọc entry_type (lấy cả text + file).")
        return None  # Không filter entry_type, để lấy tất cả
    
    # V103: Nếu chỉ có "ds/tất cả" (KHÔNG có "trong") → Lấy file_master
    if is_all_request or has_both_file_and_image:
        print(f"[_build_rag_filter] (V103) Phát hiện yêu cầu TẤT CẢ FILE/ẢNH → Lọc entry_type=file_master.")
        return {"entry_type": "file_master"}
    # --- 🚀 KẾT THÚC V103/V108 🚀 ---
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI V89 (Regex) 🚀 ---
    
    # 0. (MỚI) Kiểm tra loại file CỤ THỂ TRƯỚC (để tránh nhầm với tên file)
    # Pattern: "xem ds file word", "file excel", "tai lieu pdf", v.v.
    # Quan trọng: Kiểm tra ngữ cảnh "ds", "danh sach", "xem", "tat ca" để tránh nhầm với tên file
    has_list_context = bool(re.search(r'\b(ds|danh sach|xem|tat ca|tất cả|list|liet ke|liệt kê)\b', q_low))
    
    if has_list_context:
        # Kiểm tra từng loại file cụ thể
        if re.search(r'\b(word|docx?|van ban|văn bản)\b', q_low):
            print(f"[_build_rag_filter] Phát hiện lọc file WORD.")
            return {
                "$and": [
                    {"file_type": "word"},
                    {"entry_type": "file_master"}
                ]
            }
        
        if re.search(r'\b(excel|xlsx?|xls|trang tinh|trang tính)\b', q_low):
            print(f"[_build_rag_filter] Phát hiện lọc file EXCEL.")
            return {
                "$and": [
                    {"file_type": "excel"},
                    {"entry_type": "file_master"}
                ]
            }
        
        if re.search(r'\bpdf\b', q_low):
            print(f"[_build_rag_filter] Phát hiện lọc file PDF.")
            return {
                "$and": [
                    {"file_type": "pdf"},
                    {"entry_type": "file_master"}
                ]
            }
    
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

    # 2. (SỬA) Tìm file GỐC (CHUNG CHUNG - tất cả loại file)
    # Chỉ khi KHÔNG có loại file cụ thể ở trên
    file_keywords = ["file", "tai lieu", "tài liệu", "document"]
    
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
    (V107 - PERFORMANCE TRACKING)
    Thêm log chi tiết thời gian từng bước
    """
    import time
    perf_start = time.time()
    perf_times = {}
    
    # Lấy dependencies từ session
    vectorstore = cl.user_session.get("vectorstore")
    llm = cl.user_session.get("llm_logic") 
    user_id_str = cl.user_session.get("user_id_str") 

    if not all([vectorstore, llm, user_id_str]):
        return "❌ Lỗi: Thiếu (vectorstore, llm, user_id_str)."

    try:
        # --- 🚀 BẮT ĐẦU SỬA LỖI V97 🚀 ---
        # 1. Lấy nội dung GỐC (original text)
        step_start = time.time()
        original_text = (noi_dung or "").strip()
        if not original_text: return "⚠️ Không có nội dung để lưu."
        perf_times['validate'] = time.time() - step_start
        
        # 2. (CŨ) Gọi GPT V88 để phân loại
        #    (CHỈ GỬI PHẦN TIÊU ĐỀ - 200 ký tự đầu)
        step_start = time.time()
        fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
        perf_times['load_dict'] = time.time() - step_start
        
        # (OPTIMIZATION) Chỉ gửi 200 ký tự đầu (tiêu đề) lên LLM để tiết kiệm token
        text_for_classification = original_text
        if len(original_text) > 200:
            # Lấy 200 ký tự đầu, cắt ở cuối từ để tránh cắt giữa chừng
            text_for_classification = original_text[:200].rsplit(' ', 1)[0] + "..."
            print(f"[luu_thong_tin] (OPTIMIZATION) Text dài {len(original_text)} chars, chỉ gửi {len(text_for_classification)} chars (tiêu đề) cho LLM phân loại.")
        else:
            print(f"[luu_thong_tin] Đang gọi GPT (V88) để phân loại ghi chú (dài {len(original_text)} chars)...")

        step_start = time.time()
        fact_key, fact_label, core_query_term = await call_llm_to_classify(
            llm, text_for_classification, fact_dict
        )
        perf_times['gpt_classify'] = time.time() - step_start
        print(f"[luu_thong_tin] (Sửa lỗi V97) GPT (V88) trả về: Key='{fact_key}', Label='{fact_label}', CoreQuery='{core_query_term}'")
        
        # --- 🚀 BƯỚC B: SENTENCE WINDOW RETRIEVAL 🚀 ---
        # STRATEGY: Lưu parent (toàn bộ) + chunks nhỏ (để search)
        # → Search chính xác trong chunks, retrieve parent đầy đủ
        
        step_start = time.time()
        current_timestamp_iso = datetime.now(VN_TZ).isoformat()
        user_email = cl.user_session.get("user_email", "unknown")
        
        # Tạo parent_id duy nhất cho document này
        parent_id = f"parent_{user_id_str}_{uuid.uuid4().hex[:8]}"
        
        # B1: Lưu PARENT (bản gốc đầy đủ) - KHÔNG embedding
        # Chỉ lưu vào metadata để retrieve sau
        parent_metadata = {
            "user_id": user_email,
            "fact_key": fact_key,
            "fact_label": fact_label,
            "file_type": "text",
            "timestamp": current_timestamp_iso,
            "entry_type": "parent_doc",
            "parent_id": parent_id,
            "full_content": original_text  # Lưu toàn bộ nội dung
        }
        
        # Lưu parent với placeholder text ngắn (để tiết kiệm embedding cost)
        parent_placeholder = f"[PARENT] {fact_label}: {original_text[:100]}..."
        perf_times['prepare'] = time.time() - step_start
        
        # B2: Chia nhỏ thành chunks (sentences/paragraphs) để search
        step_start = time.time()
        text_splitter = _get_text_splitter()
        small_chunks = text_splitter.split_text(original_text)
        perf_times['split'] = time.time() - step_start
        
        # Tạo metadata cho từng chunk (link về parent)
        chunks_to_save = [parent_placeholder]  # Parent đầu tiên
        metadatas_to_save = [parent_metadata]
        
        for idx, chunk in enumerate(small_chunks):
            chunk_meta = {
                "user_id": user_email,
                "fact_key": fact_key,
                "fact_label": fact_label,
                "file_type": "text",
                "timestamp": current_timestamp_iso,
                "entry_type": "search_chunk",
                "parent_id": parent_id,  # Link về parent
                "chunk_index": idx
            }
            chunks_to_save.append(chunk)
            metadatas_to_save.append(chunk_meta)
        
        print(f"[luu_thong_tin] (SENTENCE WINDOW) Lưu 1 parent + {len(small_chunks)} search chunks ({len(original_text)} chars)")
        
        # 3. Ghi TẤT CẢ (parent + chunks) vào Vectorstore
        step_start = time.time()
        await asyncio.to_thread(
            vectorstore.add_texts,
            texts=chunks_to_save,
            metadatas=metadatas_to_save
        )
        perf_times['chroma_add'] = time.time() - step_start
        print(f"[luu_thong_tin] ✅ Đã lưu với Sentence Window Retrieval (user_id={user_email})")
        
        # --- 🚀 BƯỚC C: LƯU VÀO CACHE (FACT_MAP) (Giữ nguyên) 🚀 ---
        step_start = time.time()
        if core_query_term and core_query_term.strip().lower() != "all":
            cache_key = core_query_term.strip().lower()
            fact_dict[cache_key] = {"key": fact_key, "label": fact_label} 
            await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
            print(f"[luu_thong_tin] Đã cập nhật cache: '{cache_key}' -> '{fact_key}'")
        else:
            print(f"[luu_thong_tin] Bỏ qua cập nhật cache vì CoreQuery là '{core_query_term}'")
        perf_times['save_dict'] = time.time() - step_start        
        # --- 🚀 V107: PERFORMANCE SUMMARY 🚀 ---
        total_time = time.time() - perf_start
        
        print(f"\n{'='*60}")
        print(f"[PERFORMANCE V107] luu_thong_tin")
        print(f"{'='*60}")
        print(f"  Validate text:      {perf_times.get('validate', 0):.3f}s")
        print(f"  Load fact dict:     {perf_times.get('load_dict', 0):.3f}s")
        print(f"  GPT Classify:       {perf_times.get('gpt_classify', 0):.3f}s")
        print(f"  Prepare metadata:   {perf_times.get('prepare', 0):.3f}s")
        print(f"  Text splitting:     {perf_times.get('split', 0):.3f}s")
        print(f"  ChromaDB add:       {perf_times.get('chroma_add', 0):.3f}s")
        print(f"  Save fact dict:     {perf_times.get('save_dict', 0):.3f}s")
        print(f"  {'─'*58}")
        print(f"  TOTAL TIME:         {total_time:.3f}s")
        print(f"  Text size:          {len(original_text)} chars")
        print(f"  Chunks created:     {len(small_chunks)}")
        print(f"{'='*60}\n")
        
        return (
            f"✅ Đã lưu ghi chú thành công!\n\n"
            f"**Chủ đề:** {fact_label}\n"
            f"**Số ký tự:** {len(original_text)}\n"
            f"**Sentence Window:** 1 parent + {len(small_chunks)} chunks\n"
            f"**Thời gian:** {total_time:.2f}s\n"
            f"**Lợi ích:** Search chính xác, retrieve đầy đủ ngữ cảnh"
        )
        
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"❌ LỖI LƯU (V97): {e}"
    
async def setup_chat_session(user: cl.User):
    """
    (CẬP NHẬT) Sửa lời chào để hiển thị tên user
    """
    global embeddings  # 🔥 V108: Cần khai báo global để dùng embeddings
    
    user_id_str = user.identifier
    cl.user_session.set("user_id_str", user_id_str)
    
    # --- 🚀 V110: THÊM MODE SWITCH (AGENT / SELL) 🚀 ---
    # Mặc định là AGENT mode (tìm ghi chú, file, RAG)
    current_mode = cl.user_session.get("mode", "AGENT")
    if not current_mode:
        cl.user_session.set("mode", "AGENT")
        current_mode = "AGENT"
    
    print(f"[Session] Mode hiện tại: {current_mode}")
    # --- 🚀 KẾT THÚC V110 🚀 ---
    
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
    async def tao_cong_viec(
        title: str,
        due_date: str,
        description: str = "",
        priority: str = "medium",
        tags: str = ""
    ) -> str:
        """
        ➕ TẠO CÔNG VIỆC MỚI
        
        Tạo task mới với đầy đủ thông tin.
        
        Args:
            title: Tiêu đề công việc (bắt buộc)
            due_date: Thời hạn (format: "2024-12-25 14:00" hoặc "ngày mai 3 giờ chiều")
            description: Mô tả chi tiết (optional)
            priority: "high", "medium", hoặc "low" (mặc định: medium)
            tags: Các tag phân loại, cách nhau bởi dấu phẩy (vd: "urgent, meeting")
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        llm = cl.user_session.get("llm_logic")
        
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        if not llm:
            return "❌ Lỗi: Không tìm thấy llm_logic"
        
        try:
            # 1. Parse due date using LLM (better than dateutil for Vietnamese)
            due_datetime = await parse_when_to_dt(due_date)
            
            # 2. Auto-extract tags from title using LLM (categorize like fact_key)
            tags_list = []
            if tags:
                # User provided tags
                tags_list = [t.strip() for t in tags.split(',') if t.strip()]
            else:
                # Auto-extract using LLM
                try:
                    extract_prompt = f"""
Phân tích tiêu đề công việc sau và xác định DANH MỤC (category) chính của nó.
Chỉ trả về 1-3 tag ngắn gọn để PHÂN LOẠI công việc, KHÔNG phải từ khóa chi tiết.

Các danh mục gợi ý:
- Cá nhân (personal): việc cá nhân, sức khỏe, học tập
- Gia đình (family): con cái, bố mẹ, họ hàng
- Công việc (work): dự án, họp, báo cáo, deadline
- Khách hàng (customer): họp khách, gặp đối tác
- Tài chính (finance): thanh toán, hóa đơn, ngân hàng
- Mua sắm (shopping): đi chợ, mua đồ
- Sự kiện (event): sinh nhật, lễ hội, tiệc

Tiêu đề: {title}

Ví dụ:
- "Họp khách hàng ABC về dự án X" → work, customer
- "Nộp báo cáo tháng 11" → work
- "Đi học lúc 10h" → personal
- "Cho con đi học" → family
- "Thanh toán tiền điện" → finance
- "Đi chợ mua rau" → shopping

Chỉ trả về các tag (1-3 tag), cách nhau bởi dấu phẩy:"""
                    
                    llm_response = await llm.ainvoke(extract_prompt)
                    tags_text = llm_response.content.strip()
                    tags_list = [t.strip() for t in tags_text.split(',') if t.strip()][:3]  # Max 3 tags
                    print(f"[Auto-Tags] Extracted from '{title}': {tags_list}")
                except Exception as e:
                    print(f"[Auto-Tags] Failed to extract: {e}")
                    tags_list = []
            
            # 3. Create task
            task_id = await asyncio.to_thread(
                tm.create_task,
                user_email=user_email,
                title=title,
                description=description or None,
                due_date=due_datetime,
                priority=priority.lower(),
                tags=tags_list,
                assigned_by=user_email
            )
            
            # 4. Display confirmation
            await cl.Message(
                content=f"✅ **Đã tạo công việc #{task_id}**\n\n"
                       f"📋 **{title}**\n"
                       f"⏰ Hạn: {due_datetime.strftime('%d/%m/%Y %H:%M')}\n"
                       f"🎯 Priority: {priority.upper()}\n"
                       f"🏷️ Tags: {', '.join(tags_list) if tags_list else 'None'}"
            ).send()
            
            return f"✅ Công việc #{task_id} đã được tạo: {title}"
            
        except Exception as e:
            return f"❌ Lỗi khi tạo công việc: {e}"
    
    @tool
    async def danh_dau_hoan_thanh(task_id: int) -> str:
        """
        ✅ ĐÁNH DẤU CÔNG VIỆC HOÀN THÀNH
        
        Args:
            task_id: ID của công việc cần đánh dấu hoàn thành
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        
        try:
            success = await asyncio.to_thread(
                tm.mark_complete,
                task_id=task_id,
                user_email=user_email
            )
            
            if success:
                await cl.Message(content=f"✅ Đã hoàn thành công việc #{task_id}").send()
                return f"✅ Task #{task_id} đã được đánh dấu hoàn thành"
            else:
                return f"❌ Không tìm thấy task #{task_id} hoặc bạn không có quyền"
                
        except Exception as e:
            return f"❌ Lỗi: {e}"
    
    @tool
    async def xoa_cong_viec(task_id: int) -> str:
        """
        🗑️ XÓA CÔNG VIỆC
        
        Args:
            task_id: ID của công việc cần xóa
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        
        try:
            success = await asyncio.to_thread(
                tm.delete_task,
                task_id=task_id,
                user_email=user_email
            )
            
            if success:
                await cl.Message(content=f"🗑️ Đã xóa công việc #{task_id}").send()
                return f"✅ Task #{task_id} đã được xóa"
            else:
                return f"❌ Không tìm thấy task #{task_id} hoặc bạn không có quyền"
                
        except Exception as e:
            return f"❌ Lỗi: {e}"
    
    @tool
    async def sua_cong_viec(
        task_id: int,
        title: str = None,
        description: str = None,
        due_date: str = None,
        priority: str = None,
        tags: str = None
    ) -> str:
        """
        ✏️ SỬA CÔNG VIỆC
        
        Cập nhật thông tin công việc. Chỉ cần truyền các field muốn thay đổi.
        
        Args:
            task_id: ID của công việc cần sửa (bắt buộc)
            title: Tiêu đề mới (optional)
            description: Mô tả mới (optional)
            due_date: Thời hạn mới (format: "2024-12-25 14:00" hoặc "ngày mai 3 giờ chiều")
            priority: "high", "medium", hoặc "low" (optional)
            tags: Các tag mới, cách nhau bởi dấu phẩy (optional)
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        
        try:
            # Parse due date if provided
            due_datetime = None
            if due_date:
                from dateutil import parser as date_parser
                try:
                    due_datetime = date_parser.parse(due_date, fuzzy=True)
                except:
                    due_datetime = await parse_when_to_dt(due_date)
            
            # Parse tags if provided
            tags_list = None
            if tags:
                tags_list = [t.strip() for t in tags.split(',') if t.strip()]
            
            # Update task
            success = await asyncio.to_thread(
                tm.update_task,
                task_id=task_id,
                title=title,
                description=description,
                due_date=due_datetime,
                priority=priority.lower() if priority else None,
                tags=tags_list
            )
            
            if success:
                update_msg = f"✅ **Đã cập nhật công việc #{task_id}**\n\n"
                if title: update_msg += f"📝 Tiêu đề: {title}\n"
                if description: update_msg += f"📄 Mô tả: {description}\n"
                if due_datetime: update_msg += f"⏰ Hạn: {due_datetime.strftime('%d/%m/%Y %H:%M')}\n"
                if priority: update_msg += f"🎯 Priority: {priority.upper()}\n"
                if tags_list: update_msg += f"🏷️ Tags: {', '.join(tags_list)}\n"
                
                await cl.Message(content=update_msg).send()
                return f"✅ Task #{task_id} đã được cập nhật"
            else:
                return f"❌ Không tìm thấy task #{task_id} hoặc không có gì thay đổi"
                
        except Exception as e:
            return f"❌ Lỗi khi sửa công việc: {e}"
    
    @tool
    async def xem_danh_sach_cong_viec(filter_status: str = "uncompleted") -> str:
        """
        📋 XEM DANH SÁCH CÔNG VIỆC
        Hiển thị tasks dưới dạng bảng tương tác với UI element.
        
        filter_status: "uncompleted" (mặc định), "completed", hoặc "all"
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        
        try:
            # Get tasks
            tasks = await asyncio.to_thread(
                tm.get_tasks,
                user_email=user_email,
                status=filter_status
            )
            
            # Get stats
            stats = await asyncio.to_thread(tm.get_task_stats, user_email)
            
            if not tasks:
                return f"📭 Không có công việc nào ({filter_status})"
            
            # Prepare data for CustomElement
            tasks_data = []
            for task in tasks:
                tasks_data.append({
                    "id": task['id'],
                    "title": task['title'],
                    "description": task.get('description', ''),
                    "due_date": task.get('due_date', ''),
                    "priority": task.get('priority', 'medium'),
                    "tags": task.get('tags', []),
                    "is_completed": task.get('is_completed', False),
                    "recurrence_rule": task.get('recurrence_rule', ''),
                    "assigned_to": task.get('assigned_to', ''),
                    "user_email": user_email  # For API calls
                })
            
            # Send CustomElement
            await cl.Message(
                content=f"📋 **Tìm thấy {len(tasks)} công việc ({filter_status})**",
                elements=[
                    cl.CustomElement(
                        name="TaskGrid",
                        props={
                            "title": f"📋 Danh sách công việc ({filter_status})",
                            "tasks": tasks_data,
                            "stats": stats
                        }
                    )
                ]
            ).send()
            
            return f"✅ Đã hiển thị {len(tasks)} công việc trong grid tương tác"
            
        except Exception as e:
            return f"❌ Lỗi: {e}"
    
    @tool
    async def hoi_thong_tin(cau_hoi: str):
        """
        📚 HỎI THÔNG TIN - TÌM KIẾM theo NỘI DUNG/CHỦ ĐỀ/DANH MỤC (RAG).
        
        ✅ DÙNG KHI user muốn:
        - Tìm theo CHỦ ĐỀ: "hình về du lịch", "ảnh thuộc danh mục du lịch", "file trong du lịch"
        - Hỏi về NỘI DUNG: "tôi thích ăn gì?", "thông tin sản phẩm X"
        - Xem DANH MỤC: "cho tôi danh mục"
        
        ❌ KHÔNG DÙNG khi user muốn tìm file có TÊN CỤ THỂ (dùng tim_kiem_file).
        
        (SỬA LỖI V96 - TỐI ƯU RAG)
        1. (Cũ - V95) Giữ logic "Ưu tiên" cho 'xem danh muc'.
        2. (MỚI - V96) Khi thực hiện tìm kiếm (SPECIFIC),
        sẽ dùng CÂU HỎI GỐC để tìm vector, giúp tăng độ chính xác.
        """
        # --- 🚀 PERFORMANCE LOGGING (V104) - IMPORT TẠI ĐÂY 🚀 ---
        import time
        perf_start = time.time()
        perf_times = {}  # Lưu thời gian từng bước
        
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
                
                # Kiểm tra lệnh xem danh mục - CHỈ khi KHÔNG có từ khóa cụ thể khác
                # VD: "cho toi danh muc" ✅ | "hinh danh muc du lich" ❌ (vì có "du lich")
                has_danh_muc = "danh muc" in q_low_norm
                has_specific_keywords = any(kw in q_low_norm for kw in ["hinh", "anh", "file", "video", "du lich", "san pham", "thong tin"])
                is_category_query = has_danh_muc and not has_specific_keywords
                
                if is_category_query:
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
                perf_times['classify'] = 0  # SKIP GPT classify
                target_fact_key = "general"
                target_fact_label = "General"
                core_search_query = cau_hoi  # Dùng câu hỏi gốc
                is_general_query = False  # Luôn là SPECIFIC (Q&A)
            else:
                # SLOW PATH: Gọi LLM phân loại đầy đủ
                print(f"[hoi_thong_tin] (V99) 🐌 SLOW PATH: Câu hỏi phức tạp, gọi call_llm_to_classify")
                fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
                
                print(f"[hoi_thong_tin] B2 (Sửa lỗi V96) Đang gọi V88 (có fact_map) để lấy Key, Label, CoreQuery...")
                
                # --- 🚀 V111: PARALLEL OPTIMIZATION - Chạy song song GPT classify + Embeddings 🚀 ---
                print(f"[hoi_thong_tin] (V111) ⚡ Chạy SONG SONG: GPT classify + Embeddings")
                classify_start = time.time()
                
                # Chạy song song 2 tác vụ
                classify_task = call_llm_to_classify(llm, cau_hoi, fact_dict)
                embed_task = asyncio.to_thread(embeddings.embed_query, cau_hoi)
                
                # Đợi cả 2 xong
                (target_fact_key, target_fact_label, core_search_query), query_vector_early = await asyncio.gather(
                    classify_task, embed_task
                )
                
                perf_times['classify'] = time.time() - classify_start
                print(f"[hoi_thong_tin] (V111) ✅ Song song hoàn tất: classify={perf_times['classify']:.3f}s")
                # --- 🚀 KẾT THÚC V111 🚀 ---
                
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
                
                # --- 🚀 V103: PHÁT HIỆN "TRONG [DANH MỤC]" 🚀 ---
                # Nếu query có "trong", "vào", "ở" + tên danh mục → dùng fact_key
                q_low_norm = unidecode.unidecode(cau_hoi.lower())
                has_in_category = bool(re.search(r'\b(trong|vao|o|tai|of|in)\b', q_low_norm))
                
                if has_in_category and target_fact_key and target_fact_key != 'general':
                    print(f"[hoi_thong_tin] B4 (V103): Phát hiện 'TRONG danh mục' → Thêm fact_key filter: {target_fact_key}")
                    final_filter_list.append({'fact_key': target_fact_key})
                # --- 🚀 KẾT THÚC V103 🚀 ---
            
            # --- 🚀 V103: THÊM FACT_KEY FILTER TỪ ACTION CALLBACK 🚀 ---
            temp_fact_key = cl.user_session.get("temp_fact_key_filter")
            if temp_fact_key:
                print(f"[hoi_thong_tin] B4 (V103): Thêm fact_key filter từ action callback: {temp_fact_key}")
                final_filter_list.append({'fact_key': temp_fact_key})
            # --- 🚀 KẾT THÚC V103 🚀 ---
            
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
                
                # --- 🚀 V111: SỬ DỤNG query_vector ĐÃ TÍNH SẴN (nếu có) 🚀 ---
                if 'query_vector_early' in locals():
                    # SLOW PATH đã tính sẵn embedding song song với classify
                    print(f"[hoi_thong_tin] (V111) ⚡ Sử dụng embedding đã tính sẵn (song song với classify)")
                    query_vector = query_vector_early
                    perf_times['embeddings'] = 0  # Đã tính trong classify_time
                else:
                    # FAST PATH hoặc trường hợp khác - tính mới
                    embed_start = time.time()
                    query_vector = await asyncio.to_thread(embeddings.embed_query, search_vector_query)
                    perf_times['embeddings'] = time.time() - embed_start
                
                # --- 🚀 V105: TĂNG n_results KHI CÓ FACT_KEY FILTER 🚀 ---
                # Đệ quy kiểm tra fact_key trong filter (xử lý cả nested $and)
                def has_fact_key_in_filter(where_clause):
                    if not where_clause:
                        return False
                    if isinstance(where_clause, dict):
                        if 'fact_key' in where_clause:
                            return True
                        if '$and' in where_clause:
                            return any(has_fact_key_in_filter(f) for f in where_clause['$and'])
                        if '$or' in where_clause:
                            return any(has_fact_key_in_filter(f) for f in where_clause['$or'])
                    elif isinstance(where_clause, list):
                        return any(has_fact_key_in_filter(f) for f in where_clause)
                    return False
                
                has_fact_key_filter = has_fact_key_in_filter(final_where_for_chroma)
                n_results = 100 if has_fact_key_filter else 20
                print(f"[hoi_thong_tin] B5c (V105): n_results={n_results} (fact_key_filter={has_fact_key_filter})")
                # --- 🚀 KẾT THÚC V105 🚀 ---
                
                chroma_start = time.time()
                results = await asyncio.to_thread(
                    vectorstore._collection.query,
                    query_embeddings=[query_vector],
                    n_results=n_results, 
                    where=final_where_for_chroma, 
                    where_document=final_where_doc_for_chroma, 
                    include=["documents", "metadatas"] 
                )
                perf_times['chroma'] = time.time() - chroma_start
                
                docs_goc_content = results.get("documents", [[]])[0] 
                docs_goc_metadatas = results.get("metadatas", [[]])[0] 
                ids_goc = results.get("ids", [[]])[0]
                
                # --- 🚀 SENTENCE WINDOW RETRIEVAL: Lấy parent khi tìm thấy chunk 🚀 ---
                sentence_window_start = time.time()  # ← 🚀 BẮT ĐẦU ĐO LƯỜNG
                final_docs = []
                final_metas = []
                seen_parents = set()  # Tránh trùng parent
                
                for doc, meta in zip(docs_goc_content, docs_goc_metadatas):
                    entry_type = meta.get("entry_type", "")
                    
                    if entry_type == "search_chunk":
                        # Tìm thấy chunk → lấy parent
                        parent_id = meta.get("parent_id")
                        if parent_id and parent_id not in seen_parents:
                            # Query parent document - ChromaDB chỉ cho 1 điều kiện where
                            parent_result = await asyncio.to_thread(
                                vectorstore._collection.get,
                                where={"parent_id": parent_id},
                                include=["metadatas"]
                            )
                            
                            # Lọc để tìm parent_doc (có thể có cả search_chunk cùng parent_id)
                            if parent_result and parent_result.get("metadatas"):
                                for p_meta in parent_result["metadatas"]:
                                    if p_meta.get("entry_type") == "parent_doc":
                                        parent_content = p_meta.get("full_content", doc)
                                        final_docs.append(parent_content)
                                        final_metas.append(p_meta)
                                        seen_parents.add(parent_id)
                                        print(f"[SENTENCE WINDOW] Chunk found → Retrieved parent: {parent_id[:30]}...")
                                        break
                                else:
                                    # Không tìm thấy parent_doc → giữ chunk
                                    final_docs.append(doc)
                                    final_metas.append(meta)
                            else:
                                # Query thất bại → giữ chunk
                                final_docs.append(doc)
                                final_metas.append(meta)
                        else:
                            # Parent đã lấy rồi hoặc không có parent_id
                            if parent_id not in seen_parents:
                                final_docs.append(doc)
                                final_metas.append(meta)
                    else:
                        # Không phải chunk → giữ nguyên
                        final_docs.append(doc)
                        final_metas.append(meta)
                
                docs_goc_content = final_docs
                docs_goc_metadatas = final_metas
                # --- 🚀 KẾT THÚC SENTENCE WINDOW RETRIEVAL 🚀 --- 
                perf_times['sentence_window'] = time.time() - sentence_window_start
                
                if not docs_goc_content:
                    return f"ℹ️ Đã tìm (Query V96: '{search_vector_query}', Filter: Where={final_where_for_chroma}) nhưng không tìm thấy."
                
                # --- 🚀 ĐO LƯỜNG SORTING 🚀 ---
                sort_start = time.time()
                final_results_to_display = _helper_sort_results_by_timestamp(
                    ids_goc, docs_goc_content, docs_goc_metadatas
                )
                perf_times['sorting'] = time.time() - sort_start
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
                # (SỬA V103) Hiển thị grid nếu có file/image, HOẶC có file_type_filter
                has_files_or_images = any(
                    meta and meta.get("file_type") != "text" 
                    for _, _, meta in final_results_to_display
                )
                
                if (bool(file_type_filter) or has_files_or_images) and not has_text_in_final_results:
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
                    
                    print(f"[hoi_thong_tin] B7: Đã có {len(candidates_for_llm_filter)} ứng viên file/ảnh.")
                    
                    # --- 🔎 KIỂM TRA SEARCH NOTES MODE 🔎 ---
                    search_notes_mode = cl.user_session.get("search_notes_mode", False)
                    
                    # --- 🚀 GPT SEMANTIC FILTER (MỚI) 🚀 ---
                    # LUÔN LUÔN gọi GPT để lọc theo ngữ cảnh (trừ query "xem tất cả")
                    q_low = cau_hoi.lower()
                    
                    # SKIP GPT filter khi query yêu cầu xem DANH SÁCH / TẤT CẢ
                    is_view_all = bool(re.search(r'\b(xem|hien thi|hiển thị)\s+(tat ca|tất cả|ds|danh sach|danh sách)\b', q_low)) or \
                                  bool(re.search(r'\b(ds|danh sach|danh sách)\s+(hinh|hình|anh|ảnh|file)\b', q_low)) or \
                                  bool(re.search(r'\b(tat ca|tất cả|all)\s+(hinh|hình|anh|ảnh|file)', q_low))
                    
                    if is_view_all:
                        print(f"[hoi_thong_tin] B7: Query 'XEM TẤT CẢ' → SKIP GPT Filter, hiển thị {len(candidates_for_llm_filter)} kết quả.")
                        final_filtered_results = candidates_for_llm_filter
                    elif search_notes_mode:
                        # MODE TÌM TRONG GHI CHÚ (người dùng nhấn nút)
                        print(f"[hoi_thong_tin] B7: MODE 'TÌM TRONG GHI CHÚ' → Chỉ tìm trong ghi chú...")
                        
                        # Lấy danh sách files ĐÃ hiển thị ở lần tìm theo TÊN (để loại bỏ)
                        already_shown_names = cl.user_session.get("last_search_results", [])
                        print(f"[hoi_thong_tin] B7 (GHI CHÚ): Loại bỏ {len(already_shown_names)} file đã hiển thị: {already_shown_names}")
                        
                        # Chỉ lấy candidates chưa được hiển thị
                        candidates_for_notes = [
                            item for item in candidates_for_llm_filter 
                            if item['name'] not in already_shown_names
                        ]
                        
                        if not candidates_for_notes:
                            print(f"[hoi_thong_tin] B7 (GHI CHÚ): Không còn file nào chưa hiển thị")
                            final_filtered_results = []
                        else:
                            # DEBUG: Hiển thị danh sách candidates cho notes
                            print(f"[hoi_thong_tin] B7 (GHI CHÚ): Có {len(candidates_for_notes)} candidates chưa hiển thị:")
                            for item in candidates_for_notes[:5]:  # Chỉ show 5 đầu
                                print(f"  - {item['name']} (note: {item['note'][:50]}...)")
                            
                            file_list_str = "\n".join([f"- {item['name']} ({item['note']})" for item in candidates_for_notes])
                            
                            note_filter_prompt = f"""
Bạn là trợ lý tìm kiếm file/ảnh theo GHI CHÚ.

DANH SÁCH FILE/ẢNH:
{file_list_str}

CÂU HỎI: "{cau_hoi}"

NHIỆM VỤ:
Tìm TẤT CẢ file/ảnh có GHI CHÚ (phần trong ngoặc) chứa từ khóa trong câu hỏi.

⚠️ QUY TẮC:
1. CHỈ so sánh với GHI CHÚ (phần trong ngoặc)
2. BỎ QUA TÊN FILE (phần trước ngoặc) - TÊN FILE KHÔNG QUAN TRỌNG
3. Nếu GHI CHÚ có BẤT KỲ từ khóa nào trong câu hỏi → CHỌN
4. Trả về TÊN FILE (phần trước ngoặc)

VÍ DỤ 1:
Q: "hinh may bao"
DS: 
- ảnh bộ dụng cụ (luu anh bo dung cu va may bao)
- may cat (luu anh may bao va may cat)
- ảnh gia đình (luu anh gia dinh)

PHÂN TÍCH GHI CHÚ:
- "luu anh bo dung cu va may bao": CÓ "may bao" → CHỌN ✅
- "luu anh may bao va may cat": CÓ "may bao" → CHỌN ✅  
- "luu anh gia dinh": KHÔNG có "may bao" → LOẠI ❌

TRẢ LỜI:
ảnh bộ dụng cụ
may cat

VÍ DỤ 2:
Q: "du lich"
DS:
- file công việc (luu file cong viec)
- ảnh biển (luu anh di bien du lich)

PHÂN TÍCH GHI CHÚ:
- "luu file cong viec": KHÔNG có "du lich" → LOẠI ❌
- "luu anh di bien du lich": CÓ "du lich" → CHỌN ✅

TRẢ LỜI:
ảnh biển

---

BÂY GIỜ TRẢ LỜI (MỖI TÊN FILE MỘT DÒNG, hoặc "NONE" nếu không tìm thấy):
"""
                            try:
                                note_resp = await llm.ainvoke(note_filter_prompt)
                                note_matched_str = note_resp.content.strip()
                                
                                if note_matched_str and note_matched_str != "NONE":
                                    note_matched_names = [n.strip() for n in note_matched_str.split('\n') if n.strip() and n.strip() != "NONE"]
                                    print(f"[hoi_thong_tin] B7 (GHI CHÚ): GPT chọn {len(note_matched_names)} file từ ghi chú: {note_matched_names}")
                                    
                                    final_filtered_results = [
                                        item for item in candidates_for_notes 
                                        if item['name'] in note_matched_names
                                    ]
                                else:
                                    print(f"[hoi_thong_tin] B7 (GHI CHÚ): Không tìm thấy trong ghi chú")
                                    final_filtered_results = []
                            except Exception as e_note:
                                print(f"[hoi_thong_tin] B7 (GHI CHÚ): Lỗi: {e_note}")
                                final_filtered_results = []
                    else:
                        # GỌI GPT LỌC THEO NGỮ CẢNH (TÌM THEO TÊN)
                        print(f"[hoi_thong_tin] B7: Query cụ thể → Gọi GPT Semantic Filter (TÌM THEO TÊN)...")
                        
                        # --- 🚀 PERFORMANCE: ĐO GPT SEMANTIC FILTER 🚀 ---
                        filter_start = time.time()
                        
                        # Chuẩn bị danh sách tên file cho GPT (GIỮ GHI CHÚ để GPT có context nhưng bảo BỎ QUA)
                        file_list_str = "\n".join([f"- {item['name']} ({item['note']})" for item in candidates_for_llm_filter])
                        
                        filter_prompt = f"""
Bạn là trợ lý lọc file/ảnh THÔNG MINH theo TÊN FILE.

DANH SÁCH FILE/ẢNH:
{file_list_str}

CÂU HỎI: "{cau_hoi}"

NHIỆM VỤ:
Tìm TẤT CẢ file/ảnh có TÊN (phần trước ngoặc) KHỚP với câu hỏi.

⚠️ QUY TẮC NGHIÊM NGẶT:
1. CHỈ so sánh TÊN FILE (phần trước ngoặc)
2. Ghi chú (trong ngoặc) chỉ để THAM KHẢO context - KHÔNG dùng để quyết định
3. So sánh CHÍNH XÁC các từ khóa QUAN TRỌNG (danh từ chính)
4. Bỏ qua các từ không quan trọng như "hinh", "anh", "file" (chỉ là loại)

VÍ DỤ 1:
Q: "hinh may bao"
DS: 
- may cat (luu anh may bao va may cat)
- ảnh máy bao (luu anh may bao va may cat)
- anh may bao (luu anh may bao va may cat)

PHÂN TÍCH:
- Từ khóa QUAN TRỌNG: "may", "bao" (bỏ "hinh/anh" vì chỉ là loại)
- "may cat": Có "may" ✓ nhưng KHÔNG có "bao" ✗ → LOẠI ❌
- "ảnh máy bao": Có "may" ✓ và "bao" ✓ → CHỌN ✅
- "anh may bao": Có "may" ✓ và "bao" ✓ → CHỌN ✅

TRẢ LỜI:
ảnh máy bao
anh may bao

---

VÍ DỤ 2:
Q: "hinh may cat"  
DS:
- ảnh máy cắt 2 (luu anh may cat)
- ảnh máy bao (luu anh may bao va may cat)
- may cat (luu anh may bao va may cat)

PHÂN TÍCH:
- Từ khóa QUAN TRỌNG: "may", "cat" (bỏ "hinh/anh")
- "ảnh máy cắt 2": Có "may" ✓ và "cat/cắt" ✓ → CHỌN ✅
- "ảnh máy bao": Có "may" ✓ nhưng KHÔNG có "cat" ✗ → LOẠI ❌
- "may cat": Có "may" ✓ và "cat" ✓ → CHỌN ✅

TRẢ LỜI:
ảnh máy cắt 2
may cat

---

VÍ DỤ 3:
Q: "may bao"
DS:
- máy bao (ghi chu abc)
- may cat (ghi chu xyz)
- ảnh máy bao (ghi chu 123)

PHÂN TÍCH:
- Từ khóa QUAN TRỌNG: "may", "bao"
- "máy bao": Có CẢ 2 từ "may" ✓ và "bao" ✓ → CHỌN ✅
- "may cat": Có "may" ✓ nhưng KHÔNG có "bao" ✗ → LOẠI ❌
- "ảnh máy bao": Có "may" ✓ và "bao" ✓ → CHỌN ✅

TRẢ LỜI:
máy bao
ảnh máy bao

---

💡 NGUYÊN TẮC: TẤT CẢ từ khóa QUAN TRỌNG (danh từ chính) phải có trong TÊN FILE!

BÂY GIỜ TRẢ LỜI (MỖI TÊN MỘT DÒNG, hoặc "NONE" nếu không khớp):
"""
                        
                        try:
                            filter_resp = await llm.ainvoke(filter_prompt)
                            perf_times['gpt_filter'] = time.time() - filter_start
                            
                            matched_str = filter_resp.content.strip()
                            
                            if matched_str and matched_str != "NONE":
                                matched_names = [n.strip() for n in matched_str.split('\n') if n.strip() and n.strip() != "NONE"]
                                print(f"[hoi_thong_tin] B7: GPT chọn {len(matched_names)} file (tìm theo TÊN): {matched_names[:3]}...")
                                
                                # Lọc candidates theo tên GPT chọn (FUZZY MATCH)
                                def normalize_name(name):
                                    """Chuẩn hóa tên: lowercase, bỏ dấu, bỏ ảnh/anh/hinh ở đầu"""
                                    name = unidecode.unidecode(name.lower().strip())
                                    name = re.sub(r'^(anh|hinh)\s+', '', name)  # Bỏ "anh/hinh" ở đầu
                                    return name
                                
                                # Chuẩn hóa danh sách GPT chọn
                                normalized_matched = {normalize_name(n) for n in matched_names}
                                
                                final_filtered_results = []
                                for item in candidates_for_llm_filter:
                                    norm_item_name = normalize_name(item['name'])
                                    # Kiểm tra exact match HOẶC contains
                                    if norm_item_name in normalized_matched or any(nm in norm_item_name for nm in normalized_matched):
                                        final_filtered_results.append(item)
                                        print(f"[DEBUG] ✅ Matched: '{item['name']}' (normalized: '{norm_item_name}')")
                                    else:
                                        print(f"[DEBUG] ❌ Skipped: '{item['name']}' (normalized: '{norm_item_name}')")
                            else:
                                print(f"[hoi_thong_tin] B7: GPT trả về NONE, không tìm thấy theo TÊN")
                                final_filtered_results = []
                        except Exception as e_gpt:
                            print(f"[hoi_thong_tin] B7: Lỗi GPT filter: {e_gpt}, fallback hiển thị tất cả")
                            final_filtered_results = candidates_for_llm_filter
                    # --- 🚀 KẾT THÚC GPT SEMANTIC FILTER 🚀 ---
                    
                    # AUTO-SEARCH IN NOTES nếu không tìm thấy kết quả trong TÊN
                    if not final_filtered_results and not search_notes_mode:
                        print(f"[hoi_thong_tin] B7: Không tìm thấy theo TÊN → Tự động tìm trong GHI CHÚ...")
                        await cl.Message(content=f"ℹ️ Không tìm thấy file/ảnh theo TÊN với '{cau_hoi}'. Đang tự động tìm trong **ghi chú**...").send()
                        
                        # Thay vì gọi đệ quy, chuyển sang chế độ tìm trong ghi chú NGAY
                        search_notes_mode = True
                        
                        # Lấy danh sách files ĐÃ hiển thị (trống vì không có kết quả từ tên)
                        already_shown_names = []
                        
                        # Chỉ lấy candidates chưa được hiển thị (tất cả vì chưa hiển thị gì)
                        candidates_for_notes = candidates_for_llm_filter
                        
                        if not candidates_for_notes:
                            return f"ℹ️ Không tìm thấy file/ảnh nào."
                        else:
                            file_list_str = "\n".join([f"- {item['name']} ({item['note']})" for item in candidates_for_notes])
                            
                            note_filter_prompt = f"""
Bạn là trợ lý tìm kiếm file/ảnh theo GHI CHÚ.

DANH SÁCH FILE/ẢNH:
{file_list_str}

CÂU HỎI: "{cau_hoi}"

NHIỆM VỤ:
Tìm file/ảnh có GHI CHÚ (phần trong ngoặc) khớp với câu hỏi.

QUY TẮC:
1. CHỈ so sánh với GHI CHÚ (phần trong ngoặc), BỎ QUA TÊN FILE
2. Trả về TÊN FILE (phần trước ngoặc) nếu ghi chú khớp
3. Nếu không khớp → "NONE"

VÍ DỤ:
Q: "anh may bao"
DS: 
- ảnh bộ dụng cụ (luu anh bo dung cu va may bao)
- ảnh gia đình (luu anh gia dinh)

→ ảnh bộ dụng cụ
(vì ghi chú có "may bao", dù TÊN FILE không có "may bao")

TRẢ LỜI (CHỈ TÊN hoặc NONE):
"""
                            try:
                                note_resp = await llm.ainvoke(note_filter_prompt)
                                note_matched_str = note_resp.content.strip()
                                
                                if note_matched_str and note_matched_str != "NONE":
                                    note_matched_names = [n.strip() for n in note_matched_str.split('\n') if n.strip() and n.strip() != "NONE"]
                                    print(f"[hoi_thong_tin] B7 (AUTO GHI CHÚ): GPT chọn {len(note_matched_names)} file từ ghi chú: {note_matched_names}")
                                    
                                    final_filtered_results = [
                                        item for item in candidates_for_notes 
                                        if item['name'] in note_matched_names
                                    ]
                                else:
                                    print(f"[hoi_thong_tin] B7 (AUTO GHI CHÚ): Không tìm thấy trong ghi chú")
                                    final_filtered_results = []
                            except Exception as e_note:
                                print(f"[hoi_thong_tin] B7 (AUTO GHI CHÚ): Lỗi: {e_note}")
                                final_filtered_results = []
                        
                        # Nếu vẫn không tìm thấy
                        if not final_filtered_results:
                            return f"ℹ️ Không tìm thấy file/ảnh nào trong GHI CHÚ với '{cau_hoi}'."
                    elif not final_filtered_results and search_notes_mode:
                        return f"ℹ️ Không tìm thấy file/ảnh nào trong GHI CHÚ với '{cau_hoi}'."
                    
                    # Lưu query để dùng cho nút "Tìm thêm trong ghi chú"
                    has_note_search_button = len(final_filtered_results) > 0 and not is_view_all and not search_notes_mode
                    stored_query = cau_hoi
                    
                    # LƯU DANH SÁCH FILE ĐÃ HIỂN THỊ (để tránh hiển thị lại khi tìm trong ghi chú)
                    if not search_notes_mode:
                        # Chỉ lưu khi tìm theo TÊN (không lưu khi tìm trong ghi chú)
                        shown_names = [item['name'] for item in final_filtered_results]
                        cl.user_session.set("last_search_results", shown_names)
                        print(f"[hoi_thong_tin] B7: Lưu {len(shown_names)} file đã hiển thị để tránh duplicate")
                    # --- 🚀 KẾT THÚC FALLBACK 🚀 ---
                    
                    # V102: Phân loại ảnh theo fact_key và file
                    from collections import defaultdict
                    images_by_fact_key = defaultdict(list)
                    files = []
                    
                    # Hiển thị header nếu kết quả từ tìm kiếm ghi chú
                    if search_notes_mode:
                        await cl.Message(content="✅ **Kết quả từ tìm kiếm trong ghi chú:**").send()
                    
                    for item in final_filtered_results:
                        doc_id = item['id']; metadata = item['metadata']
                        content = metadata.get("original_content"); file_type = metadata.get("file_type", "file")
                        fact_key = metadata.get("fact_key", None)  # Lấy fact_key từ metadata
                        fact_label = metadata.get("fact_label", None)  # Lấy fact_label tiếng Việt từ metadata
                        
                        # Debug: In ra fact_key và fact_label để kiểm tra
                        print(f"[DEBUG] doc_id={doc_id}, fact_key={fact_key}, fact_label={fact_label}, file_type={file_type}")
                        
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
                                    "fact_key": fact_key,
                                    "fact_label": fact_label
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
                    print(f"[DEBUG] Tổng số files (không phải ảnh): {len(files)}")
                    
                    for fact_key, images_list in images_by_fact_key.items():
                        print(f"[DEBUG] fact_key='{fact_key}', số ảnh={len(images_list)}")
                        
                        if len(images_list) >= 2:
                            # Chuẩ bị dữ liệu cho ImageGrid
                            images_data = []
                            actions = []
                            for img in images_list:
                                # Skip nếu file không tồn tại
                                if not os.path.exists(img['path']):
                                    print(f"[WARNING] ❌ File không tồn tại, skip: {img['path']} (name={img['name']})")
                                    continue
                                else:
                                    print(f"[DEBUG] ✅ File tồn tại: {img['path']}")
                                    
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
                            
                            # Tên album: Dùng fact_label từ metadata (tiếng Việt có dấu)
                            # Lấy fact_label từ ảnh đầu tiên trong group (vì tất cả ảnh cùng fact_key đều có cùng fact_label)
                            display_label = images_list[0].get('fact_label')
                            if not display_label:
                                # Fallback nếu không có fact_label trong metadata
                                if fact_key == images_list[0]['name']:
                                    display_label = fact_key  # Dùng tên file gốc
                                else:
                                    display_label = fact_key.replace("_", " ").title()
                            
                            # Đếm số ảnh THỰC TẾ sau khi lọc file không tồn tại
                            actual_count = len(images_data)
                            print(f"[DEBUG] Hiển thị album: '{display_label}' với {actual_count} ảnh (gốc: {len(images_list)})")
                            
                            # Chỉ hiển thị nếu còn ảnh
                            if actual_count == 0:
                                print(f"[WARNING] Album '{display_label}' không còn ảnh nào tồn tại, skip!")
                                continue
                            elif actual_count == 1:
                                # Chỉ 1 ảnh → hiển thị đơn lẻ
                                el = cl.CustomElement(
                                    name="ImageGrid",
                                    props={"title": f"📸 {display_label} (1 ảnh)", "images": images_data},
                                    display="inline",
                                )
                                await cl.Message(content="", elements=[el]).send()
                            else:
                                # Nhiều ảnh → hiển thị album
                                el = cl.CustomElement(
                                    name="ImageGrid",
                                    props={"title": f"📸 {display_label} ({actual_count} ảnh)", "images": images_data},
                                    display="inline",
                                )
                                await cl.Message(content="", elements=[el]).send()
                            
                            # ❌ KHÔNG GỬI actions riêng - ImageGrid đã có nút Tải/Xóa rồi!
                        elif len(images_list) == 1:
                            # 1 ảnh: Dùng ImageGrid luôn (thống nhất UI)
                            img = images_list[0]
                            
                            # Skip nếu file không tồn tại
                            if not os.path.exists(img['path']):
                                print(f"[WARNING] ❌ File (đơn) không tồn tại, skip: {img['path']} (name={img['name']})")
                                continue
                            else:
                                print(f"[DEBUG] ✅ File (đơn) tồn tại: {img['path']}")
                            
                            # Lấy fact_label từ ảnh
                            single_label = img.get('fact_label')
                            if not single_label:
                                if fact_key == img['name']:
                                    single_label = fact_key
                                else:
                                    single_label = fact_key.replace("_", " ").title()
                            
                            images_data = [{
                                "name": img['name'],
                                "note": img['note'],
                                "url": f"/public/files/{img['saved_name']}",
                                "path": img['path'],
                                "file_path": img['path'],
                                "doc_id": img['doc_id']
                            }]
                            el = cl.CustomElement(
                                name="ImageGrid",
                                props={"title": f"📸 {single_label} (1 ảnh)", "images": images_data},
                                display="inline",
                            )
                            await cl.Message(content="", elements=[el]).send()
                    
                    # Hiển thị files (nếu có) - Dùng FileGrid
                    if files:
                        files_data = []
                        for f in files:
                            files_data.append({
                                "name": f['name'],
                                "note": f['note'],
                                "type": f.get('file_type', 'FILE').upper(),
                                "url": f"/public/files/{f['saved_name']}",
                                "file_path": f['path'],
                                "doc_id": f['doc_id']
                            })
                        
                        el = cl.CustomElement(
                            name="FileGrid",
                            props={"title": f"📁 Tài liệu ({len(files)})", "files": files_data},
                            display="inline",
                        )
                        await cl.Message(content="", elements=[el]).send()
                    
                    # ✨ NÚT TÌM THÊM TRONG GHI CHÚ ✨
                    if has_note_search_button:
                        note_search_action = cl.Action(
                            name="search_in_notes",
                            payload={"query": stored_query, "search_notes": True},
                            label="🔍 Tìm thêm trong ghi chú",
                            description="Tìm kiếm file/ảnh có ghi chú khớp với câu hỏi"
                        )
                        await cl.Message(content="💡 Nếu muốn tìm thêm trong **ghi chú**, nhấn nút bên dưới:", actions=[note_search_action]).send()
                    
                    # Return rỗng để Agent không hiển thị thêm message
                    return ""
                
                else: 
                    print(f"[hoi_thong_tin] B7 (Sửa lỗi V93): Gửi {len(final_results_to_display)} context (ĐÃ SẮP XẾP) cho RAG Q&A (Prompt V93)...")
                    
                    final_context_list = [content for _, content, _ in final_results_to_display if content]
                    context_tho = "\n---\n".join(final_context_list)
                    if not context_tho.strip(): return "ℹ️ Đã lọc, nhưng nội dung của chúng bị rỗng."
                    
                    print(f"[hoi_thong_tin] B8: Gửi context ({len(context_tho)} chars) cho LLM để TRẢ LỜI...")
                    
                    # --- 🚀 ĐO LƯỜNG LLM ANSWER 🚀 ---
                    llm_answer_start = time.time()
                    
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
                    
                    5. ⚠️ ĐẶC BIỆT QUAN TRỌNG - KHI CÓ IP/HOSTNAME/ID CỤ THỂ:
                       - Nếu Input hỏi về "10.1.2.15" → CHỈ trả lời thông tin ĐÚNG về 10.1.2.15
                       - KHÔNG lấy nhầm thông tin của 10.1.2.200 hay IP khác
                       - Nếu Context có NHIỀU IP cùng lúc → TÌM phần liên quan CHÍNH XÁC với IP trong Input
                       - Nếu Context KHÔNG CÓ thông tin cụ thể về IP đó → Nói "Không tìm thấy thông tin về [IP] trong context"
                    
                    Ví dụ:
                    Context:
                    ```
                    10.1.2.15, 10.1.2.16
                    user: root
                    pass: CaoHung@2019esx
                    ---
                    Link: https://10.1.2.200
                    user: administrator@caohung.local
                    pass: P@ssw0rd!@#2504.
                    ```
                    
                    Input: "user pass của 10.1.2.15"
                    Câu trả lời ĐÚNG: user: root, pass: CaoHung@2019esx
                    
                    Input: "user pass của 10.1.2.200"
                    Câu trả lời ĐÚNG: user: administrator@caohung.local, pass: P@ssw0rd!@#2504.

                    Ví dụ Context (Đã sắp xếp):
                    tôi CHỈ thích ăn phở
                    ---
                    tôi thích ăn bún bò
                    ---
                    tôi thích ăn cơm
                    
                    Input: tôi thích ăn gì?
                    Câu trả lời (ĐÚNG): Bạn CHỈ thích ăn phở.
                    
                    Input: {cau_hoi}
                    Câu trả lời (dựa trên thông tin MỚI NHẤT và CHÍNH XÁC với Input):
                    """
                    
                    resp = await llm.ainvoke(custom_prompt)
                    perf_times['llm_answer'] = time.time() - llm_answer_start
                    llm_answer = resp.content.strip()
                    
                    if not llm_answer or "không có thông tin" in llm_answer.lower() or "không tìm thấy" in llm_answer.lower():
                        print(f"LLM RAG Q&A (V93) trả về không có gì: {llm_answer}")
                        
                        # --- 🚀 FALLBACK: GPT FILENAME MATCHING 🚀 ---
                        # Nếu LLM không tìm thấy → lấy TẤT CẢ tên file, gửi GPT lọc
                        print("[hoi_thong_tin] FALLBACK: Lấy tất cả tên file, gửi GPT lọc...")
                        
                        if file_type_filter:
                            # Tìm trong ChromaDB với filter file_type
                            try:
                                all_files_results = vectorstore.get(
                                    where={
                                        "$and": [
                                            {"user_id": user_id_str},
                                            file_type_filter
                                        ]
                                    },
                                    include=["metadatas"]
                                )
                                
                                # Lấy TẤT CẢ tên file
                                all_file_names = []
                                file_map = {}  # doc_id -> metadata
                                
                                for doc_id, metadata in zip(all_files_results['ids'], all_files_results['metadatas']):
                                    if not metadata:
                                        continue
                                    
                                    original_content = metadata.get("original_content", "")
                                    name_match = re.search(r"name=([^|]+)", original_content)
                                    note_match = re.search(r"note=([^|]+)", original_content)
                                    
                                    if not name_match:
                                        continue
                                    
                                    file_name = name_match.group(1).strip()
                                    file_note = note_match.group(1).strip() if note_match else ""
                                    
                                    all_file_names.append(f"- {file_name} ({file_note})")
                                    file_map[file_name] = {
                                        "doc_id": doc_id,
                                        "metadata": metadata,
                                        "note": file_note
                                    }
                                
                                if all_file_names:
                                    print(f"[FALLBACK GPT] Có {len(all_file_names)} file, gửi GPT lọc...")
                                    
                                    # Gọi GPT để lọc
                                    filter_prompt = f"""
Bạn là trợ lý tìm kiếm file/ảnh THÔNG MINH.

DANH SÁCH FILE/ẢNH:
{chr(10).join(all_file_names)}

CÂU HỎI CỦA USER: "{cau_hoi}"

NHIỆM VỤ:
Hãy TÌM và LIỆT KÊ TẤT CẢ tên file/ảnh KHỚP với câu hỏi của user.

QUY TẮC:
1. Hiểu NGỮ CẢNH của câu hỏi (ví dụ: "hà nội" khớp với "du lịch hà nội", "ảnh hà nội")
2. CHỈ trả về tên file CHÍNH XÁC từ danh sách trên (giữ nguyên dấu tiếng Việt)
3. Nếu KHÔNG tìm thấy file nào khớp → trả về "NONE"
4. Nếu tìm thấy → trả về DANH SÁCH tên file, mỗi tên 1 dòng, KHÔNG thêm dấu "-" hay số thứ tự

VÍ DỤ:
Input: "cho toi anh ha noi"
Danh sách có: "ảnh du lịch hà nội", "ảnh đi chơi gia đình"
Output:
ảnh du lịch hà nội

Input: "anh di ha noi"
Danh sách có: "ảnh du lịch hà nội", "ảnh cá nhân"
Output:
NONE
(vì "đi hà nội" ≠ "du lịch hà nội", ngữ cảnh khác)

BÂY GIỜ HÃY TRẢ LỜI (CHỈ TÊN FILE hoặc NONE):
"""
                                    
                                    filter_resp = await llm.ainvoke(filter_prompt)
                                    matched_names_str = filter_resp.content.strip()
                                    
                                    if matched_names_str and matched_names_str != "NONE":
                                        # Parse tên file từ response
                                        matched_names = [line.strip() for line in matched_names_str.split('\n') if line.strip()]
                                        
                                        print(f"[FALLBACK GPT] GPT chọn {len(matched_names)} file: {matched_names}")
                                        
                                        # Lấy metadata của file được chọn
                                        final_filtered_results = []
                                        for name in matched_names:
                                            if name in file_map:
                                                file_info = file_map[name]
                                                final_filtered_results.append({
                                                    "id": file_info["doc_id"],
                                                    "name": name,
                                                    "note": file_info["note"],
                                                    "metadata": file_info["metadata"]
                                                })
                                        
                                        if final_filtered_results:
                                            # Hiển thị (dùng lại code hiển thị từ B7)
                                            images = []
                                            files = []
                                            images_by_fact_key = defaultdict(list)
                                            
                                            for item in final_filtered_results:
                                                doc_id = item["id"]
                                                goc_name = item["name"]
                                                goc_note = item["note"]
                                                metadata = item["metadata"]
                                                
                                                file_type = metadata.get("file_type", "text")
                                                saved_name = metadata.get("saved_name", "")
                                                fact_key = metadata.get("fact_key", "general")
                                                fact_label = metadata.get("fact_label", fact_key.replace("_", " ").title())
                                                
                                                full_path = os.path.join(PUBLIC_FILES_DIR, saved_name)
                                                
                                                if file_type == "image":
                                                    images_by_fact_key[fact_key].append({
                                                        "doc_id": doc_id,
                                                        "path": full_path,
                                                        "name": goc_name,
                                                        "note": goc_note,
                                                        "saved_name": saved_name,
                                                        "fact_key": fact_key,
                                                        "fact_label": fact_label
                                                })
                                            
                                            # Hiển thị ảnh theo album
                                            for fact_key, images_list in images_by_fact_key.items():
                                                if len(images_list) >= 2:
                                                    images_data = []
                                                    for img in images_list:
                                                        if not os.path.exists(img['path']):
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
                                                    
                                                    if images_data:
                                                        fact_label = images_list[0]['fact_label']
                                                        await cl.Message(
                                                            content=f"📁 **{fact_label}** ({len(images_data)} ảnh - GPT lọc)",
                                                            elements=[
                                                                cl.CustomElement(
                                                                    name="ImageGrid",
                                                                    props={"title": fact_label, "images": images_data}
                                                                )
                                                            ]
                                                        ).send()
                                            
                                            return f"✅ Đã tìm thấy {len(final_filtered_results)} file/ảnh khớp với '{cau_hoi}' (GPT lọc theo tên file)"
                                    else:
                                        print("[FALLBACK GPT] GPT trả về NONE, không tìm thấy file khớp")
                                else:
                                    print("[FALLBACK GPT] Không có file nào trong DB")
                            except Exception as e_fallback:
                                print(f"[FALLBACK GPT] Lỗi: {e_fallback}")
                                import traceback
                                traceback.print_exc()
                        
                        # Nếu vẫn không tìm thấy
                        return f"ℹ️ Tôi tìm thấy {len(final_results_to_display)} mục liên quan, nhưng không tìm thấy câu trả lời chính xác cho '{cau_hoi}' trong đó."
                    else:
                        return llm_answer
                    
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi RAG (Sửa lỗi V96): {e}"
        finally:
            # --- 🚀 PERFORMANCE SUMMARY (V104) 🚀 ---
            total_time = time.time() - perf_start
            
            # Tính thời gian các bước
            classify_time = perf_times.get('classify', 0)
            embed_time = perf_times.get('embeddings', 0)
            chroma_time = perf_times.get('chroma', 0)
            sentence_window_time = perf_times.get('sentence_window', 0)
            sort_time = perf_times.get('sorting', 0)
            filter_time = perf_times.get('gpt_filter', 0)
            llm_answer_time = perf_times.get('llm_answer', 0)
            
            # V111: Nếu chạy song song, classify_time đã bao gồm embed_time
            parallel_note = ""
            if classify_time > 0 and embed_time == 0:
                parallel_note = " (bao gồm Embeddings ⚡)"
            
            # Log summary
            print(f"\n{'='*60}")
            print(f"[PERFORMANCE V111] Query: '{cau_hoi[:50]}'")
            print(f"{'='*60}")
            print(f"  GPT Classify:      {classify_time:.3f}s {'(SKIPPED ⚡)' if classify_time == 0 else parallel_note}")
            print(f"  OpenAI Embeddings: {embed_time:.3f}s {'(Song song ⚡)' if embed_time == 0 and classify_time > 0 else ''}")
            print(f"  ChromaDB Search:   {chroma_time:.3f}s")
            print(f"  Sentence Window:   {sentence_window_time:.3f}s")
            print(f"  Sorting Results:   {sort_time:.3f}s")
            print(f"  GPT Filter:        {filter_time:.3f}s")
            print(f"  LLM Answer:        {llm_answer_time:.3f}s {'(SKIPPED ⚡)' if llm_answer_time == 0 else ''}")
            print(f"  {'─'*58}")
            print(f"  TOTAL TIME:        {total_time:.3f}s")
            print(f"{'='*60}\n")
    
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
        🔍 TÌM KIẾM file/ảnh theo TÊN CỤ THỂ (exact name match).
        
        ✅ DÙNG KHI user muốn TÌM file có TÊN CHÍNH XÁC:
        - "cho tôi file có tên 2022" → tu_khoa = "2022"
        - "cho tôi file ds 2022" → tu_khoa = "ds 2022"  
        - "file báo cáo tháng 5" → tu_khoa = "báo cáo tháng 5"
        - "tìm file tên là xyz" → tu_khoa = "xyz"
        
        ❌ KHÔNG DÙNG khi:
        - User hỏi về CHỦ ĐỀ/NỘI DUNG (dùng hoi_thong_tin): "hình về du lịch", "ảnh thuộc danh mục du lịch"
        - User muốn xem TẤT CẢ file (dùng xem_danh_sach_file)
        
        Trả về file/ảnh có TÊN khớp nhất (có LLM smart filter).
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
        
        
    # OLD TOOLS - DISABLED (replaced by xem_danh_sach_cong_viec)
    # @tool("xem_viec_chua_hoan_thanh")
    # async def xem_viec_chua_hoan_thanh() -> str:
    #     """Hiển thị tất cả các CÔNG VIỆC (tasks) CHƯA hoàn thành trong UI."""
    #     try: 
    #         await ui_show_uncompleted_tasks()
    #     except Exception as e: 
    #         return f"❌ Lỗi khi hiển thị danh sách công việc: {e}"
    #     return "✅ Đã liệt kê các công việc chưa hoàn thành."
    
    # @tool("xem_viec_da_hoan_thanh")
    # async def xem_viec_da_hoan_thanh() -> str:
    #     """Hiển thị tất cả các CÔNG VIỆC (tasks) ĐÃ hoàn thành trong UI."""
    #     try: 
    #         await ui_show_completed_tasks()
    #     except Exception as e: 
    #         return f"❌ Lỗi khi hiển thị danh sách công việc đã hoàn thành: {e}"
    #     return "✅ Đã liệt kê các công việc đã hoàn thành."
    # (Tool xem_danh_sach_user của bạn bắt đầu từ đây...)
    
    # (DÁN TOOL MỚI NÀY VÀO KHOẢNG DÒNG 4650)
    @tool("tim_cong_viec_theo_ngay", args_schema=TimCongViecSchema)
    async def tim_cong_viec_theo_ngay(thoi_gian: str) -> str:
        """
        Tìm và hiển thị các công việc (tasks) CHƯA HOÀN THÀNH
        dựa trên một khoảng thời gian (ví dụ: 'ngày mai', 'hôm nay').
        """
        import task_manager as tm
        
        llm = cl.user_session.get("llm_logic")
        user_email = cl.user_session.get("user_email")
        
        if not llm:
            return "❌ Lỗi: Không tìm thấy llm_logic."
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
            
        try:
            # Parse date from natural language
            dt_target = await _llm_parse_dt(llm, thoi_gian)
            
            # Default: filter by day
            start_dt = _get_start_of_day(dt_target)
            end_dt = _get_end_of_day(dt_target)
            
            # Special cases
            low_q = thoi_gian.lower()
            now = datetime.now(VN_TZ)
            
            if "tuần này" in low_q or "tuan nay" in low_q:
                start_dt = _get_start_of_day(now - timedelta(days=now.weekday()))
                end_dt = _get_end_of_day(start_dt + timedelta(days=6))
            elif "tháng này" in low_q or "thang nay" in low_q:
                start_dt = _get_start_of_day(now.replace(day=1))
                last_day_num = calendar.monthrange(now.year, now.month)[1]
                end_dt = _get_end_of_day(now.replace(day=last_day_num))
            
            # Get tasks
            tasks = await asyncio.to_thread(
                tm.get_tasks,
                user_email=user_email,
                status="uncompleted",
                start_date=start_dt,
                end_date=end_dt
            )
            
            if not tasks:
                return f"📭 Không có công việc nào trong khoảng {_fmt_dt(start_dt)} - {_fmt_dt(end_dt)}"
            
            # Build markdown table
            md_content = f"📋 **Công việc {thoi_gian}** ({len(tasks)} tasks)\n\n"
            md_content += f"📅 Từ {_fmt_dt(start_dt)} đến {_fmt_dt(end_dt)}\n\n"
            
            md_content += "| ID | Tiêu đề | Hạn | Priority |\n"
            md_content += "|---|---|---|---|\n"
            
            for task in tasks[:20]:
                priority = task.get('priority', 'medium').upper()
                md_content += f"| {task['id']} | {task['title']} | {task.get('due_date', 'N/A')} | {priority} |\n"
            
            await cl.Message(content=md_content).send()
            
            return f"✅ Đã hiển thị {len(tasks)} công việc"

        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi khi tìm công việc: {e}"
    @tool("tim_cong_viec_qua_han")
    async def tim_cong_viec_qua_han() -> str:
        """
        Tìm và hiển thị các công việc (tasks) CHƯA HOÀN THÀNH
        có ngày HẠN CHÓT (Due Date) ĐÃ QUA (quá hạn).
        """
        import task_manager as tm
        
        user_email = cl.user_session.get("user_email")
        if not user_email:
            return "❌ Lỗi: Không tìm thấy user_email"
        
        now_vn = datetime.now(VN_TZ)
        yesterday_end = _get_end_of_day(now_vn - timedelta(days=1))
        
        try:
            # Get overdue tasks
            tasks = await asyncio.to_thread(
                tm.get_tasks,
                user_email=user_email,
                status="uncompleted",
                end_date=yesterday_end
            )
            
            if not tasks:
                return "✅ Không có công việc quá hạn"
            
            # Build markdown table
            md_content = f"⚠️ **Công việc quá hạn** ({len(tasks)} tasks)\n\n"
            
            md_content += "| ID | Tiêu đề | Hạn | Priority |\n"
            md_content += "|---|---|---|---|\n"
            
            for task in tasks[:20]:
                priority = task.get('priority', 'medium').upper()
                md_content += f"| {task['id']} | {task['title']} | {task.get('due_date', 'N/A')} | {priority} |\n"
            
            await cl.Message(content=md_content).send()
            
            return f"✅ Đã hiển thị {len(tasks)} công việc quá hạn"
            
        except Exception as e:
            import traceback; traceback.print_exc()
            return f"❌ Lỗi: {e}"
    
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
        "sua_cong_viec": {
            "rule": "(SỬA CÔNG VIỆC) Nếu 'input' yêu cầu 'sửa công việc', 'cập nhật task', 'thay đổi task', 'edit task' -> Dùng `sua_cong_viec`.",
            "tool": sua_cong_viec
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
        "tao_cong_viec": {
            "rule": "(TẠO TASK MỚI - ƯU TIÊN 2) Nếu 'input' yêu cầu 'tạo công việc', 'thêm task', 'tạo task mới' -> Dùng `tao_cong_viec`.",
            "tool": tao_cong_viec
        },
        "danh_dau_hoan_thanh": {
            "rule": "(HOÀN THÀNH TASK) Nếu 'input' yêu cầu 'đánh dấu hoàn thành', 'hoàn thành công việc', 'xong task' -> Dùng `danh_dau_hoan_thanh`.",
            "tool": danh_dau_hoan_thanh
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
        "xem_danh_sach_cong_viec": {
            "rule": "(XEM TẤT CẢ TASK - ƯU TIÊN 1) Nếu 'input' yêu cầu 'xem công việc', 'xem task', 'danh sách công việc' -> Dùng `xem_danh_sach_cong_viec`.",
            "tool": xem_danh_sach_cong_viec
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

    # 2.2. Phân loại tool vào các nhóm (theo MODE - V110)
    current_mode = cl.user_session.get("mode", "AGENT")
    
    # SELL MODE: Chỉ có tool sản phẩm/doanh số
    if current_mode == "SELL":
        ask_tools_data = {
            "get_product_detail": base_tools_data["get_product_detail"],
            "searchlistproductnew": base_tools_data["searchlistproductnew"],
            "goi_chart_dashboard": base_tools_data["goi_chart_dashboard"],
            "hien_thi_web": base_tools_data["hien_thi_web"],
        }
    # AGENT MODE: Chỉ có tool RAG/file/task
    else:
        ask_tools_data = {
            "hien_thi_web": base_tools_data["hien_thi_web"],
            "hoi_thong_tin": base_tools_data["hoi_thong_tin"],
            "tim_cong_viec_qua_han": base_tools_data["tim_cong_viec_qua_han"],
            "tim_cong_viec_theo_ngay": base_tools_data["tim_cong_viec_theo_ngay"],
            "xem_danh_sach_cong_viec": base_tools_data["xem_danh_sach_cong_viec"],
            "xem_lich_nhac": base_tools_data["xem_lich_nhac"],
            "xem_bo_nho": base_tools_data["xem_bo_nho"],
            "tim_kiem_file": base_tools_data["tim_kiem_file"],
            "xem_danh_sach_file": base_tools_data["xem_danh_sach_file"],
        }
    
    save_tools_data = {
        "luu_thong_tin": base_tools_data["luu_thong_tin"],
        "dat_lich_cong_viec": base_tools_data["dat_lich_cong_viec"],
        "dat_lich_nhac_nho": base_tools_data["dat_lich_nhac_nho"],
        "tao_cong_viec": base_tools_data["tao_cong_viec"],
    }
    
    delete_tools_data = {
        "xoa_file_da_luu": base_tools_data["xoa_file_da_luu"],
        "xoa_cong_viec": base_tools_data["xoa_cong_viec"],
        "xoa_ghi_chu": base_tools_data["xoa_ghi_chu"],
        "danh_dau_hoan_thanh": base_tools_data["danh_dau_hoan_thanh"],
        "sua_cong_viec": base_tools_data["sua_cong_viec"],
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

⚠️ QUAN TRỌNG - KHI GỌI TOOL:
- GIỮ NGUYÊN các từ khóa quan trọng từ input gốc của user
- TUYỆT ĐỐI KHÔNG được bỏ các từ: "ảnh", "hình", "file", "word", "excel", "pdf"
- VD: "cho anh du lich ha noi" → gọi hoi_thong_tin với "anh du lich ha noi" (GIỮ chữ "anh")
- VD: "xem ds file word" → gọi hoi_thong_tin với "file word" (GIỮ cả "file" và "word")
- Chỉ làm sạch ngữ pháp, KHÔNG bỏ từ khóa quan trọng!

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
    num_files: int,
    existing_fact_map: dict = None
) -> List[dict]:
    """
    (MỚI - SỬA LỖI 79, 105)
    Một lệnh gọi GPT duy nhất để TÁCH và PHÂN LOẠI
    cho 'Smart Mode' (khi không có 'vào mục').
    Trả về list of dicts: 
    [{"name": "...", "key": "...", "label": "..."}, ...]
    
    SỬA LỖI 105: Kiểm tra fact_map hiện có trước khi tạo mới.
    """
    
    # Lấy danh sách fact_key hiện có
    existing_keys_info = ""
    if existing_fact_map:
        keys_list = []
        for key, value in existing_fact_map.items():
            if isinstance(value, dict):
                label = value.get("label", key)
                keys_list.append(f"  - {key}: {label}")
        if keys_list:
            existing_keys_info = "\nDanh sách fact_key ĐÃ TỒN TẠI:\n" + "\n".join(keys_list) + "\n\nƯU TIÊN sử dụng fact_key đã tồn tại nếu phù hợp với ngữ cảnh."
    
    prompt = f"""
    Ghi chú của người dùng: "{user_note}"
    Số lượng file đã upload: {num_files}
{existing_keys_info}

    Nhiệm vụ: 
    1. Phân tích Ghi chú để tìm ra ngữ cảnh chung.
    2. **ƯU TIÊN** sử dụng fact_key đã tồn tại nếu phù hợp. Chỉ tạo mới nếu KHÔNG khớp.
    3. **PHÂN TÍCH CHÍNH XÁC** dựa trên từ khóa:
       - "gia đình", "gia dinh" → gia_dinh (KHÔNG phải cong_viec)
       - "cá nhân", "ca nhan", "cccd", "hộ chiếu" → ca_nhan hoặc ho_so_ca_nhan
       - "công việc", "cong viec", "doanh số", "ns", "báo cáo" → cong_viec
       - "du lịch", "du lich", "vũng tàu", "hạ long" → du_lich
       - "máy cắt", "máy khoan", "dụng cụ" → general (nếu không rõ)
    4. Nếu KHÔNG RÕ ngữ cảnh → dùng "general | General"
    5. Tách Ghi chú thành chính xác {num_files} TÊN FILE riêng lẻ.
    6. Trả về MỖI file trên MỘT DÒNG theo định dạng:
       `Tên file đã tách | fact_key (snake_case) | Fact Label (Tiếng Việt có dấu)`

    QUY TẮC:
    - Phải trả về ĐÚNG {num_files} dòng.
    - BẮT BUỘC SỬ DỤNG TIẾNG VIỆT CÓ DẤU cho Tên file:
      * "anh" → "ảnh"
      * "du lich" → "du lịch"
      * "vung tau" → "vũng tàu"
      * "phan thiet" → "phan thiết"
      * "may" → "máy"
      * "cat" → "cắt"
    - Loại bỏ từ "lưu", "luu", "vào", "vao" khỏi tên file.
    - PHẢI áp dụng ngữ cảnh chung cho TẤT CẢ các dòng.
    - KHÔNG giải thích.

    Ví dụ 1 (Sử dụng fact_key ĐÃ TỒN TẠI):
    Danh sách fact_key ĐÃ TỒN TẠI:
      - du_lich: Du Lịch
      - cong_viec: Công Việc
    Ghi chú: "luu anh du lich vung tau va phan thiet"
    Số lượng file: 2
    Output:
    ảnh du lịch vũng tàu | du_lich | Du Lịch
    ảnh du lịch phan thiết | du_lich | Du Lịch

    Ví dụ 2 (Tạo MỚI vì không khớp):
    Danh sách fact_key ĐÃ TỒN TẠI:
      - cong_viec: Công Việc
    Ghi chú: "anh cccd mat truoc va mat sau"
    Số lượng file: 2
    Output:
    ảnh cccd mặt trước | ho_so_ca_nhan | Hồ Sơ Cá Nhân
    ảnh cccd mặt sau | ho_so_ca_nhan | Hồ Sơ Cá Nhân

    Ví dụ 3 (Tạo MỚI - Phân biệt GIA ĐÌNH vs CÔNG VIỆC):
    Ghi chú: "luu bai phat bieu gia dinh"
    Số lượng file: 1
    Output:
    bài phát biểu gia đình | gia_dinh | Gia Đình

    Ví dụ 4 (Sử dụng fact_key ĐÃ TỒN TẠI):
    Danh sách fact_key ĐÃ TỒN TẠI:
      - cong_viec: Công Việc
    Ghi chú: "luu file ns 2024 và ns 2025"
    Số lượng file: 2
    Output:
    file ns 2024 | cong_viec | Công Việc
    file ns 2025 | cong_viec | Công Việc
    
    Ví dụ 5 (KHÔNG RÕ ngữ cảnh → general):
    Ghi chú: "luu anh may cat"
    Số lượng file: 2
    Output:
    ảnh máy cắt 1 | general | General
    ảnh máy cắt 2 | general | General
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


async def _llm_normalize_filename(llm: ChatOpenAI, user_note: str) -> str:
    """
    (MỚI - SỬA LỖI 104)
    Dùng LLM để chuẩn hóa tên file: Tiếng Việt có dấu, loại bỏ "lưu", "vào", etc.
    """
    prompt = f"""
    Ghi chú: "{user_note}"

    Nhiệm vụ: Trích xuất TÊN FILE từ ghi chú và chuẩn hóa.

    QUY TẮC:
    - SỬ DỤNG TIẾNG VIỆT CÓ DẤU (ví dụ: "ảnh máy khoan" KHÔNG phải "anh may khoan").
    - Loại bỏ từ: "lưu", "luu", "vào", "vao", "mục".
    - Trả về CHỈ tên file, KHÔNG giải thích.

    Ví dụ 1:
    Ghi chú: "lưu ảnh máy cắt vào công việc"
    Output: ảnh máy cắt

    Ví dụ 2:
    Ghi chú: "luu file hop dong vao ho so"
    Output: file hợp đồng

    Ví dụ 3:
    Ghi chú: "anh may khoan"
    Output: ảnh máy khoan
    """
    
    try:
        resp = await llm.ainvoke(prompt)
        normalized = resp.content.strip()
        print(f"✅ [Normalize] '{user_note}' -> '{normalized}'")
        return normalized
    except Exception as e:
        print(f"❌ Lỗi _llm_normalize_filename: {e}. Dùng fallback.")
        return user_note


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

    Nhiệm vụ: Tách "Ghi chú của người dùng" thành chính xác {num_files} tên file riêng lẻ, 
    tương ứng với {num_files} file theo đúng thứ tự.

    QUAN TRỌNG:
    - Trả về MỖI tên file trên MỘT DÒNG.
    - BẮT BUỘC SỬ DỤNG TIẾNG VIỆT CÓ DẤU:
      * "anh" → "ảnh"
      * "may" → "máy" 
      * "bao" → "bao" hoặc "báo" (tùy ngữ cảnh)
      * "cat" → "cắt"
      * "khoan" → "khoan"
      * "dung cu" → "dụng cụ"
    - Loại bỏ từ "lưu", "luu", "vào", "vao" khỏi tên file.
    - KHÔNG giải thích.

    Ví dụ 1:
    Ghi chú: "lưu 2 ảnh du lịch vũng tàu và hạ long"
    Số lượng file: 2
    Output:
    ảnh du lịch vũng tàu
    ảnh du lịch hạ long

    Ví dụ 2:
    Ghi chú: "luu anh may bao va may cat vao cong viec"
    Số lượng file: 2
    Output:
    ảnh máy bao
    ảnh máy cắt

    Ví dụ 3:
    Ghi chú: "lưu ảnh bộ dụng cụ và máy khoan vào công việc"
    Số lượng file: 2
    Output:
    ảnh bộ dụng cụ
    ảnh máy khoan

    Ví dụ 4 (Ghi chú chung - KHÔNG tách):
    Ghi chú: "lưu ảnh máy cắt vào công việc"
    Số lượng file: 2
    Output:
    ảnh máy cắt
    ảnh máy cắt
    
    Ví dụ 5:
    Ghi chú: "file hop dong, file bao gia"
    Số lượng file: 2
    Output:
    file hợp đồng
    file báo giá
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
    (SỬA LỖI V95 - HYBRID AGENT + V107 - EDIT NOTE)
    1. Kiểm tra xem có đang edit note không
    2. Xử lý file upload
    3. Gọi main_agent
    """
    import json
    import traceback
    import time  # 🚀 THÊM ĐO LƯỜNG TỔNG THỜI GIAN
    
    # --- 🚀 BẮT ĐẦU ĐO LƯỜNG TỔNG THỜI GIAN 🚀 ---
    total_start_time = time.time()
    
    try:
        # ----- 0) Kiểm tra EDIT NOTE MODE -----
        editing_note_id = cl.user_session.get("editing_note_id")
        if editing_note_id:
            # User đang trong quá trình edit note
            new_content = (message.content or "").strip()
            if not new_content:
                await cl.Message(content="❌ Nội dung không được rỗng!").send()
                return
            
            # Cập nhật ghi chú
            vectorstore = cl.user_session.get("vectorstore")
            if vectorstore:
                try:
                    # Lấy metadata hiện tại
                    result = vectorstore.get(ids=[editing_note_id], include=["metadatas"])
                    if result and result["ids"]:
                        metadata = result["metadatas"][0]
                        
                        # Cập nhật timestamp
                        metadata["timestamp"] = datetime.now().isoformat()
                        
                        # Update document
                        vectorstore.update_document(
                            document_id=editing_note_id,
                            document=new_content,
                            metadata=metadata
                        )
                        
                        await cl.Message(content=f"✅ Đã cập nhật ghi chú!\n\n**Nội dung mới:**\n```\n{new_content}\n```").send()
                    else:
                        await cl.Message(content=f"❌ Không tìm thấy ghi chú với ID: {editing_note_id}").send()
                except Exception as e:
                    await cl.Message(content=f"❌ Lỗi khi cập nhật: {e}").send()
            
            # Clear editing mode
            cl.user_session.set("editing_note_id", None)
            return
        
        # ----- 0.1) V110.4: Kiểm tra TOGGLE MODE COMMAND -----
        text = (message.content or "").strip()
        if text == "::toggle_mode::":
            current_mode = cl.user_session.get("mode", "AGENT")
            new_mode = "SELL" if current_mode == "AGENT" else "AGENT"
            cl.user_session.set("mode", new_mode)
            
            if new_mode == "SELL":
                emoji = "🛍️"
                desc = "Bán hàng (Tìm sản phẩm, doanh số, đơn hàng)"
            else:
                emoji = "🤖"
                desc = "Trợ lý (Ghi chú, file, RAG, nhắc nhở)"
            
            await cl.Message(content=f"{emoji} **{new_mode}**\n\n{desc}").send()
            return
        
        # ----- 1) Tiền xử lý + V110.5: Kiểm tra mode phù hợp -----
        user = cl.user_session.get("user")
        if not user:
            await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất thông tin user. Vui lòng F5.").send()
            return
        user_id_str = user.identifier
        session_id = cl.user_session.get("session_id")
        if not session_id:
            await cl.Message(content="⚠️ Lỗi nghiêm trọng: Mất session_id. Vui lòng F5.").send()
            return
        
        # V110.5: Kiểm tra nếu user đang ở sai mode
        current_mode = cl.user_session.get("mode", "AGENT")
        
        # Phát hiện query liên quan đến sản phẩm/doanh số (cần SELL mode)
        sell_keywords = [
            "sản phẩm", "sp", "máy", "doanh số", "doanh so", "bán", "đơn hàng", 
            "don hang", "giá", "gia", "kho", "tồn kho", "ton kho",
            "chart", "biểu đồ", "bieu do", "dashboard"
        ]
        
        # Phát hiện query liên quan đến ghi chú/file (cần AGENT mode)
        agent_keywords = [
            "ghi chú", "ghi chu", "note", "lưu", "luu", "nhắc", "nhac", 
            "file", "ảnh", "anh", "hình", "hinh", "công việc", "cong viec",
            "task", "reminder", "lịch", "lich"
        ]
        
        text_lower = text.lower()
        is_sell_query = any(kw in text_lower for kw in sell_keywords)
        is_agent_query = any(kw in text_lower for kw in agent_keywords)
        
        # Cảnh báo nếu sai mode
        if current_mode == "AGENT" and is_sell_query and not is_agent_query:
            await cl.Message(
                content="⚠️ **Bạn đang ở chế độ AGENT**\n\n"
                        "Câu hỏi này liên quan đến **sản phẩm/doanh số**.\n"
                        "👉 Vui lòng click nút **🛍️ SELL Mode** (bên trái) để chuyển sang chế độ Bán hàng."
            ).send()
            return
        
        if current_mode == "SELL" and is_agent_query and not is_sell_query:
            await cl.Message(
                content="⚠️ **Bạn đang ở chế độ SELL**\n\n"
                        "Câu hỏi này liên quan đến **ghi chú/file/công việc**.\n"
                        "👉 Vui lòng click nút **🤖 AGENT Mode** (bên phải) để chuyển sang chế độ Trợ lý."
            ).send()
            return

        print(f"[on_message] User={user_id_str} Session={session_id} text={text!r}")
        chat_history = cl.user_session.get("chat_history", []) 
        try:
            global TASK_ACK_STATUS
            user_id_str_esc = cl.user_session.get("user_id_str")
            # 1. ACK escalation (logic cũ)
            if user_id_str_esc in ACTIVE_ESCALATIONS:
                if not ACTIVE_ESCALATIONS[user_id_str_esc].get("acked"):
                    ACTIVE_ESCALATIONS[user_id_str_esc]["acked"] = True
                    print(f"[Escalation] ACK dừng leo thang cho USER {user_id_str_esc}")
            
            # 2. ACK tất cả task notifications của user (logic mới)
            user_db_path = os.path.join(BASE_DIR, "user_data", "users.sqlite")
            conn = sqlite3.connect(user_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT task_id FROM notification_queue 
                WHERE user_email = ? AND sent = 0
            """, (user_id_str_esc,))
            pending_tasks = cursor.fetchall()
            conn.close()
            
            for (task_id,) in pending_tasks:
                ack_key = f"{user_id_str_esc}:{task_id}"
                TASK_ACK_STATUS[ack_key] = True
                print(f"[Task ACK] User {user_id_str_esc} đã phản hồi → Ngừng nhắc task #{task_id}")
                
        except Exception as e:
            print(f"[Escalation/Task ACK] Lỗi khi ack: {e}")

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
                        
                        # (SỬA LỖI 103) KIỂM TRA xem ghi chú có dấu hiệu LIỆT KÊ nhiều mục không
                        # Chỉ tách tên nếu có: dấu phẩy, "và", "with", "và", số thứ tự, etc
                        split_indicators = [",", " và ", " va ", " with ", " + ", "1.", "2.", "3.", "- "]
                        should_split_names = any(indicator in note_part_to_split.lower() for indicator in split_indicators)
                        
                        if should_split_names and num_files > 1:
                            # CÓ dấu hiệu liệt kê → Tách tên riêng cho từng file
                            print(f"✅ [Album Mode] (Sửa lỗi 103) Phát hiện dấu hiệu liệt kê. Đang tách tên từ: '{note_part_to_split}'")
                            clean_names_for_files = await _llm_split_notes(llm, note_part_to_split, num_files)
                            
                            if len(clean_names_for_files) != num_files:
                                clean_names_for_files = [f"{summary_name} ({i+1})" for i in range(num_files)]
                                print(f"⚠️ [Album Mode] (Sửa lỗi 103) Tách tên thất bại, dùng tên chung có số: '{summary_name}'")
                        else:
                            # KHÔNG có dấu hiệu → Dùng CHUNG 1 tên cho tất cả file
                            print(f"ℹ️ [Album Mode] (Sửa lỗi 104) KHÔNG phát hiện dấu hiệu liệt kê. Đang chuẩn hóa tên: '{note_part_to_split}'")
                            
                            # Gọi LLM để chuẩn hóa tên file (tiếng Việt có dấu)
                            normalized_name = await _llm_normalize_filename(llm, note_part_to_split)
                            
                            if num_files == 1:
                                clean_names_for_files = [normalized_name]
                            else:
                                # Nhiều file cùng tên → thêm số thứ tự
                                clean_names_for_files = [f"{normalized_name} ({i+1})" for i in range(num_files)]

                    else:
                        # --- NHÁNH A.2: CHẾ ĐỘ SMART (SỬA LỖI 79, 105) ---
                        print(f"[Smart Mode] (Sửa lỗi 105) Không phát hiện 'vào mục'. Đang gọi Batch Split với fact_map...")
                        batch_results = []
                        if text:
                            # SỬA LỖI 105: Truyền fact_dict vào để GPT ưu tiên dùng fact_key có sẵn
                            batch_results = await _llm_batch_split_classify(llm, text, num_files, fact_dict)
                        
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
                loading_msg_to_remove = await cl.Message(
                    content="⏳ Đang thực hiện yêu cầu của bạn..."
                ).send()
                
                # 1. Lấy Agent duy nhất
                main_agent = cl.user_session.get("main_agent")
                if not main_agent:
                    ai_output = "❌ Lỗi: Mất Main Agent (V95). Vui lòng F5."
                else:
                    print(f"[Agent V95] B1: Đang gọi Main Agent (1 Call) cho: '{text}'")
                    
                    # --- 🚀 ĐO LƯỜNG AGENT EXECUTION 🚀 ---
                    agent_start_time = time.time()
                    
                    # 2. Gọi Agent
                    payload = {"input": text}
                    result = await main_agent.ainvoke(payload)
                    
                    agent_execution_time = time.time() - agent_start_time
                    print(f"[Agent V95] ⏱️ Agent execution time: {agent_execution_time:.3f}s")
                    
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
    finally:
        # --- 🚀 KẾT THÚC ĐO LƯỜNG TỔNG THỜI GIAN 🚀 ---
        total_elapsed = time.time() - total_start_time
        print(f"\n{'='*60}")
        print(f"[ON_MESSAGE TOTAL] ⏱️ TỔNG THỜI GIAN XỬ LÝ MESSAGE")
        print(f"{'='*60}")
        print(f"  User message: '{message.content[:50] if message.content else '(empty)'}...'")
        print(f"  TOTAL TIME (User gửi → Bot trả lời): {total_elapsed:.3f}s")
        print(f"{'='*60}\n")

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
@cl.action_callback("toggle_mode")
async def on_toggle_mode(action: cl.Action):
    """
    (V110.3) Chuyển đổi trực tiếp giữa AGENT mode và SELL mode.
    Gửi thông báo cho frontend để cập nhật nút.
    """
    current_mode = cl.user_session.get("mode", "AGENT")
    new_mode = "SELL" if current_mode == "AGENT" else "AGENT"
    cl.user_session.set("mode", new_mode)
    
    if new_mode == "SELL":
        emoji = "🛍️"
        desc = "Bán hàng (Tìm sản phẩm, doanh số, đơn hàng)"
    else:
        emoji = "🤖"
        desc = "Trợ lý (Ghi chú, file, RAG, nhắc nhở)"
    
    # Gửi thông báo
    await cl.Message(
        content=f"{emoji} **Đã chuyển sang mode: {new_mode}**\n\n{desc}"
    ).send()

@cl.action_callback("view_tasks")
async def on_view_tasks(action: cl.Action):
    """Hiển thị TaskGrid để xem và edit tasks."""
    try:
        import task_manager as tm
        user_email = cl.user_session.get("user_email")
        tasks = await asyncio.to_thread(tm.get_tasks, user_email=user_email, status="pending")
        
        # Tạo CustomElement với TaskGrid
        grid_html = f"""
        <link rel="stylesheet" href="/public/elements/TaskGrid.css">
        <script src="/public/elements/TaskGrid.jsx" type="text/babel"></script>
        <div id="task-grid-root" data-tasks='{json.dumps(tasks)}'></div>
        """
        
        element = CustomElement(
            name="TaskGrid",
            content=grid_html,
            display="inline"
        )
        
        await cl.Message(
            content=f"✅ Đã hiển thị {len(tasks)} công việc trong grid tương tác",
            elements=[element]
        ).send()
        
    except Exception as e:
        await cl.Message(content=f"❌ Lỗi khi load tasks: {e}").send()
        print(f"[Action] Error in view_tasks: {e}")

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

