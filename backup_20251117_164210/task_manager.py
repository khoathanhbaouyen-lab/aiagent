"""
Task Manager Module - PostgreSQL Version
Enhanced với Priority, Tags, Assignment
"""
import os
import json
from typing import List, Optional, Dict
from datetime import datetime
from postgres_utils import execute_query

def get_all_users() -> List[Dict]:
    """Lấy danh sách tất cả users (email + name) từ SQLite (users.sqlite)"""
    import sqlite3
    import os
    
    # Path to SQLite users database
    db_path = os.path.join(os.path.dirname(__file__), "user_data", "users.sqlite")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email, name, is_active 
            FROM users 
            WHERE is_active = 1
            ORDER BY name, email
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        users = []
        for row in results:
            users.append({
                'email': row['email'],
                'name': row['name'] or row['email'].split('@')[0]
            })
        
        return users
    except Exception as e:
        print(f"❌ [task_manager] Error getting users from SQLite: {e}")
        return []

def create_task(
    user_email: str,
    title: str,
    description: Optional[str] = None,
    due_date: datetime = None,
    priority: str = "medium",
    tags: List[str] = None,
    assigned_to: Optional[str] = None,
    assigned_by: Optional[str] = None,
    recurrence_rule: Optional[str] = None
) -> int:
    """Tạo task mới trong PostgreSQL"""
    tags_str = json.dumps(tags) if tags else None
    due_date_str = due_date.strftime('%Y-%m-%d %H:%M:%S') if due_date else None
    
    query = """
        INSERT INTO tasks 
        (user_email, title, description, due_date, priority, tags, assigned_to, assigned_by, recurrence_rule, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        RETURNING id
    """
    
    result = execute_query(
        query,
        params=(user_email, title, description, due_date_str, priority, tags_str, assigned_to, assigned_by, recurrence_rule),
        fetch=True
    )
    
    return result[0]['id'] if result else None

def get_tasks(
    user_email: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    include_assigned_tasks: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict]:
    """Lấy danh sách tasks từ PostgreSQL"""
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    
    if user_email:
        if include_assigned_tasks:
            query += " AND (user_email = %s OR assigned_to = %s)"
            params.extend([user_email, user_email])
        else:
            query += " AND user_email = %s"
            params.append(user_email)
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    if priority:
        query += " AND priority = %s"
        params.append(priority)
    
    if assigned_to:
        query += " AND assigned_to = %s"
        params.append(assigned_to)
    
    if start_date:
        query += " AND due_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND due_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY due_date ASC NULLS LAST, created_at DESC"
    
    results = execute_query(query, params=tuple(params), fetch=True)
    
    tasks = []
    for row in results:
        task = dict(row)
        # Parse tags từ JSON
        if task.get('tags'):
            try:
                task['tags'] = json.loads(task['tags'])
            except:
                task['tags'] = []
        tasks.append(task)
    
    return tasks

def get_upcoming_tasks(user_email: str, limit: int = 5) -> List[Dict]:
    """Lấy các tasks sắp đến hạn"""
    query = """
        SELECT * FROM tasks
        WHERE (user_email = %s OR assigned_to = %s)
        AND status = 'pending'
        AND due_date IS NOT NULL
        AND due_date >= NOW()
        ORDER BY due_date ASC
        LIMIT %s
    """
    
    results = execute_query(query, params=(user_email, user_email, limit), fetch=True)
    
    tasks = []
    for row in results:
        task = dict(row)
        if task.get('tags'):
            try:
                task['tags'] = json.loads(task['tags'])
            except:
                task['tags'] = []
        tasks.append(task)
    
    return tasks

def get_task_by_id(task_id: int) -> Optional[Dict]:
    """Lấy 1 task theo ID"""
    query = "SELECT * FROM tasks WHERE id = %s"
    results = execute_query(query, params=(task_id,), fetch=True)
    
    if not results:
        return None
    
    task = dict(results[0])
    if task.get('tags'):
        try:
            task['tags'] = json.loads(task['tags'])
        except:
            task['tags'] = []
    
    return task

def update_task(
    task_id: int,
    user_email: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[datetime] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
    assigned_to: Optional[str] = None,
    recurrence_rule: Optional[str] = None
) -> bool:
    """Cập nhật task"""
    updates = []
    params = []
    
    if title is not None:
        updates.append("title = %s")
        params.append(title)
    
    if description is not None:
        updates.append("description = %s")
        params.append(description)
    
    if due_date is not None:
        updates.append("due_date = %s")
        # Handle both string and datetime object
        if isinstance(due_date, str):
            params.append(due_date)
        else:
            params.append(due_date.strftime('%Y-%m-%d %H:%M:%S'))
    
    if priority is not None:
        updates.append("priority = %s")
        params.append(priority)
    
    if tags is not None:
        updates.append("tags = %s")
        params.append(json.dumps(tags))
    
    if assigned_to is not None:
        updates.append("assigned_to = %s")
        params.append(assigned_to)
    
    if recurrence_rule is not None:
        updates.append("recurrence_rule = %s")
        params.append(recurrence_rule)
    
    if not updates:
        return False
    
    updates.append("updated_at = NOW()")
    
    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = %s AND (user_email = %s OR assigned_by = %s)"
    params.extend([task_id, user_email, user_email])
    
    execute_query(query, params=tuple(params), fetch=False)
    return True

