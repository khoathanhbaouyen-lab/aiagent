export default function FileGrid() {
  const data = props || {};
  const title = data.title || "Tai lieu";
  const initialItems = Array.isArray(data.files) ? data.files : [];
  const [items, setItems] = React.useState(initialItems);
  const [selectedItem, setSelectedItem] = React.useState(null);

  const getFileIcon = (type) => {
    const t = (type || "").toUpperCase();
    if (t.includes("PDF")) return "PDF";
    if (t.includes("EXCEL") || t.includes("XLS")) return "XLS";
    if (t.includes("WORD") || t.includes("DOC")) return "DOC";
    return "FILE";
  };

  const handleDownload = (file, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Thêm extension từ file path gốc vào filename
    let downloadName = file.name || 'download';
    const originalPath = file.file_path || file.path || file.url || '';
    const ext = originalPath.split('.').pop();
    if (ext && !downloadName.includes('.')) {
      downloadName = downloadName + '.' + ext;
    }
    
    const url = `http://localhost:8001/api/download-file?file_path=${encodeURIComponent(file.file_path)}&filename=${encodeURIComponent(downloadName)}`;
    console.log('Download:', downloadName, 'from', file.file_path);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadName;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDelete = async (file, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Xoa file "' + file.name + '"?')) return;
    try {
      const res = await fetch('http://localhost:8001/api/delete-file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ doc_id: file.doc_id, file_path: file.file_path })
      });
      if (res.ok) {
        setItems(prev => prev.filter(f => f.doc_id !== file.doc_id));
        alert('Da xoa thanh cong!');
      } else alert('Loi khi xoa');
    } catch (err) {
      alert('Khong the ket noi server');
    }
  };

  const openModal = (file, e) => {
    e.preventDefault();
    setSelectedItem(file);
  };

  return React.createElement('div', { className: 'fg-wrap' }, [
    React.createElement('style', { key: 's' }, `
      .fg-wrap { width: 100%; padding: 0; margin: 12px 0; }
      .fg-title { font-size: 18px; font-weight: 600; margin-bottom: 12px; color: #1f2937; }
      .fg-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
      .fg-card { background: white; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; transition: all 0.2s; display: flex; flex-direction: column; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
      .fg-card:hover { border-color: #3b82f6; box-shadow: 0 4px 12px rgba(59,130,246,0.15); transform: translateY(-2px); }
      .fg-icon-wrap { width: 100%; height: 140px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); cursor: pointer; position: relative; }
      .fg-icon { font-size: 32px; color: white; font-weight: bold; }
      .fg-info { padding: 12px; flex: 1; display: flex; flex-direction: column; }
      .fg-name { font-size: 13px; font-weight: 600; color: #1f2937; margin-bottom: 4px; cursor: pointer; }
      .fg-name:hover { color: #3b82f6; }
      .fg-note { font-size: 11px; color: #6b7280; flex: 1; margin-bottom: 8px; }
      .fg-actions { display: flex; gap: 8px; }
      .fg-btn { padding: 6px 12px; font-size: 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: white; cursor: pointer; transition: all 0.15s; }
      .fg-btn:hover { background: #f9fafb; }
      .fg-btn-download { color: #059669; border-color: #a7f3d0; }
      .fg-btn-download:hover { background: #d1fae5; }
      .fg-btn-delete { color: #dc2626; border-color: #fecaca; }
      .fg-btn-delete:hover { background: #fee2e2; }
      .fg-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px; }
      .fg-modal-content { background: white; border-radius: 16px; max-width: 500px; width: 100%; padding: 24px; position: relative; }
      .fg-modal-close { position: absolute; top: 16px; right: 16px; background: #f3f4f6; border: none; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; }
      .fg-modal-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #1f2937; }
      .fg-modal-field { margin-bottom: 12px; }
      .fg-modal-label { font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 4px; }
      .fg-modal-value { font-size: 14px; color: #1f2937; word-break: break-word; }
      .fg-modal-actions { display: flex; gap: 8px; margin-top: 20px; }
      .fg-modal-btn { flex: 1; padding: 10px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
      .fg-modal-btn-download { background: #10b981; color: white; }
      .fg-modal-btn-delete { background: #ef4444; color: white; }
    `),
    React.createElement('h3', { className: 'fg-title', key: 't' }, title),
    React.createElement('div', { className: 'fg-grid', key: 'g' },
      items.map((file, idx) =>
        React.createElement('div', { key: idx, className: 'fg-card' }, [
          React.createElement('div', { className: 'fg-icon-wrap', onClick: (e) => openModal(file, e), key: 'icon' },
            React.createElement('span', { className: 'fg-icon' }, getFileIcon(file.type))
          ),
          React.createElement('div', { className: 'fg-info', key: 'info' }, [
            React.createElement('div', { className: 'fg-name', onClick: (e) => openModal(file, e), key: 'name' }, file.name),
            React.createElement('div', { className: 'fg-note', key: 'note' }, file.note || "(không có ghi chú)"),
            React.createElement('div', { className: 'fg-actions', key: 'act' }, [
              React.createElement('button', { className: 'fg-btn fg-btn-download', onClick: (e) => handleDownload(file, e), key: 'dl' }, 'Tải'),
              React.createElement('button', { className: 'fg-btn fg-btn-delete', onClick: (e) => handleDelete(file, e), key: 'del' }, 'Xóa')
            ])
          ])
        ])
      )
    ),
    selectedItem && React.createElement('div', { className: 'fg-modal', onClick: () => setSelectedItem(null), key: 'm' },
      React.createElement('div', { className: 'fg-modal-content', onClick: (e) => e.stopPropagation() }, [
        React.createElement('button', { className: 'fg-modal-close', onClick: () => setSelectedItem(null), key: 'close' }, 'X'),
        React.createElement('div', { className: 'fg-modal-title', key: 'title' }, 'Chi tiết file'),
        React.createElement('div', { className: 'fg-modal-field', key: 'name' }, [
          React.createElement('div', { className: 'fg-modal-label', key: 'l' }, 'TEN FILE'),
          React.createElement('div', { className: 'fg-modal-value', key: 'v' }, selectedItem.name)
        ]),
        React.createElement('div', { className: 'fg-modal-field', key: 'note' }, [
          React.createElement('div', { className: 'fg-modal-label', key: 'l' }, 'GHI CHÚ'),
          React.createElement('div', { className: 'fg-modal-value', key: 'v' }, selectedItem.note || '(không có)')
        ]),
        React.createElement('div', { className: 'fg-modal-field', key: 'type' }, [
          React.createElement('div', { className: 'fg-modal-label', key: 'l' }, 'LOAI FILE'),
          React.createElement('div', { className: 'fg-modal-value', key: 'v' }, selectedItem.type || 'Unknown')
        ]),
        React.createElement('div', { className: 'fg-modal-actions', key: 'acts' }, [
          React.createElement('button', { className: 'fg-modal-btn fg-modal-btn-download', onClick: (e) => handleDownload(selectedItem, e), key: 'dl' }, 'Tải xuống'),
          React.createElement('button', { className: 'fg-modal-btn fg-modal-btn-delete', onClick: (e) => { setSelectedItem(null); handleDelete(selectedItem, e); }, key: 'del' }, 'Xóa file')
        ])
      ])
    )
  ]);
}
