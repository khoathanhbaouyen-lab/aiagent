# chat_logic.py
import asyncio
import unidecode
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import re

import os
import shutil
import uuid
from pathlib import Path

import pandas as pd
import pypdf
import docx
import html
from nicegui import ui
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docx import Document
from helpers import current_user, run_js_bg, embeddings
from rag_helpers import (
    load_user_fact_dict,
    save_user_fact_dict,
    call_llm_to_classify,
    get_user_llm,
    get_user_vectorstore_retriever,
    _build_rag_filter_from_query,
    _helper_sort_results_by_timestamp,
    _llm_filter_for_selection,
    VN_TZ,
    _timestamp,
    _llm_batch_split_classify, # 👈 THÊM IMPORT
    _llm_split_notes,          # 👈 THÊM IMPORT
)

# ====== CACHE GLOBAL (KHÔNG JSON, KHÔNG LƯU FILE) ======
LLM_CACHE: Dict[str, Any] = {}
VECTORSTORE_CACHE: Dict[str, Any] = {}
RETRIEVER_CACHE: Dict[str, Any] = {}

# Thư mục public/files để lưu file/ảnh giống code cũ
# ====== CACHE GLOBAL (KHÔNG JSON, KHÔNG LƯU FILE) ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public") # Sẽ là "I:\AI NEW\public"
PUBLIC_FILES_DIR = os.path.join(PUBLIC_DIR, "files") # Sẽ là "I:\AI NEW\public\files"
os.makedirs(PUBLIC_FILES_DIR, exist_ok=True)
# ================== HELPER CHUNG CHO FILE/ẢNH (PORT TỪ CODEOLD) ==================

