# topic_engine.py
import os, re, uuid, shutil, unicodedata, string
from datetime import datetime
from typing import List, Optional, Tuple

# ==== Vector store (Chroma + OpenAI Embeddings) ====
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# === CONFIG ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_DIR   = os.path.abspath(".")
MEMORY_DIR = os.path.join(BASE_DIR, "memory_db")
FILES_DIR  = os.path.join(MEMORY_DIR, "files")
IMAGES_DIR = os.path.join(MEMORY_DIR, "images")
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(FILES_DIR,  exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

_embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model="text-embedding-3-small")
_vector     = Chroma(persist_directory=MEMORY_DIR, embedding_function=_embeddings, collection_name="memory")

# Topic (giữ trong RAM – app chủ quản có thể lưu ở session)
_current_topic = "general"

# ====== Helpers chung ======
def _ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def vn_fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower().strip()

_VI_WH   = {"ai","cai gi","gi","o dau","khi nao","bao gio","vi sao","tai sao","nhu the nao","bao nhieu","may"}
_VI_FILL = {"la","la gi","ve","cua","cho","de","voi","nhu","nao","can","bao","nhieu","may","o","trong","thang","nam","ngay"}
_PUNC    = set(string.punctuation + "“”’‘–—…")

def canon_topic(text: str, max_tokens: int = 7) -> str:
    t = vn_fold(text)
    t = "".join("" if ch in _PUNC else ch for ch in t)
    toks = [w for w in t.split() if w not in _VI_WH and w not in _VI_FILL]
    if not toks: toks = t.split()
    return " ".join(toks[:max_tokens]) or "general"

def set_current_topic(t: str): 
    global _current_topic; _current_topic = t or "general"

def get_current_topic() -> str: 
    return _current_topic

def update_topic_from_text(user_text: str):
    """Gọi với mọi câu không phải lệnh. Suy ra topic từ câu hỏi/ngữ cảnh."""
    lf = vn_fold(user_text or "")
    if not lf: return
    # đừng cập nhật topic khi là lệnh
    if re.search(r"\b(doi|đổi|cap nhat|cập nhật)\b", lf) and " thanh " in lf: return
    if re.match(r"^\s*(them|thêm|add|ghi chu|ghi chú|xoa|xóa)\b", lf): return
    set_current_topic(canon_topic(user_text))

# ====== Low-level storage ======
def _col_get_all():
    raw = _vector._collection.get()
    return raw.get("ids", []) or [], raw.get("documents", []) or [], raw.get("metadatas", []) or []

def add_note(text: str, topic: Optional[str]=None):
    topic = topic or get_current_topic()
    _vector.add_texts(
        texts=[text],
        metadatas=[{"type":"NOTE","topic":topic,"ts":_ts()}],
        ids=[f"note-{uuid.uuid4().hex[:8]}"],
    )
    _vector.persist()

def add_file_record(path: str, display_name: Optional[str], note: str, topic: Optional[str]=None):
    topic = topic or get_current_topic()
    display_name = display_name or os.path.basename(path)
    rec = f"[FILE] path={path} | name={display_name} | note={note.strip() or '(no note)'}"
    _vector.add_texts(
        texts=[rec],
        metadatas=[{"type":"FILE","topic":topic,"ts":_ts(),"filename":display_name}],
        ids=[f"file-{uuid.uuid4().hex[:8]}"],
    )
    _vector.persist()

def list_by_topic(topic: str) -> List[Tuple[str,str,dict]]:
    ids, docs, metas = _col_get_all()
    tq = vn_fold(topic)
    out = []
    for i,(d,m) in enumerate(zip(docs, metas)):
        if vn_fold(str((m or {}).get("topic", ""))) == tq:
            out.append((ids[i], d, m))
    return out

def delete_by_topic(topic: str, contains: Optional[str]=None) -> int:
    ids, docs, metas = _col_get_all()
    tq = vn_fold(topic); cq = vn_fold(contains) if contains else None
    to_del = []
    for i,(d,m) in enumerate(zip(docs, metas)):
        if vn_fold(str((m or {}).get("topic",""))) != tq: 
            continue
        if cq and cq not in vn_fold(d or ""):
            continue
        to_del.append(ids[i])
    if to_del:
        _vector._collection.delete(ids=to_del); _vector.persist()
    return len(to_del)

# ====== File save (copy vào memory_db/files) ======
def save_attachments(paths: List[str], user_note: str="", topic: Optional[str]=None) -> List[str]:
    """Copy file vào kho và tạo record [FILE]. Trả về danh sách đích."""
    topic = topic or get_current_topic()
    saved = []
    for src in paths:
        name = os.path.basename(src)
        ext  = os.path.splitext(name)[1]
        dst  = os.path.join(FILES_DIR, f"{_ts()}-{uuid.uuid4().hex[:6]}{ext}")
        shutil.copyfile(src, dst)
        add_file_record(dst, name, user_note or "", topic)
        saved.append(dst)
    return saved

