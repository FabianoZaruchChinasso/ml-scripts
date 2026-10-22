# Studio novo integrado ao MLflow (design)

**Data:** 2026-10-22
**Base:** `master` (commit `68b8d86`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

O QoE Studio atual (`src/ml/studio/`) ficou confuso, quebrado e, pior, mudou o benchmark do Fabiano: a régua única foi enfiada em `regression_benchmark.py` e `classification_benchmark.py`, e o upload do Studio grava em `data/` e em `core/predios.json`, que o benchmark lê.

Esta entrega constrói um Studio novo, do zero, em pacote separado:

- **Dados:** a área de Dados e o Conjunto (com upload) do Studio atual, migrados e limpos.
- **Modelo:** treino, avaliação, registro de versões e reavaliação sobre um MLflow **próprio do Studio**. Listar, comparar e inspecionar runs fica na UI nativa do MLflow, aberta pelo Studio.

O Studio novo é fino: faz só o que o MLflow não faz.

## 2. Fronteiras (o que não pode ser tocado)

O benchmark e o MLflow são do Fabiano. Decisões desta conversa:

- **Benchmark congelado como está.** `regression_benchmark.py`, `classification_benchmark.py` e os módulos de `src/ml/core/` que eles importam não são alterados por esta entrega. Voltar ou não para versões antigas é conversa com o Fabiano, fora deste escopo.
- **MLflow do Fabiano intocado.** O Studio nunca lê nem escreve `mlflow.db` e `mlruns/` da raiz, nunca usa o experimento "MLflow Wifi Regressions" e nunca importa nem altera `regression_mlflow.py`.
- **`data/` só leitura.** `core.carga.discover()` varre `data/` inteira: qualquer arquivo gravado lá entra no conjunto canônico do benchmark. O Studio lê `data/`, mas nunca escreve.
- **`src/ml/core/*.json` só leitura.** Inclui `predios.json` (muda o agrupamento por prédio do benchmark), `aplicacoes.json`, `modelos.json` e `column_provenance.json`.

Regras verificáveis (viram teste, seção 8):

1. Nenhum módulo do pacote `studio` importa `ml` ou `ml.*`.
2. Um ciclo completo de upload, treino, promoção e reavaliação não altera o conteúdo de nenhum arquivo em `data/`, `src/ml/`, `mlflow.db` e `mlruns/`.

## 3. Arquitetura

### 3.1 Código

Pacote novo `src/studio/` (importado como `studio`), fora de `src/ml/`. Stack igual à do Studio atual, sem dependência nova: FastAPI + uvicorn no servidor, JS puro sem build no front, MLflow 3.15.1 (já no `requirements.txt`).

```
src/studio/
  run.py               # sobe o Studio e o servidor MLflow
  api.py               # rotas FastAPI (Dados, Conjunto, Modelo)
  catalogo.py          # datasets de data/ (só leitura) + .studio/uploads/
  predios.py           # cadastro de prédios do Studio
  conjunto.py          # conjunto ativo
  dados.py             # agregações das telas de Dados
  plantas.py           # planta em escala
  upload.py            # prévia, revisão, confirmação
  mlflow_servidor.py   # processo filho do mlflow server
  avaliacao.py         # LOGO por prédio, métricas, "atende"
  treino.py            # fila de treino, run e versão registrada
  registro.py          # promover (@ativo), reavaliar, deep links
  arquivos.py          # gravação atômica
  config/
    predios.json       # semeado de src/ml/core/predios.json
    aplicacoes.json    # semeado de src/ml/core/aplicacoes.json
    colunas.json       # colunas com vazamento, semeado de column_provenance.json
  web/                 # index.html, styles.css, *.js
```

Os `config/*.json` são cópias feitas uma vez na implementação e depois independentes dos de `core/`. Ficam versionados.

### 3.2 Estado local

Pasta `.studio/` na raiz do repositório, adicionada ao `.gitignore`:

```
.studio/
  mlflow.db         # backend do MLflow do Studio
  artefatos/        # artefatos do MLflow do Studio
  uploads/          # CSVs enviados pelo upload
  conjunto.json     # conjunto ativo
```

### 3.3 Plantas

A planta continua lendo `docs/planta/` (imagens e `plantas.json`), que o benchmark não usa. Enquanto o Studio antigo existir, os dois compartilham essa pasta.

### 3.4 Inicialização

`python src/studio/run.py [--port 8100] [--mlflow-port 5100]`:

1. Verifica que as duas portas estão livres; se uma estiver ocupada, para com mensagem dizendo qual. Nunca se conecta a um MLflow que já esteja rodando (pode ser o do Fabiano).
2. Sobe `mlflow server --backend-store-uri sqlite:///.studio/mlflow.db --artifacts-destination .studio/artefatos --host 127.0.0.1 --port 5100` como processo filho.
3. Sobe o Studio em `127.0.0.1:8100`.
4. Ao sair (Ctrl+C ou erro), encerra o processo do MLflow.

### 3.5 Studio antigo

`src/ml/studio/` e `src/ml/studio.py` ficam como estão nesta entrega. A remoção é uma entrega separada, depois que o Studio novo cobrir Dados e Conjunto.

## 4. Dados e Conjunto

Migração do que funciona hoje. Cada módulo é porta (cópia simplificada) do código atual, sem importar dele.

| Módulo | Responsabilidade | Origem |
|---|---|---|
| `catalogo.py` | Lista os datasets de `data/` e `.studio/uploads/` num catálogo único, com a origem de cada um. Lê CSV e zip; ignora nomes com `-qoe` e `filllast`; exige `local` e os 4 alvos; calcula o fingerprint; marca duplicados e contidos (ex.: 0817 dentro de 0827). Arquivo ilegível vira entrada inutilizável com o motivo. Cache por processo, invalidado ao confirmar um upload. | `core.carga.discover`, `fingerprint`, `_superseded`, `duplicatas` |
| `predios.py` | Carrega `config/predios.json` e resolve `local` para prédio e posição. Grava só nesse arquivo, de forma atômica. | `core.sites` |
| `conjunto.py` | Lê e grava o conjunto ativo (lista de ids do catálogo) em `.studio/conjunto.json`. Ids que sumiram do catálogo são descartados com aviso. | novo |
| `dados.py` | Monta o payload da área Dados: linhas cruas dos quatro alvos (com prédio, posição, contenção e coordenadas), descritores dos datasets, prédios, limiares de `config/aplicacoes.json` e plantas. Mesmo formato do payload atual: a agregação (matriz, detalhe, queda com 1, 2 e 3 clientes, qual métrica reprova mais) continua no navegador, em `logica.js` e `dados.js`, migrados sem mudança. | `ml/studio/data.py` |
| `plantas.py` | Planta em escala com as posições reais. | `ml/studio/plans.py` |
| `upload.py` | Prévia → revisão → confirmação. Prévia: colunas obrigatórias, marcadores de geração, duplicado ou contido em outro dataset, prédios novos detectados. Revisão: você nomeia os prédios novos. Confirmação: grava o arquivo em `.studio/uploads/` e os prédios novos em `config/predios.json`. | `ml/studio/ingestao.py` |

Sai em relação ao Studio atual: contadores, derivadas, paralelos, assistente, receitas, Laboratório e qualquer avaliação de modelo dentro de Dados. A área de Dados mostra só dados medidos.

**Front:** duas abas (Dados, Modelo) e o painel lateral de Conjunto. O JS de matriz, planta e gráficos vem de `graficos.js`, `planta.js`, `dados.js` e `conjunto.js`, limpo das dependências de Laboratório e Modelo. Ícones em SVG inline, sem emojis.

## 5. Modelo com MLflow

### 5.1 Servidor e registro

- Todo acesso ao MLflow passa por `MlflowClient` apontado para `http://127.0.0.1:5100`.
- Antes de liberar a aba Modelo, o Studio faz health check no servidor.
- Experimento único: `QoE Studio`.
- Um modelo registrado por alvo: `studio-speedtest_down_mbps`, `studio-speedtest_up_mbps`, `studio-latency_ms`, `studio-jitter_ms`.
- A versão em produção de cada alvo é a que tem o alias `ativo`.
- O registro começa vazio; nada é importado de `modelos.json`.

### 5.2 Avaliação (`avaliacao.py`)

Avaliação própria do Studio, sem relação com a régua de `core.avaliacao`.

- **Validação:** LOGO por prédio. Cada prédio fica fora do treino uma vez; as previsões fora do fold de todos os prédios formam o conjunto avaliado.
- **Métricas de regressão:** MAE, RMSE e R², globais (sobre todas as previsões fora do fold) e por prédio.
- **"Atende" por aplicação:** para cada aplicação de `config/aplicacoes.json` com limiar para o alvo, aplica o limiar à previsão e ao valor real e mede a acurácia balanceada. Download e upload atendem com `>=`; latência e jitter com `<=`. Aplicação sem limiar para o alvo fica fora.
- **Regras**, parâmetros explícitos sempre logados no run:
  - `descartar_alvo_zero` (padrão: ligada): remove linhas com alvo exatamente 0 (teste que falhou).
  - `teto_wan` (padrão: desligada): remove linhas em que o speedtest provavelmente mediu a WAN e não o Wi-Fi: o prédio tem `tetos_wan` para o alvo em `config/predios.json`, alvo `>= 0,85 × teto` e `router_expected_throughput_mbps > teto`. É a mesma condição de `core.carga.marcar_limitado_wan`, reimplementada no Studio. Prédio sem teto, latência e jitter nunca perdem linhas.
- Linhas com alvo vazio são sempre removidas, e a contagem vai para o run.

### 5.3 Treino (`treino.py`)

**Formulário (um por vez, no Studio):**

| Campo | Conteúdo | Padrão |
|---|---|---|
| Alvo | download, upload, latência, jitter | download |
| Datasets | ids do catálogo | conjunto ativo |
| Features | checklist das colunas numéricas presentes em todos os datasets escolhidos | nenhuma marcada; botão "copiar features da versão @ativo" |
| Modelo | RandomForest, ExtraTrees, HistGradientBoosting, XGBoost | RandomForest |
| Hiperparâmetros | campos do modelo escolhido | os de `build_models` em `regression_benchmark.py` para aquele modelo, copiados para `treino.py` (sem importar) |
| Regras | `descartar_alvo_zero`, `teto_wan` | ligada, desligada |

Colunas listadas em `config/colunas.json` (os contadores `router_*` da janela do speedtest) aparecem com o rótulo "vazamento" e nunca vêm marcadas. Se forem marcadas mesmo assim, o run recebe a tag `contem_vazamento=true`.

**Execução:**

- Os treinos entram numa fila com um worker só, em background. A tela acompanha pelo status do job (`na fila`, `rodando`, `concluído`, `falhou`).
- Pipeline: `SimpleImputer(strategy='median')` + o regressor.
- Passos: carrega os datasets, aplica as regras, roda a avaliação LOGO, treina o modelo final com todas as linhas restantes, registra tudo no MLflow.

**O que cada run grava:**

- Params: `alvo`, `datasets`, `fingerprints`, `features`, `modelo`, os hiperparâmetros e as regras.
- Tags: `tipo=treino`, `contem_vazamento` (quando aplicável).
- Métricas: `mae`, `rmse`, `r2`, `mae__<prédio>`, `rmse__<prédio>`, `r2__<prédio>`, `atende_bacc__<aplicação>`, `linhas`, `predios`.
- Artefatos: `por_predio.csv`, `previsoes_fora_do_fold.csv`, `features.json`.
- Modelo: `mlflow.sklearn.log_model(..., name='modelo', signature=..., serialization_format='cloudpickle', registered_model_name='studio-<alvo>')`, que cria a versão nova. O padrão `skops` exige declarar tipos confiáveis ao carregar; `cloudpickle` foi verificado no MLflow 3.15.1 com Pipeline + XGBoost (grava, registra, aplica alias e recarrega por `models:/<nome>@ativo`).

### 5.4 Promover (`registro.py`)

1. Você escolhe uma versão de `studio-<alvo>`.
2. O Studio mostra as métricas dela ao lado das da `@ativo` atual.
3. O Studio avisa, sem bloquear, quando o run da versão tem `contem_vazamento=true` ou foi avaliado em menos prédios que o da `@ativo`.
4. Ao confirmar, move o alias `ativo` para essa versão.

### 5.5 Reavaliar (`registro.py`)

1. Você escolhe uma versão e um ou mais datasets (ex.: um upload novo).
2. O Studio carrega o modelo registrado e prevê, **sem retreinar**.
3. Se faltar alguma feature da versão em algum dataset, recusa listando as colunas e onde faltam.
4. Se algum dataset escolhido estiver entre os de treino da versão (mesmo fingerprint), avisa que a medida é otimista.
5. Cria um run com tags `tipo=reavaliacao` e `modelo_versao=<nome>/<versão>`, com as mesmas métricas de 5.3 (globais, por prédio e "atende"), aplicando as mesmas regras do treino daquela versão.

### 5.6 Tela Modelo

Para cada alvo:

- card da `@ativo`: versão, MAE, R², prédios avaliados;
- botões **Novo treino**, **Reavaliar**, **Promover** e **Abrir no MLflow**;
- jobs em andamento, com link para o run quando terminar.

Listagem de runs, comparação e gráficos ficam na UI do MLflow, por deep link:

- run: `http://127.0.0.1:5100/#/experiments/<id>/runs/<run_id>`
- versão: `http://127.0.0.1:5100/#/models/<nome>/versions/<versão>`

## 6. API

Todas as rotas sob `/api`. POST só aceito de localhost (mesma regra do Studio atual).

| Método | Rota | Faz |
|---|---|---|
| GET | `/api/catalogo` | catálogo de datasets |
| GET, POST | `/api/conjunto` | lê e grava o conjunto ativo |
| GET | `/api/payload` | payload da área Dados (linhas cruas, datasets com `enabled` do conjunto ativo, prédios, limiares, plantas) |
| GET, POST | `/api/plan/...` | arquivos, paredes, foto e calibração da planta (mesmas rotas do Studio atual) |
| POST | `/api/upload/previa` | prévia de um CSV (corpo cru) |
| POST | `/api/upload/revisar` | refaz a prévia com nome e prédios novos editados |
| POST | `/api/upload/confirmar` | grava o upload revisado |
| GET | `/api/mlflow/status` | health check e URL base da UI |
| GET | `/api/modelos/{alvo}` | `@ativo` e versões (para os seletores) |
| GET | `/api/colunas` | colunas disponíveis nos datasets escolhidos, com marca de vazamento |
| GET | `/api/modelos/padroes` | modelos, hiperparâmetros padrão e regras padrão (para o formulário) |
| POST | `/api/treinos` | valida o pedido (422 se recusado) e enfileira um treino |
| GET | `/api/modelos/{alvo}/promover?versao=N` | comparação candidata × `@ativo` e avisos |
| POST | `/api/modelos/{alvo}/promover` | move `@ativo` |
| POST | `/api/modelos/{alvo}/reavaliar` | valida e enfileira uma reavaliação |
| GET | `/api/jobs`, `/api/jobs/{job}` | jobs recentes (treinos e reavaliações) e status de um |
| POST | `/api/mlflow/reiniciar` | reinicia o processo do MLflow do Studio |

## 7. Erros

Mensagens sempre em português na tela; nada falha em silêncio.

| Situação | Comportamento |
|---|---|
| Porta 8100 ou 5100 ocupada | `run.py` para e diz qual porta |
| MLflow não responde ou cai | aba Modelo mostra "MLflow indisponível" e botão Reiniciar; aba Dados continua funcionando |
| Dataset ilegível em `data/` | entra no catálogo como inutilizável, com o motivo; os outros seguem |
| Upload inválido (sem `local`, sem alvos, duplicado) | prévia lista os problemas; Confirmar desabilitado |
| Treino com menos de 2 prédios | recusado antes de entrar na fila |
| Treino falha no meio | run com status `FAILED` e erro em artefato `erro.txt`; job mostra o erro; nenhuma versão registrada |
| Feature ausente | recusa listando colunas e datasets |
| Gravação de config ou estado | atômica (arquivo temporário + rename) |

## 8. Testes

Em arquivos `tests/test_studio_novo_*.py`, com `unittest`, como o resto do projeto (uma pasta `tests/studio/` sombrearia o pacote `studio` na descoberta de testes). Rotas da API são testadas chamando as funções direto, como os testes atuais do Studio (o venv não tem `httpx`).

- **Isolamento**
  - Varredura de imports: nenhum módulo de `src/studio/` importa `ml`.
  - Não escrita: ciclo completo (upload, treino, promoção, reavaliação) com MLflow num store temporário; hash de todos os arquivos em `data/`, `src/ml/`, `mlflow.db` e `mlruns/` igual antes e depois.
- **Unidade**
  - `catalogo`: fingerprint, contidos, filtros de nome, arquivo ilegível.
  - `predios`: resolução de `local` para prédio e posição.
  - `avaliacao`: LOGO, métricas por prédio e acurácia balanceada do "atende" contra números calculados à mão; regras `descartar_alvo_zero` e `teto_wan`.
- **Integração MLflow** (store sqlite temporário, `MlflowClient` direto, sem servidor)
  - treino gera run com os params, métricas e artefatos de 5.3 e uma versão registrada;
  - promover move o `@ativo`;
  - reavaliar cria run `tipo=reavaliacao` e avisa sobreposição de fingerprint.
- **API**: rotas de Dados devolvem o formato esperado para uma fixture pequena.
- **Manual (passo do plano)**: subir `run.py`, fazer um upload, treinar, promover, abrir o deep link no MLflow.

## 9. Fora de escopo

- Quantis e correção conformal para latência e jitter.
- Denominador e eficiência.
- Classificação direta de "atende".
- Laboratório (features, paralelos, derivadas, desenho automático, assistente, receitas).
- Importar versões de `modelos.json` para o registro.
- Modo guiado para técnicos de rede.
- Remover o Studio antigo (entrega separada).
- Qualquer mudança no benchmark, em `regression_mlflow.py` ou em `src/ml/core/`.
