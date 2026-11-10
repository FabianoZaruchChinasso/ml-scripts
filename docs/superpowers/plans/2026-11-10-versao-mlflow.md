# Comando único que treina, avalia e grava uma versão no MLflow — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `MODELO=v5 venv/bin/python src/ml/versao_mlflow.py` grava um run no experimento "MLflow Wifi Pipeline" com a avaliação completa, o pacote com os modelos avaliados e a versão do dado.

**Architecture:** `src/ml/core/pacote.py` treina os modelos finais pela mesma receita da avaliação e implementa a previsão, sem conhecer o MLflow. `src/ml/core/pacote_mlflow.py` embrulha o pacote como modelo `pyfunc`, com o código de `ml/core` embutido. `src/ml/versao_mlflow.py` é o comando: lê a versão em `core/modelos.json`, avalia com `core/completa.py`, treina, grava o run e confere que o pacote gravado carrega.

**Tech Stack:** Python 3.12, mlflow 3.15.1 (sqlite), scikit-learn, skops, pandas, unittest.

**Spec:** `docs/superpowers/specs/2026-11-10-versao-mlflow-design.md`.

---

## Regras deste repositório (ler antes de começar)

- **Não rode `git commit` nem `git push` sem o Lucas autorizar na sessão.** Nos passos "Sugerir commit", pare, mostre os arquivos e a mensagem sugerida (só a linha de assunto, sem `Co-Authored-By`, sem citar o Claude). Se ele autorizar, commite com essa mensagem e siga; push é sempre dele.
- Trabalhe na branch `versao-mlflow` (já criada; contém a spec).
- Não edite `src/ml/regression_benchmark.py`, `src/ml/classification_benchmark.py`, `src/ml/regression_mlflow.py`, `src/ml/qoe_mlflow.py`, `src/ml/core/modelos.json` nem nada em `src/ml/studio/`.
- Nada de emoji em código, texto ou docs.
- Python do projeto: `venv/bin/python`. Testes: `venv/bin/python -m unittest discover -s tests -p '<arquivo>'` a partir da raiz (não há pytest no venv; os testes importam uns aos outros, e por isso precisam do `discover -s tests`).
- Indentação Python do projeto: 2 espaços. Aspas simples. Comentários e docstrings em português.
- **Nenhum teste pode gravar no `mlflow.db` da raiz.** Todo teste que grava run usa `MLFLOW_TRACKING_URI` temporário, e cria o experimento com `artifact_location` dentro da pasta temporária (o padrão do MLflow é `./mlruns` da pasta atual).

## O que já foi provado antes deste plano (2026-11-10)

O código das tarefas 2 a 7 foi escrito e rodado num rascunho fora do repositório. Os 25 testes novos passaram, e quatro pontos ficaram resolvidos:

1. **Código embutido:** `code_paths` com uma cópia de `src/ml/core` dentro de uma pasta `ml` funciona. O modelo carrega num processo novo, fora do repositório, e `ml.core` vem da pasta do próprio modelo. Não foi preciso o modo "models from code".
2. **Igualdade com a avaliação:** nos dados de teste, o pacote treinado sem um prédio reproduz a previsão da avaliação com diferença abaixo de 1e-13.
3. **Entrada de teste por pickle, não JSON:** o JSON arredonda os números (diferença de 4e-11), e isso bastou para um valor de treino cair do outro lado de um corte do modelo quantílico e mudar uma previsão de 108,3 para 109,5. O teste do processo novo passa a entrada por pickle.
4. **Sem assinatura do MLflow:** com a assinatura inferida do exemplo, o modelo recusa um inteiro ausente em coluna inteira, e recusa um inteiro em coluna decimal. Os contadores TR-181 chegam inteiros e às vezes faltam, então o pacote é gravado com `signature=False`. O exemplo de entrada continua gravado junto, e quem valida a entrada é `pacote.prever`.

Nos dados reais (v5, conjunto canônico), a mesma comparação da seção 4.3 da spec deu:

```
versão v5; avaliação em 741 s
casa-marcelo {'down': 5.68e-14, 'down_cortadas': 0, 'up': 1.14e-13, 'up_cortadas': 0, 'lat': 0.0, 'jit': 0.0}
coworking {'down': 5.68e-14, 'down_cortadas': 0, 'up': 7.11e-14, 'up_cortadas': 0, 'lat': 0.0, 'jit': 0.0}
hotmilk {'down': 3.41e-13, 'down_cortadas': 0, 'up': 3.41e-13, 'up_cortadas': 0, 'lat': 0.0, 'jit': 0.0}
residencia {'down': 7.11e-14, 'down_cortadas': 21, 'up': 4.26e-14, 'up_cortadas': 51, 'lat': 0.0, 'jit': 0.0}
villa-escritorio {'down': 0.0, 'down_cortadas': 140, 'up': 0.0, 'up_cortadas': 140, 'lat': 0.0, 'jit': 0.0}
villa-residencial {'down': 2.27e-13, 'down_cortadas': 0, 'up': 2.27e-13, 'up_cortadas': 0, 'lat': 0.0, 'jit': 0.0}
total 933 s
```

Cada linha é um prédio; os números são a maior diferença absoluta entre o pacote e a avaliação, por alvo (Mbps para `down` e `up`, ms para `lat` e `jit`). `*_cortadas` é quantas linhas ficaram fora da comparação por terem sido cortadas no teto de WAN. No `villa-escritorio` todas as linhas de download e upload são cortadas, então lá a vazão não tem como ser comparada. Os tempos impressos estão inflados: havia outra medição rodando na mesma máquina.

## Arquivos

| Arquivo | Papel |
|---|---|
| `src/ml/core/registro_mlflow.py` | ganha `tags_git()`, função pública que chama `_tags_git()` |
| `src/ml/core/pacote.py` (novo) | `Pacote`, `treinar`, `prever`: modelos finais e receita de previsão, sem MLflow |
| `src/ml/core/pacote_mlflow.py` (novo) | `PacoteQoE` (pyfunc), `gravar`, `carregar` |
| `src/ml/versao_mlflow.py` (novo) | o comando: `metricas_do_pipeline`, `registrar`, `main` |
| `tests/test_pacote.py` (novo) | receita de previsão e igualdade com a avaliação |
| `tests/test_pacote_mlflow.py` (novo) | gravar, carregar e carregar em processo novo |
| `tests/test_versao_mlflow.py` (novo) | métricas, run gravado e fluxo do comando |
| `tests/test_registro_mlflow.py` | teste de `tags_git` e guarda de isolamento dos testes novos |
| `README.md`, `CHANGELOG.md`, `docs/pipeline/2026-11-10-inventario-studio-mlflow.md` | documentação |

Os testes novos usam `frame()` e `TABELA` de `tests/test_studio_features.py`: 84 linhas em três prédios (`residencia`, `coworking`, `hotmilk`), sem teto de WAN, com `radio` alternando entre `5ghz` e `2.4ghz` em todos os prédios, e `router_tx_bytes` marcado como vazamento.

---

### Task 1: `tags_git()` público em `core/registro_mlflow.py`

O comando novo precisa das tags do git (commit e `git_arvore`). Hoje a função é `_tags_git`, e `tests/test_registro_mlflow.py` troca esse nome por um dublê; por isso o nome antigo continua sendo o que `registrar_avaliacao` chama.

**Files:**
- Modify: `src/ml/core/registro_mlflow.py` (logo depois de `_tags_git`)
- Test: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_registro_mlflow.py`, logo antes de `class TestIsolamentoDosTestes`:

```python
class TestTagsGitPublica(unittest.TestCase):
  def test_devolve_o_mesmo_que_a_interna(self):
    with mock.patch.object(R, '_tags_git', return_value={'git_arvore': 'limpa'}):
      self.assertEqual(R.tags_git(), {'git_arvore': 'limpa'})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registro_mlflow.py' 2>&1 | tail -5`
Expected: FAIL com `AttributeError: module 'ml.core.registro_mlflow' has no attribute 'tags_git'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/registro_mlflow.py`, logo depois do fim de `_tags_git` (antes de `@_exclusivo` de `registrar_avaliacao`):

```python
def tags_git() -> dict:
  """As tags do git de um run (commit e git_arvore), para os outros registros no MLflow."""
  return _tags_git()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registro_mlflow.py' 2>&1 | tail -3`
Expected: `OK` (25 testes)

- [ ] **Step 5: Sugerir commit**

Arquivos: `src/ml/core/registro_mlflow.py`, `tests/test_registro_mlflow.py`
Mensagem: `feat(core): tags_git público no registro do MLflow`

---

### Task 2: `core/pacote.py`: treinar e prever

**Files:**
- Create: `src/ml/core/pacote.py`
- Test: `tests/test_pacote.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_pacote.py`:

