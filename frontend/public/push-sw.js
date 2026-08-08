/* Obserra service worker — installable PWA + web-push.
   IMPORTANT: never cache the HTML app shell or JS chunks. Caching the shell pins
   stale build references and breaks code-split chunk loading after a rebuild
   (symptom: app stuck on a spinner after login). We only cache a few stable
   brand assets and always serve HTML/scripts from the network. */
const CACHE = "obserra-static-v3";
const STATIC_ASSETS = ["/brand-mark.png", "/logo-mark-192.png", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Drop every previous cache (e.g. the old shell cache that pinned stale chunks).
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  // Navigations always hit the network so the freshest index.html + code-split
  // chunks are used. Never serve a cached HTML shell.
  if (req.mode === "navigate") return;
  const url = new URL(req.url);
  // Cache-first only for the small set of stable static brand assets.
  if (url.origin === self.location.origin && STATIC_ASSETS.includes(url.pathname)) {
    event.respondWith(caches.match(req).then((r) => r || fetch(req)));
  }
});

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) { d = {}; }
  event.waitUntil(
    self.registration.showNotification(d.title || "Obserra", {
      body: d.body || "",
      icon: "/logo.png",
      badge: "/logo.png",
      data: { url: d.url || "/app" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/app";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cl) => {
      for (const c of cl) { if ("focus" in c) { c.navigate(url); return c.focus(); } }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
