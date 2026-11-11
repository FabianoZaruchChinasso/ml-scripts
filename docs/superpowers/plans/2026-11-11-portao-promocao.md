# Portão de promoção — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `venv/bin/python src/ml/portao_mlflow.py` decide se a versão registrada mais recente de `qoe-wifi` substitui a ativa, grava o veredito no run e na versão, e move o alias quando for o caso.

**Architecture:** `src/ml/core/portao.py` compara duas definições nas mesmas linhas (previsões fora do fold recalculadas nos dados da candidata), ou, no re-treino da mesma definição, a receita treinada só com o dado antigo contra a treinada com tudo, e decide, sem MLflow. As funções de previsão fora do fold ganham `treinar_em` para restringir as linhas de treino. `src/ml/core/registry_mlflow.py` ganha leitura de uma versão e tags de portão. `src/ml/portao_mlflow.py` é o comando: lê o Registry, chama o core, grava e promove.

**Tech Stack:** Python 3.12, mlflow 3.15.1 (sqlite), pandas, scikit-learn, unittest.

**Spec:** `docs/superpowers/specs/2026-11-11-portao-promocao-design.md`.

---

## Regras deste repositório (ler antes de começar)

- **Commits:** pode commitar ao fim de cada tarefa, com a mensagem indicada. Só a linha de assunto, **sem `Co-Authored-By` e sem citar o Claude**, nunca. **Push e merge: nunca sem perguntar ao Lucas.**
- Trabalhe na branch `portao-promocao` (já criada a partir de `model-registry`; contém a spec).
- Nada de emoji em código, texto ou docs.
- Python: `venv/bin/python`. Testes: `venv/bin/python -m unittest discover -s tests -p '<arquivo>'` a partir da raiz.
- Indentação Python: 2 espaços. Aspas simples. Comentários e docstrings em português.
- **Nenhum teste pode ler ou gravar o `mlflow.db` da raiz.** Use `ComBanco` de `tests/test_registry_mlflow.py` (banco temporário).
- Memória da máquina é curta (cerca de 1 GB livre). A suíte inteira leva uns 6 min; exit 137 é falta de memória, rode de novo sozinha.

## O que já foi conferido (2026-11-11)

- `core_avaliacao.delta_mae` + `veredito_promocao` e `core_quantis.delta_pinball` + `veredito_quantis` são os vereditos que o Studio usa em `_promocao` (`src/ml/studio/api.py`); comparam nas mesmas linhas (`_linha`) e reamostram posições dentro dos prédios com semente fixa.
- Cobertura do p90 nas cinco versões registradas: latência 0,905 a 0,920 e jitter 0,906 a 0,919, dentro de `FAIXA_COBERTURA` (0,80 a 0,95).
- O run de `versao_mlflow.py` tem as métricas `comodo_nota`, `comodo_lo90`, `comodo_hi90` e `atende_completo`; a versão registrada tem as tags `definicao` e `fingerprints` (separados por vírgula).

---

### Task 0: `treinar_em` nas previsões fora do fold

**Files:**
- Modify: `src/ml/core/avaliacao.py` (`prever_fora_do_fold`, `_prever_por_banda`), `src/ml/core/quantis.py` (`prever_quantis_fora_do_fold`)
- Test: `tests/test_avaliacao.py`, `tests/test_quantis.py`

- [ ] **Step 1: Testes**

Em `tests/test_avaliacao.py`, classe `TestPrevisoes`, acrescentar (o `Constante` do arquivo guarda em `indices_` as linhas de treino de cada ajuste):

```python
  def test_treinar_em_tira_linhas_do_treino_sem_mudar_o_teste(self):
    conj = conjunto()
    so_metade = pd.Series(np.arange(len(conj.df)) % 2 == 0, index=conj.df.index)
    vistos = []
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(),
                                 ao_ajustar=lambda fold, modelo: vistos.append(modelo.indices_),
                                 treinar_em=so_metade)
    self.assertEqual(sorted(prev['_linha']), sorted(conj.df['_linha']))   # todas as linhas são previstas
    treinadas = {i for indices in vistos for i in indices}
    self.assertTrue(treinadas)
    self.assertTrue(treinadas <= set(conj.df.index[so_metade]))

  def test_treinar_em_tudo_igual_a_none(self):
    conj = conjunto()
    tudo = pd.Series(True, index=conj.df.index)
    a = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    b = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], treinar_em=tudo)
    pd.testing.assert_frame_equal(a, b)

  def test_treinar_em_passa_pelo_denominador_por_banda(self):
    f = frame()
    f['radio'] = np.where(np.arange(len(f)) % 2 == 0, '5ghz', '2.4ghz')
    conj = conjunto(f=f)
    so_metade = pd.Series(np.arange(len(conj.df)) % 3 != 0, index=conj.df.index)
    vistos = []
    A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(),
                          ao_ajustar=lambda fold, modelo: vistos.append(modelo.indices_),
                          denominador={'coluna': 'router_snr', 'radio': '5ghz'}, treinar_em=so_metade)
    self.assertTrue({i for indices in vistos for i in indices} <= set(conj.df.index[so_metade]))
```

(Se `C.preparar` descartar a coluna `radio` do frame sintético por não estar na `TABELA` do arquivo, acrescente `'radio': {'classe': 'tr069'}` às colunas da `TABELA` só neste teste, com uma cópia do dicionário.)

Em `tests/test_quantis.py`, classe `TestPrevisoes`, acrescentar:

```python
  def test_treinar_em_tudo_igual_a_none_e_metade_muda_a_previsao(self):
    conj = conjunto()
    tudo = pd.Series(True, index=conj.df.index)
    metade = pd.Series(np.arange(len(conj.df)) % 2 == 0, index=conj.df.index)
    a = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    b = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], treinar_em=tudo)
    c = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], treinar_em=metade)
    pd.testing.assert_frame_equal(a, b)
    self.assertEqual(sorted(c['_linha']), sorted(conj.df['_linha']))
    self.assertFalse(np.allclose(a['q50'].to_numpy(), c.loc[a.index, 'q50'].to_numpy()))

  def test_treinar_em_conta_as_linhas_de_treino(self):
    conj = conjunto()
    metade = pd.Series(np.arange(len(conj.df)) % 2 == 0, index=conj.df.index)
    vistos = []

    class Conta(Constante):
      def fit(self, X, y):
        vistos.append(set(X.index))
        return super().fit(X, y)

    Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], conformal=False,
                                  estimadores={0.5: Conta(), 0.9: Conta()}, treinar_em=metade)
    self.assertTrue(vistos)
    self.assertTrue(set().union(*vistos) <= set(conj.df.index[metade]))
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_avaliacao.py'` e `-p 'test_quantis.py'`
Expected: `TypeError: ... unexpected keyword argument 'treinar_em'`.

- [ ] **Step 2: Implementar**

`src/ml/core/avaliacao.py`:
- `prever_fora_do_fold(..., excluir_limitados: bool = False, treinar_em=None)`; na docstring, acrescentar: "`treinar_em` (série booleana alinhada a `df`, ou None para todas) restringe as linhas de treino de cada fold; as linhas de teste não mudam."
- No ramo `if isinstance(denominador, dict):`, repassar: `return _prever_por_banda(..., ao_ajustar, denominador, treinar_em)`.
- Depois de `limitado = ...` (antes do laço), acrescentar:

