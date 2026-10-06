# Latência e jitter por quantis e "atende completo" (design)

**Data:** 2026-10-05
**Base:** `master` (commit `7a81093`), depois da régua única (`docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

Hoje latência e jitter são tratados como regressão pontual, e o R² pooled da `v2-tr069` é negativo nos dois. A métrica "atende" só cobre throughput. Esta entrega:

- prevê latência e jitter como **faixa** (p50 e p90) em escala log, com um modelo quantílico;
- mede essa faixa na régua única (LOGO por prédio) por pinball loss e **cobertura**;
- fecha o **"atende completo"** por aplicação, com os quatro limiares: download e upload pela previsão pontual, latência e jitter pelo p90.

Esta é a frente D do lembrete da spec anterior. A frente C (dados externos e fine-tuning) vem depois, com sua própria spec (seção 9).

## 2. Evidência

Medido em 2026-10-05 no conjunto canônico (`core/carga.py`, 5 datasets, 4 prédios). Latência: 1.311 linhas. Jitter: 1.310 linhas.

**Caudas.** Latência: p50 13,5 ms, p90 45,8 ms, p99 350 ms, máximo 3.543 ms. Jitter: p50 5,5 ms, p90 40,2 ms, p99 205 ms, máximo 884 ms.

**Existe sinal.** A correlação de Spearman dentro de cada prédio é consistente:

| Feature | latência | jitter |
|---|---|---|
| `router_snr` | −0,32 a −0,50 | −0,30 a −0,54 |
| `router_rx_rate_mbps` | −0,28 a −0,66 | −0,19 a −0,63 |
| `router_expected_throughput_mbps` | −0,35 a −0,61 | −0,27 a −0,57 |
| `router_opportunity_medium_use` | +0,06 a +0,38 | +0,18 a +0,51 |

A mediana sobe com a concorrência. Latência: 9,3 ms (1 cliente), 13,6 (2) e 29,4 (3). Jitter: 4,6, 5,7 e 12,2 ms.

**Sem linha de base de WAN.** O p5 da latência fica entre 3,4 e 4,0 ms em todos os prédios, e `local_test` é `internal` em todas as linhas: o servidor de teste é local. A diferença entre prédios (mediana de 6,4 ms na casa-marcelo e 21,9 ms na residência) vem do Wi-Fi e da contenção. Em escala log, o prédio explica 12% da variância da latência e 5% da do jitter.

**"Atende" por aplicação quase não discrimina sozinho.** Fração de linhas que atendem o limiar:

| Aplicação | latência | jitter |
|---|---|---|
| Navegação | 0,986 | 0,968 |
| Chamada de vídeo | 0,977 | 0,854 |
| Streaming 4K | 0,994 | 0,968 |
| Jogo em nuvem | 0,882 | 0,644 |

Por isso o desenho prevê a faixa e deriva o "atende" dela, em vez de treinar um classificador por aplicação.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Ordem das frentes | D agora, C depois |
| Saída do modelo | Faixa por quantis (p50 e p90) em escala log |
| Quantil que decide "atende" em latência e jitter | p90 |
| Modelo | Gradient boosting quantílico (`HistGradientBoostingRegressor`, `loss='quantile'`), sem calibração conformal por enquanto |
| Calibração conformal (CQR) | Só se a cobertura medida pedir (critério na seção 7) |
| Features | As da `v3-tr069`, sem versão nova |

## 4. Régua quantílica: `src/ml/core/quantis.py` (novo)

Módulo próprio, para não crescer `avaliacao.py`. Reaproveita de `avaliacao` `reamostras`, `_intervalo`, `_juntar`, `_acuracia_balanceada`, `_media_sem_nan`, `_atende_em` e `assert_sem_vazamento`.

### 4.1 Constantes

- `QUANTIS = (0.5, 0.9)`.
- `ALVOS_QUANTILICOS = ('latency_ms', 'jitter_ms')`.
- `FAIXA_COBERTURA = (0.80, 0.95)`: faixa aceita para a cobertura pooled do p90.

### 4.2 Modelo

- `modelo_quantil(q)`: `HistGradientBoostingRegressor(loss='quantile', quantile=q, learning_rate=0.05, max_iter=300, min_samples_leaf=20, random_state=42)`. Aceita NaN sem imputer. Categóricas entram em one-hot por `features.matriz`, como no resto da régua.
- Treina em `log1p(y)` e prevê `expm1(previsão)`, cortado em 0.
- Quantis cruzados: se o p90 previsto ficar abaixo do p50, o p90 passa a valer o p50.

### 4.3 `prever_quantis_fora_do_fold(df, colunas, y_col, vazadas)`

- O mesmo LOGO por `_site` de `avaliacao.prever_fora_do_fold`, com `assert_sem_vazamento` e `matriz`.
- Sem teto de WAN (não se aplica a latência e jitter).
- Devolve um DataFrame indexado como `df`, com `_linha`, `y`, `q50`, `q90`, `_site` e `_pos`.

### 4.4 Métricas: `resumir_quantis(prev, n)`

Por prédio e pooled:

- `pinball` de cada quantil, em ms, definido como a média de `max(q·(y − ŷ), (q − 1)·(y − ŷ))`;
- `cobertura` de cada quantil: a fração de `y ≤ ŷ`;
- `intervalos`: intervalo de 90% de pinball e cobertura pooled, pelo bootstrap de posições de `avaliacao.reamostras`;
- `cruzados`: quantas linhas tiveram o p90 corrigido para o p50 (seção 4.2);
- `mediana_mae`: MAE em ms da previsão p50, para comparar com a regressão (seção 7.2);
- `versao_regua`.

### 4.5 Comparação e veredito

- `delta_pinball(nova, base, q=0.9)`: pinball da nova versão menos o da base, nas mesmas linhas (`_juntar`) e nas mesmas reamostragens. Devolve `valor`, `intervalo`, `pinball_base` e `n`.
- `veredito_quantis(delta, cobertura_nova)`:
  - **pior:** a cobertura pooled do p90 da nova versão sai de `FAIXA_COBERTURA`, ou o intervalo de Δ pinball fica todo acima de 0;
  - **melhor:** o intervalo de Δ pinball fica todo abaixo de 0 e a cobertura está dentro da faixa;
  - **empate:** o resto.

### 4.6 "Atende completo": `atende_completo(prev_dn, prev_up, quant_lat, quant_jit, aplicacoes)`

- **Real:** `down ≥ dn`, `up ≥ up`, `latência ≤ lat` e `jitter ≤ jit`, com os limiares de `core/aplicacoes.json`.
- **Previsto:** download e upload previstos (pontuais) contra `dn` e `up`; o **p90** de latência e de jitter contra `lat` e `jit`.
- Só nas linhas presentes nos quatro alvos (junção por `_linha`).
- Mesma forma de `avaliacao.atende`: acurácia balanceada por aplicação, média, intervalo, `n` e avisos. Aplicação com uma classe só nos dados reais fica fora da média.
- `atende_throughput` continua existindo e continua sendo a métrica de decisão das versões de throughput.

## 5. Integração

1. **Versão da régua:** `avaliacao.VERSAO_REGUA` passa a `2026-10-05.2`. Avaliações guardadas sem quantis (a da `v3-tr069`) aparecem como "desatualizadas" pelo mecanismo existente.
2. **`api.avaliacao_completa`:**
   - continua com as métricas de regressão nos quatro alvos, para não quebrar as tabelas atuais;
   - para latência e jitter, acrescenta `quantis` (o resumo da seção 4.4) ao resultado do alvo;
   - grava `atende_completo` ao lado de `atende_throughput`.
3. **`api._promocao`:** para latência e jitter, usa `delta_pinball` e `veredito_quantis` (`delta_mae`/`delta_atende` não se aplicam). Download e upload não mudam. O resultado mantém as chaves `veredito` e `versao_regua`, e troca `delta_mae`/`delta_atende` por `delta_pinball` e `cobertura`.
4. **Interface:**
   - **Versões salvas** (`modelos.js`): com alvo latência ou jitter, as colunas de R² e MAE passam a mostrar a cobertura do p90 e o pinball do p90, e os cabeçalhos mudam com o alvo. Uma coluna nova mostra o "atende completo" (média e intervalo) em qualquer alvo.
   - **Assistente** (`assistente.js`): para latência e jitter, o cartão de promoção mostra Δ pinball p90 com intervalo e a cobertura da nova versão.
5. **`regression_mlflow.py`:** com `ALVO` em `ALVOS_QUANTILICOS`, ignora a varredura das 6 configurações de árvore e treina os dois modelos quantílicos. Registra pinball, cobertura e intervalos (pooled e por prédio) e os dois modelos finais (skops, com os mesmos `skops_trusted_types` já usados).
6. **Sem mudança:** `regression_benchmark.py`, `core/carga.py`, `column_provenance.json` e o registro de versões (nenhuma versão nova).

## 6. Erros e avisos

- Feature com vazamento: `assert_sem_vazamento` levanta, como na régua de regressão.
- Menos de 2 prédios: o mesmo erro de `outer_logo_folds`.
- `atende_completo` sem nenhuma linha comum aos quatro alvos: `ValueError` com mensagem clara (a API devolve 422).
- Quantis cruzados não geram aviso: a correção da seção 4.2 é silenciosa. A contagem de linhas corrigidas entra no resumo como `cruzados`, para a régua mostrar se isso é frequente.

## 7. Testes, experimento e critério para a CQR

### 7.1 Testes

- `tests/test_quantis.py` (novo):
  - folds sempre por prédio, `_linha` estável, colunas de saída;
  - transformação log, corte em 0 e correção de quantis cruzados (com um estimador falso que devolve p90 < p50);
  - pinball e cobertura conferidos com valores calculados à mão;
  - `delta_pinball` com uma versão perfeita contra uma deslocada;
  - `veredito_quantis` nos três casos, incluindo "pior" por cobertura fora da faixa com pinball melhor;
  - `atende_completo` com dados sintéticos, incluindo aplicação de classe única fora da média e junção só nas linhas comuns.
- `tests/test_studio_assistente.py`: `avaliacao_completa` traz `quantis` em latência e jitter e traz `atende_completo`; `_promocao` em latência devolve `delta_pinball` e o veredito quantílico.
- Os testes atuais continuam passando.

### 7.2 Experimento (registrado no CHANGELOG)

- `v2-tr069` e `v3-tr069` em latência e jitter: cobertura do p50 e do p90 por prédio e pooled, pinball, intervalos e "atende completo".
- Referência: o MAE em ms da mediana quantílica ao lado do MAE da regressão RF atual, nas mesmas linhas.

### 7.3 Critério para a CQR

Se a cobertura do p90 de algum prédio deixado de fora sair da faixa de 0,80 a 0,95, o CHANGELOG registra isso e a recomendação passa a ser implementar a calibração conformal (CQR: quantílico mais correção calculada em LOGO interno nos prédios de treino). Se todas ficarem dentro, a CQR não entra.

## 8. Para o responsável pela coleta

Nada daqui é implementado nesta entrega.

1. **Quando a latência é medida.** A correlação de −0,4 a −0,7 entre latência e download sugere latência medida durante o download (sob carga, bufferbloat), e não com o enlace ocioso. As duas coisas são úteis, mas são alvos diferentes. Pedido: confirmar em que momento do teste a latência e o jitter são medidos e, se possível, gravar as duas (ociosa e sob carga) em colunas separadas.

## 9. Próximo passo: frente C (lembrete)

Dados externos e fine-tuning ficam para a próxima spec, como descrito na seção 10 de `docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`:

- fontes: IEEE 802.11ac performance dataset (DataPort, exige login), Komondor / ITU AI for 5G Challenge (Zenodo) e um prior sintético próprio a partir das tabelas de MCS;
- caminhos de fine-tuning com árvores: prior externo como feature mais modelo de resíduo, MLP pré-treinada, ou TabPFN;
- outras ideias de modelagem para throughput na mesma régua: alvo em `log1p`, restrições monotônicas e regressão quantílica (que esta entrega já deixa pronta para reuso).
