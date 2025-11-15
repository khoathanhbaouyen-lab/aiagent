// public/elements/FileGrid.jsx
// Custom element để hiển thị file/tài liệu dạng grid giống Google Drive
// PHIÊN BẢN ĐẦY ĐỦ - Có xóa/tải qua API

export default function FileGrid() {
  /* global props, React */
  const data = props || {};
  const title = data.title || "Tài liệu";
  const initialItems = Array.isArray(data.files) ? data.files : [];
  
  const [items, setItems] = React.useState(initialItems);
  const [selectedItem, setSelectedItem] = React.useState(null);

  // Icon theo loại file
  const getFileIcon = (type) => {
    const t = (type || "").toUpperCase();
    if (t.includes("PDF")) return "📕";
    if (t.includes("EXCEL") || t.includes("XLS")) return "📊";
    if (t.includes("WORD") || t.includes("DOC")) return "📘";
    if (t.includes("VIDEO")) return "🎥";
    if (t.includes("AUDIO")) return "🎵";
    if (t.includes("ZIP") || t.includes("RAR")) return "🗜️";
    return "📄";
  };

  // Tải file qua API (không bị zip)
  const handleDownload = (file, e) => {
    e.preventDefault();
    e.stopPropagation();
    const downloadUrl = `http://localhost:8001/api/download-file?file_path=${encodeURIComponent(file.file_path)}`;
    window.open(downloadUrl, '_blank');
  };

  // Xóa file
  const handleDelete = async (file, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm(`Xóa file "${file.name}"?`)) return;
    
    try {
      const response = await fetch('http://localhost:8001/api/delete-file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          doc_id: file.doc_id,
          file_path: file.file_path
        })
      });
      
      if (response.ok) {
        setItems(prev => prev.filter(f => f.doc_id !== file.doc_id));
        alert('✅ Đã xóa file thành công!');
      } else {
        alert('❌ Lỗi khi xóa file');
      }
    } catch (err) {
      console.error('Lỗi API:', err);
      alert('❌ Không thể kết nối tới server');
    }
  };

  // Mở modal xem chi tiết
  const openModal = (file, e) => {
    e.preventDefault();
    setSelectedItem(file);
  };

  return (
    <div className="fg-wrap">
      <style>{`
        .fg-wrap {
          width: 100%;
          padding: 0;
          margin: 12px 0;
          background: transparent;
        }
        .fg-title {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 12px;
          color: #1f2937;
        }

        /* Grid Layout */
        .fg-grid {
          display: grid;
          gap: 16px;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        }
        @media (max-width: 768px) {
          .fg-grid { 
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
          }
        }

        .fg-card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
          position: relative;
        }
        .fg-card:hover {
          border-color: #3b82f6;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
          transform: translateY(-2px);
        }

        .fg-icon-wrap {
          width: 100%;
          height: 140px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          position: relative;
          cursor: pointer;
        }
        .fg-icon {
          font-size: 56px;
          filter: brightness(1.2);
        }
        .fg-type-badge {
          position: absolute;
          bottom: 8px;
          right: 8px;
          background: rgba(255, 255, 255, 0.9);
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 600;
          color: #374151;
        }

        /* Actions below filename */
        .fg-actions {
          display: flex;
          gap: 8px;
          justify-content: flex-start;
          margin-top: 8px;
        }
        .fg-btn {
          padding: 6px 12px;
          font-size: 12px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          background: white;
          cursor: pointer;
          transition: all 0.15s;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .fg-btn:hover {
          background: #f9fafb;
        }
        .fg-btn-download {
          color: #059669;
          border-color: #a7f3d0;
        }
        .fg-btn-download:hover {
          background: #d1fae5;
        }
        .fg-btn-delete {
          color: #dc2626;
          border-color: #fecaca;
        }
        .fg-btn-delete:hover {
          background: #fee2e2;
        }

        .fg-info {
          padding: 12px;
          flex: 1;
          display: flex;
          flex-direction: column;
        }
        .fg-name {
          font-size: 13px;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 4px;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          line-height: 1.4;
          cursor: pointer;
        }
        .fg-name:hover {
          color: #3b82f6;
        }
        .fg-note {
          font-size: 11px;
          color: #6b7280;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          flex: 1;
        }

        /* Modal */
        .fg-modal {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          animation: fadeIn 0.2s;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .fg-modal-content {
          background: white;
          border-radius: 16px;
          max-width: 500px;
          width: 100%;
          padding: 24px;
          position: relative;
        }
        .fg-modal-close {
          position: absolute;
          top: 16px;
          right: 16px;
          background: #f3f4f6;
          border: none;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 20px;
        }
        .fg-modal-close:hover {
          background: #e5e7eb;
        }
        .fg-modal-title {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
          color: #1f2937;
          padding-right: 32px;
        }
        .fg-modal-field {
          margin-bottom: 12px;
        }
        .fg-modal-label {
          font-size: 12px;
          font-weight: 600;
          color: #6b7280;
          margin-bottom: 4px;
        }
        .fg-modal-value {
          font-size: 14px;
          color: #1f2937;
          word-break: break-word;
        }
        .fg-modal-actions {
          display: flex;
          gap: 8px;
          margin-top: 20px;
        }
        .fg-modal-btn {
          flex: 1;
          padding: 10px;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.2s;
        }
        .fg-modal-btn-download {
          background: #10b981;
          color: white;
        }
        .fg-modal-btn-download:hover {
          background: #059669;
        }
        .fg-modal-btn-delete {
          background: #ef4444;
          color: white;
        }
        .fg-modal-btn-delete:hover {
          background: #dc2626;
        }
      `}</style>

      <h3 className="fg-title">{title}</h3>

      {/* GRID CARDS */}
      <div className="fg-grid">
        {items.map((file, idx) => (
          <div key={idx} className="fg-card">
            <div className="fg-icon-wrap" onClick={(e) => openModal(file, e)}>
              <span className="fg-icon">{getFileIcon(file.type)}</span>
              {file.type && (
                <span className="fg-type-badge">
                  {file.type.toUpperCase().substring(0, 10)}
                </span>
              )}
            </div>
            <div className="fg-info">
              <div 
                className="fg-name" 
                title={file.name}
                onClick={(e) => openModal(file, e)}
              >
                {file.name}
              </div>
              <div className="fg-note" title={file.note}>
                {file.note || "(không có ghi chú)"}
              </div>
              {/* Actions: Tải và Xóa */}
              <div className="fg-actions">
                <button
                  className="fg-btn fg-btn-download"
                  title="Tải xuống"
                  onClick={(e) => handleDownload(file, e)}
                >
                  📥 Tải
                </button>
                <button
                  className="fg-btn fg-btn-delete"
                  title="Xóa"
                  onClick={(e) => handleDelete(file, e)}
                >
                  🗑️ Xóa
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* MODAL */}
      {selectedItem && (
        <div className="fg-modal" onClick={() => setSelectedItem(null)}>
          <div className="fg-modal-content" onClick={(e) => e.stopPropagation()}>
            <button 
              className="fg-modal-close"
              onClick={() => setSelectedItem(null)}
            >
              ✕
            </button>
            <div className="fg-modal-title">Chi tiết file</div>
            
            <div className="fg-modal-field">
              <div className="fg-modal-label">TÊN FILE</div>
              <div className="fg-modal-value">{selectedItem.name}</div>
            </div>
            
            <div className="fg-modal-field">
              <div className="fg-modal-label">GHI CHÚ</div>
              <div className="fg-modal-value">
                {selectedItem.note || "(không có)"}
              </div>
            </div>
            
            <div className="fg-modal-field">
              <div className="fg-modal-label">LOẠI FILE</div>
              <div className="fg-modal-value">
                {selectedItem.type || "Unknown"}
              </div>
            </div>

            <div className="fg-modal-actions">
              <button
                className="fg-modal-btn fg-modal-btn-download"
                onClick={(e) => handleDownload(selectedItem, e)}
              >
                📥 Tải xuống
              </button>
              <button
                className="fg-modal-btn fg-modal-btn-delete"
                onClick={(e) => {
                  setSelectedItem(null);
                  handleDelete(selectedItem, e);
                }}
              >
                🗑️ Xóa file
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
