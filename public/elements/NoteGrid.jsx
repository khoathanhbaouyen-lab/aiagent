// NoteGrid.jsx — CustomElement cho Chainlit 2.x
// Hiển thị grid các ghi chú với nút Edit/Delete/Detail

export default function NoteGrid() {
  // eslint-disable-next-line no-undef
  const data = props || {};
  const title = data.title || "📝 Ghi Chú";
  const notes = Array.isArray(data.notes) ? data.notes : [];

  if (!notes.length) {
    return <div className="border rounded-xl p-4 bg-muted/30 text-sm">Không có ghi chú nào.</div>;
  }

  const handleAction = (actionName, payload) => {
    // eslint-disable-next-line no-undef
    if (typeof onAction === 'function') {
      // eslint-disable-next-line no-undef
      onAction(actionName, payload);
    }
  };

  return (
    <div className="w-full my-3">
      <h2 className="text-base font-semibold mb-3">{title}</h2>

      {/* Grid layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {notes.map((note, i) => {
          const { doc_id, content, timestamp } = note;
          const previewContent = content.length > 150 ? content.substring(0, 150) + '...' : content;
          
          return (
            <div 
              key={i} 
              className="border rounded-xl p-4 bg-card shadow-sm hover:shadow-md transition-all hover:scale-[1.02]"
            >
              {/* Timestamp */}
              {timestamp && (
                <div className="text-xs text-muted-foreground mb-2">
                  {new Date(timestamp).toLocaleString('vi-VN')}
                </div>
              )}

              {/* Content Preview */}
              <div className="text-sm mb-3 whitespace-pre-wrap break-words">
                {previewContent}
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 mt-3 pt-3 border-t">
                <button
                  onClick={() => handleAction('show_note_detail', { doc_id })}
                  className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors"
                >
                  👁️ Chi tiết
                </button>
                
                <button
                  onClick={() => handleAction('edit_note', { doc_id, content })}
                  className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-amber-50 hover:bg-amber-100 text-amber-700 transition-colors"
                >
                  ✏️ Sửa
                </button>
                
                <button
                  onClick={() => {
                    if (confirm('Bạn có chắc muốn xóa ghi chú này?')) {
                      handleAction('delete_note', { doc_id });
                    }
                  }}
                  className="flex-1 px-3 py-1.5 text-xs font-medium rounded-md bg-red-50 hover:bg-red-100 text-red-700 transition-colors"
                >
                  🗑️ Xóa
                </button>
              </div>

              {/* Doc ID (hidden, for debugging) */}
              <div className="text-[10px] text-muted-foreground mt-2 opacity-50">
                ID: {doc_id.substring(0, 8)}...
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
