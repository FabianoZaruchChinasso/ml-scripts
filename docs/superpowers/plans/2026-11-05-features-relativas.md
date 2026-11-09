# Régua por cômodo: modelo de razão com features relativas à casa — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** medir, com regra de decisão fixada antes, se um modelo que prevê direto a **razão** de capacidade de cada cômodo (fração do melhor cômodo da casa) a partir de **features relativas à casa** (taxa PHY ÷ maior taxa PHY da casa; sinal e SNR menos o melhor da casa) acerta mais a classe bom / degradado / ruim do que a v5 de hoje.

**Architecture:** só o lado da capacidade da previsão muda. A verdade continua igual (referência real). Para a linha candidata, download e upload deixam de ser previstos em Mbps e divididos pela referência: o modelo (o mesmo RandomForest da régua, LOGO por prédio) aprende o alvo `dn ÷ referência real da casa` (e `up`) com as features de taxa e sinal da v5 trocadas pela versão relativa à casa. A referência das features é calculada só com entradas (taxa PHY, sinal, SNR), então existe numa casa nova. Latência, jitter e o piso absoluto continuam vindo da previsão normal da versão em Mbps. Entra só como opção do `comodo_benchmark.py` (`RELATIVAS=1`); régua padrão, `VERSAO_COMODO`, Studio e `modelos.json` não mudam.

**Tech Stack:** Python 3 (pandas, numpy, scikit-learn via `core/avaliacao.py`, unittest), MLflow 3.15.1.

## Por que (contexto para quem executa)

- Os 9 erros da v5 são de capacidade: a mesma taxa PHY rende throughput diferente em cada prédio (eficiência de upload de 0,15 a 0,73), e com o prédio de teste fora do treino o modelo erra o nível da casa inteira.
- Em 2026-10-29 foi testado treinar a **razão** (fração do V0 da casa) com as features **absolutas**: a nota caiu (v1 0,643 -> 0,564; v3 0,722 -> 0,579; CHANGELOG, seção da régua por cômodo). Com features absolutas a razão é inaprendível: 500 Mbps de PHY é o melhor cômodo de uma casa e o pior de outra.
- A hipótese deste plano: com as features **também** relativas à casa, a razão passa a ser aprendível (o cômodo com 60% da maior PHY da casa tende a ter ~60% da capacidade, em qualquer casa).
- A referência prevista (plano `2026-11-05-referencia-prevista.md`) atacou o mesmo erro de nível por outro lado e não passou na regra para a v5 (+0,040, empate).
- Por isso o benchmark roda duas linhas: `v5-rel` (razão + features relativas, a candidata) e `v5-razao-abs` (razão + features absolutas, a reprodução do teste de 2026-10-29). Se `v5-rel` > `v5-razao-abs`, o mecanismo é a relativização das features.

## Regra de decisão (fixada antes de rodar; não mude depois de ver os números)

Comparações pareadas nas mesmas 27 posições e na mesma verdade, intervalo de 90% pelas reamostras da régua (`core_comodo.comparar`):

1. **Candidato aprovado** (vira proposta de versão nova, em plano próprio) se `v5-rel` contra `v5` (régua de hoje) tiver limite inferior > 0 **e** `v5-rel` contra `piso` tiver limite inferior > 0.
2. Qualquer outro resultado: não aprovado; registrar no CHANGELOG e parar.
3. Descritivo (não decide nada): `v5-razao-abs` contra `v5`, e `v5-rel` contra `v5-razao-abs`.

As features relativas são só estas quatro, fixadas antes (todas estão na v5): `router_tx_rate_mbps` e `router_rx_rate_mbps` por razão; `router_signal_dbm` e `router_snr` por diferença. Não acrescente outras depois de ver o resultado.

