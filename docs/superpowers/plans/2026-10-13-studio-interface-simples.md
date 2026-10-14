# QoE Studio: interface simplificada — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar as nove telas do QoE Studio por duas áreas (Dados e Modelo), um painel de conjunto ativo e um Laboratório, com o rascunho do modelo reavaliado sozinho a cada mudança.

**Architecture:** Só o front muda de forma, mais um parâmetro novo no backend (`contra=` em `api/modelos/avaliar`). As regras puras (filtros, gargalo, diff do rascunho, trava de ativação, agendador da avaliação) ficam em `static/logica.js`, carregado no navegador e testado no Node. Cada área é um módulo com estado próprio que expõe `render(ctx)`; `studio.js` guarda o estado global, as rotas e o chip do conjunto. As views antigas de Features e Paralelos vão para o Laboratório sem mudar de comportamento.

**Tech Stack:** Python 3.12 + FastAPI (backend, testes com `unittest`), JavaScript puro sem build (front), `node --test` (Node 18) para `logica.js`, `google-chrome --headless` para as screenshots.

**Spec:** `docs/superpowers/specs/2026-10-13-studio-interface-simples-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit` nem `git push`.** O usuário faz os dois à mão. No fim de cada task, o passo "Commit" lista os arquivos e a mensagem sugerida; pare ali e avise que está pronto para o commit. As mensagens não levam linha `Co-Authored-By`.
- Sem emojis em nenhum arquivo: ícones são SVG inline (`<svg class="icon"><use href="#i-..."/></svg>`), como no resto do Studio.
- Mantenha o estilo do código atual: 2 espaços, `'use strict'`, IIFE por arquivo, comentários em português explicando o porquê.
- Rode os comandos a partir da raiz do repositório (`/home/venko/ml/TR069/ml-scripts`).
- Comandos de teste:
  - Python, rotas do Studio: `cd tests && ../venv/bin/python -m unittest test_studio_assistente` (cerca de 1 min);
  - Python, suíte inteira: `venv/bin/python -m unittest discover -s tests`;
  - JS: `node --test tests/js/logica.test.js`.
- Para ver o Studio rodando: `venv/bin/python src/ml/studio.py --port 8100` e abra `http://127.0.0.1:8100`.

## Como este plano foi conferido

Antes da entrega, o plano inteiro foi aplicado numa cópia do repositório (`4d0ad57`), com os blocos de código exatamente como estão aqui:
- todos os trechos "troque X por Y" casaram uma única vez com o código atual;
- `node --check` passou em todos os `.js`, e `node --test` passou com 20 testes;
- `test_studio_assistente` passou com 64 testes;
- `tests/studio_screenshots.sh` rodou sem erro no console nas oito telas;
- um clique simulado (cartão da `v5`, depois tirar `router_snr`) mostrou o veredito "Pior que v1" e a barra fixa com a trava.

Se um trecho "troque" não casar, o código mudou depois de `4d0ad57`: leia o arquivo e adapte, sem forçar.

## Bug conhecido que o plano corrige

`static/modelos.js:128` tem `const chaveDesenho = () => chaveDesenho() + '|' + st.escopo;`, que chama a si mesma. Isso estoura a pilha toda vez que o cartão "Desenhar melhor modelo" é desenhado. A Task 16 extrai esse cartão para `desenho.js` com a versão certa: `chaveConj() + '|' + st.escopo`.

## Mapa de arquivos

| Arquivo | Estado | Responsabilidade |
|---|---|---|
| `src/ml/studio/api.py` | modificar | `contra=` em `modelos_avaliar` |
| `src/ml/studio/static/logica.js` | criar | regras puras: métricas, gargalo, avisos do conjunto, diff do rascunho, trava de ativação, voo único, grupos de colunas, nome e descrição sugeridos |
| `src/ml/studio/static/util.js` | criar | helpers de página partilhados: `esc`, `num`, `pedir`, `post`, `gate`, selos TR-181, preservar foco ao redesenhar |
| `src/ml/studio/static/index.html` | modificar | casca nova: barra do topo, três áreas, painel Conjunto |
| `src/ml/studio/static/styles.css` | modificar | barra do topo, painel, matriz nova, cartões, chips, barra fixa |
| `src/ml/studio/static/studio.js` | reescrever | estado global, `V.app`, rotas e redirecionamentos, chip, tema |
| `src/ml/studio/static/conjunto.js` | criar | painel Conjunto: avisos, pendências, ambiente, datasets |
| `src/ml/studio/static/dados.js` | criar | área Dados: limiares, matriz, planta, detalhe da posição, "ver todas" |
| `src/ml/studio/static/modelo.js` | criar | área Modelo: alvo, cartões, comparação, rascunho, avaliação reativa, veredito, barra fixa, receitas |
| `src/ml/studio/static/desenho.js` | criar | "Desenhar melhor modelo", extraído de `modelos.js` |
| `src/ml/studio/static/laboratorio.js` | criar | área Laboratório: seletor de alvo; desenha Features, Desenho e Paralelos |
| `src/ml/studio/static/graficos.js` | modificar | `drawLines` com `ref` e `compacto`; `hitAt`; `key` nos hits da planta |
| `src/ml/studio/static/planta.js` | modificar | `aoSelecionar` no clique de um ponto |
| `src/ml/studio/static/features.js` | modificar | lê o alvo de `#labAlvo` |
| `src/ml/studio/static/paralelos.js` | modificar | lê o alvo de `#labAlvo`; recarrega `V.areas.modelo` |
| `src/ml/studio/static/assistente.js` | apagar | substituído por `modelo.js` |
| `src/ml/studio/static/modelos.js` | apagar | substituído por `modelo.js` e `desenho.js` |
| `tests/test_studio_assistente.py` | modificar | testes do `contra=` |
| `tests/js/logica.test.js` | criar | testes de `logica.js` |
| `tests/studio_screenshots.sh` | criar | sobe o Studio e tira screenshots das áreas, em claro e escuro |
| `CHANGELOG.md` | modificar | entrada da mudança |

`util.js` não está na tabela da spec. Ele existe porque `esc`, `num`, `pedir` e `gate` hoje estão copiados em cada arquivo, e os quatro módulos novos copiariam de novo. Os módulos antigos (`features.js`, `paralelos.js`, `planta.js`) ficam com as próprias cópias, para não mudarem de comportamento.

Ordem final dos `<script>` no `index.html`: `graficos`, `logica`, `util`, `features`, `paralelos`, `planta`, `desenho`, `conjunto`, `dados`, `modelo`, `laboratorio`, `studio`.

---

# Fase 1 — Casca, Conjunto e Dados

Ao fim desta fase, o Studio tem a barra no topo, as rotas novas, o painel Conjunto e a área Dados nova. As áreas Modelo e Laboratório ainda mostram as telas antigas: o assistente, e as views antigas de Features e Modelos.

> As fases 1 e 2 da spec (Casca + Conjunto e Dados) viraram uma fase só. Pendurar as telas antigas de Dados na casca nova seria código jogado fora uma task depois. A página fica quebrada entre a Task 8 e a Task 9; ao fim da Task 9, volta a funcionar.

### Task 1: `logica.js` com as regras da área Dados

**Files:**
- Create: `src/ml/studio/static/logica.js`
- Create: `tests/js/logica.test.js`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/js/logica.test.js`:

```js
/* Testes de src/ml/studio/static/logica.js: node --test tests/js/logica.test.js */
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../../src/ml/studio/static/logica.js');

const THR = { dn: 4, up: 2, lat: 150, jit: 30 };
const bom = (extra) => Object.assign({ b: 'casa', p: 'sala', n: 1, dn: 10, up: 5, lat: 20, jit: 3 }, extra);
const repete = (n, linha) => Array.from({ length: n }, () => Object.assign({}, linha));

test('atende exige as quatro métricas dentro do limiar, com o limiar incluso', () => {
  assert.equal(L.atende(bom(), THR), true);
  assert.equal(L.atende(bom({ dn: 3.9 }), THR), false);
  assert.equal(L.atende(bom({ lat: 151 }), THR), false);
  assert.equal(L.atende(bom({ dn: 4, lat: 150 }), THR), true);
});

test('gargalo aponta a métrica que mais reprova', () => {
  const rows = repete(6, bom({ dn: 1 })).concat(repete(2, bom({ jit: 99 }))).concat(repete(2, bom()));
  const g = L.gargalo(rows, THR);
  assert.equal(g.metrica, 'dn');
  assert.equal(g.rotulo, 'Download');
  assert.equal(g.pct, 60);
  assert.equal(g.folga, false);
});

test('gargalo com reprovação de até 5% é folga', () => {
  const rows = repete(1, bom({ up: 0 })).concat(repete(19, bom()));
  const g = L.gargalo(rows, THR);
  assert.equal(g.metrica, 'up');
  assert.equal(g.pct, 5);
  assert.equal(g.folga, true);
});

test('gargalo sem linhas é null', () => {
  assert.equal(L.gargalo([], THR), null);
});

test('celulas: menos de 5 amostras vira null e linhas sem n ficam de fora', () => {
  const rows = repete(5, bom({ n: 1 })).concat(repete(4, bom({ n: 2 }))).concat(repete(3, bom({ n: null })));
  const [linha] = L.celulas(rows, THR);
  assert.equal(linha.k, 'casa|sala');
  assert.deepEqual(linha.cells.map((c) => c.n), [5, 4, 0]);
  assert.equal(linha.cells[0].pct, 100);
  assert.equal(linha.cells[1].pct, null);
});

test('semContagem lista só posições sem nenhuma linha com n', () => {
  const rows = [bom({ p: 'sala', n: 1 }), bom({ p: 'sala', n: null }), bom({ p: 'quarto', n: undefined })];
  assert.deepEqual(L.semContagem(rows).map((x) => x.p), ['quarto']);
});

test('contencao: mediana por número de dispositivos, null com poucas amostras', () => {
  const rows = repete(5, bom({ n: 1, dn: 10 })).concat(repete(5, bom({ n: 2, dn: 6 }))).concat(repete(2, bom({ n: 3 })));
  assert.deepEqual(L.contencao(rows, 'dn'), [10, 6, null]);
});

test('piores ordena pela % que atende e ignora posições com menos de 5 amostras', () => {
  const rows = repete(5, bom({ p: 'a' })).concat(repete(5, bom({ p: 'b', dn: 1 }))).concat(repete(2, bom({ p: 'c', dn: 1 })));
  assert.deepEqual(L.piores(rows, THR, 3).map((x) => [x.p, x.pct]), [['b', 0], ['a', 100]]);
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js`
Expected: FAIL com `Cannot find module '../../src/ml/studio/static/logica.js'`.

- [ ] **Step 3: Implementar `logica.js`**

Crie `src/ml/studio/static/logica.js`:

```js
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

  return { METRICAS, MIN_AMOSTRAS, FOLGA_PCT, reprova, atende, mediana, chavePos, posicoes, daPosicao,
           reprovacao, gargalo, celulas, semContagem, contencao, piores };
});
```

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/logica.test.js`
Expected: PASS, 8 testes.

- [ ] **Step 5: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/logica.js`, `tests/js/logica.test.js`.
Mensagem: `feat(QoE Studio): logica.js com as regras puras da área Dados`

---

### Task 2: avisos do conjunto em `logica.js`

Os gates de hoje (`renderGates` em `studio.js`) viram dados. O painel Conjunto lista todos; Dados e Modelo mostram só os críticos.

**Files:**
- Modify: `src/ml/studio/static/logica.js`
- Modify: `tests/js/logica.test.js`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/js/logica.test.js`:

```js
const DATA = {
  ambientes: { domestico: 'Doméstico', corporativo: 'Corporativo' },
  datasets: [{ id: 'a' }, { id: 'b', duplicateOf: 'a' }, { id: 'c', supersededBy: 'a' }],
  locaisDesconhecidos: [{ dataset: 'a', linhas: 12, valores: ['marcelo-garagem'] }],
};
const DOIS_PREDIOS = [bom({ b: 'casa', gen: 'current' }), bom({ b: 'cwpb', gen: 'current' })];

test('avisosConjunto: um prédio só é crítico, com a causa do filtro de ambiente', () => {
  const avisos = L.avisosConjunto(DATA, [bom({ gen: 'current' })], { a: true }, 'domestico');
  assert.equal(avisos[0].sev, 'critical');
  assert.match(avisos[0].causas[0], /Doméstico/);
});

test('avisosConjunto: duplicado e contido ligados viram aviso com ação de desligar', () => {
  const avisos = L.avisosConjunto(DATA, DOIS_PREDIOS, { a: false, b: true, c: true }, 'todos');
  assert.deepEqual(avisos.map((a) => a.acao), [{ tipo: 'desligar', ds: 'b' }, { tipo: 'desligar', ds: 'c' }]);
});

test('avisosConjunto: dataset desligado não gera aviso; local desconhecido do ligado gera', () => {
  const avisos = L.avisosConjunto(DATA, DOIS_PREDIOS, { a: true, b: false, c: false }, 'todos');
  assert.equal(avisos.length, 1);
  assert.match(avisos[0].titulo, /12 linhas com local desconhecido/);
});

test('avisosConjunto: gerações misturadas avisam quantas linhas têm n', () => {
  const rows = DOIS_PREDIOS.concat([bom({ b: 'casa', gen: 'legacy', n: undefined })]);
  const avisos = L.avisosConjunto(DATA, rows, {}, 'todos');
  assert.equal(avisos[0].titulo, 'Gerações de esquema misturadas');
  assert.match(avisos[0].msg, /só 2 têm contagem/);
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js`
Expected: FAIL com `L.avisosConjunto is not a function`.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/static/logica.js`, acrescente esta função logo antes da linha `return { METRICAS, ...`:

```js
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
          causas: ['Acrescente a regra da posição em src/ml/core/sites.py.'] });
      }
    });
    return avisos;
  }
```

E acrescente `avisosConjunto` à lista do `return`:

```js
  return { METRICAS, MIN_AMOSTRAS, FOLGA_PCT, reprova, atende, mediana, chavePos, posicoes, daPosicao,
           reprovacao, gargalo, celulas, semContagem, contencao, piores, avisosConjunto };
