# Hướng Dẫn Sử Dụng Grid Components

## 📋 Tổng Quan

Các Grid Components được thiết kế theo phong cách **Google Drive** với đầy đủ chức năng xem, tải, xóa và sửa file/hình ảnh. Tất cả thao tác được xử lý thông qua **ChainlitContext** để gửi action về server.

## 🎯 Các Components Có Sẵn

### 1. FileGrid.jsx - Hiển thị File/Tài liệu
- ✅ Hiển thị file dạng grid với icon theo loại
- ✅ Modal chi tiết với đầy đủ thông tin
- ✅ Tải xuống nhanh trực tiếp từ grid
- ✅ Xóa/Sửa file thông qua ChainlitContext
- ✅ Responsive trên mọi thiết bị

### 2. ImageGrid.jsx - Hiển thị Hình Ảnh
- ✅ Hiển thị ảnh dạng grid với thumbnail
- ✅ Lightbox xem ảnh fullscreen
- ✅ Modal chi tiết để quản lý
- ✅ Tải xuống nhanh
- ✅ Xóa/Sửa ảnh thông qua ChainlitContext
- ✅ Responsive với hiệu ứng hover đẹp

### 3. MemoryGrid.jsx - Hiển thị Bộ Nhớ
- ✅ Đã có sẵn, hoạt động tốt
- ✅ Modal popup với actions

---

## 🚀 Cách Sử Dụng

### A. Sử Dụng FileGrid

```python
import chainlit as cl
from chainlit.element import Element

@cl.on_chat_start
async def start():
    # Cách 1: Không có actions (chỉ hiển thị và tải)
    files = [
        {
            "name": "Báo cáo tháng 10.pdf",
            "url": "/files/report.pdf",
            "type": "PDF",
            "note": "Báo cáo tài chính Q3"
        },
        {
            "name": "Dữ liệu khách hàng.xlsx",
            "url": "/files/data.xlsx",
            "type": "EXCEL",
            "note": "Cập nhật mới nhất"
        }
    ]
    
    await cl.Message(
        content="",
        elements=[
            Element(
                name="FileGrid",
                props={
                    "title": "Tài liệu của tôi",
                    "files": files,
                    "showActions": True  # Cho phép xóa/sửa
                }
            )
        ]
    ).send()

# Cách 2: Có actions tùy chỉnh từ server
@cl.on_chat_start
async def start_with_actions():
    files = [
        {
            "name": "Document.pdf",
            "url": "/files/doc.pdf",
            "type": "PDF",
            "note": "Tài liệu quan trọng",
            "actions": [
                {
                    "name": "edit_file",
                    "label": "✏️ Sửa tên",
                    "payload": {"file_id": "123", "action": "edit"}
                },
                {
                    "name": "delete_file",
                    "label": "🗑️ Xóa file",
                    "payload": {"file_id": "123", "action": "delete"}
                }
            ]
        }
    ]
    
    await cl.Message(
        content="",
        elements=[Element(name="FileGrid", props={"files": files})]
    ).send()
```

### B. Sử Dụng ImageGrid

```python
import chainlit as cl
from chainlit.element import Element

@cl.on_chat_start
async def start():
    # Cách 1: Không có actions (chỉ xem và tải)
    images = [
        {
            "name": "Ảnh sản phẩm 1.jpg",
            "url": "/images/product1.jpg",
            "note": "Sản phẩm mới nhất"
        },
        {
            "name": "Banner quảng cáo.png",
            "url": "/images/banner.png",
            "note": "Cho chiến dịch tháng 11"
        }
    ]
    
    await cl.Message(
        content="",
        elements=[
            Element(
                name="ImageGrid",
                props={
                    "title": "Thư viện ảnh",
                    "images": images,
                    "showActions": True
                }
            )
        ]
    ).send()

# Cách 2: Có actions tùy chỉnh
@cl.on_chat_start
async def start_with_actions():
    images = [
        {
            "name": "photo.jpg",
            "url": "/saved_images/photo.jpg",
            "note": "Ảnh đẹp",
            "actions": [
                {
                    "name": "edit_image",
                    "label": "✏️ Đổi tên",
                    "payload": {"img_id": "456"}
                },
                {
                    "name": "delete_image",
                    "label": "🗑️ Xóa ảnh",
                    "payload": {"img_id": "456"}
                }
            ]
        }
    ]
    
    await cl.Message(
        content="",
        elements=[Element(name="ImageGrid", props={"images": images})]
    ).send()
```

---

## 🔧 Xử Lý Actions Từ Server

### 1. Xử Lý Action Xóa File