**Regras do projeto para quem executa:**
- **Nunca rode `git commit` nem `git push`.** Os passos de commit só sugerem a mensagem; o Lucas commita à mão. Sem linha `Co-Authored-By`.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`.
- Sem emojis.
- Trabalhe na branch `regua-hibrida` (tem mudanças de três planos de 2026-11-05 ainda sem commit; não as reverta).
- O benchmark leva ~10 a 15 min: rode em segundo plano e espere a notificação.
- Testes: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.<Classe> -v` para iterar; no fim, `tests/test_comodo.py tests/test_studio_comodo.py tests/test_comodo_benchmark.py` inteiros em segundo plano.

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/core/comodo.py` | `RELATIVAS`, `RAZAO_DN/UP`, `referencia_features`, `relativizar`, `alvos_razao`, `prever_razao`, `classe_prevista_razao`; `classificar` aceita `razao=` |
| `tests/test_comodo.py` | classes `TestFeaturesRelativas` e `TestRazaoPrevista` |
| `src/ml/comodo_benchmark.py` | `RELATIVAS=1`: linhas `<ativa>-rel` e `<ativa>-razao-abs`, regra de decisão, runs no MLflow |
| `CHANGELOG.md` | entrada com o resultado e a decisão |

---

### Task 1: features relativas e alvo de razão no core

**Files:**
- Modify: `src/ml/core/comodo.py`
- Test: `tests/test_comodo.py`

- [ ] **Step 1: testes que falham**

Em `tests/test_comodo.py`, antes de `def conjs_sinteticos():`, acrescente:

```python
def linhas_feat(pos, n, tx, sinal, site='s1', conc=1.0, dn=100.0, up=100.0):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, 'router_tx_rate_mbps': [float(tx)] * n,
                       'router_signal_dbm': [float(sinal)] * n, 'concorrentes_mesmo_radio': [conc] * n,
                       C.DN: [dn] * n, C.UP: [up] * n})


