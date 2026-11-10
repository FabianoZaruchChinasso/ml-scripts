# Comando único: treina, avalia e grava uma versão no MLflow

**Data:** 2026-11-10
**Origem:** reunião de 2026-11-09 ("QoE Wi-Fi - Backlog para Avançarmos") e decisões de 2026-11-10: a pipeline
usa só o MLflow, o deploy é uma API e tudo roda local por enquanto. Segundo item do inventário
(`docs/pipeline/2026-11-10-inventario-studio-mlflow.md`).

## 1. Problema

Hoje uma versão do modelo está espalhada em três lugares que não medem nem guardam a mesma coisa:

- a avaliação do Studio (experimento "MLflow Wifi Studio") mede as features com o modelo da régua
  (`core/avaliacao.modelo_regua`) e não guarda modelo nenhum;
- `regression_mlflow.py` ("MLflow Wifi Regressions") treina 6 configurações por alvo e guarda os 6 modelos, sem
  escolher um: 14 runs por versão;
- `qoe_mlflow.py` ("MLflow Wifi QoE") guarda um classificador por aplicação.

Consequências: a nota de uma versão vem de um modelo e os binários guardados são outros; a receita de previsão
(contrato de colunas, denominador por banda, correção do p90) existe só como texto em arquivos JSON; nenhum run
aponta para a versão do dado; o Model Registry está vazio.

## 2. Objetivo

Um comando que, para uma versão de `core/modelos.json`, grava **um** run com a avaliação, o modelo que foi
avaliado e a versão do dado:

```bash
MODELO=v5 venv/bin/python src/ml/versao_mlflow.py
```

Decisões tomadas com o Lucas em 2026-11-10:

1. **O modelo do run é o modelo da régua**, um por alvo. O que é medido é o que é entregue. A varredura de 6
   configurações fica fora.
2. **A métrica principal é o erro das quatro previsões** (download, upload, latência, jitter). A régua por
   cômodo e os "atende" entram como métricas secundárias, com a versão de cada régua em tag. Motivo: a pesquisa
   de 2026-11-09 (`reports/Como prosseguir com rótulos de QoE.md`) concluiu que nem a régua relativa nem a fixa
   têm validação, e o erro das previsões não depende de régua.
3. **O run guarda um pacote único por versão**, que recebe linhas com os contadores e devolve as previsões. Os
   modelos pequenos ficam dentro dele e a receita vira código testado.

Critérios de sucesso:

1. Um comando produz um run com métricas, pacote, dado e arquivos (seção 4.4).
2. Os números da avaliação são os mesmos do Studio para a mesma versão e os mesmos datasets. Referência: a v5
   no conjunto canônico em 2026-11-10 deu nota por cômodo 0,7222 e R² de download 0,7455.
3. O pacote gravado carrega num processo novo, sem o repositório no caminho do Python, e prevê.
4. Treinado sem um prédio, o pacote prevê esse prédio com o mesmo número que a avaliação deu (seção 4.3).
5. Nenhum teste grava no `mlflow.db` da raiz do repositório.
6. Não mudam: `core/modelos.json`, o Studio, `regression_mlflow.py`, `qoe_mlflow.py` e os benchmarks congelados
   (`regression_benchmark.py`, `classification_benchmark.py`).

Fora do escopo: Model Registry e alias do modelo ativo; portão de promoção; classificadores por aplicação;
varredura de configurações; avaliar um rascunho que não está em `modelos.json` (versão nova entra no arquivo,
à mão ou pelo Studio, e o comando avalia pelo nome); servir o pacote como API; filtro de ambiente (o comando
avalia sempre todos os ambientes, como os outros scripts).

## 3. Abordagem

Dois módulos novos e um ajuste pequeno:

| Peça | Papel | Depende de |
|---|---|---|
| `src/ml/core/pacote.py` (novo) | Treina os modelos finais e implementa a receita de previsão. Não importa o MLflow | `core/avaliacao`, `core/quantis`, `core/producao`, `core/features` |
| `src/ml/core/pacote_mlflow.py` (novo) | Embrulha o pacote como modelo `pyfunc` do MLflow: grava e carrega | `core/pacote`, `mlflow`, `skops` |
| `src/ml/versao_mlflow.py` (novo) | O comando: lê a versão, avalia, treina, monta o pacote e grava o run | `core/completa`, `core/pacote`, `core/pacote_mlflow`, `core/registro_mlflow` |
| `src/ml/core/registro_mlflow.py` | Expõe `tags_git()` (hoje `_tags_git`; o nome antigo fica como alias) | |

