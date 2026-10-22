# Conserto do Studio atual: salvar versão, vazamento e assistente (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o "Salvar versão" do Studio atual terminar com progresso visível, parar de rodar o assistente sem pedido, tirar colunas com vazamento do rascunho antes de salvar, permitir reavaliar versões antigas que têm vazamento e avisar quando `data/` mudou depois que o Studio subiu.

**Architecture:** Tudo em `src/ml/studio/` (Python e JS). `avaliacao_completa` passa a descartar colunas com vazamento (registrando quais) e a emitir progresso por etapa. `POST /api/modelos` valida na requisição e roda avaliação + gravação + ativação num job (`_iniciar_job`, o mesmo da reavaliação). O front acompanha o job, começa o rascunho sem colunas com vazamento e só roda o assistente quando o botão é clicado.

**Tech Stack:** Python 3.12, FastAPI, JS puro, `unittest`, `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-22-studio-antigo-conserto-design.md` (Parte A).

**Regras do projeto para quem executa:**
- Indentação de 2 espaços no Python e no JS.
- Testes Python: `./venv/bin/python -m unittest <arquivo>` a partir da raiz. JS: `node --test tests/js/logica.test.js`.
- **Não rodar `git commit` nem `git push`.** Nos "Pontos de commit", pare, liste os arquivos e sugira a mensagem (sem `Co-Authored-By`).
- **Não editar `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`** (combinado com o Fabiano). Não editar `src/ml/core/`, `data/`, `mlflow.db`, `mlruns/`. Este plano só toca `src/ml/studio/`, `tests/` e `CHANGELOG.md`.
- Não matar processos que você não iniciou (o Studio do usuário pode estar na porta 8100).

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/studio/api.py` | `avaliacao_completa` (vazamento + progresso), `modelos_salvar` (job), rota `GET /api/modelos/salvar/{id}`, `modelos_reavaliar` (repasse de progresso), `_data_mudou` + payload |
| `src/ml/studio/static/logica.js` | `semVazamento` |
| `src/ml/studio/static/modelo.js` | rascunho sem vazamento, salvar por job, assistente sob pedido, etapa na barra de reavaliação |
| `src/ml/studio/static/conjunto.js` | aviso "data/ mudou" |
| `tests/test_studio_salvar.py` | novo |
| `tests/test_studio_data_mudou.py` | novo |
| `tests/js/logica.test.js` | teste de `semVazamento` |
| `CHANGELOG.md` | entrada nova |

---

### Task 1: `avaliacao_completa` sem colunas com vazamento e com progresso

**Files:**
- Modify: `src/ml/studio/api.py` (função `avaliacao_completa`, perto da linha 309)
- Create: `tests/test_studio_salvar.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_salvar.py`:

```python
import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None)


class TestAvaliacaoCompleta(unittest.TestCase):
  """O peso (LOGO, quantis, limiar) vai para mocks: aqui só importa o que entra em cada etapa."""

  def rodar(self, features, progresso=None):
    patches = {
      'conjunto': mock.patch.object(api, '_conjunto', side_effect=lambda ds, alvo, amb='': (conj(alvo), None)),
      'vazadas': mock.patch.object(api.studio_features, 'vazadas_do_conjunto', return_value=['router_tx_retries']),
      'avaliar': mock.patch.object(api.core_avaliacao, 'avaliar', return_value=({'n': 10}, 'prev')),
      'quantis': mock.patch.object(api, '_prever_quantis', return_value='q'),
      'resumir_quantis': mock.patch.object(api.core_quantis, 'resumir_quantis', return_value={}),
      'atende': mock.patch.object(api.core_avaliacao, 'atende', return_value={}),
      'decisoes': mock.patch.object(api.core_limiar, 'decisoes_atende', return_value={}),
      'resumir_decisoes': mock.patch.object(api.core_limiar, 'resumir_decisoes', return_value={}),
      'fatores': mock.patch.object(api.core_limiar, 'fatores_producao', return_value={}),
      'completo': mock.patch.object(api.core_quantis, 'atende_completo', return_value={}),
      'aplicacoes': mock.patch.object(api.core_aplicacoes, 'carregar', return_value={}),
    }
    m = {k: p.start() for k, p in patches.items()}
    self.addCleanup(lambda: [p.stop() for p in patches.values()])
    return api.avaliacao_completa('a.csv', '', features, None, progresso=progresso), m

  def test_colunas_com_vazamento_saem_da_conta_e_ficam_registradas(self):
    saida, m = self.rodar(['router_snr', 'router_tx_retries'])
    for chamada in m['avaliar'].call_args_list:
      self.assertEqual(chamada.args[1], ['router_snr'])
    for chamada in m['quantis'].call_args_list:
      self.assertEqual(chamada.args[1], ['router_snr'])
    self.assertEqual(m['decisoes'].call_args.args[2], ['router_snr'])
    self.assertEqual(m['fatores'].call_args.args[2], ['router_snr'])
    self.assertEqual(saida['removidas_por_vazamento'], ['router_tx_retries'])
    self.assertEqual(saida['speedtest_down_mbps']['removidas_por_vazamento'], ['router_tx_retries'])

  def test_progresso_tem_as_cinco_etapas_em_ordem(self):
    eventos = []
    self.rodar(['router_snr'], eventos.append)
    self.assertEqual([e['etapa'] for e in eventos], ['download', 'upload', 'latência', 'jitter', 'atende'])
    self.assertEqual([e['passo'] for e in eventos], [0, 1, 2, 3, 4])
    self.assertTrue(all(e['passos'] == 5 for e in eventos))

  def test_sem_vazamento_nada_e_removido(self):
    saida, _ = self.rodar(['router_snr'])
    self.assertEqual(saida['removidas_por_vazamento'], [])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: FAIL/ERROR. `avaliacao_completa()` não aceita `progresso` (`TypeError: ... unexpected keyword argument 'progresso'`).

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`, substituir a função `avaliacao_completa` inteira por:

```python
# Rótulo de cada etapa da avaliação completa, na ordem em que roda (progresso do salvar e do reavaliar).
ETAPAS = {'speedtest_down_mbps': 'download', 'speedtest_up_mbps': 'upload',
          'latency_ms': 'latência', 'jitter_ms': 'jitter'}
