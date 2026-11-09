# Modelo de razão com features relativas: rodada justa — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** corrigir o CHANGELOG do experimento das features relativas e rodar uma versão **justa** do modelo de razão (`v5-rel-justo`), que recebe a mesma informação sobre o teto de WAN que a v5 recebe, com a referência das features por banda, decidida por regra fixada antes.

**Architecture:** três mudanças contra a `v5-rel` de 2026-11-05, todas opcionais e com padrão igual ao comportamento atual: (1) `avaliacao.prever_fora_do_fold` ganha `excluir_limitados=` para tirar do treino as linhas `_limitado_wan` de qualquer alvo, como já faz para download e upload; (2) `referencia_features` e `relativizar` ganham `por_banda=` (referência por prédio **e** `radio`); (3) `classe_prevista_razao` ganha `saturar_wan=`: a linha cuja previsão absoluta da versão (já cortada no teto, a mesma da v5) chega a `LIMIAR_TETO × teto de WAN` do prédio fica com razão pelo menos 1, porque satura a WAN como o melhor cômodo. O benchmark acrescenta a linha `<ativa>-rel-justo` ao `RELATIVAS=1`.

**Tech Stack:** Python 3 (pandas, numpy, unittest com `unittest.mock`), MLflow 3.15.1.

## Por que (contexto para quem executa)

A revisão de 2026-11-05 do experimento das features relativas (CHANGELOG, entrada "modelo de razão com features relativas") achou uma **assimetria de desenho**:

- A v5 corta a previsão de download e upload no teto de WAN do prédio de teste (`teto_wan`, `core/sites.py`) e tira do treino as linhas `_limitado_wan`. O modelo de razão não fazia nenhuma das duas coisas.
- Das 159 linhas `_limitado_wan`, 139 são do `villa-escritorio` (teto 93,1 / 100,2 Mbps) e 20 da residência (154 / 99). Com o `villa-escritorio` de teste, a v5 corta todos os cômodos em ~93 Mbps: todos iguais ao melhor, todos "bom" (5 de 5). No modelo de razão, as 139 linhas entraram no treino com razão ~1 e PHY relativa baixa, e não havia teto: 2 de 5.
- A referência das features mistura bandas e celulares: 172 linhas (69 sozinhas no rádio) têm taxa PHY acima do dobro da referência da casa.

**Declaração obrigatória:** este experimento foi desenhado **depois** de ver o resultado da `v5-rel`. A justificativa é que a assimetria é um defeito de desenho achado na revisão, não um ajuste para melhorar a nota. Isso tem de constar no CHANGELOG. As três mudanças estão fixadas aqui e não mudam depois do resultado.

## Regra de decisão (fixada antes de rodar; não mude depois de ver os números)

Comparações pareadas nas mesmas 27 posições e na mesma verdade, intervalo de 90% (`core_comodo.comparar`):

1. **Candidato aprovado** (vira proposta de versão nova, em plano próprio) se `v5-rel-justo` contra `v5` tiver limite inferior > 0 **e** `v5-rel-justo` contra `piso` tiver limite inferior > 0.
2. Qualquer outro resultado: não aprovado; registrar e parar. **Não haverá outra rodada nestes dados** com outras correções.
3. Descritivo (não decide): `v5-rel-justo` contra `v5-rel`; acertos do `villa-escritorio`.

**Regras do projeto para quem executa:**
- **Nunca rode `git commit` nem `git push`.** Os passos de commit só sugerem a mensagem; o Lucas commita à mão. Sem linha `Co-Authored-By`.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`. `src/ml/core/avaliacao.py` pode ser editado só como descrito (argumento novo com padrão que não muda nada), porque esses scripts o importam; avise isso na mensagem de commit.
- Sem emojis.
- Branch `regua-hibrida` (tem mudanças de cinco planos de 2026-11-05 sem commit; não as reverta).
- Benchmark ~15 min: em segundo plano, esperar a notificação.

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `CHANGELOG.md` | Task 0: corrige a entrada das features relativas; Task 5: entrada nova |
| `src/ml/core/avaliacao.py` | `prever_fora_do_fold(..., excluir_limitados=False)` |
| `tests/test_avaliacao.py` | `TestExcluirLimitados` |
| `src/ml/core/comodo.py` | `por_banda=` em `referencia_features`/`relativizar`/`prever_razao`; `excluir_wan=` em `prever_razao`; `saturar_wan=` em `classe_prevista_razao` |
| `tests/test_comodo.py` | `TestRazaoJusta` |
| `src/ml/comodo_benchmark.py` | linha `<ativa>-rel-justo` e a regra dela |

---

### Task 0: corrigir o CHANGELOG da `v5-rel`

**Files:**
- Modify: `CHANGELOG.md` (entrada "Régua por cômodo: modelo de razão com features relativas (experimento, não aprovado)", linhas ~51 a 58)

- [ ] **Step 1: contagem da `casa-marcelo`**

Troque:
```
  posições. Os dois erros que a v5 tinha em `casa-marcelo` somem (9 de 9; antes 4 de 9) e os erros graves
  vão a zero, mas outros aparecem.
