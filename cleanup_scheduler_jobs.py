"""
Xóa các job lỗi trong PostgreSQL APScheduler jobstore.
"""
from postgres_utils import execute_query, init_connection_pool

def main():
    init_connection_pool()
    
    print("=" * 60)
    print("DỌN DẸP APSCHEDULER JOBS")
    print("=" * 60)
    
    # Kiểm tra bảng có tồn tại không
    check = execute_query("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'apscheduler_jobs'
        )
    """, fetch=True)
    
    if not check[0]['exists']:
        print("✅ Bảng apscheduler_jobs chưa tồn tại - không cần dọn dẹp")
        return
    
    # Đếm jobs hiện tại
    count = execute_query("SELECT COUNT(*) as count FROM apscheduler_jobs", fetch=True)[0]['count']
    print(f"\nTìm thấy: {count} jobs")
    
    if count == 0:
        print("✅ Không có job nào cần xóa")
        return
    
    # Liệt kê jobs
    jobs = execute_query("SELECT id, next_run_time FROM apscheduler_jobs", fetch=True)
    print("\nDanh sách jobs:")
    for job in jobs:
        print(f"  - {job['id']} (next_run: {job['next_run_time']})")
    
    # Xóa các job có vấn đề (sync_users_job và jobs cũ)
    print("\nĐang xóa jobs cũ...")
    execute_query("""
        DELETE FROM apscheduler_jobs 
        WHERE id LIKE 'sync_users_job%' 
           OR id LIKE '%_sync_users_from_api_sync%'
    """, fetch=False)
    
    # Đếm lại
    count_after = execute_query("SELECT COUNT(*) as count FROM apscheduler_jobs", fetch=True)[0]['count']
    
    print("\n" + "=" * 60)
    print(f"✅ HOÀN TẤT")
    print(f"   Trước: {count} jobs")
    print(f"   Sau: {count_after} jobs")
    print("=" * 60)
    print("\nBây giờ khởi động lại app, APScheduler sẽ tạo job mới đúng cách.")

if __name__ == '__main__':
    main()
