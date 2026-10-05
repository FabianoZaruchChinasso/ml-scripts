# Régua única, carga canônica e concorrência no modelo (design)

**Data:** 2026-10-05
**Base:** `master` (commit `b2c864b`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

Hoje o Studio e os scripts de treino medem o modelo com réguas diferentes, e o fator que mais move o download (quantos clientes testam ao mesmo tempo) não entra em nenhuma versão. Esta entrega faz duas coisas:

- **A. Avaliação honesta:** uma carga e uma régua só, no `core`, usadas pelo Studio, por `regression_mlflow.py` e por `regression_benchmark.py`, com intervalo de confiança e uma métrica de decisão por aplicação.
- **B. Dados e features:** concorrência como feature, teto de WAN tratado, linhas sem stats de estação fora, e a `v3-tr069` comparada à `v2-tr069` nessa régua.

Os datasets em `data/` não são alterados. Toda correção é regra aplicada na carga, em código versionado. O coletor (agente que grava no InfluxDB) e o extrator (`src/get-metrics.py`, `src/get-all.py`) também ficam intocados; o que precisa mudar neles vai para a seção 9, para ser repassado ao responsável.

As frentes C (dados externos e fine-tuning) e D (latência e jitter) ficam para depois (seção 10).

## 2. Evidência

Medido em 2026-10-05 sobre os 5 datasets ativos (`20260827`, `20260917-fix`, `20260921-distcalc`, `20260925`, `20260928`): 1.642 linhas, 4 prédios, 18 posições.

**Duas réguas.** O Studio lê os zip, remove duplicatas por fingerprint e faz LOGO por prédio. `regression_mlflow.py` usa `load_datasets` com o padrão `group_level='position'` (o mesmo prédio aparece no treino e no teste), avalia só `folds[0]` e tem `DS_CSV` padrão apontando para `metrics-20260630-out.csv`.

**Concorrência.** Download mediano (Mbps) por número de clientes testando ao mesmo tempo:

| Prédio | 1 cliente | 2 clientes | 3 clientes |
|---|---|---|---|
| hotmilk | 120,7 | 35,7 | – |
| coworking | 102,3 | 54,5 | 25,2 |
| casa-marcelo | 59,9 | 28,7 | – |
| residencia | 13,4 | 10,9 | 8,4 |

A tabela foi medida sobre as linhas com download maior que 0, antes dos descartes da carga; no conjunto canônico (depois de descartar linhas sem stats de estação) o hotmilk fica em 92,3 Mbps com 1 cliente e 37,1 com 2.

81% da variância do download fica dentro da mesma posição. Médias por (prédio, rádio, `n_clients`) já explicam R² 0,49. `n_clients` está classificado como `identificador` e nunca entrou em versão. Ele bate com `combo` (número de letras = número de clientes).

**Grupos de teste simultâneo.** Agrupando por (`dataset`, `session_id`, `run_id`, `combo`): em 91% dos grupos o tamanho é igual a `n_clients`. `run_id` se repete ao longo do tempo dentro da mesma sessão (hotmilk), e falta a linha de algum cliente em parte dos grupos. 69 dos 406 grupos com mais de um cliente misturam 2,4 e 5 GHz. A casa-marcelo tem dois roteadores (AX1750 e AX3000).

**Teto de WAN.** Na residência, p99 do download é 154 Mbps e do upload 99,8 Mbps. 20 linhas de download (de 490) e 19 de upload ficam a ≥85% do teto com `router_expected_throughput_mbps` acima dele. Os demais prédios chegam a p99 de 262 a 642 Mbps, sem teto evidente.

**Sem stats de estação.** Na casa-marcelo, só 56% das linhas têm `router_tx_rate_mbps` (o AX3000 e todo o `20260925` não trazem stats de estação). Hoje o imputer preenche essas linhas com a mediana.

**Confusões que só a coleta resolve.** Os moto g9 aparecem só na residência e no coworking (no 2,4 GHz ficam em 5–6 Mbps de mediana). O ARCHER_C7 aparece só no coworking. Taxas PHY e `router_expected_throughput_mbps` são lidas com o enlace carregado pelo speedtest; em produção o ACS lê em momento qualquer.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Escopo | A + B nesta spec; C + D como lembrete (seção 10) |
| Datasets, coletor e extrator | Não mexer; observações vão para o responsável (seção 9) |
| Concorrência | `n_clients` (reclassificado) + `concorrentes_mesmo_radio`; sem `concorrentes_total` |
| Teto de WAN | Linhas limitadas saem do treino; previsão final = `min(previsão, teto)` |
| Métrica | Regressão (MAE, MAE log, R²) para treino; "atende em throughput" por aplicação para decisão. Promover não pode piorar nenhuma das duas |
| Arquitetura | Carga e régua únicas no `core`, usadas pelo Studio e pelos scripts |
| Linhas sem stats de estação | Fora do treino e da avaliação |

## 4. Carga única: `src/ml/core/carga.py`

Devolve o conjunto canônico para um alvo. Só lê; nunca grava em `data/`.

### 4.1 Descoberta e remoção de duplicatas

- `discover`, `_read_any`, `_generation`, `_superseded` e o fingerprint de alvos saem de `src/ml/studio/data.py` e vêm para cá, sem mudar a lógica. `studio/data.py` passa a importá-los e continua montando o payload (`BUILDINGS`, `POSITION_LABELS`, envelopes e plantas ficam no Studio).
- Conjunto padrão: geração atual, não substituído, não duplicado. Hoje são os mesmos 5 arquivos da seção 2.
- Os scripts aceitam `DATASETS=a.zip,b.zip` (nomes em `data/`) para sobrepor o padrão. `DS_CSV` sai de `regression_mlflow.py`.
- Nome do dataset de cada linha na coluna interna `_ds`.

### 4.2 Concorrência

Calculada **antes** de qualquer descarte de linha: um teste que falhou também disputava o ar.

- **Grupo de teste simultâneo:** (`_ds`, `session_id`, `run_id`, `combo`), e dentro dele só as linhas a até `JANELA_SIMULTANEO_S = 60` segundos da primeira, por `_time`. Linhas além dessa janela formam outro grupo (o `run_id` repetido mais tarde).
- **`concorrentes_mesmo_radio`:** número de linhas do grupo com o mesmo `bssid` da linha (ela incluída). Mesmo `bssid` = mesmo rádio do mesmo roteador.
- Fica NaN quando o tamanho do grupo é diferente de `n_clients` (faltou a linha de um cliente, ou duas rodadas caíram na mesma janela), quando falta `bssid` na linha ou quando falta `n_clients`. A contagem de NaN vai para os avisos.
- `n_clients` entra como está.

### 4.3 Descartes

Na ordem, cada um com contagem nos avisos:

1. Alvo vazio (já existe).
2. Alvo exatamente 0, por `descartar_testes_falhos` (já existe).
3. `local` desconhecido em `core/sites.py` (já existe no Studio).
4. **Novo:** linhas sem stats de estação, quando `router_tx_rate_mbps`, `router_rx_rate_mbps`, `router_snr` e `router_signal_dbm` estão **todos** vazios. Vale para todos os alvos.

### 4.4 Teto de WAN

- `src/ml/core/sites.py` ganha `TETOS_WAN = {'residencia': {'speedtest_down_mbps': 154.0, 'speedtest_up_mbps': 99.0}}`. Prédio ausente = sem teto conhecido.
- Coluna interna `_limitado_wan` (booleana), só para download e upload: verdadeira quando o prédio tem teto para o alvo, `alvo >= 0.85 * teto` e `router_expected_throughput_mbps > teto`. Para latência e jitter é sempre falsa.
- Contagem nos avisos.

### 4.5 Saída

- O dataclass `Conjunto` sai de `studio/features.py` e vem para `core/carga.py`, com os mesmos campos.
- Colunas internas: `_ds`, `_site` (prédio), `_pos` (posição), `_amb`, `_limitado_wan`. `_INTERNAS` passa a incluir `_limitado_wan`.
- As derivadas do catálogo continuam calculadas aqui (`aplicar_derivadas`), depois de `concorrentes_mesmo_radio`.
- `preparar` do Studio vira um chamador de `carga`. `load_datasets` de `core/data.py` deixa de ser usado pelos scripts de treino; `descartar_testes_falhos`, `validate_columns` e as constantes continuam em `core/data.py`.

## 5. Régua única: `src/ml/core/avaliacao.py`

Dado um `Conjunto` e uma lista de features, devolve as previsões fora do fold e as métricas. `_logo`, `_resumo`, `avaliar` e `avaliar_versao` saem de `studio/features.py` e vêm para cá; o Studio passa a importá-los.

### 5.1 Folds e modelo

- LOGO por `_site` (prédio), sempre. `regression_benchmark.py` muda o padrão de `group_level` para `building`.
- Modelo da régua: o mesmo do Studio (imputer pela mediana + RandomForest de 200 árvores, `min_samples_leaf=2`, `random_state=42`). `regression_benchmark.py` pode passar outro estimador, nos mesmos folds e com as mesmas métricas.
- Treino de cada fold: sem as linhas `_limitado_wan`.
- Teste de cada fold: todas as linhas do prédio. Se o prédio tem teto para o alvo, a previsão vira `min(previsão, teto)`.
- Previsões fora do fold devolvidas como série indexada pela linha do `Conjunto`, para cruzar alvos.

### 5.2 Métricas

Por prédio e sobre todas as previsões fora do fold juntas (pooled):

- **Regressão:** R², MAE (unidade do alvo), MAE em escala log: média de `|log1p(y) - log1p(ŷ)|`, com `ŷ` cortado em 0.
- **Decisão, "atende em throughput":** para cada aplicação de `aplicacoes.json`, real = `down >= limiar_down and up >= limiar_up`; previsto, o mesmo com as previsões fora do fold. Só nas linhas com os dois alvos presentes e não descartadas em nenhum dos dois. Métrica: acurácia balanceada por aplicação, e a média entre aplicações. Aplicação em que só uma classe aparece no real fica de fora da média, com aviso.
- Latência e jitter continuam com as métricas de regressão; ficam fora de "atende" até a frente D.

### 5.3 Intervalos

- Bootstrap de **posições** (`_pos`), estratificado por prédio: em cada uma de `N_BOOTSTRAP = 1000` reamostragens, sorteia com reposição as posições de cada prédio e recalcula as métricas pooled sobre as previsões fora do fold já feitas (não retreina). `random_state` fixo.
- Intervalo de 90% (percentis 5 e 95) para cada métrica.
- Comparação de duas versões: as mesmas reamostragens para as duas, dando o intervalo da **diferença**.

### 5.4 Veredito de promoção

Sugestão mostrada na view Modelos; promover continua sendo decisão humana.

- **melhor:** o intervalo da diferença exclui 0 a favor da nova versão em MAE pooled **ou** em acurácia balanceada média de "atende", e a outra métrica não piora mais que `RUIDO` (0,02 em acurácia; 2% do MAE da base em MAE).
- **pior:** o intervalo da diferença exclui 0 contra a nova versão em qualquer uma das duas.
- **empate:** os demais casos.

O veredito por local que já existe (`veredito`, "melhora em N de M locais") continua, ao lado deste.

### 5.5 Limiares de aplicação

- `PROFILES` sai de `src/ml/studio/static/studio.js` para `src/ml/core/aplicacoes.json`, com os mesmos valores (download, upload, latência e jitter por aplicação).
- `core/aplicacoes.py` carrega e valida (as quatro chaves numéricas e não negativas por aplicação; pelo menos uma aplicação).
- O payload do Studio (`/api/payload`) ganha `aplicacoes`; `studio.js` passa a ler daí. A view Limiares continua editando só na sessão do navegador.

### 5.6 Registro e MLflow

- Toda `avaliacao` gravada em `modelos.json` ganha `versao_regua` (constante `VERSAO_REGUA = '2026-10-05.1'` em `avaliacao.py`), além das métricas novas com intervalo. `validar_registro` aceita o campo.
- Avaliação sem `versao_regua`, ou com versão diferente da atual, aparece na view Modelos como "desatualizada", com o motivo "régua de avaliação mudou", no mesmo mecanismo que já avisa quando a classificação ou o catálogo mudam.
- `src/ml/regression_mlflow.py`:
  - usa `carga` e `avaliacao`;
  - registra métricas de **todos** os folds, as pooled com intervalo, o nome da versão, a lista e os fingerprints dos datasets, `versao_tabela`, `CATALOGO_VERSAO` e `VERSAO_REGUA`;
  - treina o modelo final com todas as linhas não limitadas pelo teto e o registra (skops, como hoje);
  - as 6 configurações de árvore atuais continuam como varredura, cada uma avaliada pela régua.

## 6. Features e versões

### 6.1 Classificação (`src/ml/core/column_provenance.json`)

- `n_clients`: `{"classe": "tr069", "parametro": "substituto de estações ativas no rádio; em produção depende do coletor"}`.
- `concorrentes_mesmo_radio`: `{"classe": "tr069", "parametro": "clientes em teste simultâneo no mesmo bssid; em produção depende do coletor"}`. É coluna calculada em `carga` (não derivada do catálogo: os insumos de agrupamento são identificadores e fariam a derivada cair em `auxiliar`). Entra em `colunas_conhecidas` porque `carga` sempre a produz.

### 6.2 Versões (`src/ml/core/modelos.json`)

- `v3-tr069`: features da `v2-tr069` + `n_clients` + `concorrentes_mesmo_radio`. Salva com `salvar_versao`, com a avaliação da régua nova nos quatro alvos. **Não fica ativa.**
- `v1` e `v2-tr069` não mudam (versões são imutáveis). A comparação na view Modelos é recalculada pela régua nova.

### 6.3 Ordem do experimento

Registrada no CHANGELOG, cada passo em separado para atribuir o ganho:

1. `v2-tr069` na régua antiga (número de referência, já registrado: download R² pooled 0,59, MAE 45 Mbps).
2. `v2-tr069` na régua nova: efeito da carga (sem stats fora, teto de WAN, intervalos).
3. `v3-tr069` na régua nova: efeito da concorrência.

## 7. Erros e avisos

- Conjunto com menos de 2 prédios depois dos descartes: erro, como hoje (`_checar_locais`).
- Menos de 4 prédios: aviso de instabilidade, como hoje.
- `aplicacoes.json` inválido: erro na carga do Studio e da régua, com o nome da aplicação e do campo.
- Feature com vazamento numa lista avaliada: `assert_sem_vazamento` continua levantando.
- Toda regra de descarte e marcação da carga gera uma linha de aviso com contagem, exibida no Studio e impressa nos scripts.

## 8. Testes

- `tests/test_carga.py` (novo):
  - grupo simultâneo: mesmo `run_id` a mais de 60 s vira outro grupo; grupo de tamanho diferente de `n_clients` dá NaN; dois `bssid` no mesmo grupo dão contagens separadas;
  - concorrência calculada antes do descarte de alvo 0;
  - linha sem os quatro campos de enlace sai; linha com só um deles fica;
  - `_limitado_wan` só com as duas condições; nunca para latência e jitter; prédio sem teto nunca marca;
  - dedupe e `_superseded` (testes que hoje cobrem `studio/data.py` passam a importar de `core/carga.py`).
- `tests/test_avaliacao.py` (novo):
  - folds sempre por prédio;
  - linha limitada fora do treino e presente no teste;
  - previsão cortada no teto;
  - MAE log com previsão negativa;
  - "atende" com dois alvos e aplicação de classe única excluída da média;
  - bootstrap determinístico com `random_state` e estratificado (todo prédio presente em toda reamostragem);
  - veredito nos três casos.
- `tests/test_aplicacoes.py` (novo): validação do JSON.
- `tests/test_modelos_core.py`: `versao_regua` aceito.
- Os testes atuais de Studio (`test_studio_features.py`, `test_studio_assistente.py`, `test_selecao.py`, `test_formulas_paralelos.py`) continuam passando, ajustando só os imports que mudaram de módulo.

## 9. Para o responsável pela coleta

Nada daqui é implementado nesta entrega. São observações para repassar.

1. **Token versionado.** `src/get-all.py:10` tem um token do InfluxDB em texto, comentado, no histórico do git. Revogar e gerar outro.
2. **Snapshot pré-teste (deadzone).** Contadores (`router_tx/rx_bytes`, `_packets`, `_duration_us`, `_retries`, `_failed`, `_drop_misc`) são o delta da janela do speedtest e vazam o alvo. Taxas PHY e `router_expected_throughput_mbps` são lidas com o enlace carregado. Pedido: gravar também uma leitura numa janela que termina alguns segundos antes do início do teste, em colunas separadas (por exemplo `router_pre_*`).
3. **Estações ativas por rádio.** Para `n_clients` e `concorrentes_mesmo_radio` existirem em produção: `Device.WiFi.AccessPoint.{i}.AssociatedDeviceNumberOfEntries` por rádio, e o volume de cada estação associada na janela pré-teste (para contar as ativas).
4. **Rodízio de clientes e roteadores.** Hoje os moto g9 só aparecem na residência e no coworking, e o ARCHER_C7 só no coworking. Levar os mesmos clientes e roteadores a prédios diferentes separa o efeito do aparelho do efeito do prédio.
5. **Grupos de teste simultâneo.** `run_id` se repete ao longo do tempo dentro da mesma sessão (hotmilk), e em cerca de 9% dos grupos falta a linha de algum cliente. Um identificador único por rodada simultânea, e uma linha por cliente mesmo quando o teste falha, eliminam a heurística de 60 s.
6. **Stats de estação ausentes.** O AX3000 da casa-marcelo e todo o `20260925` não trazem stats de estação.
7. **Teto de WAN.** Registrar o plano contratado de cada local de coleta (download e upload) junto da coleta, em vez de inferir pelo p99.

## 10. Próximos passos: frentes C e D (lembrete)

Fora do escopo desta spec. Cada uma vira sua própria spec, depois que a régua desta estiver em uso, porque é ela que vai dizer se ajudam.

### C. Dados externos e fine-tuning

- **Fontes que se encaixam nas colunas TR-069:**
  - IEEE 802.11ac performance dataset (IEEE DataPort): SNR, MIMO, largura de canal, MCS, guard interval e agregação → throughput normalizado. Corresponde a `router_snr`, `router_NSS_*`, `channel_width` e taxa PHY.
  - Komondor / ITU AI for 5G Challenge (Zenodo, registros 7198348 e 5574984): WLANs densas simuladas, RSSI, SINR, interferência e channel bonding → throughput. Corresponde a sinal e `router_opportunity_medium_use`.
  - Prior sintético próprio: tabelas de MCS 802.11n/ac/ax mais eficiência de MAC, dando a capacidade teórica do enlace. Barato e cobre faixas que as coletas não têm.
- **Kaggle:** pouco útil. Ookla é agregado por tile, sem métrica de enlace; os datasets de RSSI são de localização, sem throughput; os de LTE são celular.
- **Como fazer o fine-tuning com árvores:**
  1. modelo externo como feature de prior + modelo de resíduo no TR-069 (o mais compatível com RF/XGB);
  2. MLP pré-treinada no externo e ajustada no TR-069;
  3. modelo tabular de fundação (TabPFN), que costuma ir bem com cerca de 1,6 mil linhas.
- **Outras ideias de modelagem** a testar na mesma régua: alvo em `log1p`, restrições monotônicas no gradient boosting (SNR, taxa PHY e largura de canal só podem aumentar o throughput; `n_clients` só pode diminuir), regressão quantílica para dar faixa em vez de ponto.

### D. Latência e jitter

- 97% da variância da latência fica dentro da mesma posição, com caudas de até 3,5 s; o R² pooled da `v2-tr069` é negativo nos dois alvos.
- Reformular o alvo em vez de insistir na regressão: classificação "atende" pelos limiares de latência e jitter de `aplicacoes.json`, ou previsão de percentil (p90) por posição.
- Depois disso, "atende em throughput" (seção 5.2) vira "atende" completo, com os quatro limiares.