```
por:
```
  posições. Os cinco erros que a v5 tinha em `casa-marcelo` somem (9 de 9; antes 4 de 9), entre eles os dois
  graves, e os erros graves vão a zero, mas outros aparecem.
```

- [ ] **Step 2: trocar a hipótese pelo fato medido**

Troque o item que começa com `- A perda de v5-rel está concentrada em \`villa-escritorio\`` (4 linhas, até `prevê uma razão menor.`) por:
```
- A perda de v5-rel está concentrada em `villa-escritorio` (2 de 5, antes 5 de 5): três cômodos "bom"
  previstos "degradado". Revisão posterior: a comparação não era justa. A v5 corta a previsão no teto de WAN
  do prédio de teste (93,1 / 100,2 Mbps no `villa-escritorio`) e tira do treino as linhas limitadas pela WAN;
  o modelo de razão não fazia nenhuma das duas coisas. Das 159 linhas limitadas pela WAN, 139 são do
  `villa-escritorio`: entraram no treino da razão com razão ~1 e PHY relativa baixa. O descritivo v5-rel
  contra v5-razao-abs continua válido (as duas linhas têm a mesma assimetria); o veredito contra a v5 está
  contaminado. A referência das features também mistura bandas e celulares (172 linhas com PHY acima do dobro
  da referência da casa). Rodada justa: entrada "rodada justa" acima.
```

- [ ] **Step 3: sugerir commit (o Lucas commita)**
```
docs: corrige o changelog das features relativas (contagem e assimetria do teto de WAN)
```

---

### Task 1: `excluir_limitados` em `prever_fora_do_fold`

**Files:**
- Modify: `src/ml/core/avaliacao.py:56-90`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: teste que falha**

No fim de `tests/test_avaliacao.py` (antes do `if __name__`, se houver), acrescente:

```python
class TestExcluirLimitados(unittest.TestCase):
  def _df(self):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(1)
    partes = []
    for s in ('s1', 's2', 's3'):
      x = rng.uniform(0, 1, 30)
      partes.append(pd.DataFrame({'_site': s, '_pos': f'{s}-a', 'x': x, 'alvo_livre': x,
                                  '_limitado_wan': False}))
    df = pd.concat(partes, ignore_index=True)
    # Linhas limitadas no s1 com alvo absurdo: se entrarem no treino, puxam a previsão dos outros prédios.
    df.loc[df['_site'] == 's1', 'alvo_livre'] = 1000.0
    df.loc[df['_site'] == 's1', '_limitado_wan'] = True
    df['_linha'] = [f'd:{i}' for i in range(len(df))]
    return df

  def test_padrao_nao_exclui_para_alvo_sem_teto(self):
    from ml.core import avaliacao
    p = avaliacao.prever_fora_do_fold(self._df(), ['x'], 'alvo_livre', [])
    self.assertGreater(p[p['_site'] == 's2']['yhat'].max(), 100)

  def test_excluir_limitados_tira_do_treino_e_mantem_no_teste(self):
    from ml.core import avaliacao
    p = avaliacao.prever_fora_do_fold(self._df(), ['x'], 'alvo_livre', [], excluir_limitados=True)
    self.assertLess(p[p['_site'] == 's2']['yhat'].max(), 2)
    self.assertEqual(int((p['_site'] == 's1').sum()), 30)   # o prédio limitado continua sendo previsto
```

