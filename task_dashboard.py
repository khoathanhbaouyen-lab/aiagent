"""
Task UI Dashboard - Web Interface for Task Management
"""
from flask import Flask, render_template_string, request, jsonify
import task_manager as tm
from datetime import datetime
import os

app = Flask(__name__)

# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Task Manager Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 30px; }
        
        /* Stats Cards */
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; }
        .stat-card h3 { font-size: 14px; opacity: 0.9; margin-bottom: 10px; }
        .stat-card p { font-size: 32px; font-weight: bold; }
        
        /* Filters */
        .filters { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 30px; }
        .filters input, .filters select { padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        
        /* Task Form */
        .task-form { background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .form-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 15px; }
        .form-row input, .form-row select, .form-row textarea { padding: 10px; border: 1px solid #ddd; border-radius: 5px; width: 100%; }
        .form-row textarea { grid-column: span 3; resize: vertical; min-height: 80px; }
        .btn { padding: 12px 30px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn:hover { background: #5568d3; }
        .btn-export { background: #10b981; }
        .btn-export:hover { background: #059669; }
        
        /* Tasks Table */
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #f3f4f6; padding: 12px; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; }
        td { padding: 12px; border-bottom: 1px solid #e5e7eb; }
        tr:hover { background: #f9fafb; }
        
        /* Priority Badges */
        .priority { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .priority-high { background: #fee2e2; color: #991b1b; }
        .priority-medium { background: #fef3c7; color: #92400e; }
        .priority-low { background: #dbeafe; color: #1e40af; }
        
        /* Tags */
        .tags { display: flex; gap: 5px; flex-wrap: wrap; }
        .tag { padding: 3px 10px; background: #e0e7ff; color: #3730a3; border-radius: 10px; font-size: 11px; }
        
        /* Action Buttons */
        .actions { display: flex; gap: 8px; }
        .actions button { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .btn-complete { background: #10b981; color: white; }
        .btn-delete { background: #ef4444; color: white; }
        .btn-edit { background: #3b82f6; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Task Manager Dashboard</h1>
        
        <!-- Statistics -->
        <div class="stats">
            <div class="stat-card">
                <h3>Total Tasks</h3>
                <p id="stat-total">0</p>
            </div>
            <div class="stat-card">
                <h3>Completed</h3>
                <p id="stat-completed">0</p>
            </div>
            <div class="stat-card">
                <h3>Pending</h3>
                <p id="stat-pending">0</p>
            </div>
            <div class="stat-card">
                <h3>High Priority</h3>
                <p id="stat-high">0</p>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="filters">
            <input type="text" id="filter-user" placeholder="User Email" value="onsm@oshima.vn">
            <select id="filter-status">
                <option value="all">All Status</option>
                <option value="uncompleted" selected>Pending</option>
                <option value="completed">Completed</option>
            </select>
            <select id="filter-priority">
                <option value="">All Priority</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
            </select>
            <input type="date" id="filter-start" placeholder="Start Date">
            <input type="date" id="filter-end" placeholder="End Date">
        </div>
        <button class="btn" onclick="loadTasks()">🔍 Search</button>
        <button class="btn btn-export" onclick="exportExcel()">📊 Export Excel</button>
        
        <!-- Create Task Form -->
        <div class="task-form">
            <h2>➕ Create New Task</h2>
            <form id="task-form" onsubmit="createTask(event)">
                <div class="form-row">
                    <input type="text" name="title" placeholder="Task Title *" required>
                    <input type="datetime-local" name="due_date" required>
                    <select name="priority">
                        <option value="low">Low Priority</option>
                        <option value="medium" selected>Medium Priority</option>
                        <option value="high">High Priority</option>
                    </select>
                </div>
                <div class="form-row">
                    <input type="text" name="tags" placeholder="Tags (comma separated)">
                    <input type="text" name="assigned_to" placeholder="Assign To (email)">
                    <input type="text" name="user_email" placeholder="Your Email *" value="onsm@oshima.vn" required>
                </div>
                <div class="form-row">
                    <textarea name="description" placeholder="Task Description"></textarea>
                </div>
                <button type="submit" class="btn">Create Task</button>
            </form>
        </div>
        
        <!-- Tasks Table -->
        <table id="tasks-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Due Date</th>
                    <th>Priority</th>
                    <th>Tags</th>
                    <th>Assigned To</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="tasks-body">
                <tr><td colspan="8" style="text-align: center; color: #999;">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        // Load tasks
        async function loadTasks() {
            const user = document.getElementById('filter-user').value;
            const status = document.getElementById('filter-status').value;
            const priority = document.getElementById('filter-priority').value;
            const startDate = document.getElementById('filter-start').value;
            const endDate = document.getElementById('filter-end').value;
            
            const params = new URLSearchParams({
                user_email: user,
                status: status,
                priority: priority,
                start_date: startDate,
                end_date: endDate
            });
            
            const res = await fetch(`/api/tasks?${params}`);
            const data = await res.json();
            
            // Update stats
            document.getElementById('stat-total').textContent = data.stats.total;
            document.getElementById('stat-completed').textContent = data.stats.completed;
            document.getElementById('stat-pending').textContent = data.stats.pending;
            document.getElementById('stat-high').textContent = data.stats.high_priority;
            
            // Update table
            const tbody = document.getElementById('tasks-body');
            tbody.innerHTML = '';
            
            if (data.tasks.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #999;">No tasks found</td></tr>';
                return;
            }
            
            data.tasks.forEach(task => {
                const row = `
                    <tr>
                        <td>${task.id}</td>
                        <td>${task.title}</td>
                        <td>${new Date(task.due_date).toLocaleString()}</td>
                        <td><span class="priority priority-${task.priority}">${task.priority.toUpperCase()}</span></td>
                        <td><div class="tags">${task.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div></td>
                        <td>${task.assigned_to || '-'}</td>
                        <td>${task.is_completed ? '✅ Done' : '⏳ Pending'}</td>
                        <td>
                            <div class="actions">
                                ${!task.is_completed ? `<button class="btn-complete" onclick="completeTask(${task.id})">✓</button>` : ''}
                                <button class="btn-delete" onclick="deleteTask(${task.id})">✗</button>
                            </div>
                        </td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        }
        
        // Create task
        async function createTask(e) {
            e.preventDefault();
            const form = document.getElementById('task-form');
            const formData = new FormData(form);
            
            const data = {
                user_email: formData.get('user_email'),
                title: formData.get('title'),
                description: formData.get('description'),
                due_date: formData.get('due_date'),
                priority: formData.get('priority'),
                tags: formData.get('tags').split(',').map(t => t.trim()).filter(t => t),
                assigned_to: formData.get('assigned_to') || null
            };
            
            const res = await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            if (res.ok) {
                alert('✅ Task created successfully!');
                form.reset();
                loadTasks();
            } else {
                alert('❌ Failed to create task');
            }
        }
        
        // Complete task
        async function completeTask(id) {
            const user = document.getElementById('filter-user').value;
            const res = await fetch(`/api/tasks/${id}/complete`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_email: user})
            });
            
            if (res.ok) {
                loadTasks();
            }
        }
        
        // Delete task
        async function deleteTask(id) {
            if (!confirm('Are you sure?')) return;
            
            const user = document.getElementById('filter-user').value;
            const res = await fetch(`/api/tasks/${id}`, {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_email: user})
            });
            
            if (res.ok) {
                loadTasks();
            }
        }
        
        // Export Excel
        function exportExcel() {
            const user = document.getElementById('filter-user').value;
            window.location.href = `/api/export/excel?user_email=${user}`;
        }
        
        // Load on start
        loadTasks();
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """API: Get tasks"""
    user_email = request.args.get('user_email')
    status = request.args.get('status', 'all')
    priority = request.args.get('priority')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.fromisoformat(start_date)
    if end_date:
        end_date = datetime.fromisoformat(end_date)
    
    tasks = tm.get_tasks(
        user_email=user_email,
        status=status,
        priority=priority if priority else None,
        start_date=start_date,
        end_date=end_date
    )
    
    stats = tm.get_task_stats(user_email) if user_email else {'total': 0, 'completed': 0, 'pending': 0, 'high_priority': 0}
    
    return jsonify({'tasks': tasks, 'stats': stats})

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """API: Create task"""
    data = request.json
    
    due_date = datetime.fromisoformat(data['due_date'])
    
    task_id = tm.create_task(
        user_email=data['user_email'],
        title=data['title'],
        description=data.get('description'),
        due_date=due_date,
        priority=data.get('priority', 'medium'),
        tags=data.get('tags', []),
        assigned_to=data.get('assigned_to'),
        assigned_by=data['user_email']
    )
    
    return jsonify({'id': task_id, 'success': True})

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """API: Mark complete"""
    data = request.json
    success = tm.mark_complete(task_id, data['user_email'])
    return jsonify({'success': success})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """API: Delete task"""
    data = request.json
    success = tm.delete_task(task_id, data['user_email'])
    return jsonify({'success': success})

@app.route('/api/export/excel')
def export_excel():
    """API: Export Excel"""
    user_email = request.args.get('user_email')
    output_path = f"task_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    tm.export_tasks_excel(user_email=user_email, output_path=output_path)
    
    return f"✅ Exported to {output_path}"

if __name__ == '__main__':
    # Migrate schema first
    tm.migrate_task_schema()
    
    print("🚀 Task Manager Dashboard")
    print("📍 http://localhost:5000")
    app.run(debug=True, port=5000)