N_ETAPAS = len(ETAPAS) + 1


def avaliacao_completa(ds: str, ambiente: str, features: list, denominador: dict = None, progresso=None) -> dict:
  """Avaliação dos quatro alvos, de "atende em throughput" e de "atende completo", guardada junto da versão.

  Latência e jitter levam também o resumo quantílico (p50 e p90). Colunas hoje marcadas como
  vazamento saem da conta e ficam em `removidas_por_vazamento` (a versão salva antes da marcação
  continua avaliável, como no benchmark). `progresso(evento)` recebe {'etapa', 'passo', 'passos'}
  antes de cada uma das cinco etapas.
  """
  avisar = progresso or (lambda evento: None)
  saida, previsoes, quantis = {}, {}, {}
  aplicacoes = core_aplicacoes.carregar()
  removidas = set()
  for passo, alvo in enumerate(studio_features.TARGETS):
    avisar({'etapa': ETAPAS[alvo], 'passo': passo, 'passos': N_ETAPAS})
    conj, _ = _conjunto(ds, alvo, ambiente)
    vazadas = studio_features.vazadas_do_conjunto(conj)
    usadas = [f for f in features if f not in vazadas]
    fora = [f for f in features if f in vazadas]
    removidas.update(fora)
    resumo, previsoes[alvo] = core_avaliacao.avaliar(conj, usadas, vazadas, com_previsoes=True,
                                                     denominador=(denominador or {}).get(alvo))
    saida[alvo] = dict(resumo, datasets=conj.datasets, ambiente=_ambiente(ambiente) or 'todos',
                       versao_tabela=core_features.versao_tabela(),
                       versao_catalogo=core_features.CATALOGO_VERSAO,
                       removidas_por_vazamento=fora)
    if alvo in core_quantis.ALVOS_QUANTILICOS:
      quantis[alvo] = _prever_quantis(conj, usadas)
      saida[alvo]['quantis'] = core_quantis.resumir_quantis(quantis[alvo], resumo['n'])
  avisar({'etapa': 'atende', 'passo': N_ETAPAS - 1, 'passos': N_ETAPAS})
  usadas = [f for f in features if f not in removidas]
  saida['atende_throughput'] = core_avaliacao.atende(previsoes['speedtest_down_mbps'],
                                                     previsoes['speedtest_up_mbps'], aplicacoes)
  conj_dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
  conj_up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
  den = denominador or {}
  decisoes = core_limiar.decisoes_atende(conj_dn, conj_up, usadas, aplicacoes,
                                         den.get(conj_dn.alvo), den.get(conj_up.alvo))
  saida['atende_ajustado'] = dict(core_limiar.resumir_decisoes(decisoes),
                                  fatores_producao=core_limiar.fatores_producao(
                                    conj_dn, conj_up, usadas, aplicacoes, den.get(conj_dn.alvo),
                                    den.get(conj_up.alvo)))
  saida['atende_completo'] = core_quantis.atende_completo(previsoes['speedtest_down_mbps'],
                                                          previsoes['speedtest_up_mbps'],
                                                          quantis['latency_ms'], quantis['jitter_ms'], aplicacoes)
  saida['removidas_por_vazamento'] = sorted(removidas)
  return saida
