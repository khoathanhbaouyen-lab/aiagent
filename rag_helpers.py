# rag_helpers.py
import os
import re
import json
import pytz
import unidecode
from datetime import datetime
from typing import List, Tuple, Optional, Union, Dict, Any
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
# Import embeddings đã được khởi tạo từ helpers.py
from helpers import embeddings, OPENAI_API_KEY

# --- CẤU HÌNH ĐƯỜNG DẪN (Lấy từ codeold.py) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Thư mục MỚI chứa TẤT CẢ dữ liệu riêng của người dùng
USER_DATA_ROOT = os.path.join(BASE_DIR, "user_data")
os.makedirs(USER_DATA_ROOT, exist_ok=True)

# 2. Các thư mục con (Vector)
USER_VECTOR_DB_ROOT = os.path.join(USER_DATA_ROOT, "vector_db")
os.makedirs(USER_VECTOR_DB_ROOT, exist_ok=True)

# 3. Thư mục Từ điển Fact
USER_FACT_DICTS_ROOT = os.path.join(USER_DATA_ROOT, "fact_dictionaries")
os.makedirs(USER_FACT_DICTS_ROOT, exist_ok=True)

# Timezone VN
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")


# --- HÀM HELPER CHUNG (Lấy từ codeold.py) ---

def _timestamp() -> str:
    """Lấy timestamp (dùng cho V94/V97)"""
    return datetime.now().strftime('%Y%m%d-%H%M%S')

def _sanitize_user_id_for_path(user_email: str) -> str:
    """Biến email thành tên thư mục an toàn."""
    # Thay @ và . bằng _
    safe_name = re.sub(r"[@\.]", "_", user_email)
    # Xóa các ký tự không an toàn còn lại
    return re.sub(r"[^a-zA-Z0-9_\-]", "", safe_name)


# --- 1. HÀM CHÍNH BẠN YÊU CẦU ---
# (Lấy từ codeold.py)

def get_user_vector_dir(user_id_str: str) -> str:
    """Lấy đường dẫn thư mục vector DB của user (và tạo nếu chưa có)."""
    safe_user_dir = _sanitize_user_id_for_path(user_id_str)
    user_dir = os.path.join(USER_VECTOR_DB_ROOT, safe_user_dir)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_vectorstore_retriever(user_id_str: str) -> Tuple[Chroma, Any]:
    """
    Khởi tạo Vectorstore và Retriever cho 1 user cụ thể.
    (Lấy từ codeold.py)
    """
    global embeddings
    if embeddings is None:
        raise ValueError("Lỗi: Embeddings chưa được khởi tạo (OPENAI_API_KEY có thể bị thiếu).")

    persist_directory = get_user_vector_dir(user_id_str)
    
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
        collection_name="memory"
    )
    # Lấy K=20 (theo logic V96)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 20})
    
    print(f"✅ VectorStore cho user '{user_id_str}' đã sẵn sàng tại {persist_directory} (mode=Similarity K=20)")
    return vectorstore, retriever


# --- 2. HÀM KHỞI TẠO LLM ---
# (Lấy từ codeold.py)

def get_user_llm() -> ChatOpenAI:
    """
    Khởi tạo LLM (logic) cho user.
    """
    return ChatOpenAI(
        model="gpt-4.1-mini", 
        temperature=0, 
        api_key=OPENAI_API_KEY
    )


# --- 3. CÁC HÀM RAG HELPER KHÁC (ĐỂ `index.py` VÀ `chat_logic.py` HOẠT ĐỘNG) ---

# --- Fact Map (Từ điển Fact) Helpers ---
# (Lấy từ codeold.py)

def get_user_fact_dict_path(user_id_str: str) -> str:
    """Lấy đường dẫn file JSON từ điển fact của user."""
    safe_name = _sanitize_user_id_for_path(user_id_str)
    # Sửa: Dùng USER_FACT_DICTS_ROOT thay vì get_user_vector_dir
    user_dir = os.path.join(USER_FACT_DICTS_ROOT, safe_name)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "fact_map.json")

def load_user_fact_dict(user_id_str: str) -> dict:
    """Tải từ điển fact của user từ file JSON. (Sửa lỗi V94)"""
    path = get_user_fact_dict_path(user_id_str)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi đọc fact dict {user_id_str}: {e}")
            try:
                bad_file_path = f"{path}.{_timestamp()}.corrupted"
                os.rename(path, bad_file_path)
                print(f"✅ Đã di dời file hỏng sang: {bad_file_path}")
            except Exception as e_rename:
                print(f"❌ Không thể di dời file hỏng: {e_rename}")
    return {}

