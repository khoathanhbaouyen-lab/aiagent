from postgres_utils import execute_query, init_connection_pool
import json

init_connection_pool()

print("=" * 60)
print("KIỂM TRA TẤT CẢ JOBS TRONG POSTGRESQL")
print("=" * 60)

# 1. Kiểm tra bảng apscheduler_jobs có tồn tại không
print("\n1. Kiểm tra bảng apscheduler_jobs...")
exists = execute_query("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'apscheduler_jobs'
    )
""", fetch=True)[0]['exists']

if not exists:
    print("   ℹ️ Bảng apscheduler_jobs chưa tồn tại")
else:
    print("   ✅ Bảng apscheduler_jobs đã tồn tại")
    
    # Đếm jobs
    count = execute_query("SELECT COUNT(*) as count FROM apscheduler_jobs", fetch=True)[0]['count']
    print(f"   📊 Số lượng jobs: {count}")
    
    if count > 0:
        # Liệt kê tất cả jobs
        jobs = execute_query("SELECT id, next_run_time FROM apscheduler_jobs ORDER BY id", fetch=True)
        print("\n   Danh sách jobs:")
        for job in jobs:
            print(f"     - {job['id']} (next_run: {job['next_run_time']})")
        
        # Xóa TẤT CẢ
        print("\n   ⚠️ Đang xóa TẤT CẢ jobs...")
        execute_query("DELETE FROM apscheduler_jobs", fetch=False)
        print("   ✅ Đã xóa tất cả jobs")
        
        # Kiểm tra lại
        count_after = execute_query("SELECT COUNT(*) as count FROM apscheduler_jobs", fetch=True)[0]['count']
        print(f"   📊 Số lượng jobs sau khi xóa: {count_after}")

# 2. Kiểm tra tasks
print("\n2. Kiểm tra bảng tasks...")
tasks_count = execute_query("SELECT COUNT(*) as count FROM tasks", fetch=True)[0]['count']
print(f"   📊 Số lượng tasks: {tasks_count}")

if tasks_count > 0:
    # Lấy một vài tasks mẫu
    samples = execute_query("SELECT id, title, status, due_date FROM tasks LIMIT 5", fetch=True)
    print("   Mẫu tasks:")
    for t in samples:
        print(f"     - [{t['id']}] {t['title']} ({t['status']}) - {t['due_date']}")

# 3. Kiểm tra notification_queue
print("\n3. Kiểm tra bảng notification_queue...")
try:
    noti_count = execute_query("SELECT COUNT(*) as count FROM notification_queue", fetch=True)[0]['count']
    print(f"   📊 Số lượng notifications: {noti_count}")
    
    if noti_count > 0:
        print("   ⚠️ Đang xóa notifications...")
        execute_query("DELETE FROM notification_queue", fetch=False)
        print("   ✅ Đã xóa")
except Exception as e:
    print(f"   ℹ️ Bảng chưa tồn tại hoặc lỗi: {e}")

# 4. Kiểm tra langchain_pg_embedding (jobs có thể lưu ở đây?)
print("\n4. Kiểm tra embeddings...")
emb_count = execute_query("SELECT COUNT(*) as count FROM langchain_pg_embedding", fetch=True)[0]['count']
print(f"   📊 Số lượng embeddings: {emb_count}")

print("\n" + "=" * 60)
print("✅ HOÀN TẤT KIỂM TRA")
print("=" * 60)