```

`studio_features.TARGETS` é `ml.core.carga.TARGETS` (download, upload, latência, jitter, nessa ordem). Conferir com `grep -n "TARGETS" src/ml/studio/features.py src/ml/core/carga.py`.

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_salvar.py tests/test_studio_reavaliar.py -v`
Expected: 3 + 3 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/ml/studio/api.py`, `tests/test_studio_salvar.py`.
Mensagem sugerida: `fix(studio): avaliação completa avalia versões com vazamento sem as colunas marcadas e reporta progresso`

---

### Task 2: Salvar versão vira job; vazamento recusado na requisição

**Files:**
- Modify: `src/ml/studio/api.py` (`NovaVersao`, `modelos_salvar`, `modelos_reavaliar`, rota nova)
- Modify: `tests/test_studio_salvar.py`

- [ ] **Step 1: Escrever os testes**

Acrescentar em `tests/test_studio_salvar.py`, antes do `if __name__ == '__main__':`:

```python
PEDIDO = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x'}}}
AVAL = {'atende_completo': {'media': 0.6}}


def sincrono(chave, tarefa):
  """_iniciar_job sem thread: a tarefa roda na hora e o resultado volta no lugar do id."""
  return {'resultado': tarefa(lambda evento: None)}


def classes(features, tabela):
  return {f: types.SimpleNamespace(vazamento=f == 'router_tx_retries') for f in features}


class TestSalvarRota(unittest.TestCase):
  def setUp(self):
    patches = [mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
               mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)),
               mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr', 'router_tx_retries'}),
               mock.patch.object(api.core_modelos, 'classificar_features', side_effect=classes)]
    for p in patches:
      p.start()
      self.addCleanup(p.stop)
    self.job = mock.patch.object(api, '_iniciar_job', side_effect=sincrono).start()
    self.addCleanup(mock.patch.stopall)

  def salvar(self, ativar_falha=None, aval=AVAL, **campos):
    corpo = api.NovaVersao(**{'nome': 'v2', 'features': ['router_snr'], 'descricao': 'teste', **campos})
    with mock.patch.object(api, 'avaliacao_completa', side_effect=[aval] if isinstance(aval, dict) else aval) as a, \
         mock.patch.object(api.core_modelos, 'salvar_versao') as s, \
         mock.patch.object(api.core_modelos, 'definir_ativo', side_effect=ativar_falha) as d:
      try:
        r = api.modelos_salvar(corpo, PEDIDO)
      except Exception as erro:  # 422 e falhas do job voltam para o teste examinar
        r = erro
    return r, a, s, d

  def test_salva_dentro_do_job_com_progresso(self):
    r, aval, salvar, ativar = self.salvar()
    self.assertEqual(r['resultado'], {'nome': 'v2', 'ativa': False, 'erro_ativar': None})
    self.assertEqual(salvar.call_args.kwargs['avaliacao'], AVAL)
    self.assertIn('progresso', aval.call_args.kwargs)
    ativar.assert_not_called()
    self.assertEqual(self.job.call_args.args[0][:2], ('salvar', 'v2'))

  def test_ativar_no_mesmo_job(self):
    r, _, _, ativar = self.salvar(ativar=True)
    ativar.assert_called_once_with('v2')
    self.assertTrue(r['resultado']['ativa'])

  def test_falha_ao_ativar_mantem_a_versao_salva(self):
    r, _, salvar, _ = self.salvar(ativar=True, ativar_falha=ValueError('registro travado'))
    salvar.assert_called_once()
    self.assertEqual(r['resultado']['ativa'], False)
    self.assertIn('registro travado', r['resultado']['erro_ativar'])

  def test_vazamento_recusa_na_requisicao_sem_job(self):
    r, aval, _, _ = self.salvar(features=['router_snr', 'router_tx_retries'])
    self.assertIsInstance(r, api.HTTPException)
    self.assertEqual(r.status_code, 422)
    self.assertIn('router_tx_retries', r.detail)
    self.assertIn('Tire-as do rascunho', r.detail)
    aval.assert_not_called()
    self.job.assert_not_called()

  def test_nome_repetido_e_base_inexistente_sao_422_sem_job(self):
    for campos in ({'nome': 'v1'}, {'base': 'v9'}):
      r, _, _, _ = self.salvar(**campos)
      self.assertIsInstance(r, api.HTTPException)
      self.assertEqual(r.status_code, 422)
    self.job.assert_not_called()

  def test_falha_na_avaliacao_nao_grava(self):
    r, _, salvar, _ = self.salvar(aval=[RuntimeError('sem memória')])
    self.assertIn('sem memória', str(r))
    salvar.assert_not_called()


