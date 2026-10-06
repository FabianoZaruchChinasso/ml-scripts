# Latência e jitter por quantis — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Latência e jitter passam a ser previstos como faixa (p50 e p90, em escala log) e medidos na régua única por pinball loss e cobertura, e o "atende" por aplicação passa a usar os quatro limiares ("atende completo").

**Architecture:** Um módulo novo, `src/ml/core/quantis.py`, faz as previsões quantílicas fora do fold (LOGO por prédio) com `HistGradientBoostingRegressor(loss='quantile')`, e calcula as métricas, a comparação entre versões e o "atende completo". Ele reaproveita de `src/ml/core/avaliacao.py` o bootstrap de posições, a junção por `_linha` e a acurácia balanceada. O Studio (`api.py`, `modelos.js`, `assistente.js`) e `regression_mlflow.py` passam a usá-lo para latência e jitter.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn (`HistGradientBoostingRegressor`), MLflow, FastAPI (Studio), JavaScript sem framework. Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-05-latencia-jitter-quantis-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add` nem `git stash`.** O usuário faz commit à mão. Onde aparecer "Checkpoint", siga adiante sem commitar.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 341 tests`, `OK`.
- `tests/test_studio_assistente.py` importa o irmão com `from test_studio_features import ...`, então só roda por `discover`: `python3 -m unittest discover -s tests -p "test_studio_assistente.py"`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último. Classes novas entram acima dele.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/quantis.py` | Novo. Modelo quantílico, previsões fora do fold, métricas, `delta_pinball`, `veredito_quantis`, `atende_completo` |
| `src/ml/core/avaliacao.py` | `VERSAO_REGUA` vai para `2026-10-05.2`; `atende` delega a um `_resumo_atende` reaproveitável |
| `src/ml/studio/api.py` | `avaliacao_completa` grava `quantis` e `atende_completo`; `_promocao` usa quantis em latência e jitter |
| `src/ml/studio/static/modelos.js` | Versões salvas: cobertura e pinball do p90 em latência e jitter; coluna "Atende completo" |
| `src/ml/studio/static/assistente.js` | Cartão de promoção com Δ pinball p90 e cobertura em latência e jitter |
| `src/ml/regression_mlflow.py` | Ramo quantílico para `ALVO=latency_ms` ou `jitter_ms` |
| `tests/test_quantis.py` | Novo |
| `tests/test_studio_assistente.py` | Testes da integração |
| `CHANGELOG.md` | Entrada nova no topo |

---

### Task 1: Métricas básicas e modelo quantílico

**Files:**
- Create: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_quantis.py`:

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import quantis as Q

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


class Constante(BaseEstimator, RegressorMixin):
  """Prevê sempre `valor` (na escala em que é treinado, a log)."""

  def __init__(self, valor=0.0):
    self.valor = valor

  def fit(self, X, y):
    self.n_ = len(X)
    return self

  def predict(self, X):
    return np.full(len(X), self.valor)


def frame(n_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n_por_local),
    'speedtest_down_mbps': 3 * snr, 'speedtest_up_mbps': snr,
    'latency_ms': 300 / snr * rng.lognormal(0, 0.3, n),
    'jitter_ms': 100 / snr * rng.lognormal(0, 0.5, n),
    'router_snr': snr, 'router_tx_bytes': snr * 1000,
  })


def conjunto(alvo='latency_ms'):
  return C.preparar({'a.csv': frame()}, alvo, TABELA, catalogo=())