class TestFeaturesRelativas(unittest.TestCase):
  def test_referencia_e_o_maior_valor_entre_posicoes(self):
    df = juntas(linhas_feat('sala', 10, 800, -45), linhas_feat('quarto', 10, 400, -70),
                linhas_feat('canto', 9, 1200, -30),             # poucas linhas: fora
                linhas_feat('sala', 5, 2000, -10, conc=2.0))    # não sozinha: fora
    ref = C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm'])
    self.assertEqual(ref.loc['s1', 'router_tx_rate_mbps'], 800.0)
    self.assertEqual(ref.loc['s1', 'router_signal_dbm'], -45.0)

  def test_razao_para_taxa_e_diferenca_para_db(self):
    df = juntas(linhas_feat('sala', 10, 800, -45), linhas_feat('quarto', 10, 400, -70))
    ref = C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm'])
    rel = C.relativizar(df, ref)
    quarto = rel[rel['_pos'] == 'quarto'].iloc[0]
    self.assertAlmostEqual(quarto['router_tx_rate_mbps_rel'], 0.5)
    self.assertAlmostEqual(quarto['router_signal_dbm_rel'], -25.0)
    self.assertNotIn('router_snr_rel', rel.columns)   # coluna ausente no df: não cria

  def test_mesma_fracao_em_casas_de_nivel_diferente(self):
    # Casa rica e casa pobre: o cômodo com metade da PHY tem o mesmo valor relativo.
    df = juntas(linhas_feat('a1', 10, 1200, -40, site='s1'), linhas_feat('a2', 10, 600, -60, site='s1'),
                linhas_feat('b1', 10, 300, -40, site='s2'), linhas_feat('b2', 10, 150, -60, site='s2'))
    rel = C.relativizar(df, C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm']))
    por_pos = rel.groupby('_pos')['router_tx_rate_mbps_rel'].first()
    self.assertAlmostEqual(por_pos['a2'], por_pos['b2'])

  def test_alvos_razao(self):
    df = linhas_feat('quarto', 2, 400, -70, dn=50.0, up=20.0)
    ref = pd.DataFrame({'dn': [100.0], 'up': [80.0]}, index=pd.Index(['s1'], name='_site'))
    out = C.alvos_razao(df, ref)
    self.assertAlmostEqual(out[C.RAZAO_DN].iloc[0], 0.5)
    self.assertAlmostEqual(out[C.RAZAO_UP].iloc[0], 0.25)
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestFeaturesRelativas -v`
Expected: 4 ERROR com `AttributeError` (`referencia_features`, `relativizar`, `alvos_razao`, `RAZAO_DN`).

- [ ] **Step 2: implementar**

Em `src/ml/core/comodo.py`, depois de `MIN_LINHAS_REFERENCIA = 10`, acrescente:

```python
# Experimento de 2026-11-05 (features relativas): taxas viram razão, níveis em dB viram diferença,
# contra o maior valor da casa. Fixadas antes de medir; ver docs/superpowers/plans/2026-11-05-features-relativas.md.
RELATIVAS = {'router_tx_rate_mbps': 'razao', 'router_rx_rate_mbps': 'razao',
             'router_signal_dbm': 'diferenca', 'router_snr': 'diferenca'}
# Alvos do modelo de razão: fração da capacidade do melhor cômodo da casa.
RAZAO_DN, RAZAO_UP = '_razao_dn', '_razao_up'
```

E, depois de `referencia_prevista`, acrescente:

```python
def referencia_features(df: pd.DataFrame, colunas) -> pd.DataFrame:
  """Por prédio, o maior valor entre as medianas por posição de cada coluna, com as linhas sozinhas
  no rádio e posições com MIN_LINHAS_REFERENCIA linhas (a regra de `referencia`). Só usa entradas
  (taxa PHY, sinal, SNR): numa casa nova ela existe."""
  so = sozinhas(df)
  colunas = [c for c in colunas if c in so.columns]
  valores = so[colunas].apply(pd.to_numeric, errors='coerce')
  med = valores.groupby(so['_pos']).median()
  med['_site'] = so.groupby('_pos')['_site'].first()
  med['n'] = so.groupby('_pos').size()
  return med[med['n'] >= MIN_LINHAS_REFERENCIA].groupby('_site')[colunas].max()


def relativizar(df: pd.DataFrame, ref_feat: pd.DataFrame, modos: dict = None) -> pd.DataFrame:
  """Acrescenta `<coluna>_rel` para cada coluna de `modos` (padrão RELATIVAS) presente em `df` e em
  `ref_feat`: razão (taxas) ou diferença (dB) contra a referência da casa da linha."""
  novas = {}
  for coluna, modo in (modos or RELATIVAS).items():
    if coluna not in df.columns or coluna not in ref_feat.columns:
      continue
    valor = pd.to_numeric(df[coluna], errors='coerce')
    ref = df['_site'].map(ref_feat[coluna])
    rel = valor / ref if modo == 'razao' else valor - ref
    novas[f'{coluna}_rel'] = rel.replace([np.inf, -np.inf], np.nan)
  return df.assign(**novas)


def alvos_razao(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
  """Acrescenta RAZAO_DN e RAZAO_UP: download e upload como fração da referência real da casa."""
  return df.assign(**{RAZAO_DN: pd.to_numeric(df[DN], errors='coerce') / df['_site'].map(ref['dn']),
                      RAZAO_UP: pd.to_numeric(df[UP], errors='coerce') / df['_site'].map(ref['up'])})
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestFeaturesRelativas -v`
Expected: 4 PASS.

- [ ] **Step 3: sugerir commit (o Lucas commita)**

```
feat(comodo): features relativas à casa e alvo de razão (experimento)
```

---

### Task 2: prever e classificar pela razão

**Files:**
- Modify: `src/ml/core/comodo.py` (`classificar`; novas `prever_razao`, `classe_prevista_razao`)
- Test: `tests/test_comodo.py`

- [ ] **Step 1: testes que falham**

Em `tests/test_comodo.py`, **depois** de `class TestPrevisao` (precisa de `conjs_sinteticos`), acrescente:

```python
class TestRazaoPrevista(unittest.TestCase):
  def test_classificar_com_razao_dada_ignora_a_referencia(self):
    t = C.classificar(est(100), None, LIM, razao=pd.Series([0.5], index=pd.Index(['p'], name='_pos')))
    self.assertAlmostEqual(t.loc['p', 'razao'], 0.5)
    self.assertEqual(t.loc['p', 'classe'], 'degradado')

  def test_classificar_com_razao_mantem_o_piso_absoluto(self):
    # Razão alta, mas 1,5 Mbps de download previsto: abaixo do mínimo de Navegação.
    t = C.classificar(est(1.5, up=1.5), None, LIM, razao=pd.Series([0.95], index=pd.Index(['p'], name='_pos')))
    self.assertEqual(t.loc['p', 'classe'], 'ruim')

  def test_classe_prevista_razao_usa_o_menor_entre_download_e_upload(self):
    prev = pd.DataFrame({'_linha': ['l1', 'l2'], '_pos': ['a', 'a'], '_site': ['s1', 's1'],
                         'dn': [50.0, 50.0], 'up': [50.0, 50.0], 'lat': [10.0, 10.0], 'jit': [2.0, 2.0]})
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.9, 0.9], C.RAZAO_UP: [0.6, 0.6]})
    t = C.classe_prevista_razao(prev, pr, LIM)
    self.assertAlmostEqual(t.loc['a', 'razao'], 0.6)
    self.assertEqual(t.loc['a', 'classe'], 'degradado')

  def test_prever_razao_fora_do_fold(self):
    conjs, _ = conjs_sinteticos()
    ref = pd.DataFrame({'dn': [100.0] * 3, 'up': [55.0] * 3}, index=pd.Index(['s1', 's2', 's3'], name='_site'))
    ref_feat = pd.DataFrame(index=pd.Index(['s1', 's2', 's3'], name='_site'))
    vaz = {a: [] for a in conjs}
    pr = C.prever_razao(conjs, ['x'], vaz, ref, ref_feat)
    self.assertEqual(list(pr.columns), ['_linha', C.RAZAO_DN, C.RAZAO_UP])
    self.assertEqual(len(pr), 90)
    self.assertTrue(pr[C.RAZAO_DN].between(0, 1.2).all())
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestRazaoPrevista -v`
Expected: 4 falham (`TypeError: classificar() got an unexpected keyword argument 'razao'` e `AttributeError` para `classe_prevista_razao` e `prever_razao`).

- [ ] **Step 2: `classificar` aceita a razão pronta**

Em `classificar`, troque a assinatura e o começo do corpo:

```python
def classificar(est: pd.DataFrame, ref: pd.DataFrame, limiares: dict, razao: pd.Series = None) -> pd.DataFrame:
```

Acrescente ao fim da docstring: `Com `razao` (por posição), ela substitui `dn ÷ ref` e `ref` não é usada; o piso absoluto continua olhando `dn` e `up` de `est`.`

E troque as linhas de `faltam = ...` até `razao = np.minimum(...)` por:

```python
  if razao is None:
    faltam = sorted(set(est['_site']) - set(ref.index))
    if faltam:
      raise ValueError(f'sem referência da casa para os prédios {faltam}')
    razao = np.minimum(est['dn'] / est['_site'].map(ref['dn']), est['up'] / est['_site'].map(ref['up']))
  else:
    razao = razao.reindex(est.index)