def _get_simple_file_type(mime_type: str, src_path: str) -> str:
    """Rút gọn loại file: 'image', 'excel', 'pdf', 'word', 'text', 'file'."""
    mime_low = (mime_type or "").lower()
    src_low = (src_path or "").lower()

    if any(ext in src_low for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return "image"
    if "excel" in mime_low or src_low.endswith((".xlsx", ".xls")):
        return "excel"
    if "pdf" in mime_low or src_low.endswith(".pdf"):
        return "pdf"
    if "wordprocessingml" in mime_low or src_low.endswith(".docx"):
        return "word"
    if "text" in mime_low or src_low.endswith((".txt", ".md", ".py", ".js")):
        return "text"
    return "file"


def _save_file_and_note(
    vectorstore,
    src_path: str,
    original_name: Optional[str],
    user_text: str,
    fact_key: str = "general",
    fact_label: str = "General",
    file_type: str = "file",
) -> tuple[str, str]:
    """
    (PORT TỪ CODEOLD – GIỮ NGUYÊN TÊN HÀM)
    - Copy file từ src_path sang PUBLIC_FILES_DIR với tên safe (timestamp + uuid).
    - Ghi 1 record [FILE] vào VectorStore (entry_type = 'file_master').
    """
    name = original_name or os.path.basename(src_path) or f"file-{uuid.uuid4().hex[:6]}"
    ext = os.path.splitext(name)[1]
    safe_name = f"{_timestamp()}-{uuid.uuid4().hex[:6]}{ext or ''}"

    dst = os.path.join(PUBLIC_FILES_DIR, safe_name)
    shutil.copyfile(src_path, dst)

    original_content_str = f"[FILE] path={dst} | name={name} | note={user_text.strip() or '(no note)'}"
    vector_text_str = f"{fact_label} | {name} | {user_text.strip() or '(no note)'}"

    metadata = {
        "fact_key": fact_key,
        "fact_label": fact_label,
        "file_type": file_type,
        "original_content": original_content_str,
        "entry_type": "file_master",
        "timestamp": datetime.now(VN_TZ).isoformat(),
    }

    vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
    return dst, name
# chat_logic.py

# ... (Giữ nguyên code ở trên) ...

# ================== UI: XEM TẤT CẢ FILE/ẢNH ==================
# chat_logic.py (KIỂM TRA HÀM NÀY - KHOẢNG DÒNG 140)

async def xem_tat_ca_file_da_luu(message_container: ui.column) -> str:
    """
    (SỬA LỖI V109 - HIỂN THỊ ẢNH + NÚT TẢI)
    Hiển thị toàn bộ FILE/ẢNH đã lưu (file_master) – mới nhất lên đầu.
    """
    cu = current_user()
    if not cu:
        return "❌ Lỗi: Chưa đăng nhập, không biết user để xem file."

    user_id_str = cu.get("email") or cu.get("id") or "unknown"
    _, vectorstore, _ = _ensure_llm_and_vectorstore(user_id_str)

    files = await asyncio.to_thread(list_active_files, vectorstore)

    with message_container:
        if not files:
            ui.chat_message(
                text="📂 Chưa có FILE/ẢNH nào được lưu.",
                name="Bot",
            )
            return "📂 Chưa có FILE/ẢNH nào được lưu."

        ui.chat_message(
            text="📂 **Danh sách FILE/ẢNH đã lưu (mới nhất lên đầu):**",
            name="Bot",
        )

        for f in files:
            # Lấy tất cả thông tin
            full_path = f.get("path") or ""
            original_name = f.get("original_name") or "(không tên)"
            note = f.get("note") or "(không ghi chú)"
            file_type = f.get("file_type") or "file"
            doc_id = f.get("id") # <-- Cần cho nút Xóa
            saved_name = f.get("saved_name")
            
            file_url = "#"
            if saved_name:
                file_url = f"/public/files/{saved_name}"

            # Card hiển thị file (Gán vào biến 'card' để ẩn khi xóa)
            with ui.card().classes("w-full max-w-xl my-1") as card:
                
                safe_download_name = original_name.replace('"', "'")
                
                # --- 🚀 BẮT ĐẦU SỬA LỖI V109 (HIỂN THỊ ẢNH) 🚀 ---
                
                if file_type == 'image' and file_url != "#":
                    # --- 1. HIỂN THỊ ẢNH ---
                    ui.image(file_url).classes('w-full rounded') # Hiển thị ảnh
                    ui.label(original_name).classes("font-semibold mt-2") # Hiển thị tên
                
                else:
                    # --- 2. HIỂN THỊ FILE (LINK TẢI) ---
                    if file_url != "#":
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('description').classes('m-1 text-gray-600')
                            # Link tải file
                            ui.link(original_name, file_url, new_tab=True) \
                                .props(f'download="{safe_download_name}"') \
                                .classes('font-semibold text-blue-600 text-base')
                    else:
                        ui.label(f"📄 {original_name}").classes("font-semibold") # Fallback
                
                # --- 🚀 KẾT THÚC SỬA LỖI V109 🚀 ---

                ui.label(f"Loại: {file_type}")
                ui.label(f"Ghi chú: {note}")
                
                with ui.row().classes('items-center gap-4 mt-2'): # Tăng gap

                    # --- 🚀 BẮT ĐẦU SỬA LỖI V109 (NÚT TẢI CHO ẢNH) 🚀 ---
                    if file_type == 'image' and file_url != "#":
                         ui.link("Tải ảnh", file_url, new_tab=True) \
                            .props(f'download="{safe_download_name}"') \
                            .classes('text-blue-600 text-sm font-medium')
                    # --- 🚀 KẾT THÚC SỬA LỖI V109 🚀 ---

                    # --- Logic Nút Xóa (V106 - Giữ nguyên) ---
                    async def on_delete_click(
                        doc_id=doc_id, 
                        path=full_path, 
                        card_to_hide=card, 
                        name=original_name,
                        s_name=saved_name 
                    ):
                        if doc_id:
                            await _delete_file_by_id_in_vectorstore(vectorstore, doc_id)
                        
                        correct_path_to_delete = None
                        if s_name:
                             correct_path_to_delete = os.path.join(PUBLIC_FILES_DIR, s_name)
                        path_to_delete = correct_path_to_delete or path

                        if path_to_delete:
                            try:
                                await asyncio.to_thread(os.remove, path_to_delete)
                            except Exception:
                                pass
                        
                        card_to_hide.visible = False 
                        ui.notify(f"🗑️ Đã xóa file: {name}", type="positive")

                    ui.button(
                        "🗑️ Xóa", 
                        on_click=on_delete_click, 
                        color='negative'
                    ).props('flat dense')
                    # --- Kết thúc Nút Xóa ---

    return f"📂 Đã hiển thị {len(files)} file/ảnh."


# ================== UI: XEM FILE THEO TỪ KHÓA ==================
# (Đảm bảo 'asyncio' và 'os' đã được import ở đầu file chat_logic.py)
import asyncio
import os
async def xem_file_theo_tu_khoa(tu_khoa: str, message_container: ui.column) -> str:
    """
    (SỬA LỖI TÊN FILE KHI TẢI VỀ)
    Tìm file theo tên/ghi chú bằng từ khóa (accent-insensitive) và hiển thị.
    """
    cu = current_user()
    if not cu:
        return "❌ Lỗi: Chưa đăng nhập, không biết user để xem file."

    user_id_str = cu.get("email") or cu.get("id") or "unknown"
    _, vectorstore, _ = _ensure_llm_and_vectorstore(user_id_str)

    matches = await asyncio.to_thread(_find_files_by_name_db, vectorstore, tu_khoa)

    with message_container:
        if not matches:
            msg = f"⚠️ Không tìm thấy file nào khớp với '{tu_khoa}'."
            ui.chat_message(text=msg, name="Bot")
            return msg

        ui.chat_message(
            text=f"📂 **Các file khớp với '{tu_khoa}':**",
            name="Bot",
        )

        for f in matches:
            full_path = f.get("path") or ""
            original_name = f.get("original_name") or "(không tên)"
            note = f.get("note") or "(không ghi chú)"
            file_type = f.get("file_type") or "file"
            doc_id = f.get("id")
            
            saved_name = f.get("saved_name") 

            file_url = "#"
            if saved_name:
                file_url = f"/public/files/{saved_name}"

            with ui.card().classes("w-full max-w-xl my-1") as card:
                with ui.row().classes('items-center'):
                    ui.icon('description').classes('m-1 text-gray-600')
                    
                    # --- 🚀 BẮT ĐẦU SỬA LỖI (TÊN FILE KHI TẢI) 🚀 ---
                    safe_download_name = original_name.replace('"', "'")
                    if file_url != "#":
                        # Thay thế ui.label bằng ui.link
                        ui.link(original_name, file_url, new_tab=True) \
                            .props(f'download="{safe_download_name}"') \
                            .classes('font-semibold text-blue-600 text-base')
                    else:
                        ui.label(original_name).classes("font-semibold") # Fallback
                    # --- 🚀 KẾT THÚC SỬA LỖI 🚀 ---

                ui.label(f"Loại: {file_type}")
                ui.label(f"Ghi chú: {note}")
                
                with ui.row().classes('items-center gap-2 mt-2'):
                    # (Đã xóa link "Mở file" ở đây vì đã gộp vào tên file)

                    async def on_delete_click(
                        doc_id=doc_id, 
                        path=full_path, 
                        card_to_hide=card,
                        name=original_name,
                        s_name=saved_name 
                    ):
                        if doc_id:
                            await _delete_file_by_id_in_vectorstore(vectorstore, doc_id)
                        
                        correct_path_to_delete = None
                        if s_name:
                             correct_path_to_delete = os.path.join(PUBLIC_FILES_DIR, s_name)
                        path_to_delete = correct_path_to_delete or path

                        if path_to_delete:
                            try:
                                await asyncio.to_thread(os.remove, path_to_delete)
                            except Exception:
                                pass
                        
                        card_to_hide.visible = False 
                        ui.notify(f"🗑️ Đã xóa file: {name}", type="positive")

                    ui.button(
                        "🗑️ Xóa", 
                        on_click=on_delete_click, 
                        color='negative'
                    ).props('flat dense')

    return f"📂 Đã hiển thị {len(matches)} file khớp."

# ... (Giữ nguyên các hàm khác) ...
# chat_logic.py (DÁN VÀO TRƯỚC HÀM get_rag_response - KHOẢNG DÒNG 340)
async def _display_file_item_in_ui(
    vectorstore, 
    item_metadata: dict,
    message_container: ui.column
) -> None:
    """
    (SỬA LỖI V115 - ĐỒNG BỘ HIỂN THỊ ẢNH/TẢI ẢNH)
    Helper: Render một file/ảnh (từ metadata) ra UI.
    - Dùng ui.image để render.
    - Thêm nút "Tải ảnh" cho file image (giống hàm xem_tat_ca_file).
    """
    try:
        content = item_metadata.get("original_content")
        file_type = item_metadata.get("file_type", "file")
        doc_id = item_metadata.get("doc_id", "unknown_id")

        if not content:
            return

        path_match = re.search(r"path=([^|]+)", content)
        name_match = re.search(r"name=([^|]+)", content)
        note_match = re.search(r"note=([^|]+)", content)
        if not path_match:
            return

        full_path = path_match.group(1).strip() # path (có thể) stale
        goc_name = name_match.group(1).strip() if name_match else "N/A"
        goc_note = note_match.group(1).strip() if note_match else "(không ghi chú)"
        safe_name = html.escape(goc_name) # Dùng cho tên file

        saved_name = os.path.basename(full_path) # Lấy tên file từ path

        safe_href = "#"
        if saved_name:
            safe_href = f"/public/files/{saved_name}"

        with message_container:
            # SỬA LỖI: Không dùng 'with ui.chat_message'
            # vì hàm get_rag_response đã tạo nó rồi (bản V109)
            # Chúng ta chỉ render nội dung BÊN TRONG bubble
            # (Nếu bạn dùng bản vá V110 cũ, nó sẽ tạo bubble lồng bubble)
            
            # Thay vào đó, dùng ui.card lồng bên trong
            with ui.card().classes("w-full max-w-xl my-1") as card:
            
                safe_download_name = goc_name.replace('"', "'")
                
                # --- 🚀 BẮT ĐẦU SỬA LỖI V115 (COPY TỪ 'xem_tat_ca_file') 🚀 ---
                
                if file_type == 'image' and safe_href != "#":
                    # --- 1. HIỂN THỊ ẢNH ---
                    ui.image(safe_href).classes('w-full rounded') # Hiển thị ảnh
                    ui.label(safe_name).classes("font-semibold mt-2") # Hiển thị tên
                
                else:
                    # --- 2. HIỂN THỊ FILE (LINK TẢI) ---
                    if safe_href != "#":
                        with ui.row().classes('items-center gap-1'):
                            ui.icon('description').classes('m-1 text-gray-600')
                            # Link tải file
                            ui.link(safe_name, safe_href, new_tab=True) \
                                .props(f'download="{safe_download_name}"') \
                                .classes('font-semibold text-blue-600 text-base')
                    else:
                        ui.label(f"📄 {safe_name}").classes("font-semibold") # Fallback
                
                # --- 🚀 KẾT THÚC SỬA LỖI V115 🚀 ---

                ui.label(f"Loại: {file_type}")
                ui.label(f"Ghi chú: {goc_note.strip() or '(không ghi chú)'}")
                ui.label(f"ID: {doc_id}").classes('text-xs text-gray-400')
                
                with ui.row().classes('items-center gap-4 mt-2'): # Tăng gap

                    # --- 🚀 BẮT ĐẦU SỬA LỖI V115 (NÚT TẢI ẢNH) 🚀 ---
                    if file_type == 'image' and safe_href != "#":
                         ui.link("Tải ảnh", safe_href, new_tab=True) \
                            .props(f'download="{safe_download_name}"') \
                            .classes('text-blue-600 text-sm font-medium')
                    # --- 🚀 KẾT THÚC SỬA LỖI V115 🚀 ---

                    # --- Nút Xóa (Logic cũ) ---
                    async def on_delete_click(
                        doc_id=doc_id, 
                        path=full_path, 
                        card_to_hide=card, # Ẩn card này
                        name=goc_name,
                        s_name=saved_name 
                    ):
                        if doc_id:
                            await _delete_file_by_id_in_vectorstore(vectorstore, doc_id)
                        
                        correct_path_to_delete = None
                        if s_name:
                             correct_path_to_delete = os.path.join(PUBLIC_FILES_DIR, s_name)
                        
                        path_to_delete = correct_path_to_delete or path

                        if path_to_delete:
                            try:
                                await asyncio.to_thread(os.remove, path_to_delete)
                            except Exception:
                                pass
                        
                        card_to_hide.visible = False # Ẩn card
                        ui.notify(f"🗑️ Đã xóa file: {name}", type="positive")

                    ui.button(
                        "🗑️ Xóa", 
                        on_click=on_delete_click, 
                        color='negative'
                    ).props('flat dense')
            
    except Exception as e:
        print(f"❌ Lỗi _display_file_item_in_ui: {e}")
        with message_container:
            # (Không lồng ui.chat_message)
            ui.label(f"Lỗi render file: {e}").classes('text-red-500')

def _load_and_process_document(
    vectorstore,
    src_path: str,
    original_name: str,
    mime_type: str,
    user_note: str,
    fact_key: str = "general",
    fact_label: str = "General",
) -> tuple[int, str]:
    """
    (PORT TỪ CODEOLD – V94)
    1. Trích text nội dung file (excel / pdf / word / text).
    2. Chunk bằng _get_text_splitter().
    3. Lưu các chunk vào VectorStore (entry_type='file_chunk').
    4. Ghi thêm 1 record master [FILE] bằng _save_file_and_note().
    """
    simple_file_type = _get_simple_file_type(mime_type, src_path)
    metadata_note = f"Trích từ tài liệu: {original_name} | Ghi chú của người dùng: {user_note}"
    text_content = ""

    current_timestamp_iso = datetime.now(VN_TZ).isoformat()

    try:
        # 1. Đọc nội dung
        if "excel" in mime_type or src_path.endswith((".xlsx", ".xls")):
            df_dict = pd.read_excel(src_path, sheet_name=None)
            all_text = []
            for sheet_name, df in df_dict.items():
                md_table = df.to_markdown(index=False)
                all_text.append(f"--- Sheet: {sheet_name} ---\n{md_table}")
            text_content = "\n\n".join(all_text)
        elif "pdf" in mime_type or src_path.endswith(".pdf"):
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
            # FILE KHÔNG HỖ TRỢ → lưu 1 record master và thoát
            original_content_str = f"[FILE_UNSUPPORTED] path={src_path} | name={original_name} | note={user_note}"
            vector_text_str = f"{fact_label} | {original_name} | {user_note} | File không hỗ trợ"
            metadata = {
                "fact_key": fact_key,
                "fact_label": fact_label,
                "file_type": simple_file_type,
                "original_content": original_content_str,
                "entry_type": "file_master",
                "timestamp": current_timestamp_iso,
            }
            vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
            _save_file_and_note(
                vectorstore,
                src_path,
                original_name,
                user_note,
                fact_key,
                fact_label,
                simple_file_type,
            )
            return 0, original_name

        if not (text_content or "").strip():
            raise ValueError("File rỗng hoặc không thể trích xuất nội dung.")

        # 2. Chunk text
        splitter = _get_text_splitter()
        chunks = splitter.split_text(text_content)
        chunks_with_metadata = [
            f"{metadata_note}\n\n[NỘI DUNG CHUNK]:\n{chunk}" for chunk in chunks
        ]

        # 3. Lưu chunks
        chunk_metadatas = [
            {
                "file_type": simple_file_type,
                "fact_label": fact_label,
                "fact_key": fact_key,
                "entry_type": "file_chunk",
                "timestamp": current_timestamp_iso,
            }
            for _ in chunks_with_metadata
        ]

        vectorstore.add_texts(texts=chunks_with_metadata, metadatas=chunk_metadatas)

        # 4. Lưu bản ghi master [FILE]
        _save_file_and_note(
            vectorstore,
            src_path,
            original_name,
            user_note,
            fact_key,
            fact_label,
            simple_file_type,
        )

        return len(chunks_with_metadata), original_name

    except Exception as e:
        print(f"[ERROR] _load_and_process_document failed: {e}")

        original_content_str = (
            f"[ERROR_PROCESSING_FILE] name={original_name} | "
            f"note={user_note} | error={e}"
        )
        vector_text_str = (
            f"{fact_label} | {original_name} | {user_note} | Lỗi xử lý file"
        )
        metadata = {
            "fact_key": fact_key,
            "fact_label": fact_label,
            "file_type": simple_file_type,
            "original_content": original_content_str,
            "entry_type": "file_master",
            "timestamp": current_timestamp_iso,
        }
        vectorstore.add_texts(texts=[vector_text_str], metadatas=[metadata])
        raise

# ================== DANH SÁCH FILE/ẢNH (PORT TỪ CODEOLD) ==================

def list_active_files(vectorstore) -> list[dict]:
    """
    Lấy toàn bộ FILE/ẢNH (file_type != 'text', entry_type = file_master)
    và trả về list dict đã parse path / name / note, sort theo timestamp mới → cũ.
    """
    try:
        raw = vectorstore._collection.get(
            where={"file_type": {"$ne": "text"}},
            include=["documents", "metadatas"],
        )
        ids = raw.get("ids", []) or []
        docs = raw.get("documents", []) or []
        metadatas = raw.get("metadatas", []) or []

        if not ids:
            return []

        sorted_results = _helper_sort_results_by_timestamp(ids, docs, metadatas)


        files: list[dict] = []
        for doc_id, content, metadata in sorted_results:
            meta = metadata or {}
            original_content_str = meta.get("original_content") or content or ""
            file_type = meta.get("file_type", "file")

            # Chỉ lấy [FILE] hoặc [IMAGE]
            if not original_content_str.startswith(("[FILE]", "[IMAGE]")):
                continue

            path_part = ""
            name_part = ""
            note_part = ""

            try:
                segments = [seg.strip() for seg in original_content_str.split("|")]
                for seg in segments:
                    if seg.startswith("path="):
                        path_part = seg.replace("path=", "", 1).strip()
                    elif seg.startswith("name="):
                        name_part = seg.replace("name=", "", 1).strip()
                    elif seg.startswith("note="):
                        note_part = seg.replace("note=", "", 1).strip()
            except Exception:
                pass

            # Lấy tên file đã lưu (tên file trong thư mục /public/files)
            saved_name = None
            if path_part:
                try:
                    saved_name = os.path.basename(path_part)
                except Exception:
                    saved_name = None

            files.append(
                {
                    "id": doc_id,
                    "path": path_part,
                    "original_name": name_part,
                    "note": note_part,
                    "file_type": file_type,
                    "entry_type": meta.get("entry_type", ""),
                    "timestamp": meta.get("timestamp"),
                    "saved_name": saved_name,
                }
            )

        return files
    except Exception as e:
        print(f"[RAG/NiceGUI] Lỗi list_active_files: {e}")
        return []

def _find_files_by_name_db(vectorstore, query: str) -> list[dict]:
    """
    (SỬA LỖI: Chỉ tìm trong TÊN FILE, bỏ qua GHI CHÚ)
    Tìm file theo tên (accent-insensitive, không phân biệt hoa thường).
    Dùng logic 'set.issubset' (tất cả các từ phải khớp) thay vì 'in' (chuỗi con).
    """
    all_files = list_active_files(vectorstore)
    if not all_files:
        return []

    # 1. Chuẩn bị TỪ KHÓA (Query)
    # Tách query thành các từ riêng lẻ, ví dụ: "file 2023" -> {"file", "2023"}
    q_words_norm = set(unidecode.unidecode((query or "").strip().lower()).split())
    if not q_words_norm:
        return [] # Không có từ khóa để tìm

    results = []

    for item in all_files:
        # 2. Chuẩn bị NỘI DUNG TÊN FILE
        # CHỈ lấy tên file (original_name)
        name_str = (item.get("original_name") or "").strip()
        
        # Tách tên file thành các từ
        # Ví dụ: "luu_file_ds_2024.xlsx" -> {"luu", "file", "ds", "2024", "xlsx"}
        name_words_norm = set(unidecode.unidecode(name_str).lower().split())

        # (BỎ QUA GHI CHÚ)
        # note_norm = unidecode.unidecode((item.get("note") or "").strip().lower())

        # 3. So sánh
        # (Kiểm tra xem TẤT CẢ các từ khóa có nằm trong TÊN FILE không)
        if q_words_norm.issubset(name_words_norm):
            results.append(item)

    return results
# ================== HELPER XÓA FILE TRONG VECTORSTORE ==================

async def _delete_file_by_id_in_vectorstore(vectorstore, doc_id: str):
    """Xóa 1 record file_master khỏi Chroma theo id."""
    def _delete_sync():
        try:
            vectorstore._collection.delete(ids=[doc_id])
            print(f"[RAG/NiceGUI] Đã xóa file id={doc_id} khỏi Chroma.")
        except Exception as e:
            print(f"[RAG/NiceGUI] Lỗi xóa file id={doc_id}: {e}")

    await asyncio.to_thread(_delete_sync)

def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Text splitter giống code cũ (V97)."""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )


def _ensure_llm_and_vectorstore(user_id_str: str):
    """Đảm bảo đã có LLM & Vectorstore cho user trong cache."""
    llm = LLM_CACHE.get(user_id_str)
    vectorstore = VECTORSTORE_CACHE.get(user_id_str)
    retriever = RETRIEVER_CACHE.get(user_id_str)

    if llm is None:
        llm = get_user_llm()
        LLM_CACHE[user_id_str] = llm
        print(f"[chat_logic] Khởi tạo LLM cho {user_id_str}")

    if vectorstore is None or retriever is None:
        vectorstore, retriever = get_user_vectorstore_retriever(user_id_str)
        VECTORSTORE_CACHE[user_id_str] = vectorstore
        RETRIEVER_CACHE[user_id_str] = retriever
        print(f"[chat_logic] Khởi tạo Vectorstore cho {user_id_str}")

    return llm, vectorstore, retriever


# ================= LƯU GHI CHÚ (GIỮ NGUYÊN TÊN HÀM) =================

async def luu_thong_tin(noi_dung: str) -> str:
    """
    (Port từ codeold - logic V97)
    1. Bỏ tóm tắt, lưu NỘI DUNG GỐC sau khi chia chunk.
    2. Dùng GPT V88 để lấy (fact_key, fact_label, core_query_term).
    3. Ghi vào VectorStore với metadata (fact_key, fact_label, file_type='text', timestamp).
    4. Cập nhật fact_dict cache.
    """
    cu = current_user()
    if not cu:
        return "❌ Lỗi: Chưa đăng nhập, không biết user để lưu."

    user_id_str = cu.get("email") or cu.get("id") or "unknown"

    # Đảm bảo có LLM & Vectorstore trong cache
    llm, vectorstore, _ = _ensure_llm_and_vectorstore(user_id_str)

    try:
        original_text = (noi_dung or "").strip()
        if not original_text:
            return "⚠️ Không có nội dung để lưu."

        # --- Bước A: Gọi V88 để phân loại fact ---
        fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)

        # Để an toàn, nếu text quá dài, chỉ dùng 300 ký tự đầu cho V88
        text_for_v88 = original_text
        if len(text_for_v88) > 300:
            text_for_v88 = original_text[:300] + "..."
            print("[luu_thong_tin] Text dài, chỉ dùng 300 ký tự đầu cho V88.")

        # call_llm_to_classify là async → phải await trực tiếp
        fact_key, fact_label, core_query_term = await call_llm_to_classify(
            llm, text_for_v88, fact_dict
        )

        if not fact_key:
            fact_key = "general"
        if not fact_label:
            fact_label = "General"

        print(
            f"[luu_thong_tin] -> fact_key='{fact_key}', "
            f"fact_label='{fact_label}', core_query_term='{core_query_term}'"
        )

        # --- Bước B: Chia nhỏ NỘI DUNG GỐC bằng text_splitter ---
        splitter = _get_text_splitter()
        chunks = splitter.split_text(original_text)
        if not chunks:
            return "⚠️ Văn bản rỗng sau khi chia nhỏ, không lưu gì cả."
        print(
            f"[luu_thong_tin] Đã chia NỘI DUNG GỐC thành {len(chunks)} chunks "
            f"để lưu vào VectorStore."
        )

        # --- Bước C: Ghi các CHUNK vào VectorStore với metadata ---
        current_timestamp_iso = datetime.now(VN_TZ).isoformat()
        metadata_base = {
            "fact_key": fact_key,
            "fact_label": fact_label,
            "file_type": "text",
            "timestamp": current_timestamp_iso,
        }
        metadatas_list = [metadata_base.copy() for _ in chunks]

        await asyncio.to_thread(
            vectorstore.add_texts,
            texts=chunks,
            metadatas=metadatas_list,
        )

        # --- Bước D: Cập nhật fact_dict cache ---
        if core_query_term and core_query_term.strip().lower() != "all":
            cache_key = core_query_term.strip().lower()
            fact_dict[cache_key] = {"key": fact_key, "label": fact_label}
            await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict)
            print(f"[luu_thong_tin] Cập nhật cache: '{cache_key}' -> '{fact_key}'")
        else:
            print(
                f"[luu_thong_tin] Bỏ qua cập nhật cache vì core_query_term='{core_query_term}'"
            )

        preview_text = chunks[0]
        if len(preview_text) > 100:
            preview_text = preview_text[:100] + "..."

        msg = (
            f"✅ ĐÃ LƯU ({len(chunks)} đoạn) với nhãn '{fact_label}'. "
            f"Nội dung mẫu: {preview_text}"
        )
        return msg

    except Exception as e:
        import traceback

        traceback.print_exc()
        return f"❌ LỖI LƯU (NiceGUI): {e}"


# ================== HELPER XÓA NOTE ==================

async def _delete_note_by_id_in_vectorstore(vectorstore, doc_id: str):
    """Xóa 1 note khỏi vectorstore theo id."""

    def _delete_sync():
        try:
            vectorstore._collection.delete(ids=[doc_id])
            print(f"[RAG/NiceGUI] Đã xóa note id={doc_id} khỏi Chroma.")
        except Exception as exc:
            print(f"[RAG/NiceGUI] Lỗi khi xóa note id={doc_id}: {exc}")

    await asyncio.to_thread(_delete_sync)

# ================== UI: XEM TẤT CẢ FILE/ẢNH ==================


async def xoa_file_da_luu_theo_tu_khoa(
    tu_khoa: str, message_container: ui.column
) -> str:
    """
    Xóa file theo từ khóa (tên hoặc ghi chú).
    - Nếu 0 kết quả: báo không tìm thấy.
    - Nếu 1 kết quả: xóa luôn (VectorStore + file vật lý nếu có).
    - Nếu >1: liệt kê để user gõ lại chính xác hơn.
    """
    cu = current_user()
    if not cu:
        return "❌ Lỗi: Chưa đăng nhập, không biết user để xóa file."

    user_id_str = cu.get("email") or cu.get("id") or "unknown"
    _, vectorstore, _ = _ensure_llm_and_vectorstore(user_id_str)

    matches = await asyncio.to_thread(_find_files_by_name_db, vectorstore, tu_khoa)

    if not matches:
        msg = f"⚠️ Không tìm thấy file nào khớp với '{tu_khoa}'."
        with message_container:
            ui.chat_message(text=msg, name="Bot")
        return msg

    # Nếu nhiều hơn 1, chỉ liệt kê và yêu cầu user cụ thể hơn
    if len(matches) > 1:
        with message_container:
            ui.chat_message(
                text=(
                    "⚠️ Có nhiều file khớp với từ khóa này, "
                    "vui lòng gõ cụ thể hơn tên file để xóa:\n"
                    + "\n".join(
                        f"- {m.get('original_name') or '(không tên)'}"
                        for m in matches
                    )
                ),
                name="Bot",
            )
        return "⚠️ Nhiều file khớp, yêu cầu user chỉ rõ hơn."

    # Chính xác 1 file → xóa
    target = matches[0]
    doc_id = target.get("id")
    path = target.get("path")
    name = target.get("original_name") or "(không tên)"

    if doc_id:
        await _delete_file_by_id_in_vectorstore(vectorstore, doc_id)

    if path:
        try:
            await asyncio.to_thread(os.remove, path)
            print(f"[RAG/NiceGUI] Đã xóa file vật lý: {path}")
        except FileNotFoundError:
            print(f"[RAG/NiceGUI] File vật lý không tồn tại: {path}")
        except Exception as e:
            print(f"[RAG/NiceGUI] Lỗi xóa file vật lý: {e}")

    msg = f"🗑️ ĐÃ XÓA FILE: {name}"
    with message_container:
        ui.chat_message(text=msg, name="Bot")

    return msg

# ================== HIỂN THỊ DANH SÁCH GHI CHÚ (TEXT) ==================
# chat_logic.py (THAY THẾ TOÀN BỘ HÀM NÀY - KHOẢNG DÒNG 654)

async def _display_rag_list_in_ui(
    vectorstore,
    where_clause: dict,
    title: str,
    message_container: ui.column,
) -> int:
    """
    (SỬA LỖI TÌM ẢNH)
    Hiển thị danh sách GHI CHÚ (TEXT) hoặc FILE/ẢNH (file_master) 
    tùy theo where_clause.
    """

    # --- 🚀 BẮT ĐẦU SỬA LỖI (FIX TÌM ẢNH) 🚀 ---
    
    # B1: Helper mới: Quyết định bộ lọc
    def _build_where_for_items(where_clause_inner: dict) -> dict:
        # 1. Kiểm tra xem filter bên ngoài đã có file_type chưa
        has_external_file_type_filter = False
        if where_clause_inner:
            if '"file_type"' in str(where_clause_inner):
                 has_external_file_type_filter = True
        
        text_filter = {"file_type": "text"}

        if has_external_file_type_filter:
            # Nếu đã có filter (ví dụ: file_type: image), DÙNG NÓ
            print(f"[_display_rag_list_in_ui] Dùng filter file_type bên ngoài: {where_clause_inner}")
            return where_clause_inner
        else:
            # Nếu không có, ép "text" (hành vi cũ)
            print(f"[_display_rag_list_in_ui] Ép filter file_type: 'text'")
            if where_clause_inner:
                return {"$and": [where_clause_inner, text_filter]}
            return text_filter

    # B2: Dùng helper mới
    where_for_get = _build_where_for_items(where_clause or {})

    # B3: Lấy full danh sách từ collection
    def _get_docs_sync():
        return vectorstore._collection.get(
            where=where_for_get,
            include=["documents", "metadatas"],
        )

    raw_data = await asyncio.to_thread(_get_docs_sync)
    ids = raw_data.get("ids", []) or []
    docs = raw_data.get("documents", []) or []
    metas = raw_data.get("metadatas", []) or []

    if not docs:
        with message_container:
            ui.markdown("📭 Bộ nhớ đang trống. Không tìm thấy mục nào khớp.")
        return 0

    # B4: Sắp xếp theo timestamp (mới nhất trước)
    sorted_results = _helper_sort_results_by_timestamp(ids, docs, metas)

    found_count = 0
    with message_container:
        ui.markdown(f"📝 **{title} (mới nhất lên đầu):**")

        # B5: (SỬA LỖI) Lặp và render (Text HOẶC File)
        for doc_id, content, metadata in sorted_results:
            
            file_type = (metadata or {}).get("file_type", "text")

            if file_type == "text":
                # --- NHÁNH 1: RENDER TEXT (LOGIC CŨ) ---
                if not content:
                    continue
                
                # Bỏ qua các loại ghi chú system
                if content.startswith(("[FILE]", "[IMAGE]", "[REMINDER_", 
                   "[ERROR_PROCESSING_FILE]", "[FILE_UNSUPPORTED]", 
                   "Trích từ tài liệu:", "FACT:")):
                    continue

                found_count += 1

                summary = (content.split("\n", 1)[0] or content).strip()
                if len(summary) > 200:
                    summary = summary[:200] + "..."

                row = ui.row().classes("w-full items-start gap-2")
                with row:
                    ui.icon("notes").classes("mt-1")
                    ui.markdown(
                        f"**Ghi chú {found_count}:** {summary}\n\n`ID: {doc_id}`"
                    ).classes("grow")

                    async def _on_delete_click(doc_id=doc_id, row=row):
                        await _delete_note_by_id_in_vectorstore(vectorstore, doc_id)
                        row.visible = False
                        ui.notify(f"Đã xóa ghi chú ID: {doc_id}", type="positive")

                    ui.button(
                        "🗑️ Xóa",
                        on_click=_on_delete_click,
                    ).props("flat color=negative")
            
            else:
                # --- NHÁNH 2: RENDER FILE/ẢNH (LOGIC MỚI) ---
                
                # Chỉ render bản ghi 'master' (không render chunk)
                entry_type = (metadata or {}).get("entry_type")
                if entry_type != "file_master":
                    continue
                    
                found_count += 1
                
                # Thêm doc_id vào metadata để helper sử dụng
                if metadata:
                     metadata['doc_id'] = doc_id
                
                # Dùng helper (đã có) để render file
                await _display_file_item_in_ui(
                    vectorstore,
                    metadata, 
                    message_container
                )

    # --- 🚀 KẾT THÚC SỬA LỖI (FIX TÌM ẢNH) 🚀 ---

    if found_count <= 0:
        with message_container:
            ui.markdown(
                "📭 Không tìm thấy mục nào (sau khi lọc)."
            )

    return found_count


# chat_logic.py

# ... (Giữ nguyên các import và hàm helper ở đầu file) ...
# (Đảm bảo _llm_batch_split_classify và _llm_split_notes đã được import từ rag_helpers)
from rag_helpers import (
    load_user_fact_dict,
    save_user_fact_dict,
    call_llm_to_classify,
    get_user_llm,
    get_user_vectorstore_retriever,
    _build_rag_filter_from_query,
    _helper_sort_results_by_timestamp,
    _llm_filter_for_selection,
    VN_TZ,
    _timestamp,
    _llm_batch_split_classify, # 👈 THÊM IMPORT
    _llm_split_notes,          # 👈 THÊM IMPORT
)
# ... (Giữ nguyên các hàm khác) ...


# ================== NHÁNH A: XỬ LÝ FILE/IMAGE (NiceGUI) ==================

# 🚀 THAY THẾ TOÀN BỘ HÀM NÀY BẰNG LOGIC V85 TỪ CODEOLD 🚀
async def handle_uploaded_files(
    cu: dict,
    user_text: str,
    elements: list,
    message_container: ui.column,
) -> str:
    """
    (SỬA LỖI THEO YÊU CẦU - KHÔI PHỤC LOGIC V85)
    Sử dụng logic 'Album Mode' và 'Smart Mode' từ codeold.py
    để tách ghi chú thành TÊN FILE RIÊNG LẺ.
    """
    if not elements:
        return "⚠️ Không có file/ảnh nào để xử lý."

    if not cu:
        err = "❌ Lỗi: Chưa đăng nhập, không biết user để lưu file."
        with message_container:
            ui.chat_message(text=err, name="Bot")
        return err

    user_id_str = cu.get("email") or cu.get("id") or "unknown"
    llm, vectorstore, _ = _ensure_llm_and_vectorstore(user_id_str)

    with message_container:
        loading_msg = ui.chat_message(
            text=f"⏳ Đang xử lý {len(elements)} file/ảnh...",
            name="Bot",
        )

    try:
        fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
        saved_files_summary_lines: list[str] = []
        num_files = len(elements)
        
        notes_for_files: List[str] = []
        keys_for_files: List[str] = []
        labels_for_files: List[str] = []
        clean_names_for_files: List[str] = [] # 👈 Quan trọng nhất
        
        # Lấy các key đã tồn tại để giúp LLM phân loại (giống V85)
        existing_keys = list(set(
            d.get('key', 'general') if isinstance(d, dict) else d
            for d in fact_dict.values()
        ))

        # --- BẮT ĐẦU LOGIC V85 ---
        
        # B1: Kiểm tra "Album Mode" (có "vào mục")
        album_match = re.match(r"^(.*?)\s+(vào mục|vào)\s+(.*?)\s*$", user_text, re.IGNORECASE | re.DOTALL)

        if album_match:
            # --- NHÁNH A.1: CHẾ ĐỘ ALBUM (V85) ---
            print(f"✅ [Album Mode] Phát hiện 'vào mục'. Đang gọi LLM phân tích: '{user_text}'")
            
            # 1a. Dùng LLM phân tích câu lệnh (giống V78)
            album_prompt = f"""
Bạn là một trợ lý phân tích. Câu lệnh của người dùng có 2 phần: (A) Tên/ghi chú của file, và (B) Danh mục muốn lưu vào.
Câu lệnh: "{user_text}"
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
            
            forced_key = "general"
            forced_label = "General"
            
            if "|" in raw_output:
                parts = raw_output.split("|")
                if len(parts) >= 3:
                    forced_key = parts[1].strip() or forced_key
                    forced_label = parts[2].strip() or forced_label

            print(f"✅ [Album Mode] LLM đã phân tích: Key='{forced_key}' | Label='{forced_label}'")
            
            # 1b. Gán Key/Label này cho TẤT CẢ file
            keys_for_files = [forced_key] * num_files
            labels_for_files = [forced_label] * num_files
            notes_for_files = [user_text] * num_files # Ghi chú vẫn là ghi chú gốc

            # 1c. Tách TÊN FILE (Phần quan trọng)
            note_part_to_split = album_match.group(1).strip() # (phần trước "vào mục")
            print(f"✅ [Album Mode] (V85) Đang gọi _llm_split_notes để tách tên từ: '{note_part_to_split}'")
            clean_names_for_files = await _llm_split_notes(llm, note_part_to_split, num_files)
            
            if len(clean_names_for_files) != num_files:
                clean_names_for_files = [f"File {i+1}" for i in range(num_files)]
                print(f"⚠️ [Album Mode] (V85) Tách tên thất bại, dùng tên chung.")

        else:
            # --- NHÁNH A.2: CHẾ ĐỘ SMART (V85) ---
            print(f"✅ [Smart Mode] (V85) Không phát hiện 'vào mục'. Đang gọi Batch Split...")
            batch_results = []
            if user_text:
                batch_results = await _llm_batch_split_classify(llm, user_text, num_files)
            
            if batch_results and len(batch_results) == num_files:
                print("✅ [Smart Mode] (V85) Batch Split thành công.")
                for res in batch_results:
                    clean_names_for_files.append(res["name"])
                    keys_for_files.append(res["key"])
                    labels_for_files.append(res["label"])
                    notes_for_files.append(user_text) # Ghi chú vẫn là ghi chú gốc
                    # Cập nhật cache
                    fact_dict[res["name"].strip().lower()] = {"key": res["key"], "label": res["label"]}
            else:
                # --- NHÁNH A.3: FALLBACK (N+1 CALLS) ---
                print("⚠️ [Smart Mode] (V85) Batch Split thất bại. Quay về logic Fallback (N+1 call).")
                
                # 1. Tách tên (hoặc dùng tên gốc)
                if user_text:
                    # Tách tên bằng LLM
                    clean_names_for_files = await _llm_split_notes(llm, user_text, num_files)
                else:
                    # Dùng tên file gốc
                    clean_names_for_files = [
                        os.path.splitext(el.get("name") if isinstance(el, dict) else el.name)[0].replace("-", " ").replace("_", " ")
                        for el in elements
                    ]
                
                notes_for_files = [user_text or name for name in clean_names_for_files]
                
                # 2. Phân loại N lần
                for temp_note in clean_names_for_files: # Dùng tên đã tách để phân loại
                    temp_note_clean = temp_note.strip().lower()
                    cached_data = fact_dict.get(temp_note_clean)
                    fact_key, fact_label = None, None
                    
                    if isinstance(cached_data, dict):
                        fact_key = cached_data.get("key"); fact_label = cached_data.get("label")
                    elif isinstance(cached_data, str):
                        fact_key = cached_data
                        
                    if not fact_key or not fact_label:
                        fact_key, fact_label, _ = await call_llm_to_classify(llm, temp_note, fact_dict) 
                        fact_dict[temp_note_clean] = {"key": fact_key, "label": fact_label} 
                        
                    keys_for_files.append(fact_key)
                    labels_for_files.append(fact_label)

        # --- KẾT THÚC LOGIC V85 ---

        # B5: Quyết định có CHUNK file hay không (Logic V97 - Giữ nguyên)
        user_intent_text = (user_text or "").lower()
        keywords_for_chunking = [
            "đọc nội dung", "doc noi dung", "tóm tắt", "tom tat", "summary",
            "phân tích", "phan tich", "doc file", "đọc file",
        ]
        should_chunk_file = any(k in user_intent_text for k in keywords_for_chunking)

        # B6: Xử lý từng file (ĐÃ SỬA)
        # (Zip 5 danh sách lại)
        zipped_data = zip(
            elements, 
            notes_for_files, 
            keys_for_files, 
            labels_for_files, 
            clean_names_for_files
        )
        
        for (el, user_note_for_file, fact_key_for_file, fact_label_for_file, clean_name_for_file) in zipped_data:
            
            # 1. Lấy thông tin file (giống code cũ)
            if isinstance(el, dict):
                src_path = el.get("path") or el.get("stored_path")
                original_name_from_upload = el.get("name") or el.get("original_name") or "File"
                mime_type = el.get("mime") or el.get("content_type") or ""
            else:
                src_path = getattr(el, "path", None)
                original_name_from_upload = getattr(el, "name", None) or "File"
                mime_type = getattr(el, "mime", None) or getattr(el, "content_type", "") or ""

            if not src_path:
                saved_files_summary_lines.append(f"- ❌ File: không có đường dẫn (bỏ qua).")
                continue

            # 2. Tên file cuối cùng (QUAN TRỌNG)
            # (Dùng tên đã được LLM tách (clean_name_for_file),
            #  nếu không có thì mới dùng tên gốc (original_name_from_upload))
            final_name_to_save = clean_name_for_file or original_name_from_upload
            # (Thêm đuôi file .jpg, .xlsx... nếu LLM tách tên bị mất)
            _, ext = os.path.splitext(original_name_from_upload)
            if ext and not final_name_to_save.endswith(ext):
                final_name_to_save += ext

            simple_type = _get_simple_file_type(mime_type, src_path)

            try:
                if simple_type == "image":
                    _, name = await asyncio.to_thread(
                        _save_file_and_note,
                        vectorstore,
                        src_path,
                        final_name_to_save,      # 👈 SỬA Ở ĐÂY
                        user_note_for_file,      # Ghi chú (chung)
                        fact_key_for_file,
                        fact_label_for_file,
                        "image",
                    )
                    saved_files_summary_lines.append(
                        f"- 🖼 Ảnh: {name} (Label: {fact_label_for_file})"
                    )

                elif should_chunk_file and simple_type != "text":
                    chunks, name = await asyncio.to_thread(
                        _load_and_process_document,
                        vectorstore,
                        src_path,
                        final_name_to_save,      # 👈 SỬA Ở ĐÂY
                        mime_type,
                        user_note_for_file,
                        fact_key_for_file,
                        fact_label_for_file,
                    )
                    saved_files_summary_lines.append(
                        f"- 📄 File: {name} → đã đọc & lưu {chunks} đoạn (Label: {fact_label_for_file})"
                    )

                else:
                    _, name = await asyncio.to_thread(
                        _save_file_and_note,
                        vectorstore,
                        src_path,
                        final_name_to_save,      # 👈 SỬA Ở ĐÂY
                        user_note_for_file,
                        fact_key_for_file,
                        fact_label_for_file,
                        simple_type,
                    )
                    saved_files_summary_lines.append(
                        f"- 📎 File: {name} (Label: {fact_label_for_file}, không đọc nội dung)"
                    )

            except Exception as e:
                saved_files_summary_lines.append(
                    f"- ❌ File {final_name_to_save}: lỗi khi xử lý ({e})"
                )

        # B7: LƯU CACHE (1 LẦN)
        await asyncio.to_thread(save_user_fact_dict, user_id_str, fact_dict) 

        # B8: Xóa bubble loading
        try:
            loading_msg.delete() # Sửa: Dùng .delete()
        except Exception:
            pass

        # B9: Hiển thị tóm tắt trong UI
        summary_text = "✅ ĐÃ LƯU FILE/ẢNH:\n" + "\n".join(saved_files_summary_lines)
        with message_container:
            ui.chat_message(text=summary_text, name="Bot")

        return summary_text

    except Exception as e:
        # Xử lý lỗi chung
        import traceback
        traceback.print_exc()
        try:
            loading_msg.delete() # Sửa: Dùng .delete()
        except Exception:
            pass
        err_msg = f"❌ Lỗi nghiêm trọng khi xử lý file: {e}"
        with message_container:
            ui.chat_message(text=err_msg, name="Bot")
        return err_msg
    
# chat_logic.py

# (Đảm bảo các hàm helper bên trên, như _display_rag_list_in_ui, vẫn giữ nguyên)

async def get_rag_response(
    cu: dict,
    query: str,
    message_container: ui.column,
) -> str:
    """
    Logic RAG V103 (Hybrid):
    - Fix 1: (Q&A) KHÔNG lọc theo fact_key khi truy vấn CỤ THỂ (SPECIFIC)
             (quay lại logic V90 của codeold.py).
    - Fix 2: (FILE) VÔ HIỆU HÓA bộ lọc LLM V91 (filter_for_selection)
             để tránh lỗi lọc nhầm (hiển thị 0 file).
    """
    try:
        # --- BƯỚC 0: SETUP ---
        user_id_str = cu.get("email") or cu.get("id") or "unknown"
        llm, vectorstore, retriever = _ensure_llm_and_vectorstore(user_id_str)

        print(f"[RAG/NiceGUI] (V103) Đang RAG với query: '{query}'")
        q_low_norm = unidecode.unidecode(query.lower())

        # --- (Giữ nguyên các QUY TẮC ĐẶC BIỆT 1-5) ---
        # (Ví dụ: 'lưu lại...', 'xem tất cả ghi chú', 'xem tất cả file', 'xóa file...')
        # (Tua qua 100 dòng)
        # --- QUY TẮC ĐẶC BIỆT 1: 'lưu lại ...' ---
        if "luu lai" in q_low_norm:
            words = query.strip().split()
            note_text = query.strip()
            if len(words) >= 3:
                w0 = unidecode.unidecode(words[0].lower())
                w1 = unidecode.unidecode(words[1].lower())
                if w0 == "luu" and w1 == "lai":
                    note_text = " ".join(words[2:]).strip() or note_text

            save_msg = await luu_thong_tin(note_text)
            display_msg = f"Mình đã lưu lại: {note_text}"
            with message_container:
                ui.chat_message(text=display_msg, name="Bot", sent=False)
            return save_msg or display_msg

        # --- QUY TẮC ĐẶC BIỆT 2: 'xem tất cả ghi chú' ---
        if (
            ("ghi chu" in q_low_norm or "note" in q_low_norm)
            and (
                "tat ca" in q_low_norm
                or "tất cả" in q_low_norm
                or "toan bo" in q_low_norm
                or "toàn bộ" in q_low_norm
                or "ds" in q_low_norm
                or "danh sach" in q_low_norm
            )
            and ("file" not in q_low_norm)
            and ("anh" not in q_low_norm)
            and ("hinh" not in q_low_norm)
            and ("danh muc" not in q_low_norm)
        ):
            print("[RAG/NiceGUI] Match rule 'xem_bo_nho' -> hiển thị TOÀN BỘ ghi chú (TEXT).")
            found = await _display_rag_list_in_ui(
                vectorstore=vectorstore,
                where_clause={},  # Không lọc
                title="Tất cả ghi chú",
                message_container=message_container,
            )
            if found <= 0:
                return "ℹ️ Bộ nhớ chưa có ghi chú văn bản nào."
            return f"✅ Đã hiển thị {found} ghi chú trong bộ nhớ."

        # --- QUY TẮC ĐẶC BIỆT 3: 'xem danh mục' ---
        if "danh muc" in q_low_norm and (
            "xem" in q_low_norm or "tat ca" in q_low_norm or "tất cả" in q_low_norm
        ):
            return "ℹ️ Tính năng 'xem danh mục' (dưới dạng nút bấm) đang được cập nhật."
        
        # --- QUY TẮC ĐẶC BIỆT 4: 'xem tất cả file' / 'xem ds file' ---
        if (
            ("file" in q_low_norm or "anh" in q_low_norm or "hinh" in q_low_norm or "tep" in q_low_norm)
            and (
                "tat ca" in q_low_norm
                or "tất cả" in q_low_norm
                or "toan bo" in q_low_norm
                or "toàn bộ" in q_low_norm
            )
        ):
            print(
                "[RAG/NiceGUI] Match rule 'xem_danh_sach_file' -> hiển thị TOÀN BỘ file/ảnh."
            )
            return await xem_tat_ca_file_da_luu(message_container)

        # --- QUY TẮC ĐẶC BIỆT 5: 'xóa file ...' ---
        if (
            ("xoa" in q_low_norm or "huy" in q_low_norm or "huy bo" in q_low_norm)
            and ("file" in q_low_norm or "anh" in q_low_norm or "hinh" in q_low_norm or "tep" in q_low_norm)
        ):
            print("[RAG/NiceGUI] Match rule 'xoa_file' -> tìm và xóa file.")
            tu_khoa = query.lower()
            tu_khoa = (
                tu_khoa.replace("xóa file", "")
                .replace("xoa file", "")
                .replace("hủy file", "")
                .replace("huy file", "")
                .strip()
            )
            return await xoa_file_da_luu_theo_tu_khoa(tu_khoa, message_container)
        
        # --- (Kết thúc Quy tắc đặc biệt) ---

        
        # --- BƯỚC 1: TÍNH BỘ LỌC METADATA (V89) ---
        file_type_filter = _build_rag_filter_from_query(query)

        # --- BƯỚC 2: GỌI GPT V88 ĐỂ PHÂN LOẠI FACT ---
        fact_dict = await asyncio.to_thread(load_user_fact_dict, user_id_str)
        fact_key, fact_label, core_search_query = await call_llm_to_classify(
            llm, query, fact_dict
        )

        # --- BƯỚC 3: XÂY DỰNG BỘ LỌC (V103) ---
        where_clause: Dict[str, Any] = {}
        final_filter_list = []
        is_general_query = (
            not core_search_query.strip()
            or core_search_query.strip().upper() == "ALL"
        )
        
        if file_type_filter:
            final_filter_list.append(file_type_filter)
        
        # --- 🚀 BẮT ĐẦU SỬA LỖI V114 (REVERT LẠI LOGIC V103/V90) 🚀 ---
        # Logic V103/V90:
        # - Chỉ lọc fact_key nếu đây là truy vấn CHUNG (is_general_query)
        # - KHÔNG lọc fact_key nếu đây là truy vấn CỤ THỂ (Q&A / tìm file cụ thể)
        
        if is_general_query and fact_key and fact_key != "general":
            # Case A: "cho anh trong cong viec" (General query)
            # V88 sẽ trả về core_search_query='ALL', fact_key='cong_viec'
            # -> is_general_query = True -> Áp dụng filter
            print(f"[RAG/NiceGUI] (V114) BƯỚC 3 (General): ĐANG ÉP lọc theo fact_key='{fact_key}'")
            final_filter_list.append({"fact_key": fact_key})
        else:
            # Case B: "cho toi user pass" (Specific query)
            # Case C: "cho toi hinh may khoan" (Specific query)
            # V88 sẽ trả về core_search_query='hình máy khoan', fact_key='may_khoan'
            # -> is_general_query = False -> Bỏ qua filter fact_key
            print(f"[RAG/NiceGUI] (V114) BƯỚC 3 (Specific/General): Bỏ qua lọc fact_key.")
        
        # --- 🚀 KẾT THÚC SỬA LỖI V114 🚀 ---

        if len(final_filter_list) > 1:
            where_clause = {"$and": final_filter_list}
        elif len(final_filter_list) == 1:
            where_clause = final_filter_list[0]
        final_where_for_chroma = where_clause or None # BỘ LỌC CHÍNH

        # ------------------------------------------------------------------
        # BƯỚC 5: THỰC THI (RẼ NHÁNH GENERAL / SPECIFIC)
        # ------------------------------------------------------------------

        if is_general_query:
            # =============== 5a: GENERAL -> LIST MODE =====================
            print("[RAG/NiceGUI] (V103) (GENERAL) Gọi _display_rag_list_in_ui...")
            label = fact_label or fact_key or "Tất cả"
            if label.lower() == "general":
                label = "Tất cả"
            title = f"📂 Danh sách cho: {label}"
            
            # (Hàm _display_rag_list_in_ui (V103) đã được sửa để render cả file/ảnh)
            found = await _display_rag_list_in_ui(
                vectorstore=vectorstore,
                where_clause=final_where_for_chroma, # 👈 Sửa: Dùng final_where_for_chroma
                title=title,
                message_container=message_container,
            )
            if found <= 0:
                return f"ℹ️ Không tìm thấy mục nào cho '{label}' (Filter: {final_where_for_chroma})."
            return f"✅ Đã hiển thị {found} mục cho danh mục '{label}'."

        else:
            # =============== 5b: SPECIFIC -> Q&A / FILE DISPLAY MODE ========================
            print("[RAG/NiceGUI] (V103) (SPECIFIC) Truy vấn cụ thể...")
            
            if bool(file_type_filter):
                # --- NHÁNH 5b.1: TÌM FILE CỤ THỂ (FIX LỖI 2) ---
                print("[RAG/NiceGUI] (V108) (SPECIFIC) -> Rẽ nhánh 5b.2: HỎI ĐÁP (Q&A)")
                
                search_vector_query = query.strip()
                print(f"[RAG/NiceGUI] (V108) search_vector_query='{search_vector_query}'")

                # --- 🚀 BẮT ĐẦU SỬA LỖI V108 (KHÔI PHỤC) 🚀 ---
                # (Bộ lọc final_where_for_chroma đã được BƯỚC 3 (V108)
                #  tính toán chính xác rồi. Chúng ta chỉ cần dùng nó.)
                print(f"[RAG/NiceGUI] (V108) Q&A: Sử dụng bộ lọc từ Bước 3: {final_where_for_chroma}")
                # --- 🚀 KẾT THÚC SỬA LỖI V108 🚀 ---

                final_where_doc_for_chroma = None
                query_vector = await asyncio.to_thread(
                    embeddings.embed_query, search_vector_query
                )
                results = await asyncio.to_thread(
                    vectorstore._collection.query,
                    query_embeddings=[query_vector],
                    n_results=20,
                    where=final_where_for_chroma, # 👈 SỬA: Dùng final_where_for_chroma
                    where_document=final_where_doc_for_chroma,
                    include=["documents", "metadatas"],
                )

                docs_goc_content = results.get("documents", [[]])[0]
                docs_goc_metadatas = results.get("metadatas", [[]])[0]
                ids_goc = results.get("ids", [[]])[0]

                if not docs_goc_content:
                     return f"ℹ️ Không tìm thấy file/ảnh nào (sau khi query) khớp với '{query}' (Filter: {final_where_for_chroma})."

                # B2. Chuẩn bị ứng viên
                candidates_to_display = []
                for doc_id, _, metadata in zip(ids_goc, docs_goc_content, docs_goc_metadatas):
                    if not metadata: continue
                    file_type = metadata.get("file_type", "text")
                    if file_type == "text": continue
                    content = metadata.get("original_content")
                    if not content: continue
                    
                    # Chỉ lấy bản ghi 'master'
                    if metadata.get("entry_type") != "file_master":
                        continue
                        
                    try:
                        metadata['doc_id'] = doc_id
                        candidates_to_display.append({
                            "id": doc_id, "metadata": metadata
                        })
                    except Exception:
                        continue
                
                # chat_logic.py (Bên trong hàm get_rag_response, nhánh 5b.1)

                # ... (code lấy candidates_to_display giữ nguyên) ...
                
                if not candidates_to_display:
                    return f"ℹ️ Đã tìm thấy {len(docs_goc_content)} mục (vector) nhưng không thể trích xuất metadata (Tên/Ghi chú) để lọc."

                # --- 🚀 BẮT ĐẦU SỬA LỖI 2 (BẬT LẠI V91/V104) 🚀 ---
                
                # B2. Chuẩn bị ứng viên cho LLM Filter (V104)
                candidates_for_llm_filter = []
                for item in candidates_to_display:
                    metadata = item.get("metadata", {})
                    content = metadata.get("original_content", "")
                    doc_id = item.get("id")
                    try:
                        name_match = re.search(r"name=([^|]+)", content)
                        note_match = re.search(r"note=([^|]+)", content)
                        goc_name = name_match.group(1).strip() if name_match else "N/A"
                        goc_note = note_match.group(1).strip() if note_match else "(không ghi chú)"
                        
                        candidates_for_llm_filter.append({
                            "id": doc_id, "name": goc_name, "note": goc_note, "metadata": metadata
                        })
                    except Exception:
                        continue
                
                print(f"[RAG/NiceGUI] (V104) Đã có {len(candidates_for_llm_filter)} ứng viên. Đang gọi LLM Filter (V104)...")

                # (BẬT LẠI DÒNG NÀY)
                final_filtered_results = await asyncio.to_thread(
                    _llm_filter_for_selection,
                    llm, query, candidates_for_llm_filter
                )

                print(f"[RAG/NiceGUI] (V104) Hiển thị {len(final_filtered_results)} file (Đã qua LLM Filter V104).")
                with message_container:
                    ui.chat_message(text=f"**Kết quả lọc (V104) cho: {query}**", name='Bot', sent=False)

                if not final_filtered_results:
                    return f"ℹ️ Đã tìm thấy {len(candidates_for_llm_filter)} ứng viên, nhưng Bộ lọc LLM (V104) đã loại bỏ chúng (vì không khớp Tên/Ghi chú)."

                # B4. Hiển thị kết quả (Dùng item từ final_filtered_results)
                found_count = 0
                for item in final_filtered_results: # 👈 Sửa: lặp qua final_filtered_results
                    await _display_file_item_in_ui(
                        vectorstore,
                        item['metadata'], 
                        message_container
                    )
                    found_count += 1
                
                return f"✅ Đã lọc (bằng LLM V104) và hiển thị {found_count} mục khớp."
                # --- 🚀 KẾT THÚC SỬA LỖI 2 🚀 ---

            else:
                # --- NHÁNH 5b.2: HỎI-ĐÁP (Q&A) (FIX LỖI 1) ---
                # (Phần này giữ nguyên bản vá V103 của tôi)
                print("[RAG/NiceGUI] (V103) (SPECIFIC) -> Rẽ nhánh 5b.2: HỎI ĐÁP (Q&A)")
                
                search_vector_query = query.strip()
                print(f"[RAG/NiceGUI] (V103) search_vector_query='{search_vector_query}'")
                # (final_where_for_chroma LÚC NÀY SẼ LÀ NONE - Y HỆT V90)
                print(f"[RAG/NiceGUI] (V103) where_filter='{final_where_for_chroma}'")

                final_where_doc_for_chroma = None
                query_vector = await asyncio.to_thread(
                    embeddings.embed_query, search_vector_query
                )
                results = await asyncio.to_thread(
                    vectorstore._collection.query,
                    query_embeddings=[query_vector],
                    n_results=20,
                    where=final_where_for_chroma, # 👈 (SỬA LỖI 1)
                    where_document=final_where_doc_for_chroma,
                    include=["documents", "metadatas"],
                )
    
                docs_goc_content = results.get("documents", [[]])[0]
                docs_goc_metadatas = results.get("metadatas", [[]])[0]
                ids_goc = results.get("ids", [[]])[0]

                if not docs_goc_content:
                    # (Đây là logic fallback khi không tìm thấy gì trong CSDL)
                    with message_container:
                        ui.chat_message(
                            text=(
                                "❓ Không tìm thấy thông tin phù hợp trong bộ nhớ. "
                                "Mình sẽ trả lời theo kiến thức chung."
                            ),
                            name="Bot",
                            sent=False,
                        )
                    messages = [
                        {"role": "system", "content": "Bạn là trợ lý AI trả lời ngắn gọn, dễ hiểu bằng tiếng Việt."},
                        {"role": "user", "content": query},
                    ]
                    answer = await llm.ainvoke(messages)
                    answer_text = getattr(answer, "content", str(answer))
                    with message_container:
                        ui.chat_message(text=answer_text, name="Bot", sent=False)
                    return answer_text # Trả về câu trả lời chung

                # (Phần RAG Q&A V93 - giữ nguyên)
                final_results_to_display = _helper_sort_results_by_timestamp(
                    ids_goc, docs_goc_content, docs_goc_metadatas
                )
                context_chunks = []
                for _, content, metadata in final_results_to_display:
                    ts = None
                    if isinstance(metadata, dict):
                        ts = metadata.get("timestamp")
                    file_type = (metadata or {}).get("file_type", "text")
                    if file_type == "text":
                        if not content.startswith(("[FILE]", "[IMAGE]", "[REMINDER_", "[ERROR_PROCESSING_FILE]", "[FILE_UNSUPPORTED]", "Trích từ tài liệu:", "FACT:")):
                            ts_str = ts or "không rõ thời gian"
                            context_chunks.append(f"[{ts_str}] {content}")
                
                if not context_chunks:
                     return f"ℹ️ Đã tìm thấy {len(final_results_to_display)} mục liên quan, nhưng không có nội dung văn bản (TEXT) nào để trả lời."

                joined_context = "\n\n".join(context_chunks[:8]) 
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là trợ lý AI truy vấn trên bộ nhớ cá nhân (RAG). "
                            "Hãy dùng thông tin trong CONTEXT dưới đây để trả lời người dùng. "
                            "Nếu không chắc chắn, hãy nói rõ 'không chắc' chứ đừng bịa.\n\n"
                            f"CONTEXT:\n{joined_context}"
                        ),
                    },
                    {"role": "user", "content": query},
                ]
                answer = await llm.ainvoke(messages)
                answer_text = getattr(answer, "content", str(answer))
                with message_container:
                    ui.chat_message(text=answer_text, name="Bot", sent=False)
                return answer_text

    # Đây là khối except tổng của toàn bộ hàm
    except Exception as e:
        import traceback
        traceback.print_exc()
        err = f"⚠️ Lỗi trong get_rag_response: {e}"
        with message_container:
            ui.chat_message(text=err, name="Bot", sent=False)
        return err