```python
import dataclasses
import json
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import producao
from ml.core import quantis as Q
from test_studio_features import TABELA, frame

DN, UP, LAT, JIT = P.PREFIXOS
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}


def conjuntos():
  """Três prédios (residencia, coworking, hotmilk), sem teto de WAN, com as duas bandas em todos."""
  return {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}


def sem_predio(conjs, predio):
  return {alvo: dataclasses.replace(c, df=c.df[c.df['_site'] != predio]) for alvo, c in conjs.items()}


class PoucasArvores(unittest.TestCase):
  """25 árvores no modelo da régua: o que se testa é a receita, não a qualidade do modelo."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = conjuntos()


class TestTreinarEPrever(PoucasArvores):
  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.absoluto = P.treinar(cls.conjs, FEATURES)
    cls.eficiencia = P.treinar(cls.conjs, FEATURES, {DN: 'router_snr'})
    cls.por_banda = P.treinar(cls.conjs, FEATURES, POR_BANDA)

  def matriz(self, pacote, alvo, linhas):
    return producao.preparar_entrada(linhas, pacote.receita['alvos'][alvo]['contrato'])[0]

  def test_devolve_as_saidas_com_o_indice_da_entrada(self):
    linhas = self.conjs[DN].df.iloc[[5, 3, 20]]
    saida, avisos = P.prever(self.absoluto, linhas)
    self.assertEqual(list(saida.columns), list(P.SAIDAS))
    self.assertEqual(list(saida.index), list(linhas.index))
    self.assertFalse(saida.isna().any().any())
    self.assertEqual(avisos, [])

  def test_modelos_de_cada_tipo_de_denominador(self):
    quantis = ['jit_q50', 'jit_q90', 'lat_q50', 'lat_q90']
    self.assertEqual(sorted(self.absoluto.modelos), ['down_absoluto'] + quantis + ['up_absoluto'])
    self.assertEqual(sorted(self.eficiencia.modelos), ['down_eficiencia'] + quantis + ['up_absoluto'])
    self.assertEqual(sorted(self.por_banda.modelos),
                     ['down_absoluto', 'down_eficiencia'] + quantis + ['up_absoluto', 'up_eficiencia'])

  def test_receita_vira_json_e_diz_as_colunas_de_entrada(self):
    receita = json.loads(json.dumps(self.por_banda.receita))
    self.assertEqual(receita['entradas'], FEATURES)
    self.assertEqual(receita['saidas'], list(P.SAIDAS))
    self.assertEqual(receita['versao_pacote'], P.VERSAO_PACOTE)
    self.assertEqual(receita['alvos'][DN]['denominador']['radio'], '5ghz')
    self.assertIsNone(self.absoluto.receita['alvos'][DN]['denominador'])
    # Denominador e radio fora das features também são colunas de entrada.
    so_sinal = P.treinar(self.conjs, ['router_signal_dbm'], POR_BANDA)
    self.assertEqual(so_sinal.receita['entradas'], ['router_signal_dbm', 'router_snr', 'radio'])

  def test_eficiencia_multiplica_pelo_denominador(self):
    linhas = self.conjs[DN].df.head(6)
    saida, avisos = P.prever(self.eficiencia, linhas)
    X = self.matriz(self.eficiencia, DN, linhas)
    esperado = self.eficiencia.modelos['down_eficiencia'].predict(X) * linhas['router_snr'].to_numpy()
    np.testing.assert_allclose(saida['download_mbps'].to_numpy(), esperado)
    self.assertEqual(avisos, [])

  def test_denominador_vazio_ou_baixo_usa_a_mediana_e_avisa(self):
    linhas = self.conjs[DN].df.head(6).copy()
    linhas.loc[linhas.index[0], 'router_snr'] = np.nan
    linhas.loc[linhas.index[1], 'router_snr'] = 0.5
    saida, avisos = P.prever(self.eficiencia, linhas)
    den = self.eficiencia.receita['alvos'][DN]['denominador']
    X = self.matriz(self.eficiencia, DN, linhas)
    esperado = self.eficiencia.modelos['down_eficiencia'].predict(X)[:2] * den['mediana_imputacao']
    np.testing.assert_allclose(saida['download_mbps'].to_numpy()[:2], esperado)
    self.assertEqual(len(avisos), 1)
    self.assertIn('2 linha(s)', avisos[0])

  def test_banda_aceita_a_grafia_do_acs_e_radio_vazio_vai_para_o_absoluto(self):
    linhas = self.conjs[DN].df.head(4).copy()
    linhas['radio'] = ['5GHz', ' 5ghz ', '2.4ghz', None]
    saida, avisos = P.prever(self.por_banda, linhas)
    X = self.matriz(self.por_banda, DN, linhas)
    eficiencia = self.por_banda.modelos['down_eficiencia'].predict(X) * linhas['router_snr'].to_numpy()
    absoluto = self.por_banda.modelos['down_absoluto'].predict(X)
    np.testing.assert_allclose(saida['download_mbps'].to_numpy(),
                               [eficiencia[0], eficiencia[1], absoluto[2], absoluto[3]])
    self.assertEqual(avisos, [])

  def test_p90_leva_a_correcao_e_nunca_fica_abaixo_do_p50(self):
    pacote = P.Pacote(self.absoluto.modelos, json.loads(json.dumps(self.absoluto.receita)))
    pacote.receita['alvos'][LAT]['correcao_log_q90'] = 0.5
    linhas = self.conjs[LAT].df.head(10)
    saida, _ = P.prever(pacote, linhas)
    X = self.matriz(pacote, LAT, linhas)
    p50 = np.expm1(pacote.modelos['lat_q50'].predict(X))
    q90_log = pacote.modelos['lat_q90'].predict(X)
    np.testing.assert_allclose(saida['latency_ms_p50'].to_numpy(), p50)
    np.testing.assert_allclose(saida['latency_ms_p90_bruto'].to_numpy(), np.maximum(np.expm1(q90_log), p50))
    np.testing.assert_allclose(saida['latency_ms_p90'].to_numpy(), np.maximum(np.expm1(q90_log + 0.5), p50))
    self.assertTrue((saida['latency_ms_p90'] >= saida['latency_ms_p90_bruto']).all())
    self.assertTrue((saida['latency_ms_p90_bruto'] >= saida['latency_ms_p50']).all())

  def test_entrada_sem_coluna_levanta(self):
    with self.assertRaisesRegex(ValueError, 'router_snr'):
      P.prever(self.absoluto, self.conjs[DN].df.head(3).drop(columns=['router_snr']))

  def test_feature_com_vazamento_nao_entra(self):
    with self.assertRaises(AssertionError):
      P.treinar(self.conjs, FEATURES + ['router_tx_bytes'])

  def test_sem_features_levanta(self):
    with self.assertRaises(ValueError):
      P.treinar(self.conjs, [])

  def test_linhas_limitadas_pela_wan_ficam_fora_do_treino_de_download_e_upload(self):
    marcado, sem = dict(self.conjs), dict(self.conjs)
    for alvo in (DN, UP):
      df = self.conjs[alvo].df.copy()
      df['_limitado_wan'] = df['_site'] == 'hotmilk'
      marcado[alvo] = dataclasses.replace(self.conjs[alvo], df=df)
      sem[alvo] = dataclasses.replace(self.conjs[alvo], df=df[df['_site'] != 'hotmilk'])
    linhas = self.conjs[DN].df.head(10)
    com_marca, sem_linhas = P.prever(P.treinar(marcado, FEATURES), linhas)[0], P.prever(P.treinar(sem, FEATURES), linhas)[0]
    vazao = ['download_mbps', 'upload_mbps']
    np.testing.assert_allclose(com_marca[vazao].to_numpy(), sem_linhas[vazao].to_numpy())
    # Latência e jitter não têm teto: usam todas as linhas.
    todas = P.prever(self.absoluto, linhas)[0]
    np.testing.assert_allclose(com_marca['latency_ms_p50'].to_numpy(), todas['latency_ms_p50'].to_numpy())


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_pacote.py' 2>&1 | tail -5`
Expected: FAIL com `ImportError: cannot import name 'pacote' from 'ml.core'`

- [ ] **Step 3: Implementar**

Criar `src/ml/core/pacote.py`:

```python
"""Pacote de uma versão: os modelos finais e a receita de previsão.

Treina com todos os prédios pela mesma receita que a avaliação usa dentro de cada fold
(core/avaliacao.prever_fora_do_fold e core/quantis.prever_quantis_fora_do_fold), para que o modelo
entregue seja o modelo medido. Não importa o MLflow: core/pacote_mlflow.py grava e carrega.
O pacote não corta a previsão no teto de WAN: em produção o link da casa não é conhecido.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.core import avaliacao as core_avaliacao
from ml.core import producao as core_producao
from ml.core import quantis as core_quantis
from ml.core.features import matriz

VERSAO_PACOTE = '2026-11-10.1'
PREFIXOS = {'speedtest_down_mbps': 'down', 'speedtest_up_mbps': 'up', 'latency_ms': 'lat', 'jitter_ms': 'jit'}
SAIDA_VAZAO = {'speedtest_down_mbps': 'download_mbps', 'speedtest_up_mbps': 'upload_mbps'}
SAIDAS = ('download_mbps', 'upload_mbps', 'latency_ms_p50', 'latency_ms_p90', 'latency_ms_p90_bruto',
          'jitter_ms_p50', 'jitter_ms_p90', 'jitter_ms_p90_bruto')


@dataclass
class Pacote:
  modelos: dict
  receita: dict


def _treinar_vazao(conj, features: list, denominador, modelos: dict) -> dict:
  """Download ou upload: absoluto, eficiência (alvo ÷ denominador) ou os dois, quando a eficiência vale só numa banda."""
  p = PREFIXOS[conj.alvo]
  df = conj.df[conj.df[conj.alvo].notna()]
  if '_limitado_wan' in df.columns:
    df = df[~df['_limitado_wan'].astype(bool)]
  X = matriz(df, features)
  y = df[conj.alvo].astype(float)
  coluna = denominador['coluna'] if isinstance(denominador, dict) else denominador
  radio = denominador.get('radio') if isinstance(denominador, dict) else None
  bloco = {'contrato': core_producao.contrato(df, features), 'denominador': None}
  if coluna is None or radio is not None:
    modelos[f'{p}_absoluto'] = core_avaliacao.modelo_regua().fit(X, y)
  if coluna is not None:
    if coluna not in df.columns:
      raise ValueError(f'denominador {coluna!r} não existe no conjunto de {conj.alvo}')
    den = pd.to_numeric(df[coluna], errors='coerce')
    validos = den >= core_avaliacao.DEN_MINIMO
    if not validos.any():
      raise ValueError(f'nenhuma linha de treino com {coluna!r} válido em {conj.alvo}')
    mediana = float(den[validos].median())
    modelos[f'{p}_eficiencia'] = core_avaliacao.modelo_regua().fit(X, y / den.where(validos, mediana))
    bloco['denominador'] = {'coluna': coluna, 'radio': radio, 'mediana_imputacao': mediana,
                            'den_minimo': core_avaliacao.DEN_MINIMO}
  return bloco


def _treinar_quantis(conj, features: list, modelos: dict) -> dict:
  """Latência ou jitter: p50 e p90 em log1p, e a correção conformal do p90 entre todos os prédios."""
  p = PREFIXOS[conj.alvo]
  df = conj.df[conj.df[conj.alvo].notna()]
  X = matriz(df, features)
  y_log = np.log1p(df[conj.alvo].astype(float).clip(lower=0))
  for q in core_quantis.QUANTIS:
    modelos[f'{p}_{core_quantis.coluna(q)}'] = core_quantis.modelo_quantil(q).fit(X, y_log)
  correcao = core_quantis.correcao_conformal(X, y_log, df['_site'], 0.9)
  return {'contrato': core_producao.contrato(df, features),
          'correcao_log_q90': 0.0 if correcao is None else correcao, 'sem_correcao': correcao is None}


def treinar(conjs: dict, features, denominador: dict = None) -> Pacote:
  """Modelos finais dos quatro alvos e a receita para prever com eles.

  `conjs`: {alvo: Conjunto}. `features`: já sem as colunas de vazamento (se alguma chegar, levanta
  AssertionError). `denominador`: {alvo: coluna ou {'coluna', 'radio'}} da versão, ou None.
  """
  features = list(features)
  if not features:
    raise ValueError('o pacote precisa de pelo menos uma feature')
  denominador = denominador or {}
  modelos, alvos, entradas = {}, {}, list(features)
  for alvo in PREFIXOS:
    conj = conjs[alvo]
    core_avaliacao.assert_sem_vazamento(features, [c for c, k in conj.classes.items() if k is not None and k.vazamento])
    if alvo in SAIDA_VAZAO:
      alvos[alvo] = _treinar_vazao(conj, features, denominador.get(alvo), modelos)
      den = alvos[alvo]['denominador']
      if den:
        entradas += [c for c in (den['coluna'], 'radio' if den['radio'] else None) if c and c not in entradas]
    else:
      alvos[alvo] = _treinar_quantis(conj, features, modelos)
  receita = {'versao_pacote': VERSAO_PACOTE, 'versao_regua': core_avaliacao.VERSAO_REGUA, 'features': features,
             'entradas': entradas, 'saidas': list(SAIDAS), 'alvos': alvos}
  return Pacote(modelos, receita)


def _na_banda(radio: pd.Series, valor: str) -> np.ndarray:
  """Linhas da banda `valor`, sem diferença de maiúsculas e espaços ('5GHz' do ACS casa com '5ghz')."""
  igual = radio.astype('string').str.strip().str.lower() == valor.strip().lower()
  return igual.fillna(False).to_numpy(dtype=bool)


def _prever_vazao(pacote: Pacote, alvo: str, linhas: pd.DataFrame, avisos: list) -> np.ndarray:
  p = PREFIXOS[alvo]
  bloco = pacote.receita['alvos'][alvo]
  X, da_entrada = core_producao.preparar_entrada(linhas, bloco['contrato'])
  avisos += [f'{alvo}: {a}' for a in da_entrada]
  den = bloco['denominador']
  if den is None:
    return np.asarray(pacote.modelos[f'{p}_absoluto'].predict(X), dtype=float)
  valores = pd.to_numeric(linhas[den['coluna']], errors='coerce')
  invalido = ~(valores >= den['den_minimo']).to_numpy(dtype=bool)
  valores = valores.where(~invalido, den['mediana_imputacao']).to_numpy(dtype=float)
  previsto = np.asarray(pacote.modelos[f'{p}_eficiencia'].predict(X), dtype=float) * valores
  if den['radio'] is not None:
    na_banda = _na_banda(linhas['radio'], den['radio'])
    previsto = np.where(na_banda, previsto, np.asarray(pacote.modelos[f'{p}_absoluto'].predict(X), dtype=float))
    invalido = invalido & na_banda
  if invalido.any():
    avisos.append(f"{alvo}: {den['coluna']} vazio ou abaixo de {den['den_minimo']} em {int(invalido.sum())} "
                  'linha(s); usei a mediana do treino')
  return previsto


def _prever_quantis(pacote: Pacote, alvo: str, linhas: pd.DataFrame, avisos: list) -> dict:
  p = PREFIXOS[alvo]
  bloco = pacote.receita['alvos'][alvo]
  X, da_entrada = core_producao.preparar_entrada(linhas, bloco['contrato'])
  avisos += [f'{alvo}: {a}' for a in da_entrada]
  q90_log = np.asarray(pacote.modelos[f'{p}_q90'].predict(X), dtype=float)
  p50 = np.clip(np.expm1(np.asarray(pacote.modelos[f'{p}_q50'].predict(X), dtype=float)), 0, None)
  p90 = np.maximum(np.clip(np.expm1(q90_log + bloco['correcao_log_q90']), 0, None), p50)
  bruto = np.maximum(np.clip(np.expm1(q90_log), 0, None), p50)
  return {f'{alvo}_p50': p50, f'{alvo}_p90': p90, f'{alvo}_p90_bruto': bruto}


def prever(pacote: Pacote, linhas: pd.DataFrame):
  """Previsões das linhas, com as colunas de SAIDAS e o índice de `linhas`. Devolve (DataFrame, avisos).

  `linhas` precisa das colunas de receita['entradas']. O p90 leva a correção conformal; o p90_bruto é o
  que a régua por cômodo usa. Nenhum p90 fica abaixo do p50.
  """
  faltam = [c for c in pacote.receita['entradas'] if c not in linhas.columns]
  if faltam:
    raise ValueError(f'colunas ausentes na entrada do pacote: {faltam}')
  avisos, saida = [], {}
  for alvo, nome in SAIDA_VAZAO.items():
    saida[nome] = _prever_vazao(pacote, alvo, linhas, avisos)
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    saida.update(_prever_quantis(pacote, alvo, linhas, avisos))
  return pd.DataFrame(saida, index=linhas.index)[list(SAIDAS)], avisos
```

Pontos que precisam ficar exatamente assim, porque são o que mantém o pacote igual à avaliação (`core/avaliacao.prever_fora_do_fold` e `core/quantis.prever_quantis_fora_do_fold`):

- download e upload treinam sem as linhas `_limitado_wan`; latência e jitter treinam com todas;
- a mediana do denominador sai só das linhas de treino com denominador válido;
- com denominador por banda, os dois modelos treinam com as mesmas linhas (todas as bandas), e a banda só escolhe qual previsão vale;
- o p90 soma a correção em escala log antes do `expm1`, e os dois p90 nunca ficam abaixo do p50.

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_pacote.py' 2>&1 | tail -3`
Expected: `Ran 11 tests` e `OK` (cerca de 20 s)

---

### Task 3: o pacote é igual à avaliação (spec, seção 4.3)

É o teste que sustenta a decisão "o modelo entregue é o modelo medido". Ele não pede código novo: se falhar, a receita de `pacote.py` divergiu da avaliação e é ela que precisa ser corrigida, não o teste.

**Files:**
- Modify: `tests/test_pacote.py`

- [ ] **Step 1: Acrescentar a classe de teste**

Em `tests/test_pacote.py`, logo antes de `if __name__ == '__main__':`:

