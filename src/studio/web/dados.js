/* dados.js — área Dados: limiares da aplicação, matriz de capacidade ou planta,
   detalhe da posição escolhida e, sob demanda, contenção e restrição de todas as
   posições. Estado próprio; studio.js chama render(ctx) a cada mudança. */
(function () {
  'use strict';
  const V = window.VENKO;
  const L = V.logica;
  const U = V.util;
  const { esc, num, icone } = U;
  const $ = (s) => document.querySelector(s);

  const SEQ = ['--seq-100', '--seq-200', '--seq-300', '--seq-400', '--seq-500', '--seq-600', '--seq-700'];
  const st = { ctx: null, visao: 'matriz', sel: null, popover: null, todas: false, metrica: 'dn', hits: {} };

  const rampa = (pct) => U.cssv(SEQ[Math.min(SEQ.length - 1, Math.floor(pct / 100 * SEQ.length))]);
  // A rampa é a mesma nos dois temas: a cor do texto segue o fundo da célula, não o tema.
  const tinta = (pct) => (pct > 55 ? '#ffffff' : '#0b0b0b');
  const predio = (b) => st.ctx.data.buildings[b];
  const tagAmbiente = (b) => `<span class="tag amb-${predio(b).ambiente}">${esc(st.ctx.ambientes[predio(b).ambiente])}</span>`;
  const valor = (v) => num(v, Number.isInteger(v) ? 0 : 1);
  const metrica = (key) => L.METRICAS.find((m) => m.key === key);

  /* ---------------- limiares ---------------- */
  // O cabeçalho só é refeito quando a lista de aplicações ou o popover aberto mudam;
  // o resto é atualizado no lugar, para o slider não perder o foco no meio do arraste.
  function cabecalho() {
    const c = st.ctx;
    const host = $('#dLimiares');
    const sig = Object.keys(c.perfis).join('|') + '#' + st.popover;
    if (host.dataset.sig !== sig) {
      host.dataset.sig = sig;
      host.innerHTML = `<label for="dApp">Aplicação</label>
        <select id="dApp">${Object.keys(c.perfis).map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join('')}
          <option value="__custom">Personalizado</option></select>
        ${L.METRICAS.map((m) => `<span class="lim">
          <button class="chip-lim" data-lim="${m.key}" aria-expanded="${st.popover === m.key}">
            ${m.label} ${m.dir === 'min' ? '≥' : '≤'} <b data-lim-valor="${m.key}"></b> ${m.unit}</button>
          ${st.popover === m.key ? `<div class="pop" role="dialog" aria-label="Limiar de ${m.label}">
            <label for="dSlider">${m.label} ${m.dir === 'min' ? 'mínimo' : 'máximo'}</label>
            <input type="range" id="dSlider" data-key="${m.key}" min="0" max="${m.max}" step="${m.step}">
            <output id="dSliderOut" for="dSlider"></output></div>` : ''}</span>`).join('')}
        <button class="linkbtn link hide" id="dRestaurar" data-acao="restaurar">restaurar</button>`;
      if (st.popover) { $('#dSlider').value = c.thr[st.popover]; $('#dSlider').focus(); }
    }
    $('#dApp').value = c.personalizado ? '__custom' : c.app;
    $('#dRestaurar').classList.toggle('hide', !c.personalizado);
    L.METRICAS.forEach((m) => { host.querySelector(`[data-lim-valor="${m.key}"]`).textContent = valor(c.thr[m.key]); });
    if (st.popover) {
      const m = metrica(st.popover);
      $('#dSliderOut').textContent = `${valor(c.thr[m.key])} ${m.unit}`;
      if (document.activeElement !== $('#dSlider')) $('#dSlider').value = c.thr[m.key];
    }
  }

  function fecharPopover() {
    if (!st.popover) return;
    const k = st.popover;
    st.popover = null;
    cabecalho();
    const chip = $(`[data-lim="${k}"]`);
    if (chip) chip.focus();
  }

  /* ---------------- matriz ---------------- */
  const legenda = () => `<div class="legend"><span>0%</span><span class="ramp">${SEQ.map((s) =>
    `<i style="background:var(${s})"></i>`).join('')}</span><span>100%</span>
    <span style="margin-left:12px">– = menos de ${L.MIN_AMOSTRAS} amostras</span></div>`;

  function matriz(rows) {
    const linhas = L.celulas(rows, st.ctx.thr);
    const sem = L.semContagem(rows);
    const nota = sem.length ? `<p class="gate-msg nota-sem">${sem.length} posição(ões) sem contagem de dispositivos:
      ${sem.map((x) => `<button class="linkbtn link" data-pos="${esc(x.k)}" data-k="pos-${esc(x.k)}">${esc(x.p)}</button>`).join(', ')}.
      Veja na planta ou no detalhe.</p>` : '';
    if (!linhas.length) return '<p class="hint">Nenhum dataset com contagem de dispositivos está ativo.</p>' + nota;
    let html = `<div class="mtx"><div class="mtx-cab"><span>Posição</span><span>1 disp.</span><span>2 disp.</span><span>3 disp.</span></div>`;
    let atual = null;
    linhas.forEach((l) => {
      if (l.b !== atual) { atual = l.b; html += `<div class="mtx-predio">${esc(predio(l.b).label)} ${tagAmbiente(l.b)}</div>`; }
      const desc = l.cells.map((c, i) => `${i + 1} disp. ${c.pct == null ? `${c.n} amostras` : Math.round(c.pct) + '%'}`).join(', ');
      html += `<button class="mtx-lin${st.sel === l.k ? ' sel' : ''}" data-pos="${esc(l.k)}" data-k="pos-${esc(l.k)}"
        aria-pressed="${st.sel === l.k}" aria-label="${esc(l.p)}: ${desc}"><span class="mtx-rot">${esc(l.p)}</span>${l.cells.map((c) =>
        c.pct == null ? `<span class="cel vazia" title="${c.n} amostras">–</span>`
          : `<span class="cel" style="background:${rampa(c.pct)};color:${tinta(c.pct)}" title="${c.n} amostras">${Math.round(c.pct)}%</span>`).join('')}</button>`;
    });
    return html + '</div>' + legenda() + nota;
  }

  /* ---------------- planta ---------------- */
  function pontos(rows) {
    const grupos = new Map();
    rows.forEach((r) => {
      const k = `${r.x}|${r.y}`;
      if (!grupos.has(k)) grupos.set(k, { x: r.x, y: r.y, p: r.p, key: L.chavePos(r.b, r.p), rows: [] });
      grupos.get(k).rows.push(r);
    });
    return [...grupos.values()].map((g) => {
      const pct = 100 * g.rows.filter((r) => L.atende(r, st.ctx.thr)).length / g.rows.length;
      return { x: g.x, y: g.y, n: g.rows.length, value: pct, label: g.p, key: g.key, color: rampa(pct) };
    });
  }

  function desenharPlanta(rows) {
    const c = st.ctx;
    const comXY = rows.filter((r) => r.x != null);
    const predios = [];
    Object.entries(c.data.envelopes).forEach(([b, env]) => {
      const meus = comXY.filter((r) => r.b === b);
      if (!meus.length) return;
      const label = predio(b).label;
      const planta = (c.data.plantas || {})[b] || null;
      if (!planta || !planta.andares) {
        predios.push({ k: b, b, andar: null, label, env, points: pontos(meus), planta });
        return;
      }
      // r.andar vem do servidor (plans.andar_de); aqui só se separa por andar.
      const semAndar = meus.filter((r) => r.andar == null).length;
      planta.andares.forEach((a, i) => {
        const extras = i > 0 ? [] : planta.avisos.concat(semAndar ? [`${semAndar} linha(s) sem z ficaram fora da planta`] : []);
        predios.push({
          k: `${b}|${a.id}`, b, andar: a.id, label: `${label} · ${a.id}`,
          env: a.roteador ? env : Object.assign({}, env, { routerX: null, routerY: null }),
          points: pontos(meus.filter((r) => r.andar === a.id)),
          planta: Object.assign({}, a, { avisos: a.avisos.concat(extras) }),
        });
      });
    });
    V.views.planta.render({
      predios,
      avisos: c.data.plantasAvisos || [],
      atualizarPlantas: (plantas, avisos) => { c.data.plantas = plantas; c.data.plantasAvisos = avisos; V.app.atualizar(); },
      aoSelecionar: selecionar,
    });
  }

  /* ---------------- detalhe ---------------- */
  function barras(rep) {
    return `<div class="hbars">${L.METRICAS.map((m) => `<div class="hbar"><span>${m.label}</span>
      <span class="trilho"><i style="width:${rep[m.key].toFixed(1)}%"></i></span><span class="num">${Math.round(rep[m.key])}%</span></div>`).join('')}</div>`;
  }

  function frase(g) {
    return g.folga ? 'Atende em praticamente todas as amostras.'
      : `<b>${g.rotulo}</b> reprova em ${Math.round(g.pct)}% das amostras.`;
  }

  function resumo(rows) {
    if (!rows.length) return '<p class="hint">Sem amostras no conjunto ativo.</p>';
    const g = L.gargalo(rows, st.ctx.thr);
    const piores = L.piores(rows, st.ctx.thr, 3);
    return `<h2>Resumo do conjunto</h2>
      <p class="gate-msg">Clique numa posição da matriz ou num ponto da planta para ver o detalhe.</p>
      <div class="gargalo${g.folga ? ' ok' : ''}"><span class="label">Gargalo geral</span><p>${frase(g)}</p></div>
      <h3 class="grupo">Posições com menos amostras atendendo</h3>
      ${piores.map((x) => `<button class="pior-pos" data-pos="${esc(x.k)}" data-k="pior-${esc(x.k)}">
        <span>${esc(x.p)} <span class="gate-msg">${esc(predio(x.b).label)}</span></span><b>${Math.round(x.pct)}%</b></button>`).join('')}
      <h3 class="grupo">Reprovação por métrica</h3>${barras(L.reprovacao(rows, st.ctx.thr))}`;
  }

  function detalhe(rows) {
    if (!st.sel) return resumo(rows);
    const meus = L.daPosicao(rows, st.sel);
    if (!meus.length) { st.sel = null; return resumo(rows); }
    const { b, p } = meus[0];
    const thr = st.ctx.thr;
    const g = L.gargalo(meus, thr);
    const datasets = new Set(meus.map((r) => r.ds)).size;
    const comN = meus.some((r) => r.n != null);
    const contencao = comN
      ? `<div class="minis">${L.METRICAS.map((m) => `<div class="mini"><div class="mini-tit">${m.label} <span>(${m.unit})</span></div>
          <div class="chartwrap"><canvas data-mini="${m.key}"></canvas><div class="tooltip"></div></div></div>`).join('')}</div>`
      : `<p class="gate-msg">Sem contagem de dispositivos nesta posição (datasets legacy). Mediana geral:</p>
        <table><tbody>${L.METRICAS.map((m) => `<tr><td>${m.label}</td>
          <td class="num">${valor(L.mediana(meus.map((r) => r[m.key])))} ${m.unit}</td>
          <td class="num gate-msg">limiar ${m.dir === 'min' ? '≥' : '≤'} ${valor(thr[m.key])}</td></tr>`).join('')}</tbody></table>`;
    return `<div class="det-cab"><div><h2>${esc(p)}</h2>
        <div class="gate-msg">${esc(predio(b).label)} ${tagAmbiente(b)} · ${meus.length} amostras · ${datasets} dataset(s)</div></div>
        <button class="btn-icone" data-acao="limpar" aria-label="Fechar o detalhe">${icone('i-x')}</button></div>
      <div class="gargalo${g.folga ? ' ok' : ''}"><span class="label">Gargalo</span><p>${frase(g)}</p></div>
      <h3 class="grupo">Com 1, 2 e 3 dispositivos</h3>${contencao}
      <h3 class="grupo">Reprovação por métrica</h3>${barras(L.reprovacao(meus, thr))}`;
  }

  function desenharMinis(rows) {
    if (!st.sel) return;
    const meus = L.daPosicao(rows, st.sel);
    document.querySelectorAll('#dDetalhe canvas[data-mini]').forEach((cv) => {
      const m = metrica(cv.dataset.mini);
      const hits = V.drawLines(cv, {
        height: 118, compacto: true, x: ['1', '2', '3'],
        series: [{ label: m.label, color: U.cssv('--s1'), points: L.contencao(meus, m.key).map((v) => ({ v })) }],
        ref: { valor: st.ctx.thr[m.key], rotulo: 'limiar' },
        yFmt: (v) => v.toFixed(v < 10 ? 1 : 0),
      });
      V.attachTooltip(cv, cv.nextElementSibling, () => hits,
        (h) => `<b>${h.at} dispositivo(s)</b>${m.label}: ${num(h.value, 1)} ${m.unit}`);
    });
  }

  /* ---------------- todas as posições ---------------- */
  function desenharTodas(rows) {
    const c = st.ctx;
    const comN = rows.filter((r) => r.n != null);
    const m = metrica(st.metrica);
    const series = L.posicoes(comN).map((pos, i) => ({
      label: pos.p, color: U.cssv('--s' + (i % 5 + 1)),
      points: L.contencao(L.daPosicao(comN, pos.k), m.key).map((v) => ({ v })),
    }));
    st.hits.cont = V.drawLines($('#cContention'), {
      height: 320, x: ['1 dispositivo', '2 dispositivos', '3 dispositivos'], series,
      yFmt: (v) => v.toFixed(v < 10 ? 1 : 0), yTitle: `${m.label} (${m.unit}) — mediana`,
      ref: { valor: c.thr[m.key], rotulo: 'limiar' },
    });
    $('#kContention').innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join('');
    const seriesR = L.METRICAS.map((x, i) => ({ label: x.label, color: U.cssv('--s' + (i % 5 + 1)) }));
    st.hits.rest = V.drawGroupedBars($('#cConstraint'), {
      height: 320, max: 100, yFmt: (v) => v + '%', series: seriesR,
      groups: L.posicoes(rows).map((pos) => {
        const rep = L.reprovacao(L.daPosicao(rows, pos.k), c.thr);
        return { label: pos.p, values: L.METRICAS.map((x) => rep[x.key]) };
      }),
    });
    $('#kConstraint').innerHTML = seriesR.map((s) => `<span><i style="background:${s.color}"></i>${s.label} reprovado</span>`).join('');
  }

  /* ---------------- composição ---------------- */
  function selecionar(k) {
    st.sel = k;
    render(st.ctx);
  }

  function render(ctx) {
    st.ctx = ctx;
    const vazio = !ctx.enabledIds.length;
    $('#dVazio').classList.toggle('hide', !vazio);
    $('#dConteudo').classList.toggle('hide', vazio);
    if (vazio) return;
    cabecalho();
    const criticos = L.avisosConjunto(ctx.data, ctx.rows, ctx.enabled, ctx.ambiente).filter((a) => a.sev === 'critical');
    $('#dCritico').innerHTML = criticos.map((a) => U.gate('critical', esc(a.titulo), esc(a.msg))).join('');
    document.querySelectorAll('#area-dados [data-visao]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.visao === st.visao)));
    $('#dMatriz').classList.toggle('hide', st.visao !== 'matriz');
    $('#dPlanta').classList.toggle('hide', st.visao !== 'planta');
    if (st.visao === 'matriz') U.redesenhar($('#dMatriz'), matriz(ctx.rows));
    else desenharPlanta(ctx.rows);
    U.redesenhar($('#dDetalhe'), detalhe(ctx.rows));
    desenharMinis(ctx.rows);
    $('#dTodas').setAttribute('aria-expanded', String(st.todas));
    $('#dTodas').textContent = st.todas ? 'Esconder todas as posições' : 'Ver todas as posições';
    $('#dTodasCorpo').classList.toggle('hide', !st.todas);
    if (st.todas) desenharTodas(ctx.rows);
  }

  /* ---------------- eventos ---------------- */
  const area = $('#area-dados');
  area.addEventListener('click', (ev) => {
    const pos = ev.target.closest('[data-pos]');
    if (pos) { selecionar(pos.dataset.pos); return; }
    const lim = ev.target.closest('[data-lim]');
    if (lim) { st.popover = st.popover === lim.dataset.lim ? null : lim.dataset.lim; cabecalho(); return; }
    const visao = ev.target.closest('[data-visao]');
    if (visao) { st.visao = visao.dataset.visao; render(st.ctx); return; }
    const a = ev.target.closest('[data-acao]');
    if (!a) return;
    if (a.dataset.acao === 'restaurar') V.app.definirAplicacao(st.ctx.app);
    if (a.dataset.acao === 'limpar') { st.sel = null; render(st.ctx); }
    if (a.dataset.acao === 'todas') { st.todas = !st.todas; render(st.ctx); }
    if (a.dataset.acao === 'conjunto') V.conjunto.abrir();
  });
  area.addEventListener('change', (ev) => {
    if (ev.target.id === 'dApp' && ev.target.value !== '__custom') V.app.definirAplicacao(ev.target.value);
    if (ev.target.id === 'dMetrica') { st.metrica = ev.target.value; desenharTodas(st.ctx.rows); }
  });
  area.addEventListener('input', (ev) => {
    if (ev.target.id === 'dSlider') V.app.definirLimiar(ev.target.dataset.key, parseFloat(ev.target.value));
  });
  area.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && st.popover) { ev.preventDefault(); fecharPopover(); }
  });
  // Clique fora do chip e do popover fecha o popover.
  document.addEventListener('click', (ev) => {
    if (st.popover && !ev.target.closest('.lim')) { st.popover = null; if (st.ctx) cabecalho(); }
  });

  V.attachTooltip($('#cContention'), $('#tContention'), () => st.hits.cont,
    (h) => `<b>${esc(h.label)}</b>${esc(h.at)}: ${h.value.toFixed(1)}`);
  V.attachTooltip($('#cConstraint'), $('#tConstraint'), () => st.hits.rest,
    (h) => `<b>${esc(h.at)}</b>${esc(h.label)} reprovado em ${h.value.toFixed(0)}%`);

  V.areas = V.areas || {};
  V.areas.dados = { render };
})();