Confira o topo de `tests/test_avaliacao.py`: se ele não importa `unittest` nem acrescenta `src` ao `sys.path`, siga o padrão dos outros testes do arquivo.

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_avaliacao.TestExcluirLimitados -v`
Expected: `test_padrao...` PASS; `test_excluir...` ERROR com `TypeError: ... unexpected keyword argument 'excluir_limitados'`.

- [ ] **Step 2: implementar**

Em `prever_fora_do_fold`, acrescente o argumento `excluir_limitados: bool = False` depois de `denominador=None`, e na docstring, depois da frase do teto de WAN: `Com `excluir_limitados`, as linhas `_limitado_wan` saem do treino também para alvos sem teto (ex.: a razão de capacidade); o corte no teto continua só para download e upload.`

Troque:
```python
  if com_teto and '_limitado_wan' in sub.columns:
```
por:
```python
  if (com_teto or excluir_limitados) and '_limitado_wan' in sub.columns:
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_avaliacao.TestExcluirLimitados -v`
Expected: 2 PASS.

Run (em segundo plano): `PYTHONPATH=src venv/bin/python -m unittest tests/test_avaliacao.py`
Expected: `OK` (o padrão não mudou nada).

- [ ] **Step 3: sugerir commit (o Lucas commita)**
```
feat(avaliacao): excluir_limitados em prever_fora_do_fold (padrão inalterado; os benchmarks congelados importam este módulo)
```

---

### Task 2: referência por banda, exclusão e saturação no core

**Files:**
- Modify: `src/ml/core/comodo.py`
- Test: `tests/test_comodo.py`

- [ ] **Step 1: testes que falham**

Em `tests/test_comodo.py`, acrescente `from unittest import mock` aos imports do topo, e depois de `class TestRazaoPrevista` acrescente:

```python
def linhas_banda(pos, n, tx, radio, site='s1'):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, 'radio': [radio] * n,
                       'router_tx_rate_mbps': [float(tx)] * n, 'concorrentes_mesmo_radio': [1.0] * n})


