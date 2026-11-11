# Portão de promoção — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `venv/bin/python src/ml/portao_mlflow.py` decide se a versão registrada mais recente de `qoe-wifi` substitui a ativa, grava o veredito no run e na versão, e move o alias quando for o caso.

**Architecture:** `src/ml/core/portao.py` compara duas definições nas mesmas linhas (previsões fora do fold recalculadas nos dados da candidata) e decide, sem MLflow. `src/ml/core/registry_mlflow.py` ganha leitura de uma versão e tags de portão. `src/ml/portao_mlflow.py` é o comando: lê o Registry, chama o core, grava e promove.

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
  def test_mesmos_dados(self):
    d = T.decidir_mesma_definicao(['b', 'a'], ['a', 'b'])
    self.assertEqual((d['promover'], d['resultado']), (False, 'igual'))

  def test_dado_novo(self):
    d = T.decidir_mesma_definicao(['a', 'b', 'c'], ['a', 'b'])
    self.assertEqual((d['promover'], d['resultado']), (True, 'dado_novo'))
    self.assertIn('1', d['motivo'])

  def test_dados_que_nao_contem_os_da_ativa(self):
    for candidata in (['a', 'c'], ['a']):
      with self.subTest(candidata=candidata):
        d = T.decidir_mesma_definicao(candidata, ['a', 'b'])
        self.assertEqual((d['promover'], d['resultado']), (False, 'dados_diferentes'))
        self.assertIn('ativar_mlflow.py', d['motivo'])


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


def decidir_mesma_definicao(fp_candidata, fp_ativa) -> dict:
  """Re-treino da mesma definição: a validação cruzada nos mesmos dados daria diferença zero.

  Promove quando os dados da candidata contêm os da ativa e mais algum.
  """
  candidata, ativa = set(fp_candidata), set(fp_ativa)
  if candidata == ativa:
    return {'promover': False, 'resultado': 'igual',
            'motivo': 'mesma definição e mesmos dados da ativa: nada a trocar'}
  if candidata > ativa:
    return {'promover': True, 'resultado': 'dado_novo',
            'motivo': f'mesma definição treinada com os dados da ativa e mais {len(candidata - ativa)} dataset(s)'}
  return {'promover': False, 'resultado': 'dados_diferentes',
          'motivo': 'mesma definição com dados que não contêm os da ativa: o portão não compara; '
                    'se for o caso, troque à mão com src/ml/ativar_mlflow.py'}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao.py'`
Expected: `OK` (9 testes). Se `test_denominador_por_alvo_chega_na_previsao` falhar porque o `frame()` sintético não tem linhas de 5 GHz suficientes para o modelo de eficiência, troque `'radio': '5ghz'` por um denominador simples (`{'speedtest_down_mbps': 'router_snr', 'speedtest_up_mbps': 'router_snr'}`) e mantenha a asserção.

- [ ] **Step 5: Commit**

