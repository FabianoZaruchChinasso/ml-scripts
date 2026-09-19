# Changelog — Revisão Inicial dos Scripts de ML

**Branch:** `Revisão-Inicial`
**Data:** 2026-08-13

Esta revisão substitui a lógica de avaliação dos scripts em `src/ml/` por um pacote compartilhado
(`src/ml/core/`) que impõe validação **leave-one-site-out (LOGO)**. O objetivo é que as métricas
reportadas passem a medir generalização para uma **residência nunca vista no treino**, que é a
afirmação que o projeto precisa sustentar.

---

## 1. Por que esta mudança foi necessária

A auditoria do código anterior encontrou três classes de defeito, todas verificadas por execução
(não apenas por leitura):

### 1.1 Código que não executava

| Defeito | Onde estava |
|---|---|
| O caminho padrão (`--split random`) quebrava com `TypeError` — a dataclass `SplitData` exigia o campo `grp`, que `train_test_split_random` nunca preenchia | `regression_benchmark.py` |
| Arquivo não compilava: `IndentationError` na linha 21; `y`, `target` e `regression` nunca eram definidos | `regression_keras.py` |
| `NameError` em `display_labels` — depois de todo o treino terminar | `classifier_keras.py` |
| Caminhos de dataset fixos no código apontando para arquivos inexistentes | `classifier_mlflow.py`, `classifier_keras.py` |

### 1.2 Metodologia (as métricas estavam infladas)

- **Vazamento em todos os folds da validação cruzada.** O `classification_benchmark.py` fazia um
  holdout consciente de grupo, mas depois rodava `TimeSeriesSplit` na CV **e** no tuning — nenhum dos
  dois consciente de grupo. Verificado: **5 de 5 folds** tinham o mesmo local em treino e validação.
  Ou seja, tanto o ranqueamento dos modelos quanto a busca de hiperparâmetros otimizavam um score
  vazado.
- **Degradação silenciosa dos folds.** Ao pedir 5 folds com apenas 3 sites, o `GroupKFold` caía para
  2 folds **sem nenhum aviso na saída**. Um fold chegava a treinar em 1.030 linhas e validar em 5.987.
- **Fronteiras de classe calculadas no dataset inteiro** antes do split, fazendo valores do conjunto
  de teste influenciarem a própria definição dos rótulos `bad`/`mid`/`good`.
- **Splits aleatórios** nos scripts de MLflow, colocando medições repetidas do mesmo local nos dois
  lados do split.
- **O dataset do escritório codificava distância como local.** Os valores `cwpb-2m`, `cwpb-10m`,
  `cwpb-10m-2a`, `cwpb-13m` são **um único prédio medido a quatro distâncias** — agrupar por `local`
  ali fabricaria 4 pseudo-sites a partir de 1.

### 1.3 Relatórios enganosos

- `LabelEncoder` ordenava alfabeticamente (`bad=0, good=1, mid=2`), embaralhando o sentido ordinal.
- Linha imprimia `F1-score:` mas passava a variável `accuracy`.
- Log dizia `"Split strategy: time-aware"` enquanto o código fazia split por grupo.
- `safe_mape` retornava fração, reportada como "mape" sem multiplicar por 100.

---

## 2. Arquivos novos

### 2.1 `src/ml/core/` — pacote compartilhado

Toda a lógica de avaliação passou a viver aqui, e os scripts de linha de comando viraram invólucros
finos sobre este pacote.

#### `src/ml/core/__init__.py`
Arquivo vazio, apenas marca o diretório como pacote Python.

#### `src/ml/core/sites.py`
Resolução canônica de sites, em dois níveis. Expõe `resolve_site_id(local_values, level='position')`,
que mapeia a coluna bruta `local` — que registra a POSIÇÃO de medição dentro de um prédio, não o
prédio em si — para identificadores canônicos:

- `level='position'` (padrão, 7 grupos): residência → `res-sala`/`res-quarto`/`res-suite`;
  coworking → `cwpb-2m`/`cwpb-10m`/`cwpb-10m-2a`/`cwpb-13m`, cada um distinto.
