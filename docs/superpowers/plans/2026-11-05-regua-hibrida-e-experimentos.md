# Régua híbrida, experimentos "um dispositivo" e "só cliente", e MLflow — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fechar as tarefas da reunião de 2026-11-04: a Comparação por prédio abre na régua por cômodo, a régua ganha um piso absoluto de capacidade (resposta ao Otani), os experimentos "treino só com um dispositivo" e "só features do cliente" rodam contra a v5, e os resultados aparecem no MLflow.

**Architecture:** a régua continua relativa ao melhor cômodo da casa (`core/comodo.py`), mas download e upload passam também a ser checados contra os mínimos absolutos do perfil `norma` (`core/aplicacoes_norma.json`), do mesmo jeito que latência e jitter já são. Os experimentos entram no `comodo_benchmark.py` por variáveis de ambiente (sem salvar versão nova no registro) e, com `MLFLOW=1`, cada linha da tabela vira um run no experimento "MLflow Wifi Experimentos".

**Tech Stack:** Python 3 (pandas, numpy, unittest), MLflow 3.15.1, JS do Studio (sem build), `node --test`.

**Regras do projeto para quem executa:**
- **Nunca rode `git commit` nem `git push`.** Os passos de commit só sugerem a mensagem; o Lucas commita à mão. Sem linha `Co-Authored-By`.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py` (congelados por acordo com o Fabiano). `comodo_benchmark.py` pode ser editado.
- Mudança em `src/ml/core/modelos.json` chega ao benchmark do Fabiano: diga isso na mensagem de commit sugerida.
- Sem emojis em código, UI ou docs.
- Testes Python: `venv/bin/python -m unittest tests/test_<arquivo>.py -v` (a suíte inteira leva ~30 min; rode só os arquivos citados).

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/studio/static/modelo.js:31` | padrão `metrica: 'comodo'` |
| `src/ml/core/comodo.py` | `_abaixo_do_minimo`, `classificar` híbrida, `VERSAO_COMODO`, `conjuntos_sozinhos` |
| `tests/test_comodo.py` | testes do piso absoluto e de `conjuntos_sozinhos` |
| `src/ml/comodo_benchmark.py` | `TREINO=sozinhas`, `EXPERIMENTO=...`, `MLFLOW=1` |
| `tests/test_comodo_benchmark.py` (novo) | teste de `metricas_mlflow` |
| `src/ml/core/modelos.json` | reescrito pelo Studio ao reavaliar v1–v5 (Task 3) |
| `CHANGELOG.md` | uma entrada |

---

### Task 1: Comparação por prédio abre em "Cômodos certos"

**Files:**
- Modify: `src/ml/studio/static/modelo.js:31`

- [ ] **Step 1: trocar o padrão**

Em `src/ml/studio/static/modelo.js`, linha 31, troque `metrica: 'r2'` por `metrica: 'comodo'`:

```js
    cmp: null, cmpKey: null, cmpErro: null, comparando: false, cmpAberto: false, metrica: 'comodo', cmpHits: null,
```

- [ ] **Step 2: testes JS continuam passando**

Run: `node --test tests/js/logica.test.js`
Expected: todos `ok`, nenhum `not ok`.

- [ ] **Step 3: conferir no Studio**

Run: `venv/bin/python src/ml/studio.py --port 8100`, abra http://127.0.0.1:8100, área Modelo, clique "Comparar por prédio".
Expected: o botão "Cômodos certos (bom / degradado / ruim)" já vem marcado e o gráfico mostra bolinhas por prédio com a nota do cartão (0,72 na v5). Os botões R² e MAE continuam funcionando.

- [ ] **Step 4: sugerir commit (o Lucas commita)**

```
feat(studio): comparação por prédio abre na régua por cômodo
```

---

### Task 2: piso absoluto de capacidade na régua por cômodo