class TestMetricas(unittest.TestCase):
  def test_pinball_valores_conhecidos(self):
    # erros +2 e -2 com q=0,9: max(1,8; -0,2) = 1,8 e max(-1,8; 0,2) = 0,2 -> média 1,0
    self.assertAlmostEqual(Q.pinball([10.0, 10.0], [8.0, 12.0], 0.9), 1.0)

  def test_cobertura(self):
    self.assertEqual(Q.cobertura([1.0, 2.0, 3.0, 4.0], [2.0, 2.0, 2.0, 2.0]), 0.5)

  def test_modelo_quantil_usa_perda_quantilica(self):
    m = Q.modelo_quantil(0.9)
    self.assertEqual((m.loss, m.quantile), ('quantile', 0.9))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis -v`
Expected: `ImportError: cannot import name 'quantis'`

- [ ] **Step 3: Criar `src/ml/core/quantis.py`**

```python
"""Régua quantílica para latência e jitter: faixa p50–p90 em escala log, por prédio.

Latência e jitter têm caudas longas (p99 de 350 ms e 205 ms) e variam muito na mesma
posição: um número só engana. O modelo prevê a faixa, e a régua mede pinball loss e
cobertura (a fração de valores reais abaixo de cada quantil previsto).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

QUANTIS = (0.5, 0.9)
ALVOS_QUANTILICOS = ('latency_ms', 'jitter_ms')
# Faixa aceita para a cobertura pooled do p90 num prédio novo.
FAIXA_COBERTURA = (0.80, 0.95)


def coluna(q: float) -> str:
  """Nome da coluna de um quantil nas previsões: 0,5 -> 'q50', 0,9 -> 'q90'."""
  return f'q{int(round(q * 100))}'


def modelo_quantil(q: float) -> HistGradientBoostingRegressor:
  """Gradient boosting com perda quantílica; aceita NaN sem imputer."""
  return HistGradientBoostingRegressor(loss='quantile', quantile=q, learning_rate=0.05, max_iter=300,
                                       min_samples_leaf=20, random_state=42)


def _perda(y, previsto, q: float) -> np.ndarray:
  erro = np.asarray(y, dtype=float) - np.asarray(previsto, dtype=float)
  return np.maximum(q * erro, (q - 1) * erro)


def pinball(y, previsto, q: float) -> float:
  """Perda quantílica média: penaliza q vezes o que ficou abaixo e (1 - q) o que ficou acima."""
  return float(np.mean(_perda(y, previsto, q)))


def cobertura(y, previsto) -> float:
  """Fração dos valores reais menores ou iguais ao quantil previsto (o ideal é o próprio quantil)."""
  return float(np.mean(np.asarray(y, dtype=float) <= np.asarray(previsto, dtype=float)))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v`
Expected: `Ran 3 tests ... OK`

---

### Task 2: Previsões quantílicas fora do fold

**Files:**
- Modify: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

Acima do bloco `__main__` de `tests/test_quantis.py`:

```python
class TestPrevisoes(unittest.TestCase):
  def test_folds_por_predio_e_colunas(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    self.assertEqual(list(prev.columns), ['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos'])
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    self.assertEqual(sorted(prev['_linha']), sorted(conj.df['_linha']))
    self.assertTrue((prev['q90'] >= prev['q50']).all())

  def test_volta_da_escala_log(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(np.log1p(20.0))}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    np.testing.assert_allclose(prev['q50'], 5.0)
    np.testing.assert_allclose(prev['q90'], 20.0)
    self.assertFalse(prev['cruzado'].any())

  def test_corta_em_zero_e_corrige_cruzamento(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(-10.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    np.testing.assert_allclose(prev['q90'], prev['q50'])
    self.assertTrue(prev['cruzado'].all())

  def test_y_fica_em_ms(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    reais = conj.df.set_index('_linha')['latency_ms']
    np.testing.assert_allclose(prev.set_index('_linha')['y'].sort_index(), reais.sort_index())

  def test_vazamento_levanta(self):
    conj = conjunto()
    with self.assertRaises(AssertionError):
      Q.prever_quantis_fora_do_fold(conj.df, ['router_tx_bytes'], conj.alvo, ['router_tx_bytes'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestPrevisoes -v`
Expected: `AttributeError: module 'ml.core.quantis' has no attribute 'prever_quantis_fora_do_fold'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/quantis.py`, acrescente aos imports (bloco único no topo):

```python
from sklearn.base import clone

from ml.core.avaliacao import assert_sem_vazamento
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds
```

Junto das constantes:

```python
_COLUNAS = ['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']
```

Ao fim do arquivo:

```python
def prever_quantis_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas,
                                estimadores: dict = None) -> pd.DataFrame:
  """p50 e p90 de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Treina em log1p(y) e volta com expm1, cortado em 0. Se o p90 sair abaixo do p50
  (quantis cruzados), o p90 passa a valer o p50 e a linha fica com `cruzado` verdadeiro.
  `estimadores` ({quantil: estimador}) troca os modelos; são clonados a cada fold.
  Devolve _linha, y (em ms), q50, q90, cruzado, _site, _pos, indexados como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS)
  sub = df[df[y_col].notna()]
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  y_log = np.log1p(y.clip(lower=0))
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y_log, sub['_site']):
    previstos = {}
    for q in QUANTIS:
      base = (estimadores or {}).get(q)
      modelo = clone(base) if base is not None else modelo_quantil(q)
      modelo.fit(fold.X_train, fold.y_train)
      previstos[q] = np.clip(np.expm1(np.asarray(modelo.predict(fold.X_test), dtype=float)), 0, None)
    cruzado = previstos[0.9] < previstos[0.5]
    previstos[0.9] = np.maximum(previstos[0.9], previstos[0.5])
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': y.loc[indice].to_numpy(),
                                'q50': previstos[0.5], 'q90': previstos[0.9], 'cruzado': cruzado,
                                '_site': fold.test_site, '_pos': posicao.loc[indice].to_numpy()},
                               index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS)
  return pd.concat(partes)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 3: Resumo quantílico com intervalos

**Files:**
- Modify: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

Acima do bloco `__main__`:

```python
def previsto(y, q50, q90, sites=None, linhas=None):
  n = len(y)
  return pd.DataFrame({'_linha': linhas or [f'a:{i}' for i in range(n)], 'y': y, 'q50': q50, 'q90': q90,
                       'cruzado': [False] * n, '_site': sites or ['s1', 's1', 's2', 's2'][:n],
                       '_pos': ['p1', 'p2', 'p3', 'p4'][:n]})


class TestResumo(unittest.TestCase):
  def test_metricas_pooled_e_por_predio(self):
    prev = previsto([10.0, 20.0, 30.0, 40.0], [10.0, 20.0, 30.0, 40.0], [15.0, 25.0, 25.0, 45.0])
    prev.loc[0, 'cruzado'] = True
    r = Q.resumir_quantis(prev, 3)
    self.assertEqual(r['cobertura']['q90'], 0.75)
    self.assertEqual(r['cobertura']['q50'], 1.0)
    self.assertEqual(r['pinball']['q50'], 0.0)
    self.assertEqual(r['por_local']['s2']['cobertura']['q90'], 0.5)
    self.assertEqual(r['cruzados'], 1)
    self.assertEqual(r['mediana_mae'], 0.0)
    self.assertEqual(r['n'], 3)
    for chave in ('pinball_q50', 'pinball_q90', 'cobertura_q50', 'cobertura_q90'):
      self.assertIn(chave, r['intervalos'])

  def test_vazio_nao_quebra(self):
    r = Q.resumir_quantis(pd.DataFrame(columns=['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']), 0)
    self.assertEqual((r['pinball'], r['cobertura'], r['intervalos'], r['mediana_mae']), ({}, {}, {}, None))

  def test_traz_versao_da_regua(self):
    from ml.core import avaliacao as A
    self.assertEqual(Q.resumir_quantis(previsto([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]), 1)['versao_regua'],
                     A.VERSAO_REGUA)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestResumo -v`
