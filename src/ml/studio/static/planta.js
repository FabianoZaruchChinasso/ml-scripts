/* planta.js — view Planta: vetor + foto, so foto, so vetor ou retangulo; giro e
   calibracao. studio.js calcula os pontos (os limiares sao dele) e chama render(ctx). */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const ler = (k, padrao) => { try { return localStorage.getItem(k) || padrao; } catch (e) { return padrao; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* modo privado */ } };
  const escuro = () => {
    const tema = document.documentElement.getAttribute('data-theme');
    return tema ? tema === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  };

  const ORIGENS = [['superior-esquerdo', 'superior esquerdo'], ['superior-direito', 'superior direito'],
    ['inferior-esquerdo', 'inferior esquerdo'], ['inferior-direito', 'inferior direito']];
  const ROTULO_MODO = { C: 'vetor + foto', B: 'foto', A: 'vetor', R: 'sem planta' };
  const ALERTA = '<svg class="icon"><use href="#i-alert"/></svg>';

  const st = { ctx: null, orient: ler('qoe-plan-orient', 'paisagem'), foto: ler('qoe-plan-foto', 'on'),
               imgs: {}, hits: {}, cal: null };

  function imagem(url) {
    let img = st.imgs[url];
    if (!img) {
      img = new Image();
      img.onload = () => { if (st.ctx) render(st.ctx); };
      img.src = url;
      st.imgs[url] = img;
    }
    return img.complete && img.naturalWidth ? img : null;
  }

  function modo(pl) {
    if (pl && pl.paredes && pl.foto) return 'C';
    if (pl && pl.foto) return 'B';
    if (pl && pl.paredes) return 'A';
    return 'R';
  }

  function especificacao(p, pl) {
    const md = modo(pl);
    const img = pl && pl.foto ? imagem(pl.foto.url) : null;
    const comFoto = img && (md === 'B' || st.foto === 'on');
    return {
      envelope: p.env, points: p.points,
      paredes: pl ? pl.paredes : null, papel: pl ? pl.papel : null,
      margem: pl && pl.foto ? pl.margem_cm : 0,
      foto: comFoto ? { img, margem: pl.margem_cm } : null,
      fotoAlpha: md === 'B' ? 1 : 0.28, orient: st.orient, escuro: escuro(),
    };
  }

  const tooltip = (h) => `<b>${esc(h.label)}</b>${Math.round(h.value)}% atende · ${esc(h.at)}`;

  function render(ctx) {
    st.ctx = ctx;
    const host = $('#plans');
    $('#planGirar').setAttribute('aria-pressed', String(st.orient === 'retrato'));
    $('#planFoto').setAttribute('aria-pressed', String(st.foto === 'on'));
    $('#planFoto').classList.toggle('hide', !ctx.predios.some((p) => modo(p.planta) === 'C'));
    $('#planAvisos').innerHTML = ctx.avisos.map((a) => `<div class="plan-aviso">${ALERTA}${esc(a)}</div>`).join('');
    host.classList.toggle('paisagem', st.orient === 'paisagem');
    st.hits = {};
    if (!ctx.predios.length) {
      host.innerHTML = '<p class="hint">Nenhum dataset com geometria está ativo.</p>';
      renderCalibracao();
      return;
    }
    host.innerHTML = '';
    // Duas passadas: monta TODO o DOM antes de desenhar. Desenhar durante a
    // montagem mede o canvas enquanto ele ainda e o unico filho do grid — ele
    // fica com backing store da largura inteira e depois encolhe para meia
    // coluna, o que achata os circulos em elipses.
    const pendentes = [];
    ctx.predios.forEach((p) => {
      const pl = p.planta;
      const fora = p.points.filter((q) => q.x < 0 || q.x > p.env.w || q.y < 0 || q.y > p.env.h).length;
      const avisos = (pl ? pl.avisos : []).concat(fora ? [`${fora} ponto(s) fora do envelope de ${p.env.w} × ${p.env.h} cm`] : []);
      const pendente = pl && pl.calibracao.foto && !pl.foto;
      const wrap = document.createElement('div');
      wrap.innerHTML = `<div class="plan-head"><h2>${esc(p.label)} <span>· ${p.env.w}×${p.env.h} cm · ${p.points.length} pontos · ${ROTULO_MODO[modo(pl)]}</span></h2>
        <button class="${pendente ? 'btn-pri' : 'btn'}" data-calibrar="${esc(p.b)}">Calibrar planta</button></div>
        ${avisos.map((a) => `<div class="plan-aviso">${ALERTA}${esc(a)}</div>`).join('')}
        <div class="chartwrap"><canvas></canvas><div class="tooltip"></div></div>`;
      host.appendChild(wrap);
      pendentes.push({ p, pl, wrap });
    });
    pendentes.forEach(({ p, pl, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      st.hits[p.b] = V.drawFloorPlan(canvas, especificacao(p, pl));
      V.attachTooltip(canvas, wrap.querySelector('.tooltip'), () => st.hits[p.b], tooltip);
    });
    renderCalibracao();
  }

  /* ---------------- calibracao ---------------- */
  async function abrirCalibracao(b) {
    const p = st.ctx.predios.find((x) => x.b === b);
    const cal = (p.planta && p.planta.calibracao) || { paredes: null, foto: null };
    const arquivos = await fetch('api/plan/arquivos').then((r) => r.json());
    const cp = cal.paredes || {};
    const cf = cal.foto || {};
    st.cal = { b, arquivos, csv: cp.arquivo || '', origem: cp.origem || 'inferior-direito',
               eixo: cp.eixo_x || 'horizontal', foto: cf.arquivo || '',
               cantos: (cf.cantos || []).map((c) => c.slice()), paredes: null, erro: null, escala: 1 };
    await carregarParedes();
    render(st.ctx);
    $('#planCal').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function carregarParedes() {
    const c = st.cal;
    c.paredes = null;
    c.erro = null;
    if (!c.csv) return;
    const q = new URLSearchParams({ arquivo: c.csv, origem: c.origem, eixo_x: c.eixo });
    const r = await fetch(`api/plan/${encodeURIComponent(c.b)}/paredes?${q}`);
    const corpo = await r.json().catch(() => ({}));
    if (r.ok) c.paredes = corpo;
    else c.erro = typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`;
  }

  // Mesma regra de plans.papel_da_foto: cada eixo vai para o eixo dominante da foto.
  function papelDaFoto(cantos) {
    const encaixar = (dx, dy) => (Math.abs(dx) >= Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)]);
    const ex = encaixar(cantos[1][0] - cantos[0][0], cantos[1][1] - cantos[0][1]);
    const ey = encaixar(cantos[3][0] - cantos[0][0], cantos[3][1] - cantos[0][1]);
    return [[ex[0], ey[0]], [ex[1], ey[1]]];
  }

  function renderCalibracao() {
    const host = $('#planCal');
    const c = st.cal;
    const p = c && st.ctx.predios.find((x) => x.b === c.b);
    if (!p) { st.cal = null; host.innerHTML = ''; host.classList.add('hide'); return; }
    host.classList.remove('hide');
    const passos = ['(0, 0), a origem', `(${p.env.w}, 0)`, `(${p.env.w}, ${p.env.h})`, `(0, ${p.env.h})`];
    const opcoes = (lista, atual, vazio) => `<option value="">${vazio}</option>` +
      lista.map((n) => `<option${n === atual ? ' selected' : ''}>${esc(n)}</option>`).join('');
    const passo = c.cantos.length < 4 ? `Clique no canto <b>${passos[c.cantos.length]}</b> do envelope na foto.`
      : 'Os 4 cantos estão marcados. Confira a pré-visualização.';
    host.innerHTML = `<div class="card"><div class="card-head"><div><h2>Calibrar planta · ${esc(p.label)}</h2>
      <p class="hint">Os cantos são os do envelope dos dados (${p.env.w} × ${p.env.h} cm), a partir da origem. Nada é gravado antes de salvar.</p></div>
      <div><button class="btn" data-cal="cancelar">Cancelar</button> <button class="btn-pri" data-cal="salvar">Salvar calibração</button></div></div>
      ${c.erro ? `<div class="plan-aviso">${ALERTA}${esc(c.erro)}</div>` : ''}
      <div class="cal-grid"><div>
        <div class="controls"><label>Paredes</label><select data-campo="csv">${opcoes(c.arquivos.paredes, c.csv, 'nenhum CSV')}</select>
          <label>Origem</label><select data-campo="origem">${ORIGENS.map(([k, r]) => `<option value="${k}"${k === c.origem ? ' selected' : ''}>${r}</option>`).join('')}</select>
          <label>Eixo x</label><select data-campo="eixo">${['horizontal', 'vertical'].map((k) => `<option${k === c.eixo ? ' selected' : ''}>${k}</option>`).join('')}</select></div>
        <div class="controls"><label>Foto</label><select data-campo="foto">${opcoes(c.arquivos.fotos, c.foto, 'nenhuma foto')}</select>
          <button class="btn" data-cal="desfazer"${c.cantos.length ? '' : ' disabled'}>Desfazer</button>
          <button class="btn" data-cal="recomecar"${c.cantos.length ? '' : ' disabled'}>Recomeçar</button></div>
        ${c.foto ? `<p class="hint">${passo}</p><div class="cal-foto"><canvas id="calFoto"></canvas></div>`
          : '<p class="hint">Sem foto: o registro usa só as paredes.</p>'}
      </div><div><p class="hint">Pré-visualização</p>
        <div class="chartwrap"><canvas id="calPrevia"></canvas><div class="tooltip" id="calTip"></div></div></div></div></div>`;
    desenharFoto();
    desenharPrevia(p);
  }

  function desenharFoto() {
    const c = st.cal;
    const canvas = $('#calFoto');
    if (!canvas) return;
    const img = imagem('api/plan/arquivo/' + encodeURIComponent(c.foto));
    if (!img) return;
    c.escala = Math.min(canvas.parentElement.clientWidth / img.naturalWidth, 640 / img.naturalHeight);
    const w = Math.round(img.naturalWidth * c.escala);
    const h = Math.round(img.naturalHeight * c.escala);
    const ratio = window.devicePixelRatio || 1;
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.drawImage(img, 0, 0, w, h);
    const cor = getComputedStyle(document.documentElement).getPropertyValue('--s1').trim();
    const pts = c.cantos.map(([x, y]) => [x * c.escala, y * c.escala]);
    if (pts.length > 1) {
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (pts.length === 4) ctx.closePath();
      ctx.stroke();
    }
    ctx.font = '600 11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    pts.forEach(([x, y], i) => {
      ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fillStyle = cor; ctx.fill();
      ctx.fillStyle = '#ffffff'; ctx.fillText(String(i + 1), x, y);
    });
  }

  function desenharPrevia(p) {
    const c = st.cal;
    const canvas = $('#calPrevia');
    const margem = p.planta ? p.planta.margem_cm : 0;
    let foto = null;
    if (c.foto && c.cantos.length === 4) {
      const q = new URLSearchParams({ arquivo: c.foto, cantos: c.cantos.flat().join(',') });
      const img = imagem(`api/plan/${encodeURIComponent(c.b)}/foto.png?${q}`);
      if (img) foto = { img, margem };
    }
    const papel = c.paredes ? c.paredes.papel : (c.foto && c.cantos.length === 4 ? papelDaFoto(c.cantos) : null);
    const hits = V.drawFloorPlan(canvas, {
      envelope: p.env, points: p.points, paredes: c.paredes ? c.paredes.paredes : null, papel,
      margem: c.foto ? margem : 0, foto, fotoAlpha: c.paredes ? 0.28 : 1,
      orient: 'retrato', altura: 640, escuro: escuro(),
    });
    V.attachTooltip(canvas, $('#calTip'), () => hits, tooltip);
  }

  async function salvar() {
    const c = st.cal;
    const corpo = {};
    if (c.csv) corpo.paredes = { arquivo: c.csv, origem: c.origem, eixo_x: c.eixo };
    if (c.foto) corpo.foto = { arquivo: c.foto, cantos: c.cantos.length === 4 ? c.cantos : null };
    const r = await fetch(`api/plan/${encodeURIComponent(c.b)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
    const resp = await r.json().catch(() => ({}));
    if (!r.ok) {
      c.erro = typeof resp.detail === 'string' ? resp.detail : `HTTP ${r.status}`;
      renderCalibracao();
      return;
    }
    st.cal = null;
    st.ctx.atualizarPlantas(resp.plantas, resp.plantasAvisos);
  }

  /* ---------------- eventos ---------------- */
  $('#planGirar').addEventListener('click', () => {
    st.orient = st.orient === 'paisagem' ? 'retrato' : 'paisagem';
    guardar('qoe-plan-orient', st.orient);
    render(st.ctx);
  });
  $('#planFoto').addEventListener('click', () => {
    st.foto = st.foto === 'on' ? 'off' : 'on';
    guardar('qoe-plan-foto', st.foto);
    render(st.ctx);
  });
  $('#plans').addEventListener('click', (ev) => {
    const botao = ev.target.closest('[data-calibrar]');
    if (botao) abrirCalibracao(botao.dataset.calibrar);
  });
  $('#planCal').addEventListener('click', (ev) => {
    const c = st.cal;
    if (!c) return;
    if (ev.target.id === 'calFoto' && c.cantos.length < 4) {
      const r = ev.target.getBoundingClientRect();
      const arred = (v) => Math.round(v * 10) / 10;
      c.cantos.push([arred((ev.clientX - r.left) / c.escala), arred((ev.clientY - r.top) / c.escala)]);
      renderCalibracao();
      return;
    }
    const acao = ev.target.closest('[data-cal]');
    if (!acao) return;
    if (acao.dataset.cal === 'cancelar') { st.cal = null; renderCalibracao(); }
    if (acao.dataset.cal === 'desfazer') { c.cantos.pop(); renderCalibracao(); }
    if (acao.dataset.cal === 'recomecar') { c.cantos = []; renderCalibracao(); }
    if (acao.dataset.cal === 'salvar') salvar();
  });
  $('#planCal').addEventListener('change', async (ev) => {
    const c = st.cal;
    const campo = ev.target.dataset.campo;
    if (!c || !campo) return;
    c[campo] = ev.target.value;
    if (campo === 'foto') c.cantos = [];
    if (campo !== 'foto') await carregarParedes();
    renderCalibracao();
  });

  V.views.planta = { render };
})();
