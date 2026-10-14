/* desenho.js — "Desenhar melhor modelo", no Laboratório. Seleção gulosa num job do
   servidor; o resultado vai para o rascunho da área Modelo. Veio de modelos.js sem
   mudança de comportamento, salvo a chave do desenho, que chamava a si mesma. */
(function () {
  'use strict';
  const V = window.VENKO;
  const U = V.util;
  const { esc, num, sinal } = U;
  const $ = (s) => document.querySelector(s);

  const st = { ctx: null, reg: null, regErro: null,
               des: null, desId: null, desKey: null, desErro: null, desTimer: null,
               semVolume: true, semVolumeTocado: false, escopo: 'tudo' };

  const alvo = () => $('#labAlvo').value;
  const chaveConj = () => st.ctx.enabledIds.slice().sort().join(',') + '|' + alvo() + '|' + st.ctx.ambiente;
  const query = () => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(alvo()) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);
  const chaveDesenho = () => chaveConj() + '|' + st.escopo;

  function carregarRegistro() {
    U.pedir('api/modelos').then((reg) => {
      st.reg = reg; st.regErro = null;
      // Sem resposta sobre os contadores, o desenho começa sem eles: podem ser vazamento.
      if (!st.semVolumeTocado) st.semVolume = reg.contadores !== 'nao';
    }).catch((e) => { st.regErro = e.message; }).finally(desenhar);
  }

  function desenharModelo() {
    if (st.des && st.des.status === 'rodando') return;
    const k = chaveDesenho();
    st.desErro = null; st.des = { status: 'rodando', progresso: [] }; st.desKey = k; desenhar();
    U.pedir('api/modelos/desenhar?' + query() + '&sem_volume=' + st.semVolume + '&escopo=' + st.escopo, { method: 'POST' })
      .then((r) => { st.desId = r.id; acompanhar(); })
      .catch((e) => { st.desErro = e.message; st.des = null; desenhar(); });
  }

  function acompanhar() {
    clearTimeout(st.desTimer);
    U.pedir('api/modelos/desenhar/' + st.desId)
      .then((job) => {
        st.des = job;
        if (job.status === 'rodando') st.desTimer = setTimeout(acompanhar, 1500);
      })
      .catch((e) => { st.desErro = e.message; })
      .finally(desenhar);
  }

  function abrirNoModelo() {
    V.areas.modelo.carregarRascunho(st.des.resultado.features, st.desId);
    V.app.irPara('modelo');
  }

  function cardDesenho() {
    const u = U.ALVO[alvo()].unidade;
    const rodando = st.des && st.des.status === 'rodando';
    const atual = st.desKey === chaveDesenho();
    let corpo = `<p class="hint">Seleção gulosa: a cada passo entra a feature que mais sobe o R² pooled (folds por local de coleta);
      para quando o ganho fica abaixo de 0,005. "Tudo" busca o melhor treino com todas as colunas sem vazamento; "Implantável"
      fica só com TR-181 padrão, derivável ou proxy. Leva de 3 a 6 minutos.</p>`;
    if (st.desErro) corpo = U.gate('critical', 'O desenho falhou', esc(st.desErro));
    else if (rodando) {
      corpo = `<div class="log">${st.des.progresso.slice(-8).map((e) => `<div>${e.fase ? esc(e.fase)
        : `+ <code>${esc(e.feature)}</code> → pooled ${num(e.pooled, 3)}${e.ganho == null ? '' : ` (${sinal(e.ganho)})`}`}</div>`).join('')}
        <div class="gate-msg">calculando…</div></div>`;
    } else if (st.des && st.des.status === 'erro') corpo = U.gate('critical', 'O desenho falhou', esc(st.des.erro));
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
          <div><span>Ativa: ${esc(st.reg.ativo)}</span><b>${avAtivo ? num(avAtivo.pooled, 3) : '–'}</b><em>MAE ${avAtivo ? num(avAtivo.mae, 1) : '–'} ${u}</em></div>
        </div>
        <p class="hint">A nota aninhada roda a seleção sem o local de teste, para cada local: é o que esperar num prédio novo.
          A nota da seleção escolheu olhando todos os locais e por isso sai melhor do que é. Compare a ativa com a <b>aninhada</b>.</p>
        <div class="dois">
          <div><h2 style="font-size:13px">Passos da seleção</h2><table><thead><tr><th class="num">#</th><th>Entrou</th><th class="num">R² pooled</th><th class="num">Ganho</th></tr></thead><tbody>
            ${r.passos.map((p, i) => `<tr><td class="num">${i + 1}</td><td><code>${esc(p.feature)}</code></td><td class="num">${num(p.pooled, 3)}</td>
              <td class="num">${p.ganho == null ? '–' : sinal(p.ganho)}</td></tr>`).join('')}</tbody></table></div>
          <div><h2 style="font-size:13px">Estabilidade da escolha</h2><table><thead><tr><th>Feature</th><th class="num">Final</th>${locais.map((l) =>
            `<th class="num" title="seleção feita sem ${esc(l)}">sem ${esc(l)}</th>`).join('')}</tr></thead><tbody>${estab}</tbody></table>
            <p class="hint" style="margin-top:6px">Uma feature escolhida em todas as colunas é estável; uma que aparece só no final dependeu de ver todos os locais.</p></div>
        </div>
        <div class="controls" style="margin-top:10px"><button class="btn-pri" data-dacao="abrir">Abrir no Modelo</button>
          <span class="gate-msg">${r.features.length} features · ${num(r.segundos, 0)} s${atual ? '' : ' · desatualizado: o conjunto ou o alvo mudou'}</span>
          ${U.tagNivel(r.cobertura)} ${r.cobertura ? r.cobertura.lacunas.map(U.tagLacuna).join(' ') : ''}</div></div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Desenhar melhor modelo</h2>
      <p class="hint">O resultado mostra a cobertura TR-069 e as lacunas: o que falta derivar ou coletar para levar a produção.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-dacao="desenhar"${rodando ? ' disabled' : ''}>${rodando ? 'Desenhando…' : 'Desenhar'}</button>
        <div class="status"><label for="dEscopo">Escopo</label> <select id="dEscopo"${rodando ? ' disabled' : ''}>
          <option value="tudo"${st.escopo === 'tudo' ? ' selected' : ''}>Tudo</option>
          <option value="implantavel"${st.escopo === 'implantavel' ? ' selected' : ''}>Implantável</option></select></div>
        <div class="status"><label title="router_tx/rx_duration_us, router_tx_retries, router_tx_failed, router_rx_drop_misc: crescem com o tráfego do próprio teste se forem medidos na janela dele">
          <input type="checkbox" id="dSemVolume"${st.semVolume ? ' checked' : ''}${rodando ? ' disabled' : ''}> sem contadores brutos de volume</label></div></div></div>${corpo}</div>`;
  }

  function desenhar() {
    const host = $('#lDesenho');
    if (!st.ctx || !st.ctx.enabledIds.length) { host.innerHTML = ''; return; }
    if (!st.reg) {
      host.innerHTML = st.regErro ? U.gate('critical', 'Registro de modelos indisponível', esc(st.regErro)) : '';
      return;
    }
    host.innerHTML = cardDesenho();
  }

  $('#lDesenho').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-dacao]');
    if (!b || b.disabled) return;
    if (b.dataset.dacao === 'desenhar') desenharModelo();
    if (b.dataset.dacao === 'abrir') abrirNoModelo();
  });
  $('#lDesenho').addEventListener('change', (ev) => {
    if (ev.target.id === 'dEscopo') { st.escopo = ev.target.value; desenhar(); }
    if (ev.target.id === 'dSemVolume') { st.semVolume = ev.target.checked; st.semVolumeTocado = true; desenhar(); }
  });

  V.views = V.views || {};
  V.views.desenho = {
    render(ctx) {
      st.ctx = ctx;
      if (!st.reg && !st.regErro) carregarRegistro();
      desenhar();
    },
    // A versão ativa e o estado dos contadores podem ter mudado.
    recarregar() { st.reg = null; st.regErro = null; },
  };
})();
