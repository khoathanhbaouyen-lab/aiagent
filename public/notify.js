// public/notify.js  — clean version
(function () {
  const LOG = (...a) => console.log("[notify.js]", ...a);

  // === 1) Quyền Notification ==============================================
  async function ensurePermission() {
    try {
      if (!("Notification" in window)) return "no-support";
      if (Notification.permission === "granted") return "granted";
      return await Notification.requestPermission();
    } catch (e) {
      LOG("permission error:", e);
      return "error";
    }
  }

  // === 2) Beep ngắn ========================================================
  function beep() {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      g.gain.value = 0.04;
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start();
      setTimeout(() => {
        osc.stop();
        ctx.close();
      }, 700);
    } catch {}
  }

  // === 3) System notification + in-page toast (fallback) ==================
  async function notify(title, body) {
    // 1) System notification (nếu được phép)
    let usedSystem = false;
    try {
      if ("Notification" in window) {
        if (Notification.permission !== "granted") {
          const r = await Notification.requestPermission();
          if (r === "granted") {
            new Notification(title, { body, requireInteraction: true });
            usedSystem = true;
          }
        } else {
          new Notification(title, { body, requireInteraction: true });
          usedSystem = true;
        }
      }
    } catch {}

    // 2) In-page toast (luôn hiện, phòng OS chặn)
    try {
      const toast = document.createElement("div");
      toast.style.position = "fixed";
      toast.style.right = "20px";
      toast.style.bottom = "20px";
      toast.style.zIndex = "999999";
      toast.style.maxWidth = "340px";
      toast.style.padding = "14px 16px";
      toast.style.borderRadius = "12px";
      toast.style.boxShadow = "0 8px 30px rgba(0,0,0,.25)";
      toast.style.backdropFilter = "blur(6px)";
      toast.style.background = "rgba(20,20,28,.92)";
      toast.style.color = "#fff";
      toast.style.fontFamily = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
      toast.style.lineHeight = "1.35";
      toast.style.cursor = "pointer";

      toast.innerHTML =
        `<div style="font-weight:700; margin-bottom:6px;">${title}</div>` +
        `<div style="white-space:pre-wrap">${body}</div>` +
        `<div style="margin-top:10px; font-size:12px; opacity:.7">` +
        (usedSystem ? "Also sent to system tray" : "Screen popup (fallback)") +
        `</div>`;

      toast.addEventListener("click", () => toast.remove());
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 12000);
    } catch {}

    // 3) Beep
    beep();
  }

  // === 4) Helpers ==========================================================
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  function uniqLines(lines) {
    const seen = new Set();
    const out = [];
    for (const raw of lines || []) {
      const s = (raw || "").replace(/\s+/g, " ").trim();
      if (!s || seen.has(s)) continue;
      seen.add(s);
      out.push(s);
    }
    return out;
  }
  function isReminderText(text) {
    const t = norm(text);
    return (
      t.includes("đã đến giờ:") ||
      t.includes("da den gio:") ||
      t.includes("nhắc việc") ||
      t.includes("nhac viec") ||
      t.includes("⏰")
    );
  }
  function extractTextFromNode(node) {
    try {
      return (node.innerText || node.textContent || "").trim();
    } catch {
      return "";
    }
  }

  // === 5) Rút nội dung gọn + chống trùng ================================
  // RÚT GỌN: chỉ hiện nội dung nhắc + 1 status đầu tiên (nếu có)
const lastToast = { hash: null, ts: 0 };

function fireIfReminder(fullText) {
  if (!fullText) return;

  // Chỉ bắn khi có “ĐÃ ĐẾN GIỜ”
  const tnorm = (fullText || "").toLowerCase().replace(/\s+/g, " ").trim();
  if (!/đ[ãa]\s*đến\s*giờ/.test(tnorm)) return;

  // 1) Lấy task sau “ĐÃ ĐẾN GIỜ:”
  const mTask = /đ[ãa]\s*đến\s*giờ[:：]?\s*\**\s*([^\n]+)/i.exec(fullText);
  const task = mTask ? mTask[1].replace(/[*_`~]/g, "").trim() : "";

  // 2) Lấy đúng 1 status đầu tiên (nếu có)
  const mStatus = /status\s*=?\s*(\d+)/i.exec(fullText);
  const status = mStatus ? `status=${mStatus[1]}` : "";

  // 3) Body gọn
  const parts = [];
  if (task) parts.push(task);
  if (status) parts.push(status);
  const body = parts.join(" • ").slice(0, 180);

  // 4) Debounce 5s theo hash để không bắn trùng
  const title = "⏰ Đến giờ nhắc việc";
  const hash = title + "|" + body;
  const now = Date.now();
  if (hash === lastToast.hash && now - lastToast.ts < 5000) return;
  lastToast.hash = hash;
  lastToast.ts = now;

  console.log("[notify.js] Detected reminder →", body);
  notify(title, body); // system notification + in-page toast + beep
}


  // === 6) Quan sát message mới + quét ban đầu ============================
  function scanExisting() {
    const nodes = document.querySelectorAll('[data-cy="messages-container"] *');
    let found = 0;
    nodes.forEach((n) => {
      const t = extractTextFromNode(n);
      if (isReminderText(t)) {
        found++;
        fireIfReminder(t);
      }
    });
    LOG("Initial scan, found =", found);
  }

  function setupObserver() {
    const root =
      document.querySelector('[data-cy="messages-container"]') || document.body;
    const seen = new WeakSet();

    const ob = new MutationObserver((muts) => {
      muts.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          if (seen.has(node)) return;
          seen.add(node);
          const t = extractTextFromNode(node);
          if (t) fireIfReminder(t);
        });
      });
    });
    ob.observe(root, { childList: true, subtree: true });
    LOG("observer started");
  }

  // === 7) Boot ============================================================
  (async () => {
    LOG("permission:", await ensurePermission());
    scanExisting();
    setupObserver();
    LOG("ready");
  })();
})();
