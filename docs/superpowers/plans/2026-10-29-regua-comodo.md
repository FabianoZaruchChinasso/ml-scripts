# Régua por cômodo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma régua que dá nota às versões pela pergunta "quais cômodos de uma casa nova estão ruins?", com a verdade relativa à casa (bom / degradado / ruim), e um script que reavalia v1 a v5 e o piso.

**Architecture:** Funções puras em `src/ml/core/comodo.py`: verdade por posição (só linhas sozinhas no rádio, capacidade relativa à melhor posição do prédio, latência e jitter contra a norma), previsão das quatro grandezas pelas funções fora do fold que já existem, classe prevista com a referência da verdade, nota por posição. `src/ml/comodo_benchmark.py` orquestra e imprime. Studio, registro e as réguas de regressão e QoE não mudam.

**Tech Stack:** Python 3, pandas 2.3, scikit-learn 1.9, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-29-regua-comodo-design.md`.

---

## Regras do repositório que valem para todas as tarefas

- Indentação de 2 espaços, nomes e docstrings em português, como no resto de `src/ml/core/`.
- Testes com `unittest`, da raiz do repositório: `venv/bin/python -m unittest tests/test_comodo.py -v`. Não há pytest no venv.
- **Não rodar `git commit`, `git add` nem `git push`.** O usuário commita à mão. O passo "Commit" de cada tarefa é: parar, listar os arquivos e sugerir a mensagem (sem linha `Co-Authored-By`).
- Não mexer em `classification_benchmark.py`, `regression_benchmark.py`, `compare_protocols.py` (benchmarks congelados do Fabiano), nem em `core/avaliacao.py`, `core/quantis.py`, `core/qoe.py`, `core/percepcao.py`, `core/modelos.json`, Studio.

## Estrutura de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/core/comodo.py` | criar | verdade, classificação, previsão, métricas |
| `tests/test_comodo.py` | criar | testes das funções, sem a base real |
| `src/ml/comodo_benchmark.py` | criar | reavaliação das versões e do piso, relatório |
| `CHANGELOG.md` | modificar (topo) | seção nova com os números medidos |

---

### Task 0: Pré-requisito

- [ ] **Step 1: Conferir que `core/percepcao.py` está no git**

Run: `git ls-files src/ml/core/percepcao.py src/ml/core/percepcao.json`
Expected: as duas linhas impressas. Se alguma faltar, PARAR e pedir ao usuário que commite os arquivos do rótulo de percepção (spec `2026-10-29-rotulo-percepcao-design.md`) antes de seguir: `comodo.py` importa funções de `percepcao.py`.

---

### Task 1: Verdade de referência e classificação

**Files:**
- Create: `src/ml/core/comodo.py`
- Create: `tests/test_comodo.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_comodo.py`:

