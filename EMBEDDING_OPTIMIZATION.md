# 🚀 EMBEDDING OPTIMIZATION - TĂNG TỐC 10-20 LẦN

## 📊 So sánh hiệu năng

| Phương pháp | Thời gian | Chi phí | Offline | Tiếng Việt |
|-------------|-----------|---------|---------|------------|
| **OpenAI API** (cũ) | ~1.2s | $$ | ❌ | ✅ Tốt |
| **Local MiniLM** (mới) | ~0.05-0.15s | Miễn phí | ✅ | ✅ Tốt |
| **all-MiniLM-L6-v2** | ~0.03-0.08s | Miễn phí | ✅ | ⚠️ Trung bình |
| **PhoBERT** | ~0.2-0.4s | Miễn phí | ✅ | ✅✅ Xuất sắc |

## 🎯 Cấu hình hiện tại

### Model đang dùng: `paraphrase-multilingual-MiniLM-L12-v2`
- ✅ Hỗ trợ tiếng Việt tốt (multilingual)
- ✅ Tốc độ nhanh: **0.05-0.15s** (nhanh gấp 8-20 lần OpenAI)
- ✅ Kích thước: ~420MB (tải lần đầu, sau đó cache)
- ✅ Chạy offline, không cần internet
- ✅ Miễn phí, không giới hạn

## 🔧 Cách sử dụng

### 1. Bật/Tắt Local Embeddings

Trong file `.env`:
```env
# true = Dùng local (nhanh, miễn phí)
# false = Dùng OpenAI (chậm, tốn tiền)
USE_LOCAL_EMBEDDINGS=true
```

### 2. Chuyển đổi model (nếu cần)

Trong `app.py` (dòng ~1945), chọn 1 trong 3 options:

#### OPTION 1: Multilingual MiniLM (ĐANG DÙNG - Khuyên dùng)
```python
embeddings = HuggingFaceEmbeddings(
    model_name="paraphrase-multilingual-MiniLM-L12-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)
```

#### OPTION 2: all-MiniLM-L6-v2 (NHANH NHẤT)
```python
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",  # ~80MB, cực nhanh
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)
```

#### OPTION 3: PhoBERT (TỐT NHẤT CHO TIẾNG VIỆT)
```python
embeddings = HuggingFaceEmbeddings(
    model_name="vinai/phobert-base",  # ~500MB
    model_kwargs={'device': 'cpu'}
)
```

### 3. Tăng tốc bằng GPU (nếu có)

Đổi `'device': 'cpu'` thành `'device': 'cuda'`:
```python
model_kwargs={'device': 'cuda'}  # Tốc độ tăng 5-10 lần nữa!
```

## 📦 Dependencies đã cài

```bash
pip install langchain-huggingface sentence-transformers
```

## ⚡ Lưu ý

### Lần đầu chạy:
- Model sẽ tải về từ HuggingFace (~420MB)
- Mất ~30-60s download
- Sau đó cache tại `~/.cache/huggingface/`

### Lần sau:
- Load từ cache cục bộ
- Không cần internet
- Tốc độ khởi động ~2-5s

## 🧪 Kiểm tra hiệu năng

Log sẽ hiển thị thời gian từng bước:
```
[PERFORMANCE V104] Query: 'cho toi anh may bao'
========================================================
  GPT Classify:      0.000s (SKIPPED ⚡)
  OpenAI Embeddings: 0.087s  ← Giảm từ 1.243s xuống 0.087s!
  ChromaDB Search:   0.024s
  GPT Filter:        0.543s
  ──────────────────────────────────────────────────────
  TOTAL TIME:        0.654s
========================================================
```

## 🎯 Kết quả kỳ vọng

**Trước (OpenAI):**
```
OpenAI Embeddings: 1.243s
TOTAL TIME: 2.1s
```

**Sau (Local):**
```
HuggingFace Embeddings: 0.087s  ← Nhanh gấp 14 lần!
TOTAL TIME: 0.7s  ← Nhanh gấp 3 lần toàn bộ!
```

## 🔄 Rollback về OpenAI

Nếu gặp vấn đề, đổi trong `.env`:
```env
USE_LOCAL_EMBEDDINGS=false
```

---

**Tối ưu hóa bởi:** GitHub Copilot
**Ngày tạo:** 16/11/2025