Descartadas:

- Guardar os modelos soltos com arquivos de receita, como `regression_mlflow.py`: o Registry teria até 8
  entradas por versão e a receita seria reescrita no item da API, sem garantia de bater com a avaliação.
- Pôr o treino final dentro de `core/completa.py`: a avaliação completa é usada pelo Studio a cada salvar e
  reavaliar, e passaria a treinar e guardar modelos que o Studio não usa.
- Gravar no experimento "MLflow Wifi Studio": os runs de lá não têm modelo nem dado, e as tags `atual` e
  `ativo` são mantidas pelo Studio.

## 4. Desenho

### 4.1 `core/pacote.py`

Prefixos dos alvos, os mesmos de `registro_mlflow.ALVOS`: `down`, `up`, `lat`, `jit`.

`SAIDAS`, na ordem: `download_mbps`, `upload_mbps`, `latency_ms_p50`, `latency_ms_p90`, `latency_ms_p90_bruto`,
`jitter_ms_p50`, `jitter_ms_p90`, `jitter_ms_p90_bruto`. O `p90` leva a correção conformal; o `p90_bruto` é o
que a régua por cômodo usa.

`treinar(conjs, features, denominador=None) -> Pacote`

- `conjs`: `{alvo: Conjunto}` dos quatro alvos; `features`: já sem as colunas de vazamento; `denominador`:
  `{alvo: coluna | {'coluna', 'radio'}}` da versão, ou `None`.
- `Pacote` é um `dataclass` com `modelos` (`{nome: estimador}`) e `receita` (`dict` que vira JSON).
- Download e upload, com as linhas em que o alvo existe e `_limitado_wan` é falso (o mesmo treino de
  `prever_fora_do_fold`):
  - sem denominador: `<p>_absoluto = modelo_regua().fit(X, y)`;
  - denominador coluna: `<p>_eficiencia`, com `y ÷ den`; `den` vazio ou abaixo de `DEN_MINIMO` vira a mediana
    dos `den` válidos do treino, guardada na receita;
  - denominador `{'coluna', 'radio'}`: os dois modelos, com as mesmas linhas.
- Latência e jitter, com as linhas em que o alvo existe: `<p>_q50` e `<p>_q90` (`quantis.modelo_quantil`)
  em `log1p(y)`, e a correção `quantis.correcao_conformal(X, y_log, sites, 0.9)` (0 quando devolve `None`).
- `receita`:
  - `features`; `entradas` (features, mais as colunas de denominador, mais `radio` se houver denominador por
    banda): são as colunas que a entrada precisa ter;
  - por alvo: `contrato` (`producao.contrato` das linhas de treino daquele alvo); para download e upload,
    `denominador` (`coluna`, `radio`, `mediana_imputacao`, `den_minimo`) ou `null`; para latência e jitter,
    `correcao_log_q90` e `sem_correcao`;
  - `saidas`, `versao_regua` e `versao_pacote` (`'2026-11-10.1'`).

`prever(pacote, linhas) -> (DataFrame, avisos)`

- `linhas`: `DataFrame` com as colunas de `receita['entradas']`; falta de coluna levanta `ValueError` com a
  lista das que faltam.
- Por alvo, `X = producao.preparar_entrada(linhas, contrato)[0]`; os avisos de categoria desconhecida vão
  para `avisos`.
- Download e upload:
  - sem denominador: `absoluto.predict(X)`;
  - denominador coluna: `eficiencia.predict(X) * den`, com `den` vazio ou abaixo de `den_minimo` trocado
    pela mediana da receita (e um aviso com quantas linhas);
  - por banda: a eficiência nas linhas em que `radio` é igual ao da receita, comparando sem diferença de
    maiúsculas e espaços (`'5GHz'` do ACS casa com `'5ghz'`); o absoluto nas demais, inclusive `radio` vazio.
- Latência e jitter: `p50 = expm1(q50.predict(X))`, `p90 = expm1(q90.predict(X) + correcao)` e
  `p90_bruto = expm1(q90.predict(X))`, todos cortados em 0 e os dois p90 nunca abaixo do p50, como em
  `prever_quantis_fora_do_fold`.
- Devolve um `DataFrame` com as colunas de `SAIDAS`, indexado como `linhas`.

O pacote **não** corta a previsão no teto de WAN. A avaliação corta no teto do prédio de teste
(`sites.teto_wan`), e em produção o link da casa não é conhecido.

### 4.2 `core/pacote_mlflow.py`

