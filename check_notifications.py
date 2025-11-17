import sqlite3

conn = sqlite3.connect('I:/AI GPT/user_data/users.sqlite')
cursor = conn.cursor()

cursor.execute("""
    SELECT id, task_id, user_email, sent 
    FROM notification_queue 
    WHERE user_email = 'onsm@oshima.vn' 
    ORDER BY id DESC 
    LIMIT 30
""")

print('\n=== NOTIFICATION QUEUE ===')
rows = cursor.fetchall()
for r in rows:
    print(f'ID: {r[0]:3d} | Task: {r[1]:3d} | Sent: {r[3]}')

print(f'\n📊 Total: {len(rows)} notifications')
print(f'🔴 Pending (sent=0): {sum(1 for r in rows if r[3] == 0)}')
print(f'✅ Sent (sent=1): {sum(1 for r in rows if r[3] == 1)}')

conn.close()
