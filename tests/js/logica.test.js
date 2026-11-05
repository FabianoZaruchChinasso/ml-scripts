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

const AVAL = (extra = {}) => Object.assign({ cobertura: { nivel: '100%', lacunas: [] } }, extra);
const COMODO = (resultado) => ({ resultado, nota: 0.7, nota_base: 0.6, diferenca: 0.1 });

test('podeAtivar segue o veredito por cômodo e exige cobertura implantável', () => {
  assert.deepEqual(L.podeAtivar(AVAL(), true, COMODO('melhor')), { ok: true, motivo: '' });
  assert.equal(L.podeAtivar(AVAL(), false, COMODO('melhor')).ok, false);
  assert.equal(L.podeAtivar(null, true, COMODO('melhor')).ok, false);
  assert.match(L.podeAtivar(AVAL(), true, null).motivo, /^Sem veredito por cômodo contra a versão ativa/);
  assert.match(L.podeAtivar(AVAL(), true, {}).motivo, /^Sem veredito por cômodo contra a versão ativa/);
  assert.match(L.podeAtivar(AVAL(), true, COMODO('empate')).motivo, /por cômodo não diz "melhor"/);
  assert.match(L.podeAtivar(AVAL(), true, COMODO('pior')).motivo, /por cômodo não diz "melhor"/);
  const parcial = AVAL({ cobertura: { nivel: 'parcial', lacunas: [{ feature: 'client_mode' }] } });
  assert.match(L.podeAtivar(parcial, true, COMODO('melhor')).motivo, /TR-069 parcial" \(client_mode\)/);
  assert.equal(L.podeAtivar(AVAL({ cobertura: { nivel: 'proxy', lacunas: [] } }), true, COMODO('melhor')).ok, true);
});

test('notaCartao usa a régua por cômodo, trata 0 como valor e sem ela pede reavaliação', () => {
  const com = { avaliacao: { comodo: { nota: 0.722, contra_piso: { diferenca: 0.27 } }, atende_completo: { media: 0.65 } } };
  assert.deepEqual(L.notaCartao(com), { valor: 0.722, rotulo: 'cômodo', secundario: 0.27 });
  const zero = { avaliacao: { comodo: { nota: 0, contra_piso: { diferenca: 0 } } } };
  assert.deepEqual(L.notaCartao(zero), { valor: 0, rotulo: 'cômodo', secundario: 0 });
  const soQoe = { avaliacao: { qoe: { perfil: 'norma', modelo: { nota: 0.66 } }, atende_completo: { media: 0.64 } } };
  assert.deepEqual(L.notaCartao(soQoe), { valor: 0.64, rotulo: 'reavaliar', secundario: null });
  assert.deepEqual(L.notaCartao({}), { valor: null, rotulo: 'reavaliar', secundario: null });
});

test('precisaPedirComodo: pede quando a chave mudou, mesmo com a anterior em voo; não repete a mesma', () => {
  const base = { temSel: true, igualAtiva: false, comodoKey: 'A', chaveComodo: 'A' };
  assert.equal(L.precisaPedirComodo(base), false);
  assert.equal(L.precisaPedirComodo({ ...base, comodoKey: 'B' }), true);
  assert.equal(L.precisaPedirComodo({ ...base, comodoKey: null }), true);
  assert.equal(L.precisaPedirComodo({ ...base, comodoKey: 'B', igualAtiva: true }), false);
  assert.equal(L.precisaPedirComodo({ ...base, comodoKey: 'B', temSel: false }), false);
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

test('semVazamento: tira do rascunho as colunas marcadas e diz quais saíram', () => {
  assert.deepEqual(L.semVazamento(['router_snr', 'router_tx_retries', 'router_noise'], ['router_tx_retries']),
    { features: ['router_snr', 'router_noise'], removidas: ['router_tx_retries'] });
  assert.deepEqual(L.semVazamento(['router_snr'], undefined), { features: ['router_snr'], removidas: [] });
});

test('diffContraBase: colunas com vazamento tiradas da base não contam como mudança do rascunho', () => {
  const base = ['router_snr', 'router_tx_retries', 'router_noise'];
  assert.deepEqual(L.diffContraBase(base, ['router_tx_retries'], ['router_snr', 'router_noise']), { mais: [], menos: [] });
  assert.deepEqual(L.diffContraBase(base, ['router_tx_retries'], ['router_snr', 'router_power_dbm']),
    { mais: ['router_power_dbm'], menos: ['router_noise'] });
  assert.deepEqual(L.diffContraBase(base, undefined, ['router_snr']), { mais: [], menos: ['router_noise', 'router_tx_retries'] });
});

test('linhasComodo: acerto por prédio, nota do cartão e piso vêm da régua guardada', () => {
  const pos = (site, pos, real, previsto) => ({ site, pos, real, previsto });
  const versoes = [
    { nome: 'v1', avaliacao: { comodo: { datasets: ['b', 'a'], ambiente: 'todos', nota: 0.7222, intervalo: [0.5, 0.9],
      piso: { nota: 0.45, intervalo: [0.3, 0.6] },
      posicoes: [pos('x', 'p2', 'bom', 'ruim'), pos('x', 'p1', 'bom', 'bom'), pos('y', 'q1', 'ruim', 'ruim')],
      piso_posicoes: [pos('x', 'p1', 'bom', 'ruim'), pos('y', 'q1', 'ruim', 'ruim')] } } },
    { nome: 'v2', avaliacao: {} },
    { nome: 'v3', avaliacao: { comodo: { datasets: ['a'], ambiente: 'domestico', nota: 0.5, intervalo: null,
      piso: { nota: 0.45, intervalo: null }, posicoes: [pos('x', 'p1', 'bom', 'bom')], piso_posicoes: [] } } },
  ];
  const r = L.linhasComodo(versoes, ['a', 'b'], 'todos');
  assert.equal(r.linhas[0].nota, 0.7222);
  assert.equal(r.linhas[0].desatualizada, '');
  assert.deepEqual([r.linhas[0].predios.x.acertos, r.linhas[0].predios.x.n], [1, 2]);
  assert.deepEqual(r.linhas[0].predios.x.itens.map((i) => i.pos), ['p1', 'p2']);   // ordenado por posição
  assert.deepEqual([r.linhas[0].predios.y.acertos, r.linhas[0].predios.y.n], [1, 1]);
  assert.equal(r.linhas[1].sem, true);
  assert.equal(r.linhas[2].desatualizada, 'datasets diferentes, ambiente diferente');
  assert.equal(r.piso.nota, 0.45);
  assert.equal(r.piso.predios.x.acertos, 0);
});