```python
class TestIgualAAvaliacao(PoucasArvores):
  """O pacote treinado sem um prédio prevê esse prédio com o mesmo número da avaliação (spec, seção 4.3)."""

  def conferir(self, denominador):
    vazao = {alvo: A.prever_fora_do_fold(self.conjs[alvo].df, FEATURES, alvo, [], denominador=denominador.get(alvo))
             for alvo in (DN, UP)}
    quantis = {alvo: Q.prever_quantis_fora_do_fold(self.conjs[alvo].df, FEATURES, alvo, []) for alvo in (LAT, JIT)}
    for predio in sorted(self.conjs[DN].df['_site'].unique()):
      pacote = P.treinar(sem_predio(self.conjs, predio), FEATURES, denominador)
      for alvo, prev in vazao.items():
        fora = self.conjs[alvo].df[self.conjs[alvo].df['_site'] == predio]
        saida = P.prever(pacote, fora)[0]
        np.testing.assert_allclose(saida[P.SAIDA_VAZAO[alvo]].to_numpy(), prev.loc[fora.index, 'yhat'].to_numpy(),
                                   rtol=1e-9, err_msg=f'{alvo} em {predio}')
      for alvo, prev in quantis.items():
        fora = self.conjs[alvo].df[self.conjs[alvo].df['_site'] == predio]
        saida = P.prever(pacote, fora)[0]
        for coluna, da_avaliacao in ((f'{alvo}_p50', 'q50'), (f'{alvo}_p90', 'q90'), (f'{alvo}_p90_bruto', 'q90_bruto')):
          np.testing.assert_allclose(saida[coluna].to_numpy(), prev.loc[fora.index, da_avaliacao].to_numpy(),
                                     rtol=1e-9, err_msg=f'{coluna} em {predio}')

  def test_eficiencia_no_download_e_absoluto_no_upload(self):
    self.conferir({DN: 'router_snr'})

  def test_eficiencia_por_banda(self):
    self.conferir(POR_BANDA)
```

- [ ] **Step 2: Rodar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_pacote.py' 2>&1 | tail -3`
Expected: `Ran 13 tests` e `OK` (cerca de 45 s)

Se falhar, a mensagem diz o alvo e o prédio. Compare o trecho correspondente de `_treinar_vazao` ou `_treinar_quantis` com o laço de `prever_fora_do_fold` ou `prever_quantis_fora_do_fold`.

- [ ] **Step 3: Sugerir commit**

Arquivos: `src/ml/core/pacote.py`, `tests/test_pacote.py`
Mensagem: `feat(core): pacote com os modelos finais e a receita de previsão`

---

### Task 4: `core/pacote_mlflow.py`: gravar e carregar

**Files:**
- Create: `src/ml/core/pacote_mlflow.py`
- Test: `tests/test_pacote_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_pacote_mlflow.py`:

```python
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mlflow
import numpy as np

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, SRC)

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import pacote_mlflow as PM
from test_studio_features import TABELA, frame

DN, UP = 'speedtest_down_mbps', 'speedtest_up_mbps'
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}

# A entrada vai por pickle: JSON arredonda os números, e um valor de treino arredondado pode cair do
# outro lado de um corte do modelo quantílico.
PROCESSO_NOVO = '''
import sys
import mlflow, numpy as np, pandas as pd
uri, pasta, src = sys.argv[1:4]
assert src not in [p.rstrip('/') for p in sys.path], sys.path
saida = mlflow.pyfunc.load_model(uri).predict(pd.read_pickle(pasta + '/exemplo.pkl'))
origem = sys.modules['ml.core.pacote'].__file__
assert not origem.startswith(src), origem
np.testing.assert_allclose(saida.to_numpy(), pd.read_pickle(pasta + '/esperado.pkl').to_numpy(), rtol=1e-9)
'''


class TestGravarECarregar(unittest.TestCase):
  """Um mlflow.db temporário para a classe: gravar o pacote uma vez basta para os dois testes."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    tmp = tempfile.TemporaryDirectory()
    cls.addClassCleanup(tmp.cleanup)
    cls.tmp = tmp.name
    cls.addClassCleanup(mlflow.set_tracking_uri, mlflow.get_tracking_uri())
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{cls.tmp}/mlflow.db'})
    env.start()
    cls.addClassCleanup(env.stop)
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(conjs, FEATURES, POR_BANDA)
    cls.exemplo = conjs[DN].df[cls.pacote.receita['entradas']].head(5)
    experimento = mlflow.create_experiment('teste', artifact_location=os.path.join(cls.tmp, 'mlruns'))
    with mlflow.start_run(experiment_id=experimento) as run:
      PM.gravar(cls.pacote, cls.exemplo)
    cls.uri = f'runs:/{run.info.run_id}/{PM.NOME}'

  def test_carregar_devolve_um_pacote_que_preve_igual(self):
    volta = PM.carregar(self.uri)
    self.assertEqual(volta.receita, self.pacote.receita)
    self.assertEqual(sorted(volta.modelos), sorted(self.pacote.modelos))
    np.testing.assert_allclose(P.prever(volta, self.exemplo)[0].to_numpy(),
                               P.prever(self.pacote, self.exemplo)[0].to_numpy(), rtol=1e-12)

  def test_modelo_carregado_aceita_inteiro_valor_ausente_e_coluna_a_mais(self):
    """Os contadores chegam inteiros e às vezes faltam. A assinatura do MLflow recusaria os dois casos,
    e por isso o modelo é gravado sem ela."""
    modelo = mlflow.pyfunc.load_model(self.uri)
    self.assertIsNone(modelo.metadata.signature)
    esperado = P.prever(self.pacote, self.exemplo)[0]
    inteiros = self.exemplo.assign(router_snr=self.exemplo['router_snr'].astype('int64'), extra=1)
    np.testing.assert_allclose(modelo.predict(inteiros).to_numpy(), esperado.to_numpy(), rtol=1e-12)
    faltando = self.exemplo.copy()
    faltando.loc[faltando.index[0], ['router_snr', 'router_signal_dbm']] = np.nan
    faltando['radio'] = [None, '5GHz', '2.4GHz', '5ghz', '2.4ghz']
    saida = modelo.predict(faltando)
    self.assertEqual(list(saida.columns), list(P.SAIDAS))
    self.assertFalse(saida.isna().any().any())

  def test_carrega_em_processo_novo_fora_do_repositorio(self):
    self.exemplo.to_pickle(os.path.join(self.tmp, 'exemplo.pkl'))
    P.prever(self.pacote, self.exemplo)[0].to_pickle(os.path.join(self.tmp, 'esperado.pkl'))
    ambiente = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    r = subprocess.run([sys.executable, '-c', PROCESSO_NOVO, self.uri, self.tmp, SRC], cwd=self.tmp,
                       env=ambiente, capture_output=True, text=True, timeout=300)
    self.assertEqual(r.returncode, 0, r.stderr[-2000:])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_pacote_mlflow.py' 2>&1 | tail -5`
Expected: FAIL com `ImportError: cannot import name 'pacote_mlflow' from 'ml.core'`

- [ ] **Step 3: Implementar**

Criar `src/ml/core/pacote_mlflow.py`:

```python
"""Grava e carrega o pacote de uma versão (core/pacote.py) como modelo pyfunc do MLflow.

O código de ml/core vai dentro do modelo gravado, para que ele carregue sem o repositório: quem
serve o pacote só precisa das bibliotecas (mlflow, scikit-learn, skops, pandas).
"""

import json
import os
import shutil
import tempfile
import zipfile

import mlflow
import mlflow.pyfunc
import skops.io

from ml.core import pacote as core_pacote

NOME = 'pacote'
# O imputer do modelo da régua guarda um numpy.dtype, que o skops não confia por padrão.
TIPOS_CONFIAVEIS = ['numpy.dtype']
_CORE = os.path.dirname(os.path.abspath(__file__))


class PacoteQoE(mlflow.pyfunc.PythonModel):
  """Recebe linhas com as colunas de receita['entradas'] e devolve as de pacote.SAIDAS."""

  def load_context(self, context):
    with open(context.artifacts['receita'], encoding='utf-8') as f:
      receita = json.load(f)
    modelos = {nome: skops.io.load(caminho, trusted=TIPOS_CONFIAVEIS)
               for nome, caminho in context.artifacts.items() if nome != 'receita'}
    self.pacote = core_pacote.Pacote(modelos, receita)

  def predict(self, context, model_input, params=None):
    return core_pacote.prever(self.pacote, model_input)[0]


def _copia_do_core(destino: str) -> str:
  """ml/core numa pasta 'ml' só dele: code_paths copia a pasta inteira, e src/ml também tem o Studio e os scripts."""
  raiz = os.path.join(destino, 'ml')
  shutil.copytree(_CORE, os.path.join(raiz, 'core'), ignore=shutil.ignore_patterns('__pycache__'))
  return raiz


def gravar(pacote: core_pacote.Pacote, exemplo):
  """Grava o pacote no run ativo, em NOME, e devolve o ModelInfo. `exemplo`: poucas linhas com as colunas de entradas.

  Sem assinatura do MLflow (signature=False): ela recusa um inteiro ausente em coluna inteira e um
  inteiro em coluna decimal, e os contadores chegam inteiros e às vezes faltam. Quem valida a entrada
  é pacote.prever. O exemplo fica gravado junto do modelo, como documentação.
  """
  with tempfile.TemporaryDirectory() as tmp:
    artefatos = {}
    for nome, modelo in pacote.modelos.items():
      artefatos[nome] = os.path.join(tmp, f'{nome}.skops')
      skops.io.dump(modelo, artefatos[nome], compression=zipfile.ZIP_DEFLATED)
    artefatos['receita'] = os.path.join(tmp, 'receita.json')
    with open(artefatos['receita'], 'w', encoding='utf-8') as f:
      json.dump(pacote.receita, f, ensure_ascii=False, indent=1)
    return mlflow.pyfunc.log_model(name=NOME, python_model=PacoteQoE(), artifacts=artefatos,
                                   code_paths=[_copia_do_core(tmp)], input_example=exemplo, signature=False)


def carregar(uri: str) -> core_pacote.Pacote:
  """O pacote gravado em `uri` (por exemplo 'runs:/<run_id>/pacote')."""
  return mlflow.pyfunc.load_model(uri).unwrap_python_model().pacote
```

