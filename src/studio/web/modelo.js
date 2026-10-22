/* modelo.js — área Modelo: versões no MLflow do Studio por alvo, treino, promoção e
   reavaliação. Listas de runs, comparações e gráficos ficam na UI do MLflow, aberta
   por link. Estado próprio; studio.js chama render(ctx) a cada mudança. */
(function () {
  'use strict';
  const V = window.VENKO;
  const U = V.util;
  const { esc, num, icone } = U;
  const $ = (s) => document.querySelector(s);

  const ATIVOS = ['na fila', 'rodando'];
  const st = { ctx: null, alvo: 'speedtest_down_mbps', status: null, padroes: null, modelos: {}, painel: null,
               form: null, colunas: null, colunasChave: null, filtro: '', jobs: [], poll: null,
               promo: null, reav: null, erro: null, ocupado: false };

  const nomeAlvo = (a) => U.ALVO[a].rotulo;
  const unidade = (a) => U.ALVO[a].unidade;
  const link = (href, texto) => `<a class="btn" href="${esc(href)}" target="_blank" rel="noopener">${icone('i-external')} ${esc(texto)}</a>`;
  const modelos = () => st.modelos[st.alvo] || { nome: 'studio-' + st.alvo, versoes: [], ativo: null };
  const ativo = () => modelos().ativo;
  const listaHtml = (itens) => '<ul>' + itens.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';

  function alternar(lista, id, ligado) {
    const i = lista.indexOf(id);
    if (ligado && i < 0) lista.push(id);
    if (!ligado && i >= 0) lista.splice(i, 1);
  }

  /* ---------------- carregamento ---------------- */
  function carregarStatus() {
    return U.pedir('api/mlflow/status').then((s) => { st.status = s; })
      .catch((e) => { st.status = { ok: false, erro: e.message }; });
  }

  function carregarModelos(alvo) {
    return U.pedir('api/modelos/' + alvo).then((m) => { st.modelos[alvo] = m; st.erro = null; })
      .catch((e) => { st.erro = e.message; });
  }

  function iniciar() {
    if (st.status) return;
    st.status = { carregando: true };
    Promise.all([carregarStatus(), U.pedir('api/modelos/padroes').then((p) => { st.padroes = p; })])
      .then(() => (st.status.ok ? carregarModelos(st.alvo) : null))
      .catch((e) => { st.erro = e.message; })
      .then(() => { desenhar(); return atualizarJobs(); });
  }

  /* ---------------- jobs ---------------- */
  function agendar() {
    clearTimeout(st.poll);
    if (st.jobs.some((j) => ATIVOS.includes(j.status))) st.poll = setTimeout(atualizarJobs, 2000);
  }

  function atualizarJobs() {
    return U.pedir('api/jobs').then((r) => {
      const antes = new Set(st.jobs.filter((j) => ATIVOS.includes(j.status)).map((j) => j.id));
      st.jobs = r.jobs;
      if (st.jobs.some((j) => antes.has(j.id) && !ATIVOS.includes(j.status))) carregarModelos(st.alvo).then(desenhar);
      agendar();
      desenhar();
    }).catch(agendar);
  }

  /* ---------------- treino ---------------- */
  function abrirTreino() {
    if (!st.padroes) return;
    const modelo = 'RandomForest';
    st.form = { datasets: st.ctx.enabledIds.slice(), features: new Set(), modelo,
                hiper: { ...st.padroes.modelos[modelo] }, regras: { ...st.padroes.regras } };
    st.painel = 'treino';
    st.erro = null;
    carregarColunas();
  }

  function carregarColunas() {
    const chave = st.form.datasets.slice().sort().join(',');
    if (st.colunasChave === chave && st.colunas) { desenhar(); return; }
    st.colunasChave = chave;
    st.colunas = null;
    desenhar();
    if (!st.form.datasets.length) return;
    U.pedir('api/colunas?ds=' + encodeURIComponent(chave))
      .then((r) => { if (st.colunasChave === chave) st.colunas = r.colunas; })
      .catch((e) => { if (st.colunasChave === chave) st.colunas = { erro: e.message }; })
      .finally(desenhar);
  }

  function enviarTreino() {
    const f = st.form;
    const hiper = {};
    Object.entries(f.hiper).forEach(([k, v]) => {
      const n = Number(v);
      hiper[k] = String(v).trim() !== '' && Number.isFinite(n) ? n : v;
    });
    st.ocupado = true; st.erro = null; desenhar();
    U.post('api/treinos', { alvo: st.alvo, datasets: f.datasets, features: [...f.features],
                            modelo: f.modelo, hiper, regras: f.regras })
      .then((job) => { st.jobs = [job].concat(st.jobs); st.painel = null; agendar(); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- promover ---------------- */
  function abrirPromover() {
    st.painel = 'promover';
    st.promo = { versao: '', comp: null };
    st.erro = null;
    desenhar();
  }

  function compararPromo(versao) {
    st.promo = { versao, comp: null };
    desenhar();
    if (!versao) return;
    U.pedir(`api/modelos/${st.alvo}/promover?versao=${encodeURIComponent(versao)}`)
      .then((c) => { if (st.promo && st.promo.versao === versao) st.promo.comp = c; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function confirmarPromo() {
    st.ocupado = true; desenhar();
    U.post(`api/modelos/${st.alvo}/promover`, { versao: st.promo.versao })
      .then(() => { st.painel = null; return carregarModelos(st.alvo); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- reavaliar ---------------- */
  function abrirReavaliar() {
    st.painel = 'reavaliar';
    st.reav = { versao: (ativo() || {}).versao || '', datasets: st.ctx.enabledIds.slice() };
    st.erro = null;
    desenhar();
  }

  function enviarReav() {
    st.ocupado = true; st.erro = null; desenhar();
    U.post(`api/modelos/${st.alvo}/reavaliar`, st.reav)
      .then((job) => { st.jobs = [job].concat(st.jobs); st.painel = null; agendar(); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- desenho ---------------- */
  function cartaoAtivo() {
    const a = ativo();
    if (!a) {
      return `<div class="card"><h2>Versão @ativo</h2>
        <p class="gate-msg">Nenhuma versão promovida para ${esc(nomeAlvo(st.alvo))} ainda. Treine e promova uma.</p></div>`;
    }
    return `<div class="card"><h2>Versão @ativo · v${esc(a.versao)}</h2>
      <p class="resumo">MAE <b>${num(a.mae, 2)}</b> ${esc(unidade(st.alvo))} · R² <b>${num(a.r2, 3)}</b> ·
        ${a.predios} prédios · ${a.linhas} linhas · ${esc(a.modelo || '')}</p>
      ${a.contem_vazamento ? U.gate('warning', 'Treinada com vazamento', 'Usou contadores da janela do speedtest: o erro medido é otimista.') : ''}
      <div class="controls">${link(a.link, 'Abrir versão no MLflow')}${link(a.link_run, 'Abrir run')}</div></div>`;
  }

  function linhaDataset(d, marcado, atributo) {
    return `<label class="ds"><input type="checkbox" ${atributo}="${esc(d.id)}" data-k="${atributo}-${esc(d.id)}"${marcado ? ' checked' : ''}>
      <code>${esc(d.id)}</code>${d.origem === 'upload' ? ' <span class="tag">upload</span>' : ''}
      <span class="gate-msg num">${d.rows.toLocaleString('pt-BR')} linhas</span><span></span></label>`;
  }

  function painelTreino() {
    const f = st.form;
    const ds = st.ctx.data.datasets.map((d) => linhaDataset(d, f.datasets.includes(d.id), 'data-fds')).join('');
    let cols;
    if (!f.datasets.length) cols = '<p class="gate-msg">Escolha pelo menos um dataset.</p>';
    else if (!st.colunas) cols = '<p class="gate-msg">Carregando colunas…</p>';
    else if (st.colunas.erro) cols = U.gate('critical', 'Colunas indisponíveis', esc(st.colunas.erro));
    else {
      const filtro = st.filtro.toLowerCase();
      cols = st.colunas.filter((c) => !filtro || c.coluna.toLowerCase().includes(filtro)).map((c) =>
        `<label class="ds"><input type="checkbox" data-fcol="${esc(c.coluna)}" data-k="fcol-${esc(c.coluna)}"${f.features.has(c.coluna) ? ' checked' : ''}>
          <code>${esc(c.coluna)}</code>${c.vazamento ? ' <span class="tag leak">vazamento</span>' : ''}
          <span class="gate-msg num">${U.pct(c.preenchimento)} preenchido</span><span></span></label>`).join('');
    }
    const a = ativo();
    const hiper = Object.entries(f.hiper).map(([k, v]) =>
      `<label>${esc(k)}<input type="text" data-hiper="${esc(k)}" data-k="hiper-${esc(k)}" value="${esc(v)}"></label>`).join('');
    const regras = Object.keys(st.padroes.regras).map((k) =>
      `<label class="ds"><input type="checkbox" data-regra="${esc(k)}" data-k="regra-${esc(k)}"${f.regras[k] ? ' checked' : ''}>
        <code>${esc(k)}</code><span></span><span></span></label>`).join('');
    const pode = !st.ocupado && f.datasets.length && f.features.size;
    return `<div class="card"><h2>Novo treino · ${esc(nomeAlvo(st.alvo))}</h2>
      <h3>Datasets</h3>${ds}
      <h3>Features (${f.features.size})</h3>
      <div class="controls">
        <input type="search" placeholder="filtrar colunas" data-filtro="1" data-k="filtro" value="${esc(st.filtro)}" aria-label="Filtrar colunas">
        ${a && a.features.length ? '<button class="btn" data-acao="copiar-ativo" data-k="copiar-ativo">Copiar features da @ativo</button>' : ''}
        <button class="btn" data-acao="limpar-features" data-k="limpar-features">Limpar</button></div>
      <div class="lista-colunas">${cols}</div>
      <h3>Modelo</h3>
      <div class="controls"><select data-modelo="1" data-k="modelo" aria-label="Modelo">${Object.keys(st.padroes.modelos).map((m) =>
        `<option${m === f.modelo ? ' selected' : ''}>${esc(m)}</option>`).join('')}</select></div>
      <div class="upload-campos">${hiper}</div>
      <h3>Regras</h3>${regras}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="enviar-treino" data-k="enviar-treino"${pode ? '' : ' disabled'}>${icone('i-play')} Treinar</button></div></div>`;
  }

  function opcoesVersoes(selecionada) {
    return modelos().versoes.map((v) => `<option value="${esc(v.versao)}"${v.versao === selecionada ? ' selected' : ''}>
      v${esc(v.versao)} · ${esc(v.modelo || '')} · MAE ${num(v.mae, 2)}</option>`).join('');
  }

  function painelPromover() {
    const pr = st.promo;
    const c = pr.comp;
    const celula = (r, k, d) => (!r || r[k] == null ? '–' : num(r[k], d));
    const linha = (rotulo, k, d) => `<tr><th>${rotulo}</th><td class="num">${celula(c.candidata, k, d)}</td>
      <td class="num">${celula(c.ativo, k, d)}</td></tr>`;
    const tabela = c ? `<table><thead><tr><th></th><th>v${esc(c.candidata.versao)}</th>
        <th>@ativo${c.ativo ? ' v' + esc(c.ativo.versao) : ''}</th></tr></thead><tbody>
        ${linha('MAE', 'mae', 2)}${linha('RMSE', 'rmse', 2)}${linha('R²', 'r2', 3)}${linha('Prédios', 'predios', 0)}${linha('Linhas', 'linhas', 0)}
      </tbody></table>${c.avisos.length ? U.gate('warning', 'Avisos', listaHtml(c.avisos)) : ''}` : '';
    return `<div class="card"><h2>Promover para @ativo · ${esc(nomeAlvo(st.alvo))}</h2>
      <div class="controls"><select data-promo="1" data-k="promo" aria-label="Versão">
        <option value="">Escolha uma versão</option>${opcoesVersoes(pr.versao)}</select></div>
      ${tabela}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-promo" data-k="confirmar-promo"${c && !st.ocupado ? '' : ' disabled'}>Promover</button></div></div>`;
  }

  function painelReavaliar() {
    const r = st.reav;
    const ds = st.ctx.data.datasets.map((d) => linhaDataset(d, r.datasets.includes(d.id), 'data-rds')).join('');
    return `<div class="card"><h2>Reavaliar sem retreinar · ${esc(nomeAlvo(st.alvo))}</h2>
      <p class="gate-msg">Prevê com a versão escolhida nos datasets marcados e registra um run de reavaliação.
        Datasets que estavam no treino da versão deixam a medida otimista: o Studio avisa.</p>
      <div class="controls"><select data-reav="1" data-k="reav" aria-label="Versão">
        <option value="">Escolha uma versão</option>${opcoesVersoes(r.versao)}</select></div>
      ${ds}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="enviar-reav" data-k="enviar-reav"${r.versao && r.datasets.length && !st.ocupado ? '' : ' disabled'}>
          ${icone('i-play')} Reavaliar</button></div></div>`;
  }

  function secaoJobs() {
    if (!st.jobs.length) return '';
    return `<div class="card"><h2>Jobs</h2><ul class="jobs">${st.jobs.map((j) => {
      const r = j.resultado || {};
      let extra;
      if (j.status === 'falhou') extra = U.gate('critical', 'Falhou', esc(j.erro || ''));
      else if (j.status === 'concluído') {
        extra = `<div class="controls">${r.versao ? `<span class="tag ok">v${esc(r.versao)}</span>` : ''}
            ${r.metricas ? `<span class="gate-msg">MAE ${num(r.metricas.mae, 2)} · R² ${num(r.metricas.r2, 3)}</span>` : ''}
            ${r.link_run ? link(r.link_run, 'Abrir run') : ''}</div>
          ${(r.avisos || []).length ? U.gate('warning', 'Avisos', listaHtml(r.avisos)) : ''}`;
      } else extra = `<span class="gate-msg">${esc(j.etapa || '')}</span>`;
      return `<li><b>${esc(j.descricao)}</b> <span class="tag">${esc(j.status)}</span>${extra}</li>`;
    }).join('')}</ul></div>`;
  }

  function desenhar() {
    const host = $('#mCorpo');
    if (!st.ctx || !host || $('#area-modelo').classList.contains('hide')) return;
    $('#mAlvos').innerHTML = U.ALVOS.map(([k, r]) =>
      `<button data-alvo="${k}" aria-pressed="${k === st.alvo}">${esc(r)}</button>`).join('');
    if (!st.status || st.status.carregando) {
      U.redesenhar(host, '<p class="gate-msg">Conectando ao MLflow do Studio…</p>');
      return;
    }
    if (!st.status.ok) {
      U.redesenhar(host, U.gate('critical', 'MLflow indisponível',
        'O processo do MLflow do Studio não responde. A aba Dados continua funcionando.',
        `<div class="controls"><button class="btn" data-acao="reiniciar" data-k="reiniciar"${st.ocupado ? ' disabled' : ''}>
          ${icone('i-refresh')} Reiniciar MLflow</button></div>`) + (st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : ''));
      return;
    }
    const temVersoes = modelos().versoes.length > 0;
    const botoes = `<div class="controls">
      <button class="btn-pri" data-acao="novo-treino" data-k="novo-treino">${icone('i-play')} Novo treino</button>
      <button class="btn" data-acao="reavaliar" data-k="reavaliar"${temVersoes ? '' : ' disabled'}>Reavaliar</button>
      <button class="btn" data-acao="promover" data-k="promover"${temVersoes ? '' : ' disabled'}>Promover</button>
      ${link(`${st.status.ui}/#/models/${encodeURIComponent(modelos().nome)}`, 'Abrir no MLflow')}</div>`;
    const painel = st.painel === 'treino' ? painelTreino()
      : st.painel === 'promover' ? painelPromover()
        : st.painel === 'reavaliar' ? painelReavaliar() : '';
    U.redesenhar(host, (st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : '') +
      cartaoAtivo() + botoes + painel + secaoJobs());
  }

  /* ---------------- eventos ---------------- */
  document.addEventListener('click', (ev) => {
    if ($('#area-modelo').classList.contains('hide')) return;
    const alvo = ev.target.closest('#mAlvos [data-alvo]');
    if (alvo) {
      st.alvo = alvo.dataset.alvo; st.painel = null; st.erro = null;
      desenhar();
      carregarModelos(st.alvo).then(desenhar);
      return;
    }
    const b = ev.target.closest('#mCorpo [data-acao]');
    if (!b || b.disabled) return;
    const acao = b.dataset.acao;
    if (acao === 'novo-treino') abrirTreino();
    if (acao === 'promover') abrirPromover();
    if (acao === 'reavaliar') abrirReavaliar();
    if (acao === 'fechar-painel') { st.painel = null; desenhar(); }
    if (acao === 'enviar-treino') enviarTreino();
    if (acao === 'confirmar-promo') confirmarPromo();
    if (acao === 'enviar-reav') enviarReav();
    if (acao === 'copiar-ativo') { st.form.features = new Set(ativo().features); desenhar(); }
    if (acao === 'limpar-features') { st.form.features = new Set(); desenhar(); }
    if (acao === 'reiniciar') {
      st.ocupado = true; st.erro = null; desenhar();
      U.post('api/mlflow/reiniciar', {})
        .catch((e) => { st.erro = e.message; })
        .then(carregarStatus)
        .then(() => (st.status.ok ? carregarModelos(st.alvo) : null))
        .finally(() => { st.ocupado = false; desenhar(); });
    }
  });

  document.addEventListener('change', (ev) => {
    const t = ev.target;
    if (!t.closest || !t.closest('#mCorpo')) return;
    if (t.dataset.fds) { alternar(st.form.datasets, t.dataset.fds, t.checked); carregarColunas(); }
    else if (t.dataset.fcol) {
      if (t.checked) st.form.features.add(t.dataset.fcol); else st.form.features.delete(t.dataset.fcol);
      desenhar();
    } else if (t.dataset.modelo) {
      st.form.modelo = t.value; st.form.hiper = { ...st.padroes.modelos[t.value] }; desenhar();
    } else if (t.dataset.regra) st.form.regras[t.dataset.regra] = t.checked;
    else if (t.dataset.promo !== undefined) compararPromo(t.value);
    else if (t.dataset.reav !== undefined) { st.reav.versao = t.value; desenhar(); }
    else if (t.dataset.rds) { alternar(st.reav.datasets, t.dataset.rds, t.checked); desenhar(); }
  });

  document.addEventListener('input', (ev) => {
    const t = ev.target;
    if (!t.closest || !t.closest('#mCorpo')) return;
    if (t.dataset.hiper) st.form.hiper[t.dataset.hiper] = t.value;
    if (t.dataset.filtro) { st.filtro = t.value; desenhar(); }
  });

  V.areas = V.areas || {};
  V.areas.modelo = { render(ctx) { st.ctx = ctx; iniciar(); desenhar(); } };
})();