class TestReavaliarProgresso(unittest.TestCase):
  def test_reavaliar_repassa_a_etapa_com_o_nome_da_versao(self):
    eventos = []

    def job(chave, tarefa):
      return {'resultado': tarefa(eventos.append)}

    def aval(ds, amb, feats, den, progresso=None):
      progresso({'etapa': 'download', 'passo': 0, 'passos': 5})
      return AVAL

    with mock.patch.object(api, '_registro', return_value=(REGISTRO, None)), \
         mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)), \
         mock.patch.object(api, '_iniciar_job', side_effect=job), \
         mock.patch.object(api, 'avaliacao_completa', side_effect=aval), \
         mock.patch.object(api.core_features, 'cobertura_tr069', return_value={}), \
         mock.patch.object(api.core_modelos, 'reavaliar'):
      api.modelos_reavaliar(api.Reavaliacao(nomes=['v1'], ds='a.csv'), PEDIDO)
    self.assertEqual(eventos[-1], {'nome': 'v1', 'i': 0, 'total': 1, 'etapa': 'download', 'passo': 0, 'passos': 5})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: os testes novos falham (`NovaVersao` não tem `ativar`; `modelos_salvar` devolve o registro, não o job; reavaliar não repassa a etapa).

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`:

1. Em `class NovaVersao(BaseModel)`, acrescentar o campo depois de `base`:

```python
  ativar: bool = False
```

2. Substituir a função `modelos_salvar` inteira por:

```python
@app.post('/api/modelos')
def modelos_salvar(corpo: NovaVersao, request: Request):
  """Valida na hora (422 com o motivo); avaliação, gravação e ativação rodam num job.

  A avaliação completa leva de 1 a 2 minutos: na requisição, o botão ficava parado sem
  dizer nada. O front acompanha por GET /api/modelos/salvar/{id}.
  """
  _so_local(request)
  tabela, erro_tabela = _tabela()
  if erro_tabela:
    raise HTTPException(422, erro_tabela)
  registro, _ = _registro()
  if corpo.nome in registro['versoes']:
    raise HTTPException(422, f'a versão {corpo.nome!r} já existe e é imutável; escolha outro nome')
  if corpo.base and corpo.base not in registro['versoes']:
    raise HTTPException(422, f'versão base {corpo.base!r} não existe')
  vazadas = [f for f, c in core_modelos.classificar_features(corpo.features, tabela).items()
             if c is not None and c.vazamento]
  if vazadas:
    raise HTTPException(422, f'estas colunas estão marcadas como vazamento e não podem entrar numa versão nova: '
                             f'{vazadas}. Tire-as do rascunho.')
  # Mesma regra da avaliação do rascunho: herda o denominador da base (ou da ativa).
  denominador = registro['versoes'][corpo.base or registro['ativo']].get('denominador') or None
  try:
    core_modelos.validar_registro({'ativo': corpo.nome, 'versoes': {corpo.nome: {
      'features': corpo.features, 'descricao': corpo.descricao or '-'}}})
    selecao = _metadados_do_desenho(corpo.desenho, corpo.features) if corpo.desenho else None
  except (ValueError, AssertionError) as erro:
    raise HTTPException(422, str(erro))
  conhecidas = _colunas_conhecidas()

  def tarefa(progresso):
    avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, corpo.features, denominador, progresso=progresso)
    try:
      core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, conhecidas,
                                 tabela, origem='selecao-gulosa' if selecao else 'studio',
                                 avaliacao=avaliacao, selecao=selecao, denominador=denominador)
    finally:
      _ajustes.clear()
      _modelos_cache.clear()
    erro_ativar = None
    if corpo.ativar:
      try:
        core_modelos.definir_ativo(corpo.nome)
      except (OSError, ValueError) as erro:
        erro_ativar = str(erro)
      finally:
        _ajustes.clear()
        _modelos_cache.clear()
    return {'nome': corpo.nome, 'ativa': corpo.ativar and erro_ativar is None, 'erro_ativar': erro_ativar}

  return _iniciar_job(('salvar', corpo.nome, tuple(sorted(_lista(corpo.ds))), _ambiente(corpo.ambiente))
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/salvar/{job_id}')
def modelos_salvamento(job_id: str):
  return _job(job_id)
```

3. Em `modelos_reavaliar`, dentro de `tarefa`, trocar a linha

```python
        avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, versao['features'], versao.get('denominador'))
