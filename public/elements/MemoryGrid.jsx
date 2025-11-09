// public/elements/MemoryGrid.jsx
// (PHIÊN BẢN V7.1 - Sau khi bấm XÓA thì ẩn luôn item khỏi lưới)

export default function MemoryGrid() {
  /* global props, React */
  const { useState, useEffect, useContext } = React;

  // Modal đang mở item index nào
  const [openIdx, setOpenIdx] = useState(null);

  // Lấy context của Chainlit
  const context = useContext(window.ChainlitContext);
  const sendAction = context ? context.sendAction : null;

  const data = props || {};
  const title = data.title || "Bộ nhớ";
  const items = Array.isArray(data.items) ? data.items : [];

  // --- STATE LOCAL CHO LIST ITEM (để xóa khỏi UI) ---
  const [itemsState, setItemsState] = useState(items);

  // Khi props.items thay đổi (server gửi lại), sync vào state
  useEffect(() => {
    setItemsState(items);
  }, [items]);

  const close = () => {
    setOpenIdx(null);
  };

  // Khóa scroll nền khi mở modal
  useEffect(() => {
    if (openIdx !== null) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [openIdx]);

  // Lấy item đang được chọn từ state local
  const currentItem =
    openIdx !== null && itemsState[openIdx] ? itemsState[openIdx] : null;

  // Hàm xử lý khi bấm nút (Xóa, Xem chi tiết, ...)
  const handleActionClick = (e, action) => {
    e.preventDefault();
    e.stopPropagation();

    if (action.is_link) {
      // Các nút kiểu mở link (Xem file, mở web, v.v.)
      if (action.payload && action.payload.url) {
        window.open(action.payload.url, "_blank");
      }
      close();
    } else {
      if (sendAction) {
        // Gửi action về server
        sendAction(action.name, action.payload);

        // Nếu là action kiểu "Xóa / Hủy" thì xóa luôn item khỏi UI
        const label = (action.label || "").toLowerCase();
        const name = (action.name || "").toLowerCase();
        const isDeleteLike =
          name.startsWith("delete") ||
          label.includes("xóa") ||
          label.includes("hủy");

        if (isDeleteLike && openIdx !== null) {
          setItemsState((prev) =>
            prev.filter((_, idx) => idx !== openIdx)
          );
        }

        close();
      } else {
        console.error("Lỗi: Nút được bấm nhưng sendAction chưa sẵn sàng!");
        alert("Lỗi: Giao diện chưa sẵn sàng. Vui lòng F5 và thử lại.");
      }
    }
  };

  // Chọn màu nút (Xanh/Đỏ/Xám)
  const getButtonClass = (label) => {
    const lbl = (label || "").toLowerCase();
    if (lbl.includes("xóa") || lbl.includes("hủy")) {
      return "mg-btn mg-btn-danger"; // Nút Đỏ
    }
    if (lbl.includes("xem") || lbl.includes("mở") || lbl.includes("chi tiết")) {
      return "mg-btn mg-btn-primary"; // Nút Xanh
    }
    return "mg-btn mg-btn-secondary"; // Nút Xám
  };

  return (
    <div className="mg-wrap">
      <h2 className="mg-title">{title}</h2>

      {/* 1. GRID 3/2/1 CARD */}
      <div className="mg-grid">
        {itemsState.map((it, idx) => (
          <div
            key={it.id || idx}
            className="mg-card"
            onClick={() => setOpenIdx(idx)}
          >
            {/* Ảnh / Icon */}
            {it.image_url ? (
              <div className="mg-img-wrap">
                <img
                  className="mg-img"
                  src={it.image_url}
                  alt={it.title}
                  loading="lazy"
                />
              </div>
            ) : (
              <div className="mg-img-wrap mg-icon-wrap">
                <span className="mg-icon">{it.icon || "🗂️"}</span>
              </div>
            )}

            {/* Thông tin */}
            <div className="mg-info">
              <div className="mg-name">{it.title || `Mục ${idx + 1}`}</div>
              {it.content_preview ? (
                <div className="mg-note">{it.content_preview}</div>
              ) : (
                <div style={{ height: 12 }} />
              )}

              {/* Chỉ 1 nút "Xem chi tiết" trên card */}
              <div className="mg-actions-placeholder">
                <button
                  className="mg-btn mg-btn-primary"
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenIdx(idx);
                  }}
                >
                  Xem chi tiết
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 2. MODAL POPUP */}
      {currentItem && (
        <div className="mg-overlay" onClick={close}>
          <div className="mg-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header (Ảnh/Icon + Đóng) */}
            <div className="mg-head">
              {currentItem.image_url ? (
                <div className="mg-modal-img-wrap">
                  <img
                    className="mg-modal-img"
                    src={currentItem.image_url}
                    alt={currentItem.title}
                  />
                </div>
              ) : (
                <div className="mg-modal-img-wrap mg-modal-icon-wrap">
                  <span className="mg-icon">
                    {currentItem.icon || "🗂️"}
                  </span>
                </div>
              )}
              <button className="mg-close" onClick={close}>
                Đóng
              </button>
            </div>

            {/* Body + Nút action thật */}
            <div className="mg-body">
              <div className="mg-modal-name">{currentItem.title}</div>
              <div className="mg-modal-note">
                {currentItem.content_preview}
              </div>

              <div className="mg-modal-actions">
                {Array.isArray(currentItem.actions) &&
                  currentItem.actions.map((act, actIdx) => (
                    <button
                      key={actIdx}
                      className={getButtonClass(act.label)}
                      onClick={(e) => handleActionClick(e, act)}
                    >
                      {act.label}
                    </button>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CSS giữ nguyên như bản V7 của anh */}
      <style>{`
        .mg-wrap { 
          width: 100%; margin: 8px 0; 
        }
        .mg-title { 
          font-size: 16px; font-weight: 600; margin-bottom: 10px; 
        }
        .mg-grid {
          display: grid; gap: 16px;
          grid-template-columns: repeat(3, 1fr);
        }
        @media (max-width: 1024px) {
          .mg-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 640px) {
          .mg-grid { grid-template-columns: 1fr; }
        }
        .mg-card {
          border: 1px solid #e5e7eb; border-radius: 14px;
          background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
          transition: box-shadow .15s ease;
          display: flex; flex-direction: column;
          overflow: hidden; cursor: pointer;
        }
        .mg-card:hover { 
          box-shadow: 0 4px 14px rgba(0,0,0,0.08); 
        }
        .mg-img-wrap {
          width: 100%; height: 160px; 
          display: flex; align-items: center; justify-content: center;
          background: #f8f9fa;
        }
        .mg-img {
          width: 100%; height: 100%; object-fit: contain; 
        }
        .mg-icon-wrap { height: 112px; }
        .mg-icon { font-size: 48px; opacity: 0.5; }
        .mg-info {
          padding: 10px; display: flex;
          flex-direction: column; flex-grow: 1;
        }
        .mg-name {
          font-size: 13px; font-weight: 600; line-height: 1.35;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .mg-note { 
          font-size: 11px; opacity: .65; margin-top: 2px;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .mg-actions-placeholder {
          margin-top: 10px;
          display: grid;
        }

        .mg-btn {
          padding: 7px 10px; font-size: 12px;
          font-weight: 500; border-radius: 10px;
          border: 0; cursor: pointer;
          transition: opacity .15s ease;
        }
        .mg-btn:hover { opacity: .9; }
        .mg-btn-primary { background: #16a34a; color: #fff; }
        .mg-btn-danger { background: #dc2626; color: #fff; }
        .mg-btn-secondary { background: #e5e7eb; color: #374151; }

        .mg-overlay { 
          position: fixed; inset: 0; background: rgba(0,0,0,0.4); 
          display:flex; align-items:center; justify-content:center; 
          z-index: 9999;
        }
        .mg-modal {
          background: #fff; 
          width: min(92vw, 480px);
          max-height: 85vh; overflow: hidden;
          border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
          display: flex; flex-direction: column;
        }
        .mg-head {
          padding: 12px 12px 0;
          display: flex; justify-content: flex-end;
          position: relative;
        }
        .mg-modal-img-wrap {
          position: absolute; top: 0; left: 0; right: 0;
          width: 100%; height: 200px;
          background: #f8f9fa; display: flex;
          align-items: center; justify-content: center;
          border-bottom: 1px solid #e5e7eb;
        }
        .mg-modal-img {
          width: 100%; height: 100%; object-fit: contain;
        }
        .mg-modal-icon-wrap { height: 120px; border: 0; }
        .mg-close {
          border-radius: 99px; border: 1px solid #e5e7eb; 
          background: #fff; padding: 4px;
          cursor: pointer; z-index: 10;
          line-height: 1;
        }
        .mg-body {
          margin-top: 200px;
          padding: 16px;
        }
        .mg-modal-icon-wrap + .mg-body {
          margin-top: 120px;
        }
        .mg-modal-name {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 6px;
        }
        .mg-modal-note {
          font-size: 13px;
          opacity: .75;
          white-space: pre-wrap;
        }
        .mg-modal-actions {
          margin-top: 14px;
          display: flex; flex-wrap: wrap;
          gap: 8px;
        }
      `}</style>
    </div>
  );
}