```python
  fora_do_treino = pd.Series(False, index=sub.index)
  if treinar_em is not None:
    fora_do_treino = ~treinar_em.reindex(sub.index, fill_value=False).astype(bool)
```

- No laço, `treino = ~limitado.loc[fold.X_train.index].to_numpy()` vira
  `treino = ~(limitado | fora_do_treino).loc[fold.X_train.index].to_numpy()`.

- `_prever_por_banda(df, colunas, y_col, vazadas, arvores, min_teste, min_treino, estimador, ao_ajustar, denominador: dict, treinar_em=None)`: as duas chamadas internas a `prever_fora_do_fold` passam `treinar_em=treinar_em`.

`src/ml/core/quantis.py`, `prever_quantis_fora_do_fold(..., conformal: bool = True, treinar_em=None)`; docstring: mesma frase. Antes do laço:

```python
  dentro = pd.Series(True, index=sub.index)
  if treinar_em is not None:
    dentro = treinar_em.reindex(sub.index, fill_value=False).astype(bool)
```

No laço, logo no começo de cada fold:

```python
    usar = dentro.loc[fold.X_train.index].to_numpy()
    X_treino, y_treino = fold.X_train[usar], fold.y_train[usar]
    sites_treino = np.asarray(fold.train_site_ids)[usar]
```

e trocar `fold.X_train, fold.y_train` por `X_treino, y_treino` no `modelo.fit` e na chamada de `correcao_conformal` (que passa a receber `sites_treino` no lugar de `fold.train_site_ids`). Se `fold.train_site_ids` não for alinhado a `fold.X_train` (conferir em `core/splits.py`), use `sub['_site'].loc[fold.X_train.index].to_numpy()[usar]`.

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_avaliacao.py'`, `-p 'test_quantis.py'`, `-p 'test_pacote.py'` e `-p 'test_completa.py'`
Expected: `OK` nos quatro (os dois últimos confirmam que o padrão `None` não mudou nada).

- [ ] **Step 4: Commit**

```bash
git add src/ml/core/avaliacao.py src/ml/core/quantis.py tests/test_avaliacao.py tests/test_quantis.py
git commit -m "feat(core): previsões fora do fold aceitam restringir as linhas de treino"
```

---

### Task 1: `core/portao.py`

**Files:**
- Create: `src/ml/core/portao.py`
- Test: `tests/test_portao.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_portao.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import portao as T
from test_studio_features import TABELA, frame

RESULTADOS = {'melhor', 'pior', 'empate'}


def por_alvo(*resultados):
  return {alvo: {'veredito': {'resultado': r, 'motivo': 'x'}} for alvo, r in zip(T.ALVOS, resultados)}


class TestDecidir(unittest.TestCase):
  def test_pior_em_um_alvo_nao_promove(self):
    d = T.decidir(por_alvo('melhor', 'melhor', 'pior', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'pior'))
    self.assertIn('latency_ms', d['motivo'])

  def test_melhor_sem_pior_promove(self):
    d = T.decidir(por_alvo('empate', 'melhor', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (True, 'melhor'))
    self.assertIn('speedtest_up_mbps', d['motivo'])

  def test_so_empates_mantem(self):
    d = T.decidir(por_alvo('empate', 'empate', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'empate'))


class TestMesmaDefinicao(unittest.TestCase):
  def test_situacoes(self):
    self.assertEqual(T.situacao_mesma_definicao(['b', 'a'], ['a', 'b']), 'igual')
    self.assertEqual(T.situacao_mesma_definicao(['a', 'b', 'c'], ['a', 'b']), 'dado_novo')
    self.assertEqual(T.situacao_mesma_definicao(['a', 'c'], ['a', 'b']), 'dados_diferentes')
    self.assertEqual(T.situacao_mesma_definicao(['a'], ['a', 'b']), 'dados_diferentes')

  def test_decidir_dado_novo_promove_sem_pior(self):
    d = T.decidir_dado_novo(por_alvo('empate', 'empate', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (True, 'dado_novo'))
    d = T.decidir_dado_novo(por_alvo('melhor', 'empate', 'empate', 'pior'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'pior'))
    self.assertIn('jitter_ms', d['motivo'])

  def test_decisoes_sem_comparacao(self):
    for situacao in ('igual', 'dados_diferentes'):
      with self.subTest(situacao=situacao):
        d = T.decidir_sem_comparar(situacao)
        self.assertEqual((d['promover'], d['resultado']), (False, situacao))
    self.assertIn('ativar_mlflow.py', T.decidir_sem_comparar('dados_diferentes')['motivo'])


class TestComparar(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}

  def test_quatro_alvos_com_veredito(self):
    r = T.comparar(self.conjs, {'features': ['router_snr', 'router_signal_dbm', 'radio'], 'denominador': None},
                   {'features': ['router_snr'], 'denominador': None})
    self.assertEqual(list(r), list(T.ALVOS))
    for alvo in A.ALVOS_COM_TETO:
      self.assertIn('intervalo', r[alvo]['delta_mae'])
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)
    for alvo in ('latency_ms', 'jitter_ms'):
      self.assertIn('intervalo', r[alvo]['delta_pinball'])
      self.assertIsInstance(r[alvo]['cobertura'], float)
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)

  def test_definicao_contra_ela_mesma_tem_diferenca_zero(self):
    d = {'features': ['router_snr', 'radio'], 'denominador': None}
    r = T.comparar(self.conjs, d, d)
    self.assertEqual([r[a]['delta_mae']['valor'] for a in A.ALVOS_COM_TETO], [0.0, 0.0])
    self.assertEqual([r[a]['delta_pinball']['valor'] for a in ('latency_ms', 'jitter_ms')], [0.0, 0.0])

  def test_denominador_por_alvo_chega_na_previsao(self):
    den = {'speedtest_down_mbps': {'coluna': 'router_snr', 'radio': '5ghz'},
           'speedtest_up_mbps': {'coluna': 'router_snr', 'radio': '5ghz'}}
    sem = T.comparar(self.conjs, {'features': ['router_signal_dbm', 'radio'], 'denominador': None},
                     {'features': ['router_signal_dbm', 'radio'], 'denominador': None})
    com = T.comparar(self.conjs, {'features': ['router_signal_dbm', 'radio'], 'denominador': den},
                     {'features': ['router_signal_dbm', 'radio'], 'denominador': None})
    self.assertEqual(sem['speedtest_down_mbps']['delta_mae']['valor'], 0.0)
    self.assertNotEqual(com['speedtest_down_mbps']['delta_mae']['valor'], 0.0)

  def test_dado_novo_com_todo_o_dado_antigo_tem_diferenca_zero(self):
    d = {'features': ['router_snr', 'radio'], 'denominador': None}
    r = T.comparar_dado_novo(self.conjs, d, ids_antigos=['a.csv'])   # tudo é antigo: as duas receitas são iguais
    self.assertEqual(list(r), list(T.ALVOS))
    self.assertEqual([r[a]['delta_mae']['valor'] for a in A.ALVOS_COM_TETO], [0.0, 0.0])
    self.assertEqual([r[a]['delta_pinball']['valor'] for a in ('latency_ms', 'jitter_ms')], [0.0, 0.0])

  def test_dado_novo_compara_nas_mesmas_linhas(self):
    conjs = {alvo: C.preparar({'a.csv': frame(seed=1), 'b.csv': frame(seed=2)}, alvo, TABELA) for alvo in P.PREFIXOS}
    d = {'features': ['router_snr', 'router_signal_dbm'], 'denominador': None}
    r = T.comparar_dado_novo(conjs, d, ids_antigos=['a.csv'])
    for alvo in A.ALVOS_COM_TETO:
      self.assertEqual(r[alvo]['delta_mae']['n'], int(conjs[alvo].df[alvo].notna().sum()))
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao.py'`
Expected: erro de import (`cannot import name 'portao'`).

