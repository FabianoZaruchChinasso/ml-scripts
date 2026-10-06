# CQR do p90 de latência e jitter — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O p90 de latência e jitter passa a ser corrigido por calibração conformal (CQR) calculada em LOGO interno nos prédios de treino, na régua e no modelo de produção.

**Architecture:** `src/ml/core/quantis.py` ganha `correcao_conformal` (LOGO entre prédios, escores juntos, nível de amostra finita) e `prever_quantis_fora_do_fold` passa a somar essa correção ao p90 em escala log (`conformal=True` por padrão). `resumir_quantis` passa a relatar a correção por prédio. `regression_mlflow.py` calcula a correção de produção com todos os prédios e a registra em `conformal.json`. O Studio não muda de código.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn, MLflow. Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-06-cqr-latencia-jitter-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add` nem `git stash`.** O usuário faz commit à mão.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 363 tests`, `OK`.
- `tests/test_studio_assistente.py` só roda por `discover`: `python3 -m unittest discover -s tests -p "test_studio_assistente.py"`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último.
- A frente D (`quantis.py`, `test_quantis.py` e o resto) ainda não foi commitada: edite os arquivos como estão na árvore de trabalho.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/quantis.py` | `correcao_conformal`; `prever_quantis_fora_do_fold(..., conformal=True)` com colunas `correcao` e `sem_correcao`; `resumir_quantis` com `correcao_por_local` e `sem_correcao` |
| `src/ml/core/avaliacao.py` | `VERSAO_REGUA = '2026-10-06.1'` |
| `src/ml/regression_mlflow.py` | `treinar_quantis` registra a correção de produção (`correcao_log_q90` e `conformal.json`) |
| `tests/test_quantis.py` | Testes novos; os que dependem do p90 cru passam a usar `conformal=False` |
| `CHANGELOG.md` | Entrada nova no topo |

---

### Task 1: `correcao_conformal`

**Files:**
- Modify: `src/ml/core/quantis.py`
- Test: `tests/test_quantis.py`

- [ ] **Step 1: Escrever o teste que falha**

Acima do bloco `__main__` de `tests/test_quantis.py`:

```python
class TestCorrecaoConformal(unittest.TestCase):
  def test_nivel_de_amostra_finita_com_escores_juntos(self):
    # Estimador constante 0: os escores são os próprios y. Com n = 30 escores, o nível é
    # ceil(31 * 0,9) / 30 = 0,9333, e o quantil 'higher' dá 29 (o quantil 0,9 ingênuo daria 28).
    X = pd.DataFrame({'x': np.arange(30, dtype=float)})
    y = pd.Series(np.arange(1, 31, dtype=float))
    sites = pd.Series(['a'] * 10 + ['b'] * 10 + ['c'] * 10)
    self.assertEqual(Q.correcao_conformal(X, y, sites, 0.9, estimador=Constante(0.0)), 29.0)

  def test_um_predio_so_devolve_none(self):
    X = pd.DataFrame({'x': np.arange(5, dtype=float)})
    y = pd.Series(np.arange(5, dtype=float))
    self.assertIsNone(Q.correcao_conformal(X, y, pd.Series(['a'] * 5), 0.9, estimador=Constante(0.0)))

  def test_usa_o_modelo_quantilico_por_padrao(self):
    conj = conjunto()
    from ml.core.features import matriz
    X = matriz(conj.df, ['router_snr'])
    y = np.log1p(conj.df['latency_ms'].astype(float))
    c = Q.correcao_conformal(X, y, conj.df['_site'], 0.9)
    self.assertIsInstance(c, float)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestCorrecaoConformal -v`
Expected: `AttributeError: module 'ml.core.quantis' has no attribute 'correcao_conformal'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/quantis.py`, acrescente `import math` no topo do bloco de imports (antes de `import numpy as np`) e, logo depois de `cobertura`:

```python
def correcao_conformal(X: pd.DataFrame, y_log, sites, q: float = 0.9, estimador=None):
  """Termo conformal (CQR) do quantil `q`, em escala log, por LOGO entre os prédios de `sites`.

  Para cada prédio, ajusta o modelo sem ele e mede quanto o real passou do quantil previsto
  (escore = y_log - previsto). A correção é o quantil de nível de amostra finita,
  min(1, ceil((n + 1) * q) / n), de todos os escores juntos. Devolve None com menos de
  2 prédios, porque não há como deixar um de fora.
  """
  grupos = np.asarray(sites)
  unicos = pd.unique(grupos)
  if len(unicos) < 2:
    return None
  y = np.asarray(y_log, dtype=float)
  escores = []
  for predio in unicos:
    fora = grupos == predio
    modelo = clone(estimador) if estimador is not None else modelo_quantil(q)
    modelo.fit(X[~fora], y[~fora])
    escores.append(y[fora] - np.asarray(modelo.predict(X[fora]), dtype=float))
  todos = np.concatenate(escores)
  if not len(todos):
    return None
  nivel = min(1.0, math.ceil((len(todos) + 1) * q) / len(todos))
  return float(np.quantile(todos, nivel, method='higher'))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 2: Correção aplicada às previsões fora do fold