Expected: `AttributeError: ... 'resumir_quantis'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/quantis.py`, troque `from ml.core.avaliacao import assert_sem_vazamento` por:

```python
from ml.core.avaliacao import VERSAO_REGUA, _intervalo, assert_sem_vazamento, reamostras
```

Ao fim do arquivo:

```python
def _metricas(prev: pd.DataFrame) -> dict:
  return {'pinball': {coluna(q): round(pinball(prev['y'], prev[coluna(q)], q), 4) for q in QUANTIS},
          'cobertura': {coluna(q): round(cobertura(prev['y'], prev[coluna(q)]), 4) for q in QUANTIS}}


def resumir_quantis(prev: pd.DataFrame, n: int, amostras=None) -> dict:
  """Pinball e cobertura de cada quantil, pooled e por prédio, com intervalo de 90% pooled.

  `mediana_mae` é o MAE em ms do p50, para comparar com a regressão pontual.
  `cruzados` conta as linhas em que o p90 foi corrigido para o p50.
  """
  resumo = {'n': n, 'versao_regua': VERSAO_REGUA}
  if prev.empty:
    return dict(resumo, pinball={}, cobertura={}, por_local={}, intervalos={}, cruzados=0, mediana_mae=None)
  resumo.update(_metricas(prev))
  resumo['por_local'] = {s: _metricas(g) for s, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0])}
  resumo['cruzados'] = int(prev['cruzado'].astype(bool).sum())
  y = prev['y'].to_numpy(dtype=float)
  resumo['mediana_mae'] = round(float(np.mean(np.abs(y - prev['q50'].to_numpy(dtype=float)))), 4)
  resumo['intervalos'] = {}
  if len(prev) > 1:
    amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
    for q in QUANTIS:
      c = coluna(q)
      p = prev[c].to_numpy(dtype=float)
      resumo['intervalos'][f'pinball_{c}'] = _intervalo([pinball(y[i], p[i], q) for i in amostras])
      resumo['intervalos'][f'cobertura_{c}'] = _intervalo([cobertura(y[i], p[i]) for i in amostras])
  return resumo
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 4: Comparação entre versões e veredito

**Files:**
- Modify: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

Acima do bloco `__main__`:

```python
def delta(valor, lo, hi):
  return {'valor': valor, 'intervalo': [lo, hi], 'pinball_base': 5.0, 'n': 10}


class TestVeredito(unittest.TestCase):
  def test_delta_pinball_da_nova_perfeita(self):
    y = [10.0, 20.0, 30.0, 40.0]
    nova = previsto(y, y, y)
    base = previsto(y, y, [v + 10 for v in y])
    d = Q.delta_pinball(nova, base)
    # base: erro -10 com q=0,9 -> max(-9; 1) = 1 por linha; nova: 0
    self.assertEqual((d['valor'], d['pinball_base'], d['n']), (-1.0, 1.0, 4))
    self.assertLess(d['intervalo'][1], 0)

  def test_sem_linhas_em_comum_levanta(self):
    with self.assertRaises(ValueError):
      Q.delta_pinball(previsto([1.0], [1.0], [1.0]), previsto([1.0], [1.0], [1.0], linhas=['b:0']))

  def test_cobertura_fora_da_faixa_e_pior_mesmo_com_pinball_melhor(self):
    self.assertEqual(Q.veredito_quantis(delta(-1.5, -2.0, -1.0), 0.70)['resultado'], 'pior')

  def test_pinball_pior_e_pior(self):
    self.assertEqual(Q.veredito_quantis(delta(0.8, 0.5, 1.0), 0.90)['resultado'], 'pior')

  def test_pinball_melhor_com_cobertura_boa_e_melhor(self):
    self.assertEqual(Q.veredito_quantis(delta(-1.5, -2.0, -1.0), 0.90)['resultado'], 'melhor')

  def test_intervalo_com_zero_e_empate(self):
    self.assertEqual(Q.veredito_quantis(delta(0.0, -1.0, 1.0), 0.90)['resultado'], 'empate')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestVeredito -v`
Expected: `AttributeError: ... 'delta_pinball'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/quantis.py`, troque a linha de import de `avaliacao` por:

```python
from ml.core.avaliacao import VERSAO_REGUA, _br, _intervalo, assert_sem_vazamento, reamostras
```

Ao fim do arquivo:

```python
def delta_pinball(nova: pd.DataFrame, base: pd.DataFrame, q: float = 0.9, amostras=None) -> dict:
  """Pinball do quantil `q` da nova versão menos o da base, nas mesmas linhas e reamostragens."""
  c = coluna(q)
  j = nova.set_index('_linha')[['y', c, '_site', '_pos']].join(
    base.set_index('_linha')[[c]].rename(columns={c: 'base'}), how='inner')
  if j.empty:
    raise ValueError('as duas versões não têm previsões em comum para comparar')
  y = j['y'].to_numpy(dtype=float)
  perda_nova, perda_base = _perda(y, j[c], q), _perda(y, j['base'], q)
  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(float(perda_nova.mean() - perda_base.mean()), 4),
          'intervalo': _intervalo([perda_nova[i].mean() - perda_base[i].mean() for i in amostras]),
          'pinball_base': round(float(perda_base.mean()), 4), 'n': int(len(j))}