```

por

```python
        etapa = lambda evento, nome=nome, i=i: progresso({'nome': nome, 'i': i, 'total': len(nomes), **evento})
        avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, versao['features'], versao.get('denominador'),
                                       progresso=etapa)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_salvar.py tests/test_studio_reavaliar.py -v`
Expected: 10 + 3 testes, OK. Se `test_reavalia_em_ordem_com_o_denominador_da_versao` (já existente) falhar porque o mock de `avaliacao_completa` recebe `progresso` por palavra-chave, não mude o teste: os `args` posicionais continuam os mesmos; verifique a assinatura da chamada.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/ml/studio/api.py`, `tests/test_studio_salvar.py`.
Mensagem sugerida: `fix(studio): salvar versão roda em job com progresso e recusa colunas com vazamento na hora`

---

### Task 3: `semVazamento` na lógica pura

**Files:**
- Modify: `src/ml/studio/static/logica.js`
- Modify: `tests/js/logica.test.js`

- [ ] **Step 1: Escrever o teste**

No fim de `tests/js/logica.test.js`:

```js
test('semVazamento: tira do rascunho as colunas marcadas e diz quais saíram', () => {
  assert.deepEqual(L.semVazamento(['router_snr', 'router_tx_retries', 'router_noise'], ['router_tx_retries']),
    { features: ['router_snr', 'router_noise'], removidas: ['router_tx_retries'] });
  assert.deepEqual(L.semVazamento(['router_snr'], undefined), { features: ['router_snr'], removidas: [] });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 1` (`L.semVazamento is not a function`).

- [ ] **Step 3: Implementar**

Em `src/ml/studio/static/logica.js`, logo antes da linha `return { METRICAS, MIN_AMOSTRAS, ...`:

```js
  // Uma versão salva antes de uma coluna virar vazamento ainda a lista; o rascunho começa sem ela.
  function semVazamento(features, vazadas) {
    const fora = new Set(vazadas || []);
    return { features: features.filter((f) => !fora.has(f)), removidas: features.filter((f) => fora.has(f)) };
  }

```

E acrescentar `semVazamento` à lista do `return`, que fica:

```js
  return { METRICAS, MIN_AMOSTRAS, FOLGA_PCT, reprova, atende, mediana, chavePos, posicoes, daPosicao,
           reprovacao, gargalo, celulas, semContagem, contencao, piores, avisosConjunto,
           diffRascunho, mesmasFeatures, podeAtivar, vooUnico, corTr181, agruparColunas,
           sugerirNome, descricaoRascunho, semVazamento };
```

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/ 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 0`.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/ml/studio/static/logica.js`, `tests/js/logica.test.js`.
Mensagem sugerida: `feat(studio): semVazamento para limpar o rascunho`

---

### Task 4: Front do Modelo: rascunho sem vazamento, salvar por job, etapa na reavaliação

**Files:**
- Modify: `src/ml/studio/static/modelo.js`
- Modify: `src/ml/studio/static/index.html` (versão do script)

Todas as trocas abaixo são de texto exato; use Edit com o trecho "antes" e substitua pelo "depois".

- [ ] **Step 1: Estado novo**

Antes:
```js
    form: null, salvando: false, salvarErro: null,
```
Depois:
```js
    form: null, salvando: false, salvarErro: null, salvarEtapa: null, avisoVaz: null,
```

- [ ] **Step 2: `usarBase` começa o rascunho sem vazamento**

Antes:
```js
  function usarBase(nome) {
    st.base = nome;
    st.sel = new Set(featsBase());
    st.desenho = null; st.form = null; st.salvarErro = null;
  }
```
Depois:
```js
  function usarBase(nome) {
    st.base = nome;
    const limpo = L.semVazamento(featsBase(), (versao(nome) || {}).vazadas);
    st.sel = new Set(limpo.features);
    st.avisoVaz = limpo.removidas.length ? limpo.removidas : null;
    st.desenho = null; st.form = null; st.salvarErro = null;
  }
```

- [ ] **Step 3: Aviso no rascunho**

Em `secaoRascunho`, antes:
```js
      <div class="ed">${painelFeatures()}
```
Depois:
```js
      ${st.avisoVaz ? U.gate('warning', `${st.avisoVaz.length} ${st.avisoVaz.length === 1 ? 'coluna' : 'colunas'} com vazamento fora do rascunho`,
        `<code>${st.avisoVaz.map(esc).join('</code>, <code>')}</code> estão em ${esc(st.base)}, mas hoje são marcadas como vazamento
        (contadores da janela do speedtest carregam o próprio resultado). Uma versão nova não pode usá-las.`) : ''}
      <div class="ed">${painelFeatures()}
```

- [ ] **Step 4: `publicar` inicia o job e acompanha**

