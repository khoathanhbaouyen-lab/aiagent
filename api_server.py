# api_server.py
# Mini HTTP API Server để xử lý DELETE/EDIT từ CustomElements
# Chạy song song với Chainlit trên port config từ .env

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Cho phép CORS để CustomElement có thể gọi

# Port configuration from .env
API_SERVER_PORT = int(os.getenv("API_SERVER_PORT", "8001"))

# APScheduler instance
SCHEDULER = None
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def init_scheduler():
    """Khởi tạo scheduler nếu chưa có"""
    global SCHEDULER
    if SCHEDULER is None:
        SCHEDULER = BackgroundScheduler(timezone=VN_TZ)
        SCHEDULER.start()
        print("✅ [API] Scheduler started")

# Cấu hình (phải giống app.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_FILES_DIR = os.path.join(BASE_DIR, "public", "files")

def get_vectorstore_connection():
    """Kết nối tới ChromaDB (SQLite backend)"""
    # Sửa đường dẫn này cho đúng với cấu trúc của bạn
    db_path = os.path.join(BASE_DIR, "user_data", "shared_vector_db", "chroma.sqlite3")
    return sqlite3.connect(db_path)

def parse_rrule_to_trigger(rrule_str, start_time):
    """
    Parse RRULE string thành APScheduler trigger
    Format: TYPE:REPEAT;FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR;COUNT=10
    """
    if not rrule_str:
        return None, None
    
    parts = rrule_str.split(';')
    rule_dict = {}
    
    for part in parts:
        if ':' in part:
            key, val = part.split(':', 1)
            rule_dict[key.upper()] = val.upper()
        elif '=' in part:
            key, val = part.split('=', 1)
            rule_dict[key.upper()] = val
    
    recur_type = rule_dict.get('TYPE', 'REPEAT')  # REPEAT or REMIND
    freq = rule_dict.get('FREQ', '').upper()
    interval = int(rule_dict.get('INTERVAL', 1))
    
    if freq == 'MINUTELY':
        trigger = IntervalTrigger(minutes=interval, start_date=start_time, timezone=VN_TZ)
    elif freq == 'HOURLY':
        trigger = IntervalTrigger(hours=interval, start_date=start_time, timezone=VN_TZ)
    elif freq == 'DAILY':
        trigger = IntervalTrigger(days=interval, start_date=start_time, timezone=VN_TZ)
    elif freq == 'WEEKLY':
        # Parse BYDAY (MO,TU,WE,TH,FR,SA,SU)
        byday_str = rule_dict.get('BYDAY', '')
        day_map = {'MO': 'mon', 'TU': 'tue', 'WE': 'wed', 'TH': 'thu', 'FR': 'fri', 'SA': 'sat', 'SU': 'sun'}
        days = [day_map[d.strip()] for d in byday_str.split(',') if d.strip() in day_map]
        
        if not days:
            days = None  # Every day
        
        # Extract hour and minute from start_time
        hour = start_time.hour
        minute = start_time.minute
        
        trigger = CronTrigger(
            day_of_week=','.join(days) if days else None,
            hour=hour,
            minute=minute,
            timezone=VN_TZ
        )
    elif freq == 'MONTHLY':
        trigger = IntervalTrigger(weeks=4*interval, start_date=start_time, timezone=VN_TZ)
    elif freq == 'YEARLY':
        trigger = IntervalTrigger(days=365*interval, start_date=start_time, timezone=VN_TZ)
    else:
        # Once (no recurrence)
        trigger = DateTrigger(run_date=start_time, timezone=VN_TZ)
    
    return trigger, recur_type

def task_reminder_job(task_id, recur_type):
    """Job callback khi đến hạn task"""
    print(f"⏰ [Scheduler] Task #{task_id} triggered (type: {recur_type})")
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import task_manager as tm
        
        # Get task info
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "user_data", "users.sqlite"))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            conn.close()
            print(f"⚠️ [Scheduler] Task #{task_id} not found")
            return
        
        # Create notification queue table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                task_title TEXT NOT NULL,
                task_description TEXT,
                notification_type TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            )
        """)
        
        # Insert notification for task owner
        user_email = task['user_email']
        cursor.execute("""
            INSERT INTO notification_queue (user_email, task_id, task_title, task_description, notification_type)
            VALUES (?, ?, ?, ?, ?)
        """, (user_email, task_id, task['title'], task['description'] or '', recur_type))
        
        # Insert notification for assigned users
        assigned_to = task['assigned_to']
        if assigned_to:
            for email in assigned_to.split(','):
                email = email.strip()
                if email and email != user_email:
                    cursor.execute("""
                        INSERT INTO notification_queue (user_email, task_id, task_title, task_description, notification_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (email, task_id, task['title'], task['description'] or '', recur_type))
        
        conn.commit()
        conn.close()
        
        print(f"✅ [Scheduler] Notification queued for task #{task_id} (type: {recur_type})")
        
        if recur_type == 'REPEAT':
            print(f"🔁 [Scheduler] Creating new task from #{task_id}")
            # Clone task with new due_date based on recurrence
            if task['recurrence_rule']:
                # Parse next due date from RRULE
                # For now, just log
                print(f"   → Would create new task based on RRULE: {task['recurrence_rule']}")
        else:
            print(f"🔔 [Scheduler] Reminder only (no new task)")
            
    except Exception as e:
        print(f"❌ [Scheduler] Error in task_reminder_job: {e}")
        import traceback
        traceback.print_exc()