```

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/logica.test.js`
Expected: PASS, 12 testes.

- [ ] **Step 5: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/logica.js`, `tests/js/logica.test.js`.
Mensagem: `feat(QoE Studio): avisos do conjunto ativo como dados em logica.js`

---

### Task 3: `util.js` com os helpers de página

Sem teste automático: são helpers de DOM e de `fetch`, exercitados pelas áreas e pelas screenshots.

**Files:**
- Create: `src/ml/studio/static/util.js`

- [ ] **Step 1: Criar o arquivo**

```js
/* util.js — helpers de página partilhados pelas áreas novas (conjunto, dados,
   modelo, desenho, laboratório). features.js, paralelos.js e planta.js mantêm
   cópias próprias, para não mudarem de comportamento. */
(function () {
  'use strict';
  const V = window.VENKO = window.VENKO || {};

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d));
  const pct = (v) => Math.round(v * 100) + '%';
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const icone = (id, cls = 'icon') => `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`;

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }
  const post = (url, corpo) => pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });

  const gate = (sev, titulo, msg, extra = '') => `<div class="gate ${sev}">
    ${icone(sev === 'good' ? 'i-check' : 'i-alert')}
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div>${extra}</div></div>`;

  const ALVOS = [['speedtest_down_mbps', 'Download', 'Mbps'], ['speedtest_up_mbps', 'Upload', 'Mbps'],
    ['latency_ms', 'Latência', 'ms'], ['jitter_ms', 'Jitter', 'ms']];
  const ALVO = Object.fromEntries(ALVOS.map(([k, r, u]) => [k, { rotulo: r, unidade: u }]));

  // Como a produção obtém a coluna pelo TR-181 (core/features.STATUS_TR181).
  const STATUS_TR181 = { padrao: ['ok', 'TR-181 padrão'], derivavel: ['ok', 'derivável do TR-181'],
    proxy: ['mid', 'proxy TR-181'], extensao: ['mid', 'extensão de fabricante'],
    ausente: ['lab', 'sem caminho TR-069'], desconhecido: ['leak', 'TR-181 não classificado'] };
  const NIVEL = { '100%': ['ok', '100% TR-069'], proxy: ['mid', 'TR-069 com proxy'], parcial: ['lab', 'TR-069 parcial'] };
  const tagTr181 = (t) => {
    const [cls, rot] = STATUS_TR181[(t || {}).status] || STATUS_TR181.desconhecido;
    return `<span class="tag ${cls}" title="${esc([(t || {}).caminho, (t || {}).nota].filter(Boolean).join(' · '))}">${rot}</span>`;
  };
  const tagNivel = (cob) => {
    if (!cob) return '';
    const [cls, rot] = NIVEL[cob.nivel] || NIVEL.parcial;
    return `<span class="tag ${cls}">${rot}</span>`;
  };
  const tagLacuna = (l) => {
    const [cls, rot] = STATUS_TR181[l.status] || STATUS_TR181.desconhecido;
    return `<span class="tag ${cls}" title="${esc([rot, l.caminho, l.nota].filter(Boolean).join(' · '))}">${esc(l.feature)}</span>`;
  };

  // Redesenhar com innerHTML apaga o foco, o cursor e os <details> abertos. Isto devolve
  // os três, achando o elemento de novo pelo id ou pelo data-k.
  function seletorDe(el) {
    if (!el || el === document.body) return null;
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.dataset && el.dataset.k) return `[data-k="${CSS.escape(el.dataset.k)}"]`;
    return null;
  }
  function redesenhar(host, html) {
    const el = document.activeElement;
    const sel = host.contains(el) ? seletorDe(el) : null;
    const ini = sel && typeof el.selectionStart === 'number' ? el.selectionStart : null;
    const fim = sel && typeof el.selectionEnd === 'number' ? el.selectionEnd : null;
    const abertos = new Set([...host.querySelectorAll('details[data-k]')].filter((d) => d.open).map((d) => d.dataset.k));
    host.innerHTML = html;
    host.querySelectorAll('details[data-k]').forEach((d) => { if (abertos.has(d.dataset.k)) d.open = true; });
    if (!sel) return;
    const novo = host.querySelector(sel);
    if (!novo) return;
    novo.focus();
    if (ini != null) {
      try { novo.setSelectionRange(ini, fim); } catch (e) { /* select e checkbox não têm cursor */ }
    }
  }

  V.util = { esc, num, sinal, pct, cssv, icone, pedir, post, gate, ALVOS, ALVO, STATUS_TR181,
             tagTr181, tagNivel, tagLacuna, redesenhar };
})();
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/util.js`
Expected: nenhuma saída, código 0.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Arquivo: `src/ml/studio/static/util.js`.
Mensagem: `feat(QoE Studio): util.js com helpers de página partilhados`

---

### Task 4: `graficos.js` — limiar tracejado, modo compacto e clique em marcas

`drawLines` ganha `ref` (linha tracejada do limiar, que entra na escala do eixo y) e `compacto` (margens pequenas, sem rótulo no fim da linha) para os mini-gráficos do detalhe da posição. `hitAt` expõe a mesma busca de marca que o tooltip já faz, para a planta tratar o clique. Os hits da planta passam a levar `key`. Sem as opções novas, o desenho é idêntico ao de hoje.

**Files:**
- Modify: `src/ml/studio/static/graficos.js`

- [ ] **Step 1: Margens, escala e linha de referência em `drawLines`**

Em `graficos.js`, troque o começo de `VENKO.drawLines` (da linha `VENKO.drawLines = function (canvas, spec) {` até a chamada `axes(...)`, inclusive):

```js
  VENKO.drawLines = function (canvas, spec) {
    const { ctx, width, height } = prepare(canvas, spec.height || 300);
    const box = { l: 62, t: 14, w: width - 62 - 104, h: (spec.height || 300) - 14 - 30 };
    box.y = (v) => box.t + box.h - ((v - lo) / (hi - lo)) * box.h;
    const all = spec.series.flatMap((s) => s.points.map((p) => p.v)).filter((v) => v != null);
    let lo = 0;
    let hi = Math.max(...all) * 1.12 || 1;
    const ticks = niceTicks(lo, hi, 4);
    hi = Math.max(hi, ticks[ticks.length - 1]);

    const xs = spec.x.map((_, i) =>
      box.l + (spec.x.length === 1 ? box.w / 2 : (i / (spec.x.length - 1)) * box.w));
    axes(ctx, box, ticks, spec.yFmt || String,
      spec.x.map((t, i) => ({ text: t, x: xs[i] })));
```

por:

```js
  VENKO.drawLines = function (canvas, spec) {
    const H = spec.height || 300;
    const { ctx, width } = prepare(canvas, H);
    // `compacto`: margens pequenas e sem rótulo no fim da linha, para os mini-gráficos.
    const ml = spec.compacto ? 36 : 62;
    const mr = spec.compacto ? 10 : 104;
    const mb = spec.compacto ? 24 : 30;
    const box = { l: ml, t: 14, w: width - ml - mr, h: H - 14 - mb };
    box.y = (v) => box.t + box.h - ((v - lo) / (hi - lo)) * box.h;
    // O limiar entra na escala: a linha tracejada não pode ficar fora do gráfico.
    const all = spec.series.flatMap((s) => s.points.map((p) => p.v)).filter((v) => v != null)
      .concat(spec.ref ? [spec.ref.valor] : []);
    let lo = 0;
    let hi = Math.max(...all) * 1.12 || 1;
    const ticks = niceTicks(lo, hi, spec.compacto ? 3 : 4);
    hi = Math.max(hi, ticks[ticks.length - 1]);

    const xs = spec.x.map((_, i) =>
      box.l + (spec.x.length === 1 ? box.w / 2 : (i / (spec.x.length - 1)) * box.w));
    axes(ctx, box, ticks, spec.yFmt || String,
      spec.x.map((t, i) => ({ text: t, x: xs[i] })));

    if (spec.ref) {
      const Y = Math.round(box.y(spec.ref.valor)) + 0.5;
      ctx.save();
      ctx.strokeStyle = css('--ink-2');
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(box.l, Y); ctx.lineTo(box.l + box.w, Y); ctx.stroke();
      ctx.restore();
      if (spec.ref.rotulo) {
        ctx.fillStyle = css('--ink-muted');
        ctx.font = '10.5px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'bottom';
        ctx.fillText(spec.ref.rotulo, box.l + box.w, Y - 3);
      }
    }
```

- [ ] **Step 2: Sem rótulo no fim da linha no modo compacto**

Ainda em `drawLines`, troque:

```js
      if (last) endLabels.push({ text: s.label, x: xs[last.i] + 10, y: box.y(last.p.v), color: s.color });
```

por:

```js
      if (last && !spec.compacto) endLabels.push({ text: s.label, x: xs[last.i] + 10, y: box.y(last.p.v), color: s.color });
```

- [ ] **Step 3: `key` nos hits da planta**

Em `VENKO.drawFloorPlan`, troque:

```js
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color });
```

por:

```js
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color, key: p.key });
```

- [ ] **Step 4: `hitAt` partilhado pelo tooltip e pelo clique**

Troque o bloco `/* ---------- hover partilhado ---------- */` inteiro (do comentário até o fim de `VENKO.attachTooltip`) por:

```js
  /* ---------- hover e clique partilhados ---------- */
  // Marca mais próxima sob o ponteiro, dentro do raio dela; null fora de qualquer marca.
  VENKO.hitAt = function (canvas, hits, ev) {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    let best = null;
    let bestD = Infinity;
    (hits || []).forEach((h) => {
      const d = Math.hypot(h.x - mx, h.y - my);
      if (d < h.r && d < bestD) { best = h; bestD = d; }
    });
    return best;
  };

  VENKO.attachTooltip = function (canvas, tip, getHits, fmt) {
    function move(ev) {
      const best = VENKO.hitAt(canvas, getHits(), ev);
      if (!best) { tip.style.opacity = 0; return; }
      tip.innerHTML = fmt(best);
      tip.style.opacity = 1;
      const tw = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(canvas.clientWidth - tw, best.x - tw / 2)) + 'px';
      tip.style.top = (best.y - tip.offsetHeight - 12) + 'px';
    }
    canvas.addEventListener('mousemove', move);
    canvas.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
  };
```

- [ ] **Step 5: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/graficos.js`
Expected: nenhuma saída, código 0. O efeito visual é conferido nas screenshots da Task 10.

- [ ] **Step 6: Commit (o usuário faz à mão)**

Arquivo: `src/ml/studio/static/graficos.js`.
Mensagem: `feat(QoE Studio): drawLines com limiar e modo compacto; hitAt para clique`

---

### Task 5: `planta.js` — clicar num ponto seleciona a posição

**Files:**
- Modify: `src/ml/studio/static/planta.js`

- [ ] **Step 1: Ligar o clique quando o contexto trouxer `aoSelecionar`**

Em `render(ctx)`, troque:

```js
    pendentes.forEach(({ p, pl, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      st.hits[p.k] = V.drawFloorPlan(canvas, especificacao(p, pl));
      V.attachTooltip(canvas, wrap.querySelector('.tooltip'), () => st.hits[p.k], tooltip);
    });
```

por:

```js
    pendentes.forEach(({ p, pl, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      st.hits[p.k] = V.drawFloorPlan(canvas, especificacao(p, pl));
      V.attachTooltip(canvas, wrap.querySelector('.tooltip'), () => st.hits[p.k], tooltip);
      // A área Dados abre o detalhe da posição clicada; o cursor só vira mão sobre um ponto.
      if (ctx.aoSelecionar) {
        canvas.addEventListener('mousemove', (ev) => {
          canvas.style.cursor = V.hitAt(canvas, st.hits[p.k], ev) ? 'pointer' : '';
        });
        canvas.addEventListener('click', (ev) => {
          const h = V.hitAt(canvas, st.hits[p.k], ev);
          if (h && h.key) ctx.aoSelecionar(h.key);
        });
      }
    });
```

E atualize o comentário do topo do arquivo:

```js
/* planta.js — planta baixa da área Dados: vetor + foto, só foto, só vetor ou retângulo;
   giro e calibração. dados.js calcula os pontos (os limiares são dele), chama render(ctx)
   e recebe o clique num ponto por ctx.aoSelecionar(chave da posição). */
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/planta.js`
Expected: nenhuma saída, código 0.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Arquivo: `src/ml/studio/static/planta.js`.
Mensagem: `feat(QoE Studio): clique num ponto da planta seleciona a posição`

---

### Task 6: `conjunto.js` — painel do conjunto ativo

O painel junta o que hoje está espalhado:
- o banner de gates;
- a tela Datasets e o botão legacy;
- o seletor de ambiente;
- o passo "Preparar" do assistente e o card "Limites e pendências" do Modelos.

As pendências vêm do servidor e são buscadas mesmo com o painel fechado, para o contador do chip ficar certo.

O módulo depende de `V.app` (criado em `studio.js`, Task 9):
- `V.app.ligar(id, on)`, `V.app.definirLegacy(on)`, `V.app.definirAmbiente(a)`;
- `V.app.atualizarChip()`, `V.app.colunasMudaram()`.

**Files:**
- Create: `src/ml/studio/static/conjunto.js`

- [ ] **Step 1: Criar o arquivo**