- `level='building'` (2 grupos, viabilidade): todas as posições de cada prédio colapsam em
  `residencia` ou `coworking`.

A função **levanta `ValueError`** para valores vazios, não reconhecidos, não inteiros (ex.:
`1.5`) ou não finitos (`inf`) — nunca deixa um valor desconhecido formar um grupo próprio
silenciosamente.

#### `src/ml/core/splits.py`
Geração de folds LOGO e a garantia central contra vazamento.

- `assert_sites_disjoint(train_sites, test_sites)` — levanta `AssertionError` se qualquer site
  aparecer nos dois lados do split. **Esta é a decisão estrutural mais importante da revisão:** o
  vazamento anterior aconteceu porque "ser consciente de grupo" era uma convenção que um caminho de
  código não seguia. Com a asserção na camada de split, essa classe de defeito fica impossível de
  reintroduzir.
- `validate_site_count(site_ids)` — erro se houver menos de 2 sites; **aviso** se houver menos de 4,
  deixando explícito que a estimativa é instável.
- `outer_logo_folds(X, y, site_ids)` — retorna `List[Fold]` (lista, não gerador, para poder ser
  iterada mais de uma vez com segurança). Um fold por site: treina em todos os outros, testa neste.
- `inner_logo_splits(train_site_ids)` — LOGO aninhado, para que a busca de hiperparâmetros nunca
  enxergue o site separado no fold externo. Retorna lista de pares de índices, pronta para o
  parâmetro `cv=` do scikit-learn.
- Dataclass `Fold` com `X_train`, `X_test`, `y_train`, `y_test`, `train_sites`, `test_site`,
  `train_site_ids`.

#### `src/ml/core/metrics.py`
Métricas e limiares de classe locais ao fold.

- `safe_mape` — agora retorna **percentual** (multiplica por 100); antes devolvia fração rotulada
  como percentual.
- `regression_metrics` — `r2`, `rmse`, `mae`, `mape_pct`, `p90_ae`.
- `quartile_thresholds(y_train)` — calcula os limiares **somente com o fold de treino**.
- `apply_thresholds(y, t_low, t_high)` — aplica os limiares. Levanta erro claro quando
  `t_low == t_high` (fold de treino sem dispersão entre P25 e P75), em vez de deixar o `pd.cut`
  quebrar com mensagem interna do pandas.
- `assert_multiclass(y, context)` — erro legível quando um fold colapsa em uma única classe,
  nomeando qual site causou o problema.

#### `src/ml/core/data.py`
Carregamento e mesclagem de datasets.

- `load_datasets(paths, target=None)` — carrega e concatena vários CSVs, anexando a coluna canônica
  `site_id`. Valida as colunas de site **e de alvo por arquivo, antes do merge** (importante: validar
  só depois do `pd.concat` deixaria um arquivo sem a coluna-alvo virar linhas silenciosamente
  descartadas). Erros de leitura identificam qual arquivo falhou.
- `validate_columns(df, columns, role)` — validação reutilizável de colunas ausentes.
- Constantes `SITE_COLUMN = 'site_id'` e `RAW_SITE_COLUMN = 'local'`.

#### `src/ml/core/reporting.py`
Formatação da saída.

- `format_fold_plan(...)` — imprime exatamente quais sites treinam e testam cada fold. **Foi
  justamente esse tipo de saída que revelou o vazamento durante a auditoria**; torná-la permanente
  faz o próximo defeito do gênero aparecer imediatamente, sem precisar de auditoria de código.
- `format_per_site_table(results, metric)` — tabela por site com colunas `n`, `mean`, `min`, `max`.
  A coluna `n` mostra de quantos sites cada média foi realmente calculada, evitando que uma média
  calculada sobre menos sites que o cabeçalho `n_sites` sugere passe despercebida. Nunca reporta uma
  média isolada.