def save_user_fact_dict(user_id_str: str, data: dict):
    """Lưu từ điển fact của user vào file JSON."""
    path = get_user_fact_dict_path(user_id_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi lưu fact dict {user_id_str}: {e}")

async def call_llm_to_classify(
    llm: ChatOpenAI, 
    question: str, 
    fact_map: dict
) -> Tuple[str, str, str]:
    """
    (SỬA LỖI V88 - Lấy từ codeold.py)
    """
    existing_facts_str = "Context (Fact) hiện tại:\n(Không có)"
    try:
        if fact_map and isinstance(fact_map, dict):
            existing_facts_list = []
            seen_keys = set()
            for data in fact_map.values():
                if isinstance(data, dict):
                    key = data.get("key")
                    label = data.get("label")
                    if key and key not in seen_keys:
                        existing_facts_list.append(f"- Key: {key} (Label: {label})")
                        seen_keys.add(key)
                elif isinstance(data, str) and data not in seen_keys:
                    label = data.replace("_", " ").title()
                    existing_facts_list.append(f"- Key: {data} (Label: {label})")
                    seen_keys.add(data)
            if existing_facts_list:
                existing_facts_str = "Context (Fact) hiện tại:\n" + "\n".join(sorted(existing_facts_list))
    except Exception as e_parse:
        print(f"⚠️ Lỗi parse fact_map (V88): {e_parse}")
        existing_facts_str = "Context (Fact) hiện tại:\n(Lỗi parse)"
        
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
    (GPT sẽ thấy 'phan thiet' liên quan đến 'du_lich')
    Output: du_lich | Du Lịch | anh phan thiet
    VÍ DỤ TẠO MỚI:
    Query: "pass server của tôi"
    Context (Fact) hiện tại:
    - Key: du_lich (Label: Du Lịch)
    Output: server_thong_tin | Server Thông Tin | pass server
    VÍ DỤ LỌC (CHUNG):
    Query: "xem file trong cong viec"
    Context (Fact) hiện tại:
    - Key: cong_viec (Label: Công Việc)
    Output: cong_viec | Công Việc | ALL
    Output (key | label | core_query_term):
    """
    
    try:
        # Sửa: Dùng ainvoke (async)
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
        
        print(f"[call_llm_to_classify] (Prompt V88) Query: '{question}' -> Key: '{fact_key}' | Label: '{fact_label}' | CoreQuery: '{core_query_term}'")
        return fact_key, fact_label, core_query_term
        
    except Exception as e:
        print(f"❌ Lỗi call_llm_to_classify (V88): {e}")
        return "general", "General", question

# --- RAG Filter Helpers ---
# (Lấy từ codeold.py)

def _build_rag_filter_from_query(query: str) -> Optional[dict]:
    """(SỬA LỖI V89)
    Dùng regex để tìm TỪ KHÓA (word) 'anh'/'hinh'/'file'.
    Lọc theo 'entry_type': 'file_master'.
   
    """
    q_low = unidecode.unidecode(query.lower())
    
    # 1. Ưu tiên: Tìm (chỉ) ảnh
    if re.search(r"\b(anh|hinh|images?|imgs?)\b", q_low):
         print(f"[_build_rag_filter] (Sửa lỗi V89) Phát hiện lọc (chỉ) ảnh GỐC (Regex).")
         return {
             "$and": [
                 {"file_type": "image"},
                 {"entry_type": "file_master"}
             ]
         }

    # 2. Tìm file GỐC
    file_keywords = [
        "file", "excel", "xlsx", "xls", "trang tinh", 
        "word", "docx", "doc", "van ban", 
        "pdf", "tai lieu", "danh sach", "ds"
    ]
    if any(re.search(r"\b" + re.escape(kw) + r"\b", q_low) for kw in file_keywords):
         print(f"[_build_rag_filter] (Sửa lỗi V89) Phát hiện lọc file GỐC (master) (Regex).")
         return {"entry_type": "file_master"}
         
    # 3. Không phát hiện
    return None

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
# chat_logic.py (THAY THẾ HÀM NÀY - KHOẢNG DÒNG 239)

def _llm_filter_for_selection(
    llm: ChatOpenAI,
    query: str,
    candidates: List[dict] # List of {"id": str, "name": str, "note": str, "metadata": dict}
) -> List[dict]:
    """
    (SỬA LỖI V104 - FIX LỖI "RA HẾT")
    Dùng LLM (sync) để lọc KẾT QUẢ TÌM KIẾM (cho file/ảnh).
    Quy tắc V104: Ưu tiên TÊN, nếu Tên không khớp thì kiểm tra GHI CHÚ.
    """
    if not candidates:
        return []
        
    # 1. Tạo danh sách ứng viên
    candidate_list_str = "\n".join([
        f"<item id='{item['id']}'>Tên: {item['name']} | Ghi chú: {item['note']}</item>"
        for item in candidates
    ])
    
    # --- 🚀 BẮT ĐẦU SỬA LỖI V104 (PROMPT MỚI) 🚀 ---
    prompt = f"""Bạn là một bộ lọc thông minh (Smart Filter).
Nhiệm vụ của bạn là LỌC danh sách (Context) dựa trên Yêu cầu (Query).

Yêu cầu (Query): "{query}"

Danh sách ứng viên (Context):
{candidate_list_str}

QUY TẮC LỌC (V104):
1. Đọc kỹ Yêu cầu (Query).
2. So sánh Query với TỪNG item.
3. ƯU TIÊN GIỮ LẠI (Keep) nếu PHẦN TÊN (Name) khớp với Query.
   (Ví dụ: Query 'máy khoan' khớp Tên 'ảnh máy khoan bosch').
4. NẾU TÊN KHÔNG KHỚP, hãy kiểm tra PHẦN GHI CHÚ (Note). Giữ lại (Keep) nếu Ghi chú khớp với Query.
   (Ví dụ: Query 'máy khoan' khớp Ghi chú 'đây là máy khoan').
5. BỎ QUA (Discard) nếu cả Tên và Ghi chú đều không liên quan.

VÍ DỤ QUAN TRỌNG (V104):
Query: "ảnh máy khoan"
Context:
<item id='abc'>Tên: anh may khoan bosch | Ghi chú: ...</item>
<item id='def'>Tên: IMG_1234.jpg | Ghi chú: luu anh may khoan</item>
<item id='xyz'>Tên: anh du lich vung tau | Ghi chú: ...</item>

Output (Chỉ trả về ID):
abc
def

Output (Chỉ trả về các ID, mỗi ID một dòng. KHÔNG GIẢI THÍCH):
"""
    # --- 🚀 KẾT THÚC SỬA LỖI V104 🚀 ---
    
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
                
        print(f"[LLM Filter Selection] (V104) Đã lọc {len(candidates)} -> còn {len(final_list)} (Query: '{query}')")
        return final_list
        
    except Exception as e:
        print(f"❌ Lỗi _llm_filter_for_selection (V104): {e}")
        # An toàn: trả về rỗng nếu LLM lỗi
        return []

# rag_helpers.py

# ... (Giữ nguyên các hàm đã có) ...

# 🚀 BẮT ĐẦU: THÊM 2 HÀM MỚI TỪ CODEOLD.PY VÀO CUỐI FILE 🚀

async def _llm_batch_split_classify(
    llm: BaseChatModel, 
    user_note: str, 
    num_files: int
) -> List[dict]:
    """
    (MỚI - SỬA LỖI 79 TỪ CODEOLD)
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
                    results.append({"name": line, "key": "general", "label": "General"})
            return results
        
        print(f"⚠️ [LLM Batch Split] (Sửa lỗi 79) GPT trả về {len(lines)} dòng (mong đợi {num_files}). Dùng fallback.")

    except Exception as e:
        print(f"❌ Lỗi _llm_batch_split_classify: {e}. Dùng fallback.")

    return [] # Trả về list rỗng để kích hoạt fallback


async def _llm_split_notes(
    llm: BaseChatModel, 
    user_note: str, 
    num_files: int
) -> List[str]:
    """
    (MỚI - TỪ CODEOLD)
    Dùng LLM để tách ghi chú chung thành các ghi chú con
    tương ứng với số lượng file (Dùng cho Album Mode).
    """
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
        
        if len(lines) == num_files:
            print(f"✅ [LLM Split] Đã tách '{user_note}' -> {lines}")
            return lines
            
        print(f"⚠️ [LLM Split] Tách thất bại (trả về {len(lines)}), dùng fallback.")
        return [user_note] * num_files 
        
    except Exception as e:
        print(f"❌ Lỗi _llm_split_notes: {e}. Dùng fallback.")
        return [user_note] * num_files
# 🚀 KẾT THÚC: THÊM 2 HÀM MỚI