def veredito_quantis(delta: dict, cobertura_nova: float) -> dict:
  """Melhor / empate / pior para latência e jitter (nova − base, intervalo de 90%).

  Pior: a cobertura pooled do p90 da nova versão sai de FAIXA_COBERTURA, ou o
  intervalo de Δ pinball fica todo acima de 0. Melhor: o intervalo fica todo abaixo
  de 0 com a cobertura na faixa. Empate: o resto.
  """
  lo_c, hi_c = FAIXA_COBERTURA
  lo, hi = delta['intervalo']
  faixa = f'{_br(lo, 2)} a {_br(hi, 2)}'
  if not lo_c <= cobertura_nova <= hi_c:
    return {'resultado': 'pior', 'motivo': f'A cobertura do p90 é {_br(cobertura_nova, 2)}, fora da faixa de '
                                           f'{_br(lo_c, 2)} a {_br(hi_c, 2)}: a faixa prevista não é confiável.'}
  if lo > 0:
    return {'resultado': 'pior', 'motivo': f'O pinball do p90 subiu {_br(delta["valor"], 2)} (90%: {faixa}).'}
  if hi < 0:
    return {'resultado': 'melhor', 'motivo': f'O pinball do p90 caiu {_br(-delta["valor"], 2)} (90%: {faixa}), '
                                             'com a cobertura na faixa.'}
  return {'resultado': 'empate', 'motivo': 'O intervalo da diferença de pinball inclui 0: com estes locais, '
                                           'não dá para separar as duas versões.'}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 5: "Atende completo" e `_resumo_atende` compartilhado

**Files:**
- Modify: `src/ml/core/avaliacao.py` (`atende` passa a delegar a `_resumo_atende`)
- Modify: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

Acima do bloco `__main__`:

```python
def pontual(y, yhat, linhas):
  n = len(y)
  return pd.DataFrame({'_linha': linhas, 'y': y, 'yhat': yhat,
                       '_site': ['s1', 's1', 's2', 's2', 's2'][:n], '_pos': ['p1', 'p2', 'p3', 'p4', 'p5'][:n]})


APPS = {'Jogo': {'dn': 10, 'up': 1, 'lat': 40, 'jit': 10},
        'Tudo': {'dn': 0, 'up': 0, 'lat': 10000, 'jit': 10000}}
LINHAS = ['a:0', 'a:1', 'a:2', 'a:3']


class TestAtendeCompleto(unittest.TestCase):
  def test_quatro_limiares_com_p90_em_latencia_e_jitter(self):
    dn = pontual([30.0] * 5, [30.0] * 5, LINHAS + ['a:9'])
    up = pontual([10.0] * 4, [10.0] * 4, LINHAS)
    lat = previsto([20.0, 20.0, 80.0, 20.0], [15.0] * 4, [30.0, 50.0, 90.0, 30.0])
    jit = previsto([5.0, 5.0, 5.0, 20.0], [4.0] * 4, [5.0] * 4)
    r = Q.atende_completo(dn, up, lat, jit, APPS)
    # Jogo: real [T, T, F, F]; previsto pelo p90 [T, F, F, T] -> (1/2 + 1/2) / 2 = 0,5
    self.assertEqual(r['por_aplicacao'], {'Jogo': 0.5})
    self.assertEqual((r['media'], r['n']), (0.5, 4))
    self.assertTrue(any('Tudo' in a for a in r['avisos']))

  def test_sem_linha_comum_levanta(self):
    dn = pontual([30.0], [30.0], ['x:0'])
    with self.assertRaises(ValueError):
      Q.atende_completo(dn, dn, previsto([1.0], [1.0], [1.0]), previsto([1.0], [1.0], [1.0]), APPS)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestAtendeCompleto -v`
Expected: `AttributeError: ... 'atende_completo'`

- [ ] **Step 3: Extrair `_resumo_atende` em `avaliacao.py`**

Em `src/ml/core/avaliacao.py`, troque a função `atende` inteira por estas duas:

```python
def _resumo_atende(j: pd.DataFrame, classes: dict, amostras=None) -> dict:
  """Acurácia balanceada por aplicação, média e intervalo de 90%.

  `classes`: nome da aplicação -> (real, previsto), vetores booleanos alinhados com `j`.
  Aplicação em que só uma classe aparece nos dados reais fica fora da média, com aviso.
  """
  pares, por_aplicacao, avisos = {}, {}, []
  for nome, (real, previsto) in classes.items():
    valor = _acuracia_balanceada(real, previsto)
    if np.isnan(valor):
      avisos.append(f'{nome}: só uma classe nos dados reais; fora da média')
      continue
    pares[nome] = (real, previsto)
    por_aplicacao[nome] = round(valor, 4)
  media = round(mean(por_aplicacao.values()), 4) if por_aplicacao else None
  intervalo = None
  if pares and len(j) > 1:
    amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
    intervalo = _intervalo([_media_sem_nan([_acuracia_balanceada(r[i], p[i]) for r, p in pares.values()])
                            for i in amostras])
  return {'por_aplicacao': por_aplicacao, 'media': media, 'intervalo': intervalo,
          'n': int(len(j)), 'avisos': avisos}


def atende(prev_down: pd.DataFrame, prev_up: pd.DataFrame, aplicacoes: dict, amostras=None) -> dict:
  """Acurácia balanceada de "atende em throughput" por aplicação, real contra previsto.

  Atende = download >= limiar dn e upload >= limiar up, nas linhas com os dois alvos.
  """
  j = _juntar(dn=prev_down, up=prev_up)
  classes = {nome: (_atende_em(j, limiares, 'y_dn', 'y_up'), _atende_em(j, limiares, 'p_dn', 'p_up'))
             for nome, limiares in aplicacoes.items()}
  return _resumo_atende(j, classes, amostras)
```

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -3`
Expected: `OK` (os testes de `atende` continuam passando).

- [ ] **Step 4: Implementar `atende_completo`**

Em `src/ml/core/quantis.py`, troque a linha de import de `avaliacao` por:

```python
from ml.core.avaliacao import (VERSAO_REGUA, _atende_em, _br, _intervalo, _juntar, _resumo_atende,
                               assert_sem_vazamento, reamostras)
