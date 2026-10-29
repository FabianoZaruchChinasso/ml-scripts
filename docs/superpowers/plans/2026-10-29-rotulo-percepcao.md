# Classificador do rótulo de percepção — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Medir se o rótulo de percepção por cômodo (3 classes) é aprendível com as features da v5 e se a v5 acrescenta ao piso "só `radio`", por posição, LOGO por prédio.

**Architecture:** Funções puras em `src/ml/core/percepcao.py` (carga e validação dos rótulos, pesos por posição, previsão fora do fold, agregação por posição, métricas e regra de leitura). Um script `src/ml/percepcao_benchmark.py` orquestra e imprime. Rótulos em `src/ml/core/percepcao.json`. Studio, MLflow e `qoe.py` não mudam.

**Tech Stack:** Python 3, pandas 2.3, scikit-learn 1.9 (RandomForestClassifier, Pipeline), `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md`.

---

## Regras do repositório que valem para todas as tarefas

- Indentação de 2 espaços, nomes e docstrings em português, como no resto de `src/ml/core/`.
- Testes com `unittest`, rodados da raiz do repositório: `venv/bin/python -m unittest tests/test_percepcao.py -v`. Não há pytest no venv.
- **Não rodar `git commit` nem `git push`.** O usuário commita à mão. O passo "Commit" de cada tarefa é: parar, listar os arquivos alterados e sugerir a mensagem (sem linha `Co-Authored-By`).
- Não mexer em `classification_benchmark.py`, `regression_benchmark.py` e `compare_protocols.py` (benchmarks congelados do Fabiano).

## Estrutura de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/core/percepcao.json` | criar | rótulo bruto por posição e o agrupamento em 3 classes |
| `src/ml/core/percepcao.py` | criar | funções puras: carga, pesos, previsão, agregação, métricas, leitura |
| `tests/test_percepcao.py` | criar | testes das funções puras, sem a base real |
| `src/ml/percepcao_benchmark.py` | criar | script: carrega a base, roda v5 e piso, imprime |
| `CHANGELOG.md` | modificar (topo) | seção nova com o efeito medido |

---

### Task 1: Rótulos e carga validada

**Files:**
- Create: `src/ml/core/percepcao.json`
- Create: `src/ml/core/percepcao.py`
- Create: `tests/test_percepcao.py`

- [ ] **Step 1: Criar `src/ml/core/percepcao.json`**

```json
{
  "classes": {
    "Excelente": "excelente",
    "Bom": "media",
    "Ok": "media",
    "Ruim": "ruim",
    "Ausente": "ruim"
  },
  "posicoes": {
    "villa_res_sala": "Excelente",
    "villa_res_cozinha": "Ausente",
    "villa_res_escritorio": "Excelente",
    "villa_res_quarto1": "Bom",
    "villa_res_quarto2": "Ruim",
    "villa_esc_recepcao": "Bom",
    "villa_esc_sala1": "Excelente",
    "villa_esc_sala2": "Excelente",
    "villa_esc_copa": "Excelente",
    "villa_esc_estoque": "Bom",
    "marcelo-copa": "Bom",
    "marcelo-copa-split": "Bom",
    "marcelo-sala-estar": "Ruim",
    "marcelo-quarto": "Excelente",
    "marcelo-quarto-split": "Excelente",
    "marcelo-inf-sala": "Bom",
    "marcelo-inf-sala-split": "Bom",
    "marcelo-inf-quarto": "Ok",
    "marcelo-inf-quarto-split": "Ok",
    "marcelo-inf-ext": "Ruim",
    "res-sala": "Excelente",
    "res-quarto": "Bom",
    "res-suite": "Ruim",
    "cwpb-1": "Excelente",
    "cwpb-2": "Bom",
    "hotmilk-aquario": "Excelente",
    "hotmilk-aquario-fora": "Excelente",
    "hotmilk-copa": "Ok"
  }
}
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `tests/test_percepcao.py`:

```python
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import percepcao as P

# Um prédio por posições nomeadas (como a residência) e um por prefixo (como o hotmilk).
REGISTRO = {'aliases': {},
            'predios': {'casa': {'ambiente': 'domestico', 'prefixos': [], 'rotulo': 'Casa', 'studio': 'casa',
                                 'posicoes': {'sala': 'res-sala', 'quarto': 'res-quarto'}},
                        'hot': {'ambiente': 'corporativo', 'prefixos': ['hotmilk'], 'rotulo': 'Hot',
                                'studio': 'hot'}}}