**Files:**
- Modify: `src/ml/core/quantis.py` (`_COLUNAS`, `prever_quantis_fora_do_fold`)
- Test: `tests/test_quantis.py` (`TestPrevisoes`)

- [ ] **Step 1: Ajustar os testes existentes e escrever os novos**

Em `tests/test_quantis.py`, dentro de `TestPrevisoes`:

1. Em `test_folds_por_predio_e_colunas`, troque a asserção da lista de colunas por:

```python
    self.assertEqual(list(prev.columns), ['_linha', 'y', 'q50', 'q90', 'cruzado', 'correcao', 'sem_correcao',
                                          '_site', '_pos'])
```

2. Em `test_volta_da_escala_log` e em `test_corta_em_zero_e_corrige_cruzamento`, acrescente `conformal=False` à chamada (estes testes conferem o p90 cru):

```python
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est, conformal=False)
```

3. Acrescente ao fim da classe `TestPrevisoes`:

```python
  def test_conformal_soma_a_correcao_ao_p90_em_escala_log(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(0.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    self.assertTrue((prev['correcao'] > 0).all())
    self.assertFalse(prev['sem_correcao'].any())
    np.testing.assert_allclose(prev['q90'], np.maximum(np.expm1(prev['correcao']), prev['q50']))

  def test_correcao_do_fold_vem_so_dos_predios_de_treino(self):
    from ml.core.features import matriz
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(0.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    treino = conj.df[conj.df['_site'] != 'residencia']
    esperado = Q.correcao_conformal(matriz(treino, ['router_snr']),
                                    np.log1p(treino['latency_ms'].astype(float)), treino['_site'], 0.9,
                                    estimador=Constante(0.0))
    np.testing.assert_allclose(prev.loc[prev['_site'] == 'residencia', 'correcao'], esperado)

  def test_um_predio_de_treino_fica_sem_correcao(self):
    f = frame()
    f = f[f['local'].isin(['sala', 'quarto', 'cwpb-1', 'cwpb-2'])]
    conj = C.preparar({'a.csv': f}, 'latency_ms', TABELA, catalogo=())
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    self.assertTrue(prev['sem_correcao'].all())
    self.assertTrue((prev['correcao'] == 0).all())

  def test_sem_conformal_nao_corrige(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], conformal=False)
    self.assertTrue((prev['correcao'] == 0).all())
    self.assertFalse(prev['sem_correcao'].any())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestPrevisoes -v 2>&1 | tail -15`
Expected: falhas com `TypeError: ... unexpected keyword argument 'conformal'` e diferença na lista de colunas.

- [ ] **Step 3: Implementar**

Em `src/ml/core/quantis.py`:

1. Troque `_COLUNAS`:

```python
_COLUNAS = ['_linha', 'y', 'q50', 'q90', 'cruzado', 'correcao', 'sem_correcao', '_site', '_pos']
```

2. Troque a função `prever_quantis_fora_do_fold` inteira por:

```python
def prever_quantis_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas,
                                estimadores: dict = None, conformal: bool = True) -> pd.DataFrame:
  """p50 e p90 de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Treina em log1p(y) e volta com expm1, cortado em 0. Com `conformal`, soma ao p90 (em
  escala log) a correção de `correcao_conformal`, calculada só com os prédios de treino do
  fold; sem pelo menos 2 deles, a correção é 0 e a linha fica com `sem_correcao`. Se o p90
  sair abaixo do p50 (quantis cruzados), o p90 passa a valer o p50 e a linha fica com
  `cruzado`. `estimadores` ({quantil: estimador}) troca os modelos; são clonados a cada fold.
  Devolve _linha, y (em ms), q50, q90, cruzado, correcao, sem_correcao, _site, _pos,
  indexados como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS)
  estimadores = estimadores or {}
  sub = df[df[y_col].notna()]
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  y_log = np.log1p(y.clip(lower=0))
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y_log, sub['_site']):
    em_log = {}
    for q in QUANTIS:
      base = estimadores.get(q)
      modelo = clone(base) if base is not None else modelo_quantil(q)
      modelo.fit(fold.X_train, fold.y_train)
      em_log[q] = np.asarray(modelo.predict(fold.X_test), dtype=float)
    correcao = None
    if conformal:
      correcao = correcao_conformal(fold.X_train, fold.y_train, fold.train_site_ids, 0.9, estimadores.get(0.9))
    termo = 0.0 if correcao is None else correcao
    em_log[0.9] = em_log[0.9] + termo
    previstos = {q: np.clip(np.expm1(v), 0, None) for q, v in em_log.items()}
    cruzado = previstos[0.9] < previstos[0.5]
    previstos[0.9] = np.maximum(previstos[0.9], previstos[0.5])
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': y.loc[indice].to_numpy(),
                                'q50': previstos[0.5], 'q90': previstos[0.9], 'cruzado': cruzado,
                                'correcao': termo, 'sem_correcao': conformal and correcao is None,
                                '_site': fold.test_site, '_pos': posicao.loc[indice].to_numpy()},
                               index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS)
  return pd.concat(partes)
```

(`fold.train_site_ids` já existe no dataclass `Fold` de `src/ml/core/splits.py`: são os prédios das linhas de treino, alinhados com `fold.X_train`.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK` (os testes do Studio que usam quantis continuam passando; o fixture deles tem 3 prédios, então cada fold tem 2 de treino e a correção é calculada).

---

### Task 3: Resumo com a correção por prédio e versão da régua

**Files:**
- Modify: `src/ml/core/quantis.py` (`resumir_quantis`)
- Modify: `src/ml/core/avaliacao.py` (`VERSAO_REGUA`)
- Test: `tests/test_quantis.py` (`TestResumo`)

- [ ] **Step 1: Escrever o teste que falha**

Ao fim da classe `TestResumo`:

```python
  def test_sem_coluna_de_correcao(self):
    r = Q.resumir_quantis(previsto([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]), 1)
    self.assertEqual((r['correcao_por_local'], r['sem_correcao']), ({}, 0))

  def test_correcao_por_predio(self):
    prev = previsto([10.0, 20.0, 30.0, 40.0], [10.0, 20.0, 30.0, 40.0], [15.0, 25.0, 35.0, 45.0])
    prev['correcao'] = [0.5, 0.5, 0.8, 0.8]
    prev['sem_correcao'] = [False, False, False, False]
    r = Q.resumir_quantis(prev, 1)
    self.assertEqual(r['correcao_por_local'], {'s1': 0.5, 's2': 0.8})
    self.assertEqual(r['sem_correcao'], 0)

  def test_vazio_traz_campos_de_correcao(self):
    r = Q.resumir_quantis(pd.DataFrame(columns=['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']), 0)
    self.assertEqual((r['correcao_por_local'], r['sem_correcao']), ({}, 0))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_quantis.TestResumo -v 2>&1 | tail -8`
Expected: `KeyError: 'correcao_por_local'`

- [ ] **Step 3: Implementar**

Em `resumir_quantis` (`src/ml/core/quantis.py`):

1. Na linha do retorno para `prev.empty`, acrescente os dois campos:

```python
    return dict(resumo, pinball={}, cobertura={}, por_local={}, intervalos={}, cruzados=0, mediana_mae=None,
                correcao_por_local={}, sem_correcao=0)
```

2. Logo depois da linha `resumo['cruzados'] = ...`, acrescente:

```python
  # A correção conformal é uma por fold, então é constante dentro de cada prédio de teste.
  if 'correcao' in prev.columns:
    resumo['correcao_por_local'] = {s: round(float(g['correcao'].iloc[0]), 4)
                                    for s, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0])}
    resumo['sem_correcao'] = int(prev['sem_correcao'].astype(bool).sum())
  else:
    resumo['correcao_por_local'], resumo['sem_correcao'] = {}, 0