Por que assim:

- `code_paths` copia a pasta inteira que recebe. `src/ml` não tem `__init__.py` (é um pacote de namespace) e contém o Studio e os scripts; por isso a cópia leva só `core`, dentro de uma pasta chamada `ml`, para que `import ml.core.pacote` funcione no destino.
- `signature=False` desliga a checagem de tipos do MLflow, que recusaria contadores inteiros ausentes (ver "O que já foi provado"). O `input_example` continua gravado, e fica disponível em `modelo.input_example` depois de carregar.
- O aviso do MLflow sobre "type hints" e sobre CloudPickle é esperado e pode ser ignorado.

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_pacote_mlflow.py' 2>&1 | tail -3`
Expected: `Ran 3 tests` e `OK` (cerca de 30 s)

- [ ] **Step 5: Conferir que nada foi gravado na raiz**

Run: `git status --short`
Expected: só os arquivos novos de código e teste; nenhuma pasta `mlruns/pipeline` nem mudança em `mlflow.db` (os dois estão no `.gitignore`, então confira também com `ls mlruns | grep -c pipeline`, que deve dar `0`).

- [ ] **Step 6: Sugerir commit**

Arquivos: `src/ml/core/pacote_mlflow.py`, `tests/test_pacote_mlflow.py`
Mensagem: `feat(core): pacote gravado e carregado como modelo pyfunc do MLflow`

---

### Task 5: `versao_mlflow.py`: métricas do pipeline

**Files:**
- Create: `src/ml/versao_mlflow.py`
- Test: `tests/test_versao_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_versao_mlflow.py` (os imports e as constantes já servem às tarefas 6 e 7):

```python
import os
import sys
import tempfile
import unittest
from unittest import mock

import mlflow
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import versao_mlflow as V
from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import pacote_mlflow as PM
from ml.core import registro_mlflow as R
from test_studio_features import TABELA, frame

DN, UP, LAT, JIT = P.PREFIXOS
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': FEATURES + ['router_tx_bytes'], 'descricao': 'teste',
                                              'denominador': POR_BANDA}}}


def avaliacao() -> dict:
  def alvo(pooled, mae):
    return {'pooled': pooled, 'mae': mae, 'mae_log': 0.6, 'versao_regua': 'r1',
            'intervalos': {'pooled': [pooled - 0.1, pooled + 0.1], 'mae': [mae - 5, mae + 5], 'mae_log': [0.5, 0.7]},
            'por_local': {'casa-a': 0.4, 'casa-b': None}, 'mae_por_local': {'casa-a': 12.5, 'casa-b': 30.0}}
  quantis = {'cobertura': {'q50': 0.5, 'q90': 0.91}, 'pinball': {'q50': 4.0, 'q90': 11.2}}
  return {
    'perfil': 'norma', 'removidas_por_vazamento': [],
    'comodo': {'ambiente': 'todos', 'datasets': ['a.csv'], 'nota': 0.7, 'intervalo': [0.6, 0.8],
               'piso': {'nota': 0.45}, 'contra_piso': {'diferenca': 0.25}, 'graves': 2,
               'jogo': {'nota': 0.64, 'intervalo': [0.5, 0.78], 'piso': {'nota': 0.55}},
               'versao_comodo': 'v-c', 'posicoes': [{'pos': 'p1'}], 'piso_posicoes': [{'pos': 'p2'}]},
    'atende_completo': {'media': 0.66}, 'atende_throughput': {'media': 0.65}, 'atende_ajustado': {'media': 0.8},
    DN: alvo(0.75, 59.0), UP: alvo(0.74, 56.0),
    LAT: dict(alvo(-0.1, 22.5), quantis=quantis), JIT: dict(alvo(-0.08, 15.7), quantis=quantis),
  }


class TestMetricasDoPipeline(unittest.TestCase):
  def test_intervalos_por_predio_e_pinball(self):
    m = V.metricas_do_pipeline(avaliacao())
    self.assertEqual((m['down_pooled_lo90'], m['down_pooled_hi90']), (0.65, 0.85))
    self.assertEqual((m['up_mae_lo90'], m['up_mae_hi90']), (51.0, 61.0))
    self.assertEqual(m['down_r2_casa-a'], 0.4)
    self.assertEqual(m['jit_mae_casa-b'], 30.0)
    self.assertEqual(m['lat_pinball_q90'], 11.2)

  def test_valor_ausente_fica_de_fora(self):
    m = V.metricas_do_pipeline(avaliacao())
    self.assertNotIn('down_r2_casa-b', m)       # R² None: o prédio não teve como ser medido
    self.assertNotIn('down_pinball_q90', m)     # download não tem quantis
    self.assertFalse([k for k in m if 'mae_log' in k])
    self.assertEqual(V.metricas_do_pipeline({}), {})


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -5`
Expected: FAIL com `ImportError: cannot import name 'versao_mlflow' from 'ml'`

- [ ] **Step 3: Implementar**

Criar `src/ml/versao_mlflow.py`:

```python
"""Treina, avalia e grava uma versão do registro num run do MLflow (experimento "MLflow Wifi Pipeline").

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Datasets: DATASETS=a.zip,b.zip (nomes em
data/; padrão: o conjunto canônico, o mesmo do Studio). O run leva a avaliação completa
(core/completa.py), o pacote com os modelos finais e a receita de previsão (core/pacote.py) e a versão
do dado. A métrica principal é o erro das quatro previsões; a régua por cômodo e os "atende" vão como
métricas secundárias, com a versão de cada régua em tag. Não escreve em core/modelos.json nem toca nos
runs do Studio.
"""

import hashlib
import os
import sys

import mlflow

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import completa as core_completa
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core import pacote as core_pacote
from ml.core import pacote_mlflow as core_pacote_mlflow
from ml.core import registro_mlflow as core_registro_mlflow

EXPERIMENTO = 'MLflow Wifi Pipeline'
DN = 'speedtest_down_mbps'


def metricas_do_pipeline(avaliacao: dict) -> dict:
  """Intervalos de 90%, métricas por prédio e pinball do p90, por alvo.

  Completa registro_mlflow.parametros_e_metricas, que já traz pooled, mae, mae_log e cobertura_q90.
  """
  brutas = {}
  for alvo, p in core_registro_mlflow.ALVOS.items():
    bloco = avaliacao.get(alvo) or {}
    for chave in ('pooled', 'mae'):
      intervalo = (bloco.get('intervalos') or {}).get(chave)
      if intervalo:
        brutas[f'{p}_{chave}_lo90'], brutas[f'{p}_{chave}_hi90'] = intervalo[0], intervalo[1]
    for predio, valor in (bloco.get('por_local') or {}).items():
      brutas[f'{p}_r2_{predio}'] = valor
    for predio, valor in (bloco.get('mae_por_local') or {}).items():
      brutas[f'{p}_mae_{predio}'] = valor
    brutas[f'{p}_pinball_q90'] = ((bloco.get('quantis') or {}).get('pinball') or {}).get('q90')
  return {k: float(v) for k, v in brutas.items()
          if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -3`
Expected: `Ran 2 tests` e `OK`

---

### Task 6: `versao_mlflow.py`: gravar o run

**Files:**
- Modify: `src/ml/versao_mlflow.py`
- Modify: `tests/test_versao_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_versao_mlflow.py`, logo antes de `if __name__ == '__main__':`:

```python
class ComBancoTemporario(unittest.TestCase):
  """Cada teste com um mlflow.db próprio; 25 árvores no modelo da régua."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(cls.conjs, FEATURES, POR_BANDA)

  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    self.tmp = tmp.name
    self.addCleanup(mlflow.set_tracking_uri, mlflow.get_tracking_uri())
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{self.tmp}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)

  def registrar(self):
    versao = {'features': FEATURES, 'denominador': POR_BANDA, 'cobertura': {'nivel': 'proxy'}}
    return V.registrar('v9', versao, self.conjs, avaliacao(), self.pacote, ['abc123', 'def456'])


class TestRegistrar(ComBancoTemporario):
  def test_run_tem_parametros_tags_dado_e_arquivos(self):
    cli = R.cliente()
    run = cli.get_run(self.registrar())
    self.assertEqual(run.info.status, 'FINISHED')
    self.assertEqual(run.info.run_name, 'v9-pipeline')
    experimento = cli.get_experiment(run.info.experiment_id)
    self.assertEqual(experimento.name, 'MLflow Wifi Pipeline')
    self.assertEqual(experimento.artifact_location, os.path.join(self.tmp, 'mlruns', 'pipeline'))
    p = run.data.params
    self.assertEqual((p['modelo'], p['features'], p['cobertura_tr069']), ('v9', ','.join(FEATURES), 'proxy'))
    self.assertEqual((p['fingerprints'], p['versao_pacote']), ('abc123,def456', P.VERSAO_PACOTE))
    for chave in ('versao_tabela', 'versao_catalogo', 'removidas_por_vazamento', 'datasets', 'denominador'):
      self.assertIn(chave, p)
    tags = run.data.tags
    self.assertEqual((tags['modelo'], tags['metrica_principal']), ('v9', 'erro_das_previsoes'))
    self.assertEqual((tags['versao_comodo'], tags['versao_regua']), ('v-c', 'r1'))
    self.assertNotIn('atual', tags)   # atual e ativo são do experimento do Studio
    self.assertNotIn('ativo', tags)
    m = run.data.metrics
    for chave in ('down_pooled', 'down_mae', 'down_pooled_lo90', 'down_r2_casa-a', 'lat_cobertura_q90',
                  'lat_pinball_q90', 'comodo_nota', 'atende_completo'):
      self.assertIn(chave, m)
    dado = run.inputs.dataset_inputs[0]
    self.assertEqual((dado.dataset.name, len(dado.dataset.digest)), ('qoe-wifi', 8))
    self.assertEqual([t.value for t in dado.tags], ['treino'])
    self.assertEqual(sorted(a.path for a in cli.list_artifacts(run.info.run_id)),
                     ['avaliacao.json', 'cobertura_tr069.json', 'posicoes.json', 'receita.json'])

  def test_pacote_do_run_carrega_e_preve_igual(self):
    volta = PM.carregar(f'runs:/{self.registrar()}/{PM.NOME}')
    linhas = self.conjs[DN].df.head(7)
    np.testing.assert_allclose(P.prever(volta, linhas)[0].to_numpy(), P.prever(self.pacote, linhas)[0].to_numpy(),
                               rtol=1e-12)

  def test_nao_cria_o_experimento_do_studio(self):
    self.registrar()
    self.assertIsNone(R.cliente().get_experiment_by_name(R.EXPERIMENTO))

  def test_falha_ao_gravar_o_pacote_deixa_o_run_failed(self):
    with mock.patch.object(V.core_pacote_mlflow, 'gravar', side_effect=RuntimeError('disco cheio')):
      with self.assertRaisesRegex(RuntimeError, 'disco cheio'):
        self.registrar()
    cli = R.cliente()
    runs = cli.search_runs([cli.get_experiment_by_name(V.EXPERIMENTO).experiment_id])
    self.assertEqual([r.info.status for r in runs], ['FAILED'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -5`
Expected: 4 erros com `AttributeError: module 'ml.versao_mlflow' has no attribute 'registrar'`

- [ ] **Step 3: Implementar**

Em `src/ml/versao_mlflow.py`, depois de `metricas_do_pipeline`:

```python
def _experimento() -> str:
  """Id do experimento. Ao criar, põe os artefatos ao lado do banco: o padrão do mlflow é ./mlruns da pasta atual."""
  exp = mlflow.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  uri = core_registro_mlflow.uri_rastreamento()
  local = None
  if uri.startswith('sqlite:///'):
    local = os.path.join(os.path.dirname(uri[len('sqlite:///'):]), 'mlruns', 'pipeline')
  return mlflow.create_experiment(EXPERIMENTO, artifact_location=local)


def registrar(nome: str, versao: dict, conjs: dict, avaliacao: dict, pacote, fingerprints: list) -> str:
  """Grava o run '<nome>-pipeline' e devolve o run_id.

  `versao`: features, denominador e cobertura da versão avaliada. Se gravar ou carregar o pacote
  falhar, o run termina FAILED e a exceção sobe.
  """
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  base = conjs[DN]
  params, metricas = core_registro_mlflow.parametros_e_metricas(nome, dict(versao, avaliacao=avaliacao))
  params.update({'fingerprints': ','.join(fingerprints), 'versao_tabela': core_features.versao_tabela(),
                 'versao_catalogo': core_features.CATALOGO_VERSAO,
                 'versao_pacote': pacote.receita['versao_pacote'],
                 'removidas_por_vazamento': ','.join(avaliacao.get('removidas_por_vazamento') or [])})
  metricas.update(metricas_do_pipeline(avaliacao))
  tags = {'modelo': nome, 'metrica_principal': 'erro_das_previsoes'}
  for chave in ('versao_comodo', 'versao_regua'):
    if params.get(chave):
      tags[chave] = str(params[chave])
  tags.update(core_registro_mlflow.tags_git())
  entradas = pacote.receita['entradas']
  dados = base.df[list(dict.fromkeys(entradas + list(core_pacote.PREFIXOS)))]
  digest = hashlib.sha256(','.join(fingerprints).encode()).hexdigest()[:8]
  comodo = avaliacao.get('comodo') or {}
  exemplo = base.df[entradas].head(5)
  with mlflow.start_run(experiment_id=_experimento(), run_name=f'{nome}-pipeline', tags=tags) as run:
    mlflow.log_params({k: v for k, v in params.items() if v is not None})
    mlflow.log_metrics(metricas)
    mlflow.log_input(mlflow.data.from_pandas(dados, name='qoe-wifi', digest=digest), context='treino')
    mlflow.log_dict(avaliacao, 'avaliacao.json')
    mlflow.log_dict({'posicoes': comodo.get('posicoes') or [], 'piso_posicoes': comodo.get('piso_posicoes') or []},
                    'posicoes.json')
    mlflow.log_dict(pacote.receita, 'receita.json')
    mlflow.log_dict(versao.get('cobertura') or {}, 'cobertura_tr069.json')
    core_pacote_mlflow.gravar(pacote, exemplo)
    mlflow.pyfunc.load_model(f'runs:/{run.info.run_id}/{core_pacote_mlflow.NOME}').predict(exemplo)
  return run.info.run_id
```

Detalhes que os testes cobram:

- o experimento é criado com os artefatos em `<pasta do banco>/mlruns/pipeline`;
- uma exceção dentro do `with mlflow.start_run(...)` deixa o run `FAILED` sozinha e sobe;
- o pacote não aparece em `list_artifacts` do run (o MLflow 3 guarda modelos à parte), mas carrega por `runs:/<run_id>/pacote`;
- nenhuma tag `atual` ou `ativo`, e nada no experimento "MLflow Wifi Studio".

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -3`
Expected: `Ran 6 tests` e `OK` (cerca de 40 s)

---

### Task 7: `versao_mlflow.py`: o comando

**Files:**
- Modify: `src/ml/versao_mlflow.py`
- Modify: `tests/test_versao_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_versao_mlflow.py`, logo antes de `if __name__ == '__main__':`:

```python
class TestMain(unittest.TestCase):
  def setUp(self):
    self.conjs = {alvo: mock.Mock(alvo=alvo, datasets=['a.csv'], avisos=[], tabela={'prefixos': {}, 'colunas': {}},
                                  catalogo=()) for alvo in P.PREFIXOS}
    medida = dict(avaliacao(), removidas_por_vazamento=['router_tx_bytes'])
    self.m = {}
    for nome, alvo, extra in (
        ('registro', (V.core_modelos, 'carregar'), {'return_value': REGISTRO}),
        ('carregar', (V.core_carga, 'carregar'), {'side_effect': lambda alvo, ids=None: self.conjs[alvo]}),
        ('descobertos', (V.core_carga, 'descobertos'),
         {'return_value': [{'id': 'a.csv', 'fingerprint': 'abc123', 'usable': True}]}),
        ('avaliar', (V.core_completa, 'avaliacao_completa'), {'return_value': medida}),
        ('treinar', (V.core_pacote, 'treinar'), {'return_value': 'pacote'}),
        ('cobertura', (V.core_features, 'cobertura_tr069'), {'return_value': {'nivel': 'proxy'}}),
        ('registrar', (V, 'registrar'), {'return_value': 'run-1'})):
      p = mock.patch.object(*alvo, **extra)
      self.m[nome] = p.start()
      self.addCleanup(p.stop)
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': 'sqlite:////nao/usado.db'})
    env.start()
    self.addCleanup(env.stop)
    os.environ.pop('MODELO', None)
    os.environ.pop('DATASETS', None)

  def test_versao_inexistente_sai_antes_de_carregar_dados(self):
    with mock.patch.dict(os.environ, {'MODELO': 'nao-existe'}):
      with self.assertRaises(SystemExit) as erro:
        V.main()
    self.assertIn('v1', str(erro.exception))
    self.m['carregar'].assert_not_called()
    self.m['registrar'].assert_not_called()

  def test_avalia_com_as_features_da_versao_e_treina_sem_as_de_vazamento(self):
    V.main()
    conjunto, ambiente, features, denominador = self.m['avaliar'].call_args.args
    self.assertEqual(conjunto(LAT), self.conjs[LAT])
    self.assertIsNone(ambiente)
    self.assertEqual(features, FEATURES + ['router_tx_bytes'])
    self.assertEqual(denominador, POR_BANDA)
    self.assertEqual(self.m['treinar'].call_args.args[1:], (FEATURES, POR_BANDA))
    nome, versao, conjs, medida, pacote, fingerprints = self.m['registrar'].call_args.args
    self.assertEqual((nome, pacote, fingerprints), ('v1', 'pacote', ['abc123']))
    self.assertEqual(versao, {'features': FEATURES + ['router_tx_bytes'], 'denominador': POR_BANDA,
                              'cobertura': {'nivel': 'proxy'}})
    self.assertEqual(medida['removidas_por_vazamento'], ['router_tx_bytes'])

  def test_datasets_da_variavel_de_ambiente(self):
    with mock.patch.dict(os.environ, {'DATASETS': 'a.csv,b.zip'}):
      V.main()
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.csv', 'b.zip'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -5`
Expected: 3 erros com `AttributeError: module 'ml.versao_mlflow' has no attribute 'main'`