Contexto: hoje `classificar` (`src/ml/core/comodo.py:57-72`) marca ruim quando a razão de capacidade contra o melhor cômodo fica abaixo de 0,25 **ou** a latência/jitter falham em Navegação; degradado com razão < 0,75 **ou** falha em Chamada de vídeo. Download e upload nunca são comparados com um mínimo absoluto. Se o melhor cômodo da casa tem 4 Mbps, um cômodo com 3,5 Mbps sai "bom". O perfil `norma` já tem os mínimos: Navegação dn 2 / up 0,5; Chamada de vídeo dn 3,0 / up 3,8. "Apto para jogo" **não muda** (continua só latência e jitter).

**Files:**
- Modify: `src/ml/core/comodo.py:1-17` (docstring e `VERSAO_COMODO`), `:53-72`
- Test: `tests/test_comodo.py` (classe `TestClassificar`)

- [ ] **Step 0: guardar a linha de base**

Antes de mexer no código, rode e guarde a saída da régua atual:
`venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/regua_2026-11-03.txt 2>&1`
Expected: o arquivo começa com `Régua por cômodo 2026-11-03.1` e tem a tabela "Verdade por posição".

- [ ] **Step 1: escrever os testes que falham**

Em `tests/test_comodo.py`, dentro de `class TestClassificar`, acrescente:

```python
  def test_piso_absoluto_quando_o_melhor_comodo_e_fraco(self):
    # Casa cujo melhor cômodo tem 4 Mbps: pela razão tudo seria bom.
    ref_fraca = pd.DataFrame({'dn': [4.0], 'up': [4.0]}, index=pd.Index(['s1'], name='_site'))
    def c(dn, up):
      return C.classificar(est(dn, up), ref_fraca, LIM)['classe'].iloc[0]
    self.assertEqual(c(4.0, 4.0), 'bom')          # acima dos mínimos de Chamada (3,0 / 3,8)
    self.assertEqual(c(3.5, 3.5), 'degradado')    # razão 0,875 (seria bom), mas up < 3,8 (Chamada)
    self.assertEqual(c(1.9, 4.0), 'ruim')         # razão 0,475 (seria degradado), mas dn < 2 (Navegação)

  def test_piso_absoluto_inclui_o_limite(self):
    ref = pd.DataFrame({'dn': [3.8], 'up': [3.8]}, index=pd.Index(['s1'], name='_site'))
    self.assertEqual(C.classificar(est(3.0, 3.8), ref, LIM)['classe'].iloc[0], 'bom')

  def test_apto_jogo_nao_usa_capacidade(self):
    ref = pd.DataFrame({'dn': [4.0], 'up': [4.0]}, index=pd.Index(['s1'], name='_site'))
    t = C.classificar(est(4.0, 4.0, lat=10.0, jit=2.0), ref, LIM)
    self.assertTrue(bool(t['apto_jogo'].iloc[0]))  # dn 4 < 15 do Jogo, mas jogo é só lat/jit
```

- [ ] **Step 2: rodar e ver falhar**

Run: `venv/bin/python -m unittest tests.test_comodo.TestClassificar -v` (a partir da raiz, com `PYTHONPATH=src` se o import reclamar)
Expected: `test_piso_absoluto_quando_o_melhor_comodo_e_fraco` FAIL (`'bom' != 'degradado'`); os outros dois passam.

- [ ] **Step 3: implementar**

Em `src/ml/core/comodo.py`, logo depois de `_falha` (linha 54), acrescente:

```python
def _abaixo_do_minimo(est: pd.DataFrame, lim: dict) -> pd.Series:
  """Capacidade abaixo do mínimo absoluto da aplicação (o limite em si atende)."""
  return (est['dn'] < lim['dn']) | (est['up'] < lim['up'])
```

E troque as duas linhas de `ruim`/`degradado` em `classificar`:

```python
  ruim = (razao < CORTE_RUIM) | _falha(est, limiares[NAVEGACAO]) | _abaixo_do_minimo(est, limiares[NAVEGACAO])
  degradado = (razao < CORTE_BOM) | _falha(est, limiares[CHAMADA]) | _abaixo_do_minimo(est, limiares[CHAMADA])
```

Atualize a docstring de `classificar`:

```python
  """Razão de capacidade, classe e "apto para jogo" de cada posição de `est`, com a referência `ref`.

  `limiares`: {aplicação: {'dn', 'up', 'lat', 'jit'}}, como aplicacoes.carregar_perfil devolve. Ruim:
  razão abaixo de CORTE_RUIM, ou falha em Navegação (latência, jitter ou capacidade abaixo do mínimo).
  Degradado: razão abaixo de CORTE_BOM, ou falha em Chamada de vídeo pelos mesmos critérios (nunca ruim
  só por Chamada). O mínimo absoluto cobre a casa cujo melhor cômodo já é fraco. Jogo em nuvem não
  entra na classe; "apto para jogo" é só latência e jitter.
  """
```

Na docstring do módulo (linha 3-5), depois de "...como fração da melhor posição do prédio (V0 provisório)", acrescente "e contra os mínimos absolutos de download e upload do perfil". Suba a versão:

```python
VERSAO_COMODO = '2026-11-05.1'
```

- [ ] **Step 4: rodar o arquivo inteiro**

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: tudo PASS. Se um teste antigo quebrar, é porque usava capacidade abaixo dos mínimos esperando "bom": confira o valor e ajuste o **teste** só se a nova regra justificar (registre qual no relatório). Rode também `venv/bin/python -m unittest tests/test_studio_comodo.py -v` (Expected: PASS).

- [ ] **Step 5: ver o efeito na verdade antes de reavaliar**

Run:
```
venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/regua_2026-11-05.txt 2>&1
diff <(grep -A200 'Verdade por posição' /tmp/claude-1000/regua_2026-11-03.txt | grep -B200 -m1 '^Classes') \
     <(grep -A200 'Verdade por posição' /tmp/claude-1000/regua_2026-11-05.txt | grep -B200 -m1 '^Classes')
```
Expected: o arquivo novo começa com `Régua por cômodo 2026-11-05.1`; o diff lista só posições que pioraram de classe (nunca melhoraram: o piso só acrescenta condições de falha). **Reporte ao Lucas**: quantas posições mudaram, em quais prédios, e a nota da v5 com intervalo (antes 0,722).

- [ ] **Step 6: sugerir commit (o Lucas commita)**

```
feat(comodo): piso absoluto de download e upload na régua por cômodo

Casa cujo melhor cômodo já é fraco não vira "bom" só pela razão: dn/up abaixo
do mínimo de Navegação é ruim, abaixo do de Chamada de vídeo é degradado
(perfil norma). Apto para jogo não muda. VERSAO_COMODO 2026-11-05.1: as
avaliações salvas ficam desatualizadas até reavaliar.
```

---

### Task 3: reavaliar v1–v5 no Studio e atualizar o MLflow do Studio

**Files:**
- Modify (pelo Studio): `src/ml/core/modelos.json`

- [ ] **Step 1: reavaliar**

Run: `venv/bin/python src/ml/studio.py --port 8100`, área Modelo, use "Reavaliar" em cada versão (v1, v2-tr069, v3-tr069, v4, v5). Cada uma leva alguns minutos.
Expected: nenhum cartão fica com "desatualizada"; a Comparação por prédio (modo Cômodos certos) mostra as cinco versões e o piso.

- [ ] **Step 2: conferir o que mudou no registro**

Run: `git diff --stat src/ml/core/modelos.json && venv/bin/python -c "import json;r=json.load(open('src/ml/core/modelos.json'));[print(k,(v.get('avaliacao') or {}).get('comodo',{}).get('nota'),(v.get('avaliacao') or {}).get('comodo',{}).get('versao_comodo')) for k,v in r['versoes'].items()]"`
Expected: as cinco versões com `versao_comodo 2026-11-05.1`. Antes: v1 0.6429, v2 0.6429, v3/v4/v5 0.7222. Reporte as notas novas.

