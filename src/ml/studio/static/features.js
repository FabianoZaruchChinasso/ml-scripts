/* features.js — view Features. Estado proprio; studio.js chama render(ctx)
   sempre que a view esta visivel e algo muda (datasets, tema, resize). */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d);
  const pct = (v) => Math.round(v * 100) + '%';
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const CLASSES = [['tr069', 'TR-069'], ['sniffer', 'Sniffer'], ['cliente', 'Cliente'],
    ['ambiente', 'Ambiente'], ['geometria', 'Geometria'], ['identificador', 'Identificador'], ['alvo', 'Alvo']];
  const ROTULO = Object.fromEntries(CLASSES.concat([['auxiliar', 'Auxiliar']]));
  const LEITURA = { alcancavel: ['ok', 'alcançável'], parcial: ['mid', 'parcial'], laboratorio: ['lab', 'só laboratório'] };
  const VAZAMENTO = 'Medida durante o teste: carrega o próprio alvo e não existe em produção.';

  const st = { ctx: null, alvo: 'speedtest_down_mbps', inv: null, invKey: null, invErro: null,
               aj: null, ajKey: null, ajHora: null, ajErro: null, rodando: false, inicio: 0,
               relogio: null, salvarErro: null, hits: null, abertos: [] };

  const chave = () => st.ctx.enabledIds.slice().sort().join(',') + '|' + st.alvo;
  const query = () => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(st.alvo);

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }

  function carregarInventario() {
    const k = chave();
    if (st.invKey === k) return;
    st.invKey = k; st.inv = null; st.invErro = null;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.invKey === k) st.inv = inv; })
      .catch((e) => { if (st.invKey === k) st.invErro = e.message; })
      .finally(() => { if (st.invKey === k) desenhar(); });
  }

  function rodarAnalise() {
    if (st.rodando) return;
    const k = chave();
    st.rodando = true; st.ajErro = null; st.inicio = Date.now();
    st.relogio = setInterval(() => {
      const el = $('#fRelogio');
      if (el) el.textContent = Math.round((Date.now() - st.inicio) / 1000) + ' s';
    }, 500);
    desenhar();
    pedir('api/features/ajuste?' + query())
      .then((aj) => { st.aj = aj; st.ajKey = k; st.ajHora = new Date(); })
      .catch((e) => { st.ajErro = e.message; })
      .finally(() => { clearInterval(st.relogio); st.rodando = false; desenhar(); });
  }

  function classificar(coluna, classe, vazamento, parametro) {
    st.salvarErro = null;
    pedir('api/columns', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ coluna, classe, vazamento, parametro: parametro || null }) })
      .then(() => { st.invKey = null; st.ajKey = null; carregarInventario(); })
      .catch((e) => { st.salvarErro = `${coluna}: ${e.message}`; desenhar(); });
  }

  /* ---------------- blocos ---------------- */
  const gate = (sev, titulo, msg, extra = '') => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div>${extra}</div></div>`;

  function gates(inv, porNome) {
    let html = '';
    if (st.salvarErro) html += gate('critical', 'Não foi possível salvar', esc(st.salvarErro));
    if (inv.tabela_erro) html += gate('critical', 'Tabela de classificação ilegível', esc(inv.tabela_erro));
    if (inv.sem_classificacao.length) {
      const linhas = inv.sem_classificacao.map((c) => `<div class="frow" data-col="${esc(c.coluna)}">
        <code>${esc(c.coluna)}</code>
        <span class="gate-msg">${pct(c.cobertura)} · ${esc(c.amostra)}</span>
        <select>${CLASSES.map(([k, r]) => `<option value="${k}"${k === c.sugestao ? ' selected' : ''}>${r}${k === c.sugestao ? ' (sugerido)' : ''}</option>`).join('')}</select>
        <span><label class="gate-msg" title="${VAZAMENTO}"><input type="checkbox"> vazamento</label>
          <button class="btn-pri" data-acao="adicionar">Adicionar</button></span></div>`).join('');
      html += gate('critical', `${inv.sem_classificacao.length} coluna(s) sem classificação`,
        'Ficam fora de toda a análise até alguém classificar. A sugestão vem do nome e precisa ser confirmada.',
        linhas + '<div class="gate-msg" style="margin-top:6px">Salva em <code>src/ml/core/column_provenance.json</code>. Revise no <code>git diff</code> antes do commit.</div>');
    }
    if (st.aj && st.ajKey === chave()) {
      st.aj.proxy.filter((p) => p.parece_tr069).forEach((p) => {
        html += gate('warning', `<code>${esc(p.coluna)}</code> parece ser TR-069`,
          `O TR-069 reconstrói esta coluna com R² ≥ 0,99 em todas as posições (média ${num(p.r2, 2)}).`,
          `<div style="margin-top:8px"><button class="btn" data-acao="reclassificar" data-col="${esc(p.coluna)}">Reclassificar como TR-069</button></div>`);
      });
    }
    inv.colunas.filter((c) => c.suspeita && !c.derivada).forEach((c) => {
      html += gate('warning', `<code>${esc(c.coluna)}</code> pode ter vazamento`,
        `|ρ| = ${num(c.rho, 2)} com o alvo. ${VAZAMENTO} Confirme antes de usar.`,
        `<div style="margin-top:8px"><button class="btn" data-acao="vazar" data-col="${esc(c.coluna)}">Marcar vazamento</button></div>`);
    });
    inv.modelo_fora_do_tr069.forEach((c) => {
      html += gate('warning', `<code>${esc(c)}</code> está no modelo, mas não é TR-069`,
        `Classe: ${ROTULO[porNome[c].classe]}. O ACS não lê esta coluna em produção.`);
    });
    inv.avisos.forEach((a) => { html += gate('warning', 'Aviso', esc(a)); });
    return html;
  }

  function leituraTeto(aj) {
    const t = aj.teto;
    const n = aj.posicoes.length;
    if (t.atual.media == null) return 'Nenhuma feature do modelo atual está disponível neste conjunto.';
    const d = t.tr069.media - t.atual.media;
    const melhora = Object.keys(t.atual.por_posicao)
      .filter((s) => t.tr069.por_posicao[s] > t.atual.por_posicao[s]).length;
    const dt = t.tudo.media - t.tr069.media;
    return `Todo o TR-069 rende <b>${sinal(d)}</b> sobre o modelo atual e melhora ${melhora} de ${n} posições. ` +
      (Math.abs(dt) < 0.02 ? `Somar as auxiliares não muda o teto (${num(t.tudo.media, 3)}). `
        : `Somar as auxiliares leva a ${num(t.tudo.media, 3)} (${sinal(dt)}). `) +
      `Com ${n} posições, diferenças abaixo de ~0,02 são ruído.`;
  }

  function cardTeto() {
    const atual = st.aj && st.ajKey === chave();
    let status = '';
    if (st.rodando) status = 'calculando… <span id="fRelogio">0 s</span>';
    else if (st.ajErro) status = `<span style="color:var(--critical)">${esc(st.ajErro)}</span>`;
    else if (atual) status = `calculado às ${st.ajHora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} · ${num(st.aj.segundos, 0)} s`;
    else if (st.aj) status = 'desatualizado: o conjunto ou o alvo mudou';
    let corpo = '<p class="hint">Clique em <b>Rodar análise</b>. Leva cerca de 75 s com os dados atuais.</p>';
    if (st.aj) {
      const pos = st.aj.posicoes;
      corpo = `<div class="${atual ? '' : 'stale'}"><div class="chartwrap"><canvas id="fTeto"></canvas><div class="tooltip" id="fTetoTip"></div></div>
        <div class="serieskey">${pos.map((p, i) => `<span><i style="background:var(--s${i % 5 + 1})"></i>${esc(p)}</span>`).join('')}</div>
        <p style="margin:12px 0 0;font-size:13px">${leituraTeto(st.aj)}</p></div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Teto de desempenho</h2>
      <p class="hint">R² LOGO do alvo com três conjuntos de features. Cada ponto é uma posição deixada de fora; a barra vertical é a média.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-acao="rodar"${st.rodando ? ' disabled' : ''}>Rodar análise</button>
      <div class="status">${status}</div></div></div>${corpo}</div>`;
  }

  function desenharTeto() {
    const canvas = $('#fTeto');
    if (!canvas || !st.aj) return;
    const aj = st.aj;
    const linhas = [['atual', 'Modelo atual'], ['tr069', 'TR-069 completo'], ['tudo', 'Tudo']].map(([k, rotulo]) => ({
      label: rotulo, sub: `${aj.teto[k].n} features`, mean: aj.teto[k].media,
      points: aj.posicoes.map((p, i) => ({ key: p, v: aj.teto[k].por_posicao[p], color: cssv('--s' + (i % 5 + 1)) }))
        .filter((p) => p.v != null),
    }));
    st.hits = V.drawDotRows(canvas, { rows: linhas, fmt: (v) => num(v, 2), fmtMean: (v) => num(v, 3) });
    V.attachTooltip(canvas, $('#fTetoTip'), () => st.hits,
      (h) => `<b>${esc(h.label)}</b>${esc(h.at)}: R² ${num(h.value, 3)}`);
  }

  const barra = (v, cor) => `<i class="bar" style="width:${Math.max(0, Math.min(1, v)) * 80}px${cor ? ';background:' + cor : ''}"></i>`;

  function cardCandidatas(inv) {
    const atual = st.aj && st.ajKey === chave();
    const ganho = atual ? Object.fromEntries(st.aj.ganho.map((g) => [g.coluna, g])) : {};
    const lista = inv.colunas.filter((c) => c.classe === 'tr069' && !c.no_modelo && !c.constante && c.cobertura >= 0.7);
    const limpas = lista.filter((c) => !c.vazamento).sort((a, b) =>
      atual ? ((ganho[b.coluna] || { delta: -9 }).delta - (ganho[a.coluna] || { delta: -9 }).delta)
        : ((b.rho || 0) - (a.rho || 0)));
    const vazadas = lista.filter((c) => c.vazamento).sort((a, b) => (b.rho || 0) - (a.rho || 0));
    const tipo = (c) => c.derivada
      ? '<span class="tag">derivada</span>' + (c.normaliza_volume ? ' <span class="tag ok" title="razão entre dois contadores de volume: o volume se cancela">normaliza volume</span>' : '')
      : '<span class="tag">bruta</span>';
    const linha = (c) => {
      const g = ganho[c.coluna];
      const cel = c.vazamento ? '<td class="num" colspan="2">fora dos ajustes</td>'
        : g ? `<td class="num">${sinal(g.delta)}</td><td class="num${g.melhora === g.posicoes ? ' good' : ''}">${g.melhora}/${g.posicoes}</td>`
          : '<td class="num">–</td><td class="num">–</td>';
      const t = c.vazamento ? `<span class="tag leak" title="${VAZAMENTO}">${c.derivada ? 'vazamento herdado' : 'vazamento'}</span>` : tipo(c);
      return `<tr${c.vazamento ? ' class="dim"' : ''}><td><code>${esc(c.coluna)}</code></td><td>${t}</td>
        <td class="num">${pct(c.cobertura)}</td><td>${c.rho == null ? '–' : barra(c.rho, c.vazamento ? 'var(--grid)' : '') + num(c.rho, 2)}</td>${cel}</tr>`;
    };
    return `<div class="card"><h2>Candidatas TR-069 fora do modelo</h2>
      <p class="hint">Ganho é o ΔR² LOGO médio ao somar a coluna às features atuais. Abaixo de ~0,01 é ruído; "melhora" diz se o ganho é consistente entre posições.</p>
      ${lista.length ? `<table><thead><tr><th>Coluna</th><th>Tipo</th><th class="num">Cobertura</th><th>|ρ| com o alvo</th><th class="num">Ganho</th><th class="num">Melhora</th></tr></thead>
      <tbody>${limpas.concat(vazadas).map(linha).join('')}</tbody></table>` : '<p class="hint">Nenhuma coluna TR-069 fora do modelo neste conjunto.</p>'}</div>`;
  }

  function cardProxy(inv) {
    let corpo = '<p class="hint">Rode a análise para ver os proxies.</p>';
    if (st.aj) {
      const idem = {};
      inv.grupos_identicos.forEach((g) => g.forEach((c) => { idem[c] = g.filter((x) => x !== c); }));
      const cor = { alcancavel: 'var(--good)', parcial: 'var(--warning)', laboratorio: 'var(--axis)' };
      corpo = st.aj.proxy.length ? `<div class="${st.ajKey === chave() ? '' : 'stale'}"><table><thead><tr><th>Auxiliar</th><th>Fonte</th><th class="num">|ρ| com o alvo</th><th>R² do proxy</th><th class="num">Faixa por posição</th><th>Leitura</th></tr></thead><tbody>` +
        st.aj.proxy.map((p) => `<tr><td><code>${esc(p.coluna)}</code>${idem[p.coluna] ? `<div class="gate-msg">idêntica a <code>${esc(idem[p.coluna].join(', '))}</code></div>` : ''}</td>
          <td>${ROTULO[p.classe]}</td><td class="num">${num(p.rho, 2)}</td><td>${barra(p.r2, cor[p.leitura])}${num(p.r2, 2)}</td>
          <td class="num gate-msg">${num(p.min, 2)} a ${num(p.max, 2)}</td>
          <td><span class="tag ${LEITURA[p.leitura][0]}">${LEITURA[p.leitura][1]}</span></td></tr>`).join('') + '</tbody></table></div>'
        : '<p class="hint">Nenhuma auxiliar elegível neste conjunto.</p>';
    }
    return `<div class="card"><h2>Auxiliares: o TR-069 consegue reconstruir?</h2>
      <p class="hint">R² LOGO de "auxiliar ≈ f(todas as TR-069)". Alcançável ≥ 0,7 · parcial 0,3 a 0,7 · só laboratório &lt; 0,3. Um sinal alcançável ainda precisa de uma receita TR-069 que o reproduza, então vira ideia de derivada.</p>${corpo}</div>`;
  }

  function blocos(inv) {
    const vazadas = inv.colunas.filter((c) => c.vazamento);
    const constantes = inv.colunas.filter((c) => c.constante);
    const contagem = Object.entries(inv.contagem_por_classe).sort((a, b) => b[1] - a[1])
      .map(([k, n]) => `${ROTULO[k]} ${n}`).join(' · ');
    const codes = (xs) => xs.map((x) => `<code>${esc(x)}</code>`).join(', ');
    return `<details class="fold"><summary>Vazamento <span>· ${vazadas.length} colunas</span></summary>
        <div class="inner"><p>${VAZAMENTO} Fica fora dos ajustes.</p>${codes(vazadas.map((c) => c.coluna))}</div></details>
      <details class="fold"><summary>Qualidade das colunas <span>· ${constantes.length} constantes · ${inv.grupos_identicos.length} grupos idênticos</span></summary>
        <div class="inner"><p><b>Constantes:</b> ${codes(constantes.map((c) => c.coluna)) || '—'}</p>
        <p><b>Idênticas:</b></p><ul>${inv.grupos_identicos.map((g) => `<li>${codes(g)}</li>`).join('') || '<li>—</li>'}</ul></div></details>
      <details class="fold"><summary>Inventário completo <span>· ${inv.colunas.length} colunas · ${contagem}</span></summary>
        <div class="inner"><table><thead><tr><th>Coluna</th><th>Classe</th><th>Origem</th><th>Tipo</th><th class="num">Cobertura</th><th class="num">|ρ|</th><th>Vazamento</th></tr></thead><tbody>` +
      inv.colunas.slice().sort((a, b) => a.coluna.localeCompare(b.coluna)).map((c) => `<tr><td><code>${esc(c.coluna)}</code></td>
        <td>${ROTULO[c.classe]}</td><td>${esc(c.origem)}</td><td>${esc(c.tipo)}</td><td class="num">${pct(c.cobertura)}</td>
        <td class="num">${c.rho == null ? '–' : num(c.rho, 2)}</td><td>${c.vazamento ? 'sim' : ''}</td></tr>`).join('') +
      '</tbody></table></div></details>';
  }

  function desenhar() {
    const host = $('#fBody');
    if (!st.ctx) return;
    // Guarda quais blocos estavam abertos antes de qualquer troca de conteúdo:
    // o "Carregando…" intermediário apagaria os <details> e o estado com eles.
    const atuais = host.querySelectorAll('details.fold');
    if (atuais.length) st.abertos = [...atuais].map((d) => d.open);
    if (!st.ctx.enabledIds.length) { host.innerHTML = '<p class="hint">Nenhum dataset ativo.</p>'; $('#fChip').textContent = ''; return; }
    if (st.invErro) { host.innerHTML = gate('critical', 'Não foi possível montar o inventário', esc(st.invErro)); return; }
    if (!st.inv) { host.innerHTML = '<p class="hint">Carregando inventário…</p>'; return; }
    const inv = st.inv;
    const porNome = Object.fromEntries(inv.colunas.map((c) => [c.coluna, c]));
    $('#fChip').textContent = `${inv.datasets.join(', ')} · ${inv.n_linhas.toLocaleString('pt-BR')} amostras · ${inv.posicoes.length} posições`;
    host.innerHTML = gates(inv, porNome) + cardTeto() + cardCandidatas(inv) + cardProxy(inv) + blocos(inv);
    host.querySelectorAll('details.fold').forEach((d, i) => { d.open = !!st.abertos[i]; });
    desenharTeto();
  }

  $('#fBody').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-acao]');
    if (!alvo) return;
    const acao = alvo.dataset.acao;
    const porNome = st.inv ? Object.fromEntries(st.inv.colunas.map((c) => [c.coluna, c])) : {};
    if (acao === 'rodar') rodarAnalise();
    if (acao === 'adicionar') {
      const linha = alvo.closest('.frow');
      classificar(linha.dataset.col, linha.querySelector('select').value, linha.querySelector('input').checked, null);
    }
    if (acao === 'reclassificar') {
      const c = porNome[alvo.dataset.col];
      classificar(c.coluna, 'tr069', false, c.parametro);
    }
    if (acao === 'vazar') {
      const c = porNome[alvo.dataset.col];
      classificar(c.coluna, c.classe, true, c.parametro);
    }
  });
  $('#fAlvo').addEventListener('change', (ev) => { st.alvo = ev.target.value; carregarInventario(); desenhar(); });

  V.views.features = {
    render(ctx) {
      st.ctx = ctx;
      carregarInventario();
      desenhar();
    },
  };
})();