- `PacoteQoE(mlflow.pyfunc.PythonModel)`: `load_context` lê `receita.json` e os modelos (um arquivo skops
  por modelo); `predict(context, model_input)` devolve só o `DataFrame` de `pacote.prever`.
- `gravar(pacote, exemplo) -> None`, dentro de um run ativo: grava os modelos em skops numa pasta temporária
  e chama `mlflow.pyfunc.log_model(name='pacote', ...)` com esses arquivos e `receita.json` como artefatos,
  `input_example=exemplo` (5 linhas de treino só com as colunas de `entradas`) e o código de `ml/core`
  embutido.
- `carregar(uri) -> Pacote`: o caminho inverso, para testes e para o item da API.
- Os modelos da régua têm cerca de 45 MB cada em skops sem compressão. Os arquivos são gravados com
  compressão (`zipfile.ZIP_DEFLATED`).

Como o código de `ml/core` entra no pacote é a única parte não verificada deste desenho. O candidato é
`code_paths` apontando para `src/ml`; a alternativa é o modo "models from code" do MLflow. A primeira tarefa
do plano prova uma das duas com um pacote de brinquedo carregado num processo novo, fora do repositório,
antes do resto.

### 4.3 O modelo entregue é o modelo medido

`pacote.treinar` e `prever_fora_do_fold` treinam com a mesma receita. O teste que garante isso: para cada
prédio, treinar o pacote com os conjuntos sem as linhas dele, prever as linhas dele e comparar com `yhat`
(download e upload) e com `q50`, `q90` e `q90_bruto` (latência e jitter) da avaliação.

Diferenças esperadas, e só estas:

- o teto de WAN, que a avaliação aplica e o pacote não: a comparação usa só as linhas que a avaliação não
  cortou (prédios sem teto, ou previsão abaixo do teto). Nos dados de teste nenhum prédio tem teto;
- quando o prédio de teste tem uma categoria que o treino não viu, a matriz da avaliação tem uma coluna a
  mais, toda zero no treino. As árvores não usam essa coluna, mas a ordem do sorteio interno do RandomForest
  pode mudar um desempate. Nos dados de teste, todas as categorias aparecem em todos os prédios e a igualdade
  é exigida com `numpy.allclose`. Na rodada real, o plano mede a diferença máxima por prédio e registra o
  valor no CHANGELOG.

### 4.4 `versao_mlflow.py`

Variáveis: `MODELO` (padrão: a versão ativa) e `DATASETS=a.zip,b.zip` (padrão: o conjunto canônico), como
nos outros scripts.

Passos:

1. Lê `core/modelos.json`. Versão inexistente: `SystemExit` com as versões disponíveis.
2. Carrega `{alvo: core_carga.carregar(alvo, ids=ids)}` para os quatro alvos e imprime os avisos.
3. `avaliacao = core_completa.avaliacao_completa(conjs.__getitem__, None, features, denominador,
   perfil_qoe=core_modelos.perfil_de(registro, nome))`.
4. `pacote = core_pacote.treinar(conjs, usadas, denominador)`, com `usadas` igual às features menos
   `avaliacao['removidas_por_vazamento']`.
5. Abre o run e grava (lista abaixo). Depois de gravar, carrega o pacote pelo URI do run e prevê as 5 linhas
   do exemplo; se falhar, o run termina `FAILED` e o comando sai com erro.
6. Imprime o resumo: métricas principais por alvo, nota por cômodo, "atende completo" e o id do run.

Destino: `registro_mlflow.uri_rastreamento()` (o `mlflow.db` da raiz, ou `MLFLOW_TRACKING_URI`). Experimento
`'MLflow Wifi Pipeline'`, criado com os artefatos em `<pasta do banco>/mlruns/pipeline`, pelo mesmo motivo de
`registro_mlflow._local_artefatos`. Nome do run: `<versão>-pipeline`.

O que o run guarda:

| Tipo | Conteúdo |
|---|---|
| Parâmetros | os de `registro_mlflow.parametros_e_metricas` (modelo, features, n_features, denominador, datasets, ambiente, perfil, cobertura_tr069, versao_comodo, versao_regua), mais `fingerprints`, `versao_tabela`, `versao_catalogo`, `versao_pacote` e `removidas_por_vazamento` |
| Métricas principais | por alvo `<p>`: `<p>_pooled`, `<p>_mae`, `<p>_mae_log` (já vêm de `parametros_e_metricas`), mais `<p>_pooled_lo90`/`_hi90`, `<p>_mae_lo90`/`_hi90`, `<p>_r2_<prédio>` e `<p>_mae_<prédio>`; para `lat` e `jit`, também `<p>_cobertura_q90` e `<p>_pinball_q90` |
| Métricas secundárias | as de `parametros_e_metricas`, com os mesmos nomes dos runs do Studio: `comodo_*`, `jogo_*`, `atende_completo`, `atende_throughput`, `atende_ajustado` |
| Tags | `modelo`, `metrica_principal=erro_das_previsoes`, `versao_comodo`, `versao_regua`, e as de `tags_git()` (commit e `git_arvore`) |
| Dado | `mlflow.log_input` de um dataset com as linhas do conjunto de download (features e os quatro alvos), nome `qoe-wifi`, `digest` igual aos 8 primeiros caracteres do SHA-256 dos fingerprints dos datasets na ordem, contexto `treino` |
| Arquivos | `avaliacao.json`, `posicoes.json` (como no Studio), `receita.json` e `cobertura_tr069.json` |
| Modelo | o pacote `pyfunc`, em `pacote` |

As métricas por prédio e os intervalos são montados por `metricas_do_pipeline(avaliacao) -> dict`, função
pura do próprio script, para poder ser testada sem MLflow.

O comando não escreve em `modelos.json`, não cria nem move tags `atual` e `ativo` e não toca no Model
Registry.

## 5. Erros

| Situação | Comportamento |
|---|---|
| `MODELO` inexistente | `SystemExit` com as versões disponíveis, antes de carregar dados |
| Dataset de `DATASETS` desconhecido ou da geração antiga | o `ValueError` de `core_carga.carregar` sobe |
| Feature marcada como vazamento | sai da conta, fica em `removidas_por_vazamento` e é impressa, como na avaliação |
| Falha na avaliação ou no treino | nenhum run é criado: os passos 3 e 4 acontecem antes de abrir o run |
| Falha ao gravar ou ao carregar o pacote | o run termina `FAILED` e o comando sai com código diferente de zero |
| Entrada do pacote sem uma coluna de `entradas` | `ValueError` com a lista das colunas que faltam |
| Categoria que o treino não viu | zero em todas as colunas dela e aviso, como em `producao.preparar_entrada` |

## 6. Testes

`tests/test_pacote.py`, com um conjunto sintético pequeno (três prédios, as mesmas categorias em todos):

- sem denominador, com denominador coluna e com denominador por banda: `prever` devolve as colunas de
  `SAIDAS`, com o índice de `linhas`;
- denominador vazio ou abaixo do mínimo usa a mediana da receita e gera aviso;
- `radio` com a grafia do ACS (`'5GHz'`) escolhe o modelo de eficiência; `radio` vazio escolhe o absoluto;
- `p90` nunca abaixo do `p50`; `p90_bruto` é o `p90` sem a correção;
- entrada sem coluna de `entradas` levanta `ValueError`;
- a igualdade da seção 4.3, para os quatro alvos;
- `treinar` deixa as linhas `_limitado_wan` fora do treino de download e upload.

`tests/test_pacote_mlflow.py`, com um `mlflow.db` temporário:

- `gravar` seguido de `carregar` devolve um pacote que prevê igual ao original;
- o modelo gravado carrega num processo novo, com a pasta de trabalho fora do repositório e sem `src` no
  caminho do Python, e prevê as linhas do exemplo.

`tests/test_versao_mlflow.py`, com `mlflow.db` temporário e a avaliação e o treino em mock (como
`tests/test_studio_salvar.py` faz com o peso da avaliação):

- `metricas_do_pipeline` monta os nomes da tabela da seção 4.4 a partir de uma avaliação de exemplo;
- o run tem os parâmetros, as tags, o dataset de entrada e os quatro arquivos;
- versão inexistente sai com erro antes de carregar dados;
- falha ao gravar o pacote deixa o run `FAILED`;
- o comando não cria nada no experimento "MLflow Wifi Studio".

A guarda de `tests/test_registro_mlflow.py` contra gravação no `mlflow.db` da raiz passa a cobrir os testes
novos.

Verificação com os dados reais, no fim do plano: rodar o comando para a v5 e conferir que as métricas do
run são iguais às da avaliação de referência de 2026-11-10; medir a diferença da seção 4.3 por prédio;
carregar o pacote num processo novo e prever.

## 7. Documentação

- `README.md`: o comando em "How to run" e o experimento novo em "MLflow".
- `CHANGELOG.md`: entrada com o porquê, as mudanças, o efeito medido na rodada da v5 e a diferença da
  seção 4.3.
- `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`: marcar o passo 3 da ordem proposta como feito.
