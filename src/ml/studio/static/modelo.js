/* modelo.js — área Modelo: versões salvas em cartões, comparação por prédio sob
   demanda, rascunho com chips, avaliação que roda sozinha contra a versão ativa,
   veredito pela régua de promoção e barra fixa para salvar. Estado próprio, em
   memória; studio.js chama render(ctx) a cada mudança do conjunto. */
(function () {
  'use strict';
  const V = window.VENKO;
  const L = V.logica;
  const U = V.util;
  const { esc, num, sinal, icone } = U;
  const $ = (s) => document.querySelector(s);

  const VEREDITO = {
    melhor: { rotulo: 'Melhor', icone: 'i-check', frase: (a) => `Melhor que ${a}` },
    empate: { rotulo: 'Empate', icone: 'i-equal', frase: (a) => `Empate com ${a}` },
    pior: { rotulo: 'Pior', icone: 'i-alert', frase: (a) => `Pior que ${a}` },
  };
  const NOME_OK = /^[a-z0-9][a-z0-9-]{1,39}$/;
  const ATRASO_MS = 800;

  const st = {
    ctx: null, alvo: 'speedtest_down_mbps',
    reg: null, regErro: null, regAviso: null, msg: null, erro: null, menu: null, vereditos: {}, pendente: null, reav: null,
    perfil: 'norma', qoe: null, qoeKey: null, qoeErro: null,
    cols: null, colsKey: null, colsErro: null,
    sug: null, sugKey: null, sugTimer: null,
    base: null, sel: new Set(), desenho: null,
    busca: '', aberto: false, lab: false, destaque: 0, itens: [],
    aval: null, avalKey: null, avalErro: null, avalErroKey: null, avaliando: false, inicio: 0, relogio: null,
    outros: null, outrosKey: null, outrosCarregando: false,
    cmp: null, cmpKey: null, cmpErro: null, comparando: false, cmpAberto: false, metrica: 'r2', cmpHits: null,
    form: null, salvando: false, salvarErro: null, salvarEtapa: null, avisoVaz: null,
    receitas: null, recAberto: false,
    rec: { id: 'razao', colunas: [], montada: null, nome: '', ocupado: false, erro: null, resultado: null, montarKey: null },
  };

  /* ---------------- chaves e atalhos ---------------- */
  const dsIds = () => st.ctx.enabledIds.slice().sort();
  const chaveConj = () => dsIds().join(',') + '|' + st.alvo + '|' + st.ctx.ambiente;
  const queryDe = (alvo) => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(alvo) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);
  const query = () => queryDe(st.alvo);
  const selLista = () => [...st.sel].sort();
  const versao = (nome) => (st.reg ? st.reg.versoes.find((v) => v.nome === nome) : null);
  const ativa = () => versao(st.reg.ativo);
  const featsBase = () => (versao(st.base) || { features: [] }).features;
  const diff = () => L.diffContraBase(featsBase(), (versao(st.base) || {}).vazadas, selLista());
  const sujo = () => { const d = diff(); return d.mais.length + d.menos.length > 0; };
  const igualAtiva = () => L.mesmasFeatures(ativa().features, selLista());
  const pronto = () => !!(st.ctx && st.ctx.enabledIds.length && st.reg);
  // A avaliação depende do conjunto, do rascunho, da base (denominador) e da ativa (referência).
  const chaveAval = () => [chaveConj(), selLista().join(','), st.base, st.reg.ativo].join('|');
  const avalAtual = () => !!st.aval && st.avalKey === chaveAval();
  const promocao = (a) => (a.promocao ? a.promocao.veredito : a.veredito);
  // O QoE não depende do alvo da tela: a chave é a do rascunho mais o perfil.
  const chaveQoe = () => [dsIds().join(','), st.ctx.ambiente, selLista().join(','), st.reg.ativo, st.perfil].join('|');
  const qoeAtual = () => (st.qoe && st.qoeKey === chaveQoe() ? st.qoe : null);
  // Último veredito de QoE de cada versão (para o "Tornar ativa" do cartão); independe do alvo.
  // Inclui a ativa: "melhor contra a ativa antiga" não vale depois que outra versão é ativada.
  const chaveVered = (nome) => [nome, 'qoe', dsIds().join(','), st.ctx.ambiente, st.perfil, st.reg.ativo].join('|');
  const chaveCmp = () => chaveConj() + '|' + st.reg.ativo + '|' + st.reg.versoes.map((v) => v.nome).join(',');

  /* ---------------- carregamento ---------------- */
  function usarBase(nome) {
    st.base = nome;
    const limpo = L.semVazamento(featsBase(), (versao(nome) || {}).vazadas);
    st.sel = new Set(limpo.features);
    st.avisoVaz = limpo.removidas.length ? limpo.removidas : null;
    st.desenho = null; st.form = null; st.salvarErro = null;
  }

  function aplicarRascunho(features, desenhoId) {
    usarBase(st.reg.ativo);
    st.sel = new Set(features);
    st.desenho = desenhoId ? { id: desenhoId, features: features.slice().sort() } : null;
  }

  function carregarRegistro() {
    return U.pedir('api/modelos').then((reg) => {
      st.reg = reg; st.regErro = null; st.regAviso = reg.erro || null;
      if (!st.base || !versao(st.base)) usarBase(reg.ativo);
      if (st.pendente) { aplicarRascunho(st.pendente.features, st.pendente.desenhoId); st.pendente = null; }
    }).catch((e) => { st.regErro = e.message; })
      .finally(() => { agendar(); desenhar(); });
  }

  function carregarColunas() {
    const k = chaveConj();
    if (st.colsKey === k) return;
    st.colsKey = k; st.cols = null; st.colsErro = null;
    U.pedir('api/assistente/colunas?' + query())
      .then((r) => { if (st.colsKey === k) st.cols = r.colunas; })
      .catch((e) => { if (st.colsKey === k) st.colsErro = e.message; })
      .finally(() => { if (st.colsKey === k) desenhar(); });
  }

  function carregarReceitas() {
    if (st.receitas) return;
    st.receitas = [];
    U.pedir('api/receitas').then((r) => { st.receitas = r.receitas; }).catch(() => { st.receitas = null; }).finally(desenhar);
  }

  // Ganho +1 de cada coluna sobre a base, num job do servidor; o grupo "Sugeridas" acompanha.
  function iniciarSugestoes(forcar) {
    if (!pronto() || !st.base) return;
    const k = chaveConj() + '|' + st.base;
    if (st.sugKey === k && !forcar) return;
    st.sugKey = k; st.sug = { status: 'rodando', progresso: [] };
    clearTimeout(st.sugTimer);
    U.pedir('api/assistente/sugestoes?' + query() + '&base=' + encodeURIComponent(st.base), { method: 'POST' })
      .then((r) => acompanhar(r.id, k))
      .catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }

  function acompanhar(id, k) {
    U.pedir('api/assistente/sugestoes/' + id).then((job) => {
      if (st.sugKey !== k) return;
      st.sug = job;
      if (job.status === 'rodando') st.sugTimer = setTimeout(() => acompanhar(id, k), 1500);
      desenhar();
    }).catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }
  const sugPronta = () => (st.sug && st.sug.status === 'pronto' && st.sugKey === chaveConj() + '|' + st.base
    ? st.sug.resultado : null);

  /* ---------------- avaliação reativa ---------------- */
  function urlAvaliar(alvo) {
    return 'api/modelos/avaliar?' + queryDe(alvo) + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&base=' + encodeURIComponent(st.base) + '&contra=' + encodeURIComponent(st.reg.ativo);
  }

  function urlQoe() {
    return 'api/modelos/avaliar_qoe?ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
      '&ambiente=' + encodeURIComponent(st.ctx.ambiente) + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&contra=' + encodeURIComponent(st.reg.ativo) + '&perfil=' + encodeURIComponent(st.perfil);
  }

  // Síncrono no servidor (cerca de 40 s sem cache). Resposta de chave velha é descartada.
  function avaliarQoe() {
    if (!pronto()) return Promise.resolve();
    const k = chaveQoe();
    if (!L.precisaPedirQoe({ temSel: st.sel.size > 0, igualAtiva: igualAtiva(), qoeKey: st.qoeKey, chaveQoe: k })) return Promise.resolve();
    const base = st.base;
    st.qoeKey = k; st.qoe = null; st.qoeErro = null;
    return U.pedir(urlQoe()).then((q) => {
      if (st.qoeKey !== k) return;                     // resposta de rascunho/perfil antigo
      st.qoe = q; st.qoeErro = null;
      if (base === st.base && !sujo()) st.vereditos[chaveVered(base)] = q.promocao_qoe ? q.promocao_qoe.resultado : null;
    }).catch((e) => { if (st.qoeKey === k) st.qoeErro = e.message; }).finally(desenhar);
  }

  function avaliarAgora(k) {
    if (!pronto() || k !== chaveAval()) return Promise.resolve();   // o rascunho já mudou: o próximo voo cuida
    st.avalErro = null;
    avaliarQoe();
    return U.pedir(urlAvaliar(st.alvo)).then((a) => {
      if (k !== chaveAval()) return;                                   // resposta velha
      st.aval = a; st.avalKey = k; st.avaliando = false;
    }).catch((e) => {
      if (k !== chaveAval()) return;
      st.avalErro = e.message; st.avalErroKey = k; st.avaliando = false;
    }).finally(desenhar);
  }

  // Um pedido por vez; mudanças durante um voo viram um único pedido novo, com o estado mais recente.
  const voo = L.vooUnico(avaliarAgora, { atraso: ATRASO_MS });

  function agendar() {
    if (!pronto() || !st.sel.size || igualAtiva()) { st.avaliando = false; voo.cancelar(); return; }
    const k = chaveAval();
    if (st.avalKey === k || st.avalErroKey === k) { st.avaliando = false; avaliarQoe(); return; }   // regressão em cache: o QoE pode ter ficado para trás
    if (!st.avaliando) st.inicio = Date.now();
    st.avaliando = true;
    voo.pedir(k);
  }

  function relogio() {
    if (st.avaliando && !st.relogio) {
      st.relogio = setInterval(() => {
        const el = $('#mRelogio');
        if (el) el.textContent = Math.round((Date.now() - st.inicio) / 1000) + ' s';
      }, 500);
    }
    if (!st.avaliando && st.relogio) { clearInterval(st.relogio); st.relogio = null; }
  }

  function testarOutros() {
    const k = chaveAval();
    st.outrosCarregando = true; desenhar();
    Promise.all(U.ALVOS.filter(([a]) => a !== st.alvo).map(([a]) => U.pedir(urlAvaliar(a))
      .then((r) => ({ alvo: a, resultado: promocao(r).resultado }))
      .catch(() => ({ alvo: a, erro: true }))))
      .then((xs) => { if (k === chaveAval()) { st.outros = xs; st.outrosKey = k; } })
      .finally(() => { st.outrosCarregando = false; desenhar(); });
  }

  /* ---------------- comparação por prédio ---------------- */
  function comparar() {
    if (st.comparando) return;
    const k = chaveCmp();
    st.comparando = true; st.cmpErro = null; desenhar();
    U.pedir('api/modelos/comparar?' + query())
      .then((c) => { st.cmp = c; st.cmpKey = k; })
      .catch((e) => { st.cmpErro = e.message; })
      .finally(() => { st.comparando = false; desenhar(); });
  }

  /* ---------------- salvar e ativar ---------------- */
  function abrirForm(ativar) {
    const a = avalAtual() ? st.aval : null;
    const sufixo = a && a.resumo_base ? `${U.ALVO[st.alvo].rotulo.toLowerCase()}: ${VEREDITO[promocao(a).resultado].rotulo.toLowerCase()}` +
      ` contra ${st.reg.ativo} (R² ${num(a.resumo_base.pooled, 2)}→${num(a.resumo.pooled, 2)})` : '';
    st.form = { ativar, nome: L.sugerirNome(st.reg.ativo, st.reg.versoes.map((v) => v.nome)),
                desc: L.descricaoRascunho(diff(), sufixo) };
    st.salvarErro = null;
    desenhar();
    const el = $('#mNome');
    if (el) el.focus();
  }

  function publicar() {
    const f = st.form;
    st.salvarErro = null; st.msg = null; st.erro = null;
    if (!NOME_OK.test(f.nome)) { st.salvarErro = 'Nome inválido: use minúsculas, dígitos e hífen (2 a 40 caracteres).'; desenhar(); return; }
    if (!f.desc.trim()) { st.salvarErro = 'Escreva uma descrição: ela é o que explica a versão no git log.'; desenhar(); return; }
    // O vínculo com o desenho automático só vale se o rascunho for exatamente o conjunto escolhido.
    const desenho = st.desenho && L.mesmasFeatures(st.desenho.features, selLista()) ? st.desenho.id : null;
    const nome = f.nome;
    const qPub = qoeAtual();   // o veredito de QoE do que está sendo salvo, para lembrar na versão nova
    const verPub = qPub && qPub.promocao_qoe ? qPub.promocao_qoe.resultado : null;
    st.salvando = true; st.salvarEtapa = null; desenhar();
    U.post('api/modelos', { nome, descricao: f.desc, features: selLista(), ds: st.ctx.enabledIds.join(','),
                            ambiente: st.ctx.ambiente, base: st.base, desenho, ativar: !!f.ativar, perfil_qoe: st.perfil })
      .then((r) => acompanharSalvar(r.id, nome, verPub))
      .catch((e) => { st.salvando = false; st.salvarErro = e.message; desenhar(); });
  }

  // O servidor avalia os quatro alvos e o "atende" antes de gravar (1 a 2 minutos). Recarregar a
  // página não cancela: a versão é gravada mesmo assim e aparece no registro quando terminar.
  function acompanharSalvar(id, nome, verPub) {
    U.pedir('api/modelos/salvar/' + id).then((job) => {
      if (job.status === 'rodando') {
        st.salvarEtapa = job.progresso[job.progresso.length - 1] || null;
        desenhar();
        setTimeout(() => acompanharSalvar(id, nome, verPub), 1500);
        return null;
      }
      st.salvando = false; st.salvarEtapa = null;
      if (job.status === 'erro') { st.salvarErro = job.erro; desenhar(); return null; }
      const r = job.resultado;
      if (verPub) st.vereditos[chaveVered(nome)] = verPub;   // ainda com a ativa antiga: a chave é a do veredito que foi dado
      if (r.erro_ativar) st.erro = `Versão ${nome} salva, mas não foi possível ativar: ${r.erro_ativar}`;
      else st.msg = `Versão ${nome} salva${r.ativa ? ' e ativa' : ''} em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
      st.cmpKey = null;
      return U.pedir('api/modelos').then((reg) => { st.reg = reg; usarBase(nome); agendar(); desenhar(); });
    }).catch((e) => { st.salvando = false; st.salvarEtapa = null; st.salvarErro = e.message; desenhar(); });
  }

  function ativarManual(nome) {
    st.menu = null;
    const conhecido = st.vereditos[chaveVered(nome)];
    if (conhecido !== 'melhor') {
      const txt = conhecido
        ? `O último veredito de QoE de ${nome} contra ${st.reg.ativo} foi "${VEREDITO[conhecido].rotulo}".`
        : `Não há veredito de QoE de ${nome} contra ${st.reg.ativo} nesta sessão: clique no cartão para avaliar antes.`;
      if (!window.confirm(`${txt}\n\nTornar ${nome} a versão ativa mesmo assim?`)) { desenhar(); return; }
    }
    st.msg = null; st.erro = null;
    U.post('api/modelos/ativo', { nome })
      .then((reg) => { st.reg = reg; st.msg = `${nome} agora é a versão ativa. Revise src/ml/core/modelos.json no git diff antes do commit.`; })
      .catch((e) => { st.erro = `Não foi possível ativar ${nome}: ${e.message}`; })
      .finally(() => { st.cmpKey = null; agendar(); desenhar(); });
  }

  /* ---------------- reavaliar ---------------- */
  // Mesma régua do selo "desatualizada": a lista que a tela mostra é a que vai para o servidor.
  const desatualizadas = () => st.reg.versoes
    .filter((v) => motivoDesatualizada((v.avaliacao || {})[st.alvo])).map((v) => v.nome);

  function reavaliar(nomes) {
    st.menu = null; st.msg = null; st.erro = null;
    st.reav = { status: 'rodando', progresso: [], total: nomes.length };
    desenhar();
    U.post('api/modelos/reavaliar', { nomes, ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente })
      .then((r) => acompanharReav(r.id))
      .catch((e) => { st.reav = null; st.erro = `Não foi possível reavaliar: ${e.message}`; desenhar(); });
  }

  function acompanharReav(id) {
    U.pedir('api/modelos/reavaliar/' + id).then((job) => {
      if (job.status === 'rodando') {
        st.reav = Object.assign(job, { total: st.reav.total });
        desenhar();
        setTimeout(() => acompanharReav(id), 1500);
        return;
      }
      if (job.status === 'pronto') {
        const n = job.resultado.reavaliadas.length;
        st.msg = `${n} ${n === 1 ? 'versão reavaliada' : 'versões reavaliadas'} em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
      } else {
        st.erro = `A reavaliação parou: ${job.erro}`;
      }
      st.reav = null; st.cmpKey = null;
      // Mesmo com erro, as versões que terminaram já foram gravadas: recarrega o registro.
      carregarRegistro();
    }).catch((e) => { st.reav = null; st.erro = e.message; desenhar(); });
  }

  function barraReav() {
    if (st.reav) {
      const atual = st.reav.progresso[st.reav.progresso.length - 1];
      const feito = atual ? atual.i / st.reav.total : 0;
      return `<div class="reav" role="status">
        <span>${atual ? `Reavaliando <code>${esc(atual.nome)}</code> (${atual.i + 1} de ${st.reav.total})${atual.etapa ? ` · ${esc(atual.etapa)}` : ''}…` : 'Reavaliando…'}</span>
        <span class="ver-barra"><i style="width:${Math.round(feito * 100)}%"></i></span></div>`;
    }
    const n = desatualizadas().length;
    return n ? `<button class="linkbtn link" data-acao="reavaliar-todas" data-k="reavaliar-todas">${icone('i-refresh')}
      Reavaliar ${n} ${n === 1 ? 'desatualizada' : 'desatualizadas'}</button>` : '';
  }

  /* ---------------- receitas ---------------- */
  function montarReceita() {
    const r = st.rec;
    const def = (st.receitas || []).find((x) => x.id === r.id);
    r.montada = null; r.erro = null;
    if (!def) { desenhar(); return; }
    const colunas = r.colunas.slice(0, def.colunas);
    if (colunas.length < def.colunas || colunas.some((c) => !c)) { r.montarKey = null; desenhar(); return; }
    const k = colunas.join('|');
    r.montarKey = k;
    U.post('api/receitas/montar', { receita: r.id, colunas })
      .then((m) => { if (r.montarKey === k) { r.montada = m; r.nome = m.nome; } })
      .catch((e) => { if (r.montarKey === k) r.erro = e.message; })
      .finally(() => { if (r.montarKey === k) desenhar(); });
  }

  function salvarReceita() {
    const r = st.rec;
    r.ocupado = true; r.erro = null; r.resultado = null; desenhar();
    U.post('api/derivadas', { nome: r.nome, formula: r.montada.formula, descricao: r.montada.descricao,
                              base: st.base, ds: st.ctx.enabledIds.join(','), alvo: st.alvo, ambiente: st.ctx.ambiente })
      .then((res) => {
        r.resultado = res;
        st.sel.add(r.nome);
        r.montada = null; r.colunas = []; r.nome = '';
        // A derivada nova muda as colunas de todas as áreas.
        V.app.colunasMudaram();
      })
      .catch((e) => { r.erro = e.message; })
      .finally(() => { r.ocupado = false; desenhar(); });
  }

  function painelReceita() {
    const r = st.rec;
    const def = (st.receitas || []).find((x) => x.id === r.id);
    // Receita é para derivar do TR-181: só insumos padrão ou deriváveis, numéricos e sem vazamento.
    const brutas = (st.cols || []).filter((c) => !c.derivada && c.tr181 && ['padrao', 'derivavel'].includes(c.tr181.status)
      && c.tipo === 'numerica' && !c.vazamento).map((c) => c.coluna);
    const letras = ['A', 'B', 'C'].slice(0, def ? def.colunas : 2);
    const seletores = letras.map((l, i) => `<label for="mCol${i}">${l}</label><select id="mCol${i}" data-rcol="${i}">
      <option value="">— escolha —</option>${brutas.map((b) => `<option${b === r.colunas[i] ? ' selected' : ''}>${esc(b)}</option>`).join('')}</select>`).join('');
    const montada = r.montada ? `<label>Fórmula</label><code>${esc(r.montada.formula)}</code>
      <label for="mRecNome">Nome</label><input id="mRecNome" class="minput" maxlength="40" value="${esc(r.nome)}">` : '';
    let resultado = '';
    if (r.resultado) {
      const ok = r.resultado.status === 'aprovada';
      const falhas = r.resultado.teste.criterios.filter((c) => !c.ok).map((c) => `<li>${esc(c.criterio)}</li>`).join('');
      resultado = U.gate(ok ? 'good' : 'warning',
        ok ? `Aprovada: melhora o ${U.ALVO[st.alvo].rotulo.toLowerCase()} em todos os locais` : 'Hipótese: não passou em todos os critérios',
        (ok ? '' : 'Fica salva e entra no rascunho, mas não é sugerida. ') + 'A métrica já está no rascunho.' + (falhas ? `<ul>${falhas}</ul>` : ''));
    }
    return `<div class="receita"><div class="secao-cab"><h2>Criar métrica a partir de receita</h2>
        <button class="btn-icone" data-acao="fechar-receita" aria-label="Fechar a receita" style="margin-left:auto">${icone('i-x')}</button></div>
      <div class="pform">
        <label for="mReceita">Receita</label><select id="mReceita">${(st.receitas || []).map((x) =>
          `<option value="${x.id}"${x.id === r.id ? ' selected' : ''}>${esc(x.rotulo)}</option>`).join('')}</select>
        ${seletores}${montada}
      </div>
      ${def && def.dica ? `<p class="gate-msg" style="margin-top:6px">${esc(def.dica)}</p>` : ''}
      <div class="controls" style="margin-top:10px">
        <button class="btn-pri" data-acao="salvar-receita"${!r.montada || r.ocupado ? ' disabled' : ''}>${r.ocupado ? 'Testando…' : 'Testar e salvar'}</button>
        ${r.ocupado ? '<span class="gate-msg">o teste de aceite leva cerca de 1 minuto</span>' : ''}
      </div>
      ${r.erro ? U.gate('critical', 'Não deu', esc(r.erro)) : ''}${resultado}</div>`;
  }

  /* ---------------- versões ---------------- */
  function motivoDesatualizada(av) {
    if (!av) return 'sem avaliação salva para este alvo';
    const motivos = [];
    if (JSON.stringify((av.datasets || []).slice().sort()) !== JSON.stringify(dsIds())) motivos.push('datasets diferentes');
    if ((av.ambiente || 'todos') !== st.ctx.ambiente) motivos.push('ambiente diferente');
    if (av.versao_tabela !== st.reg.versao_tabela) motivos.push('classificação de colunas mudou');
    if (av.versao_catalogo !== st.reg.versao_catalogo) motivos.push('catálogo de derivadas mudou');
    if (av.versao_regua !== st.reg.versao_regua) motivos.push('régua de avaliação mudou');
    return motivos.join(', ');
  }

  function seloEficiencia(v) {
    const valor = (v.denominador || {})[st.alvo];
    if (!valor) return '';
    // Texto: eficiência em todas as linhas. {coluna, radio}: só nas linhas dessa banda.
    const den = typeof valor === 'string' ? valor : valor.coluna;
    const radio = typeof valor === 'string' ? '' : valor.radio;
    const banda = radio === '5ghz' ? '5 GHz' : radio === '2.4ghz' ? '2,4 GHz' : radio;
    const titulo = `prevê a eficiência (alvo ÷ ${den})${banda ? ` só em ${banda}, absoluto nas demais bandas` : ''} e volta para Mbps`;
    return `<span class="tag mid" title="${esc(titulo)}">eficiência${banda ? ` (${esc(banda)})` : ''}</span>`;
  }

  function cartao(v) {
    const nota = L.notaCartao(v);
    const media = nota.valor;
    const motivo = motivoDesatualizada((v.avaliacao || {})[st.alvo]);
    const editando = v.nome === st.base;
    const selos = [U.tagNivel(v.cobertura),
      (v.vazadas || []).length ? `<span class="tag leak" title="${esc(v.vazadas.join(', '))}">${v.vazadas.length} c/ vazamento</span>` : '',
      seloEficiencia(v),
      ((v.avaliacao || {}).qoe || {}).perfil ? `<span class="tag" title="limiares do QoE desta versão">${v.avaliacao.qoe.perfil === 'norma' ? 'norma' : 'perfil atual'}</span>` : '',
      (((v.avaliacao || {}).qoe || {}).supera_piso === false) ? '<span class="tag leak" title="não supera o classificador só com radio">abaixo do piso</span>' : '',
      motivo ? `<span class="tag lab" title="${esc(motivo)}">desatualizada</span>` : '',
      `<span class="tag">${v.features.length} feat.</span>`].join(' ');
    return `<div class="ver${editando ? ' base' : ''}">
      <button class="ver-corpo" data-acao="base" data-nome="${esc(v.nome)}" data-k="ver-${esc(v.nome)}" aria-pressed="${editando}"
        title="${esc(v.descricao || '')}">
        <span class="ver-nome"><code>${esc(v.nome)}</code>${v.ativo ? ' <span class="tag ativa">ativa</span>' : ''}${editando ? ' <span class="tag editando">editando</span>' : ''}</span>
        <span class="ver-num">${media == null ? '–' : num(media, 2)} <small>${esc(nota.rotulo)}</small>${nota.secundario == null ? '' : ` <small class="gate-msg">atende ${num(nota.secundario, 2)}</small>`}</span>
        <span class="ver-barra"><i style="width:${media == null ? 0 : Math.round(media * 100)}%"></i></span>
        <span class="ver-selos">${selos}</span>
      </button>
      <button class="btn-icone ver-menu" data-acao="menu" data-nome="${esc(v.nome)}" data-k="menu-${esc(v.nome)}"
        aria-haspopup="menu" aria-expanded="${st.menu === v.nome}" aria-label="Mais ações para ${esc(v.nome)}">${icone('i-more')}</button>
      ${st.menu === v.nome ? `<div class="menu" role="menu">
        <button role="menuitem" data-acao="reavaliar" data-nome="${esc(v.nome)}"${st.reav ? ' disabled' : ''}>Reavaliar</button>
        ${v.ativo ? '' : `<button role="menuitem" data-acao="ativar" data-nome="${esc(v.nome)}">Tornar ativa</button>`}</div>` : ''}
    </div>`;
  }

  function secaoVersoes() {
    return `<div class="secao"><div class="secao-cab"><h2>Versões</h2>${barraReav()}
        <button class="linkbtn link" data-acao="comparar" aria-expanded="${st.cmpAberto}">${icone('i-bars')} Comparar por prédio</button></div>
      ${st.msg ? U.gate('good', 'Feito', esc(st.msg)) : ''}${st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : ''}
      <div class="vers">${st.reg.versoes.map(cartao).join('')}</div></div>`;
  }

  function secaoComparar() {
    const atual = st.cmp && st.cmpKey === chaveCmp();
    let status = '';
    if (st.comparando) status = 'calculando… leva cerca de 20 s';
    else if (st.cmpErro) status = `<span style="color:var(--critical)">${esc(st.cmpErro)}</span>`;
    else if (atual) status = `${num(st.cmp.segundos, 0)} s`;
    else if (st.cmp) status = 'desatualizada: o conjunto, o alvo ou as versões mudaram';
    let corpo = '';
    if (st.cmp) {
      const u = U.ALVO[st.cmp.alvo].unidade;
      corpo = `<div class="${atual ? '' : 'stale'}">
        <div class="controls" style="margin-bottom:8px">
          <button class="toggle" data-acao="metrica" data-m="r2" aria-pressed="${st.metrica === 'r2'}"><span class="dot"></span> R² por local</button>
          <button class="toggle" data-acao="metrica" data-m="mae" aria-pressed="${st.metrica === 'mae'}"><span class="dot"></span> MAE por local (${u})</button>
        </div>
        <div class="chartwrap"><canvas id="mCmp"></canvas><div class="tooltip" id="mCmpTip"></div></div>
        <div class="serieskey">${st.cmp.locais.map((p, i) => `<span><i style="background:var(--s${i % 5 + 1})"></i>${esc(p)}</span>`).join('')}</div>
        <p class="hint" style="margin-top:10px">${st.metrica === 'r2'
          ? 'A barra vertical é a média dos R² por local. Um local com pouca variância no alvo puxa o R² dele muito para baixo; o MAE não tem esse problema.'
          : `MAE em ${u}: menor é melhor. A barra vertical é o MAE de todas as previsões fora do fold juntas.`}</p>
        ${st.cmp.avisos.map((a) => `<p class="gate-msg">${esc(a)}</p>`).join('')}</div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Comparação por prédio</h2>
        <p class="hint">Todas as versões, mais duas referências: <b>TR-069 completo</b> (todas as colunas TR-069 elegíveis) e
          <b>Tudo</b> (inclui sniffer e cliente, só laboratório). Cada prédio fica de fora uma vez.</p></div>
      <div style="text-align:right"><button class="btn" data-acao="recomparar"${st.comparando ? ' disabled' : ''}>Comparar de novo</button>
        <div class="status">${status}</div></div></div>${corpo}</div>`;
  }

  function desenharComparacao() {
    const canvas = $('#mCmp');
    if (!canvas || !st.cmp) return;
    const c = st.cmp;
    const r2 = st.metrica === 'r2';
    const linha = (rotulo, sub, res) => ({
      label: rotulo, sub, mean: r2 ? res.media : res.mae,
      points: c.locais.map((p, i) => ({ key: p, v: (r2 ? res.por_local : res.mae_por_local || {})[p], color: U.cssv('--s' + (i % 5 + 1)) }))
        .filter((p) => p.v != null),
    });
    const sub = (res) => `${res.n} feat. · pooled ${num(res.pooled, 2)} · MAE ${num(res.mae, 1)}` +
      ((res.removidas_por_vazamento || []).length ? ` · sem ${res.removidas_por_vazamento.length} com vazamento` : '');
    const linhas = c.versoes.map((v) => linha(v.nome + (v.ativo ? ' (ativa)' : ''), sub(v), v))
      .concat([linha('TR-069 completo', sub(c.referencias.tr069), c.referencias.tr069),
               linha('Tudo (laboratório)', sub(c.referencias.tudo), c.referencias.tudo)]);
    st.cmpHits = V.drawDotRows(canvas, { rows: linhas, fmt: (v) => num(v, r2 ? 2 : 1), fmtMean: (v) => num(v, r2 ? 3 : 1),
      floor: r2 ? -1 : null });
    V.attachTooltip(canvas, $('#mCmpTip'), () => st.cmpHits,
      (h) => `<b>${esc(h.label)}</b>${esc(h.at)}: ${r2 ? 'R² ' + num(h.value, 3) : 'MAE ' + num(h.value, 1) + ' ' + U.ALVO[c.alvo].unidade}`);
  }

  /* ---------------- rascunho ---------------- */
  function chip(f, c, novo, carregado) {
    const ausente = carregado && !c;
    const bloq = !!c && !c.liberada;
    const motivo = ausente ? 'ausente neste conjunto' : bloq ? c.motivo : '';
    const status = c ? (U.STATUS_TR181[(c.tr181 || {}).status] || U.STATUS_TR181.desconhecido)[1] : '';
    const dica = [c && c.descricao, status].filter(Boolean).join(' · ');
    return `<span class="fchip${novo ? ' novo' : ''}${ausente ? ' ausente' : ''}${bloq ? ' bloq' : ''}" title="${esc(dica)}">
      <i class="dot ${c ? L.corTr181(c.tr181) : 'lab'}"></i><code>${esc(f)}</code>${motivo ? `<span class="fchip-motivo">${esc(motivo)}</span>` : ''}
      <button class="fchip-x" data-acao="tirar" data-col="${esc(f)}" aria-label="Tirar ${esc(f)} do rascunho">${icone('i-x')}</button></span>`;
  }

  function chipRemovido(f, c) {
    const volta = !c || c.liberada;   // uma coluna bloqueada sai, mas não volta
    return `<span class="fchip removido"><code>${esc(f)}</code>${volta ? `<button class="fchip-x" data-acao="voltar" data-col="${esc(f)}"
      aria-label="Devolver ${esc(f)} ao rascunho" title="Desfazer">${icone('i-undo')}</button>` : ''}</span>`;
  }

  // O assistente roda um ajuste por coluna candidata: só quando alguém pede.
  function statusSugestoes(n) {
    const botao = (rotulo) => `<button class="linkbtn link" data-acao="refazer-sug" data-k="refazer-sug">${rotulo}</button>`;
    if (!st.sug) return botao('sugerir features') + ' (roda em segundo plano)';
    if (st.sug.status === 'rodando') {
      const u = st.sug.progresso && st.sug.progresso[st.sug.progresso.length - 1];
      return `calculando sugestões…${u ? ` ${u.feito}/${u.total}` : ''}`;
    }
    if (st.sug.status === 'erro') return 'sugestões indisponíveis · ' + botao('tentar de novo');
    if (st.sugKey !== chaveConj() + '|' + st.base) return 'sugestões de outro conjunto ou base · ' + botao('atualizar');
    return n ? '' : 'nenhuma agora';
  }

  function listaAdicionar() {
    if (!st.cols) return '<div class="drop"><p class="hint" style="padding:8px 12px">Carregando colunas…</p></div>';
    const g = L.agruparColunas(st.cols, selLista(), sugPronta(), st.busca);
    const total = g.sugeridas.length + g.tr069.length + (st.lab ? g.laboratorio.length : 0);
    st.destaque = Math.min(st.destaque, Math.max(0, total - 1));
    st.itens = [];
    const op = (c) => {
      const i = st.itens.length;
      st.itens.push(c.coluna);
      const gn = g.ganho[c.coluna];
      return `<li role="option" id="mOp-${i}" class="op${i === st.destaque ? ' hl' : ''}" aria-selected="${i === st.destaque}"
        data-acao="por" data-col="${esc(c.coluna)}"><i class="dot ${L.corTr181(c.tr181)}"></i><code>${esc(c.coluna)}</code>
        <span class="op-ganho">${gn ? sinal(gn.delta, 3) : ''}</span></li>`;
    };
    const cap = (t, extra) => `<li class="cap" role="presentation">${t}${extra || ''}</li>`;
    const nada = '<li class="vazio-op" role="presentation">nada com esse filtro</li>';
    return `<ul class="drop" id="mLista" role="listbox" aria-label="Features para adicionar">
      ${cap('Sugeridas: melhoram em todos os prédios', ` <span class="cap-status">${statusSugestoes(g.sugeridas.length)}</span>`)}${g.sugeridas.map(op).join('')}
      ${cap('Outras TR-069')}${g.tr069.map(op).join('') || nada}
      ${cap(`Laboratório (sniffer, cliente): ${g.laboratorio.length} colunas`, ` <button class="linkbtn link" data-acao="lab">${st.lab ? 'esconder' : 'mostrar'}</button>`)}${st.lab ? g.laboratorio.map(op).join('') : ''}
      <li class="cap rodape" role="presentation"><button class="linkbtn link" data-acao="abrir-receita">${icone('i-plus')} Criar métrica a partir de receita</button></li></ul>`;
  }

  function caixaAdicionar() {
    const lista = st.aberto ? listaAdicionar() : '';
    const ativo = st.aberto && st.itens.length ? ` aria-activedescendant="mOp-${st.destaque}"` : '';
    return `<div class="add">${icone('i-search')}
      <input id="mBusca" type="text" role="combobox" aria-expanded="${st.aberto}" aria-controls="mLista" aria-autocomplete="list"
        aria-label="Adicionar feature" placeholder="Adicionar feature…" autocomplete="off" spellcheck="false" value="${esc(st.busca)}"${ativo}></div>${lista}`;
  }

  function blocoCorrelacoes() {
    const c = st.aval && st.aval.correlacoes;
    if (!c || !c.colunas.length) return '';
    const cor = (v) => {
      if (v == null) return 'background:var(--grid)';
      return `background:color-mix(in srgb, var(${v >= 0 ? '--s1' : '--s2'}) ${Math.round(Math.abs(v) * 85)}%, transparent)`;
    };
    const cab = c.colunas.map((x, i) => `<th class="rot" title="${esc(x)}"><span>${i + 1}</span></th>`).join('');
    const linhas = c.colunas.map((a, i) => `<tr><th class="lin"><span class="gate-msg">${i + 1}</span> <code>${esc(a)}</code></th>` +
      c.matriz[i].map((v, j) => `<td class="hm" style="${cor(i === j ? null : v)}" title="${esc(a)} × ${esc(c.colunas[j])}: ${v == null ? '–' : num(v, 2)}">${i === j || v == null ? '' : num(v, 1)}</td>`).join('') + '</tr>').join('');
    return `<details class="fold${avalAtual() ? '' : ' stale'}" data-k="corr"><summary>Correlações <span>· ${c.redundantes.length} par(es) redundante(s), |ρ| ≥ 0,9</span></summary>
      <div class="inner"><p class="gate-msg">Spearman entre pares. Azul: sobem juntas; laranja: uma sobe quando a outra desce. Um par redundante carrega quase a mesma informação: um deles pode sair sem perda.</p>
        ${c.redundantes.length ? `<p class="gate-msg"><b>Redundantes:</b> ${c.redundantes.map((r) => `<code>${esc(r.a)}</code> × <code>${esc(r.b)}</code> (${num(r.rho, 2)})`).join(' · ')}</p>` : ''}
        <div style="overflow-x:auto;margin-top:10px"><table class="heat"><thead><tr><th></th>${cab}</tr></thead><tbody>${linhas}</tbody></table></div>
        ${c.fora.length ? `<p class="gate-msg" style="margin-top:8px">Fora da matriz (categóricas ou constantes): <code>${esc(c.fora.join(', '))}</code></p>` : ''}</div></details>`;
  }

  function painelFeatures() {
    if (st.colsErro) return `<div class="card">${U.gate('critical', 'Não foi possível carregar as colunas', esc(st.colsErro))}</div>`;
    const porNome = st.cols ? Object.fromEntries(st.cols.map((c) => [c.coluna, c])) : {};
    const d = diff();
    const chips = selLista().map((f) => chip(f, porNome[f], d.mais.includes(f), !!st.cols)).join('') +
      d.menos.map((f) => chipRemovido(f, porNome[f])).join('');
    return `<div class="card painel-feat">
      <div class="add-wrap">${caixaAdicionar()}</div>
      <div class="chips" aria-label="Features no rascunho">${chips || '<p class="hint">Nenhuma feature: adicione pelo campo acima.</p>'}</div>
      <div class="legenda-tr"><span><i class="dot ok"></i>TR-069 padrão</span><span><i class="dot mid"></i>proxy ou extensão</span>
        <span><i class="dot lab"></i>laboratório (não vai para produção)</span></div>
      ${blocoCorrelacoes()}
      ${st.recAberto ? painelReceita() : ''}
    </div>`;
  }

  /* ---------------- veredito ---------------- */
  function outrosAlvos() {
    if (!st.outros || st.outrosKey !== chaveAval()) {
      return `<button class="btn" data-acao="outros"${st.outrosCarregando ? ' disabled' : ''}>${st.outrosCarregando ? 'Calculando…' : 'Calcular nos outros alvos'}</button>
        <span class="gate-msg">Só informativo; leva cerca de 1 min.</span>`;
    }
    return `<p class="gate-msg">${st.outros.map((o) => `${U.ALVO[o.alvo].rotulo}: ${o.erro ? 'erro' : VEREDITO[o.resultado].rotulo}`).join(' · ')}</p>`;
  }

  function cartaoVeredito(a, atual) {
    const p = a.promocao;
    const v = promocao(a);
    const r2 = a.veredito;
    const d = a.delta;
    const u = U.ALVO[a.alvo].unidade;
    const faixa = (iv, casas) => (iv ? ` <em>${num(iv[0], casas)} a ${num(iv[1], casas)}</em>` : '');
    const kpis = p && p.delta_pinball
      ? [['Δ pinball p90', `${sinal(p.delta_pinball.valor, 2)} ${u}`, faixa(p.delta_pinball.intervalo, 2)],
         ['Cobertura p90', num(p.cobertura, 2), ''],
         ['R² melhora em', `${d.melhora} de ${d.locais}`, ' <em>prédios</em>']]
      : [['Δ atende', p && p.delta_atende ? sinal(p.delta_atende.valor, 3) : '–', p && p.delta_atende ? faixa(p.delta_atende.intervalo, 3) : ''],
         ['Δ MAE', p ? `${sinal(p.delta_mae.valor, 1)} ${u}` : '–', p ? faixa(p.delta_mae.intervalo, 1) : ''],
         ['R² melhora em', `${d.melhora} de ${d.locais}`, ' <em>prédios</em>']];
    const locais = Object.keys(a.resumo.por_local).map((s) => `<tr><td>${esc(s)}</td>
      <td class="num">${num(a.resumo_base.por_local[s], 3)}</td><td class="num">${num(a.resumo.por_local[s], 3)}</td>
      <td class="num">${sinal(d.por_local[s])}</td>
      <td class="num">${num(a.resumo_base.mae_por_local[s], 1)}</td><td class="num">${num(a.resumo.mae_por_local[s], 1)}</td></tr>`).join('');
    const contra = v.predios_contra || [];
    return `<div class="${atual ? '' : 'stale'}">
      <div class="veredito ${v.resultado}">${icone(VEREDITO[v.resultado].icone)}
        <div><b>${esc(VEREDITO[v.resultado].frase(st.reg.ativo))}</b> <span class="gate-msg">(ativa)</span>
          ${r2 && r2.provisorio ? ` <span class="tag mid" title="${esc(r2.motivos_provisorio.join('; '))}">provisório</span>` : ''}
          ${atual ? '' : ' <span class="tag lab">desatualizado</span>'}
          <div class="gate-msg">${esc(v.motivo)}</div></div></div>
      <div class="kpis">${kpis.map(([t, b, e]) => `<div><span>${t}</span><b>${b}</b>${e}</div>`).join('')}</div>
      ${contra.length ? `<details class="fold" data-k="contra"><summary>Piora em <span>· ${esc(contra.join(', '))}</span></summary>
        <div class="inner">A régua diz o resultado geral, mas estes prédios pioram com o rascunho.</div></details>` : ''}
      <details class="fold" data-k="locais"><summary>Por prédio</summary><div class="inner" style="overflow-x:auto"><table>
        <thead><tr><th>Local de coleta</th><th class="num">R² ativa</th><th class="num">R² rascunho</th><th class="num">Δ R²</th>
        <th class="num">MAE ativa</th><th class="num">MAE rascunho</th></tr></thead><tbody>${locais}</tbody></table></div></details>
      <details class="fold" data-k="outros"><summary>Nos outros alvos</summary><div class="inner">${outrosAlvos()}</div></details>
      <details class="fold" data-k="cob"><summary>Cobertura TR-069 <span>· ${U.tagNivel(a.cobertura)} ${a.cobertura.lacunas.length} lacuna(s)</span></summary>
        <div class="inner">${a.cobertura.lacunas.length ? a.cobertura.lacunas.map(U.tagLacuna).join(' ') : 'Todas as features têm caminho TR-181 padrão.'}</div></details>
      <p class="gate-msg nota-atende">O "atende" daqui usa os limiares de <code>src/ml/core/aplicacoes.json</code>, não os da área Dados.</p>
    </div>`;
  }

  const PERFIS = [['norma', 'Norma'], ['atual', 'Atual']];

  function seletorPerfil() {
    return `<div class="seg" role="group" aria-label="Limiares do QoE">${PERFIS.map(([p, r]) =>
      `<button data-acao="perfil" data-p="${p}" data-k="perfil-${p}" aria-pressed="${st.perfil === p}"${st.salvando ? ' disabled' : ''}>${r}</button>`).join('')}</div>`;
  }

  function tabelaLimiares(q) {
    const chaves = [['dn', 'Download', 'Mbps'], ['up', 'Upload', 'Mbps'], ['lat', 'Latência', 'ms'], ['jit', 'Jitter', 'ms']];
    const linhas = Object.keys(q.limiares).map((app) => `<tr><td>${esc(app)}</td>${chaves.map(([c, , u]) => {
      const f = ((q.fontes || {})[app] || {})[c];
      const titulo = f ? [f.fonte, f.nota].filter(Boolean).join(' · ') : 'perfil atual (aplicacoes.json)';
      const valor = `${num(q.limiares[app][c], 1)} ${u}`;
      const link = f && typeof f.url === 'string' && /^https?:\/\//.test(f.url);
      return `<td class="num" title="${esc(titulo)}">${link ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${valor}</a>` : valor}</td>`;
    }).join('')}</tr>`).join('');
    return `<table><thead><tr><th>Aplicação</th>${chaves.map(([, r]) => `<th class="num">${r}</th>`).join('')}</tr></thead><tbody>${linhas}</tbody></table>`;
  }

  function blocoQoe() {
    const q = qoeAtual();
    if (st.qoeErro && st.qoeKey === chaveQoe()) return U.gate('critical', 'Não foi possível avaliar o QoE', `${esc(st.qoeErro)} Tente de novo; se persistir, mude o rascunho ou o perfil.
      <button class="btn" data-acao="qoe-repetir" data-k="qoe-repetir">Tentar de novo</button>`);
    if (!q) return '<p class="hint" role="status">Avaliando QoE (classificador por aplicação, cerca de 1 min)…</p>';
    const v = q.promocao_qoe;
    const faixa = (iv) => (iv ? ` <em>${num(iv[0], 3)} a ${num(iv[1], 3)}</em>` : '');
    const kpis = [['QoE rascunho', num(q.modelo.nota, 3), faixa(q.modelo.intervalo)],
                  ['QoE ativa', v ? num(v.nota_base, 3) : '–', ''],
                  ['RF referência', num(q.referencia.nota, 3), ''],
                  ['Piso (só radio)', q.piso ? num(q.piso.nota, 3) : '–', '']];
    const alarmes = Object.entries(q.modelo.por_predio).flatMap(([s, apps]) => Object.entries(apps)
      .filter(([, x]) => x.classes === 1).map(([app, x]) => `${esc(s)} · ${esc(app)}: ${num(x.erro * 100, 1)}% ${x.atende ? 'alarme falso' : 'perda'}`));
    return `<div class="qoe">
      ${v ? `<div class="veredito ${v.resultado}">${icone(VEREDITO[v.resultado].icone)}
        <div><b>QoE: ${esc(VEREDITO[v.resultado].frase(st.reg.ativo))}</b> <span class="gate-msg">(decide a ativação)</span>
          <div class="gate-msg">${esc(v.motivo)}</div></div></div>` : ''}
      ${q.supera_piso === false ? U.gate('warning', 'Não supera o piso', 'O rascunho não decide melhor que um classificador que só sabe a banda (radio).') : ''}
      <div class="kpis">${kpis.map(([t, b, e]) => `<div><span>${t}</span><b>${b}</b>${e}</div>`).join('')}</div>
      <p class="gate-msg">Nota: média por prédio da acurácia balanceada, nos ${q.modelo.predios_na_nota.length} prédios com as duas classes
        (${q.modelo.n_posicoes} posições). Fora da nota: ${q.modelo.predios_fora_da_nota.map(esc).join(', ') || 'nenhum'}.</p>
      ${alarmes.length ? `<details class="fold" data-k="qoe-alarmes"><summary>Prédios de uma classe só</summary><div class="inner">${alarmes.join('<br>')}</div></details>` : ''}
      <details class="fold" data-k="qoe-limiares"><summary>Limiares do perfil ${esc(q.perfil)}</summary><div class="inner" style="overflow-x:auto">${tabelaLimiares(q)}</div></details>
    </div>`;
  }

  function painelVeredito() {
    if (!st.sel.size) return '<p class="hint">Adicione features para avaliar.</p>';
    if (igualAtiva()) {
      return `<div class="veredito igual">${icone('i-equal')}<div><b>Igual à versão ativa</b>
        <div class="gate-msg">O rascunho tem as mesmas features de ${esc(st.reg.ativo)}. Mude alguma, ou clique noutro cartão, para ver o efeito.</div></div></div>`;
    }
    const vivo = st.avaliando ? `<div class="ao-vivo"><span class="giro" aria-hidden="true"></span>
      <span role="status">Reavaliando com a última mudança…</span>
      <span id="mRelogio" aria-hidden="true">${Math.round((Date.now() - st.inicio) / 1000)} s</span></div>` : '';
    const bq = blocoQoe();   // o QoE decide a ativação: aparece mesmo sem o resultado da regressão
    if (st.avalErro && !st.avaliando) return bq + U.gate('critical', 'Não foi possível avaliar', esc(st.avalErro));
    if (!st.aval) return vivo + bq + (vivo ? '' : '<p class="hint">Preparando a avaliação…</p>');
    return vivo + bq + cartaoVeredito(st.aval, avalAtual());
  }

  function secaoRascunho() {
    const criticos = L.avisosConjunto(st.ctx.data, st.ctx.rows, st.ctx.enabled, st.ctx.ambiente).filter((a) => a.sev === 'critical');
    return `<div class="secao"><div class="secao-cab"><h2>Rascunho a partir de <code>${esc(st.base)}</code></h2>
        ${seletorPerfil()}
        ${st.desenho ? '<span class="tag current" title="ao salvar, a versão guarda a nota aninhada e os passos da seleção">do desenho automático</span>' : ''}</div>
      ${st.avisoVaz ? U.gate('warning', `${st.avisoVaz.length} ${st.avisoVaz.length === 1 ? 'coluna' : 'colunas'} com vazamento fora do rascunho`,
        `<code>${st.avisoVaz.map(esc).join('</code>, <code>')}</code> estão em ${esc(st.base)}, mas hoje são marcadas como vazamento
        (contadores da janela do speedtest carregam o próprio resultado). Uma versão nova não pode usá-las.`) : ''}
      <div class="ed">${painelFeatures()}
        <div class="painel-ver">${criticos.map((a) => U.gate('critical', esc(a.titulo), esc(a.msg))).join('')}${painelVeredito()}</div></div></div>`;
  }

  /* ---------------- barra fixa ---------------- */
  const textoSalvando = () => (st.salvarEtapa
    ? `Avaliando ${st.salvarEtapa.etapa} (${st.salvarEtapa.passo + 1} de ${st.salvarEtapa.passos})…` : 'Salvando…');

  function formSalvar() {
    const f = st.form;
    return `<div class="dock-form">
      <label for="mNome">Nome</label><input id="mNome" class="minput" maxlength="40" value="${esc(f.nome)}">
      <label for="mDesc">Descrição</label><input id="mDesc" class="minput" maxlength="500" value="${esc(f.desc)}">
      ${st.salvarErro ? `<p class="dock-erro" role="alert">${esc(st.salvarErro)}</p>` : ''}
      ${st.salvando ? '<p class="hint" role="status">Leva de 2 a 3 minutos. Recarregar a página não cancela: a versão é gravada mesmo assim.</p>' : ''}
      <div class="dock-form-acoes"><button class="btn" data-acao="cancelar-salvar"${st.salvando ? ' disabled' : ''}>Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-salvar"${st.salvando ? ' disabled' : ''}>${st.salvando ? textoSalvando() : f.ativar ? 'Salvar e tornar ativa' : 'Salvar versão'}</button></div></div>`;
  }

  // Por que "Salvar e tornar ativa" está desabilitado: o QoE ainda roda, falhou, ou a trava diz.
  function motivoDock(q, pode) {
    if (!q && st.sel.size && !igualAtiva()) {
      return st.qoeErro && st.qoeKey === chaveQoe() ? `QoE falhou: ${st.qoeErro} (use "Tentar de novo" no painel)` : 'Avaliando QoE…';
    }
    return st.avaliando ? 'Reavaliando o rascunho…' : pode.motivo;
  }

  function dock() {
    const el = $('#mDock');
    const mostrar = pronto() && !!st.base && sujo();
    el.classList.toggle('hide', !mostrar);
    if (!mostrar) { el.innerHTML = ''; return; }
    const d = diff();
    const atual = avalAtual();
    const q = qoeAtual();
    const v = q && q.promocao_qoe ? q.promocao_qoe : null;
    const pode = L.podeAtivar(st.aval, atual, q);
    const estado = st.avaliando ? '<span class="dock-ver">avaliando…</span>'
      : v ? `<span class="dock-ver ${v.resultado}">${icone(VEREDITO[v.resultado].icone)} ${VEREDITO[v.resultado].rotulo}</span>` : '';
    U.redesenhar(el, `<div class="dock-linha">
        <span><b>Rascunho</b> <span class="dock-sub">de ${esc(st.base)}</span></span>
        <span class="dock-mais" title="${esc(d.mais.join(', '))}">+${d.mais.length}</span>
        <span class="dock-menos" title="${esc(d.menos.join(', '))}">−${d.menos.length}</span>${estado}
        <span class="dock-acoes">
          <button class="btn" data-acao="descartar" data-k="descartar">Descartar</button>
          <button class="btn" data-acao="abrir-salvar" data-k="abrir-salvar"${st.sel.size ? '' : ' disabled'}>Salvar…</button>
          <button class="btn-pri" data-acao="abrir-ativar" data-k="abrir-ativar"${pode.ok ? '' : ' disabled'} aria-describedby="mDockMotivo">Salvar e tornar ativa</button>
        </span></div>
      ${pode.ok ? '' : `<p class="dock-motivo" id="mDockMotivo" role="status">${esc(motivoDock(q, pode))}</p>`}
      ${st.form ? formSalvar() : ''}`);
  }

  /* ---------------- composição ---------------- */
  function desenhar() {
    if (!st.ctx) return;
    document.querySelectorAll('#mAlvos [data-alvo]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.alvo === st.alvo)));
    let html;
    if (!st.ctx.enabledIds.length) {
      html = '<div class="vazio"><p>Nenhum dataset ativo.</p><button class="btn-pri" data-acao="conjunto">Abrir Conjunto</button></div>';
    } else if (!st.reg) {
      html = st.regErro ? U.gate('critical', 'Registro de modelos indisponível', esc(st.regErro)) : '<p class="hint">Carregando versões…</p>';
    } else {
      html = (st.regAviso ? U.gate('warning', 'Registro de modelos', esc(st.regAviso)) : '') +
        secaoVersoes() + (st.cmpAberto ? secaoComparar() : '') + secaoRascunho();
    }
    U.redesenhar($('#mCorpo'), html);
    if (st.cmpAberto) desenharComparacao();
    if (st.aberto) { const hl = $('#mLista .op.hl'); if (hl) hl.scrollIntoView({ block: 'nearest' }); }
    dock();
    relogio();
  }

  function mudouRascunho() {
    st.form = null; st.outros = null;
    agendar();
    desenhar();
  }

  function adicionar(col) {
    if (!col) return;
    st.sel.add(col);
    st.busca = ''; st.destaque = 0;
    mudouRascunho();
    const el = $('#mBusca');
    if (el) el.focus();
  }

  function escolherBase(nome) {
    if (nome === st.base && !sujo()) return;
    if (sujo()) {
      const d = diff();
      if (!window.confirm(`Descartar o rascunho (+${d.mais.length} −${d.menos.length}) e carregar ${nome}?`)) return;
    }
    usarBase(nome);
    st.msg = null; st.erro = null;
    mudouRascunho();
  }

  function trocarAlvo(alvo) {
    st.alvo = alvo;
    carregarColunas(); agendar(); desenhar();
  }

  /* ---------------- eventos ---------------- */
  const area = $('#area-modelo');
  $('#mAlvos').innerHTML = U.ALVOS.map(([k, r]) => `<button data-alvo="${k}" aria-pressed="${k === st.alvo}">${r}</button>`).join('');

  area.addEventListener('click', (ev) => {
    const alvoBtn = ev.target.closest('[data-alvo]');
    if (alvoBtn) { trocarAlvo(alvoBtn.dataset.alvo); return; }
    const b = ev.target.closest('[data-acao]');
    if (!b || b.disabled) return;
    const col = b.dataset.col;
    switch (b.dataset.acao) {
      case 'conjunto': V.conjunto.abrir(); break;
      case 'qoe-repetir': st.qoeKey = null; avaliarQoe(); desenhar(); break;
      case 'perfil': st.perfil = b.dataset.p; avaliarQoe(); desenhar(); break;
      case 'base': escolherBase(b.dataset.nome); break;
      case 'menu': st.menu = st.menu === b.dataset.nome ? null : b.dataset.nome; desenhar(); break;
      case 'ativar': ativarManual(b.dataset.nome); break;
      case 'reavaliar': reavaliar([b.dataset.nome]); break;
      case 'reavaliar-todas': reavaliar(desatualizadas()); break;
      case 'comparar': st.cmpAberto = !st.cmpAberto; if (st.cmpAberto && st.cmpKey !== chaveCmp()) comparar(); desenhar(); break;
      case 'recomparar': comparar(); break;
      case 'metrica': st.metrica = b.dataset.m; desenhar(); break;
      case 'tirar': st.sel.delete(col); mudouRascunho(); break;
      case 'voltar': st.sel.add(col); mudouRascunho(); break;
      case 'por': adicionar(col); break;
      case 'lab': st.lab = !st.lab; desenhar(); break;
      case 'refazer-sug': iniciarSugestoes(true); desenhar(); break;
      case 'outros': testarOutros(); break;
      case 'abrir-receita': st.recAberto = true; st.aberto = false; carregarReceitas(); desenhar(); break;
      case 'fechar-receita': st.recAberto = false; st.rec.resultado = null; st.rec.erro = null; desenhar(); break;
      case 'salvar-receita': salvarReceita(); break;
      case 'descartar': usarBase(st.base); mudouRascunho(); break;
      case 'abrir-salvar': abrirForm(false); break;
      case 'abrir-ativar': abrirForm(true); break;
      case 'cancelar-salvar': st.form = null; st.salvarErro = null; desenhar(); break;
      case 'confirmar-salvar': publicar(); break;
      default: break;
    }
  });

  area.addEventListener('keydown', (ev) => {
    if (ev.target.id !== 'mBusca') return;
    const n = st.itens.length;
    if (ev.key === 'ArrowDown') { ev.preventDefault(); st.aberto = true; st.destaque = n ? (st.destaque + 1) % n : 0; desenhar(); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); st.destaque = n ? (st.destaque - 1 + n) % n : 0; desenhar(); }
    else if (ev.key === 'Enter') { ev.preventDefault(); if (st.aberto && n) adicionar(st.itens[st.destaque]); }
    else if (ev.key === 'Escape' && st.aberto) { ev.preventDefault(); ev.stopPropagation(); st.aberto = false; desenhar(); }
    else if (ev.key === 'Backspace' && !ev.target.value) {
      const ultimo = selLista().pop();
      if (ultimo) { st.sel.delete(ultimo); mudouRascunho(); }
    }
  });

  area.addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.id === 'mBusca') { st.busca = t.value; st.aberto = true; st.destaque = 0; desenhar(); }
    if (t.id === 'mNome' && st.form) st.form.nome = t.value;
    if (t.id === 'mDesc' && st.form) st.form.desc = t.value;
    if (t.id === 'mRecNome') st.rec.nome = t.value;
  });

  // Abrir a lista ao focar o campo. Só quando fechada: redesenhar devolve o foco ao
  // campo e dispararia isto de novo.
  area.addEventListener('focusin', (ev) => {
    if (ev.target.id === 'mBusca' && !st.aberto) { st.aberto = true; desenhar(); }
  });

  area.addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.id === 'mReceita') { st.rec.id = t.value; st.rec.colunas = []; montarReceita(); }
    if (t.dataset.rcol != null) { st.rec.colunas[Number(t.dataset.rcol)] = t.value; montarReceita(); }
  });

  // Clique fora fecha a lista de features e o menu do cartão.
  document.addEventListener('click', (ev) => {
    let mudou = false;
    if (st.aberto && !ev.target.closest('.add-wrap')) { st.aberto = false; mudou = true; }
    if (st.menu && !ev.target.closest('.ver')) { st.menu = null; mudou = true; }
    if (mudou) desenhar();
  });

  V.areas = V.areas || {};
  V.areas.modelo = {
    render(ctx) {
      st.ctx = ctx;
      if (ctx.enabledIds.length) {
        if (!st.reg && !st.regErro) carregarRegistro();
        carregarColunas(); carregarReceitas(); agendar();
      }
      desenhar();
    },
    // Classificação, contadores ou derivada nova: colunas, vazamento e avaliações mudam.
    recarregar() {
      st.colsKey = null; st.sugKey = null; st.avalKey = null; st.avalErroKey = null; st.cmpKey = null;
      if (st.ctx && st.ctx.enabledIds.length) carregarRegistro();
    },
    // O desenho automático (Laboratório) manda o conjunto escolhido para o rascunho.
    carregarRascunho(features, desenhoId) {
      if (!st.reg) { st.pendente = { features, desenhoId }; return; }
      aplicarRascunho(features, desenhoId);
      agendar();
    },
  };
})();