```js
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
               dispensadas: new Set() };

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
      <h3>Datasets</h3>${secaoDatasets()}`);
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
    if (t.dataset.ds) V.app.ligar(t.dataset.ds, t.checked);
    if (t.dataset.acao === 'legacy') V.app.definirLegacy(t.checked);
    if (t.name === 'cContadores') responder(U.post('api/contadores', { estado: t.value }));
  });

  V.conjunto = {
    render(ctx) { st.ctx = ctx; carregar(); desenhar(); },
    contagem, abrir, fechar,
    recarregar() { st.chave = null; },
  };
})();
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/conjunto.js`
Expected: nenhuma saída, código 0. O painel é testado no navegador na Task 9.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Arquivo: `src/ml/studio/static/conjunto.js`.
Mensagem: `feat(QoE Studio): painel do conjunto ativo (avisos, pendências, ambiente, datasets)`

---

### Task 7: `dados.js` — área Dados

A área tem quatro partes:
- os limiares da aplicação, como chips com popover;
- a matriz de capacidade agrupada por prédio, ou a planta, pelo alternador;
- o detalhe da posição escolhida: gargalo, quatro mini-gráficos de contenção com o limiar e as barras de reprovação;
- "ver todas as posições", com os gráficos completos de contenção e restrição de hoje.

O módulo depende de `V.app.definirAplicacao(nome)`, `V.app.definirLimiar(key, valor)` e `V.app.atualizar()` (Task 9). O `ctx` que `studio.js` passa traz `{ data, rows, enabled, enabledIds, ambiente, ambientes, legacy, app, personalizado, thr, perfis }`.

**Files:**
- Create: `src/ml/studio/static/dados.js`

- [ ] **Step 1: Criar o arquivo**

```js
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
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/dados.js`
Expected: nenhuma saída, código 0. A área é testada no navegador na Task 9.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Arquivo: `src/ml/studio/static/dados.js`.
Mensagem: `feat(QoE Studio): área Dados com matriz, planta e detalhe da posição`

---

### Task 8: casca nova em `index.html` e `styles.css`

A barra lateral sai e entram a barra do topo, as três áreas e o painel Conjunto. A área Dados ganha a marcação nova. As áreas Modelo e Laboratório recebem a marcação antiga, sem mudança, até as fases 2 e 3: o assistente (`#aBody`) e as views antigas de Features e Modelos (`#fAlvo`, `#fChip`, `#fBody`, `#mAlvo`, `#mBody`, `#pBody`).

A página fica quebrada até a Task 9, porque o `studio.js` atual procura elementos que saem daqui.

**Files:**
- Modify: `src/ml/studio/static/index.html` (reescrever)
- Modify: `src/ml/studio/static/styles.css`

- [ ] **Step 1: Reescrever `index.html`**

Substitua o arquivo inteiro por:

```html
<!doctype html>
<html lang="pt-BR">
<head>
<script>
/* Tema aplicado antes do primeiro paint: fazer isso no studio.js causaria um
   flash claro antes do escuro. Aceita ?theme=dark para links diretos. */
(function () {
  var p = new URLSearchParams(location.search);
  var t = p.get('theme') || localStorage.getItem('qoe-theme');
  if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
})();
</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QoE Studio — Venko</title>
<link rel="stylesheet" href="styles.css?v=12">
</head>
<body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <symbol id="i-bars" viewBox="0 0 24 24"><line x1="5" y1="21" x2="5" y2="11"/><line x1="12" y1="21" x2="12" y2="4"/><line x1="19" y1="21" x2="19" y2="15"/></symbol>
  <symbol id="i-db" viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></symbol>
  <symbol id="i-alert" viewBox="0 0 24 24"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><polyline points="22 4 12 14.01 9 11.01"/></symbol>
  <symbol id="i-equal" viewBox="0 0 24 24"><line x1="5" y1="9" x2="19" y2="9"/><line x1="5" y1="15" x2="19" y2="15"/></symbol>
  <symbol id="i-wifi" viewBox="0 0 24 24"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><line x1="12" y1="20" x2="12.01" y2="20"/><path d="M1.5 9a15 15 0 0 1 21 0"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></symbol>
  <symbol id="i-more" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/></symbol>
  <symbol id="i-undo" viewBox="0 0 24 24"><polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/></symbol>
  <symbol id="i-flask" viewBox="0 0 24 24"><path d="M9 3h6"/><path d="M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3"/><line x1="7" y1="15" x2="17" y2="15"/></symbol>
</defs></svg>

<header class="topo">
  <div class="brand"><svg class="icon" aria-hidden="true"><use href="#i-wifi"/></svg> QoE Studio</div>
  <nav class="abas" aria-label="Áreas">
    <a href="#dados" data-area="dados">Dados</a>
    <a href="#modelo" data-area="modelo">Modelo</a>
  </nav>
  <button class="chip-conjunto" id="chipConjunto" aria-haspopup="dialog" aria-controls="painelConjunto" aria-expanded="false"></button>
  <a class="link-lab" href="#laboratorio" data-area="laboratorio"><svg class="icon" aria-hidden="true"><use href="#i-flask"/></svg> Laboratório</a>
  <button class="btn-icone" id="themeBtn" aria-label="Alternar tema claro ou escuro"><svg class="icon" aria-hidden="true"><use href="#i-moon"/></svg></button>
</header>

<main>
  <section id="area-dados" class="area">
    <div class="area-cab"><div><h1>Dados</h1>
      <p class="sub">Nesta posição, com esta quantidade de gente na rede, a aplicação funciona? Se não, por quê?</p></div></div>
    <div id="dVazio" class="vazio hide"><p>Nenhum dataset ativo.</p><button class="btn-pri" data-acao="conjunto">Abrir Conjunto</button></div>
    <div id="dConteudo">
      <div class="limiares" id="dLimiares"></div>
      <div id="dCritico"></div>
      <div class="dados-grade">
        <div class="card">
          <div class="card-head">
            <div class="seg" role="group" aria-label="Visão"><button data-visao="matriz">Matriz</button><button data-visao="planta">Planta</button></div>
            <button class="linkbtn link" id="dTodas" data-acao="todas" aria-controls="dTodasCorpo">Ver todas as posições</button>
          </div>
          <div id="dMatriz"></div>
          <div id="dPlanta" class="hide">
            <p class="hint">Posições reais de medição, em escala, sem interpolação. Os vazios são onde falta coletar,
              não onde o sinal é ruim. Clique num ponto para ver o detalhe.</p>
            <div class="controls">
              <button class="toggle" id="planGirar" aria-pressed="false"><span class="dot"></span> Retrato</button>
              <button class="toggle hide" id="planFoto" aria-pressed="true"><span class="dot"></span> Foto ao fundo</button>
            </div>
            <div id="planAvisos"></div>
            <div id="plans"></div>
            <div id="planCal" class="hide"></div>
          </div>
        </div>
        <aside class="card detalhe" id="dDetalhe" aria-live="polite"></aside>
      </div>
      <div id="dTodasCorpo" class="hide">
        <div class="card">
          <h2>Queda com dispositivos simultâneos</h2>
          <p class="hint">Mediana por posição com 1, 2 e 3 clientes competindo (desenho <code>combo</code>).
            A linha tracejada é o limiar da aplicação.</p>
          <div class="controls">
            <label for="dMetrica">Métrica</label>
            <select id="dMetrica">
              <option value="dn">Download (Mbps)</option>
              <option value="up">Upload (Mbps)</option>
              <option value="lat">Latência (ms)</option>
              <option value="jit">Jitter (ms)</option>
            </select>
          </div>
          <div class="chartwrap"><canvas id="cContention"></canvas><div class="tooltip" id="tContention"></div></div>
          <div class="serieskey" id="kContention"></div>
        </div>
        <div class="card">
          <h2>Qual métrica reprova mais</h2>
          <p class="hint">Percentual de amostras que falham em cada limiar, por posição. A barra mais alta é o gargalo.</p>
          <div class="chartwrap"><canvas id="cConstraint"></canvas><div class="tooltip" id="tConstraint"></div></div>
          <div class="serieskey" id="kConstraint"></div>
        </div>
      </div>
    </div>
  </section>

  <!-- Provisório até a fase 2: o assistente antigo. -->
  <section id="area-modelo" class="area hide">
    <div id="aBody"></div>
  </section>

  <!-- Provisório até a fase 3: as views antigas de Features e Modelos. -->
  <section id="area-laboratorio" class="area hide">
    <div class="controls">
      <label for="fAlvo">Alvo</label>
      <select id="fAlvo">
        <option value="speedtest_down_mbps">Download (Mbps)</option>
        <option value="speedtest_up_mbps">Upload (Mbps)</option>
        <option value="latency_ms">Latência (ms)</option>
        <option value="jitter_ms">Jitter (ms)</option>
      </select>
      <span class="chip" id="fChip"></span>
    </div>
    <div id="fBody"></div>
    <div class="controls">
      <label for="mAlvo">Alvo</label>
      <select id="mAlvo">
        <option value="speedtest_down_mbps">Download (Mbps)</option>
        <option value="speedtest_up_mbps">Upload (Mbps)</option>
        <option value="latency_ms">Latência (ms)</option>
        <option value="jitter_ms">Jitter (ms)</option>
      </select>
    </div>
    <div id="mBody"></div>
    <div id="pBody"></div>
  </section>
</main>

<div class="veu hide" id="veuConjunto"></div>
<aside class="painel hide" id="painelConjunto" role="dialog" aria-modal="true" aria-labelledby="painelTitulo">
  <div class="painel-cab">
    <h2 id="painelTitulo">Conjunto ativo</h2>
    <button class="btn-icone" data-acao="fechar" aria-label="Fechar o painel"><svg class="icon" aria-hidden="true"><use href="#i-x"/></svg></button>
  </div>
  <div id="painelCorpo"></div>
</aside>

<script src="graficos.js?v=6"></script>
<script src="logica.js?v=1"></script>
<script src="util.js?v=1"></script>
<script src="features.js?v=6"></script>
<script src="modelos.js?v=11"></script>
<script src="paralelos.js?v=3"></script>
<script src="planta.js?v=5"></script>
<script src="assistente.js?v=1"></script>
<script src="conjunto.js?v=1"></script>
<script src="dados.js?v=1"></script>
<script src="studio.js?v=8"></script>

</body>
</html>
```

- [ ] **Step 2: Trocar a barra lateral pela barra do topo em `styles.css`**

Troque o bloco que vai de `body {` até a regra `.sub { ... }` (logo antes de `.controls {`):

```css
body {
  margin: 0; background: var(--plane); color: var(--ink-1);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  display: grid; grid-template-columns: 216px 1fr; min-height: 100vh;
}
.icon { width: 18px; height: 18px; stroke: currentColor; fill: none;
        stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none; }

/* ---------- rail ---------- */
aside { background: var(--surface-1); border-right: 1px solid var(--border);
        padding: 20px 14px; display: flex; flex-direction: column; gap: 4px; }
.brand { display: flex; align-items: center; gap: 9px; padding: 0 8px 18px;
         font-weight: 650; letter-spacing: -0.01em; }
.brand .icon { width: 20px; height: 20px; stroke: var(--s1); }
nav button { display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 9px 10px; border: 0; border-radius: 8px; background: transparent;
  color: var(--ink-2); font: inherit; text-align: left; cursor: pointer; }
nav button:hover { background: color-mix(in srgb, var(--s1) 8%, transparent); color: var(--ink-1); }
nav button[aria-current="true"] { background: color-mix(in srgb, var(--s1) 13%, transparent);
  color: var(--ink-1); font-weight: 600; }
nav button[aria-current="true"] .icon { stroke: var(--s1); }
.rail-foot { margin-top: auto; padding-top: 14px; border-top: 1px solid var(--border);
             font-size: 12px; color: var(--ink-muted); }
.rail-foot b { color: var(--ink-2); font-weight: 600; }

/* ---------- main ---------- */
main { padding: 22px 26px 60px; max-width: 1180px; min-width: 0; }
header.page { display: flex; align-items: flex-start; justify-content: space-between;
              gap: 20px; margin-bottom: 6px; }
h1 { font-size: 19px; margin: 0 0 3px; letter-spacing: -0.01em; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0 0 18px; max-width: 68ch; }
```

por:

```css
body {
  margin: 0; background: var(--plane); color: var(--ink-1);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; min-height: 100vh;
}
.icon { width: 18px; height: 18px; stroke: currentColor; fill: none;
        stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none; }

/* ---------- barra do topo ---------- */
.topo { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 16px;
  padding: 10px 22px; background: var(--surface-1); border-bottom: 1px solid var(--border); }
.brand { display: flex; align-items: center; gap: 9px; font-weight: 650; letter-spacing: -0.01em; }
.brand .icon { width: 20px; height: 20px; stroke: var(--s1); }
.abas { display: flex; gap: 2px; padding: 3px; border-radius: 9px; background: var(--plane); }
.abas a { padding: 5px 16px; border-radius: 7px; color: var(--ink-2); text-decoration: none; font-size: 13.5px; }
.abas a:hover { color: var(--ink-1); }
.abas a[aria-current="true"] { background: var(--surface-1); color: var(--ink-1); font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.chip-conjunto { margin-left: auto; display: inline-flex; align-items: center; gap: 8px; font: inherit;
  font-size: 13px; padding: 5px 12px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface-1); color: var(--ink-2); cursor: pointer; }
.chip-conjunto b { color: var(--ink-1); }
.chip-conjunto .icon { width: 16px; height: 16px; }
.badge { min-width: 20px; padding: 0 7px; border-radius: 999px; background: var(--warning); color: #0b0b0b;
  font-size: 11.5px; font-weight: 650; text-align: center; }
.badge.critico { background: var(--critical); color: #fff; }
.link-lab { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--ink-muted); text-decoration: none; }
.link-lab .icon { width: 15px; height: 15px; }
.link-lab:hover, .link-lab[aria-current="true"] { color: var(--ink-1); }
.btn-icone { display: inline-grid; place-items: center; width: 30px; height: 30px; padding: 0; flex: none;
  border-radius: 8px; border: 1px solid var(--border); background: var(--surface-1); color: var(--ink-2); cursor: pointer; }
.btn-icone .icon { width: 16px; height: 16px; }
.abas a:focus-visible, .chip-conjunto:focus-visible, .link-lab:focus-visible, .btn-icone:focus-visible {
  outline: 2px solid var(--s1); outline-offset: 2px; }
@media (max-width: 700px) {
  .topo { flex-wrap: wrap; padding: 10px 16px; gap: 10px; }
  .chip-conjunto { order: 5; margin-left: 0; width: 100%; justify-content: center; }
}

/* ---------- áreas ---------- */
main { padding: 20px 22px 110px; max-width: 1180px; margin: 0 auto; min-width: 0; }
.area-cab { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap;
  margin-bottom: 14px; }
.area-cab h1 { margin: 0 0 2px; }
.area-cab .sub { margin: 0; }
h1 { font-size: 20px; margin: 0 0 3px; letter-spacing: -0.01em; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0 0 18px; max-width: 68ch; }
.vazio { text-align: center; padding: 50px 16px; color: var(--ink-2); }
@media (max-width: 700px) { main { padding: 16px 16px 130px; } }

/* ---------- painel Conjunto ---------- */
.veu { position: fixed; inset: 0; z-index: 30; background: rgba(0,0,0,.28); }
.painel { position: fixed; top: 0; right: 0; bottom: 0; z-index: 31; width: min(460px, 100%); overflow-y: auto;
  background: var(--surface-1); border-left: 1px solid var(--border); box-shadow: -12px 0 32px rgba(0,0,0,.18);
  padding: 16px 18px 40px; }
.painel-cab { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.painel-cab h2 { font-size: 16px; margin: 0; }
.painel .resumo { font-size: 12.5px; color: var(--ink-2); margin: 0 0 6px; }
.painel h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-muted);
  margin: 18px 0 8px; font-weight: 600; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 9px; overflow: hidden; }
.seg button { font: inherit; font-size: 13px; padding: 5px 12px; border: 0; border-right: 1px solid var(--border);
  background: var(--surface-1); color: var(--ink-2); cursor: pointer; }
.seg button:last-child { border-right: 0; }
.seg button[aria-pressed="true"] { background: var(--s1); color: #fff; }
.seg button:focus-visible { outline: 2px solid var(--s1); outline-offset: -2px; }
.ds { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; gap: 2px 8px; align-items: start;
  padding: 7px 0; border-bottom: 1px solid var(--grid); font-size: 12.5px; cursor: pointer; }
.ds code { overflow-wrap: anywhere; }
.ds > .gate-msg:last-child { grid-column: 2 / -1; }
.ds input { margin-top: 3px; accent-color: var(--s1); }
.aviso-acao { margin-top: 6px; }
```

