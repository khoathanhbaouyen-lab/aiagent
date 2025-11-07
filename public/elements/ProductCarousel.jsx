// ProductCarousel.jsx — CustomElement cho Chainlit 2.x
// Không dùng @chainlit/react-client; props được inject GLOBAL.

function HtmlContent({ html }) {
  if (!html) return null;
  return <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: html }} />;
}

export default function ProductCarousel() {
  // eslint-disable-next-line no-undef
  const data = props || {};
  const title = data.title || "Kết quả:";
  const products = Array.isArray(data.products) ? data.products : [];

  if (!products.length) {
    return <div className="border rounded-xl p-4 bg-muted/30 text-sm">Không có dữ liệu sản phẩm.</div>;
  }

  return (
    <div className="w-full my-3">
      <h2 className="text-base font-semibold mb-3">{title}</h2>

      {/* Hàng ngang cuộn được */}
      <div className="flex gap-4 overflow-x-auto pb-2">
        {products.map((p, i) => {
          const item = p || {};
          return (
            <div key={i} className="min-w-[360px] max-w-[380px] border rounded-2xl p-4 bg-card shadow-sm">
              {/* Ảnh */}
              {item.image && (
                <div className="w-full flex justify-center mb-3">
                  <img
                    src={item.image}
                    alt={item.item_name || "Sản phẩm"}
                    className="max-h-28 object-contain"
                    loading="lazy"
                  />
                </div>
              )}

              {/* Tiêu đề + danh mục */}
              <div className="mb-1">
                <div className="text-[15px] font-semibold">{item.item_name || "Sản phẩm"}</div>
                {item.category ? (
                  <div className="text-xs opacity-70">{item.category}</div>
                ) : null}
              </div>

              {/* Mã hàng màu xanh */}
              {item.item_code ? (
                <div className="text-sm font-bold text-green-600 mb-3">{item.item_code}</div>
              ) : <div className="h-3" />}

              {/* Tóm tắt ngắn (nếu có) – tự cắt bớt bằng maxHeight */}
              {item.summary && (
                <div
                  className="text-sm opacity-80 mb-3"
                  style={{ maxHeight: 64, overflow: "hidden" }}
                  dangerouslySetInnerHTML={{ __html: item.summary }}
                />
              )}

              <div className="flex items-center gap-2">
                {/* Nút xem chi tiết → Dialog */}
                <details className="group">
                  <summary className="list-none">
                    <button className="px-3 py-1.5 rounded-xl text-white bg-green-600 text-sm hover:opacity-90">
                      Xem chi tiết
                    </button>
                  </summary>

                  {/* Nội dung chi tiết (mở trong <details>) */}
                  <div className="mt-3 border rounded-xl p-3 bg-muted/20">
                    {/* Tabs đơn giản bằng anchors */}
                    <div className="flex gap-2 text-xs mb-2">
                      <a href="#tab-desc" className="underline">Mô tả</a>
                      {item.advantages ? <a href="#tab-adv" className="underline">Ưu điểm</a> : null}
                      {item.specifications ? <a href="#tab-spec" className="underline">Thông số</a> : null}
                      {item.video ? <a href="#tab-video" className="underline">Video</a> : null}
                      {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="underline">Trang chi tiết</a> : null}
                    </div>

                    <div id="tab-desc">
                      <b>Mô tả:</b>
                      <HtmlContent html={item.description} />
                    </div>

                    {item.advantages && (
                      <div id="tab-adv" className="mt-2">
                        <b>Ưu điểm:</b>
                        <HtmlContent html={item.advantages} />
                      </div>
                    )}

                    {item.specifications && (
                      <div id="tab-spec" className="mt-2">
                        <b>Thông số:</b>
                        <HtmlContent html={item.specifications} />
                      </div>
                    )}

                    {item.video && (
                      <div id="tab-video" className="mt-2">
                        <b>Video:</b><br />
                        <a className="text-primary underline" href={item.video} target="_blank" rel="noopener noreferrer">
                          Xem video
                        </a>
                      </div>
                    )}
                  </div>
                </details>

                {/* Link ngoài (tùy chọn) */}
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-xl text-sm border hover:bg-muted"
                  >
                    Mở trang
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* CSS nhỏ cho nội dung HTML bên trong */}
      <style>{`
        .prose table { border-collapse: collapse; width: 100%; }
        .prose th, .prose td { border: 1px solid #ddd; padding: 4px; text-align: left; }
        .prose ul { padding-left: 20px; margin: 0; }
        .prose p { margin: 4px 0; }
      `}</style>
    </div>
  );
}
