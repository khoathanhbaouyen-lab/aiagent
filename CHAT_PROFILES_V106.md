# 🔄 V106 - CHAT PROFILES (Thay thế Toggle Mode)

## 📋 Tổng Quan

Đã migrate từ **Toggle Mode** (nút JS custom) sang **Chat Profiles** (tính năng native của Chainlit).

### ✅ Ưu Điểm Chat Profiles

| Tính năng | Toggle Mode (cũ) | Chat Profiles (mới) |
|-----------|------------------|---------------------|
| **UI** | Nút custom (JS) | Dropdown native Chainlit |
| **Vị trí** | Góc dưới trái (fixed) | Góc trên phải (chuẩn) |
| **Icon** | Emoji text | Avatar động (API) |
| **Mô tả** | Không có | Markdown đầy đủ |
| **Trạng thái** | Dễ bị mất khi reload | Persistent (Chainlit quản lý) |
| **Code** | ~130 dòng JS + callback | ~20 dòng Python |

---

## 🎯 Cách Hoạt Động

### 1. Định nghĩa Profiles

```python
# app.py (dòng ~298)
@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="AGENT",
            markdown_description="🤖 **Agent Mode** - Trợ lý thông minh...",
            icon="https://api.dicebear.com/7.x/bottts/svg?seed=agent",
        ),
        cl.ChatProfile(
            name="SELL",
            markdown_description="🛍️ **Sell Mode** - Chuyên viên tư vấn...",
            icon="https://api.dicebear.com/7.x/bottts/svg?seed=sell",
        ),
    ]
```

### 2. Lấy Profile khi Start

```python
# app.py (dòng ~320)
@cl.on_chat_start
async def on_start_after_login():
    # Lấy profile user chọn
    chat_profile = cl.user_session.get("chat_profile")
    
    if chat_profile == "SELL":
        current_mode = "SELL"
    else:
        current_mode = "AGENT"  # Mặc định
    
    # Lưu vào session
    cl.user_session.set("mode", current_mode)
```

### 3. Setup Tools theo Mode

Logic setup tools **KHÔNG ĐỔI**, vẫn dùng `current_mode`:

```python
# app.py (dòng ~7450)
current_mode = cl.user_session.get("mode", "AGENT")

if current_mode == "SELL":
    # Chỉ tool sản phẩm/doanh số
    ask_tools_data = {
        "get_product_detail": ...,
        "searchlistproductnew": ...,
        ...
    }
else:
    # Tool RAG/file/task
    ask_tools_data = {
        "hoi_thong_tin": ...,
        "luu_thong_tin": ...,
        ...
    }
```

---

## 🖼️ Giao Diện

### Trước (Toggle Mode):
```
┌─────────────────────────┐
│                         │
│   Chat messages...      │
│                         │
│                         │
└─────────────────────────┘
[🛍️ SELL Mode]  ← Nút góc dưới trái
```

### Sau (Chat Profiles):
```
┌─────────────────────────┐
│ [Dropdown ▼] AGENT     │ ← Góc trên phải
├─────────────────────────┤
│                         │
│   Chat messages...      │
│                         │
└─────────────────────────┘

Click dropdown:
┌──────────────────────┐
│ 🤖 AGENT            │ ✓
│ Agent Mode - Trợ lý  │
│                      │
│ 🛍️ SELL             │
│ Sell Mode - Tư vấn   │
└──────────────────────┘
```

---

## 🔧 Customization

### Icon Động (DiceBear API)

```python
icon="https://api.dicebear.com/7.x/bottts/svg?seed=agent"
#                                    ^^^^^^       ^^^^^
#                                    Style        Seed (tên unique)
```

**Các style khác:**
- `bottts` - Robot/Bot (đang dùng)
- `avataaars` - Avatar người
- `identicon` - Hình học
- `lorelei` - Nhân vật nữ
- `personas` - Nhân vật đơn giản

