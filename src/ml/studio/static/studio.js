/* studio.js — estado e composicao das views. Desenho fica em graficos.js. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);

  const METRICS = [
    { key: 'dn',  label: 'Download',  unit: 'Mbps', dir: 'min', max: 60,   step: 0.5 },
    { key: 'up',  label: 'Upload',    unit: 'Mbps', dir: 'min', max: 60,   step: 0.5 },
    { key: 'lat', label: 'Latência',  unit: 'ms',   dir: 'max', max: 500,  step: 5 },
    { key: 'jit', label: 'Jitter',    unit: 'ms',   dir: 'max', max: 200,  step: 2 },
  ];

  /* Limiares de referencia por aplicacao. Editaveis na view Limiares. */
  const PROFILES = {
    'Navegação':        { dn: 2,   up: 0.5, lat: 300, jit: 100 },
    'Chamada de vídeo': { dn: 3.8, up: 3.8, lat: 150, jit: 30 },
    'Streaming 4K':     { dn: 25,  up: 0,   lat: 500, jit: 100 },
    'Jogo em nuvem':    { dn: 15,  up: 1,   lat: 40,  jit: 10 },
  };
  const SEQ = ['--seq-100','--seq-200','--seq-300','--seq-400','--seq-500','--seq-600','--seq-700'];
  const MIN_SAMPLES = 5;

  const state = { data: null, app: 'Chamada de vídeo', thr: null, legacy: false,
                  enabled: {}, view: 'matrix', metric: 'dn' };
  const hits = {};

  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const seriesColor = (i) => cssv('--s' + (i % 5 + 1));

  function meets(row, thr) {
    return row.dn >= thr.dn && row.up >= thr.up && row.lat <= thr.lat && row.jit <= thr.jit;
  }
  function activeRows() {
    return state.data.rows.filter((r) => state.enabled[r.ds]);
  }
  function positionsOf(rows) {
    const seen = new Map();
    rows.forEach((r) => { if (!seen.has(r.b + '|' + r.p)) seen.set(r.b + '|' + r.p, { b: r.b, p: r.p }); });
    return [...seen.values()].sort((a, z) => a.b.localeCompare(z.b) || a.p.localeCompare(z.p));
  }
  const median = (xs) => {
    if (!xs.length) return null;
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  };
  const rampColor = (pct) => cssv(SEQ[Math.min(SEQ.length - 1, Math.floor(pct / 100 * SEQ.length))]);

  /* ---------------- gates (titulo/mensagem/causas) ------------- */
  function renderGates() {
    const rows = activeRows();
    const gates = [];
    const buildings = new Set(rows.map((r) => r.b));
    const gens = new Set(rows.map((r) => r.gen));
    const withN = rows.filter((r) => r.n != null).length;

    if (buildings.size < 2) {
      gates.push({ sev: 'critical', title: 'Menos de 2 prédios no conjunto ativo',
        msg: 'Leave-one-building-out fica indefinido e nenhum número aqui generaliza para um prédio novo.',
        causes: ['Ligue um dataset do outro prédio na view Datasets.'] });
    }
    if (gens.size > 1) {
      gates.push({ sev: 'warning', title: 'Gerações de esquema misturadas',
        msg: `${rows.length.toLocaleString('pt-BR')} linhas ativas, mas só ${withN.toLocaleString('pt-BR')} têm contagem de dispositivos.`,
        causes: ['As linhas legacy não entram na view Contenção — combo e n_clients só existem a partir de 2026-08-17.',
                 'Geometria (station_x/y/z) também falta nelas, então não aparecem na Planta.'] });
    }
    Object.entries(state.enabled).forEach(([id, on]) => {
      if (!on) return;
      const d = state.data.datasets.find((x) => x.id === id);
      if (d && d.duplicateOf) {
        gates.push({ sev: 'warning', title: `${id} é idêntico a ${d.duplicateOf}`,
          msg: 'Os quatro alvos batem exatamente; manter os dois ligados duplica o peso de cada amostra.',
          causes: [`Desligue ${id} na view Datasets.`] });
      }
      if (d && d.supersededBy) {
        gates.push({ sev: 'warning', title: `${id} está contido em ${d.supersededBy}`,
          msg: 'Todas as suas linhas já existem no outro dataset; mantê-los juntos duplica o peso dessas amostras.',
          causes: [`Desligue ${id} na view Datasets.`] });
      }
    });
    if (!gates.length) {
      gates.push({ sev: 'good', title: 'Conjunto ativo consistente',
        msg: `${rows.length.toLocaleString('pt-BR')} amostras, ${buildings.size} prédios, ${positionsOf(rows).length} posições.`, causes: [] });
    }
    $('#gates').innerHTML = gates.map((g) => `
      <div class="gate ${g.sev}">
        <svg class="icon"><use href="#${g.sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
        <div><div class="gate-title">${g.title}</div><div class="gate-msg">${g.msg}</div>
        ${g.causes.length ? '<ul>' + g.causes.map((c) => `<li>${c}</li>`).join('') + '</ul>' : ''}</div>
      </div>`).join('');
  }

  /* ---------------- matriz de capacidade ---------------- */
  function matrixData() {
    const rows = activeRows().filter((r) => r.n != null);
    const positions = positionsOf(rows);
    const devices = [1, 2, 3];
    return positions.map((pos) => ({
      pos,
      cells: devices.map((n) => {
        const g = rows.filter((r) => r.b === pos.b && r.p === pos.p && r.n === n);
        return g.length < MIN_SAMPLES
          ? { n: g.length, pct: null }
          : { n: g.length, pct: 100 * g.filter((r) => meets(r, state.thr)).length / g.length };
      }),
    }));
  }

  function renderMatrix() {
    const data = matrixData();
    const el = $('#matrix');
    if (!data.length) { el.innerHTML = '<p class="hint">Nenhum dataset com contagem de dispositivos está ativo.</p>';
                        $('#matrixTable').innerHTML = ''; return; }
    el.style.gridTemplateColumns = '170px repeat(3, 1fr)';
    let html = '<div class="collab"></div>' +
      [1, 2, 3].map((n) => `<div class="collab">${n} disp.</div>`).join('');
    data.forEach((r) => {
      const label = `${state.data.buildings[r.pos.b].label} · ${r.pos.p}`;
      html += `<div class="rowlab">${label}</div>`;
      r.cells.forEach((c) => {
        if (c.pct == null) {
          html += `<div class="cell" style="background:var(--grid);color:var(--ink-muted)" title="${c.n} amostras">–</div>`;
        } else {
          const bg = rampColor(c.pct);
          const ink = c.pct > 55 ? '#ffffff' : cssv('--ink-1');
          html += `<div class="cell" style="background:${bg};color:${ink}" title="${label} · ${c.n} amostras">${Math.round(c.pct)}%</div>`;
        }
      });
    });
    el.innerHTML = html;
    $('#ramp').innerHTML = SEQ.map((s) => `<i style="background:var(${s})"></i>`).join('');

    $('#matrixTable').innerHTML = `<table><thead><tr><th>Prédio</th><th>Posição</th>
      <th class="num">1 disp.</th><th class="num">2 disp.</th><th class="num">3 disp.</th><th class="num">amostras</th></tr></thead><tbody>` +
      data.map((r) => `<tr><td>${state.data.buildings[r.pos.b].label}</td><td>${r.pos.p}</td>` +
        r.cells.map((c) => `<td class="num">${c.pct == null ? '–' : Math.round(c.pct) + '%'}</td>`).join('') +
        `<td class="num">${r.cells.reduce((a, c) => a + c.n, 0)}</td></tr>`).join('') + '</tbody></table>';
  }

  /* ---------------- contencao ---------------- */
  function renderContention() {
    const rows = activeRows().filter((r) => r.n != null);
    const positions = positionsOf(rows);
    const m = METRICS.find((x) => x.key === state.metric);
    const series = positions.map((pos, i) => ({
      label: pos.p,
      color: seriesColor(i),
      points: [1, 2, 3].map((n) => {
        const g = rows.filter((r) => r.b === pos.b && r.p === pos.p && r.n === n);
        return { v: g.length < MIN_SAMPLES ? null : median(g.map((r) => r[state.metric])) };
      }),
    }));
    const canvas = $('#cContention');
    hits.contention = V.drawLines(canvas, {
      height: 320, x: ['1 dispositivo', '2 dispositivos', '3 dispositivos'],
      series, yFmt: (v) => v.toFixed(v < 10 ? 1 : 0),
      yTitle: `${m.label} (${m.unit}) — mediana`,
    });
    $('#kContention').innerHTML = series.map((s) =>
      `<span><i style="background:${s.color}"></i>${s.label}</span>`).join('');
  }

  /* ---------------- restricao dominante ---------------- */
  function renderConstraint() {
    const rows = activeRows();
    const positions = positionsOf(rows);
    const series = METRICS.map((m, i) => ({ label: m.label, color: seriesColor(i) }));
    const groups = positions.map((pos) => {
      const g = rows.filter((r) => r.b === pos.b && r.p === pos.p);
      return {
        label: pos.p,
        values: METRICS.map((m) => !g.length ? null : 100 * g.filter((r) =>
          m.dir === 'min' ? r[m.key] < state.thr[m.key] : r[m.key] > state.thr[m.key]).length / g.length),
      };
    });
    hits.constraint = V.drawGroupedBars($('#cConstraint'),
      { height: 320, groups, series, max: 100, yFmt: (v) => v + '%' });
    $('#kConstraint').innerHTML = series.map((s) =>
      `<span><i style="background:${s.color}"></i>${s.label} reprovado</span>`).join('');
  }

  /* ---------------- planta ---------------- */
  function renderPlan() {
    const rows = activeRows().filter((r) => r.x != null);
    const host = $('#plans');
    if (!rows.length) { host.innerHTML = '<p class="hint">Nenhum dataset com geometria está ativo.</p>'; return; }
    host.innerHTML = '';
    hits.plan = {};
    // Duas passadas: monta TODO o DOM antes de desenhar. Desenhar durante a
    // montagem mede o canvas enquanto ele ainda e o unico filho do grid — ele
    // fica com backing store da largura inteira e depois encolhe para meia
    // coluna, o que achata os circulos em elipses.
    const pending = [];
    Object.entries(state.data.envelopes).forEach(([b, env]) => {
      const mine = rows.filter((r) => r.b === b);
      if (!mine.length) return;
      const groups = new Map();
      mine.forEach((r) => {
        const k = `${r.x}|${r.y}`;
        if (!groups.has(k)) groups.set(k, { x: r.x, y: r.y, p: r.p, rows: [] });
        groups.get(k).rows.push(r);
      });
      const points = [...groups.values()].map((g) => {
        const pct = 100 * g.rows.filter((r) => meets(r, state.thr)).length / g.rows.length;
        return { x: g.x, y: g.y, n: g.rows.length, value: pct, label: g.p, color: rampColor(pct) };
      });
      const wrap = document.createElement('div');
      wrap.innerHTML = `<h2 style="font-size:13px;margin:0 0 8px">${state.data.buildings[b].label}
        <span style="color:var(--ink-muted);font-weight:400">· ${env.w}×${env.h} cm · ${points.length} pontos</span></h2>
        <div class="chartwrap"><canvas></canvas><div class="tooltip"></div></div>`;
      host.appendChild(wrap);
      pending.push({ b, env, points, wrap });
    });
    pending.forEach(({ b, env, points, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      const tip = wrap.querySelector('.tooltip');
      hits.plan[b] = V.drawFloorPlan(canvas, { height: 460, envelope: env, points });
      V.attachTooltip(canvas, tip, () => hits.plan[b],
        (h) => `<b>${h.label}</b>${Math.round(h.value)}% atende · ${h.at}`);
    });
  }

  /* ---------------- limiares ---------------- */
  function renderSliders() {
    $('#sliders').innerHTML = METRICS.map((m) => `
      <label for="sl-${m.key}">${m.label} ${m.dir === 'min' ? 'mínimo' : 'máximo'}</label>
      <input type="range" id="sl-${m.key}" min="0" max="${m.max}" step="${m.step}" value="${state.thr[m.key]}">
      <output id="out-${m.key}">${state.thr[m.key]} ${m.unit}</output>`).join('');
    METRICS.forEach((m) => {
      $('#sl-' + m.key).addEventListener('input', (e) => {
        state.thr[m.key] = parseFloat(e.target.value);
        $('#out-' + m.key).textContent = `${state.thr[m.key]} ${m.unit}`;
        $('#appSel').value = '__custom';
        renderAll();
      });
    });
  }

  /* ---------------- datasets ---------------- */
  function renderDatasets() {
    $('#dsTable').innerHTML = `<table><thead><tr><th>Usar</th><th>Dataset</th><th>Geração</th>
      <th class="num">linhas</th><th class="num">colunas</th><th>Prédios</th><th>Contenção</th><th>Observação</th></tr></thead><tbody>` +
      state.data.datasets.map((d) => `<tr>
        <td><input type="checkbox" data-ds="${d.id}" ${state.enabled[d.id] ? 'checked' : ''}></td>
        <td>${d.generation === 'legacy' ? '<span style="color:var(--serious)">legacy_</span>' : ''}${d.id}</td>
        <td><span class="tag ${d.generation}">${d.generation}</span></td>
        <td class="num">${d.rows.toLocaleString('pt-BR')}</td>
        <td class="num">${d.columns}</td>
        <td>${d.buildings.map((b) => state.data.buildings[b].label).join(', ') || '—'}</td>
        <td>${d.hasContention ? 'sim' : '—'}</td>
        <td style="color:var(--ink-muted)">${d.supersededBy ? 'contido em ' + d.supersededBy
          : d.duplicateOf ? 'idêntico a ' + d.duplicateOf : ''}</td>
      </tr>`).join('') + '</tbody></table>';
    $('#dsTable').querySelectorAll('input[data-ds]').forEach((cb) =>
      cb.addEventListener('change', () => { state.enabled[cb.dataset.ds] = cb.checked; renderAll(); }));
  }

  function renderPool() {
    const rows = activeRows();
    const b = new Set(rows.map((r) => r.b)).size;
    const p = positionsOf(rows).length;
    $('#poolSummary').innerHTML =
      `<b>${rows.length.toLocaleString('pt-BR')}</b> amostras<br><b>${b}</b> prédios · <b>${p}</b> posições`;
  }

  function renderAll() {
    renderPool(); renderGates(); renderMatrix();
    if (state.view === 'contention') renderContention();
    if (state.view === 'constraint') renderConstraint();
    if (state.view === 'plan') renderPlan();
    if (state.view === 'datasets') renderDatasets();
  }

  const TITLES = {
    matrix: ['Capacidade por aplicação', 'QoE não é uma nota: é o que dá para fazer aqui, com esta quantidade de gente na rede.'],
    contention: ['Contenção', 'A mesma posição medida com 1, 2 e 3 clientes competindo.'],
    constraint: ['Restrição dominante', 'Qual das quatro métricas reprova mais em cada posição.'],
    plan: ['Planta baixa', 'Pontos realmente medidos, em escala. Sem interpolação.'],
    thresholds: ['Limiares', 'Limiares de QoE por aplicação, explícitos e editáveis.'],
    datasets: ['Datasets', 'Varredura automática do repositório, com o interruptor de legacy.'],
  };

  function show(view) {
    state.view = view;
    if (location.hash.slice(1) !== view) location.hash = view;
    document.querySelectorAll('.view').forEach((s) => s.classList.add('hide'));
    $('#view-' + view).classList.remove('hide');
    document.querySelectorAll('nav button').forEach((b) =>
      b.setAttribute('aria-current', String(b.dataset.view === view)));
    $('#viewTitle').textContent = TITLES[view][0];
    $('#viewSub').textContent = TITLES[view][1];
    renderAll();
  }

  fetch('api/payload').then((r) => r.json()).then((data) => {
    state.data = data;
    data.datasets.forEach((d) => { state.enabled[d.id] = d.enabled; });
    // ?legacy=1 liga os datasets legacy de saida — deixa um link reproduzir
    // exatamente o conjunto que alguem estava vendo.
    if (new URLSearchParams(location.search).get('legacy') === '1') {
      state.legacy = true;
      data.datasets.forEach((d) => {
        if (d.generation === 'legacy') state.enabled[d.id] = !d.supersededBy && !d.duplicateOf;
      });
    }
    state.thr = { ...PROFILES[state.app] };

    $('#appSel').innerHTML = Object.keys(PROFILES).map((k) =>
      `<option${k === state.app ? ' selected' : ''}>${k}</option>`).join('') +
      '<option value="__custom">Personalizado</option>';
    $('#appSel').addEventListener('change', (e) => {
      if (e.target.value === '__custom') return;
      state.app = e.target.value;
      state.thr = { ...PROFILES[state.app] };
      renderSliders(); renderAll();
    });
    $('#legacyBtn').addEventListener('click', () => {
      state.legacy = !state.legacy;
      $('#legacyBtn').setAttribute('aria-pressed', String(state.legacy));
      state.data.datasets.forEach((d) => {
        if (d.generation === 'legacy') {
          state.enabled[d.id] = state.legacy && !d.supersededBy && !d.duplicateOf;
        }
      });
      renderDatasets(); renderAll();
    });
    $('#metricSel').addEventListener('change', (e) => { state.metric = e.target.value; renderContention(); });
    document.querySelectorAll('nav button').forEach((b) =>
      b.addEventListener('click', () => show(b.dataset.view)));
    $('#themeBtn').addEventListener('click', () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      const next = dark ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('qoe-theme', next); } catch (e) { /* modo privado */ }
      renderAll();
    });

    V.attachTooltip($('#cContention'), $('#tContention'), () => hits.contention,
      (h) => `<b>${h.label}</b>${h.at}: ${h.value.toFixed(1)}`);
    V.attachTooltip($('#cConstraint'), $('#tConstraint'), () => hits.constraint,
      (h) => `<b>${h.at}</b>${h.label} reprovado em ${h.value.toFixed(0)}%`);

    $('#legacyBtn').setAttribute('aria-pressed', String(state.legacy));
    renderSliders(); renderDatasets();
    const wanted = location.hash.slice(1);
    show(TITLES[wanted] ? wanted : 'matrix');
    window.addEventListener('hashchange', () => {
      const v = location.hash.slice(1);
      if (TITLES[v] && v !== state.view) show(v);
    });
    window.addEventListener('resize', () => renderAll());
  });
})();