- [ ] **Step 3: registrar no MLflow**

Run: `venv/bin/python src/ml/studio_mlflow.py`
Expected: `registrado: v1-studio` ... `registrado: v5-studio`.

- [ ] **Step 4: sugerir commit (o Lucas commita)**

```
chore(modelos): reavalia v1 a v5 com a régua por cômodo 2026-11-05.1

Atenção: muda core/modelos.json, que o benchmark do Fabiano também lê.
```

---

### Task 4: experimentos "um dispositivo" e "só cliente" no comodo_benchmark

Contexto: a verdade já usa só as linhas com o cliente sozinho no rádio (`sozinhas`, `concorrentes_mesmo_radio == 1`; 982 de 1710 linhas), mas o treino em `prever` usa todas. O experimento "um dispositivo" treina só com as sozinhas. O experimento "só cliente" usa só colunas que um Android consegue ler, todas presentes nos seis prédios:

`RSSI, link_speed_mbps, channel_width, client_mode, radio, site_survey_same_channel_aps, site_survey_total_aps`

(`channel_width`, `client_mode` e `radio` estão classificadas como tr069 no catálogo, mas o Android expõe frequência, padrão Wi-Fi e largura; `site_survey_same_channel_aps` é o substituto possível de `concorrentes_mesmo_radio` que o Fabiano sugeriu. `signal_level` fica fora: falta em villa.)

**Files:**
- Modify: `src/ml/core/comodo.py` (nova função `conjuntos_sozinhos`)
- Modify: `src/ml/comodo_benchmark.py`
- Test: `tests/test_comodo.py`

- [ ] **Step 1: teste de `conjuntos_sozinhos`**

Em `tests/test_comodo.py`, acrescente uma classe:

```python
class TestConjuntosSozinhos(unittest.TestCase):
  def test_filtra_cada_alvo_e_preserva_o_resto(self):
    df = juntas(linhas('a', 3, 10, 10), linhas('a', 2, 10, 10, conc=2.0), linhas('b', 1, 10, 10, conc=np.nan))
    conj = types.SimpleNamespace(df=df, datasets=['d.zip'], classes={'x': None})
    out = C.conjuntos_sozinhos({C.DN: conj, C.UP: conj})
    self.assertEqual(len(out[C.DN].df), 3)
    self.assertTrue((out[C.UP].df['concorrentes_mesmo_radio'] == 1).all())
    self.assertEqual(out[C.DN].datasets, ['d.zip'])
    self.assertEqual(len(conj.df), 6)  # o original não muda
```

Run: `venv/bin/python -m unittest tests.test_comodo.TestConjuntosSozinhos -v`
Expected: FAIL com `AttributeError: module 'ml.core.comodo' has no attribute 'conjuntos_sozinhos'`.

- [ ] **Step 2: implementar**

Em `src/ml/core/comodo.py`, depois de `sozinhas`, acrescente (e `import copy` no topo):

```python
def conjuntos_sozinhos(conjs: dict) -> dict:
  """Cópia de cada Conjunto com o `.df` só nas linhas sozinhas no rádio (treino "um dispositivo")."""
  saida = {}
  for alvo, conj in conjs.items():
    novo = copy.copy(conj)
    novo.df = sozinhas(conj.df).reset_index(drop=True)
    saida[alvo] = novo
  return saida
```

Run: `venv/bin/python -m unittest tests/test_comodo.py -v`
Expected: tudo PASS.

- [ ] **Step 3: variáveis de ambiente no benchmark**

Em `src/ml/comodo_benchmark.py`:

1. Na docstring do módulo, acrescente:

```
Experimentos: TREINO=sozinhas treina todas as linhas da tabela só com as linhas sozinhas no rádio
(a verdade já é só delas). EXPERIMENTO=f1,f2,... acrescenta a linha 'experimento' com essas
features (sem denominador). MLFLOW=1 registra cada linha como um run em 'MLflow Wifi Experimentos'.
```

2. Logo depois de `conjs = {...}` e de `vazadas = {...}` (linhas 41-43), acrescente:

```python
  treino = os.environ.get('TREINO', 'todas')
  if treino not in ('todas', 'sozinhas'):
    raise SystemExit(f'TREINO={treino!r}: use todas ou sozinhas')
  conjs_treino = core_comodo.conjuntos_sozinhos(conjs) if treino == 'sozinhas' else conjs
  experimento = [x for x in os.environ.get('EXPERIMENTO', '').split(',') if x]
  if experimento:
    nomes.append(EXPERIMENTO)
```

com a constante `EXPERIMENTO = 'experimento'` ao lado de `PISO = 'piso'`.

3. Ajuste o print de cabeçalho para mostrar o treino:

```python
  print(f'Régua por cômodo {core_comodo.VERSAO_COMODO}; datasets {conjs[core_comodo.DN].datasets}; treino {treino}')
```

4. No laço que monta `pos`, troque o bloco por:

```python
  features_de = {}
  for nome in [PISO] + nomes:
    if nome == PISO:
      features, denominador = ['radio'], None
    elif nome == EXPERIMENTO:
      features, denominador = experimento, None
    else:
      features = registro['versoes'][nome]['features']
      denominador = {a: core_modelos.denominador_de(registro, nome, a) for a in (core_comodo.DN, core_comodo.UP)}
    features_de[nome] = features
    prev = core_comodo.prever(conjs_treino, features, vazadas, denominador)
    prev = prev[prev['_linha'].isin(linhas)]
    pos[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(prev, ref, limiares))
```

(`ref` e `real` continuam vindo de `df` inteiro: a verdade não muda com o treino.)

- [ ] **Step 4: rodar os dois experimentos**

Run (um dispositivo, só a v5 e o piso):
`MODELO=v5 TREINO=sozinhas venv/bin/python src/ml/comodo_benchmark.py 2>&1 | grep -A3 '^Nota'`
Expected: linhas `piso`, `v5` com nota e intervalo. Compare com a v5 da Task 3.

Run (só cliente, treino normal):
`MODELO=v5 EXPERIMENTO=RSSI,link_speed_mbps,channel_width,client_mode,radio,site_survey_same_channel_aps,site_survey_total_aps venv/bin/python src/ml/comodo_benchmark.py 2>&1 | grep -A4 '^Nota'`
Expected: linhas `piso`, `v5`, `experimento`; a coluna "vs v5" do experimento diz quanto se perde sem o roteador.

Run (só cliente e um dispositivo, o cenário do app):
`MODELO=v5 TREINO=sozinhas EXPERIMENTO=RSSI,link_speed_mbps,channel_width,client_mode,radio,site_survey_same_channel_aps,site_survey_total_aps venv/bin/python src/ml/comodo_benchmark.py 2>&1 | grep -A4 '^Nota'`

Guarde as três saídas completas em `/tmp/claude-1000/experimentos_2026-11-05.txt` e reporte ao Lucas a tabela: nota, intervalo, diferença contra v5 e contra o piso, e acertos por prédio de cada cenário.

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
feat(comodo): experimentos de treino só com um dispositivo e features livres no benchmark
```

---

### Task 5: experimentos no MLflow

**Files:**
- Modify: `src/ml/comodo_benchmark.py`
- Create: `tests/test_comodo_benchmark.py`

- [ ] **Step 1: teste da função pura**

Crie `tests/test_comodo_benchmark.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import comodo_benchmark as B