- [ ] **Step 3: Implementar**

`src/ml/core/portao.py`:

```python
"""Portão de promoção: decide se uma definição candidata substitui a ativa.

As duas definições são comparadas nas mesmas linhas: previsões fora do fold (LOGO por prédio) recalculadas
nos dados da candidata, com as mesmas funções da avaliação. Download e upload decidem pelo Δ MAE
(core_avaliacao.veredito_promocao, sem o "atende"); latência e jitter, pelo Δ pinball do p90 e pela cobertura
do p90 (core_quantis.veredito_quantis). Não importa o MLflow: src/ml/portao_mlflow.py lê o Registry, grava o
veredito e move o alias.
"""

from ml.core import avaliacao as core_avaliacao
from ml.core import completa as core_completa
from ml.core import quantis as core_quantis

ALVOS = tuple(core_avaliacao.ALVOS_COM_TETO) + tuple(core_quantis.ALVOS_QUANTILICOS)


def _prever_pontual(conj, definicao: dict):
  usadas, vazadas = core_completa.presentes(conj, definicao['features'])
  return core_avaliacao.prever_fora_do_fold(conj.df, usadas, conj.alvo, vazadas,
                                            denominador=(definicao.get('denominador') or {}).get(conj.alvo))


def comparar(conjs: dict, candidata: dict, ativa: dict) -> dict:
  """{alvo: bloco} com a diferença candidata − ativa e o veredito de cada alvo.

  `conjs`: {alvo: Conjunto} dos quatro alvos. `candidata` e `ativa`: {'features', 'denominador'}, com o
  denominador no formato de modelos.json ({alvo: coluna} ou {alvo: {'coluna', 'radio'}}) ou None.
  """
  por_alvo = {}
  for alvo in core_avaliacao.ALVOS_COM_TETO:
    delta = core_avaliacao.delta_mae(_prever_pontual(conjs[alvo], candidata), _prever_pontual(conjs[alvo], ativa))
    por_alvo[alvo] = {'delta_mae': delta, 'veredito': core_avaliacao.veredito_promocao(delta)}
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    nova = core_completa.prever_quantis(conjs[alvo], candidata['features'])
    delta = core_quantis.delta_pinball(nova, core_completa.prever_quantis(conjs[alvo], ativa['features']))
    cobertura = round(core_quantis.cobertura(nova['y'], nova['q90']), 4)
    por_alvo[alvo] = {'delta_pinball': delta, 'cobertura': cobertura,
                      'veredito': core_quantis.veredito_quantis(delta, cobertura)}
  return por_alvo


def decidir(por_alvo: dict) -> dict:
  """Promove se nenhum alvo piorar e pelo menos um melhorar; empate mantém a ativa."""
  resultados = {alvo: bloco['veredito']['resultado'] for alvo, bloco in por_alvo.items()}
  piores = [a for a, r in resultados.items() if r == 'pior']
  melhores = [a for a, r in resultados.items() if r == 'melhor']
  if piores:
    return {'promover': False, 'resultado': 'pior', 'motivo': f'a candidata piora em {", ".join(piores)}'}
  if melhores:
    return {'promover': True, 'resultado': 'melhor',
            'motivo': f'a candidata melhora em {", ".join(melhores)} sem piorar nos outros alvos'}
  return {'promover': False, 'resultado': 'empate',
          'motivo': 'empate nos quatro alvos: com estes prédios não dá para separar as duas versões; a ativa fica'}


def situacao_mesma_definicao(fp_candidata, fp_ativa) -> str:
  """Re-treino da mesma definição: 'igual' (mesmos dados), 'dado_novo' (os da ativa e mais algum) ou
  'dados_diferentes' (não contém os da ativa)."""
  candidata, ativa = set(fp_candidata), set(fp_ativa)
  if candidata == ativa:
    return 'igual'
  return 'dado_novo' if candidata > ativa else 'dados_diferentes'


def decidir_sem_comparar(situacao: str) -> dict:
  """Mesma definição em que o portão não compara: mantém a ativa e explica."""
  if situacao == 'igual':
    return {'promover': False, 'resultado': 'igual', 'motivo': 'mesma definição e mesmos dados da ativa: nada a trocar'}
  return {'promover': False, 'resultado': 'dados_diferentes',
          'motivo': 'mesma definição com dados que não contêm os da ativa: o portão não compara; '
                    'se for o caso, troque à mão com src/ml/ativar_mlflow.py'}


def _treino(conj, ids_antigos) -> 'pd.Series':
  return conj.df['_ds'].isin(list(ids_antigos))


def comparar_dado_novo(conjs: dict, definicao: dict, ids_antigos) -> dict:
  """Mesma receita, dois treinos: só as linhas dos datasets `ids_antigos` ("ativa") contra todas
  ("candidata"). Mesmo formato de `comparar`; as previsões são das mesmas linhas (LOGO por prédio)."""
  por_alvo = {}
  for alvo in core_avaliacao.ALVOS_COM_TETO:
    conj = conjs[alvo]
    usadas, vazadas = core_completa.presentes(conj, definicao['features'])
    den = (definicao.get('denominador') or {}).get(alvo)
    com_tudo = core_avaliacao.prever_fora_do_fold(conj.df, usadas, alvo, vazadas, denominador=den)
    so_antigo = core_avaliacao.prever_fora_do_fold(conj.df, usadas, alvo, vazadas, denominador=den,
                                                   treinar_em=_treino(conj, ids_antigos))
    delta = core_avaliacao.delta_mae(com_tudo, so_antigo)
    por_alvo[alvo] = {'delta_mae': delta, 'veredito': core_avaliacao.veredito_promocao(delta)}
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    conj = conjs[alvo]
    usadas, vazadas = core_completa.presentes(conj, definicao['features'])
    com_tudo = core_quantis.prever_quantis_fora_do_fold(conj.df, usadas, alvo, vazadas)
    so_antigo = core_quantis.prever_quantis_fora_do_fold(conj.df, usadas, alvo, vazadas,
                                                         treinar_em=_treino(conj, ids_antigos))
    delta = core_quantis.delta_pinball(com_tudo, so_antigo)
    cobertura = round(core_quantis.cobertura(com_tudo['y'], com_tudo['q90']), 4)
    por_alvo[alvo] = {'delta_pinball': delta, 'cobertura': cobertura,
                      'veredito': core_quantis.veredito_quantis(delta, cobertura)}
  return por_alvo


def decidir_dado_novo(por_alvo: dict) -> dict:
  """Re-treino com dado novo: promove se nenhum alvo piorar. Mais dado da mesma receita é a expectativa;
  com 6 prédios, exigir "melhor" deixaria a ativa presa no dado velho."""
  piores = [a for a, b in por_alvo.items() if b['veredito']['resultado'] == 'pior']
  if piores:
    return {'promover': False, 'resultado': 'pior', 'motivo': f'o dado novo piora {", ".join(piores)}'}
  return {'promover': True, 'resultado': 'dado_novo',
          'motivo': 'mesma definição com dado novo, sem piorar nenhum alvo'}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao.py'`