```

Ao fim do arquivo:

```python
def atende_completo(prev_dn: pd.DataFrame, prev_up: pd.DataFrame, quant_lat: pd.DataFrame,
                    quant_jit: pd.DataFrame, aplicacoes: dict, amostras=None) -> dict:
  """Acurácia balanceada de "atende" com os quatro limiares, por aplicação.

  Real: download >= dn, upload >= up, latência <= lat e jitter <= jit. Previsto:
  download e upload pontuais, e o p90 de latência e de jitter. Só nas linhas
  presentes nos quatro alvos.
  """
  j = _juntar(dn=prev_dn, up=prev_up,
              lat=quant_lat.rename(columns={'q90': 'yhat'}), jit=quant_jit.rename(columns={'q90': 'yhat'}))
  if j.empty:
    raise ValueError('nenhuma linha comum aos quatro alvos para medir "atende completo"')
  classes = {}
  for nome, lim in aplicacoes.items():
    real = (_atende_em(j, lim, 'y_dn', 'y_up') & (j['y_lat'] <= lim['lat']).to_numpy()
            & (j['y_jit'] <= lim['jit']).to_numpy())
    previsto = (_atende_em(j, lim, 'p_dn', 'p_up') & (j['p_lat'] <= lim['lat']).to_numpy()
                & (j['p_jit'] <= lim['jit']).to_numpy())
    classes[nome] = (real, previsto)
  return _resumo_atende(j, classes, amostras)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis tests.test_avaliacao 2>&1 | tail -3`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 6: Integração no Studio (API) e versão da régua

**Files:**
- Modify: `src/ml/core/avaliacao.py:22` (`VERSAO_REGUA`)
- Modify: `src/ml/studio/api.py` (`_promocao`, `avaliacao_completa`, imports)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_assistente.py`, dentro de `TestRotasAssistente`:

```python
  def test_avaliacao_completa_traz_quantis_e_atende_completo(self):
    av = api.avaliacao_completa('a.csv', '', ['router_snr'])
    self.assertIn('q90', av['latency_ms']['quantis']['cobertura'])
    self.assertIn('q90', av['jitter_ms']['quantis']['pinball'])
    self.assertNotIn('quantis', av['speedtest_down_mbps'])
    self.assertIn('media', av['atende_completo'])
    self.assertIn('media', av['atende_throughput'])

  def test_promocao_em_latencia_usa_quantis(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', alvo='latency_ms', base='v1')
    p = r['promocao']
    self.assertIn('intervalo', p['delta_pinball'])
    self.assertNotIn('delta_mae', p)
    self.assertGreaterEqual(p['cobertura'], 0.0)
    self.assertIn(p['veredito']['resultado'], {'melhor', 'empate', 'pior'})

  def test_promocao_em_download_nao_muda(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn('delta_mae', r['promocao'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -8`
Expected: falhas com `KeyError: 'quantis'` e `KeyError: 'delta_pinball'`.

- [ ] **Step 3: Versão da régua**

Em `src/ml/core/avaliacao.py`, troque:

```python
VERSAO_REGUA = '2026-10-05.1'
```

por:

```python
VERSAO_REGUA = '2026-10-05.2'
```

- [ ] **Step 4: API**

Em `src/ml/studio/api.py`:

1. Acrescente aos imports de `ml.core`:

```python
from ml.core import quantis as core_quantis
```

2. Troque a função `_promocao` inteira por:

```python
def _presentes(c, lista):
  vazadas = studio_features.vazadas_do_conjunto(c)
  return [f for f in lista if f in c.df.columns and f not in vazadas], vazadas


def _prever_pontual(c, lista):
  presentes, vazadas = _presentes(c, lista)
  return core_avaliacao.prever_fora_do_fold(c.df, presentes, c.alvo, vazadas)


def _prever_quantis(c, lista):
  presentes, vazadas = _presentes(c, lista)
  return core_quantis.prever_quantis_fora_do_fold(c.df, presentes, c.alvo, vazadas)


def _promocao(ds: str, ambiente: str, alvo: str, feats: list, feats_base: list, conj) -> dict:
  """Veredito de promoção da régua contra a versão base.

  Latência e jitter: Δ pinball do p90 e cobertura da nova versão. Download e upload:
  Δ MAE e Δ "atende em throughput".
  """
  if alvo in core_quantis.ALVOS_QUANTILICOS:
    nova = _prever_quantis(conj, feats)
    d_pinball = core_quantis.delta_pinball(nova, _prever_quantis(conj, feats_base))
    cobertura = round(core_quantis.cobertura(nova['y'], nova['q90']), 4)
    return {'delta_pinball': d_pinball, 'cobertura': cobertura,
            'veredito': core_quantis.veredito_quantis(d_pinball, cobertura),
            'versao_regua': core_avaliacao.VERSAO_REGUA}
  d_mae = core_avaliacao.delta_mae(_prever_pontual(conj, feats), _prever_pontual(conj, feats_base))
  d_atende = None
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    d_atende = core_avaliacao.delta_atende(_prever_pontual(dn, feats), _prever_pontual(up, feats),
                                           _prever_pontual(dn, feats_base), _prever_pontual(up, feats_base),
                                           core_aplicacoes.carregar())
  return {'delta_mae': d_mae, 'delta_atende': d_atende,
          'veredito': core_avaliacao.veredito_promocao(d_mae, d_atende),
          'versao_regua': core_avaliacao.VERSAO_REGUA}
```

