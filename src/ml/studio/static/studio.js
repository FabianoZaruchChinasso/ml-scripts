/* studio.js — estado global do Studio, rotas, chip do conjunto e tema.
   Cada área se desenha sozinha a partir de render(ctx): dados.js, modelo.js e
   laboratorio.js. O painel do conjunto fica em conjunto.js; o desenho de
   gráficos, em graficos.js; as regras puras, em logica.js. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  const { esc } = V.util;

  const AREAS = ['dados', 'modelo', 'laboratorio'];
  // Hashes de antes da reorganização: links salvos continuam abrindo o lugar certo.
  const REDIRECIONA = { matrix: 'dados', contention: 'dados', constraint: 'dados', plan: 'dados',
    thresholds: 'dados', datasets: 'dados', assistente: 'modelo', modelos: 'modelo', features: 'laboratorio' };

  /* Limiares de referência por aplicação: src/ml/core/aplicacoes.json, via payload.
     Editáveis na área Dados, só na sessão. */
  let PERFIS = {};
  const state = { data: null, app: 'Chamada de vídeo', thr: null, personalizado: false, legacy: false,
                  enabled: {}, area: null, ambiente: 'todos' };


  const ambienteDe = (b) => state.data.buildings[b].ambiente;
  function activeRows() {
    return state.data.rows.filter((r) => state.enabled[r.ds]
      && (state.ambiente === 'todos' || ambienteDe(r.b) === state.ambiente));
  }
  const enabledIds = () => Object.keys(state.enabled).filter((id) => state.enabled[id]);

  function ctx() {
    return { data: state.data, rows: activeRows(), enabled: state.enabled, enabledIds: enabledIds(),
             ambiente: state.ambiente, ambientes: state.data.ambientes, legacy: state.legacy,
             app: state.app, personalizado: state.personalizado, thr: state.thr, perfis: PERFIS };
  }

  function renderChip(c) {
    const predios = new Set(c.rows.map((r) => r.b)).size;
    const amb = c.ambiente === 'todos' ? 'todos os ambientes' : c.ambientes[c.ambiente].toLowerCase();
    const n = V.conjunto.contagem();
    const total = n.avisos + n.pendencias;
    const chip = $('#chipConjunto');
    chip.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#i-db"/></svg>
      <span><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras · <b>${predios}</b> prédios · ${esc(amb)}</span>
      ${total ? `<span class="badge${n.critico ? ' critico' : ''}">${total}</span>` : ''}`;
    chip.setAttribute('aria-label', `Conjunto ativo: ${c.rows.length} amostras, ${predios} prédios, ${amb}` +
      (total ? `, ${total} avisos ou pendências` : '') + '. Abrir o painel.');
  }

  function renderAll() {
    if (!state.data || !state.area) return;
    const c = ctx();
    V.conjunto.render(c);
    renderChip(c);
    V.areas[state.area].render(c);
  }

  function show(area) {
    state.area = area;
    AREAS.forEach((a) => $('#area-' + a).classList.toggle('hide', a !== area));
    document.querySelectorAll('[data-area]').forEach((el) =>
      el.setAttribute('aria-current', String(el.dataset.area === area)));
    renderAll();
  }

  function rota() {
    const h = location.hash.slice(1);
    const area = AREAS.includes(h) ? h : (REDIRECIONA[h] || 'dados');
    if (h !== area) history.replaceState(null, '', '#' + area);
    show(area);
    if (h === 'datasets') V.conjunto.abrir();
  }

  function aplicarLegacy(on) {
    state.legacy = on;
    state.data.datasets.forEach((d) => {
      if (d.generation === 'legacy') state.enabled[d.id] = on && !d.supersededBy && !d.duplicateOf;
    });
  }

  V.app = {
    ctx,
    atualizar: renderAll,
    atualizarChip() { if (state.data) renderChip(ctx()); },
    irPara(area) { location.hash = area; },
    ligar(id, on) { state.enabled[id] = on; renderAll(); },
    definirLegacy(on) { aplicarLegacy(on); renderAll(); },
    definirAmbiente(a) { state.ambiente = a; renderAll(); },
    definirAplicacao(app) { state.app = app; state.thr = { ...PERFIS[app] }; state.personalizado = false; renderAll(); },
    definirLimiar(key, valor) { state.thr[key] = valor; state.personalizado = true; renderAll(); },
    // Classificação, contadores ou derivada nova mudam colunas e chaves de cache: quem guarda cache recarrega.
    colunasMudaram() {
      [V.conjunto, V.areas.modelo].concat(Object.values(V.views || {}))
        .forEach((m) => { if (m && m.recarregar) m.recarregar(); });
      renderAll();
    },
  };

  fetch('api/payload').then((r) => r.json()).then((data) => {
    state.data = data;
    PERFIS = data.aplicacoes;
    data.datasets.forEach((d) => { state.enabled[d.id] = d.enabled; });
    const q = new URLSearchParams(location.search);
    // ?legacy=1 liga os datasets legacy de saída: deixa um link reproduzir o conjunto que alguém estava vendo.
    if (q.get('legacy') === '1') aplicarLegacy(true);
    // ?ambiente=domestico|corporativo abre o Studio já filtrado.
    const amb = q.get('ambiente');
    if (amb && data.ambientes[amb]) state.ambiente = amb;
    state.thr = { ...PERFIS[state.app] };

    $('#chipConjunto').addEventListener('click', () => V.conjunto.abrir());
    $('#themeBtn').addEventListener('click', () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      const next = dark ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('qoe-theme', next); } catch (e) { /* modo privado */ }
      renderAll();
    });
    window.addEventListener('hashchange', rota);
    window.addEventListener('resize', renderAll);
    rota();
  });
})();
