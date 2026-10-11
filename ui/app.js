/* fresh.: staff app logic. Reads window.SHELF_DATA (data.js). No network, no libraries. */
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
      skip: 'Skip to content', title: 'fresh.', tab_tasks: 'Do now', tab_gondola: 'Gondolas', tab_products: 'Products',
      f_camera: 'Camera', f_search: 'Search', search_ph: 'Search product or area', all_cams: 'All cameras',
      snapshot: 'Snapshot', pics_range: 'Pictures from {a} to {b}', old: '{t} old', unreadable: 'Picture unreadable: not checked',
      clear: 'Clear filters', theme: 'Switch light / dark theme', print: 'Print task list', lang: 'Language',
      s_empty: 'Empty', s_low: 'Low', s_wrong: 'Wrong product', s_ok: 'OK',
      areas_n: '{n} areas', area1: '1 area', camera: 'Camera', area: 'area',
      long_empty: 'Empty: nothing left to sell', long_low: 'Half full: top up soon',
      long_wrong: 'Wrong product on this spot', long_ok: 'Looks right: leave alone',
      lv_empty: 'Empty', lv_half: 'Half', lv_full: 'Full',
      act_restock: 'Restock', act_restock_x: 'shelf is empty', act_top: 'Top up soon', act_move: 'Swap',
      act_move_x: 'this spot should hold {p}, but it holds {q}.', take_to: 'Take {q} to', areas_w: 'areas',
      act_check: 'Check product', expected: 'expected', seen: 'seen', belongs: '{q} belongs in', empty_in: 'Empty in ~{t}', around: 'around {t}',
      empty_now: 'Probably empty by now: check now', empty_was: 'forecast for {t}',
      conf: 'Confidence', c_sure: 'High', c_likely: 'Medium', c_check: 'Low: check by eye', seen_at: 'Seen at {t}',
      partly: 'Partly out of view', stock: 'Stock',
      mark_done: 'Mark done', show_gondola: 'Show on gondola', tasks_title: 'Do now', n_tasks: '{n} tasks', n_tasks1: '1 task', progress: '{d} of {n} done',
      urgent: 'Do first: wrong product and empty', soon: 'Then: running low', by_priority: 'By priority', by_route: 'By gondola',
      leave: 'Leave alone: {n} areas look right', leave1: 'Leave alone: 1 area looks right', all_good: 'All good', all_good_x: 'Nothing needs doing right now.',
      none_match: 'No area matches these filters.', done_title: 'Done',
      pick_area: 'Tap an area on the picture', no_picture: 'No picture', planned: 'Planned product', seen_instead: 'Seen instead',
      today: 'Stock during the day', visible: 'In view', snapshot_of: 'Picture taken', raw: 'Catalogue name',
      col_product: 'Product', col_do: 'What to do', todo: '{n} to do', every_ok: 'All OK', legend: 'Legend', zoom_out: 'Show full picture', zoom_in: 'Zoom to shelves',
      plain_empty: 'Nothing left to sell. Restock {p}.',
      plain_low: 'About half is left. Top up {p} soon.',
      plain_wrong: 'This spot should hold {p}, but it looks like {q}. Swap them.',
      plain_wrong_nq: 'This spot should hold {p}, but another product seems to be there. Check it.',
      plain_ok: 'Right product, well stocked. Leave alone.',
      plain_ok_fresh: 'Right product, well stocked. When there is time, check freshness and rotate stock.',
      sort_by: 'Sort by', p_attention: 'Needs attention', p_name: 'Name', p_stock: 'Stock', p_areas: 'Areas',
      avg_stock: 'Average stock', elsewhere: 'Found in the wrong place', no_products: 'No product matches.',
      foot: 'Made automatically from camera pictures. When it says “check by eye”, look before you move stock.',
      spark_alt: 'Stock during the day: {a}',
      det_show: 'Show detections', det_n: '{n} products found by the camera model. Hover or tap a box for its name.',
      det_one: '{p} · {c} sure', det_alt: 'Product boxes',
      cnt_u: '≈ {n} visible units', cnt_u1: '≈ 1 visible unit', cnt_p: '≈ {n} visible packs', cnt_p1: '≈ 1 visible pack',
      cnt_in: 'in {a}', cnt_est: 'estimate', cnt_lbl_u: 'Visible units (estimate)', cnt_lbl_p: 'Visible packs (estimate)',
      cnt_note: 'Counted from the product boxes the camera model finds. Items that are stacked or hidden are not counted.',
      foot_cnt: 'Unit counts are estimates of what is visible, not of what is in the store room.',
      tab_insights: 'Insights', ins_title: 'Insights', ins_none: 'Not enough data for insights.',
      ins_sub: 'From {n} pictures taken between {a} and {b}. All numbers are estimates from the camera model.',
      ins_hints: 'Highlights',
      hint_store: 'Across the store, stock goes down fastest {a} to {b}.',
      hint_peak: '{p} sells fastest {a} to {b}.',
      hint_restock: '{p} was topped up {n} times during the day.',
      hint_slow: '{n} products barely moved all day. Check they are still fresh.', hint_slow1: '1 product barely moved all day. Check it is still fresh.',
      soon_title: 'Running out soon', soon_x: 'Areas forecast to be empty within 2 hours. Restock these first.',
      soon_none: 'Nothing is forecast to run empty in the next 2 hours.', soon_in: 'in ~{t}', soon_at: 'around {t}',
      sales_title: 'Sales speed', sales_x: 'Share of a full shelf that leaves per hour, from one picture to the next. Jumps up are restocks, not sales.',
      sales_rate: '{r}% of a shelf per hour', sales_lt1: 'under 1% of a shelf per hour', sales_zero: 'no drop seen',
      sales_tops: 'Topped up at {t}', more_n: 'and {n} more',
      sales_more: 'Show {n} more products', sales_more1: 'Show 1 more product', hourly_title: 'Whole store, by hour', hourly_alt: 'Stock lost per hour of the day: {a}',
      hourly_x: 'Share of a shelf lost per area and hour',
      adh_title: 'Planogram adherence', adh_x: 'Areas that hold the planned product right now, per gondola.',
      adh_rest: 'Show the {n} gondolas that are all right', adh_rest1: 'Show the gondola that is all right', adh_all_n: 'Show all {n} gondolas', adh_all_n1: 'Show the gondola', adh_overall: '{p}% of areas hold the right product', adh_of: '{ok} of {n} areas', adh_fix: '{n} to move back', adh_all: 'All right',
      fr_badge: 'Check freshness / rotate stock', fr_short: 'Check freshness', fr_group: 'When there is time: freshness checks',
      fr_est_restock: 'Estimate: about {h} on display since the last restock seen ({t}). Stock left from before it can be older.',
      fr_est_first: 'Estimate: no restock seen today, so on display at least since the first picture ({t}): {h} or more.',
      fr_rule: '{c} product: check every {l} h.', cls_fast: 'Highly perishable', cls_medium: 'Medium shelf-life', cls_slow: 'Long shelf-life',
      fr_why: 'Based only on the time since restock and the product\'s shelf-life class, not on the picture.',
      fr_src: 'Source: {s} ({e}). Assumes an unrefrigerated display at about 20 °C; chilled displays keep produce longer.',
      fr_edited: 'values edited by the team', conf_high: 'strong evidence', conf_medium: 'moderate evidence', conf_low: 'weak evidence', conf_none: 'evidence not rated',
      fr_look: 'What to look for',
      fr_potato: 'Potatoes keep for weeks, but store lighting can turn them green after 24-60 h of light.',
      fr_line: 'Freshness: {h} on display, check every {l} h (estimate).', fr_h_about: 'about {h}', fr_h_least: 'at least {h}',
      fr_also: 'While there: check freshness and rotate stock ({h} on display, estimate).',
      fr_task: '{h} on display, check every {l} h',
      lay_title: 'Layout & waste', lay_x: 'Layout suggestions from the planogram and a produce biology table. Not seen in the pictures.',
      eth_title: 'Neighbours that speed up ripening', eth_gas: 'Gives off a lot of ethylene, a natural ripening gas. Right next to it:', eth_fx: 'can {fx} sooner.',
      eth_tip: 'Suggestion: leave a gap, or put a product that does not react to ethylene between them.',
      eth_none: 'No strong ethylene producer sits right next to a highly sensitive product.',
      eth_calm: 'Ethylene in an open shop is usually low (Warton et al. 2000), so this is a layout suggestion, not an alarm.',
      eth_mild: '{n} milder pairs (fruit that ripen each other a little faster) are not listed.',
      eth_src: 'Sources: ethylene classes after Kader (Pesis 2004) and USDA Agriculture Handbook 66 (2016). Neighbours are areas that touch or almost touch in the same camera picture.',
      eth_panel: 'Layout suggestion', eth_p_dst: 'Next to {p} ({a}), which gives off a lot of ethylene: this product can {fx} sooner.',
      eth_p_src: 'Gives off a lot of ethylene, and sensitive products are right next to it: {list}.', eth_more: 'See Insights: Layout & waste',
      risk_b: 'Risk {s}/9 · {b}', rb_avoid: 'Avoid', rb_caution: 'Caution', rb_compatible: 'Compatible',
      ra_avoid: 'Keep apart: another gondola, or at least one neutral product between them.',
      ra_caution: 'Separate shelves are fine; take out damaged pieces quickly.', ra_compatible: 'Can share space.',
      risk_credit: 'Score: Inês Matias Medeiros (biology)',
      risk_how: 'Risk = the larger of A’s ethylene output × B’s sensitivity and the reverse (low 1, medium 2, high 3): 1-3 compatible, 4-6 caution, 7-9 avoid.',
      watch_sum: '{n} more product pairs side by side to watch (caution)', watch_sum1: '1 more product pair side by side to watch (caution)',
      fr_ins_title: 'On display longest', fr_ins_x: 'Areas past their product\'s check interval since the last restock seen. An estimate from time and shelf-life class: look for spoilage and move older stock to the front.',
      fr_ins_none: 'No area is past its check interval.', fr_more: 'Show {n} more', fr_val: 'every {l} h',
      fx_avocado: 'ripen and go soft', fx_banana: 'ripen and get brown spots', fx_broccoli: 'turn yellow', fx_cabbage: 'turn yellow',
      fx_cauliflower: 'discolour and drop leaves', fx_cucumber: 'turn yellow and go soft', fx_eggplant: 'get brown patches',
      'fx_green beans': 'turn yellow', fx_kiwi: 'go soft', fx_lettuce: 'get brown spots and turn yellow', fx_tomato: 'ripen and go soft',
      fx_watermelon: 'go soft and over-ripe', fx_other: 'ripen or spoil',
      tab_day: 'Day', day_title: 'The store’s day',
      day_honest: 'Replay of one day with the dataset’s own pictures ({n} pictures from {c} cameras). The model was calibrated on this day, so this shows the experience, not accuracy.',
      day_play: 'Play the day', day_pause: 'Pause', day_slider: 'Time of day', day_at: 'Store at {t}',
      day_todo: 'To do at {t}', day_log: 'What happened', day_log_x: 'Changes between consecutive pictures of each area, newest first. Tap one to see that picture.',
      day_log_none: 'No changes yet.', day_pulse: 'Store pulse', day_pulse_x: 'Empty, low and wrong-product areas every 30 min. Tap a bar to go there.',
      day_frame: 'Picture taken {t}', day_nopic: 'No picture yet at this time', day_more: 'and {n} more', day_cam_todo: '{n} to do', day_pick: 'Tap an area or an event',
      ev_empty: 'went empty', ev_low: 'running low', ev_wrong: 'wrong product on the spot', ev_fixed: 'wrong product fixed', ev_restock: 'restock detected', ev_ok: 'back to OK',
      close_lbl: 'Closing time', close_group: 'Leave until tomorrow (close to closing)',
      close_why: 'The store closes at {c}: topping up short or medium shelf-life produce now leaves more of it out overnight, where it spoils. Restock in the morning. Empty spots and wrong products never wait.',
      close_on: 'Close to closing ({c}): top-ups of perishable produce wait until tomorrow.',
    },
    pt: {
      skip: 'Saltar para o conteúdo', title: 'fresh.', tab_tasks: 'Fazer agora', tab_gondola: 'Gôndolas', tab_products: 'Produtos',
      f_camera: 'Câmara', f_search: 'Pesquisar', search_ph: 'Pesquisar produto ou zona', all_cams: 'Todas as câmaras',
      snapshot: 'Estado às', pics_range: 'Imagens das {a} às {b}', old: 'há {t}', unreadable: 'Imagem ilegível: não verificado',
      clear: 'Limpar filtros', theme: 'Mudar tema claro / escuro', print: 'Imprimir lista de tarefas', lang: 'Idioma',
      s_empty: 'Vazio', s_low: 'Baixo', s_wrong: 'Produto errado', s_ok: 'OK',
      areas_n: '{n} zonas', area1: '1 zona', camera: 'Câmara', area: 'zona',
      long_empty: 'Vazio: nada para vender', long_low: 'Metade: reforçar em breve',
      long_wrong: 'Produto errado neste local', long_ok: 'Tudo certo: deixar como está',
      lv_empty: 'Vazio', lv_half: 'Metade', lv_full: 'Cheio',
      act_restock: 'Repor', act_restock_x: 'está vazio', act_top: 'Reforçar em breve', act_move: 'Trocar',
      act_move_x: 'aqui devia estar {p}, mas está {q}.', take_to: 'Levar {q} para', areas_w: 'zonas',
      act_check: 'Verificar produto', expected: 'esperado', seen: 'visto', belongs: '{q} pertence a', empty_in: 'Vazio daqui a ~{t}', around: 'por volta das {t}',
      empty_now: 'Já deve estar vazio: verificar agora', empty_was: 'previsto para as {t}',
      conf: 'Confiança', c_sure: 'Alta', c_likely: 'Média', c_check: 'Baixa: confirmar à vista', seen_at: 'Visto às {t}',
      partly: 'Parcialmente fora da imagem', stock: 'Stock',
      mark_done: 'Marcar feito', show_gondola: 'Ver na gôndola', tasks_title: 'Fazer agora', n_tasks: '{n} tarefas', n_tasks1: '1 tarefa', progress: '{d} de {n} feitas',
      urgent: 'Primeiro: produto errado e vazio', soon: 'Depois: a ficar baixo', by_priority: 'Por prioridade', by_route: 'Por gôndola',
      leave: 'Deixar: {n} zonas estão certas', leave1: 'Deixar: 1 zona está certa', all_good: 'Tudo certo', all_good_x: 'Nada para fazer neste momento.',
      none_match: 'Nenhuma zona corresponde aos filtros.', done_title: 'Feito',
      pick_area: 'Toque numa zona da imagem', no_picture: 'Sem imagem', planned: 'Produto planeado', seen_instead: 'Visto em vez disso',
      today: 'Stock ao longo do dia', visible: 'Visível', snapshot_of: 'Imagem das', raw: 'Nome no catálogo',
      col_product: 'Produto', col_do: 'O que fazer', todo: '{n} por fazer', every_ok: 'Tudo OK', legend: 'Legenda', zoom_out: 'Ver imagem completa', zoom_in: 'Aproximar às prateleiras',
      plain_empty: 'Nada para vender. Repor {p}.',
      plain_low: 'Resta cerca de metade. Reforçar {p} em breve.',
      plain_wrong: 'Este local devia ter {p}, mas parece haver {q}. Trocar.',
      plain_wrong_nq: 'Este local devia ter {p}, mas parece haver outro produto. Verificar.',
      plain_ok: 'Produto certo e bem abastecido. Deixar como está.',
      plain_ok_fresh: 'Produto certo e bem abastecido. Quando houver tempo, verificar a frescura e rodar o stock.',
      sort_by: 'Ordenar por', p_attention: 'Precisa de atenção', p_name: 'Nome', p_stock: 'Stock', p_areas: 'Zonas',
      avg_stock: 'Stock médio', elsewhere: 'Encontrado no sítio errado', no_products: 'Nenhum produto corresponde.',
      foot: 'Feito automaticamente a partir de imagens das câmaras. Quando diz «confirmar à vista», veja antes de mexer no stock.',
      spark_alt: 'Stock ao longo do dia: {a}',
      det_show: 'Mostrar deteções', det_n: '{n} produtos encontrados pelo modelo. Passe o rato ou toque numa caixa para ver o nome.',
      det_one: '{p} · {c} de certeza', det_alt: 'Caixas de produtos',
      cnt_u: '≈ {n} unidades visíveis', cnt_u1: '≈ 1 unidade visível', cnt_p: '≈ {n} embalagens visíveis', cnt_p1: '≈ 1 embalagem visível',
      cnt_in: 'em {a}', cnt_est: 'estimativa', cnt_lbl_u: 'Unidades visíveis (estimativa)', cnt_lbl_p: 'Embalagens visíveis (estimativa)',
      cnt_note: 'Contado a partir das caixas de produtos que o modelo encontra. Artigos empilhados ou escondidos não são contados.',
      foot_cnt: 'As contagens são estimativas do que se vê, não do que está no armazém.',
      tab_insights: 'Análise', ins_title: 'Análise', ins_none: 'Dados insuficientes para a análise.',
      ins_sub: 'Com {n} imagens tiradas entre as {a} e as {b}. Todos os valores são estimativas do modelo.',
      ins_hints: 'Destaques',
      hint_store: 'Em toda a loja, o stock desce mais depressa das {a} às {b}.',
      hint_peak: '{p} vende mais depressa das {a} às {b}.',
      hint_restock: 'Reposições de {p} durante o dia: {n}.',
      hint_slow: '{n} produtos quase não mexeram durante o dia. Verifique se ainda estão frescos.', hint_slow1: '1 produto quase não mexeu durante o dia. Verifique se ainda está fresco.',
      soon_title: 'A acabar em breve', soon_x: 'Zonas previstas ficarem vazias nas próximas 2 horas. Repor primeiro.',
      soon_none: 'Nenhuma zona deverá ficar vazia nas próximas 2 horas.', soon_in: 'daqui a ~{t}', soon_at: 'por volta das {t}',
      sales_title: 'Velocidade de vendas', sales_x: 'Parte de uma prateleira cheia que sai por hora, de uma imagem para a seguinte. Subidas são reposições, não vendas.',
      sales_rate: '{r}% de uma prateleira por hora', sales_lt1: 'menos de 1% de uma prateleira por hora', sales_zero: 'sem descida',
      sales_tops: 'Reposto às {t}', more_n: 'e mais {n}',
      sales_more: 'Mostrar mais {n} produtos', sales_more1: 'Mostrar mais 1 produto', hourly_title: 'Toda a loja, por hora', hourly_alt: 'Stock perdido por hora do dia: {a}',
      hourly_x: 'Parte de uma prateleira perdida por zona e hora',
      adh_title: 'Cumprimento do planograma', adh_x: 'Zonas com o produto planeado neste momento, por gôndola.',
      adh_rest: 'Mostrar as {n} gôndolas que estão certas', adh_rest1: 'Mostrar a gôndola que está certa', adh_all_n: 'Mostrar as {n} gôndolas', adh_all_n1: 'Mostrar a gôndola', adh_overall: '{p}% das zonas têm o produto certo', adh_of: '{ok} de {n} zonas', adh_fix: '{n} a devolver ao lugar', adh_all: 'Tudo certo',
      fr_badge: 'Verificar frescura / rodar stock', fr_short: 'Verificar frescura', fr_group: 'Quando houver tempo: verificar frescura',
      fr_est_restock: 'Estimativa: cerca de {h} em exposição desde a última reposição vista ({t}). O stock que já lá estava pode ser mais antigo.',
      fr_est_first: 'Estimativa: sem reposição vista hoje, por isso em exposição pelo menos desde a primeira imagem ({t}): {h} ou mais.',
      fr_rule: '{c}: verificar a cada {l} h.', cls_fast: 'Produto muito perecível', cls_medium: 'Produto de conservação média', cls_slow: 'Produto de longa conservação',
      fr_why: 'Com base apenas no tempo desde a reposição e na classe de conservação do produto, e não na imagem.',
      fr_src: 'Fonte: {s} ({e}). Pressupõe exposição sem refrigeração, a cerca de 20 °C; em expositores refrigerados os produtos duram mais.',
      fr_edited: 'valores editados pela equipa', conf_high: 'evidência forte', conf_medium: 'evidência moderada', conf_low: 'evidência fraca', conf_none: 'evidência não classificada',
      fr_look: 'O que procurar',
      fr_potato: 'As batatas duram semanas, mas a luz da loja pode torná-las verdes ao fim de 24 a 60 h de exposição à luz.',
      fr_line: 'Frescura: {h} em exposição, verificar a cada {l} h (estimativa).', fr_h_about: 'cerca de {h}', fr_h_least: 'pelo menos {h}',
      fr_also: 'Aproveitar para verificar a frescura e rodar o stock ({h} em exposição, estimativa).',
      fr_task: '{h} em exposição, verificar a cada {l} h',
      lay_title: 'Disposição e desperdício', lay_x: 'Sugestões de disposição a partir do planograma e de uma tabela de biologia dos produtos. Não são vistas nas imagens.',
      eth_title: 'Vizinhos que aceleram o amadurecimento', eth_gas: 'Liberta muito etileno, um gás natural de amadurecimento. Mesmo ao lado:', eth_fx: 'pode {fx} mais cedo.',
      eth_tip: 'Sugestão: deixar espaço ou pôr entre eles um produto que não reaja ao etileno.',
      eth_none: 'Nenhum grande produtor de etileno está mesmo ao lado de um produto muito sensível.',
      eth_calm: 'Numa loja aberta o etileno costuma ser baixo (Warton et al. 2000): é uma sugestão de disposição, não um alarme.',
      eth_mild: 'Não se listam {n} pares menos graves (frutas que fazem amadurecer umas às outras um pouco mais depressa).',
      eth_src: 'Fontes: classes de etileno segundo Kader (Pesis 2004) e USDA Agriculture Handbook 66 (2016). Vizinhos são zonas que se tocam, ou quase, na mesma imagem de câmara.',
      eth_panel: 'Sugestão de disposição', eth_p_dst: 'Ao lado de {p} ({a}), que liberta muito etileno: este produto pode {fx} mais cedo.',
      eth_p_src: 'Liberta muito etileno e tem produtos sensíveis mesmo ao lado: {list}.', eth_more: 'Ver Análise: Disposição e desperdício',
      risk_b: 'Risco {s}/9 · {b}', rb_avoid: 'Evitar', rb_caution: 'Cuidado', rb_compatible: 'Compatível',
      ra_avoid: 'Manter afastados: outra gôndola, ou pelo menos um produto neutro entre eles.',
      ra_caution: 'Prateleiras separadas chegam; retirar depressa as peças danificadas.', ra_compatible: 'Podem partilhar o espaço.',
      risk_credit: 'Pontuação: Inês Matias Medeiros (biologia)',
      risk_how: 'Risco = o maior entre o etileno libertado por A × a sensibilidade de B e o inverso (baixo 1, médio 2, alto 3): 1-3 compatível, 4-6 cuidado, 7-9 evitar.',
      watch_sum: 'Mais {n} pares de produtos lado a lado a vigiar (cuidado)', watch_sum1: 'Mais 1 par de produtos lado a lado a vigiar (cuidado)',
      fr_ins_title: 'Há mais tempo em exposição', fr_ins_x: 'Zonas que já passaram o intervalo de verificação do produto desde a última reposição vista. Estimativa a partir do tempo e da classe de conservação: procurar sinais de estrago e passar o stock mais antigo para a frente.',
      fr_ins_none: 'Nenhuma zona passou o intervalo de verificação.', fr_more: 'Mostrar mais {n}', fr_val: 'a cada {l} h',
      fx_avocado: 'amadurecer e amolecer', fx_banana: 'amadurecer e ganhar pintas castanhas', fx_broccoli: 'amarelecer', fx_cabbage: 'amarelecer',
      fx_cauliflower: 'escurecer e perder folhas', fx_cucumber: 'amarelecer e amolecer', fx_eggplant: 'ganhar manchas castanhas',
      'fx_green beans': 'amarelecer', fx_kiwi: 'amolecer', fx_lettuce: 'ganhar manchas castanhas e amarelecer', fx_tomato: 'amadurecer e amolecer',
      fx_watermelon: 'amolecer e passar do ponto', fx_other: 'amadurecer ou estragar-se',
      tab_day: 'Dia', day_title: 'O dia da loja',
      day_honest: 'Repetição de um dia com as próprias imagens do conjunto de dados ({n} imagens de {c} câmaras). O modelo foi calibrado neste dia: isto mostra a experiência, não a precisão.',
      day_play: 'Reproduzir o dia', day_pause: 'Pausa', day_slider: 'Hora do dia', day_at: 'Loja às {t}',
      day_todo: 'Por fazer às {t}', day_log: 'O que aconteceu', day_log_x: 'Mudanças entre imagens seguidas de cada zona, as mais recentes primeiro. Toque numa para ver essa imagem.',
      day_log_none: 'Ainda sem mudanças.', day_pulse: 'Pulso da loja', day_pulse_x: 'Zonas vazias, baixas e com produto errado, a cada 30 min. Toque numa barra para ir para essa hora.',
      day_frame: 'Imagem das {t}', day_nopic: 'Ainda sem imagem a esta hora', day_more: 'e mais {n}', day_cam_todo: '{n} por fazer', day_pick: 'Toque numa zona ou num evento',
      ev_empty: 'ficou vazia', ev_low: 'ficou baixa', ev_wrong: 'produto errado no lugar', ev_fixed: 'produto errado corrigido', ev_restock: 'reposição detetada', ev_ok: 'voltou a OK',
      close_lbl: 'Hora de fecho', close_group: 'Deixar até amanhã (perto do fecho)',
      close_why: 'A loja fecha às {c}: reforçar agora fruta e legumes de conservação curta ou média deixa mais produto exposto durante a noite, onde se estraga. Repor de manhã. Vazios e produtos errados nunca esperam.',
      close_on: 'Perto do fecho ({c}): os reforços de produtos perecíveis ficam para amanhã.',
    },
  };

  /* Product-box labels are the English detector queries; staff in PT mode get Portuguese names. */
  const DET_PT = {
    'bananas': 'bananas', 'oranges': 'laranjas', 'net bags of oranges': 'sacos de laranjas', 'lemons': 'limões', 'limes': 'limas',
    'clementines': 'clementinas', 'apples': 'maçãs', 'green apples': 'maçãs verdes', 'red apples': 'maçãs vermelhas',
    'yellow apples': 'maçãs amarelas', 'pears': 'peras', 'kiwis': 'quivis', 'packs of kiwis': 'embalagens de quivis',
    'melons': 'melões', 'watermelons': 'melancias', 'cantaloupes': 'melões cantalupe', 'mangoes': 'mangas', 'pineapples': 'ananases',
    'papayas': 'papaias', 'passion fruits': 'maracujás', 'dragon fruits': 'pitaias', 'guavas': 'goiabas', 'white grapes': 'uvas brancas',
    'red grapes': 'uvas tintas', 'packs of cherries': 'embalagens de cerejas', 'packs of strawberries': 'embalagens de morangos',
    'apricots': 'alperces', 'peaches': 'pêssegos', 'flat peaches': 'pêssegos planos', 'nectarines': 'nectarinas', 'tomatoes': 'tomates',
    'tomatoes on the vine': 'tomates em ramo', 'packs of cherry tomatoes': 'embalagens de tomate cherry',
    'oxheart tomatoes': 'tomates coração de boi', 'plum tomatoes': 'tomates pera', 'potatoes': 'batatas', 'bags of potatoes': 'sacos de batatas',
    'red potatoes': 'batatas vermelhas', 'sweet potatoes': 'batatas-doces', 'onions': 'cebolas', 'red onions': 'cebolas roxas',
    'bags of onions': 'sacos de cebolas', 'garlic': 'alho', 'packs of garlic': 'embalagens de alho', 'pumpkins': 'abóboras',
    'ginger': 'gengibre', 'bagged lettuce': 'alface em saco', 'avocados': 'abacates', 'green peppers': 'pimentos verdes',
    'red peppers': 'pimentos vermelhos', 'cabbages': 'couves', 'red cabbages': 'couves roxas', 'broccoli': 'brócolos',
    'cauliflowers': 'couves-flores', 'kale': 'couve kale', 'zucchini': 'curgetes', 'eggplants': 'beringelas', 'chayotes': 'chuchus',
    'green beans': 'feijão-verde', 'cucumbers': 'pepinos', 'shallots': 'chalotas', 'a plastic package of fruit': 'embalagem de plástico com fruta',
    'a net bag': 'saco de rede',
  };

  /* ------------------------------------------------------------------ state */
  const STATUS = ['empty', 'low', 'wrong', 'ok'];               // counter order
  const ORDER = { wrong: 0, empty: 1, low: 2, ok: 3 };
  const LV_ICON = { empty: 'i-empty', half: 'i-low', full: 'i-full' };
  const LV_CLASS = { empty: 's-empty', half: 's-low', full: 's-ok' };
  const SAME_LV = { empty: 'empty', low: 'half', ok: 'full' };      // status words that already say the level
  const S_ICON = { empty: 'i-empty', low: 'i-low', wrong: 'i-wrong', ok: 'i-ok' };
  const RP = D.replay && D.replay.frames && Object.keys(D.replay.frames).length ? D.replay : null;   /* several frames per camera */
  const VIEWS = ['tasks', 'gondola', 'products', 'insights'].concat(RP ? ['day'] : []);

  const areas = D.areas;
  const areaById = Object.fromEntries(areas.map((a) => [a.id, a]));
  const camById = Object.fromEntries(D.cameras.map((c) => [c.id, c]));
  const detLabels = D.det_labels || [];
  const INS = D.insights || {};
  const BIO = D.bio || {};
  const PAIRS = (INS.layout && INS.layout.pairs) || [];
  const hasCounts = areas.some((a) => a.n != null);        // item counts exist only when product boxes were available
  const byPid = {};
  areas.forEach((a) => { if (!byPid[a.pid]) byPid[a.pid] = a; });
  const hasDet = (c) => !!(c && c.frame && c.det && c.det.length);
  const detName = (i) => { const en = detLabels[i] || ''; return cap(st.lang === 'pt' ? (DET_PT[en] || en) : en); };
  const st = {
    view: 'tasks', lang: store.get('sensei.lang', (window.SHELF_DATA && window.SHELF_DATA.lang) || 'pt'), theme: store.get('sensei.theme', 'auto'),
    status: null, full: false, cam: 'all', q: '', sort: 'priority', gcam: null, sel: null, psort: 'attention', pdir: 1,
    det: false, dsel: null, dcam: null,   // product boxes: toggle, tapped box index, camera it belongs to
    close: store.get('sensei.close', '21:00'),          // closing time (closing-time mode)
    dt: RP ? RP.t1 : 0, dplay: false, dgc: null, dga: null,   // Day view: time shown, playing, camera and area picked
  };
  if (!/^\d{1,2}:\d{2}$/.test(String(st.close))) st.close = '21:00';
  if (!T[st.lang]) st.lang = 'en';
  let done = store.get('sensei.done.v1', {});
  const scrollMem = {};

  const t = (k, v) => {
    let s = (T[st.lang][k] != null ? T[st.lang][k] : T.en[k]) || k;
    if (v) for (const key in v) s = s.split('{' + key + '}').join(v[key]);
    return s;
  };
  /* count-dependent text: the '<key>1' singular when n is 1 and the language has one */
  const tn = (k, n, v) => t(n === 1 && T[st.lang][k + '1'] != null ? k + '1' : k, Object.assign({ n }, v || {}));

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
    const m = Math.max(5, Math.round(s / 300) * 5);        /* 5-minute steps */
    if (m < 60) return m + ' min';
    if (m < 180) return Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + (m % 60) + ' min' : '');
    return Math.round(s / 3600) + ' h';
  }
  const pct = (x) => Math.round(x * 100) + '%';
  const hh = (h) => String(h).padStart(2, '0') + ':00';
  const areaWord = (k) => (k === 1 ? t('area1') : t('areas_n', { n: k }));
  /* Item counts: "≈ 12 visible units" (loose produce) or "visible packs" (packaged). A wrong-product area is not a pack of the planned product. */
  const isPack = (a) => a.loose === false && a.status !== 'wrong';
  const unitsTxt = (n, pack) => t((pack ? 'cnt_p' : 'cnt_u') + (n === 1 ? '1' : ''), { n });

  /* ------------------------------------------------------------------ names, labels */
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const pair = (en, pt) => {
    const p = st.lang === 'pt' ? { main: pt, sub: cap(en) } : { main: cap(en), sub: pt };
    if (norm(p.main) === norm(p.sub)) p.sub = '';
    return p;
  };
  const nm = (a) => (st.lang === 'pt' ? { main: a.pt, sub: '' } : pair(a.en, a.pt));
  const seenName = (a) => (a.len ? (st.lang === 'pt' ? a.lpt : a.len) : '');
  const loc = (a) => `${t('camera')} ${esc(a.cam)} · ${t('area')} ${esc(a.num)}`;
  const camTs = (a) => (camById[a.cam] ? camById[a.cam].ts : D.snapshot_ts);
  const FC_MAX_S = 4 * 3600;   // longer forecasts are not actionable on this shift
  const fcShow = (a) => a.fc != null && a.fc > 0 && a.fc < FC_MAX_S && (a.status === 'low' || a.status === 'wrong');
  /* Closing-time mode: in the last 2 hours before closing, topping up short / medium shelf-life produce waits until
     tomorrow (less produce out overnight). Empty spots and wrong products never wait. */
  const CLOSE_WIN_MIN = 120;
  const hmToMin = (s) => { const m = /^(\d{1,2}):(\d{2})/.exec(String(s || '')); return m ? (+m[1] % 24) * 60 + +m[2] : null; };
  const closeMin = () => { const m = hmToMin(st.close); return m == null ? 21 * 60 : m; };
  const localMin = (ts) => hmToMin(fmt('time').format(new Date(ts * 1000)));
  const nearClose = (ts) => { if (ts == null) return false; const m = localMin(ts); const c = closeMin(); return m != null && m >= c - CLOSE_WIN_MIN && m < c; };
  const canWait = (a, status) => (status || a.status) === 'low' && (a.pcls === 'fast' || a.pcls === 'medium');
  const closeGroup = (list, card) => (list.length ? `<h3 class="group-title g-close">${icon('i-moon')}${t('close_group')} <span class="count">${list.length}</span></h3><p class="close-why">${t('close_why', { c: esc(st.close) })}</p><div class="cards">${list.map(card).join('')}</div>` : '');
  function closeOpts() {
    const cur = closeMin(); const opts = [];
    for (let m = 12 * 60; m <= 24 * 60 - 30; m += 30) opts.push(m);
    if (opts.indexOf(cur) < 0) opts.push(cur);
    return opts.sort((x, y) => x - y).map((m) => { const v = `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`; return `<option value="${v}"${m === cur ? ' selected' : ''}>${v}</option>`; }).join('');
  }
  const OLD_S = 1800;          // pictures older than this vs the newest one get an age chip
  /* forecast "empty in ~N" counted from the snapshot (the newest picture), not from this camera's older frame */
  const fcLeft = (a) => camTs(a) + a.fc - (D.snapshot_ts != null ? D.snapshot_ts : camTs(a));
  const fcText = (a) => (fcLeft(a) <= 0 ? `<b class="now">${t('empty_now')}</b> (${t('empty_was', { t: fmtTime(camTs(a) + a.fc) })})`
    : t('empty_in', { t: dur(fcLeft(a)) }));
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

  /* Freshness watch and ethylene neighbours (sensei/freshness.py): estimates from time since restock and the
     product's biology, never read from the picture. Absent data = no badge. */
  const freshDue = (a) => !!(a.fresh && a.fresh.due);
  const isTask = (a) => a.status !== 'ok' || freshDue(a);     // anything with a card (incl. freshness checks)
  const isJob = (a) => a.status !== 'ok';                      // counted as a task: freshness checks are extras
  const bioOf = (a) => (a.bk && BIO[a.bk]) || null;
  const freshBadge = (short) => `<span class="badge s-fresh">${icon('i-leaf')}${t(short ? 'fr_short' : 'fr_badge')}</span>`;
  const hrs = (h) => dur(h * 3600);
  /* hours on display: 'about' since a restock seen, 'at least' when counted from the first picture of the day */
  const freshH = (a) => t(a.fresh.basis === 'first' ? 'fr_h_least' : 'fr_h_about', { h: hrs(a.fresh.h) });
  function freshEst(a) {
    const f = a.fresh; const b = bioOf(a) || {};
    const est = t(f.basis === 'restock' ? 'fr_est_restock' : 'fr_est_first', { h: hrs(f.h), t: fmtTime(f.since) });
    const rule = b.cls ? ' ' + t('fr_rule', { c: t('cls_' + b.cls), l: f.lim }) : '';
    return est + rule + (b.type === 'potato' ? ' ' + t('fr_potato') : '');   /* slow class, short interval: say why */
  }
  function freshSrc(a) {
    const b = bioOf(a) || {};
    const ev = b.edited ? t('fr_edited') : t(b.conf ? 'conf_' + b.conf : 'conf_none');
    return t('fr_src', { s: esc(b.src || 'docs/produce_biology_reference.csv'), e: ev });
  }
  /* The product actually on the shelf: the likely one when the spot holds the wrong product. */
  const shelfName = (a) => (a.status === 'wrong' && a.len ? (st.lang === 'pt' ? a.lpt : cap(a.len)) : nm(a).main);
  const fxText = (type) => t(T.en['fx_' + type] ? 'fx_' + type : 'fx_other');
  const areaRef = (a) => `${t('area')} ${esc(a.num)}`;
  const pairsOf = (a) => PAIRS.filter((p) => p.src === a.id || p.dst === a.id);
  /* Ines' ethylene compatibility score (sensei/freshness.py ethylene_score): 1-9 with a band; absent = no badge */
  const WATCH = (INS.layout && INS.layout.watch) || [];
  const RB_ICON = { avoid: 'i-wrong', caution: 'i-low', compatible: 'i-ok' };
  const hasRisk = (p) => p && p.score != null && RB_ICON[p.band];
  const riskBadge = (p) => hasRisk(p) ? `<span class="risk-b rb-${p.band}">${icon(RB_ICON[p.band])}${t('risk_b', { s: p.score, b: t('rb_' + p.band) })}</span>` : '';
  const riskAdvice = (p) => hasRisk(p) ? `<span class="risk-adv">${t('ra_' + p.band)}</span>` : '';
  const riskCredit = () => `<p class="risk-credit">${icon('i-leaf')}${t('risk_credit')}</p>`;
  const maxScore = (ps) => ps.reduce((m, p) => Math.max(m, p.score || 0), 0);
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
    ? `<img class="${cls}" src="${esc(a.crop)}" alt="${esc(nm(a).main)}" loading="lazy" decoding="async">`
    : `<div class="ph">${t('no_picture')}</div>`);

  /* ------------------------------------------------------------------ task cards */
  function actionHtml(a) {
    if (a.status === 'empty') return `<strong>${t('act_restock')}</strong>: ${t('act_restock_x')}`;
    if (a.status === 'low') {
      const f = fcShow(a) ? `. ${fcText(a)}` : '';
      return `<strong>${t('act_top')}</strong>${f}`;
    }
    if (a.status === 'wrong') {
      const p = esc(nm(a).main); const q = esc(seenName(a));
      return q ? `<strong>${t('act_move')}</strong>: ${t('act_move_x', { p, q })}`
        : `<strong>${t('act_check')}</strong>: ${t('expected')} ${p}`;
    }
    if (freshDue(a)) {
      return `<strong>${t('fr_badge')}</strong>: ${t('fr_task', { h: freshH(a), l: a.fresh.lim })} <span class="muted">(${t('cnt_est')})</span>`;
    }
    return t('long_ok');
  }
  function homeHtml(a) {
    if (a.status !== 'wrong' || !a.home || !a.home.length) return '';
    const byCam = {};
    a.home.map((id) => areaById[id]).filter(Boolean).forEach((h) => { (byCam[h.cam] = byCam[h.cam] || []).push(esc(h.num)); });
    const links = Object.keys(byCam).map((c) => `${t('camera')} ${esc(c)} · ${byCam[c].length === 1 ? t('area') : t('areas_w')} ${
      byCam[c].join(', ')}`).join('; ');
    return links ? `<p class="home">${t('take_to', { q: esc(seenName(a)) })}: ${links}</p>` : '';
  }
  function metaHtml(a) {
    /* a freshness-only task is a time estimate: the stock model's confidence would read as confidence in freshness */
    const bits = a.status === 'ok' ? [] : [`<span>${t('conf')}: <b>${t(confKey(a.conf))}</b></span>`];
    if (a.status === 'wrong' && a.level !== 'full') bits.push(`<span>${t('stock')}: <b>${t('lv_' + a.level)}</b></span>`);
    if (a.vis != null && a.vis < 0.7) bits.push(`<span>${t('partly')}</span>`);
    bits.push(`<span>${icon('i-clock')} ${t('seen_at', { t: fmtTime(camTs(a)) })}</span>`);
    const age = ageChip(camTs(a));
    if (age) bits.push(age);
    return bits.join('');
  }
  function taskCard(a) {
    const n = nm(a); const key = taskKey(a); const isDone = !!done[key];
    return `<article class="task s-${a.status === 'ok' && freshDue(a) ? 'fresh' : a.status}${isDone ? ' is-done' : ''}" data-key="${esc(key)}">
      <div class="task-head">${a.status === 'ok' && freshDue(a) ? freshBadge(true) : badge(a.status)}<span class="loc">${loc(a)}</span></div>
      <h3 class="pname"><a href="${hrefOf(a)}">${esc(n.main)}</a><small>${esc(n.sub)}</small></h3>
      <p class="action">${actionHtml(a)}</p>${homeHtml(a)}${
  a.status !== 'ok' && freshDue(a) ? `<p class="fresh-note">${icon('i-leaf')}<span>${t('fr_also', { h: freshH(a) })}</span></p>` : ''}
      <div class="media">${ctxThumb(a)}${cropImg(a)}</div>
      <div class="meta">${metaHtml(a)}</div>
      <div class="task-foot">
        <label class="done"><input type="checkbox" data-act="done" data-key="${esc(key)}"${isDone ? ' checked' : ''}> ${t('mark_done')}</label>
        <span class="go">${t('show_gondola')} ${icon('i-arrow')}</span>
      </div></article>`;
  }

  function renderTasks() {
    const el = $('#view-tasks');
    const all = areas.filter(isTask);
    const tasks = areas.filter((a) => isJob(a) && matches(a));                 /* = the Empty + Low + Wrong counters */
    const closing = nearClose(D.snapshot_ts);
    const wait = closing ? tasks.filter((a) => canWait(a)).sort((x, y) => y.pri - x.pri || sortRoute(x, y)) : [];
    const now = tasks.filter((a) => wait.indexOf(a) < 0);
    const freshAll = areas.filter((a) => a.status === 'ok' && freshDue(a) && matches(a));
    const doneN = tasks.filter((a) => done[taskKey(a)]).length;
    const showOk = st.status === 'ok' || st.status === null;
    const oks = areas.filter((a) => a.status === 'ok' && matches(a));          /* = the OK counter */
    let html = `<div class="view-head"><h2>${t('tasks_title')} <span class="muted">· ${tn('n_tasks', tasks.length)}</span></h2>
      <div class="prog-wrap"><div class="progress" role="progressbar" aria-label="${t('tasks_title')}" aria-valuemin="0" aria-valuemax="${tasks.length}" aria-valuenow="${doneN}"><i style="width:${tasks.length ? (100 * doneN) / tasks.length : 0}%"></i></div>
      <span class="muted" id="prog-txt">${t('progress', { d: doneN, n: tasks.length })}</span></div>
      <div class="seg" role="group" aria-label="${t('sort_by')}">
        <button type="button" data-act="sort" data-v="priority" aria-pressed="${st.sort === 'priority'}">${t('by_priority')}</button>
        <button type="button" data-act="sort" data-v="route" aria-pressed="${st.sort === 'route'}">${t('by_route')}</button></div>
      <label class="close-set">${icon('i-moon')}<span>${t('close_lbl')}</span><select id="close-time">${closeOpts()}</select></label></div>
      ${closing ? `<p class="close-note">${icon('i-moon')}<span>${t('close_on', { c: esc(st.close) })}</span></p>` : ''}`;
    /* freshness checks never outrank restock or wrong-product tasks: own group, last, most overdue first */
    const fresh = freshAll.slice().sort((x, y) => y.fresh.h / y.fresh.lim - x.fresh.h / x.fresh.lim || sortRoute(x, y));
    const freshGroup = fresh.length ? `<h3 class="group-title">${icon('i-leaf', 'g-fresh')}${t('fr_group')} <span class="count">${fresh.length}</span></h3><div class="cards">${fresh.map(taskCard).join('')}</div>` : '';
    if (!tasks.length && !fresh.length && st.status !== 'ok') {
      html += all.length ? `<div class="allgood"><h3>${t('none_match')}</h3></div>`
        : `<div class="allgood">${icon('i-ok')}<h3>${t('all_good')}</h3><p class="muted">${t('all_good_x')}</p></div>`;
    } else if (st.sort === 'priority') {
      const sorted = now.slice().sort((x, y) => y.pri - x.pri || sortRoute(x, y));
      /* wrong product first (the item has to be carried elsewhere), then empty */
      const urgent = sorted.filter((a) => a.status === 'wrong').concat(sorted.filter((a) => a.status === 'empty'));
      const soon = sorted.filter((a) => a.status === 'low');
      if (urgent.length) html += `<h3 class="group-title">${t('urgent')} <span class="count">${urgent.length}</span></h3><div class="cards">${urgent.map(taskCard).join('')}</div>`;
      if (soon.length) html += `<h3 class="group-title">${t('soon')} <span class="count">${soon.length}</span></h3><div class="cards">${soon.map(taskCard).join('')}</div>`;
      html += closeGroup(wait, taskCard) + freshGroup;
    } else {
      const byCam = {};
      now.slice().sort(sortRoute).forEach((a) => { (byCam[a.cam] = byCam[a.cam] || []).push(a); });
      Object.keys(byCam).forEach((c) => {
        html += `<h3 class="group-title">${t('camera')} ${esc(c)} <span class="count">${byCam[c].length}</span></h3><div class="cards">${byCam[c].sort((x, y) => y.pri - x.pri).map(taskCard).join('')}</div>`;
      });
      html += closeGroup(wait, taskCard) + freshGroup;
    }
    if (showOk && oks.length) html += leaveHtml(oks, st.status === 'ok');
    el.innerHTML = html;
  }
  function leaveHtml(oks, open) {
    const byCam = {};
    oks.slice().sort(sortRoute).forEach((a) => { (byCam[a.cam] = byCam[a.cam] || []).push(a); });
    const body = Object.keys(byCam).map((c) => `<div class="leave-cam"><h4>${t('camera')} ${esc(c)}</h4><div class="pill-row">${
      byCam[c].map((a) => `<a class="pill s-ok" href="${hrefOf(a)}">${icon('i-ok')}${esc(a.num)} · ${esc(nm(a).main)}</a>`).join('')}</div></div>`).join('');
    return `<details class="leave"${open ? ' open' : ''}><summary>${icon('i-ok')}${tn('leave', oks.length)}</summary><div class="leave-body">${body}</div></details>`;
  }
  function updateProgress() {
    const tasks = areas.filter((a) => isJob(a) && matches(a));
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
    return t(freshDue(a) ? 'plain_ok_fresh' : 'plain_ok');
  }
  function freshHtml(a) {
    if (!a.fresh) return '';
    const b = bioOf(a) || {};
    if (!freshDue(a)) {
      return a.level === 'empty' ? '' : `<p class="fresh-line">${icon('i-leaf')}<span>${t('fr_line', { h: freshH(a), l: a.fresh.lim })}</span></p>`;
    }
    const look = b.signs && st.lang !== 'pt' ? `<details class="look"><summary>${t('fr_look')}</summary><p>${esc(b.signs)}</p></details>` : '';
    return `<div class="fresh-box s-fresh">${freshBadge(false)}<p>${freshEst(a)}</p><p class="small muted">${t('fr_why')} ${freshSrc(a)}</p>${look}</div>`;
  }
  function ethHtml(a) {
    const ps = pairsOf(a).slice().sort((x, y) => (y.score || 0) - (x.score || 0));
    if (!ps.length) return '';
    const lines = [];
    const srcPs = ps.filter((p) => p.src === a.id && areaById[p.dst]);
    if (srcPs.length && srcPs.some(hasRisk)) {          // scored: one line per neighbour with its badge
      lines.push(`${t('eth_gas')}</p><ul class="risk-ul">${srcPs.map((p) => { const x = areaById[p.dst]; return `<li>${esc(shelfName(x))} (${areaRef(x)}) ${riskBadge(p)}</li>`; }).join('')}</ul><p hidden>`);
    } else if (srcPs.length) lines.push(t('eth_p_src', { list: srcPs.map((p) => { const x = areaById[p.dst]; return `${esc(shelfName(x))} (${areaRef(x)})`; }).join(', ') }));
    ps.filter((p) => p.dst === a.id).forEach((p) => {
      const s = areaById[p.src]; if (s) lines.push(t('eth_p_dst', { p: esc(shelfName(s)), a: areaRef(s), fx: fxText(p.dst_type) }) + (hasRisk(p) ? ' ' + riskBadge(p) : ''));
    });
    const top = ps.find(hasRisk);
    const adv = top ? `<p class="risk-line">${riskAdvice(top)}</p>${riskCredit()}` : '';
    return `<div class="eth-box">${icon('i-gas')}<div><b>${t('eth_panel')}</b>${lines.map((l) => `<p>${l}</p>`).join('')}${adv}<a href="#/insights/layout">${t('eth_more')}</a></div></div>`;
  }
  function panelHtml(a) {
    if (!a) return `<p class="panel-hint">${t('pick_area')}</p>`;
    const n = nm(a); const key = taskKey(a); const isDone = !!done[key];
    const fcTxt = fcShow(a)
      ? `<div class="forecast">${icon('i-clock')}<span>${fcLeft(a) <= 0 ? fcText(a) : `${fcText(a)} (${t('around', { t: fmtTime(camTs(a) + a.fc) })})`}</span></div>` : '';
    const rows = [[t('planned'), esc(nm(a).main)]];
    if (a.status === 'wrong' && seenName(a)) rows.push([t('seen_instead'), esc(seenName(a))]);
    rows.push([t('conf'), t(confKey(a.conf))]);
    if (a.n != null) rows.push([t(isPack(a) ? 'cnt_lbl_p' : 'cnt_lbl_u'), `≈ ${a.n}`]);
    if (a.vis != null && a.vis < 0.95) rows.push([t('visible'), pct(a.vis)]);
    rows.push([t('snapshot_of'), fmtTime(camTs(a)) + (ageChip(camTs(a)) ? ` (${t('old', { t: dur(D.snapshot_ts - camTs(a)) })})` : '')]);
    rows.push([t('raw'), esc(a.raw)]);
    return `<div class="task-head">${badge(a.status)}<span class="loc">${loc(a)}</span></div>
      ${a.crop ? `<img class="crop" src="${esc(a.crop)}" alt="${esc(nm(a).main)}">` : ''}
      <h3 class="pname">${esc(n.main)}<small>${esc(n.sub)}</small></h3>
      <p class="plain">${plainText(a)}</p>${homeHtml(a)}${freshHtml(a)}${ethHtml(a)}
      ${levelsHtml(a)}${fcTxt}${sparkHtml(a)}
      <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${a.n != null ? `<p class="note">${t('cnt_note')}</p>` : ''}
      ${isTask(a) ? `<label class="done"><input type="checkbox" data-act="done" data-key="${esc(key)}"${isDone ? ' checked' : ''}> ${t('mark_done')}</label>` : ''}`;
  }
  /* Product boxes: pointer-events are off on the boxes (area polygons stay tappable), so the box under the pointer is found by hand. */
  function detReadout(dets) {
    const b = st.dsel != null ? dets[st.dsel] : null;
    return b ? t('det_one', { p: `<b>${esc(detName(b[4]))}</b>`, c: pct(b[5]) }) : t('det_n', { n: dets.length });
  }
  function detAt(e) {
    const wrap = e.target.closest ? e.target.closest('.frame-wrap') : null;
    const svg = wrap && $('svg.overlay', wrap); const cam = camById[st.gcam];
    if (!svg || !st.det || !hasDet(cam)) return null;
    const r = svg.getBoundingClientRect(); const vb = svg.viewBox.baseVal;
    if (!r.width || !r.height) return null;
    const x = vb.x + ((e.clientX - r.left) / r.width) * vb.width; const y = vb.y + ((e.clientY - r.top) / r.height) * vb.height;
    let best = -1; let bestA = Infinity;
    cam.det.forEach((b, i) => {
      if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) { const ar = (b[2] - b[0]) * (b[3] - b[1]); if (ar < bestA) { bestA = ar; best = i; } }
    });
    return { i: best, wrap, r };
  }
  function paintDet(hot) {
    const cam = camById[st.gcam]; if (!hasDet(cam) || !st.det) return;
    $$('.dbox').forEach((n) => {
      const i = +n.dataset.i;
      n.classList.toggle('sel', i === st.dsel);
      n.classList.toggle('hot', hot != null && i === hot && i !== st.dsel);
    });
    const ro = $('#det-readout'); if (ro) ro.innerHTML = detReadout(cam.det);
  }
  document.addEventListener('pointermove', (e) => {
    const tip = $('#dtip');
    if (!st.det || e.pointerType === 'touch') { if (tip) tip.hidden = true; return; }
    const h = detAt(e);
    if (!h || h.i < 0) { if (tip) tip.hidden = true; paintDet(null); return; }
    const b = camById[st.gcam].det[h.i];
    paintDet(h.i);
    if (!tip) return;
    tip.textContent = `${detName(b[4])} · ${pct(b[5])}`; tip.hidden = false;
    const left = e.clientX - h.r.left + 14; const top = e.clientY - h.r.top + 14;
    tip.style.left = Math.min(left, h.wrap.clientWidth - tip.offsetWidth - 4) + 'px';
    tip.style.top = Math.min(top, h.wrap.clientHeight - tip.offsetHeight - 4) + 'px';
  });
  document.addEventListener('mouseout', (e) => { if (!e.relatedTarget) { const tip = $('#dtip'); if (tip) tip.hidden = true; paintDet(null); } });   // pointer left the window

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
      const dets = st.det && hasDet(cam) ? cam.det : [];
      if (st.dcam !== cam.id) { st.dcam = cam.id; st.dsel = null; }
      if (st.dsel != null && !dets[st.dsel]) st.dsel = null;
      const boxes = dets.length ? `<g class="dets" aria-hidden="true">${dets.map((b, i) => {
        const g = `x="${b[0]}" y="${b[1]}" width="${(b[2] - b[0]).toFixed(1)}" height="${(b[3] - b[1]).toFixed(1)}" data-i="${i}"`;
        return `<rect class="dbox-h" ${g}/><rect class="dbox${i === st.dsel ? ' sel' : ''}" ${g}/>`;
      }).join('')}</g>` : '';
      const polys = camAreas.filter((a) => a.quad).map((a) => `<polygon class="poly s-${a.status}${a.status === 'ok' ? ' ok' : ''}${a.id === st.sel ? ' sel' : ''}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" points="${a.quad.map((p) => p.join(',')).join(' ')}"/>`).join('');
      const pins = camAreas.filter((a) => a.quad).map((a) => {
        const [px, py] = pinPos(a, vb);
        return `<button type="button" class="pin s-${a.status}${a.id === st.sel ? ' sel' : ''}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" style="left:${px.toFixed(2)}%;top:${py.toFixed(2)}%" aria-pressed="${a.id === st.sel}" aria-label="${esc(`${t('area')} ${a.num}, ${nm(a).main}, ${t('s_' + a.status)}`)}">${icon(S_ICON[a.status])}<span>${esc(a.num)}</span></button>`;
      }).join('');
      frame = `<div class="frame-wrap${dets.length ? ' det-on' : ''}" role="group" aria-label="${t('camera')} ${esc(cam.id)}, ${fmtTime(cam.ts)}" style="aspect-ratio:${vb[2].toFixed(1)}/${vb[3].toFixed(1)}">
        <svg class="overlay" viewBox="${vb.map((v) => v.toFixed(1)).join(' ')}" preserveAspectRatio="none"><image href="${esc(cam.frame)}" x="0" y="0" width="${cam.w}" height="${cam.h}"/>${polys}${boxes}</svg>${pins}<div class="dtip" id="dtip" hidden></div></div>
        <div class="frame-tools"><button type="button" class="chip zoom" data-act="zoom" aria-pressed="${st.full}">${t(st.full ? 'zoom_in' : 'zoom_out')}</button>${
  hasDet(cam) ? `<button type="button" class="chip" data-act="det" aria-pressed="${st.det}">${icon('i-box')}${t('det_show')}</button>` : ''}</div>
        ${dets.length ? `<p class="det-readout" id="det-readout" aria-live="polite">${detReadout(dets)}</p>` : ''}`;
    } else {
      frame = `<div class="frame-wrap noframe">${t(cam.unreadable ? 'unreadable' : 'no_picture')}</div>`;
    }
    const legend = `<div class="legend" aria-label="${t('legend')}">${['wrong', 'empty', 'low', 'ok'].map((s) => `<span class="s-${s}">${icon(S_ICON[s])}${t('s_' + s)}</span>`).join('')}</div>`;
    const list = camAreas.slice().sort(sortRoute).map((a) => `<li><button type="button" class="area-btn s-${a.status}${matches(a, true) ? '' : ' dim'}" data-act="area" data-id="${esc(a.id)}" aria-pressed="${a.id === st.sel}">${icon(S_ICON[a.status])}<b>${esc(a.num)} · ${esc(nm(a).main)}</b><small>${t('s_' + a.status)}${SAME_LV[a.status] === a.level ? '' : ' · ' + t('stock') + ': ' + t('lv_' + a.level)}${
  freshDue(a) ? ` · <span class="tag-fresh">${icon('i-leaf')}${t('fr_short')}</span>` : ''}${pairsOf(a).length ? (() => { const ms = maxScore(pairsOf(a)); const lab = t('eth_panel') + (ms ? ' · ' + t('risk_b', { s: ms, b: t('rb_avoid') }) : ''); return ` <span class="tag-eth${ms >= 7 ? ' rb-avoid' : ''}" title="${esc(lab)}">${icon('i-gas')}<span class="sr">${esc(lab)}</span></span>`; })() : ''}</small></button></li>`).join('');
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
      const counted = g.areas.filter((a) => a.n != null && a.status !== 'wrong');
      const units = counted.length ? `<p class="units"><b>${unitsTxt(counted.reduce((sum, a) => sum + a.n, 0), g.areas[0].loose === false)}</b> ${t('cnt_in', { a: areaWord(counted.length) })} <span class="muted">(${t('cnt_est')})</span></p>` : '';
      return `<article class="prod s-${g.worst}"><div class="prod-top"><h3 class="pname">${esc(nmn.main)}<small>${esc(nmn.sub)}</small></h3>${badge(g.worst)}</div>
        ${units}
        <div class="stat-row"><span class="muted">${g.areas.length === 1 ? t('area1') : t('areas_n', { n: g.areas.length })}</span>${counts.map(([s, n]) => `<span class="badge s-${s}">${icon(S_ICON[s])}${n} ${t('s_' + s)}</span>`).join('')}</div>
        <div><div class="meta"><span>${t('avg_stock')}: <b>${pct(g.avg)}</b></span></div><div class="fillbar" aria-hidden="true"><i style="width:${pct(clamp(g.avg, 0.03, 1))}"></i></div></div>
        ${els}<div class="pill-row">${pills}</div></article>`;
    }).join('');
    el.innerHTML = `<div class="view-head"><h2>${t('tab_products')} <span class="muted">· ${list.length}</span></h2>
      <div class="sortbar"><span class="lbl">${t('sort_by')}</span>${['attention', 'name', 'stock', 'areas'].map(sortBtn).join('')}</div></div>
      ${list.length ? `<div class="prod-grid">${cards}</div>` : `<div class="allgood"><h3>${t('no_products')}</h3></div>`}`;
  }

  /* ------------------------------------------------------------------ insights */
  /* Everything here is computed in sensei/dashboard.py (compute_insights) from the day's timeline; this only draws it. */
  const pname = (pid) => (byPid[pid] ? nm(byPid[pid]) : { main: pid, sub: '' });
  function insHints() {
    const out = []; const sales = INS.sales || [];
    if (INS.store_peak) out.push(t('hint_store', { a: hh(INS.store_peak[0]), b: hh(INS.store_peak[1]) }));
    sales.filter((s) => s.peak).sort((x, y) => y.peak[3] - x.peak[3]).slice(0, 3)
      .forEach((s) => out.push(t('hint_peak', { p: esc(pname(s.pid).main), a: hh(s.peak[0]), b: hh(s.peak[1]) })));
    const most = sales.filter((s) => s.restocks.length >= 3).sort((x, y) => y.restocks.length - x.restocks.length)[0];
    if (most) out.push(t('hint_restock', { p: esc(pname(most.pid).main), n: most.restocks.length }));
    const slow = sales.filter((s) => s.rate < 0.01 && s.hours >= 10 && !s.restocks.length).length;
    if (slow) out.push(t(slow === 1 ? 'hint_slow1' : 'hint_slow', { n: slow }));
    return out;
  }
  function soonHtml() {
    const now = D.snapshot_ts;
    const rows = (INS.soon || []).map((x) => ({ x, a: areaById[x.id] })).filter((r) => r.a)
      .sort((p, q) => p.x.at - q.x.at);                  /* already due (before the snapshot) first */
    const list = rows.map(({ x, a }) => {
      const n = nm(a); const left = now != null ? x.at - now : x.fc;
      return `<li><a class="ins-row s-${a.status}" href="${hrefOf(a)}"><span class="ins-main"><b>${esc(n.main)}</b><small>${loc(a)} · ${t('s_' + a.status)}</small></span>
        <span class="ins-val"><b>${left <= 0 ? t('empty_now') : t('soon_in', { t: dur(left) })}</b><small>${left <= 0 ? t('empty_was', { t: fmtTime(x.at) }) : t('soon_at', { t: fmtTime(x.at) })}</small></span></a></li>`;
    }).join('');
    return `<section class="ins-card c-soon" aria-labelledby="ins-soon"><h3 id="ins-soon">${icon('i-clock')}${t('soon_title')} <span class="count">${rows.length}</span></h3>
      <p class="muted">${t(rows.length ? 'soon_x' : 'soon_none')}</p>${rows.length ? `<ul class="ins-list">${list}</ul>` : ''}</section>`;
  }
  function hourlyHtml() {
    const hs = INS.hourly || [];
    if (hs.length < 4) return '';
    const W = 320; const H = 120; const L = 6; const R = 6; const Tp = 8; const B = 20;
    const h0 = hs[0][0]; const h1 = hs[hs.length - 1][0]; const slots = h1 - h0 + 1; const bw = (W - L - R) / slots;
    const max = Math.max(...hs.map((h) => h[1]), 0.01);
    const sp = INS.store_peak;
    const inPeak = (h) => sp && (h === sp[0] || h === (sp[0] + 1) % 24);
    let g = `<line class="axis" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/>`;
    hs.forEach(([h, r]) => {
      const x = L + (h - h0) * bw; const bh = Math.max(1.5, (r / max) * (H - B - Tp));
      g += `<rect class="hbar${inPeak(h) ? ' peak' : ''}" x="${(x + bw * 0.12).toFixed(1)}" y="${(H - B - bh).toFixed(1)}" width="${(bw * 0.76).toFixed(1)}" height="${bh.toFixed(1)}" rx="2"><title>${hh(h)}: ${t('sales_rate', { r: Math.round(r * 100) })}</title></rect>`;
      if (h % 2 === 0) g += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - 5}" text-anchor="middle">${h}</text>`;
    });
    const alt = t('hourly_alt', { a: hs.map(([h, r]) => `${h}h ${Math.round(r * 100)}%`).join(', ') });
    return `<div class="hourly"><h4>${t('hourly_title')}</h4><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(alt)}">${g}</svg><p class="muted small">${t('hourly_x')}</p></div>`;
  }
  function salesRow(s, max) {
    const n = pname(s.pid);
    const r = s.rate * 100;
    const val = s.rate <= 0 ? t('sales_zero') : r < 1 ? t('sales_lt1') : t('sales_rate', { r: Math.round(r) });
    const times = Array.from(new Set(s.restocks.map((x) => fmtTime(x[0])))).sort();
    const tops = times.length ? `<small>${icon('i-up')}${t('sales_tops', { t: times.slice(0, 3).join(', ') })}${times.length > 3 ? ' ' + t('more_n', { n: times.length - 3 }) : ''}</small>` : '';
    return `<li class="bar-row"><div class="bar-top"><b>${esc(n.main)}</b><span>${val}</span></div>
      <div class="bar" aria-hidden="true"><i style="width:${s.rate > 0 ? Math.max(3, (s.rate / max) * 100).toFixed(1) : 0}%"></i></div>${tops}</li>`;
  }
  function salesHtml() {
    const sales = INS.sales || [];
    if (!sales.length) return '';
    const max = Math.max(...sales.map((s) => s.rate), 0.01); const TOP = 8;
    const first = sales.slice(0, TOP).map((s) => salesRow(s, max)).join('');
    const rest = sales.slice(TOP);
    const more = rest.length ? `<details class="more"><summary>${tn('sales_more', rest.length)}</summary><ul class="bar-list">${rest.map((s) => salesRow(s, max)).join('')}</ul></details>` : '';
    return `<section class="ins-card c-sales" aria-labelledby="ins-sales"><h3 id="ins-sales">${icon('i-chart')}${t('sales_title')}</h3><p class="muted">${t('sales_x')}</p>
      ${hourlyHtml()}<ul class="bar-list">${first}</ul>${more}</section>`;
  }
  function adherenceHtml() {
    const ad = INS.adherence;
    if (!ad || !ad.n) return '';
    const share = ad.ok / ad.n;
    const row = (c) => {
      const bad = c.n - c.ok;
      return `<li><a class="ins-row ${bad ? 's-wrong' : 's-ok'}" href="#/gondola/${encodeURIComponent(c.id)}"><span class="ins-main"><b>${t('camera')} ${esc(c.id)}</b>
        <small>${t('adh_of', { ok: c.ok, n: c.n })}${bad ? ' · ' + t('adh_fix', { n: bad }) : ''}</small></span>
        <span class="ins-val"><b>${pct(c.ok / c.n)}</b></span><span class="bar full" aria-hidden="true"><i style="width:${pct(c.ok / c.n)}"></i></span></a></li>`;
    };
    const byShare = (x, y) => (x.ok / x.n - y.ok / y.n) || (x.id < y.id ? -1 : 1);
    const off = ad.cams.filter((c) => c.ok < c.n).sort(byShare);          // gondolas with something to move: always visible
    const fine = ad.cams.filter((c) => c.ok >= c.n).sort(byShare);        // the rest folds away, so the page stays short
    const rows = off.map(row).join('')
      + (fine.length ? `<li><details class="more"><summary>${tn(off.length ? 'adh_rest' : 'adh_all_n', fine.length)}</summary><ul class="ins-list">${fine.map(row).join('')}</ul></details></li>` : '');
    return `<section class="ins-card c-adh" aria-labelledby="ins-adh"><h3 id="ins-adh">${icon('i-ok')}${t('adh_title')}</h3><p class="muted">${t('adh_x')}</p>
      <p class="big"><b>${t('adh_overall', { p: Math.round(share * 100) })}</b> <span class="muted">(${t('adh_of', { ok: ad.ok, n: ad.n })})</span></p>
      <div class="bar" aria-hidden="true"><i style="width:${pct(share)}"></i></div><ul class="ins-list">${rows}</ul></section>`;
  }
  function ethGroupsHtml() {
    const groups = [];
    PAIRS.forEach((p) => {
      let g = groups.find((x) => x.src === p.src);
      if (!g) { g = { src: p.src, dst: [] }; groups.push(g); }
      g.dst.push(p);
    });
    groups.forEach((g) => g.dst.sort((x, y) => (y.score || 0) - (x.score || 0)));
    groups.sort((x, y) => maxScore(y.dst) - maxScore(x.dst));          // highest risk first (stable otherwise)
    return groups.map((g) => {
      const s = areaById[g.src]; if (!s) return '';
      const items = g.dst.map((p) => {
        const d = areaById[p.dst]; if (!d) return '';
        return `<li><a href="${hrefOf(d)}"><b>${esc(shelfName(d))}</b> (${areaRef(d)})</a> ${t('eth_fx', { fx: fxText(p.dst_type) })}${hasRisk(p) ? `<span class="risk-row">${riskBadge(p)}</span>` : ''}</li>`;
      }).join('');
      const top = g.dst.find(hasRisk);
      return `<li class="eth-row"><div class="eth-head">${icon('i-gas')}<a href="${hrefOf(s)}"><b>${esc(shelfName(s))}</b></a><small>${t('camera')} ${esc(s.cam)} · ${areaRef(s)}</small></div>
        <p>${t('eth_gas')}</p><ul class="eth-dst">${items}</ul>${top ? `<p class="risk-line">${riskAdvice(top)}</p>` : ''}</li>`;
    }).join('');
  }
  function freshRow(a) {
    return `<li><a class="ins-row s-fresh" href="${hrefOf(a)}"><span class="ins-main"><b>${esc(shelfName(a))}</b><small>${loc(a)}${a.fresh.basis === 'first' ? '' : ' · ' + fmtTime(a.fresh.since)}</small></span>
      <span class="ins-val"><b>${a.fresh.basis === 'first' ? '≥ ' : ''}${hrs(a.fresh.h)}</b><small>${t('fr_val', { l: a.fresh.lim })}</small></span></a></li>`;
  }
  function layoutHtml() {
    const due = areas.filter(freshDue).sort((x, y) => y.fresh.h / y.fresh.lim - x.fresh.h / x.fresh.lim || sortRoute(x, y));
    const hasBio = Object.keys(BIO).length > 0;
    if (!hasBio && !PAIRS.length) return '';
    const TOP = 6;
    const mild = INS.layout && INS.layout.mild && !WATCH.length ? ' ' + t('eth_mild', { n: INS.layout.mild }) : '';
    const wGroups = [];                       // one row per product pair and camera (several areas of the same product)
    WATCH.forEach((p) => {
      const x = areaById[p.a], y = areaById[p.b]; if (!x || !y) return;
      const [u, v] = [x, y].sort((m, n) => shelfName(m).localeCompare(shelfName(n)));
      const key = p.cam + '|' + shelfName(u) + '|' + shelfName(v);
      let g = wGroups.find((q) => q.key === key);
      if (!g) { g = { key, p, u, v, n: 0 }; wGroups.push(g); }
      g.n += 1;
    });
    const wRow = (g) => `<li class="watch-row"><span><a href="${hrefOf(g.u)}">${esc(shelfName(g.u))}</a> + <a href="${hrefOf(g.v)}">${esc(shelfName(g.v))}</a> <small>${t('camera')} ${esc(g.p.cam)}${g.n > 1 ? ' · ×' + g.n : ''}</small></span><span class="risk-row">${riskBadge(g.p)}</span></li>`;
    const wAdv = wGroups.length ? `<p class="risk-line">${riskAdvice(wGroups[0].p)}</p>` : '';
    const watch = wGroups.length ? `<details class="more watch"><summary>${tn('watch_sum', wGroups.length)}</summary>${wAdv}<ul class="watch-list">${wGroups.map(wRow).join('')}</ul></details>` : '';
    const scored = PAIRS.some(hasRisk) || wGroups.length;
    const credit = scored ? `<p class="muted small risk-how">${t('risk_how')}</p>${riskCredit()}` : '';
    const fresh = `<h4>${icon('i-leaf', 'g-fresh')}${t('fr_ins_title')} <span class="count">${due.length}</span></h4><p class="muted small">${t(due.length ? 'fr_ins_x' : 'fr_ins_none')}</p>${
      due.length ? `<ul class="ins-list">${due.slice(0, TOP).map(freshRow).join('')}</ul>` : ''}${
      due.length > TOP ? `<details class="more"><summary>${t('fr_more', { n: due.length - TOP })}</summary><ul class="ins-list">${due.slice(TOP).map(freshRow).join('')}</ul></details>` : ''}`;
    const eth = `<h4>${icon('i-gas', 'g-eth')}${t('eth_title')} <span class="count">${PAIRS.length}</span></h4>${
      PAIRS.length ? `<ul class="eth-list">${ethGroupsHtml()}</ul><p class="eth-tip">${t('eth_tip')}</p>` : `<p class="muted small">${t('eth_none')}</p>`}${watch}${credit}
      <p class="muted small">${t('eth_calm')}${mild} ${t('eth_src')}</p>`;
    return `<section class="ins-card c-layout" id="ins-layout-card" aria-labelledby="ins-layout"><h3 id="ins-layout">${icon('i-gas')}${t('lay_title')}</h3><p class="muted">${t('lay_x')}</p>
      <div class="lay-part">${eth}</div><div class="lay-part">${fresh}</div></section>`;
  }
  function renderInsights() {
    const el = $('#view-insights');
    if (!INS.adherence && !(INS.sales || []).length) { el.innerHTML = `<div class="view-head"><h2>${t('ins_title')}</h2></div><p class="muted">${t('ins_none')}</p>${layoutHtml()}`; return; }
    const stamps = new Set(); areas.forEach((a) => (a.tl || []).forEach((p) => stamps.add(p[0])));
    const lo = Math.min(...stamps); const hi = Math.max(...stamps);
    const sub = stamps.size ? t('ins_sub', { n: stamps.size, a: fmtTime(lo), b: fmtTime(hi) }) : '';
    const hints = insHints();
    el.innerHTML = `<div class="view-head"><h2>${t('ins_title')}</h2></div><p class="muted ins-sub">${sub}</p>
      ${hints.length ? `<section class="ins-card hints" aria-labelledby="ins-hints"><h3 id="ins-hints">${t('ins_hints')}</h3><ul>${hints.map((h) => `<li>${h}</li>`).join('')}</ul></section>` : ''}
      <div class="ins-grid">${soonHtml()}${salesHtml()}${adherenceHtml()}</div>${layoutHtml()}`;
  }

  /* ------------------------------------------------------------------ day replay */
  /* Built in sensei/dashboard.py (_build_replay) when details.json holds several frames per camera: every camera's
     latest picture at or before the chosen time, the events between pictures and a store pulse. */
  const SC = { e: 'empty', l: 'low', w: 'wrong', o: 'ok' };
  const D_MIN = RP ? Math.min(6 * 60, Math.floor((RP.t0 - RP.day0) / 300) * 5) : 0;        // slider range, minutes since local midnight
  const D_MAX = RP ? Math.max(20 * 60 + 30, Math.ceil((RP.t1 - RP.day0) / 300) * 5) : 0;
  const D_STEP_S = 360;                 // play: 6 min every 100 ms = about 1 hour per second
  let dTimer = null; let dFrameKey = ''; let dChipCam = null;
  const dCams = RP ? Object.keys(RP.frames).sort((x, y) => (x.length - y.length) || (x < y ? -1 : 1)) : [];
  function dState(ts) {                  // camera -> latest frame at or before ts
    const out = {};
    dCams.forEach((c) => { let best = null; RP.frames[c].forEach((f) => { if (f.ts <= ts && (!best || f.ts > best.ts)) best = f; }); if (best) out[c] = best; });
    return out;
  }
  function dItems(state) {               // [{a, s, f}] for every area of every pictured camera
    const out = [];
    Object.keys(state).forEach((c) => {
      const f = state[c]; const ids = RP.order[c] || [];
      ids.forEach((id, i) => { const s = SC[f.s.charAt(i)]; const a = areaById[id]; if (s && a) out.push({ a, s, f }); });
    });
    return out;
  }
  const dPlayInner = () => (st.dplay ? `<span class="pp pause" aria-hidden="true"></span>${t('day_pause')}` : `<span class="pp play" aria-hidden="true"></span>${t('day_play')}`);
  function dPause() { if (dTimer) { clearInterval(dTimer); dTimer = null; } st.dplay = false; const b = $('#d-play'); if (b) b.innerHTML = dPlayInner(); }
  function dPlay() {
    if (st.dt >= RP.t1) st.dt = RP.day0 + D_MIN * 60;      /* at or after the last picture: nothing left to play, start over */
    st.dplay = true; const b = $('#d-play'); if (b) b.innerHTML = dPlayInner();
    dTimer = setInterval(() => {
      st.dt = Math.min(RP.day0 + D_MAX * 60, st.dt + D_STEP_S);
      if (st.dt >= RP.day0 + D_MAX * 60) dPause();
      updateDay();
    }, 100);
  }
  const evLine = (a) => `${t('camera')} ${esc(a.cam)} · ${t('area')} ${esc(a.num)} · <b>${esc(nm(a).main)}</b>`;
  const EV_S = { empty: 'empty', low: 'low', wrong: 'wrong', fixed: 'ok', restock: 'ok', ok: 'ok' };
  const EV_I = { empty: 'i-empty', low: 'i-low', wrong: 'i-wrong', fixed: 'i-ok', restock: 'i-up', ok: 'i-ok' };
  function dTaskText(it) {
    if (it.s === 'empty') return t('act_restock');
    if (it.s === 'low') return t('act_top');
    const lk = it.f.lk && it.f.lk[it.a.id];
    const q = lk ? (st.lang === 'pt' ? lk[1] : lk[0]) : '';
    return q ? `${t('act_move')}: ${t('act_move_x', { p: esc(nm(it.a).main), q: esc(q) })}` : `${t('act_check')}: ${t('expected')} ${esc(nm(it.a).main)}`;
  }
  function renderDay() {
    const el = $('#view-day');
    const nPics = dCams.reduce((s, c) => s + RP.frames[c].length, 0);
    el.innerHTML = `<div class="view-head"><h2>${t('day_title')}</h2></div>
      <p class="day-honest">${t('day_honest', { n: nPics, c: dCams.length })}</p>
      <div class="day-ctrl"><div class="day-btns"><button type="button" class="day-play" id="d-play" data-act="dplay">${dPlayInner()}</button>
        <output class="day-clock" id="d-clock"></output></div>
        <div class="day-slider"><div id="d-pulse" class="day-pulse"></div><label><span class="sr">${t('day_slider')}</span><input type="range" id="d-range" min="${D_MIN}" max="${D_MAX}" step="5" value="${Math.round((st.dt - RP.day0) / 60)}"></label>
        <div class="day-ticks" aria-hidden="true">${[6, 9, 12, 15, 18, 20].filter((h) => h * 60 >= D_MIN && h * 60 <= D_MAX).map((h) => `<span style="left:calc(10px + (100% - 20px) * ${((h * 60 - D_MIN) / (D_MAX - D_MIN)).toFixed(4)})">${hh(h)}</span>`).join('')}</div></div>
        <p class="day-cap"><b>${t('day_pulse')}</b><span class="legend">${['empty', 'low', 'wrong'].map((s) => `<span class="s-${s}">${icon(S_ICON[s])}${t('s_' + s)}</span>`).join('')}</span><span class="muted">${t('day_pulse_x')}</span></p></div>
      <div class="counters day-counters" id="d-counts"></div>
      <div class="day-grid">
        <div class="day-main"><section class="ins-card"><div class="cam-chips" id="d-cams" role="group" aria-label="${t('f_camera')}"></div><div id="d-frame"></div></section>
          <section class="ins-card"><h3 id="d-todo-h">${icon('i-list')}</h3><div id="d-todo" class="day-todo"></div></section></div>
        <div class="day-side"><section class="ins-card"><h3>${icon('i-clock')}${t('day_log')}</h3><p class="muted small">${t('day_log_x')}</p><ol class="ev-list ev-log" id="d-log"></ol></section></div>
      </div>`;
    dFrameKey = ''; dChipCam = null;
    updateDay();
  }
  function updateDay() {
    const el = $('#view-day'); if (!el || el.hidden || !$('#d-clock')) return;
    const ts = st.dt; const state = dState(ts); const items = dItems(state);
    $('#d-clock').textContent = fmtTime(ts);
    const rg = $('#d-range'); const v = Math.round((ts - RP.day0) / 60); if (rg && +rg.value !== v) rg.value = v;
    /* counters */
    const c = { empty: 0, low: 0, wrong: 0, ok: 0 }; items.forEach((it) => { c[it.s]++; });
    $('#d-counts').innerHTML = STATUS.map((s) => `<div class="counter s-${s}${c[s] ? '' : ' zero'}">${icon(S_ICON[s])}<span class="n">${c[s]}</span><span class="lbl">${t('s_' + s)}</span></div>`).join('');
    /* camera chips */
    if (!st.dgc || !RP.frames[st.dgc]) {
      const worst = dCams.map((cm) => [cm, items.filter((it) => it.a.cam === cm && it.s !== 'ok').length]).sort((x, y) => y[1] - x[1])[0];
      st.dgc = worst ? worst[0] : dCams[0];
    }
    const box = $('#d-cams'); const keep = { cams: box.scrollLeft, log: $('#d-log').scrollTop, todo: $('#d-todo').scrollTop };
    box.innerHTML = dCams.map((cm) => {
      const n = items.filter((it) => it.a.cam === cm && it.s !== 'ok').length; const f = state[cm];
      return `<button type="button" class="cam-chip" data-act="dcam" data-v="${esc(cm)}" aria-pressed="${cm === st.dgc}"><b>${t('camera')} ${esc(cm)}</b><span>${f ? `${n ? t('day_cam_todo', { n }) : t('every_ok')} · ${fmtTime(f.ts)}` : '-'}</span></button>`;
    }).join('');
    const act = $('.cam-chip[aria-pressed="true"]', box);
    if (act && dChipCam !== st.dgc) box.scrollLeft = act.offsetLeft - (box.clientWidth - act.offsetWidth) / 2; else box.scrollLeft = keep.cams;
    dChipCam = st.dgc;
    /* frame of the picked camera */
    const f = state[st.dgc]; const cam = camById[st.dgc];
    const key = [st.dgc, f ? f.ts : 0, st.dga, st.lang, st.full].join('|');
    if (key !== dFrameKey) {
      dFrameKey = key;
      if (!f || !cam || !cam.w) {
        $('#d-frame').innerHTML = `<div class="frame-wrap noframe">${t(f ? 'no_picture' : 'day_nopic')}</div>`;
      } else {
        const ids = RP.order[st.dgc] || [];
        const camAreas = ids.map((id) => areaById[id]).filter(Boolean);
        const vb = viewBoxFor(cam, camAreas);
        const stOf = (id) => SC[f.s.charAt(ids.indexOf(id))] || 'ok';
        const polys = camAreas.filter((a) => a.quad).map((a) => { const s = stOf(a.id); return `<polygon class="poly s-${s}${s === 'ok' ? ' ok' : ''}${a.id === st.dga ? ' sel' : ''}" data-act="dpick" data-id="${esc(a.id)}" points="${a.quad.map((p) => p.join(',')).join(' ')}"><title>${esc(`${a.num} · ${nm(a).main}: ${t('s_' + s)}`)}</title></polygon>`; }).join('');
        const pins = camAreas.filter((a) => a.quad).map((a) => { const s = stOf(a.id); const [px, py] = pinPos(a, vb); return `<button type="button" class="pin s-${s}${a.id === st.dga ? ' sel' : ''}" data-act="dpick" data-id="${esc(a.id)}" style="left:${px.toFixed(2)}%;top:${py.toFixed(2)}%" aria-label="${esc(`${t('area')} ${a.num}, ${nm(a).main}, ${t('s_' + s)}`)}">${icon(S_ICON[s])}<span>${esc(a.num)}</span></button>`; }).join('');
        const img = f.f ? `<image href="${esc(f.f)}" x="0" y="0" width="${cam.w}" height="${cam.h}" preserveAspectRatio="none"/>` : '';
        const sa = st.dga && areaById[st.dga] && areaById[st.dga].cam === st.dgc ? areaById[st.dga] : null;
        const info = sa ? `<p class="day-sel">${badge(stOf(sa.id))} <span>${evLine(sa)}</span></p>` : `<p class="muted small day-sel">${t('day_pick')}</p>`;
        $('#d-frame').innerHTML = `<div class="frame-wrap" style="aspect-ratio:${vb[2].toFixed(1)}/${vb[3].toFixed(1)}"><svg class="overlay" viewBox="${vb.map((x) => x.toFixed(1)).join(' ')}" preserveAspectRatio="none">${img}${polys}</svg>${pins}
          <span class="day-stamp">${icon('i-clock')}${t('day_frame', { t: fmtTime(f.ts) })}</span></div>${info}`;
      }
    }
    /* event log, newest first */
    const evs = RP.events.filter((e) => e[0] <= ts && areaById[e[1]]);
    const MAXE = 60; const shown = evs.slice(-MAXE).reverse();
    $('#d-log').innerHTML = shown.length ? shown.map((e) => {
      const a = areaById[e[1]]; const k = e[2];
      return `<li><button type="button" class="ev-row s-${EV_S[k]}${ts - e[0] < 3600 ? ' recent' : ''}${st.dga === a.id ? ' sel' : ''}" data-act="dev" data-v="${e[0]}" data-id="${esc(a.id)}"><time>${fmtTime(e[0])}</time>${icon(EV_I[k])}<span>${evLine(a)}: ${t('ev_' + k)}</span></button></li>`;
    }).join('') + (evs.length > MAXE ? `<li class="muted small">${t('day_more', { n: evs.length - MAXE })}</li>` : '') : `<li class="muted">${t('day_log_none')}</li>`;
    /* to-do list of that moment (closing-time mode applies at that hour) */
    const todo = items.filter((it) => it.s !== 'ok');
    const closing = nearClose(ts);
    const wait = closing ? todo.filter((it) => canWait(it.a, it.s)) : [];
    const rest = todo.filter((it) => wait.indexOf(it) < 0).sort((x, y) => ORDER[x.s] - ORDER[y.s] || sortRoute(x.a, y.a));
    const row = (it) => `<li><button type="button" class="ev-row s-${it.s}" data-act="dpick" data-id="${esc(it.a.id)}">${icon(S_ICON[it.s])}<span><b>${esc(nm(it.a).main)}</b> <small>${t('camera')} ${esc(it.a.cam)} · ${t('area')} ${esc(it.a.num)} · ${dTaskText(it)}</small></span></button></li>`;
    $('#d-todo-h').innerHTML = `${icon('i-list')}${t('day_todo', { t: fmtTime(ts) })} <span class="count">${todo.length}</span>`;
    $('#d-todo').innerHTML = (rest.length ? `<ol class="ev-list">${rest.map(row).join('')}</ol>` : `<p class="muted">${t('all_good_x')}</p>`)
      + (wait.length ? `<h4 class="group-title g-close">${icon('i-moon')}${t('close_group')} <span class="count">${wait.length}</span></h4><p class="close-why">${t('close_why', { c: esc(st.close) })}</p><ol class="ev-list">${wait.map(row).join('')}</ol>` : '');
    $('#d-log').scrollTop = keep.log; $('#d-todo').scrollTop = keep.todo;     /* re-rendering must not jump the lists */
    /* store pulse */
    $('#d-pulse').innerHTML = dPulseSvg(ts);
  }
  function dPulseSvg(ts) {
    const ps = RP.pulse || []; if (!ps.length) return '';
    const W = 1000; const H = 64; const L = 10; const R = 10;      /* L / R ~ the range thumb inset, so bars sit over their hour */
    const x0 = RP.day0 + D_MIN * 60; const x1 = RP.day0 + D_MAX * 60;
    const X = (v) => L + ((v - x0) / Math.max(1, x1 - x0)) * (W - L - R);
    const max = Math.max(...ps.map((p) => p[1] + p[2] + p[3]), 1);
    const Y = (v) => (v / max) * (H - 2);
    const bw = Math.max(3, (1800 / Math.max(1, x1 - x0)) * (W - L - R) * 0.8);
    let g = '';
    ps.filter((p) => p[0] >= x0 && p[0] <= x1).forEach((p) => {
      const x = X(p[0]) - bw / 2; let y = H;
      [['wrong', p[3]], ['empty', p[1]], ['low', p[2]]].forEach(([s, n]) => {
        if (!n) return; const h = Y(n); y -= h;
        g += `<rect class="pb s-${s}${p[0] > ts ? ' later' : ''}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}"/>`;
      });
      g += `<rect class="pb-hit" data-act="dseek" data-v="${p[0]}" x="${x.toFixed(1)}" y="0" width="${bw.toFixed(1)}" height="${H}"><title>${fmtTime(p[0])}: ${p[1]} ${t('s_empty')}, ${p[2]} ${t('s_low')}, ${p[3]} ${t('s_wrong')}</title></rect>`;
    });
    const cx = X(ts).toFixed(1);
    g += `<line class="pb-now" x1="${cx}" x2="${cx}" y1="0" y2="${H}"/>`;
    return `<svg class="pulse" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(t('day_pulse') + ': ' + t('day_pulse_x'))}">${g}</svg>`;
  }

  /* ------------------------------------------------------------------ print sheet */
  function buildPrintSheet() {
    const tasks = areas.filter((a) => isTask(a) && !done[taskKey(a)]).sort(sortRoute);
    let cur = null; let rows = '';
    tasks.forEach((a) => {
      if (a.cam !== cur) { cur = a.cam; rows += `<tr class="cam"><td colspan="4">${t('camera')} ${esc(a.cam)} · ${fmtTime(camTs(a))}</td></tr>`; }
      rows += `<tr><td><span class="box"></span></td><td>${t('area')} ${esc(a.num)}</td><td><b>${esc(nm(a).main)}</b><small>${esc(nm(a).sub)}</small></td>
        <td><b>${a.status === 'ok' ? t('fr_badge') : a.status === 'low' ? t('act_top') : a.status === 'empty' ? t('act_restock') : (seenName(a) ? t('act_move') : t('act_check'))}</b>${
  freshDue(a) ? `<small>${a.status === 'ok' ? '' : t('fr_short') + ': '}${t('fr_task', { h: freshH(a), l: a.fresh.lim })} (${t('cnt_est')})</small>` : ''}${
  a.status === 'wrong' && seenName(a) ? `<small>${t('expected')} ${esc(nm(a).main)}, ${t('seen')} ${esc(seenName(a))}</small>` : ''}${
  fcShow(a) ? `<small>${fcText(a)}</small>` : ''}</td></tr>`;
    });
    $('#print-sheet').innerHTML = `<h1>${t('title')} · ${t('tasks_title')}</h1><p>${esc(D.section || '')} · ${snapText()} · ${tn('n_tasks', tasks.length)}</p>
      <table><thead><tr><th></th><th>${cap(t('area'))}</th><th>${t('col_product')}</th><th>${t('col_do')}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  /* ------------------------------------------------------------------ chrome */
  function counts() {
    const c = { empty: 0, low: 0, wrong: 0, ok: 0 };
    const keep = st.status; st.status = null;                     /* a status filter must not zero the other counters */
    areas.filter((a) => matches(a)).forEach((a) => { c[a.status]++; });
    st.status = keep;
    return c;
  }
  function renderChrome() {
    document.documentElement.lang = st.lang;
    document.title = `${t('title')} · ${D.section || ''}`.replace(/ · $/, '');
    $$('[data-i18n]').forEach((n) => { n.textContent = t(n.dataset.i18n); });
    $('#app-title').innerHTML = esc(t('title')).replace(/\.$/, '<span class="brand-dot">.</span>');
    const camTxt = st.cam === 'all' ? '' : ` · ${t('camera')} ${st.cam}`;
    $('#subtitle').textContent = `${D.section || ''} · ${snapText()}${camTxt}`;
    $('#search').placeholder = t('search_ph');
    $$('[data-act="lang"]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === st.lang)));
    $('#theme-btn').setAttribute('aria-label', t('theme'));
    $('#print-btn').setAttribute('aria-label', t('print'));
    const dark = isDark();
    $('#theme-btn').innerHTML = icon(dark ? 'i-sun' : 'i-moon');
    const c = counts();
    $('#counters').hidden = st.view === 'insights' || st.view === 'day';
    $('#filters').hidden = st.view === 'insights' || st.view === 'day';
    const dayTab = $('.tab[data-tab="day"]'); if (dayTab) dayTab.hidden = !RP;
    $('#counters').classList.add('compact');
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
    $('#foot').textContent = t('foot') + (hasCounts ? ' ' + t('foot_cnt') : '');
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
    if (st.view !== 'day' && st.dplay) dPause();
    renderChrome();
    ['tasks', 'gondola', 'products', 'insights', 'day'].forEach((v) => { const n = $('#view-' + v); if (n) n.hidden = v !== st.view; });
    if (st.view === 'tasks') renderTasks();
    else if (st.view === 'gondola') renderGondola();
    else if (st.view === 'products') renderProducts();
    else if (st.view === 'day') renderDay();
    else renderInsights();
    buildPrintSheet();
  }

  /* ------------------------------------------------------------------ routing and events */
  let jumpTo = null;     // section id to scroll to after the next render (#/insights/layout)
  function readHash() {
    const p = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    st.view = VIEWS.includes(p[0]) ? p[0] : 'tasks';
    jumpTo = st.view === 'insights' && p[1] === 'layout' ? 'ins-layout-card' : null;
    if (st.view === 'day' && RP) {
      const m = /^(\d{1,2})(\d{2})$/.exec(p[1] || '');
      if (m) st.dt = clamp(RP.day0 + (+m[1]) * 3600 + (+m[2]) * 60, RP.day0 + D_MIN * 60, RP.day0 + D_MAX * 60);
      if (p[2] && RP.frames[p[2]]) st.dgc = p[2];
      if (p[3] && areaById[p[3]]) st.dga = p[3];
    }
    if (st.view === 'gondola') {
      if (p[1] && camById[p[1]]) st.gcam = p[1];
      if (p[2] && areaById[p[2]]) { st.sel = p[2]; st.gcam = areaById[p[2]].cam; }
      if (p[3] === 'det' && D.cameras.some(hasDet)) st.det = true;   // shareable link: .../gondola/<cam>/<area>/det
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
    jumpToSection();
  });
  function jumpToSection() {
    const el = jumpTo && document.getElementById(jumpTo);
    if (!el) return;
    el.scrollIntoView({ block: 'start' });
    const h = el.querySelector('h3'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
  }

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
    if (st.det && e.target.closest && e.target.closest('.frame-wrap')) { const h = detAt(e); if (h) { st.dsel = h.i >= 0 ? h.i : null; paintDet(null); } }
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
    else if (act === 'det') { st.det = !st.det; st.dsel = null; renderGondola(); }
    else if (act === 'dplay') { if (st.dplay) dPause(); else dPlay(); return; }
    else if (act === 'dcam') { st.dgc = v; st.dga = null; updateDay(); }
    else if (act === 'dpick') { const a = areaById[b.dataset.id]; if (a) { st.dgc = a.cam; st.dga = a.id; updateDay(); } }
    else if (act === 'dev') { dPause(); const a = areaById[b.dataset.id]; st.dt = +v; if (a) { st.dgc = a.cam; st.dga = a.id; } updateDay(); const fr = $('#d-frame'); if (fr && window.innerWidth < 960) fr.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    else if (act === 'dseek') { dPause(); st.dt = +v; updateDay(); }
    restoreFocus(b);
  });
  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.id === 'cam-select') { st.cam = el.value; render(); }
    else if (el.id === 'close-time') { if (hmToMin(el.value) != null) { st.close = el.value; store.set('sensei.close', st.close); render(); } }
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
  document.addEventListener('input', (e) => {
    if (e.target.id !== 'd-range' || !RP) return;
    dPause(); st.dt = RP.day0 + (+e.target.value) * 60; updateDay();
  });
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
  jumpToSection();
})();