**Tùy chỉnh màu:**
```python
icon="https://api.dicebear.com/7.x/bottts/svg?seed=sell&backgroundColor=ff6b6b"
```

### Markdown Description

Hỗ trợ:
- **Bold**: `**text**`
- *Italic*: `*text*`
- Emoji: `🤖 🛍️ 📊`
- Links: `[text](url)`

Ví dụ:
```python
markdown_description="""
🛍️ **Sell Mode**  
Chuyên viên tư vấn bán hàng với:
- Tìm kiếm sản phẩm
- Xem doanh số
- Dashboard báo cáo
"""
```

---

## 🚀 Migration Checklist

✅ **Đã thực hiện:**
- [x] Thêm `@cl.set_chat_profiles`
- [x] Update `@cl.on_chat_start` để lấy profile
- [x] Xóa file `public/mode-toggle.js`
- [x] Xóa callback `@cl.action_callback("toggle_mode")`
- [x] Giữ nguyên logic setup tools (dùng `mode` session)

❌ **Không cần làm:**
- ~~Sửa logic tools~~ (vẫn hoạt động như cũ)
- ~~Sửa prompts~~ (vẫn dùng `current_mode`)
- ~~Thay đổi database~~ (không ảnh hưởng)

---

## 📊 So Sánh Code

### Trước (V105):
```javascript
// public/mode-toggle.js (~130 dòng)
function createToggleButton() { ... }
function updateButtonContent() { ... }
button.addEventListener('click', () => { ... });
```

```python
# app.py
@cl.action_callback("toggle_mode")
async def on_toggle_mode(action):
    current_mode = cl.user_session.get("mode", "AGENT")
    new_mode = "SELL" if current_mode == "AGENT" else "AGENT"
    cl.user_session.set("mode", new_mode)
    # ... restart chat
```

**Tổng:** ~150 dòng code

---

### Sau (V106):
```python
# app.py
@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(name="AGENT", ...),
        cl.ChatProfile(name="SELL", ...),
    ]

@cl.on_chat_start
async def on_start_after_login():
    chat_profile = cl.user_session.get("chat_profile")
    current_mode = "SELL" if chat_profile == "SELL" else "AGENT"
    cl.user_session.set("mode", current_mode)
```

**Tổng:** ~20 dòng code

**Giảm:** 130 dòng (87%)

---

## 🎯 User Experience

### Workflow cũ (Toggle Mode):
1. User nhấn nút góc dưới trái
2. JS gửi message `::toggle_mode::`
3. Backend bắt message, restart chat
4. User mất history, phải hỏi lại

### Workflow mới (Chat Profiles):
1. User click dropdown góc trên phải
2. Chọn profile mới
3. Chainlit tự động restart chat
4. History được giữ (Chainlit quản lý)

**Ưu điểm:**
- ✅ UX mượt hơn
- ✅ Không mất context
- ✅ Chuẩn Chainlit
- ✅ Mobile-friendly

---

## 🧪 Testing

### Test Case 1: Chọn Profile lần đầu
```
1. Login
2. Thấy dropdown "AGENT" (default)
3. Click dropdown → Chọn "SELL"
4. Chat restart
5. Tools chỉ có: searchlistproductnew, get_product_detail, ...
✅ PASS
```

### Test Case 2: Reload page
```
1. Chọn "SELL"
2. F5 reload
3. Profile vẫn là "SELL"
✅ PASS (Chainlit persistence)
```

### Test Case 3: Multiple tabs
```
1. Tab 1: Chọn "AGENT"
2. Tab 2: Chọn "SELL"
3. Mỗi tab hoạt động độc lập
✅ PASS
```

---

## 📝 Notes

- Profile được lưu tại **session level** (mỗi tab riêng)
- Không persist khi logout (reset về default)
- Nếu cần persist, dùng `cl.user_session.set("chat_profile", ...)` + database

---

**Version:** V106  
**Ngày:** 16/11/2025  
**Migration:** Toggle Mode → Chat Profiles  
**Code giảm:** 130 dòng (87%)
