/* logica.js — regras puras do QoE Studio: sem DOM, sem fetch, sem estado.
   Carregado no navegador (window.VENKO.logica) e no Node (module.exports), para
   que tests/js/logica.test.js teste as mesmas funções que a página usa. */
(function (raiz, fabrica) {
  const modulo = fabrica();
  if (typeof module === 'object' && module.exports) module.exports = modulo;
  else { raiz.VENKO = raiz.VENKO || {}; raiz.VENKO.logica = modulo; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------------- métricas de QoE ---------------- */
  // dir 'min': a amostra precisa de pelo menos o limiar; 'max': de no máximo o limiar.
  const METRICAS = [
    { key: 'dn',  label: 'Download', unit: 'Mbps', dir: 'min', max: 60,  step: 0.5 },
    { key: 'up',  label: 'Upload',   unit: 'Mbps', dir: 'min', max: 60,  step: 0.5 },
    { key: 'lat', label: 'Latência', unit: 'ms',   dir: 'max', max: 500, step: 5 },
    { key: 'jit', label: 'Jitter',   unit: 'ms',   dir: 'max', max: 200, step: 2 },
  ];
  // Abaixo disto, uma célula da matriz ou um ponto de contenção vira "–".
  const MIN_AMOSTRAS = 5;
  // Reprovar em até 5% das amostras não é gargalo: a posição atende quase sempre.
  const FOLGA_PCT = 5;

  const reprova = (r, m, thr) => (m.dir === 'min' ? r[m.key] < thr[m.key] : r[m.key] > thr[m.key]);
  const atende = (r, thr) => METRICAS.every((m) => !reprova(r, m, thr));

  function mediana(xs) {
    if (!xs.length) return null;
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  const chavePos = (b, p) => b + '|' + p;

  // Posições distintas das linhas, ordenadas por prédio e posição.
  function posicoes(rows) {
    const vistas = new Map();
    rows.forEach((r) => {
      const k = chavePos(r.b, r.p);
      if (!vistas.has(k)) vistas.set(k, { b: r.b, p: r.p, k });
    });
    return [...vistas.values()].sort((a, z) => a.b.localeCompare(z.b) || a.p.localeCompare(z.p));
  }

  const daPosicao = (rows, k) => rows.filter((r) => chavePos(r.b, r.p) === k);

  // % das amostras que reprovam em cada métrica; null sem amostras.
  function reprovacao(rows, thr) {
    if (!rows.length) return null;
    const saida = {};
    METRICAS.forEach((m) => { saida[m.key] = 100 * rows.filter((r) => reprova(r, m, thr)).length / rows.length; });
    return saida;
  }

  // A métrica que mais reprova. `folga` diz que nenhuma passa de FOLGA_PCT.
  function gargalo(rows, thr) {
    const rep = reprovacao(rows, thr);
    if (!rep) return null;
    const pior = METRICAS.reduce((a, m) => (rep[m.key] > rep[a.key] ? m : a));
    return { metrica: pior.key, rotulo: pior.label, pct: rep[pior.key], folga: rep[pior.key] <= FOLGA_PCT };
  }

  // Matriz de capacidade: uma linha por posição com contagem de dispositivos e uma
  // célula para 1, 2 e 3 dispositivos ({n, pct}; pct null abaixo de MIN_AMOSTRAS).
  function celulas(rows, thr) {
    const comN = rows.filter((r) => r.n != null);
    return posicoes(comN).map((pos) => {
      const meus = daPosicao(comN, pos.k);
      return Object.assign({}, pos, {
        cells: [1, 2, 3].map((n) => {
          const g = meus.filter((r) => r.n === n);
          return { n: g.length,
                   pct: g.length < MIN_AMOSTRAS ? null : 100 * g.filter((r) => atende(r, thr)).length / g.length };
        }),
      });
    });
  }

  // Posições que só têm linhas sem contagem de dispositivos (datasets legacy).
  function semContagem(rows) {
    const comN = new Set(rows.filter((r) => r.n != null).map((r) => chavePos(r.b, r.p)));
    return posicoes(rows).filter((pos) => !comN.has(pos.k));
  }

  // Mediana de uma métrica com 1, 2 e 3 dispositivos; null abaixo de MIN_AMOSTRAS.
  function contencao(rows, key) {
    return [1, 2, 3].map((n) => {
      const g = rows.filter((r) => r.n === n);
      return g.length < MIN_AMOSTRAS ? null : mediana(g.map((r) => r[key]));
    });
  }

  // As `k` posições com menor % de amostras que atendem, entre as que têm MIN_AMOSTRAS.
  function piores(rows, thr, k) {
    return posicoes(rows).map((pos) => {
      const meus = daPosicao(rows, pos.k);
      return Object.assign({}, pos, { n: meus.length,
        pct: 100 * meus.filter((r) => atende(r, thr)).length / meus.length });
    }).filter((x) => x.n >= MIN_AMOSTRAS)
      .sort((a, z) => a.pct - z.pct || a.k.localeCompare(z.k))
      .slice(0, k);
  }

  /* ---------------- avisos do conjunto ativo ---------------- */
  // Os gates de antes, como dados: o painel Conjunto lista todos; Dados e Modelo
  // repetem os críticos, que invalidam os números da própria tela.
  function avisosConjunto(data, rows, enabled, ambiente) {
    const avisos = [];
    const predios = new Set(rows.map((r) => r.b));
    if (predios.size < 2) {
      avisos.push({ sev: 'critical', titulo: 'Menos de 2 locais de coleta no conjunto ativo',
        msg: 'Os folds deixam um local de coleta de fora; com um só, nenhum número aqui generaliza para um prédio novo.',
        causas: ambiente === 'todos' ? ['Ligue um dataset de outro prédio.']
          : [`O filtro de ambiente (${data.ambientes[ambiente]}) deixou ${predios.size} local de coleta. Mude para Todos ou ligue outro dataset.`] });
    }
    if (new Set(rows.map((r) => r.gen)).size > 1) {
      const comN = rows.filter((r) => r.n != null).length;
      avisos.push({ sev: 'warning', titulo: 'Gerações de esquema misturadas',
        msg: `${rows.length.toLocaleString('pt-BR')} linhas ativas, mas só ${comN.toLocaleString('pt-BR')} têm contagem de dispositivos.`,
        causas: ['As linhas legacy não entram na matriz nem na contenção: combo e n_clients só existem a partir de 2026-08-17.',
                 'Geometria (station_x/y/z) também falta nelas, então não aparecem na planta.'] });
    }
    data.datasets.forEach((d) => {
      if (!enabled[d.id]) return;
      if (d.duplicateOf) {
        avisos.push({ sev: 'warning', titulo: `${d.id} é idêntico a ${d.duplicateOf}`,
          msg: 'Os quatro alvos batem exatamente; manter os dois ligados duplica o peso de cada amostra.',
          causas: [], acao: { tipo: 'desligar', ds: d.id } });
      }
      if (d.supersededBy) {
        avisos.push({ sev: 'warning', titulo: `${d.id} está contido em ${d.supersededBy}`,
          msg: 'Todas as suas linhas já existem no outro dataset; mantê-los juntos duplica o peso dessas amostras.',
          causas: [], acao: { tipo: 'desligar', ds: d.id } });
      }
      const fora = (data.locaisDesconhecidos || []).find((x) => x.dataset === d.id);
      if (fora) {
        avisos.push({ sev: 'warning', titulo: `${d.id}: ${fora.linhas} linhas com local desconhecido`,
          msg: `Ficam fora de todas as telas e do treino: ${fora.valores.join(', ')}.`,
          causas: ['Cadastre o prédio em Conjunto > Adicionar dados, ou edite src/ml/core/predios.json.'] });
      }
    });
    return avisos;
  }

  /* ---------------- rascunho do modelo ---------------- */
  function diffRascunho(base, sel) {
    const b = new Set(base);
    const s = new Set(sel);
    return { mais: [...s].filter((f) => !b.has(f)).sort(), menos: [...b].filter((f) => !s.has(f)).sort() };
  }

  const mesmasFeatures = (a, b) => {
    const d = diffRascunho(a, b);
    return !d.mais.length && !d.menos.length;
  };

  // A ativação segue o veredito de QoE (classificador por aplicação, nota por prédio); o de
  // promoção da regressão continua na tela, mas não trava. `qoe` é a resposta de api/modelos/avaliar_qoe.
  function podeAtivar(aval, atual, qoe) {
    if (!aval || !atual) return { ok: false, motivo: 'Espere a avaliação do rascunho atual terminar.' };
    const v = qoe && qoe.promocao_qoe;
    if (!v) return { ok: false, motivo: 'Sem veredito de QoE contra a versão ativa: espere a avaliação de QoE.' };
    const cob = aval.cobertura;
    if (!cob || (cob.nivel !== '100%' && cob.nivel !== 'proxy')) {
      const lacunas = cob ? cob.lacunas.map((l) => l.feature).join(', ') : '';
      return { ok: false, motivo: `O rascunho é "TR-069 parcial" (${lacunas}): salve para estudar; ativar daqui exige 100% TR-069 ou proxy.` };
    }
    const contra = v.predios_contra || [];
    if (v.resultado === 'melhor' && contra.length) {
      return { ok: false, motivo: `O QoE diz "melhor", mas piora em ${contra.join(', ')}: para ativar mesmo assim, salve e use o menu do cartão.` };
    }
    if (v.resultado !== 'melhor') {
      return { ok: false, motivo: 'O veredito de QoE não diz "melhor": para ativar mesmo assim, salve e use o menu do cartão.' };
    }
    return { ok: true, motivo: '' };
  }

  // Decisão de pedir o QoE: há rascunho diferente da ativa e o que está guardado é de outra chave
  // (ou de nenhuma). Idempotente por chave: em voo ou pronto, não repete.
  function precisaPedirQoe(e) {
    return !!e.temSel && !e.igualAtiva && e.qoeKey !== e.chaveQoe;
  }

  // Número principal do cartão de versão: a nota de QoE, se a versão já foi avaliada com ela.
  function notaCartao(v) {
    const a = (v && v.avaliacao) || {};
    const ac = a.atende_completo && a.atende_completo.media != null ? a.atende_completo.media : null;
    const q = a.qoe && a.qoe.modelo && a.qoe.modelo.nota != null ? a.qoe : null;
    if (q) return { valor: q.modelo.nota, rotulo: `QoE (${q.perfil})`, secundario: ac };
    return { valor: ac, rotulo: 'atende', secundario: null };
  }

  // Agendador da avaliação reativa: `pedir(estado)` espera `atraso` ms sem pedidos novos e
  // decola `executar(estado)`, que devolve uma Promise. Só um voo por vez: o que chega
  // durante um voo fica pendente, e só o último estado decola quando ele pousa.
  function vooUnico(executar, opcoes) {
    const atraso = opcoes && opcoes.atraso != null ? opcoes.atraso : 800;
    let pendente = null;
    let temPendente = false;
    let voando = false;
    let relogio = null;
    function decolar() {
      relogio = null;
      if (voando || !temPendente) return;
      const estado = pendente;
      pendente = null; temPendente = false; voando = true;
      Promise.resolve().then(() => executar(estado)).catch(() => {}).then(() => {
        voando = false;
        if (temPendente && !relogio) decolar();
      });
    }
    return {
      pedir(estado) {
        pendente = estado; temPendente = true;
        if (relogio) clearTimeout(relogio);
        relogio = setTimeout(decolar, atraso);
      },
      cancelar() {
        if (relogio) clearTimeout(relogio);
        relogio = null; pendente = null; temPendente = false;
      },
    };
  }

  // Cor da bolinha do chip: verde quando a produção lê pelo TR-181, âmbar com proxy ou
  // extensão, vermelho quando não há caminho (laboratório).
  function corTr181(t) {
    const s = (t || {}).status;
    if (s === 'padrao' || s === 'derivavel') return 'ok';
    if (s === 'proxy' || s === 'extensao') return 'mid';
    return 'lab';
  }

  // Grupos do campo "Adicionar": colunas liberadas fora do rascunho que casam com a busca.
  // Sugerida = ganho ≥ ganho_min e melhora em todos os locais (job de sugestões).
  function agruparColunas(cols, sel, sug, busca) {
    const naSel = new Set(sel);
    const f = (busca || '').trim().toLowerCase();
    const ganho = sug ? Object.fromEntries(sug.ganho.map((g) => [g.coluna, g])) : {};
    const sugerida = (c) => {
      const g = ganho[c.coluna];
      return !!g && g.delta >= sug.ganho_min && g.melhora === g.locais;
    };
    const pontos = (c) => (ganho[c.coluna] ? ganho[c.coluna].delta : -Infinity);
    const ordem = (a, b) => (pontos(b) - pontos(a)) || ((b.rho || 0) - (a.rho || 0)) || a.coluna.localeCompare(b.coluna);
    const livres = cols.filter((c) => c.liberada && !naSel.has(c.coluna) && (!f || c.coluna.toLowerCase().includes(f)));
    const resto = livres.filter((c) => !sugerida(c));
    return {
      sugeridas: livres.filter(sugerida).sort(ordem),
      tr069: resto.filter((c) => corTr181(c.tr181) !== 'lab').sort(ordem),
      laboratorio: resto.filter((c) => corTr181(c.tr181) === 'lab').sort(ordem),
      ganho,
    };
  }

  // Próximo nome livre a partir da ativa: v3-tr069 -> v4-tr069 (ou o primeiro livre depois).
  function sugerirNome(ativo, nomes) {
    const m = ativo.match(/^(\D*)(\d+)(.*)$/);
    const gerar = m ? (i) => m[1] + i + m[3] : (i) => `${ativo}-${i}`;
    let i = m ? Number(m[2]) + 1 : 2;
    while (nomes.includes(gerar(i))) i += 1;
    return gerar(i);
  }

  function descricaoRascunho(d, sufixo) {
    const partes = d.mais.map((f) => '+' + f).concat(d.menos.map((f) => '−' + f));
    return ((partes.join(' ') || 'sem mudança de features') + (sufixo ? ' · ' + sufixo : '')).slice(0, 500);
  }

  // Uma versão salva antes de uma coluna virar vazamento ainda a lista; o rascunho começa sem ela.
  function semVazamento(features, vazadas) {
    const fora = new Set(vazadas || []);
    return { features: features.filter((f) => !fora.has(f)), removidas: features.filter((f) => fora.has(f)) };
  }

  // O rascunho começa sem as colunas com vazamento da base: tirá-las não é mudança do usuário.
  const diffContraBase = (base, vazadas, sel) => diffRascunho(semVazamento(base, vazadas).features, sel);

  return { METRICAS, MIN_AMOSTRAS, FOLGA_PCT, reprova, atende, mediana, chavePos, posicoes, daPosicao,
           reprovacao, gargalo, celulas, semContagem, contencao, piores, avisosConjunto,
           diffRascunho, mesmasFeatures, podeAtivar, notaCartao, precisaPedirQoe, vooUnico, corTr181, agruparColunas,
           sugerirNome, descricaoRascunho, semVazamento, diffContraBase };
});