Expected: `OK` (11 testes). Se `test_denominador_por_alvo_chega_na_previsao` falhar porque o `frame()` sintético não tem linhas de 5 GHz suficientes para o modelo de eficiência, troque `'radio': '5ghz'` por um denominador simples (`{'speedtest_down_mbps': 'router_snr', 'speedtest_up_mbps': 'router_snr'}`) e mantenha a asserção.

- [ ] **Step 5: Commit**

```bash
git add src/ml/core/portao.py tests/test_portao.py
git commit -m "feat(core): comparação e decisão do portão de promoção"
```

---

### Task 1b: `core/degradacao.py`

**Files:**
- Create: `src/ml/core/degradacao.py`
- Test: `tests/test_degradacao.py`

- [ ] **Step 1: Testes**

`tests/test_degradacao.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import degradacao as D
from ml.core import pacote as P
from test_studio_features import TABELA, frame

FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
ZERO = {'down_mae': 0.0, 'up_mae': 0.0, 'lat_pinball_q90': 0.0, 'jit_pinball_q90': 0.0}
ALTO = {chave: 1e9 for chave in ZERO}


class TestMedir(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    antigos = {alvo: C.preparar({'a.csv': frame(seed=1)}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(antigos, FEATURES, None)
    cls.conjs = {alvo: C.preparar({'a.csv': frame(seed=1), 'b.csv': frame(seed=2)}, alvo, TABELA)
                 for alvo in P.PREFIXOS}

  def test_mede_so_as_linhas_novas(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], ALTO)
    self.assertEqual(set(r), set(D.SAIDA))
    for alvo, bloco in r.items():
      df = self.conjs[alvo].df
      self.assertEqual(bloco['n'], int(((df['_ds'] == 'b.csv') & df[alvo].notna()).sum()))
      self.assertEqual(bloco['datasets'], ['b.csv'])
      self.assertIsNotNone(bloco['intervalo'])
    self.assertEqual([r[a]['resultado'] for a in A.ALVOS_COM_TETO], ['estavel', 'estavel'])
    self.assertIn('cobertura', r['latency_ms'])

  def test_erro_acima_do_esperado_degrada(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], ZERO)
    self.assertEqual(r['speedtest_down_mbps']['resultado'], 'degradou')
    self.assertIn('esperado', r['speedtest_down_mbps']['motivo'])
    self.assertTrue(D.degradou(r))

  def test_sem_linhas_novas_volta_vazio(self):
    self.assertEqual(D.medir(self.pacote, self.conjs, ['a.csv', 'b.csv'], ALTO), {})
    self.assertFalse(D.degradou({}))

  def test_sem_esperado_vazao_nao_degrada_pelo_erro(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], {})
    self.assertEqual([r[a]['resultado'] for a in A.ALVOS_COM_TETO], ['estavel', 'estavel'])
    self.assertIsNone(r['speedtest_down_mbps']['esperado'])


if __name__ == '__main__':
  unittest.main()
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_degradacao.py'`
Expected: erro de import.

- [ ] **Step 2: Implementar**

`src/ml/core/degradacao.py`:

```python
"""Degradação da versão ativa: o erro do pacote implantado nas linhas que ele nunca viu.

Quando chega dado novo, o pacote da ativa (treinado só com os datasets dela) prevê as linhas dos datasets
novos, como faria em produção. O erro medido é comparado com o esperado, a validação cruzada gravada no run
da ativa: MAE de download e upload, pinball do p90 de latência e jitter. "degradou" quando o intervalo de 90%
do erro novo fica todo acima do esperado, ou quando a cobertura do p90 nas linhas novas sai da faixa.

O esperado vem de LOGO (prédios que o modelo não viu): para dado novo de um prédio que a ativa já viu, é uma
referência conservadora. Download e upload são cortados no teto de WAN do prédio, como na avaliação (o pacote
não corta). Não decide a promoção: vai para o relatório do portão.
"""

import numpy as np

from ml.core import avaliacao as core_avaliacao
from ml.core import pacote as core_pacote
from ml.core import quantis as core_quantis
from ml.core.sites import teto_wan

SAIDA = {'speedtest_down_mbps': 'download_mbps', 'speedtest_up_mbps': 'upload_mbps',
         'latency_ms': 'latency_ms_p90', 'jitter_ms': 'jitter_ms_p90'}
ESPERADO = {'speedtest_down_mbps': 'down_mae', 'speedtest_up_mbps': 'up_mae',
            'latency_ms': 'lat_pinball_q90', 'jitter_ms': 'jit_pinball_q90'}


def _erro(alvo: str, y: np.ndarray, previsto: np.ndarray) -> np.ndarray:
  """Erro por linha: absoluto na vazão, pinball do p90 em latência e jitter."""
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    return np.abs(y - previsto)
  e = y - previsto
  return np.maximum(0.9 * e, -0.1 * e)


def medir(pacote, conjs: dict, ids_antigos, esperado: dict) -> dict:
  """{alvo: bloco} com o erro do pacote nas linhas de datasets fora de `ids_antigos`.

  `esperado`: métricas do run da ativa (nomes em ESPERADO); a que faltar não entra na comparação. Alvo sem
  linhas novas fica de fora.
  """
  antigos = list(ids_antigos)
  saida = {}
  for alvo, coluna in SAIDA.items():
    df = conjs[alvo].df
    novas = df[~df['_ds'].isin(antigos) & df[alvo].notna()]
    if novas.empty:
      continue
    previsto = core_pacote.prever(pacote, novas)[0][coluna].to_numpy(dtype=float)
    y = novas[alvo].to_numpy(dtype=float)
    if alvo in core_avaliacao.ALVOS_COM_TETO:
      tetos = np.array([teto_wan(s, alvo) or np.inf for s in novas['_site']], dtype=float)
      previsto = np.minimum(previsto, tetos)
    erro = _erro(alvo, y, previsto)
    amostras = core_avaliacao.reamostras(novas['_pos'], novas['_site'])
    intervalo = core_avaliacao._intervalo([erro[i].mean() for i in amostras])
    referencia = esperado.get(ESPERADO[alvo])
    bloco = {'n': int(len(novas)), 'datasets': sorted(novas['_ds'].unique()), 'metrica': ESPERADO[alvo],
             'erro': round(float(erro.mean()), 4), 'intervalo': intervalo,
             'esperado': None if referencia is None else round(float(referencia), 4)}
    motivos = []
    if bloco['esperado'] is not None and intervalo is not None and intervalo[0] > bloco['esperado']:
      motivos.append(f"erro {bloco['erro']} (90%: {intervalo[0]} a {intervalo[1]}) acima do esperado "
                     f"{bloco['esperado']}")
    if alvo in core_quantis.ALVOS_QUANTILICOS:
      bloco['cobertura'] = round(core_quantis.cobertura(y, previsto), 4)
      lo, hi = core_quantis.FAIXA_COBERTURA
      if not lo <= bloco['cobertura'] <= hi:
        motivos.append(f"cobertura do p90 {bloco['cobertura']} fora da faixa de {lo} a {hi}")
    bloco['resultado'] = 'degradou' if motivos else 'estavel'
    bloco['motivo'] = '; '.join(motivos) or 'erro dentro do esperado'
    saida[alvo] = bloco
  return saida


def degradou(blocos: dict) -> bool:
  return any(b['resultado'] == 'degradou' for b in blocos.values())
```

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_degradacao.py'`
Expected: `OK` (4 testes). Se `core_pacote.prever` reclamar de colunas ausentes no frame sintético, confira `pacote.receita['entradas']` contra `conjs[alvo].df.columns` e ajuste `FEATURES` para colunas que o `frame()` de `test_studio_features` tem.