```python
import copy
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import comodo as C

# Mesmos valores de latência e jitter do perfil de norma (core/aplicacoes_norma.json).
LIM = {'Navegação': {'dn': 2, 'up': 0.5, 'lat': 800, 'jit': 100},
       'Chamada de vídeo': {'dn': 3.0, 'up': 3.8, 'lat': 200, 'jit': 50},
       'Streaming 4K': {'dn': 15, 'up': 0, 'lat': 500, 'jit': 100},
       'Jogo em nuvem': {'dn': 15, 'up': 1, 'lat': 80, 'jit': 10}}
REF = pd.DataFrame({'dn': [100.0], 'up': [100.0]}, index=pd.Index(['s1'], name='_site'))


def linhas(pos, n, dn, up, lat=10.0, jit=2.0, conc=1.0, site='s1'):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, C.DN: [float(dn)] * n, C.UP: [float(up)] * n,
                       C.LAT: [lat] * n, C.JIT: [jit] * n, 'concorrentes_mesmo_radio': [conc] * n})


def juntas(*partes):
  return pd.concat(partes, ignore_index=True)


def est(dn, up=100.0, lat=10.0, jit=2.0, site='s1'):
  """Estatísticas de uma posição só, no formato de C.estatisticas."""
  return pd.DataFrame({'_site': [site], 'n': [10], 'dn': [float(dn)], 'up': [float(up)], 'lat': [lat],
                       'jit': [jit]}, index=pd.Index(['p'], name='_pos'))


def classe(dn, up=100.0, lat=10.0, jit=2.0, lim=LIM):
  return C.classificar(est(dn, up, lat, jit), REF, lim)['classe'].iloc[0]


class TestVerdade(unittest.TestCase):
  def test_so_linhas_sozinhas(self):
    df = juntas(linhas('a', 10, 100, 100), linhas('a', 10, 1, 1, conc=2.0), linhas('a', 5, 1, 1, conc=np.nan),
                linhas('b', 10, 50, 50))
    tab, ref = C.verdade(df, LIM)
    self.assertEqual(ref.loc['s1', 'dn'], 100.0)
    self.assertEqual(tab.loc['a', 'classe'], 'bom')
    self.assertAlmostEqual(tab.loc['b', 'razao'], 0.5)
    self.assertEqual(tab.loc['b', 'classe'], 'degradado')

  def test_referencia_ignora_posicao_com_poucas_linhas(self):
    tab, ref = C.verdade(juntas(linhas('a', 10, 100, 100), linhas('b', 9, 400, 400)), LIM)
    self.assertEqual(ref.loc['s1', 'dn'], 100.0)
    self.assertAlmostEqual(tab.loc['b', 'razao'], 4.0)

  def test_predio_sem_referencia_levanta(self):
    with self.assertRaisesRegex(ValueError, 's1'):
      C.verdade(linhas('a', 9, 100, 100), LIM)

  def test_razao_e_o_pior_entre_download_e_upload(self):
    tab, _ = C.verdade(juntas(linhas('a', 10, 100, 100), linhas('b', 10, 100, 20)), LIM)
    self.assertAlmostEqual(tab.loc['b', 'razao'], 0.2)
    self.assertEqual(tab.loc['b', 'classe'], 'ruim')


class TestClassificar(unittest.TestCase):
  def test_cortes_de_capacidade(self):
    self.assertEqual([classe(25), classe(24.99), classe(75), classe(74.99), classe(100)],
                     ['degradado', 'ruim', 'bom', 'degradado', 'bom'])

  def test_falha_em_navegacao_e_ruim(self):
    self.assertEqual(classe(100, lat=900), 'ruim')
    self.assertEqual(classe(100, jit=101), 'ruim')

  def test_falha_em_chamada_e_no_maximo_degradado(self):
    self.assertEqual(classe(100, jit=60), 'degradado')
    self.assertEqual(classe(50, jit=60), 'degradado')
    self.assertEqual(classe(100, lat=250), 'degradado')

  def test_apto_para_jogo_nao_muda_a_classe(self):
    t = C.classificar(est(100, jit=20), REF, LIM)
    self.assertEqual(t['classe'].iloc[0], 'bom')
    self.assertFalse(bool(t['apto_jogo'].iloc[0]))
    self.assertTrue(bool(C.classificar(est(100, lat=50, jit=5), REF, LIM)['apto_jogo'].iloc[0]))

  def test_limiares_vem_do_perfil(self):
    lim = copy.deepcopy(LIM)
    lim['Navegação']['jit'] = 5
    self.assertEqual(classe(100, jit=6, lim=lim), 'ruim')

  def test_predio_sem_referencia_levanta(self):
    with self.assertRaisesRegex(ValueError, 's2'):
      C.classificar(est(100, site='s2'), REF, LIM)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: erro de import (`No module named 'ml.core.comodo'`).

- [ ] **Step 3: Implementar**

Criar `src/ml/core/comodo.py`:

```python
"""Régua por cômodo: a experiência de cada posição em relação ao resto da casa.

Verdade: por posição, só com as linhas em que o cliente está sozinho no rádio, a capacidade
(mediana de download e upload) como fração da melhor posição do prédio (V0 provisório) e a
interatividade (p90 de latência e jitter) contra o perfil de norma, em bom / degradado / ruim.
Previsão: as grandezas físicas fora do fold (régua de regressão e p90 com CQR), classificadas
com a mesma referência. Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.
"""

import numpy as np
import pandas as pd

# Muda quando cortes, referência, filtro de linhas ou regras mudam.
VERSAO_COMODO = '2026-10-29.1'
CLASSES = ('bom', 'degradado', 'ruim')
# Fração da capacidade da casa: abaixo de CORTE_RUIM é ruim, abaixo de CORTE_BOM é degradado.
CORTE_RUIM = 0.25
CORTE_BOM = 0.75
# Posição com menos linhas sozinha no rádio não define a referência da casa.
MIN_LINHAS_REFERENCIA = 10
NAVEGACAO, CHAMADA, JOGO = 'Navegação', 'Chamada de vídeo', 'Jogo em nuvem'
DN, UP, LAT, JIT = 'speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms'


