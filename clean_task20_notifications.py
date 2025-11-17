import sqlite3

conn = sqlite3.connect('I:/AI GPT/user_data/users.sqlite')
cursor = conn.cursor()

# Delete all old notifications for task 20
cursor.execute("DELETE FROM notification_queue WHERE task_id = 20")
deleted = cursor.rowcount

conn.commit()
conn.close()

print(f'✅ Đã xóa {deleted} notifications cũ của task #20')
print('🔄 Restart server để áp dụng!')