- [ ] **Step 3: Implementar**

No fim de `src/ml/versao_mlflow.py`:

```python
def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f"MODELO={nome!r} não existe em core/modelos.json; "
                     f"versões disponíveis: {sorted(registro['versoes'])}")
  definicao = registro['versoes'][nome]
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
  base = conjs[DN]
  for aviso in base.avisos:
    print(f'aviso: {aviso}')
  denominador = definicao.get('denominador') or None
  print(f"Versão {nome}" + (' (ativa)' if nome == registro['ativo'] else '')
        + f": {len(definicao['features'])} features, datasets {base.datasets}")
  avaliacao = core_completa.avaliacao_completa(
    conjs.__getitem__, None, definicao['features'], denominador,
    progresso=lambda e: print(f"  etapa {e['passo'] + 1}/{e['passos']}: {e['etapa']}"),
    perfil_qoe=core_modelos.perfil_de(registro, nome))
  removidas = avaliacao['removidas_por_vazamento']
  if removidas:
    print(f'features com vazamento fora da conta: {removidas}')
  usadas = [f for f in definicao['features'] if f not in removidas]
  print('  treinando os modelos finais')
  pacote = core_pacote.treinar(conjs, usadas, denominador)
  versao = {'features': definicao['features'], 'denominador': denominador,
            'cobertura': core_features.cobertura_tr069(definicao['features'], base.tabela, base.catalogo)}
  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  run_id = registrar(nome, versao, conjs, avaliacao, pacote, [impressoes[i] for i in base.datasets])
  for alvo, p in core_registro_mlflow.ALVOS.items():
    bloco = avaliacao[alvo]
    print(f"{alvo}: R² {bloco['pooled']} (90%: {(bloco.get('intervalos') or {}).get('pooled')}), MAE {bloco['mae']}")
  print(f"secundárias: nota por cômodo {avaliacao['comodo']['nota']}, "
        f"atende completo {avaliacao['atende_completo']['media']}")
  print(f'run {run_id} em "{EXPERIMENTO}" ({core_registro_mlflow.uri_rastreamento()})')


if __name__ == '__main__':
  main()
```

A avaliação recebe a lista de features da versão inteira (ela mesma tira as de vazamento e devolve `removidas_por_vazamento`); o treino recebe a lista já sem elas. Os parâmetros do run levam a lista inteira, como nos runs do Studio, e `removidas_por_vazamento` diz o que saiu.

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py' 2>&1 | tail -3`
Expected: `Ran 9 tests` e `OK` (cerca de 40 s)

---

### Task 8: guarda de isolamento dos testes novos

**Files:**
- Modify: `tests/test_registro_mlflow.py` (classe `TestIsolamentoDosTestes`)

- [ ] **Step 1: Acrescentar o teste**

Dentro de `class TestIsolamentoDosTestes`, depois do método que já existe:

```python
  def test_testes_do_pipeline_usam_banco_temporario(self):
    """Os testes de pacote_mlflow e versao_mlflow gravam runs de verdade: sem MLFLOW_TRACKING_URI
    temporário, eles iriam para o mlflow.db da raiz."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    faltam = []
    for arq in sorted(os.listdir(pasta)):
      if not arq.endswith('.py') or arq == os.path.basename(__file__):
        continue
      with open(os.path.join(pasta, arq), encoding='utf-8') as f:
        texto = f.read()
      if re.search(r'pacote_mlflow|versao_mlflow', texto) and 'MLFLOW_TRACKING_URI' not in texto:
        faltam.append(arq)
    self.assertEqual(faltam, [])
```

- [ ] **Step 2: Rodar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registro_mlflow.py' 2>&1 | tail -3`
Expected: `OK` (26 testes)

- [ ] **Step 3: Rodar a suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -3 && node --test tests/js/logica.test.js 2>&1 | grep -E '^# (pass|fail)'`
Expected: `OK` com 774 testes de Python (747 de antes mais 27 novos) em cerca de 7 minutos, e `# pass 26`, `# fail 0` no JS.

- [ ] **Step 4: Sugerir commit**

Arquivos: `src/ml/versao_mlflow.py`, `tests/test_versao_mlflow.py`, `tests/test_registro_mlflow.py`
Mensagem: `feat(pipeline): comando versao_mlflow treina, avalia e grava um run`

---

### Task 9: rodada real da v5

Esta tarefa grava no MLflow de trabalho da raiz (`mlflow.db` e `mlruns/`, os dois fora do git). É o uso real do comando.

- [ ] **Step 1: Rodar o comando**

Run: `MODELO=v5 venv/bin/python src/ml/versao_mlflow.py 2>&1 | grep -vE 'INFO|WARNING mlflow|UserWarning|color_warning|^$' | tail -14`
Expected (cerca de 7 minutos): as seis etapas da avaliação, `treinando os modelos finais`, quatro linhas de alvo, a linha `secundárias: nota por cômodo 0.7222, atende completo 0.661` e a linha final com o id do run.

- [ ] **Step 2: Conferir as métricas contra a referência de 2026-11-10**

Os valores abaixo são os da avaliação completa da v5 no conjunto canônico, medidos em 2026-11-10 antes deste plano. Eles só valem enquanto `data/`, `column_provenance.json` e as réguas não mudarem.

Run:

```bash
venv/bin/python - <<'E'
import sys
sys.path.insert(0, 'src')
from ml import versao_mlflow as V
from ml.core import registro_mlflow as R
REF = {'down_pooled': 0.7455, 'down_mae': 59.2212, 'up_pooled': 0.7387, 'up_mae': 55.96,
       'lat_pooled': -0.1261, 'lat_mae': 22.5762, 'jit_pooled': -0.0813, 'jit_mae': 15.7487,
       'lat_cobertura_q90': 0.9111, 'jit_cobertura_q90': 0.9081, 'lat_pinball_q90': 11.2792,
       'jit_pinball_q90': 7.5135, 'comodo_nota': 0.7222, 'jogo_nota': 0.6735,
       'atende_completo': 0.661, 'atende_throughput': 0.6611, 'atende_ajustado': 0.8219}
cli = R.cliente()
exp = cli.get_experiment_by_name(V.EXPERIMENTO)
run = cli.search_runs([exp.experiment_id], order_by=['attributes.start_time DESC'], max_results=1)[0]
m = run.data.metrics
ruins = {k: (m.get(k), v) for k, v in REF.items() if m.get(k) is None or abs(m[k] - v) > 1e-9}
print(run.info.run_id, run.info.status, '| métricas:', len(m), '| divergentes:', ruins or 'nenhuma')
print('dado:', [(i.dataset.name, i.dataset.digest) for i in run.inputs.dataset_inputs])
print('tags:', {k: v for k, v in run.data.tags.items() if not k.startswith('mlflow.')})
E
```

Expected: `FINISHED`, `divergentes: nenhuma`, um dataset `qoe-wifi` e as tags `modelo=v5`, `metrica_principal`, `versao_comodo`, `versao_regua` e `git_arvore`. Se alguma métrica divergir, pare e avise o Lucas: ou os dados mudaram desde 2026-11-10, ou o comando não está avaliando como o Studio.

- [ ] **Step 3: Carregar o pacote num processo novo, fora do repositório**

Run (troque `<RUN_ID>` pelo id impresso no Step 2):

```bash
RAIZ=$(pwd) && cd /tmp && MLFLOW_TRACKING_URI=sqlite:///$RAIZ/mlflow.db $RAIZ/venv/bin/python - <<'E'
import sys
import mlflow, numpy as np, pandas as pd
modelo = mlflow.pyfunc.load_model('runs:/<RUN_ID>/pacote')
linhas = modelo.input_example
print(modelo.predict(linhas).round(2).T)
vazias = pd.DataFrame({c: [np.nan] for c in linhas.columns})
print(modelo.predict(vazias).round(2).T)
print('ml.core veio de:', sys.modules['ml.core.pacote'].__file__)
E
cd $RAIZ
```

Expected: uma tabela com as 8 saídas para as 5 linhas do exemplo e outra para uma linha com tudo ausente, as duas sem NaN, e o caminho de `ml.core` dentro de `mlruns/pipeline/`, não em `src/`. A linha vazia mostra só que o pacote não quebra quando falta tudo; o número dela vem da imputação do modelo.