```

3. Na docstring de `resumir_quantis`, acrescente a linha: `` `correcao_por_local` é o termo conformal (em log) usado em cada prédio de teste. ``

4. Em `src/ml/core/avaliacao.py`, troque `VERSAO_REGUA = '2026-10-05.2'` por:

```python
VERSAO_REGUA = '2026-10-06.1'
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_quantis -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 4: Correção de produção no MLflow

**Files:**
- Modify: `src/ml/regression_mlflow.py` (`treinar_quantis` e a docstring do topo)

- [ ] **Step 1: Registrar a correção**

Em `src/ml/regression_mlflow.py`:

1. Na docstring do topo, troque a frase `Para ALVO=latency_ms ou jitter_ms, treina os dois modelos quantílicos (p50 e p90) em vez da varredura de árvores.` por:

```
Para ALVO=latency_ms ou jitter_ms, treina os dois modelos quantílicos (p50 e p90) em vez da
varredura de árvores, e registra em conformal.json a correção conformal do p90 (em escala log) que
a produção soma à previsão do modelo antes de voltar para ms.
```

2. Em `treinar_quantis`, logo depois do laço `for q in core_quantis.QUANTIS:` que registra os modelos (o que termina em `serialization_format='skops')`), acrescente:

```python
    # A produção não vê prédio novo durante o treino: a correção usa LOGO entre todos os prédios.
    correcao = core_quantis.correcao_conformal(X, y_log, conj.df['_site'], 0.9)
    termo = 0.0 if correcao is None else correcao
    mlflow.log_metric('correcao_log_q90', termo)
    mlflow.log_dict({'quantil': 0.9, 'correcao_log': termo, 'escala': 'log1p',
                     'uso': 'q90_ms = expm1(predict(X) + correcao_log)',
                     'sem_correcao': correcao is None,
                     'versao_regua': core_avaliacao.VERSAO_REGUA}, 'conformal.json')
```

3. Ainda em `treinar_quantis`, logo depois do `print(f"Quantis {ALVO}: ...")`, acrescente:

```python
    print(f'  correção conformal do p90 (log): {termo:.4f}; por prédio na régua: {resumo["correcao_por_local"]}')
```

- [ ] **Step 2: Conferir import**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); import ml.regression_mlflow as m; print(m.ALVO, callable(m.treinar_quantis))"`
Expected: `speedtest_down_mbps True`

- [ ] **Step 3: Rodar de verdade**

Run: `ALVO=latency_ms MODELO=v3-tr069 timeout 580 python3 src/ml/regression_mlflow.py 2>&1 | grep -v Warning | tail -12`
Expected: os avisos da carga, a linha `Quantis latency_ms: cobertura {...}` com a cobertura do p90 pooled entre 0,80 e 0,95, a linha `correção conformal do p90 (log): ...` e uma linha por prédio. Sem traceback. Leva cerca de 1 a 2 minutos.

Run: `python3 -c "import mlflow; c = mlflow.MlflowClient(); r = c.search_runs([c.get_experiment_by_name('MLflow Wifi Regressions').experiment_id], order_by=['start_time DESC'], max_results=1)[0]; print(r.info.run_name, r.data.metrics.get('correcao_log_q90')); print([a.path for a in c.list_artifacts(r.info.run_id)])"`
Expected: o nome do run `v3-tr069-quantis-latency_ms`, o valor da correção e `conformal.json` na lista de artefatos.

