# app.py
import os
import re
import json
import uuid
import base64
import html
import shutil

import pandas as pd
import docx # từ python-docx
import pypdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from chromadb.config import Settings
import contextvars
from datetime import datetime
from typing import List, Tuple, Optional, Union
from pydantic import BaseModel, Field
import chainlit as cl
from chainlit import Image as ClImage
from chainlit import File as ClFile
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.triggers.interval import IntervalTrigger
from langchain.tools import tool
# ==== NEW: libs for real reminders (scheduler + HTTP + time parsing) ====
import requests
# (Dán dòng này vào vị trí dòng 32)

from langchain.agents import AgentExecutor

from langchain.agents import create_openai_tools_agent

from dateutil import parser as dtparser  # pip install python-dateutil
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # pip install apscheduler
from apscheduler.triggers.date import DateTrigger
import pytz  # pip install pytz
import asyncio # <--- THÊM DÒNG NÀY
from asyncio import Queue
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore # <--- THÊM DÒNG NÀY
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
BASE_DIR = os.path.abspath(".")
MEMORY_DIR = os.path.join(BASE_DIR, "memory_db")
JOBSTORE_DB_FILE = os.path.join(MEMORY_DIR, "jobs.sqlite")
# NEW: timeout giây
PUSH_TIMEOUT = int(os.getenv("PUSH_TIMEOUT", "15"))
POLLER_STARTED = False # <--- THÊM DÒNG NÀY
JOBSTORE_DB_FILE = os.path.join(MEMORY_DIR, "jobs.sqlite")
# Timezone VN
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Global Scheduler (khởi tạo 1 lần)
SCHEDULER: Optional[AsyncIOScheduler] = None
# Cấu hình nơi lưu trữ job (database)
jobstores = {
    'default': SQLAlchemyJobStore(url=f'sqlite:///{JOBSTORE_DB_FILE}')
}

# Theo dõi các “escalating reminders” đang chạy theo từng session
ACTIVE_ESCALATIONS = {}  # { intern

# =========================================================
# 🧠 LangChain + OpenAI + Vector
# =========================================================
# 🧠 LangChain + OpenAI + Vector


# Chroma (ưu tiên gói community mới, fallback cho môi trường rất cũ)

from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

print("🤖 [Global Setup] Khởi tạo môi trường...")

# =========================================================
# 💾 ChromaDB (persist + collection cố định)
# =========================================================

os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

# Thư mục lưu ảnh & file
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
FILES_DIR = os.path.join(PUBLIC_DIR, "files") # Đường dẫn sẽ là ./public/files
IMAGES_DIR = os.path.join(PUBLIC_DIR, "files") # SỬA LỖI: Gộp ảnh vào chung thư mục public
os.makedirs(FILES_DIR, exist_ok=True)

# Embeddings OpenAI rẻ & tốt

embeddings = OpenAIEmbeddings(
    api_key=OPENAI_API_KEY,
    model="text-embedding-3-small"
)

