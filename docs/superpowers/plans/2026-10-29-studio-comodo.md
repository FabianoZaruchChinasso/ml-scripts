# Studio com a régua por cômodo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A nota da régua por cômodo vira o número principal do cartão e o critério de ativação do Studio, no lugar do QoE.

**Architecture:** `core/comodo.py` ganha a junção das previsões que o Studio já calcula, a tabela por posição, o bloco serializável guardado na avaliação e a comparação entre blocos guardados. `studio/api.py` troca a etapa de QoE pela de cômodo (piso em cache) e o endpoint `avaliar_qoe` por `avaliar_comodo`, que prevê só o rascunho e compara com a tabela guardada da ativa. O front troca o bloco de QoE pelo bloco "Cômodo" e a trava de ativação.

**Tech Stack:** Python 3, pandas, FastAPI, `unittest`; JavaScript sem build, `node --test`; Playwright para a conferência no navegador.

**Spec:** `docs/superpowers/specs/2026-10-29-studio-comodo-design.md`.

---

## Regras do repositório que valem para todas as tarefas

- Indentação de 2 espaços, nomes, docstrings e textos de interface em português, como no código em volta.
- Testes Python da raiz: `venv/bin/python -m unittest tests/<arquivo>.py -v` (sem pytest). Testes JS: `node --test tests/js/logica.test.js`.
- **Não rodar `git commit`, `git add` nem `git push`.** O usuário commita à mão. O passo "Commit" de cada tarefa é: parar, listar os arquivos e sugerir a mensagem (sem linha `Co-Authored-By`).
- Não mexer em `classification_benchmark.py`, `regression_benchmark.py`, `compare_protocols.py` (benchmarks congelados do Fabiano), `core/qoe.py`, `core/avaliacao.py`, `core/quantis.py`, `core/percepcao.py`.
- Sem emojis em código ou interface; ícones só pelos `icone(...)` que já existem.

## Estrutura de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/core/comodo.py` | modificar | `de_previsoes`, `tabela_posicoes`, `amostras_posicoes`, `bloco`, `comparar_blocos` |
| `tests/test_comodo.py` | modificar | testes das funções novas |
| `src/ml/studio/api.py` | modificar | etapa "cômodo", piso em cache, `avaliar_comodo`, sai `avaliar_qoe` |
| `src/ml/core/modelos.py` | modificar | `nota_reavaliacao` registra a nota por cômodo |
| `tests/test_studio_comodo.py` | criar | endpoint e `_bloco_comodo` |
| `tests/test_studio_qoe.py` | modificar | sai `TestAvaliarQoe`; fica `TestListagem` |
| `tests/test_studio_salvar.py` | modificar | `TestAvaliacaoCompleta` com a etapa "cômodo" |
| `tests/test_modelos_core.py` | modificar | teste da linha do histórico |
| `src/ml/studio/static/logica.js` | modificar | `notaCartao`, `podeAtivar`, `precisaPedirComodo` |
| `tests/js/logica.test.js` | modificar | testes JS dessas três funções |
| `src/ml/studio/static/modelo.js` | modificar | estado, pedido, bloco "Cômodo", trava, cartão, sem seletor de perfil |
| `CHANGELOG.md` | modificar (topo) | seção nova |

---

### Task 0: Pré-requisito

- [ ] **Step 1: Conferir que a régua por cômodo está no git**

Run: `git ls-files src/ml/core/comodo.py tests/test_comodo.py src/ml/comodo_benchmark.py`
Expected: as três linhas. Se faltar alguma, PARAR e pedir ao usuário o commit da régua por cômodo (spec `2026-10-29-regua-comodo-design.md`).

---

### Task 1: Núcleo — junção, tabela, bloco e comparação

**Files:**
- Modify: `src/ml/core/comodo.py`
- Modify: `tests/test_comodo.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_comodo.py`, acrescentar `import json` como primeira linha dos imports (antes de `import copy`). Antes do bloco `if __name__ == '__main__':`, acrescentar:

```python
def df_e_prev():
  """2 prédios x 2 posições, 10 linhas sozinhas cada, mais 10 linhas com concorrência em s1-a.

  Verdade: s1-a bom, s1-b ruim (razão 0,2), s2-a bom, s2-b degradado (0,6). A previsão copia
  os valores reais, menos s2-b, que sai com download 100 (bom).
  """
  partes = []
  for s, dn_b in (('s1', 20.0), ('s2', 60.0)):
    partes.append(linhas(f'{s}-a', 10, 100, 100, site=s))
    partes.append(linhas(f'{s}-b', 10, dn_b, 100, site=s))
  partes.append(linhas('s1-a', 10, 1, 1, conc=2.0, site='s1'))
  df = juntas(*partes)
  df['_linha'] = [f'd:{i}' for i in range(len(df))]
  prev = pd.DataFrame({'_linha': df['_linha'], '_site': df['_site'], '_pos': df['_pos'], 'dn': df[C.DN],
                       'up': df[C.UP], 'lat': df[C.LAT], 'jit': df[C.JIT]})
  prev.loc[prev['_pos'] == 's2-b', 'dn'] = 100.0
  return df, prev


META = {'datasets': ['a.csv'], 'ambiente': 'todos'}


class TestBloco(unittest.TestCase):
  def test_de_previsoes_casa_por_linha(self):
    base = pd.DataFrame({'_linha': ['a', 'b', 'c'], '_site': ['s1'] * 3, '_pos': ['p', 'p', 'q']})
    pdn = pd.DataFrame({'_linha': ['a', 'b', 'c'], 'yhat': [1.0, 2.0, 3.0]})
    pup = pd.DataFrame({'_linha': ['c', 'b', 'a'], 'yhat': [30.0, 20.0, 10.0]})
    qlat = pd.DataFrame({'_linha': ['a', 'b'], 'q90': [5.0, 6.0]})
    qjit = pd.DataFrame({'_linha': ['a', 'b', 'c'], 'q90': [7.0, 8.0, 9.0]})
    p = C.de_previsoes(base, pdn, pup, qlat, qjit).set_index('_linha')
    self.assertEqual(sorted(p.index), ['a', 'b'])
    self.assertEqual(p.loc['b', ['dn', 'up', 'lat', 'jit']].tolist(), [2.0, 20.0, 6.0, 8.0])
    self.assertEqual(p.loc['a', '_pos'], 'p')

  def test_tabela_posicoes_usa_so_linhas_sozinhas(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    self.assertEqual(tab.index.tolist(), ['s1-a', 's1-b', 's2-a', 's2-b'])
    self.assertEqual(tab['real'].tolist(), ['bom', 'ruim', 'bom', 'degradado'])
    # Sem o filtro, as 10 linhas com concorrência puxariam a mediana prevista de s1-a para 50,5.
    self.assertEqual(tab['previsto'].tolist(), ['bom', 'ruim', 'bom', 'bom'])
    self.assertAlmostEqual(tab.loc['s2-b', 'razao_prevista'], 1.0)
    self.assertEqual(set(tab.columns), {'_site', 'real', 'previsto', 'razao_prevista', 'apto_real', 'apto_previsto'})

  def test_bloco_tem_os_campos_e_e_serializavel(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    b = C.bloco(tab, tab.assign(previsto='bom'), META)
    self.assertEqual(set(b), {'versao_comodo', 'datasets', 'ambiente', 'nota', 'intervalo', 'piso', 'contra_piso',
                              'por_predio', 'confusao', 'graves', 'posicoes', 'piso_posicoes'})
    json.dumps(b)
    self.assertEqual(b['versao_comodo'], C.VERSAO_COMODO)
    self.assertAlmostEqual(b['nota'], 0.6667)
    self.assertAlmostEqual(b['piso']['nota'], 0.3333)
    self.assertEqual(b['posicoes'][3], {'pos': 's2-b', 'site': 's2', 'real': 'degradado', 'previsto': 'bom',
                                        'razao_prevista': 1.0, 'apto_real': True, 'apto_previsto': True})
    self.assertEqual(b['por_predio'], {'s1': [2, 2], 's2': [1, 2]})
    self.assertEqual(b['confusao'], [[2, 0, 0], [1, 0, 0], [0, 0, 1]])

  def test_bloco_recusa_piso_com_outras_posicoes(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    with self.assertRaisesRegex(ValueError, 'posições'):
      C.bloco(tab, tab.iloc[:3], META)

  def test_comparar_blocos_igual_a_comparar_as_tabelas(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    piso = tab.assign(previsto='bom')
    nova, base = C.bloco(tab, piso, META), C.bloco(piso, piso, META)
    r = C.comparar_blocos(nova, base)
    direto = C.comparar(tab, piso, C.amostras_posicoes(tab))
    self.assertEqual((r['diferenca'], r['intervalo'], r['resultado']),
                     (direto['diferenca'], direto['intervalo'], direto['resultado']))
    self.assertEqual((r['nota'], r['nota_base']), (nova['nota'], base['nota']))

  def test_comparar_blocos_recusa_avaliacoes_incompativeis(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    b = C.bloco(tab, tab, META)
    for campo, valor in (('versao_comodo', 'velha'), ('datasets', ['b.csv']), ('ambiente', 'domestico')):
      with self.assertRaisesRegex(ValueError, campo):
        C.comparar_blocos(b, dict(b, **{campo: valor}))
    with self.assertRaisesRegex(ValueError, 'posições'):
      C.comparar_blocos(b, dict(b, posicoes=b['posicoes'][:3]))
```