class TestRazaoJusta(unittest.TestCase):
  def test_referencia_por_banda(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('sala', 10, 150, '2.4ghz'),
                linhas_banda('quarto', 10, 400, '5ghz'), linhas_banda('quarto', 10, 60, '2.4ghz'))
    ref = C.referencia_features(df, ['router_tx_rate_mbps'], por_banda=True)
    self.assertEqual(ref.loc[('s1', '5ghz'), 'router_tx_rate_mbps'], 800.0)
    self.assertEqual(ref.loc[('s1', '2.4ghz'), 'router_tx_rate_mbps'], 150.0)

  def test_relativizar_por_banda(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('sala', 10, 150, '2.4ghz'),
                linhas_banda('quarto', 10, 60, '2.4ghz'))
    ref = C.referencia_features(df, ['router_tx_rate_mbps'], por_banda=True)
    rel = C.relativizar(df, ref, por_banda=True)
    q = rel[(rel['_pos'] == 'quarto')].iloc[0]
    self.assertAlmostEqual(q['router_tx_rate_mbps_rel'], 0.4)   # 60 / 150, não 60 / 800

  def test_referencia_sem_banda_continua_igual(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('quarto', 10, 60, '2.4ghz'))
    self.assertEqual(C.referencia_features(df, ['router_tx_rate_mbps']).loc['s1', 'router_tx_rate_mbps'], 800.0)

  def _prev(self, dn):
    return pd.DataFrame({'_linha': ['l1', 'l2'], '_pos': ['a', 'a'], '_site': ['casa', 'casa'],
                         'dn': [dn, dn], 'up': [90.0, 90.0], 'lat': [10.0, 10.0], 'jit': [2.0, 2.0]})

  def test_saturar_wan_leva_a_razao_a_1(self):
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.5, 0.5], C.RAZAO_UP: [0.9, 0.9]})
    with mock.patch.object(C, 'teto_wan', lambda s, a: 100.0):
      t = C.classe_prevista_razao(self._prev(90.0), pr, LIM, saturar_wan=True)   # 90 >= 0,85 x 100
    self.assertEqual(t.loc['a', 'classe'], 'bom')
    self.assertAlmostEqual(t.loc['a', 'razao'], 1.0)

  def test_saturar_wan_nao_mexe_abaixo_do_limiar_nem_sem_teto(self):
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.5, 0.5], C.RAZAO_UP: [0.9, 0.9]})
    with mock.patch.object(C, 'teto_wan', lambda s, a: 100.0):
      abaixo = C.classe_prevista_razao(self._prev(80.0), pr, LIM, saturar_wan=True)
    with mock.patch.object(C, 'teto_wan', lambda s, a: None):
      sem_teto = C.classe_prevista_razao(self._prev(90.0), pr, LIM, saturar_wan=True)
    self.assertAlmostEqual(abaixo.loc['a', 'razao'], 0.5)
    self.assertAlmostEqual(sem_teto.loc['a', 'razao'], 0.5)

  def test_prever_razao_aceita_por_banda_e_excluir_wan(self):
    conjs, _ = conjs_sinteticos()
    for c in conjs.values():
      c.df['_limitado_wan'] = False
    ref = pd.DataFrame({'dn': [100.0] * 3, 'up': [55.0] * 3}, index=pd.Index(['s1', 's2', 's3'], name='_site'))
    ref_feat = pd.DataFrame(index=pd.MultiIndex.from_tuples([], names=['_site', 'radio']))
    pr = C.prever_razao(conjs, ['x'], {a: [] for a in conjs}, ref, ref_feat, por_banda=True, excluir_wan=True)
    self.assertEqual(len(pr), 90)
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestRazaoJusta -v`
Expected: falham com `TypeError` (`por_banda`, `saturar_wan`, `excluir_wan`) e `AttributeError: ... 'teto_wan'`.

- [ ] **Step 2: imports**

No topo de `src/ml/core/comodo.py`, acrescente:
```python
from ml.core.carga import LIMIAR_TETO
from ml.core.sites import teto_wan
```

- [ ] **Step 3: `referencia_features` e `relativizar` por banda**

Troque `referencia_features` inteira por:
```python
def referencia_features(df: pd.DataFrame, colunas, por_banda: bool = False) -> pd.DataFrame:
  """Por prédio (e por `radio`, com `por_banda`), o maior valor entre as medianas por posição de cada
  coluna, com as linhas sozinhas no rádio e grupos com MIN_LINHAS_REFERENCIA linhas (a regra de
  `referencia`). Só usa entradas (taxa PHY, sinal, SNR): numa casa nova ela existe."""
  so = sozinhas(df)
  colunas = [c for c in colunas if c in so.columns]
  chave = ['_pos', 'radio'] if por_banda else ['_pos']
  grupos = [so[k] for k in chave]
  med = so[colunas].apply(pd.to_numeric, errors='coerce').groupby(grupos).median()
  med['_site'] = so.groupby(grupos)['_site'].first()
  med['n'] = so.groupby(grupos).size()
  med = med[med['n'] >= MIN_LINHAS_REFERENCIA].reset_index()
  return med.groupby(['_site', 'radio'] if por_banda else '_site')[colunas].max()
```

Em `relativizar`, acrescente o argumento `por_banda: bool = False` (depois de `modos`), e troque a linha `ref = df['_site'].map(ref_feat[coluna])` por:
```python
    if por_banda:
      chave = pd.MultiIndex.from_arrays([df['_site'], df['radio']])
      ref = pd.Series(ref_feat[coluna].reindex(chave).to_numpy(), index=df.index)
    else:
      ref = df['_site'].map(ref_feat[coluna])