- [ ] **Step 3: Tirar a matriz e os sliders antigos, deixar `.hide` sem exceção**

Apague o bloco da matriz antiga, que vai de `/* ---------- matrix ---------- */` até `.matrix .collab { ... }`, inclusive. A regra `.legend` logo abaixo **fica**, porque a área Dados usa.

Apague as três regras `.sliders ...`.

Troque `.hide { display: none; }` por:

```css
.hide { display: none !important; }
```

- [ ] **Step 4: Estilos da área Dados**

Acrescente ao fim de `styles.css`:

```css
/* ---------- área Dados ---------- */
.limiares { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 14px; }
.limiares > label { font-size: 12px; color: var(--ink-2); }
.lim { position: relative; }
.chip-lim { font: inherit; font-size: 12.5px; padding: 5px 11px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface-1); color: var(--ink-2); cursor: pointer; }
.chip-lim b { color: var(--ink-1); font-variant-numeric: tabular-nums; }
.chip-lim[aria-expanded="true"] { border-color: var(--s1); }
.chip-lim:focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
.pop { position: absolute; top: calc(100% + 6px); left: 0; z-index: 15; width: 260px; display: grid;
  grid-template-columns: 1fr auto; gap: 6px 10px; align-items: center; padding: 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface-1); box-shadow: 0 8px 24px rgba(0,0,0,.14); }
.pop label { grid-column: 1 / -1; font-size: 12px; color: var(--ink-2); }
.pop output { font-size: 13px; font-variant-numeric: tabular-nums; }
.link { color: var(--s1); font-size: 13px; }
.card-head .link { white-space: nowrap; }
.dados-grade { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr); gap: 16px; align-items: start; }
@media (max-width: 900px) { .dados-grade { grid-template-columns: 1fr; } }
.mtx-cab, .mtx-lin { display: grid; grid-template-columns: minmax(110px, 1.3fr) repeat(3, minmax(0, 1fr));
  gap: 3px; align-items: center; }
.mtx-cab { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-muted); padding: 10px 2px 2px; }
.mtx-cab span:not(:first-child) { text-align: center; }
.mtx-predio { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: var(--ink-2);
  margin: 12px 0 4px; }
.mtx-lin { width: 100%; padding: 2px; margin: 0; border: 1px solid transparent; border-radius: 7px; background: none;
  font: inherit; color: inherit; text-align: left; cursor: pointer; }
.mtx-lin:hover { border-color: var(--border); }
.mtx-lin.sel { border-color: var(--s1); background: color-mix(in srgb, var(--s1) 6%, transparent); }
.mtx-lin:focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
.mtx-rot { font-size: 12.5px; color: var(--ink-1); padding-left: 6px; overflow-wrap: anywhere; }
.cel { padding: 9px 4px; border-radius: 4px; text-align: center; font-size: 13px; font-weight: 600;
  font-variant-numeric: tabular-nums; }
.cel.vazia { background: var(--grid); color: var(--ink-muted); font-weight: 400; }
.nota-sem { margin-top: 10px; }
.detalhe { position: sticky; top: 70px; }
.detalhe h2 { font-size: 16px; margin: 0; }
.det-cab { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.gargalo { margin: 14px 0 6px; padding: 10px 12px; border-radius: 9px; border-left: 3px solid var(--critical);
  background: color-mix(in srgb, var(--critical) 7%, transparent); }
.gargalo.ok { border-left-color: var(--good); background: color-mix(in srgb, var(--good) 7%, transparent); }
.gargalo .label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-muted); }
.gargalo p { margin: 2px 0 0; font-size: 13.5px; }
.minis { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.mini-tit { font-size: 12px; color: var(--ink-2); }
.mini-tit span { color: var(--ink-muted); }
.hbar { display: grid; grid-template-columns: 70px 1fr 44px; gap: 8px; align-items: center; font-size: 12.5px; padding: 3px 0; }
.hbar .trilho { height: 8px; border-radius: 4px; background: var(--grid); overflow: hidden; }
.hbar .trilho i { display: block; height: 100%; background: var(--critical); border-radius: 4px; }
.hbar .num { text-align: right; font-variant-numeric: tabular-nums; }
.pior-pos { display: flex; justify-content: space-between; gap: 10px; width: 100%; padding: 8px 10px; margin-bottom: 6px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface-1); font: inherit; font-size: 13px;
  color: var(--ink-1); text-align: left; cursor: pointer; }
.pior-pos:hover { border-color: var(--s1); }
.pior-pos:focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
#dTodasCorpo { margin-top: 16px; }
```

- [ ] **Step 5: Commit (o usuário faz à mão)**

Nada a rodar: a página só volta a funcionar na Task 9. Faça o commit junto com a Task 9.

---

### Task 9: `studio.js` novo — estado global, `V.app`, rotas e chip

**Files:**
- Modify: `src/ml/studio/static/studio.js` (reescrever)
- Modify: `src/ml/studio/static/modelos.js:128` (bug da recursão, para o Laboratório provisório abrir)

- [ ] **Step 1: Reescrever `studio.js`**

Substitua o arquivo inteiro por:

```js
/* studio.js — estado global do Studio, rotas, chip do conjunto e tema.
   Cada área se desenha sozinha a partir de render(ctx): dados.js, modelo.js e
   laboratorio.js. O painel do conjunto fica em conjunto.js; o desenho de
   gráficos, em graficos.js; as regras puras, em logica.js. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  const { esc } = V.util;

  const AREAS = ['dados', 'modelo', 'laboratorio'];
  // Hashes de antes da reorganização: links salvos continuam abrindo o lugar certo.
  const REDIRECIONA = { matrix: 'dados', contention: 'dados', constraint: 'dados', plan: 'dados',
    thresholds: 'dados', datasets: 'dados', assistente: 'modelo', modelos: 'modelo', features: 'laboratorio' };

  /* Limiares de referência por aplicação: src/ml/core/aplicacoes.json, via payload.
     Editáveis na área Dados, só na sessão. */
  let PERFIS = {};
  const state = { data: null, app: 'Chamada de vídeo', thr: null, personalizado: false, legacy: false,
                  enabled: {}, area: null, ambiente: 'todos' };

  // Provisório: até a fase 2 a área Modelo é o assistente antigo; até a fase 3, o
  // Laboratório são as views antigas de Features e Modelos.
  V.areas = V.areas || {};
  V.areas.modelo = V.areas.modelo || { render: (c) => V.views.assistente.render(c) };
  V.areas.laboratorio = V.areas.laboratorio || { render: (c) => {
    V.views.features.render(c); V.views.modelos.render(c); V.views.paralelos.render(c); } };

  const ambienteDe = (b) => state.data.buildings[b].ambiente;
  function activeRows() {
    return state.data.rows.filter((r) => state.enabled[r.ds]
      && (state.ambiente === 'todos' || ambienteDe(r.b) === state.ambiente));
  }
  const enabledIds = () => Object.keys(state.enabled).filter((id) => state.enabled[id]);

  function ctx() {
    return { data: state.data, rows: activeRows(), enabled: state.enabled, enabledIds: enabledIds(),
             ambiente: state.ambiente, ambientes: state.data.ambientes, legacy: state.legacy,
             app: state.app, personalizado: state.personalizado, thr: state.thr, perfis: PERFIS };
  }

  function renderChip(c) {
    const predios = new Set(c.rows.map((r) => r.b)).size;
    const amb = c.ambiente === 'todos' ? 'todos os ambientes' : c.ambientes[c.ambiente].toLowerCase();
    const n = V.conjunto.contagem();
    const total = n.avisos + n.pendencias;
    const chip = $('#chipConjunto');
    chip.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#i-db"/></svg>
      <span><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras · <b>${predios}</b> prédios · ${esc(amb)}</span>
      ${total ? `<span class="badge${n.critico ? ' critico' : ''}">${total}</span>` : ''}`;
    chip.setAttribute('aria-label', `Conjunto ativo: ${c.rows.length} amostras, ${predios} prédios, ${amb}` +
      (total ? `, ${total} avisos ou pendências` : '') + '. Abrir o painel.');
  }

  function renderAll() {
    if (!state.data || !state.area) return;
    const c = ctx();
    V.conjunto.render(c);
    renderChip(c);
    V.areas[state.area].render(c);
  }

  function show(area) {
    state.area = area;
    AREAS.forEach((a) => $('#area-' + a).classList.toggle('hide', a !== area));
    document.querySelectorAll('[data-area]').forEach((el) =>
      el.setAttribute('aria-current', String(el.dataset.area === area)));
    renderAll();
  }

  function rota() {
    const h = location.hash.slice(1);
    const area = AREAS.includes(h) ? h : (REDIRECIONA[h] || 'dados');
    if (h !== area) history.replaceState(null, '', '#' + area);
    show(area);
    if (h === 'datasets') V.conjunto.abrir();
  }

  function aplicarLegacy(on) {
    state.legacy = on;
    state.data.datasets.forEach((d) => {
      if (d.generation === 'legacy') state.enabled[d.id] = on && !d.supersededBy && !d.duplicateOf;
    });
  }

  V.app = {
    ctx,
    atualizar: renderAll,
    atualizarChip() { if (state.data) renderChip(ctx()); },
    irPara(area) { location.hash = area; },
    ligar(id, on) { state.enabled[id] = on; renderAll(); },
    definirLegacy(on) { aplicarLegacy(on); renderAll(); },
    definirAmbiente(a) { state.ambiente = a; renderAll(); },
    definirAplicacao(app) { state.app = app; state.thr = { ...PERFIS[app] }; state.personalizado = false; renderAll(); },
    definirLimiar(key, valor) { state.thr[key] = valor; state.personalizado = true; renderAll(); },
    // Classificação, contadores ou derivada nova mudam colunas e chaves de cache: quem guarda cache recarrega.
    colunasMudaram() {
      [V.conjunto, V.areas.modelo].concat(Object.values(V.views || {}))
        .forEach((m) => { if (m && m.recarregar) m.recarregar(); });
      renderAll();
    },
  };

  fetch('api/payload').then((r) => r.json()).then((data) => {
    state.data = data;
    PERFIS = data.aplicacoes;
    data.datasets.forEach((d) => { state.enabled[d.id] = d.enabled; });
    const q = new URLSearchParams(location.search);
    // ?legacy=1 liga os datasets legacy de saída: deixa um link reproduzir o conjunto que alguém estava vendo.
    if (q.get('legacy') === '1') aplicarLegacy(true);
    // ?ambiente=domestico|corporativo abre o Studio já filtrado.
    const amb = q.get('ambiente');
    if (amb && data.ambientes[amb]) state.ambiente = amb;
    state.thr = { ...PERFIS[state.app] };

    $('#chipConjunto').addEventListener('click', () => V.conjunto.abrir());
    $('#themeBtn').addEventListener('click', () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      const next = dark ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('qoe-theme', next); } catch (e) { /* modo privado */ }
      renderAll();
    });
    window.addEventListener('hashchange', rota);
    window.addEventListener('resize', renderAll);
    rota();
  });
})();
```

- [ ] **Step 2: Corrigir a recursão em `modelos.js`**

O Laboratório provisório desenha `modelos.js`, que hoje quebra com `RangeError` (veja "Bug conhecido" no topo). Em `src/ml/studio/static/modelos.js`, troque:

```js
  const chaveDesenho = () => chaveDesenho() + '|' + st.escopo;
```

por:

```js
  const chaveDesenho = () => chaveConj() + '|' + st.escopo;
