// TaskGrid.jsx - Custom Element cho quản lý task với edit popup
export default function TaskGrid() {
  const data = props || {};
  const title = data.title || "📋 Danh sách công việc";
  const stats = data.stats || {};
  const initialTasks = Array.isArray(data.tasks) ? data.tasks : [];
  const [tasks, setTasks] = React.useState(initialTasks);
  const [editModal, setEditModal] = React.useState(null);
  const [editForm, setEditForm] = React.useState({});
  const [allUsers, setAllUsers] = React.useState([]);
  const [userSearch, setUserSearch] = React.useState('');

  // Load users on mount
  React.useEffect(() => {
    fetch('http://localhost:8001/api/get-users')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setAllUsers(data.users);
        }
      })
      .catch(err => console.error('Failed to load users:', err));
  }, []);

  const priorityColors = {
    high: '#ef4444',
    medium: '#f59e0b',
    low: '#10b981'
  };

  const handleComplete = async (task, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Đánh dấu hoàn thành: "${task.title}"?`)) return;
    
    try {
      const res = await fetch('http://localhost:8001/api/complete-task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ task_id: task.id })
      });
      
      if (res.ok) {
        setTasks(prev => prev.map(t => 
          t.id === task.id ? {...t, is_completed: true} : t
        ));
        alert('✅ Đã hoàn thành!');
      } else {
        alert('⚠️ Lỗi khi cập nhật');
      }
    } catch (err) {
      alert('❌ Không thể kết nối server');
    }
  };

  const handleDelete = async (task, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Xóa công việc: "${task.title}"?`)) return;
    
    try {
      const res = await fetch('http://localhost:8001/api/delete-task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ task_id: task.id })
      });
      
      if (res.ok) {
        setTasks(prev => prev.filter(t => t.id !== task.id));
        alert('🗑️ Đã xóa!');
      } else {
        alert('⚠️ Lỗi khi xóa');
      }
    } catch (err) {
      alert('❌ Không thể kết nối server');
    }
  };

  const openEditModal = (task, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Parse recurrence_rule
    let recurrence = { freq: 'once', interval: 1, byday: [], bymonthday: [], type: 'repeat', count: '', until: '' };
    if (task.recurrence_rule) {
      const rule = task.recurrence_rule.toUpperCase();
      
      // Parse each part
      const parts = rule.split(';');
      parts.forEach(part => {
        if (part.includes('TYPE:')) {
          const type = part.split(':')[1];
          recurrence.type = type.toLowerCase();
        }
        else if (part.includes('FREQ=')) {
          const freq = part.split('=')[1];
          recurrence.freq = freq.toLowerCase();
        }
        else if (part.includes('INTERVAL=')) {
          recurrence.interval = parseInt(part.split('=')[1]) || 1;
        }
        else if (part.includes('BYDAY=')) {
          const days = part.split('=')[1].split(',');
          recurrence.byday = days;
        }
        else if (part.includes('COUNT=')) {
          recurrence.count = part.split('=')[1];
        }
        else if (part.includes('UNTIL=')) {
          recurrence.until = part.split('=')[1];
        }
      });
    }
    
    setEditForm({
      task_id: task.id,
      title: task.title,
      description: task.description || '',
      due_date: task.due_date ? task.due_date.replace(' ', 'T').substring(0, 16) : '', // Format for datetime-local
      priority: task.priority || 'medium',
      tags: (task.tags || []).join(', '),
      assigned_to: task.assigned_to ? task.assigned_to.split(',') : [], // Multi-select array
      recurrence_type: recurrence.type,
      recurrence_freq: recurrence.freq,
      recurrence_interval: recurrence.interval,
      recurrence_byday: recurrence.byday,
      recurrence_count: recurrence.count,
      recurrence_until: recurrence.until
    });
    setUserSearch(''); // Reset search
    setEditModal(task);
  };

  const toggleUserSelection = (email) => {
    const current = editForm.assigned_to || [];
    const newSelection = current.includes(email)
      ? current.filter(e => e !== email)
      : [...current, email];
    setEditForm({...editForm, assigned_to: newSelection});
  };

  const removeUser = (email) => {
    const newSelection = (editForm.assigned_to || []).filter(e => e !== email);
    setEditForm({...editForm, assigned_to: newSelection});
  };

  const filteredUsers = allUsers.filter(user => {
    const searchLower = userSearch.toLowerCase();
    return user.name.toLowerCase().includes(searchLower) || 
           user.email.toLowerCase().includes(searchLower);
  });

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    
    // Build recurrence_rule
    let recurrence_rule = null;
    if (editForm.recurrence_freq !== 'once') {
      const parts = [];
      
      // Add type (repeat or remind)
      parts.push(`TYPE:${editForm.recurrence_type.toUpperCase()}`);
      
      parts.push(`FREQ=${editForm.recurrence_freq.toUpperCase()}`);
      
      if (editForm.recurrence_interval > 1) {
        parts.push(`INTERVAL=${editForm.recurrence_interval}`);
      }
      
      if (editForm.recurrence_freq === 'weekly' && editForm.recurrence_byday.length > 0) {
        parts.push(`BYDAY=${editForm.recurrence_byday.join(',')}`);
      }
      
      if (editForm.recurrence_count) {
        parts.push(`COUNT=${editForm.recurrence_count}`);
      } else if (editForm.recurrence_until) {
        parts.push(`UNTIL=${editForm.recurrence_until}`);
      }
      
      recurrence_rule = parts.join(';');
    }
    
    try {
      const res = await fetch('http://localhost:8001/api/edit-task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          task_id: editForm.task_id,
          title: editForm.title,
          description: editForm.description,
          due_date: editForm.due_date ? editForm.due_date.replace('T', ' ') + ':00' : null, // Convert back to SQL format
          priority: editForm.priority,
          tags: editForm.tags.split(',').map(t => t.trim()).filter(t => t),
          assigned_to: editForm.assigned_to ? editForm.assigned_to.join(',') : null,
          recurrence_rule: recurrence_rule
        })
      });
      
      if (res.ok) {
        const result = await res.json();
        // Update local state
        setTasks(prev => prev.map(t => 
          t.id === editForm.task_id ? {
            ...t,
            title: editForm.title,
            description: editForm.description,
            due_date: editForm.due_date,
            priority: editForm.priority,
            tags: editForm.tags.split(',').map(t => t.trim()).filter(t => t)
          } : t
        ));
        setEditModal(null);
        alert('✅ Đã cập nhật!');
      } else {
        alert('⚠️ Lỗi khi cập nhật');
      }
    } catch (err) {
      alert('❌ Không thể kết nối server');
    }
  };

  return React.createElement('div', { style: { width: '100%', padding: '20px 0' } }, [
    React.createElement('style', { key: 's' }, `
      .tg-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin-bottom: 20px;
      }
      .tg-stat-card {
        padding: 15px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }
      .tg-stat-label { font-size: 12px; opacity: 0.9; margin-bottom: 5px; }
      .tg-stat-value { font-size: 24px; font-weight: bold; }
      
      .tg-table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }
      .tg-table thead {
        background: #f3f4f6;
      }
      .tg-table th {
        padding: 12px;
        text-align: left;
        font-weight: 600;
        color: #374151;
        border-bottom: 2px solid #e5e7eb;
        font-size: 13px;
      }
      .tg-table td {
        padding: 12px;
        border-bottom: 1px solid #f3f4f6;
        font-size: 13px;
      }
      .tg-table tbody tr:hover {
        background: #f9fafb;
      }
      
      .tg-priority {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        color: white;
      }
      .tg-tag {
        display: inline-block;
        padding: 3px 8px;
        margin: 2px;
        background: #e5e7eb;
        border-radius: 8px;
        font-size: 11px;
        color: #4b5563;
      }
      .tg-status-icon {
        font-size: 16px;
      }
      
      .tg-actions {
        display: flex;
        gap: 6px;
      }
      .tg-btn {
        padding: 6px 12px;
        font-size: 12px;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s;
      }
      .tg-btn-edit {
        background: #3b82f6;
        color: white;
      }
      .tg-btn-edit:hover { background: #2563eb; }
      .tg-btn-complete {
        background: #10b981;
        color: white;
      }
      .tg-btn-complete:hover { background: #059669; }
      .tg-btn-delete {
        background: #ef4444;
        color: white;
      }
      .tg-btn-delete:hover { background: #dc2626; }
      
      .tg-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .tg-modal {
        background: white;
        border-radius: 12px;
        padding: 24px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      }
      .tg-modal-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 20px;
        color: #1f2937;
      }
      .tg-form-group {
        margin-bottom: 16px;
      }
      .tg-form-label {
        display: block;
        font-size: 13px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 6px;
      }
      .tg-form-input {
        width: 100%;
        padding: 10px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 14px;
        box-sizing: border-box;
      }
      .tg-form-input:focus {
        outline: none;
        border-color: #3b82f6;
      }
      .tg-form-select {
        width: 100%;
        padding: 10px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 14px;
        box-sizing: border-box;
      }
      .tg-user-select-container {
        position: relative;
        width: 100%;
      }
      .tg-user-search {
        width: 100%;
        padding: 10px;
        border: 1px solid #d1d5db;
        border-radius: 8px 8px 0 0;
        font-size: 14px;
        box-sizing: border-box;
      }
      .tg-user-list {
        width: 100%;
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid #d1d5db;
        border-top: none;
        border-radius: 0 0 8px 8px;
        background: white;
      }
      .tg-user-item {
        padding: 8px 10px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
      }
      .tg-user-item:hover {
        background: #f3f4f6;
      }
      .tg-user-item input[type="checkbox"] {
        cursor: pointer;
      }
      .tg-selected-users {
        padding: 8px;
        margin-top: 8px;
        background: #f9fafb;
        border-radius: 6px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        min-height: 40px;
      }
      .tg-user-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        background: #3b82f6;
        color: white;
        border-radius: 4px;
        font-size: 12px;
      }
      .tg-user-tag-remove {
        cursor: pointer;
        font-weight: bold;
      }
      .tg-form-textarea {
        width: 100%;
        padding: 10px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 14px;
        min-height: 80px;
        box-sizing: border-box;
        resize: vertical;
      }
      .tg-form-actions {
        display: flex;
        gap: 10px;
        margin-top: 20px;
      }
      .tg-btn-save {
        flex: 1;
        padding: 12px;
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
      }
      .tg-btn-save:hover { background: #2563eb; }
      .tg-btn-cancel {
        flex: 1;
        padding: 12px;
        background: #e5e7eb;
        color: #374151;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
      }
      .tg-btn-cancel:hover { background: #d1d5db; }
    `),
    
    // Title
    React.createElement('h3', { 
      style: { fontSize: '22px', fontWeight: 700, marginBottom: '20px', color: '#1f2937' }, 
      key: 'title' 
    }, title),
    
    // Stats Cards
    React.createElement('div', { className: 'tg-stats', key: 'stats' }, [
      React.createElement('div', { 
        className: 'tg-stat-card', 
        style: { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
        key: 'total' 
      }, [
        React.createElement('div', { className: 'tg-stat-label', key: 'l' }, 'Tổng'),
        React.createElement('div', { className: 'tg-stat-value', key: 'v' }, stats.total || 0)
      ]),
      React.createElement('div', { 
        className: 'tg-stat-card', 
        style: { background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
        key: 'completed' 
      }, [
        React.createElement('div', { className: 'tg-stat-label', key: 'l' }, 'Hoàn thành'),
        React.createElement('div', { className: 'tg-stat-value', key: 'v' }, stats.completed || 0)
      ]),
      React.createElement('div', { 
        className: 'tg-stat-card', 
        style: { background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
        key: 'pending' 
      }, [
        React.createElement('div', { className: 'tg-stat-label', key: 'l' }, 'Chưa xong'),
        React.createElement('div', { className: 'tg-stat-value', key: 'v' }, stats.pending || 0)
      ]),
      React.createElement('div', { 
        className: 'tg-stat-card', 
        style: { background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
        key: 'high' 
      }, [
        React.createElement('div', { className: 'tg-stat-label', key: 'l' }, 'Ưu tiên cao'),
        React.createElement('div', { className: 'tg-stat-value', key: 'v' }, stats.high_priority || 0)
      ])
    ]),
    
    // Table
    React.createElement('table', { className: 'tg-table', key: 'table' }, [
      React.createElement('thead', { key: 'thead' }, 
        React.createElement('tr', {}, [
          React.createElement('th', { key: 'id' }, 'ID'),
          React.createElement('th', { key: 'title' }, 'Tiêu đề'),
          React.createElement('th', { key: 'due' }, 'Hạn'),
          React.createElement('th', { key: 'assign' }, '👥 Giao cho'),
          React.createElement('th', { key: 'recur' }, '🔁 Lặp lại'),
          React.createElement('th', { key: 'priority' }, 'Priority'),
          React.createElement('th', { key: 'tags' }, 'Tags'),
          React.createElement('th', { key: 'status' }, 'Trạng thái'),
          React.createElement('th', { key: 'actions' }, 'Thao tác')
        ])
      ),
      React.createElement('tbody', { key: 'tbody' },
        tasks.map((task, idx) => {
          const priorityColor = priorityColors[task.priority] || priorityColors.medium;
          
          // Parse recurrence display
          let recurDisplay = '⚪ Một lần';
          if (task.recurrence_rule) {
            const rule = task.recurrence_rule.toLowerCase();
            let typeIcon = '🔁'; // Default: repeat
            
            // Check type
            if (rule.includes('type:remind')) {
              typeIcon = '🔔'; // remind
            }
            
            if (rule.includes('daily')) recurDisplay = `${typeIcon} Hàng ngày`;
            else if (rule.includes('weekly')) recurDisplay = `${typeIcon} Hàng tuần`;
            else if (rule.includes('monthly')) recurDisplay = `${typeIcon} Hàng tháng`;
            else if (rule.includes('yearly')) recurDisplay = `${typeIcon} Hàng năm`;
            else if (rule.includes('hourly')) recurDisplay = `${typeIcon} Theo giờ`;
            else if (rule.includes('minutely')) recurDisplay = `${typeIcon} Theo phút`;
          }
          
          return React.createElement('tr', { key: idx }, [
            React.createElement('td', { key: 'id' }, task.id),
            React.createElement('td', { key: 'title', style: { fontWeight: 500 } }, task.title),
            React.createElement('td', { key: 'due' }, task.due_date || '-'),
            React.createElement('td', { key: 'assign', style: { fontSize: '12px' } }, 
              task.assigned_to 
                ? task.assigned_to.split(',').map(email => email.split('@')[0]).join(', ')
                : '-'
            ),
            React.createElement('td', { key: 'recur', style: { fontSize: '12px' } }, recurDisplay),
            React.createElement('td', { key: 'priority' }, 
              React.createElement('span', { 
                className: 'tg-priority',
                style: { background: priorityColor }
              }, (task.priority || 'medium').toUpperCase())
            ),
            React.createElement('td', { key: 'tags' }, 
              (task.tags || []).map((tag, i) => 
                React.createElement('span', { className: 'tg-tag', key: i }, tag)
              )
            ),
            React.createElement('td', { key: 'status' }, 
              React.createElement('span', { className: 'tg-status-icon' },
                task.is_completed ? '✅' : '⏳'
              )
            ),
            React.createElement('td', { key: 'actions' },
              React.createElement('div', { className: 'tg-actions' }, [
                React.createElement('button', {
                  className: 'tg-btn tg-btn-edit',
                  onClick: (e) => openEditModal(task, e),
                  key: 'edit'
                }, '✏️ Sửa'),
                !task.is_completed && React.createElement('button', {
                  className: 'tg-btn tg-btn-complete',
                  onClick: (e) => handleComplete(task, e),
                  key: 'complete'
                }, '✅'),
                React.createElement('button', {
                  className: 'tg-btn tg-btn-delete',
                  onClick: (e) => handleDelete(task, e),
                  key: 'delete'
                }, '🗑️')
              ])
            )
          ]);
        })
      )
    ]),
    
    // Edit Modal
    editModal && React.createElement('div', {
      className: 'tg-modal-overlay',
      onClick: () => setEditModal(null),
      key: 'modal'
    }, 
      React.createElement('div', {
        className: 'tg-modal',
        onClick: (e) => e.stopPropagation()
      }, [
        React.createElement('div', { className: 'tg-modal-title', key: 'title' }, 
          `✏️ Sửa công việc #${editModal.id}`
        ),
        React.createElement('form', { onSubmit: handleEditSubmit, key: 'form' }, [
          React.createElement('div', { className: 'tg-form-group', key: 'title' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '📝 Tiêu đề'),
            React.createElement('input', {
              className: 'tg-form-input',
              type: 'text',
              value: editForm.title,
              onChange: (e) => setEditForm({...editForm, title: e.target.value}),
              key: 'i'
            })
          ]),
          React.createElement('div', { className: 'tg-form-group', key: 'desc' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '📄 Mô tả'),
            React.createElement('textarea', {
              className: 'tg-form-textarea',
              value: editForm.description,
              onChange: (e) => setEditForm({...editForm, description: e.target.value}),
              key: 'i'
            })
          ]),
          React.createElement('div', { className: 'tg-form-group', key: 'due' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '⏰ Thời hạn (Ngày & Giờ)'),
            React.createElement('input', {
              className: 'tg-form-input',
              type: 'datetime-local',
              value: editForm.due_date,
              onChange: (e) => setEditForm({...editForm, due_date: e.target.value}),
              key: 'i'
            })
          ]),
          React.createElement('div', { className: 'tg-form-group', key: 'assign' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '👥 Giao cho (Multi-select)'),
            React.createElement('div', { 
              style: { fontSize: '11px', color: '#6b7280', marginBottom: '6px' }, 
              key: 'help' 
            }, 'Tìm kiếm và chọn nhiều người cùng lúc'),
            
            // Search box
            React.createElement('div', { className: 'tg-user-select-container', key: 'container' }, [
              React.createElement('input', {
                className: 'tg-user-search',
                type: 'text',
                placeholder: '🔍 Tìm kiếm theo tên hoặc email...',
                value: userSearch,
                onChange: (e) => setUserSearch(e.target.value),
                key: 'search'
              }),
              
              // User list with checkboxes
              React.createElement('div', { className: 'tg-user-list', key: 'list' },
                filteredUsers.map(user => {
                  const isSelected = (editForm.assigned_to || []).includes(user.email);
                  return React.createElement('div', {
                    className: 'tg-user-item',
                    key: user.email,
                    onClick: () => toggleUserSelection(user.email)
                  }, [
                    React.createElement('input', {
                      type: 'checkbox',
                      checked: isSelected,
                      onChange: () => {},
                      key: 'check'
                    }),
                    React.createElement('span', { key: 'name' }, `${user.name} (${user.email})`)
                  ]);
                })
              )
            ]),
            
            // Selected users tags
            (editForm.assigned_to && editForm.assigned_to.length > 0) && 
              React.createElement('div', { className: 'tg-selected-users', key: 'selected' },
                editForm.assigned_to.map(email => {
                  const user = allUsers.find(u => u.email === email);
                  return React.createElement('span', { 
                    className: 'tg-user-tag', 
                    key: email 
                  }, [
                    React.createElement('span', { key: 'name' }, user ? user.name : email),
                    React.createElement('span', {
                      className: 'tg-user-tag-remove',
                      onClick: (e) => {
                        e.stopPropagation();
                        removeUser(email);
                      },
                      key: 'remove'
                    }, '×')
                  ]);
                })
              )
          ]),
          React.createElement('div', { className: 'tg-form-group', key: 'priority' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '🎯 Priority'),
            React.createElement('select', {
              className: 'tg-form-select',
              value: editForm.priority,
              onChange: (e) => setEditForm({...editForm, priority: e.target.value}),
              key: 'i'
            }, [
              React.createElement('option', { value: 'low', key: 'low' }, 'LOW'),
              React.createElement('option', { value: 'medium', key: 'med' }, 'MEDIUM'),
              React.createElement('option', { value: 'high', key: 'high' }, 'HIGH')
            ])
          ]),
          React.createElement('div', { className: 'tg-form-group', key: 'tags' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '🏷️ Tags (cách nhau bởi dấu phẩy)'),
            React.createElement('input', {
              className: 'tg-form-input',
              type: 'text',
              value: editForm.tags,
              onChange: (e) => setEditForm({...editForm, tags: e.target.value}),
              placeholder: 'work, urgent, meeting',
              key: 'i'
            })
          ]),
          
          // Recurrence Type (Repeat vs Remind)
          React.createElement('div', { className: 'tg-form-group', key: 'recur-type' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '🔔 Loại lặp lại'),
            React.createElement('div', { 
              style: { fontSize: '11px', color: '#6b7280', marginBottom: '6px' }, 
              key: 'help' 
            }, 'Chọn giữa Lặp lại (tạo task mới) hoặc Nhắc lại (chỉ thông báo)'),
            React.createElement('select', {
              className: 'tg-form-select',
              value: editForm.recurrence_type || 'repeat',
              onChange: (e) => setEditForm({...editForm, recurrence_type: e.target.value}),
              key: 'i'
            }, [
              React.createElement('option', { value: 'repeat', key: '1' }, '🔁 Lặp lại (Tạo task mới mỗi lần)'),
              React.createElement('option', { value: 'remind', key: '2' }, '🔔 Nhắc lại (Chỉ thông báo, không tạo task mới)')
            ])
          ]),
          
          // Recurring Rule
          React.createElement('div', { className: 'tg-form-group', key: 'recur' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '🔁 Tần suất lặp lại'),
            React.createElement('div', { 
              style: { fontSize: '11px', color: '#6b7280', marginBottom: '6px' }, 
              key: 'help' 
            }, 'Công việc sẽ tự động lặp lại theo tần suất bạn chọn'),
            React.createElement('select', {
              className: 'tg-form-select',
              value: editForm.recurrence_freq,
              onChange: (e) => setEditForm({...editForm, recurrence_freq: e.target.value}),
              key: 'i'
            }, [
              React.createElement('option', { value: 'once', key: '1' }, '⚪ Một lần (Không lặp)'),
              React.createElement('option', { value: 'minutely', key: '2' }, '⏱️ Theo phút'),
              React.createElement('option', { value: 'hourly', key: '3' }, '🕐 Theo giờ'),
              React.createElement('option', { value: 'daily', key: '4' }, '📅 Hàng ngày'),
              React.createElement('option', { value: 'weekly', key: '5' }, '📆 Hàng tuần'),
              React.createElement('option', { value: 'monthly', key: '6' }, '📊 Hàng tháng'),
              React.createElement('option', { value: 'yearly', key: '7' }, '🗓️ Hàng năm')
            ])
          ]),
          
          // Interval (if not once)
          editForm.recurrence_freq !== 'once' && React.createElement('div', { className: 'tg-form-group', key: 'interval' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, 
              `🔢 Lặp lại sau mỗi (${editForm.recurrence_freq === 'minutely' ? 'phút' : editForm.recurrence_freq === 'hourly' ? 'giờ' : editForm.recurrence_freq === 'daily' ? 'ngày' : editForm.recurrence_freq === 'weekly' ? 'tuần' : editForm.recurrence_freq === 'monthly' ? 'tháng' : 'năm'})`
            ),
            React.createElement('input', {
              className: 'tg-form-input',
              type: 'number',
              min: '1',
              value: editForm.recurrence_interval,
              onChange: (e) => setEditForm({...editForm, recurrence_interval: e.target.value}),
              placeholder: '1',
              key: 'i'
            })
          ]),
          
          // Weekly: Choose days
          editForm.recurrence_freq === 'weekly' && React.createElement('div', { className: 'tg-form-group', key: 'byday' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '📆 Chọn các ngày trong tuần'),
            React.createElement('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' }, key: 'd' }, 
              ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'].map((day, idx) => {
                const labels = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
                const isSelected = (editForm.recurrence_byday || []).includes(day);
                return React.createElement('button', {
                  type: 'button',
                  key: day,
                  style: {
                    padding: '8px 12px',
                    border: isSelected ? '2px solid #3b82f6' : '1px solid #d1d5db',
                    background: isSelected ? '#dbeafe' : 'white',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontWeight: isSelected ? '600' : '400'
                  },
                  onClick: () => {
                    const days = editForm.recurrence_byday || [];
                    const newDays = days.includes(day) 
                      ? days.filter(d => d !== day)
                      : [...days, day];
                    setEditForm({...editForm, recurrence_byday: newDays});
                  }
                }, labels[idx]);
              })
            )
          ]),
          
          // Count or Until
          editForm.recurrence_freq !== 'once' && React.createElement('div', { className: 'tg-form-group', key: 'limit' }, [
            React.createElement('label', { className: 'tg-form-label', key: 'l' }, '⏹️ Giới hạn lặp lại (tùy chọn)'),
            React.createElement('div', { 
              style: { fontSize: '11px', color: '#6b7280', marginBottom: '6px' }, 
              key: 'help' 
            }, 'Chọn 1 trong 2: Số lần thực hiện HOẶC Đến ngày kết thúc (để trống = lặp mãi mãi)'),
            React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }, key: 'd' }, [
              React.createElement('div', { key: 'count-wrap' }, [
                React.createElement('label', { 
                  style: { fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '4px', display: 'block' },
                  key: 'cl' 
                }, '🔢 Số lần thực hiện'),
                React.createElement('input', {
                  className: 'tg-form-input',
                  type: 'number',
                  min: '1',
                  placeholder: 'VD: 10 (lặp 10 lần)',
                  value: editForm.recurrence_count,
                  onChange: (e) => setEditForm({...editForm, recurrence_count: e.target.value, recurrence_until: ''}),
                  key: 'count'
                })
              ]),
              React.createElement('div', { key: 'until-wrap' }, [
                React.createElement('label', { 
                  style: { fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '4px', display: 'block' },
                  key: 'ul' 
                }, '📅 Đến ngày'),
                React.createElement('input', {
                  className: 'tg-form-input',
                  type: 'date',
                  value: editForm.recurrence_until,
                  onChange: (e) => setEditForm({...editForm, recurrence_until: e.target.value, recurrence_count: ''}),
                  key: 'until'
                })
              ])
            ])
          ]),
          
          React.createElement('div', { className: 'tg-form-actions', key: 'actions' }, [
            React.createElement('button', {
              type: 'submit',
              className: 'tg-btn-save',
              key: 'save'
            }, '💾 Lưu'),
            React.createElement('button', {
              type: 'button',
              className: 'tg-btn-cancel',
              onClick: () => setEditModal(null),
              key: 'cancel'
            }, '❌ Hủy')
          ])
        ])
      ])
    )
  ]);
}
