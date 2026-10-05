# Changelog — Contadores do roteador como vazamento e limpeza do registro

**Data:** 2026-10-02

## Por quê

Os contadores de volume do roteador são o delta da janela do próprio speedtest:
`router_tx_bytes·8 / speedtest_down_mbps` fica entre 11,2 e 12,5 s em todos os prédios, e os
contadores não são acumulados (só cerca de 45% sobem entre linhas seguidas do mesmo `mac`).
Razões por pacote não cancelam o volume: retry por pacote tem ρ −0,61 com o número de pacotes e
−0,64 com o download.

## Mudanças

- `router_tx_duration_us`, `router_rx_duration_us`, `router_tx_retries`, `router_tx_failed` e
  `router_rx_drop_misc` passam a ser **vazamento** (resposta "sim" em Limites e pendências).
- Fim da isenção `normaliza_volume`: uma derivada vaza se qualquer insumo vazar.
  `retry_por_pacote`, `falha_por_pacote`, `descarte_por_pacote_rx` e `fracao_airtime_tx`
  continuam no catálogo, mas saem de ajustes e versões. Catálogo `2026-10-02.1`.
- Registro de versões limpo: fica a `v1` (era `v1-legado`), ativa. `v1-sem-cliente`, a `v2-tr069`
  antiga e `v2-tr069-volume` foram removidas. Na avaliação, a `v1` perde os 5 contadores, listados
  em `removidas_por_vazamento`.
- Nova `v2-tr069`, montada no Studio sobre a base limpa e não ativa: só TR-069, sem contadores da
  janela (taxa PHY, SNR, sinal, largura de canal, eficiência espectral e perda de percurso).
  Download: R² pooled 0,59, MAE 45 Mbps em 4 prédios.
- `regression_mlflow.py` treina a versão ativa do registro, ou a indicada em `MODELO=`.
- Testes que falharam (alvo exatamente 0) são descartados em `load_datasets` e no Studio, com a
  contagem impressa ou nos avisos. Valores pequenos e positivos ficam: são enlaces ruins reais.

## Efeito medido (download, deixando um prédio de fora, RandomForest do Studio, 4 prédios)

| Conjunto | R² pooled | MAE (Mbps) |
|---|---|---|
| Base TR-069 sem contadores | 0,348 | 50,7 |
| + colunas e derivadas físicas que já existem | 0,404 | 47,4 |
| + físicas, sem testes que falharam | 0,439 | 44,7 |

A `v2-tr069` foi montada sobre essa base e chega a R² pooled 0,59 (MAE 45 Mbps).

## Fica para depois

- Deadzone temporal no coletor: contadores numa janela que termina antes do teste (`router_pre_*`).
- Teto de WAN da residência.
- Stats de estação ausentes no AX3000 da casa-marcelo e em todo o `20260925`.

# Changelog — Coletor sem zeros falsos e pendências dos dados no Studio

**Data:** 2026-09-25

## Coletor (`get-metrics.py`)

- `router_opportunity_medium_use` e `client_opportunity_medium_use` ficam **vazios** quando o scan
  de vizinhos falta ou não é legível, ou quando o canal do AP é ausente ou desconhecido. `0` passa a
  significar só "scan existe e não há vizinho no canal". Antes os dois casos viravam 0.
- A contagem foi para `src/medium_use.py`, testável sem o cliente do InfluxDB (`tests/test_medium_use.py`).
- Datasets já coletados continuam com o comportamento antigo. O Studio os lista como "coletor antigo".

## Limites e pendências dos dados (view Modelos; avisos também em Features)

- **Locais de coleta:** quantos há no conjunto ativo (e quantos domésticos/corporativos) contra o
  mínimo de 4. Abaixo disso, o Studio avisa que a leitura por local não é interpretável e que os
  números mudam com a coleta em andamento. Com 1 só local doméstico, avisa que nada vale para
  residências em geral.