def sozinhas(df: pd.DataFrame) -> pd.DataFrame:
  """Linhas com o cliente sozinho no rádio (`concorrentes_mesmo_radio` conta a própria linha)."""
  return df[df['concorrentes_mesmo_radio'] == 1]


def estatisticas(df: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição (índice `_pos`): `_site`, `n`, medianas de download e upload, p90 de latência e jitter."""
  g = df.groupby('_pos')
  return pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g[DN].median(), 'up': g[UP].median(),
                       'lat': g[LAT].quantile(0.9), 'jit': g[JIT].quantile(0.9)})


def referencia(est: pd.DataFrame) -> pd.DataFrame:
  """V0 provisório por prédio: maior mediana de download e de upload entre posições com MIN_LINHAS_REFERENCIA linhas."""
  ref = est[est['n'] >= MIN_LINHAS_REFERENCIA].groupby('_site')[['dn', 'up']].max()
  faltam = sorted(set(est['_site']) - set(ref.index))
  if faltam:
    raise ValueError(f'prédios sem posição com {MIN_LINHAS_REFERENCIA} linhas sozinhas no rádio: {faltam}')
  return ref


def _falha(est: pd.DataFrame, lim: dict) -> pd.Series:
  return (est['lat'] > lim['lat']) | (est['jit'] > lim['jit'])


def classificar(est: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Razão de capacidade, classe e "apto para jogo" de cada posição de `est`, com a referência `ref`.

  `limiares`: {aplicação: {'lat', 'jit', ...}}, como aplicacoes.carregar_perfil devolve. Ruim:
  razão abaixo de CORTE_RUIM ou falha em Navegação. Degradado: razão abaixo de CORTE_BOM ou falha
  em Chamada de vídeo (nunca ruim só por Chamada). Jogo em nuvem não entra na classe.
  """
  faltam = sorted(set(est['_site']) - set(ref.index))
  if faltam:
    raise ValueError(f'sem referência da casa para os prédios {faltam}')
  razao = np.minimum(est['dn'] / est['_site'].map(ref['dn']), est['up'] / est['_site'].map(ref['up']))
  ruim = (razao < CORTE_RUIM) | _falha(est, limiares[NAVEGACAO])
  degradado = (razao < CORTE_BOM) | _falha(est, limiares[CHAMADA])
  classe = np.where(ruim, 'ruim', np.where(degradado, 'degradado', 'bom'))
  return pd.DataFrame({'_site': est['_site'], 'razao': razao, 'classe': classe,
                       'apto_jogo': ~_falha(est, limiares[JOGO])}, index=est.index)


def verdade(df: pd.DataFrame, limiares: dict) -> tuple:
  """(classe de cada posição, referência por prédio), só com as linhas sozinhas no rádio."""
  est = estatisticas(sozinhas(df))
  ref = referencia(est)
  return classificar(est, ref, limiares), ref
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: 10 testes OK.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/comodo.py`, `tests/test_comodo.py`.
Mensagem sugerida: `feat(comodo): verdade por cômodo relativa à casa`

---

### Task 2: Previsão das quatro grandezas e classe prevista

**Files:**
- Modify: `src/ml/core/comodo.py`
- Modify: `tests/test_comodo.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_comodo.py`, acrescentar `import types` aos imports (entre `import sys` e `import unittest`), e antes do bloco `if __name__ == '__main__':`:

```python
def conjs_sinteticos():
  """3 prédios, 2 posições, 15 linhas cada; uma feature `x` que move os quatro alvos."""
  rng = np.random.default_rng(0)
  partes = []
  for s in ('s1', 's2', 's3'):
    for p in ('a', 'b'):
      x = rng.uniform(0, 1, 15)
      partes.append(pd.DataFrame({'_site': s, '_pos': f'{s}-{p}', 'x': x, C.DN: 10 + 90 * x, C.UP: 5 + 50 * x,
                                  C.LAT: 50 - 30 * x, C.JIT: 10 - 5 * x}))
  df = pd.concat(partes, ignore_index=True)
  df['_linha'] = [f'd:{i}' for i in range(len(df))]
  return {a: types.SimpleNamespace(df=df) for a in (C.DN, C.UP, C.LAT, C.JIT)}, df


class TestPrevisao(unittest.TestCase):
  def test_classe_prevista_usa_a_referencia_dada_e_a_mediana_dos_p90(self):
    prev = pd.DataFrame({'_pos': ['a'] * 3, '_site': ['s1'] * 3, 'dn': [50.0] * 3, 'up': [50.0] * 3,
                         'lat': [10.0, 10.0, 300.0], 'jit': [2.0] * 3})
    t = C.classe_prevista(prev, REF, LIM)
    # Com a referência das próprias previsões a razão seria 1,0; com a da verdade (100) é 0,5.
    self.assertAlmostEqual(t.loc['a', 'razao'], 0.5)
    self.assertEqual(t.loc['a', 'classe'], 'degradado')
    cheio = prev.assign(dn=100.0, up=100.0)
    # Mediana dos p90 previstos (10), não o maior (300): Chamada não falha.
    self.assertEqual(C.classe_prevista(cheio, REF, LIM).loc['a', 'classe'], 'bom')

  def test_prever_casa_os_quatro_alvos_por_linha(self):
    conjs, df = conjs_sinteticos()
    conjs[C.LAT] = types.SimpleNamespace(df=df.iloc[1:])
    prev = C.prever(conjs, ['x'], {a: [] for a in conjs})
    self.assertTrue({'_linha', '_site', '_pos', 'dn', 'up', 'lat', 'jit'} <= set(prev.columns))
    self.assertNotIn('d:0', set(prev['_linha']))
    self.assertEqual(len(prev), len(df) - 1)
    por_linha = df.set_index('_linha')['_pos']
    self.assertTrue((prev['_pos'].to_numpy() == por_linha.loc[prev['_linha']].to_numpy()).all())
    self.assertTrue((prev[['dn', 'up', 'lat', 'jit']] >= 0).all().all())

  def test_prever_sem_feature_utilizavel_levanta(self):
    conjs, _ = conjs_sinteticos()
    vazadas = {a: [] for a in conjs}
    vazadas[C.DN] = ['x']
    with self.assertRaisesRegex(ValueError, C.DN):
      C.prever(conjs, ['x'], vazadas)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: `AttributeError: module 'ml.core.comodo' has no attribute 'classe_prevista'` (e `prever`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/comodo.py`, acrescentar depois de `import pandas as pd`:

```python

from ml.core import avaliacao, quantis
```

E no fim do arquivo:

```python
def prever(conjs: dict, features, vazadas: dict, denominador: dict = None) -> pd.DataFrame:
  """Previsões fora do fold (LOGO por prédio) dos quatro alvos, casadas por `_linha`.

  `conjs`: {alvo: objeto com `.df`} (o Conjunto da carga); `vazadas`: {alvo: colunas com
  vazamento}; `denominador`: {alvo: valor do registro} para download e upload. Feature
  ausente ou com vazamento num alvo fica fora só dele. Linha sem previsão em algum alvo sai.
  Devolve _linha, _site, _pos, dn, up (previsão pontual), lat, jit (p90 com CQR).
  """
  partes = {}
  for alvo, nome in ((DN, 'dn'), (UP, 'up'), (LAT, 'lat'), (JIT, 'jit')):
    df = conjs[alvo].df
    colunas = [f for f in features if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {alvo}')
    if alvo in (LAT, JIT):
      p = quantis.prever_quantis_fora_do_fold(df, colunas, alvo, vazadas[alvo])
      partes[nome] = p.set_index('_linha')['q90']
    else:
      p = avaliacao.prever_fora_do_fold(df, colunas, alvo, vazadas[alvo],
                                        denominador=(denominador or {}).get(alvo))
      partes[nome] = p.set_index('_linha')['yhat']
  saida = pd.concat(partes, axis=1, join='inner')
  base = conjs[DN].df.set_index('_linha')
  saida = saida.assign(_site=base['_site'].reindex(saida.index).to_numpy(),
                       _pos=base['_pos'].reindex(saida.index).to_numpy())
  return saida.rename_axis('_linha').reset_index()


def classe_prevista(prev: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Classe de cada posição pela previsão: medianas de download, upload e dos p90 previstos,
  com a referência da verdade (o V0 é dado conhecido)."""
  g = prev.groupby('_pos')
  est = pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g['dn'].median(), 'up': g['up'].median(),
                      'lat': g['lat'].median(), 'jit': g['jit'].median()})
  return classificar(est, ref, limiares)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: 13 testes OK. O aviso de "menos de 4 prédios" de `outer_logo_folds` nos testes sintéticos é esperado.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/comodo.py`, `tests/test_comodo.py`.
Mensagem sugerida: `feat(comodo): previsão das quatro grandezas e classe prevista`

---

### Task 3: Nota, comparação e validação contra o rótulo

**Files:**
- Modify: `src/ml/core/comodo.py`
- Modify: `tests/test_comodo.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_comodo.py`, antes do bloco `if __name__ == '__main__':`:

```python
def posicoes(real, previsto, site=None):
  site = site or ['s1'] * len(real)
  return pd.DataFrame({'_site': site, 'real': real, 'previsto': previsto},
                      index=pd.Index([f'p{i}' for i in range(len(real))], name='_pos'))


class TestMetricas(unittest.TestCase):
  def test_juntar_fica_com_as_posicoes_comuns_em_ordem(self):
    real = pd.DataFrame({'_site': ['s1'] * 3, 'classe': ['bom', 'ruim', 'bom'], 'apto_jogo': [True, False, True]},
                        index=pd.Index(['b', 'a', 'c'], name='_pos'))
    prev = real.loc[['a', 'b']].assign(classe=['ruim', 'degradado'])
    j = C.juntar(real, prev)
    self.assertEqual(j.index.tolist(), ['a', 'b'])
    self.assertEqual(j['real'].tolist(), ['ruim', 'bom'])
    self.assertEqual(j['previsto'].tolist(), ['ruim', 'degradado'])
    self.assertEqual(j['jogo_real'].tolist(), [False, True])

  def test_nota_conta_posicoes_juntas(self):
    # O prédio A só tem "bom" (como o Villa): numa média entre prédios ele valeria 0,5 fixo.
    pos_df = posicoes(['bom', 'bom', 'bom', 'bom', 'degradado', 'ruim'],
                      ['bom', 'bom', 'bom', 'bom', 'degradado', 'bom'], site=['A', 'A', 'A', 'B', 'B', 'B'])
    r = C.nota(pos_df, [np.arange(6)] * 3)
    self.assertAlmostEqual(r['nota'], 0.6667)

  def test_nota_jogo(self):
    pos_df = posicoes(['bom', 'bom'], ['bom', 'bom']).assign(jogo_real=[True, False], jogo_previsto=[True, True])
    self.assertAlmostEqual(C.nota_jogo(pos_df), 0.5)

  def test_comparar_da_o_veredito_pelo_intervalo(self):
    real = ['bom', 'ruim']
    certa, errada = posicoes(real, ['bom', 'ruim']), posicoes(real, ['bom', 'bom'])
    amostras = [np.arange(2)] * 3
    self.assertEqual(C.comparar(certa, errada, amostras)['resultado'], 'melhor')
    self.assertEqual(C.comparar(errada, certa, amostras)['resultado'], 'pior')
    self.assertEqual(C.comparar(certa, certa, amostras)['resultado'], 'empate')

  def test_confusao_e_erros_graves(self):
    m, graves = C.confusao(posicoes(['bom', 'ruim', 'degradado'], ['ruim', 'bom', 'degradado']))
    self.assertEqual(list(m.index), list(C.CLASSES))
    self.assertEqual(list(m.columns), list(C.CLASSES))
    self.assertEqual(int(m.loc['degradado', 'degradado']), 1)
    self.assertEqual(graves, 2)

  def test_contra_rotulo_converte_os_cinco_niveis(self):
    real = pd.DataFrame({'_site': ['s1'] * 5, 'classe': ['bom', 'bom', 'degradado', 'ruim', 'ruim']},
                        index=pd.Index(list('abcde'), name='_pos'))
    niveis = {'a': 'Excelente', 'b': 'Bom', 'c': 'Ok', 'd': 'Ruim', 'e': 'Ausente', 'z': 'Bom'}
    acuracia, m = C.contra_rotulo(real, niveis)
    self.assertAlmostEqual(acuracia, 1.0)
    self.assertEqual(int(m.loc['bom', 'bom']), 2)
    self.assertEqual(int(m.values.sum()), 5)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: `AttributeError` em `juntar`, `nota`, `nota_jogo`, `comparar`, `confusao`, `contra_rotulo`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/comodo.py`, trocar `from ml.core import avaliacao, quantis` por:

```python
from ml.core import avaliacao, quantis
from ml.core.percepcao import acuracia_balanceada, diferenca, por_predio, resumir
```

(`por_predio` é usado pelo script como `comodo.por_predio`.) Logo abaixo de `DN, UP, LAT, JIT = ...`, acrescentar:

```python
# Erros que trocam um extremo pelo outro.
GRAVES = (('bom', 'ruim'), ('ruim', 'bom'))
# Níveis do rótulo humano (core/percepcao.json) nas classes desta régua.
ROTULO_PARA_CLASSE = {'Excelente': 'bom', 'Bom': 'bom', 'Ok': 'degradado', 'Ruim': 'ruim', 'Ausente': 'ruim'}
```

E no fim do arquivo:

```python
def juntar(real: pd.DataFrame, previsto: pd.DataFrame) -> pd.DataFrame:
  """Posições presentes nas duas tabelas, em ordem: `_site`, `real`, `previsto`, `jogo_real`, `jogo_previsto`."""
  comuns = real.index.intersection(previsto.index).sort_values()
  return pd.DataFrame({'_site': real.loc[comuns, '_site'], 'real': real.loc[comuns, 'classe'],
                       'previsto': previsto.loc[comuns, 'classe'], 'jogo_real': real.loc[comuns, 'apto_jogo'],
                       'jogo_previsto': previsto.loc[comuns, 'apto_jogo']})


def nota(pos_df: pd.DataFrame, amostras) -> dict:
  """Acurácia balanceada das 3 classes sobre as posições de todos os prédios juntas, com o
  intervalo de 90% nas reamostras. Não é média entre prédios: um prédio de uma classe só não prende a nota."""
  return resumir(pos_df, amostras)


def nota_jogo(pos_df: pd.DataFrame) -> float:
  """Acurácia balanceada de "apto para jogo" por posição."""
  return acuracia_balanceada(pos_df['jogo_real'], pos_df['jogo_previsto'])


def comparar(nova: pd.DataFrame, base: pd.DataFrame, amostras) -> dict:
  """Diferença pareada de nota (nova - base) e o resultado: intervalo todo acima de 0 é melhor,
  todo abaixo é pior, o resto é empate."""
  dif = diferenca(nova, base, amostras)
  if dif['intervalo'] is None:
    resultado = 'empate'
  else:
    lo, hi = dif['intervalo']
    resultado = 'melhor' if lo > 0 else 'pior' if hi < 0 else 'empate'
  return dict(dif, resultado=resultado)


def confusao(pos_df: pd.DataFrame) -> tuple:
  """(matriz 3x3 em posições, real nas linhas; quantos erros graves bom <-> ruim)."""
  m = pd.crosstab(pos_df['real'], pos_df['previsto']).reindex(index=list(CLASSES), columns=list(CLASSES),
                                                              fill_value=0)
  return m, int(sum(m.loc[a, b] for a, b in GRAVES))


def contra_rotulo(real: pd.DataFrame, niveis: dict) -> tuple:
  """Verdade contra o rótulo humano (níveis brutos de percepcao.json), nas posições em comum.

  Devolve (acurácia balanceada da verdade contra o rótulo, matriz 3x3 com o rótulo nas linhas).
  """
  comuns = sorted(set(real.index) & set(niveis))
  pos_df = pd.DataFrame({'real': [ROTULO_PARA_CLASSE[niveis[p]] for p in comuns],
                         'previsto': real.loc[comuns, 'classe'].to_numpy()}, index=comuns)
  m, _ = confusao(pos_df)
  return acuracia_balanceada(pos_df['real'], pos_df['previsto']), m
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: 19 testes OK.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/comodo.py`, `tests/test_comodo.py`.
Mensagem sugerida: `feat(comodo): nota por posição, comparação e validação contra o rótulo`

---

### Task 4: Script de reavaliação

**Files:**
- Create: `src/ml/comodo_benchmark.py`

- [ ] **Step 1: Escrever o script**

```python
"""Régua por cômodo (core/comodo.py): reavalia as versões do registro e o piso.

Versão: MODELO=<nome> restringe a uma versão (a ativa entra sempre, para a comparação).
Datasets: DATASETS=a.zip,b.zip (padrão: o conjunto canônico, o mesmo do Studio). Imprime a
referência da casa, a verdade por posição, a verdade contra o rótulo humano e, por versão, a
nota com intervalo de 90%, a comparação com o piso e com a ativa, a matriz de confusão, os
acertos por prédio e "apto para jogo". Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import comodo as core_comodo
from ml.core import modelos as core_modelos
from ml.core import percepcao as core_percepcao
from ml.core import qoe as core_qoe

PISO = 'piso'


def _faixa(intervalo) -> str:
  return '–' if intervalo is None else f'{intervalo[0]:+.3f} a {intervalo[1]:+.3f}'


def main():
  registro = core_modelos.carregar()
  pedido = os.environ.get('MODELO')
  if pedido and pedido not in registro['versoes']:
    raise SystemExit(f'MODELO={pedido!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ativa = registro['ativo']
  nomes = [pedido] if pedido else list(registro['versoes'])
  if ativa not in nomes:
    nomes.append(ativa)
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_qoe.ALVOS}
  vazadas = {alvo: [c for c, k in conj.classes.items() if k is not None and k.vazamento]
             for alvo, conj in conjs.items()}
  limiares = core_aplicacoes.carregar_perfil('norma')
  df = core_qoe.conjunto_qoe(conjs)
  real, ref = core_comodo.verdade(df, limiares)
  linhas = set(core_comodo.sozinhas(df)['_linha'])

  print(f'Régua por cômodo {core_comodo.VERSAO_COMODO}; datasets {conjs[core_comodo.DN].datasets}')
  print(f'{len(linhas)} de {len(df)} linhas sozinhas no rádio; {len(real)} posições; {real["_site"].nunique()} prédios')
  print('\nReferência da casa (V0 provisório, Mbps):')
  print(ref.round(1).to_string())
  print('\nVerdade por posição:')
  print(real.sort_values(['_site', 'razao']).round(2).to_string())
  print(f'Classes: {real["classe"].value_counts().to_dict()}; apto para jogo: {int(real["apto_jogo"].sum())}')

  core_percepcao.carregar()  # valida o arquivo de rótulos antes de ler os níveis brutos
  with open(core_percepcao.PERCEPCAO_PATH, encoding='utf-8') as handle:
    niveis = json.load(handle)['posicoes']
  acuracia, m = core_comodo.contra_rotulo(real, niveis)
  print(f'\nVerdade contra o rótulo humano (rótulo nas linhas): acurácia balanceada {acuracia:.3f}')
  print(m.to_string())

  pos = {}
  for nome in [PISO] + nomes:
    if nome == PISO:
      features, denominador = ['radio'], None
    else:
      features = registro['versoes'][nome]['features']
      denominador = {a: core_modelos.denominador_de(registro, nome, a) for a in (core_comodo.DN, core_comodo.UP)}
    prev = core_comodo.prever(conjs, features, vazadas, denominador)
    prev = prev[prev['_linha'].isin(linhas)]
    pos[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(prev, ref, limiares))
  if len({tuple(p.index) for p in pos.values()}) != 1:
    raise SystemExit('as versões não cobrem as mesmas posições: '
                     + '; '.join(f'{n}: {len(p)}' for n, p in pos.items()))
  amostras = core_avaliacao.reamostras(pos[PISO].index, pos[PISO]['_site'])

  print(f'\nNota (acurácia balanceada por posição, acaso 0,333); ativa = {ativa}')
  for nome in [PISO] + nomes:
    p = pos[nome]
    r = core_comodo.nota(p, amostras)
    c_piso = core_comodo.comparar(p, pos[PISO], amostras)
    c_ativa = core_comodo.comparar(p, pos[ativa], amostras)
    _, graves = core_comodo.confusao(p)
    acertos = int((p['real'] == p['previsto']).sum())
    print(f'  {nome:<10} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs piso {c_piso["diferenca"]:+.3f} '
          f'({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | vs {ativa} {c_ativa["diferenca"]:+.3f} '
          f'({_faixa(c_ativa["intervalo"])}) {c_ativa["resultado"]} | acertos {acertos}/{len(p)} | '
          f'graves {graves} | jogo {core_comodo.nota_jogo(p):.3f}')

  for nome in [PISO] + nomes:
    p = pos[nome]
    m, graves = core_comodo.confusao(p)
    print(f'\n{nome}: matriz de confusão (posições; verdade nas linhas), erros graves {graves}')
    print(m.to_string())
    print('Acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
    erradas = p[p['real'] != p['previsto']]
    print('Erradas: ' + ', '.join(f'{i} ({l.real}->{l.previsto})' for i, l in erradas.iterrows()))


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Rodar na base real**

Run: `venv/bin/python src/ml/comodo_benchmark.py 2>/dev/null | tee /tmp/claude-1000/-home-venko-ml-TR069-ml-scripts/1082c2d4-0586-4f81-ae0b-684a01e3d378/scratchpad/comodo_saida.txt`
(leva alguns minutos: 6 conjuntos de features x 4 alvos x 6 folds; usar timeout de 600000 ms.)

Expected, conferir item por item (medido com as mesmas regras antes do plano):
- `981 de 1708 linhas sozinhas no rádio; 27 posições; 6 prédios`;
- referência: casa-marcelo 117,8 / 153,0; coworking 98,1 / 60,6; hotmilk 182,4 / 176,8; residencia 98,7 / 47,0; villa-escritorio 93,1 / 98,7; villa-residencial 681,8 / 671,0;
- `Classes: {'bom': 14, 'ruim': 7, 'degradado': 6}` (a ordem do dicionário pode variar); `apto para jogo: 10`;
- verdade contra o rótulo: diagonal 13 (bom), 0 (degradado), 4 (ruim);
- uma linha de nota para `piso` e para cada uma de v1, v2-tr069, v3-tr069, v4, v5, cada uma com `acertos x/27`.

Se alguma contagem da verdade não bater, PARAR e reportar a saída inteira; não ajustar cortes, filtro ou regras para fazer bater.

- [ ] **Step 3: Rodar a suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests 2>&1 | tail -15`
Expected: os testes de `test_comodo` passam; falhas só nas 2 antigas (`test_features_core.TestSemente.test_tabela_tr181_do_repositorio`, `test_modelos_core.TestSemente.test_registro_do_repositorio`).

- [ ] **Step 4: Commit (pelo usuário)**

Arquivos: `src/ml/comodo_benchmark.py`.
Mensagem sugerida: `feat(comodo): script de reavaliação das versões pela régua por cômodo`

---

### Task 5: CHANGELOG com o efeito medido

**Files:**
- Modify: `CHANGELOG.md` (acrescentar no topo, sem apagar as seções existentes)

- [ ] **Step 1: Acrescentar a seção no topo**

Preencher com a saída do Step 2 da Task 4 (copiar os números, sem arredondar diferente). Nenhum `<...>` pode ficar no arquivo.

```markdown
# Changelog — Régua por cômodo (experiência relativa à casa)

**Data:** 2026-10-29

## Por quê

Depois da reavaliação de 2026-10-28, todas as versões ficaram em cerca de 0,66 no Studio: os dois prédios
do Villa prendem um terço da nota de QoE em 0,5, e o alvo de limiar absoluto não separa as versões. Esta
régua mede a pergunta do produto, "quais cômodos de uma casa nova estão ruins?", com a experiência relativa
à casa. Spec: `docs/superpowers/specs/2026-10-29-regua-comodo-design.md`; plano:
`docs/superpowers/plans/2026-10-29-regua-comodo.md`.

## Mudanças

- `core/comodo.py`: verdade por posição (linhas sozinhas no rádio; capacidade como fração da melhor posição do prédio; latência e jitter p90 contra a norma), classe bom / degradado / ruim, "apto para jogo", previsão pelas funções fora do fold existentes, nota sobre posições juntas. Versão `2026-10-29.1`.
- `comodo_benchmark.py` novo. Studio, registro e as réguas de regressão e QoE não mudaram.

## Efeito medido

Base padrão, <linhas sozinhas> de <linhas> linhas sozinhas no rádio, 27 posições, 6 prédios. Verdade:
<bom> bom, <degradado> degradado, <ruim> ruim; <apto> aptas para jogo. Verdade contra o rótulo humano:
acurácia balanceada <acurácia>.

| Versão | Nota (IC 90%) | vs piso (IC 90%) | vs ativa (IC 90%) | Acertos | Graves | Jogo |
|---|---|---|---|---|---|---|
| piso | <...> | | | <...> | <...> | <...> |
| v1 | <...> | <...> | | <...> | <...> | <...> |
| v2-tr069 | <...> | <...> | <...> | <...> | <...> | <...> |
| v3-tr069 | <...> | <...> | <...> | <...> | <...> | <...> |
| v4 | <...> | <...> | <...> | <...> | <...> | <...> |
| v5 | <...> | <...> | <...> | <...> | <...> | <...> |

## Limites

- A posição que define a referência é "bom" em capacidade por construção.
- A referência é relativa: num prédio em que todos os cômodos são ruins, ela fica errada.
- O V0 vem da verdade da própria casa de teste (tratado como conhecido).
- Nota provisória até o teste de vídeo e o V0 com cabo existirem.
```

- [ ] **Step 2: Commit (pelo usuário)**

Arquivos: `CHANGELOG.md`.
Mensagem sugerida: `docs(changelog): régua por cômodo`
