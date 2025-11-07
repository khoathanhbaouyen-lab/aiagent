// public/elements/ProductGrid.jsx
// No external libs. Works without Tailwind.

export default function ProductGrid() {
  /* global props, React */
  const { useState, useEffect } = React;
  const data = props || {};
  const title = data.title || "Kết quả";
  const items = Array.isArray(data.products) ? data.products : [];
  // 👉 THÊM 2 DÒNG NÀY Ở ĐÂY
  const cols = Math.min(items.length || 0, 3); // tối đa 3 cột
  const gridClass = `pg-grid pg-cols-${cols || 1}`;
  const [openIdx, setOpenIdx] = useState(null);
  const [tab, setTab] = useState("desc");

  const Html = ({ html }) =>
    html ? <div className="pg-prose" dangerouslySetInnerHTML={{ __html: html }} /> : null;

  const close = () => {
    setOpenIdx(null);
    setTab("desc");
  };

  // Khóa scroll nền khi mở modal
  useEffect(() => {
    if (openIdx !== null) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = prev; };
    }
  }, [openIdx]);

  // ================== VIDEO RENDERER (force our own iframe) ==================
const renderVideo = (raw) => {
  if (!raw) return null;
  const val = String(raw).trim();

  // 1) Tách URL từ <iframe ... src="..."> (nếu là HTML Quill/khác)
  const iframeSrcFromHtml = () => {
    const m = val.match(/<iframe[^>]+src=["']([^"']+)["']/i);
    return m ? m[1] : null;
  };

  // 2) Chuẩn hoá YouTube -> embed URL
  const toYoutubeEmbed = (url) => {
    try {
      const u = new URL(url);
      const host = u.hostname.replace(/^www\./, "");
      let id = null;

      if (host === "youtu.be") {
        id = u.pathname.slice(1);
      } else if (host.includes("youtube.com")) {
        if (u.pathname.startsWith("/watch") && u.searchParams.get("v")) id = u.searchParams.get("v");
        else if (u.pathname.startsWith("/embed/")) id = u.pathname.split("/")[2];
        else if (u.pathname.startsWith("/shorts/")) id = u.pathname.split("/")[2];
      }
      if (!id) return null;

      // các param nhẹ gọn để tránh UI rác
      const params = new URLSearchParams({
        rel: "0",
        modestbranding: "1",
        controls: "1",
      });
      return `https://www.youtube.com/embed/${id}?${params.toString()}`;
    } catch {
      return null;
    }
  };

  // 3) Lấy URL gốc (từ HTML hoặc chuỗi URL thuần)
  const urlFromValue = () => {
    // nếu là HTML có iframe
    const fromHtml = iframeSrcFromHtml();
    if (fromHtml) return fromHtml;

    // nếu là URL thuần
    try {
      const u = new URL(val);
      return u.href;
    } catch {
      return null;
    }
  };

  let src = null;

  // Ưu tiên: nếu là YouTube -> ép về embed
  const candidate = urlFromValue();
  const yt = candidate ? toYoutubeEmbed(candidate) : null;
  if (yt) src = yt;
  else if (candidate) src = candidate;

  // 4) Nếu là file video trực tiếp
  if (!src) {
    const lower = val.toLowerCase();
    if (lower.endsWith(".mp4") || lower.endsWith(".webm") || lower.endsWith(".ogg")) {
      return (
        <div className="pg-vwrap">
          <video className="pg-video" src={val} controls preload="metadata" />
        </div>
      );
    }
  }

  // 5) Có src thì render iframe “chuẩn” của mình (không dùng HTML gốc)
  if (src) {
    return (
      <div className="pg-vwrap">
        <iframe
          className="pg-iframe"
          src={src}
          title="Video"
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
    );
  }

  // 6) Không nhận diện được → link dự phòng
  return (
    <div>
      <a className="pg-a" href={val} target="_blank" rel="noopener noreferrer">Xem video</a>
    </div>
  );
};
// ===========================================================================


  // ====================================================

  return (
    <div className="pg-wrap">
      <h2 className="pg-title">{title}</h2>

      <div className={gridClass}>
        {items.map((it, idx) => (
          <div key={idx} className="pg-card" onClick={() => setOpenIdx(idx)}>
            {it.image ? (
              <div className="pg-imgwrap">
                <img className="pg-img" src={it.image} alt={it.item_name || "Sản phẩm"} loading="lazy" />
              </div>
            ) : null}

            <div className="pg-name">{it.item_name || `Sản phẩm ${idx + 1}`}</div>
            {it.category ? <div className="pg-cat">{it.category}</div> : null}
            {it.item_code ? <div className="pg-code">{it.item_code}</div> : <div style={{height: 12}} />}

            <div className="pg-actions" onClick={(e)=>e.stopPropagation()}>
              <button className="pg-btn" onClick={() => setOpenIdx(idx)}>Xem chi tiết</button>
              {it.url ? (
                <a className="pg-link" href={it.url} target="_blank" rel="noopener noreferrer">Mở trang</a>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      {openIdx !== null && items[openIdx] && (
        <div className="pg-overlay" onClick={close}>
          <div className="pg-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="pg-head">
              {items[openIdx].image ? (
                <img
                  src={items[openIdx].image}
                  alt={items[openIdx].item_name || "Sản phẩm"}
                  className="pg-headimg"
                />
              ) : null}

              <div className="pg-headinfo">
                <div className="pg-headname">{items[openIdx].item_name || `Sản phẩm ${openIdx + 1}`}</div>
                {items[openIdx].item_code ? (
                  <div className="pg-headcode">{items[openIdx].item_code}</div>
                ) : null}
                {items[openIdx].category ? (
                  <div className="pg-headcat">{items[openIdx].category}</div>
                ) : null}
              </div>

              <button className="pg-close" onClick={close}>Đóng</button>
            </div>

            {/* Tabs */}
            <div className="pg-tabs">
              <button className={`pg-tab ${tab==="desc"?"is-active":""}`} onClick={()=>setTab("desc")}>Mô tả</button>
              {items[openIdx].advantages ? (
                <button className={`pg-tab ${tab==="adv"?"is-active":""}`} onClick={()=>setTab("adv")}>Ưu điểm</button>
              ) : null}
              {items[openIdx].specifications ? (
                <button className={`pg-tab ${tab==="spec"?"is-active":""}`} onClick={()=>setTab("spec")}>Thông số</button>
              ) : null}
              {items[openIdx].video ? (
                <button className={`pg-tab ${tab==="video"?"is-active":""}`} onClick={()=>setTab("video")}>Video</button>
              ) : null}
              {items[openIdx].url ? (
                <a className="pg-tablink" href={items[openIdx].url} target="_blank" rel="noopener noreferrer">
                  Trang chi tiết
                </a>
              ) : null}
            </div>

            <div className="pg-body">
              {tab === "desc" && (
                <section>
                  <b>Mô tả:</b>
                  <Html html={items[openIdx].description} />
                </section>
              )}
              {tab === "adv" && items[openIdx].advantages && (
                <section>
                  <b>Ưu điểm:</b>
                  <Html html={items[openIdx].advantages} />
                </section>
              )}
              {tab === "spec" && items[openIdx].specifications && (
                <section>
                  <b>Thông số:</b>
                  <Html html={items[openIdx].specifications} />
                </section>
              )}
              {tab === "video" && items[openIdx].video && (
                <section>
                  <b>Video:</b>
                  {renderVideo(items[openIdx].video)}
                </section>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Pure CSS, no Tailwind needed */}
      <style>{`
        .pg-wrap { width: 100%; margin: 8px 0; }
        .pg-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; }

        /* GRID */
        .pg-grid{
        --pg-cols: 3; /* default */
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(var(--pg-cols), minmax(0, 1fr));
        }

        /* Tự set số cột theo class đã tính ở JS */
        .pg-cols-1{ --pg-cols: 1; max-width: 560px; margin: 0 auto; }
        .pg-cols-2{ --pg-cols: 2; max-width: 900px; margin: 0 auto; }
        .pg-cols-3{ --pg-cols: 3; }

        /* Mobile vẫn 1 cột cho dễ nhìn */
        @media (max-width: 640px){
        .pg-grid{ --pg-cols: 1; max-width: 100%; }
        }

        /* CARD */
        .pg-card {
          border: 1px solid #e5e7eb;
          border-radius: 14px;
          padding: 10px;
          background: var(--pg-card, #fff);
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
          transition: box-shadow .15s ease;
          cursor: pointer;
          display: flex; flex-direction: column;
        }
        .pg-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.08); }

        .pg-imgwrap { width: 100%; height: 112px; display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
        @media (min-width: 768px){ .pg-imgwrap { height: 112px; } }
        .pg-img { max-height: 100%; max-width: 100%; object-fit: contain; }

        .pg-name {
          font-size: 13px; font-weight: 600; line-height: 1.35; margin-bottom: 2px;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
          min-height: 35px;
          flex: 1 1 auto;
        }
        .pg-cat { font-size: 11px; opacity: .65; }
        .pg-code { font-size: 12px; font-weight: 700; color: #16a34a; }

        .pg-actions { margin-top: 8px; display: flex; gap: 8px; }
        .pg-btn { padding: 6px 10px; font-size: 12px; border-radius: 10px; color: #fff; background: #16a34a; border: 0; }
        .pg-btn:hover { opacity: .9; }
        .pg-link { padding: 6px 10px; font-size: 12px; border-radius: 10px; border: 1px solid #e5e7eb; text-decoration: none; color: inherit; }
        .pg-link:hover { background: #f6f7f9; }
        
        .pg-cols-2 .pg-imgwrap{ height: 160px; }
        .pg-cols-1 .pg-imgwrap{ height: 220px; }

        /* Khi chỉ có 1 sản phẩm: chữ to hơn 1 chút */
        .pg-cols-1 .pg-name{ font-size: 14px; }
        .pg-cols-1 .pg-card{ padding: 14px; }
        /* MODAL */
        .pg-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; z-index: 9999; }
        .pg-modal {
          background: #fff; width: min(92vw, 860px); max-height: 85vh; overflow: hidden;
          border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.2);
          display: flex; flex-direction: column;
        }
        .pg-head { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; padding: 16px 18px 8px; align-items: start; }
        @media (max-width: 640px){ .pg-head { grid-template-columns: 1fr auto; } }
        .pg-headimg { width: 140px; max-height: 110px; object-fit: contain; }
        .pg-headinfo { min-width: 0; }
        .pg-headname { font-size: 16px; font-weight: 600; }
        .pg-headcode { font-size: 13px; font-weight: 700; color: #16a34a; }
        .pg-headcat { font-size: 12px; opacity: .7; }
        .pg-close { margin-left: auto; padding: 6px 10px; border-radius: 10px; border: 1px solid #e5e7eb; background: #fff; }

        .pg-tabs { display: flex; gap: 8px; padding: 6px 18px 10px; flex-wrap: wrap; }
        .pg-tab, .pg-tablink {
          font-size: 12px; padding: 6px 8px; border-radius: 8px; border: 1px solid #e5e7eb; background: #fff;
          cursor: pointer; text-decoration: none; color: inherit;
        }
        .pg-tab.is-active { background: #111; color: #fff; border-color: #111; }
        .pg-tablink:hover, .pg-tab:hover { background: #f6f7f9; }

        .pg-body { padding: 0 18px 16px; overflow: auto; }
        .pg-prose table { border-collapse: collapse; width: 100%; }
        .pg-prose th, .pg-prose td { border: 1px solid #ddd; padding: 4px; text-align: left; }
        .pg-prose ul { padding-left: 20px; margin: 0; }
        .pg-prose p { margin: 4px 0; }
        .pg-a { color: #2563eb; text-decoration: underline; }

        /* VIDEO area - responsive 16:9 */
        .pg-vwrap {
          position: relative; width: 100%;
          aspect-ratio: 16 / 9;
          background: #000;
          border-radius: 10px; overflow: hidden; margin-top: 6px;
        }
        .pg-iframe, .pg-video {
          position: absolute; inset: 0; width: 100%; height: 100%;
          border: 0; display: block;
        }
      `}</style>
    </div>
  );
}