- **Contadores do roteador medidos na janela do teste?** (`router_tx/rx_duration_us`,
  `router_tx_retries`, `router_tx_failed`, `router_rx_drop_misc`), com três respostas gravadas em
  `column_provenance.json`:
  - **Não sei** (estado atual): continuam nos ajustes, marcados como "não confirmado". Derivadas
    deles herdam a marca, e o desenho automático começa sem eles.
  - **Sim:** viram vazamento. Versões que os usam são avaliadas sem eles, e notas guardadas com eles
    aparecem como "refazer".
  - **Não:** liberados como qualquer coluna TR-069.
- **Datasets do coletor antigo:** onde um 0 em `router_opportunity_medium_use` pode ser "sem medição".

---

# Changelog — QoE Studio: view Modelos (etapa 3, paralelos e derivadas)

**Data:** 2026-09-25

## Paralelos: laboratório × TR-069

`studio/paralelos.py` + card na view Modelos. Para cada coluna fora do TR-069 (sniffer, cliente,
manual, ambiente; numérica, sem vazamento, cobertura ≥ 70%; as 40 de maior |ρ| com o alvo):

1. **Importa?** Ganho médio de R² ≥ 0,01 **e** melhora em todos os locais ao somá-la à versão base
   (se já está na base, mede o efeito de tirá-la).
2. **Reconstrói?** Todo o TR-069 prevê a coluna com R² ≥ 0,3 em **todos** os locais (folds por local).
3. **Assinatura.** Spearman **dentro** de cada prédio com cada TR-069 numérica. Só conta como
   consistente com |ρ| ≥ 0,3 e o mesmo sinal em todos os prédios onde a coluna varia.
4. **Leitura:** candidata a receita / só laboratório / o TR-069 já carrega / sem paralelo.

Campos constantes por posição (manuais) mostram o **n efetivo** (grupos independentes).

## Desenhista de derivadas

- `core/formulas.py`: fórmulas aritméticas sobre colunas brutas (`+ − * / **`, parênteses, `log10`,
  `log`, `sqrt`, `abs`), analisadas por AST e **sem eval**. Qualquer outra construção é recusada.
- `src/ml/core/derivadas.json`: derivadas desenhadas, com nome imutável, fórmula, inspiração e o
  resultado do teste. Derivada de derivada não é aceita.
- **Critério de aceite** (roda de novo no servidor ao salvar; o status nunca vem do navegador):
  insumos TR-069, sem vazamento, ganho ≥ 0,01 com melhora em todos os locais e, com inspiração,
  reconstrução com R² ≥ 0,3 em todos. Quem passa é **aprovada**; quem não passa é **hipótese**, fica
  visível no editor e fora do teto, do ganho e do desenho automático.

## Primeiro uso (download, base v2-tr069)

- **Nenhuma candidata a receita** entre as 40 colunas.
- `stats_80211_client_retry_overhead_pct` (sniffer): **o TR-069 já carrega**. Reconstrução com
  R² ≥ 0,42 nos 3 locais, com assinatura consistente em `retry_por_pacote`.
- `link_speed_mbps` (cliente) e `stats_80211_global_overhead_pct` (sniffer): **só laboratório**.
  Melhoram o alvo nos 3 locais, mas o TR-069 não os reconstrói em prédio novo.
- `taxa_phy_media = (router_tx_rate_mbps + router_rx_rate_mbps) / 2`, inspirada em
  `link_speed_mbps`: reconstrói (R² 0,51 / 0,49 / 0,31), mas não melhora o download sobre a
  v2-tr069. Salva como **hipótese**.

---

# Changelog — QoE Studio: view Modelos (etapa 2, desenho automático)

**Data:** 2026-09-25

## Desenhar melhor modelo TR-069