### 2.2 `tests/test_ml_core.py`
Suíte nova com **53 testes** cobrindo todo o `core/`, usando `unittest` (mesma convenção de
`tests/test_fn_metrics.py`) e DataFrames sintéticos — nenhum teste depende dos CSVs reais (que chegam
a 52 MB e impediriam rodar a suíte em CI ou em um clone novo).

Os testes de maior valor codificam os bugs encontrados, para que não voltem:

| Teste | Protege contra |
|---|---|
| Todos os `cwpb-*` colapsam em exatamente um site | A distância virar 4 pseudo-sites |
| Todo fold tem conjuntos de sites disjuntos | O vazamento de 5/5 folds |
| LOGO interno nunca contém o site de teste externo | Tuning "espiando" o site de teste |
| Cada site é o site de teste exatamente uma vez | Degradação silenciosa de folds |
| Perturbar valores do fold de teste não altera os limiares | Vazamento na definição das classes |
| Teste de integração: `load_datasets` → `outer_logo_folds` | Quebra na junção entre os módulos |

### 2.3 `src/ml/compare_protocols.py`
Script de auditoria de uso único. Roda o **mesmo** modelo sob os dois protocolos nos **mesmos** dados
— o antigo (split aleatório) e o novo (LOGO) — e imprime a diferença. Serve como registro permanente
de quanto os números antigos estavam inflados.

### 2.4 `src/ml/experimental/README.md`
Documenta por que os dois scripts Keras foram movidos para quarentena e quais defeitos conhecidos
foram **deliberadamente não corrigidos**.

---

## 3. Arquivos modificados

### `src/ml/regression_benchmark.py`
- **Removidos:** dataclass `SplitData`, `train_test_split_time_aware`, `group_split`,
  `train_test_split_random`, `safe_mape`, `compute_metrics` e a definição local de `validate_columns`
  (que sombreava a versão do `core`).
- **`evaluate_target`** reescrito para o laço LOGO: um fold por site, `clone(model)` a cada fold.
- **Imputação adicionada a todos os modelos** — cada estimador agora é um `Pipeline` iniciado por
  `SimpleImputer(strategy='median')`. Antes, RF/ExtraTrees/MLP quebrariam em qualquer dataset com NaN.
- **`random_state=seed`** no `XGBRegressor` (antes fixo em `42`, ignorando `--seed`).
- **Linhas com alvo vazio são descartadas** por alvo, com contagem reportada.
- **CLI:** `--csv` aceita múltiplos caminhos separados por vírgula. `--test-size` e `--cv-folds`
  continuam sendo aceitos, mas **avisam** que são ignorados (em vez de quebrar comandos antigos).
  `--time-column`, `--group-column` e `--split` foram removidos.

### `src/ml/classification_benchmark.py`
- **Removidos:** `group_split`, `time_holdout_split`, `assign_classes`, `run_cv`, `tune_model`,
  `print_class_distribution` (código morto), além das definições locais de `CLASS_NAMES` e
  `validate_columns` que sombreavam as do `core`.
- **`TimeSeriesSplit` eliminado** da CV e do tuning — ambos agora usam LOGO (externo e interno).
- **Limiares de classe passam a ser calculados por fold**, só com os sites de treino, e são
  **impressos** para cada fold (antes não havia visibilidade nenhuma sobre eles).
- **Log corrigido:** agora diz `leave-one-site-out (N folds)`, refletindo o que de fato roda.
- **CLI:** `--csv` aceita múltiplos caminhos. `--test-size`/`--cv-folds` avisam em vez de quebrar.
  `--class-mode`/`--fixed-thresholds` continuam existindo mas **ainda não são honrados** — passar
  `--class-mode fixed` imprime um aviso explícito e usa quartis mesmo assim (ver seção 6).

### `src/ml/regression_mlflow.py`
- Caminho fixo do dataset substituído por `os.environ.get('DS_CSV', ...)` e carregamento via
  `load_datasets`, com suporte a múltiplos CSVs.
- `train_test_split` aleatório substituído pelo **primeiro fold LOGO** — o run agora treina em 3
  sites e testa no 4º, em vez de misturar linhas do mesmo local nos dois lados.