3. Troque `avaliacao_completa` inteira por:

```python
def avaliacao_completa(ds: str, ambiente: str, features: list) -> dict:
  """Avaliação dos quatro alvos, de "atende em throughput" e de "atende completo", guardada junto da versão.

  Latência e jitter levam também o resumo quantílico (p50 e p90).
  """
  saida, previsoes, quantis = {}, {}, {}
  aplicacoes = core_aplicacoes.carregar()
  for alvo in studio_features.TARGETS:
    conj, _ = _conjunto(ds, alvo, ambiente)
    resumo, previsoes[alvo] = core_avaliacao.avaliar(conj, features, studio_features.vazadas_do_conjunto(conj),
                                                     com_previsoes=True)
    saida[alvo] = dict(resumo, datasets=conj.datasets, ambiente=_ambiente(ambiente) or 'todos',
                       versao_tabela=core_features.versao_tabela(),
                       versao_catalogo=core_features.CATALOGO_VERSAO)
    if alvo in core_quantis.ALVOS_QUANTILICOS:
      quantis[alvo] = _prever_quantis(conj, features)
      saida[alvo]['quantis'] = core_quantis.resumir_quantis(quantis[alvo], resumo['n'])
  saida['atende_throughput'] = core_avaliacao.atende(previsoes['speedtest_down_mbps'],
                                                     previsoes['speedtest_up_mbps'], aplicacoes)
  saida['atende_completo'] = core_quantis.atende_completo(previsoes['speedtest_down_mbps'],
                                                          previsoes['speedtest_up_mbps'],
                                                          quantis['latency_ms'], quantis['jitter_ms'], aplicacoes)
  return saida
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 7: Interface do Studio

**Files:**
- Modify: `src/ml/studio/static/modelos.js` (`cardVersoes`)
- Modify: `src/ml/studio/static/assistente.js` (`cartaoVeredito`)

- [ ] **Step 1: `modelos.js`, versões salvas**

Em `cardVersoes`:

1. Logo depois de `const u = UNIDADE[st.alvo];`, acrescente:

```js
    // Latência e jitter são faixas (p50–p90): a tabela mostra cobertura e pinball do p90.
    const quantil = st.alvo === 'latency_ms' || st.alvo === 'jitter_ms';
    const faixa = (iv, casas) => (iv ? ` <em>(${num(iv[0], casas)} a ${num(iv[1], casas)})</em>` : '');
```

2. Troque as duas células:

```js
        <td class="num">${nota ? num(nota.pooled, 3) : '–'}${marca}</td>
        <td class="num">${nota ? num(nota.mae, 1) + ' ' + u : '–'}</td>
```

por:

```js
        <td class="num">${quantil ? (nota && nota.quantis ? num(nota.quantis.cobertura.q90, 2) : '–')
          : (nota ? num(nota.pooled, 3) : '–')}${marca}</td>
        <td class="num">${quantil ? (nota && nota.quantis ? num(nota.quantis.pinball.q90, 1) + ' ' + u : '–')
          : (nota ? num(nota.mae, 1) + ' ' + u : '–')}</td>
        <td class="num">${(() => {
          const ac = (v.avaliacao || {}).atende_completo;
          return ac && ac.media != null ? num(ac.media, 3) + faixa(ac.intervalo, 3) : '–';
        })()}</td>
```

3. Troque o cabeçalho:

```js
        <th class="num">R² pooled</th><th class="num">MAE</th><th>Avaliação</th><th></th></tr></thead>
```

por:

```js
        <th class="num">${quantil ? 'Cobertura p90' : 'R² pooled'}</th><th class="num">${quantil ? 'Pinball p90' : 'MAE'}</th>
        <th class="num" title="download, upload, latência (p90) e jitter (p90) contra os limiares de cada aplicação">Atende completo</th>
        <th>Avaliação</th><th></th></tr></thead>
```

- [ ] **Step 2: `assistente.js`, cartão de promoção**

Em `cartaoVeredito`, troque o bloco `const promocao = p ? ... : '';` inteiro por:

```js
    const detalhePromocao = !p ? ''
      : p.delta_pinball
        ? `Δ pinball p90 ${num(p.delta_pinball.valor, 2)} ${u} ${faixa(p.delta_pinball.intervalo, 2)} · cobertura p90 ${num(p.cobertura, 2)}`
        : `Δ MAE ${num(p.delta_mae.valor, 1)} ${u} ${faixa(p.delta_mae.intervalo, 1)}${p.delta_atende
          ? ` · Δ atende ${num(p.delta_atende.valor, 3)} ${faixa(p.delta_atende.intervalo, 3)}` : ''}`;
    const promocao = p ? `<div class="veredito ${p.veredito.resultado}" style="margin-top:10px">
        <svg class="icon"><use href="#${VEREDITO[p.veredito.resultado][1]}"/></svg>
        <div><b>Régua de promoção: ${VEREDITO[p.veredito.resultado][0]}</b>
          <div class="gate-msg">${esc(p.veredito.motivo)}</div>
          <div class="gate-msg">${detalhePromocao}</div></div></div>` : '';
