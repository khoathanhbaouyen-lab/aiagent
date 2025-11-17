// firebase-messaging-sw.js - Service Worker for FCM
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

// TODO: Replace with your Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyARg7fu-yQ2wd5p8LVUp40hvTpa17KJIQ0",
  authDomain: "ai-agent-e4e73.firebaseapp.com",
  projectId: "ai-agent-e4e73",
  storageBucket: "ai-agent-e4e73.firebasestorage.app",
  messagingSenderId: "813633792094",
  appId: "1:813633792094:web:05c355ec8305f27a09accf",
  measurementId: "G-LSPCQP2PQY"
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message:', payload);
  
  const notificationTitle = payload.notification.title || '⏰ Nhắc việc';
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/public/icon-192x192.png',
    badge: '/public/badge-72x72.png',
    tag: 'oshima-reminder',
    requireInteraction: true,
    vibrate: [200, 100, 200],
    data: payload.data
  };

  return self.registration.showNotification(notificationTitle, notificationOptions);
});