- `test_site` e `train_sites` registrados como parâmetros no MLflow.
- Nome do dataset no MLflow passou a ser derivado do arquivo real (antes fixo como
  `metrics-20260630-out-filllast`, o que informava erradamente a procedência dos dados).
- Alvo com NaN agora é descartado no carregamento; import morto removido.

### `src/ml/classifier_mlflow.py`
- **Caminho padrão do dataset corrigido** — apontava para `metrics-20260630-qoe-speed.csv`, arquivo
  que **nunca existiu no repositório** (o script não rodava de forma alguma). Agora usa
  `os.environ.get('DS_CSV', 'data/metrics-20260630-qoe.csv')`.
- Bloco duplicado de `LabelEncoder` substituído por mapeamento ordenado explícito
  (`bad < mid < good`), corrigindo a ordenação alfabética que embaralhava o sentido ordinal.
- Corrigido `print(f"F1-score: {accuracy}")` → `{f1}`.
- **Removida a lista de features vazada** (continha `speedtest_down_mbps`, `latency_ms`,
  `download_*` — exatamente as grandezas de que `qoe_dw_score` é derivado). Ela era sobrescrita na
  linha seguinte e, portanto, inofensiva hoje; mas uma única edição a transformaria em vazamento
  total do alvo.
- **Nota:** a estratégia de split deste script **não** foi alterada (segue com `train_test_split`
  estratificado) — ficou fora do escopo desta revisão.

### `.gitignore`
Os padrões `src/__pycache__` e `src/opers/__pycache__` foram substituídos por `__pycache__/`, que
cobre qualquer diretório, incluindo os novos `src/ml/core/` e `tests/`.

---

## 4. Arquivos movidos (quarentena)

| De | Para |
|---|---|
| `src/ml/regression_keras.py` | `src/ml/experimental/regression_keras.py` |
| `src/ml/classifier_keras.py` | `src/ml/experimental/classifier_keras.py` |

Movidos **sem modificação**. Não são importados por nenhum script mantido e não têm cobertura de
testes. Seus defeitos (`IndentationError`, `NameError` em `display_labels`, `LabelEncoder` duplicado,
split aleatório) **permanecem sem correção de propósito**: o `regression_keras.py` não compila e a
intenção original não pôde ser recuperada do código quebrado, então reescrevê-lo seria adivinhação.

---

## 5. Limitação importante — leia antes de interpretar qualquer número

### 5.1 `local` é a posição de medição, não a residência

No dataset **bruto** de residência, `local` não é numérico — são nomes de cômodos, cada um medido a
uma distância:

| `local` (bruto) | distância | linhas | no CSV transformado | grupo resolvido hoje |
|---|---|---|---|---|
| `sala` | 1–2 m | 2618 | `1.0` | `res-sala` |
| `quarto` | 10 m | 5987 | `2.0` | `res-quarto` |
| `suite` | 13 m | 1030 | `3.0` | `res-suite` |

O pipeline de transformação converte os nomes em `1`/`2`/`3` (as contagens de linhas batem
exatamente), o que **escondeu a semântica**. O dataset do escritório segue o **mesmo** padrão
(`cwpb-2m`, `cwpb-10m`, `cwpb-13m` — as mesmas distâncias).

**Consequência:** `local` = posição dentro de **um** prédio, nos dois datasets. O número real de
prédios independentes é **2** (uma residência, um escritório), e são **7 posições** no total.

Portanto, as tabelas por site produzidas hoje respondem *"generaliza para outro cômodo/distância do
mesmo prédio?"* — uma pergunta legítima e útil, mas **mais fraca** do que "generaliza para uma
residência nova". A afirmação de generalização precisa ser reescolhida (ver seção 6).

### 5.2 Escalas divergentes — causa raiz identificada, e é corrigível

