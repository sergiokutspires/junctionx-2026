/* Shelf check: staff dashboard logic. Reads window.SHELF_DATA (data.js). No network, no libraries. */
(() => {
  'use strict';
  const D = window.SHELF_DATA;
  if (!D || !D.areas) {
    document.body.insertAdjacentHTML('afterbegin', '<p style="padding:16px">data.js is missing or empty.</p>');
    return;
  }

  /* ------------------------------------------------------------------ helpers */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: keep in memory only */ } },
  };
  const icon = (id, cls = '') => `<svg class="ic ${cls}" aria-hidden="true" focusable="false"><use href="#${id}"/></svg>`;

  /* ------------------------------------------------------------------ text */
  const T = {
    en: {
      skip: 'Skip to content', title: 'Shelf check', tab_tasks: 'Do now', tab_gondola: 'Gondolas', tab_products: 'Products',
      f_camera: 'Camera', f_search: 'Search', search_ph: 'Search product or area', all_cams: 'All cameras',
      snapshot: 'Snapshot', pics_range: 'Pictures from {a} to {b}', old: '{t} old', unreadable: 'Picture unreadable: not checked',
      clear: 'Clear filters', theme: 'Switch light / dark theme', print: 'Print task list', lang: 'Language',
      s_empty: 'Empty', s_low: 'Low', s_wrong: 'Wrong product', s_ok: 'OK',
      areas_n: '{n} areas', area1: '1 area', camera: 'Camera', area: 'area',
      long_empty: 'Empty: nothing left to sell', long_low: 'Half full: top up soon',
      long_wrong: 'Wrong product on this spot', long_ok: 'Looks right: leave alone',
      lv_empty: 'Empty', lv_half: 'Half', lv_full: 'Full',
      act_restock: 'Restock', act_restock_x: 'shelf is empty', act_top: 'Top up soon', act_move: 'Move back',
      act_check: 'Check product', expected: 'expected', seen: 'seen', belongs: '{q} belongs in', empty_in: 'Empty in ~{t}', around: 'around {t}',
      conf: 'Confidence', c_sure: 'Sure', c_likely: 'Likely', c_check: 'Not sure: check by eye', seen_at: 'Seen at {t}',
      partly: 'Partly out of view', stock: 'Stock',
      mark_done: 'Mark done', show_gondola: 'Show on gondola', tasks_title: 'Do now', n_tasks: '{n} tasks', progress: '{d} of {n} done',
      urgent: 'Do first: wrong product and empty', soon: 'Then: running low', by_priority: 'By priority', by_route: 'By gondola',
      leave: 'Leave alone: {n} areas look right', all_good: 'All good', all_good_x: 'Nothing needs doing right now.',
      none_match: 'No area matches these filters.', done_title: 'Done',
      pick_area: 'Tap an area on the picture', no_picture: 'No picture', planned: 'Planned product', seen_instead: 'Seen instead',
      today: 'Stock during the day', visible: 'In view', snapshot_of: 'Picture taken', raw: 'Catalogue name',
      col_product: 'Product', col_do: 'What to do', todo: '{n} to do', every_ok: 'All OK', legend: 'Legend', zoom_out: 'Show full picture', zoom_in: 'Zoom to shelves',
      plain_empty: 'Nothing left to sell. Restock {p}.',
      plain_low: 'About half is left. Top up {p} soon.',
      plain_wrong: 'This spot should hold {p}, but it looks like {q}. Move it back.',
      plain_wrong_nq: 'This spot should hold {p}, but another product seems to be there. Check it.',
      plain_ok: 'Right product, well stocked. Leave alone.',
      sort_by: 'Sort by', p_attention: 'Needs attention', p_name: 'Name', p_stock: 'Stock', p_areas: 'Areas',
      avg_stock: 'Average stock', elsewhere: 'Found in the wrong place', no_products: 'No product matches.',
      foot: 'Made automatically from camera pictures ({b}). When it says "check by eye", look before you move stock.',
      spark_alt: 'Stock during the day: {a}',
    },
    pt: {
      skip: 'Saltar para o conteúdo', title: 'Controlo de prateleiras', tab_tasks: 'Fazer agora', tab_gondola: 'Gôndolas', tab_products: 'Produtos',
      f_camera: 'Câmara', f_search: 'Pesquisar', search_ph: 'Pesquisar produto ou zona', all_cams: 'Todas as câmaras',
      snapshot: 'Estado às', pics_range: 'Imagens das {a} às {b}', old: 'há {t}', unreadable: 'Imagem ilegível: não verificado',
      clear: 'Limpar filtros', theme: 'Mudar tema claro / escuro', print: 'Imprimir lista de tarefas', lang: 'Idioma',
      s_empty: 'Vazio', s_low: 'Baixo', s_wrong: 'Produto errado', s_ok: 'OK',
      areas_n: '{n} zonas', area1: '1 zona', camera: 'Câmara', area: 'zona',
      long_empty: 'Vazio: nada para vender', long_low: 'A meio: reforçar em breve',
      long_wrong: 'Produto errado neste local', long_ok: 'Tudo certo: deixar como está',
      lv_empty: 'Vazio', lv_half: 'Meio', lv_full: 'Cheio',
      act_restock: 'Repor', act_restock_x: 'está vazio', act_top: 'Reforçar em breve', act_move: 'Devolver ao lugar',
      act_check: 'Verificar produto', expected: 'esperado', seen: 'visto', belongs: '{q} pertence a', empty_in: 'Vazio daqui a ~{t}', around: 'por volta das {t}',
      conf: 'Confiança', c_sure: 'Certo', c_likely: 'Provável', c_check: 'Incerto: confirmar à vista', seen_at: 'Visto às {t}',
      partly: 'Parcialmente fora da imagem', stock: 'Stock',
      mark_done: 'Marcar feito', show_gondola: 'Ver na gôndola', tasks_title: 'Fazer agora', n_tasks: '{n} tarefas', progress: '{d} de {n} feitas',
      urgent: 'Primeiro: produto errado e vazio', soon: 'Depois: a ficar baixo', by_priority: 'Por prioridade', by_route: 'Por gôndola',
      leave: 'Deixar: {n} zonas estão certas', all_good: 'Tudo certo', all_good_x: 'Nada para fazer neste momento.',
      none_match: 'Nenhuma zona corresponde aos filtros.', done_title: 'Feito',
      pick_area: 'Toque numa zona da imagem', no_picture: 'Sem imagem', planned: 'Produto planeado', seen_instead: 'Visto em vez disso',
      today: 'Stock ao longo do dia', visible: 'Visível', snapshot_of: 'Imagem das', raw: 'Nome no catálogo',
      col_product: 'Produto', col_do: 'O que fazer', todo: '{n} por fazer', every_ok: 'Tudo OK', legend: 'Legenda', zoom_out: 'Ver imagem completa', zoom_in: 'Aproximar às prateleiras',
      plain_empty: 'Nada para vender. Repor {p}.',
      plain_low: 'Resta cerca de metade. Reforçar {p} em breve.',
      plain_wrong: 'Este local devia ter {p}, mas parece haver {q}. Devolver ao lugar.',
      plain_wrong_nq: 'Este local devia ter {p}, mas parece haver outro produto. Verificar.',
      plain_ok: 'Produto certo e bem abastecido. Deixar como está.',
      sort_by: 'Ordenar por', p_attention: 'Precisa de atenção', p_name: 'Nome', p_stock: 'Stock', p_areas: 'Zonas',
      avg_stock: 'Stock médio', elsewhere: 'Encontrado no sítio errado', no_products: 'Nenhum produto corresponde.',
      foot: 'Feito automaticamente a partir de imagens das câmaras ({b}). Quando diz "confirmar à vista", veja antes de mexer no stock.',
      spark_alt: 'Stock ao longo do dia: {a}',
    },
  };

  /* ------------------------------------------------------------------ state */
  const STATUS = ['empty', 'low', 'wrong', 'ok'];               // counter order
  const ORDER = { wrong: 0, empty: 1, low: 2, ok: 3 };
  const LV_ICON = { empty: 'i-empty', half: 'i-low', full: 'i-full' };
  const LV_CLASS = { empty: 's-empty', half: 's-low', full: 's-ok' };
  const S_ICON = { empty: 'i-empty', low: 'i-low', wrong: 'i-wrong', ok: 'i-ok' };
  const VIEWS = ['tasks', 'gondola', 'products'];

  const areas = D.areas;
  const areaById = Object.fromEntries(areas.map((a) => [a.id, a]));
  const camById = Object.fromEntries(D.cameras.map((c) => [c.id, c]));
  const st = {
    view: 'tasks', lang: store.get('sensei.lang', 'en'), theme: store.get('sensei.theme', 'auto'),
    status: null, full: false, cam: 'all', q: '', sort: 'priority', gcam: null, sel: null, psort: 'attention', pdir: 1,
  };
  if (!T[st.lang]) st.lang = 'en';
  let done = store.get('sensei.done.v1', {});
  const scrollMem = {};

  const t = (k, v) => {
    let s = (T[st.lang][k] != null ? T[st.lang][k] : T.en[k]) || k;
    if (v) for (const key in v) s = s.split('{' + key + '}').join(v[key]);
    return s;
  };

  /* ------------------------------------------------------------------ formatting */
  const tz = D.timezone || 'Europe/Lisbon';
  const fmtCache = {};
  function fmt(kind) {
    const key = kind + st.lang;
    if (fmtCache[key]) return fmtCache[key];
    const loc = st.lang === 'pt' ? 'pt-PT' : 'en-GB';
    const opts = kind === 'time' ? { hour: '2-digit', minute: '2-digit', hour12: false }
      : kind === 'min' ? { minute: '2-digit' } : { weekday: 'short', day: 'numeric', month: 'short' };
    try { fmtCache[key] = new Intl.DateTimeFormat(loc, Object.assign({ timeZone: tz }, opts)); } catch (e) {
      fmtCache[key] = new Intl.DateTimeFormat(loc, Object.assign({ timeZone: 'UTC' }, opts));
    }
    return fmtCache[key];
  }
  const fmtTime = (ts) => fmt('time').format(new Date(ts * 1000));
  const fmtDay = (ts) => fmt('day').format(new Date(ts * 1000));
  const fmtMin = (ts) => parseInt(fmt('min').format(new Date(ts * 1000)), 10) || 0;
  function dur(s) {
    const m = Math.round(s / 60);
    if (m < 90) return Math.max(5, Math.round(m / 5) * 5) + ' min';
    const h = Math.round((s / 3600) * 2) / 2;
    return String(h).replace('.', st.lang === 'pt' ? ',' : '.') + ' h';
  }
  const pct = (x) => Math.round(x * 100) + '%';

  /* ------------------------------------------------------------------ names, labels */
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const pair = (en, pt) => {
    const p = st.lang === 'pt' ? { main: pt, sub: cap(en) } : { main: cap(en), sub: pt };
    if (norm(p.main) === norm(p.sub)) p.sub = '';
    return p;
  };
  const nm = (a) => pair(a.en, a.pt);
  const seenName = (a) => (a.len ? (st.lang === 'pt' ? a.lpt : a.len) : '');
  const loc = (a) => `${t('camera')} ${esc(a.cam)} · ${t('area')} ${esc(a.num)}`;
  const camTs = (a) => (camById[a.cam] ? camById[a.cam].ts : D.snapshot_ts);
  const FC_MAX_S = 4 * 3600;   // longer forecasts are not actionable on this shift
  const fcShow = (a) => a.fc != null && a.fc > 0 && a.fc < FC_MAX_S && (a.status === 'low' || a.status === 'wrong');
  const OLD_S = 3600;          // pictures older than this vs the newest one get an age chip
  const ageChip = (ts) => (D.snapshot_ts != null && D.snapshot_ts - ts > OLD_S
    ? `<span class="age">${icon('i-clock')}${t('old', { t: dur(D.snapshot_ts - ts) })}</span>` : '');
  function snapText() {
    const ts = D.cameras.filter((c) => !c.unreadable).map((c) => c.ts).filter((x) => x != null);
    if (!ts.length) return '';
    const lo = Math.min(...ts); const hi = Math.max(...ts);
    return hi - lo > 15 * 60 ? `${t('pics_range', { a: fmtTime(lo), b: fmtTime(hi) })}, ${fmtDay(hi)}`
      : `${t('snapshot')} ${fmtTime(hi)}, ${fmtDay(hi)}`;
  }
  const hrefOf = (a) => `#/gondola/${encodeURIComponent(a.cam)}/${encodeURIComponent(a.id)}`;
  const confKey = (c) => (c >= 0.85 ? 'c_sure' : c >= 0.65 ? 'c_likely' : 'c_check');
  const taskKey = (a) => `${a.id}|${camTs(a)}|${a.status}`;
  const badge = (s) => `<span class="badge s-${s}">${icon(S_ICON[s])}${t('s_' + s)}</span>`;
  const sortRoute = (x, y) => (x.cam === y.cam ? (parseInt(x.num, 10) || 0) - (parseInt(y.num, 10) || 0) : (x.cam < y.cam ? -1 : 1));

  function matches(a, ignoreCam) {
    if (!ignoreCam && st.cam !== 'all' && a.cam !== st.cam) return false;
    if (st.status && a.status !== st.status) return false;
    if (st.q) {
      const hay = `${a.en} ${a.pt} ${a.raw} ${a.id} ${a.cam} ${a.len || ''} ${a.lpt || ''}`.toLowerCase();
      if (!st.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }
  const inCam = (a) => st.cam === 'all' || a.cam === st.cam;

  /* ------------------------------------------------------------------ thumbnails */
  function ctxThumb(a) {
    const c = camById[a.cam];
    if (!c || !c.frame || !a.quad) return `<div class="ph">${t('no_picture')}</div>`;
    const xs = a.quad.map((p) => p[0]); const ys = a.quad.map((p) => p[1]);
    const x0 = Math.min(...xs); const x1 = Math.max(...xs); const y0 = Math.min(...ys); const y1 = Math.max(...ys);
    const asp = 1.6;
    let vw = clamp(Math.max((x1 - x0) * 2.6, (y1 - y0) * 2.6 * asp, c.w * 0.3), 80, c.w);
    let vh = vw / asp;
    if (vh > c.h) { vh = c.h; vw = vh * asp; }
    const vx = clamp((x0 + x1) / 2 - vw / 2, 0, c.w - vw);
    const vy = clamp((y0 + y1) / 2 - vh / 2, 0, c.h - vh);
    const pts = a.quad.map((p) => p.join(',')).join(' ');
    return `<svg class="ctx s-${a.status}" viewBox="${vx.toFixed(1)} ${vy.toFixed(1)} ${vw.toFixed(1)} ${vh.toFixed(1)}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${esc(loc(a).replace(/<[^>]+>/g, ''))}">
      <image href="${esc(c.frame)}" x="0" y="0" width="${c.w}" height="${c.h}"/>
      <polygon class="poly halo" points="${pts}"/><polygon class="poly ${a.status === 'ok' ? 'ok' : ''}" points="${pts}" style="pointer-events:none"/></svg>`;
  }
  const cropImg = (a, cls = '') => (a.crop
    ? `<img class="${cls}" src="${esc(a.crop)}" alt="${esc(cap(a.en))}" loading="lazy" decoding="async">`
    : `<div class="ph">${t('no_picture')}</div>`);

  /* ------------------------------------------------------------------ task cards */
  function actionHtml(a) {
    if (a.status === 'empty') return `<strong>${t('act_restock')}</strong>: ${t('act_restock_x')}`;
    if (a.status === 'low') {
      const f = fcShow(a) ? `. ${t('empty_in', { t: dur(a.fc) })}` : '';
      return `<strong>${t('act_top')}</strong>${f}`;
    }
    if (a.status === 'wrong') {
      const p = esc(nm(a).main); const q = esc(seenName(a));
      return q ? `<strong>${t('act_move')}</strong>: ${t('expected')} ${p}, ${t('seen')} ${q}`
        : `<strong>${t('act_check')}</strong>: ${t('expected')} ${p}`;
    }
    return t('long_ok');
  }
  function homeHtml(a) {
    if (a.status !== 'wrong' || !a.home || !a.home.length) return '';
    const links = a.home.map((id) => areaById[id]).filter(Boolean)
      .map((h) => `${t('camera')} ${esc(h.cam)} · ${t('area')} ${esc(h.num)}`).join('; ');
    return links ? `<p class="home">${t('belongs', { q: esc(cap(seenName(a))) })}: ${links}</p>` : '';
  }
  function metaHtml(a) {
    const bits = [`<span>${t('conf')}: <b>${t(confKey(a.conf))}</b></span>`];
    if (a.status === 'wrong' && a.level !== 'full') bits.push(`<span>${t('stock')}: <b>${t('lv_' + a.level)}</b></span>`);
    if (a.vis != null && a.vis < 0.7) bits.push(`<span>${t('partly')}</span>`);
    bits.push(`<span>${icon('i-clock')} ${t('seen_at', { t: fmtTime(camTs(a)) })}</span>`);
    const age = ageChip(camTs(a));
    if (age) bits.push(age);
    return bits.join('');
  }
  function taskCard(a) {
    const n = nm(a); const key = taskKey(a); const isDone = !!done[key];
    return `<article class="task s-${a.status}${isDone ? ' is-done' : ''}" data-key="${esc(key)}">
      <div class="task-head">${badge(a.status)}<span class="loc">${loc(a)}</span></div>
      <h3 class="pname"><a href="${hrefOf(a)}">${esc(n.main)}</a><small>${esc(n.sub)}</small></h3>
      <p class="action">${actionHtml(a)}</p>${homeHtml(a)}
      <div class="media">${ctxThumb(a)}${cropImg(a)}</div>
      <div class="meta">${metaHtml(a)}</div>
      <div class="task-foot">
        <label class="done"><input type="checkbox" data-act="done" data-key="${esc(key)}"${isDone ? ' checked' : ''}> ${t('mark_done')}</label>
        <span class="go">${t('show_gondola')} ${icon('i-arrow')}</span>
      </div></article>`;
  }

  function renderTasks() {
    const el = $('#view-tasks');
    const all = areas.filter((a) => a.status !== 'ok');
    const tasks = all.filter((a) => matches(a));
    const doneN = tasks.filter((a) => done[taskKey(a)]).length;
    const showOk = st.status === 'ok' || st.status === null;
    const oks = areas.filter((a) => a.status === 'ok' && matches(a));
    let html = `<div class="view-head"><h2>${t('tasks_title')} <span class="muted">· ${t('n_tasks', { n: tasks.length })}</span></h2>
      <div class="prog-wrap"><div class="progress" role="progressbar" aria-label="${t('tasks_title')}" aria-valuemin="0" aria-valuemax="${tasks.length}" aria-valuenow="${doneN}"><i style="width:${tasks.length ? (100 * doneN) / tasks.length : 0}%"></i></div>
      <span class="muted" id="prog-txt">${t('progress', { d: doneN, n: tasks.length })}</span></div>
      <div class="seg" role="group" aria-label="${t('sort_by')}">
        <button type="button" data-act="sort" data-v="priority" aria-pressed="${st.sort === 'priority'}">${t('by_priority')}</button>
        <button type="button" data-act="sort" data-v="route" aria-pressed="${st.sort === 'route'}">${t('by_route')}</button></div></div>`;
    if (!tasks.length && st.status !== 'ok') {
      html += all.length ? `<div class="allgood"><h3>${t('none_match')}</h3></div>`
        : `<div class="allgood">${icon('i-ok')}<h3>${t('all_good')}</h3><p class="muted">${t('all_good_x')}</p></div>`;
    } else if (st.sort === 'priority') {
      const sorted = tasks.slice().sort((x, y) => y.pri - x.pri || sortRoute(x, y));
      const urgent = sorted.filter((a) => a.status !== 'low');
      const soon = sorted.filter((a) => a.status === 'low');
      if (urgent.length) html += `<h3 class="group-title">${t('urgent')} <span class="count">${urgent.length}</span></h3><div class="cards">${urgent.map(taskCard).join('')}</div>`;
      if (soon.length) html += `<h3 class="group-title">${t('soon')} <span class="count">${soon.length}</span></h3><div class="cards">${soon.map(taskCard).join('')}</div>`;
    } else {
      const byCam = {};
      tasks.slice().sort(sortRoute).forEach((a) => { (byCam[a.cam] = byCam[a.cam] || []).push(a); });
      Object.keys(byCam).forEach((c) => {
        html += `<h3 class="group-title">${t('camera')} ${esc(c)} <span class="count">${byCam[c].length}</span></h3><div class="cards">${byCam[c].sort((x, y) => y.pri - x.pri).map(taskCard).join('')}</div>`;
      });
    }
    if (showOk && oks.length) html += leaveHtml(oks, st.status === 'ok');
    el.innerHTML = html;
  }
  function leaveHtml(oks, open) {
    const byCam = {};
    oks.slice().sort(sortRoute).forEach((a) => { (byCam[a.cam] = byCam[a.cam] || []).push(a); });
    const body = Object.keys(byCam).map((c) => `<div class="leave-cam"><h4>${t('camera')} ${esc(c)}</h4><div class="pill-row">${
      byCam[c].map((a) => `<a class="pill s-ok" href="${hrefOf(a)}">${icon('i-ok')}${esc(a.num)} · ${esc(nm(a).main)}</a>`).join('')}</div></div>`).join('');
    return `<details class="leave"${open ? ' open' : ''}><summary>${icon('i-ok')}${t('leave', { n: oks.length })}</summary><div class="leave-body">${body}</div></details>`;
  }
  function updateProgress() {
    const tasks = areas.filter((a) => a.status !== 'ok' && matches(a));
    const n = tasks.filter((a) => done[taskKey(a)]).length;
    const txt = $('#prog-txt'); if (txt) txt.textContent = t('progress', { d: n, n: tasks.length });
    const bar = $('#view-tasks .progress'); if (bar) {
      bar.setAttribute('aria-valuenow', n);
      bar.firstElementChild.style.width = (tasks.length ? (100 * n) / tasks.length : 0) + '%';
    }
  }

  /* ------------------------------------------------------------------ gondola view */
  /* Region of the frame to show: the union of all areas plus a margin (the shelves fill a small part of the picture). */
  function viewBoxFor(cam, camAreas) {
    const full = [0, 0, cam.w, cam.h];
    const pts = [].concat(...camAreas.filter((a) => a.quad).map((a) => a.quad));
    if (st.full || !pts.length) return full;
    let x0 = Math.max(0, Math.min(...pts.map((p) => p[0]))); let x1 = Math.min(cam.w, Math.max(...pts.map((p) => p[0])));
    let y0 = Math.max(0, Math.min(...pts.map((p) => p[1]))); let y1 = Math.min(cam.h, Math.max(...pts.map((p) => p[1])));
    const m = 0.07 * Math.max(x1 - x0, y1 - y0) + 12;
    x0 -= m; x1 += m; y0 -= m; y1 += m;
    let w = Math.max(x1 - x0, cam.w * 0.35); let h = y1 - y0;
    if (w / h > 1.9) h = w / 1.9; else if (w / h < 1.3) w = h * 1.3;
    if (w >= cam.w * 0.88 || h >= cam.h * 0.88) return full;
    const cx = (x0 + x1) / 2; const cy = (y0 + y1) / 2;
    return [clamp(cx - w / 2, 0, cam.w - w), clamp(cy - h / 2, 0, cam.h - h), w, h];
  }
  function pinPos(a, vb) {
    const cx = a.quad.reduce((s, p) => s + p[0], 0) / 4; const cy = a.quad.reduce((s, p) => s + p[1], 0) / 4;
    return [clamp((cx - vb[0]) / vb[2], 0.04, 0.96) * 100, clamp((cy - vb[1]) / vb[3], 0.06, 0.94) * 100];
  }
  function sparkHtml(a) {
    const pts = a.tl || [];
    if (pts.length < 2) return '';
    const W = 320; const H = 112; const L = 42; const R = 10; const Tp = 8; const B = 22;
    const t0 = pts[0][0]; const tLast = pts[pts.length - 1][0];
    const snap = camTs(a);
    const showFc = fcShow(a);
    const tEnd = Math.max(tLast, showFc ? snap + a.fc : 0, t0 + 1);
    const X = (ts) => L + ((ts - t0) / (tEnd - t0)) * (W - L - R);
    const Y = (f) => Tp + (1 - clamp(f, 0, 1)) * (H - Tp - B);
    const colour = { empty: 'var(--empty)', half: 'var(--low)', full: 'var(--ok)' };
    let g = '';
    [[1, 'lv_full'], [0.5, 'lv_half'], [0, 'lv_empty']].forEach(([f, k]) => {
      g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(f)}" y2="${Y(f)}"/><text x="${L - 6}" y="${Y(f) + 4}" text-anchor="end">${t(k)}</text>`;
    });
    const spanH = (tEnd - t0) / 3600; const stepH = spanH > 9 ? 3 : spanH > 4 ? 2 : 1;
    let tick = t0 + ((60 - fmtMin(t0)) % 60) * 60;
    for (let n = 0; tick <= tEnd && n < 14; tick += stepH * 3600, n++) {
      g += `<line class="axis" x1="${X(tick)}" x2="${X(tick)}" y1="${H - B}" y2="${H - B + 4}"/><text x="${X(tick)}" y="${H - 5}" text-anchor="middle">${fmtTime(tick)}</text>`;
    }
    const line = pts.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ');
    const dots = pts.map((p) => `<circle class="pt" cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="4.5" fill="${colour[p[2]] || 'var(--muted)'}"><title>${fmtTime(p[0])}: ${t('lv_' + p[2])}</title></circle>`).join('');
    const last = pts[pts.length - 1];
    const fc = showFc ? `<polyline class="fc" points="${X(last[0]).toFixed(1)},${Y(last[1]).toFixed(1)} ${X(snap + a.fc).toFixed(1)},${Y(0)}"/>` : '';
    const alt = t('spark_alt', { a: `${fmtTime(pts[0][0])} ${t('lv_' + pts[0][2])}, ${fmtTime(last[0])} ${t('lv_' + last[2])}` });
    return `<div class="spark-wrap"><h4>${t('today')}</h4><svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(alt)}">${g}<polyline class="line" points="${line}"/>${fc}${dots}</svg></div>`;
  }
  function levelsHtml(a) {
    return `<div class="levels" role="group" aria-label="${t('stock')}">${['empty', 'half', 'full'].map((lv, i) => {
      const on = a.level === lv;
      const p = a.pl && a.pl.length === 3 ? `<span class="pc">${pct(a.pl[i])}</span>` : '';
      return `<div class="lvl ${LV_CLASS[lv]}${on ? ' on' : ''}"${on ? ' aria-current="true"' : ''}>${icon(LV_ICON[lv])}<span>${t('lv_' + lv)}</span>${p}</div>`;
    }).join('')}</div>`;
  }
  function plainText(a) {
    const p = nm(a).main; const q = seenName(a);
    if (a.status === 'empty') return t('plain_empty', { p });
    if (a.status === 'low') return t('plain_low', { p });
    if (a.status === 'wrong') return q ? t('plain_wrong', { p, q }) : t('plain_wrong_nq', { p });
    return t('plain_ok');
  }
  function panelHtml(a) {
    if (!a) return `<p class="panel-hint">${t('pick_area')}</p>`;
    const n = nm(a); const key = taskKey(a); const isDone = !!done[key];
    const fcTxt = fcShow(a)
      ? `<div class="forecast">${icon('i-clock')}<span>${t('empty_in', { t: dur(a.fc) })} (${t('around', { t: fmtTime(camTs(a) + a.fc) })})</span></div>` : '';
    const rows = [[t('planned'), esc(nm(a).main)]];
    if (a.status === 'wrong' && seenName(a)) rows.push([t('seen_instead'), esc(seenName(a))]);
    rows.push([t('conf'), t(confKey(a.conf))]);
    if (a.vis != null && a.vis < 0.95) rows.push([t('visible'), pct(a.vis)]);
    rows.push([t('snapshot_of'), fmtTime(camTs(a)) + (ageChip(camTs(a)) ? ` (${t('old', { t: dur(D.snapshot_ts - camTs(a)) })})` : '')]);
    rows.push([t('raw'), esc(a.raw)]);
    return `<div class="task-head">${badge(a.status)}<span class="loc">${loc(a)}</span></div>
      ${a.crop ? `<img class="crop" src="${esc(a.crop)}" alt="${esc(cap(a.en))}">` : ''}
      <h3 class="pname">${esc(n.main)}<small>${esc(n.sub)}</small></h3>
      <p class="plain">${plainText(a)}</p>${homeHtml(a)}
      ${levelsHtml(a)}${fcTxt}${sparkHtml(a)}
      <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${a.status !== 'ok' ? `<label class="done"><input type="checkbox" data-act="done" data-key="${esc(key)}"${isDone ? ' checked' : ''}> ${t('mark_done')}</label>` : ''}`;
  }
  function renderGondola() {
    const el = $('#view-gondola');
    if (!D.cameras.length) { el.innerHTML = `<p class="muted">${t('no_picture')}</p>`; return; }
    if (!camById[st.gcam]) {
      const first = areas.filter((a) => a.status !== 'ok').sort((x, y) => y.pri - x.pri)[0];
      st.gcam = first ? first.cam : D.cameras[0].id;
    }
    const cam = camById[st.gcam];
    const camAreas = areas.filter((a) => a.cam === cam.id);
    if (!st.sel || !areaById[st.sel] || areaById[st.sel].cam !== cam.id) {
      const top = camAreas.slice().sort((x, y) => y.pri - x.pri || sortRoute(x, y))[0];
      st.sel = top ? top.id : null;
    }
    const sel = st.sel ? areaById[st.sel] : null;
    const chips = D.cameras.map((c) => {
      const as = areas.filter((a) => a.cam === c.id); const n = as.filter((a) => a.status !== 'ok').length;
      return `<button type="button" class="cam-chip" data-act="cam" data-v="${esc(c.id)}" aria-pressed="${c.id === cam.id}"><b>${t('camera')} ${esc(c.id)}</b><span>${c.unreadable ? t('unreadable') : `${n ? t('todo', { n }) : t('every_ok')} · ${fmtTime(c.ts)}`}${c.unreadable ? '' : ageChip(c.ts)}</span></button>`;
    }).join('');
    let frame;
    if (cam.frame) {
      const vb = viewBoxFor(cam, camAreas); const zoomed = vb[2] < cam.w;
      const polys = camAreas.filter((a) => a.quad).map((a) => `<polygon class="poly s-${a.status}${a.status === 'ok' ? ' ok' : ''}${a.id === st.sel ? ' sel' : ''}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" points="${a.quad.map((p) => p.join(',')).join(' ')}"/>`).join('');
      const pins = camAreas.filter((a) => a.quad).map((a) => {
        const [px, py] = pinPos(a, vb);
        return `<button type="button" class="pin s-${a.status}${a.id === st.sel ? ' sel' : ''}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" style="left:${px.toFixed(2)}%;top:${py.toFixed(2)}%" aria-pressed="${a.id === st.sel}" aria-label="${esc(`${t('area')} ${a.num}, ${nm(a).main}, ${t('s_' + a.status)}`)}">${icon(S_ICON[a.status])}<span>${esc(a.num)}</span></button>`;
      }).join('');
      frame = `<div class="frame-wrap" role="group" aria-label="${t('camera')} ${esc(cam.id)}, ${fmtTime(cam.ts)}" style="aspect-ratio:${vb[2].toFixed(1)}/${vb[3].toFixed(1)}">
        <svg class="overlay" viewBox="${vb.map((v) => v.toFixed(1)).join(' ')}" preserveAspectRatio="none"><image href="${esc(cam.frame)}" x="0" y="0" width="${cam.w}" height="${cam.h}"/>${polys}</svg>${pins}</div>
        <button type="button" class="chip zoom" data-act="zoom" aria-pressed="${st.full}">${t(st.full ? 'zoom_in' : 'zoom_out')}</button>`;
    } else {
      frame = `<div class="frame-wrap noframe">${t(cam.unreadable ? 'unreadable' : 'no_picture')}</div>`;
    }
    const legend = `<div class="legend" aria-label="${t('legend')}">${['wrong', 'empty', 'low', 'ok'].map((s) => `<span class="s-${s}">${icon(S_ICON[s])}${t('s_' + s)}</span>`).join('')}</div>`;
    const list = camAreas.slice().sort(sortRoute).map((a) => `<li><button type="button" class="area-btn s-${a.status}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" aria-pressed="${a.id === st.sel}">${icon(S_ICON[a.status])}<b>${esc(a.num)} · ${esc(nm(a).main)}</b><small>${t('s_' + a.status)} · ${t('lv_' + a.level)}</small></button></li>`).join('');
    el.innerHTML = `<div class="view-head"><h2>${t('tab_gondola')}</h2></div><div class="cam-chips" role="group" aria-label="${t('f_camera')}">${chips}</div>
      <div class="gv"><div class="frame-col">${frame}${legend}</div>
      <aside class="panel" id="panel" aria-live="polite">${panelHtml(sel)}</aside>
      <div class="list-col"><ul class="area-list">${list}</ul></div></div>`;
    const active = $('.cam-chip[aria-pressed="true"]', el);
    if (active) { const box = active.parentElement; box.scrollLeft = active.offsetLeft - (box.clientWidth - active.offsetWidth) / 2; }
  }

  /* ------------------------------------------------------------------ products */
  function renderProducts() {
    const el = $('#view-products');
    const groups = {};
    areas.filter((a) => matches(a)).forEach((a) => {
      const g = groups[a.pid] || (groups[a.pid] = { pid: a.pid, en: a.en, pt: a.pt, areas: [] });
      g.areas.push(a);
    });
    const list = Object.values(groups).map((g) => {
      const worst = g.areas.reduce((w, a) => (ORDER[a.status] < ORDER[w] ? a.status : w), 'ok');
      const fills = g.areas.map((a) => (a.fill == null ? (a.level === 'full' ? 0.9 : a.level === 'half' ? 0.5 : 0.05) : a.fill));
      return Object.assign(g, {
        worst, avg: fills.reduce((s, v) => s + v, 0) / fills.length,
        maxPri: Math.max(...g.areas.map((a) => a.pri)), name: (st.lang === 'pt' ? g.pt : g.en).toLowerCase(),
        elsewhere: areas.filter((a) => a.lpid === g.pid && a.status === 'wrong'),
      });
    });
    const dir = st.pdir;
    const cmp = {
      attention: (x, y) => (y.maxPri - x.maxPri) * dir || x.name.localeCompare(y.name),
      name: (x, y) => x.name.localeCompare(y.name) * dir,
      stock: (x, y) => (x.avg - y.avg) * dir || x.name.localeCompare(y.name),
      areas: (x, y) => (y.areas.length - x.areas.length) * dir || x.name.localeCompare(y.name),
    }[st.psort];
    list.sort(cmp);
    const sortBtn = (k) => `<button type="button" class="chip" data-act="psort" data-v="${k}" aria-pressed="${st.psort === k}">${t('p_' + k)}${st.psort === k ? (st.pdir === 1 ? ' ↑' : ' ↓') : ''}</button>`;
    const cards = list.map((g) => {
      const counts = STATUS.map((s) => [s, g.areas.filter((a) => a.status === s).length]).filter(([, n]) => n);
      const pills = g.areas.slice().sort(sortRoute).map((a) => `<a class="pill s-${a.status}" href="${hrefOf(a)}">${icon(S_ICON[a.status])}${esc(a.cam)} · ${esc(a.num)}</a>`).join('');
      const nmn = pair(g.en, g.pt);
      const els = g.elsewhere.length ? `<p class="home">${t('elsewhere')}: ${g.elsewhere.map((a) => `${esc(a.cam)} · ${esc(a.num)}`).join('; ')}</p>` : '';
      return `<article class="prod s-${g.worst}"><div class="prod-top"><h3 class="pname">${esc(nmn.main)}<small>${esc(nmn.sub)}</small></h3>${badge(g.worst)}</div>
        <div class="stat-row"><span class="muted">${g.areas.length === 1 ? t('area1') : t('areas_n', { n: g.areas.length })}</span>${counts.map(([s, n]) => `<span class="badge s-${s}">${icon(S_ICON[s])}${n} ${t('s_' + s)}</span>`).join('')}</div>
        <div><div class="meta"><span>${t('avg_stock')}: <b>${pct(g.avg)}</b></span></div><div class="fillbar" aria-hidden="true"><i style="width:${pct(clamp(g.avg, 0.03, 1))}"></i></div></div>
        ${els}<div class="pill-row">${pills}</div></article>`;
    }).join('');
    el.innerHTML = `<div class="view-head"><h2>${t('tab_products')} <span class="muted">· ${list.length}</span></h2>
      <div class="sortbar"><span class="lbl">${t('sort_by')}</span>${['attention', 'name', 'stock', 'areas'].map(sortBtn).join('')}</div></div>
      ${list.length ? `<div class="prod-grid">${cards}</div>` : `<div class="allgood"><h3>${t('no_products')}</h3></div>`}`;
  }

  /* ------------------------------------------------------------------ print sheet */
  function buildPrintSheet() {
    const tasks = areas.filter((a) => a.status !== 'ok' && !done[taskKey(a)]).sort(sortRoute);
    let cur = null; let rows = '';
    tasks.forEach((a) => {
      if (a.cam !== cur) { cur = a.cam; rows += `<tr class="cam"><td colspan="4">${t('camera')} ${esc(a.cam)} · ${fmtTime(camTs(a))}</td></tr>`; }
      rows += `<tr><td><span class="box"></span></td><td>${t('area')} ${esc(a.num)}</td><td><b>${esc(nm(a).main)}</b><small>${esc(nm(a).sub)}</small></td>
        <td><b>${a.status === 'low' ? t('act_top') : a.status === 'empty' ? t('act_restock') : (seenName(a) ? t('act_move') : t('act_check'))}</b>${
  a.status === 'wrong' && seenName(a) ? `<small>${t('expected')} ${esc(nm(a).main)}, ${t('seen')} ${esc(seenName(a))}</small>` : ''}${
  fcShow(a) ? `<small>${t('empty_in', { t: dur(a.fc) })}</small>` : ''}</td></tr>`;
    });
    $('#print-sheet').innerHTML = `<h1>${t('title')}: ${t('tasks_title')}</h1><p>${esc(D.section || '')} · ${snapText()} · ${t('n_tasks', { n: tasks.length })}</p>
      <table><thead><tr><th></th><th>${cap(t('area'))}</th><th>${t('col_product')}</th><th>${t('col_do')}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  /* ------------------------------------------------------------------ chrome */
  function counts() {
    const c = { empty: 0, low: 0, wrong: 0, ok: 0 };
    areas.filter(inCam).forEach((a) => { c[a.status]++; });
    return c;
  }
  function renderChrome() {
    document.documentElement.lang = st.lang;
    document.title = `${t('title')}: ${D.section || ''}`.replace(/: $/, '');
    $$('[data-i18n]').forEach((n) => { n.textContent = t(n.dataset.i18n); });
    $('#app-title').textContent = t('title');
    const camTxt = st.cam === 'all' ? '' : ` · ${t('camera')} ${st.cam}`;
    $('#subtitle').textContent = `${D.section || ''} · ${snapText()}${camTxt}`;
    $('#search').placeholder = t('search_ph');
    $$('[data-act="lang"]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === st.lang)));
    $('#theme-btn').setAttribute('aria-label', t('theme'));
    $('#print-btn').setAttribute('aria-label', t('print'));
    const dark = isDark();
    $('#theme-btn').innerHTML = icon(dark ? 'i-sun' : 'i-moon');
    const c = counts();
    $('#counters').classList.toggle('compact', st.view !== 'tasks');
    $('#counters').innerHTML = STATUS.map((s) => `<button type="button" class="counter s-${s}${c[s] ? '' : ' zero'}" data-act="status" data-v="${s}" aria-pressed="${st.status === s}">
      ${icon(S_ICON[s])}<span class="n">${c[s]}</span><span class="lbl">${t('s_' + s)}</span></button>`).join('');
    const sel = $('#cam-select'); const want = st.cam;
    sel.innerHTML = `<option value="all">${t('all_cams')}</option>` + D.cameras.map((cm) => {
      const n = areas.filter((a) => a.cam === cm.id && a.status !== 'ok').length;
      return `<option value="${esc(cm.id)}">${t('camera')} ${esc(cm.id)}${n ? ` (${n})` : ''}</option>`;
    }).join('');
    sel.value = want;
    $('#cam-field').hidden = st.view === 'gondola';
    $$('.tab').forEach((a) => { if (a.dataset.tab === st.view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    const any = st.status || st.cam !== 'all' || st.q;
    const cl = $('#clear-filters'); cl.hidden = !any; cl.textContent = t('clear');
    $('#foot').textContent = t('foot', { b: D.backend || 'model' });
  }
  function isDark() {
    if (st.theme === 'dark') return true;
    if (st.theme === 'light') return false;
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }
  function applyTheme() {
    if (st.theme === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', st.theme);
  }

  function render() {
    renderChrome();
    VIEWS.forEach((v) => { $('#view-' + v).hidden = v !== st.view; });
    if (st.view === 'tasks') renderTasks();
    else if (st.view === 'gondola') renderGondola();
    else renderProducts();
    buildPrintSheet();
  }

  /* ------------------------------------------------------------------ routing and events */
  function readHash() {
    const p = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    st.view = VIEWS.includes(p[0]) ? p[0] : 'tasks';
    if (st.view === 'gondola') {
      if (p[1] && camById[p[1]]) st.gcam = p[1];
      if (p[2] && areaById[p[2]]) { st.sel = p[2]; st.gcam = areaById[p[2]].cam; }
    }
  }
  let skipHash = false;
  function setHash(h, replace) {
    if (!replace) { location.hash = h; return; }
    try { history.replaceState(null, '', h); } catch (e) { skipHash = true; location.replace(h); } /* some file:// setups */
  }
  window.addEventListener('hashchange', () => {
    if (skipHash) { skipHash = false; return; }
    const old = st.view; scrollMem[old] = window.scrollY;
    readHash(); render();
    window.scrollTo(0, st.view === old ? 0 : (st.view === 'tasks' ? scrollMem.tasks || 0 : 0));
  });

  /* Re-rendering replaces the clicked element: give keyboard focus back to its twin. */
  function restoreFocus(b) {
    if (!b || !b.matches || !b.matches('button, a, input')) return;
    const sel = `[data-act="${b.dataset.act}"]` + (b.dataset.v != null ? `[data-v="${CSS.escape(b.dataset.v)}"]` : '')
      + (b.dataset.id != null ? `[data-id="${CSS.escape(b.dataset.id)}"]` : '');
    const same = $$(sel).filter((n) => n.tagName === b.tagName && n.className.split(' ')[0] === b.className.split(' ')[0]);
    if (same[0] && same[0] !== b) same[0].focus({ preventScroll: true });
  }
  function selectArea(id) {
    const a = areaById[id]; if (!a) return;
    st.sel = id; st.gcam = a.cam;
    setHash(`#/gondola/${encodeURIComponent(a.cam)}/${encodeURIComponent(id)}`, true);
    renderGondola();
    const panel = $('#panel');
    if (panel && window.innerWidth < 860) {
      const r = panel.getBoundingClientRect();
      if (r.top > window.innerHeight - 120 || r.bottom < 0) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]'); if (!b) return;
    const act = b.dataset.act; const v = b.dataset.v;
    if (act === 'lang') { st.lang = v; store.set('sensei.lang', v); render(); return; }
    if (act === 'theme') { st.theme = isDark() ? 'light' : 'dark'; store.set('sensei.theme', st.theme); applyTheme(); renderChrome(); return; }
    if (act === 'print') { buildPrintSheet(); window.print(); return; }
    if (act === 'status') { st.status = st.status === v ? null : v; render(); }
    else if (act === 'clear') { st.status = null; st.cam = 'all'; st.q = ''; $('#search').value = ''; render(); return; }
    else if (act === 'sort') { st.sort = v; render(); }
    else if (act === 'psort') { if (st.psort === v) st.pdir = -st.pdir; else { st.psort = v; st.pdir = 1; } render(); }
    else if (act === 'cam') { st.gcam = v; st.sel = null; setHash(`#/gondola/${encodeURIComponent(v)}`, true); renderGondola(); }
    else if (act === 'area') { selectArea(b.dataset.id); }
    else if (act === 'zoom') { st.full = !st.full; renderGondola(); }
    restoreFocus(b);
  });
  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.id === 'cam-select') { st.cam = el.value; render(); }
    else if (el.dataset && el.dataset.act === 'done') {
      const key = el.dataset.key;
      if (el.checked) done[key] = 1; else delete done[key];
      store.set('sensei.done.v1', done);
      $$('.task').forEach((card) => { if (card.dataset.key === key) card.classList.toggle('is-done', el.checked); });
      $$('input[data-act="done"]').forEach((o) => { if (o.dataset.key === key) o.checked = el.checked; });
      updateProgress(); buildPrintSheet();
    }
  });
  $('#search').addEventListener('input', (e) => { st.q = e.target.value.trim(); render(); });
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => { if (st.theme === 'auto') renderChrome(); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
  }
  window.addEventListener('beforeprint', buildPrintSheet);

  /* ------------------------------------------------------------------ start */
  applyTheme();
  readHash();
  render();
})();
