# Fator de decisão do "atende" — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A régua passa a decidir "atende" em throughput com um fator por aplicação (`previsão ≥ k × limiar`), escolhido por LOGO interno nos prédios de treino; a promoção usa esse "atende ajustado", e o bruto continua visível.

**Architecture:** Um módulo novo, `src/ml/core/limiar.py`, escolhe o fator (`escolher_fator`), produz as decisões fora do prédio com o fator aninhado (`decisoes_atende`), resume, compara versões e calcula o fator de produção. Ele reaproveita `prever_fora_do_fold`, `_juntar`, `_atende_em`, `_resumo_atende` e o bootstrap de `avaliacao.py`. O Studio (`api.py`, `assistente.js`) e `classification_benchmark.py` passam a usá-lo.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn. Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-08-limiar-atende-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add` nem `git stash`.** O usuário faz commit à mão.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 403 tests`, `OK`.
- `tests/test_studio_assistente.py` só roda por `discover`: `python3 -m unittest discover -s tests -p "test_studio_assistente.py"`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último.
- Leia cada função antes de editá-la: os trechos "troque X por Y" citam o código atual pelo conteúdo.
- **Não rode nada em segundo plano que use todos os núcleos ao mesmo tempo que a suíte**: na rodada anterior, o `--tune` em paralelo deixou a suíte 12 vezes mais lenta.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/limiar.py` | Novo |
| `src/ml/core/avaliacao.py` | `VERSAO_REGUA = '2026-10-08.1'` |
| `src/ml/studio/api.py` | `avaliacao_completa` grava `atende_ajustado`; `_promocao` usa `delta_decisoes` |
| `src/ml/studio/static/assistente.js` | Rótulo "Δ atende (limiar ajustado)" |
| `src/ml/classification_benchmark.py` | Linha de referência "régua (limiar ajustado)" |
| `tests/test_limiar.py` | Novo |
| `tests/test_studio_assistente.py` | Testes da integração |
| `CHANGELOG.md` | Entrada nova no topo |

---

### Task 1: `escolher_fator`

**Files:**
- Create: `src/ml/core/limiar.py`
- Test: `tests/test_limiar.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_limiar.py`:

```python
import os
import sys
import unittest
from unittest import mock

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import limiar as L

LIM = {'dn': 5.0, 'up': 1.0, 'lat': 100, 'jit': 30}


def junta(y_dn, p_dn, y_up=None, p_up=None):
  n = len(y_dn)
  y_up = y_up if y_up is not None else [100.0] * n
  p_up = p_up if p_up is not None else [100.0] * n
  return pd.DataFrame({'_site': ['s'] * n, '_pos': [f'p{i}' for i in range(n)], 'y_dn': y_dn, 'p_dn': p_dn,
                       'y_up': y_up, 'p_up': p_up}, index=[f'a:{i}' for i in range(n)])