def complete_task(task_id: int, user_email: str) -> bool:
    """Đánh dấu task hoàn thành"""
    query = "UPDATE tasks SET status = 'completed', updated_at = NOW() WHERE id = %s AND (user_email = %s OR assigned_to = %s)"
    execute_query(query, params=(task_id, user_email, user_email), fetch=False)
    return True

def delete_task(task_id: int, user_email: str) -> bool:
    """Xóa task"""
    # Kiểm tra task có tồn tại trước
    check_query = "SELECT id FROM tasks WHERE id = %s AND (user_email = %s OR assigned_by = %s)"
    result = execute_query(check_query, params=(task_id, user_email, user_email), fetch=True)
    
    if not result:
        print(f"⚠️ [Task Manager] Task #{task_id} không tồn tại hoặc không thuộc về {user_email}")
        return False
    
    # Xóa task
    query = "DELETE FROM tasks WHERE id = %s AND (user_email = %s OR assigned_by = %s)"
    execute_query(query, params=(task_id, user_email, user_email), fetch=False)
    print(f"✅ [Task Manager] Đã xóa task #{task_id}")
    return True

def get_tasks_with_recurrence() -> List[Dict]:
    """Lấy tất cả tasks có recurrence rule"""
    query = """
        SELECT * FROM tasks
        WHERE recurrence_rule IS NOT NULL
        AND recurrence_rule != ''
        AND status = 'pending'
        ORDER BY due_date ASC
    """
    
    results = execute_query(query, fetch=True)
    
    tasks = []
    for row in results:
        task = dict(row)
        if task.get('tags'):
            try:
                task['tags'] = json.loads(task['tags'])
            except:
                task['tags'] = []
        tasks.append(task)
    
    return tasks

def get_overdue_tasks(user_email: Optional[str] = None) -> List[Dict]:
    """Lấy các tasks quá hạn"""
    query = """
        SELECT * FROM tasks
        WHERE status = 'pending'
        AND due_date < NOW()
    """
    params = []
    
    if user_email:
        query += " AND (user_email = %s OR assigned_to = %s)"
        params.extend([user_email, user_email])
    
    query += " ORDER BY due_date ASC"
    
    results = execute_query(query, params=tuple(params) if params else (), fetch=True)
    
    tasks = []
    for row in results:
        task = dict(row)
        if task.get('tags'):
            try:
                task['tags'] = json.loads(task['tags'])
            except:
                task['tags'] = []
        tasks.append(task)
    
    return tasks

def get_task_stats(user_email: str) -> Dict:
    """Thống kê tasks"""
    stats = {
        'total': 0,
        'pending': 0,
        'completed': 0,
        'overdue': 0,
        'by_priority': {'high': 0, 'medium': 0, 'low': 0}
    }
    
    # Total
    query = "SELECT COUNT(*) as count FROM tasks WHERE (user_email = %s OR assigned_to = %s)"
    result = execute_query(query, params=(user_email, user_email), fetch=True)
    stats['total'] = result[0]['count'] if result else 0
    
    # Pending
    query = "SELECT COUNT(*) as count FROM tasks WHERE (user_email = %s OR assigned_to = %s) AND status = 'pending'"
    result = execute_query(query, params=(user_email, user_email), fetch=True)
    stats['pending'] = result[0]['count'] if result else 0
    
    # Completed
    query = "SELECT COUNT(*) as count FROM tasks WHERE (user_email = %s OR assigned_to = %s) AND status = 'completed'"
    result = execute_query(query, params=(user_email, user_email), fetch=True)
    stats['completed'] = result[0]['count'] if result else 0
    
    # Overdue
    query = "SELECT COUNT(*) as count FROM tasks WHERE (user_email = %s OR assigned_to = %s) AND status = 'pending' AND due_date < NOW()"
    result = execute_query(query, params=(user_email, user_email), fetch=True)
    stats['overdue'] = result[0]['count'] if result else 0
    
    # By priority
    for priority in ['high', 'medium', 'low']:
        query = "SELECT COUNT(*) as count FROM tasks WHERE (user_email = %s OR assigned_to = %s) AND priority = %s AND status = 'pending'"
        result = execute_query(query, params=(user_email, user_email, priority), fetch=True)
        stats['by_priority'][priority] = result[0]['count'] if result else 0
    
    return stats

# Không cần migrate_task_schema cho PostgreSQL - đã tạo table rồi
def migrate_task_schema():
    """No-op - table đã được tạo trong PostgreSQL"""
    pass
