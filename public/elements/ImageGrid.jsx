export default function ImageGrid() {
  const data = props || {};
  const title = data.title || "Hinh anh";
  const initialItems = Array.isArray(data.images) ? data.images : [];
  const [items, setItems] = React.useState(initialItems);
  const [lightbox, setLightbox] = React.useState(null);

  const handleDownload = (img, e) => {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    
    const filePath = img.file_path || img.path || img.url;
    
    // Thêm extension từ file path gốc vào filename
    let downloadName = img.name || 'download';
    const originalPath = img.file_path || img.path || img.url || '';
    const ext = originalPath.split('.').pop();
    if (ext && !downloadName.includes('.')) {
      downloadName = downloadName + '.' + ext;
    }
    
    const url = `http://localhost:8001/api/download-file?file_path=${encodeURIComponent(filePath)}&filename=${encodeURIComponent(downloadName)}`;
    console.log('Download:', downloadName, 'from', filePath);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadName;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDelete = async (img, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Xoa anh "' + img.name + '"?')) return;
    try {
      const res = await fetch('http://localhost:8001/api/delete-file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ doc_id: img.doc_id, file_path: img.file_path || img.path })
      });
      if (res.ok) {
        setItems(prev => prev.filter(i => i.doc_id !== img.doc_id));
        setLightbox(null);
        alert('Da xoa thanh cong!');
      } else alert('Loi khi xoa');
    } catch (err) {
      alert('Khong the ket noi server');
    }
  };

  return React.createElement('div', { style: { width: '100%', padding: '12px 0' } }, [
    React.createElement('style', { key: 's' }, `
      .ig-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
      .ig-card { background: white; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; transition: all 0.2s; cursor: pointer; }
      .ig-card:hover { border-color: #3b82f6; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(59,130,246,0.15); }
      .ig-img { width: 100%; height: 180px; object-fit: cover; }
      .ig-info { padding: 12px; }
      .ig-name { font-size: 13px; font-weight: 600; color: #1f2937; margin-bottom: 4px; }
      .ig-note { font-size: 11px; color: #6b7280; margin-bottom: 8px; }
      .ig-actions { display: flex; gap: 8px; }
      .ig-btn { padding: 6px 12px; font-size: 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: white; cursor: pointer; }
      .ig-btn:hover { background: #f9fafb; }
      .ig-btn-download { color: #059669; border-color: #a7f3d0; }
      .ig-btn-delete { color: #dc2626; border-color: #fecaca; }
      .ig-lightbox { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.9); z-index: 9999; display: flex; align-items: center; justify-content: center; }
      .ig-lightbox img { max-width: 90%; max-height: 90%; }
      .ig-lightbox-close { position: absolute; top: 20px; right: 20px; background: white; border: none; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; font-size: 20px; }
      .ig-lightbox-actions { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); display: flex; gap: 12px; }
      .ig-lightbox-btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
      .ig-lightbox-btn-download { background: #10b981; color: white; }
      .ig-lightbox-btn-delete { background: #ef4444; color: white; }
    `),
    React.createElement('h3', { style: { fontSize: '18px', fontWeight: 600, marginBottom: '12px', color: '#1f2937' }, key: 't' }, title),
    React.createElement('div', { className: 'ig-grid', key: 'g' },
      items.map((img, idx) => {
        const imgUrl = img.url || img.path || img.file_path;
        return React.createElement('div', { key: idx, className: 'ig-card', onClick: () => setLightbox(img) }, [
          React.createElement('img', { src: imgUrl, className: 'ig-img', key: 'img' }),
          React.createElement('div', { className: 'ig-info', key: 'info' }, [
            React.createElement('div', { className: 'ig-name', key: 'name' }, img.name),
            React.createElement('div', { className: 'ig-note', key: 'note' }, img.note || '(không có ghi chú)'),
            React.createElement('div', { className: 'ig-actions', key: 'act' }, [
              React.createElement('button', { className: 'ig-btn ig-btn-download', onClick: (e) => handleDownload(img, e), key: 'dl' }, 'Tải'),
              React.createElement('button', { className: 'ig-btn ig-btn-delete', onClick: (e) => handleDelete(img, e), key: 'del' }, 'Xóa')
            ])
          ])
        ]);
      })
    ),
    lightbox && React.createElement('div', { className: 'ig-lightbox', onClick: () => setLightbox(null), key: 'lb' }, [
      React.createElement('button', { className: 'ig-lightbox-close', onClick: () => setLightbox(null), key: 'close' }, 'X'),
      React.createElement('img', { src: lightbox.url || lightbox.path || lightbox.file_path, onClick: (e) => e.stopPropagation(), key: 'img' }),
      React.createElement('div', { className: 'ig-lightbox-actions', key: 'acts' }, [
        React.createElement('button', { className: 'ig-lightbox-btn ig-lightbox-btn-download', onClick: () => handleDownload(lightbox), key: 'dl' }, 'Tải xuống'),
        React.createElement('button', { className: 'ig-lightbox-btn ig-lightbox-btn-delete', onClick: (e) => handleDelete(lightbox, e), key: 'del' }, 'Xóa ảnh')
      ])
    ])
  ]);
}
