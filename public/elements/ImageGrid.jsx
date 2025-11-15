// public/elements/ImageGrid.jsx
// Custom element để hiển thị ảnh dạng grid giống Google Drive
// PHIÊN BẢN ĐẦY ĐỦ - Có xóa/tải qua API + Lightbox

export default function ImageGrid() {
  /* global props, React */
  const data = props || {};
  const title = data.title || "Hình ảnh";
  const initialItems = Array.isArray(data.images) ? data.images : [];
  
  const [items, setItems] = React.useState(initialItems);
  const [lightbox, setLightbox] = React.useState(null);
  const [selectedItem, setSelectedItem] = React.useState(null);

  // Đóng lightbox khi nhấn ESC
  React.useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') {
        setLightbox(null);
        setSelectedItem(null);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, []);

  // Tải file qua API (không bị zip)
  const handleDownload = (img, e) => {
    e.preventDefault();
    e.stopPropagation();
    const filePath = img.file_path || img.path;
    const downloadUrl = `http://localhost:8001/api/download-file?file_path=${encodeURIComponent(filePath)}`;
    window.open(downloadUrl, '_blank');
  };

  // Xóa ảnh
  const handleDelete = async (img, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm(`Xóa ảnh "${img.name}"?`)) return;
    
    try {
      const response = await fetch('http://localhost:8001/api/delete-file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          doc_id: img.doc_id,
          file_path: img.file_path || img.path
        })
            <a
              href={`http://localhost:8001/api/download-file?file_path=${encodeURIComponent(lightbox.file_path || lightbox.path || lightbox.url)}&filename=${encodeURIComponent(lightbox.name || '')}`}
              className="ig-lightbox-btn"
              title="Tải xuống"
              onClick={(e) => e.stopPropagation()}
              target="_blank"
              rel="noreferrer"
            >
              📥
            </a>
      }
    } catch (err) {
      console.error('Lỗi API:', err);
      alert('❌ Không thể kết nối tới server');
    }
  };

  return (
    <div className="ig-wrap">
      <style>{`
        .ig-wrap {
          width: 100%;
          padding: 0;
          margin: 12px 0;
          background: transparent;
        }
        .ig-title {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 12px;
          color: #1f2937;
        }

        /* Grid Layout */
        .ig-grid {
          display: grid;
          gap: 12px;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        }
        @media (max-width: 768px) {
          .ig-grid { 
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 10px;
          }
        }

        .ig-card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
          position: relative;
        }
        .ig-card:hover {
          border-color: #3b82f6;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
          transform: translateY(-2px);
        }

        .ig-img-wrap {
          width: 100%;
          height: 180px;
          overflow: hidden;
          background: #f3f4f6;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }
        .ig-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          transition: transform 0.3s;
        }
        .ig-card:hover .ig-img {
          transform: scale(1.05);
        }

        .ig-info {
          padding: 12px;
        }
        .ig-name {
          font-size: 14px;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 4px;
          display: -webkit-box;
          -webkit-line-clamp: 1;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .ig-note {
          font-size: 12px;
          color: #6b7280;
          margin-bottom: 8px;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        /* Actions below filename */
        .ig-actions {
          display: flex;
          gap: 8px;
          justify-content: flex-start;
          margin-top: 8px;
        }
        .ig-btn {
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
        .ig-btn:hover {
          background: #f9fafb;
        }
        .ig-btn-download {
          color: #059669;
          border-color: #a7f3d0;
        }
        .ig-btn-download:hover {
          background: #d1fae5;
        }
        .ig-btn-delete {
          color: #dc2626;
          border-color: #fecaca;
        }
        .ig-btn-delete:hover {
          background: #fee2e2;
        }

        /* Lightbox */
        .ig-lightbox {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.95);
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
        .ig-lightbox-img {
          max-width: 90%;
          max-height: 90vh;
          object-fit: contain;
          border-radius: 8px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }
        .ig-lightbox-actions {
          position: absolute;
          top: 20px;
          right: 20px;
          display: flex;
          gap: 10px;
        }
        .ig-lightbox-btn {
          background: rgba(255, 255, 255, 0.9);
          border: none;
          width: 44px;
          height: 44px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }
        .ig-lightbox-btn:hover {
          background: white;
          transform: scale(1.1);
        }
        .ig-lightbox-info {
          position: absolute;
          bottom: 20px;
          left: 50%;
          transform: translateX(-50%);
          background: rgba(255, 255, 255, 0.95);
          padding: 12px 20px;
          border-radius: 8px;
          max-width: 80%;
        }
        .ig-lightbox-name {
          font-size: 14px;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 4px;
        }
        .ig-lightbox-note {
          font-size: 12px;
          color: #6b7280;
        }

        /* Modal chi tiết */
        .ig-modal {
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
        .ig-modal-content {
          background: white;
          border-radius: 16px;
          max-width: 500px;
          width: 100%;
          padding: 24px;
          position: relative;
        }
        .ig-modal-close {
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
        .ig-modal-close:hover {
          background: #e5e7eb;
        }
        .ig-modal-preview {
          width: 100%;
          max-height: 300px;
          object-fit: contain;
          border-radius: 8px;
          margin-bottom: 16px;
          background: #f3f4f6;
        }
        .ig-modal-title {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
          color: #1f2937;
          padding-right: 32px;
        }
        .ig-modal-field {
          margin-bottom: 12px;
        }
        .ig-modal-label {
          font-size: 12px;
          font-weight: 600;
          color: #6b7280;
          margin-bottom: 4px;
        }
        .ig-modal-value {
          font-size: 14px;
          color: #1f2937;
          word-break: break-word;
        }
        .ig-modal-actions {
          display: flex;
          gap: 8px;
          margin-top: 20px;
        }
        .ig-modal-btn {
          flex: 1;
          padding: 10px;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.2s;
        }
        .ig-modal-btn-download {
          background: #10b981;
          color: white;
        }
        .ig-modal-btn-download:hover {
          background: #059669;
        }
        .ig-modal-btn-delete {
          background: #ef4444;
          color: white;
        }
        .ig-modal-btn-delete:hover {
          background: #dc2626;
        }
      `}</style>

      <h3 className="ig-title">{title}</h3>

      {/* GRID CARDS */}
      <div className="ig-grid">
        {items.map((img, idx) => {
          const imgUrl = img.url || img.path || '';
          return (
            <div 
              key={idx} 
              className="ig-card"
              onClick={() => setLightbox(img)}
            >
              <div className="ig-img-wrap">
                <img 
                  src={imgUrl} 
                  alt={img.name} 
                  className="ig-img"
                  loading="lazy"
                />
              </div>
              <div className="ig-info">
                <div className="ig-name" title={img.name}>
                  {img.name}
                </div>
                <div className="ig-note" title={img.note}>
                  {img.note || "(không có ghi chú)"}
                </div>
                {/* Actions: Tải và Xóa */}
                <div className="ig-actions" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="ig-btn ig-btn-download"
                    title="Tải xuống"
                    onClick={(e) => handleDownload(img, e)}
                  >
                    📥 Tải
                  </button>
                  <button
                    className="ig-btn ig-btn-delete"
                    title="Xóa"
                    onClick={(e) => handleDelete(img, e)}
                  >
                    🗑️ Xóa
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* LIGHTBOX */}
      {lightbox && (
        <div 
          className="ig-lightbox"
          onClick={() => setLightbox(null)}
        >
          <div className="ig-lightbox-actions">
            <button
              className="ig-lightbox-btn"
              title="Tải xuống"
              onClick={(e) => {
                e.stopPropagation();
                handleDownload(lightbox, e);
              }}
            >
              📥
            </button>
            <button 
              className="ig-lightbox-btn"
              onClick={(e) => {
                e.stopPropagation();
                setLightbox(null);
              }}
              title="Đóng"
            >
              ✕
            </button>
          </div>
          <img 
            src={lightbox.url || lightbox.path} 
            alt={lightbox.name}
            className="ig-lightbox-img"
            onClick={(e) => e.stopPropagation()}
          />
          <div 
            className="ig-lightbox-info"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ig-lightbox-name">{lightbox.name}</div>
            <div className="ig-lightbox-note">
              {lightbox.note || "(không có ghi chú)"}
            </div>
          </div>
        </div>
      )}

      {/* MODAL CHI TIẾT */}
      {selectedItem && (
        <div className="ig-modal" onClick={() => setSelectedItem(null)}>
          <div className="ig-modal-content" onClick={(e) => e.stopPropagation()}>
            <button 
              className="ig-modal-close"
              onClick={() => setSelectedItem(null)}
            >
              ✕
            </button>
            
            <img 
              src={selectedItem.url || selectedItem.path}
              alt={selectedItem.name}
              className="ig-modal-preview"
            />
            
            <div className="ig-modal-title">Chi tiết ảnh</div>
            
            <div className="ig-modal-field">
              <div className="ig-modal-label">TÊN ẢNH</div>
              <div className="ig-modal-value">{selectedItem.name}</div>
            </div>
            
            <div className="ig-modal-field">
              <div className="ig-modal-label">GHI CHÚ</div>
              <div className="ig-modal-value">
                {selectedItem.note || "(không có)"}
              </div>
            </div>

            <div className="ig-modal-actions">
              <button
                className="ig-modal-btn ig-modal-btn-download"
                onClick={(e) => handleDownload(selectedItem, e)}
              >
                📥 Tải xuống
              </button>
              <button
                className="ig-modal-btn ig-modal-btn-delete"
                onClick={(e) => {
                  setSelectedItem(null);
                  handleDelete(selectedItem, e);
                }}
              >
                🗑️ Xóa ảnh
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
