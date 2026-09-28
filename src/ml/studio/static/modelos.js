/* modelos.js — view Modelos: versões salvas, comparação, editor e correlações.
   Estado próprio; studio.js chama render(ctx) quando a view está visível. */
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
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const UNIDADE = { speedtest_down_mbps: 'Mbps', speedtest_up_mbps: 'Mbps', latency_ms: 'ms', jitter_ms: 'ms' };
  const ROTULO = { tr069: 'TR-069', sniffer: 'Sniffer', cliente: 'Cliente', ambiente: 'Ambiente',
    geometria: 'Manual', auxiliar: 'Auxiliar' };
  const FORA_DO_EDITOR = new Set(['identificador', 'alvo']);
  const COBERTURA_MIN = 0.7;
  const NOME_OK = /^[a-z0-9][a-z0-9-]{1,39}$/;

  const st = { ctx: null, alvo: 'speedtest_down_mbps', metrica: 'r2',
               reg: null, regErro: null, inv: null, invKey: null, invErro: null,
               cmp: null, cmpKey: null, cmpErro: null, comparando: false,
               base: null, sel: new Set(), filtro: '',
               aval: null, avalKey: null, avalErro: null, avaliando: false,
               salvarErro: null, salvando: false, msg: null, hits: null,
               des: null, desId: null, desKey: null, desErro: null, desTimer: null, semVolume: true, semVolumeTocado: false,
               pend: null, pendKey: null, pendErro: null };

  const dsIds = () => st.ctx.enabledIds.slice().sort();
  const chaveConj = () => dsIds().join(',') + '|' + st.alvo + '|' + st.ctx.ambiente;
  const query = () => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(st.alvo) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);
  const selLista = () => [...st.sel];
  const chaveAval = () => chaveConj() + '|' + selLista().join(',') + '|' + st.base;

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }

  function carregarPendencias() {
    const k = chaveConj();
    if (st.pendKey === k) return;
    st.pendKey = k;
    pedir('api/pendencias?' + query())
      .then((p) => { if (st.pendKey === k) { st.pend = p; st.pendErro = null; } })
      .catch((e) => { st.pendErro = e.message; })
      .finally(desenhar);
  }

  function definirContadores(estado) {
    st.salvarErro = null; st.msg = null;
    pedir('api/contadores', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ estado }) })
      .then(() => {
        st.pendKey = null; st.invKey = null; st.cmpKey = null; st.aval = null;
        st.msg = `Contadores do roteador marcados como "${ESTADO_TXT[estado]}" em src/ml/core/column_provenance.json. Revise no git diff antes do commit.`;
        carregarPendencias(); carregarInventario(); carregarRegistro();
        if (V.views.paralelos && V.views.paralelos.recarregar) V.views.paralelos.recarregar();
      })
      .catch((e) => { st.salvarErro = e.message; desenhar(); });
  }

  function carregarRegistro() {
    return pedir('api/modelos').then((reg) => {
      st.reg = reg; st.regErro = reg.erro;
      if (!st.semVolumeTocado) st.semVolume = reg.contadores !== 'nao';
      if (!st.base || !reg.versoes.some((v) => v.nome === st.base)) usarBase(reg.ativo);
    }).catch((e) => { st.regErro = e.message; }).finally(desenhar);
  }

  function carregarInventario() {
    const k = chaveConj();
    if (st.invKey === k) return;
    st.invKey = k; st.inv = null; st.invErro = null;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.invKey === k) st.inv = inv; })
      .catch((e) => { if (st.invKey === k) st.invErro = e.message; })
      .finally(() => { if (st.invKey === k) desenhar(); });
  }

  function comparar() {
    if (st.comparando) return;
    const k = chaveConj();
    st.comparando = true; st.cmpErro = null; desenhar();
    pedir('api/modelos/comparar?' + query())
      .then((c) => { st.cmp = c; st.cmpKey = k; })
      .catch((e) => { st.cmpErro = e.message; })
      .finally(() => { st.comparando = false; desenhar(); });
  }

  function avaliar() {
    if (st.avaliando || !st.sel.size) return;
    const k = chaveAval();
    st.avaliando = true; st.avalErro = null; desenhar();
    pedir('api/modelos/avaliar?' + query() + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&base=' + encodeURIComponent(st.base || ''))
      .then((a) => { st.aval = a; st.avalKey = k; })
      .catch((e) => { st.avalErro = e.message; })
      .finally(() => { st.avaliando = false; desenhar(); });
  }

  function desenharModelo() {
    if (st.des && st.des.status === 'rodando') return;
    const k = chaveConj() + '|' + st.semVolume;
    st.desErro = null; st.des = { status: 'rodando', progresso: [] }; st.desKey = k; desenhar();
    pedir('api/modelos/desenhar?' + query() + '&sem_volume=' + st.semVolume, { method: 'POST' })
      .then((r) => { st.desId = r.id; acompanhar(); })
      .catch((e) => { st.desErro = e.message; st.des = null; desenhar(); });
  }

  function acompanhar() {
    clearTimeout(st.desTimer);
    pedir('api/modelos/desenhar/' + st.desId)
      .then((job) => {
        st.des = job;
        if (job.status === 'rodando') st.desTimer = setTimeout(acompanhar, 1500);
      })
      .catch((e) => { st.desErro = e.message; })
      .finally(desenhar);
  }

  function carregarDesenho() {
    const r = st.des.resultado;
    st.base = st.reg.ativo;
    st.sel = new Set(r.features);
    st.aval = null; st.filtro = '';
    desenhar();
    $('#mBase').scrollIntoView({ block: 'center' });
  }

  // O vínculo com o desenho só vale se o rascunho for exatamente o conjunto escolhido.
  const desenhoVinculado = () => (st.des && st.des.status === 'pronto' && st.desKey === chaveConj() + '|' + st.semVolume
    && JSON.stringify(st.des.resultado.features) === JSON.stringify(selLista()) ? st.desId : null);

  function salvar(nome, descricao) {
    st.salvarErro = null; st.msg = null;
    if (!NOME_OK.test(nome)) { st.salvarErro = 'Nome inválido: use minúsculas, dígitos e hífen (2 a 40 caracteres).'; desenhar(); return; }
    if (!descricao.trim()) { st.salvarErro = 'Escreva uma descrição: ela é o que explica a versão no git log.'; desenhar(); return; }
    st.salvando = true; desenhar();
    pedir('api/modelos', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, descricao, features: selLista(), desenho: desenhoVinculado(),
                             ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente }) })
      .then((reg) => {
        st.reg = reg; st.cmpKey = null; st.base = nome;
        st.msg = `Versão ${nome} salva em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
      })
      .catch((e) => { st.salvarErro = e.message; })
      .finally(() => { st.salvando = false; desenhar(); });
  }

  function tornarAtivo(nome) {
    st.salvarErro = null; st.msg = null;
    pedir('api/modelos/ativo', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome }) })
      .then((reg) => { st.reg = reg; st.cmpKey = null; st.invKey = null; st.msg = `${nome} agora é a versão ativa.`; carregarInventario(); })
      .catch((e) => { st.salvarErro = e.message; })
      .finally(desenhar);
  }

  function usarBase(nome) {
    st.base = nome;
    const v = st.reg && st.reg.versoes.find((x) => x.nome === nome);
    st.sel = new Set(v ? v.features : []);
  }

  /* ---------------- blocos ---------------- */
  const gate = (sev, titulo, msg) => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div></div></div>`;

  function motivoDesatualizada(av) {
    if (!av) return 'sem avaliação salva para este alvo';
    const motivos = [];
    if (JSON.stringify((av.datasets || []).slice().sort()) !== JSON.stringify(dsIds())) motivos.push('datasets diferentes');
    if ((av.ambiente || 'todos') !== st.ctx.ambiente) motivos.push('ambiente diferente');
    if (av.versao_tabela !== st.reg.versao_tabela) motivos.push('classificação de colunas mudou');
    if (av.versao_catalogo !== st.reg.versao_catalogo) motivos.push('catálogo de derivadas mudou');
    return motivos.join(', ');
  }

  const tagsFora = (v) => (v.fora_do_tr069.length
    ? v.fora_do_tr069.map((f) => `<span class="tag mid" title="não existe em produção via TR-069">${esc(f)}</span>`).join(' ')
    : '<span class="tag ok">pronta para produção</span>') +
    ((v.vazadas || []).length ? ` <span class="tag leak" title="${esc(v.vazadas.join(', '))}">usa ${v.vazadas.length} coluna(s) com vazamento: avaliada sem elas</span>` : '') +
    ((v.pendentes || []).length ? ` <span class="tag mid" title="${esc(v.pendentes.join(', '))}">depende de confirmação (${v.pendentes.length})</span>` : '');

  const ESTADO_TXT = { nao_sei: 'não sei', sim: 'sim, medidos na janela do teste', nao: 'não, acumulados fora da janela' };

  function cardPendencias() {
    if (st.pendErro) return gate('warning', 'Limites dos dados indisponíveis', esc(st.pendErro));
    const p = st.pend;
    if (!p) return '';
    const u = p.ambientes;
    const dom = (u.domestico || []).length;
    const corp = (u.corporativo || []).length;
    const poucos = p.n_locais < p.minimo_confortavel;
    const estado = p.contadores.estado;
    // Pela classificação herdada: pega também quem usa derivadas deles (ex.: fracao_airtime_tx).
    const afetadas = st.reg ? st.reg.versoes.filter((v) => (v.pendentes || []).length || (v.vazadas || []).length).map((v) => v.nome) : [];
    const opcao = (valor, titulo, efeito) => `<label class="opcao${estado === valor ? ' marcada' : ''}">
      <input type="radio" name="mContadores" value="${valor}"${estado === valor ? ' checked' : ''}>
      <span><b>${titulo}</b><span class="gate-msg">${efeito}</span></span></label>`;
    return `<div class="card pend"><h2>Limites e pendências dos dados</h2>
      <p class="hint">A coleta está em andamento. Tudo nesta página depende do que está abaixo; refaça a comparação e o desenho quando novos locais entrarem.</p>
      <div class="pend-grid">
        <div class="pend-item ${poucos ? 'warning' : 'good'}">
          <div class="pend-num">${p.n_locais}<span> / ${p.minimo_confortavel}+</span></div>
          <div><b>Locais de coleta</b> · ${dom} doméstico${dom === 1 ? '' : 's'}, ${corp} corporativo${corp === 1 ? '' : 's'}
            <div class="gate-msg">${p.locais.map(esc).join(', ') || '—'}</div>
            <div class="gate-msg">${poucos
              ? `Com menos de ${p.minimo_confortavel} locais, a leitura por local não é interpretável, a seleção automática muda de um fold para outro e quase nenhuma derivada consegue "melhorar em todos os locais".`
              : 'Quantidade suficiente para ler a dispersão por local.'}
              ${dom === 1 ? ' Só 1 local doméstico: nenhum resultado aqui vale para residências em geral.' : ''}
              ${dom === 0 && corp ? ' Nenhum local doméstico no conjunto ativo.' : ''}</div></div>
        </div>
        <div class="pend-item ${estado === 'nao_sei' ? 'warning' : estado === 'sim' ? 'critical' : 'good'}">
          <div><b>Contadores do roteador: medidos na janela do teste?</b>
            <div class="gate-msg"><code>${p.contadores.colunas.map(esc).join('</code>, <code>')}</code>. Se forem medidos durante o speedtest, carregam o próprio alvo, como <code>router_tx_bytes</code>.
              ${afetadas.length ? `Versões que usam algum deles, direto ou por derivada: <b>${afetadas.map(esc).join(', ')}</b>.` : ''}</div>
            <div class="opcoes" role="radiogroup" aria-label="Contadores medidos na janela do teste?">
              ${opcao('nao_sei', 'Não sei', 'Continuam nos ajustes, marcados como "não confirmado"; o desenho automático começa sem eles.')}
              ${opcao('sim', 'Sim', 'Viram vazamento: saem dos ajustes, e versões que os usam são avaliadas sem eles.')}
              ${opcao('nao', 'Não', 'Liberados como qualquer coluna TR-069.')}
            </div></div>
        </div>
        ${p.zeros_ambiguos.length ? `<div class="pend-item warning"><div><b>Datasets do coletor antigo</b>
          <div class="gate-msg">Antes da correção, <code>router_opportunity_medium_use</code> gravava 0 também quando o scan de vizinhos faltava.
            Nestes datasets um 0 pode ser "canal limpo" ou "sem medição": ${p.zeros_ambiguos.map((z) => `<code>${esc(z.dataset)}</code> (${Math.round(z.zeros * 100)}% de zeros)`).join(', ')}.
            Coletas novas gravam vazio quando não há scan.</div></div></div>` : ''}
      </div></div>`;
  }

  function cardVersoes() {
    const u = UNIDADE[st.alvo];
    const linhas = st.reg.versoes.map((v) => {
      const av = (v.avaliacao || {})[st.alvo];
      const motivo = motivoDesatualizada(av);
      // Versão desenhada com estes dados: a avaliação comum viu o teste na escolha.
      // No alvo otimizado mostramos a nota aninhada; nos outros, marcamos como otimista.
      const sel = v.selecao;
      // Nota guardada com uma coluna que hoje é vazamento não vale mais: não mostramos número.
      const invalida = (v.vazadas || []).length > 0;
      const aninhada = sel && sel.alvo === st.alvo && !invalida ? sel.nota_aninhada : null;
      const nota = invalida ? null : aninhada || av;
      const marca = invalida ? ' <span class="tag leak" title="a nota guardada usou coluna hoje marcada como vazamento; veja a comparação ou refaça o desenho">refazer</span>'
        : aninhada ? ' <span class="tag current" title="seleção refeita sem o local de teste: estimativa honesta">aninhada</span>'
        : sel ? ' <span class="tag mid" title="as features foram escolhidas olhando estes mesmos locais (para ' + esc(sel.alvo) + ')">otimista</span>' : '';
      return `<tr>
        <td><code>${esc(v.nome)}</code>${v.ativo ? ' <span class="tag current">ativo</span>' : ''}
          <div class="gate-msg">${esc(v.descricao)}</div></td>
        <td class="num">${v.features.length}</td>
        <td>${tagsFora(v)}</td>
        <td class="num">${nota ? num(nota.pooled, 3) : '–'}${marca}</td>
        <td class="num">${nota ? num(nota.mae, 1) + ' ' + u : '–'}</td>
        <td>${motivo ? `<span class="tag lab" title="${esc(motivo)}">desatualizada</span>` : `<span class="gate-msg">${esc(v.criado_em || '')}</span>`}</td>
        <td style="white-space:nowrap"><button class="btn" data-acao="base" data-nome="${esc(v.nome)}">Editar a partir desta</button>
          ${v.ativo ? '' : `<button class="btn" data-acao="ativar" data-nome="${esc(v.nome)}">Tornar ativa</button>`}</td></tr>`;
    }).join('');
    return `<div class="card"><h2>Versões salvas</h2>
      <p class="hint">Cada versão é uma lista de features, imutável depois de salva, em <code>src/ml/core/modelos.json</code>.
        Os números são a avaliação guardada quando a versão foi salva; "desatualizada" diz o que mudou desde então. A versão ativa é a base do "ganho" em Features.</p>
      <div style="overflow-x:auto"><table><thead><tr><th>Versão</th><th class="num">Features</th><th>Fora do TR-069</th>
        <th class="num">R² pooled</th><th class="num">MAE</th><th>Avaliação</th><th></th></tr></thead>
      <tbody>${linhas}</tbody></table></div></div>`;
  }

  function cardComparacao() {
    const atual = st.cmp && st.cmpKey === chaveConj();
    let status = '';
    if (st.comparando) status = 'calculando…';
    else if (st.cmpErro) status = `<span style="color:var(--critical)">${esc(st.cmpErro)}</span>`;
    else if (atual) status = `${num(st.cmp.segundos, 0)} s`;
    else if (st.cmp) status = 'desatualizada: o conjunto, o alvo ou as versões mudaram';
    let corpo = '<p class="hint">Clique em <b>Comparar</b> para avaliar todas as versões no conjunto ativo. Leva cerca de 20 s.</p>';
    if (st.cmp) {
      const locais = st.cmp.locais;
      const u = UNIDADE[st.cmp.alvo];
      corpo = `<div class="${atual ? '' : 'stale'}">
        <div class="controls" style="margin-bottom:8px">
          <button class="toggle" data-acao="metrica" data-m="r2" aria-pressed="${st.metrica === 'r2'}"><span class="dot"></span> R² por local</button>
          <button class="toggle" data-acao="metrica" data-m="mae" aria-pressed="${st.metrica === 'mae'}"><span class="dot"></span> MAE por local (${u})</button>
        </div>
        <div class="chartwrap"><canvas id="mCmp"></canvas><div class="tooltip" id="mCmpTip"></div></div>
        <div class="serieskey">${locais.map((p, i) => `<span><i style="background:var(--s${i % 5 + 1})"></i>${esc(p)}</span>`).join('')}</div>
        <p class="hint" style="margin-top:10px">${st.metrica === 'r2'
          ? 'A barra vertical é a média dos R² por local. Um local com pouca variância no alvo puxa o R² dele muito para baixo; o MAE não tem esse problema.'
          : 'MAE em ' + u + ': menor é melhor. A barra vertical é o MAE de todas as previsões fora do fold juntas.'}
          ${st.reg.versoes.some((v) => v.selecao) ? ' Versões desenhadas automaticamente aparecem <b>otimistas</b> aqui, porque escolheram as features olhando estes locais; a estimativa honesta é a nota aninhada, na linha de baixo do nome.' : ''}</p>
        ${st.cmp.avisos.map((a) => `<p class="gate-msg">${esc(a)}</p>`).join('')}</div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Comparação no conjunto ativo</h2>
      <p class="hint">Todas as versões, mais duas referências: <b>TR-069 completo</b> (todas as colunas TR-069 elegíveis) e <b>Tudo</b> (inclui sniffer e cliente, só laboratório). Folds por local de coleta.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-acao="comparar"${st.comparando ? ' disabled' : ''}>Comparar</button>
      <div class="status">${status}</div></div></div>${corpo}</div>`;
  }

  function desenharComparacao() {
    const canvas = $('#mCmp');
    if (!canvas || !st.cmp) return;
    const c = st.cmp;
    const r2 = st.metrica === 'r2';
    const linha = (rotulo, sub, res) => ({
      label: rotulo, sub,
      mean: r2 ? res.media : res.mae,
      points: c.locais.map((p, i) => ({ key: p, v: (r2 ? res.por_local : res.mae_por_local || {})[p], color: cssv('--s' + (i % 5 + 1)) }))
        .filter((p) => p.v != null),
    });
    const sub = (res) => `${res.n} feat. · pooled ${num(res.pooled, 2)} · MAE ${num(res.mae, 1)}` +
      ((res.removidas_por_vazamento || []).length ? ` · sem ${res.removidas_por_vazamento.length} com vazamento` : '');
    const selecao = Object.fromEntries(st.reg.versoes.filter((v) => v.selecao).map((v) => [v.nome, v.selecao]));
    const subVersao = (v) => {
      const sel = selecao[v.nome];
      if (!sel || (v.removidas_por_vazamento || []).length) return sub(v);
      return sel.alvo === c.alvo
        ? `otimista · aninhada: pooled ${num(sel.nota_aninhada.pooled, 2)} · MAE ${num(sel.nota_aninhada.mae, 1)}`
        : `${sub(v)} · otimista`;
    };
    const linhas = c.versoes.map((v) => linha(v.nome + (v.ativo ? ' (ativo)' : ''), subVersao(v), v))
      .concat([linha('TR-069 completo', sub(c.referencias.tr069), c.referencias.tr069),
               linha('Tudo (laboratório)', sub(c.referencias.tudo), c.referencias.tudo)]);
    const d = r2 ? 2 : 1;
    st.hits = V.drawDotRows(canvas, { rows: linhas, fmt: (v) => num(v, d), fmtMean: (v) => num(v, r2 ? 3 : 1) });
    V.attachTooltip(canvas, $('#mCmpTip'), () => st.hits,
      (h) => `<b>${esc(h.label)}</b>${esc(h.at)}: ${r2 ? 'R² ' + num(h.value, 3) : 'MAE ' + num(h.value, 1) + ' ' + UNIDADE[c.alvo]}`);
  }

  function cardDesenho() {
    const u = UNIDADE[st.alvo];
    const rodando = st.des && st.des.status === 'rodando';
    const atual = st.desKey === chaveConj() + '|' + st.semVolume;
    let corpo = '<p class="hint">Seleção gulosa só entre colunas TR-069 e derivadas TR-069: a cada passo entra a feature que mais sobe o R² pooled (folds por local de coleta); para quando o ganho fica abaixo de 0,005. Leva de 3 a 6 minutos.</p>';
    if (st.desErro) corpo = gate('critical', 'O desenho falhou', esc(st.desErro));
    else if (rodando) {
      corpo = `<div class="log">${st.des.progresso.slice(-8).map((e) => `<div>${e.fase ? esc(e.fase)
        : `+ <code>${esc(e.feature)}</code> → pooled ${num(e.pooled, 3)}${e.ganho == null ? '' : ` (${sinal(e.ganho)})`}`}</div>`).join('')}<div class="gate-msg">calculando…</div></div>`;
    } else if (st.des && st.des.status === 'erro') corpo = gate('critical', 'O desenho falhou', esc(st.des.erro));
    else if (st.des && st.des.status === 'pronto') {
      const r = st.des.resultado;
      const ativo = st.reg.versoes.find((v) => v.ativo);
      const avAtivo = ativo && (ativo.avaliacao || {})[r.alvo];
      const locais = Object.keys(r.nota_aninhada.por_local);
      const todas = [...new Set(r.features.concat(...Object.values(r.nota_aninhada.escolhas_por_local)))];
      const estab = todas.map((f) => `<tr><td><code>${esc(f)}</code></td><td class="num">${r.features.includes(f) ? '●' : ''}</td>` +
        locais.map((l) => `<td class="num">${r.nota_aninhada.escolhas_por_local[l].includes(f) ? '●' : ''}</td>`).join('') + '</tr>').join('');
      corpo = `<div class="${atual ? '' : 'stale'}">
        <div class="kpis">
          <div><span>Nota aninhada (honesta)</span><b>${num(r.nota_aninhada.pooled, 3)}</b><em>MAE ${num(r.nota_aninhada.mae, 1)} ${u}</em></div>
          <div><span>Nota da seleção (otimista)</span><b>${num(r.nota_selecao.pooled, 3)}</b><em>MAE ${num(r.nota_selecao.mae, 1)} ${u}</em></div>
          <div><span>Ativo: ${esc(st.reg.ativo)}</span><b>${avAtivo ? num(avAtivo.pooled, 3) : '–'}</b><em>MAE ${avAtivo ? num(avAtivo.mae, 1) : '–'} ${u}</em></div>
        </div>
        <p class="hint">A nota aninhada roda a seleção sem o local de teste, para cada local: é o que esperar num prédio novo. A nota da seleção escolheu olhando os 3 locais e por isso sai melhor do que é. Compare o ativo com a <b>aninhada</b>.</p>
        <div class="dois">
          <div><h2 style="font-size:13px">Passos da seleção</h2><table><thead><tr><th class="num">#</th><th>Entrou</th><th class="num">R² pooled</th><th class="num">Ganho</th></tr></thead><tbody>
            ${r.passos.map((p, i) => `<tr><td class="num">${i + 1}</td><td><code>${esc(p.feature)}</code></td><td class="num">${num(p.pooled, 3)}</td><td class="num">${p.ganho == null ? '–' : sinal(p.ganho)}</td></tr>`).join('')}</tbody></table></div>
          <div><h2 style="font-size:13px">Estabilidade da escolha</h2><table><thead><tr><th>Feature</th><th class="num">Final</th>${locais.map((l) => `<th class="num" title="seleção feita sem ${esc(l)}">sem ${esc(l)}</th>`).join('')}</tr></thead><tbody>${estab}</tbody></table>
            <p class="hint" style="margin-top:6px">Uma feature escolhida em todas as colunas é estável; uma que aparece só no final dependeu de ver todos os locais.</p></div>
        </div>
        <div class="controls" style="margin-top:10px"><button class="btn-pri" data-acao="carregar-desenho">Carregar no editor</button>
          <span class="gate-msg">${r.features.length} features · ${num(r.segundos, 0)} s${atual ? '' : ' · desatualizado: o conjunto ou o alvo mudou'}</span></div></div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Desenhar melhor modelo TR-069</h2>
      <p class="hint">Só métricas TR-069 e derivadas delas: o que o ACS consegue ler em produção.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-acao="desenhar"${rodando ? ' disabled' : ''}>${rodando ? 'Desenhando…' : 'Desenhar'}</button>
        <div class="status"><label title="router_tx/rx_duration_us, router_tx_retries, router_tx_failed, router_rx_drop_misc: crescem com o tráfego do próprio teste se forem medidos na janela dele"><input type="checkbox" id="mSemVolume"${st.semVolume ? ' checked' : ''}${rodando ? ' disabled' : ''}> sem contadores brutos de volume</label></div></div></div>${corpo}</div>`;
  }

  function grupos() {
    const cols = st.inv.colunas.filter((c) => !FORA_DO_EDITOR.has(c.classe));
    const f = st.filtro.trim().toLowerCase();
    const vis = (c) => !f || c.coluna.toLowerCase().includes(f) || st.sel.has(c.coluna);
    const ordem = (a, b) => (st.sel.has(b.coluna) - st.sel.has(a.coluna)) || ((b.rho || 0) - (a.rho || 0));
    return [
      ['TR-069 · brutas', cols.filter((c) => c.classe === 'tr069' && !c.derivada)],
      ['TR-069 · derivadas', cols.filter((c) => c.classe === 'tr069' && c.derivada)],
      ['Fora do TR-069 · laboratório (não vai para produção)', cols.filter((c) => c.classe !== 'tr069')],
    ].map(([t, xs]) => [t, xs.filter(vis).sort(ordem), xs.length]);
  }

  function motivoBloqueio(c) {
    if (c.vazamento) return 'vazamento: medida durante o teste';
    if (c.constante) return 'constante neste conjunto';
    if (c.tipo === 'categorica_alta') return 'categórica com muitos valores';
    return '';
  }

  function linhaEditor(c) {
    const bloq = motivoBloqueio(c);
    const marcado = st.sel.has(c.coluna);
    const tags = [c.derivada ? '<span class="tag">derivada</span>' : '',
      c.pendente ? '<span class="tag mid" title="vazamento ainda não confirmado: veja Limites e pendências dos dados">não confirmado</span>' : '',
      c.hipotese ? '<span class="tag mid" title="derivada desenhada que não passou no critério de aceite: fica fora do teto e do desenho automático">hipótese</span>' : '',
      c.classe !== 'tr069' ? `<span class="tag lab">${ROTULO[c.classe] || esc(c.classe)}</span>` : '',
      c.cobertura < COBERTURA_MIN ? `<span class="tag mid" title="menos de ${pct(COBERTURA_MIN)} das linhas têm valor">cobertura baixa</span>` : '',
      bloq ? `<span class="tag leak">${esc(bloq)}</span>` : ''].join(' ');
    return `<label class="mrow${bloq && !marcado ? ' dim' : ''}">
      <input type="checkbox" data-col="${esc(c.coluna)}"${marcado ? ' checked' : ''}${bloq && !marcado ? ' disabled' : ''}>
      <code>${esc(c.coluna)}</code><span>${tags}</span>
      <span class="num">${pct(c.cobertura)}</span>
      <span class="num">${c.rho == null ? '–' : `<i class="bar" style="width:${c.rho * 60}px"></i>${num(c.rho, 2)}`}</span></label>`;
  }

  function cardEditor() {
    if (st.invErro) return gate('critical', 'Não foi possível carregar as colunas', esc(st.invErro));
    if (!st.inv) return '<div class="card"><p class="hint">Carregando colunas…</p></div>';
    const fora = st.inv.colunas.filter((c) => st.sel.has(c.coluna) && c.classe !== 'tr069').map((c) => c.coluna);
    const vazadas = st.inv.colunas.filter((c) => st.sel.has(c.coluna) && c.vazamento).map((c) => c.coluna);
    const conhecidas = new Set(st.inv.colunas.map((c) => c.coluna));
    const ausentes = selLista().filter((f) => !conhecidas.has(f));
    const opcoes = st.reg.versoes.map((v) => `<option value="${esc(v.nome)}"${v.nome === st.base ? ' selected' : ''}>${esc(v.nome)}</option>`).join('');
    // O grupo de laboratório tem ~120 colunas: começa recolhido, salvo se já tiver algo marcado ou filtro ativo.
    const listas = grupos().map(([titulo, xs, total], i) => `<details class="fold"${i < 2 || st.filtro.trim() || xs.some((c) => st.sel.has(c.coluna)) ? ' open' : ''}><summary>${titulo} <span>· ${total} colunas</span></summary>
      <div class="inner"><div class="mhead"><span></span><span>Coluna</span><span></span><span class="num">Cobertura</span><span class="num">|ρ| com o alvo</span></div>
      ${xs.map(linhaEditor).join('') || '<p class="hint">Nada com esse filtro.</p>'}</div></details>`).join('');
    const resumo = `<b>${st.sel.size}</b> features · ${fora.length ? `<b>${fora.length}</b> fora do TR-069` : '<span class="tag ok">100% TR-069</span>'}` +
      (desenhoVinculado() ? ' · <span class="tag current" title="ao salvar, a versão guarda a nota aninhada e os passos da seleção">do desenho automático</span>' : '');
    const avisos = [
      vazadas.length ? gate('critical', 'Features com vazamento no rascunho', `Tire antes de avaliar: <code>${esc(vazadas.join(', '))}</code>.`) : '',
      ausentes.length ? gate('warning', 'Features da base que não existem neste conjunto', `<code>${esc(ausentes.join(', '))}</code> ficam fora da conta.`) : '',
    ].join('');
    return `<div class="card"><h2>Montar modelo</h2>
      <p class="hint">Parte de uma versão salva. Ligue e desligue features; <b>Avaliar</b> compara o rascunho com a versão de partida, local de coleta por local de coleta.
        Colunas fora do TR-069 podem ser testadas, mas uma versão com elas não vai para produção.</p>
      <div class="controls">
        <label for="mBase">Partir de</label><select id="mBase">${opcoes}</select>
        <label for="mFiltro">Filtrar</label><input id="mFiltro" class="minput" type="search" placeholder="nome da coluna" value="${esc(st.filtro)}">
        <span class="chip">${resumo}</span>
      </div>
      ${avisos}${listas}
      <div class="controls" style="margin-top:12px">
        <button class="btn-pri" data-acao="avaliar"${st.avaliando || !st.sel.size || vazadas.length ? ' disabled' : ''}>${st.avaliando ? 'Avaliando…' : 'Avaliar rascunho'}</button>
        <input id="mNome" class="minput" placeholder="nome da versão, ex.: v2-tr069" maxlength="40">
        <input id="mDesc" class="minput" style="flex:1;min-width:200px" placeholder="descrição: o que mudou e por quê" maxlength="500">
        <button class="btn" data-acao="salvar"${st.salvando || !st.sel.size || vazadas.length ? ' disabled' : ''}>${st.salvando ? 'Salvando…' : 'Salvar como nova versão'}</button>
      </div>
      ${st.salvarErro ? gate('critical', 'Não foi possível salvar', esc(st.salvarErro)) : ''}
      ${st.msg ? gate('good', 'Feito', esc(st.msg)) : ''}
      ${cardResultado()}</div>`;
  }

  function cardResultado() {
    if (st.avalErro) return gate('critical', 'Não foi possível avaliar', esc(st.avalErro));
    if (!st.aval) return '';
    const a = st.aval;
    const atual = st.avalKey === chaveAval();
    const u = UNIDADE[a.alvo];
    const d = a.delta;
    const cor = (v, menorMelhor) => (v == null || Math.abs(v) < 0.005 ? '' : ((v > 0) !== !!menorMelhor ? ' good' : ' bad'));
    const linhas = Object.keys(a.resumo.por_local).map((s) => `<tr><td>${esc(s)}</td>
      <td class="num">${a.resumo_base ? num(a.resumo_base.por_local[s], 3) : '–'}</td>
      <td class="num">${num(a.resumo.por_local[s], 3)}</td>
      <td class="num${d ? cor(d.por_local[s]) : ''}">${d ? sinal(d.por_local[s]) : '–'}</td>
      <td class="num">${a.resumo_base ? num(a.resumo_base.mae_por_local[s], 1) : '–'}</td>
      <td class="num">${num(a.resumo.mae_por_local[s], 1)}</td></tr>`).join('');
    return `<div class="${atual ? '' : 'stale'}" style="margin-top:16px">
      <h2 style="font-size:13px">Rascunho contra <code>${esc(a.base || '—')}</code>${atual ? '' : ' · desatualizado'}</h2>
      <div class="kpis">
        <div><span>R² pooled</span><b>${num(a.resumo.pooled, 3)}</b><em class="${d ? cor(d.pooled).trim() : ''}">${d ? sinal(d.pooled) : ''}</em></div>
        <div><span>MAE (${u})</span><b>${num(a.resumo.mae, 1)}</b><em class="${d ? cor(d.mae, true).trim() : ''}">${d ? sinal(d.mae, 1) : ''}</em></div>
        <div><span>Melhora em</span><b>${d ? `${d.melhora} de ${d.locais}` : '–'}</b><em>locais (R²)</em></div>
      </div>
      <div style="overflow-x:auto"><table><thead><tr><th>Local de coleta</th><th class="num">R² base</th><th class="num">R² rascunho</th><th class="num">Δ R²</th>
        <th class="num">MAE base</th><th class="num">MAE rascunho</th></tr></thead><tbody>${linhas}</tbody></table></div>
      ${a.resumo.ausentes.length ? `<p class="gate-msg">Fora da conta (ausentes): <code>${esc(a.resumo.ausentes.join(', '))}</code></p>` : ''}
      <p class="hint" style="margin-top:8px">Com 3 locais de coleta, diferenças de R² abaixo de ~0,02 são ruído. Um ganho que aparece em um local só não é ganho.</p></div>`;
  }

  function corCelula(v) {
    if (v == null) return 'background:var(--grid)';
    const base = v >= 0 ? '--s1' : '--s2';
    return `background:color-mix(in srgb, var(${base}) ${Math.round(Math.abs(v) * 85)}%, transparent)`;
  }

  function cardCorrelacoes() {
    if (!st.aval) return '';
    const c = st.aval.correlacoes;
    if (!c.colunas.length) return '';
    const cab = c.colunas.map((x, i) => `<th class="rot" title="${esc(x)}"><span>${i + 1}</span></th>`).join('');
    const linhas = c.colunas.map((a, i) => `<tr><th class="lin"><span class="gate-msg">${i + 1}</span> <code>${esc(a)}</code></th>` +
      c.matriz[i].map((v, j) => `<td class="hm" style="${corCelula(i === j ? null : v)}" title="${esc(a)} × ${esc(c.colunas[j])}: ${v == null ? '–' : num(v, 2)}">${i === j || v == null ? '' : num(v, 1)}</td>`).join('') + '</tr>').join('');
    return `<div class="card${st.avalKey === chaveAval() ? '' : ' stale'}"><h2>Correlações entre as features do rascunho</h2>
      <p class="hint">Spearman entre pares. Azul: sobem juntas; laranja: uma sobe quando a outra desce. Pares com |ρ| ≥ 0,9 carregam quase a mesma informação: um deles pode sair sem perda.</p>
      ${c.redundantes.length ? `<p class="gate-msg"><b>Redundantes:</b> ${c.redundantes.map((r) => `<code>${esc(r.a)}</code> × <code>${esc(r.b)}</code> (${num(r.rho, 2)})`).join(' · ')}</p>` : '<p class="gate-msg">Nenhum par com |ρ| ≥ 0,9.</p>'}
      <div style="overflow-x:auto;margin-top:10px"><table class="heat"><thead><tr><th></th>${cab}</tr></thead><tbody>${linhas}</tbody></table></div>
      ${c.fora.length ? `<p class="gate-msg" style="margin-top:8px">Fora da matriz (categóricas ou constantes): <code>${esc(c.fora.join(', '))}</code></p>` : ''}</div>`;
  }

  function desenhar() {
    const host = $('#mBody');
    if (!st.ctx) return;
    if (!st.ctx.enabledIds.length) { host.innerHTML = '<p class="hint">Nenhum dataset ativo.</p>'; return; }
    if (!st.reg) { host.innerHTML = st.regErro ? gate('critical', 'Registro de modelos indisponível', esc(st.regErro)) : '<p class="hint">Carregando versões…</p>'; return; }
    const foco = document.activeElement && document.activeElement.id;
    const nome = $('#mNome') ? $('#mNome').value : '';
    const desc = $('#mDesc') ? $('#mDesc').value : '';
    const abertos = [...host.querySelectorAll('details.fold')].map((d) => d.open);
    host.innerHTML = (st.regErro ? gate('warning', 'Registro de modelos', esc(st.regErro)) : '') +
      cardPendencias() + cardVersoes() + cardComparacao() + cardDesenho() + cardEditor() + cardCorrelacoes();
    // Preserva o que a pessoa abriu ou fechou; filtro ativo sempre mostra os resultados.
    if (!st.filtro.trim()) host.querySelectorAll('details.fold').forEach((d, i) => { if (i < abertos.length) d.open = abertos[i]; });
    if ($('#mNome')) $('#mNome').value = nome;
    if ($('#mDesc')) $('#mDesc').value = desc;
    if (foco && $('#' + foco)) {
      const el = $('#' + foco);
      el.focus();
      if (el.id === 'mFiltro') el.setSelectionRange(el.value.length, el.value.length);
    }
    desenharComparacao();
  }

  $('#mBody').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-acao]');
    if (!alvo) return;
    const acao = alvo.dataset.acao;
    if (acao === 'comparar') comparar();
    if (acao === 'desenhar') desenharModelo();
    if (acao === 'carregar-desenho') carregarDesenho();
    if (acao === 'metrica') { st.metrica = alvo.dataset.m; desenhar(); }
    if (acao === 'avaliar') avaliar();
    if (acao === 'salvar') salvar($('#mNome').value.trim(), $('#mDesc').value);
    if (acao === 'ativar') tornarAtivo(alvo.dataset.nome);
    if (acao === 'base') { usarBase(alvo.dataset.nome); st.aval = null; desenhar(); $('#mBase').scrollIntoView({ block: 'center' }); }
  });
  $('#mBody').addEventListener('change', (ev) => {
    if (ev.target.id === 'mBase') { usarBase(ev.target.value); st.aval = null; desenhar(); return; }
    if (ev.target.id === 'mSemVolume') { st.semVolume = ev.target.checked; st.semVolumeTocado = true; desenhar(); return; }
    if (ev.target.name === 'mContadores') { definirContadores(ev.target.value); return; }
    const col = ev.target.dataset && ev.target.dataset.col;
    if (col) {
      if (ev.target.checked) st.sel.add(col); else st.sel.delete(col);
      desenhar();
    }
  });
  $('#mBody').addEventListener('input', (ev) => {
    if (ev.target.id === 'mFiltro') { st.filtro = ev.target.value; desenhar(); }
  });
  $('#mAlvo').addEventListener('change', (ev) => { st.alvo = ev.target.value; carregarInventario(); desenhar(); });

  V.views.modelos = {
    // Uma derivada nova muda as colunas disponíveis e a chave das avaliações.
    recarregar() { st.invKey = null; st.cmpKey = null; if (st.ctx) { carregarInventario(); carregarRegistro(); } },
    render(ctx) {
      st.ctx = ctx;
      if (!st.reg && !st.regErro) carregarRegistro();
      carregarPendencias();
      carregarInventario();
      desenhar();
    },
  };
})();