- `studio/selecao.py`: seleção gulosa só entre TR-069 e derivadas TR-069 (critério: R² pooled,
  folds por local de coleta; para quando o ganho < 0,005; até 12 features). Roda em thread
  (`POST /api/modelos/desenhar`, progresso em `GET /api/modelos/desenhar/{id}`).
- Duas notas: a **da seleção** (escolhe e avalia nos mesmos locais, otimista) e a **aninhada** (para
  cada local, a seleção roda sem ele e o modelo é testado nele: a estimativa honesta). A página
  mostra também quais features cada fold aninhado escolheu (estabilidade).
- Opção "sem contadores brutos de volume" (`router_tx/rx_duration_us`, `router_tx_retries`,
  `router_tx_failed`, `router_rx_drop_misc`); as versões por pacote continuam disponíveis.
- Uma versão salva a partir do desenho guarda passos, parâmetros e as duas notas (`selecao`). A API só
  aceita esse vínculo de um desenho que ela mesma rodou e com as mesmas features.
- Versões desenhadas aparecem com a nota **aninhada** no alvo otimizado e marcadas como
  **otimistas** nos demais e na comparação.

## Primeiro uso (download, 3 locais)

| versão | R² pooled | MAE (Mbps) |
|---|---|---|
| v1-legado (ativo) | −0,09 | 90,7 |
| v1-sem-cliente | +0,06 | 80,7 |
| v2-tr069 (aninhada, sem contadores de volume, 7 features) | −0,00 | 71,4 |
| v2-tr069-volume (aninhada, com contadores, 6 features) | +0,13 | 65,0 |

- A escolha é instável entre folds: nenhuma feature aparece nas 3 seleções aninhadas.
- Boa parte da vantagem da `v2-tr069-volume` vem de `router_tx_duration_us` (ρ 0,70 com
  `router_tx_bytes`, que já é vazamento). **Pendente:** confirmar com o coletor se os contadores de
  duração são medidos na janela do teste. Se forem, são vazamento e a `v2-tr069-volume` deve ser descartada.
- A versão ativa continua `v1-legado`: promover é decisão humana.

## Outros

- `main` com `min-width: 0`: a coluna principal encolhe e as tabelas largas rolam dentro do próprio card.

---

# Changelog — QoE Studio: view Modelos (etapa 1)

**Data:** 2026-09-25

## Versões de modelo

- `src/ml/core/modelos.json` + `core/modelos.py`: registro de versões. Cada versão é uma lista de
  features, imutável depois de salva, com descrição, origem e a avaliação dos 4 alvos da época
  (datasets, ambiente, versão da tabela e do catálogo). O modelo treinado não é salvo: refaz-se a
  partir da definição e, quando for para produção, vai para o MLflow.
- Semente: `v1-legado` (o `MODELO_ATUAL`, ativo) e `v1-sem-cliente` (sem
  `client_opportunity_medium_use`, a única feature fora do TR-069; ela conta vizinhos no scan do
  cliente, `site_survey_client`, e só o canal vem do TR-069). Sem ela, download vai de R² pooled
  −0,09 / MAE 90,7 para +0,06 / 80,7; latência e jitter pioram levemente.
- A versão ativa substitui o `MODELO_ATUAL` como base do "ganho" e do "no modelo" na view Features.
  O Teto de Features passa a mostrar todas as versões salvas.

## View Modelos

- Versões salvas (com "desatualizada" quando datasets, ambiente, tabela ou catálogo mudaram),
  **Comparar** no conjunto ativo (R² ou MAE por local de coleta, mais TR-069 completo e Tudo),
  **Montar modelo** a partir de uma versão (TR-069 bruta, TR-069 derivada e laboratório),
  **Avaliar rascunho** contra a base local a local, **Salvar como nova versão**, **Tornar ativa** e
  matriz de correlação Spearman das features do rascunho, com pares redundantes (|ρ| ≥ 0,9).
