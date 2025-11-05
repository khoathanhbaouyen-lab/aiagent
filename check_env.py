import sys
import os

print("========================================")
print("--- KET QUA KIEM TRA MOI TRUONG ---")
print("========================================")

print(f"\n[Python] Phien ban (sys.version):\n{sys.version}\n")
print(f"[Python] Duong dan (sys.executable):\n{sys.executable}\n")

try:
    import chainlit
    print(f"[Chainlit] Phien ban da tim thay:\n{chainlit.__version__}\n")
    
    # SỬA LỖI KIỂM TRA:
    # Phiên bản 1.x trở lên dùng "Html", không phải "HTML"
    # Phiên bản 0.7.x không có cả hai
    try:
        from chainlit import Html # <--- Sửa 'H' hoa
        print("[Chainlit] Kiem tra 'Html':\nOK! (Tim thay 'from chainlit import Html')\n")
    except (ImportError, KeyError) as e:
        print(f"[Chainlit] Kiem tra 'Html':\nLOI!!! (Khong tim thay 'Html'. Day la nguyen nhan crash: {e})\n")

except ImportError:
    print("[Chainlit] LOI!!! Khong tim thay thu vien chainlit.\n")

print("========================================")