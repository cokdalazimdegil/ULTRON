/**
 * ULTRON Service Worker — PWA Caching & Push Notification Engine (v1.0)
 * Statik kabuğu cache'e alir, offline acilişı destekler, WebSocket
 * koptuğunda push bildirimi gönderir.
 */

const CACHE_NAME = "ultron-shell-v1";
const SHELL_URLS = [
  "/",
  "/static/app.js",
  "/static/style.css",
  "/static/pcm-worklet.js",
  "/static/qrcode.min.js",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

// ── Kurulum: Shell dosyalarini cache'e al ─────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_URLS).catch((err) => {
        console.warn("[SW] Shell cache hatasi (bazi dosyalar eksik olabilir):", err);
      });
    })
  );
  self.skipWaiting();
});

// ── Aktivasyon: Eski cache'leri temizle ──────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => {
            console.log("[SW] Eski cache siliniyor:", k);
            return caches.delete(k);
          })
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: Shell-first strateji ───────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API ve WebSocket isteklerini cache'leme
  if (
    url.pathname.startsWith("/ws") ||
    url.pathname.startsWith("/api") ||
    event.request.method !== "GET"
  ) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          // Yeni shell dosyalarini cache'e ekle
          if (
            response.ok &&
            SHELL_URLS.some((u) => url.pathname.endsWith(u.replace(/^\//, "")))
          ) {
            caches.open(CACHE_NAME).then((c) =>
              c.put(event.request, response.clone())
            );
          }
          return response;
        })
        .catch(() => {
          // Offline fallback
          if (event.request.mode === "navigate") {
            return caches.match("/");
          }
        });
    })
  );
});

// ── Push Bildirimleri ─────────────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let data = { title: "ULTRON", body: "Yeni bir bildirim var.", icon: "/static/icons/icon-192.png" };
  try {
    data = { ...data, ...event.data.json() };
  } catch (_) {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
      vibrate: [200, 100, 200],
      tag: "ultron-alert",
      renotify: true,
      data: { url: data.url || "/" },
    })
  );
});

// ── Bildirime tıklama: Uygulamayı öne getir ───────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url.includes(self.registration.scope) && "focus" in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) return clients.openWindow(targetUrl);
      })
  );
});

// ── Mesaj: Sayfa'dan SW'ye mesaj al ──────────────────────────────────────
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