- API: `GET /api/modelos`, `/api/modelos/comparar`, `/api/modelos/avaliar`; `POST /api/modelos` e
  `/api/modelos/ativo` só a partir da própria máquina.

## Derivadas TR-069 novas (catálogo 2026-09-25.1)

`perda_percurso_db`, `eficiencia_espectral_tx`, `eficiencia_espectral_rx`, `vazao_esperada_por_mhz`,
`descarte_por_pacote_rx`. Primeira leitura: não sobem o TR-069 completo (pooled 0,073 → 0,069) e
`perda_percurso_db` é redundante com `router_signal_dbm` (ρ −0,92), porque `router_power_dbm` quase
não varia nestes dados.

## Outros

- Avaliações trazem MAE por local de coleta além do R².
- `mlruns/` no `.gitignore` (os scripts de MLflow gravam ali por padrão).

## Achado para o coletor (não corrigido aqui)

`get-metrics.py` grava `router_opportunity_medium_use = 0` quando o scan não existe, igual a "nenhum
vizinho". Na residência, 47% das linhas têm 0; entre elas, 22% também não têm dados de estação.

---

# Changelog — QoE Studio: folds por local de coleta e ambiente

**Data:** 2026-09-25

## Folds por local de coleta (prédio) em vez de cômodo

A view Features passou a deixar um **local de coleta inteiro** de fora por fold (`casa`,
`cowork-pedra-branca`, `hotmilk`), em vez de um cômodo. Com folds por cômodo, os outros cômodos do
mesmo prédio ficavam no treino — mesmo roteador, mesmo ambiente, mesmo dia de coleta — e o R² saía
inflado. Medido em `speedtest_down_mbps` sobre `0827` + `0917-fix` + `0921-distcalc` (1.071 linhas):

| esquema | atual | TR-069 | tudo |
|---|---|---|---|
| KFold aleatório | +0,84 | +0,88 | +0,92 |
| por cômodo (antigo) | −1,95 | +0,27 | +0,68 |
| mesmo cômodo de teste, sem o próprio prédio no treino | −6,69 | −4,34 | −2,53 |
| **por local de coleta (novo)** | −2,62 | −1,26 | −0,70 |
| por local de coleta, R² pooled | −0,09 | +0,07 | +0,25 |

A linha "sem o próprio prédio" usa o mesmo teste da linha por cômodo: a diferença entre as duas é
o vazamento. Com 3 locais a média por fold é instável (o fold `casa` tem pouca variância no alvo),
então o teto agora também traz **R² pooled** e **MAE** sobre todas as previsões fora do fold.

## Hotmilk e flag de ambiente

- `core/sites.py`: `hotmilk-*` vira o prédio `hotmilk`; `quarto-marcelo` resolve para
  `hotmilk-aquario`, como o `20260917-metrics-fix` já regravou. Antes essas linhas eram descartadas
  pelo Studio.
- `BUILDING_ENVIRONMENT` / `resolve_environment`: cada local é `domestico` (casa) ou `corporativo`
  (cowork, hotmilk). O Studio tem um seletor **Ambiente** que filtra todas as views e a análise de
  Features (`?ambiente=` na URL e na API).

## Dedupe tolerante a ruído de float

O fingerprint dos datasets arredonda os alvos em 6 casas. As versões `-fix`/`-distcalc` diferem da
original em ~1e-14 e passavam como datasets distintos, ligados juntos por padrão — duplicando o peso
das amostras e, via `quarto-marcelo`, colocando as mesmas medições em treino e teste.

## Pendências

- Os benchmarks de linha de comando (`regression_benchmark.py`, `classification_benchmark.py`,
  `compare_protocols.py`) continuam com `--group-level position` por padrão.
- O envelope do hotmilk (`house_x0`/`house_y0` = 410×1386) é idêntico ao da casa: conferir com a coleta.
- Só 1 local doméstico: com o filtro Doméstico a análise de Features é recusada (LOGO precisa de 2).

---

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