class TestEscolherFator(unittest.TestCase):
  def test_grade_vai_de_meio_a_dezesseis(self):
    self.assertEqual((L.FATORES[0], L.FATORES[-1]), (0.5, 16.0))
    self.assertIn(1.0, L.FATORES)

  def test_corrige_regressao_que_superestima(self):
    # Real: só as duas últimas atendem (>= 5). A regressão prevê 8 para quem entrega 1.
    # Com k = 1, tudo "atende" (acurácia balanceada 0,5). O primeiro fator da grade com
    # 5·k > 8 e 5·k <= 30 é 2^(0,75) = 1,6818: separa as classes por completo.
    j = junta([1.0, 1.0, 10.0, 10.0], [8.0, 8.0, 30.0, 30.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.6818)

  def test_empate_fica_com_o_mais_perto_de_um(self):
    j = junta([1.0, 10.0], [1.0, 10.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.0)

  def test_uma_classe_so_devolve_um(self):
    j = junta([10.0, 10.0], [1.0, 30.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.0)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_limiar -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'limiar'`

- [ ] **Step 3: Criar `src/ml/core/limiar.py`**

```python
"""Fator de decisão do "atende" em throughput, escolhido sem olhar o prédio de teste.

A regressão superestima os enlaces quase mortos: comparar a previsão de Mbps direto com o
limiar da aplicação diz "atende" demais. O fator k exige previsão >= k × limiar (download e
upload). Em cada fold da régua, k vem de um LOGO interno nos prédios de treino (a maior
acurácia balanceada do "atende"); em produção, de um LOGO com todos os prédios.
"""

import numpy as np
import pandas as pd

from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, _media_sem_nan,
                               _resumo_atende, prever_fora_do_fold, reamostras)

# Grade geométrica de 0,5 a 16, passo 2^(1/8): no protótipo, 8 ainda batia na borda.
FATORES = tuple(float(round(2 ** e, 4)) for e in np.arange(-1, 4.0001, 0.125))
ALVO_DN, ALVO_UP = 'speedtest_down_mbps', 'speedtest_up_mbps'


def _decide(j: pd.DataFrame, limiares: dict, k) -> np.ndarray:
  return (j['p_dn'].to_numpy(dtype=float) >= limiares['dn'] * k) & (j['p_up'].to_numpy(dtype=float) >= limiares['up'] * k)


def escolher_fator(j: pd.DataFrame, limiares: dict, fatores=FATORES) -> float:
  """Fator da grade com a maior acurácia balanceada de "atende"; empate fica com o mais perto de 1.

  `j` é a junção (avaliacao._juntar) das previsões fora do fold de download (dn) e upload (up).
  Com uma classe só no real, devolve 1.
  """
  real = _atende_em(j, limiares, 'y_dn', 'y_up')
  if real.all() or not real.any():
    return 1.0
  melhor, melhor_valor = 1.0, -1.0
  for k in sorted(fatores, key=lambda f: abs(np.log(f))):
    valor = _acuracia_balanceada(real, _decide(j, limiares, k))
    if valor > melhor_valor + 1e-12:
      melhor, melhor_valor = k, valor
  return float(melhor)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_limiar -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 2: Decisões, resumo, comparação e fator de produção

**Files:**
- Modify: `src/ml/core/limiar.py`
- Test: `tests/test_limiar.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_limiar.py`, acima do bloco `__main__`:

```python
ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}}, 'colunas': {a: {'classe': 'alvo'} for a in ALVOS}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']
APPS = {'Baixa': {'dn': 5.0, 'up': 1.0, 'lat': 100, 'jit': 30}, 'Alta': {'dn': 40.0, 'up': 10.0, 'lat': 100, 'jit': 30}}


def frame(n_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(0, 40, n)
  return pd.DataFrame({'local': np.repeat(LOCAIS, n_por_local), 'speedtest_down_mbps': 2 * snr + 0.1,
                       'speedtest_up_mbps': snr / 2 + 0.1, 'latency_ms': 10.0, 'jitter_ms': 2.0,
                       'router_snr': snr + rng.normal(0, 3, n)})


def conjuntos():
  f = frame()
  return (C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA, catalogo=()),
          C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA, catalogo=()))


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = A.ARVORES
    A.ARVORES = 15

  def tearDown(self):
    A.ARVORES = self._arvores


class TestDecisoes(Base):
  def test_fator_de_cada_predio_vem_so_dos_outros(self):
    dn, up = conjuntos()
    chamadas = []
    original = L.prever_fora_do_fold

    def espiao(df, *args, **kwargs):
      chamadas.append(sorted(df['_site'].unique()))
      return original(df, *args, **kwargs)

    with mock.patch.object(L, 'prever_fora_do_fold', side_effect=espiao):
      dec = L.decisoes_atende(dn, up, ['router_snr'], APPS)
    todos = ['coworking', 'hotmilk', 'residencia']
    internas = [c for c in chamadas if c != todos]
    self.assertEqual(len(internas), 2 * len(todos))
    for site in todos:
      self.assertEqual(sum(site not in c for c in internas), 2)
    # O fator do prédio é o que escolher_fator dá sobre o LOGO interno sem ele.
    sem = {a: c.df[c.df['_site'] != 'hotmilk'] for a, c in (('dn', dn), ('up', up))}
    interno = A._juntar(dn=A.prever_fora_do_fold(sem['dn'], ['router_snr'], dn.alvo, []),
                        up=A.prever_fora_do_fold(sem['up'], ['router_snr'], up.alvo, []))
    for app, lim in APPS.items():
      fatores = dec[app].groupby('_site')['fator'].first().to_dict()
      self.assertEqual(fatores['hotmilk'], L.escolher_fator(interno, lim))
      self.assertEqual(list(dec[app].columns), ['_linha', '_site', '_pos', 'real', 'previsto', 'fator'])

  def test_sem_ajuste_reproduz_o_atende_bruto(self):
    dn, up = conjuntos()
    dec = L.decisoes_atende(dn, up, ['router_snr'], APPS, ajustar=False)
    bruto = A.atende(A.prever_fora_do_fold(dn.df, ['router_snr'], dn.alvo, []),
                     A.prever_fora_do_fold(up.df, ['router_snr'], up.alvo, []), APPS)
    r = L.resumir_decisoes(dec)
    self.assertEqual(r['por_aplicacao'], bruto['por_aplicacao'])
    self.assertTrue(all(v == 1.0 for app in r['fatores'].values() for v in app.values()))

  def test_fatores_de_producao_dentro_da_grade(self):
    dn, up = conjuntos()
    fatores = L.fatores_producao(dn, up, ['router_snr'], APPS)
    self.assertEqual(set(fatores), set(APPS))
    self.assertTrue(all(k in L.FATORES for k in fatores.values()))


def decisao(real, previsto, fator=1.0):
  n = len(real)
  return pd.DataFrame({'_linha': [f'a:{i}' for i in range(n)], '_site': ['s1', 's1', 's2', 's2'][:n],
                       '_pos': ['p1', 'p2', 'p3', 'p4'][:n], 'real': real, 'previsto': previsto, 'fator': fator})


class TestResumoEDelta(unittest.TestCase):
  def test_resumo_tem_a_forma_do_atende_e_os_fatores(self):
    dec = {'X': decisao([True, False, True, False], [True, False, False, True], 2.0)}
    r = L.resumir_decisoes(dec)
    self.assertEqual(r['por_aplicacao'], {'X': 0.5})
    self.assertEqual(r['media'], 0.5)
    self.assertEqual(r['fatores'], {'X': {'s1': 2.0, 's2': 2.0}})
    self.assertEqual(r['n'], 4)

  def test_delta_da_nova_perfeita_contra_base_que_diz_sempre_atende(self):
    real = [True, False, True, False]
    nova = {'X': decisao(real, real)}
    base = {'X': decisao(real, [True, True, True, True])}
    d = L.delta_decisoes(nova, base)
    self.assertEqual(d['valor'], 0.5)
    self.assertTrue(d['ajustado'])

  def test_delta_sem_aplicacao_com_duas_classes_e_none(self):
    tudo = {'X': decisao([True] * 4, [True] * 4)}
    self.assertIsNone(L.delta_decisoes(tudo, tudo))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_limiar -v 2>&1 | tail -8`
Expected: erros `AttributeError: module 'ml.core.limiar' has no attribute 'decisoes_atende'` (e `resumir_decisoes`, `delta_decisoes`, `fatores_producao`).

- [ ] **Step 3: Implementar**

Ao fim de `src/ml/core/limiar.py`:

```python
def _vazadas(conj) -> list:
  return [c for c, k in conj.classes.items() if k is not None and k.vazamento]


def _prever(conj, features, denominador, df=None) -> pd.DataFrame:
  vazadas = _vazadas(conj)
  presentes = [f for f in features if f in conj.df.columns and f not in vazadas]
  return prever_fora_do_fold(conj.df if df is None else df, presentes, conj.alvo, vazadas,
                             denominador=denominador)


def _previsoes(conj_dn, conj_up, features, den_dn, den_up, sem_predio=None) -> pd.DataFrame:
  """Previsões fora do fold de download e upload, juntas por `_linha`; `sem_predio` tira um prédio antes."""
  df_dn = conj_dn.df if sem_predio is None else conj_dn.df[conj_dn.df['_site'] != sem_predio]
  df_up = conj_up.df if sem_predio is None else conj_up.df[conj_up.df['_site'] != sem_predio]
  return _juntar(dn=_prever(conj_dn, features, den_dn, df_dn), up=_prever(conj_up, features, den_up, df_up))


def decisoes_atende(conj_dn, conj_up, features, aplicacoes: dict, den_dn=None, den_up=None,
                    ajustar: bool = True) -> dict:
  """Decisão "atende" de cada linha e aplicação, com o prédio de teste fora do treino e da escolha do fator.

  Com `ajustar`, o fator de cada prédio de teste vem de escolher_fator sobre previsões fora do
  fold feitas só com os outros prédios (LOGO interno); com menos de 2 prédios de treino, ou sem
  `ajustar`, o fator é 1 (a régua de antes). Devolve
  {aplicação: DataFrame(_linha, _site, _pos, real, previsto, fator)}.
  """
  externo = _previsoes(conj_dn, conj_up, features, den_dn, den_up)
  sites = sorted(externo['_site'].unique())
  fatores = {app: {} for app in aplicacoes}
  for site in sites:
    if not ajustar or len(sites) < 3:
      for app in aplicacoes:
        fatores[app][site] = 1.0
      continue
    interno = _previsoes(conj_dn, conj_up, features, den_dn, den_up, sem_predio=site)
    for app, limiares in aplicacoes.items():
      fatores[app][site] = escolher_fator(interno, limiares)
  saida = {}
  for app, limiares in aplicacoes.items():
    k = externo['_site'].map(fatores[app]).to_numpy(dtype=float)
    saida[app] = pd.DataFrame({'_linha': externo.index.to_numpy(), '_site': externo['_site'].to_numpy(),
                               '_pos': externo['_pos'].to_numpy(),
                               'real': _atende_em(externo, limiares, 'y_dn', 'y_up'),
                               'previsto': _decide(externo, limiares, k), 'fator': k})
  return saida


def resumir_decisoes(decisoes: dict, amostras=None) -> dict:
  """A forma de avaliacao.atende (por aplicação, média, intervalo, n, avisos), mais os fatores por prédio."""
  if not decisoes:
    return {'por_aplicacao': {}, 'media': None, 'intervalo': None, 'n': 0, 'avisos': [], 'fatores': {}}
  primeiro = next(iter(decisoes.values()))
  j = primeiro.set_index('_linha')[['_site', '_pos']]
  classes = {app: (d['real'].to_numpy(dtype=bool), d['previsto'].to_numpy(dtype=bool)) for app, d in decisoes.items()}
  resumo = _resumo_atende(j, classes, amostras)
  resumo['fatores'] = {app: {s: float(g['fator'].iloc[0]) for s, g in sorted(d.groupby('_site'), key=lambda kv: kv[0])}
                       for app, d in decisoes.items()}
  return resumo


def delta_decisoes(nova: dict, base: dict, amostras=None):
  """Acurácia balanceada média do "atende" da nova versão menos a da base, nas mesmas linhas.

  None quando nenhuma aplicação tem as duas classes no real.
  """
  trios, j = [], None
  for app, d in nova.items():
    if app not in base:
      continue
    m = d.set_index('_linha')[['_site', '_pos', 'real', 'previsto']].join(
      base[app].set_index('_linha')[['previsto']].rename(columns={'previsto': 'base'}), how='inner')
    j = m if j is None else j
    real = m['real'].to_numpy(dtype=bool)
    if real.all() or not real.any():
      continue
    trios.append((real, m['previsto'].to_numpy(dtype=bool), m['base'].to_numpy(dtype=bool)))
  if not trios:
    return None

  def diferenca(idx):
    return (_media_sem_nan([_acuracia_balanceada(r[idx], n[idx]) for r, n, _ in trios])
            - _media_sem_nan([_acuracia_balanceada(r[idx], b[idx]) for r, _, b in trios]))

  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(diferenca(np.arange(len(j))), 4), 'intervalo': _intervalo([diferenca(i) for i in amostras]),
          'n': int(len(j)), 'ajustado': True}


def fatores_producao(conj_dn, conj_up, features, aplicacoes: dict, den_dn=None, den_up=None) -> dict:
  """{aplicação: fator} escolhido sobre as previsões fora do fold de todos os prédios (para produção)."""
  externo = _previsoes(conj_dn, conj_up, features, den_dn, den_up)
  return {app: escolher_fator(externo, limiares) for app, limiares in aplicacoes.items()}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_limiar -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 3: Régua, Studio e benchmark

**Files:**
- Modify: `src/ml/core/avaliacao.py` (`VERSAO_REGUA`)
- Modify: `src/ml/studio/api.py` (imports, `_promocao`, `avaliacao_completa`)
- Modify: `src/ml/studio/static/assistente.js` (rótulo)
- Modify: `src/ml/classification_benchmark.py` (linha de referência)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_assistente.py`, dentro da classe `TestRotasAssistente`:

```python
  def test_avaliacao_completa_traz_atende_ajustado(self):
    av = api.avaliacao_completa('a.csv', '', ['router_snr'])
    self.assertIn('media', av['atende_ajustado'])
    self.assertIn('fatores', av['atende_ajustado'])
    self.assertIn('fatores_producao', av['atende_ajustado'])
    self.assertIn('media', av['atende_throughput'])

  def test_promocao_em_download_usa_o_atende_ajustado(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    d = r['promocao']['delta_atende']
    if d is not None:
      self.assertTrue(d['ajustado'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -6`
Expected: `KeyError: 'atende_ajustado'` (e falha em `ajustado`, se o fixture tiver aplicação com as duas classes).

- [ ] **Step 3: Régua e API**

1. Em `src/ml/core/avaliacao.py`, troque `VERSAO_REGUA = '2026-10-07.1'` por `VERSAO_REGUA = '2026-10-08.1'`.

2. Em `src/ml/studio/api.py`, acrescente aos imports de `ml.core`:

```python
from ml.core import limiar as core_limiar
```

3. Em `_promocao`, troque o bloco:

```python
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    d_atende = core_avaliacao.delta_atende(_prever_pontual(dn, feats, den_nova), _prever_pontual(up, feats, den_nova),
                                           _prever_pontual(dn, feats_base, den_base),
                                           _prever_pontual(up, feats_base, den_base),
                                           core_aplicacoes.carregar())
```

por:

```python
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    aplicacoes = core_aplicacoes.carregar()
    den_nova, den_base = den_nova or {}, den_base or {}
    # "Atende" com o fator de decisão escolhido sem o prédio de teste (core/limiar.py).
    d_atende = core_limiar.delta_decisoes(
      core_limiar.decisoes_atende(dn, up, feats, aplicacoes, den_nova.get(dn.alvo), den_nova.get(up.alvo)),
      core_limiar.decisoes_atende(dn, up, feats_base, aplicacoes, den_base.get(dn.alvo), den_base.get(up.alvo)))
```

E, na docstring de `_promocao`, troque `Δ MAE e Δ "atende em throughput"` por `Δ MAE e Δ "atende em throughput" com o fator de decisão ajustado`.

4. Em `avaliacao_completa`, logo depois da atribuição de `saida['atende_throughput'] = ...`, acrescente:

```python
  conj_dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
  conj_up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
  den = denominador or {}
  decisoes = core_limiar.decisoes_atende(conj_dn, conj_up, features, aplicacoes,
                                         den.get(conj_dn.alvo), den.get(conj_up.alvo))
  saida['atende_ajustado'] = dict(core_limiar.resumir_decisoes(decisoes),
                                  fatores_producao=core_limiar.fatores_producao(
                                    conj_dn, conj_up, features, aplicacoes, den.get(conj_dn.alvo),
                                    den.get(conj_up.alvo)))
```

5. Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
   Expected: `OK`

- [ ] **Step 4: Rótulo no Assistente**

Em `src/ml/studio/static/assistente.js`, troque:

```js
            ? ` · Δ atende ${num(p.delta_atende.valor, 3)} ${faixa(p.delta_atende.intervalo, 3)}` : ''}`;
```

por:

```js
            ? ` · Δ atende${p.delta_atende.ajustado ? ' (limiar ajustado)' : ''} ${num(p.delta_atende.valor, 3)} ${faixa(p.delta_atende.intervalo, 3)}` : ''}`;
```

Run: `node --check src/ml/studio/static/assistente.js && echo ok`
Expected: `ok`

- [ ] **Step 5: Linha de referência no benchmark**

Em `src/ml/classification_benchmark.py`:

1. Acrescente aos imports de `ml.core`:

```python
from ml.core import limiar as core_limiar
```

2. Logo depois do bloco que valida `desconhecidas` (o `raise SystemExit(f'aplicações desconhecidas: ...')`), acrescente:

```python
  # Referência com o fator de decisão ajustado (core/limiar.py), uma vez para todas as aplicações.
  decisoes = core_limiar.decisoes_atende(conj_dn, conj_up, features, {a: aplicacoes[a] for a in pedidas_apps},
                                         core_modelos.denominador_de(registro, nome, ALVO_DN),
                                         core_modelos.denominador_de(registro, nome, ALVO_UP))
```

3. Troque a montagem de `linhas`:

```python
    linhas = [('régua (regressão)', core_classificacao.resumir_classe(
      core_classificacao.referencia_regua(prev_dn, prev_up, limiares)))]
```

por:

```python
    ajustada = decisoes[app].rename(columns={'real': 'y', 'previsto': 'yhat'})[['_linha', 'y', 'yhat', '_site', '_pos']]
    linhas = [('régua (regressão)', core_classificacao.resumir_classe(
                core_classificacao.referencia_regua(prev_dn, prev_up, limiares))),
              ('régua (limiar ajustado)', core_classificacao.resumir_classe(ajustada))]
```

4. Run: `python3 -c "import ast; ast.parse(open('src/ml/classification_benchmark.py').read()); print('ok')"`
   Expected: `ok`

- [ ] **Step 6: Suíte**

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 4: Experimento e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: "Atende" bruto contra ajustado e vereditos**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v "Warning\|validate_site\|warnings.warn"
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M, aplicacoes as AP, limiar as L
from ml.studio import api
reg = M.carregar(); apps = AP.carregar(); ds = ','.join(C.ids_padrao(C.descobertos()))
dn, up = C.carregar('speedtest_down_mbps'), C.carregar('speedtest_up_mbps')
for nome in ('v3-tr069', 'v4-tr069', 'v5-tr069'):
  feats = reg['versoes'][nome]['features']
  d_dn, d_up = M.denominador_de(reg, nome, dn.alvo), M.denominador_de(reg, nome, up.alvo)
  bruto = L.resumir_decisoes(L.decisoes_atende(dn, up, feats, apps, d_dn, d_up, ajustar=False))
  ajust = L.resumir_decisoes(L.decisoes_atende(dn, up, feats, apps, d_dn, d_up))
  prod = L.fatores_producao(dn, up, feats, apps, d_dn, d_up)
  print(nome, 'bruto', bruto['media'], bruto['intervalo'], bruto['por_aplicacao'])
  print(nome, 'ajustado', ajust['media'], ajust['intervalo'], ajust['por_aplicacao'])
  print(nome, 'fatores por prédio', json.dumps(ajust['fatores'], ensure_ascii=False))
  print(nome, 'fatores de produção', json.dumps(prod, ensure_ascii=False))
v3, v5 = reg['versoes']['v3-tr069'], reg['versoes']['v5-tr069']
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  conj, _ = api._conjunto(ds, alvo, '')
  r = api._promocao(ds, '', alvo, v5['features'], v3['features'], conj, v5.get('denominador'), v3.get('denominador'))
  print(alvo, 'promocao v5 contra v3', json.dumps(r, ensure_ascii=False))
EOF
```

Expected: para cada versão, as linhas bruto, ajustado e fatores; um veredito por alvo. Leva alguns minutos. Anote tudo.

- [ ] **Step 2: Benchmark com as duas referências**

Run: `timeout 900 python3 src/ml/classification_benchmark.py --modelo v5-tr069 2>&1 | grep -v "Warning\|validate_site\|warnings.warn" | tail -32`
Expected: por aplicação, as linhas "régua (regressão)" e "régua (limiar ajustado)" e os 4 classificadores. Anote.

- [ ] **Step 3: CHANGELOG**

No topo de `CHANGELOG.md`, no estilo das entradas existentes. Use só números impressos nos Steps 1 e 2 (e os da seção 2 da spec, citando-a):

- **Por quê:** a régua decidia "atende" comparando a previsão de Mbps direto com o limiar e errava nas aplicações de limiar baixo (régua 0,519 em Navegação contra classificadores até 0,81), porque a regressão superestima enlaces quase mortos.
- **Mudanças:** `core/limiar.py` (fator por aplicação, aninhado, grade de 0,5 a 16); régua `2026-10-08.1`; `atende_ajustado` (com `fatores` e `fatores_producao`) na avaliação das versões; promoção com o "atende ajustado"; rótulo no Assistente; linha "régua (limiar ajustado)" no benchmark. Registre também a validação do `--tune` desta rodada (spec, seção 2: o melhor classificador com busca) e a correção de layout da tabela de versões no Studio.
- **Efeito medido:** tabela bruto × ajustado por versão e aplicação, com intervalos; os fatores por prédio e de produção; os vereditos da `v5` contra a `v3`; as duas linhas de referência do benchmark ao lado do melhor classificador.
- **Ressalvas:** o fator corrige a decisão, não a previsão (MAE inalterado); em Streaming 4K o ajuste pode perder um pouco (spec, seção 2); a escolha usa só 3 prédios de treino por fold.

- [ ] **Step 4: Conferir**

Run: `sed -n 1,100p CHANGELOG.md | grep -n "<\|TBD\|TODO"`
Expected: nenhuma linha.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`
