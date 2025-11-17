import { useEffect, useState } from 'react';

interface Task {
  id: number;
  title: string;
  priority: string;
  due_date: string;
}

interface TaskListProps {
  tasks: Task[];
}

const TaskListWidget = ({ tasks }: TaskListProps) => {
  const [isVisible, setIsVisible] = useState(true);
  
  const getPriorityStyles = (priority: string) => {
    switch (priority) {
      case 'high':
        return { icon: '🔴', color: '#ff6b6b', bg: 'rgba(255,107,107,0.1)' };
      case 'low':
        return { icon: '🟢', color: '#51cf66', bg: 'rgba(81,207,102,0.1)' };
      default:
        return { icon: '🟡', color: '#ffd93d', bg: 'rgba(255,217,61,0.1)' };
    }
  };
  
  if (!isVisible) return null;

  return (
    <>
      <div 
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(4px)',
          zIndex: 9998,
        }}
        onClick={() => setIsVisible(false)}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'linear-gradient(135deg, rgba(30,30,45,0.98) 0%, rgba(20,20,35,0.98) 100%)',
          borderRadius: '16px',
          padding: '24px',
          maxWidth: '600px',
          width: '90%',
          maxHeight: '70vh',
          overflowY: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.1)',
          zIndex: 9999,
        }}
      >
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          borderBottom: '2px solid rgba(255,255,255,0.1)',
          paddingBottom: '12px',
        }}>
          <h2 style={{ margin: 0, color: '#fff', fontSize: '20px' }}>
            📋 Công việc sắp đến hạn ({tasks.length})
          </h2>
          <button
            onClick={() => setIsVisible(false)}
            style={{
              background: 'rgba(255,255,255,0.1)',
              border: 'none',
              color: '#fff',
              padding: '8px 12px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '18px',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.2)')}
            onMouseOut={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
          >
            ✕
          </button>
        </div>
        
        {tasks.map((task) => {
          const styles = getPriorityStyles(task.priority);
          return (
            <div
              key={task.id}
              style={{
                background: styles.bg,
                borderLeft: `4px solid ${styles.color}`,
                borderRadius: '10px',
                padding: '14px',
                marginBottom: '12px',
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = 'translateX(4px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = 'translateX(0)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div style={{ color: '#fff', fontWeight: 600, fontSize: '16px', marginBottom: '4px' }}>
                {styles.icon} {task.title}
              </div>
              <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
                ⏰ {task.due_date}
              </div>
            </div>
          );
        })}
        
        <div style={{
          textAlign: 'center',
          marginTop: '20px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
        }}>
          <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: '13px', margin: 0 }}>
            💡 Click nút bên dưới để edit từng task
          </p>
        </div>
      </div>
    </>
  );
};

export default TaskListWidget;