```python
@cl.action_callback("delete_file")
async def handle_delete_file(action):
    """Xử lý khi người dùng xóa file"""
    payload = action.payload
    file_name = payload.get("name")
    file_url = payload.get("url")
    
    # Xóa file thật từ server
    import os
    if file_url.startswith("/files/"):
        file_path = f"./saved_files/{os.path.basename(file_url)}"
        if os.path.exists(file_path):
            os.remove(file_path)
    
    await cl.Message(f"✅ Đã xóa file: {file_name}").send()
    
    # Gửi lại grid mới (không có file vừa xóa)
    # ... code cập nhật lại grid
```

### 2. Xử Lý Action Xóa Ảnh

```python
@cl.action_callback("delete_image")
async def handle_delete_image(action):
    """Xử lý khi người dùng xóa ảnh"""
    payload = action.payload
    img_name = payload.get("name")
    img_url = payload.get("url")
    
    # Xóa ảnh thật từ server
    import os
    if img_url:
        img_path = img_url.replace("/saved_images/", "./saved_images/")
        if os.path.exists(img_path):
            os.remove(img_path)
    
    await cl.Message(f"✅ Đã xóa ảnh: {img_name}").send()
```

### 3. Xử Lý Action Sửa (Edit)

```python
@cl.action_callback("edit_file")
async def handle_edit_file(action):
    """Xử lý khi người dùng muốn sửa file"""
    payload = action.payload
    file_id = payload.get("file_id")
    
    # Hiển thị form nhập tên mới
    res = await cl.AskUserMessage(
        content="Nhập tên file mới:",
        timeout=30
    ).send()
    
    if res:
        new_name = res["output"]
        # Xử lý đổi tên file
        await cl.Message(f"✅ Đã đổi tên thành: {new_name}").send()
```

---

## 🎨 Tùy Chỉnh Giao Diện

### Màu Sắc Nút (Button Classes)

Các component tự động chọn màu dựa trên label:

- 🔴 **Đỏ (Danger)**: Label có "xóa", "hủy"
- 🟢 **Xanh lá (Success)**: Label có "tải", "download"  
- 🟡 **Vàng (Warning)**: Label có "sửa", "edit"
- 🔵 **Xanh dương (Primary)**: Các nút khác

### Ví Dụ Action Với Màu Tùy Chỉnh

```python
actions = [
    {"name": "view", "label": "👁️ Xem chi tiết"},      # → Xanh dương
    {"name": "download", "label": "📥 Tải xuống"},    # → Xanh lá
    {"name": "edit", "label": "✏️ Chỉnh sửa"},        # → Vàng
    {"name": "delete", "label": "🗑️ Xóa"},            # → Đỏ
]
```

---

## 📱 Responsive Design

Các grid tự động điều chỉnh số cột theo màn hình:

### FileGrid
- **Desktop (>768px)**: 4-5 cột
- **Tablet (768px)**: 3-4 cột  
- **Mobile (<640px)**: 2 cột

### ImageGrid
- **Desktop (>768px)**: 5-6 cột
- **Tablet (768px)**: 3-4 cột
- **Mobile (<640px)**: 2-3 cột

---

## ⚡ Tính Năng Nổi Bật

### FileGrid
1. **Grid View**: Hiển thị file với icon đẹp theo loại
2. **Quick Download**: Tải nhanh ngay từ card
3. **Modal Chi Tiết**: Xem đầy đủ thông tin file
4. **Actions**: Xóa/Sửa/Custom actions từ server
5. **Badge Loại File**: Hiển thị loại file (PDF, EXCEL, v.v.)

### ImageGrid
1. **Grid View**: Thumbnail ảnh đẹp với hover effect
2. **Lightbox**: Xem ảnh fullscreen với nền tối
3. **Modal Chi Tiết**: Quản lý ảnh với đầy đủ actions
4. **Quick Download**: Tải nhanh từ card hoặc lightbox
5. **Dual Mode**: Vừa xem ảnh to, vừa có thể xóa/sửa

---

## 🔄 So Sánh Trước & Sau

### ❌ Trước (Vấn đề cũ)
- Chỉ có nút "alert" không thực hiện được gì
- Phải có button ẩn bên ngoài để xóa
- Không có modal chi tiết
- UI đơn giản, không giống Google Drive

### ✅ Sau (Giải pháp mới)
- ✅ Tích hợp ChainlitContext để gửi action thực
- ✅ Modal popup đầy đủ chức năng
- ✅ Xóa/Sửa trực tiếp từ UI, cập nhật realtime
- ✅ Giống Google Drive với grid đẹp, hover effects
- ✅ Lightbox cho ảnh (ImageGrid)
- ✅ Quick actions ngay trên card

---