```bash
git add src/ml/core/portao.py tests/test_portao.py
git commit -m "feat(core): comparação e decisão do portão de promoção"
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
        ('comparar', (M.core_portao, 'comparar'), {'return_value': por_alvo('melhor', 'empate', 'empate', 'empate')})):
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
    candidata, ativa = self.m['comparar'].call_args.args[1:]
    self.assertEqual(candidata, {'features': ['a', 'b'], 'denominador': DEN})
    self.assertEqual(ativa, {'features': ['a'], 'denominador': None})

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

  def test_mesma_definicao_com_dado_novo_promove_sem_comparar(self):
    self.registrar('v5')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 2)
    self.assertEqual(self.tags_run(2)['portao'], 'dado_novo')
    self.m['comparar'].assert_not_called()
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
um melhorar. A mesma definição com dado novo é promovida sem comparação; sem versão ativa, a candidata é
promovida. SIMULAR=1 grava o veredito sem mover o alias. O veredito fica no run da candidata (tags portao_*
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

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import modelos as core_modelos
from ml.core import pacote as core_pacote
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


def _auxiliares(cli, run_id: str) -> dict:
  metricas = cli.get_run(run_id).data.metrics
  return {chave: metricas.get(chave) for chave in AUXILIARES}


def gravar(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool) -> None:
  """portao.json e tags no run da candidata; tags na versão registrada."""
  cli = core_registro_mlflow.cliente()
  contra = str(ativa['versao']) if ativa else 'nenhuma'
  relatorio = {
    'data': date.today().isoformat(), 'candidata': candidata, 'ativa': ativa, 'decisao': decisao,
    'simulado': simular, 'por_alvo': por_alvo,
    'auxiliares': {'candidata': _auxiliares(cli, candidata['run_id']),
                   'ativa': _auxiliares(cli, ativa['run_id']) if ativa else None,
                   'nota': 'métricas gravadas em cada run, não decidem; podem ser de dados diferentes'}}
  # json com default=float: os blocos do core podem trazer números do numpy.
  cli.log_dict(candidata['run_id'], json.loads(json.dumps(relatorio, default=float)), 'portao.json')
  tags = {'portao': decisao['resultado'], 'portao_promovida': 'sim' if decisao['promover'] and not simular else 'nao',
          'portao_contra': contra, 'portao_simulado': 'sim' if simular else 'nao'}
  for chave, valor in tags.items():
    cli.set_tag(candidata['run_id'], chave, valor)
  core_registry.marcar_portao(candidata['versao'], {'portao': decisao['resultado'], 'portao_contra': contra})


def _imprimir(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool) -> None:
  for alvo, bloco in (por_alvo or {}).items():
    print(f"  {alvo}: {bloco['veredito']['resultado']} ({bloco['veredito']['motivo']})")
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
  por_alvo = None
  if ativa is None:
    decisao = {'promover': True, 'resultado': 'primeira', 'motivo': 'não há versão ativa'}
  elif candidata['definicao'] == ativa['definicao']:
    decisao = core_portao.decidir_mesma_definicao(candidata['fingerprints'], ativa['fingerprints'])
  else:
    def_ativa = _definicao(registro, ativa['definicao'])
    ids = _ids(candidata['fingerprints'])
    print(f"comparando {candidata['definicao']} (versão {candidata['versao']}) com {ativa['definicao']} "
          f"(versão {ativa['versao']}) nos datasets {ids}")
    conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
    por_alvo = core_portao.comparar(conjs, def_candidata, def_ativa)
    decisao = core_portao.decidir(por_alvo)
  gravar(candidata, ativa, decisao, por_alvo, simular)
  if decisao['promover'] and not simular:
    core_registry.ativar(candidata['versao'])
  _imprimir(candidata, ativa, decisao, por_alvo, simular)


if __name__ == '__main__':
  main()
```

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_portao_mlflow.py'`
Expected: `OK` (8 testes). Nota: `from test_registry_mlflow import ComBanco, G` faz o `discover` rodar também os testes de `test_registry_mlflow` neste arquivo? Não: o unittest só coleta classes `TestCase` com métodos `test_*`; `ComBanco` não tem nenhum. Se aparecerem testes duplicados, troque por `import test_registry_mlflow as base` e use `base.ComBanco`.

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
- `src/ml/portao_mlflow.py` is the promotion gate. It compares the candidate (`VERSAO=`, default: the latest registered version) with the active version on the candidate's data: out-of-fold predictions of both definitions on the same rows, download and upload by the MAE difference, latency and jitter by the p90 pinball difference and the p90 coverage (90% intervals, positions resampled within buildings). It promotes when no target gets worse and at least one gets better; a tie keeps the active version. The same definition retrained with more data is promoted without comparison. The verdict is stored on the candidate run (tags `portao`, `portao_promovida`, `portao_contra`, `portao_simulado`, file `portao.json`, with the per-room ruler and "atende completo" of both runs as auxiliaries) and on the registered version (tags `portao`, `portao_contra`). `ativar_mlflow.py` stays for rollbacks.
```

- [ ] **Step 2: Docstring de `ativar_mlflow.py`**

Trocar "É a promoção manual até o portão de promoção existir." por "O caminho normal é o portão (src/ml/portao_mlflow.py); este comando fica para voltar uma versão ou forçar uma troca."

- [ ] **Step 3: CHANGELOG**

Acrescentar no topo uma entrada "Changelog — Portão de promoção", data 2026-11-11, no formato das outras (Por quê, Decisões, Mudanças). As decisões são as da tabela da seção 2 da spec; as mudanças, os arquivos das Tarefas 1 a 3. A seção "Efeito medido" entra na Tarefa 5.

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

Acrescentar à entrada do portão a seção "Efeito medido" com: o resultado por alvo de v4 contra v5 e de v5 contra v1, o tempo de cada comparação, e o estado final do alias. Commit:

```bash
git add CHANGELOG.md
git commit -m "docs: efeito medido do portão de promoção no changelog"
```

---

### Task 6: suíte inteira e fechamento

- [ ] **Step 1:** `stat -c %Y mlflow.db` antes e depois de `venv/bin/python -m unittest discover -s tests 2>&1 | tail -5` e `node --test tests/js/logica.test.js 2>&1 | tail -5`. Expected: `OK`, todos `pass`, e o mesmo `stat` (os testes não tocam o banco da raiz).
- [ ] **Step 2:** `git log model-registry..HEAD --format=%B | grep -ci co-authored` imprime `0`.
- [ ] **Step 3:** Relatório final ao Lucas: o que foi feito, decisões tomadas durante a execução, o resultado real das comparações (Tarefa 5) e a pergunta sobre merge (as duas branches, `model-registry` e `portao-promocao`) e push.