# ====== PARSER lệnh CHUNG ======
_RE_CHANGE = re.compile(r"^\s*(đổi|doi|update|cập nhật|cap nhat)\s+(?P<old>.+?)\s+(thành|thanh)\s+(?P<new>.+)$", flags=re.I)
_RE_ADD    = re.compile(r"^\s*(thêm|them|add|ghi chú|ghi chu[:\-]?)\s+(?P<val>.+)$", flags=re.I)
_RE_DEL    = re.compile(r"^\s*(xóa|xoa)\s*(?P<val>.*)$", flags=re.I)

def process_command(command: str, attachments: Optional[List[str]]=None) -> str:
    """
    Engine CHUNG cho các thao tác:
    - 'đổi A thành B'  → xoá các mục của topic hiện tại (ưu tiên chứa 'A'; nếu không có A thì xoá hết) → thêm 'B'.
                         Nếu có attachments: xoá FILE cũ trong topic rồi lưu attachments mới.
    - 'thêm B'         → thêm NOTE 'B' (và lưu attachments nếu có).
    - 'xóa [A]'        → xoá mục chứa 'A' trong topic; nếu không có 'A' → xoá toàn bộ topic.
    - Không khớp lệnh  → trả lại danh sách mục trong topic (để xem nhanh).
    """
    topic = get_current_topic()
    text  = (command or "").strip()
    att   = attachments or []
    low   = vn_fold(text)

    # --- ĐỔI ---
    m = _RE_CHANGE.match(text) or _RE_CHANGE.match(low)
    if not m and " thanh " in low:
        # hỗ trợ dạng rút gọn "... thành ..."
        m = re.match(r"^(?P<old>.+?)\s+(thanh|thành)\s+(?P<new>.+)$", text, flags=re.I)
    if m:
        old_span, new_span = m.span("old"), m.span("new")
        old_raw = text[old_span[0]:old_span[1]].strip().strip('"').strip("'")
        new_raw = text[new_span[0]:new_span[1]].strip().strip('"').strip("'")

        deleted = delete_by_topic(topic, contains=old_raw)
        if deleted == 0:
            deleted = delete_by_topic(topic)
        add_note(new_raw, topic)

        # Nếu có file đính kèm: thay luôn file cho topic
        if att:
            # xoá tất cả FILE hiện có trong topic
            ids, docs, metas = _col_get_all()
            to_del = []
            for i,(d,m) in enumerate(zip(docs, metas)):
                if vn_fold(str((m or {}).get("topic",""))) == vn_fold(topic) and (m or {}).get("type")=="FILE":
                    to_del.append(ids[i])
            if to_del:
                _vector._collection.delete(ids=to_del); _vector.persist()
            save_attachments(att, user_note=new_raw, topic=topic)

        return f"✅ Đã đổi chủ đề [{topic}] thành: “{new_raw}” (xoá {deleted})."

    # --- THÊM ---
    m = _RE_ADD.match(text) or _RE_ADD.match(low)
    if m:
        val_span = m.span("val")
        val = text[val_span[0]:val_span[1]].strip().strip('"').strip("'")
        add_note(val, topic)
        if att: save_attachments(att, user_note=val, topic=topic)
        return f"➕ Đã thêm vào chủ đề [{topic}]: “{val}”" + (f" (+{len(att)} file)" if att else "")

    # --- XÓA ---
    m = _RE_DEL.match(text) or _RE_DEL.match(low)
    if m:
        val_span = m.span("val"); needle = text[val_span[0]:val_span[1]].strip()
        if needle:
            deleted = delete_by_topic(topic, contains=needle)
            return f"🗑️ Đã xoá {deleted} mục trong chủ đề [{topic}] có chứa “{needle}”."
        deleted = delete_by_topic(topic)
        return f"🗑️ Đã xoá toàn bộ {deleted} mục của chủ đề [{topic}]."

    # --- Không khớp lệnh → liệt kê nhanh ---
    items = list_by_topic(topic)
    if not items:
        return f"(Chủ đề [{topic}] chưa có dữ liệu.)"
    lines = []
    for _, d, m in items:
        ty = (m or {}).get("type","?")
        if ty == "FILE":
            lines.append("FILE — " + d)
        else:
            lines.append("NOTE — " + d)
    return "📌 Chủ đề [" + topic + "]\n- " + "\n- ".join(lines)