```

- [ ] **Step 3: Conferir a sintaxe de tudo**

Run: `for f in src/ml/studio/static/*.js; do node --check "$f" || echo "FALHOU: $f"; done`
Expected: nenhuma linha `FALHOU`.

- [ ] **Step 4: Abrir no navegador e conferir**

Run: `venv/bin/python src/ml/studio.py --port 8100` e abra `http://127.0.0.1:8100`.

Confira, com o console do navegador aberto (sem erros vermelhos):
- abre em `#dados`, com a barra do topo, a matriz agrupada por prédio e o resumo do conjunto à direita;
- clicar numa linha da matriz abre o detalhe: gargalo, quatro mini-gráficos com a linha tracejada do limiar e as barras de reprovação. O "x" volta ao resumo;
- clicar no chip "Download ≥ …" abre o slider, e arrastar muda a matriz ao vivo sem perder o foco. O seletor vira "Personalizado" e aparece "restaurar". Esc fecha o popover;
- "Planta" mostra a planta, e clicar num ponto abre o detalhe daquela posição;
- "Ver todas as posições" abre os gráficos de contenção (com o limiar) e de restrição;
- o chip do conjunto abre o painel:
  - Esc fecha e Tab não sai do painel;
  - desligar um dataset muda o número de amostras no chip;
  - trocar o ambiente para "Doméstico" filtra a matriz;
- `#matrix` vira `#dados`, `#datasets` vira `#dados` com o painel aberto, `#assistente` vira `#modelo` e `#features` vira `#laboratorio`;
- `#modelo` mostra o assistente antigo, e `#laboratorio` mostra as views antigas de Features e Modelos, sem o `RangeError`;
- o botão de tema alterna entre claro e escuro.

- [ ] **Step 5: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/index.html`, `src/ml/studio/static/styles.css`, `src/ml/studio/static/studio.js`, `src/ml/studio/static/modelos.js`.
Mensagem: `feat(QoE Studio): barra no topo, painel Conjunto e área Dados nova`

---

### Task 10: script de screenshots e conferência visual

As screenshots servem para olhar as telas de verdade e para pegar erro de JavaScript: o Chrome headless imprime o console, e o script falha se aparecer `Uncaught`.

**Files:**
- Create: `tests/studio_screenshots.sh`

- [ ] **Step 1: Criar o script**

```bash
#!/usr/bin/env bash
# Sobe o QoE Studio numa porta própria e tira screenshots das áreas, em claro e escuro,
# com o Chrome headless. Falha se o console do navegador mostrar um erro não tratado.
#
#   tests/studio_screenshots.sh [pasta-de-saida]     (padrão: /tmp/qoe-studio-telas)
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
cd "$raiz"   # core/carga.DATA_DIR é relativo: o servidor precisa rodar da raiz
saida="${1:-/tmp/qoe-studio-telas}"
porta=8199
mkdir -p "$saida"

"$raiz/venv/bin/python" "$raiz/src/ml/studio.py" --port "$porta" >"$saida/servidor.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do
  curl -sf -o /dev/null "http://127.0.0.1:$porta/api/payload" && break
  sleep 1
done

erros=0
# nome|hash|espera em ms (o Modelo avalia o rascunho no servidor, que leva até ~40 s)
for tela in "dados|dados|8000" "conjunto|datasets|8000" "modelo|modelo|60000" "laboratorio|laboratorio|20000"; do
  IFS='|' read -r nome hash espera <<<"$tela"
  for tema in light dark; do
    arquivo="$saida/$nome-$tema.png"
    google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1366,1500 \
      --enable-logging=stderr --v=0 --virtual-time-budget="$espera" \
      --screenshot="$arquivo" "http://127.0.0.1:$porta/?theme=$tema#$hash" 2>"$saida/$nome-$tema.log" || true
    if grep -E "Uncaught|RangeError|TypeError" "$saida/$nome-$tema.log"; then
      echo "ERRO no console: $nome ($tema)"
      erros=1
    fi
    echo "$arquivo"
  done
done
exit "$erros"
```

- [ ] **Step 2: Tornar executável e rodar**

Run: `chmod +x tests/studio_screenshots.sh && tests/studio_screenshots.sh`
Expected: oito caminhos `.png` impressos, nenhuma linha `ERRO no console`, código 0.

- [ ] **Step 3: Olhar as imagens**

Abra `/tmp/qoe-studio-telas/dados-light.png`, `dados-dark.png`, `conjunto-light.png` e `conjunto-dark.png` (com a ferramenta Read, que mostra imagens). Confira:
- a barra do topo cabe numa linha;
- a matriz tem um cabeçalho por prédio;
- os números das células são legíveis nos dois temas;
- o painel cobre a direita com o véu escuro atrás.

Corrija o que estiver quebrado antes de seguir.

- [ ] **Step 4: Commit (o usuário faz à mão)**

Arquivo: `tests/studio_screenshots.sh`.
Mensagem: `test(QoE Studio): screenshots das áreas com checagem de erro no console`

---

# Fase 2 — Modelo

Ao fim desta fase, a área Modelo tem os cartões de versão, o rascunho com chips, a avaliação reativa contra a versão ativa e a barra fixa. O assistente antigo sai.

### Task 11: `contra=` em `api/modelos/avaliar`

Hoje `base` faz dois papéis: diz de qual versão o rascunho herda o denominador e contra qual versão ele é comparado. A área Modelo precisa separar os dois. O rascunho de uma `v4` (eficiência) continua herdando o denominador da `v4`, mas é comparado com a ativa.

**Files:**
- Modify: `src/ml/studio/api.py` (função `modelos_avaliar`)
- Test: `tests/test_studio_assistente.py` (classe `TestDenominadorNaApi`)

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_studio_assistente.py`, acrescente `import json` aos imports do topo e estes métodos ao fim da classe `TestDenominadorNaApi`. O registro dela, `REGISTRO_DEN`, tem a `v1` com denominador `router_snr` e a `v2` absoluta:

```python
  def test_contra_compara_com_outra_versao_e_mantem_o_denominador_da_base(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(
      features='router_snr,router_signal_dbm', ds='a.csv', base='v1', contra='v2'))
    self.assertIn('router_snr', usados)   # o rascunho herda o denominador da base v1
    self.assertIn(None, usados)           # a referência v2 é absoluta

  def test_contra_v1_com_base_v2_inverte_os_papeis(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(
      features='router_snr,router_signal_dbm', ds='a.csv', base='v2', contra='v1'))
    self.assertIn('router_snr', usados)
    self.assertIn(None, usados)

  def test_sem_contra_a_resposta_e_a_de_antes(self):
    sem = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    api._modelos_cache.clear()
    com = dict(api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1', contra='v1'))
    self.assertNotIn('contra', sem)
    self.assertEqual(com.pop('contra'), 'v1')
    # json.dumps compara NaN com NaN; assertEqual em dicionários com NaN falharia.
    self.assertEqual(json.dumps(sem, sort_keys=True, default=str), json.dumps(com, sort_keys=True, default=str))

  def test_contra_entra_na_chave_do_cache(self):
    api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1', contra='v2')
    self.assertEqual(len([k for k in api._modelos_cache if k[0] == 'avaliar']), 2)

  def test_contra_inexistente_e_404(self):
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar(features='router_snr', ds='a.csv', base='v1', contra='v9')
    self.assertEqual(erro.exception.status_code, 404)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd tests && ../venv/bin/python -m unittest test_studio_assistente.TestDenominadorNaApi -v`
Expected: os 5 testes novos FALHAM com `TypeError: modelos_avaliar() got an unexpected keyword argument 'contra'`; os 4 antigos passam.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`, substitua a função `modelos_avaliar` inteira por:

```python
@app.get('/api/modelos/avaliar')
def modelos_avaliar(features: str, ds: str = '', alvo: str = 'speedtest_down_mbps',
                    ambiente: str = '', base: str = '', contra: str = ''):
  feats = _lista(features)
  if not feats:
    raise HTTPException(422, 'escolha pelo menos uma feature')
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  for nome in (base, contra):
    if nome and nome not in registro['versoes']:
      raise HTTPException(404, f'versão {nome!r} não existe')
  # `base` diz de onde o rascunho partiu, e por isso de quem herda o denominador; `contra`
  # diz com quem comparar. Sem `contra`, compara com a própria base, como antes.
  ref = contra or base
  chave = ('avaliar', tuple(conj.datasets), alvo, _ambiente(ambiente), tuple(feats), base, ref) + _chave_versoes()
  if chave not in _modelos_cache:
    vazadas = studio_features.vazadas_do_conjunto(conj)
    # O rascunho herda o denominador da versão de onde partiu (ou da ativa, sem base).
    den_nova = registro['versoes'][base or registro['ativo']].get('denominador') or {}
    den_ref = (registro['versoes'][ref].get('denominador') or {}) if ref else {}
    try:
      studio_features.assert_sem_vazamento(feats, vazadas)
      studio_features._checar_locais(conj.df)
      resumo = studio_features.avaliar(conj, feats, vazadas, denominador=den_nova.get(alvo))
      saida = {'alvo': alvo, 'features': feats, 'resumo': resumo,
               'correlacoes': studio_features.correlacoes(conj.df, feats),
               'fora_do_tr069': core_modelos.fora_do_tr069(feats, conj.tabela),
               'cobertura': core_features.cobertura_tr069(feats, conj.tabela, conj.catalogo)}
      if ref:
        feats_ref = registro['versoes'][ref]['features']
        saida['base'] = base or ref
        if contra:
          saida['contra'] = contra
        saida['resumo_base'] = studio_features.avaliar_versao(conj, feats_ref, vazadas,
                                                              denominador=den_ref.get(alvo))
        saida['delta'] = studio_features.delta_por_local(resumo, saida['resumo_base'])
        pendentes = [f for f in feats if conj.classes.get(f) is not None and conj.classes[f].pendente]
        saida['veredito'] = studio_features.veredito(saida['delta'], int(conj.df['_site'].nunique()),
                                                     pendentes, studio_features.UNIDADES[alvo])
        saida['promocao'] = _promocao(ds, ambiente, alvo, feats, feats_ref, conj, den_nova, den_ref)
    except (ValueError, AssertionError) as erro:
      raise HTTPException(422, str(erro))
    _modelos_cache[chave] = saida
  return _modelos_cache[chave]
```

Sem `contra`, `ref` é `base`, e as chaves `base`, `resumo_base`, `delta`, `veredito` e `promocao` saem iguais às de antes. A chave `contra` só aparece quando o parâmetro vem.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd tests && ../venv/bin/python -m unittest test_studio_assistente -v 2>&1 | tail -5`
Expected: `OK`, com 64 testes (eram 59).

- [ ] **Step 5: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/api.py`, `tests/test_studio_assistente.py`.
Mensagem: `feat(QoE Studio): avaliar aceita contra= para separar a referência da base`

---

### Task 12: regras do rascunho em `logica.js`

As regras são:
- `diffRascunho` e `mesmasFeatures`;
- `podeAtivar`, a trava de "Salvar e tornar ativa";
- `vooUnico`, o agendador da avaliação reativa;
- `agruparColunas`, os grupos do campo "Adicionar";
- `corTr181`, `sugerirNome` e `descricaoRascunho`.

**Files:**
- Modify: `src/ml/studio/static/logica.js`
- Modify: `tests/js/logica.test.js`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/js/logica.test.js`:

```js
test('diffRascunho separa o que entrou do que saiu, em ordem alfabética', () => {
  assert.deepEqual(L.diffRascunho(['b', 'a', 'c'], ['c', 'd', 'a']), { mais: ['d'], menos: ['b'] });
  assert.equal(L.mesmasFeatures(['b', 'a'], new Set(['a', 'b'])), true);
  assert.equal(L.mesmasFeatures(['a'], ['a', 'b']), false);
});

const AVAL = (resultado, extra = {}) => Object.assign({
  promocao: { veredito: { resultado, motivo: 'm', predios_contra: [] } },
  cobertura: { nivel: '100%', lacunas: [] },
}, extra);

test('podeAtivar só libera com veredito atual, melhor, sem prédio contra e implantável', () => {
  assert.deepEqual(L.podeAtivar(AVAL('melhor'), true), { ok: true, motivo: '' });
  assert.equal(L.podeAtivar(AVAL('melhor'), false).ok, false);
  assert.equal(L.podeAtivar(null, true).ok, false);
  assert.match(L.podeAtivar(AVAL('empate'), true).motivo, /não diz "melhor"/);
  const contra = AVAL('melhor');
  contra.promocao.veredito.predios_contra = ['casa'];
  assert.match(L.podeAtivar(contra, true).motivo, /piora em casa/);
  const parcial = AVAL('melhor', { cobertura: { nivel: 'parcial', lacunas: [{ feature: 'client_mode' }] } });
  assert.match(L.podeAtivar(parcial, true).motivo, /TR-069 parcial" \(client_mode\)/);
  assert.equal(L.podeAtivar(AVAL('melhor', { cobertura: { nivel: 'proxy', lacunas: [] } }), true).ok, true);
});

const espera = (ms) => new Promise((r) => setTimeout(r, ms));

test('vooUnico: o atraso junta pedidos rápidos num só, com o último estado', async () => {
  const voos = [];
  const v = L.vooUnico((e) => { voos.push(e); return Promise.resolve(); }, { atraso: 5 });
  v.pedir('a'); v.pedir('b'); v.pedir('c');
  await espera(30);
  assert.deepEqual(voos, ['c']);
});

test('vooUnico: mudanças durante um voo geram exatamente mais um voo, com o último estado', async () => {
  const voos = [];
  const pousos = [];
  const v = L.vooUnico((e) => { voos.push(e); return new Promise((r) => pousos.push(r)); }, { atraso: 1 });
  v.pedir('a');
  await espera(20);
  assert.deepEqual(voos, ['a']);
  v.pedir('b'); v.pedir('c');
  await espera(20);
  assert.deepEqual(voos, ['a']);          // ainda voando: ninguém decola
  pousos[0]();
  await espera(20);
  assert.deepEqual(voos, ['a', 'c']);
  pousos[1]();
  await espera(20);
  assert.deepEqual(voos, ['a', 'c']);
});

test('vooUnico: erro no voo não trava a fila; cancelar descarta o pendente', async () => {
  const voos = [];
  const v = L.vooUnico((e) => { voos.push(e); return Promise.reject(new Error('x')); }, { atraso: 1 });
  v.pedir('a');
  await espera(20);
  v.pedir('b');
  await espera(20);
  assert.deepEqual(voos, ['a', 'b']);
  v.pedir('c'); v.cancelar();
  await espera(20);
  assert.deepEqual(voos, ['a', 'b']);
});

const COLS = [
  { coluna: 'router_snr', liberada: true, tr181: { status: 'padrao' }, rho: 0.5 },
  { coluna: 'router_noise', liberada: true, tr181: { status: 'padrao' }, rho: 0.2 },
  { coluna: 'n_clients', liberada: true, tr181: { status: 'proxy' }, rho: 0.4 },
  { coluna: 'client_rssi', liberada: true, tr181: { status: 'ausente' }, rho: 0.6 },
  { coluna: 'router_tx_bytes', liberada: false, motivo: 'vazamento', tr181: { status: 'padrao' }, rho: 0.9 },
];
const SUG = { ganho_min: 0.01, ganho: [
  { coluna: 'router_noise', delta: 0.03, melhora: 4, locais: 4 },
  { coluna: 'n_clients', delta: 0.02, melhora: 3, locais: 4 },
] };

test('agruparColunas: sugeridas melhoram em todos os locais; laboratório separado; bloqueadas e marcadas fora', () => {
  const g = L.agruparColunas(COLS, ['router_snr'], SUG, '');
  assert.deepEqual(g.sugeridas.map((c) => c.coluna), ['router_noise']);
  assert.deepEqual(g.tr069.map((c) => c.coluna), ['n_clients']);
  assert.deepEqual(g.laboratorio.map((c) => c.coluna), ['client_rssi']);
});

test('agruparColunas: busca por nome e sem sugestões ordena por |ρ|', () => {
  const g = L.agruparColunas(COLS, [], null, 'ROUTER');
  assert.deepEqual(g.sugeridas, []);
  assert.deepEqual(g.tr069.map((c) => c.coluna), ['router_snr', 'router_noise']);
});

test('corTr181, sugerirNome e descricaoRascunho', () => {
  assert.equal(L.corTr181({ status: 'derivavel' }), 'ok');
  assert.equal(L.corTr181({ status: 'extensao' }), 'mid');
  assert.equal(L.corTr181(null), 'lab');
  assert.equal(L.sugerirNome('v3-tr069', ['v1', 'v3-tr069', 'v4-tr069']), 'v5-tr069');
  assert.equal(L.sugerirNome('base', ['base']), 'base-2');
  assert.equal(L.descricaoRascunho({ mais: ['a'], menos: ['b'] }, 'download: melhor'), '+a −b · download: melhor');
  assert.equal(L.descricaoRascunho({ mais: [], menos: [] }, ''), 'sem mudança de features');
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js`
Expected: FAIL nos testes novos (`L.diffRascunho is not a function` e afins); os 12 antigos passam.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/static/logica.js`, acrescente logo antes da linha `return { METRICAS, ...`:

```js
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

  // Trava do "Salvar e tornar ativa" (os mesmos textos do antigo passo Publicar). A ativação
  // manual, sem trava, fica no menu do cartão da versão.
  function podeAtivar(aval, atual) {
    if (!aval || !atual) return { ok: false, motivo: 'Espere a avaliação do rascunho atual terminar.' };
    const v = aval.promocao ? aval.promocao.veredito : aval.veredito;
    if (!v) return { ok: false, motivo: 'Sem veredito contra a versão ativa.' };
    const cob = aval.cobertura;
    if (!cob || (cob.nivel !== '100%' && cob.nivel !== 'proxy')) {
      const lacunas = cob ? cob.lacunas.map((l) => l.feature).join(', ') : '';
      return { ok: false, motivo: `O rascunho é "TR-069 parcial" (${lacunas}): salve para estudar; ativar daqui exige 100% TR-069 ou proxy.` };
    }
    const contra = v.predios_contra || [];
    if (v.resultado === 'melhor' && contra.length) {
      return { ok: false, motivo: `A régua diz "melhor", mas piora em ${contra.join(', ')}: para ativar mesmo assim, salve e use o menu do cartão.` };
    }
    if (v.resultado !== 'melhor') {
      return { ok: false, motivo: 'A régua de promoção não diz "melhor": para ativar mesmo assim, salve e use o menu do cartão.' };
    }
    return { ok: true, motivo: '' };
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
```

E troque o `return` final por:

```js
  return { METRICAS, MIN_AMOSTRAS, FOLGA_PCT, reprova, atende, mediana, chavePos, posicoes, daPosicao,
           reprovacao, gargalo, celulas, semContagem, contencao, piores, avisosConjunto,
           diffRascunho, mesmasFeatures, podeAtivar, vooUnico, corTr181, agruparColunas,
           sugerirNome, descricaoRascunho };
```

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/logica.test.js`
Expected: PASS, 20 testes.

- [ ] **Step 5: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/logica.js`, `tests/js/logica.test.js`.
Mensagem: `feat(QoE Studio): regras do rascunho e agendador da avaliação reativa`

---

### Task 13: `modelo.js` — área Modelo

O módulo reaproveita a lógica de três lugares:
- do `assistente.js`: sugestões, receitas, publicar e outros alvos;
- do `modelos.js`: comparação, motivo de "desatualizada" e selo de eficiência;
- de `logica.js`: diff, trava, voo único e grupos.

O estado fica em memória.

Ele depende de `V.app.colunasMudaram()`, `V.app.irPara()` e `V.conjunto.abrir()` (Fase 1). Expõe `V.areas.modelo = { render, recarregar, carregarRascunho }`; o `carregarRascunho` é usado pelo desenho automático no Laboratório (Fase 3).

**Files:**
- Create: `src/ml/studio/static/modelo.js`

- [ ] **Step 1: Criar o arquivo**

```js
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
    reg: null, regErro: null, regAviso: null, msg: null, erro: null, menu: null, vereditos: {}, pendente: null,
    cols: null, colsKey: null, colsErro: null,
    sug: null, sugKey: null, sugTimer: null,
    base: null, sel: new Set(), desenho: null,
    busca: '', aberto: false, lab: false, destaque: 0, itens: [],
    aval: null, avalKey: null, avalErro: null, avalErroKey: null, avaliando: false, inicio: 0, relogio: null,
    outros: null, outrosKey: null, outrosCarregando: false,
    cmp: null, cmpKey: null, cmpErro: null, comparando: false, cmpAberto: false, metrica: 'r2', cmpHits: null,
    form: null, salvando: false, salvarErro: null,
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
  const diff = () => L.diffRascunho(featsBase(), selLista());
  const sujo = () => { const d = diff(); return d.mais.length + d.menos.length > 0; };
  const igualAtiva = () => L.mesmasFeatures(ativa().features, selLista());
  const pronto = () => !!(st.ctx && st.ctx.enabledIds.length && st.reg);
  // A avaliação depende do conjunto, do rascunho, da base (denominador) e da ativa (referência).
  const chaveAval = () => [chaveConj(), selLista().join(','), st.base, st.reg.ativo].join('|');
  const avalAtual = () => !!st.aval && st.avalKey === chaveAval();
  const promocao = (a) => (a.promocao ? a.promocao.veredito : a.veredito);
  const chaveCmp = () => chaveConj() + '|' + st.reg.ativo + '|' + st.reg.versoes.map((v) => v.nome).join(',');

  /* ---------------- carregamento ---------------- */
  function usarBase(nome) {
    st.base = nome;
    st.sel = new Set(featsBase());
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
      .finally(() => { iniciarSugestoes(); agendar(); desenhar(); });
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

  function avaliarAgora(k) {
    if (!pronto() || k !== chaveAval()) return Promise.resolve();   // o rascunho já mudou: o próximo voo cuida
    st.avalErro = null;
    return U.pedir(urlAvaliar(st.alvo)).then((a) => {
      if (k !== chaveAval()) return;                                   // resposta velha
      st.aval = a; st.avalKey = k; st.avaliando = false;
      // Guardado para o menu "Tornar ativa" do cartão daquela versão.
      if (!sujo()) st.vereditos[st.base + '|' + chaveConj()] = promocao(a).resultado;
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
    if (st.avalKey === k || st.avalErroKey === k) { st.avaliando = false; return; }
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
    st.salvando = true; desenhar();
    U.post('api/modelos', { nome, descricao: f.desc, features: selLista(), ds: st.ctx.enabledIds.join(','),
                            ambiente: st.ctx.ambiente, base: st.base, desenho })
      .then((reg) => {
        st.reg = reg;
        usarBase(nome);
        if (!f.ativar) { st.msg = `Versão ${nome} salva em src/ml/core/modelos.json. Revise no git diff antes do commit.`; return null; }
        return U.post('api/modelos/ativo', { nome })
          .then((reg2) => { st.reg = reg2; st.msg = `Versão ${nome} salva e ativa em src/ml/core/modelos.json. Revise no git diff antes do commit.`; })
          .catch((e) => { st.erro = `Versão ${nome} salva, mas não foi possível ativar: ${e.message}`; });
      })
      .catch((e) => { st.salvarErro = e.message; })
      .finally(() => { st.salvando = false; st.cmpKey = null; iniciarSugestoes(); agendar(); desenhar(); });
  }

  function ativarManual(nome) {
    st.menu = null;
    const conhecido = st.vereditos[nome + '|' + chaveConj()];
    if (conhecido !== 'melhor') {
      const txt = conhecido
        ? `O último veredito de ${nome} contra ${st.reg.ativo} (${U.ALVO[st.alvo].rotulo.toLowerCase()}) foi "${VEREDITO[conhecido].rotulo}".`
        : `Não há veredito de ${nome} contra ${st.reg.ativo} nesta sessão: clique no cartão para avaliar antes.`;
      if (!window.confirm(`${txt}\n\nTornar ${nome} a versão ativa mesmo assim?`)) { desenhar(); return; }
    }
    st.msg = null; st.erro = null;
    U.post('api/modelos/ativo', { nome })
      .then((reg) => { st.reg = reg; st.msg = `${nome} agora é a versão ativa. Revise src/ml/core/modelos.json no git diff antes do commit.`; })
      .catch((e) => { st.erro = `Não foi possível ativar ${nome}: ${e.message}`; })
      .finally(() => { st.cmpKey = null; agendar(); desenhar(); });
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
    const ac = (v.avaliacao || {}).atende_completo;
    const media = ac && ac.media != null ? ac.media : null;
    const motivo = motivoDesatualizada((v.avaliacao || {})[st.alvo]);
    const editando = v.nome === st.base;
    const selos = [U.tagNivel(v.cobertura),
      (v.vazadas || []).length ? `<span class="tag leak" title="${esc(v.vazadas.join(', '))}">${v.vazadas.length} c/ vazamento</span>` : '',
      seloEficiencia(v),
      motivo ? `<span class="tag lab" title="${esc(motivo)}">desatualizada</span>` : '',
      `<span class="tag">${v.features.length} feat.</span>`].join(' ');
    return `<div class="ver${editando ? ' base' : ''}">
      <button class="ver-corpo" data-acao="base" data-nome="${esc(v.nome)}" data-k="ver-${esc(v.nome)}" aria-pressed="${editando}"
        title="${esc(v.descricao || '')}">
        <span class="ver-nome"><code>${esc(v.nome)}</code>${v.ativo ? ' <span class="tag ativa">ativa</span>' : ''}${editando ? ' <span class="tag editando">editando</span>' : ''}</span>
        <span class="ver-num">${media == null ? '–' : num(media, 2)} <small>atende</small></span>
        <span class="ver-barra"><i style="width:${media == null ? 0 : Math.round(media * 100)}%"></i></span>
        <span class="ver-selos">${selos}</span>
      </button>
      ${v.ativo ? '' : `<button class="btn-icone ver-menu" data-acao="menu" data-nome="${esc(v.nome)}" data-k="menu-${esc(v.nome)}"
        aria-haspopup="menu" aria-expanded="${st.menu === v.nome}" aria-label="Mais ações para ${esc(v.nome)}">${icone('i-more')}</button>
      ${st.menu === v.nome ? `<div class="menu" role="menu"><button role="menuitem" data-acao="ativar" data-nome="${esc(v.nome)}">Tornar ativa</button></div>` : ''}`}
    </div>`;
  }

  function secaoVersoes() {
    return `<div class="secao"><div class="secao-cab"><h2>Versões</h2>
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

  function statusSugestoes(n) {
    if (!st.sug || st.sug.status === 'rodando') {
      const u = st.sug && st.sug.progresso && st.sug.progresso[st.sug.progresso.length - 1];
      return `calculando sugestões…${u ? ` ${u.feito}/${u.total}` : ''}`;
    }
    if (st.sug.status === 'erro') return 'sugestões indisponíveis · <button class="linkbtn link" data-acao="refazer-sug">tentar de novo</button>';
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

  function painelVeredito() {
    if (!st.sel.size) return '<p class="hint">Adicione features para avaliar.</p>';
    if (igualAtiva()) {
      return `<div class="veredito igual">${icone('i-equal')}<div><b>Igual à versão ativa</b>
        <div class="gate-msg">O rascunho tem as mesmas features de ${esc(st.reg.ativo)}. Mude alguma, ou clique noutro cartão, para ver o efeito.</div></div></div>`;
    }
    const vivo = st.avaliando ? `<div class="ao-vivo"><span class="giro" aria-hidden="true"></span>
      <span role="status">Reavaliando com a última mudança…</span>
      <span id="mRelogio" aria-hidden="true">${Math.round((Date.now() - st.inicio) / 1000)} s</span></div>` : '';
    if (st.avalErro && !st.avaliando) return U.gate('critical', 'Não foi possível avaliar', esc(st.avalErro));
    if (!st.aval) return vivo || '<p class="hint">Preparando a avaliação…</p>';
    return vivo + cartaoVeredito(st.aval, avalAtual());
  }

  function secaoRascunho() {
    const criticos = L.avisosConjunto(st.ctx.data, st.ctx.rows, st.ctx.enabled, st.ctx.ambiente).filter((a) => a.sev === 'critical');
    return `<div class="secao"><div class="secao-cab"><h2>Rascunho a partir de <code>${esc(st.base)}</code></h2>
        ${st.desenho ? '<span class="tag current" title="ao salvar, a versão guarda a nota aninhada e os passos da seleção">do desenho automático</span>' : ''}</div>
      <div class="ed">${painelFeatures()}
        <div class="painel-ver">${criticos.map((a) => U.gate('critical', esc(a.titulo), esc(a.msg))).join('')}${painelVeredito()}</div></div></div>`;
  }

  /* ---------------- barra fixa ---------------- */
  function formSalvar() {
    const f = st.form;
    return `<div class="dock-form">
      <label for="mNome">Nome</label><input id="mNome" class="minput" maxlength="40" value="${esc(f.nome)}">
      <label for="mDesc">Descrição</label><input id="mDesc" class="minput" maxlength="500" value="${esc(f.desc)}">
      ${st.salvarErro ? `<p class="dock-erro" role="alert">${esc(st.salvarErro)}</p>` : ''}
      <div class="dock-form-acoes"><button class="btn" data-acao="cancelar-salvar">Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-salvar"${st.salvando ? ' disabled' : ''}>${st.salvando ? 'Salvando…' : f.ativar ? 'Salvar e tornar ativa' : 'Salvar versão'}</button></div></div>`;
  }

  function dock() {
    const el = $('#mDock');
    const mostrar = pronto() && !!st.base && sujo();
    el.classList.toggle('hide', !mostrar);
    if (!mostrar) { el.innerHTML = ''; return; }
    const d = diff();
    const atual = avalAtual();
    const v = atual ? promocao(st.aval) : null;
    const pode = L.podeAtivar(st.aval, atual);
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
      ${pode.ok || st.avaliando || !st.aval ? '' : `<p class="dock-motivo" id="mDockMotivo">${esc(pode.motivo)}</p>`}
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
    iniciarSugestoes();
    mudouRascunho();
  }

  function trocarAlvo(alvo) {
    st.alvo = alvo;
    carregarColunas(); iniciarSugestoes(); agendar(); desenhar();
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
      case 'base': escolherBase(b.dataset.nome); break;
      case 'menu': st.menu = st.menu === b.dataset.nome ? null : b.dataset.nome; desenhar(); break;
      case 'ativar': ativarManual(b.dataset.nome); break;
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
        carregarColunas(); carregarReceitas(); iniciarSugestoes(); agendar();
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
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/modelo.js`
Expected: nenhuma saída, código 0.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Faça o commit junto com a Task 14, que liga o arquivo na página.

---

### Task 14: ligar a área Modelo na página

**Files:**
- Modify: `src/ml/studio/static/index.html`
- Modify: `src/ml/studio/static/studio.js`
- Modify: `src/ml/studio/static/styles.css`

- [ ] **Step 1: Marcação da área Modelo**

Em `index.html`, troque:

```html
  <!-- Provisório até a fase 2: o assistente antigo. -->
  <section id="area-modelo" class="area hide">
    <div id="aBody"></div>
  </section>
```

por:

```html
  <section id="area-modelo" class="area hide">
    <div class="area-cab">
      <div><h1>Modelo</h1>
        <p class="sub">Escolha uma versão, mexa nas features e veja na hora se o rascunho melhora contra a versão ativa.</p></div>
      <div class="seg" role="group" aria-label="O que o modelo prevê" id="mAlvos"></div>
    </div>
    <div id="mCorpo"></div>
    <div class="dock hide" id="mDock" aria-label="Rascunho"></div>
  </section>
```

- [ ] **Step 2: Scripts**

Em `index.html`, apague a linha `<script src="assistente.js?v=1"></script>` e acrescente `modelo.js` depois de `dados.js`:

```html
<script src="dados.js?v=1"></script>
<script src="modelo.js?v=1"></script>
<script src="studio.js?v=9"></script>
```

O `?v=` do `studio.js` muda de 8 para 9. O mesmo vale para `styles.css?v=12`, que vira `styles.css?v=13`.

- [ ] **Step 3: Tirar o adaptador provisório do Modelo em `studio.js`**

Troque:

```js
  // Provisório: até a fase 2 a área Modelo é o assistente antigo; até a fase 3, o
  // Laboratório são as views antigas de Features e Modelos.
  V.areas = V.areas || {};
  V.areas.modelo = V.areas.modelo || { render: (c) => V.views.assistente.render(c) };
  V.areas.laboratorio = V.areas.laboratorio || { render: (c) => {
```

por:

```js
  // Provisório: até a fase 3, o Laboratório são as views antigas de Features e Modelos.
  V.areas = V.areas || {};
  V.areas.laboratorio = V.areas.laboratorio || { render: (c) => {
```

- [ ] **Step 4: Estilos da área Modelo**

Acrescente ao fim de `styles.css`:

```css
/* ---------- área Modelo ---------- */
.secao { margin-bottom: 22px; }
.secao-cab { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.secao-cab h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-muted); margin: 0; font-weight: 600; }
.secao-cab h2 code { text-transform: none; letter-spacing: 0; color: var(--ink-1); font-size: 12.5px; }
.secao-cab > .link { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.secao-cab .link .icon { width: 15px; height: 15px; }
.vers { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.ver { position: relative; }
.ver-corpo { display: grid; gap: 4px; width: 100%; height: 100%; padding: 12px; border-radius: 12px; border: 1px solid var(--border);
  background: var(--surface-1); font: inherit; color: inherit; text-align: left; cursor: pointer; }
.ver-corpo:hover { border-color: var(--s1); }
.ver-corpo:focus-visible { outline: 2px solid var(--s1); outline-offset: 2px; }
.ver.base .ver-corpo { border: 2px solid var(--s1); padding: 11px; }
.ver-nome { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding-right: 30px; }
.ver-nome code { font-size: 13px; font-weight: 650; }
.ver-num { font-size: 22px; font-weight: 650; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.ver-num small { font-size: 12px; font-weight: 400; color: var(--ink-muted); }
.ver-barra { height: 5px; border-radius: 3px; background: var(--grid); overflow: hidden; }
.ver-barra i { display: block; height: 100%; background: var(--s1); }
.ver-selos { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.tag.ativa { background: var(--ink-1); border-color: var(--ink-1); color: var(--surface-1); }
.tag.editando { border-color: var(--s1); color: var(--s1); }
.ver-menu { position: absolute; top: 8px; right: 8px; width: 26px; height: 26px; }
.menu { position: absolute; top: 38px; right: 8px; z-index: 12; min-width: 150px; padding: 4px; border-radius: 9px;
  border: 1px solid var(--border); background: var(--surface-1); box-shadow: 0 8px 24px rgba(0,0,0,.14); }
.menu button { display: block; width: 100%; padding: 7px 10px; border: 0; border-radius: 6px; background: none; font: inherit;
  font-size: 13px; color: var(--ink-1); text-align: left; cursor: pointer; }
.menu button:hover, .menu button:focus-visible { background: color-mix(in srgb, var(--s1) 10%, transparent); outline: none; }
.ed { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 14px; align-items: start; }
@media (max-width: 900px) { .ed { grid-template-columns: 1fr; } }
.add-wrap { position: relative; }
.add { display: flex; align-items: center; gap: 8px; padding: 0 12px; border: 1px solid var(--border); border-radius: 10px;
  background: var(--plane); }
.add .icon { width: 16px; height: 16px; color: var(--ink-muted); }
.add input { flex: 1; min-width: 0; padding: 9px 0; border: 0; background: transparent; font: inherit; font-size: 13.5px;
  color: var(--ink-1); outline: none; }
.add:focus-within { border-color: var(--s1); box-shadow: 0 0 0 1px var(--s1); }
.drop { position: absolute; left: 0; right: 0; top: calc(100% + 6px); z-index: 14; max-height: 380px; overflow-y: auto;
  margin: 0; padding: 0; list-style: none; border: 1px solid var(--border); border-radius: 10px; background: var(--surface-1);
  box-shadow: 0 10px 28px rgba(0,0,0,.14); }
.drop .cap { display: flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: 11px; text-transform: uppercase;
  letter-spacing: .05em; color: var(--ink-muted); background: var(--plane); }
.drop .cap button, .drop .cap-status { text-transform: none; letter-spacing: 0; }
.drop .cap-status { margin-left: auto; }
.drop .rodape { background: var(--surface-1); border-top: 1px solid var(--border); }
.drop .rodape .link { display: inline-flex; align-items: center; gap: 6px; }
.drop .rodape .icon { width: 14px; height: 14px; }
.op { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 7px 12px;
  border-top: 1px solid var(--grid); font-size: 13px; cursor: pointer; }
.op code { overflow-wrap: anywhere; }
.op.hl, .op:hover { background: color-mix(in srgb, var(--s1) 9%, transparent); }
.op-ganho { font-size: 12px; color: var(--good); font-variant-numeric: tabular-nums; }
.vazio-op { padding: 7px 12px; font-size: 12.5px; color: var(--ink-muted); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.fchip { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; padding: 3px 4px 3px 9px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--plane); font-size: 12.5px; }
.fchip code { overflow-wrap: anywhere; }
.fchip.novo { border-color: color-mix(in srgb, var(--good) 55%, transparent); background: color-mix(in srgb, var(--good) 8%, transparent); }
.fchip.bloq { border-color: var(--critical); }
.fchip.ausente { border-style: dashed; }
.fchip.removido { opacity: .6; }
.fchip.removido code { text-decoration: line-through; }
.fchip-motivo { font-size: 11px; color: var(--critical); }
.fchip.ausente .fchip-motivo { color: var(--ink-muted); }
.fchip-x { display: inline-grid; place-items: center; width: 20px; height: 20px; padding: 0; border: 0; border-radius: 5px;
  background: none; color: var(--ink-muted); cursor: pointer; }
.fchip-x .icon { width: 12px; height: 12px; }
.fchip-x:hover { background: var(--grid); color: var(--ink-1); }
.fchip-x:focus-visible { outline: 2px solid var(--s1); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex: none; }
.dot.ok { background: var(--good); }
.dot.mid { background: var(--warning); }
.dot.lab { background: var(--critical); }
.legenda-tr { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 12px; font-size: 12px; color: var(--ink-muted); }
.legenda-tr span { display: inline-flex; align-items: center; gap: 5px; }
.painel-feat details.fold { margin: 12px 0 0; }
.painel-ver details.fold { margin: 8px 0 0; }
.ao-vivo { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-muted); margin-bottom: 8px; }
.giro { width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--grid); border-top-color: var(--s1);
  animation: giro .8s linear infinite; }
@keyframes giro { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .giro { animation: none; } }
.veredito.empate { border-left-color: var(--warning); }
.veredito.empate .icon { stroke: var(--warning); }
.veredito.igual { margin-top: 0; }
.nota-atende { margin-top: 10px; }
.dock { position: fixed; left: 50%; bottom: 16px; transform: translateX(-50%); z-index: 18; width: min(1136px, calc(100% - 32px));
  padding: 10px 14px; border-radius: 14px; border: 1px solid var(--border); background: var(--surface-1);
  box-shadow: 0 10px 30px rgba(0,0,0,.18); }
.dock-linha { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; }
.dock-sub { color: var(--ink-muted); }
.dock-mais { color: var(--good); font-weight: 600; }
.dock-menos { color: var(--critical); font-weight: 600; }
.dock-ver { display: inline-flex; align-items: center; gap: 5px; color: var(--ink-2); }
.dock-ver .icon { width: 16px; height: 16px; }
.dock-ver.melhor { color: var(--good); }
.dock-ver.pior { color: var(--critical); }
.dock-acoes { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
.dock-motivo { margin: 6px 0 0; font-size: 12px; color: var(--ink-muted); }
.dock-form { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px 10px; align-items: center; margin-top: 10px;
  padding-top: 10px; border-top: 1px solid var(--border); }
.dock-form label { font-size: 12.5px; color: var(--ink-2); }
.dock-form-acoes { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 8px; }
.dock-erro { grid-column: 1 / -1; margin: 0; font-size: 12.5px; color: var(--critical); }
@media (max-width: 700px) {
  .dock { bottom: 8px; width: calc(100% - 16px); }
  .dock-acoes { margin-left: 0; width: 100%; }
  .dock-form { grid-template-columns: 1fr; }
}
```

- [ ] **Step 5: Conferir a sintaxe**

Run: `for f in src/ml/studio/static/*.js; do node --check "$f" || echo "FALHOU: $f"; done`
Expected: nenhuma linha `FALHOU`.

- [ ] **Step 6: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/modelo.js`, `src/ml/studio/static/index.html`, `src/ml/studio/static/studio.js`, `src/ml/studio/static/styles.css`.
Mensagem: `feat(QoE Studio): área Modelo com cartões, chips e avaliação reativa`

---

### Task 15: conferir a área Modelo no navegador

Os itens abaixo dependem do servidor de verdade (avaliação de cerca de 20 s, gravação em `modelos.json`). Por isso são conferidos à mão, e a avaliação de cada um fica no resumo da task.

**Files:** nenhum, salvo correções.

- [ ] **Step 1: Subir o Studio**

Run: `venv/bin/python src/ml/studio.py --port 8100` e abra `http://127.0.0.1:8100/#modelo` com o console aberto.

- [ ] **Step 2: Percorrer o fluxo**

Confira cada item:
1. Os cartões mostram todas as versões de `modelos.json`. A ativa tem o selo "ativa", e a que está no rascunho tem "editando" e borda azul.
2. Com o rascunho igual à ativa, o painel direito diz "Igual à versão ativa" e a barra fixa não aparece.
3. Clique no × de um chip:
   - o chip fica riscado, com o botão de desfazer;
   - a barra fixa aparece com `−1`;
   - cerca de 0,8 s depois, "Reavaliando com a última mudança… N s" aparece;
   - quando a avaliação termina, o veredito diz "Melhor que", "Empate com" ou "Pior que" a ativa, com três números.
4. Durante uma avaliação, tire mais dois chips. Na aba Network, quando o pedido em voo terminar, sai **um** pedido novo a `api/modelos/avaliar`, não dois.
5. Desfaça as três remoções. O rascunho volta a ser igual à ativa e nada é pedido.
6. Clique no campo "Adicionar feature…". A lista abre:
   - "Sugeridas" mostra "calculando sugestões… n/N" e depois a lista com o ganho;
   - "Outras TR-069" vem em seguida;
   - "Laboratório" está escondido, com o link "mostrar".

   Setas e Enter adicionam o item destacado, e o chip entra em verde. Backspace com o campo vazio tira o último chip. Esc fecha a lista.
7. Clique no cartão de outra versão. Com o rascunho sujo, aparece a confirmação "Descartar o rascunho…?". Ao aceitar, o veredito passa a comparar aquela versão com a ativa.
8. "Comparar por prédio" abre o gráfico de pontos (cerca de 20 s), e "MAE por local" alterna a métrica.
9. Na barra fixa:
   - "Salvar…" abre nome e descrição já preenchidos (por exemplo, `v6` e `+router_noise · download: …`);
   - "Cancelar" fecha;
   - "Salvar e tornar ativa" fica desabilitado, com o motivo embaixo, quando o veredito não é "Melhor";
   - com o rascunho igual à ativa, a barra fixa some.

   **Não confirme o salvar** sem combinar com o usuário: isso grava em `src/ml/core/modelos.json`. Se for gravar para testar, desfaça depois com `git checkout src/ml/core/modelos.json`.
10. O menu "⋯" de um cartão que não é o ativo mostra "Tornar ativa". Clique e **cancele** a confirmação.
11. "+ Criar métrica a partir de receita" abre o painel de receitas dentro do cartão das features.
12. Trocar o alvo para "Latência" mostra "Δ pinball p90" e "Cobertura p90" no veredito.

- [ ] **Step 3: Screenshots**

Run: `tests/studio_screenshots.sh`
Expected: código 0, sem `ERRO no console`. Olhe `modelo-light.png` e `modelo-dark.png`.

- [ ] **Step 4: Commit (o usuário faz à mão), se houve correção**

Mensagem: `fix(QoE Studio): ajustes da área Modelo vistos no navegador`

---

# Fase 3 — Laboratório + limpeza

Ao fim desta fase:
- o Laboratório tem um seletor de alvo único e desenha Features, Desenho e Paralelos;
- o desenho automático manda o resultado para o rascunho da área Modelo;
- `assistente.js` e `modelos.js` saem do repositório.

### Task 16: `desenho.js` — "Desenhar melhor modelo" no Laboratório

O código vem de `modelos.js` (`desenharModelo`, `acompanhar`, `cardDesenho`), com três mudanças:
- `chaveDesenho` sem a recursão;
- o alvo vem de `#labAlvo`;
- "Carregar no editor" vira "Abrir no Modelo", que manda as features para o rascunho da área Modelo junto com o id do job. Ao salvar, a versão guarda a nota aninhada.

**Files:**
- Create: `src/ml/studio/static/desenho.js`

- [ ] **Step 1: Criar o arquivo**

```js
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
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/desenho.js`
Expected: nenhuma saída, código 0.

- [ ] **Step 3: Commit (o usuário faz à mão)**

Faça o commit junto com a Task 17.

---

### Task 17: área Laboratório e limpeza

**Files:**
- Create: `src/ml/studio/static/laboratorio.js`
- Modify: `src/ml/studio/static/index.html`
- Modify: `src/ml/studio/static/features.js`
- Modify: `src/ml/studio/static/paralelos.js`
- Modify: `src/ml/studio/static/studio.js`
- Modify: `src/ml/studio/static/styles.css`
- Delete: `src/ml/studio/static/assistente.js`
- Delete: `src/ml/studio/static/modelos.js`

- [ ] **Step 1: Criar `laboratorio.js`**

```js
/* laboratorio.js — área Laboratório: análises de apoio que mudam pouco no dia a dia.
   Um seletor de alvo (#labAlvo) vale para as três partes: Features, Desenho e Paralelos. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  let ultimo = null;

  function render(ctx) {
    ultimo = ctx;
    V.views.features.render(ctx);
    V.views.desenho.render(ctx);
    V.views.paralelos.render(ctx);
  }

  // features.js e paralelos.js escutam #labAlvo por conta própria; o desenho só redesenha.
  $('#labAlvo').addEventListener('change', () => { if (ultimo) V.views.desenho.render(ultimo); });

  V.areas = V.areas || {};
  V.areas.laboratorio = { render };
})();
```

- [ ] **Step 2: Marcação do Laboratório**

Em `index.html`, troque a seção inteira que começa em `<!-- Provisório até a fase 3: as views antigas de Features e Modelos. -->` e vai até o `</section>` dela por:

```html
  <section id="area-laboratorio" class="area hide">
    <div class="area-cab">
      <div><h1>Laboratório</h1>
        <p class="sub">Análises de apoio: teto de desempenho, desenho automático, paralelos e derivadas. Mudam pouco no dia a dia.</p></div>
      <div class="controls" style="margin:0">
        <label for="labAlvo">Alvo</label>
        <select id="labAlvo">
          <option value="speedtest_down_mbps">Download (Mbps)</option>
          <option value="speedtest_up_mbps">Upload (Mbps)</option>
          <option value="latency_ms">Latência (ms)</option>
          <option value="jitter_ms">Jitter (ms)</option>
        </select>
      </div>
    </div>
    <p><span class="chip" id="fChip"></span></p>
    <div id="fBody"></div>
    <div id="lDesenho"></div>
    <div id="pBody"></div>
  </section>
```

- [ ] **Step 3: Scripts finais**

Em `index.html`, troque o bloco de `<script>` inteiro por:

```html
<script src="graficos.js?v=6"></script>
<script src="logica.js?v=2"></script>
<script src="util.js?v=1"></script>
<script src="features.js?v=7"></script>
<script src="paralelos.js?v=4"></script>
<script src="planta.js?v=5"></script>
<script src="desenho.js?v=1"></script>
<script src="conjunto.js?v=1"></script>
<script src="dados.js?v=1"></script>
<script src="modelo.js?v=1"></script>
<script src="laboratorio.js?v=1"></script>
<script src="studio.js?v=10"></script>
```

e mude o `<link>` para `styles.css?v=14`.

- [ ] **Step 4: `features.js` lê o alvo de `#labAlvo`**

Em `src/ml/studio/static/features.js`, troque:

```js
  $('#fAlvo').addEventListener('change', (ev) => { st.alvo = ev.target.value; carregarInventario(); desenhar(); });
```

por:

```js
  $('#labAlvo').addEventListener('change', (ev) => { st.alvo = ev.target.value; carregarInventario(); desenhar(); });
```

E troque, no comentário do topo, `view Features` por `Features, no Laboratório`. No primeiro gate de `gates()`, troque `Detalhes em Modelos → Limites e pendências dos dados.` por `Detalhes no painel Conjunto.`, e no segundo, `até alguém responder em Modelos → Limites e pendências dos dados.` por `até alguém responder no painel Conjunto.`.

- [ ] **Step 5: `paralelos.js` lê o alvo de `#labAlvo` e avisa a área Modelo**

Em `src/ml/studio/static/paralelos.js`, faça três trocas.

```js
  const alvo = () => $('#mAlvo').value;
```
vira
```js
  const alvo = () => $('#labAlvo').value;
```

```js
  $('#mAlvo').addEventListener('change', () => { carregarColunas(); desenhar(); });
```
vira
```js
  $('#labAlvo').addEventListener('change', () => { carregarColunas(); desenhar(); });
```

```js
          if (V.views.modelos.recarregar) V.views.modelos.recarregar();
```
vira
```js
          // A derivada nova aparece no campo "Adicionar" da área Modelo.
          if (V.areas && V.areas.modelo) V.areas.modelo.recarregar();
```

E troque o comentário do topo por:

```js
/* paralelos.js — no Laboratório: paralelos laboratório × TR-069 e o desenhista de
   derivadas. laboratorio.js chama render(ctx). */
```

- [ ] **Step 6: Tirar o adaptador provisório do Laboratório em `studio.js`**

Troque:

```js
  // Provisório: até a fase 3, o Laboratório são as views antigas de Features e Modelos.
  V.areas = V.areas || {};
  V.areas.laboratorio = V.areas.laboratorio || { render: (c) => {
    V.views.features.render(c); V.views.modelos.render(c); V.views.paralelos.render(c); } };
```

por nada (apague as quatro linhas). As três áreas agora se registram sozinhas em `V.areas`.

- [ ] **Step 7: Apagar os arquivos substituídos**

Run: `rm src/ml/studio/static/assistente.js src/ml/studio/static/modelos.js`

(Só apaga do disco; o `git add`/`git rm` e o commit ficam com o usuário.)

- [ ] **Step 8: Tirar o CSS que ficou sem uso**

Em `styles.css`, apague:
- a seção inteira `/* Assistente (view Modelo) */`, de `.nav-avancado` até `.passo:focus-visible`, inclusive, e a regra `.rodape-passo`. As regras `.grupo`, `.receita`, `.veredito...` e `.btn.marcado`, que estão no meio, **ficam**;
- as regras `.mhead, .mrow`, `.mhead`, `.mrow`, `.mrow.dim`, `.mrow code`, `.mrow .num, .mhead .num`, `.mrow input` e o `@media (max-width: 760px)` que esconde colunas de `.mhead`/`.mrow`;
- o trecho `, .mrow input:focus-visible` na regra de `:focus-visible` que começa com `.minput:focus-visible`.

Depois rode:

Run: `grep -nE 'mrow|mhead|nav-avancado|rail-foot|rodape-passo|\.passo\b|class="passo' src/ml/studio/static/*.css src/ml/studio/static/*.js src/ml/studio/static/*.html`
Expected: nenhuma linha.

- [ ] **Step 9: Conferir a sintaxe e os testes JS**

Run: `for f in src/ml/studio/static/*.js; do node --check "$f" || echo "FALHOU: $f"; done; node --test tests/js/logica.test.js`
Expected: nenhuma linha `FALHOU`; 20 testes passando.

- [ ] **Step 10: Conferir no navegador**

Run: `venv/bin/python src/ml/studio.py --port 8100` e abra `http://127.0.0.1:8100/#laboratorio`.

Confira:
- o link "Laboratório" do topo fica marcado;
- aparecem os cartões de Features, "Desenhar melhor modelo" e Paralelos;
- trocar o alvo para "Upload" recarrega o inventário de Features;
- `#features` e `#modelos` redirecionam para `#laboratorio` e `#modelo`;
- no console, nenhum erro.

Rodar o desenho leva de 3 a 6 minutos. Se der tempo, rode e confira que "Abrir no Modelo" leva para `#modelo` com o selo "do desenho automático" e as features escolhidas no rascunho.

- [ ] **Step 11: Commit (o usuário faz à mão)**

Arquivos: `src/ml/studio/static/desenho.js`, `src/ml/studio/static/laboratorio.js`, `src/ml/studio/static/index.html`, `src/ml/studio/static/features.js`, `src/ml/studio/static/paralelos.js`, `src/ml/studio/static/studio.js`, `src/ml/studio/static/styles.css`, remoção de `assistente.js` e `modelos.js`.
Mensagem: `feat(QoE Studio): Laboratório com Features, Desenho e Paralelos; sai o assistente`

---

### Task 18: verificação final e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests 2>&1 | tail -3 && node --test tests/js/logica.test.js 2>&1 | tail -8`
Expected: `OK` no Python (o total de antes mais 5) e `pass 20`, `fail 0` no Node.

- [ ] **Step 2: Screenshots finais**

Run: `tests/studio_screenshots.sh`
Expected: código 0. Olhe as oito imagens em `/tmp/qoe-studio-telas/`, em claro e escuro: Dados, Conjunto, Modelo e Laboratório.

Pontos de atenção:
- texto legível nas células da matriz e nos chips nos dois temas;
- a barra fixa não cobre o fim da página (o `main` tem 110 px de folga embaixo);
- nenhum cartão vazio ou "Carregando…" preso fora do Modelo.

Na janela estreita, rode também uma screenshot a 390 px de largura:

Run: `google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=390,1400 --virtual-time-budget=8000 --screenshot=/tmp/qoe-studio-telas/dados-estreito.png "http://127.0.0.1:8100/#dados"` (com o Studio no ar na porta 8100)

Expected: sem rolagem horizontal; o chip do conjunto ocupa uma linha própria; o detalhe da posição vai para baixo da matriz.

- [ ] **Step 3: Entrada no CHANGELOG**

Acrescente no topo de `CHANGELOG.md`, antes da primeira entrada atual:

```markdown
# Changelog — QoE Studio: interface simplificada

**Data:** 2026-10-13

## Mudanças

- A barra lateral de nove telas virou uma barra no topo com duas áreas, **Dados** e **Modelo**, um link para o
  **Laboratório** e um chip do conjunto ativo. Hashes antigos (`#matrix`, `#modelos`, `#assistente`, `#datasets`...)
  redirecionam para a área nova.
- **Painel Conjunto** (`static/conjunto.js`): avisos (os antigos gates), pendências (classificar colunas, suspeita de
  vazamento, contadores do roteador), ambiente e datasets com o grupo legacy. O banner fixo de gates saiu; avisos
  críticos aparecem também na tela que eles invalidam.
- **Área Dados** (`static/dados.js`): limiares da aplicação como chips editáveis; matriz de capacidade agrupada por
  prédio ou planta; detalhe da posição com gargalo, contenção com a linha do limiar e reprovação por métrica;
  "ver todas as posições" com os gráficos de contenção e restrição. As telas Capacidade, Contenção, Restrição, Planta
  e Limiares saíram.
- **Área Modelo** (`static/modelo.js`): versões em cartões, comparação por prédio sob demanda, rascunho com chips e
  campo "Adicionar" com sugestões, avaliação que roda sozinha (voo único, 0,8 s depois da última mudança) contra a
  versão ativa, veredito pela régua de promoção e barra fixa para salvar. O assistente de quatro passos e o editor
  "Montar modelo" saíram.
- `GET api/modelos/avaliar` aceita `contra=`: `base` continua dizendo de quem o rascunho herda o denominador, e
  `contra`, com quem ele é comparado. Sem `contra`, a resposta é a de antes.
- **Laboratório** (`static/laboratorio.js`, `static/desenho.js`): Features, Desenhar melhor modelo e Paralelos com um
  seletor de alvo único. "Abrir no Modelo" leva o resultado do desenho para o rascunho.
- Corrigido: `chaveDesenho` em `modelos.js` chamava a si mesma (`RangeError` ao abrir a view Modelos).
- Regras puras em `static/logica.js` (testadas com `node --test tests/js/logica.test.js`); helpers de página em
  `static/util.js`; `tests/studio_screenshots.sh` tira screenshots das áreas e falha com erro no console.

## Verificação

- `venv/bin/python -m unittest discover -s tests` — sem falhas.
- `node --test tests/js/logica.test.js` — 20 testes, sem falhas.
- `tests/studio_screenshots.sh` — oito telas (quatro áreas × claro/escuro), sem erro no console.

---

```

- [ ] **Step 4: Commit (o usuário faz à mão)**

Arquivo: `CHANGELOG.md`.
Mensagem: `docs(changelog): registra a interface simplificada do QoE Studio`