- [ ] **Step 4: Commit**

```bash
git add src/ml/core/degradacao.py tests/test_degradacao.py
git commit -m "feat(core): erro da versão ativa nas linhas novas contra o esperado"
```

---

### Task 2: `registry_mlflow` lê uma versão e grava as tags do portão

**Files:**
- Modify: `src/ml/core/registry_mlflow.py`
- Test: `tests/test_registry_mlflow.py`

- [ ] **Step 1: Testes**

Acrescentar a `tests/test_registry_mlflow.py`, antes do bloco `if __name__ == '__main__':`:

```python
class TestInfoVersao(ComBanco):
  def test_info_e_mais_recente(self):
    self.registrar('v1')
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.assertEqual(G.versao_mais_recente(), 2)
    info = G.info_versao(2)
    self.assertEqual((info['versao'], info['definicao'], info['fingerprints']), (2, 'v5', ['abc', 'def', 'ghi']))
    self.assertTrue(info['run_id'])

  def test_sem_versoes_e_versao_inexistente(self):
    self.modelo()
    with self.assertRaisesRegex(ValueError, 'nenhuma versão'):
      G.versao_mais_recente()
    self.registrar()
    with self.assertRaisesRegex(ValueError, 'versão 7'):
      G.info_versao(7)

  def test_marcar_portao(self):
    self.registrar()
    G.marcar_portao(1, {'portao': 'melhor', 'portao_contra': 3})
    tags = G.core_registro_mlflow.cliente().get_model_version(G.NOME_MODELO, '1').tags
    self.assertEqual((tags['portao'], tags['portao_contra']), ('melhor', '3'))
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'`
Expected: erros (`info_versao` não existe).

- [ ] **Step 2: Implementar**

Em `src/ml/core/registry_mlflow.py`, depois de `versao_da_definicao`:

```python
def versao_mais_recente() -> int:
  """O maior número de versão registrada. ValueError se não houver nenhuma."""
  achadas = core_registro_mlflow.cliente().search_model_versions(f"name='{NOME_MODELO}'")
  if not achadas:
    raise ValueError(f'nenhuma versão registrada de {NOME_MODELO!r}; rode src/ml/versao_mlflow.py')
  return max(int(v.version) for v in achadas)


def info_versao(versao: int) -> dict:
  """{'versao', 'definicao', 'run_id', 'fingerprints'} de uma versão registrada. ValueError se não existir."""
  cli = core_registro_mlflow.cliente()
  try:
    v = cli.get_model_version(NOME_MODELO, str(versao))
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise ValueError(f'{NOME_MODELO!r} não tem a versão {versao}') from erro
    raise
  return {'versao': int(v.version), 'definicao': v.tags.get('definicao'), 'run_id': v.run_id,
          'fingerprints': [f for f in (v.tags.get('fingerprints') or '').split(',') if f]}


def marcar_portao(versao: int, tags: dict) -> None:
  """Grava as tags do veredito do portão na versão registrada."""
  cli = core_registro_mlflow.cliente()
  for chave, valor in tags.items():
    cli.set_model_version_tag(NOME_MODELO, str(versao), chave, str(valor))
```

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'`
Expected: `OK`. Se `search_model_versions` sem o modelo registrado levantar em vez de devolver lista vazia, embrulhe a busca em `try/except MlflowException` com `_AUSENTE` e trate como lista vazia.

- [ ] **Step 4: Commit**

```bash
git add src/ml/core/registry_mlflow.py tests/test_registry_mlflow.py
git commit -m "feat(core): leitura de versão registrada e tags do portão no Registry"
```

---

### Task 3: comando `portao_mlflow.py`

**Files:**
- Create: `src/ml/portao_mlflow.py`
- Test: `tests/test_portao_mlflow.py`

- [ ] **Step 1: Testes**

`tests/test_portao_mlflow.py`:

```python
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

import mlflow

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import portao_mlflow as M
from ml.core import portao as T
from test_registry_mlflow import ComBanco, G

DEN = {'speedtest_down_mbps': {'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'}}
REGISTRO = {'versoes': {'v1': {'features': ['a']}, 'v5': {'features': ['a', 'b'], 'denominador': DEN}}}
DESCOBERTOS = [{'id': 'a.zip', 'fingerprint': 'abc', 'usable': True},
               {'id': 'b.zip', 'fingerprint': 'def', 'usable': True},
               {'id': 'c.zip', 'fingerprint': 'ghi', 'usable': True}]


def por_alvo(*resultados):
  return {alvo: {'veredito': {'resultado': r, 'motivo': 'x'}} for alvo, r in zip(T.ALVOS, resultados)}


class TestPortao(ComBanco):
  def setUp(self):
    super().setUp()
    self.m = {}
    for nome, alvo, extra in (
        ('registro', (M.core_modelos, 'carregar'), {'return_value': REGISTRO}),
        ('descobertos', (M.core_carga, 'descobertos'), {'return_value': DESCOBERTOS}),
        ('carregar', (M.core_carga, 'carregar'), {'side_effect': lambda alvo, ids=None: mock.Mock(alvo=alvo)}),
        ('comparar', (M.core_portao, 'comparar'), {'return_value': por_alvo('melhor', 'empate', 'empate', 'empate')}),
        ('dado_novo', (M.core_portao, 'comparar_dado_novo'),
         {'return_value': por_alvo('empate', 'empate', 'empate', 'empate')}),
        ('degradacao', (M.core_degradacao, 'medir'),
         {'return_value': {'speedtest_down_mbps': {'resultado': 'degradou', 'motivo': 'x'}}}),
        ('pacote', (M.core_pacote_mlflow, 'carregar'), {'return_value': 'pacote-da-ativa'})):
      p = mock.patch.object(*alvo, **extra)
      self.m[nome] = p.start()
      self.addCleanup(p.stop)
    for chave in ('VERSAO', 'SIMULAR'):
      os.environ.pop(chave, None)

  def rodar(self, **env) -> str:
    saida = io.StringIO()
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(saida):
      M.main()
    return saida.getvalue()

  def tags_run(self, versao):
    return G.core_registro_mlflow.cliente().get_run(G.info_versao(versao)['run_id']).data.tags

  def relatorio(self, versao):
    caminho = mlflow.artifacts.download_artifacts(run_id=G.info_versao(versao)['run_id'],
                                                  artifact_path='portao.json', dst_path=self.tmp)
    with open(caminho, encoding='utf-8') as f:
      return json.load(f)

  def ativa_v1_candidata_v5(self):
    self.registrar('v1')
    G.ativar(1)
    self.registrar('v5')

  def test_sem_ativa_promove_a_primeira(self):
    self.registrar('v5')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(1)['portao'], 'primeira')
    self.assertEqual(self.tags_run(1)['portao_contra'], 'nenhuma')
    self.m['comparar'].assert_not_called()

  def test_candidata_ja_ativa_nao_grava(self):
    self.registrar('v5')
    G.ativar(1)
    self.assertIn('já é a ativa', self.rodar())
    self.assertNotIn('portao', self.tags_run(1))

  def test_melhor_promove_e_grava_o_veredito(self):
    self.ativa_v1_candidata_v5()
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 2)
    tags = self.tags_run(2)
    self.assertEqual((tags['portao'], tags['portao_promovida'], tags['portao_contra'], tags['portao_simulado']),
                     ('melhor', 'sim', '1', 'nao'))
    versao = G.core_registro_mlflow.cliente().get_model_version(G.NOME_MODELO, '2').tags
    self.assertEqual((versao['portao'], versao['portao_contra']), ('melhor', '1'))
    rel = self.relatorio(2)
    self.assertTrue(rel['decisao']['promover'])
    self.assertEqual(rel['ativa']['definicao'], 'v1')
    self.assertIn('auxiliares', rel)
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.zip', 'b.zip'])
    self.m['degradacao'].assert_not_called()   # mesmos datasets: não há linha nova
    self.assertEqual(tags['portao_degradacao'], 'sem_dado_novo')
    candidata, ativa = self.m['comparar'].call_args.args[1:]
    self.assertEqual(candidata, {'features': ['a', 'b'], 'denominador': DEN})
    self.assertEqual(ativa, {'features': ['a'], 'denominador': None})

  def test_outra_definicao_com_dado_novo_mede_a_degradacao(self):
    self.m['degradacao'].return_value = {'speedtest_down_mbps': {'resultado': 'estavel', 'motivo': 'x'}}
    self.registrar('v1')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(self.m['degradacao'].call_args.args[2], ['a.zip', 'b.zip'])
    self.assertEqual(self.tags_run(2)['portao_degradacao'], 'nao')

  def test_pior_mantem_a_ativa(self):
    self.m['comparar'].return_value = por_alvo('melhor', 'pior', 'empate', 'empate')
    self.ativa_v1_candidata_v5()
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual((self.tags_run(2)['portao'], self.tags_run(2)['portao_promovida']), ('pior', 'nao'))

  def test_simular_grava_sem_mover_o_alias(self):
    self.ativa_v1_candidata_v5()
    self.rodar(SIMULAR='1')
    self.assertEqual(G.ativa()['versao'], 1)
    tags = self.tags_run(2)
    self.assertEqual((tags['portao'], tags['portao_promovida'], tags['portao_simulado']), ('melhor', 'nao', 'sim'))

  def test_mesma_definicao_com_dado_novo_compara_os_dois_treinos(self):
    self.registrar('v5')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 2)
    self.assertEqual(self.tags_run(2)['portao'], 'dado_novo')
    self.m['comparar'].assert_not_called()
    conjs, definicao = self.m['dado_novo'].call_args.args
    self.assertEqual(definicao, {'features': ['a', 'b'], 'denominador': DEN})
    self.assertEqual(self.m['dado_novo'].call_args.kwargs['ids_antigos'], ['a.zip', 'b.zip'])
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.zip', 'b.zip', 'c.zip'])
    pacote, _, antigos, _ = self.m['degradacao'].call_args.args
    self.assertEqual((pacote, antigos), ('pacote-da-ativa', ['a.zip', 'b.zip']))
    self.assertEqual(self.m['pacote'].call_args.args[0], f'models:/{G.NOME_MODELO}/1')
    self.assertEqual(self.tags_run(2)['portao_degradacao'], 'sim')
    self.assertIn('speedtest_down_mbps', self.relatorio(2)['degradacao'])

  def test_dado_novo_que_piora_nao_promove(self):
    self.m['dado_novo'].return_value = por_alvo('empate', 'pior', 'empate', 'empate')
    self.registrar('v5')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(2)['portao'], 'pior')

  def test_mesma_definicao_e_mesmos_dados_nao_carrega(self):
    self.registrar('v5')
    G.ativar(1)
    self.registrar('v5')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(2)['portao'], 'igual')
    self.m['carregar'].assert_not_called()

  def test_dado_da_candidata_fora_de_data_para_antes_de_carregar(self):
    self.registrar('v1')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['zzz'], 'p1')
    with self.assertRaises(SystemExit) as erro:
      self.rodar()
    self.assertIn('data/', str(erro.exception))
    self.m['carregar'].assert_not_called()
    self.assertEqual(G.ativa()['versao'], 1)

  def test_versao_escolhida_e_invalida(self):
    self.ativa_v1_candidata_v5()
    self.registrar('v5')
    self.rodar(VERSAO='2')
    self.assertEqual(G.ativa()['versao'], 2)
    self.assertNotIn('portao', self.tags_run(3))
    for valor, trecho in (('x', 'número'), ('9', 'versão 9')):
      with self.subTest(valor=valor):
        with self.assertRaises(SystemExit) as erro:
          self.rodar(VERSAO=valor)
        self.assertIn(trecho, str(erro.exception))


if __name__ == '__main__':
  unittest.main()
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao_mlflow.py'`
Expected: erro de import (`No module named 'ml.portao_mlflow'`).

- [ ] **Step 2: Implementar**

`src/ml/portao_mlflow.py`:

```python
"""Portão de promoção: decide se uma versão registrada de 'qoe-wifi' substitui a ativa (alias 'ativo').

VERSAO=<n> escolhe a candidata (padrão: a versão registrada mais recente, a que versao_mlflow.py acabou de
gravar). As duas definições são comparadas nos dados da candidata (core/portao.py): download e upload pelo
Δ MAE, latência e jitter pelo Δ pinball e pela cobertura do p90. Promove se nenhum alvo piorar e pelo menos
um melhorar. A mesma definição com dado novo é comparada consigo mesma treinada só com o dado da ativa, e é
promovida se nenhum alvo piorar; sem versão ativa, a candidata é promovida. Quando a candidata traz
datasets que a ativa não viu, mede também a degradação da ativa: o erro do pacote dela nessas linhas contra o
esperado (core/degradacao.py), só informativo. SIMULAR=1 grava o veredito sem mover o alias. O veredito fica no run da candidata (tags portao_*
e portao.json) e na versão registrada (tags portao e portao_contra). O código de saída é 0 tanto para
"promovida" quanto para "mantida".

  venv/bin/python src/ml/portao_mlflow.py
  VERSAO=6 venv/bin/python src/ml/portao_mlflow.py
  SIMULAR=1 VERSAO=4 venv/bin/python src/ml/portao_mlflow.py
"""

import json
import os
import sys
from datetime import date

import mlflow

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import degradacao as core_degradacao
from ml.core import modelos as core_modelos
from ml.core import pacote as core_pacote
from ml.core import pacote_mlflow as core_pacote_mlflow
from ml.core import portao as core_portao
from ml.core import registro_mlflow as core_registro_mlflow
from ml.core import registry_mlflow as core_registry

AUXILIARES = ('comodo_nota', 'comodo_lo90', 'comodo_hi90', 'atende_completo')


def _definicao(registro: dict, nome: str) -> dict:
  core_registry.escolher_definicao(nome, registro)   # sai com mensagem se a definição não existir
  versao = registro['versoes'][nome]
  return {'features': list(versao['features']), 'denominador': versao.get('denominador')}


def _ids(fingerprints: list) -> list:
  """Ids em data/ dos datasets da candidata, na ordem dos fingerprints."""
  por_fp = {d['fingerprint']: d['id'] for d in core_carga.descobertos() if d.get('usable')}
  faltam = [f for f in fingerprints if f not in por_fp]
  if faltam:
    raise SystemExit(f'os dados da candidata não estão em data/ (fingerprints {faltam}): '
                     'o portão não tem como reproduzi-los')
  return [por_fp[f] for f in fingerprints]


def _antigos(ids: list, candidata: dict, ativa: dict) -> list:
  """Ids da candidata cujo dataset a ativa já viu (os outros são o dado novo)."""
  vistos = set(ativa['fingerprints'])
  return [i for i, fp in zip(ids, candidata['fingerprints']) if fp in vistos]


def _degradacao(ativa: dict, conjs: dict, antigos: list) -> dict:
  """Erro do pacote da ativa nas linhas que ele nunca viu, contra o esperado gravado no run dela."""
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  pacote = core_pacote_mlflow.carregar(f"models:/{core_registry.NOME_MODELO}/{ativa['versao']}")
  esperado = core_registro_mlflow.cliente().get_run(ativa['run_id']).data.metrics
  return core_degradacao.medir(pacote, conjs, antigos, esperado)


def _auxiliares(cli, run_id: str) -> dict:
  metricas = cli.get_run(run_id).data.metrics
  return {chave: metricas.get(chave) for chave in AUXILIARES}


def gravar(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool, degradacao=None) -> None:
  """portao.json e tags no run da candidata; tags na versão registrada."""
  cli = core_registro_mlflow.cliente()
  contra = str(ativa['versao']) if ativa else 'nenhuma'
  relatorio = {
    'data': date.today().isoformat(), 'candidata': candidata, 'ativa': ativa, 'decisao': decisao,
    'simulado': simular, 'por_alvo': por_alvo, 'degradacao': degradacao,
    'auxiliares': {'candidata': _auxiliares(cli, candidata['run_id']),
                   'ativa': _auxiliares(cli, ativa['run_id']) if ativa else None,
                   'nota': 'métricas gravadas em cada run, não decidem; podem ser de dados diferentes'}}
  # json com default=float: os blocos do core podem trazer números do numpy.
  cli.log_dict(candidata['run_id'], json.loads(json.dumps(relatorio, default=float)), 'portao.json')
  tags = {'portao': decisao['resultado'], 'portao_promovida': 'sim' if decisao['promover'] and not simular else 'nao',
          'portao_contra': contra, 'portao_simulado': 'sim' if simular else 'nao',
          'portao_degradacao': ('sem_dado_novo' if degradacao is None
                                else 'sim' if core_degradacao.degradou(degradacao) else 'nao')}
  for chave, valor in tags.items():
    cli.set_tag(candidata['run_id'], chave, valor)
  core_registry.marcar_portao(candidata['versao'], {'portao': decisao['resultado'], 'portao_contra': contra})


def _imprimir(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool, degradacao=None) -> None:
  for alvo, bloco in (por_alvo or {}).items():
    print(f"  {alvo}: {bloco['veredito']['resultado']} ({bloco['veredito']['motivo']})")
  for alvo, bloco in (degradacao or {}).items():
    print(f"  degradação da ativa em {alvo}: {bloco['resultado']} ({bloco['motivo']})")
  contra = f"{ativa['versao']} ({ativa['definicao']})" if ativa else 'nenhuma'
  print(f"candidata {candidata['versao']} ({candidata['definicao']}) contra a ativa {contra}: "
        f"{decisao['resultado']}; {decisao['motivo']}")
  if decisao['promover'] and simular:
    print('SIMULAR=1: seria promovida, o alias não mudou')
  elif decisao['promover']:
    print(f"promovida: {core_registry.NOME_MODELO}@{core_registry.ALIAS} -> {candidata['versao']}")
  else:
    print('mantida: o alias não mudou')


def main():
  simular = os.environ.get('SIMULAR') == '1'
  numero = os.environ.get('VERSAO')
  if numero and not numero.isdigit():
    raise SystemExit(f'VERSAO={numero!r}: use o número da versão registrada')
  try:
    candidata = core_registry.info_versao(int(numero) if numero else core_registry.versao_mais_recente())
  except ValueError as erro:
    raise SystemExit(str(erro)) from erro
  try:
    ativa = core_registry.info_versao(core_registry.ativa()['versao'])
  except core_registry.SemVersaoAtiva:
    ativa = None
  if ativa and ativa['versao'] == candidata['versao']:
    print(f"a versão {candidata['versao']} ({candidata['definicao']}) já é a ativa: nada a decidir")
    return
  registro = core_modelos.carregar()
  def_candidata = _definicao(registro, candidata['definicao'])
  por_alvo, degradacao = None, None
  if ativa is None:
    decisao = {'promover': True, 'resultado': 'primeira', 'motivo': 'não há versão ativa'}
  elif candidata['definicao'] == ativa['definicao']:
    situacao = core_portao.situacao_mesma_definicao(candidata['fingerprints'], ativa['fingerprints'])
    if situacao != 'dado_novo':
      decisao = core_portao.decidir_sem_comparar(situacao)
    else:
      ids = _ids(candidata['fingerprints'])
      antigos = _antigos(ids, candidata, ativa)
      print(f"{candidata['definicao']} com dado novo: treino só com {antigos} contra treino com {ids}")
      conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
      por_alvo = core_portao.comparar_dado_novo(conjs, def_candidata, ids_antigos=antigos)
      decisao = core_portao.decidir_dado_novo(por_alvo)
      degradacao = _degradacao(ativa, conjs, antigos)
  else:
    def_ativa = _definicao(registro, ativa['definicao'])
    ids = _ids(candidata['fingerprints'])
    print(f"comparando {candidata['definicao']} (versão {candidata['versao']}) com {ativa['definicao']} "
          f"(versão {ativa['versao']}) nos datasets {ids}")
    conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
    por_alvo = core_portao.comparar(conjs, def_candidata, def_ativa)
    decisao = core_portao.decidir(por_alvo)
    antigos = _antigos(ids, candidata, ativa)
    if len(antigos) < len(ids):
      degradacao = _degradacao(ativa, conjs, antigos)
  gravar(candidata, ativa, decisao, por_alvo, simular, degradacao)
  if decisao['promover'] and not simular:
    core_registry.ativar(candidata['versao'])
  _imprimir(candidata, ativa, decisao, por_alvo, simular, degradacao)


if __name__ == '__main__':
  main()
```

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao_mlflow.py'`
Expected: `OK` (11 testes). Nota: `from test_registry_mlflow import ComBanco, G` faz o `discover` rodar também os testes de `test_registry_mlflow` neste arquivo? Não: o unittest só coleta classes `TestCase` com métodos `test_*`; `ComBanco` não tem nenhum. Se aparecerem testes duplicados, troque por `import test_registry_mlflow as base` e use `base.ComBanco`.

- [ ] **Step 4: Commit**

```bash
git add src/ml/portao_mlflow.py tests/test_portao_mlflow.py
git commit -m "feat(pipeline): comando portao_mlflow decide, grava o veredito e move o alias"
```

---

### Task 4: documentação

**Files:**
- Modify: `README.md`, `CHANGELOG.md`, `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`, `src/ml/ativar_mlflow.py` (docstring)

- [ ] **Step 1: README (em inglês)**

Na lista de comandos, depois das linhas do `ativar_mlflow.py`:

```
venv/bin/python src/ml/portao_mlflow.py                            # promotion gate: latest registered version vs the active one
SIMULAR=1 VERSAO=4 venv/bin/python src/ml/portao_mlflow.py         # record the verdict without moving the alias
```

Na seção "MLflow", depois do item da versão ativa, acrescentar:

```
- `src/ml/portao_mlflow.py` is the promotion gate. It compares the candidate (`VERSAO=`, default: the latest registered version) with the active version on the candidate's data: out-of-fold predictions of both definitions on the same rows, download and upload by the MAE difference, latency and jitter by the p90 pinball difference and the p90 coverage (90% intervals, positions resampled within buildings). It promotes when no target gets worse and at least one gets better; a tie keeps the active version. The same definition retrained with more data is compared with itself trained only on the active version's datasets (same rows, leave-one-building-out) and promoted unless some target gets worse. The verdict is stored on the candidate run (tags `portao`, `portao_promovida`, `portao_contra`, `portao_simulado`, file `portao.json`, with the per-room ruler and "atende completo" of both runs as auxiliaries) and on the registered version (tags `portao`, `portao_contra`). When the candidate brings datasets the active version has not seen, the gate also measures degradation: the active package predicts those rows and its error (download/upload MAE capped at the WAN ceiling, latency/jitter p90 pinball and coverage) is compared with the cross-validation error stored in the active run (tag `portao_degradacao`, block `degradacao` in `portao.json`); it does not decide the promotion. `ativar_mlflow.py` stays for rollbacks.
```

- [ ] **Step 2: Docstring de `ativar_mlflow.py`**

Trocar "É a promoção manual até o portão de promoção existir." por "O caminho normal é o portão (src/ml/portao_mlflow.py); este comando fica para voltar uma versão ou forçar uma troca."

- [ ] **Step 3: CHANGELOG**

Acrescentar no topo uma entrada "Changelog — Portão de promoção", data 2026-11-11, no formato das outras (Por quê, Decisões, Mudanças). As decisões são as da tabela da seção 2 da spec; as mudanças, os arquivos das Tarefas 0 a 3. A seção "Efeito medido" entra na Tarefa 5.

- [ ] **Step 4: Inventário**

Em `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`, "Ordem proposta", o passo 5 ganha: "Feito em 2026-11-11: `core/portao.py` e `portao_mlflow.py` (spec `docs/superpowers/specs/2026-11-11-portao-promocao-design.md`)." Em "O que falta no MLflow", o item 5 (veredito de promoção) ganha "(feito em 2026-11-11: tags e `portao.json` no run da candidata)".

- [ ] **Step 5: Commit**

```bash
git add README.md CHANGELOG.md docs/pipeline/2026-11-10-inventario-studio-mlflow.md src/ml/ativar_mlflow.py
git commit -m "docs: portão de promoção"
```

---

### Task 5: conferência com dado real

Grava no MLflow da raiz (é o objetivo). Antes: `venv/bin/python src/ml/ativar_mlflow.py` deve mostrar a versão 5 (v5). Faça backup: `cp mlflow.db <scratchpad>/mlflow.db.antes-portao`.

- [ ] **Step 1: Já é a ativa**

Run: `VERSAO=5 venv/bin/python src/ml/portao_mlflow.py`
Expected: `a versão 5 (v5) já é a ativa: nada a decidir`.

- [ ] **Step 2: Simulação v4 contra v5**

Run: `SIMULAR=1 VERSAO=4 venv/bin/python src/ml/portao_mlflow.py 2>&1 | grep -v -i warn`
Expected: as quatro linhas por alvo, a decisão e "o alias não mudou" ou "seria promovida". Anotar o resultado de cada alvo. `ativar_mlflow.py` continua mostrando a 5.

- [ ] **Step 3: Promoção de verdade**

```bash
VERSAO=1 venv/bin/python src/ml/ativar_mlflow.py
VERSAO=5 venv/bin/python src/ml/portao_mlflow.py 2>&1 | grep -v -i warn
venv/bin/python src/ml/ativar_mlflow.py
```

Expected: o portão compara v5 com v1 nos dados da v5. Se promover, o alias volta para a 5. Se não promover (empate ou pior), anotar o motivo e voltar à mão: `VERSAO=5 venv/bin/python src/ml/ativar_mlflow.py`. **O alias termina na 5.**

- [ ] **Step 3b: Dado novo, com a Villa no papel de dado novo**

Os ids da versão 5 sem os dois arquivos da Villa:

```bash
SEM_VILLA=$(venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
from ml.core import carga as C, registry_mlflow as G
por_fp = {d['fingerprint']: d['id'] for d in C.descobertos() if d.get('usable')}
print(','.join(por_fp[f] for f in G.info_versao(5)['fingerprints'] if not por_fp[f].startswith('villa')))
EOF
)
echo "$SEM_VILLA"
MODELO=v5 DATASETS="$SEM_VILLA" venv/bin/python src/ml/versao_mlflow.py 2>&1 | tail -3
```

Expected: `versão registrada 6`. Então:

```bash
VERSAO=6 venv/bin/python src/ml/ativar_mlflow.py
VERSAO=5 venv/bin/python src/ml/portao_mlflow.py 2>&1 | grep -v -i warn
venv/bin/python src/ml/ativar_mlflow.py
```

Expected: "v5 com dado novo: treino só com [...] contra treino com [...]", os quatro vereditos e a decisão. Também as quatro linhas "degradação da ativa em ...": o erro da versão 6 (v5 sem a Villa) nas linhas da Villa contra o esperado; anotar. Se não promover, anotar o motivo (é um resultado: a Villa pioraria algum alvo) e voltar à mão com `VERSAO=5 venv/bin/python src/ml/ativar_mlflow.py`. **O alias termina na 5.** A versão 6 fica registrada (v5 sem a Villa), com o veredito do portão nas tags da 5.

- [ ] **Step 4: O veredito está gravado**

```bash
venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
from ml.core import registro_mlflow as R, registry_mlflow as G
cli = R.cliente()
for n in (4, 5):
  i = G.info_versao(n)
  tags = cli.get_run(i['run_id']).data.tags
  print(n, {k: v for k, v in tags.items() if k.startswith('portao')},
        cli.get_model_version(G.NOME_MODELO, str(n)).tags.get('portao'),
        [a.path for a in cli.list_artifacts(i['run_id']) if a.path == 'portao.json'])
EOF
```

Expected: as versões 4 e 5 com as tags do portão e `portao.json`.

- [ ] **Step 5: Efeito medido no CHANGELOG**

Acrescentar à entrada do portão a seção "Efeito medido" com: o resultado por alvo de v4 contra v5, de v5 contra v1 e da v5 com a Villa contra a v5 sem a Villa, a degradação da v5 sem a Villa nas linhas da Villa (erro contra o esperado, por alvo), o tempo de cada comparação, e o estado final do alias. Commit:

```bash
git add CHANGELOG.md
git commit -m "docs: efeito medido do portão de promoção no changelog"
```

---

### Task 6: suíte inteira e fechamento

- [ ] **Step 1:** `stat -c %Y mlflow.db` antes e depois de `venv/bin/python -m unittest discover -s tests 2>&1 | tail -5` e `node --test tests/js/logica.test.js 2>&1 | tail -5`. Expected: `OK`, todos `pass`, e o mesmo `stat` (os testes não tocam o banco da raiz).
- [ ] **Step 2:** `git log model-registry..HEAD --format=%B | grep -ci co-authored` imprime `0`.
- [ ] **Step 3:** Relatório final ao Lucas: o que foi feito, decisões tomadas durante a execução, o resultado real das comparações (Tarefa 5) e a pergunta sobre merge (as duas branches, `model-registry` e `portao-promocao`) e push.