A causa **não** é a coleta de dados: os dois CSVs brutos são perfeitamente comparáveis
(residência `[0, 667]` Mbps, escritório `[0, 568]` Mbps). A divergência é introduzida **pelo
transform**, que aplicou a diretiva `normalize` (dividir pelo máximo da coluna) a 3 dos 4 alvos do
dataset de residência, e a nenhum do escritório:

| alvo | residência `-out` | escritório `-out` | normalizado? |
|---|---|---|---|
| `speedtest_down_mbps` | `[0, 1]` | `[0, 567.67]` | só residência |
| `latency_ms` | `[0, 1]` | `[0, 1947.10]` | só residência |
| `jitter_ms` | `[0, 1]` | `[0, 564.25]` | só residência |
| `speedtest_up_mbps` | `[0, 292.65]` | `[0, 420.76]` | **nenhum — consistente** |

Das 36 colunas numéricas compartilhadas, **apenas essas 3 divergiam** — todas as features já estavam
consistentes.

**Corrigido** pelo `src/ml/fix_target_scale.py`: os três alvos da residência foram multiplicados de
volta pelos máximos do CSV bruto, deixando os dois prédios em Mbps/ms. A inversão é exata — verificada
contra `metrics-20260630-out-filllast.csv` (o gêmeo não-normalizado do mesmo transform), com diferença
máxima de 1e-13 nas 9.635 linhas. O script é idempotente: colunas já em unidade física são preservadas.

### 5.3 Com escalas consistentes, a generalização entre prédios **funciona**

`speedtest_up_mbps` escapou da normalização nos dois arquivos, então já é comparável hoje. Rodando o
`compare_protocols.py` sobre ele:

```
Sites: ['cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m', 'cwpb-2m', 'res-quarto', 'res-sala', 'res-suite']
Group level: position

Legacy protocol (random split):
  r2=0.92994  rmse=15.05753

Leave-one-position-out, per site:
  test_site      r2     rmse
   cwpb-10m 0.71429 18.88496
cwpb-10m-2a 0.41130 31.12122
   cwpb-13m 0.74614 15.28129
    cwpb-2m 0.67156 47.01169
 res-quarto 0.48522 18.86573
   res-sala 0.56893 47.51370
  res-suite 0.69572  9.08510

LOGO mean r2=0.61331 (min=0.41130, max=0.74614)

Optimism of the legacy number: 0.31663 r2
```

**Leitura:** o protocolo antigo reportava R² = 0,93; o protocolo honesto entrega R² ≈ 0,61. **O número
antigo estava inflado em ~0,32 de R².** Esse é o resultado que toda esta revisão existia para produzir.

Note que as quatro posições do coworking pontuam entre 0,41 e 0,75 — na mesma faixa das posições da
residência. Ou seja, os R² fortemente negativos vistos nos outros alvos eram **100% artefato de
escala**, não falha de generalização. Os dados são aproveitáveis.

---

## 6. Pendências conhecidas (decisões em aberto)

- **Coletar mais prédios.** Com 2 prédios, "generaliza para um prédio novo" é demonstrável (n=2), não
  estimável. Esse é o desbloqueio real para a afirmação original do projeto.
- **`--class-mode fixed` / `--fixed-thresholds`** existem na CLI mas ainda não são honrados. Definir
  se limiares fixos devem valer globalmente ou por fold é uma decisão de projeto real, pois muda as
  propriedades de vazamento — ficou em aberto, não implementada.
- **`classifier_mlflow.py`** segue com split aleatório; migrá-lo para LOGO ficou fora do escopo.
- **A suíte de testes antiga (`tests/test_fn_metrics.py`) está quebrada desde que foi adicionada** —
  o fixture `tests/res/test_data.csv` nunca foi commitado (`git log --all -- tests/res` não retorna
  nada), então os 18 testes falham com `FileNotFoundError`. Não faz parte desta revisão, mas vale
  restaurar o arquivo.

---

## 7. Como rodar