```

- [ ] **Step 3: `prever_razao` e `classe_prevista_razao`**

Depois de `alvos_razao`, acrescente:

```python
def prever_razao(conjs: dict, features, vazadas: dict, ref: pd.DataFrame, ref_feat: pd.DataFrame,
                 relativas: bool = True) -> pd.DataFrame:
  """Previsão fora do fold (LOGO por prédio) da razão de capacidade: RAZAO_DN e RAZAO_UP por `_linha`.

  O alvo de treino é a fração da referência REAL da casa (`alvos_razao`); o prédio de teste nunca entra
  no treino, então a referência dele não vaza. `relativas=True` troca as features de RELATIVAS pela
  versão `_rel` (contra `ref_feat`); `relativas=False` usa as features absolutas (o teste de 2026-10-29).
  """
  saida = {}
  for alvo, coluna in ((DN, RAZAO_DN), (UP, RAZAO_UP)):
    df = alvos_razao(conjs[alvo].df, ref)
    colunas = list(features)
    if relativas:
      df = relativizar(df, ref_feat)
      colunas = [f'{f}_rel' if f in RELATIVAS and f'{f}_rel' in df.columns else f for f in colunas]
    colunas = [f for f in colunas if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {coluna}')
    saida[coluna] = avaliacao.prever_fora_do_fold(df, colunas, coluna, vazadas[alvo]).set_index('_linha')['yhat']
  return pd.concat(saida, axis=1, join='inner').rename_axis('_linha').reset_index()


def classe_prevista_razao(prev: pd.DataFrame, prev_razao: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Classe de cada posição pela razão prevista direto: o menor entre as medianas da razão de download
  e de upload. Latência, jitter e o piso absoluto vêm de `prev` (Mbps e p90 previstos, `prever`)."""
  prev = prev[prev['_linha'].isin(set(prev_razao['_linha']))]
  r = prev_razao.set_index('_linha').reindex(prev['_linha'])
  por_pos = pd.DataFrame({'_pos': prev['_pos'].to_numpy(), 'dn': r[RAZAO_DN].to_numpy(),
                          'up': r[RAZAO_UP].to_numpy()}).groupby('_pos').median()
  return classificar(estatisticas_previstas(prev), None, limiares,
                     razao=np.minimum(por_pos['dn'], por_pos['up']))
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestRazaoPrevista tests.test_comodo.TestFeaturesRelativas tests.test_comodo.TestClassificar tests.test_comodo.TestReferenciaPrevista -v`
Expected: tudo PASS.

- [ ] **Step 4: o resto continua igual**

Run (em segundo plano): `PYTHONPATH=src venv/bin/python -m unittest tests/test_comodo.py tests/test_studio_comodo.py`
Expected: `OK`.

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
feat(comodo): previsão da razão de capacidade e classe pela razão prevista
```

---

### Task 3: `RELATIVAS=1` no benchmark

**Files:**
- Modify: `src/ml/comodo_benchmark.py`

- [ ] **Step 1: docstring e opção**

Na docstring do módulo, depois do parágrafo do `REF=prevista`, acrescente:
```
RELATIVAS=1 acrescenta, para a versão ativa, '<ativa>-rel' (prevê a razão de capacidade com as features
de core_comodo.RELATIVAS relativas à casa) e '<ativa>-razao-abs' (mesma razão, features absolutas) e
imprime a regra de decisão de docs/superpowers/plans/2026-11-05-features-relativas.md.
```

Em `main`, junto da leitura de `REF`:
```python
  relativas_on = os.environ.get('RELATIVAS') == '1'
```

- [ ] **Step 2: guardar a previsão de cada linha**

Antes do laço que monta `pos`, crie `prevs = {}`. No laço, logo depois de `prev = prev[prev['_linha'].isin(linhas)]`, acrescente `prevs[nome] = prev`.

- [ ] **Step 3: linhas candidatas e regra**

Depois do bloco `if modo_ref == 'prevista':` (o que imprime a referência prevista e a regra dela) e antes de `if os.environ.get('MLFLOW') == '1':`, acrescente:

```python
  pos_rel = {}
  if relativas_on:
    feats_ativa = registro['versoes'][ativa]['features']
    ref_feat = core_comodo.referencia_features(df, list(core_comodo.RELATIVAS))
    for rotulo, rel in ((f'{ativa}-rel', True), (f'{ativa}-razao-abs', False)):
      pr = core_comodo.prever_razao(conjs_treino, feats_ativa, vazadas, ref, ref_feat, relativas=rel)
      pr = pr[pr['_linha'].isin(linhas)]
      pos_rel[rotulo] = core_comodo.juntar(real, core_comodo.classe_prevista_razao(prevs[ativa], pr, limiares))
      if tuple(pos_rel[rotulo].index) != tuple(pos[ativa].index):
        raise SystemExit(f'{rotulo} não cobre as mesmas posições de {ativa}')
    print(f'\nModelo de razão (referência das features: maior valor da casa; relativas: '
          f'{", ".join(core_comodo.RELATIVAS)})')
    print('Referência das features por prédio:')
    print(ref_feat.round(1).to_string())
    for rotulo, p in pos_rel.items():
      r = core_comodo.nota(p, amostras)
      c_ativa = core_comodo.comparar(p, pos[ativa], amostras)
      c_piso = core_comodo.comparar(p, pos[PISO], amostras)
      m, graves = core_comodo.confusao(p)
      print(f'  {rotulo:<16} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs {ativa} {c_ativa["diferenca"]:+.3f} '
            f'({_faixa(c_ativa["intervalo"])}) {c_ativa["resultado"]} | vs piso {c_piso["diferenca"]:+.3f} '
            f'({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | acertos {int((p["real"] == p["previsto"]).sum())}'
            f'/{len(p)} | graves {graves}')
      print('    acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
      erradas = p[p['real'] != p['previsto']]
      print('    erradas: ' + ', '.join(f'{i} ({l.real}->{l.previsto})' for i, l in erradas.iterrows()))
    cand, abl = pos_rel[f'{ativa}-rel'], pos_rel[f'{ativa}-razao-abs']
    a = core_comodo.comparar(cand, pos[ativa], amostras)
    b = core_comodo.comparar(cand, pos[PISO], amostras)
    d = core_comodo.comparar(cand, abl, amostras)
    print('\nRegra de decisão (features relativas)')
    print(f'  1a. {ativa}-rel vs {ativa}: {a["diferenca"]:+.3f} ({_faixa(a["intervalo"])}) {a["resultado"]}')
    print(f'  1b. {ativa}-rel vs piso: {b["diferenca"]:+.3f} ({_faixa(b["intervalo"])}) {b["resultado"]}')
    aprovado = a['resultado'] == 'melhor' and b['resultado'] == 'melhor'
    print(f'  -> candidato {"APROVADO" if aprovado else "não aprovado"}')
    print(f'  descritivo: {ativa}-rel vs {ativa}-razao-abs: {d["diferenca"]:+.3f} ({_faixa(d["intervalo"])}) '
          f'{d["resultado"]}')
```

- [ ] **Step 4: MLflow**

No bloco `if os.environ.get('MLFLOW') == '1':`, depois do laço `for nome, tabela, ref_nome in pares:` (ainda dentro do `if`), acrescente:

```python
    for rotulo, p in pos_rel.items():
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      rel = rotulo.endswith('-rel')
      feats = [f'{f}_rel' if rel and f in core_comodo.RELATIVAS else f
               for f in registro['versoes'][ativa]['features']]
      params, metricas = metricas_mlflow(rotulo, feats, treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p),
                                         referencia='razao_prevista_rel' if rel else 'razao_prevista_abs')
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      with mlflow.start_run(run_name=f'{rotulo}-{treino}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {rotulo}-{treino}')
```

Run: `venv/bin/python -c "import ast;ast.parse(open('src/ml/comodo_benchmark.py').read())" && venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: sintaxe ok; 8 PASS.

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
feat(comodo): RELATIVAS=1 no benchmark, com a regra de decisão do modelo de razão
```

---

### Task 4: rodar e decidir

**Files:** nenhum (execução).

- [ ] **Step 1: rodar uma vez**

Run (em segundo plano):
`cd /home/venko/ml/TR069/ml-scripts && MLFLOW=1 MODELO=v5 RELATIVAS=1 venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/features_relativas.txt 2>&1; echo "exit $?" >> /tmp/claude-1000/features_relativas.txt`

Expected: `exit 0`; a seção "Nota" repete piso 0,452 e v5 0,722; aparecem "Modelo de razão", a tabela da referência das features, as linhas `v5-rel` e `v5-razao-abs`, e "Regra de decisão (features relativas)"; os runs `v5-rel-todas` e `v5-razao-abs-todas` no MLflow.

Rode **uma vez**. Não mude features, cortes, modelo ou a regra depois de ver o resultado.

- [ ] **Step 2: reportar**

Run: `sed -n '/^Modelo de razão/,$p' /tmp/claude-1000/features_relativas.txt | grep -v '^registrado'`

**Reporte ao Lucas**: as duas linhas (nota, intervalo, contra v5, contra piso, graves, acertos por prédio, erradas), as linhas da regra com o veredito, e o descritivo `v5-rel` contra `v5-razao-abs`. Compare `v5-razao-abs` com o teste de 2026-10-29 (v3 0,579): se ficar perto, reproduziu.

---

### Task 5: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (nova entrada no topo)

- [ ] **Step 1: escrever**

No topo, `# Changelog — Régua por cômodo: modelo de razão com features relativas (experimento)`, `**Data:** 2026-11-05`, e as seções:
- `## Por quê`: o "Por que" deste plano em 4 a 6 linhas, citando o teste de 2026-10-29 e a referência prevista.
- `## Mudanças`: as funções novas em `core/comodo.py`, o `razao=` de `classificar`, `RELATIVAS=1` no benchmark, os runs no MLflow; régua padrão, `VERSAO_COMODO`, Studio e `modelos.json` não mudaram.
- `## Efeito medido`: tabela com `piso`, `v5`, `v5-razao-abs`, `v5-rel` (nota, intervalo, contra v5, contra piso, graves), as linhas da regra e o veredito, o descritivo, e o que o resultado mostra e não mostra (27 posições, mais de 20 variantes já avaliadas nestes dados).
- `## Próximo passo`: se aprovado, "plano próprio para virar versão (Studio, `modelos.json`, `VERSAO_COMODO` só se a régua mudar)"; se não, "modelo de razão não aprovado; o erro de nível da casa segue em aberto e depende de mais prédios".

- [ ] **Step 2: sugerir commit (o Lucas commita)**

```
docs: changelog do experimento do modelo de razão com features relativas
```

---

## Fora deste plano

- Transformar `v5-rel` em versão do Studio (salvar no `modelos.json`, exibir no cartão): só se aprovado, em plano próprio.
- Relativizar outras features ou combinar com a referência prevista: seria uma variante nova, avaliada depois de olhar este resultado; só com dados de mais prédios.