```

- [ ] **Step 3: Conferir a sintaxe**

Run: `for f in modelos assistente; do node --check src/ml/studio/static/$f.js && echo "ok $f"; done`
Expected: `ok modelos` e `ok assistente`

- [ ] **Step 4: Conferir os dados que a interface lê**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys; sys.path.insert(0, 'src')
from ml.studio import api
reg = api.modelos_listar()
print('versao_regua', reg['versao_regua'])
for v in reg['versoes']:
  av = v.get('avaliacao') or {}
  print(v['nome'], 'quantis em latency_ms:', 'quantis' in (av.get('latency_ms') or {}),
        'atende_completo:', 'atende_completo' in av)
EOF
```

Expected: `versao_regua 2026-10-05.2` e, para as versões existentes, `False` nas duas colunas (as avaliações guardadas são de antes; a interface mostra "–" e "desatualizada").

---

### Task 8: `regression_mlflow.py` com ramo quantílico

**Files:**
- Modify: `src/ml/regression_mlflow.py`

- [ ] **Step 1: Acrescentar o ramo**

Em `src/ml/regression_mlflow.py`:

1. Na docstring do topo, acrescente ao fim do parágrafo: `Para ALVO=latency_ms ou jitter_ms, treina os dois modelos quantílicos (p50 e p90) em vez da varredura de árvores.`

2. Acrescente aos imports:

```python
import numpy as np
```

(junto de `import os`/`import sys`, no grupo da biblioteca padrão e terceiros conforme o arquivo) e:

```python
from ml.core import quantis as core_quantis
```

3. Antes de `def main():`, acrescente:

```python
def treinar_quantis(conj, features, vazadas, params: dict) -> None:
  """Latência e jitter: p50 e p90 em escala log, medidos pela régua quantílica."""
  with mlflow.start_run(run_name=f"{params['modelo_versao']}-quantis-{ALVO}"):
    mlflow.log_params(dict(params, quantis=','.join(str(q) for q in core_quantis.QUANTIS)))
    prev = core_quantis.prever_quantis_fora_do_fold(conj.df, features, ALVO, vazadas)
    resumo = core_quantis.resumir_quantis(prev, len(features))
    for q in core_quantis.QUANTIS:
      c = core_quantis.coluna(q)
      mlflow.log_metric(f'pinball_{c}', resumo['pinball'][c])
      mlflow.log_metric(f'cobertura_{c}', resumo['cobertura'][c])
      for site, metricas in resumo['por_local'].items():
        mlflow.log_metric(f'pinball_{c}_{site}', metricas['pinball'][c])
        mlflow.log_metric(f'cobertura_{c}_{site}', metricas['cobertura'][c])
    for chave, intervalo in resumo['intervalos'].items():
      if intervalo:
        mlflow.log_metric(f'{chave}_lo90', intervalo[0])
        mlflow.log_metric(f'{chave}_hi90', intervalo[1])
    mlflow.log_metric('mediana_mae', resumo['mediana_mae'])
    mlflow.log_metric('cruzados', resumo['cruzados'])
    X = core_features.matriz(conj.df, features)
    y_log = np.log1p(conj.df[ALVO].astype(float).clip(lower=0))
    for q in core_quantis.QUANTIS:
      modelo = core_quantis.modelo_quantil(q).fit(X, y_log)
      mlflow.sklearn.log_model(sk_model=modelo, name=f'quantil_{core_quantis.coluna(q)}',
                               serialization_format='skops')
    print(f"Quantis {ALVO}: cobertura {resumo['cobertura']} (90%: "
          f"{resumo['intervalos'].get('cobertura_q90')}), pinball {resumo['pinball']}, "
          f"MAE da mediana {resumo['mediana_mae']}, cruzados {resumo['cruzados']}")
    for site, metricas in resumo['por_local'].items():
      print(f'  {site}: {metricas}')
```

4. Em `main`, troque o bloco que vai de `impressoes = {...}` até o fim da função pelo código abaixo. Os parâmetros comuns saem do laço para um `params` só, e o ramo quantílico retorna antes da varredura:

```python
  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  params = {
    'modelo_versao': nome_modelo, 'alvo': ALVO,
    'datasets': ','.join(conj.datasets),
    'fingerprints': ','.join(impressoes[i] for i in conj.datasets),
    'versao_tabela': core_features.versao_tabela(),
    'versao_catalogo': core_features.CATALOGO_VERSAO,
    'versao_regua': core_avaliacao.VERSAO_REGUA,
    'features': ','.join(features),
    'removidas_por_vazamento': ','.join(removidas),
  }
  mlflow.set_experiment('MLflow Wifi Regressions')
  if ALVO in core_quantis.ALVOS_QUANTILICOS:
    treinar_quantis(conj, features, vazadas, params)
    return

  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  y_final = conj.df.loc[treino, ALVO].astype(float)
  for config in CONFIGS:
    with mlflow.start_run(run_name=f"{nome_modelo}-{config['model_type']}-{config['max_depth']}"):
      mlflow.log_params(dict(params, **config))
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config))
      resumo = core_avaliacao.resumir(prev, len(features))
      registrar_metricas(resumo)
      final = montar(config).fit(X_final, y_final)
      # O imputer guarda um numpy.dtype, que o skops não confia por padrão.
      mlflow.sklearn.log_model(sk_model=final, name=config['model_type'], serialization_format='skops',
                               skops_trusted_types=['numpy.dtype'])
      print('-' * 61)
      print(f"{config['model_type']} {config}: R² pooled {resumo['pooled']} "
            f"(90%: {resumo['intervalos'].get('pooled')}), MAE {resumo['mae']}, MAE log {resumo['mae_log']}")
      print(f"  por prédio: {resumo['por_local']}")
```

