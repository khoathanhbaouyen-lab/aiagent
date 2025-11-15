# 📚 Hướng dẫn Grid Components với API

## 🎯 Giới thiệu

Hệ thống Grid Components hiện đại với khả năng **xóa/sửa/tải** file trực tiếp từ giao diện, tương tự Google Drive.

### ✨ Tính năng chính

- ✅ **Grid layout đẹp** - Responsive, hiện đại
- ✅ **Actions on hover** - Nút xuất hiện khi hover (📥 Tải, 🗑️ Xóa, ℹ️ Chi tiết)
- ✅ **Lightbox cho ảnh** - Xem ảnh fullscreen
- ✅ **Modal chi tiết** - Xem thông tin đầy đủ
- ✅ **API Backend** - Xóa file thực sự khỏi DB + disk
- ✅ **Real-time update** - UI cập nhật ngay khi xóa

---

## 🚀 Cách khởi động

### Phương án 1: Dùng script tự động (Khuyên dùng)

```bash
start_servers.bat
```

Script này sẽ:
1. Kiểm tra và cài `flask-cors` nếu chưa có
2. Khởi động API Server (port 8001)
3. Khởi động Chainlit (port 8000)

### Phương án 2: Khởi động thủ công

**Terminal 1 - API Server:**
```bash
python api_server.py
```

**Terminal 2 - Chainlit:**
```bash
chainlit run app.py -w
```

---

## 📦 Dependencies

Cài thêm Flask và CORS:

```bash
pip install flask flask-cors
```

---

## 💻 Cách sử dụng trong Code

### 1. FileGrid Component

Hiển thị files/tài liệu với icons đẹp:

```python
import chainlit as cl

# Chuẩn bị data
files_data = [
    {
        "name": "Báo cáo.pdf",
        "type": "PDF",
        "url": "/public/files/report.pdf",
        "note": "Báo cáo quý 3",
        "doc_id": "doc_123",  # Cần cho API delete
        "file_path": "I:/AI GPT/public/files/report.pdf"  # Đường dẫn thật
    },
    {
        "name": "Dữ liệu.xlsx",
        "type": "EXCEL",
        "url": "/public/files/data.xlsx",
        "note": "Dữ liệu sales",
        "doc_id": "doc_456",
        "file_path": "I:/AI GPT/public/files/data.xlsx"
    }
]

# Hiển thị grid
await cl.Message(
    content="Đây là tài liệu của bạn:",
    elements=[
        cl.CustomElement(
            name="FileGrid",
            props={
                "title": "📁 Tài liệu của tôi",
                "files": files_data
            }
        )
    ]
).send()
```

**Các loại file được hỗ trợ:**
- 📕 PDF
- 📊 Excel (XLS, XLSX)
- 📘 Word (DOC, DOCX)
- 🎥 Video
- 🎵 Audio
- 🗜️ Nén (ZIP, RAR)
- 📄 Khác

### 2. ImageGrid Component

Hiển thị ảnh với lightbox:

```python
import chainlit as cl

# Chuẩn bị data
images_data = [
    {
        "name": "Ảnh phong cảnh.jpg",
        "url": "/public/images/landscape.jpg",
        "path": "/public/images/landscape.jpg",  # Fallback
        "note": "Chụp tại Đà Lạt",
        "doc_id": "img_789",
        "file_path": "I:/AI GPT/public/images/landscape.jpg"
    },
    {
        "name": "Chân dung.png",
        "url": "/public/images/portrait.png",
        "note": "Studio shot",
        "doc_id": "img_012",
        "file_path": "I:/AI GPT/public/images/portrait.png"
    }
]

# Hiển thị grid
await cl.Message(
    content="Đây là ảnh của bạn:",
    elements=[
        cl.CustomElement(
            name="ImageGrid",
            props={
                "title": "🖼️ Thư viện ảnh",
                "images": images_data
            }
        )
    ]
).send()
```

---

## 🔧 API Endpoints

API Server chạy trên `http://localhost:8001`

### 1. DELETE File

**Endpoint:** `POST /api/delete-file`

**Body:**
```json
{
  "doc_id": "doc_123",
  "file_path": "I:/AI GPT/public/files/report.pdf"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Đã xóa thành công"
}
```

**Chức năng:**
- Xóa metadata từ vector database (ChromaDB)
- Xóa file vật lý trên disk
- Trả về kết quả

