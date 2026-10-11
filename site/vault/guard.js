/* fresh. Sensei team vault: guard for team/app/ and team/day/.
   No valid key in this browser -> back to the login page (../?next=app|day).
   Page not controlled by the service worker yet (first visit, hard reload) -> install it, reload once. */
(function () {
  'use strict';
  var s = document.currentScript;
  var next = (s && s.getAttribute('data-next')) || 'app';
  var base = new URL('../', location.href);
  function toLogin() { location.replace(new URL('?next=' + encodeURIComponent(next), base).href); }
  if (!('serviceWorker' in navigator) || !window.crypto || !crypto.subtle || !window.indexedDB) { toLogin(); return; }

  function idb() {
    return new Promise(function (res, rej) {
      var r = indexedDB.open('fresh-vault', 1);
      r.onupgradeneeded = function () { r.result.createObjectStore('kv'); };
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
    });
  }
  function op(mode, fn) {
    return idb().then(function (db) {
      return new Promise(function (res, rej) {
        var q = fn(db.transaction('kv', mode).objectStore('kv'));
        q.onsuccess = function () { res(q.result); };
        q.onerror = function () { rej(q.error); };
      });
    });
  }
  function b64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }

  op('readonly', function (st) { return st.get('k'); }).then(function (raw) {
    if (!raw) throw new Error('no key');
    return Promise.all([
      crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt']),
      fetch(new URL('vault.json', base).href, { cache: 'no-store' }).then(function (r) { return r.json(); })
    ]);
  }).then(function (kv) {
    var check = b64(kv[1].check);
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: check.slice(0, 12) }, kv[0], check.slice(12));
  }).then(function () {
    if (navigator.serviceWorker.controller) { try { sessionStorage.removeItem('fv-reload'); } catch (e) {} return; }
    var once = false;
    try { once = sessionStorage.getItem('fv-reload') === '1'; sessionStorage.setItem('fv-reload', '1'); } catch (e) {}
    if (once) return;
    return navigator.serviceWorker.register(new URL('sw.js', base).href, { scope: base.href })
      .then(function () { return navigator.serviceWorker.ready; })
      .then(function () { location.reload(); });
  }).catch(function () {
    // no key, or a key from an older build (password or salt changed): forget it, log in again
    op('readwrite', function (st) { return st.delete('k'); }).catch(function () {}).then(toLogin, toLogin);
  });
})();