Conferência dos números esperados (já feita à mão): verdade `[bom, ruim, bom, degradado]`, previsto `[bom, ruim, bom, bom]` dá recall bom 2/2, ruim 1/1, degradado 0/1, nota 0,6667; o piso (tudo `bom`) dá 1, 0, 0, nota 0,3333. A matriz na ordem `(bom, degradado, ruim)`, verdade nas linhas: bom `[2, 0, 0]`, degradado `[1, 0, 0]`, ruim `[0, 0, 1]`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: `AttributeError` em `de_previsoes`, `tabela_posicoes`, `bloco`, `comparar_blocos`, `amostras_posicoes`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/comodo.py`, trocar a função `prever` inteira (de `def prever(` até o `return saida.rename_axis('_linha').reset_index()` dela) por:

```python
def de_previsoes(base_df: pd.DataFrame, prev_dn: pd.DataFrame, prev_up: pd.DataFrame, q_lat: pd.DataFrame,
                 q_jit: pd.DataFrame) -> pd.DataFrame:
  """Junta por `_linha` as previsões fora do fold: `yhat` de download e upload (régua de regressão)
  e `q90` de latência e jitter (quantis com CQR). Linha sem previsão em algum alvo sai; `_site` e
  `_pos` vêm de `base_df`. Devolve _linha, _site, _pos, dn, up, lat, jit."""
  saida = pd.concat({'dn': prev_dn.set_index('_linha')['yhat'], 'up': prev_up.set_index('_linha')['yhat'],
                     'lat': q_lat.set_index('_linha')['q90'], 'jit': q_jit.set_index('_linha')['q90']},
                    axis=1, join='inner')
  base = base_df.set_index('_linha')
  saida = saida.assign(_site=base['_site'].reindex(saida.index).to_numpy(),
                       _pos=base['_pos'].reindex(saida.index).to_numpy())
  return saida.rename_axis('_linha').reset_index()


def prever(conjs: dict, features, vazadas: dict, denominador: dict = None) -> pd.DataFrame:
  """Previsões fora do fold (LOGO por prédio) dos quatro alvos, casadas por `_linha`.

  `conjs`: {alvo: objeto com `.df`} (o Conjunto da carga); `vazadas`: {alvo: colunas com
  vazamento}; `denominador`: {alvo: valor do registro} para download e upload. Feature
  ausente ou com vazamento num alvo fica fora só dele. Linha sem previsão em algum alvo sai.
  Devolve _linha, _site, _pos, dn, up (previsão pontual), lat, jit (p90 com CQR).
  """
  previsto = {}
  for alvo in (DN, UP, LAT, JIT):
    df = conjs[alvo].df
    colunas = [f for f in features if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {alvo}')
    if alvo in (LAT, JIT):
      previsto[alvo] = quantis.prever_quantis_fora_do_fold(df, colunas, alvo, vazadas[alvo])
    else:
      previsto[alvo] = avaliacao.prever_fora_do_fold(df, colunas, alvo, vazadas[alvo],
                                                     denominador=(denominador or {}).get(alvo))
  return de_previsoes(conjs[DN].df, previsto[DN], previsto[UP], previsto[LAT], previsto[JIT])
```

E no fim do arquivo:

```python
def tabela_posicoes(df: pd.DataFrame, prev: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Verdade e classe prevista por posição, só com as linhas sozinhas no rádio (índice `_pos`).

  `prev`: saída de `prever` ou `de_previsoes`. Colunas `_site`, `real`, `previsto`,
  `razao_prevista`, `apto_real`, `apto_previsto`.
  """
  real, ref = verdade(df, limiares)
  linhas = set(sozinhas(df)['_linha'])
  previsto = classe_prevista(prev[prev['_linha'].isin(linhas)], ref, limiares)
  comuns = real.index.intersection(previsto.index).sort_values()
  return pd.DataFrame({'_site': real.loc[comuns, '_site'], 'real': real.loc[comuns, 'classe'],
                       'previsto': previsto.loc[comuns, 'classe'], 'razao_prevista': previsto.loc[comuns, 'razao'],
                       'apto_real': real.loc[comuns, 'apto_jogo'], 'apto_previsto': previsto.loc[comuns, 'apto_jogo']})


def amostras_posicoes(tabela: pd.DataFrame) -> list:
  """Reamostras de posições estratificadas por prédio, com a semente fixa da régua: duas tabelas
  com as mesmas posições dão as mesmas reamostras."""
  return avaliacao.reamostras(tabela.index, tabela['_site'])


def _lista(tabela: pd.DataFrame) -> list:
  """Tabela por posição em tipos nativos do Python (vai para o modelos.json)."""
  return [{'pos': str(p), 'site': str(l['_site']), 'real': str(l['real']), 'previsto': str(l['previsto']),
           'razao_prevista': round(float(l['razao_prevista']), 4), 'apto_real': bool(l['apto_real']),
           'apto_previsto': bool(l['apto_previsto'])} for p, l in tabela.iterrows()]


def _tabela(lista: list) -> pd.DataFrame:
  return pd.DataFrame(lista).set_index('pos').rename(columns={'site': '_site'})


def bloco(tabela: pd.DataFrame, piso: pd.DataFrame, meta: dict) -> dict:
  """Bloco `comodo` guardado na avaliação de uma versão. `meta`: {'datasets', 'ambiente'}.

  O "apto para jogo" só entra em `posicoes` e `piso_posicoes`: não é exibido até ser consertado.
  """
  if not tabela.index.equals(piso.index):
    raise ValueError('a versão e o piso precisam das mesmas posições, na mesma ordem')
  amostras = amostras_posicoes(tabela)
  r, rp = nota(tabela, amostras), nota(piso, amostras)
  c = comparar(tabela, piso, amostras)
  m, graves = confusao(tabela)
  return {'versao_comodo': VERSAO_COMODO, 'datasets': list(meta['datasets']), 'ambiente': meta['ambiente'],
          'nota': r['nota'], 'intervalo': r['intervalo'], 'piso': {'nota': rp['nota'], 'intervalo': rp['intervalo']},
          'contra_piso': {'diferenca': c['diferenca'], 'intervalo': c['intervalo'], 'resultado': c['resultado']},
          'por_predio': {s: [a, n] for s, (a, n) in por_predio(tabela).items()},
          'confusao': m.values.tolist(), 'graves': graves,
          'posicoes': _lista(tabela), 'piso_posicoes': _lista(piso)}


def comparar_blocos(nova: dict, base: dict) -> dict:
  """Diferença pareada de nota (nova - base) a partir das tabelas guardadas, e o resultado.

  Levanta ValueError se as duas avaliações não são comparáveis: outra régua, outros datasets,
  outro ambiente, outras posições ou outra verdade.
  """
  for campo in ('versao_comodo', 'datasets', 'ambiente'):
    if nova.get(campo) != base.get(campo):
      raise ValueError(f'{campo} diferente: {nova.get(campo)!r} contra {base.get(campo)!r}')
  tn, tb = _tabela(nova['posicoes']), _tabela(base['posicoes'])
  if not tn.index.equals(tb.index):
    raise ValueError('as duas avaliações não têm as mesmas posições')
  if not (tn['real'] == tb['real']).all():
    raise ValueError('a verdade das duas avaliações difere')
  c = comparar(tn, tb, amostras_posicoes(tn))
  return {'diferenca': c['diferenca'], 'intervalo': c['intervalo'], 'resultado': c['resultado'],
          'nota': nova['nota'], 'nota_base': base['nota']}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: 25 testes OK (19 antigos, incluindo os de `prever`, mais 6).

- [ ] **Step 5: Conferir que o benchmark continua igual**

Run: `venv/bin/python src/ml/comodo_benchmark.py 2>/dev/null | grep -E "^  (piso|v1|v3-tr069) "` (timeout 600000 ms)
Expected: as notas de antes do refator: `piso 0.452`, `v1 0.643`, `v3-tr069 0.722`.

- [ ] **Step 6: Commit (pelo usuário)**

Arquivos: `src/ml/core/comodo.py`, `tests/test_comodo.py`.
Mensagem sugerida: `feat(comodo): bloco serializável e comparação entre avaliações guardadas`

---

### Task 2: Backend do Studio

**Files:**
- Modify: `src/ml/studio/api.py`
- Modify: `src/ml/core/modelos.py`
- Create: `tests/test_studio_comodo.py`
- Modify: `tests/test_studio_qoe.py`, `tests/test_studio_salvar.py`, `tests/test_modelos_core.py`

- [ ] **Step 1: Escrever `tests/test_studio_comodo.py`**

```python
import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api

BLOCO = {'versao_comodo': 'x', 'nota': 0.6}
REGISTRO = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'x', 'denominador': {'speedtest_down_mbps': 'router_tx_rate_mbps'},
         'avaliacao': {'comodo': BLOCO}},
  'v2': {'features': ['router_snr'], 'descricao': 'sem cômodo', 'avaliacao': {'atende_completo': {'media': 0.6}}}}}
NOVO = {'nota': 0.7, 'intervalo': [0.6, 0.8], 'piso': {'nota': 0.45, 'intervalo': [0.3, 0.5]},
        'contra_piso': {'diferenca': 0.25, 'intervalo': [0.1, 0.4], 'resultado': 'melhor'}, 'por_predio': {'s1': [2, 3]}}
COMP = {'diferenca': 0.1, 'intervalo': [0.01, 0.2], 'resultado': 'melhor', 'nota': 0.7, 'nota_base': 0.6}


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None, classes={})


class TestAvaliarComodo(unittest.TestCase):
  def setUp(self):
    api._modelos_cache.clear()
    self.m = {}
    for nome, p in (('registro', mock.patch.object(api, '_registro', return_value=(REGISTRO, None))),
                    ('conjunto', mock.patch.object(api, '_conjunto',
                                                   side_effect=lambda ds, alvo, amb='': (conj(alvo), None))),
                    ('vazadas', mock.patch.object(api.studio_features, 'vazadas_do_conjunto',
                                                  return_value=['router_tx_retries'])),
                    ('prever', mock.patch.object(api.core_comodo, 'prever', return_value='prev')),
                    ('bloco', mock.patch.object(api, '_bloco_comodo', return_value=NOVO)),
                    ('comparar', mock.patch.object(api.core_comodo, 'comparar_blocos', return_value=COMP))):
      self.m[nome] = p.start()
      self.addCleanup(p.stop)

  def test_preve_so_o_rascunho_e_compara_com_o_bloco_guardado(self):
    r = api.modelos_avaliar_comodo(features='router_snr', contra='v1', ds='a.csv', base='v1')
    conjs, feats, vazadas, den = self.m['prever'].call_args.args
    self.assertEqual(sorted(conjs), sorted(api.core_qoe.ALVOS))
    self.assertEqual(feats, ['router_snr'])
    self.assertEqual(vazadas['speedtest_down_mbps'], ['router_tx_retries'])
    self.assertEqual(den, {'speedtest_down_mbps': 'router_tx_rate_mbps'})
    self.assertEqual(self.m['comparar'].call_args.args, (NOVO, BLOCO))
    self.assertEqual((r['nota'], r['nota_base'], r['diferenca'], r['intervalo_diferenca'], r['resultado']),
                     (0.7, 0.6, 0.1, [0.01, 0.2], 'melhor'))
    self.assertEqual(r['piso'], NOVO['piso'])
    self.assertEqual(r['por_predio'], NOVO['por_predio'])

  def test_denominador_da_base_ou_da_ativa(self):
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(self.m['prever'].call_args.args[3], {'speedtest_down_mbps': 'router_tx_rate_mbps'})
    api.modelos_avaliar_comodo(features='router_snr', contra='v1', base='v2')
    self.assertIsNone(self.m['prever'].call_args.args[3])

  def test_cache_nao_recalcula(self):
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(self.m['prever'].call_count, 1)

  def test_contra_sem_bloco_comodo_e_409_sem_prever(self):
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v2')
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('reavalie v2', erro.exception.detail)
    self.m['prever'].assert_not_called()

  def test_avaliacao_incompativel_e_409(self):
    self.m['comparar'].side_effect = ValueError('datasets diferente')
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('datasets diferente', erro.exception.detail)

  def test_erros_de_entrada(self):
    casos = [({'features': '', 'contra': 'v1'}, 422), ({'features': 'router_snr', 'contra': 'v9'}, 404),
             ({'features': 'router_snr', 'contra': 'v1', 'base': 'v9'}, 404)]
    for kwargs, codigo in casos:
      with self.assertRaises(api.HTTPException) as erro:
        api.modelos_avaliar_comodo(**kwargs)
      self.assertEqual(erro.exception.status_code, codigo)

  def test_valueerror_do_core_vira_422(self):
    self.m['prever'].side_effect = ValueError('nenhuma feature utilizável')
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(erro.exception.status_code, 422)

  def test_rota_do_qoe_saiu(self):
    rotas = [getattr(r, 'path', '') for r in api.app.routes]
    self.assertIn('/api/modelos/avaliar_comodo', rotas)
    self.assertNotIn('/api/modelos/avaliar_qoe', rotas)
    self.assertFalse(hasattr(api, 'modelos_avaliar_qoe'))


class TestBlocoComodo(unittest.TestCase):
  def setUp(self):
    api._piso_comodo_cache.clear()

  def test_piso_calculado_uma_vez_por_conjunto(self):
    conjs = {a: conj(a) for a in api.core_qoe.ALVOS}
    with mock.patch.object(api.core_qoe, 'conjunto_qoe', return_value='df'), \
         mock.patch.object(api.studio_features, 'vazadas_do_conjunto', return_value=[]), \
         mock.patch.object(api.core_comodo, 'prever', return_value='prev_piso') as prever, \
         mock.patch.object(api.core_comodo, 'tabela_posicoes', side_effect=lambda df, prev, lim: 'tab:' + prev), \
         mock.patch.object(api.core_comodo, 'bloco', return_value={'nota': 0.7}) as bloco:
      api._bloco_comodo(conjs, 'prev_v1', '')
      self.assertEqual(api._bloco_comodo(conjs, 'prev_v2', ''), {'nota': 0.7})
    self.assertEqual(prever.call_count, 1)
    self.assertEqual(prever.call_args.args[1], ['radio'])
    self.assertEqual(bloco.call_args.args, ('tab:prev_v2', 'tab:prev_piso', {'datasets': ['a.csv'], 'ambiente': 'todos'}))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Ajustar os testes existentes**

Em `tests/test_studio_qoe.py`, apagar a classe `TestAvaliarQoe` inteira (de `class TestAvaliarQoe(unittest.TestCase):` até antes de `class TestListagem(unittest.TestCase):`) e a função `conj` que só ela usa. `TestListagem` fica.

Em `tests/test_studio_salvar.py`, no dicionário `patches` de `TestAvaliacaoCompleta.rodar`, trocar a linha

```python
      'qoe': mock.patch.object(api.core_qoe, 'avaliar', return_value={'modelo': {'nota': 0.7}}),
```

por

```python
      'de_previsoes': mock.patch.object(api.core_comodo, 'de_previsoes', return_value='prev4'),
      'comodo': mock.patch.object(api, '_bloco_comodo', return_value={'nota': 0.7}),
```

No teste `test_progresso_tem_as_seis_etapas_em_ordem`, trocar `'QoE'` por `'cômodo'` na lista de etapas. Trocar o teste `test_qoe_com_o_perfil_da_versao_e_sem_vazamento` inteiro por:

```python
  def test_comodo_com_as_previsoes_ja_calculadas_e_sem_qoe(self):
    saida, m = self.rodar(['router_snr', 'router_tx_retries'])
    m['aplicacoes'].assert_called_with('norma')
    self.assertEqual(m['de_previsoes'].call_args.args[1:], ('prev', 'prev', 'q', 'q'))
    conjs, prev, ambiente = m['comodo'].call_args.args
    self.assertEqual(sorted(conjs), sorted(api.core_qoe.ALVOS))
    self.assertEqual((prev, ambiente), ('prev4', ''))
    self.assertEqual(saida['comodo'], {'nota': 0.7})
    self.assertNotIn('qoe', saida)
    self.assertEqual(saida['perfil'], 'norma')
```

Em `tests/test_modelos_core.py`, logo antes de `  def test_nota_sem_qoe_continua_igual(self):`, acrescentar:

```python
  def test_nota_traz_o_comodo_quando_existe(self):
    antiga = {'atende_completo': {'media': 0.6}, 'qoe': {'modelo': {'nota': 0.66}}}
    nova = {'atende_completo': {'media': 0.6}, 'comodo': {'nota': 0.722}}
    nota = M.nota_reavaliacao(antiga, nova, '2026-10-29')
    self.assertIn('cômodo – → 0,72', nota)
    self.assertIn('QoE 0,66 → –', nota)

```

- [ ] **Step 3: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_comodo.py tests/test_studio_salvar.py tests/test_studio_qoe.py tests/test_modelos_core.py 2>&1 | tail -5`
Expected: falhas e erros (`_bloco_comodo`, `core_comodo`, `modelos_avaliar_comodo` não existem; a nota do histórico não traz o cômodo).

- [ ] **Step 4: Implementar `nota_reavaliacao`**

Em `src/ml/core/modelos.py`, em `nota_reavaliacao`, trocar a primeira linha da docstring

```python
  """Linha do histórico: o que mudou de datasets e ambiente, e o atende completo antes e depois."""
```

por

```python
  """Linha do histórico: o que mudou de datasets e ambiente, e o atende completo, o QoE e a nota por cômodo antes e depois."""
```

e, logo antes de `  return '; '.join(partes)` dessa função, acrescentar:

```python
  comodo_antes = ((antiga or {}).get('comodo') or {}).get('nota')
  comodo_depois = (nova.get('comodo') or {}).get('nota')
  if comodo_antes is not None or comodo_depois is not None:
    partes.append(f'cômodo {_media_texto(comodo_antes)} → {_media_texto(comodo_depois)}')
```

- [ ] **Step 5: Implementar o backend**

Em `src/ml/studio/api.py`:

1. Depois de `from ml.core import carga as core_carga`, acrescentar `from ml.core import comodo as core_comodo`.

2. Logo abaixo de `_modelos_cache = {}`, acrescentar:

```python
# Tabela por posição do piso da régua por cômodo (só radio): igual para todas as versões, uma por
# (datasets, ambiente, VERSAO_COMODO).
_piso_comodo_cache = {}
```

3. Trocar a função `modelos_avaliar_qoe` inteira (do decorador `@app.get('/api/modelos/avaliar_qoe')` até o `return _modelos_cache[chave]` dela) por:

```python
@app.get('/api/modelos/avaliar_comodo')
def modelos_avaliar_comodo(features: str, contra: str, ds: str = '', ambiente: str = '', base: str = ''):
  """Régua por cômodo do rascunho e o veredito contra a avaliação guardada de `contra` (core/comodo.py).

  Só o rascunho é previsto (quatro alvos, cerca de 1 min sem cache); `contra` entra pela tabela por
  posição guardada na avaliação dele. O denominador é o da `base` (ou da ativa), como no salvar.
  409 quando `contra` não tem o bloco `comodo` ou foi avaliada com outra régua, outros datasets ou
  outro ambiente: é preciso reavaliar `contra` antes.
  """
  feats = _lista(features)
  if not feats:
    raise HTTPException(422, 'escolha pelo menos uma feature')
  registro, _ = _registro()
  for nome in (contra, base):
    if nome and nome not in registro['versoes']:
      raise HTTPException(404, f'versão {nome!r} não existe')
  chave = (('avaliar_comodo', tuple(sorted(_lista(ds))), _ambiente(ambiente), tuple(feats), contra, base)
           + _chave_versoes())
  if chave not in _modelos_cache:
    guardado = (registro['versoes'][contra].get('avaliacao') or {}).get('comodo')
    if not guardado:
      raise HTTPException(409, f'{contra} não foi avaliada pela régua por cômodo: reavalie {contra} antes de comparar')
    denominador = registro['versoes'][base or registro['ativo']].get('denominador') or None
    conjs = {alvo: _conjunto(ds, alvo, ambiente)[0] for alvo in core_qoe.ALVOS}
    vazadas = {alvo: studio_features.vazadas_do_conjunto(c) for alvo, c in conjs.items()}
    try:
      novo = _bloco_comodo(conjs, core_comodo.prever(conjs, feats, vazadas, denominador), ambiente)
    except (ValueError, AssertionError) as erro:
      raise HTTPException(422, str(erro))
    try:
      comp = core_comodo.comparar_blocos(novo, guardado)
    except ValueError as erro:
      raise HTTPException(409, f'{erro}: reavalie {contra} antes de comparar')
    _modelos_cache[chave] = {'nota': novo['nota'], 'intervalo': novo['intervalo'], 'piso': novo['piso'],
                             'contra_piso': novo['contra_piso'], 'por_predio': novo['por_predio'],
                             'nota_base': comp['nota_base'], 'diferenca': comp['diferenca'],
                             'intervalo_diferenca': comp['intervalo'], 'resultado': comp['resultado']}
  return _modelos_cache[chave]
```

4. Trocar o comentário `# Depois dos quatro alvos: o "atende" da regressão e o QoE do classificador.` por `# Depois dos quatro alvos: o "atende" da regressão e a régua por cômodo.` e, logo depois da linha `N_ETAPAS = len(ETAPAS) + 2`, acrescentar (com uma linha em branco antes):

```python
def _bloco_comodo(conjs: dict, prev, ambiente: str) -> dict:
  """Bloco `comodo` da avaliação (core/comodo.py), com o piso (só radio) em cache por conjunto.

  `prev`: previsões dos quatro alvos (comodo.prever ou comodo.de_previsoes). A régua usa sempre o perfil de norma.
  """
  limiares = core_aplicacoes.carregar_perfil('norma')
  df = core_qoe.conjunto_qoe(conjs)
  meta = {'datasets': list(conjs[core_comodo.DN].datasets), 'ambiente': _ambiente(ambiente) or 'todos'}
  chave = (tuple(meta['datasets']), meta['ambiente'], core_comodo.VERSAO_COMODO)
  if chave not in _piso_comodo_cache:
    vazadas = {alvo: studio_features.vazadas_do_conjunto(c) for alvo, c in conjs.items()}
    _piso_comodo_cache[chave] = core_comodo.tabela_posicoes(df, core_comodo.prever(conjs, ['radio'], vazadas), limiares)
  return core_comodo.bloco(core_comodo.tabela_posicoes(df, prev, limiares), _piso_comodo_cache[chave], meta)
```

5. Em `avaliacao_completa`, na docstring, trocar `(a última é o QoE, medido com o perfil `perfil_qoe`).` por `(a última é a régua por cômodo; `perfil_qoe` define os limiares do "atende").`. Trocar as duas linhas

```python
  avisar({'etapa': 'QoE', 'passo': N_ETAPAS - 1, 'passos': N_ETAPAS})
  saida['qoe'] = core_qoe.avaliar(conjs, usadas, sorted(removidas), perfil_qoe)
```

por

```python
  avisar({'etapa': 'cômodo', 'passo': N_ETAPAS - 1, 'passos': N_ETAPAS})
  prev = core_comodo.de_previsoes(conjs['speedtest_down_mbps'].df, previsoes['speedtest_down_mbps'],
                                  previsoes['speedtest_up_mbps'], quantis['latency_ms'], quantis['jitter_ms'])
  saida['comodo'] = _bloco_comodo(conjs, prev, ambiente)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_comodo.py tests/test_studio_salvar.py tests/test_studio_qoe.py tests/test_modelos_core.py tests/test_studio_reavaliar.py 2>&1 | tail -6`
Expected: OK, exceto a falha antiga `test_modelos_core.TestSemente.test_registro_do_repositorio` (já falhava antes deste plano).

- [ ] **Step 7: Commit (pelo usuário)**

Arquivos: `src/ml/studio/api.py`, `src/ml/core/modelos.py`, `tests/test_studio_comodo.py`, `tests/test_studio_qoe.py`, `tests/test_studio_salvar.py`, `tests/test_modelos_core.py`.
Mensagem sugerida: `feat(studio): régua por cômodo na avaliação e no endpoint do rascunho; sai o QoE`

---

### Task 3: Lógica do front (`logica.js`)

**Files:**
- Modify: `src/ml/studio/static/logica.js`
- Modify: `tests/js/logica.test.js`

- [ ] **Step 1: Trocar os testes JS**

Em `tests/js/logica.test.js`, trocar o trecho que vai de `const QOE = (resultado, contra = []) => ...` até o fim do teste `'notaCartao usa o QoE quando existe e cai para o atende completo'` (os testes `podeAtivar` x2, `notaCartao` x2 e `precisaPedirQoe`; a linha `const AVAL = ...` fica) por:

```javascript
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js 2>&1 | tail -8`
Expected: falhas em `podeAtivar`, `notaCartao` e `precisaPedirComodo` (não é função).

- [ ] **Step 3: Implementar em `logica.js`**

Trocar a função `podeAtivar` inteira, com os dois comentários acima dela, por:

```javascript
  // A ativação segue o veredito da régua por cômodo (core/comodo.py); o de promoção da regressão
  // continua na tela, mas não trava. `comodo` é a resposta de api/modelos/avaliar_comodo.
  function podeAtivar(aval, atual, comodo) {
    if (!aval || !atual) return { ok: false, motivo: 'Espere a avaliação do rascunho atual terminar.' };
    if (!comodo || !comodo.resultado) return { ok: false, motivo: 'Sem veredito por cômodo contra a versão ativa: espere a avaliação por cômodo.' };
    const cob = aval.cobertura;
    if (!cob || (cob.nivel !== '100%' && cob.nivel !== 'proxy')) {
      const lacunas = cob ? cob.lacunas.map((l) => l.feature).join(', ') : '';
      return { ok: false, motivo: `O rascunho é "TR-069 parcial" (${lacunas}): salve para estudar; ativar daqui exige 100% TR-069 ou proxy.` };
    }
    if (comodo.resultado !== 'melhor') {
      return { ok: false, motivo: 'O veredito por cômodo não diz "melhor": para ativar mesmo assim, salve e use o menu do cartão.' };
    }
    return { ok: true, motivo: '' };
  }
```

Trocar a função `precisaPedirQoe` inteira, com os dois comentários acima dela, por:

```javascript
  // Decisão de pedir a avaliação por cômodo: há rascunho diferente da ativa e o que está guardado
  // é de outra chave (ou de nenhuma). Idempotente por chave: em voo ou pronto, não repete.
  function precisaPedirComodo(e) {
    return !!e.temSel && !e.igualAtiva && e.comodoKey !== e.chaveComodo;
  }
```

Trocar a função `notaCartao` inteira, com o comentário acima dela, por:

```javascript
  // Número principal do cartão: a nota por cômodo, com a diferença contra o piso; sem ela (avaliação
  // antiga), o "atende completo" com o rótulo pedindo reavaliação.
  function notaCartao(v) {
    const a = (v && v.avaliacao) || {};
    const c = a.comodo && a.comodo.nota != null ? a.comodo : null;
    if (c) return { valor: c.nota, rotulo: 'cômodo', secundario: c.contra_piso ? c.contra_piso.diferenca : null };
    const ac = a.atende_completo && a.atende_completo.media != null ? a.atende_completo.media : null;
    return { valor: ac, rotulo: 'reavaliar', secundario: null };
  }
```

Na linha de exportação (a que lista `podeAtivar, notaCartao, precisaPedirQoe, vooUnico, ...`), trocar `precisaPedirQoe` por `precisaPedirComodo`.

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/logica.test.js 2>&1 | tail -8`
Expected: `# pass 24`, `# fail 0`.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/studio/static/logica.js`, `tests/js/logica.test.js`.
Mensagem sugerida: `feat(studio): nota do cartão e trava de ativação pela régua por cômodo`

---

### Task 4: Assistente e cartão (`modelo.js`)

**Files:**
- Modify: `src/ml/studio/static/modelo.js`

Cada item é uma troca exata de texto; o texto antigo está como aparece hoje no arquivo.

- [ ] **Step 1: Estado e chaves**

Trocar

```javascript
    perfil: 'norma', qoe: null, qoeKey: null, qoeErro: null,
```

por

```javascript
    comodo: null, comodoKey: null, comodoErro: null,
```

Trocar

```javascript
  // O QoE não depende do alvo da tela: a chave é a do rascunho mais o perfil.
  const chaveQoe = () => [dsIds().join(','), st.ctx.ambiente, selLista().join(','), st.reg.ativo, st.perfil].join('|');
  const qoeAtual = () => (st.qoe && st.qoeKey === chaveQoe() ? st.qoe : null);
  // Último veredito de QoE de cada versão (para o "Tornar ativa" do cartão); independe do alvo.
  // Inclui a ativa: "melhor contra a ativa antiga" não vale depois que outra versão é ativada.
  const chaveVered = (nome) => [nome, 'qoe', dsIds().join(','), st.ctx.ambiente, st.perfil, st.reg.ativo].join('|');
```

por

```javascript
  // O cômodo não depende do alvo da tela: a chave é a do rascunho, da base (denominador) e da ativa.
  const chaveComodo = () => [dsIds().join(','), st.ctx.ambiente, selLista().join(','), st.base, st.reg.ativo].join('|');
  const comodoAtual = () => (st.comodo && st.comodoKey === chaveComodo() ? st.comodo : null);
  // Último veredito por cômodo de cada versão (para o "Tornar ativa" do cartão); independe do alvo.
  // Inclui a ativa: "melhor contra a ativa antiga" não vale depois que outra versão é ativada.
  const chaveVered = (nome) => [nome, 'comodo', dsIds().join(','), st.ctx.ambiente, st.reg.ativo].join('|');
```

- [ ] **Step 2: Pedido ao servidor**

Trocar as funções `urlQoe` e `avaliarQoe` inteiras (do `function urlQoe() {` até o `}` que fecha `avaliarQoe`, incluindo o comentário `// Síncrono no servidor (cerca de 40 s sem cache)...`) por:

```javascript
  function urlComodo() {
    return 'api/modelos/avaliar_comodo?ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
      '&ambiente=' + encodeURIComponent(st.ctx.ambiente) + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&base=' + encodeURIComponent(st.base) + '&contra=' + encodeURIComponent(st.reg.ativo);
  }

  // Síncrono no servidor (cerca de 1 min sem cache). Resposta de chave velha é descartada.
  function avaliarComodo() {
    if (!pronto()) return Promise.resolve();
    const k = chaveComodo();
    if (!L.precisaPedirComodo({ temSel: st.sel.size > 0, igualAtiva: igualAtiva(), comodoKey: st.comodoKey, chaveComodo: k })) return Promise.resolve();
    const base = st.base;
    st.comodoKey = k; st.comodo = null; st.comodoErro = null;
    return U.pedir(urlComodo()).then((c) => {
      if (st.comodoKey !== k) return;                  // resposta de rascunho antigo
      st.comodo = c; st.comodoErro = null;
      if (base === st.base && !sujo()) st.vereditos[chaveVered(base)] = c.resultado;
    }).catch((e) => { if (st.comodoKey === k) st.comodoErro = e.message; }).finally(desenhar);
  }
```

Em `avaliarAgora`, trocar `    avaliarQoe();` por `    avaliarComodo();`. Em `agendar`, trocar

```javascript
    if (st.avalKey === k || st.avalErroKey === k) { st.avaliando = false; avaliarQoe(); return; }   // regressão em cache: o QoE pode ter ficado para trás
```

por

```javascript
    if (st.avalKey === k || st.avalErroKey === k) { st.avaliando = false; avaliarComodo(); return; }   // regressão em cache: o cômodo pode ter ficado para trás
```

- [ ] **Step 3: Salvar e "Tornar ativa"**

Trocar

```javascript
    const qPub = qoeAtual();   // o veredito de QoE do que está sendo salvo, para lembrar na versão nova
    const verPub = qPub && qPub.promocao_qoe ? qPub.promocao_qoe.resultado : null;
```

por

```javascript
    const cPub = comodoAtual();   // o veredito por cômodo do que está sendo salvo, para lembrar na versão nova
    const verPub = cPub ? cPub.resultado : null;
```

Trocar `ambiente: st.ctx.ambiente, base: st.base, desenho, ativar: !!f.ativar, perfil_qoe: st.perfil })` por `ambiente: st.ctx.ambiente, base: st.base, desenho, ativar: !!f.ativar })`.

Em `ativarManual`, trocar `O último veredito de QoE de ${nome}` por `O último veredito por cômodo de ${nome}` e `Não há veredito de QoE de ${nome}` por `Não há veredito por cômodo de ${nome}`.

- [ ] **Step 4: Cartão**

Em `cartao`, apagar as duas linhas de selo do QoE:

```javascript
      ((v.avaliacao || {}).qoe || {}).perfil ? `<span class="tag" title="limiares do QoE desta versão">${v.avaliacao.qoe.perfil === 'norma' ? 'norma' : 'perfil atual'}</span>` : '',
      (((v.avaliacao || {}).qoe || {}).supera_piso === false) ? '<span class="tag leak" title="não supera o classificador só com radio">abaixo do piso</span>' : '',
```

E trocar

```javascript
${nota.secundario == null ? '' : ` <small class="gate-msg">atende ${num(nota.secundario, 2)}</small>`}
```

por

```javascript
${nota.secundario == null ? '' : ` <small class="gate-msg" title="diferença contra o piso (só radio)">vs piso ${nota.secundario > 0 ? '+' : ''}${num(nota.secundario, 2)}</small>`}
```

- [ ] **Step 5: Painel do rascunho**

Apagar a constante `PERFIS`, a função `seletorPerfil` e a função `tabelaLimiares` inteiras (do `const PERFIS = ...` até o `}` que fecha `tabelaLimiares`).

Trocar a função `blocoQoe` inteira por:

```javascript
  function blocoComodo() {
    const c = comodoAtual();
    if (st.comodoErro && st.comodoKey === chaveComodo()) return U.gate('critical', 'Não foi possível avaliar por cômodo', `${esc(st.comodoErro)} Se a mensagem pede para reavaliar, use o menu do cartão da versão.
      <button class="btn" data-acao="comodo-repetir" data-k="comodo-repetir">Tentar de novo</button>`);
    if (!c) return '<p class="hint" role="status">Avaliando por cômodo (quatro alvos, cerca de 1 min)…</p>';
    const faixa = (iv) => (iv ? ` <em>${num(iv[0], 3)} a ${num(iv[1], 3)}</em>` : '');
    const kpis = [['Cômodo rascunho', num(c.nota, 3), faixa(c.intervalo)],
                  [`Cômodo ${esc(st.reg.ativo)}`, num(c.nota_base, 3), ''],
                  ['Piso (só radio)', num(c.piso.nota, 3), faixa(c.piso.intervalo)]];
    const predios = Object.entries(c.por_predio).map(([s, [a, n]]) => `${esc(s)} ${a}/${n}`).join(', ');
    const dif = `Diferença contra ${st.reg.ativo}: ${num(c.diferenca, 3)}` +
      (c.intervalo_diferenca ? ` (90%: ${num(c.intervalo_diferenca[0], 3)} a ${num(c.intervalo_diferenca[1], 3)}).` : '.');
    return `<div class="qoe">
      <div class="veredito ${c.resultado}">${icone(VEREDITO[c.resultado].icone)}
        <div><b>Cômodo: ${esc(VEREDITO[c.resultado].frase(st.reg.ativo))}</b> <span class="gate-msg">(decide a ativação)</span>
          <div class="gate-msg">${esc(dif)}</div></div></div>
      <div class="kpis">${kpis.map(([t, b, e]) => `<div><span>${t}</span><b>${b}</b>${e}</div>`).join('')}</div>
      <p class="gate-msg">Nota: acurácia balanceada das classes bom, degradado e ruim, por posição, com a capacidade
        relativa à melhor posição do prédio. Acertos por prédio: ${predios}.</p>
    </div>`;
  }
```

(A classe `qoe` do contêiner é mantida de propósito: reaproveita o estilo que já existe em `styles.css`.)

Em `painelVeredito`, trocar `    const bq = blocoQoe();   // o QoE decide a ativação: aparece mesmo sem o resultado da regressão` por `    const bq = blocoComodo();   // o cômodo decide a ativação: aparece mesmo sem o resultado da regressão`.

Em `secaoRascunho`, apagar a linha `        ${seletorPerfil()}`.

- [ ] **Step 6: Barra fixa**

Trocar a função `motivoDock` inteira, com o comentário acima dela, por:

```javascript
  // Por que "Salvar e tornar ativa" está desabilitado: a avaliação por cômodo ainda roda, falhou, ou a trava diz.
  function motivoDock(c, pode) {
    if (!c && st.sel.size && !igualAtiva()) {
      return st.comodoErro && st.comodoKey === chaveComodo()
        ? `Avaliação por cômodo falhou: ${st.comodoErro} (use "Tentar de novo" no painel)` : 'Avaliando por cômodo…';
    }
    return st.avaliando ? 'Reavaliando o rascunho…' : pode.motivo;
  }
```

Em `dock`, trocar

```javascript
    const q = qoeAtual();
    const v = q && q.promocao_qoe ? q.promocao_qoe : null;
    const pode = L.podeAtivar(st.aval, atual, q);
    const estado = st.avaliando ? '<span class="dock-ver">avaliando…</span>'
      : v ? `<span class="dock-ver ${v.resultado}">${icone(VEREDITO[v.resultado].icone)} ${VEREDITO[v.resultado].rotulo}</span>` : '';
```

por

```javascript
    const c = comodoAtual();
    const pode = L.podeAtivar(st.aval, atual, c);
    const estado = st.avaliando ? '<span class="dock-ver">avaliando…</span>'
      : c ? `<span class="dock-ver ${c.resultado}">${icone(VEREDITO[c.resultado].icone)} ${VEREDITO[c.resultado].rotulo}</span>` : '';
```

e `${esc(motivoDock(q, pode))}` por `${esc(motivoDock(c, pode))}`.

- [ ] **Step 7: Eventos**

Trocar

```javascript
      case 'qoe-repetir': st.qoeKey = null; avaliarQoe(); desenhar(); break;
      case 'perfil': st.perfil = b.dataset.p; avaliarQoe(); desenhar(); break;
```

por

```javascript
      case 'comodo-repetir': st.comodoKey = null; avaliarComodo(); desenhar(); break;
```

- [ ] **Step 8: Conferir que não sobrou referência ao QoE**

Run: `grep -n "qoe\|Qoe\|QoE\|perfil" src/ml/studio/static/modelo.js`
Expected: só a classe CSS `class="qoe"` em `blocoComodo`. Qualquer outra linha é resto da troca e precisa ser resolvida antes de seguir.

Run: `node --check src/ml/studio/static/modelo.js && node --test tests/js/logica.test.js 2>&1 | tail -3`
Expected: sem erro de sintaxe; `# fail 0`.

- [ ] **Step 9: Commit (pelo usuário)**

Arquivos: `src/ml/studio/static/modelo.js`.
Mensagem sugerida: `feat(studio): bloco Cômodo no Assistente e sem seletor de perfil de QoE`

---

### Task 5: Verificação e reavaliação de v1 a v5

**Files:** nenhum de código. `src/ml/core/modelos.json` muda pela reavaliação (é a migração prevista no spec).

- [ ] **Step 1: Suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)|^(FAIL|ERROR):"` (timeout 600000 ms)
Expected: só as 2 falhas antigas (`test_features_core.TestSemente.test_tabela_tr181_do_repositorio`, `test_modelos_core.TestSemente.test_registro_do_repositorio`).

Run: `node --test tests/js/logica.test.js 2>&1 | tail -3`
Expected: `# fail 0`.

- [ ] **Step 2: Subir o Studio**

Run (em segundo plano, da raiz do repositório): `venv/bin/python src/ml/studio.py --port 8123`
Esperar `curl -sf -o /dev/null http://127.0.0.1:8123/api/payload` responder.

- [ ] **Step 3: Conferir no navegador (Playwright)**

Abrir `http://127.0.0.1:8123`, área Modelos, com o conjunto padrão de datasets ligado:
1. Os cartões de v1 a v5 mostram o rótulo "reavaliar" (avaliações antigas, sem bloco `comodo`).
2. Reavaliar v1 a v5 pelo menu de cada cartão ("Reavaliar"), uma de cada vez, esperando cada uma terminar. Não usar "Reavaliar todas": ele só pega as versões marcadas como desatualizadas pela régua de regressão, e estas não estão. A etapa mostrada no progresso termina em "cômodo".
3. Os cartões passam a mostrar a nota por cômodo e "vs piso". Conferir contra o benchmark: v1 0,64; v2-tr069 0,64; v3-tr069, v4 e v5 0,72; "vs piso" de +0,19 a +0,27.
4. Clicar no cartão da v5 (rascunho a partir dela, diferente da ativa v1): o bloco "Cômodo" aparece em cerca de 1 min, com veredito "Empate com v1", e o botão "Salvar e tornar ativa" fica desabilitado com o motivo "O veredito por cômodo não diz "melhor"...".
5. Console do navegador sem erros (o 404 de `favicon.ico` não conta).

Se a nota de algum cartão diferir do benchmark em mais de 0,001, PARAR e reportar.

- [ ] **Step 4: Derrubar o servidor e conferir o registro**

Parar o processo do Studio. Run: `git diff --stat src/ml/core/modelos.json` e conferir que só o `modelos.json` mudou fora do código deste plano.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/modelos.json`.
Mensagem sugerida: `chore(modelos): reavaliação de v1 a v5 pela régua por cômodo`

---

### Task 6: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (acrescentar no topo, sem apagar as seções existentes)

- [ ] **Step 1: Acrescentar a seção no topo**

Preencher com os números da Task 5 (cartões depois da reavaliação). Nenhum `<...>` pode ficar no arquivo.

```markdown
# Changelog — Studio: régua por cômodo como nota principal e critério de ativação

**Data:** 2026-10-29

## Por quê

O Studio mostrava a nota de QoE (cerca de 0,66 em todas as versões, presa pelos dois prédios do Villa) e
ativava versões pelo veredito dela. A régua por cômodo responde à pergunta do produto e separa as versões do
piso. Spec: `docs/superpowers/specs/2026-10-29-studio-comodo-design.md`; plano:
`docs/superpowers/plans/2026-10-29-studio-comodo.md`.

## Mudanças

- `core/comodo.py`: `de_previsoes` (as previsões que o Studio já calcula), `tabela_posicoes`, `bloco` (guardado na avaliação, com a tabela por posição da versão e do piso) e `comparar_blocos` (comparação entre avaliações guardadas).
- `studio/api.py`: a etapa "QoE" da avaliação vira "cômodo" (sem treino adicional; piso em cache por conjunto); `GET /api/modelos/avaliar_comodo` prevê só o rascunho e compara com a avaliação guardada da ativa (409 pedindo reavaliação quando ela não é comparável); `GET /api/modelos/avaliar_qoe` saiu.
- Front: o cartão mostra a nota por cômodo e a diferença contra o piso; o Assistente mostra o bloco "Cômodo" e a ativação segue o veredito dele (só "melhor" libera); o seletor de perfil de QoE saiu. "Apto para jogo" é guardado e não exibido.
- `core/modelos.nota_reavaliacao`: o histórico registra a nota por cômodo.
- `core/qoe.py`, `qoe_mlflow.py`, a régua de regressão e as métricas de "atende" não mudaram.

## Efeito medido

Reavaliação de v1 a v5 pelo Studio (conjunto padrão):

| Versão | Nota por cômodo | vs piso |
|---|---|---|
| v1 | <...> | <...> |
| v2-tr069 | <...> | <...> |
| v3-tr069 | <...> | <...> |
| v4 | <...> | <...> |
| v5 | <...> | <...> |

Rascunho da v5 contra a v1 ativa: <veredito>; botão de ativar desabilitado.

## Verificação

- Suíte Python: <n> testes, só as 2 falhas antigas.
- `node --test tests/js/logica.test.js`: <n> testes, 0 falhas.
- Navegador (Playwright): reavaliação de v1 a v5, cartões, bloco "Cômodo" do rascunho; console sem erros.
```

- [ ] **Step 2: Commit (pelo usuário)**

Arquivos: `CHANGELOG.md`.
Mensagem sugerida: `docs(changelog): Studio com a régua por cômodo`
