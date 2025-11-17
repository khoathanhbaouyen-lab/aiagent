from postgres_utils import execute_query, init_connection_pool

init_connection_pool()

print("Xóa bảng apscheduler_jobs...")
execute_query('DROP TABLE IF EXISTS apscheduler_jobs CASCADE', fetch=False)
print("✅ Đã xóa bảng")

print("\nKiểm tra bảng còn tồn tại không...")
result = execute_query("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'apscheduler_jobs'
    )
""", fetch=True)

if result[0]['exists']:
    print("❌ Bảng vẫn còn!")
else:
    print("✅ Bảng đã được xóa hoàn toàn")