@app.route('/api/delete-file', methods=['POST'])
def delete_file():
    """API để xóa file từ CustomElement"""
    try:
        data = request.json
        doc_id = data.get('doc_id')
        file_path = data.get('file_path')
        
        if not doc_id or not file_path:
            return jsonify({"error": "Missing doc_id or file_path"}), 400
        
        # 1. Xóa metadata từ vectorstore
        try:
            conn = get_vectorstore_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM embeddings WHERE id = ?", (doc_id,))
            conn.commit()
            conn.close()
            print(f"✅ [API] Đã xóa metadata: {doc_id}")
        except Exception as e:
            print(f"⚠️ [API] Lỗi xóa metadata: {e}")
        
        # 2. Xóa file trên disk
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ [API] Đã xóa file: {file_path}")
        except Exception as e:
            print(f"⚠️ [API] Lỗi xóa file: {e}")
        
        return jsonify({"success": True, "message": "Đã xóa thành công"})
        
    except Exception as e:
        print(f"❌ [API] Lỗi delete_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit-file', methods=['POST'])
def edit_file():
    """API để sửa tên/note của file"""
    try:
        data = request.json
        doc_id = data.get('doc_id')
        new_name = data.get('new_name')
        new_note = data.get('new_note')
        
        if not doc_id:
            return jsonify({"error": "Missing doc_id"}), 400
        
        # Cập nhật metadata trong vectorstore
        # (Logic này phức tạp hơn, cần update content trong ChromaDB)
        # Tạm thời return success
        
        return jsonify({"success": True, "message": "Đã cập nhật (chức năng đang phát triển)"})
        
    except Exception as e:
        print(f"❌ [API] Lỗi edit_file: {e}") 
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-file', methods=['GET'])
def download_file():
    """API để tải file gốc (không bị zip) - SỬA LỖI: Xử lý khi file_path là thư mục"""
    try:
        file_path = request.args.get('file_path')
        filename_param = request.args.get('filename')  # optional: original filename from client 
        
        # DEBUG: In ra để kiểm tra
        print(f"\n[DEBUG Download] ========== START ==========")
        print(f"[DEBUG Download] Received file_path: '{file_path}'")
        print(f"[DEBUG Download] Received filename: '{filename_param}'")
        
        if not file_path:
            print(f"[DEBUG Download] ERROR: file_path is None or empty")
            return jsonify({"error": "file_path parameter is missing"}), 400
        
        # ===== SỬA LỖI: XỬ LÝ KHI file_path LÀ THƯ MỤC HOẶC FILE KHÔNG TỒN TẠI =====
        # Chuẩn hóa đường dẫn (chuyển / thành \ trên Windows)
        file_path = os.path.normpath(file_path)
        print(f"[DEBUG Download] Normalized file_path: '{file_path}'")
        
        if os.path.isdir(file_path):
            print(f"[DEBUG Download] WARNING: file_path is a DIRECTORY: '{file_path}'")
            print(f"[DEBUG Download] Trying to find file in public/files using filename: '{filename_param}'")
            
            # Nếu file_path là thư mục, tìm file trong thư mục public/files
            # bằng cách dùng filename_param
            if filename_param:
                # Thử tìm file trong PUBLIC_FILES_DIR
                potential_path = os.path.join(PUBLIC_FILES_DIR, filename_param)
                print(f"[DEBUG Download] Checking potential path: '{potential_path}'")
                
                if os.path.isfile(potential_path):
                    print(f"[DEBUG Download] Found file at: '{potential_path}'")
                    file_path = potential_path
                else:
                    # Thử tìm file có tên tương tự trong PUBLIC_FILES_DIR
                    print(f"[DEBUG Download] Searching for similar files in PUBLIC_FILES_DIR...")
                    found = False
                    for f in os.listdir(PUBLIC_FILES_DIR):
                        if filename_param.lower() in f.lower():
                            file_path = os.path.join(PUBLIC_FILES_DIR, f)
                            print(f"[DEBUG Download] Found similar file: '{file_path}'")
                            found = True
                            break
                    
                    if not found:
                        print(f"[DEBUG Download] ERROR: Could not find file in PUBLIC_FILES_DIR")
                        return jsonify({
                            "error": f"Path is a directory and could not find file: {filename_param}"
                        }), 400
            else:
                print(f"[DEBUG Download] ERROR: Path is a directory and no filename provided")
                return jsonify({"error": f"Path is a directory: {file_path}"}), 400
        
        # Kiểm tra xem file có tồn tại không, nếu không thì tìm trong PUBLIC_FILES_DIR
        if not os.path.exists(file_path):
            print(f"[DEBUG Download] WARNING: File does not exist at: '{file_path}'")
            if filename_param:
                # Lấy chỉ tên file từ file_path (bỏ đường dẫn)
                basename = os.path.basename(file_path)
                potential_path = os.path.join(PUBLIC_FILES_DIR, basename)
                print(f"[DEBUG Download] Trying with basename in PUBLIC_FILES_DIR: '{potential_path}'")
                
                if os.path.isfile(potential_path):
                    print(f"[DEBUG Download] Found file at: '{potential_path}'")
                    file_path = potential_path
                else:
                    print(f"[DEBUG Download] File still not found. Searching for similar files...")
                    found = False
                    for f in os.listdir(PUBLIC_FILES_DIR):
                        if basename.lower() in f.lower() or filename_param.lower() in f.lower():
                            file_path = os.path.join(PUBLIC_FILES_DIR, f)
                            print(f"[DEBUG Download] Found similar file: '{file_path}'")
                            found = True
                            break
                    
                    if not found:
                        print(f"[DEBUG Download] ERROR: Could not find file anywhere")
                        return jsonify({"error": f"File not found: {file_path}"}), 404
        # ===== KẾT THÚC SỬA LỖI =====
        
        print(f"[DEBUG Download] Final file_path: '{file_path}'")
        print(f"[DEBUG Download] File exists: {os.path.exists(file_path)}")
        print(f"[DEBUG Download] Is file: {os.path.isfile(file_path)}")
            
        if not os.path.exists(file_path):
            print(f"[DEBUG Download] ERROR: File not found at: {file_path}")
            return jsonify({"error": f"File not found: {file_path}"}), 404
            
        if not os.path.isfile(file_path):
            print(f"[DEBUG Download] ERROR: Path is not a file!")
            return jsonify({"error": f"Path is not a file: {file_path}"}), 400
        
        # Lấy tên file gốc (ưu tiên tên gốc truyền lên nếu có)
        filename = filename_param or os.path.basename(file_path)
        
        # ===== SỬA LỖI: THÊM EXTENSION VÀO FILENAME =====
        # Nếu filename không có extension, lấy từ file_path
        if filename and '.' not in filename:
            ext = os.path.splitext(file_path)[1]
            if ext:
                filename = filename + ext
                print(f"[DEBUG Download] Added extension: '{ext}' to filename")
        
        print(f"[DEBUG Download] Final filename: '{filename}'")
        
        # Detect mimetype
        import mimetypes
        mimetype, _ = mimetypes.guess_type(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        
        print(f"[DEBUG Download] Mimetype: {mimetype}")
        print(f"[DEBUG Download] Sending file...")
        
        # Stream file trực tiếp về browser với mimetype đúng
        from flask import send_file
        result = send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
        print(f"[DEBUG Download] ========== SUCCESS ==========\n")
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi download_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"})

@app.route('/api/get-users', methods=['GET'])
def get_users():
    """API để lấy danh sách users cho dropdown assign"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import task_manager as tm
        
        users = tm.get_all_users()
        return jsonify({"success": True, "users": users})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi get_users: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/scheduler/jobs', methods=['GET'])
def get_scheduler_jobs():
    """API để xem danh sách jobs trong scheduler"""
    try:
        if not SCHEDULER:
            return jsonify({"error": "Scheduler not initialized"}), 500
        
        jobs = []
        for job in SCHEDULER.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return jsonify({
            "success": True, 
            "scheduler_running": SCHEDULER.running,
            "jobs_count": len(jobs),
            "jobs": jobs
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi get_scheduler_jobs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit-task', methods=['POST'])
def edit_task():
    """API để sửa task từ TaskGrid"""
    try:
        data = request.json
        print(f"\n[DEBUG] Received data: {data}\n")
        
        task_id = data.get('task_id')
        title = data.get('title')
        description = data.get('description')
        due_date = data.get('due_date')
        priority = data.get('priority')
        tags = data.get('tags')  # List
        recurrence_rule = data.get('recurrence_rule')  # RRULE string
        assigned_to = data.get('assigned_to')  # Comma-separated emails
        
        if not task_id:
            return jsonify({"error": "Missing task_id"}), 400
        
        # Import task_manager
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import task_manager as tm
        
        print(f"[DEBUG] Updating task #{task_id}...")
        print(f"  - due_date: {due_date}")
        print(f"  - assigned_to: {assigned_to}")
        print(f"  - recurrence_rule: {recurrence_rule}")
        
        # Update task
        success = tm.update_task(
            task_id=task_id,
            title=title if title else None,
            description=description if description else None,
            due_date=due_date if due_date else None,
            priority=priority if priority else None,
            tags=tags if tags else None,
            assigned_to=assigned_to,
            recurrence_rule=recurrence_rule
        )
        
        print(f"[DEBUG] Update result: {success}")
        
        if success:
            print(f"✅ [API] Đã cập nhật task #{task_id} (recurrence: {recurrence_rule}, assigned_to: {assigned_to})")
            
            # Update scheduler with RRULE logic
            if recurrence_rule and due_date:
                try:
                    init_scheduler()
                    
                    # Remove old job if exists
                    job_id = f"task-{task_id}"
                    try:
                        SCHEDULER.remove_job(job_id)
                        print(f"🗑️ [Scheduler] Removed old job: {job_id}")
                    except:
                        pass
                    
                    # Parse due_date
                    if isinstance(due_date, str):
                        # Try multiple formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M']:
                            try:
                                start_time = datetime.strptime(due_date, fmt)
                                break
                            except:
                                continue
                        else:
                            print(f"⚠️ [Scheduler] Invalid date format: {due_date}")
                            return jsonify({"success": True, "message": f"Đã cập nhật task #{task_id} (no scheduler)"})
                    else:
                        start_time = due_date
                    
                    start_time = VN_TZ.localize(start_time) if start_time.tzinfo is None else start_time
                    
                    # Parse RRULE and create trigger
                    trigger, recur_type = parse_rrule_to_trigger(recurrence_rule, start_time)
                    
                    if trigger:
                        SCHEDULER.add_job(
                            task_reminder_job,
                            trigger=trigger,
                            id=job_id,
                            args=[task_id, recur_type],
                            replace_existing=True
                        )
                        next_run = SCHEDULER.get_job(job_id).next_run_time if SCHEDULER.get_job(job_id) else None
                        print(f"✅ [Scheduler] Added job: {job_id}")
                        print(f"   → Trigger: {trigger}")
                        print(f"   → Type: {recur_type}")
                        print(f"   → Next run: {next_run}")
                    else:
                        print(f"⚠️ [Scheduler] No trigger created for RRULE: {recurrence_rule}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"⚠️ [Scheduler] Failed to update: {e}")
            
            return jsonify({"success": True, "message": f"Đã cập nhật task #{task_id}"})
        else:
            return jsonify({"error": "Task not found or no changes"}), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi edit_task: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-task', methods=['POST'])
def delete_task():
    """API để xóa task từ TaskGrid"""
    try:
        data = request.json
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({"error": "Missing task_id"}), 400
        
        # Import task_manager
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import task_manager as tm
        
        # Get user_email from session (trong thực tế cần auth token)
        # Tạm thời dùng user_email từ request hoặc default
        user_email = data.get('user_email', 'default@local')
        
        success = tm.delete_task(task_id, user_email)
        
        if success:
            print(f"✅ [API] Đã xóa task #{task_id}")
            return jsonify({"success": True, "message": f"Đã xóa task #{task_id}"})
        else:
            return jsonify({"error": "Task not found"}), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi delete_task: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/complete-task', methods=['POST'])
def complete_task():
    """API để đánh dấu hoàn thành task từ TaskGrid"""
    try:
        data = request.json
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({"error": "Missing task_id"}), 400
        
        # Import task_manager
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import task_manager as tm
        
        # Get user_email from session
        user_email = data.get('user_email', 'default@local')
        
        success = tm.mark_complete(task_id, user_email)
        
        if success:
            print(f"✅ [API] Đã hoàn thành task #{task_id}")
            return jsonify({"success": True, "message": f"Đã hoàn thành task #{task_id}"})
        else:
            return jsonify({"error": "Task not found"}), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [API] Lỗi complete_task: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 API Server đang chạy trên http://localhost:8001")
    print("   - DELETE FILE: POST /api/delete-file")
    print("   - EDIT FILE:   POST /api/edit-file")
    print("   - EDIT TASK:   POST /api/edit-task")
    print("   - DELETE TASK: POST /api/delete-task")
    print("   - COMPLETE TASK: POST /api/complete-task")
    print("   - GET USERS:   GET  /api/get-users")
    print()
    
    # Initialize scheduler
    init_scheduler()
    print(f"✅ [API] Server khởi động trên port {API_SERVER_PORT}")
    print()
    
    app.run(host='0.0.0.0', port=API_SERVER_PORT, debug=False)