class TestMetricasMlflow(unittest.TestCase):
  def test_parametros_e_metricas(self):
    r = {'nota': 0.7, 'intervalo': [0.6, 0.8]}
    por_predio = {'hotmilk': (3, 5), 'residencia': (4, 4)}
    params, metricas = B.metricas_mlflow('experimento', ['RSSI', 'radio'], 'sozinhas', r, -0.05, 1, por_predio)
    self.assertEqual(params['linha'], 'experimento')
    self.assertEqual(params['features'], 'RSSI,radio')
    self.assertEqual(params['treino'], 'sozinhas')
    self.assertIn('versao_comodo', params)
    self.assertEqual(metricas['comodo_nota'], 0.7)
    self.assertEqual((metricas['comodo_lo90'], metricas['comodo_hi90']), (0.6, 0.8))
    self.assertEqual(metricas['vs_ativa'], -0.05)
    self.assertEqual(metricas['graves'], 1)
    self.assertAlmostEqual(metricas['acerto_hotmilk'], 0.6)
    self.assertEqual(metricas['acerto_residencia'], 1.0)

  def test_sem_intervalo(self):
    _, metricas = B.metricas_mlflow('piso', ['radio'], 'todas', {'nota': 0.4, 'intervalo': None}, 0.0, 0, {})
    self.assertNotIn('comodo_lo90', metricas)
```

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: FAIL com `AttributeError: ... has no attribute 'metricas_mlflow'`.

- [ ] **Step 2: implementar**

Em `src/ml/comodo_benchmark.py`, antes de `main`:

```python
def metricas_mlflow(nome: str, features, treino: str, r: dict, vs_ativa: float, graves: int, por_predio: dict) -> tuple:
  """(parâmetros, métricas) de uma linha da tabela para o run do MLflow."""
  params = {'linha': nome, 'features': ','.join(features), 'n_features': len(features), 'treino': treino,
            'versao_comodo': core_comodo.VERSAO_COMODO}
  metricas = {'comodo_nota': r['nota'], 'vs_ativa': vs_ativa, 'graves': graves}
  if r.get('intervalo'):
    metricas['comodo_lo90'], metricas['comodo_hi90'] = r['intervalo'][0], r['intervalo'][1]
  for site, (acertos, n) in por_predio.items():
    metricas[f'acerto_{site}'] = acertos / n
  return params, metricas
```

No fim de `main`, depois do último laço:

```python
  if os.environ.get('MLFLOW') == '1':
    import mlflow
    mlflow.set_experiment('MLflow Wifi Experimentos')
    for nome in [PISO] + nomes:
      p = pos[nome]
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      params, metricas = metricas_mlflow(nome, features_de[nome], treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p))
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      with mlflow.start_run(run_name=f'{nome}-{treino}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {nome}-{treino}')
```

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: PASS.

- [ ] **Step 3: registrar os três cenários**

Rode os três comandos do Task 4 Step 4 de novo, cada um com `MLFLOW=1` na frente.
Expected: `registrado no MLflow: ...` para cada linha. Abra `venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000` e confira o experimento "MLflow Wifi Experimentos" com os runs e a métrica `comodo_nota` comparável entre eles.

- [ ] **Step 4: CHANGELOG**

Em `CHANGELOG.md`, no topo, uma entrada de 2026-11-05 com: a Comparação por prédio abrindo em Cômodos certos; o piso absoluto na régua (VERSAO_COMODO 2026-11-05.1) e as notas novas de v1–v5; os três experimentos e as notas deles; o experimento "MLflow Wifi Experimentos". Use os números reportados nos Tasks 3 e 4.

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
feat(mlflow): registra os experimentos da régua por cômodo e changelog de 2026-11-05
```

---

## Fora deste plano

- Rótulo por buffering de vídeo (V2): discutir na próxima reunião.
- Backlog de ferramentas (LakeFS/DVC): tarefa do Fabiano.
- Data augmentation: pesquisa da Sofia.