- [ ] **Step 2: Conferir import**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); import ml.regression_mlflow as m; print(m.ALVO, callable(m.treinar_quantis))"`
Expected: `speedtest_down_mbps True`

- [ ] **Step 3: Rodar de verdade, latência**

Run: `ALVO=latency_ms MODELO=v3-tr069 python3 src/ml/regression_mlflow.py 2>&1 | grep -v Warning | tail -12`
Expected: avisos da carga, `Modelo: v3-tr069 — 12 features, alvo latency_ms ...`, a linha `Quantis latency_ms: cobertura {...}` e uma linha por prédio (`casa-marcelo`, `coworking`, `hotmilk`, `residencia`). Sem traceback. Leva menos de 1 minuto.

- [ ] **Step 4: Rodar a suíte**

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 9: Experimento e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (entrada nova no topo)

- [ ] **Step 1: Medir `v2-tr069` e `v3-tr069` em latência e jitter**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M
from ml.studio import api
ds = ','.join(C.ids_padrao(C.descobertos()))
reg = M.carregar()
for nome in ('v2-tr069', 'v3-tr069'):
  av = api.avaliacao_completa(ds, '', reg['versoes'][nome]['features'])
  for alvo in ('latency_ms', 'jitter_ms'):
    q = av[alvo]['quantis']
    print(nome, alvo, 'cobertura', q['cobertura'], 'pinball', q['pinball'],
          'IC cob q90', q['intervalos'].get('cobertura_q90'), 'MAE mediana', q['mediana_mae'],
          'MAE RF', av[alvo]['mae'], 'cruzados', q['cruzados'])
    print('   por prédio', json.dumps({s: m['cobertura'] for s, m in q['por_local'].items()}))
  print(nome, 'atende_completo', json.dumps(av['atende_completo'], ensure_ascii=False))
  print(nome, 'atende_throughput', av['atende_throughput']['media'], av['atende_throughput']['intervalo'])
EOF
```

Expected: para cada versão, duas linhas por alvo e as linhas de "atende". Anote todos os números para o CHANGELOG.

- [ ] **Step 2: Veredito quantílico de `v3-tr069` contra `v2-tr069`**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M
from ml.studio import api
api._modelos_cache.clear()
ds = ','.join(C.ids_padrao(C.descobertos()))
v3 = M.carregar()['versoes']['v3-tr069']['features']
for alvo in ('latency_ms', 'jitter_ms'):
  r = api.modelos_avaliar(features=','.join(v3), ds=ds, alvo=alvo, base='v2-tr069')
  print(alvo, json.dumps(r['promocao'], ensure_ascii=False))
EOF
```

Expected: um `promocao` por alvo, com `delta_pinball`, `cobertura` e `veredito`.

- [ ] **Step 3: Aplicar o critério da CQR (spec, seção 7.3)**

Com as coberturas do p90 por prédio do Step 1 (`v3-tr069`): se alguma ficar fora de 0,80 a 0,95, a conclusão é "recomendar CQR"; se todas ficarem dentro, "CQR não entra". Escreva a conclusão e os prédios que saíram da faixa.

- [ ] **Step 4: Escrever a entrada do CHANGELOG**

No topo de `CHANGELOG.md`, antes da entrada "Régua única, carga canônica e concorrência", siga o estilo das entradas existentes (título, Data, "Por quê", "Mudanças", "Efeito medido", "Fica para depois"). Use **só** números impressos nos Steps 1 e 2, sem inventar nada:

- **Por quê:** R² negativo em latência e jitter; caudas (p99 de 350 ms e 205 ms); "atende" só cobria throughput.
- **Mudanças:**
  - `core/quantis.py` (p50 e p90 em escala log por gradient boosting quantílico; pinball, cobertura, intervalos, `delta_pinball`, `veredito_quantis`, "atende completo");
  - régua `2026-10-05.2`;
  - Studio mostrando cobertura e pinball do p90 em latência e jitter, e a coluna "Atende completo";
  - promoção quantílica em latência e jitter;
  - `regression_mlflow.py` com `ALVO=latency_ms` ou `jitter_ms`.
- **Efeito medido:** uma tabela com `v2-tr069` e `v3-tr069` × latência e jitter, com as colunas cobertura p50, cobertura p90 (com intervalo), pinball p90, MAE da mediana, MAE da RF e cruzados. Depois, uma linha por prédio com a cobertura do p90 da `v3-tr069`, o "atende completo" das duas versões (média e intervalo) e os vereditos de promoção.
- **Conclusão sobre a CQR,** do Step 3.
- **Para o responsável pela coleta:** confirmar quando a latência e o jitter são medidos (ociosos ou sob carga), com referência à spec, seção 8.
- **Fica para depois:** a frente C (spec anterior, seção 10) e, se o Step 3 recomendar, a CQR.

- [ ] **Step 5: Conferir**

Run: `sed -n 1,80p CHANGELOG.md | grep -n "<\|TBD\|TODO"`
Expected: nenhuma linha.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`