Antes (de `st.salvando = true; desenhar();` até o fim da função `publicar`):
```js
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
```
Depois:
```js
    st.salvando = true; st.salvarEtapa = null; desenhar();
    U.post('api/modelos', { nome, descricao: f.desc, features: selLista(), ds: st.ctx.enabledIds.join(','),
                            ambiente: st.ctx.ambiente, base: st.base, desenho, ativar: !!f.ativar })
      .then((r) => acompanharSalvar(r.id, nome))
      .catch((e) => { st.salvando = false; st.salvarErro = e.message; desenhar(); });
  }

  // O servidor avalia os quatro alvos e o "atende" antes de gravar (1 a 2 minutos). Recarregar a
  // página não cancela: a versão é gravada mesmo assim e aparece no registro quando terminar.
  function acompanharSalvar(id, nome) {
    U.pedir('api/modelos/salvar/' + id).then((job) => {
      if (job.status === 'rodando') {
        st.salvarEtapa = job.progresso[job.progresso.length - 1] || null;
        desenhar();
        setTimeout(() => acompanharSalvar(id, nome), 1500);
        return null;
      }
      st.salvando = false; st.salvarEtapa = null;
      if (job.status === 'erro') { st.salvarErro = job.erro; desenhar(); return null; }
      const r = job.resultado;
      if (r.erro_ativar) st.erro = `Versão ${nome} salva, mas não foi possível ativar: ${r.erro_ativar}`;
      else st.msg = `Versão ${nome} salva${r.ativa ? ' e ativa' : ''} em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
      st.cmpKey = null;
      return U.pedir('api/modelos').then((reg) => { st.reg = reg; usarBase(nome); agendar(); desenhar(); });
    }).catch((e) => { st.salvando = false; st.salvarEtapa = null; st.salvarErro = e.message; desenhar(); });
  }
```

- [ ] **Step 5: Botão e dica durante o salvamento**

Em `formSalvar`, antes:
```js
      ${st.salvarErro ? `<p class="dock-erro" role="alert">${esc(st.salvarErro)}</p>` : ''}
      <div class="dock-form-acoes"><button class="btn" data-acao="cancelar-salvar">Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-salvar"${st.salvando ? ' disabled' : ''}>${st.salvando ? 'Salvando…' : f.ativar ? 'Salvar e tornar ativa' : 'Salvar versão'}</button></div></div>`;
```
Depois:
```js
      ${st.salvarErro ? `<p class="dock-erro" role="alert">${esc(st.salvarErro)}</p>` : ''}
      ${st.salvando ? '<p class="hint" role="status">Leva de 1 a 2 minutos. Recarregar a página não cancela: a versão é gravada mesmo assim.</p>' : ''}
      <div class="dock-form-acoes"><button class="btn" data-acao="cancelar-salvar"${st.salvando ? ' disabled' : ''}>Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-salvar"${st.salvando ? ' disabled' : ''}>${st.salvando ? textoSalvando() : f.ativar ? 'Salvar e tornar ativa' : 'Salvar versão'}</button></div></div>`;