CLASSES = {'Excelente': 'excelente', 'Bom': 'media', 'Ok': 'media', 'Ruim': 'ruim', 'Ausente': 'ruim'}


def gravar(dados) -> str:
  arquivo = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
  json.dump(dados, arquivo)
  arquivo.close()
  return arquivo.name


class TestCarregar(unittest.TestCase):
  def test_nivel_vira_classe(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-sala': 'Excelente', 'hotmilk-copa': 'Ok',
                                                    'res-quarto': 'Ausente'}})
    self.assertEqual(P.carregar(path, REGISTRO),
                     {'res-sala': 'excelente', 'hotmilk-copa': 'media', 'res-quarto': 'ruim'})

  def test_posicao_desconhecida_levanta(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-cozinha': 'Bom'}})
    with self.assertRaisesRegex(ValueError, 'res-cozinha'):
      P.carregar(path, REGISTRO)

  def test_nivel_desconhecido_levanta(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-sala': 'Mediano'}})
    with self.assertRaisesRegex(ValueError, 'Mediano'):
      P.carregar(path, REGISTRO)

  def test_classe_desconhecida_levanta(self):
    path = gravar({'classes': {**CLASSES, 'Bom': 'boa'}, 'posicoes': {'res-sala': 'Bom'}})
    with self.assertRaisesRegex(ValueError, 'boa'):
      P.carregar(path, REGISTRO)

  def test_chaves_erradas_levantam(self):
    path = gravar({'classes': CLASSES})
    with self.assertRaisesRegex(ValueError, 'posicoes'):
      P.carregar(path, REGISTRO)

  def test_arquivo_do_repositorio_valida(self):
    rotulos = P.carregar()
    self.assertEqual(len(rotulos), 28)
    self.assertEqual(rotulos['villa_res_cozinha'], 'ruim')


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: erro de import (`cannot import name 'percepcao'` ou `No module named 'ml.core.percepcao'`).

- [ ] **Step 4: Implementar**

Criar `src/ml/core/percepcao.py`:

```python
"""Rótulo de percepção por cômodo: quem estava no local diz se a experiência era boa ou ruim.

O rótulo é por posição (core/percepcao.json), agrupado em três classes. O classificador é
treinado nas linhas e avaliado por posição, deixando um prédio de fora por vez. Spec:
docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md.
"""

import json
import os

import pandas as pd

from ml.core import sites

PERCEPCAO_PATH = os.path.join(os.path.dirname(__file__), 'percepcao.json')
CLASSES = ('excelente', 'media', 'ruim')


def _posicao_conhecida(chave: str, registro: dict) -> bool:
  """Posição canônica: valor de `posicoes` de algum prédio, ou valor que resolve para si mesmo (prefixo)."""
  if any(chave in p.get('posicoes', {}).values() for p in registro['predios'].values()):
    return True
  try:
    return sites.resolve_site_id(pd.Series([chave]), registro=registro).iloc[0] == chave
  except ValueError:
    return False


def validar(dados, registro: dict = None) -> None:
  if not isinstance(dados, dict) or set(dados) != {'classes', 'posicoes'}:
    raise ValueError("percepcao.json precisa ter exatamente as chaves 'classes' e 'posicoes'")
  fora = sorted(set(dados['classes'].values()) - set(CLASSES))
  if fora:
    raise ValueError(f'classes desconhecidas {fora}; esperado uma de {list(CLASSES)}')
  registro = sites.registro_atual() if registro is None else registro
  for posicao, nivel in dados['posicoes'].items():
    if nivel not in dados['classes']:
      raise ValueError(f'{posicao!r}: nível {nivel!r} fora de {sorted(dados["classes"])}')
    if not _posicao_conhecida(posicao, registro):
      raise ValueError(f'{posicao!r}: posição desconhecida em core/predios.json')


def carregar(path: str = PERCEPCAO_PATH, registro: dict = None) -> dict:
  """{posição: classe} de percepcao.json, validado contra o registro de prédios."""
  with open(path, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados, registro)
  return {posicao: dados['classes'][nivel] for posicao, nivel in dados['posicoes'].items()}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: 6 testes OK.

- [ ] **Step 6: Commit (pelo usuário)**

Arquivos: `src/ml/core/percepcao.json`, `src/ml/core/percepcao.py`, `tests/test_percepcao.py`.
Mensagem sugerida: `feat(percepcao): rótulos de percepção por cômodo e carga validada`

---

### Task 2: Rotular as linhas e pesar por posição

**Files:**
- Modify: `src/ml/core/percepcao.py`
- Modify: `tests/test_percepcao.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_percepcao.py`, antes do bloco `if __name__ == '__main__':`:

```python
class TestRotular(unittest.TestCase):
  def test_rotula_e_lista_o_que_ficou_fora(self):
    df = pd.DataFrame({'_pos': ['a', 'a', 'b', 'z'], 'x': [1, 2, 3, 4]})
    saida, sem_rotulo, sem_linhas = P.rotular(df, {'a': 'excelente', 'b': 'ruim', 'c': 'media'})
    self.assertEqual(saida['_classe'].tolist(), ['excelente', 'excelente', 'ruim'])
    self.assertEqual(saida.index.tolist(), [0, 1, 2])
    self.assertEqual(sem_rotulo, ['z'])
    self.assertEqual(sem_linhas, ['c'])


class TestPesos(unittest.TestCase):
  def test_posicao_e_classe_somam_igual(self):
    pos = ['a', 'a', 'b', 'c', 'c', 'c']
    classe = ['x', 'x', 'x', 'y', 'y', 'y']
    w = P.pesos(pos, classe)
    # 3 posições, 2 classes: cada classe soma 1,5; dentro da classe x, a e b pesam o mesmo.
    np.testing.assert_allclose(w, [0.375, 0.375, 0.75, 0.5, 0.5, 0.5])

  def test_soma_total_e_o_numero_de_posicoes(self):
    w = P.pesos(['a'] * 180 + ['b'] * 20 + ['c'] * 50, ['x'] * 200 + ['y'] * 50)
    self.assertAlmostEqual(float(w.sum()), 3.0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: `AttributeError: module 'ml.core.percepcao' has no attribute 'rotular'` (e `pesos`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/percepcao.py`, acrescentar `import numpy as np` entre `import os` e `import pandas as pd`:

```python
import json
import os

import numpy as np
import pandas as pd
```

E no fim do arquivo:

```python
def rotular(df: pd.DataFrame, rotulos: dict) -> tuple:
  """(df só com posições rotuladas, com `_classe` e índice refeito; posições sem rótulo; rotuladas sem linhas)."""
  sem_rotulo = sorted(set(df['_pos']) - set(rotulos))
  sem_linhas = sorted(set(rotulos) - set(df['_pos']))
  saida = df[df['_pos'].isin(list(rotulos))].reset_index(drop=True)
  return saida.assign(_classe=saida['_pos'].map(rotulos)), sem_rotulo, sem_linhas


def pesos(pos, classe) -> np.ndarray:
  """Peso por linha: cada posição soma o mesmo dentro da classe e cada classe soma o mesmo total.

  Sem isso uma posição com 180 linhas valeria nove vezes uma com 20. A soma é o número de posições.
  """
  pos = pd.Series(np.asarray(pos))
  classe = pd.Series(np.asarray(classe))
  w = 1.0 / pos.map(pos.value_counts())
  por_classe = w.groupby(classe).transform('sum')
  return (w / por_classe * (pos.nunique() / classe.nunique())).to_numpy()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: 9 testes OK.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/percepcao.py`, `tests/test_percepcao.py`.
Mensagem sugerida: `feat(percepcao): rótulo por linha e peso por posição`

---

### Task 3: Modelo e previsão fora do fold

**Files:**
- Modify: `src/ml/core/percepcao.py`
- Modify: `tests/test_percepcao.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_percepcao.py`, acrescentar aos imports (depois de `import pandas as pd`):

```python
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.pipeline import Pipeline
```

E antes do bloco `if __name__ == '__main__':`:

```python
class Lembra(BaseEstimator, ClassifierMixin):
  """Guarda o índice e os pesos de cada ajuste; prevê a classe mais frequente do treino com prob. 1."""
  ajustes = []

  def fit(self, X, y, sample_weight=None):
    self.classes_ = np.unique(y)
    self.maioria_ = pd.Series(np.asarray(y)).value_counts().index[0]
    Lembra.ajustes.append((list(X.index), sample_weight))
    return self

  def predict_proba(self, X):
    p = np.zeros((len(X), len(self.classes_)))
    p[:, list(self.classes_).index(self.maioria_)] = 1.0
    return p


def lembra():
  return Pipeline([('clf', Lembra())])


def frame_tres_predios():
  # 3 prédios, 2 posições cada, linhas desiguais; classes nas três.
  pos = ['s1-a'] * 4 + ['s1-b'] * 2 + ['s2-a'] * 3 + ['s2-b'] * 3 + ['s3-a'] * 2 + ['s3-b'] * 2
  site = [p[:2] for p in pos]
  classe = {'s1-a': 'excelente', 's1-b': 'ruim', 's2-a': 'media', 's2-b': 'ruim', 's3-a': 'excelente',
            's3-b': 'media'}
  return pd.DataFrame({'_pos': pos, '_site': site, '_classe': [classe[p] for p in pos],
                       'radio': ['5GHz'] * len(pos), 'sinal': np.arange(len(pos), dtype=float)})


class TestPreverForaDoFold(unittest.TestCase):
  def setUp(self):
    Lembra.ajustes = []

  def test_treino_nunca_ve_o_predio_de_teste(self):
    df = frame_tres_predios()
    P.prever_fora_do_fold(df, ['sinal'], vazadas=[], fabrica=lembra)
    self.assertEqual(len(Lembra.ajustes), 3)
    for indices, _ in Lembra.ajustes:
      self.assertEqual(df.loc[indices, '_site'].nunique(), 2)

  def test_pesos_chegam_ao_estimador(self):
    df = frame_tres_predios()
    P.prever_fora_do_fold(df, ['sinal'], vazadas=[], fabrica=lembra)
    indices, w = Lembra.ajustes[0]
    np.testing.assert_allclose(w, P.pesos(df.loc[indices, '_pos'], df.loc[indices, '_classe']))

  def test_probabilidades_alinhadas_e_somam_um(self):
    df = frame_tres_predios()
    proba = P.prever_fora_do_fold(df, ['sinal', 'radio'], vazadas=[], fabrica=lembra)
    self.assertEqual(list(proba.columns), list(P.CLASSES))
    self.assertEqual(proba.index.tolist(), df.index.tolist())
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)

  def test_coluna_vazada_levanta(self):
    with self.assertRaises(AssertionError):
      P.prever_fora_do_fold(frame_tres_predios(), ['sinal'], vazadas=['sinal'], fabrica=lembra)

  def test_modelo_padrao_nao_usa_class_weight(self):
    self.assertIsNone(P.modelo().named_steps['clf'].class_weight)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: `AttributeError: module 'ml.core.percepcao' has no attribute 'prever_fora_do_fold'` (e `modelo`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/percepcao.py`, trocar o bloco de imports de terceiros e internos por:

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from ml.core import sites
from ml.core.avaliacao import assert_sem_vazamento
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds
```

E no fim do arquivo:

```python
def modelo() -> Pipeline:
  """Os hiperparâmetros do RF de referência do QoE, sem class_weight: o balanceamento vem de `pesos`."""
  return Pipeline([('imputer', SimpleImputer(strategy='median')),
                   ('clf', RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1,
                                                  random_state=42))])


def prever_fora_do_fold(df: pd.DataFrame, colunas, vazadas, fabrica=modelo) -> pd.DataFrame:
  """Probabilidade de cada classe em cada linha, pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  `fabrica()` devolve um Pipeline com o passo 'clf', que recebe os pesos de `pesos`. Devolve um
  DataFrame alinhado com `df`, colunas CLASSES; classe ausente do treino do fold fica com 0.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not df.index.is_unique:
    raise ValueError('índice do df precisa ser único')
  X = matriz(df, colunas)
  proba = pd.DataFrame(0.0, index=df.index, columns=list(CLASSES))
  for fold in outer_logo_folds(X, df['_classe'], df['_site']):
    w = pesos(df.loc[fold.X_train.index, '_pos'], fold.y_train)
    ajustado = fabrica().fit(fold.X_train, fold.y_train, clf__sample_weight=w)
    p = pd.DataFrame(ajustado.predict_proba(fold.X_test), index=fold.X_test.index, columns=ajustado.classes_)
    proba.loc[fold.X_test.index] = p.reindex(columns=list(CLASSES), fill_value=0.0).to_numpy()
  return proba
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: 14 testes OK. (`outer_logo_folds` emite um aviso de "menos de 4 prédios" nos testes com 3 prédios; é esperado.)

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/percepcao.py`, `tests/test_percepcao.py`.
Mensagem sugerida: `feat(percepcao): RF com peso por posição, LOGO por prédio`

---

### Task 4: Agregação por posição, métricas e regra de leitura

**Files:**
- Modify: `src/ml/core/percepcao.py`
- Modify: `tests/test_percepcao.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_percepcao.py`, antes do bloco `if __name__ == '__main__':`:

```python
class TestPorPosicao(unittest.TestCase):
  def test_media_das_probabilidades_e_argmax(self):
    df = pd.DataFrame({'_pos': ['a', 'a', 'a', 'b'], '_site': ['s1', 's1', 's1', 's2'],
                       '_classe': ['ruim', 'ruim', 'ruim', 'excelente']})
    # Em 'a' a maioria das linhas prevê media, mas a média das probabilidades dá ruim.
    proba = pd.DataFrame([[0.0, 0.6, 0.4], [0.0, 0.6, 0.4], [0.0, 0.0, 1.0], [0.5, 0.5, 0.0]],
                         columns=list(P.CLASSES))
    pos_df = P.por_posicao(df, proba)
    self.assertEqual(pos_df.index.tolist(), ['a', 'b'])
    self.assertEqual(pos_df['previsto'].tolist(), ['ruim', 'excelente'])
    self.assertEqual(pos_df['real'].tolist(), ['ruim', 'excelente'])
    self.assertEqual(pos_df['_site'].tolist(), ['s1', 's2'])


def posicoes(real, previsto, site=None):
  site = site or ['s1'] * len(real)
  return pd.DataFrame({'_site': site, 'real': real, 'previsto': previsto},
                      index=[f'p{i}' for i in range(len(real))])


class TestMetricas(unittest.TestCase):
  def test_acuracia_balanceada(self):
    real = ['excelente', 'excelente', 'media', 'ruim']
    previsto = ['excelente', 'media', 'media', 'media']
    # recall: excelente 0,5; media 1; ruim 0.
    self.assertAlmostEqual(P.acuracia_balanceada(real, previsto), 0.5)

  def test_resumir_sem_reamostra_igual_nota(self):
    pos_df = posicoes(['excelente', 'ruim'], ['excelente', 'ruim'])
    r = P.resumir(pos_df, [np.array([0, 1])] * 3)
    self.assertEqual(r['nota'], 1.0)
    self.assertEqual(r['intervalo'], [1.0, 1.0])

  def test_diferenca_pareada(self):
    nova = posicoes(['excelente', 'ruim'], ['excelente', 'ruim'])
    base = posicoes(['excelente', 'ruim'], ['excelente', 'excelente'])
    d = P.diferenca(nova, base, [np.array([0, 1])] * 3)
    self.assertEqual(d['diferenca'], 0.5)
    self.assertEqual(d['intervalo'], [0.5, 0.5])

  def test_diferenca_exige_mesmas_posicoes(self):
    with self.assertRaises(ValueError):
      P.diferenca(posicoes(['ruim'], ['ruim']), posicoes(['ruim', 'ruim'], ['ruim', 'ruim']), [])

  def test_confusao_e_graves(self):
    pos_df = posicoes(['excelente', 'ruim', 'media'], ['ruim', 'excelente', 'media'])
    m, graves = P.confusao(pos_df)
    self.assertEqual(list(m.index), list(P.CLASSES))
    self.assertEqual(list(m.columns), list(P.CLASSES))
    self.assertEqual(int(m.loc['media', 'media']), 1)
    self.assertEqual(graves, 2)

  def test_por_predio(self):
    pos_df = posicoes(['ruim', 'ruim', 'media'], ['ruim', 'media', 'media'], site=['s1', 's1', 's2'])
    self.assertEqual(P.por_predio(pos_df), {'s1': (1, 2), 's2': (1, 1)})


class TestLeitura(unittest.TestCase):
  def test_aprendivel_por_qualquer_um(self):
    r = P.leitura({'intervalo': [0.30, 0.5]}, {'intervalo': [0.34, 0.6]}, {'intervalo': [-0.1, 0.2]})
    self.assertEqual(r, {'aprendivel': True, 'contra_piso': 'empate'})

  def test_nao_aprendivel(self):
    r = P.leitura({'intervalo': [0.20, 0.5]}, {'intervalo': [1 / 3, 0.6]}, {'intervalo': [0.01, 0.2]})
    self.assertEqual(r, {'aprendivel': False, 'contra_piso': 'melhor'})

  def test_piora(self):
    r = P.leitura({'intervalo': [0.4, 0.5]}, {'intervalo': [0.2, 0.3]}, {'intervalo': [-0.3, -0.01]})
    self.assertEqual(r['contra_piso'], 'piora')

  def test_intervalo_vazio_e_empate(self):
    r = P.leitura({'intervalo': None}, {'intervalo': None}, {'intervalo': None})
    self.assertEqual(r, {'aprendivel': False, 'contra_piso': 'empate'})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: `AttributeError` em `por_posicao`, `acuracia_balanceada`, `resumir`, `diferenca`, `confusao`, `por_predio`, `leitura`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/percepcao.py`, trocar `from ml.core.avaliacao import assert_sem_vazamento` por:

```python
from ml.core.avaliacao import _intervalo, assert_sem_vazamento
```

Logo abaixo de `CLASSES = ...`, acrescentar:

```python
# Acaso e "sempre a classe majoritária" dão o mesmo na acurácia balanceada de 3 classes.
ACASO = 1 / len(CLASSES)
# Erros que trocam um extremo pelo outro.
GRAVES = (('excelente', 'ruim'), ('ruim', 'excelente'))
```

E no fim do arquivo:

```python
def por_posicao(df: pd.DataFrame, proba: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição (índice `_pos`): `_site`, `real` e `previsto` (classe de maior probabilidade média)."""
  media = proba.groupby(df['_pos']).mean()
  info = df.groupby('_pos')[['_site', '_classe']].first()
  return pd.DataFrame({'_site': info['_site'], 'real': info['_classe'],
                       'previsto': media.loc[info.index, list(CLASSES)].idxmax(axis=1)})


def acuracia_balanceada(real, previsto) -> float:
  """Média do recall das classes presentes em `real`."""
  real, previsto = np.asarray(real), np.asarray(previsto)
  return float(np.mean([np.mean(previsto[real == c] == c) for c in np.unique(real)]))


def resumir(pos_df: pd.DataFrame, amostras) -> dict:
  """Acurácia balanceada por posição e o intervalo de 90% nas reamostragens (índices posicionais de `pos_df`)."""
  real, prev = pos_df['real'].to_numpy(), pos_df['previsto'].to_numpy()
  return {'nota': round(acuracia_balanceada(real, prev), 4),
          'intervalo': _intervalo([acuracia_balanceada(real[i], prev[i]) for i in amostras])}


def diferenca(nova: pd.DataFrame, base: pd.DataFrame, amostras) -> dict:
  """Diferença pareada de acurácia balanceada (nova - base) nas mesmas reamostragens."""
  if not nova.index.equals(base.index):
    raise ValueError('nova e base precisam das mesmas posições, na mesma ordem')
  real = nova['real'].to_numpy()
  pn, pb = nova['previsto'].to_numpy(), base['previsto'].to_numpy()
  return {'diferenca': round(acuracia_balanceada(real, pn) - acuracia_balanceada(real, pb), 4),
          'intervalo': _intervalo([acuracia_balanceada(real[i], pn[i]) - acuracia_balanceada(real[i], pb[i])
                                   for i in amostras])}


def leitura(piso: dict, nova: dict, dif: dict) -> dict:
  """Regra fixada no spec (seção 3.4) antes de rodar."""
  aprendivel = any(r['intervalo'] is not None and r['intervalo'][0] > ACASO for r in (piso, nova))
  if dif['intervalo'] is None:
    contra_piso = 'empate'
  else:
    lo, hi = dif['intervalo']
    contra_piso = 'melhor' if lo > 0 else 'piora' if hi < 0 else 'empate'
  return {'aprendivel': aprendivel, 'contra_piso': contra_piso}


def confusao(pos_df: pd.DataFrame) -> tuple:
  """(matriz 3x3 em posições, real nas linhas; quantos erros graves excelente <-> ruim)."""
  m = pd.crosstab(pos_df['real'], pos_df['previsto']).reindex(index=list(CLASSES), columns=list(CLASSES),
                                                              fill_value=0)
  return m, int(sum(m.loc[a, b] for a, b in GRAVES))


def por_predio(pos_df: pd.DataFrame) -> dict:
  """{prédio: (acertos, posições)}."""
  certo = pos_df['real'] == pos_df['previsto']
  return {s: (int(certo[g.index].sum()), len(g)) for s, g in pos_df.groupby('_site')}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_percepcao.py -v`
Expected: 25 testes OK.

- [ ] **Step 5: Commit (pelo usuário)**

Arquivos: `src/ml/core/percepcao.py`, `tests/test_percepcao.py`.
Mensagem sugerida: `feat(percepcao): métricas por posição e regra de leitura`

---

### Task 5: Script do experimento

**Files:**
- Create: `src/ml/percepcao_benchmark.py`

- [ ] **Step 1: Escrever o script**

```python
"""Classificador do rótulo de percepção por cômodo (core/percepcao.json), medido por posição.

Versão: MODELO=<nome> (padrão: v5). Datasets: DATASETS=a.zip,b.zip (padrão: o conjunto
canônico, o mesmo do Studio). Treina o RF de core/percepcao com as features da versão e com o
piso (só `radio`), LOGO por prédio, e imprime a acurácia balanceada por posição com intervalo
de 90%, a diferença pareada, a matriz de confusão, os acertos por prédio e a leitura da regra
fixada no spec (docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md).
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import modelos as core_modelos
from ml.core import percepcao as core_percepcao

ALVO = 'speedtest_down_mbps'
PISO = ['radio']


def _linha(nome: str, r: dict) -> str:
  return f'  {nome:<6} {r["nota"]:.3f}  (90%: {r["intervalo"]})'


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or 'v5'
  if nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conj = core_carga.carregar(ALVO, ids=ids)
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  df, sem_rotulo, sem_linhas = core_percepcao.rotular(conj.df, core_percepcao.carregar())
  pedidas = list(registro['versoes'][nome]['features'])
  features = [f for f in pedidas if f in df.columns and f not in vazadas]
  fora = [f for f in pedidas if f not in features]

  print(f'Datasets: {conj.datasets}')
  for aviso in conj.avisos:
    print(f'  aviso: {aviso}')
  if sem_rotulo:
    print(f'Posições sem rótulo (fora): {sem_rotulo}')
  if sem_linhas:
    print(f'Rotuladas sem linhas na base: {sem_linhas}')
  print(f'Modelo {nome}: {len(features)} features' + (f'; fora (vazamento ou ausentes): {fora}' if fora else ''))

  resultados = {}
  for chave, colunas in ((nome, features), ('piso', PISO)):
    proba = core_percepcao.prever_fora_do_fold(df, colunas, vazadas)
    resultados[chave] = (proba, core_percepcao.por_posicao(df, proba))
  pos_piso = resultados['piso'][1]
  pos_nova = resultados[nome][1]
  print(f'{len(df)} linhas, {len(pos_piso)} posições, {pos_piso["_site"].nunique()} prédios; '
        f'classes por posição: {pos_piso["real"].value_counts().to_dict()}')

  amostras = core_avaliacao.reamostras(pos_piso.index, pos_piso['_site'])
  r_piso = core_percepcao.resumir(pos_piso, amostras)
  r_nova = core_percepcao.resumir(pos_nova, amostras)
  dif = core_percepcao.diferenca(pos_nova, pos_piso, amostras)

  print(f'\nAcurácia balanceada por posição (acaso {core_percepcao.ACASO:.3f}):')
  print(_linha(nome, r_nova))
  print(_linha('piso', r_piso))
  print(f'  {nome} - piso: {dif["diferenca"]:+.3f}  (90%: {dif["intervalo"]})')

  print('\nAcurácia balanceada por linha (só referência):')
  for chave, (proba, _) in resultados.items():
    print(f'  {chave:<6} {core_percepcao.acuracia_balanceada(df["_classe"], proba.idxmax(axis=1)):.3f}')

  for chave, (_, pos_df) in resultados.items():
    m, graves = core_percepcao.confusao(pos_df)
    print(f'\nMatriz de confusão {chave} (posições; real nas linhas), erros graves: {graves}')
    print(m.to_string())
    print('Acertos por prédio (cada prédio teve um avaliador; avaliador e prédio não se separam):')
    for site, (acertos, n) in core_percepcao.por_predio(pos_df).items():
      print(f'  {site:<18} {acertos}/{n}')
    erradas = pos_df[pos_df['real'] != pos_df['previsto']]
    print('Posições erradas:')
    for pos, linha in erradas.iterrows():
      print(f'  {pos:<26} real {linha["real"]:<10} previsto {linha["previsto"]}')

  regra = core_percepcao.leitura(r_piso, r_nova, dif)
  print(f'\nLeitura (regra do spec, seção 3.4): aprendível = {regra["aprendivel"]}; '
        f'{nome} contra o piso = {regra["contra_piso"]}')


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Rodar na base real**

Run: `venv/bin/python src/ml/percepcao_benchmark.py`
Expected, conferir item por item:
- `Rotuladas sem linhas na base: ['marcelo-quarto']`;
- `27 posições, 6 prédios; classes por posição: {'media': 12, 'excelente': 10, 'ruim': 5}`;
- as duas notas por posição entre 0 e 1, cada uma com intervalo de 2 números;
- a linha final `Leitura (...)` presente.

Se as contagens não baterem, parar e reportar; não ajustar o rótulo nem a regra para fazer bater.

- [ ] **Step 3: Rodar a suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: os testes novos passam; o número de falhas é o mesmo de antes deste plano (havia 2 falhas antigas em 2026-10-27, conferir com `git stash` se houver dúvida).

- [ ] **Step 4: Commit (pelo usuário)**

Arquivos: `src/ml/percepcao_benchmark.py`.
Mensagem sugerida: `feat(percepcao): script do experimento do rótulo de percepção`

---

### Task 6: CHANGELOG com o efeito medido

**Files:**
- Modify: `CHANGELOG.md` (acrescentar no topo, sem apagar as seções existentes)

- [ ] **Step 1: Acrescentar a seção no topo**

Preencher os números com a saída do Step 2 da Task 5 (copiar, não arredondar diferente):

```markdown
# Changelog — Rótulo de percepção por cômodo (classificador de 3 classes)

**Data:** 2026-10-29

## Por quê

Na reunião de 2026-10-28 ficou alinhado rotular a percepção de quem estava no local. Este experimento
mede se esse rótulo é aprendível com as features do roteador. Spec:
`docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md`; plano:
`docs/superpowers/plans/2026-10-29-rotulo-percepcao.md`.

## Mudanças

- `core/percepcao.json`: rótulo de 28 posições em 5 níveis, agrupados em excelente / media / ruim.
- `core/percepcao.py`: carga validada, peso por posição, RF LOGO por prédio, métricas por posição, regra de leitura.
- `percepcao_benchmark.py` novo. Studio, MLflow e `core/qoe.py` não mudaram.

## Efeito medido

Base padrão, 27 posições, 6 prédios, LOGO por prédio, acurácia balanceada por posição (acaso 0,333):

| Features | Nota | Intervalo 90% |
|---|---|---|
| v5 | <nota v5> | <intervalo v5> |
| piso (só radio) | <nota piso> | <intervalo piso> |
| v5 - piso | <diferença> | <intervalo da diferença> |

Leitura: aprendível = <sim/não>; v5 contra o piso = <melhor/empate/piora>.
Erros graves (excelente <-> ruim): v5 <n>, piso <n>.
```

Os `<...>` acima são os campos a copiar da saída; nenhum deve ficar no arquivo.

- [ ] **Step 2: Commit (pelo usuário)**

Arquivos: `CHANGELOG.md`.
Mensagem sugerida: `docs(changelog): rótulo de percepção por cômodo`
