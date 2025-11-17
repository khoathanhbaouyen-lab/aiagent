"""
Xóa HOÀN TOÀN tất cả jobs và tasks trong PostgreSQL.
"""
from postgres_utils import execute_query, init_connection_pool

def main():
    init_connection_pool()
    
    print("=" * 60)
    print("XÓA TOÀN BỘ JOBS & TASKS")
    print("=" * 60)
    
    # 1. Xóa bảng APScheduler
    print("\n1. Xóa APScheduler jobs...")
    execute_query("DROP TABLE IF EXISTS apscheduler_jobs CASCADE", fetch=False)
    print("   ✅ Đã xóa bảng apscheduler_jobs")
    
    # 2. Đếm tasks hiện tại
    tasks_count = execute_query("SELECT COUNT(*) as count FROM tasks", fetch=True)[0]['count']
    print(f"\n2. Tìm thấy {tasks_count} tasks")
    
    # Hỏi user có muốn xóa tasks không
    if tasks_count > 0:
        print("\n   Bạn có muốn XÓA TẤT CẢ TASKS không?")
        print("   (Nhấn Enter để GIỮ LẠI, gõ 'xoa' để XÓA HẾT)")
        choice = input("   >>> ").strip().lower()
        
        if choice == 'xoa':
            execute_query("DELETE FROM tasks", fetch=False)
            print("   ✅ Đã xóa tất cả tasks")
        else:
            print("   ℹ️ Giữ nguyên tasks")
    
    # 3. Đếm notification_queue
    try:
        noti_count = execute_query("SELECT COUNT(*) as count FROM notification_queue", fetch=True)[0]['count']
        print(f"\n3. Tìm thấy {noti_count} notifications trong queue")
        if noti_count > 0:
            execute_query("DELETE FROM notification_queue", fetch=False)
            print("   ✅ Đã xóa notification queue")
    except:
        print("\n3. Bảng notification_queue chưa tồn tại")
    
    print("\n" + "=" * 60)
    print("✅ HOÀN TẤT - Tất cả jobs đã được xóa")
    print("=" * 60)
    print("\nBây giờ:")
    print("  1. Restart app: python run.py")
    print("  2. APScheduler sẽ tạo lại bảng sạch")
    print("  3. Không còn lỗi 'No module named I'")

if __name__ == '__main__':
    main()
