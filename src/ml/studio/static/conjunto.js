/* conjunto.js — painel do conjunto ativo: avisos, pendências, ambiente e datasets.
   Abre pelo chip do topo, por cima de qualquer área. studio.js chama render(ctx) a
   cada mudança; as pendências são buscadas mesmo com o painel fechado, para o
   contador do chip ficar certo. */
(function () {
  'use strict';
  const V = window.VENKO;
  const L = V.logica;
  const U = V.util;
  const { esc } = U;
  const $ = (s) => document.querySelector(s);

  const CLASSES = [['tr069', 'Roteador'], ['sniffer', 'Sniffer'], ['cliente', 'Cliente'],
    ['ambiente', 'Ambiente'], ['geometria', 'Geometria'], ['identificador', 'Identificador'], ['alvo', 'Alvo']];
  const RESPOSTAS = { sim: 'Sim', nao: 'Não', nao_sei: 'Não sei' };
  const CONTADORES = {
    nao_sei: ['Não sei', 'Continuam nos ajustes, marcados como "não confirmado"; o desenho automático começa sem eles.'],
    sim: ['Sim', 'Viram vazamento: saem dos ajustes, e versões que os usam são avaliadas sem eles.'],
    nao: ['Não', 'Liberados como qualquer coluna TR-069.'],
  };

  const st = { ctx: null, aberto: false, voltarPara: null,
               pend: null, inv: null, chave: null, erro: null, respErro: null, ocupado: false,
               dispensadas: new Set() };

  const chaveDe = (c) => c.enabledIds.slice().sort().join(',') + '|' + c.ambiente;
  const suspeitas = () => st.inv.colunas.filter((c) => c.suspeita && !c.derivada && !st.dispensadas.has(c.coluna));

  /* ---------------- carregamento ---------------- */
  function carregar() {
    const c = st.ctx;
    const k = chaveDe(c);
    if (st.chave === k) return;
    st.chave = k; st.pend = null; st.inv = null; st.erro = null;
    if (!c.enabledIds.length) return;
    const q = 'ds=' + encodeURIComponent(c.enabledIds.join(',')) + '&ambiente=' + encodeURIComponent(c.ambiente);
    // A suspeita de vazamento é medida contra o download, como no antigo passo "Preparar".
    Promise.all([U.pedir('api/pendencias?' + q),
                 U.pedir('api/features/inventario?' + q + '&alvo=speedtest_down_mbps')])
      .then(([p, inv]) => { if (st.chave === k) { st.pend = p; st.inv = inv; } })
      .catch((e) => { if (st.chave === k) st.erro = e.message; })
      .finally(() => { if (st.chave === k) { desenhar(); V.app.atualizarChip(); } });
  }

  function contagem() {
    if (!st.ctx) return { avisos: 0, pendencias: 0, critico: false };
    const avisos = L.avisosConjunto(st.ctx.data, st.ctx.rows, st.ctx.enabled, st.ctx.ambiente);
    const pendencias = st.inv && st.pend
      ? st.inv.sem_classificacao.length + suspeitas().length + (st.pend.contadores.estado === 'nao_sei' ? 1 : 0) : 0;
    return { avisos: avisos.length, pendencias, critico: avisos.some((a) => a.sev === 'critical') };
  }

  // Classificação e contadores mudam colunas, vazamento e chaves de cache de todas as áreas.
  function responder(pedido) {
    st.ocupado = true; st.respErro = null; desenhar();
    pedido.then(() => { st.chave = null; V.app.colunasMudaram(); })
      .catch((e) => { st.respErro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- seções ---------------- */
  function secaoAvisos(avisos) {
    if (!avisos.length) return '<p class="gate-msg">Nenhum aviso.</p>';
    return avisos.map((a) => U.gate(a.sev, esc(a.titulo), esc(a.msg),
      (a.causas.length ? '<ul>' + a.causas.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>' : '') +
      (a.acao ? `<div class="aviso-acao"><button class="btn" data-acao="desligar" data-ds="${esc(a.acao.ds)}"
        data-k="desligar-${esc(a.acao.ds)}">Desligar ${esc(a.acao.ds)}</button></div>` : ''))).join('');
  }

  function secaoPendencias() {
    if (st.erro) return U.gate('warning', 'Pendências indisponíveis', esc(st.erro));
    if (!st.inv || !st.pend) return '<p class="gate-msg">Carregando pendências…</p>';
    const trava = st.ocupado ? ' disabled' : '';
    const itens = [];
    st.inv.sem_classificacao.forEach((c) => itens.push(`<div class="pend-item warning"><div style="flex:1">
      <b>De onde vem <code>${esc(c.coluna)}</code>?</b>
      <div class="gate-msg">${U.pct(c.cobertura)} das linhas têm valor · ex.: ${esc(c.amostra)}</div>
      <div class="controls" style="margin:8px 0 0">
        <select data-classe="${esc(c.coluna)}" data-k="classe-${esc(c.coluna)}" aria-label="Origem de ${esc(c.coluna)}">${CLASSES.map(([k, r]) =>
          `<option value="${k}"${k === c.sugestao ? ' selected' : ''}>${r}${k === c.sugestao ? ' (sugerido)' : ''}</option>`).join('')}</select>
        <button class="btn-pri" data-acao="classificar" data-col="${esc(c.coluna)}" data-k="classificar-${esc(c.coluna)}"${trava}>Salvar</button>
      </div></div></div>`));
    suspeitas().forEach((c) => itens.push(`<div class="pend-item warning"><div style="flex:1">
      <b><code>${esc(c.coluna)}</code> é medido durante o speedtest?</b>
      <div class="gate-msg">Anda quase igual ao download (|ρ| = ${U.num(c.rho, 2)}). Se for medido durante o teste,
        carrega o próprio resultado e não existe em produção.</div>
      <div class="controls" style="margin:8px 0 0">${Object.entries(RESPOSTAS).map(([k, r]) =>
        `<button class="btn" data-acao="suspeita" data-col="${esc(c.coluna)}" data-resp="${k}"
          data-k="susp-${esc(c.coluna)}-${k}"${trava}>${r}</button>`).join('')}</div></div></div>`));
    const est = st.pend.contadores.estado;
    // Respondida (sim ou não), a pergunta fica como configuração: borda neutra, não alarme.
    itens.push(`<div class="pend-item ${est === 'nao_sei' ? 'warning' : 'good'}"><div style="flex:1">
      <b>Os contadores do roteador são medidos durante o speedtest?</b>
      <div class="gate-msg"><code>${st.pend.contadores.colunas.map(esc).join('</code>, <code>')}</code>.
        Se forem, carregam o próprio alvo, como <code>router_tx_bytes</code>.</div>
      <div class="opcoes" role="radiogroup" aria-label="Contadores medidos durante o speedtest?">${Object.entries(CONTADORES).map(([k, [rot, efeito]]) =>
        `<label class="opcao${est === k ? ' marcada' : ''}"><input type="radio" name="cContadores" value="${k}"
          data-k="cont-${k}"${est === k ? ' checked' : ''}${trava}>
          <span><b>${rot}</b><span class="gate-msg">${efeito}</span></span></label>`).join('')}</div></div></div>`);
    if (st.pend.zeros_ambiguos.length) {
      itens.push(`<div class="pend-item warning"><div><b>Datasets do coletor antigo</b>
        <div class="gate-msg">Antes da correção, <code>router_opportunity_medium_use</code> gravava 0 também quando o scan
          de vizinhos faltava. Nestes datasets um 0 pode ser "canal limpo" ou "sem medição":
          ${st.pend.zeros_ambiguos.map((z) => `<code>${esc(z.dataset)}</code> (${Math.round(z.zeros * 100)}% de zeros)`).join(', ')}.</div></div></div>`);
    }
    return (st.respErro ? U.gate('critical', 'Não foi possível salvar', esc(st.respErro)) : '') +
      `<div class="pend-grid">${itens.join('')}</div>
      <p class="gate-msg" style="margin-top:8px">As respostas gravam em <code>src/ml/core/column_provenance.json</code>. Revise no <code>git diff</code> antes do commit.</p>`;
  }

  function secaoAmbiente() {
    const c = st.ctx;
    const opcoes = [['todos', 'Todos']].concat(Object.entries(c.ambientes));
    return `<div class="seg" role="group" aria-label="Ambiente">${opcoes.map(([k, r]) =>
      `<button data-acao="ambiente" data-amb="${k}" data-k="amb-${k}" aria-pressed="${c.ambiente === k}">${esc(r)}</button>`).join('')}</div>`;
  }

  function linhaDs(d) {
    const c = st.ctx;
    const predios = d.buildings.map((b) => c.data.buildings[b].label).join(', ') || '—';
    const obs = d.supersededBy ? `contido em ${d.supersededBy}` : d.duplicateOf ? `idêntico a ${d.duplicateOf}` : '';
    return `<label class="ds"><input type="checkbox" data-ds="${esc(d.id)}" data-k="ds-${esc(d.id)}"${c.enabled[d.id] ? ' checked' : ''}>
      <code>${esc(d.id)}</code><span class="gate-msg num">${d.rows.toLocaleString('pt-BR')} linhas</span>
      <span class="gate-msg">${esc(predios)}${obs ? ' · ' + esc(obs) : ''}</span></label>`;
  }

  function secaoDatasets() {
    const c = st.ctx;
    const atuais = c.data.datasets.filter((d) => d.generation !== 'legacy');
    const legacy = c.data.datasets.filter((d) => d.generation === 'legacy');
    return atuais.map(linhaDs).join('') + (legacy.length ? `<details class="fold" data-k="legacy"${c.legacy ? ' open' : ''}>
      <summary>Legacy <span>· ${legacy.length} datasets</span></summary>
      <div class="inner"><label class="ds"><input type="checkbox" data-acao="legacy" data-k="legacy-tudo"${c.legacy ? ' checked' : ''}>
        <span>Incluir datasets legacy</span><span></span>
        <span class="gate-msg">Sem contagem de dispositivos nem geometria: entram só no resumo e no detalhe das posições.</span></label>
        ${legacy.map(linhaDs).join('')}</div></details>` : '');
  }

  function desenhar() {
    if (!st.aberto || !st.ctx) return;
    const c = st.ctx;
    const avisos = L.avisosConjunto(c.data, c.rows, c.enabled, c.ambiente);
    const predios = new Set(c.rows.map((r) => r.b)).size;
    const poucos = st.pend && st.pend.n_locais < st.pend.minimo_confortavel
      ? ` Só ${st.pend.n_locais} locais de coleta: os números ainda mudam quando novos prédios entrarem.` : '';
    U.redesenhar($('#painelCorpo'), `<p class="resumo"><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras ·
        <b>${predios}</b> prédios · <b>${L.posicoes(c.rows).length}</b> posições.${poucos}</p>
      <h3>Avisos (${avisos.length})</h3>${secaoAvisos(avisos)}
      <h3>Pendências</h3>${secaoPendencias()}
      <h3>Ambiente</h3>${secaoAmbiente()}
      <h3>Datasets</h3>${secaoDatasets()}`);
  }

  /* ---------------- abrir, fechar e foco ---------------- */
  function focaveis() {
    return [...$('#painelConjunto').querySelectorAll('button, [href], input, select, summary')]
      .filter((el) => !el.disabled && el.offsetParent !== null);
  }

  function abrir() {
    if (st.aberto) return;
    st.aberto = true;
    st.voltarPara = document.activeElement;
    $('#painelConjunto').classList.remove('hide');
    $('#veuConjunto').classList.remove('hide');
    $('#chipConjunto').setAttribute('aria-expanded', 'true');
    desenhar();
    const f = focaveis();
    (f[0] || $('#painelConjunto')).focus();
  }

  function fechar() {
    if (!st.aberto) return;
    st.aberto = false;
    $('#painelConjunto').classList.add('hide');
    $('#veuConjunto').classList.add('hide');
    $('#chipConjunto').setAttribute('aria-expanded', 'false');
    if (st.voltarPara && st.voltarPara.focus) st.voltarPara.focus();
  }

  // Esc fecha; Tab fica preso no painel enquanto ele está aberto.
  document.addEventListener('keydown', (ev) => {
    if (!st.aberto) return;
    if (ev.key === 'Escape') { ev.preventDefault(); fechar(); return; }
    if (ev.key !== 'Tab') return;
    const f = focaveis();
    if (!f.length) return;
    const primeiro = f[0];
    const ultimo = f[f.length - 1];
    if (!$('#painelConjunto').contains(document.activeElement)) { ev.preventDefault(); primeiro.focus(); }
    else if (ev.shiftKey && document.activeElement === primeiro) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primeiro.focus(); }
  });

  /* ---------------- eventos ---------------- */
  $('#veuConjunto').addEventListener('click', fechar);
  $('#painelConjunto').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-acao]');
    if (!b || b.disabled) return;
    const acao = b.dataset.acao;
    if (acao === 'fechar') fechar();
    if (acao === 'desligar') V.app.ligar(b.dataset.ds, false);
    if (acao === 'ambiente') V.app.definirAmbiente(b.dataset.amb);
    if (acao === 'classificar') {
      const col = b.dataset.col;
      const classe = $('#painelConjunto').querySelector(`select[data-classe="${CSS.escape(col)}"]`).value;
      responder(U.post('api/columns', { coluna: col, classe, vazamento: false, parametro: null }));
    }
    if (acao === 'suspeita') {
      const col = b.dataset.col;
      // Não e Não sei só dispensam o aviso nesta sessão; Sim grava o vazamento.
      if (b.dataset.resp !== 'sim') { st.dispensadas.add(col); desenhar(); V.app.atualizarChip(); return; }
      const c = st.inv.colunas.find((x) => x.coluna === col);
      responder(U.post('api/columns', { coluna: col, classe: c.classe, vazamento: true, parametro: c.parametro || null }));
    }
  });
  $('#painelConjunto').addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.dataset.ds) V.app.ligar(t.dataset.ds, t.checked);
    if (t.dataset.acao === 'legacy') V.app.definirLegacy(t.checked);
    if (t.name === 'cContadores') responder(U.post('api/contadores', { estado: t.value }));
  });

  V.conjunto = {
    render(ctx) { st.ctx = ctx; carregar(); desenhar(); },
    contagem, abrir, fechar,
    recarregar() { st.chave = null; },
  };
})();