```
Na docstring de `relativizar`, acrescente: `Com `por_banda`, a referência é a do prédio na mesma `radio` da linha.`

- [ ] **Step 4: `prever_razao` com banda e exclusão**

Em `prever_razao`, acrescente os argumentos `por_banda: bool = False, excluir_wan: bool = False` depois de `relativas`. Troque `df = relativizar(df, ref_feat)` por `df = relativizar(df, ref_feat, por_banda=por_banda)`, e a chamada a `avaliacao.prever_fora_do_fold(df, colunas, coluna, vazadas[alvo])` por `avaliacao.prever_fora_do_fold(df, colunas, coluna, vazadas[alvo], excluir_limitados=excluir_wan)`. Na docstring: `Com `excluir_wan`, as linhas limitadas pela WAN saem do treino, como na v5.`

- [ ] **Step 5: `classe_prevista_razao` com saturação**

Troque `classe_prevista_razao` inteira por:
```python
def classe_prevista_razao(prev: pd.DataFrame, prev_razao: pd.DataFrame, limiares: dict,
                          saturar_wan: bool = False) -> pd.DataFrame:
  """Classe de cada posição pela razão prevista direto: o menor entre as medianas da razão de download
  e de upload. Latência, jitter e o piso absoluto vêm de `prev` (Mbps e p90 previstos, `prever`).

  Com `saturar_wan`, a linha cuja previsão absoluta de `prev` (já cortada no teto, como na v5) chega a
  LIMIAR_TETO x teto de WAN do prédio fica com razão pelo menos 1: ela satura a WAN, como o melhor cômodo.
  É a mesma informação do teto que a v5 recebe."""
  prev = prev[prev['_linha'].isin(set(prev_razao['_linha']))]
  r = prev_razao.set_index('_linha').reindex(prev['_linha'])
  razoes = {'dn': r[RAZAO_DN].to_numpy(dtype=float), 'up': r[RAZAO_UP].to_numpy(dtype=float)}
  if saturar_wan:
    for chave, alvo in (('dn', DN), ('up', UP)):
      teto = prev['_site'].map(lambda s, a=alvo: teto_wan(s, a)).astype(float).to_numpy()
      satura = prev[chave].to_numpy(dtype=float) >= LIMIAR_TETO * teto
      razoes[chave] = np.where(satura, np.maximum(razoes[chave], 1.0), razoes[chave])
  por_pos = pd.DataFrame({'_pos': prev['_pos'].to_numpy(), **razoes}).groupby('_pos').median()
  return classificar(estatisticas_previstas(prev), None, limiares,
                     razao=np.minimum(por_pos['dn'], por_pos['up']))
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestRazaoJusta tests.test_comodo.TestRazaoPrevista tests.test_comodo.TestFeaturesRelativas -v`
Expected: tudo PASS.

Run (em segundo plano): `PYTHONPATH=src venv/bin/python -m unittest tests/test_comodo.py tests/test_studio_comodo.py tests/test_comodo_benchmark.py`
Expected: `OK`.

- [ ] **Step 6: sugerir commit (o Lucas commita)**
```
feat(comodo): referência das features por banda, exclusão e saturação de WAN no modelo de razão
```

---

### Task 3: linha `<ativa>-rel-justo` no benchmark

**Files:**
- Modify: `src/ml/comodo_benchmark.py`

- [ ] **Step 1: calcular a linha**

No bloco `if relativas_on:`, troque o laço `for rotulo, rel in ((f'{ativa}-rel', True), (f'{ativa}-razao-abs', False)):` e o corpo dele por:
```python
    ref_feat_banda = core_comodo.referencia_features(df, list(core_comodo.RELATIVAS), por_banda=True)
    variantes = ((f'{ativa}-rel', dict(relativas=True), ref_feat, False),
                 (f'{ativa}-razao-abs', dict(relativas=False), ref_feat, False),
                 (f'{ativa}-rel-justo', dict(relativas=True, por_banda=True, excluir_wan=True), ref_feat_banda, True))
    for rotulo, opcoes, rf, saturar in variantes:
      pr = core_comodo.prever_razao(conjs_treino, feats_ativa, vazadas, ref, rf, **opcoes)
      pr = pr[pr['_linha'].isin(linhas)]
      pos_rel[rotulo] = core_comodo.juntar(real, core_comodo.classe_prevista_razao(prevs[ativa], pr, limiares,
                                                                                   saturar_wan=saturar))
      if tuple(pos_rel[rotulo].index) != tuple(pos[ativa].index):
        raise SystemExit(f'{rotulo} não cobre as mesmas posições de {ativa}')
```

Depois do `print(ref_feat.round(1).to_string())`, acrescente:
```python
    print('Referência das features por prédio e banda (rel-justo):')
    print(ref_feat_banda.round(1).to_string())