---

### Task 5: Experimento e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (entrada nova no topo)

- [ ] **Step 1: Medir com e sem CQR**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M, quantis as Q
from ml.studio import api
reg = M.carregar()
for alvo in ('latency_ms', 'jitter_ms'):
  conj = C.carregar(alvo)
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  for nome in ('v2-tr069', 'v3-tr069'):
    feats = [f for f in reg['versoes'][nome]['features'] if f in conj.df.columns and f not in vazadas]
    for conformal in (False, True):
      r = Q.resumir_quantis(Q.prever_quantis_fora_do_fold(conj.df, feats, alvo, vazadas, conformal=conformal),
                            len(feats))
      print(alvo, nome, 'CQR' if conformal else 'cru', 'cobertura', r['cobertura'],
            'IC cob q90', r['intervalos'].get('cobertura_q90'), 'pinball', r['pinball'],
            'correcao', r['correcao_por_local'], 'sem_correcao', r['sem_correcao'], 'cruzados', r['cruzados'])
      print('   cobertura q90 por prédio', json.dumps({s: m['cobertura']['q90'] for s, m in r['por_local'].items()}))
ds = ','.join(C.ids_padrao(C.descobertos()))
for nome in ('v2-tr069', 'v3-tr069'):
  ac = api.avaliacao_completa(ds, '', reg['versoes'][nome]['features'])['atende_completo']
  print(nome, 'atende_completo (CQR)', json.dumps(ac, ensure_ascii=False))
EOF
```

Expected: para cada alvo e versão, uma linha "cru" e uma "CQR", com cobertura por prédio, e o "atende completo" das duas versões. Anote os números para o CHANGELOG.

- [ ] **Step 2: Veredito de promoção com a régua `2026-10-06.1`**

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

Expected: um `promocao` por alvo, com `delta_pinball`, `cobertura` (agora corrigida) e `veredito`.

- [ ] **Step 3: Aplicar o critério de aceite (spec, seção 7.3)**

Com a cobertura pooled do p90 da `v3-tr069` com CQR (Step 1): se ficar entre 0,80 e 0,95 nos dois alvos, a CQR é **aceita**. Prédios acima de 0,95 são registrados como conservadorismo. Se a pooled sair da faixa, a conclusão é "não aceita; próxima recomendação: média das correções por prédio".

- [ ] **Step 4: Escrever a entrada do CHANGELOG**

No topo de `CHANGELOG.md`, antes da entrada "Latência e jitter por quantis", no mesmo estilo das entradas existentes. Use **só** números impressos nos Steps 1 e 2:

- **Por quê:** a cobertura do p90 sem correção ficava abaixo de 0,80 em três dos quatro prédios (a entrada anterior registra os números), e o critério da spec da frente D pedia a CQR.
- **Mudanças:**
  - `core/quantis.py`: `correcao_conformal` (LOGO entre os prédios de treino, escores juntos, nível de amostra finita) somada ao p90 em escala log por padrão, com as colunas `correcao` e `sem_correcao` e o campo `correcao_por_local` no resumo;
  - régua `2026-10-06.1`;
  - `regression_mlflow.py` registra a correção de produção em `correcao_log_q90` e `conformal.json`.
- **Efeito medido:**
  - uma tabela "cru × CQR" por alvo e versão, com cobertura p50, cobertura p90 (com intervalo), pinball p90 e a correção por prédio;
  - uma tabela da cobertura do p90 por prédio da `v3-tr069`, cru × CQR;
  - o "atende completo" com CQR das duas versões, por aplicação, comparado com o da entrada anterior (sem CQR), com destaque para Jogo em nuvem;
  - os vereditos de promoção.
- **Critério de aceite:** a conclusão do Step 3.
- **Fica para depois:** a frente C.

- [ ] **Step 5: Conferir**

Run: `sed -n 1,80p CHANGELOG.md | grep -n "<\|TBD\|TODO"`
Expected: nenhuma linha.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`
