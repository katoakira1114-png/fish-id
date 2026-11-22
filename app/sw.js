const APP_CACHE = "fish-id-shell-v6";
const PHOTO_CACHE = "fish-id-photos-v1";

const CORE_ASSETS = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json",
  "./data/families.json",
  "./data/pomacentridae.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_CACHE).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== APP_CACHE && k !== PHOTO_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "PRECACHE_PHOTOS" && Array.isArray(data.urls)) {
    event.waitUntil(precachePhotos(data.urls));
  }
});

async function precachePhotos(urls) {
  const cache = await caches.open(PHOTO_CACHE);
  const uniqueUrls = Array.from(new Set(urls.filter(Boolean)));
  let done = 0;

  // Limit concurrency to keep network smooth while populating offline cache
  const queue = [...uniqueUrls];
  async function worker() {
    while (queue.length > 0) {
      const url = queue.shift();
      try {
        const existing = await cache.match(url);
        if (!existing) {
          const req = new Request(url, { mode: "no-cors" });
          const res = await fetch(req);
          if (res && (res.ok || res.type === "opaque")) {
            await cache.put(url, res);
          }
        }
      } catch (_) {
        // Ignore transient offline/image fetch errors for individual photos
      }
      done += 1;
    }
  }

  const workers = Array.from({ length: 4 }, () => worker());
  await Promise.all(workers);

  const clients = await self.clients.matchAll();
  for (const client of clients) {
    client.postMessage({
      type: "PRECACHE_DONE",
      cached: done,
      total: uniqueUrls.length,
    });
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isSameOrigin = url.origin === self.location.origin;

  if (isSameOrigin) {
    // Stale-while-revalidate for local app shell & data
    event.respondWith(
      caches.open(APP_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const fetchPromise = fetch(request)
          .then((res) => {
            if (res && res.ok) {
              cache.put(request, res.clone());
            }
            return res;
          })
          .catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Cache-first for external representative photos
  if (request.destination === "image" || /\.(jpe?g|png|webp)(\?|$)/i.test(url.pathname)) {
    event.respondWith(
      caches.open(PHOTO_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        try {
          const res = await fetch(request);
          if (res && (res.ok || res.type === "opaque")) {
            cache.put(request, res.clone());
          }
          return res;
        } catch (_) {
          return new Response("", { status: 504, statusText: "Offline image unavailable" });
        }
      })
    );
  }
});
