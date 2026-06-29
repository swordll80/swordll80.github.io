/* YFxGeoStudio PWA Service Worker v0.104
 * 作用：
 * 1) 离线启动：缓存主 HTML、manifest、图标等应用外壳。
 * 2) 离线工作区：工作区数据仍由页面内 IndexedDB 负责，本文件不修改数据结构。
 * 3) 已访问地图瓦片缓存：用户在线浏览过的瓦片会尽量保存，离线时优先从缓存读取。
 *
 * 注意：公共地图源通常不允许批量预抓取。本 SW 只做“用户实际访问过瓦片”的运行时缓存。
 */
const YFX_SW_VERSION = '0.104';
const YFX_APP_CACHE = 'YFxGeoStudio-app-v0.104';
const YFX_RUNTIME_CACHE = 'YFxGeoStudio-runtime-v1';
const YFX_TILE_CACHE = 'YFxGeoStudio-tile-cache-v1';
const YFX_MAX_TILE_ENTRIES = 3000;

const YFX_APP_SHELL = [
  './manifest.webmanifest',
  './icons/yfx-icon-192.png',
  './icons/yfx-icon-512.png',
  './icons/yfx-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(YFX_APP_CACHE);
    await cache.addAll(YFX_APP_SHELL.map(u => new Request(u, {cache:'reload'})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keep = new Set([YFX_APP_CACHE, YFX_RUNTIME_CACHE, YFX_TILE_CACHE]);
    const names = await caches.keys();
    await Promise.all(names.map(name => keep.has(name) ? Promise.resolve() : caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', event => {
  const data = event.data || {};
  if(data.type === 'YFX_CACHE_URLS' && Array.isArray(data.urls)){
    event.waitUntil((async () => {
      const cache = await caches.open(YFX_APP_CACHE);
      for(const url of data.urls){
        try{
          const req = new Request(url, {cache:'reload'});
          const res = await fetch(req);
          if(res && (res.ok || res.type === 'opaque')) await cache.put(req, res.clone());
        }catch(e){}
      }
    })());
  }else if(data.type === 'YFX_CLEAR_TILE_CACHE'){
    event.waitUntil((async () => {
      let ok = false;
      try{ ok = await caches.delete(YFX_TILE_CACHE); }catch(e){ ok = false; }
      if(event.ports && event.ports[0]) event.ports[0].postMessage({ok});
    })());
  }
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if(req.method !== 'GET') return;

  if(req.mode === 'navigate'){
    event.respondWith(networkFirstNavigation(req));
    return;
  }

  const url = new URL(req.url);
  if(isMapTileRequest(req, url)){
    event.respondWith(cacheFirstWithNetworkFill(req, YFX_TILE_CACHE, true));
    return;
  }

  if(url.origin === self.location.origin){
    event.respondWith(staleWhileRevalidate(req, YFX_APP_CACHE));
    return;
  }

  if(isRuntimeAsset(url)){
    event.respondWith(staleWhileRevalidate(req, YFX_RUNTIME_CACHE));
  }
});

async function networkFirstNavigation(req){
  const cache = await caches.open(YFX_APP_CACHE);
  try{
    const res = await fetch(req);
    if(res && res.ok) await cache.put(req, res.clone());
    return res;
  }catch(e){
    const cached = await cache.match(req);
    if(cached) return cached;
    const fallback = await cache.match('./YFxGeoStudio.html') || await cache.match('./YFxGeoStudio_beta.html');
    if(fallback) return fallback;
    const keys = await cache.keys();
    for(const k of keys){
      if(k.url.endsWith('.html')){
        const html = await cache.match(k);
        if(html) return html;
      }
    }
    return new Response('<!doctype html><meta charset="utf-8"><title>YFxGeoStudio 离线不可用</title><body style="font-family:sans-serif;padding:24px;background:#101418;color:#eef3f7"><h2>YFxGeoStudio 离线不可用</h2><p>请先在线打开一次工具，等待 PWA 缓存完成后再离线使用。</p></body>', {
      headers:{'Content-Type':'text/html;charset=utf-8'}
    });
  }
}

async function staleWhileRevalidate(req, cacheName){
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const freshPromise = fetch(req).then(res => {
    if(res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone()).catch(()=>{});
    return res;
  }).catch(() => null);
  return cached || freshPromise || fetch(req);
}

async function cacheFirstWithNetworkFill(req, cacheName, trimTiles){
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if(cached) return cached;
  const res = await fetch(req);
  if(res && (res.ok || res.type === 'opaque')){
    cache.put(req, res.clone()).then(() => {
      if(trimTiles) trimCache(cacheName, YFX_MAX_TILE_ENTRIES);
    }).catch(()=>{});
  }
  return res;
}

async function trimCache(cacheName, maxEntries){
  try{
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if(keys.length <= maxEntries) return;
    const remove = keys.length - maxEntries;
    for(let i=0;i<remove;i++) await cache.delete(keys[i]);
  }catch(e){}
}

function isRuntimeAsset(url){
  return /(^|\.)unpkg\.com$/.test(url.hostname) ||
         /(^|\.)jsdelivr\.net$/.test(url.hostname) ||
         /(^|\.)cdnjs\.cloudflare\.com$/.test(url.hostname);
}

function isMapTileRequest(req, url){
  if(req.destination === 'image'){
    if(/(^|\.)google\.com$/.test(url.hostname) && url.pathname.indexOf('/vt/') >= 0) return true;
    if(/(^|\.)autonavi\.com$/.test(url.hostname) && url.pathname.indexOf('/appmaptile') >= 0) return true;
    if(/(^|\.)opentopomap\.org$/.test(url.hostname)) return true;
    if(/\/\d+\/\d+\/\d+\.(png|jpg|jpeg|webp)$/i.test(url.pathname)) return true;
  }
  return false;
}