```

- [ ] **Step 2: regra da rodada justa**

Depois do `print(f'  descritivo: {ativa}-rel vs {ativa}-razao-abs: ...')` existente, acrescente:
```python
    justo = pos_rel[f'{ativa}-rel-justo']
    ja = core_comodo.comparar(justo, pos[ativa], amostras)
    jb = core_comodo.comparar(justo, pos[PISO], amostras)
    jd = core_comodo.comparar(justo, cand, amostras)
    print('\nRegra de decisão (rodada justa, desenhada depois da revisão; ver o plano 2026-11-05-features-relativas-justo)')
    print(f'  1a. {ativa}-rel-justo vs {ativa}: {ja["diferenca"]:+.3f} ({_faixa(ja["intervalo"])}) {ja["resultado"]}')
    print(f'  1b. {ativa}-rel-justo vs piso: {jb["diferenca"]:+.3f} ({_faixa(jb["intervalo"])}) {jb["resultado"]}')
    aprovado_justo = ja['resultado'] == 'melhor' and jb['resultado'] == 'melhor'
    print(f'  -> candidato {"APROVADO" if aprovado_justo else "não aprovado"}')
    print(f'  descritivo: {ativa}-rel-justo vs {ativa}-rel: {jd["diferenca"]:+.3f} ({_faixa(jd["intervalo"])}) '
          f'{jd["resultado"]}')
```

- [ ] **Step 3: rótulo no MLflow**

No laço `for rotulo, p in pos_rel.items():` do bloco do MLflow, troque `rel = rotulo.endswith('-rel')` por `rel = '-rel' in rotulo`, e o argumento `referencia=...` por:
```python
                                         referencia=('razao_prevista_rel_justo' if rotulo.endswith('-justo') else
                                                     'razao_prevista_rel' if rel else 'razao_prevista_abs'))
```

Run: `venv/bin/python -c "import ast;ast.parse(open('src/ml/comodo_benchmark.py').read())" && venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: sintaxe ok; 8 PASS.

- [ ] **Step 4: sugerir commit (o Lucas commita)**
```
feat(comodo): linha rel-justo no benchmark, com a regra da rodada justa
```

---

### Task 4: rodar uma vez e reportar

- [ ] **Step 1: rodar**

Run (em segundo plano):
`cd /home/venko/ml/TR069/ml-scripts && MLFLOW=1 MODELO=v5 RELATIVAS=1 venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/features_relativas_justo.txt 2>&1; echo "exit $?" >> /tmp/claude-1000/features_relativas_justo.txt`

Expected: `exit 0`; `v5-rel` e `v5-razao-abs` repetem 0,770 e 0,556 (se não repetirem, pare e reporte: algo mudou no comportamento padrão); aparece `v5-rel-justo` e a "Regra de decisão (rodada justa...)". Rode **uma vez**.

- [ ] **Step 2: reportar**

Run: `sed -n '/^Modelo de razão/,$p' /tmp/claude-1000/features_relativas_justo.txt | grep -v '^registrado'`

**Reporte ao Lucas** as três linhas (nota, intervalo, contra v5, contra piso, graves, acertos por prédio, erradas), as duas regras com veredito, e o descritivo `rel-justo` contra `rel`, com os acertos do `villa-escritorio` em destaque.

---

### Task 5: CHANGELOG

- [ ] **Step 1: escrever**

No topo do `CHANGELOG.md`, `# Changelog — Régua por cômodo: modelo de razão, rodada justa (experimento)`, `**Data:** 2026-11-05`, com:
- `## Por quê`: a assimetria do teto de WAN e a referência que mistura bandas, e a **declaração** de que o experimento foi desenhado depois de ver a `v5-rel`, por defeito de desenho achado na revisão.
- `## Mudanças`: `excluir_limitados` em `avaliacao.py` (padrão inalterado), `por_banda`, `excluir_wan`, `saturar_wan`, a linha `rel-justo` no benchmark; régua padrão, `VERSAO_COMODO`, Studio e `modelos.json` sem mudança.
- `## Efeito medido`: tabela com `piso`, `v5`, `v5-razao-abs`, `v5-rel`, `v5-rel-justo`; a regra e o veredito; o descritivo; o `villa-escritorio`.
- `## Próximo passo`: se aprovado, plano próprio para virar versão; se não, "modelo de razão encerrado nestes dados; volta com mais prédios".

- [ ] **Step 2: sugerir commit (o Lucas commita)**
```
docs: changelog da rodada justa do modelo de razão
```

---

## Fora deste plano

- Qualquer outra variante do modelo de razão nestes 27 cômodos (regra 2 acima).
- Virar versão do Studio: só se aprovado, em plano próprio.
