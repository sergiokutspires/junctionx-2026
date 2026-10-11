/* fresh. Sensei team vault: login page logic (team/index.html).
   password --PBKDF2-HMAC-SHA256 (vault.json: salt, iterations)--> 256-bit AES-GCM key.
   The key is checked on vault.json's encrypted check string, stored as raw bytes in IndexedDB,
   and the service worker (sw.js) uses it to decrypt the pictures. Magic link: #k=<password>. */
(function () {
  'use strict';
  var CHECK = 'fresh-vault-check-v1';
  var $ = function (id) { return document.getElementById(id); };

  function supported() {
    return window.isSecureContext !== false && 'serviceWorker' in navigator && window.crypto && crypto.subtle && window.indexedDB;
  }
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
        var tx = db.transaction('kv', mode), q = fn(tx.objectStore('kv'));
        tx.oncomplete = function () { res(q.result); };
        tx.onerror = function () { rej(tx.error); };
      });
    });
  }
  function b64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }

  function deriveRaw(pw, meta) {
    return crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveBits'])
      .then(function (k) {
        return crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: b64(meta.salt), iterations: meta.iterations }, k, 256);
      });
  }
  function verify(raw, meta) {
    var c = b64(meta.check);
    return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt'])
      .then(function (k) { return crypto.subtle.decrypt({ name: 'AES-GCM', iv: c.slice(0, 12) }, k, c.slice(12)); })
      .then(function (p) { return new TextDecoder().decode(p) === CHECK; }, function () { return false; });
  }
  function tellSW(type) {
    return navigator.serviceWorker.ready.then(function (reg) {
      if (reg.active) reg.active.postMessage({ type: type });
    });
  }

  window.FreshVault = { deriveRaw: deriveRaw, verify: verify, b64: b64 };

  var app = $('vault-app');
  if (!app) return;
  // magic link: take the password out of the address bar FIRST, before anything else can fail
  var magic = /(?:^#|&)k=([^&]+)/.exec(location.hash);
  if (magic) {
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { location.hash = ''; }
    try { magic = decodeURIComponent(magic[1]); } catch (e) { magic = magic[1]; }
  }
  if (!supported()) {
    $('unsupported').hidden = false; $('login').hidden = true;
    if (/FBAN|FBAV|Instagram|LinkedInApp|Line\/|MicroMessenger|Twitter|; wv\)/i.test(navigator.userAgent || '')) {
      $('inapp').hidden = false;
    }
    return;
  }

  var next = new URLSearchParams(location.search).get('next');
  if (next !== 'app' && next !== 'day') next = null;
  var swReady = navigator.serviceWorker.register('sw.js', { scope: './' }).then(function () { return navigator.serviceWorker.ready; });
  var metaP = fetch('vault.json', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });

  function setMsg(t, cls) { var m = $('msg'); m.textContent = t || ''; m.className = 'msg' + (cls ? ' ' + cls : ''); }
  function busy(on) {
    $('go').disabled = on; $('pw').disabled = on;
    $('go').textContent = on ? 'Unlocking…' : 'Open';
    app.classList.toggle('is-busy', on);
    if (on) setMsg('Checking the password in your browser…', 'info');
  }
  function showOpen() {
    $('login').hidden = true; $('open').hidden = false; setMsg('');
    if (next) { location.href = next + '/'; }
  }
  function showLogin() { $('open').hidden = true; $('login').hidden = false; }

  function login(pw) {
    pw = (pw || '').trim();
    if (!pw) { setMsg('Type the password first.', 'err'); return; }
    busy(true);
    var raw;
    metaP.then(function (meta) { return deriveRaw(pw, meta).then(function (r) { raw = r; return verify(r, meta); }); })
      .then(function (ok) {
        if (!ok) { busy(false); setMsg('Wrong password', 'err'); $('pw').select(); return; }
        return op('readwrite', function (st) { return st.put(raw, 'k'); })
          .then(function () { return swReady; })
          .then(function () { return tellSW('key'); })
          .then(function () { busy(false); $('pw').value = ''; showOpen(); });
      })
      .catch(function () { busy(false); setMsg('Could not load the vault. Check your connection and try again.', 'err'); });
  }

  $('login').addEventListener('submit', function (e) { e.preventDefault(); login($('pw').value); });
  $('logout').addEventListener('click', function () {
    op('readwrite', function (st) { return st.delete('k'); })
      .then(function () { return tellSW('logout'); }, function () {})
      .then(function () { next = null; showLogin(); setMsg('Logged out.', 'info'); $('pw').focus(); });
  });

  if (magic) { login(magic); return; }
  // already logged in on this browser?
  Promise.all([op('readonly', function (st) { return st.get('k'); }), metaP]).then(function (r) {
    if (!r[0]) return false;
    return verify(r[0], r[1]);
  }).then(function (ok) { if (ok) return swReady.then(showOpen); }).catch(function () {});
})();
