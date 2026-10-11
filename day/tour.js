/* fresh. guided tour for the PUBLIC demo copies of the staff app (outputs/site/app, outputs/site/day).
   Injected by tools/build_site.py only; never part of ui/. No external requests.
   URL options:  ?tour=1        start the tour on load
                 ?tour=1&step=N jump to step N (1-based; for testing)
                 ?shot=1        hide the tour + home pills and the public banner (landing-page screenshots) */
(function () {
  'use strict';
  var qs = new URLSearchParams(location.search);
  var instant = qs.has('step');   /* test/deep-link mode: no smooth scrolling or transitions */
  if (instant) document.documentElement.classList.add('ft-instant');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s) { return document.querySelector(s); };
  if (qs.get('shot') === '1') { document.documentElement.classList.add('ft-shot'); return; }

  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function hasDay() {
    var tab = $('.tab[data-tab="day"]');
    return !!(tab && !tab.hidden && getComputedStyle(tab).display !== 'none');
  }
  var inDayCopy = /\/day\/(index\.html)?$/.test(location.pathname);
  /* "Replay the store's day" should open on the Dia view, not on a to-do list identical to app/ */
  /* ...and at the first pictures of the day (06:12-06:15), so the morning story plays forward, not the 20:16 end state */
  if (inDayCopy && !location.hash && hasDay()) location.replace('#/day/0615');
  /* on the Dia view the header should not claim the late-day picture range ("Imagens das 18:07 às 20:16") */
  (function () {
    var sub = document.getElementById('subtitle');
    if (!inDayCopy || !sub || !window.MutationObserver) return;
    function fix() {
      if (!/^#\/day/.test(location.hash)) return;
      var t = sub.textContent, n = t.replace(/Imagens das [0-9:]+ às [0-9:]+/, 'Dia inteiro').replace(/Pictures from [0-9:]+ to [0-9:]+/, 'Whole day');
      if (n !== t) sub.textContent = n;
    }
    new MutationObserver(fix).observe(sub, { childList: true, characterData: true, subtree: true });
    window.addEventListener('hashchange', function () { setTimeout(fix, 0); });
    fix();
  })();

  /* first wrong/empty task card's area link, remembered so step 4 opens a real problem area */
  var areaHref = null;
  function rememberArea() {
    var a = document.querySelector('#view-tasks article.task:not(.s-ok) .pname a');
    if (a) areaHref = a.getAttribute('href');
  }

  function buildSteps() {
    var s = [];
    var day = [
      { route: '#/day', sel: '#view-day .day-ctrl', title: 'Replay the whole day',
        text: 'Press play or drag the slider. The whole day, picture by picture.' },
      { route: null, sel: '#d-counts', title: 'The day, counted',
        text: 'Watch shelves empty and get refilled as the clock moves.' }
    ];
    if (inDayCopy && hasDay()) s = s.concat(day);
    s.push(
      { route: '#/tasks', sel: '#counters', title: 'Every area, right now',
        text: 'Vazio (empty), Baixo (low), Produto errado (wrong product). Every area, counted.' },
      { route: '#/tasks', sel: '#view-tasks article.task', title: 'Fazer agora: one to-do list',
        text: 'Repor (restock), Trocar (swap back), Deixar (leave). Most urgent first.', before: rememberArea },
      { route: '#/gondola', sel: '#view-gondola .frame-wrap', title: 'Gôndolas: the camera view',
        text: 'Each pin is one shelf area, coloured by status. Tap one.' },
      { route: function () { return areaHref || '#/gondola/6215/6215_7'; }, sel: '#panel', need: '#panel .task-head',
        title: 'One area, explained',
        text: 'What is there, and what to do. Unsure? "Confirmar à vista" (check by eye).' },
      { route: '#/insights', sel: '#view-insights .c-soon', title: 'Análise: before it runs out',
        text: '"A acabar em breve" (running out soon): restock before the shelf is empty.' },
      { route: null, sel: '.top .seg', title: 'Português or English',
        text: 'Portuguese for staff. English one tap away.' }
    );
    if (!inDayCopy && hasDay()) s = s.concat(day);
    var links = inDayCopy
      ? '<a href="../">Back to the home page</a><a href="../app/">Open the staff app</a>'
      : '<a href="../">Back to the home page</a><a href="../day/">Replay the store\'s day</a>';
    s.push({ route: null, sel: null, title: 'That is fresh.',
      text: 'See every shelf. Fix what matters first. Works offline, on a phone too.', links: links });
    return s;
  }

  /* ------------------------------------------------------------------ UI */
  var pill = document.createElement('button');
  pill.type = 'button'; pill.className = 'ft-pill ft-start';
  pill.innerHTML = '<span aria-hidden="true">&#9654;</span><span class="ft-lbl">Take the tour</span>';
  pill.setAttribute('aria-label', 'Take the tour');
  /* the way home lives in the public-demo banner (built by tools/build_site.py), not in a second floating pill */
  document.body.appendChild(pill);

  var spot = document.createElement('div'); spot.className = 'ft-spot'; spot.hidden = true;
  var shade = document.createElement('div'); shade.className = 'ft-shade'; shade.hidden = true;
  var card = document.createElement('div');
  card.className = 'ft-card'; card.hidden = true; card.tabIndex = -1;
  card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'false'); card.setAttribute('aria-labelledby', 'ft-title');
  card.innerHTML = '<div class="ft-top"><span class="ft-count" id="ft-count"></span>'
    + '<button type="button" class="ft-x" data-ft="close" aria-label="Close the tour">&times;</button></div>'
    + '<h2 class="ft-title" id="ft-title"></h2><p class="ft-text" id="ft-text" aria-live="polite"></p><div class="ft-links" id="ft-links"></div>'
    + '<div class="ft-nav"><button type="button" class="ft-btn ft-ghost" data-ft="back">Back</button>'
    + '<button type="button" class="ft-btn ft-main" data-ft="next">Next</button></div>';
  document.body.appendChild(shade); document.body.appendChild(spot); document.body.appendChild(card);

  /* keep the pills above the phone tab bar (it is fixed to the bottom below 860 px) */
  function placePills() {
    var tabs = $('#tabs'), off = 16;
    if (tabs && getComputedStyle(tabs).position === 'fixed') off += tabs.getBoundingClientRect().height;
    document.documentElement.style.setProperty('--ft-bottom', off + 'px');
  }
  placePills(); window.addEventListener('resize', placePills);

  var steps = [], idx = -1, target = null, raf = 0, token = 0;

  /* height of the sticky public-demo banner at the top (0 if absent) */
  function topInset() {
    var n = $('.public-note');
    if (!n) return 0;
    var r = n.getBoundingClientRect();
    return r.top <= 1 && r.bottom > 0 ? r.bottom : 0;
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function frames() { return wait(50); }   /* setTimeout, not rAF: rAF can stall in background tabs / headless */
  async function findEl(step) {
    for (var i = 0; i < 25; i++) {
      var el = step.sel && document.querySelector(step.sel);
      var ok = el && visible(el) && (!step.need || document.querySelector(step.need));
      if (ok) return el;
      await wait(60);
    }
    return null;
  }

  function track() {
    cancelAnimationFrame(raf);
    var loop = function () { position(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    position(); setTimeout(position, 120); setTimeout(position, 600);
  }
  window.addEventListener('scroll', position, { passive: true });
  window.addEventListener('resize', position);
  function position() {
    if (idx < 0) return;
    var vw = window.innerWidth, vh = window.innerHeight, phone = vw < 600;
    var cw = Math.min(380, vw - 32), ch = card.offsetHeight;
    var pb = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ft-bottom')) || 16;
    if (!target) {
      spot.hidden = true; shade.hidden = false;
      card.style.width = cw + 'px';
      card.style.left = Math.round((vw - cw) / 2) + 'px';
      card.style.top = Math.max(16, Math.round((vh - ch) / 2)) + 'px';
      return;
    }
    shade.hidden = true; spot.hidden = false;
    var r = target.getBoundingClientRect(), pad = 8;
    var top = Math.max(r.top - pad, -pad), bottom = Math.min(r.bottom + pad, vh + pad);
    spot.style.left = (r.left - pad) + 'px'; spot.style.top = top + 'px';
    spot.style.width = (r.width + 2 * pad) + 'px'; spot.style.height = Math.max(0, bottom - top) + 'px';
    card.style.width = cw + 'px';
    var x, y;
    if (phone) {               /* docked above the tab bar / bottom edge, or at the top if the target sits low */
      x = 16;
      var lowY = vh - pb - ch;
      y = (r.top + r.height / 2 > vh / 2 && r.top > ch + 32) ? 16 : lowY;
    } else if (vh - bottom >= ch + 24) { y = bottom + 12; x = r.left; }
    else if (top >= ch + 24) { y = top - ch - 12; x = r.left; }
    else if (vw - (r.right + pad) >= cw + 24) { x = r.right + pad + 12; y = Math.max(16, Math.min(r.top, vh - ch - 16)); }
    else if (r.left - pad >= cw + 24) { x = r.left - pad - 12 - cw; y = Math.max(16, Math.min(r.top, vh - ch - 16)); }
    else { x = vw - cw - 24; y = vh - ch - 24; }
    x = Math.max(16, Math.min(x, vw - cw - 16)); y = Math.max(16, Math.min(y, vh - ch - 16));
    card.style.left = Math.round(x) + 'px'; card.style.top = Math.round(y) + 'px';
  }

  async function go(i, dir) {
    var my = ++token;
    if (i < 0) i = 0;
    if (i >= steps.length) { close(); return; }
    idx = i;
    var step = steps[i];
    if (step.before) step.before();
    var route = typeof step.route === 'function' ? step.route() : step.route;
    if (route && location.hash !== route) { location.hash = route; await frames(); await wait(80); }
    if (my !== token) return;
    var el = step.sel ? await findEl(step) : null;
    if (my !== token) return;
    if (step.sel && !el) { go(i + (dir || 1), dir || 1); return; }   /* element missing: skip this step */
    target = el;
    if (el) {
      /* phones: put the target at the top (below the sticky privacy banner) so the card docked at the bottom
         covers as little of it as possible; desktop: centre it, or top-align tall targets */
      var place = function (smooth) {
        var q = el.getBoundingClientRect(), h = window.innerHeight;
        var startAlign = window.innerWidth < 600 || q.height > h * 0.6;
        var inset = topInset();
        var y = startAlign ? q.top - inset - 12 : q.top + q.height / 2 - h / 2;
        window.scrollTo({ top: Math.max(0, window.scrollY + y), behavior: smooth && !(reduce || instant) ? 'smooth' : 'auto' });
      };
      place(true);
      /* the app may reset the scroll after its own render: check again once it has settled */
      setTimeout(function () {
        if (my !== token || target !== el) return;
        var q = el.getBoundingClientRect(), h = window.innerHeight;
        if (q.top < topInset() || q.top > h * 0.6) place(false);
      }, 450);
    }
    var real = steps.filter(function (s) { return !s.skip; }).length;
    $('#ft-count').textContent = (i + 1) + ' / ' + real;
    $('#ft-title').textContent = step.title;
    $('#ft-text').textContent = step.text;
    var lk = $('#ft-links'); lk.innerHTML = step.links || ''; lk.hidden = !step.links;
    var back = card.querySelector('[data-ft="back"]'), next = card.querySelector('[data-ft="next"]');
    back.disabled = i === 0;
    next.textContent = i === steps.length - 1 ? 'Finish' : 'Next';
    card.hidden = false; pill.hidden = true;
    document.documentElement.classList.add('ft-on');
    track();
    card.focus({ preventScroll: true });
  }

  function start(at) {
    steps = buildSteps();
    rememberArea();
    go(Math.max(0, Math.min((at || 1) - 1, steps.length - 1)), 1);
  }
  function close() {
    token++; idx = -1; target = null;
    cancelAnimationFrame(raf);
    card.hidden = true; spot.hidden = true; shade.hidden = true; pill.hidden = false;
    document.documentElement.classList.remove('ft-on');
    pill.focus({ preventScroll: true });
  }

  pill.addEventListener('click', function () { start(1); });
  card.addEventListener('click', function (e) {
    var b = e.target.closest('[data-ft]'); if (!b) return;
    var a = b.getAttribute('data-ft');
    if (a === 'close') close();
    else if (a === 'next') go(idx + 1, 1);
    else if (a === 'back') go(idx - 1, -1);
  });
  shade.addEventListener('click', close);
  document.addEventListener('keydown', function (e) {
    if (idx < 0) return;
    var tag = (e.target && e.target.tagName) || '';
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (/INPUT|SELECT|TEXTAREA/.test(tag)) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); go(idx + 1, 1); }
    else if (e.key === 'ArrowLeft' && idx > 0) { e.preventDefault(); go(idx - 1, -1); }
  });

  if (qs.get('tour') === '1') {
    var n = parseInt(qs.get('step') || '1', 10) || 1;
    setTimeout(function () { start(n); }, 250);
  }
})();
