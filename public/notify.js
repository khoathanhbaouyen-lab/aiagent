// public/notify.js  — Firebase Cloud Messaging + Browser Notifications
(function () {
  const LOG = (...a) => console.log("[notify.js]", ...a);
  
  // === 0) Firebase Cloud Messaging Setup ===============================
  let fcmToken = null;
  
  async function initFirebase() {
    try {
      // Register Service Worker first
      if ('serviceWorker' in navigator) {
        try {
          const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
          LOG('✅ Service Worker registered:', registration);
        } catch (swError) {
          LOG('⚠️ Service Worker registration failed:', swError);
          // Continue anyway - FCM might still work for foreground messages
        }
      }
      
      const firebaseConfig = {
        apiKey: "AIzaSyARg7fu-yQ2wd5p8LVUp40hvTpa17KJIQ0",
        authDomain: "ai-agent-e4e73.firebaseapp.com",
        projectId: "ai-agent-e4e73",
        storageBucket: "ai-agent-e4e73.firebasestorage.app",
        messagingSenderId: "813633792094",
        appId: "1:813633792094:web:05c355ec8305f27a09accf",
        measurementId: "G-LSPCQP2PQY"
      };
      
      // Import Firebase (dynamically)
      if (!window.firebase) {
        await import('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
        await import('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');
      }
      
      if (!firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
      }
      
      const messaging = firebase.messaging();
      
      // Request permission and get token
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        fcmToken = await messaging.getToken({
          vapidKey: 'BK8Qq18QTByMBbOXIel-5s6jX7fwooJotMuTBKEeqoRo-xwDeMptzXQfI-n9Sy54v0QvKS4EkGB3xO0pur3IUF4'
        });
        LOG('FCM Token:', fcmToken);
        
        // For now, use 'default@local' as user_email since we don't have cross-domain auth
        // TODO: Implement proper auth token passing from Chainlit to API server
        const userEmail = 'default@local';
        
        // Send token to backend (API server on port 8001)
        try {
          const response = await fetch('http://localhost:8001/api/register-fcm-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              token: fcmToken,
              user_email: userEmail
            })
          });
          
          if (response.ok) {
            LOG('✅ FCM token registered with backend for', userEmail);
          } else {
            const errorText = await response.text();
            LOG('⚠️ Failed to register FCM token:', errorText);
          }
        } catch (error) {
          LOG('❌ Error registering FCM token:', error);
        }
      }
      
      // Handle foreground messages
      messaging.onMessage((payload) => {
        LOG('📩 Foreground message:', payload);
        const title = payload.notification?.title || '⏰ Nhắc việc';
        const body = payload.notification?.body || '';
        notify(title, body);
      });
      
    } catch (error) {
      LOG('⚠️ Firebase init error:', error);
      LOG('Falling back to browser notifications only');
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
  LOG("🔍 Checking text:", fullText.substring(0, 200));

  // Chỉ bắn khi có "đến giờ" hoặc "⏰"
  const tnorm = (fullText || "").toLowerCase().replace(/\s+/g, " ").trim();
  LOG("🔍 Normalized:", tnorm.substring(0, 150));
  
  // Check có "đến giờ", "đến hạn" HOẶC có emoji ⏰
  const hasPattern = /đến\s*(giờ|hạn)/.test(tnorm);  // Match cả "đến giờ" và "đến hạn"
  const hasEmoji = fullText.includes("⏰");
  const hasTask = tnorm.includes("công việc") || tnorm.includes("cong viec");
  LOG("🔍 Regex test:", hasPattern, "| Emoji test:", hasEmoji, "| Task:", hasTask);
  
  if (!hasPattern && !hasEmoji && !hasTask) {
    LOG("❌ Not a reminder/task, skipping");
    return;
  }
  
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
