/* assistente.js — view Modelo: assistente em quatro passos para o técnico de rede.
   Estado próprio; studio.js chama render(ctx) quando a view está visível. As views
   Features e Modelos continuam como modo avançado. */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d));
  const pct = (v) => Math.round(v * 100) + '%';

  const ALVOS = [['speedtest_down_mbps', 'Download', 'Mbps'], ['speedtest_up_mbps', 'Upload', 'Mbps'],
    ['latency_ms', 'Latência', 'ms'], ['jitter_ms', 'Jitter', 'ms']];
  const ALVO = Object.fromEntries(ALVOS.map(([k, r, u]) => [k, { rotulo: r, unidade: u }]));
  const PASSOS = ['Preparar', 'Ajustar', 'Testar', 'Publicar'];
  const CLASSES = [['tr069', 'Roteador (TR-069)'], ['sniffer', 'Sniffer'], ['cliente', 'Cliente'],
    ['ambiente', 'Ambiente'], ['geometria', 'Geometria'], ['identificador', 'Identificador'], ['alvo', 'Alvo']];
  const VEREDITO = { melhor: ['Melhor', 'i-check'], empate: ['Empate', 'i-equal'], pior: ['Pior', 'i-alert'] };
  const RESPOSTAS = { sim: 'Sim', nao: 'Não', nao_sei: 'Não sei' };
  const NOME_OK = /^[a-z0-9][a-z0-9-]{1,39}$/;

  const st = { ctx: null, passo: 1, alvo: 'speedtest_down_mbps', erro: null,
               reg: null, inv: null, invKey: null, pend: null, pendKey: null, dispensadas: new Set(),
               base: null, sel: new Set(), filtro: '', cols: null, colsKey: null,
               sug: null, sugKey: null, sugTimer: null,
               receitas: null, recAberto: false,
               rec: { id: 'razao', colunas: [], montada: null, nome: '', ocupado: false, erro: null, resultado: null, montarKey: null },
               aval: null, avalKey: null, avalErro: null, avaliando: false, avalPedido: null,
               outros: null, outrosKey: null, outrosCarregando: false, outrosPedido: null,
               nome: '', desc: '', descTocada: false, nomeTocada: false, publicando: false, pubErro: null, pubMsg: null };

  const dsIds = () => st.ctx.enabledIds.slice().sort();
  const chaveConj = () => dsIds().join(',') + '|' + st.alvo + '|' + st.ctx.ambiente;
  const queryDe = (alvo) => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(alvo) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);
  const query = () => queryDe(st.alvo);
  const selLista = () => [...st.sel].sort();
  const ativa = () => st.reg && st.reg.versoes.find((v) => v.nome === st.reg.ativo);
  const chaveVeredito = () => chaveConj() + '|' + selLista().join(',') + '|' + (st.reg ? st.reg.ativo : '');
  const igualAtiva = () => {
    const a = ativa();
    return !!a && JSON.stringify(a.features.slice().sort()) === JSON.stringify(selLista());
  };

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }
  const post = (url, corpo) => pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });

  const gate = (sev, titulo, msg) => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div></div></div>`;

  /* ---------------- carregamento ---------------- */
  function usarBase(nome) {
    st.base = nome;
    const v = st.reg && st.reg.versoes.find((x) => x.nome === nome);
    st.sel = new Set(v ? v.features : []);
  }

  function carregarRegistro() {
    return pedir('api/modelos').then((reg) => {
      st.reg = reg;
      if (!st.base || !reg.versoes.some((v) => v.nome === st.base)) usarBase(reg.ativo);
      if (st.passo === 2) iniciarSugestoes();
    }).catch((e) => { st.erro = e.message; }).finally(desenhar);
  }

  function carregarInventario() {
    const k = chaveConj();
    if (st.invKey === k) return;
    st.invKey = k; st.inv = null;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.invKey === k) st.inv = inv; })
      .catch((e) => { if (st.invKey === k) st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarPendencias() {
    const k = dsIds().join(',') + '|' + st.ctx.ambiente;
    if (st.pendKey === k) return;
    st.pendKey = k; st.pend = null;
    pedir('api/pendencias?ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente))
      .then((p) => { if (st.pendKey === k) st.pend = p; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarColunas() {
    const k = chaveConj();
    if (st.colsKey === k) return;
    st.colsKey = k; st.cols = null;
    pedir('api/assistente/colunas?' + query())
      .then((r) => { if (st.colsKey === k) st.cols = r.colunas; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarReceitas() {
    if (st.receitas) return;
    pedir('api/receitas').then((r) => { st.receitas = r.receitas; }).catch((e) => { st.erro = e.message; }).finally(desenhar);
  }

  function iniciarSugestoes() {
    if (!st.base) return;
    const k = chaveConj() + '|' + st.base;
    if (st.sugKey === k) return;
    st.sugKey = k; st.sug = { status: 'rodando', progresso: [] };
    clearTimeout(st.sugTimer);
    pedir('api/assistente/sugestoes?' + query() + '&base=' + encodeURIComponent(st.base), { method: 'POST' })
      .then((r) => acompanhar(r.id, k))
      .catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }

  function acompanhar(id, k) {
    pedir('api/assistente/sugestoes/' + id).then((job) => {
      if (st.sugKey !== k) return;
      st.sug = job;
      if (job.status === 'rodando') st.sugTimer = setTimeout(() => acompanhar(id, k), 1500);
      desenhar();
    }).catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }

  function carregar() {
    if (!st.reg) carregarRegistro();
    carregarInventario(); carregarPendencias(); carregarColunas(); carregarReceitas();
    if (st.passo === 2) iniciarSugestoes();
  }

  // Classificação, contadores ou derivada nova mudam as colunas e a chave das análises.
  function recarregarTudo() {
    st.invKey = null; st.pendKey = null; st.colsKey = null; st.sugKey = null;
    carregar();
    if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
  }

  /* ---------------- passo 1 · Preparar ---------------- */
  const pergunta = (titulo, msg, tipo, col, atual) => `<div class="pend-item warning"><div style="flex:1"><b>${titulo}</b>
    <div class="gate-msg">${msg}</div>
    <div class="controls" style="margin:8px 0 0">${Object.entries(RESPOSTAS).map(([k, r]) =>
      `<button class="btn${atual === k ? ' marcado' : ''}" data-aacao="${tipo}" data-col="${esc(col)}" data-resp="${k}">${r}</button>`).join('')}</div></div></div>`;

  function passoPreparar() {
    const alvo = `<div class="controls"><label for="aAlvo">O que o modelo prevê</label>
      <select id="aAlvo">${ALVOS.map(([k, r, u]) => `<option value="${k}"${k === st.alvo ? ' selected' : ''}>${r} (${u})</option>`).join('')}</select></div>`;
    const inv = st.inv, p = st.pend;
    if (!inv || !p) return alvo + '<p class="hint">Carregando pendências…</p>';
    const itens = [];
    inv.sem_classificacao.forEach((c) => itens.push(`<div class="pend-item warning" data-col="${esc(c.coluna)}"><div style="flex:1">
      <b>De onde vem <code>${esc(c.coluna)}</code>?</b>
      <div class="gate-msg">${pct(c.cobertura)} das linhas têm valor · ex.: ${esc(c.amostra)}</div>
      <div class="controls" style="margin:8px 0 0"><select aria-label="Origem de ${esc(c.coluna)}">${CLASSES.map(([k, r]) =>
        `<option value="${k}"${k === c.sugestao ? ' selected' : ''}>${r}${k === c.sugestao ? ' (sugerido)' : ''}</option>`).join('')}</select>
        <button class="btn-pri" data-aacao="classificar">Salvar</button></div></div></div>`));
    inv.colunas.filter((c) => c.suspeita && !c.derivada && !st.dispensadas.has(c.coluna)).forEach((c) => itens.push(pergunta(
      `<code>${esc(c.coluna)}</code> é medido durante o speedtest?`,
      `Anda quase igual ao alvo (|ρ| = ${num(c.rho, 2)}). Se for medido durante o teste, carrega o próprio resultado e não existe em produção.`,
      'suspeita', c.coluna, null)));
    if (p.contadores.estado === 'nao_sei') {
      itens.push(pergunta('Os contadores do roteador são medidos durante o speedtest?',
        `<code>${p.contadores.colunas.map(esc).join('</code>, <code>')}</code>. Enquanto ninguém responder, resultados que usam esses contadores ficam provisórios.`,
        'contadores', '', 'nao_sei'));
    }
    const lista = itens.length ? `<div class="pend-grid">${itens.join('')}</div>`
      : gate('good', 'Nenhuma pendência', 'Todas as colunas estão classificadas e não há pergunta de vazamento em aberto.');
    const poucos = p.n_locais < p.minimo_confortavel
      ? gate('warning', `Só ${p.n_locais} locais de coleta`, 'Os números ainda mudam quando novos prédios entrarem.') : '';
    return `${alvo}${poucos}<div class="card"><h2>Pendências</h2>
      <p class="hint">Não bloqueiam os próximos passos. Colunas sem classificação ficam de fora; respostas "não sei" marcam o resultado como provisório.</p>
      ${lista}</div>`;
  }

  function responder(acao, alvo) {
    st.erro = null;
    const col = alvo.dataset.col;
    const c = st.inv && st.inv.colunas.find((x) => x.coluna === col);
    let pedido = null;
    if (acao === 'classificar') {
      const classe = alvo.closest('.pend-item').querySelector('select').value;
      pedido = post('api/columns', { coluna: col, classe, vazamento: false, parametro: null });
    }
    if (acao === 'suspeita') {
      if (alvo.dataset.resp !== 'sim') { st.dispensadas.add(col); desenhar(); return; }
      pedido = post('api/columns', { coluna: col, classe: c.classe, vazamento: true, parametro: c.parametro || null });
    }
    if (acao === 'contadores') pedido = post('api/contadores', { estado: alvo.dataset.resp });
    pedido.then(recarregarTudo).catch((e) => { st.erro = e.message; desenhar(); });
  }

  /* ---------------- passo 2 · Ajustar ---------------- */
  function statusSugestoes(sug, sugerida) {
    if (!st.sug || st.sug.status === 'rodando') {
      const u = st.sug && st.sug.progresso && st.sug.progresso[st.sug.progresso.length - 1];
      return `calculando sugestões…${u ? ` ${u.feito}/${u.total}` : ''}`;
    }
    if (st.sug.status === 'erro') return `sugestões indisponíveis: ${esc(st.sug.erro)}`;
    return `sugestões sobre ${esc(sug.base)} · ${sug.ganho.filter(sugerida).length} coluna(s) sugerida(s)`;
  }

  function passoAjustar() {
    if (!st.reg || !st.cols) return '<p class="hint">Carregando colunas…</p>';
    const porNome = Object.fromEntries(st.cols.map((c) => [c.coluna, c]));
    const pronta = st.sug && st.sug.status === 'pronto' && st.sugKey === chaveConj() + '|' + st.base;
    const sug = pronta ? st.sug.resultado : null;
    const ganho = sug ? Object.fromEntries(sug.ganho.map((g) => [g.coluna, g])) : {};
    const sugerida = (g) => !!g && !!sug && g.delta >= sug.ganho_min && g.melhora === g.locais;
    const f = st.filtro.trim().toLowerCase();
    const vis = (nome) => !f || nome.toLowerCase().includes(f);
    const noModelo = selLista().filter(vis);
    const pontos = (c) => (ganho[c.coluna] ? ganho[c.coluna].delta : -9);
    const disponiveis = st.cols.filter((c) => c.liberada && !st.sel.has(c.coluna) && vis(c.coluna))
      .sort((a, b) => (pontos(b) - pontos(a)) || ((b.rho || 0) - (a.rho || 0)));
    const linha = (nome) => {
      const c = porNome[nome];
      const marcado = st.sel.has(nome);
      const g = ganho[nome];
      const tags = !c ? '<span class="tag leak">ausente neste conjunto</span>' : [
        c.derivada ? '<span class="tag">derivada</span>' : '',
        c.hipotese ? '<span class="tag mid" title="não passou no teste de aceite">hipótese</span>' : '',
        c.pendente ? '<span class="tag mid" title="vazamento ainda não confirmado">não confirmado</span>' : '',
        c.motivo && !c.hipotese ? `<span class="tag leak">${esc(c.motivo)}</span>` : '',
        sugerida(g) ? `<span class="tag ok">sugerida ${sinal(g.delta, 2)}</span>` : ''].join(' ');
      const travada = !marcado && !(c && c.liberada);
      return `<label class="mrow${travada ? ' dim' : ''}" title="${c && c.descricao ? esc(c.descricao) : ''}">
        <input type="checkbox" data-col="${esc(nome)}"${marcado ? ' checked' : ''}${travada ? ' disabled' : ''}>
        <code>${esc(nome)}</code><span>${tags}</span>
        <span class="num">${c ? pct(c.cobertura) : '–'}</span>
        <span class="num">${g ? sinal(g.delta, 3) : '–'}</span></label>`;
    };
    const opcoes = st.reg.versoes.map((v) => `<option value="${esc(v.nome)}"${v.nome === st.base ? ' selected' : ''}>${esc(v.nome)}${v.ativo ? ' (ativa)' : ''}</option>`).join('');
    return `<div class="card"><h2>Ajustar o rascunho</h2>
      <p class="hint">Só colunas do roteador (TR-069), que existem em produção. Marque e desmarque à vontade. "Sugerida" é a coluna que mais melhorou o modelo quando somada à versão de partida, em todos os locais de coleta.</p>
      <div class="controls"><label for="aBase">Partir de</label><select id="aBase">${opcoes}</select>
        <label for="aFiltro">Filtrar</label><input id="aFiltro" class="minput" type="search" placeholder="nome da coluna" value="${esc(st.filtro)}">
        <span class="chip">${st.sel.size} features</span><span class="gate-msg">${statusSugestoes(sug, sugerida)}</span></div>
      <div class="mhead"><span></span><span>Coluna</span><span></span><span class="num">Cobertura</span><span class="num">Ganho</span></div>
      <h3 class="grupo">No modelo</h3>${noModelo.map(linha).join('') || '<p class="hint">Nada marcado.</p>'}
      <h3 class="grupo">Disponíveis</h3>${disponiveis.map((c) => linha(c.coluna)).join('') || '<p class="hint">Nada com esse filtro.</p>'}
      ${painelReceita()}</div>`;
  }

  function painelReceita() {
    if (!st.recAberto) return '<div style="margin-top:14px"><button class="btn" data-aacao="abrir-receita">+ Criar métrica</button></div>';
    const r = st.rec;
    const def = (st.receitas || []).find((x) => x.id === r.id);
    const brutas = (st.cols || []).filter((c) => !c.derivada && c.classe === 'tr069' && c.tipo === 'numerica' && !c.vazamento)
      .map((c) => c.coluna);
    const letras = ['A', 'B', 'C'].slice(0, def ? def.colunas : 2);
    const seletores = letras.map((l, i) => `<label for="aCol${i}">${l}</label><select id="aCol${i}" data-rcol="${i}">
      <option value="">— escolha —</option>${brutas.map((b) => `<option${b === r.colunas[i] ? ' selected' : ''}>${esc(b)}</option>`).join('')}</select>`).join('');
    const montada = r.montada ? `<label>Fórmula</label><code>${esc(r.montada.formula)}</code>
      <label for="aRecNome">Nome</label><input id="aRecNome" class="minput" maxlength="40" value="${esc(r.nome)}">` : '';
    return `<div class="receita"><h2 style="font-size:13px">Criar métrica a partir de receita</h2>
      <div class="pform">
        <label for="aReceita">Receita</label><select id="aReceita">${(st.receitas || []).map((x) => `<option value="${x.id}"${x.id === r.id ? ' selected' : ''}>${esc(x.rotulo)}</option>`).join('')}</select>
        ${seletores}${montada}
      </div>
      ${def && def.dica ? `<p class="gate-msg" style="margin-top:6px">${esc(def.dica)}</p>` : ''}
      <div class="controls" style="margin-top:10px">
        <button class="btn-pri" data-aacao="salvar-receita"${!r.montada || r.ocupado ? ' disabled' : ''}>${r.ocupado ? 'Testando…' : 'Testar e salvar'}</button>
        <button class="btn" data-aacao="fechar-receita">Fechar</button>
        ${r.ocupado ? '<span class="gate-msg">o teste de aceite leva cerca de 1 minuto</span>' : ''}
      </div>
      ${r.erro ? gate('critical', 'Não deu', esc(r.erro)) : ''}
      ${r.resultado ? resultadoReceita(r.resultado) : ''}</div>`;
  }

  function resultadoReceita(res) {
    const ok = res.status === 'aprovada';
    const falhas = res.teste.criterios.filter((c) => !c.ok).map((c) => `<li>${esc(c.criterio)}</li>`).join('');
    const titulo = ok ? `Aprovada: melhora o ${ALVO[st.alvo].rotulo.toLowerCase()} em todos os locais`
      : 'Hipótese: não passou em todos os critérios';
    return gate(ok ? 'good' : 'warning', titulo,
      (ok ? '' : 'Fica salva e entra no rascunho, mas não é sugerida. ') + 'A métrica já está marcada no rascunho.' +
      (falhas ? `<ul>${falhas}</ul>` : ''));
  }

  function montarReceita() {
    const r = st.rec;
    const def = st.receitas.find((x) => x.id === r.id);
    r.montada = null; r.erro = null;
    const colunas = r.colunas.slice(0, def.colunas);
    if (colunas.length < def.colunas || colunas.some((c) => !c)) { r.montarKey = null; desenhar(); return; }
    const k = colunas.join('|');
    r.montarKey = k;
    post('api/receitas/montar', { receita: r.id, colunas })
      .then((m) => { if (r.montarKey === k) { r.montada = m; r.nome = m.nome; } })
      .catch((e) => { if (r.montarKey === k) r.erro = e.message; })
      .finally(() => { if (r.montarKey === k) desenhar(); });
  }

  function salvarReceita() {
    const r = st.rec;
    r.ocupado = true; r.erro = null; r.resultado = null; desenhar();
    post('api/derivadas', { nome: r.nome, formula: r.montada.formula, descricao: r.montada.descricao,
                            base: st.base, ds: st.ctx.enabledIds.join(','), alvo: st.alvo, ambiente: st.ctx.ambiente })
      .then((res) => {
        r.resultado = res; st.sel.add(r.nome);
        r.montada = null; r.colunas = []; r.nome = '';
        recarregarTudo();
      })
      .catch((e) => { r.erro = e.message; })
      .finally(() => { r.ocupado = false; desenhar(); });
  }

  /* ---------------- passo 3 · Testar ---------------- */
  function urlAvaliar(alvo) {
    return 'api/modelos/avaliar?' + queryDe(alvo) + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&base=' + encodeURIComponent(st.reg.ativo);
  }

  function testar() {
    const k = chaveVeredito();
    st.avalPedido = k;
    st.avaliando = true; st.avalErro = null; desenhar();
    pedir(urlAvaliar(st.alvo))
      .then((a) => { if (st.avalPedido === k) { st.aval = a; st.avalKey = k; } })
      .catch((e) => { if (st.avalPedido === k) st.avalErro = e.message; })
      .finally(() => { if (st.avalPedido === k) { st.avaliando = false; desenhar(); } });
  }

  function testarOutros() {
    const k = chaveVeredito();
    st.outrosPedido = k;
    st.outrosCarregando = true; desenhar();
    Promise.all(ALVOS.filter(([a]) => a !== st.alvo).map(([a]) => pedir(urlAvaliar(a))
      .then((r) => ({ alvo: a, resultado: r.veredito.resultado }))
      .catch(() => ({ alvo: a, erro: true }))))
      .then((xs) => { if (st.outrosPedido === k) { st.outros = xs; st.outrosKey = k; } })
      .finally(() => { if (st.outrosPedido === k) { st.outrosCarregando = false; desenhar(); } });
  }

  function outrosAlvos() {
    if (!st.outros || st.outrosKey !== chaveVeredito()) {
      return `<button class="btn" data-aacao="outros"${st.outrosCarregando ? ' disabled' : ''}>${st.outrosCarregando ? 'Calculando…' : 'Ver nos outros alvos'}</button>`;
    }
    return `<p class="gate-msg">Outros alvos, só informativo: ${st.outros.map((o) =>
      `${ALVO[o.alvo].rotulo}: ${o.erro ? 'erro' : VEREDITO[o.resultado][0]}`).join(' · ')}</p>`;
  }

  function cartaoVeredito(a, atual) {
    const v = a.veredito, d = a.delta, u = ALVO[a.alvo].unidade;
    const [rotulo, icone] = VEREDITO[v.resultado];
    const linhas = Object.keys(a.resumo.por_local).map((s) => `<tr><td>${esc(s)}</td>
      <td class="num">${num(a.resumo_base.por_local[s], 3)}</td><td class="num">${num(a.resumo.por_local[s], 3)}</td>
      <td class="num">${sinal(d.por_local[s])}</td>
      <td class="num">${num(a.resumo_base.mae_por_local[s], 1)}</td><td class="num">${num(a.resumo.mae_por_local[s], 1)}</td></tr>`).join('');
    const faixa = (iv, casas) => (iv ? `<em>90%: ${num(iv[0], casas)} a ${num(iv[1], casas)}</em>` : '');
    const p = a.promocao;
    const detalhePromocao = !p ? ''
      : p.delta_pinball
        ? `Δ pinball p90 ${num(p.delta_pinball.valor, 2)} ${u} ${faixa(p.delta_pinball.intervalo, 2)} · cobertura p90 ${num(p.cobertura, 2)}`
        : `Δ MAE ${num(p.delta_mae.valor, 1)} ${u} ${faixa(p.delta_mae.intervalo, 1)}${p.delta_atende
          ? ` · Δ atende ${num(p.delta_atende.valor, 3)} ${faixa(p.delta_atende.intervalo, 3)}` : ''}`;
    const promocao = p ? `<div class="veredito ${p.veredito.resultado}" style="margin-top:10px">
        <svg class="icon"><use href="#${VEREDITO[p.veredito.resultado][1]}"/></svg>
        <div><b>Régua de promoção: ${VEREDITO[p.veredito.resultado][0]}</b>
          <div class="gate-msg">${esc(p.veredito.motivo)}</div>
          <div class="gate-msg">${detalhePromocao}</div></div></div>` : '';
    return `<div class="${atual ? '' : 'stale'}">
      <div class="veredito ${v.resultado}"><svg class="icon"><use href="#${icone}"/></svg>
        <div><b>${rotulo}</b>${v.provisorio ? ` <span class="tag mid" title="${esc(v.motivos_provisorio.join('; '))}">provisório</span>` : ''}
          ${atual ? '' : ' <span class="tag lab">desatualizado: o rascunho, os dados ou o alvo mudaram</span>'}
          <div class="gate-msg">${esc(v.motivo)}</div></div></div>
      <div class="kpis">
        <div><span>R² pooled</span><b>${num(a.resumo_base.pooled, 3)} → ${num(a.resumo.pooled, 3)}</b>${faixa((a.resumo.intervalos || {}).pooled, 3)}</div>
        <div><span>MAE (${u})</span><b>${num(a.resumo_base.mae, 1)} → ${num(a.resumo.mae, 1)}</b></div>
        <div><span>Melhora em</span><b>${d.melhora} de ${d.locais}</b><em>locais</em></div>
      </div>
      ${promocao}
      <details class="fold"><summary>Ver detalhes por local</summary><div class="inner" style="overflow-x:auto"><table>
        <thead><tr><th>Local de coleta</th><th class="num">R² ativa</th><th class="num">R² rascunho</th><th class="num">Δ R²</th>
        <th class="num">MAE ativa</th><th class="num">MAE rascunho</th></tr></thead><tbody>${linhas}</tbody></table></div></details>
      <div style="margin-top:10px">${outrosAlvos()}</div></div>`;
  }

  function passoTestar() {
    if (!st.reg) return '<p class="hint">Carregando versões…</p>';
    const vazio = !st.sel.size, igual = igualAtiva();
    const motivo = vazio ? 'O rascunho está vazio.' : igual ? `O rascunho é igual à versão ativa (${esc(st.reg.ativo)}).` : '';
    let corpo = '';
    if (st.avalErro) corpo = gate('critical', 'Não foi possível testar', esc(st.avalErro));
    else if (st.aval) corpo = cartaoVeredito(st.aval, st.avalKey === chaveVeredito());
    return `<div class="card"><div class="card-head"><div><h2>Testar contra a versão ativa</h2>
      <p class="hint">Rascunho com ${st.sel.size} features contra <code>${esc(st.reg.ativo)}</code>, prevendo ${ALVO[st.alvo].rotulo.toLowerCase()}. Cada local de coleta fica de fora uma vez. Leva cerca de 20 s.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-aacao="testar"${vazio || igual || st.avaliando ? ' disabled' : ''}>${st.avaliando ? 'Testando…' : 'Testar'}</button>
      <div class="status">${motivo}</div></div></div>${corpo}</div>`;
  }

  function sugerirNome(ativo, nomes) {
    const m = ativo.match(/^(\D*)(\d+)(.*)$/);
    const gerar = m ? (i) => m[1] + i + m[3] : (i) => `${ativo}-${i}`;
    let i = m ? Number(m[2]) + 1 : 2;
    while (nomes.includes(gerar(i))) i += 1;
    return gerar(i);
  }

  function descricaoSugerida() {
    const a = ativa();
    const antes = new Set(a ? a.features : []);
    const mais = selLista().filter((f) => !antes.has(f)).map((f) => '+' + f);
    const menos = [...antes].filter((f) => !st.sel.has(f)).sort().map((f) => '−' + f);
    let txt = mais.concat(menos).join(' ') || 'sem mudança de features';
    if (st.aval && st.avalKey === chaveVeredito()) {
      txt += ` · ${ALVO[st.alvo].rotulo.toLowerCase()}: ${VEREDITO[st.aval.veredito.resultado][0].toLowerCase()}` +
        ` (R² ${num(st.aval.resumo_base.pooled, 2)}→${num(st.aval.resumo.pooled, 2)})`;
    }
    return txt.slice(0, 500);
  }

  function publicar(ativar) {
    st.pubErro = null; st.pubMsg = null;
    if (!NOME_OK.test(st.nome)) { st.pubErro = 'Nome inválido: use minúsculas, dígitos e hífen (2 a 40 caracteres).'; desenhar(); return; }
    if (!st.desc.trim()) { st.pubErro = 'Escreva uma descrição: ela é o que explica a versão no git log.'; desenhar(); return; }
    const nome = st.nome;
    st.publicando = true; desenhar();
    post('api/modelos', { nome, descricao: st.desc, features: selLista(), ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente })
      .then((reg) => {
        st.reg = reg; st.base = nome; st.nome = ''; st.nomeTocada = false; st.descTocada = false;
        st.invKey = null; st.sugKey = null;
        if (!ativar) {
          st.pubMsg = `Versão ${nome} salva em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
          if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
          return;
        }
        return post('api/modelos/ativo', { nome })
          .then((reg2) => {
            st.reg = reg2;
            st.pubMsg = `Versão ${nome} salva e ativa em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
            if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
          })
          .catch((e) => {
            st.pubErro = `Versão ${nome} salva, mas não foi possível ativar: ${e.message}`;
            if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
          });
      })
      .catch((e) => { st.pubErro = e.message; })
      .finally(() => { st.publicando = false; desenhar(); });
  }

  function passoPublicar() {
    if (!st.reg) return '<p class="hint">Carregando versões…</p>';
    if (!st.nomeTocada) st.nome = sugerirNome(st.reg.ativo, st.reg.versoes.map((v) => v.nome));
    if (!st.descTocada) st.desc = descricaoSugerida();
    const atual = st.aval && st.avalKey === chaveVeredito();
    const melhor = atual && st.aval.veredito.resultado === 'melhor';
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? '' : 'Para ativar uma versão que não é melhor que a ativa, use o modo Avançado.';
    return `<div class="card"><h2>Publicar</h2>
      <p class="hint">A versão salva é imutável e vai para <code>src/ml/core/modelos.json</code>. Complete a descrição com o porquê da mudança.</p>
      <div class="pform"><label for="aNome">Nome</label><input id="aNome" class="minput" maxlength="40" value="${esc(st.nome)}">
        <label for="aDesc">Descrição</label><input id="aDesc" class="minput" maxlength="500" value="${esc(st.desc)}"></div>
      <div class="controls" style="margin-top:12px">
        <button class="btn" data-aacao="salvar"${st.publicando || !st.sel.size ? ' disabled' : ''}>Salvar versão</button>
        <button class="btn-pri" data-aacao="salvar-ativar"${st.publicando || !melhor ? ' disabled' : ''}>Salvar e tornar ativa</button>
        ${trava ? `<span class="gate-msg">${trava}</span>` : ''}</div>
      ${st.pubErro ? gate('critical', 'Não foi possível salvar', esc(st.pubErro)) : ''}
      ${st.pubMsg ? gate('good', 'Feito', esc(st.pubMsg)) : ''}</div>`;
  }

  /* ---------------- moldura ---------------- */
  function cabecalho() {
    return `<div class="passos">${PASSOS.map((p, i) => `<button class="passo" data-aacao="passo" data-n="${i + 1}"${st.passo === i + 1 ? ' aria-current="step"' : ''}><span>${i + 1}</span> ${p}</button>`).join('')}
      <a class="gate-msg" href="#modelos" style="margin-left:auto">Abrir no modo avançado</a></div>`;
  }

  function rodape() {
    const ant = st.passo > 1 ? `<button class="btn" data-aacao="passo" data-n="${st.passo - 1}">Voltar</button>` : '<span></span>';
    const prox = st.passo < PASSOS.length
      ? `<button class="btn-pri" data-aacao="passo" data-n="${st.passo + 1}"${st.passo === 2 && !st.sel.size ? ' disabled' : ''}>Próximo: ${PASSOS[st.passo]}</button>` : '';
    return `<div class="rodape-passo">${ant}${prox}</div>`;
  }

  function desenhar() {
    const host = $('#aBody');
    if (!st.ctx) return;
    if (!st.ctx.enabledIds.length) { host.innerHTML = '<p class="hint">Nenhum dataset ativo. Ligue um na view Datasets.</p>'; return; }
    const el = document.activeElement;
    const foco = el && host.contains(el) ? el.id : null;
    const cursor = foco && typeof el.selectionStart === 'number' ? el.selectionStart : null;
    const abertos = [...host.querySelectorAll('details.fold')].map((d) => d.open);
    const corpo = [passoPreparar, passoAjustar, passoTestar, passoPublicar][st.passo - 1]();
    host.innerHTML = cabecalho() + (st.erro ? gate('critical', 'Algo deu errado', esc(st.erro)) : '') + corpo + rodape();
    host.querySelectorAll('details.fold').forEach((d, i) => { if (i < abertos.length) d.open = abertos[i]; });
    if (foco && $('#' + foco)) {
      const novo = $('#' + foco);
      novo.focus();
      if (cursor != null) try { novo.setSelectionRange(cursor, cursor); } catch (e) { /* select não tem cursor */ }
    }
  }

  function irPara(n) {
    st.passo = n;
    if (n === 2) iniciarSugestoes();
    desenhar();
    window.scrollTo(0, 0);
  }

  /* ---------------- eventos ---------------- */
  $('#aBody').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-aacao]');
    if (!alvo || alvo.disabled) return;
    const acao = alvo.dataset.aacao;
    if (acao === 'passo') irPara(Number(alvo.dataset.n));
    if (acao === 'classificar' || acao === 'suspeita' || acao === 'contadores') responder(acao, alvo);
    if (acao === 'abrir-receita') { st.recAberto = true; desenhar(); }
    if (acao === 'fechar-receita') { st.recAberto = false; st.rec.resultado = null; st.rec.erro = null; desenhar(); }
    if (acao === 'salvar-receita') salvarReceita();
    if (acao === 'testar') testar();
    if (acao === 'outros') testarOutros();
    if (acao === 'salvar') publicar(false);
    if (acao === 'salvar-ativar') publicar(true);
  });
  $('#aBody').addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.id === 'aAlvo') { st.alvo = t.value; carregar(); desenhar(); return; }
    if (t.id === 'aBase') { usarBase(t.value); iniciarSugestoes(); desenhar(); return; }
    if (t.id === 'aReceita') { st.rec.id = t.value; st.rec.colunas = []; montarReceita(); return; }
    if (t.dataset.rcol != null) { st.rec.colunas[Number(t.dataset.rcol)] = t.value; montarReceita(); return; }
    if (t.dataset.col && t.type === 'checkbox') {
      if (t.checked) st.sel.add(t.dataset.col); else st.sel.delete(t.dataset.col);
      desenhar();
    }
  });
  $('#aBody').addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.id === 'aFiltro') { st.filtro = t.value; desenhar(); }
    if (t.id === 'aRecNome') st.rec.nome = t.value;
    if (t.id === 'aNome') { st.nome = t.value; st.nomeTocada = true; }
    if (t.id === 'aDesc') { st.desc = t.value; st.descTocada = true; }
  });

  V.views.assistente = {
    render(ctx) {
      st.ctx = ctx;
      carregar();
      desenhar();
    },
  };
})();
