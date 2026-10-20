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
               up: null, upMsg: null, dispensadas: new Set() };

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

  /* ---------------- adicionar dados ---------------- */
  function enviar(arquivo) {
    st.upMsg = null;
    st.up = { nome: arquivo.name, token: null, previa: null, novos: {}, sujo: false, ocupado: true, erro: null };
    desenhar();
    U.pedir('api/datasets/previa?nome=' + encodeURIComponent(arquivo.name),
      { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: arquivo })
      .then((r) => { st.up.token = r.token; usarPrevia(r.previa); })
      .catch((e) => { st.up.erro = e.message; })
      .finally(() => { if (st.up) st.up.ocupado = false; desenhar(); });
  }

  // Os formulários de prédio ficam enquanto a prévia existir: depois de Verificar, os
  // prefixos deixam de ser desconhecidos, mas o cadastro ainda precisa ir na confirmação.
  function usarPrevia(p) {
    st.up.previa = p;
    st.up.sujo = false;
    (p.desconhecidos || []).forEach((g) => {
      if (!st.up.novos[g.prefixo]) {
        st.up.novos[g.prefixo] = { chave: 'casa-' + g.prefixo, rotulo: '', ambiente: 'domestico', prefixo: g.prefixo };
      }
    });
  }

  const novosLista = () => Object.values(st.up.novos).map((n) =>
    ({ chave: n.chave.trim(), rotulo: n.rotulo.trim(), ambiente: n.ambiente, prefixo: n.prefixo.trim() }));

  function revisar() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/datasets/revisar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then(usarPrevia)
      .catch((e) => { up.erro = e.message; })
      .finally(() => { up.ocupado = false; desenhar(); });
  }

  function confirmarUpload() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/datasets/confirmar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then((r) => {
        st.up = null;
        st.upMsg = `${r.dataset} adicionado em data/` +
          (r.predios.length ? ` e ${r.predios.join(', ')} em src/ml/core/predios.json` : '') +
          '. Revise no git diff antes do commit. As versões salvas ficam desatualizadas até serem reavaliadas na área Modelo.';
        return V.app.recarregarPayload([r.dataset]);
      })
      .catch((e) => { if (st.up) { st.up.erro = e.message; st.up.ocupado = false; } else { st.upMsg = e.message; } desenhar(); });
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

  const lista = (itens) => '<ul>' + itens.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';

  function formPredio(prefixo, n, grupo) {
    const campo = (c, rotulo, extra = '') => `<label>${rotulo}<input type="text" data-novo="${esc(prefixo)}"
      data-campo="${c}" data-k="novo-${esc(prefixo)}-${c}" value="${esc(n[c])}"${extra}></label>`;
    return `<div class="pend-item ${grupo ? 'warning' : 'good'}"><div style="flex:1">
      <b>Prédio novo para <code>${esc(prefixo)}-…</code></b>
      ${grupo ? `<div class="gate-msg">${grupo.linhas.toLocaleString('pt-BR')} linhas: ${grupo.valores.map(esc).join(', ')}</div>` : ''}
      <div class="upload-campos">${campo('rotulo', 'Nome', ' placeholder="ex.: Casa do Villa"')}${campo('chave', 'Chave')}${campo('prefixo', 'Prefixo')}
        <label>Ambiente<select data-novo="${esc(prefixo)}" data-campo="ambiente" data-k="novo-${esc(prefixo)}-ambiente">${Object.entries(st.ctx.ambientes).map(([a, r]) =>
          `<option value="${a}"${a === n.ambiente ? ' selected' : ''}>${esc(r)}</option>`).join('')}</select></label></div>
    </div></div>`;
  }

  function secaoAdicionar() {
    const up = st.up;
    const msg = st.upMsg ? U.gate('good', 'Dados adicionados', esc(st.upMsg)) : '';
    const botao = `<div class="controls"><button class="btn" data-acao="escolher-arquivo" data-k="escolher-arquivo"${up && up.ocupado ? ' disabled' : ''}>
        ${U.icone('i-plus')} Adicionar dados</button>
      <input type="file" id="cArquivo" accept=".csv,.zip" class="hide"></div>`;
    if (!up) return msg + botao;
    if (!up.previa) {
      return botao + (up.ocupado ? '<p class="gate-msg">Lendo o arquivo…</p>' : '') +
        (up.erro ? U.gate('critical', 'Não foi possível ler o arquivo', esc(up.erro)) : '');
    }
    const p = up.previa;
    const resumo = p.linhas != null ? `<p class="gate-msg">${p.linhas.toLocaleString('pt-BR')} linhas · ${p.colunas} colunas` +
      (p.geracao ? ` · geração ${p.geracao === 'current' ? 'atual' : 'legada'}` : '') + '</p>' : '';
    const predios = (p.predios || []).map((x) => `<li><b>${esc(x.rotulo)}</b>${x.novo ? ' <span class="tag">novo</span>' : ''}
      · ${x.linhas.toLocaleString('pt-BR')} linhas · ${x.posicoes.map(esc).join(', ')}</li>`).join('');
    const preench = Object.entries(p.preenchimento || {}).map(([c, v]) =>
      `<li><code>${esc(c)}</code> ${v == null ? 'ausente' : U.pct(v)}</li>`).join('');
    const forms = Object.entries(up.novos).map(([k, n]) =>
      formPredio(k, n, (p.desconhecidos || []).find((g) => g.prefixo === k))).join('');
    const pode = !up.ocupado && !up.sujo && !p.bloqueios.length;
    return `<div class="upload">
      <label class="upload-nome">Nome em data/<input type="text" data-campo="nome-arquivo" data-k="nome-arquivo" value="${esc(up.nome)}"></label>
      ${resumo}${predios ? `<ul class="upload-predios">${predios}</ul>` : ''}
      ${preench ? `<details class="fold" data-k="up-preench"><summary>Preenchimento das colunas-chave</summary>
        <div class="inner"><ul>${preench}</ul></div></details>` : ''}
      ${forms}
      ${p.bloqueios.length ? U.gate('critical', 'Ainda não dá para confirmar', lista(p.bloqueios)) : ''}
      ${p.avisos.length ? U.gate('warning', 'Avisos', lista(p.avisos)) : ''}
      ${up.erro ? U.gate('critical', 'Algo deu errado', esc(up.erro)) : ''}
      ${up.sujo ? '<p class="gate-msg">Clique em Verificar depois de mudar o nome ou os prédios.</p>' : ''}
      <div class="controls"><button class="btn" data-acao="cancelar-upload" data-k="cancelar-upload">Cancelar</button>
        <button class="btn" data-acao="revisar-upload" data-k="revisar-upload"${up.ocupado ? ' disabled' : ''}>Verificar</button>
        <button class="btn-pri" data-acao="confirmar-upload" data-k="confirmar-upload"${pode ? '' : ' disabled'}>${up.ocupado ? 'Aguarde…' : 'Confirmar'}</button></div>
    </div>`;
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
      <h3>Datasets</h3>${secaoAdicionar()}${secaoDatasets()}`);
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
    if (acao === 'escolher-arquivo') $('#cArquivo').click();
    if (acao === 'cancelar-upload') { st.up = null; desenhar(); }
    if (acao === 'revisar-upload') revisar();
    if (acao === 'confirmar-upload') confirmarUpload();
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
    if (t.id === 'cArquivo' && t.files && t.files[0]) { enviar(t.files[0]); return; }
    if (t.dataset.ds) V.app.ligar(t.dataset.ds, t.checked);
    if (t.dataset.acao === 'legacy') V.app.definirLegacy(t.checked);
    if (t.name === 'cContadores') responder(U.post('api/contadores', { estado: t.value }));
  });
  // O select também dispara input. Redesenhar a cada tecla é seguro: U.redesenhar devolve foco e cursor pelo data-k.
  $('#painelConjunto').addEventListener('input', (ev) => {
    const t = ev.target;
    if (!st.up || !t.dataset.campo) return;
    if (t.dataset.campo === 'nome-arquivo') st.up.nome = t.value;
    else if (t.dataset.novo) st.up.novos[t.dataset.novo][t.dataset.campo] = t.value;
    st.up.sujo = true;
    desenhar();
  });

  V.conjunto = {
    render(ctx) { st.ctx = ctx; carregar(); desenhar(); },
    contagem, abrir, fechar,
    recarregar() { st.chave = null; },
  };
})();
