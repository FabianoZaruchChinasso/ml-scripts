/* paralelos.js — na view Modelos: paralelos laboratório × TR-069 e o desenhista
   de derivadas. studio.js chama render(ctx) junto com o de modelos.js. */
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

  const ROTULO = { sniffer: 'Sniffer', cliente: 'Cliente', ambiente: 'Ambiente', geometria: 'Manual',
    auxiliar: 'Auxiliar', tr069: 'TR-069' };
  const VEREDITO = {
    candidata: ['ok', 'candidata a receita', 'Importa para o alvo e o TR-069 reconstrói: vale escrever uma fórmula.'],
    so_laboratorio: ['mid', 'só laboratório', 'Importa para o alvo, mas o TR-069 não reconstrói em prédio novo.'],
    ja_no_tr069: ['lab', 'o TR-069 já carrega', 'O TR-069 reconstrói, mas somar não melhora o alvo: a informação já está no modelo.'],
    sem_paralelo: ['lab', 'sem paralelo', 'Não melhora o alvo e o TR-069 não reconstrói.'],
  };

  const st = { ctx: null, base: null, versoes: [], ativo: null,
               job: null, jobId: null, jobKey: null, jobErro: null, timer: null, filtro: 'todos', aberta: null,
               derivadas: null, derivErro: null, colunas: [], colKey: null,
               form: { nome: '', formula: '', inspirada: '', descricao: '' },
               previa: null, teste: null, formErro: null, ocupado: null, msg: null };

  const alvo = () => $('#mAlvo').value;
  const chaveConj = () => st.ctx.enabledIds.slice().sort().join(',') + '|' + alvo() + '|' + st.ctx.ambiente;
  const query = () => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(alvo()) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }
  const postJson = (url, corpo) => pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });

  function carregarBase() {
    return Promise.all([pedir('api/modelos'), pedir('api/derivadas')]).then(([reg, der]) => {
      st.versoes = reg.versoes.map((v) => v.nome);
      st.ativo = reg.ativo;
      // Padrão: a versão TR-069 pura mais recente, para "importa?" medir o que a coluna soma ao TR-069.
      // Pula as desenhadas com contadores brutos de volume, que ainda podem ser vazamento.
      if (!st.base || !st.versoes.includes(st.base)) {
        const puras = reg.versoes.filter((v) => !v.fora_do_tr069.length
          && !(v.selecao && v.selecao.parametros && v.selecao.parametros.sem_volume === false));
        st.base = (puras.length ? puras[puras.length - 1] : reg.versoes.find((v) => v.ativo)).nome;
      }
      st.derivadas = der; st.derivErro = der.erro;
    }).catch((e) => { st.derivErro = e.message; }).finally(desenhar);
  }

  function carregarColunas() {
    const k = chaveConj();
    if (st.colKey === k) return;
    st.colKey = k;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.colKey === k) { st.colunas = inv.colunas; desenhar(); } })
      .catch(() => { st.colunas = []; });
  }

  function analisar() {
    if (st.job && st.job.status === 'rodando') return;
    st.jobErro = null; st.job = { status: 'rodando', progresso: [] }; st.jobKey = chaveConj() + '|' + st.base; desenhar();
    pedir('api/paralelos?' + query() + '&base=' + encodeURIComponent(st.base), { method: 'POST' })
      .then((r) => { st.jobId = r.id; acompanhar(); })
      .catch((e) => { st.jobErro = e.message; st.job = null; desenhar(); });
  }

  function acompanhar() {
    clearTimeout(st.timer);
    pedir('api/paralelos/' + st.jobId)
      .then((job) => { st.job = job; if (job.status === 'rodando') st.timer = setTimeout(acompanhar, 1500); })
      .catch((e) => { st.jobErro = e.message; })
      .finally(desenhar);
  }

  function corpoFormula() {
    lerForm();
    return { nome: st.form.nome.trim(), formula: st.form.formula.trim(), inspirada_em: st.form.inspirada || null,
             descricao: st.form.descricao, base: st.base, ds: st.ctx.enabledIds.join(','),
             alvo: alvo(), ambiente: st.ctx.ambiente };
  }

  function acao(tipo) {
    const corpo = corpoFormula();
    st.formErro = null; st.msg = null; st.ocupado = tipo;
    if (tipo !== 'previa') st.teste = null;
    desenhar();
    const url = { previa: 'api/derivadas/previa', testar: 'api/derivadas/testar', salvar: 'api/derivadas' }[tipo];
    postJson(url, corpo)
      .then((r) => {
        if (tipo === 'previa') st.previa = r;
        if (tipo === 'testar') { st.teste = r; st.previa = r; }
        if (tipo === 'salvar') {
          st.teste = r.teste; st.previa = r.teste; st.derivadas = r.lista;
          st.msg = `Derivada ${corpo.nome} salva como ${r.status === 'aprovada' ? 'aprovada' : 'hipótese'} em src/ml/core/derivadas.json. Revise no git diff antes do commit.`;
          st.colKey = null; carregarColunas();
          if (V.views.modelos.recarregar) V.views.modelos.recarregar();
        }
      })
      .catch((e) => { st.formErro = e.message; })
      .finally(() => { st.ocupado = null; desenhar(); });
  }

  function lerForm() {
    ['nome', 'formula', 'inspirada', 'descricao'].forEach((k) => {
      const el = $('#pf-' + k);
      if (el) st.form[k] = el.value;
    });
  }

  function desenharReceita(linha) {
    st.form = { nome: '', formula: linha.sugestao[0] || '', inspirada: linha.coluna,
                descricao: `Receita TR-069 inspirada em ${linha.coluna}.` };
    st.previa = null; st.teste = null; st.formErro = null; st.msg = null;
    desenhar();
    $('#pf-nome').scrollIntoView({ block: 'center' });
    $('#pf-nome').focus();
  }

  /* ---------------- blocos ---------------- */
  const gate = (sev, titulo, msg) => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div></div></div>`;
  const simNao = (ok, texto) => `<span class="tag ${ok ? 'ok' : 'lab'}">${ok ? '✓' : '✗'} ${texto}</span>`;

  function tabelaAssinatura(ass, locais) {
    if (!ass.length) return '<p class="gate-msg">Nenhuma coluna TR-069 numérica para comparar.</p>';
    return `<table><thead><tr><th>Coluna TR-069</th>${locais.map((l) => `<th class="num">ρ em ${esc(l)}</th>`).join('')}<th>Mesmo sinal, |ρ| ≥ 0,3</th></tr></thead><tbody>` +
      ass.map((a) => `<tr><td><code>${esc(a.coluna)}</code></td>${locais.map((l) => `<td class="num">${a.por_local[l] == null ? '<span title="a coluna não varia neste local">–</span>' : sinal(a.por_local[l], 2)}</td>`).join('')}
        <td>${a.consistente ? '<span class="tag ok">consistente</span>' : '<span class="tag lab">não</span>'}</td></tr>`).join('') + '</tbody></table>';
  }

  function cardParalelos() {
    const rodando = st.job && st.job.status === 'rodando';
    const opcoes = st.versoes.map((n) => `<option value="${esc(n)}"${n === st.base ? ' selected' : ''}>${esc(n)}${n === st.ativo ? ' (ativo)' : ''}</option>`).join('');
    let corpo = '<p class="hint">Clique em <b>Analisar</b>. Leva alguns minutos: cada coluna passa por dois ajustes com folds por local de coleta.</p>';
    if (st.jobErro) corpo = gate('critical', 'A análise falhou', esc(st.jobErro));
    else if (rodando) corpo = `<div class="log">${st.job.progresso.slice(-3).map((e) => `<div>${esc(e.fase)}</div>`).join('')}<div class="gate-msg">calculando…</div></div>`;
    else if (st.job && st.job.status === 'erro') corpo = gate('critical', 'A análise falhou', esc(st.job.erro));
    else if (st.job && st.job.status === 'pronto') corpo = resultado(st.job.resultado);
    return `<div class="card"><div class="card-head"><div><h2>Paralelos: laboratório × TR-069</h2>
      <p class="hint">Para cada coluna fora do TR-069: <b>1</b> somá-la à versão base melhora o alvo em prédio novo? <b>2</b> o TR-069 a reconstrói em prédio novo?
        <b>3</b> quais colunas TR-069 andam com ela <i>dentro</i> de cada prédio, com o mesmo sinal em todos? Se 1 e 2 passam, vale escrever uma receita só com TR-069 no desenhista abaixo.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-pacao="analisar"${rodando ? ' disabled' : ''}>${rodando ? 'Analisando…' : 'Analisar'}</button></div></div>
      <div class="controls"><label for="pBase">Versão base</label><select id="pBase"${rodando ? ' disabled' : ''}>${opcoes}</select>
        <span class="gate-msg">A pergunta 1 mede o que a coluna soma a esta versão.</span></div>${corpo}</div>`;
  }

  function resultado(r) {
    const atual = st.jobKey === chaveConj() + '|' + st.base;
    const cont = {};
    r.colunas.forEach((c) => { cont[c.veredito] = (cont[c.veredito] || 0) + 1; });
    const filtros = [['todos', `Todas · ${r.colunas.length}`]].concat(Object.keys(VEREDITO).filter((k) => cont[k])
      .map((k) => [k, `${VEREDITO[k][1]} · ${cont[k]}`]));
    const linhas = r.colunas.filter((c) => st.filtro === 'todos' || c.veredito === st.filtro);
    const locais = Object.keys(r.resumo_base.por_local);
    const tbody = linhas.map((c) => {
      const v = VEREDITO[c.veredito];
      const g = c.ganho;
      const aberta = st.aberta === c.coluna;
      const nef = c.n_efetivo.constante_por_posicao
        ? `<div class="gate-msg" title="constante dentro de cada posição: só ${c.n_efetivo.grupos} pontos independentes">n efetivo: ${c.n_efetivo.grupos} grupos</div>` : '';
      return `<tr class="plinha${aberta ? ' aberta' : ''}" data-col="${esc(c.coluna)}">
        <td><button class="linkbtn" data-pacao="abrir" data-col="${esc(c.coluna)}" aria-expanded="${aberta}">${aberta ? '▾' : '▸'} <code>${esc(c.coluna)}</code></button>
          <span class="tag lab">${ROTULO[c.classe] || esc(c.classe)}</span>${c.na_base ? ' <span class="tag mid" title="já está na versão base: o ganho mostrado é o de mantê-la">na base</span>' : ''}${nef}</td>
        <td class="num">${num(c.rho, 2)}</td>
        <td>${simNao(c.importa, `${sinal(g.media)} · ${g.melhora}/${g.locais}`)}</td>
        <td>${simNao(c.reconstroi, `mín. ${num(c.reconstrucao.minimo, 2)}`)}</td>
        <td>${c.sugestao.length ? c.sugestao.slice(0, 2).map((s) => `<code>${esc(s)}</code>`).join(', ') : '<span class="gate-msg">nenhuma consistente</span>'}</td>
        <td><span class="tag ${v[0]}" title="${esc(v[2])}">${v[1]}</span></td>
        <td><button class="btn" data-pacao="receita" data-col="${esc(c.coluna)}">Desenhar receita</button></td></tr>` +
        (aberta ? `<tr class="pdet"><td colspan="7"><div class="dois">
          <div><h2 style="font-size:13px">Assinatura dentro de cada prédio</h2>${tabelaAssinatura(c.assinatura, locais)}</div>
          <div><h2 style="font-size:13px">Por local de coleta</h2><table><thead><tr><th>Local</th><th class="num">Δ R² no alvo</th><th class="num">R² da reconstrução</th></tr></thead><tbody>
            ${locais.map((l) => `<tr><td>${esc(l)}</td><td class="num">${sinal(g.por_local[l])}</td><td class="num">${num(c.reconstrucao.por_local[l], 2)}</td></tr>`).join('')}</tbody></table></div>
          </div></td></tr>` : '');
    }).join('');
    return `<div class="${atual ? '' : 'stale'}">
      <p class="gate-msg">Base <code>${esc(r.versao_base)}</code>: R² pooled ${num(r.resumo_base.pooled, 3)} · MAE ${num(r.resumo_base.mae, 1)} · ${num(r.segundos, 0)} s${atual ? '' : ' · desatualizada: o conjunto, o alvo ou a base mudou'}</p>
      ${r.avisos.map((a) => `<p class="gate-msg">${esc(a)}</p>`).join('')}
      <div class="controls" style="margin:10px 0">${filtros.map(([k, t]) => `<button class="toggle" data-pacao="filtro" data-f="${k}" aria-pressed="${st.filtro === k}"><span class="dot"></span> ${esc(t)}</button>`).join('')}</div>
      <div style="overflow-x:auto"><table><thead><tr><th>Coluna</th><th class="num">|ρ| alvo</th><th>1 · Importa?</th><th>2 · Reconstrói?</th><th>3 · Assinatura consistente</th><th>Leitura</th><th></th></tr></thead>
      <tbody>${tbody}</tbody></table></div>
      <p class="hint" style="margin-top:8px">Critérios: importa = ganho médio de R² ≥ ${num(r.criterios.ganho_min, 2)} e melhora em todos os locais; reconstrói = R² ≥ ${num(r.criterios.reconstroi_min, 1)} em todos os locais.
        Ajustes desta análise usam ${r.criterios.arvores} árvores (o teste de aceite do desenhista usa 200). Colunas manuais costumam ser constantes por posição: com poucos grupos, a assinatura é fraca.</p></div>`;
  }

  function cardDesenhista() {
    const lab = st.colunas.filter((c) => c.classe !== 'tr069' && c.tipo === 'numerica' && !['identificador', 'alvo'].includes(c.classe));
    const opcoes = ['<option value="">— nenhuma —</option>'].concat(lab.map((c) => `<option value="${esc(c.coluna)}"${c.coluna === st.form.inspirada ? ' selected' : ''}>${esc(c.coluna)}</option>`)).join('');
    const brutas = st.colunas.filter((c) => !c.derivada && c.tipo === 'numerica' && !['identificador', 'alvo'].includes(c.classe));
    const funcoes = st.derivadas ? st.derivadas.funcoes.join(', ') : '';
    const oc = st.ocupado;
    return `<div class="card"><h2>Desenhista de derivadas</h2>
      <p class="hint">Escreva uma fórmula com colunas brutas: números, <code>+ − * / **</code>, parênteses e ${esc(funcoes)}. <b>Prévia</b> é instantânea;
        <b>Testar</b> roda o critério de aceite (insumos TR-069, sem vazamento, ganho no alvo em todos os locais e, se houver inspiração, reconstrução com R² ≥ 0,3 em todos).
        <b>Salvar</b> refaz o teste no servidor: a derivada entra como <i>aprovada</i> ou <i>hipótese</i>, e hipóteses ficam fora do teto e do desenho automático.</p>
      <datalist id="pf-colunas">${brutas.map((c) => `<option value="${esc(c.coluna)}">`).join('')}</datalist>
      <div class="pform">
        <label for="pf-nome">Nome</label><input id="pf-nome" class="minput" maxlength="40" placeholder="ex.: retry_overhead_tr069" value="${esc(st.form.nome)}">
        <label for="pf-formula">Fórmula</label><input id="pf-formula" class="minput mono" list="pf-colunas" maxlength="300" placeholder="ex.: router_tx_retries / router_tx_packets" value="${esc(st.form.formula)}">
        <label for="pf-inspirada">Inspirada em</label><select id="pf-inspirada">${opcoes}</select>
        <label for="pf-descricao">Descrição</label><input id="pf-descricao" class="minput" maxlength="500" placeholder="o que a fórmula mede e por quê" value="${esc(st.form.descricao)}">
      </div>
      <div class="controls" style="margin-top:10px">
        <button class="btn" data-pacao="previa"${oc ? ' disabled' : ''}>${oc === 'previa' ? 'Calculando…' : 'Prévia'}</button>
        <button class="btn-pri" data-pacao="testar"${oc ? ' disabled' : ''}>${oc === 'testar' ? 'Testando…' : 'Testar'}</button>
        <button class="btn" data-pacao="salvar"${oc ? ' disabled' : ''}>${oc === 'salvar' ? 'Salvando…' : 'Salvar derivada'}</button>
      </div>
      ${st.formErro ? gate('critical', 'Não deu', esc(st.formErro)) : ''}
      ${st.msg ? gate('good', 'Feito', esc(st.msg)) : ''}
      ${blocoPrevia()}${blocoTeste()}${listaDerivadas()}</div>`;
  }

  function blocoPrevia() {
    const p = st.previa;
    if (!p) return '';
    const locais = Object.keys(p.distribuicao);
    const classe = p.classe === 'tr069' ? '<span class="tag ok">TR-069</span>'
      : p.classe ? `<span class="tag mid">${ROTULO[p.classe] || esc(p.classe)}: não vai para produção</span>` : '<span class="tag leak">insumo sem classificação</span>';
    return `<div style="margin-top:14px"><h2 style="font-size:13px">Prévia de <code>${esc(p.nome)}</code></h2>
      <p class="gate-msg">${classe} ${p.vazamento ? '<span class="tag leak">vazamento herdado</span>' : ''} · cobertura ${pct(p.cobertura)} · |ρ| com o alvo ${num(p.rho_alvo, 2)} · insumos: ${p.insumos.map((c) => `<code>${esc(c)}</code>`).join(', ')}</p>
      <div style="overflow-x:auto"><table><thead><tr><th>Local</th><th class="num">mín.</th><th class="num">mediana</th><th class="num">máx.</th>${p.inspirada_em ? `<th class="num">ρ com ${esc(p.inspirada_em)}</th>` : ''}</tr></thead><tbody>
        ${locais.map((l) => { const d = p.distribuicao[l]; return `<tr><td>${esc(l)}</td><td class="num">${d ? num(d.min, 3) : '–'}</td><td class="num">${d ? num(d.mediana, 3) : '–'}</td><td class="num">${d ? num(d.max, 3) : '–'}</td>${p.inspirada_em ? `<td class="num">${sinal((p.rho_inspirada_por_local || {})[l], 2)}</td>` : ''}</tr>`; }).join('')}
      </tbody></table></div></div>`;
  }

  function blocoTeste() {
    const t = st.teste;
    if (!t) return '';
    const g = t.ganho;
    return `<div style="margin-top:14px"><h2 style="font-size:13px">Teste de aceite: <span class="tag ${t.status === 'aprovada' ? 'ok' : 'mid'}">${t.status === 'aprovada' ? 'aprovada' : 'hipótese'}</span></h2>
      <ul class="crit">${t.criterios.map((c) => `<li class="${c.ok ? 'ok' : 'no'}">${c.ok ? '✓' : '✗'} ${esc(c.criterio)}</li>`).join('')}</ul>
      <div style="overflow-x:auto"><table><thead><tr><th>Local</th><th class="num">R² sem</th><th class="num">R² com</th><th class="num">Δ R²</th>${t.reconstrucao ? `<th class="num">reconstrói ${esc(t.inspirada_em)}</th>` : ''}</tr></thead><tbody>
        ${Object.keys(g.por_local).map((l) => `<tr><td>${esc(l)}</td><td class="num">${num(t.resumo_sem.por_local[l], 3)}</td><td class="num">${num(t.resumo_com.por_local[l], 3)}</td>
          <td class="num ${g.por_local[l] > 0 ? 'good' : 'bad'}">${sinal(g.por_local[l])}</td>${t.reconstrucao ? `<td class="num">${num(t.reconstrucao.por_local[l], 2)}</td>` : ''}</tr>`).join('')}</tbody></table></div>
      <p class="gate-msg">Base: ${t.base.length} features · pooled ${num(t.resumo_sem.pooled, 3)} → ${num(t.resumo_com.pooled, 3)} · MAE ${num(t.resumo_sem.mae, 1)} → ${num(t.resumo_com.mae, 1)} · ${num(t.segundos, 0)} s</p></div>`;
  }

  function listaDerivadas() {
    if (st.derivErro) return gate('warning', 'Derivadas', esc(st.derivErro));
    const ds = st.derivadas ? st.derivadas.derivadas : [];
    if (!ds.length) return '<p class="hint" style="margin-top:14px">Nenhuma derivada desenhada ainda. As do catálogo curado ficam em <code>core/features.py</code>.</p>';
    return `<div style="margin-top:14px"><h2 style="font-size:13px">Derivadas desenhadas (<code>src/ml/core/derivadas.json</code>)</h2>
      <div style="overflow-x:auto"><table><thead><tr><th>Nome</th><th>Fórmula</th><th>Inspirada em</th><th>Status</th></tr></thead><tbody>
      ${ds.map((d) => `<tr><td><code>${esc(d.nome)}</code><div class="gate-msg">${esc(d.descricao)}</div></td><td><code>${esc(d.formula)}</code></td>
        <td>${d.inspirada_em ? `<code>${esc(d.inspirada_em)}</code>` : '–'}</td>
        <td><span class="tag ${d.status === 'aprovada' ? 'ok' : 'mid'}">${d.status === 'aprovada' ? 'aprovada' : 'hipótese'}</span></td></tr>`).join('')}
      </tbody></table></div></div>`;
  }

  function desenhar() {
    const host = $('#pBody');
    if (!st.ctx || !st.ctx.enabledIds.length) { host.innerHTML = ''; return; }
    lerForm();
    const foco = document.activeElement && document.activeElement.id;
    host.innerHTML = cardParalelos() + cardDesenhista();
    if (foco && foco.startsWith('pf-') && $('#' + foco)) $('#' + foco).focus();
  }

  $('#pBody').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-pacao]');
    if (!b) return;
    const a = b.dataset.pacao;
    if (a === 'analisar') analisar();
    if (a === 'filtro') { st.filtro = b.dataset.f; desenhar(); }
    if (a === 'abrir') { st.aberta = st.aberta === b.dataset.col ? null : b.dataset.col; desenhar(); }
    if (a === 'receita') desenharReceita(st.job.resultado.colunas.find((c) => c.coluna === b.dataset.col));
    if (a === 'previa' || a === 'testar' || a === 'salvar') acao(a);
  });
  $('#mAlvo').addEventListener('change', () => { carregarColunas(); desenhar(); });
  $('#pBody').addEventListener('change', (ev) => {
    if (ev.target.id === 'pBase') { st.base = ev.target.value; desenhar(); }
  });

  V.views.paralelos = {
    // Estado dos contadores mudou: colunas elegíveis e versões mudam junto.
    recarregar() { st.colKey = null; st.derivadas = null; if (st.ctx) { carregarBase(); carregarColunas(); } },
    render(ctx) {
      st.ctx = ctx;
      if (!st.derivadas && !st.derivErro) carregarBase();
      carregarColunas();
      desenhar();
    },
  };
})();