### 2. EDIT File (Coming Soon)

**Endpoint:** `POST /api/edit-file`

**Body:**
```json
{
  "doc_id": "doc_123",
  "new_name": "Báo cáo mới.pdf",
  "new_note": "Báo cáo Q4 2025"
}
```

*(Tính năng này đang được phát triển)*

### 3. Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok"
}
```

---

## 🎨 UI Features

### FileGrid

**Actions khi hover:**
- 📥 **Tải xuống** - Download file
- 🗑️ **Xóa** - Xóa file (có confirm)

**Click vào card:**
- Mở modal chi tiết với thông tin đầy đủ
- Có thể tải hoặc xóa từ modal

### ImageGrid

**Actions khi hover:**
- ℹ️ **Chi tiết** - Mở modal thông tin
- 📥 **Tải xuống** - Download ảnh
- 🗑️ **Xóa** - Xóa ảnh (có confirm)

**Click vào ảnh:**
- Mở lightbox xem fullscreen
- Click bên ngoài hoặc ESC để đóng
- Có nút tải xuống trong lightbox

---

## 🔒 Bảo mật

### CORS
API Server đã bật CORS để cho phép CustomElement gọi API từ browser.

```python
from flask_cors import CORS
CORS(app)
```

### Xác thực (Tương lai)
Hiện tại API không có authentication. Trong production nên thêm:
- JWT tokens
- API keys
- Rate limiting

---

## 🐛 Troubleshooting

### Lỗi: "Không thể kết nối tới server"

**Nguyên nhân:** API Server chưa chạy

**Giải pháp:**
```bash
# Kiểm tra API Server
curl http://localhost:8001/health

# Nếu không chạy, khởi động lại
python api_server.py
```

### Lỗi: "Xóa file không thành công"

**Nguyên nhân:** 
- `doc_id` hoặc `file_path` không đúng
- File không tồn tại
- Không có quyền xóa file

**Giải pháp:**
- Kiểm tra console log của API Server
- Đảm bảo `doc_id` và `file_path` chính xác
- Kiểm tra permissions của file

### Lỗi: "flask-cors not found"

**Giải pháp:**
```bash
pip install flask-cors
```

---

## 📁 Cấu trúc File

```
i:/AI GPT/
├── api_server.py              # API Backend
├── start_servers.bat          # Script khởi động
├── app.py                     # Chainlit app
├── public/
│   └── elements/
│       ├── FileGrid.jsx       # File grid component
│       ├── ImageGrid.jsx      # Image grid component
│       └── README_GRID_COMPONENTS.md
└── user_data/
    └── shared_vector_db/
        └── chroma.sqlite3     # Vector DB
```

---

## 🎯 Best Practices

### 1. Luôn truyền `doc_id` và `file_path`

```python
# ✅ ĐÚNG
file_data = {
    "name": "file.pdf",
    "doc_id": "unique_id_123",
    "file_path": "I:/AI GPT/public/files/file.pdf"
}

# ❌ SAI - Thiếu thông tin
file_data = {
    "name": "file.pdf"
}
```

### 2. Xử lý lỗi gracefully

```python
try:
    await cl.Message(elements=[...]).send()
except Exception as e:
    await cl.Message(f"Lỗi: {str(e)}").send()
```

### 3. Validate data trước khi hiển thị

```python
files = get_files_from_db()
valid_files = [f for f in files if f.get('doc_id') and f.get('file_path')]
```

---

## 🚀 Roadmap

- [ ] Chức năng Edit/Rename
- [ ] Bulk delete (xóa nhiều files)
- [ ] Sort & Filter
- [ ] Search trong grid
- [ ] Pagination cho grid lớn
- [ ] Upload file trực tiếp từ grid
- [ ] Preview file trong modal (PDF viewer, etc)

---

## 📞 Support

Nếu có vấn đề, kiểm tra:
1. Cả 2 servers đang chạy
2. Console logs của browser (F12)
3. Terminal logs của API Server
4. Data format đúng chuẩn

---

## 🎉 Kết luận

Hệ thống Grid Components mới giúp bạn:
- Quản lý files/images dễ dàng
- Giao diện đẹp như Google Drive
- Xóa/tải trực tiếp không cần reload

**Chúc bạn sử dụng hiệu quả!** 🚀