```bash
# Benchmark de regressão sobre o pool combinado (2 prédios, 7 posições por padrão)
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps

# Benchmark de classificação (apenas a residência: o pool combinado é bloqueado
# pelo guard, por causa da incompatibilidade de escala do qoe_dw_score)
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv --no-tune

# Comparação entre o protocolo antigo e o novo
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps

# Regressão com beeswarms SHAP (um por modelo/alvo, em res/shap/)
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps --shap

# Só os modelos de árvore (rápido), com um beeswarm por fold também
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps --shap --shap-models rf,XGB --shap-per-fold

# Suíte de testes do core
python3 -m unittest tests.test_ml_core -v
```

---

## 8. SHAP no benchmark de regressão (adicionado em 2026-09-17)

O benchmark respondia **quão bem** cada regressor generaliza para um site novo, mas nunca **quais
features** movem a predição — não dava para ver se `rf` e `XGB` concordam sobre a física ou se um
modelo está apoiado numa feature que só funciona em um site.

### 8.1 `src/ml/core/explain.py` (novo)

`shap` e `matplotlib` são importados **dentro** das funções: uma execução sem `--shap` não exige
nenhum dos dois. Com `--shap` e sem o pacote, `require_shap()` falha antes do treino, com uma
mensagem só, em vez de um WARNING por fold.

- `explain_fold` — Explanation das linhas de **teste** (fora do site) de um fold já treinado.
  `TreeExplainer` (exato, `tree_path_dependent`) para `rf`/`extra_trees`/`hist_gb`/`XGB`;
  `PermutationExplainer` com background amostrado do treino para o `mlp`. O caminho do `hist_gb` tem
  fallback para o permutation, porque o suporte a `HistGradientBoosting` é a parte mais frágil entre
  versões do shap — uma atualização não pode derrubar o benchmark.
- Como todo modelo é um `Pipeline`, o explainer recebe `fitted[:-1].transform(X)` (o que o estimador
  vê) enquanto a **cor** do beeswarm usa `fitted[:1].transform(X)` — pós-imputação, pré-escala — para
  ficar em unidades físicas (dBm, us, Mbps) também no `mlp`. `RobustScaler` é monótono por feature,
  então a ordem baixo->alto da cor se mantém. Onde o valor era NaN, a cor mostra a mediana imputada.
- `sample_rows` usa a mesma semente para todos os modelos: todos são explicados sobre EXATAMENTE as
  mesmas linhas, então beeswarms de modelos diferentes são comparáveis ponto a ponto.

### 8.2 Agrupado por padrão, por fold sob demanda

Cada fold treina seu próprio modelo, então cada um gera sua própria Explanation. O padrão empilha as
Explanations dos folds num beeswarm por modelo/alvo: todo ponto é fora do site, e todos os folds
predizem o mesmo alvo na mesma unidade (Mbps / ms), então os valores são comensuráveis.

**O gráfico agrupado é o efeito TÍPICO ENTRE SITES, não o de um modelo.** Cada bloco de linhas vem de
um fold diferente, com seu próprio base value (o beeswarm plota só os valores, então isso não
distorce a figura). Uma feature no topo do ranking mas sem separação de cor indica que o agrupamento
está achatando discordância entre folds — reveja com `--shap-per-fold`, que grava os 7 beeswarms
individuais (`n_modelos x n_sites` PNGs, por isso não é o padrão).

### 8.3 CLI e saída

`--shap`, `--shap-dir` (default `res/shap`), `--shap-per-fold`, `--shap-models`, `--shap-max-samples`
(300 linhas por fold; `0` = todas), `--shap-background` (100), `--shap-max-display` (20).

```
res/shap/<alvo>/<modelo>_beeswarm.png                    # folds agrupados
res/shap/<alvo>/folds/<modelo>_<site>_beeswarm.png       # só com --shap-per-fold
res/shap/<alvo>/mean_abs_shap.csv                        # model, rank, feature, mean_abs_shap
```

Toda chamada de shap fica dentro de `try/except`: uma falha de explicação vira um WARNING e nunca
custa as tabelas de r2/rmse do run. `evaluate_target` passou a retornar `(results, shap_ranking)`.
