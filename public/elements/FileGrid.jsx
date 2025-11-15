export default function FileGrid() {
  const data = props || {};
  const title = data.title || "Files";
  const items = Array.isArray(data.files) ? data.files : [];
  
  return (
    <div style={{padding: "20px"}}>
      <h3>{title} ({items.length})</h3>
      <div style={{display: "grid", gap: "10px"}}>
        {items.map((f, i) => (
          <div key={i} style={{border: "1px solid #ddd", padding: "10px"}}>
            <div><strong>{f.name}</strong></div>
            <div style={{fontSize: "12px", color: "#666"}}>{f.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
