// public/notify.js  — Firebase Cloud Messaging + Browser Notifications
(function () {
  const LOG = (...a) => console.log("[notify.js]", ...a);
  
  // === 0) Firebase Cloud Messaging Setup ===============================
  let fcmToken = null;
  
  async function initFirebase() {
    try {
      // Check if Firebase is available
      if (typeof firebase === 'undefined') {
        LOG('⚠️ Firebase SDK not loaded');
        return;
      }

      // Firebase config
      const firebaseConfig = {
        apiKey: "AIzaSyARg7fu-yQ2wd5p8LVUp40hvTpa17KJIQ0",
        authDomain: "ai-agent-e4e73.firebaseapp.com",
        projectId: "ai-agent-e4e73",
        storageBucket: "ai-agent-e4e73.firebasestorage.app",
        messagingSenderId: "813633792094",
        appId: "1:813633792094:web:05c355ec8305f27a09accf",
        measurementId: "G-LSPCQP2PQY"
      };

      // Initialize Firebase
      if (!firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
        LOG('✅ Firebase initialized');
      }

      // Get messaging
      const messaging = firebase.messaging();

      // Handle foreground messages (works without token registration)
      messaging.onMessage((payload) => {
        LOG('📥 Foreground FCM message:', payload);
        const title = payload.notification?.title || '⏰ Nhắc việc';
        const body = payload.notification?.body || '';
        notify(title, body);
      });

      // Optional: Try to get FCM token (requires VAPID key and user permission)
      try {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
          const token = await messaging.getToken({ 
            vapidKey: 'BK8Qgt18QTByMBbDXIel-5s6jX7fwooJotMuTBKEeqoRo-xwDeM-ptzXQfl-n9Sy54vOOvK54EkGB3xOQpur3luF4'
          });
          fcmToken = token;
          LOG('✅ FCM Token:', token);
          
          // Send token to server
          try {
            await fetch('/register_fcm_token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ token })
            });
            LOG('✅ FCM token registered with server');
          } catch (registerErr) {
            LOG('⚠️ Failed to register token with server:', registerErr.message);
          }
        }
      } catch (tokenErr) {
        LOG('⚠️ FCM token registration failed:', tokenErr.message);
      }
    } catch (e) {
      LOG('⚠️ Firebase init error:', e.message);
      // Don't block app if Firebase fails - browser notifications still work
    }
  }

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

  // === 2) Beep to và lặp lại ========================================================
  function beep() {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      
      // Phát âm thanh 3 lần, mỗi lần 0.5s
      for (let i = 0; i < 3; i++) {
        setTimeout(() => {
          const ctx = new AC();
          const osc = ctx.createOscillator();
          const g = ctx.createGain();
          osc.type = "sine";
          osc.frequency.value = 880;
          g.gain.value = 0.2; // Tăng âm lượng từ 0.04 lên 0.2
          osc.connect(g);
          g.connect(ctx.destination);
          osc.start();
          setTimeout(() => {
            osc.stop();
            ctx.close();
          }, 500);
        }, i * 700);
      }
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
            new Notification(title, { 
              body, 
              requireInteraction: true,
              tag: 'oshima-reminder',
              icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">⏰</text></svg>'
            });
            usedSystem = true;
            LOG("✅ Desktop notification sent");
          }
        } else {
          new Notification(title, { 
            body, 
            requireInteraction: true,
            tag: 'oshima-reminder',
            icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">⏰</text></svg>'
          });
          usedSystem = true;
          LOG("✅ Desktop notification sent");
        }
      }
    } catch (e) {
      LOG("❌ Desktop notification error:", e);
    }

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
    
    // 4) Focus window (nếu bị minimize)
    try {
      window.focus();
      if (document.hidden) {
        // Thử focus lại sau 100ms
        setTimeout(() => window.focus(), 100);
      }
    } catch {}
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
      t.includes("đã đến giờ") ||
      t.includes("da den gio") ||
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

  // DEBUG: Log ALL text để debug
  console.log("🔍 [notify.js] Checking text:", fullText.substring(0, 200));

  // Chỉ bắn khi có "đến giờ" hoặc "⏰"
  const tnorm = (fullText || "").toLowerCase().replace(/\s+/g, " ").trim();
  console.log("🔍 [notify.js] Normalized:", tnorm.substring(0, 150));
  
  // Check có "đến giờ", "đến hạn" HOẶC có emoji ⏰
  const hasPattern = /đến\s*(giờ|hạn)/.test(tnorm);  // Match cả "đến giờ" và "đến hạn"
  const hasEmoji = fullText.includes("⏰");
  const hasTask = tnorm.includes("công việc") || tnorm.includes("cong viec");
  console.log("🔍 [notify.js] Regex test:", hasPattern, "| Emoji test:", hasEmoji, "| Task:", hasTask);
  
  if (!hasPattern && !hasEmoji && !hasTask) {
    console.log("❌ [notify.js] Not a reminder/task, skipping");
    return;
  }
  
  console.log("✅ [notify.js] IS A REMINDER! Processing...");
  LOG("✅ IS A REMINDER! Processing...");

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
    // CHỈ quét trong message container, KHÔNG quét modal/dialog
    const messageContainer = document.querySelector('[data-cy="messages-container"]');
    if (!messageContainer) {
      LOG("⚠️ Message container not found yet");
      return;
    }
    
    const nodes = messageContainer.querySelectorAll('*');
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
    // CHỈ observe message container, KHÔNG observe modal/dialog
    const root = document.querySelector('[data-cy="messages-container"]');
    
    if (!root) {
      LOG("⚠️ Message container not found, retrying in 1s...");
      setTimeout(setupObserver, 1000);
      return;
    }
    
    LOG("Observer root element:", root.tagName, root.className || root.id || "[data-cy='messages-container']");
    
    const seen = new WeakSet();

    const ob = new MutationObserver((muts) => {
      muts.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          if (seen.has(node)) return;
          seen.add(node);
          
          // Chỉ check text của node mới này, không lấy từ parent
          const t = extractTextFromNode(node);
          if (t && t.length > 10) {  // Bỏ qua text quá ngắn (< 10 ký tự)
            LOG("🆕 New node text:", t.substring(0, 150));
            fireIfReminder(t);
          }
        });
      });
    });
    ob.observe(root, { childList: true, subtree: true });
    LOG("observer started");
  }

  // === 7) Boot ============================================================
  (async () => {
    LOG("permission:", await ensurePermission());
    await initFirebase(); // Initialize FCM
    scanExisting();
    setupObserver();
    LOG("ready");
  })();
})();