## 🛠️ Cấu Trúc Dữ Liệu

### File Object
```python
{
    "name": "tên_file.pdf",           # Bắt buộc
    "url": "/path/to/file.pdf",       # Bắt buộc
    "type": "PDF",                    # Tùy chọn (để hiển thị icon)
    "note": "Ghi chú về file",        # Tùy chọn
    "actions": [...]                  # Tùy chọn (nếu không có dùng action mặc định)
}
```

### Image Object
```python
{
    "name": "tên_ảnh.jpg",            # Bắt buộc
    "url": "/path/to/image.jpg",      # Bắt buộc (ưu tiên url)
    "path": "/path/to/image.jpg",     # Fallback nếu không có url
    "note": "Ghi chú về ảnh",         # Tùy chọn
    "actions": [...]                  # Tùy chọn
}
```

### Action Object
```python
{
    "name": "action_name",            # Bắt buộc (để callback)
    "label": "🔧 Tên hiển thị",       # Bắt buộc
    "payload": {...},                 # Tùy chọn (data gửi về server)
    "is_link": False                  # Tùy chọn (True nếu mở link)
}
```

---

## 📚 Ví Dụ Hoàn Chỉnh

```python
import chainlit as cl
from chainlit.element import Element
import os

@cl.on_chat_start
async def start():
    """Hiển thị grid file và ảnh"""
    
    # Danh sách file
    files = [
        {
            "name": "Báo cáo tài chính.pdf",
            "url": "/files/report.pdf",
            "type": "PDF",
            "note": "Báo cáo Q3 2024",
            "actions": [
                {
                    "name": "edit_file",
                    "label": "✏️ Đổi tên",
                    "payload": {"file_id": "f1"}
                },
                {
                    "name": "delete_file", 
                    "label": "🗑️ Xóa",
                    "payload": {"file_id": "f1"}
                }
            ]
        }
    ]
    
    # Danh sách ảnh
    images = [
        {
            "name": "Sản phẩm mới.jpg",
            "url": "/images/product.jpg",
            "note": "Ảnh chụp ngày 14/11/2024"
        }
    ]
    
    await cl.Message(
        content="📁 **Quản lý File & Ảnh**\n\nNhấn vào các item để xem chi tiết, tải xuống hoặc xóa.",
        elements=[
            Element(name="FileGrid", props={
                "title": "📄 Tài liệu",
                "files": files,
                "showActions": True
            }),
            Element(name="ImageGrid", props={
                "title": "🖼️ Hình ảnh", 
                "images": images,
                "showActions": True
            })
        ]
    ).send()

@cl.action_callback("delete_file")
async def on_delete_file(action):
    """Xử lý xóa file"""
    file_id = action.payload.get("file_id")
    await cl.Message(f"✅ Đã xóa file ID: {file_id}").send()

@cl.action_callback("edit_file")
async def on_edit_file(action):
    """Xử lý sửa file"""
    res = await cl.AskUserMessage(
        content="Nhập tên mới:",
        timeout=30
    ).send()
    if res:
        await cl.Message(f"✅ Đã đổi tên thành: {res['output']}").send()
```

---

## 🐛 Xử Lý Lỗi

### Lỗi: "Giao diện chưa sẵn sàng"
**Nguyên nhân**: ChainlitContext chưa được khởi tạo  
**Giải pháp**: Đảm bảo components được render trong Chainlit app

### Lỗi: Actions không hoạt động
**Nguyên nhân**: Chưa đăng ký `@cl.action_callback`  
**Giải pháp**: Tạo callback handler cho mỗi action name

### Lỗi: Ảnh không hiển thị
**Nguyên nhân**: URL không đúng hoặc file không tồn tại  
**Giải pháp**: Kiểm tra lại đường dẫn URL/path

---

## 💡 Tips & Best Practices

1. **Luôn có URL hợp lệ**: Đảm bảo file/ảnh có thể truy cập được
2. **Dùng actions tùy chỉnh**: Để kiểm soát tốt hơn các thao tác
3. **Xử lý callback đúng cách**: Luôn có feedback cho người dùng
4. **Xóa item khỏi state**: Component tự động ẩn item sau khi xóa
5. **Note ngắn gọn**: Giữ note trong 50-100 ký tự để UI đẹp

---

## 📞 Hỗ Trợ

Nếu có vấn đề hoặc câu hỏi, kiểm tra:
- File components: `public/elements/FileGrid.jsx` và `ImageGrid.jsx`
- File MemoryGrid tham khảo: `public/elements/MemoryGrid.jsx`

**Phiên bản**: 2.0 (Google Drive Style)  
**Cập nhật**: 14/11/2024
