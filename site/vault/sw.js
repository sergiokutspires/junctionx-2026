/* fresh. Sensei team vault: service worker (scope team/).
   Intercepts picture requests under team/app/img/ and team/day/img/, fetches <url>.enc
   (IV(12) || AES-256-GCM ciphertext || tag), decrypts it with the key from IndexedDB and
   answers with the plain picture. No key -> 401. Nothing is cached in plaintext. */
'use strict';
var DB = 'fresh-vault', STORE = 'kv';
var TYPES = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
var keyP = null;

function idb() {
  return new Promise(function (res, rej) {
    var r = indexedDB.open(DB, 1);
    r.onupgradeneeded = function () { r.result.createObjectStore(STORE); };
    r.onsuccess = function () { res(r.result); };
    r.onerror = function () { rej(r.error); };
  });
}
function readRaw() {
  return idb().then(function (db) {
    return new Promise(function (res, rej) {
      var q = db.transaction(STORE, 'readonly').objectStore(STORE).get('k');
      q.onsuccess = function () { res(q.result || null); };
      q.onerror = function () { rej(q.error); };
    });
  });
}
function getKey() {
  if (!keyP) {
    keyP = readRaw()
      .then(function (raw) { return raw ? crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt']) : null; })
      .catch(function () { return null; })
      .then(function (k) { if (!k) keyP = null; return k; });
  }
  return keyP;
}

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('message', function (e) {
  var t = e.data && e.data.type;
  if (t === 'key' || t === 'logout') keyP = null;   // re-read IndexedDB on the next picture
});

function blank(status) {
  return new Response('', { status: status, headers: { 'Cache-Control': 'no-store' } });
}

function serve(url, ext) {
  return getKey().then(function (key) {
    if (!key) return blank(401);
    return fetch(url.origin + url.pathname + '.enc', { cache: 'no-cache', credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) return blank(r.status);
      return r.arrayBuffer().then(function (buf) {
        return crypto.subtle.decrypt({ name: 'AES-GCM', iv: buf.slice(0, 12) }, key, buf.slice(12));
      }).then(function (plain) {
        return new Response(plain, { status: 200, headers: { 'Content-Type': TYPES[ext], 'Cache-Control': 'no-store' } });
      }, function () { return blank(403); });
    });
  }).catch(function () { return blank(500); });
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  var scope = new URL(self.registration.scope);
  if (url.origin !== scope.origin || url.pathname.indexOf(scope.pathname) !== 0) return;
  var rest = url.pathname.slice(scope.pathname.length);
  var m = /^(?:app|day)\/img\/.+\.(jpe?g|png|webp)$/i.exec(rest);
  if (!m) return;
  e.respondWith(serve(url, m[1].toLowerCase()));
});