```

E logo antes de `function formSalvar() {`:
```js
  const textoSalvando = () => (st.salvarEtapa
    ? `Avaliando ${st.salvarEtapa.etapa} (${st.salvarEtapa.passo + 1} de ${st.salvarEtapa.passos})…` : 'Salvando…');

```

- [ ] **Step 6: Etapa na barra de reavaliação**

Em `barraReav`, antes:
```js
        <span>${atual ? `Reavaliando <code>${esc(atual.nome)}</code> (${atual.i + 1} de ${st.reav.total})…` : 'Reavaliando…'}</span>
```
Depois:
```js
        <span>${atual ? `Reavaliando <code>${esc(atual.nome)}</code> (${atual.i + 1} de ${st.reav.total})${atual.etapa ? ` · ${esc(atual.etapa)}` : ''}…` : 'Reavaliando…'}</span>
```

- [ ] **Step 7: Cache do navegador**

Em `src/ml/studio/static/index.html`, aumentar em 1 o número de versão (`?v=N`) dos scripts `logica.js` e `modelo.js` (ex.: `logica.js?v=3` vira `?v=4`, `modelo.js?v=2` vira `?v=3`). Sem isso, um navegador aberto continua com o JS antigo.

- [ ] **Step 8: Conferir sintaxe**

Run: `node --check src/ml/studio/static/modelo.js && node --check src/ml/studio/static/logica.js && echo ok`
Expected: `ok`.

- [ ] **Step 9: Ponto de commit**

Arquivos: `src/ml/studio/static/modelo.js`, `src/ml/studio/static/index.html`.
Mensagem sugerida: `fix(studio): salvar mostra a etapa da avaliação e o rascunho começa sem colunas com vazamento`

---

### Task 5: Assistente de sugestões só quando pedido

**Files:**
- Modify: `src/ml/studio/static/modelo.js`

- [ ] **Step 1: Tirar as chamadas automáticas**

Trocas de texto exato em `modelo.js`:

1. Em `carregarRegistro`, antes:
```js
      .finally(() => { iniciarSugestoes(); agendar(); desenhar(); });
```
Depois:
```js
      .finally(() => { agendar(); desenhar(); });
```

2. Em `escolherBase`, apagar a linha:
```js
    iniciarSugestoes();
```
(a que vem logo depois de `st.msg = null; st.erro = null;`).

3. Em `trocarAlvo`, antes:
```js
    carregarColunas(); iniciarSugestoes(); agendar(); desenhar();
```
Depois:
```js
    carregarColunas(); agendar(); desenhar();
```

4. Em `V.areas.modelo.render`, antes:
```js
        carregarColunas(); carregarReceitas(); iniciarSugestoes(); agendar();
```
Depois:
```js
        carregarColunas(); carregarReceitas(); agendar();
```

A chamada que ficava no `.finally` de `publicar` já saiu na Task 4.

Run: `grep -n "iniciarSugestoes(" src/ml/studio/static/modelo.js`
Expected: só a definição (`function iniciarSugestoes(forcar)`) e o `case 'refazer-sug': iniciarSugestoes(true)`.

- [ ] **Step 2: Status com botão**

Substituir a função `statusSugestoes` inteira por:

```js
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
```

- [ ] **Step 3: Conferir sintaxe**

Run: `node --check src/ml/studio/static/modelo.js && echo ok`
Expected: `ok`.

- [ ] **Step 4: Ponto de commit**

Arquivos: `src/ml/studio/static/modelo.js`.
Mensagem sugerida: `fix(studio): assistente de sugestões só roda quando pedido`

---

### Task 6: Aviso quando `data/` mudou depois que o Studio leu

**Files:**
- Modify: `src/ml/studio/api.py` (`_payload`, `payload`, função nova)
- Modify: `src/ml/studio/static/conjunto.js`
- Create: `tests/test_studio_data_mudou.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_data_mudou.py`:

```python
import json
import os
import sys
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api


class TestDataMudou(unittest.TestCase):
  def test_compara_o_mtime_de_data_com_a_ultima_leitura(self):
    with mock.patch.dict(api._cache, {'lido_em': 1000.0}, clear=True):
      with mock.patch.object(api.os.path, 'getmtime', return_value=1010.0):
        self.assertTrue(api._data_mudou())
      with mock.patch.object(api.os.path, 'getmtime', return_value=990.0):
        self.assertFalse(api._data_mudou())
      with mock.patch.object(api.os.path, 'getmtime', side_effect=OSError):
        self.assertFalse(api._data_mudou())

  def test_sem_leitura_ainda_nao_avisa(self):
    with mock.patch.dict(api._cache, {}, clear=True):
      self.assertFalse(api._data_mudou())

  def test_payload_leva_o_aviso(self):
    with mock.patch.object(api, '_payload', return_value={'rows': []}), \
         mock.patch.object(api, '_data_mudou', return_value=True):
      corpo = json.loads(api.payload().body)
    self.assertEqual(corpo, {'rows': [], 'dataMudou': True})


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_data_mudou.py -v`
Expected: ERROR `AttributeError: module 'ml.studio.api' has no attribute '_data_mudou'`.

- [ ] **Step 3: Implementar no servidor**

Em `src/ml/studio/api.py`:

1. Acrescentar `import time` junto dos imports do topo (depois de `import threading`).

2. Substituir `_payload` por:

```python
def _payload() -> dict:
  if 'payload' not in _cache:
    # Marca antes de ler: um arquivo que chegue durante a leitura conta como mudança.
    _cache['lido_em'] = time.time()
    _cache['payload'] = build_payload()
  return _cache['payload']


def _data_mudou() -> bool:
  """data/ ganhou, perdeu ou renomeou arquivo depois da última leitura: a tela mostra dados velhos.

  O upload pelo próprio Studio relê tudo (_dados_mudaram limpa _cache), então só avisa de
  mudanças feitas fora dele (git pull, arquivo copiado, arquivo apagado).
  """
  lido_em = _cache.get('lido_em')
  if lido_em is None:
    return False
  try:
    return os.path.getmtime(core_carga.DATA_DIR) > lido_em
  except OSError:
    return False
```

3. Na função `payload`, trocar `return JSONResponse(_payload())` por:

```python
  return JSONResponse(dict(_payload(), dataMudou=_data_mudou()))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_data_mudou.py -v`
Expected: 3 testes, OK.

- [ ] **Step 5: Aviso no painel Conjunto**

Em `src/ml/studio/static/conjunto.js`, na função `desenhar`, antes:
```js
      <h3>Avisos (${avisos.length})</h3>${secaoAvisos(avisos)}
```
Depois:
```js
      ${c.data.dataMudou ? U.gate('warning', 'data/ mudou depois que o Studio leu os dados',
        'Reinicie o Studio para ver os datasets atuais: ele só relê data/ e predios.json ao subir.') : ''}
      <h3>Avisos (${avisos.length})</h3>${secaoAvisos(avisos)}
```

Em `src/ml/studio/static/index.html`, aumentar em 1 o `?v=N` de `conjunto.js`.

Run: `node --check src/ml/studio/static/conjunto.js && echo ok`
Expected: `ok`.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/ml/studio/api.py`, `src/ml/studio/static/conjunto.js`, `src/ml/studio/static/index.html`, `tests/test_studio_data_mudou.py`.
Mensagem sugerida: `feat(studio): avisa quando data/ mudou depois que o Studio leu os dados`

---

### Task 7: Suíte, verificação no navegador e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Suíte inteira**

Run: `./venv/bin/python -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK`.

Run: `node --test tests/js/ 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 0`.

Run: `git status --short src/ml/core src/ml/regression_benchmark.py src/ml/classification_benchmark.py data`
Expected: vazio (o plano não toca nesses arquivos).

- [ ] **Step 2: Verificação manual no navegador**

Subir uma instância nova na porta 8300 (não mexer no Studio do usuário, que pode estar na 8100):

Run (em background): `./venv/bin/python src/ml/studio.py --port 8300`

**Atenção:** salvar uma versão de teste grava em `src/ml/core/modelos.json`, que o benchmark do Fabiano lê. Antes do passo 4, copie o arquivo (`cp src/ml/core/modelos.json /tmp/modelos.json.bak`) e, no fim, restaure (`cp /tmp/modelos.json.bak src/ml/core/modelos.json`) e confira com `git status --short src/ml/core` que ficou vazio.

No navegador (Playwright, se disponível), em `http://127.0.0.1:8300/#modelo`:
1. Ao abrir a aba, a aba de rede **não** mostra `POST api/assistente/sugestoes`.
2. O rascunho, partindo da v1, mostra o aviso "5 colunas com vazamento fora do rascunho" com `router_rx_drop_misc`, `router_rx_duration_us`, `router_tx_duration_us`, `router_tx_failed`, `router_tx_retries`.
3. No campo "Adicionar feature", a seção de sugeridas mostra "sugerir features"; clicar inicia o cálculo.
4. Salvar o rascunho com nome `teste-conserto`: o botão mostra "Avaliando download (1 de 5)…" e avança até "atende (5 de 5)". No fim, a mensagem "Versão teste-conserto salva" aparece e o cartão está na lista.
5. Reavaliar a v1 (menu da versão): a barra mostra a etapa e termina; o cartão da v1 passa a ter número de "atende".
6. Restaurar `modelos.json` (ver Atenção acima).
7. Abrir o painel Conjunto: sem aviso de `data/`. Rodar `touch data/` e recarregar a página: o aviso "data/ mudou" aparece. (O `touch` só muda o mtime da pasta; não altera arquivos.)

Parar o servidor da porta 8300 (só esse) e apagar `.playwright-mcp/` se foi criado.

- [ ] **Step 3: CHANGELOG**

Acrescentar no topo de `CHANGELOG.md`:

```markdown
# Changelog — Studio: salvar versão, vazamento e assistente

**Data:** 2026-10-22

## Mudanças

- **Salvar versão** roda num job: o botão mostra a etapa ("Avaliando upload, 2 de 5") em vez de ficar parado por 1 a 2 minutos. Recarregar a página não cancela. Validações (nome repetido, base inexistente, coluna com vazamento) continuam respondendo na hora.
- O rascunho começa sem as colunas da versão base que hoje estão marcadas como vazamento, com aviso. Salvar com uma delas é recusado com mensagem clara, em vez de `AssertionError`.
- Versões antigas com colunas de vazamento (v1) voltam a ser reavaliáveis: a avaliação roda sem elas e registra `removidas_por_vazamento`, como o benchmark já fazia.
- O assistente de sugestões só roda quando se clica em "sugerir features"; antes, disparava a cada abertura da aba Modelo e disputava CPU com o salvamento.
- Painel Conjunto avisa quando `data/` mudou depois que o Studio leu os dados.
- Os scripts do benchmark não mudaram (combinado com o Fabiano em 2026-10-22).

---
```

- [ ] **Step 4: Ponto de commit**

Arquivos: `CHANGELOG.md`.
Mensagem sugerida: `docs(changelog): conserto do salvar versão e do assistente no Studio`
