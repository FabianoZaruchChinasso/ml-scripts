/* Testes de src/studio/web/logica.js: node --test tests/js/logica.test.js */
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../../src/studio/web/logica.js');

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