- [ ] **Step 4: Medir o tamanho do pacote**

Run: `du -sh mlruns/pipeline && du -sh mlruns/pipeline/models/*/artifacts/artifacts | tail -1`
Expected: anotar os dois valores para o CHANGELOG. Sem compressão seriam cerca de 45 MB por modelo da régua (quatro na v5).

- [ ] **Step 5: Medir a igualdade com a avaliação nos dados reais**

Salvar o script abaixo em `/tmp/igualdade_real.py` (fora do repositório; ele não é versionado) e rodar da raiz:

```python
"""Seção 4.3 da spec nos dados reais: o pacote treinado sem um prédio contra a previsão da avaliação para esse prédio."""
import dataclasses, os, sys, time, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else 'src')
import numpy as np
from ml.core import avaliacao as A, carga, modelos, pacote as P, quantis as Q
from ml.core.sites import teto_wan

registro = modelos.carregar()
nome = os.environ.get('MODELO') or registro['ativo']
versao = registro['versoes'][nome]
conjs = {alvo: carga.carregar(alvo) for alvo in P.PREFIXOS}
vazadas = [c for c, k in conjs['speedtest_down_mbps'].classes.items() if k is not None and k.vazamento]
features = [f for f in versao['features'] if f not in vazadas]
den = versao.get('denominador') or {}
t = time.time()
vazao = {alvo: A.prever_fora_do_fold(conjs[alvo].df, features, alvo, vazadas, denominador=den.get(alvo)) for alvo in P.SAIDA_VAZAO}
quantis = {alvo: Q.prever_quantis_fora_do_fold(conjs[alvo].df, features, alvo, vazadas) for alvo in Q.ALVOS_QUANTILICOS}
print(f'versão {nome}; avaliação em {round(time.time() - t)} s')
for predio in sorted(conjs['speedtest_down_mbps'].df['_site'].unique()):
  pacote = P.treinar({a: dataclasses.replace(c, df=c.df[c.df['_site'] != predio]) for a, c in conjs.items()}, features, den)
  difs = {}
  for alvo, prev in vazao.items():
    fora = conjs[alvo].df.loc[prev.index[prev['_site'] == predio]]
    yhat = prev.loc[fora.index, 'yhat'].to_numpy()
    teto = teto_wan(predio, alvo)
    livres = np.ones(len(fora), dtype=bool) if teto is None else yhat < teto
    saida = P.prever(pacote, fora)[0][P.SAIDA_VAZAO[alvo]].to_numpy()
    difs[P.PREFIXOS[alvo]] = float(np.abs(saida - yhat)[livres].max()) if livres.any() else 0.0
    difs[P.PREFIXOS[alvo] + '_cortadas'] = int((~livres).sum())
  for alvo, prev in quantis.items():
    fora = conjs[alvo].df.loc[prev.index[prev['_site'] == predio]]
    saida = P.prever(pacote, fora)[0]
    difs[P.PREFIXOS[alvo]] = max(float(np.abs(saida[f'{alvo}_{a}'].to_numpy() - prev.loc[fora.index, b].to_numpy()).max())
                                 for a, b in (('p50', 'q50'), ('p90', 'q90'), ('p90_bruto', 'q90_bruto')))
  print(predio, {k: (v if isinstance(v, int) else float(f'{v:.3g}')) for k, v in difs.items()})
print(f'total {round(time.time() - t)} s')
```

Run: `venv/bin/python /tmp/igualdade_real.py 2>&1 | tail -9`
Expected (cerca de 10 minutos): os mesmos valores da seção "O que já foi provado" deste plano. Anotar a maior diferença por alvo para o CHANGELOG.

---

### Task 10: documentação

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`

- [ ] **Step 1: README, "How to run"**

No bloco de comandos de "How to run", depois da linha de `qoe_mlflow.py`:

```bash
MODELO=v5 venv/bin/python src/ml/versao_mlflow.py                  # one run: evaluation, model package and data version
```

E, no parágrafo que explica as variáveis logo abaixo do bloco, acrescentar ao fim:

```markdown
`versao_mlflow.py` takes `MODELO` and `DATASETS` the same way and takes about 7 minutes per version.
```

- [ ] **Step 2: README, seção "MLflow"**

Acrescentar um item à lista da seção, depois do item que começa com "The Studio logs to the working MLflow by itself":

```markdown
- `src/ml/versao_mlflow.py` logs one run per version to the experiment "MLflow Wifi Pipeline" in the working MLflow: the full evaluation (the same numbers as the Studio), a single model package (`runs:/<run_id>/pacote`, a pyfunc that takes rows with the TR-181 counters and returns download, upload and the p50 and p90 of latency and jitter) and the data version (dataset `qoe-wifi`, with the dataset fingerprints as a parameter). The headline metrics are the errors of the four predictions; the per-room ruler and the "atende" scores are logged as secondary metrics, with the ruler versions as tags. The package carries its own copy of `src/ml/core`, so it loads without the repository. It does not cap predictions at the WAN ceiling, which the evaluation does.
```

- [ ] **Step 3: CHANGELOG**

Acrescentar no topo de `CHANGELOG.md`, trocando os cinco valores entre `<...>` pelos medidos na Task 9 (id do run, tamanho de `mlruns/pipeline`, tamanho dos modelos do pacote, maior diferença de vazão e maior diferença de quantis):

```markdown
# Changelog — Comando único: treina, avalia e grava uma versão no MLflow

**Data:** 2026-11-10

## Por quê

Segundo passo da troca do Studio pelo MLflow (`docs/pipeline/2026-11-10-inventario-studio-mlflow.md`). Uma
versão estava espalhada em três experimentos que não mediam nem guardavam a mesma coisa: a avaliação do Studio
media com o modelo da régua e não guardava modelo; `regression_mlflow.py` guardava 6 modelos por alvo sem
escolher um; nenhum run apontava para a versão do dado.

## Decisões

- O modelo do run é o modelo da régua, um por alvo: o que é medido é o que é entregue.
- A métrica principal é o erro das quatro previsões. A régua por cômodo e os "atende" são secundárias, com a
  versão de cada régua em tag. A pesquisa de 2026-11-09 não validou nenhuma das duas réguas, e o erro das
  previsões não depende de régua.
- O run guarda um pacote único por versão, com a receita de previsão em código.

## Mudanças

- `core/pacote.py` (novo): `treinar` ajusta os modelos finais pela mesma receita da avaliação e `prever`
  devolve download, upload e p50, p90 e p90 bruto de latência e jitter. O pacote não corta no teto de WAN.
- `core/pacote_mlflow.py` (novo): grava e carrega o pacote como modelo pyfunc, com `src/ml/core` embutido.
- `versao_mlflow.py` (novo): `MODELO=<versão> venv/bin/python src/ml/versao_mlflow.py` grava um run em
  "MLflow Wifi Pipeline" com métricas por alvo e por prédio, o pacote, o dataset de entrada e quatro arquivos.
- `core/registro_mlflow.py`: `tags_git()` público.
- Testes: `test_pacote.py`, `test_pacote_mlflow.py` e `test_versao_mlflow.py` (25 testes), mais dois em
  `test_registro_mlflow.py`. Nenhum grava no `mlflow.db` da raiz.
- Não mudaram: `modelos.json`, o Studio, `regression_mlflow.py`, `qoe_mlflow.py` e os benchmarks.

## Efeito medido

- Run da v5 no conjunto canônico: `<RUN_ID>`. As 17 métricas de referência (R², MAE, cobertura e pinball do
  p90, nota por cômodo, apto para jogo e os três "atende") são iguais às da avaliação do Studio.
- O pacote carrega num processo novo, fora do repositório, e prevê.
- Tamanho: `<TAMANHO_PIPELINE>` em `mlruns/pipeline`, dos quais `<TAMANHO_MODELOS>` são os modelos.
- Igualdade com a avaliação (pacote treinado sem um prédio contra a previsão da avaliação para ele): maior
  diferença de `<DIF_VAZAO>` Mbps em download e upload e de `<DIF_QUANTIS>` ms em latência e jitter.

## Como conferir

No MLflow da raiz, experimento "MLflow Wifi Pipeline": um run `v5-pipeline` com o modelo `pacote` e o dataset
`qoe-wifi`. Para carregar: `mlflow.pyfunc.load_model('runs:/<RUN_ID>/pacote')`.
```

- [ ] **Step 4: Inventário**

Em `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`, na seção "Ordem proposta", trocar o item 3 por:

```markdown
3. Criar o comando único de avaliação, que grava um run com modelo, avaliação, métricas por prédio
   e versão do dado. Feito em 2026-11-10: `src/ml/versao_mlflow.py`
   (spec em `docs/superpowers/specs/2026-11-10-versao-mlflow-design.md`).
```

- [ ] **Step 5: Conferir que o README e o CHANGELOG não ficaram com marcador**

Run: `grep -n '<RUN_ID>\|<TAMANHO\|<DIF_' README.md CHANGELOG.md`
Expected: nenhuma linha.

- [ ] **Step 6: Sugerir commit**

Arquivos: `README.md`, `CHANGELOG.md`, `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`
Mensagem: `docs: README, changelog e inventário do comando versao_mlflow`