vectorstore = Chroma(
    persist_directory=MEMORY_DIR,
    embedding_function=embeddings,
    collection_name="memory"
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
print("✅ VectorStore (bộ nhớ dài hạn) đã sẵn sàng.")
class PushThuSchema(BaseModel):
    noidung: str = Field(description="Nội dung thông báo để push ngay")
import re
from apscheduler.triggers.cron import CronTrigger

VN_DOW = {
    "thứ 2": "mon", "thu 2": "mon", "thứ hai": "mon", "thu hai": "mon", "t2": "mon",
    "thứ 3": "tue", "thu 3": "tue", "thứ ba": "tue",  "thu ba": "tue",  "t3": "tue",
    "thứ 4": "wed", "thu 4": "wed", "thứ tư": "wed",  "thu tu": "wed",  "t4": "wed",
    "thứ 5": "thu", "thu 5": "thu", "thứ năm": "thu", "thu nam": "thu", "t5": "thu",
    "thứ 6": "fri", "thu 6": "fri", "thứ sáu": "fri", "thu sau": "fri", "t6": "fri",
    "thứ 7": "sat", "thu 7": "sat", "thứ bảy": "sat", "thu bay": "sat", "t7": "sat",
    "chủ nhật": "sun", "chu nhat": "sun", "cn": "sun",
}
# ==== Helpers: format, loại job, liệt kê, hủy ====
# DÁN CODE TOOL MỚI NÀY VÀO
# (Thay thế toàn bộ hàm từ dòng 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

# (THAY THẾ HÀM TỪ DÒNG 173)

@tool
def tim_file_de_tai_ve(ten_goc_cua_file: str):
    """
    (SỬA LỖI) Chỉ dùng khi người dùng yêu cầu 'tải về', 'gửi file', 
    'cho tôi link', 'lấy ảnh' hoặc 'lấy file' của MỘT file/ảnh cụ thể.
    TUYỆT ĐỐI KHÔNG dùng tool này để đọc nội dung.
    """
    try:
        results = retriever.invoke(f"file hoặc ảnh có tên {ten_goc_cua_file}")
        
        found_path_url = None
        found_name = ten_goc_cua_file 
        is_image = False 

        for doc in results:
            content = doc.page_content
            if ten_goc_cua_file.lower() in content.lower() and \
               ("[FILE]" in content or "[IMAGE]" in content):
                
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
            # SỬA LỖI: Quay lại dùng MARKDOWN
            safe_href = found_path_url
            safe_name = html.escape(found_name)

            if is_image:
                return f"Tìm thấy ảnh: \n![{safe_name}]({safe_href})"
            else:
                # Trả về Markdown, không dùng HTML
                return f"Tìm thấy file: **[{safe_name}]({safe_href})**"
        else:
            return f"⚠️ Không tìm thấy file hoặc ảnh nào khớp với tên '{ten_goc_cua_file}'."
            
    except Exception as e:
        return f"❌ Lỗi khi tìm file: {e}"
    
    
    
def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Tạo một text splitter tiêu chuẩn."""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )

def _load_and_process_document(
    src_path: str, 
    original_name: str, 
    mime_type: str, 
    user_note: str
) -> Tuple[int, str]:
    """
    Đọc, xử lý, cắt nhỏ và lưu nội dung tài liệu vào vectorstore.
    Trả về (số lượng chunks, tên file).
    """
    
    text_content = ""
    # Ghi chú này sẽ được thêm vào mỗi chunk để RAG biết nguồn gốc
    metadata_note = f"Trích từ tài liệu: {original_name} | Ghi chú của người dùng: {user_note}"

    try:
        # 1. Đọc nội dung dựa trên loại file
        if "excel" in mime_type or src_path.endswith((".xlsx", ".xls")):
            # Đọc tất cả các sheet và gộp lại
            df_dict = pd.read_excel(src_path, sheet_name=None)
            all_text = []
            for sheet_name, df in df_dict.items():
                # SỬA LỖI: Dùng to_markdown cho LLM dễ đọc
                md_table = df.to_markdown(index=False) 
                all_text.append(f"--- Sheet: {sheet_name} ---\n{md_table}")
            
            text_content = "\n\n".join(all_text)
            
        elif "pdf" in mime_type:
            # ... (code PDF giữ nguyên) ...
            reader = pypdf.PdfReader(src_path)
            all_text = [page.extract_text() or "" for page in reader.pages]
            text_content = "\n".join(all_text)
            
        elif "wordprocessingml" in mime_type or src_path.endswith(".docx"):
            # ... (code DOCX giữ nguyên) ...
            doc = docx.Document(src_path)
            all_text = [p.text for p in doc.paragraphs]
            text_content = "\n".join(all_text)
            
        elif "text" in mime_type or src_path.endswith((".txt", ".md", ".py", ".js")):
            # ... (code TEXT giữ nguyên) ...
            with open(src_path, "r", encoding="utf-8") as f:
                text_content = f.read()
                
        else:
            # Loại file không hỗ trợ
            note = f"[FILE_UNSUPPORTED] path={src_path} | name={original_name} | note={user_note}"
            vectorstore.add_texts([note])
            _save_file_and_note(src_path, original_name, user_note) # Vẫn lưu file
            return 0, original_name

        if not text_content.strip():
            raise ValueError("File rỗng hoặc không thể trích xuất nội dung.")

        # 2. Cắt nhỏ (Chunking)
        text_splitter = _get_text_splitter()
        chunks = text_splitter.split_text(text_content)
        
        # 3. Thêm metadata (nguồn gốc) vào mỗi chunk
        chunks_with_metadata = [
            f"{metadata_note}\n\n[NỘI DUNG CHUNK]:\n{chunk}"
            for chunk in chunks
        ]

        # 4. Lưu vào Vectorstore
        vectorstore.add_texts(chunks_with_metadata)
        
        # 5. Vẫn copy file vào 'files' để lưu trữ
        _save_file_and_note(src_path, original_name, user_note) 
        
        return len(chunks_with_metadata), original_name

    except Exception as e:
        print(f"[ERROR] _load_and_process_document failed: {e}")
        # Lưu lỗi để RAG có thể thấy
        error_note = f"[ERROR_PROCESSING_FILE] name={original_name} | note={user_note} | error={e}"
        vectorstore.add_texts([error_note])
        raise  # Ném lỗi ra để on_message có thể bắt
    
    
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
            # SỬA ĐỔI: args = [internal_session_id, noti_text]
            if len(args) >= 2:
                sess = args[0] # <--- SỬA (từ 1 thành 0)
                text = args[1] # <--- SỬA (từ 2 thành 1)
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


# (Dán vào khoảng dòng 330)

# (THAY THẾ HÀM TỪ DÒNG 330)

# (THAY THẾ HÀM TỪ DÒNG 330)

def list_active_files() -> list[dict]:
    """Quét ChromaDB và trả về danh sách các file ([FILE] và [IMAGE])."""
    out = []
    try:
        # SỬA LỖI: Chuyển từ 'where' sang 'where_document'
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
            if not content:
                continue
            
            path_match = re.search(r"path=([^|]+)", content)
            name_match = re.search(r"name=([^|]+)", content)
            note_match = re.search(r"note=([^|]+)", content)

            file_path = path_match.group(1).strip() if path_match else "unknown"
            file_name = name_match.group(1).strip() if name_match else "unknown"
            user_note = note_match.group(1).strip() if note_match else "(không có)"
            
            saved_name = os.path.basename(file_path)
            
            out.append({
                "doc_id": doc_id,
                "file_path": file_path,
                "saved_name": saved_name,
                "original_name": file_name,
                "note": user_note,
                "type": "[IMAGE]" if "[IMAGE]" in content else "[FILE]"
            })
            
    except Exception as e:
        import traceback
        print("[ERROR] Lỗi nghiêm trọng trong list_active_files:")
        print(traceback.format_exc())
        
    return sorted(out, key=lambda x: (x["original_name"]))


from typing import Union, Tuple # Dòng này phải có ở đầu file (khoảng dòng 32)
def remove_reminder(job_id: str, session_id: Union[str, None] = None) -> Tuple[bool, str]:
    """Hủy 1 job theo id. Nếu có session_id: tắt luôn leo thang."""
    try:
        SCHEDULER.remove_job(job_id)
        msg = f"🗑️ Đã xóa lịch: {job_id}"
        if session_id:
            try:
                _cancel_escalation(session_id)  # bạn đã có hàm này
                msg += " • (đã tắt leo thang nếu đang bật)"
            except Exception as e:
                msg += f" • (tắt leo thang lỗi: {e})"
        return True, msg
    except Exception as e:
        return False, f"❌ Không xóa được {job_id}: {e}"
import json
import chainlit as cl

async def ui_show_active_reminders():
    items = list_active_reminders()
    if not items:
        await cl.Message(content="📭 Hiện không có lịch nhắc nào đang hoạt động.").send()
        return

    # Gửi từng item kèm nút XÓA
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
                    # Sửa: Dùng 'payload' và truyền trực tiếp dict (không dùng json.dumps)
                    payload={"job_id": it["id"], "session_id": it["session_id"]},
                    label="🗑️ Hủy lịch này"
                )
            ]
        await cl.Message(content=body, actions=actions).send()

# (Dán vào khoảng dòng 375)

# (THAY THẾ HÀM TỪ DÒNG 469)

async def ui_show_active_files():
    """Hiển thị danh sách file ra UI kèm nút XÓA."""
    items = list_active_files()
    if not items:
        await cl.Message(content="📭 Bộ nhớ file đang trống.").send()
        return

    await cl.Message(content=f"🗂️ **Danh sách {len(items)} file đã lưu:**").send()
    for it in items:
        
        safe_href = f"/public/files/{it['saved_name']}"
        safe_name = html.escape(it['original_name'])
        
        # SỬA LỖI: Quay lại dùng MARKDOWN
        if it['type'] == '[IMAGE]':
            link_html = f"![{safe_name}]({safe_href})"
        else:
            link_html = f"**[{safe_name}]({safe_href})**" # Link Markdown

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
async def _on_delete_reminder(action: cl.Action): # Thêm type hint cho rõ
    # Sửa: Dùng action.payload, nó đã là một dict, không cần json.loads
    data = action.payload
    
    if not data:
        await cl.Message(content="❌ Lỗi: Không nhận được payload khi hủy lịch.").send()
        return

    job_id = data.get("job_id")
    sess   = data.get("session_id")

    ok, msg = remove_reminder(job_id, sess)
    await cl.Message(content=msg).send()

# (Dán vào khoảng dòng 400)

@cl.action_callback("delete_file")
async def _on_delete_file(action: cl.Action):
    data = action.payload
    if not data:
        await cl.Message(content="❌ Lỗi: Không nhận được payload khi hủy file.").send()
        return

    doc_id = data.get("doc_id")
    file_path = data.get("file_path")
    msg = ""

    try:
        # 1. Xóa khỏi Vectorstore
        vectorstore._collection.delete(ids=[doc_id])
        msg += f"✅ Đã xóa metadata: {doc_id}\n"
    except Exception as e:
        msg += f"❌ Lỗi xóa metadata: {e}\n"
        
    try:
        # 2. Xóa file khỏi ổ đĩa
        if os.path.exists(file_path):
            os.remove(file_path)
            msg += f"✅ Đã xóa file: {file_path}"
        else:
            msg += f"⚠️ Không tìm thấy file trên đĩa: {file_path}"
    except Exception as e:
        msg += f"❌ Lỗi xóa file: {e}"

    await cl.Message(content=msg).send()   
    
    
from langchain.tools import tool

from langchain_core.tools import StructuredTool

from langchain.tools import tool

@tool("xem_lich_nhac")
def xem_lich_nhac() -> str:
    """Hiển thị các lịch nhắc đang hoạt động (APScheduler) kèm nút 🗑️ hủy từng lịch trong UI."""
    try:
        cl.run_sync(ui_show_active_reminders())
    except Exception as e:
        return f"❌ Lỗi khi hiển thị lịch: {e}"
    return "✅ Đã liệt kê các lịch nhắc đang hoạt động."


# (Dán vào khoảng dòng 425)
# (Dán vào khoảng dòng 500)

def _sanitize_filename(text: str) -> str:
    """Biến một chuỗi bất kỳ thành tên file an toàn."""
    if not text:
        return "empty"
    # Lấy 60 ký tự đầu
    text = text[:60]
    # Xóa các ký tự đặc biệt
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    # Thay thế dấu cách, xuống dòng
    text = re.sub(r"[\s\n\t]+", "_", text).strip('_')
    # Xóa dấu tiếng Việt (tùy chọn nhưng nên làm)
    try:
        import unidecode # Cần chạy: pip install unidecode
        text = unidecode.unidecode(text)
    except ImportError:
        pass # Bỏ qua nếu chưa cài
    return text or "sanitized"
@tool("xem_danh_sach_file")
def xem_danh_sach_file() -> str:
    """Dùng khi người dùng yêu cầu 'xem danh sách file', 'list file', 
        'các file đã up', 'tất cả file'.
        Hàm này sẽ liệt kê TOÀN BỘ file đã lưu, kèm nút 🗑️ hủy."""
    try:
        cl.run_sync(ui_show_active_files())
    except Exception as e:
        return f"❌ Lỗi khi hiển thị danh sách file: {e}"
    return "✅ Đã liệt kê danh sách file."


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

    # --- Hàng tuần: 'thứ 4 hàng tuần 8:30'
    if ("hàng tuần" in low) or ("hang tuan" in low):
        dow = None
        for k, v in VN_DOW.items():
            if k in low:
                dow = v; break
        if dow:
            hh, mm = _parse_hm(low)
            trig = CronTrigger(day_of_week=dow, hour=hh, minute=mm, timezone=VN_TZ)
            return {"type": "weekly", "trigger": trig}

    # --- Hàng tháng: 'ngày 1 hàng tháng 09:00'
    if ("hàng tháng" in low) or ("hang thang" in low):
        m = re.search(r"ngày\s*(\d{1,2})|ngay\s*(\d{1,2})", low)
        if m:
            day = int(m.group(1) or m.group(2))
            day = max(1, min(31, day))
            hh, mm = _parse_hm(low)
            trig = CronTrigger(day=day, hour=hh, minute=mm, timezone=VN_TZ)
            return {"type": "monthly", "trigger": trig}

    # --- Mỗi ngày: 'mỗi ngày 7h', 'hang ngay 07:30'
    if ("mỗi ngày" in low) or ("moi ngay" in low) or ("hàng ngày" in low) or ("hang ngay" in low):
        hh, mm = _parse_hm(low)
        trig = CronTrigger(hour=hh, minute=mm, timezone=VN_TZ)
        return {"type": "daily", "trigger": trig}

    return None

@tool(args_schema=PushThuSchema)
def push_thu(noidung: str):
    """Gọi push API ngay (không hẹn giờ) để kiểm tra kết nối local."""
    try:
        session_id = cl.user_session.get("session_id") or "default"
        clean_text = (noidung or "").strip()
        print(f"[DEBUG] push_thu called with noidung='{clean_text}'")
        fire_reminder(session_id, clean_text or "Test push")
        return f"PUSH_THU_OK ({clean_text})"  # để thấy text ngay trong chat
    except Exception as e:
        return f"PUSH_THU_ERROR: {e}"
# =========================================================
# 🧩 Tiện ích xem bộ nhớ
# =========================================================
def dump_all_memory_texts() -> str:
    try:
        raw = vectorstore._collection.get()
        docs = raw.get("documents", []) or []
        if not docs:
            return "📭 Bộ nhớ đang trống. Chưa lưu gì cả."
        return "\n".join([f"{i+1}. {d}" for i, d in enumerate(docs)])
    except Exception as e:
        return f"⚠️ Không đọc được bộ nhớ: {e}"

# =========================================================
# 🖼️ & 🗂️ Lưu ảnh / file + ghi chú vào vectorstore
# =========================================================
def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')

# (THAY THẾ HÀM TỪ DÒNG 503)

def _save_image_and_note(src_path: str, user_text: str, original_name: str) -> Tuple[str, str]:
    """
    (SỬA LỖI) Copy ảnh vào ./public/files và ghi 1 dòng note [IMAGE]
    VỚI ĐẦY ĐỦ METADATA (name=, path=, note=).
    """
    # Logic sao chép từ _save_file_and_note
    name = original_name or os.path.basename(src_path) or f"image-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or '.jpg'}" # Đặt đuôi .jpg nếu không rõ
    
    # (IMAGES_DIR bây giờ đã trỏ đúng vào public/files)
    dst = os.path.join(IMAGES_DIR, safe_name) 
    shutil.copyfile(src_path, dst)
    
    # SỬA LỖI: Thêm 'name=' vào metadata
    note = f"[IMAGE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    vectorstore.add_texts([note])
    
    return dst, name # Trả về 2 giá trị

def _save_file_and_note(src_path: str, original_name: Optional[str], user_text: str) -> Tuple[str, str]:
    """
    Copy file bất kỳ vào ./memory_db/files và ghi 1 dòng note [FILE] vào vectorstore.
    Trả về (dst_path, stored_name) để hiển thị.
    """
    name = original_name or os.path.basename(src_path) or f"file-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or ''}"
    dst = os.path.join(FILES_DIR, safe_name)
    shutil.copyfile(src_path, dst)
    note = f"[FILE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    vectorstore.add_texts([note])
    return dst, name
import requests
from requests.adapters import HTTPAdapter

# --- Import Retry ổn định cho urllib3 ---
# urllib3 >= 1.26 và 2.x: dùng allowed_methods
try:
    from urllib3.util.retry import Retry  # chuẩn, không cần fallback
except Exception:  # rất hiếm (requests vendored cực cũ)
    from importlib import import_module
    Retry = import_module("requests.packages.urllib3.util.retry").Retry  # type: ignore

# --- Tạo Retry object, tương thích cả bản cũ (method_whitelist) ---
def make_retry():
    try:
        # urllib3 >= 1.26
        return Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["POST"]),
        )
    except TypeError:
        # urllib3 < 1.26
        return Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            method_whitelist=frozenset(["POST"]),  # type: ignore[arg-type]
        )

PUSH_SESSION = requests.Session()
_retry = make_retry()
PUSH_SESSION.mount("http://",  HTTPAdapter(max_retries=_retry))
PUSH_SESSION.mount("https://", HTTPAdapter(max_retries=_retry))

def _call_push_api_frappe(payload: dict) -> tuple[bool, int, str]:
    """Gọi Frappe createpushnoti. Trả về (ok, status_code, text)."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {PUSH_API_TOKEN}",  # "api_key:api_secret"
    }
    try:
        resp = PUSH_SESSION.post(
            PUSH_API_URL,
            json=payload,
            headers=headers,
            timeout=(3.05, 10),
            verify=PUSH_VERIFY_TLS,
        )
        return (200 <= resp.status_code < 300), resp.status_code, (resp.text or "")
    except Exception as e:
        return False, -1, f"exception: {e}"


