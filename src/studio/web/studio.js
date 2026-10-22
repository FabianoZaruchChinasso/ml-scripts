/* studio.js — estado global do Studio novo, rotas, chip do conjunto e tema.
   Cada área se desenha a partir de render(ctx): dados.js (e modelo.js, na parte 2).
   O conjunto ativo é gravado no servidor (.studio/conjunto.json) a cada mudança. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  const { esc } = V.util;

  const AREAS = ['dados', 'modelo'];
  /* Limiares de referência por aplicação: src/studio/config/aplicacoes.json, via payload.
     Editáveis na área Dados, só na sessão. */
  let PERFIS = {};
  const state = { data: null, app: 'Chamada de vídeo', thr: null, personalizado: false, legacy: false,
                  enabled: {}, area: null, ambiente: 'todos', erroConjunto: null };

  const ambienteDe = (b) => state.data.buildings[b].ambiente;
  function activeRows() {
    return state.data.rows.filter((r) => state.enabled[r.ds]
      && (state.ambiente === 'todos' || ambienteDe(r.b) === state.ambiente));
  }
  const enabledIds = () => Object.keys(state.enabled).filter((id) => state.enabled[id]);

  function ctx() {
    return { data: state.data, rows: activeRows(), enabled: state.enabled, enabledIds: enabledIds(),
             ambiente: state.ambiente, ambientes: state.data.ambientes, legacy: state.legacy,
             app: state.app, personalizado: state.personalizado, thr: state.thr, perfis: PERFIS,
             erroConjunto: state.erroConjunto };
  }

  function renderChip(c) {
    const predios = new Set(c.rows.map((r) => r.b)).size;
    const amb = c.ambiente === 'todos' ? 'todos os ambientes' : c.ambientes[c.ambiente].toLowerCase();
    const n = V.conjunto.contagem();
    const chip = $('#chipConjunto');
    chip.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#i-db"/></svg>
      <span><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras · <b>${predios}</b> prédios · ${esc(amb)}</span>
      ${n.avisos ? `<span class="badge${n.critico ? ' critico' : ''}">${n.avisos}</span>` : ''}`;
    chip.setAttribute('aria-label', `Conjunto ativo: ${c.rows.length} amostras, ${predios} prédios, ${amb}` +
      (n.avisos ? `, ${n.avisos} avisos` : '') + '. Abrir o painel.');
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
    const area = AREAS.includes(h) ? h : 'dados';
    if (h !== area && h !== 'datasets') history.replaceState(null, '', '#' + area);
    show(area);
    if (h === 'datasets') V.conjunto.abrir();
  }

  // Grava o conjunto no servidor. Se falhar, a tela segue com o estado local e o painel mostra o erro.
  function gravarConjunto() {
    V.util.post('api/conjunto', { datasets: enabledIds() })
      .then(() => { state.erroConjunto = null; })
      .catch((e) => { state.erroConjunto = e.message; })
      .finally(renderAll);
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
    ligar(id, on) { state.enabled[id] = on; renderAll(); gravarConjunto(); },
    definirLegacy(on) { aplicarLegacy(on); renderAll(); gravarConjunto(); },
    definirAmbiente(a) { state.ambiente = a; renderAll(); },
    definirAplicacao(app) { state.app = app; state.thr = { ...PERFIS[app] }; state.personalizado = false; renderAll(); },
    definirLimiar(key, valor) { state.thr[key] = valor; state.personalizado = true; renderAll(); },
    // Dataset ou prédio novo: relê o payload, mantém o que estava ligado ou desligado
    // e liga os datasets que acabaram de chegar.
    recarregarPayload(ligar) {
      return V.util.pedir('api/payload').then((data) => {
        const antes = state.enabled;
        state.data = data;
        state.enabled = {};
        data.datasets.forEach((d) => { state.enabled[d.id] = d.id in antes ? antes[d.id] : d.enabled; });
        (ligar || []).forEach((id) => { state.enabled[id] = true; });
        renderAll();
        if (ligar && ligar.length) gravarConjunto();
      });
    },
  };

  V.util.pedir('api/payload').then((data) => {
    state.data = data;
    PERFIS = data.aplicacoes;
    data.datasets.forEach((d) => { state.enabled[d.id] = d.enabled; });
    const q = new URLSearchParams(location.search);
    if (q.get('legacy') === '1') aplicarLegacy(true);
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
  }).catch((e) => {
    document.querySelector('main').innerHTML = V.util.gate('critical', 'Não foi possível carregar os dados', esc(e.message));
  });
})();