# =========================================================
# 🧠 Trích FACT đơn giản
# =========================================================
def _extract_facts(noi_dung: str):
    facts = []
    text = (noi_dung or "").strip()
    low = text.lower()

    # 1) Tên
    m = re.search(r"(tên\s*(tôi|mình|là|của tôi|của mình)\s*(là)?\s*)(?P<name>[A-Za-zÀ-ỹĐđ\s]+)$", text, re.IGNORECASE)
    if m:
        name = m.group("name").strip()
        if name:
            facts.append(f"FACT: ho_ten = {name}")

    # 2) SĐT
    m = re.search(r"(\+?\d[\d\-\s]{7,}\d)", text)
    if m:
        phone = re.sub(r"[^\d\+]", "", m.group(1))
        facts.append(f"FACT: so_dien_thoai = {phone}")

    # 3) Email
    m = re.search(r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", text)
    if m:
        facts.append(f"FACT: email = {m.group(1)}")

    # 4) Địa chỉ
    addr_m = re.search(r"(địa chỉ|đc|sống ở|ở)\s*[:\-]?\s*(?P<addr>.+)", low)
    if addr_m:
        addr = text[addr_m.start("addr"):].strip()
        facts.append(f"FACT: dia_chi = {addr}")

    # 5) Sinh nhật
    m = re.search(r"(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b)", text)
    if m:
        facts.append(f"FACT: sinh_nhat = {m.group(1)}")

    # 6) Công việc
    job_m = re.search(r"(mình|tôi)\s+(đang\s+)?(làm|là)\s+(?P<job>.+)$", low)
    if job_m:
        job = text[job_m.start("job"):].strip()
        facts.append(f"FACT: cong_viec = {job}")

    # 7-12) Sở thích
    if (("thích" in low or "ưa" in low or "gu" in low or "hay ăn" in low) and ("ăn" in low or "món" in low)) \
        or ("món yêu thích" in low):
        facts.append(f"FACT: so_thich_an_uong = {text}")
    if (("thích" in low or "ưa" in low or "hay uống" in low) and ("uống" in low or "đồ uống" in low)) \
        or ("đồ uống yêu thích" in low):
        facts.append(f"FACT: so_thich_do_uong = {text}")
    if any(k in low for k in ["nhạc yêu thích", "thích nghe nhạc", "thể loại nhạc"]):
        facts.append(f"FACT: so_thich_am_nhac = {text}")
    if any(k in low for k in ["phim yêu thích", "thích xem phim", "thể loại phim"]):
        facts.append(f"FACT: so_thich_phim = {text}")
    if any(k in low for k in ["môn thể thao", "thích đá bóng", "thích bơi", "thể thao yêu thích"]):
        facts.append(f"FACT: so_thich_the_thao = {text}")
    if any(k in low for k in ["mình thích", "tôi thích", "gu của mình", "gu của tôi"]):
        facts.append(f"FACT: so_thich_chung = {text}")

    return facts

# =========================================================
# 🔁 Replay lịch sử lên UI
# =========================================================
# (THAY THẾ HÀM TỪ DÒNG 762)

async def replay_history(chat_history: list):
    """
    (SỬA LẠI) Phát lại lịch sử ra UI VÀ trả về danh sách
    các elements (tin nhắn) đã tạo.
    """
    new_elements = [] # <-- MỚI
    if not chat_history:
        msg = await cl.Message(content="(Hội thoại này chưa có nội dung)").send()
        new_elements.append(msg) # <-- MỚI
        return new_elements # <-- MỚI

    for m in chat_history:
        role = (m.get("role") or m.get("sender") or m.get("author") or "").lower()
        content = m.get("content") or m.get("text") or ""
        if not content:
            continue
            
        if role in ("user", "human"):
            msg = await cl.Message(author="Bạn", content=content).send()
            new_elements.append(msg) # <-- MỚI
        else:
            msg = await cl.Message(author="Trợ lý", content=content).send()
            new_elements.append(msg) # <-- MỚI
            
    return new_elements # <-- MỚI

# =========================================================
# 💬 Quản lý nhiều hội thoại (lưu file)
# =========================================================
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# (THAY THẾ HÀM TỪ DÒNG 806)

def list_sessions() -> List[str]:
    """(SỬA LỖI) Lấy danh sách session, sắp xếp theo NGÀY SỬA ĐỔI."""
    sessions_with_time = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith(".json"):
            file_path = os.path.join(SESSIONS_DIR, f)
            try:
                # Lấy thời gian sửa đổi (lần chat cuối)
                mod_time = os.path.getmtime(file_path)
                sessions_with_time.append((f[:-5], mod_time))
            except OSError:
                pass # Bỏ qua file nếu không đọc được
    
    # Sắp xếp theo mod_time (phần tử thứ 2), mới nhất lên trên
    sorted_sessions = sorted(sessions_with_time, key=lambda x: x[1], reverse=True)
    
    # Chỉ trả về tên
    return [session_name for session_name, mod_time in sorted_sessions]
def session_file_path(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")

def save_chat_history(session_id: str, chat_history: list):
    try:
        with open(session_file_path(session_id), "w", encoding="utf-8") as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu hội thoại {session_id}: {e}")

def load_chat_history(session_id: str) -> list:
    path = session_file_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi khi đọc hội thoại {session_id}: {e}")
    return []

def delete_session(session_id: str) -> bool:
    path = session_file_path(session_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
get_all_sessions = list_sessions
# =========================================================
# 🔔 Reminder helpers (Scheduler)
# =========================================================
def ensure_scheduler():
    """Khởi động scheduler (1 lần) VỚI LƯU TRỮ BỀN BỈ."""
    global SCHEDULER
    if SCHEDULER is None:
        try:
            SCHEDULER = AsyncIOScheduler(
                jobstores=jobstores,  # <--- SỬA ĐỔI QUAN TRỌNG
                timezone=str(VN_TZ),
                job_defaults={"max_instances": 3, "coalesce": False}
            )
            SCHEDULER.start()
            print(f"[Scheduler] Đã khởi động với JobStore tại: {JOBSTORE_DB_FILE}")
        except Exception as e:
            print(f"[Scheduler] LỖI NGHIÊM TRỌNG KHI KHỞI ĐỘNG: {e}")
            print("[Scheduler] LỖI: Có thể bạn cần xóa file 'memory_db/jobs.sqlite' nếu cấu trúc DB thay đổi.")
            SCHEDULER = None # Đảm bảo không sử dụng
            
# HÀM MỚI (SYNC) ĐỂ THAY THẾ _tick_wrapper (async)
# THAY THẾ TOÀN BỘ HÀM (từ dòng 944):

def _tick_job_sync(sid, text, repeat_job_id):
    """
    (SỬA LẠI) Hàm sync để APScheduler gọi (cho escalation).
    Đây là nơi duy nhất được phép 'remove_job'.
    """
    try:
        st = ACTIVE_ESCALATIONS.get(sid)
        
        # Job bị hủy nếu:
        # 1. Nó là "mồ côi" (st is None) - do app restart, F5...
        # 2. Nó đã được "ack" (st.get("acked") is True)
        
        if not st or st.get("acked"):
            try:
                # Dọn dẹp Scheduler
                SCHEDULER.remove_job(repeat_job_id)
                print(f"[Escalation] Tick: Job {repeat_job_id} đã ack/mồ côi. ĐANG XÓA.")
            except Exception as e:
                # Lỗi này là BÌNH THƯỜNG (nếu 2 job tick cùng lúc
                # hoặc _cancel_escalation đã chạy trước)
                print(f"[Escalation] Info: Job {repeat_job_id} đã bị xóa (lỗi: {e}).")
            
            # Dọn dẹp bộ nhớ (phòng trường hợp _cancel_escalation chưa chạy)
            ACTIVE_ESCALATIONS.pop(sid, None)
            return
            
        # Nếu không, tiếp tục gửi nhắc
        print(f"[Escalation] Tick: Gửi nhắc (sync) cho {sid}")
        _do_push(sid, text)
        
    except Exception as e:
        print(f"[ERROR] _tick_job_sync crashed: {e}")
        
        
# (Thêm hàm này vào khoảng dòng 943, ngay TRÊN hàm _schedule_escalation_after_first_fire)

def _first_fire_escalation_job(sid, text, every_sec):
    """
    Hàm (sync) được gọi cho LẦN ĐẦU TIÊN của 1 lịch leo thang.
    Nó sẽ tự lên lịch lặp lại (escalation) sau khi chạy.
    """
    try:
        print(f"[Escalation] First fire (sync) for {sid} at {datetime.now(VN_TZ)}")
        
        # 1. Gửi thông báo lần đầu
        _do_push(sid, text) 
        
        # 2. Lên lịch lặp lại (escalation)
        _schedule_escalation_after_first_fire(sid, text, every_sec)
    except Exception as e:
        print(f"[ERROR] _first_fire_escalation_job crashed: {e}")

# (Hàm _schedule_escalation_after_first_fire bên dưới giữ nguyên)

def _schedule_escalation_after_first_fire(internal_session_id: str, noti_text: str, every_sec: int):
    # Tạo job lặp 5s tick → nếu chưa ack thì push tiếp, nếu ack thì tự hủy
    repeat_job_id = f"repeat-{internal_session_id}-{uuid.uuid4().hex[:6]}"
    ACTIVE_ESCALATIONS[internal_session_id] = {"repeat_job_id": repeat_job_id, "acked": False}

    # SỬA: Xóa bỏ _tick_wrapper (async) và thay bằng hàm (sync)
    
    trigger = IntervalTrigger(seconds=every_sec, timezone=VN_TZ)
    SCHEDULER.add_job(
        _tick_job_sync, # <--- SỬA: Dùng hàm sync mới
        trigger=trigger,
        id=repeat_job_id,
        args=[internal_session_id, noti_text], # <--- SỬA: Xóa context
        replace_existing=False,
        misfire_grace_time=10,
    )
    print(f"[Escalation] Đã bật lặp mỗi {every_sec}s với job_id={repeat_job_id}")
              
RAG_FAILURE_KEYWORDS = [
    "tôi đã xem bộ nhớ",
    "nhưng chưa có thông tin",
    "chưa có thông tin về",
    "không có thông tin",
    "tôi không tìm thấy thông tin",
    "không tìm thấy thông tin",
    "i don't have information",
    "i couldn't find information"
]

def parse_repeat_to_seconds(text: str) -> int:
    if not text:
        return 0
    t = (text or "").lower().strip()
    # dạng tiếng Việt
    m = re.search(r"(mỗi|moi|lặp lại|lap lai)\s+(\d+)\s*(giây|giay|phút|phut|giờ|gio|s|m|h)\b", t)
    # dạng ngắn: "every 10s|3m|1h"
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
def parse_when_to_dt(when_str: str) -> datetime:
    """
    Chuyển tiếng Việt tự nhiên -> datetime (Asia/Ho_Chi_Minh).

    Hỗ trợ:
    - "1 phút nữa", "3 phút nữa", "trong 10 phút nữa"
    - "2 giờ nữa", "1h nữa", "1 tiếng nữa"
    - "tối nay", "chiều nay", "sáng mai", "mai", "ngày mai"
    - timestamp cụ thể: "2025-11-04 09:00", "09:30 04/11/2025", "9h30"
    """

    text_raw = (when_str or "").strip().lower()
    if not text_raw:
        raise ValueError("Thiếu thời gian nhắc")

    now = datetime.now(VN_TZ)

    # -------------------------------------------
    # 1. "X phút nữa" / "trong X phút nữa"
    # -------------------------------------------
    m = re.search(r"(\d+)\s*(phút|min)\s*(nữa)?", text_raw)
    if m and ("nữa" in text_raw or "trong" in text_raw or "phút nữa" in text_raw):
        plus_min = int(m.group(1))
        return now + timedelta(minutes=plus_min)

    # -------------------------------------------
    # 2. "X giờ nữa" / "X tiếng nữa" / "1h nữa"
    # -------------------------------------------
    m = re.search(r"(\d+)\s*(giờ|g|tiếng|tieng|h)\s*(nữa)?", text_raw)
    if m and ("nữa" in text_raw or "trong" in text_raw or "giờ nữa" in text_raw or "h nữa" in text_raw):
        plus_hour = int(m.group(1))
        return now + timedelta(hours=plus_hour)

    # -------------------------------------------
    # 3. "tối nay", "chiều nay"
    #    → đặt mặc định 20:00 cho "tối", 15:00 cho "chiều"
    # -------------------------------------------
    if "tối nay" in text_raw or "toi nay" in text_raw:
        candidate = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if candidate <= now:
            # nếu đã quá 20:00 rồi thì đẩy sang ngày mai 20:00
            candidate = candidate + timedelta(days=1)
        return candidate

    if "chiều nay" in text_raw or "chieu nay" in text_raw:
        candidate = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate


    """
    Chuyển câu thời gian tiếng Việt -> datetime (Asia/Ho_Chi_Minh).

    Hỗ trợ:
    - "1 phút nữa", "2 phút nữa", "3 phút nữa", "10 phút nữa", "trong 5 phút nữa"
    - "1 giờ nữa", "2 tiếng nữa", "3h nữa"
    - "tối nay", "chiều nay"
    - "sáng mai", "mai", "ngày mai"
    - giờ cụ thể: "12:10", "12h10", "12h"
    - datetime cụ thể: "2025-11-04 09:00", "09:30 04/11/2025"
    """

    text_raw = (when_str or "").strip().lower()
    if not text_raw:
        raise ValueError("Thiếu thời gian nhắc")

    now = datetime.now(VN_TZ)

    # -------------------------------------------
    # 0. Chuẩn hoá khoảng trắng dư
    # -------------------------------------------
    text_raw = re.sub(r"\s+", " ", text_raw).strip()

    # -------------------------------------------
    # 1. "X phút nữa" / "trong X phút nữa"
    #    ví dụ: "1 phút nữa", "2 phút nữa", "3 phút nữa", "trong 10 phút nữa"
    # -------------------------------------------
    m = re.search(r"(trong\s+)?(\d+)\s*(phút|min|phut)\s*(nữa|nua)?", text_raw)
    if m:
        plus_min = int(m.group(2))
        return now + timedelta(minutes=plus_min)

    # -------------------------------------------
    # 2. "X giờ nữa" / "X tiếng nữa" / "1h nữa"
    #    ví dụ: "1 giờ nữa", "2 tiếng nữa", "3h nữa", "trong 1 giờ nữa"
    # -------------------------------------------
    m = re.search(r"(trong\s+)?(\d+)\s*(giờ|gio|g|tiếng|tieng|h)\s*(nữa|nua)?", text_raw)
    if m:
        plus_hour = int(m.group(2))
        return now + timedelta(hours=plus_hour)

    # -------------------------------------------
    # 3. "tối nay", "chiều nay"
    # -------------------------------------------
    if "tối nay" in text_raw or "toi nay" in text_raw:
        cand = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if cand <= now:
            cand = cand + timedelta(days=1)
        return cand

    if "chiều nay" in text_raw or "chieu nay" in text_raw:
        cand = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if cand <= now:
            cand = cand + timedelta(days=1)
        return cand

    # -------------------------------------------
    # 4. "sáng mai", "mai", "ngày mai"
    #    -> mặc định 08:00 ngày mai
    # -------------------------------------------
    if ("sáng mai" in text_raw or "sang mai" in text_raw or
        "ngày mai" in text_raw or "ngay mai" in text_raw or
        text_raw.strip() == "mai"):
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)

    # -------------------------------------------
    # 5. Chuẩn hoá "12h30", "12h", "07h05"
    #    -> đổi thành "12:30", "12:00", "07:05"
    # -------------------------------------------
    text = text_raw
    text = re.sub(r"(\d{1,2})h(\d{1,2})", r"\1:\2", text, flags=re.I)
    text = re.sub(r"(\d{1,2})h\b", r"\1:00", text, flags=re.I)

    # -------------------------------------------
    # 6. Thử parse bằng dateutil cho các dạng cụ thể có ngày/giờ rõ
    # -------------------------------------------
    try:
        dt_guess = dtparser.parse(
            text,
            dayfirst=True,  # ưu tiên dd/mm
            fuzzy=True,
            default=now.replace(second=0, microsecond=0)
        )
    except Exception:
        # cuối cùng chịu, trả về luôn "now + 1 phút"
        return now + timedelta(minutes=1)

    # ép timezone VN
    if dt_guess.tzinfo is None:
        dt_guess = VN_TZ.localize(dt_guess)
    else:
        dt_guess = dt_guess.astimezone(VN_TZ)

    # -------------------------------------------
    # 7. Nếu user chỉ nói giờ (vd "12:10") chứ không nói ngày,
    #    đôi khi dateutil sẽ build cùng ngày -> ok,
    #    nhưng đôi khi nó trả ngược tháng/ngày -> quá khứ hôm nào đó (2025-03-11 thay vì 2025-11-03).
    #    Ta sửa: nếu không có pattern ngày/tháng mà dt_guess < now,
    #    thì coi như ý muốn là tương lai gần -> đẩy sang ngày mai.
    # -------------------------------------------
    mentions_date = bool(re.search(r"\d{1,2}[\/\-]\d{1,2}", text)) or bool(re.search(r"\d{4}", text))
    if not mentions_date:
        if dt_guess < now:
            dt_guess = dt_guess + timedelta(days=1)

    return dt_guess



'''
async def _send_ui_reminder(session_id: str, content: str, author: str):
    """
    Hàm async an toàn để gửi tin nhắn tới UI.
    Sẽ được gọi bởi cl.run_sync (đã có context).
    """
    try:
        import chainlit as cl
        
        # Lấy session cụ thể - BÂY GIỜ NÓ SẼ HOẠT ĐỘNG
        session = cl.sessions.get(session_id) 
        
        if session:
            # Gửi tin nhắn
            msg = cl.Message(author=author, content=content)
            await msg.send_to(session)
            print(f"✅ [send_ui_reminder] Đã gửi tin nhắn đến {session_id}")
        else:
            print(f"[WARN] [send_ui_reminder] Không tìm thấy session {session_id}.")
    except Exception as e:
        print(f"[ERROR] [send_ui_reminder] Bị crash: {e}")
async def _do_push_wrapper(context, internal_session_id: str, noti_text: str):
    try:
        print(f"[Wrapper] (async) Run job for {internal_session_id}")
        await asyncio.to_thread(context.run, _do_push, internal_session_id, noti_text)
    except Exception as e:
        print(f"[ERROR] [Wrapper] crashed: {e}")
'''

        
def _cancel_escalation(internal_session_id: str):
    """
    (SỬA LẠI) Chỉ dọn dẹp bộ nhớ. 
    Lệnh 'remove_job' sẽ được _tick_job_sync xử lý.
    """
    st = ACTIVE_ESCALATIONS.pop(internal_session_id, None)
    if st:
        print(f"[Escalation] Đã dọn dẹp in-memory cho {internal_session_id}")

# THAY THẾ HÀM CŨ TẠI DÒNG 969 BẰNG HÀM NÀY:

def _schedule_escalation_after_first_fire(internal_session_id: str, noti_text: str, every_sec: int):
    """
    (SỬA LỖI) Lên lịch lặp lại (escalation) bằng hàm sync-safe.
    """
    # Tạo job lặp 5s tick → nếu chưa ack thì push tiếp, nếu ack thì tự hủy
    repeat_job_id = f"repeat-{internal_session_id}-{uuid.uuid4().hex[:6]}"
    ACTIVE_ESCALATIONS[internal_session_id] = {"repeat_job_id": repeat_job_id, "acked": False}

    # [Đã xóa bỏ hàm lồng _tick_wrapper]
    
    trigger = IntervalTrigger(seconds=every_sec, timezone=VN_TZ)
    
    # SỬA: Dùng hàm global _tick_job_sync (đã có ở dòng 944)
    SCHEDULER.add_job(
       _tick_job_sync, # <--- SỬA: Dùng hàm sync mới
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
            # Gửi tin nhắn mà "Tổng đài" sẽ xử lý
            GLOBAL_MESSAGE_QUEUE.put_nowait({
                "author": "Trợ lý ⏰",
                "content": f"⏰ Nhắc: {noti_text}\n🕒 {ts}"
            })
            print(f"[Push/Queue] Đã gửi tin nhắn vào TỔNG ĐÀI.")
        else:
            print("[Push/Queue] LỖI: GLOBAL_MESSAGE_QUEUE is None.")
            
    except Exception as e:
        print(f"[Push/Queue] Lỗi put_nowait (Tổng đài): {e}")

    # 2. Gọi API Frappe (vẫn thực hiện)
    # ... (Toàn bộ code gọi API Frappe của bạn giữ nguyên) ...
    escalate_active = bool(ACTIVE_ESCALATIONS.get(internal_session_id) and
                           not ACTIVE_ESCALATIONS[internal_session_id].get("acked"))
    big_md = "# ⏰ **NHẮC VIỆC**\n\n## " + noti_text + "\n\n**🕒 " + ts + "**"
    payload = { "subject": "🔔 Nhắc việc", "notiname": big_md, "url": PUSH_DEFAULT_URL, }
    ok, status, text = _call_push_api_frappe(payload)
    if ok:
        print(f"[Push/API] OK status={status}")
    else:
        print(f"[Push/API] FAIL status={status} body={text[:300]}")


# (Dán 2 hàm này vào vị trí dòng 1076)

async def global_broadcaster_poller():
    """
    (MỚI) HÀM TỔNG ĐÀI - Chạy 1 lần duy nhất.
    Lấy tin từ Hàng đợi Tổng và "phát" (broadcast)
    cho tất cả các "thuê bao" (tab) đang active.
    """
    print("✅ [Tổng đài] Global Broadcaster đã khởi động.")
    while True:
        try:
            if GLOBAL_MESSAGE_QUEUE is None:
                await asyncio.sleep(2)
                continue

            # 1. Chờ tin nhắn từ Scheduler
            msg_data = await GLOBAL_MESSAGE_QUEUE.get()
            
            print(f"[Tổng đài] Nhận được tin nhắn. Đang phát cho {len(ACTIVE_SESSION_QUEUES)} thuê bao...")

            # 2. "Phát" tin nhắn cho TẤT CẢ các tab đang mở
            if ACTIVE_SESSION_QUEUES:
                # Sao chép danh sách key để tránh lỗi thread-safety
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
    """
    (MỚI) HÀM THUÊ BAO - Chạy 1 lần cho MỖI TAB.
    1. Tạo Queue (hòm thư) của riêng mình.
    2. Đăng ký "hòm thư" này với Tổng đài.
    3. Chỉ lắng nghe "hòm thư" của mình.
    """
    current_internal_id = cl.user_session.get("chainlit_internal_id", "unknown")
    my_queue = asyncio.Queue()
    
    try:
        # 2. Đăng ký
        ACTIVE_SESSION_QUEUES[current_internal_id] = my_queue
        print(f"✅ [Thuê bao] Đã ĐĂNG KÝ cho session {current_internal_id}")
        
        while True:
            # 3. Chờ "Tổng đài" phát tin nhắn
            msg_data = await my_queue.get()
            
            print(f"[Thuê bao] {current_internal_id} đã nhận được tin nhắn.")
            
            content = msg_data.get("content", "")
            
            # Gửi tin nhắn chat UI
            await cl.Message(
                author=msg_data.get("author", "Bot"),
                content=content
            ).send()
            
            # (Chúng ta biết cl.Notification hỏng, nên đã xóa)
            
            my_queue.task_done()
            
    except asyncio.CancelledError:
        print(f"[Thuê bao] {current_internal_id} đã dừng.")
            
    except Exception as e:
        print(f"[Thuê bao/ERROR] {current_internal_id} bị lỗi: {e}")
        
    finally:
        # 4. HỦY ĐĂNG KÝ (Rất quan trọng)
        ACTIVE_SESSION_QUEUES.pop(current_internal_id, None)
        print(f"[Thuê bao] Đã HỦY ĐĂNG KÝ cho session {current_internal_id}")
        
# =========================================================
# 🚀 ĐỊNH NGHĨA CLASS AGENT TÙY CHỈNH
# (Class này phải nằm BÊN NGOÀI hàm on_start)
# =========================================================
class CleanAgentExecutor(AgentExecutor):
    """
    (SỬA LẠI) AgentExecutor tùy chỉnh: chỉ chạy 1 vòng và trả về
    kết quả thô (Observation) từ tool, không cho LLM nói thêm.
    """
    async def ainvoke(self, input_data: dict, **kwargs):
        
        # 1. Giới hạn agent chỉ chạy 1 vòng (gọi tool)
        kwargs.setdefault("max_iterations", 1) 
        
        # 2. CHẠY AGENT (đây là call API duy nhất)
        #    Dòng này định nghĩa 'result'
        result = await super().ainvoke(input_data, **kwargs)
        
        # 3. Lấy kết quả (observation) từ tool
        steps = result.get("intermediate_steps") or []
        
        if steps and isinstance(steps[-1], tuple):
            # obs là kết quả thô từ tool
            obs = steps[-1][1] 
            if isinstance(obs, str) and obs.strip():
                # Trả về ngay lập tức, không cho LLM nói thêm
                return {"output": obs.strip()} 
                
        # 4. Fallback nếu không có tool (hoặc tool không trả về gì)
        return {"output": result.get("output", "⚠️ Không có phản hồi.")}

# =========================================================
# 🚀 HÀM "NGƯỜI LẮNG NGHE" (CHẠY NỀN, MỚI)
# =========================================================
# THAY THẾ TOÀN BỘ HÀM (từ dòng 1157) BẰNG CODE NÀY:

# (Dán code này vào vị trí dòng 1076)


# ==============================
# 🔔 Browser Notifications (4 spaces, no tabs)
# ==============================
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
        res = await cl.run_js(js)  # 'granted' | 'denied' | 'default' | 'no-support'
        print("[Notify] permission =", res)
    except Exception as e:
        print("[Notify] request permission error:", e)

async def show_browser_notification(title: str, body: str, play_beep: bool = True):
    # Notification API chạy trên HTTPS hoặc localhost
    js = f"""
(async () => {{
  try {{
    if (!('Notification' in window)) return 'no-support';
    if (Notification.permission !== 'granted') {{
      const r = await Notification.requestPermission();
      if (r !== 'granted') return 'denied';
    }}
    const n = new Notification({json.dumps(title)}, {{
      body: {json.dumps(body)},
      requireInteraction: true
    }});
    {"(function(){try{const a=new (window.AudioContext||window.webkitAudioContext)();const o=a.createOscillator();o.type='sine';o.frequency.value=880;const g=a.createGain();g.gain.value=0.03;o.connect(g);g.connect(a.destination);o.start();setTimeout(()=>{o.stop();a.close()},700);}catch(_){}})();" if play_beep else ""}
    return 'ok';
  }} catch (e) {{ return 'error:' + String(e); }}
}})();
"""
    try:
        res = await cl.run_js(js)
        print("[Notify] popup result =", res)
    except Exception as e:
        print("[Notify] popup error:", e)

# =========================================================
# 🚀 on_chat_start (SỬA LẠI)
# =========================================================
@cl.on_chat_start
async def on_start():
    """Khởi tạo phiên trò chuyện, thiết lập session và agent."""
    
    global GLOBAL_MESSAGE_QUEUE, POLLER_STARTED # <--- SỬA DÒNG NÀY
    await ensure_notification_permission()
    await cl.Message(content="✅ Trình duyệt đã bật quyền thông báo!").send()
    # === KHỞI TẠO TỔNG ĐÀI (CHỈ 1 LẦN) ===
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
    # ========================================
    try:
       
        
        # --- 0. Khởi tạo Session ID và Lịch sử Chat ---
        session_id = f"session_{_timestamp()}"
        chat_history = []
        
        # Lấy ID nội bộ (Internal ID)
        internal_id = cl.user_session.get("id") 
        cl.user_session.set("chainlit_internal_id", internal_id) 
        
        cl.user_session.set("session_id", session_id) 
        cl.user_session.set("chat_history", chat_history) 
        
        print(f"🤖 [Session] Khởi tạo phiên mới: {session_id} (Internal: {internal_id})")
        
        
        # --- 1. Kiểm tra khóa API ---
        if not OPENAI_API_KEY:
            await cl.Message(content="❌ Thiếu OPENAI_API_KEY trong .env").send()
            return

        # --- 2. Chuẩn bị môi trường nền ---
        ensure_scheduler()

        # --- 3. Thông báo sẵn sàng ---
        await cl.Message(
            content=f"✅ **Hệ thống đã sẵn sàng! (Session: {session_id})**\n\n"
                    "Bạn có thể bắt đầu hội thoại hoặc chọn lại phiên cũ bên dưới 👇"
        ).send()
        
        # --- 4. Hiển thị danh sách hội thoại ---
        # (Tất cả code tạo actions... của bạn giữ nguyên)
        sessions = get_all_sessions()
        actions = [
            cl.Action(
                name="new_chat", # Nút 1: Bắt đầu mới
                label="✨ Cuộc trò chuyện mới", 
                payload={"session_id": "new"}
            ),
            cl.Action(
                name="show_session_list", # Nút 2: Yêu cầu hiển thị danh sách
                label="🗂️ Tải hội thoại cũ", 
                payload={} # Không cần payload
            )
        ]
        await cl.Message(content="🗂️ **Chọn hội thoại:**", actions=actions).send()


        # --- 5. Khởi tạo LLMs ---
        llm_logic = ChatOpenAI(model="gpt-4.1-mini", temperature=0, api_key=OPENAI_API_KEY)
        llm_vision = ChatOpenAI(model="gpt-4.1-mini", temperature=0, api_key=OPENAI_API_KEY)
        cl.user_session.set("llm_logic", llm_logic)
        cl.user_session.set("llm_vision", llm_vision)
        
        # === THÊM MỚI: KHỞI ĐỘNG POLLER CHO SESSION NÀY ===
        poller_task = asyncio.create_task(session_receiver_poller())
        cl.user_session.set("poller_task", poller_task)
        # ===============================================
        
        print("✅ Kết nối OpenAI OK.")

        # --- 6. RAG chain ---
        # (Toàn bộ code RAG chain của bạn giữ nguyên)
        # [Dán code này thay cho rag_prompt hiện tại]
        rag_prompt = ChatPromptTemplate.from_template(
            "Bạn là một trợ lý RAG (truy xuất-tăng cường). Nhiệm vụ của bạn là trả lời câu hỏi của người dùng (input) CHỈ dựa trên thông tin trong (context) được cung cấp."
            "Context có thể chứa ghi chú, sự kiện (FACTs), hoặc nội dung trích xuất từ file (dưới dạng bảng Markdown hoặc text)."
            
            "QUY TẮC QUAN TRỌNG VỀ TÍNH TOÁN VÀ TỔNG HỢP:"
            "1. Nếu câu hỏi yêu cầu **tính TỔNG** (ví dụ: 'tổng doanh số', 'tổng số lượng', 'tổng cộng'), bạn PHẢI TỰ MÌNH SỬ DỤNG TẤT CẢ các con số liên quan trong [NỘI DUNG CHUNK] của Context để thực hiện phép cộng và trả về KẾT QUẢ CUỐI CÙNG."
            "2. Nếu câu hỏi yêu cầu **liệt kê doanh số**, bạn PHẢI liệt kê tên sản phẩm và doanh số/số lượng tương ứng."
            "3. QUY TẮC PHỤ KHÁC: Nếu context chứa thông tin mâu thuẫn, ưu tiên thông tin mang tính tuyệt đối."
            
            "HƯỚNG DẪN TRẢ LỜI:"
            "1. Hãy trả lời CHÍNH XÁC và **NGẮN GỌN** nhất có thể bằng tiếng Việt."
            "2. **TUYỆT ĐỐI KHÔNG GIẢI THÍCH** quy tắc hay quá trình suy luận của bạn."
            "3. Chỉ trả lời thẳng vào thông tin được hỏi (ví dụ: 'Doanh số... là X VNĐ')."
            
            "Nếu thông tin hoàn toàn không có trong context, hãy trả lời: 'Tôi đã xem bộ nhớ, nhưng chưa có thông tin về {input}.'"
            "\n\nContext:\n{context}\n\nCâu hỏi: {input}"
        )
        # [Giữ nguyên phần còn lại của on_start]
        document_chain = create_stuff_documents_chain(cl.user_session.get("llm_logic"), rag_prompt)
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        cl.user_session.set("retrieval_chain", retrieval_chain)

        # --- 7. Tools ---
        from langchain.tools import tool
        # (Toàn bộ code @tool của bạn giữ nguyên)
        @tool
        def xem_bo_nho(show: str = "xem"):
            """Liệt kê toàn bộ ghi chú đã lưu trong bộ nhớ dài hạn."""
            return dump_all_memory_texts()

        @tool
        def luu_thong_tin(noi_dung: str):
            """Lưu thông tin hoặc ghi chú người dùng."""
            try:
                text = (noi_dung or "").strip()
                if not text:
                    return "⚠️ Không có nội dung để lưu."
                texts = [text]
                facts = _extract_facts(text)
                if facts:
                    texts.extend(facts)
                vectorstore.add_texts(texts)
                return f"✅ ĐÃ LLƯU: {', '.join(texts)}"
            except Exception as e:
                return f"❌ LỖI LƯU: {e}"
        from pydantic import BaseModel, Field
        
        class DatLichSchema(BaseModel):
            noi_dung_nhac: str = Field(..., description="Nội dung nhắc, ví dụ: 'Đi tắm'")
            thoi_gian: str = Field(..., description="Thời gian tự nhiên: '1 phút nữa', '20:15', 'mai 8h'")
            escalate: bool = Field(False, description="Nếu True: nhắc 1 lần đúng giờ, rồi lặp 5s nếu chưa phản hồi")

        @tool(args_schema=DatLichSchema)
        def dat_lich_nhac_nho(noi_dung_nhac: str, thoi_gian: str, escalate: bool = False) -> str:
            """Đặt lịch nhắc việc.
            
            - Nếu `escalate=True` (hoặc câu có 'nếu không phản hồi'): bắn 1 lần ở thời điểm yêu cầu,
            rồi lặp 5s/lần cho tới khi người dùng phản hồi (ack).
            - Hỗ trợ: thời điểm một lần (ví dụ '1 phút nữa', '20:15 hôm nay'),
            lặp theo khoảng ('mỗi 10 phút', 'every 30s'),
            và lịch định kỳ tuần/tháng/ngày ('thứ 4 hàng tuần 8:30', 'ngày 1 hàng tháng 09:00', 'mỗi ngày 7h').

            Args:
                noi_dung_nhac: Nội dung thông báo.
                thoi_gian: Chuỗi thời gian người dùng nói tự nhiên.
                escalate: Bật chế độ leo thang nhắc 5s/lần nếu chưa phản hồi.

            Returns:
                Chuỗi xác nhận đã lên lịch hoặc thông báo lỗi.
            """   
            try:
                ensure_scheduler()

                internal_session_id = cl.user_session.get("chainlit_internal_id")
                if not SCHEDULER: # Kiểm tra nếu scheduler khởi động lỗi
                    return "❌ LỖI NGHIÊM TRỌNG: Scheduler không thể khởi động."

                internal_session_id = cl.user_session.get("chainlit_internal_id")
                if not internal_session_id:
                    return "❌ LỖI: Không tìm thấy 'chainlit_internal_id'. Vui lòng F5."

                noti_text = (noi_dung_nhac or "").strip()
                if not noti_text:
                    return "⚠️ Thiếu nội dung thông báo."

                when_dt = parse_when_to_dt(thoi_gian)
                now_vn  = datetime.now(VN_TZ)
                repeat_sec = parse_repeat_to_seconds(thoi_gian)

                # Fallback: nếu agent chưa truyền escalate, vẫn cho phép bắt bằng câu chữ
                if escalate is False:
                    low_text = f"{thoi_gian} {noti_text}".lower()
                    escalate = ("không phản hồi" in low_text) or ("khong phan hoi" in low_text)

                if not escalate:
                    # ===== KHÔNG LEO THANG: 1 lần hoặc lặp chuẩn =====
                    job_id = f"reminder-{internal_session_id}-{uuid.uuid4().hex[:8]}"
                    # ... (code parse when_dt, repeat_sec ... giữ nguyên) ...

                    # 2) ƯU TIÊN CRON (tuần / tháng / mỗi ngày)
                    cron = detect_cron_schedule(thoi_gian)
                    if cron:
                        job_id = f"reminder-cron-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                        SCHEDULER.add_job(
                            _do_push, # <--- SỬA
                            trigger=cron["trigger"],
                            id=job_id,
                            args=[internal_session_id, noti_text], # <--- SỬA
                            replace_existing=False,
                            misfire_grace_time=60,
                        )
                        vectorstore.add_texts([f"[REMINDER_CRON] type={cron['type']} | {thoi_gian} | {noti_text} | job_id={job_id}"])
                        return f"📅 ĐÃ LÊN LỊCH ({cron['type']}): '{noti_text}' • {thoi_gian}"

                    if repeat_sec > 0:
                        start_dt = when_dt if when_dt > now_vn else now_vn + timedelta(seconds=1)
                        trigger = IntervalTrigger(seconds=repeat_sec, start_date=start_dt, timezone=VN_TZ)
                        SCHEDULER.add_job(
                            _do_push, # <--- SỬA
                            trigger=trigger, id=job_id,
                            args=[internal_session_id, noti_text], # <--- SỬA
                            replace_existing=False, misfire_grace_time=30
                        )
                        vectorstore.add_texts([f"[REMINDER_REPEAT] start={start_dt.isoformat()} | every={repeat_sec}s | {noti_text} | job_id={job_id}"])
                        return f"⏰ ĐÃ LÊN LỊCH LẶP: '{noti_text}' • mỗi {repeat_sec}s • bắt đầu {start_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                    else:
                        if when_dt <= (now_vn - timedelta(seconds=10)):
                            return f"❌ Thời gian '{thoi_gian}' (parse ra: {when_dt}) đã qua."
                        trigger = DateTrigger(run_date=when_dt)
                        SCHEDULER.add_job(
                            _do_push, # <--- SỬA
                            trigger=trigger, id=job_id,
                            args=[internal_session_id, noti_text], # <--- SỬA
                            replace_existing=False, misfire_grace_time=60
                        )
                        vectorstore.add_texts([f"[REMINDER_SCHEDULED] {when_dt.isoformat()} | {noti_text} | job_id={job_id}"])
                        return f"⏰ ĐÃ LÊN LỊCH: '{noti_text}' @ {when_dt.strftime('%Y-%m-%d %H:%M:%S')}"

                # ===== LEO THANG: 1 lần → rồi 5s/lần nếu chưa phản hồi =====
                if when_dt <= (now_vn - timedelta(seconds=10)):
                    return f"❌ Thời gian '{thoi_gian}' (parse ra: {when_dt}) đã qua."

                first_job_id = f"first-{internal_session_id}-{uuid.uuid4().hex[:6]}"
                trigger = DateTrigger(run_date=when_dt)

                # SỬA ĐỔI: Gọi hàm _first_fire_escalation_job (global)
                SCHEDULER.add_job(
                    _first_fire_escalation_job, # <--- SỬA: Gọi hàm global mới
                    trigger=trigger,
                    id=first_job_id,
                    args=[internal_session_id, noti_text, 5], # <--- SỬA: Thêm 'every_sec=5'
                    replace_existing=False,
                    misfire_grace_time=60
                )
                
                vectorstore.add_texts([f"[REMINDER_ESCALATE] first_at={when_dt.isoformat()} | every=5s | {noti_text} | first_job_id={first_job_id}"])
                return f"⏰ ĐÃ LÊN LỊCH (leo thang): '{noti_text}' • @ {when_dt.strftime('%Y-%m-%d %H:%M:%S')} • nếu chưa phản hồi sẽ nhắc mỗi 5s"

            except Exception as e:
                import traceback; print(traceback.format_exc())
                return f"❌ Lỗi khi tạo nhắc: {e}"


        @tool
        def hoi_thong_tin(cau_hoi: str):
            """
            Dùng để trả lời câu hỏi bằng cách TÌM KIẾM NỘI DUNG 
            bên trong các file đã upload (Excel, PDF, text) 
            hoặc các ghi chú (facts) đã lưu.
            Ví dụ: 'giá của H064-0121 là bao nhiêu?', 'tôi thích ăn gì?'
            """
            try:
                retrieval_chain = cl.user_session.get("retrieval_chain")
                if not retrieval_chain:
                    return "❌ Không tìm thấy retrieval_chain."
                resp = retrieval_chain.invoke({"input": cau_hoi})
                return resp.get("answer", "Tôi chưa có thông tin đó.")
            except Exception as e:
                return f"❌ Lỗi truy xuất: {e}"

        tools = [
            luu_thong_tin, dat_lich_nhac_nho, hoi_thong_tin, xem_bo_nho, push_thu, xem_lich_nhac, 
            tim_file_de_tai_ve, xem_danh_sach_file # <--- THÊM VÀO ĐÂY
        ]
        # --- 8. Agent ---
        # (Toàn bộ code Agent của bạn giữ nguyên)
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Bạn là một trợ lý robot trung gian. Nhiệm vụ của bạn là: "
             "1. Nhận yêu cầu từ người dùng (input). "
             "2. Chọn ĐÚNG tool (luu_thong_tin, dat_lich_nhac_nho, hoi_thong_tin, xem_bo_nho, push_thu, xem_lich_nhac, tim_file_de_tai_ve, xem_danh_sach_file). " # <--- THÊM VÀO ĐÂY
             "3. Gọi tool đó với tham số chính xác. "
             "4. Trả về KẾT QUẢ (observation) từ tool đó cho người dùng. "
             "LƯU Ý: Luôn trả lời bằng tiếng Việt. "

             "QUAN TRỌNG: Bạn KHÔNG ĐƯỢC phép thêm bất kỳ lời bình luận, câu chào, hay câu hỏi nào. "
             "Bạn PHẢI trả về CHÍNH XÁC, NGUYÊN BẢN (raw) kết quả (observation) mà tool đã cung cấp. "
             "Nếu tool trả về '✅ ĐÃ LƯU: ...', bạn phải trả lời '✅ ĐÃ LƯU: ...'. "
             "Nếu tool trả về '✅ Đã liệt kê...', bạn phải trả lời '✅ Đã liệt kê...'. "
             "KHÔNG ĐƯỢC thay đổi."
             ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Sửa: Dùng AgentExecutor chuẩn và tắt verbose
        agent = create_openai_tools_agent(
            llm=cl.user_session.get("llm_logic"),
            tools=tools,
            prompt=agent_prompt,
        )
        agent_executor = CleanAgentExecutor( # <--- SỬA THÀNH CLASS NÀY
            agent=agent, 
            tools=tools, 
            verbose=False, 
            handle_parsing_errors=True,
        )
        cl.user_session.set("agent_executor", agent_executor)

        # --- 9. Kết thúc ---
        # Xóa dòng check_queue ở đây (vì Poller đã chạy)
        
        await cl.Message(
            content="🧠 **Trợ lý đã sẵn sàng**. Hãy nhập câu hỏi để bắt đầu!"
        ).send()
        # === MỚI: LƯU TẤT CẢ ELEMENTS KHỞI ĐỘNG ===
        all_elements = cl.user_session.get("elements", [])
        cl.user_session.set("elements", all_elements)

    except Exception as e:
        await cl.Message(content=f"💥 Lỗi khởi tạo nghiêm trọng: {e}").send()
        import traceback
        print(traceback.format_exc())

# 💬 on_message (Hàm xử lý tin nhắn - ĐÃ TỐI ƯU RAG-FIRST)
@cl.on_message
async def on_message(message: cl.Message):
    """
    (SỬA LẠI) Xử lý tin nhắn đến từ người dùng.
    ƯU TIÊN XỬ LÝ FILE TRƯỚC.
    """
    
    # --- 0. Quyền và xác nhận (ACK) Escalation ---
    try:
        internal_session_id = cl.user_session.get("chainlit_internal_id")
        if internal_session_id and internal_session_id in ACTIVE_ESCALATIONS:
            ACTIVE_ESCALATIONS[internal_session_id]["acked"] = True
            _cancel_escalation(internal_session_id)
            print(f"[Escalation] Đã nhận phản hồi từ user → tắt nhắc lặp.")
    except Exception as _:
        pass

    # --- 0.1. Kiểm tra từ khóa đặc biệt (như cũ) ---
    low = (message.content or "").lower()
    if any(k in low for k in ["lịch nhắc", "lich nhac"]) and any(k in low for k in ["hiện", "hien", "đang"]):
        await ui_show_active_reminders()
        return
    # SỬA: Thêm trigger cho file list
    if any(k in low for k in ["danh sách file", "ds file", "file đã up"]):
        await ui_show_active_files()
        return

    # --- 0.2. Lấy dữ liệu Session ---
    agent_executor = cl.user_session.get("agent_executor")
    session_id = cl.user_session.get("session_id")
    chat_history = cl.user_session.get("chat_history")

    if not agent_executor or not session_id or chat_history is None:
        await cl.Message("❌ Lỗi nghiêm trọng: Phiên làm việc (session) chưa được khởi tạo. Vui lòng F5 trang.").send()
        return

    user_text = (message.content or "").strip()
    ai_output = "" # Chuẩn bị lưu lịch sử

    # --- 1. LOGIC MỚI: XỬ LÝ FILE (ƯU TIÊN) ---
    if message.elements:
        note_text = user_text or "(File đính kèm)"
        
        # Chạy vòng lặp cho TỪNG file (để không crash)
        for el in message.elements:
            proc_msg = cl.Message(content=f"Đang xử lý file: `{el.name}`...")
            await proc_msg.send()
            
            try:
                # SỬA LỖI: Bọc try...except riêng cho từng file
                el: ClFile = el
                
                if "image" in el.mime:
                    # SỬA LỖI: Truyền el.name và nhận về (dst, name)
                    dst, name = _save_image_and_note(
                        el.path, 
                        note_text, 
                        el.name # <--- Truyền tên gốc vào
                    )
                    proc_msg.content = f"🖼️ Đã lưu ảnh: `{name}`\nGhi chú: {note_text}" # <--- Sửa: Dùng 'name'
                    await proc_msg.update()
                else:
                    chunk_count, name = _load_and_process_document(
                        src_path=el.path,
                        original_name=el.name,
                        mime_type=el.mime or "", 
                        user_note=note_text
                    )
                    if chunk_count > 0:
                        proc_msg.content = f"✅ Đã xử lý và ghi nhớ `{name}` ({chunk_count} phần nội dung). Ghi chú: {note_text}"
                    else:
                        proc_msg.content = f"🗂️ Đã lưu file (không hỗ trợ đọc): `{name}`. Ghi chú: {note_text}"
                    await proc_msg.update()

            except Exception as e:
                # SỬA LỖI: Báo lỗi file cụ thể và KHÔNG CRASH
                import traceback
                print("[ERROR] Lỗi xử lý file trong on_message:")
                print(traceback.format_exc())
                proc_msg.content = f"❌ Lỗi khi xử lý file `{el.name}`: {e}"
                await proc_msg.update()
        
        # SỬA LỖI: Nếu user chỉ upload file và gõ text ghi chú,
        # chúng ta KHÔNG chạy Agent với text đó nữa.
        if user_text:
             # Chỉ lưu lịch sử, không chạy agent
             chat_history.append({"role": "user", "content": f"(Upload file) {user_text}"})
             save_chat_history(session_id, chat_history)
             return # Kết thúc tại đây

    # --- 2. XỬ LÝ TEXT (Chỉ chạy nếu KHÔNG có file) ---
    ai_output = ""
    if user_text:
        msg = cl.Message(content="")
        await msg.send()
        try:
            print(f"[Flow] Bắt đầu gọi Agent (Clean) với câu: '{user_text}'")
            
            agent_response = await agent_executor.ainvoke({"input": user_text})
            ai_output = agent_response.get("output", "⚠️ Rất tiếc, tôi gặp lỗi khi xử lý.")

            # === SỬA LỖI: Bỏ kiểm tra HTML ===
            
            output_clean = ai_output.strip()
            
            if output_clean.startswith("!["):
                # 1. Đây là Markdown (Ảnh)
                msg.content = output_clean
                await msg.update()
            else:
                # 2. Đây là text thường (hoặc link Markdown)
                msg.content = ai_output
                await msg.update()

        except Exception as e:
            ai_output = f"❌ Lỗi khi xử lý: {e}"
            msg.content = ai_output
            await msg.update()

    # --- 3. Lưu lịch sử (Chỉ lưu nếu có text) ---
    try:
        if user_text:
            # Kiểm tra xem đây có phải là tin nhắn đầu tiên không
            is_first_message = len(chat_history) == 0
            
            # Thêm tin nhắn vào bộ nhớ tạm (memory)
            chat_history.append({"role": "user", "content": user_text})
            chat_history.append({"role": "assistant", "content": ai_output})
            
            if is_first_message:
                # === ĐÂY LÀ TIN NHẮN ĐẦU TIÊN ===
                
                # 1. Lấy ID tạm thời
                old_session_id = session_id 
                
                # 2. Tạo ID mới từ câu chat
                new_session_id = _sanitize_filename(user_text)
                
                # 3. Cập nhật ID trong session
                cl.user_session.set("session_id", new_session_id)
                session_id = new_session_id # Cập nhật biến local
                
                # 4. (Tùy chọn) Xóa file session tạm thời cũ (nếu có)
                delete_session(old_session_id) # Hàm này đã có (dòng 822)
                
                print(f"[Session] Đã đổi tên: {old_session_id} -> {new_session_id}")
                
                # 5. Dọn dẹp UI khởi động (xóa các nút "Tải hội thoại")
                try:
                    all_elements = cl.user_session.get("elements", [])
                    for el in all_elements:
                        await el.remove()
                    cl.user_session.set("elements", []) # Reset
                except Exception as e:
                    print(f"Lỗi dọn dẹp UI (on_message): {e}")

            # 6. Lưu file với ID ĐÚNG (mới hoặc cũ)
            save_chat_history(session_id, chat_history)
            
    except Exception as e:
        print(f"⚠️ Lỗi lưu chat history cho {session_id}: {e}")
        
@cl.on_chat_end
async def on_chat_end():
    """Hủy các tác vụ nền VÀ hủy đăng ký "Thuê bao" khi đóng session."""
    session_id = cl.user_session.get("chainlit_internal_id", "unknown")
    try:
        # 1. Hủy task (Rất quan trọng)
        #    (Hàm 'session_receiver_poller' sẽ tự Hủy đăng ký trong 'finally')
        task = cl.user_session.get("poller_task")
        if task:
            task.cancel()
            await asyncio.sleep(0.1) 
            print(f"[Session] Đã hủy task 'Thuê bao' cho {session_id}")
    except Exception as e:
        print(f"[Session] Lỗi khi on_chat_end: {e}")

# (Dán 3 hàm này vào CUỐI CÙNG của file app.py)

@cl.action_callback("new_chat")
async def on_new_chat(action: cl.Action):
    """Tải lại trang để bắt đầu một session mới."""
    await cl.Message(content="✨ Đang tạo cuộc trò chuyện mới...").send()
    await cl.Message(content="").send() # Cần 1 tin nhắn trống để reload
    await cl.Reload().send()


@cl.action_callback("show_session_list")
async def on_show_session_list(action: cl.Action):
    """
    (SỬA LỖI UI) Hàm này chạy khi user nhấn 'Tải hội thoại cũ'.
    Nó sẽ lấy danh sách và hiển thị ra các nút session.
    """
    sessions = get_all_sessions() # Hàm này đã có (dòng 806)
    if not sessions:
        await cl.Message(content="Không tìm thấy hội thoại cũ nào.").send()
        return

    # Tạo một action (nút) cho mỗi file session
    actions = [
        cl.Action(
            name="load_specific_session", # TẤT CẢ các nút này gọi CÙNG 1 callback
            label=f"💬 {s}", 
            payload={"session_id": s} # Payload chứa ID của session cần tải
        ) 
        for s in sessions
    ]
    
    await cl.Message(
        content="Vui lòng chọn hội thoại để tải:", 
        actions=actions
    ).send()


# (THAY THẾ HÀM CŨ TỪ DÒNG 1746)

# (THAY THẾ HÀM CŨ TỪ DÒNG 1746)

@cl.action_callback("load_specific_session")
async def on_load_specific_session(action: cl.Action):
    """
    (SỬA LỖI UI) Tải 1 session, XÓA SẠCH UI cũ trước, 
    và LƯU LẠI elements mới.
    """
    
    session_id = action.payload.get("session_id")
    if not session_id:
        await cl.Message(content="❌ Lỗi: Không nhận được session_id.").send()
        return

    # 1. Tải lịch sử chat từ file .json
    history = load_chat_history(session_id)
    if not history:
        await cl.Message(content=f"❌ Lỗi: Không tải được {session_id} hoặc file bị rỗng.").send()
        return

    # 2. SỬA LỖI: Xóa SẠCH toàn bộ UI cũ
    try:
        # Lấy TẤT CẢ elements (tin nhắn, nút bấm) ĐÃ LƯU TỪ LẦN TRƯỚC
        all_elements = cl.user_session.get("elements", [])
        for el in all_elements:
            await el.remove()
        
        cl.user_session.set("elements", []) # Reset lại danh sách
    except Exception as e:
        print(f"Lỗi dọn dẹp UI: {e}")
    
    # 3. Tạo tin nhắn "Loading" (và LƯU LẠI nó)
    loading_msg = await cl.Message(content=f"✅ Đang tải hội thoại: **{session_id}**...").send()

    # 4. Cập nhật session HIỆN TẠI
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_history", history)
    
    # 5. Phát lại (Replay) VÀ LẤY VỀ danh sách tin nhắn
    replayed_elements = await replay_history(history) # <-- SỬA
    
    # 6. LƯU TẤT CẢ elements MỚI vào session
    #    (để lần sau có thể xóa chúng)
    new_elements_list = [loading_msg] + replayed_elements
    cl.user_session.set("elements", new_elements_list)