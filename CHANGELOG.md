# Changelog — Throughput como eficiência do enlace (C1): nova `v4-tr069`

**Data:** 2026-10-06

## Por quê

No download, o hotmilk chega a 670,53 Mbps (máximo) com p90 de 487,39, enquanto o maior dos outros
três prédios (coworking) não passa de 266,54; o MAE da `v3-tr069` no hotmilk era de 90,8652 Mbps.
As árvores não extrapolam acima do que viram no treino, e sem o hotmilk no treino o modelo não
consegue prever acima do que os outros prédios mostraram (spec, seção 1). O TR-069 já traz a taxa
PHY nominal do enlace; esta entrega (frente C1) usa essa física como prior: a régua passa a prever
a **eficiência** (alvo ÷ taxa PHY da direção) em vez do Mbps absoluto — comparável entre prédios —
e a previsão volta a Mbps multiplicando pela taxa.

## Mudanças

- `core/modelos.py`: campo opcional `denominador` por versão (`{alvo: coluna}`, só para
  `speedtest_down_mbps`/`speedtest_up_mbps`), validado em `validar_registro` e `salvar_versao`
  (recusa coluna desconhecida ou com vazamento); `denominador_de` lê o valor de uma versão.
- `core/avaliacao.py`: `prever_fora_do_fold`, `avaliar` e `avaliar_versao` ganham `denominador`:
  treinam em `y ÷ den`, multiplicam a previsão por `den`, imputam `den` vazio pela mediana do
  treino do fold (marcando `den_imputado`) e aplicam o teto de WAN depois da multiplicação;
  `resumir` ganha `den_imputados`; versão da régua `2026-10-06.2`.
- `studio/features.py` e `studio/api.py`: comparação, avaliação, promoção e salvamento passam o
  denominador de cada versão; o rascunho do Assistente herda o denominador da base.
- `studio/static/assistente.js`: o salvamento manda `base`. `studio/static/modelos.js`: versões
  salvas com denominador ganham a etiqueta "eficiência ÷ tx/rx".
- `regression_mlflow.py`: o ramo de eficiência treina em `y ÷ den` e registra o artefato
  `eficiencia.json`.
- Nova versão `v4-tr069` no registro: mesmas features da `v3-tr069`, download ÷
  `router_tx_rate_mbps` e upload ÷ `router_rx_rate_mbps`. Salva via `salvar_versao`, mas **não
  ativa** (`ativo` continua `v1`).

## Efeito medido (`v3-tr069` × `v4-tr069`, régua `2026-10-06.2`)

### Download (`speedtest_down_mbps`)

| Versão | R² pooled (IC 90%) | MAE pooled (IC 90%) | MAE log | `den_imputados` |
|---|---|---|---|---|
| v3-tr069 | 0,4211 (0,3496 a 0,5453) | 40,7453 (29,8683 a 50,7613) | 0,7129 | 0 |
| v4-tr069 | 0,5853 (0,4724 a 0,705) | 38,0974 (29,7219 a 46,1193) | 0,7534 | 0 |

R² por prédio — v3-tr069: casa-marcelo 0,6589, coworking 0,6492, hotmilk 0,2469, residência 0,6766;
v4-tr069: 0,364, 0,6648, 0,5034, 0,6881.

MAE por prédio — v3-tr069: casa-marcelo 25,1794, coworking 26,8908, hotmilk 90,8652, residência
16,1429; v4-tr069: 32,0921, 25,9624, 75,646, 16,3731.

### Upload (`speedtest_up_mbps`)

| Versão | R² pooled (IC 90%) | MAE pooled (IC 90%) | MAE log | `den_imputados` |
|---|---|---|---|---|
| v3-tr069 | 0,6194 (0,5447 a 0,7127) | 40,2498 (30,7914 a 49,5906) | 0,8311 | 0 |
| v4-tr069 | 0,6754 (0,578 a 0,7993) | 36,5382 (27,662 a 45,7652) | 0,7571 | 0 |

R² por prédio — v3-tr069: casa-marcelo 0,6286, coworking 0,3945, hotmilk 0,5016, residência 0,2531;
v4-tr069: 0,6573, 0,3681, 0,586, 0,3.

MAE por prédio — v3-tr069: casa-marcelo 36,9348, coworking 28,2538, hotmilk 79,1961, residência
15,0927; v4-tr069: 35,4929, 28,8231, 69,2852, 13,4934.

### Atende e promoção

"Atende em throughput": `v3-tr069` média 0,6551 (IC 0,6381 a 0,6756) e `v4-tr069` 0,6425 (IC 0,6248
a 0,6662). Por aplicação, `v3-tr069` → `v4-tr069`: Navegação 0,5188 → 0,5038; Chamada de vídeo
0,5583 → 0,5474; Streaming 4K 0,7773 → 0,7824; Jogo em nuvem 0,7661 → 0,7363.

"Atende completo": `v3-tr069` 0,6611 (IC 0,6418 a 0,6904) e `v4-tr069` 0,6624 (IC 0,6421 a 0,6926).

Veredito de promoção `v4-tr069` contra `v3-tr069`, régua `2026-10-06.2`: download **pior**
(`delta_mae` −2,6479, IC −6,8412 a 1,6579; `delta_atende` −0,0127, IC −0,0195 a −0,0031: "a
acurácia de 'atende' caiu 0,013") e upload **pior** pelo mesmo motivo (`delta_mae` −3,7116, IC
−5,4043 a −1,7916; `delta_atende` −0,0127, IC −0,0195 a −0,0031). O R² e o MAE pooled melhoram nos
dois alvos, mas o critério de promoção pesa a acurácia de "atende", que piora um pouco nas duas
direções — por isso a `v4-tr069` fica salva e medida, mas não promovida a ativa.

## Exploração dos denominadores (spec, seção 2)

Protótipo anterior a este plano, com as features da `v3-tr069` e a régua `2026-10-06.1`:

| Denominador | Download R² / MAE / MAE log | Upload R² / MAE / MAE log |
|---|---|---|
| nenhum (Mbps absolutos, hoje) | 0,42 / 40,7 / 0,713 | 0,62 / 40,2 / 0,831 |
| `router_tx_rate_mbps` | 0,59 / 38,1 / 0,753 | 0,19 / 53,6 / 1,009 |
| `router_rx_rate_mbps` | 0,57 / 38,7 / 0,734 | 0,68 / 36,5 / 0,757 |
| média de `tx` e `rx` | 0,59 / 35,9 / 0,650 | 0,67 / 38,3 / 0,868 |
| máximo de `tx` e `rx` | 0,54 / 38,8 / 0,692 | 0,64 / 40,1 / 0,899 |
| raiz de `expected × tx` | 0,58 / 38,1 / 0,710 | 0,09 / 54,4 / 0,956 |
| `router_expected_throughput_mbps` | 0,54 / 38,4 / 0,677 | 0,04 / 54,9 / 0,906 |

A escolha final (download ÷ `tx`, upload ÷ `rx`) não foi a de melhor número isolado nesta tabela —
foi pela física da direção: download vai do roteador ao cliente (taxa de envio), upload vai do
cliente ao roteador (taxa de recepção); usar o lado errado no upload derruba o R² de 0,68 para
0,19. O efeito é físico, não acaso.

## Critério da C2 (dados externos): corrigido, a C2 não entra

O critério da spec (seção 8) comparava MAE **absoluto**: hotmilk 75,65 contra 23,22 nos outros três
prédios juntos, razão 3,26, acima do dobro. Mas os valores de download do hotmilk são cerca de três
vezes maiores que os dos outros prédios, então essa razão mede escala, não falta de conhecimento.
Em termos relativos, com a `v4-tr069`, o hotmilk não se destaca mais:

| Download, `v4-tr069` | hotmilk | outros três prédios |
|---|---|---|
| MAE absoluto (critério original) | 75,65 Mbps | 23,22 Mbps |
| MAE em escala log | 0,74 | 0,76 |
| Erro relativo mediano | 58% | 57% |

Na `v3-tr069`, o hotmilk era pior também em termos relativos (MAE log 0,80 contra 0,68): a
eficiência corrigiu isso. O critério passa a ser relativo: a C2 só entra se o MAE log de um prédio
for mais que 1,5 vez o dos outros juntos. Com a `v4-tr069`, a razão é 0,97, e **a C2 não entra**.

A lacuna real que sobra está nas 61 linhas do hotmilk acima de 267 Mbps, a faixa que nenhum outro
prédio cobre: ali o MAE caiu de 346 (`v3-tr069`) para 181 Mbps (`v4-tr069`), mas segue alto. É uma
lacuna de cobertura de coleta, que os dados externos listados dificilmente fecham (o IEEE 802.11ac
ensina a eficiência por MCS, que a `v4-tr069` já tira da taxa PHY; o Komondor simula cenários
densos, diferentes de um enlace de 160 MHz quase sem contenção).

Com a `v4-tr069`, o MAE log piorou na casa-marcelo (0,58 para 0,73) e na residência (0,80 para
0,86). Isso é compatível com a queda do "atende em throughput", mas a causa não foi isolada.

## Para o responsável pela coleta

Mais medições em enlaces de alta capacidade (160 MHz, Wi-Fi 6) em prédios além do hotmilk, para
que a faixa acima de cerca de 270 Mbps apareça no treino quando qualquer prédio fica de fora.

## Fica para depois

- Entender a queda do "atende" na `v4-tr069` (e a piora relativa na casa-marcelo e na residência)
  antes de qualquer promoção.
- Variantes de denominador (média de `tx` e `rx`, máximo, `router_expected_throughput_mbps`) como
  outras versões.
- A C2 (dados externos) fica fora até o critério relativo indicar uma lacuna que ela possa explicar.

---

# Changelog — Calibração conformal (CQR) do p90 de latência e jitter

**Data:** 2026-10-06

## Por quê

A cobertura do p90 sem correção ficava abaixo de 0,80 em três dos quatro prédios deixados de fora
(coworking, hotmilk e residencia, nos dois alvos), e a pooled era 0,71 em latência e 0,72 em jitter
na `v3-tr069` (ver o changelog "Latência e jitter por quantis"). O critério da spec da frente D
(seção 7.3) pedia a CQR nesse caso.

## Mudanças

- `core/quantis.py`: `correcao_conformal` (LOGO entre os prédios de treino, escores juntos, nível de
  amostra finita) é somada por padrão ao p90 em escala log (`conformal=True`). As previsões ganham as
  colunas `correcao` e `sem_correcao`, e o resumo ganha `correcao_por_local` e `sem_correcao`.
- `core/avaliacao.py`: versão da régua `2026-10-06.1`.
- `regression_mlflow.py`: o ramo quantílico calcula a correção de produção com todos os prédios e a
  registra na métrica `correcao_log_q90` e no artefato `conformal.json` (`q90_ms = expm1(predict(X)
  + correcao_log)`). Rodando `ALVO=latency_ms MODELO=v3-tr069`, a correção de produção foi 0,6134
  (escala log).
- O Studio não muda de código: a régua e o veredito de promoção já leem o p90 corrigido.

## Efeito medido (LOGO por prédio, 4 prédios)

Cru contra CQR, por alvo e versão (cobertura do p90 com intervalo de 90%):

| Alvo | Versão | Modo | Cobertura p50 | Cobertura p90 (IC 90%) | Pinball p90 | Cruzados |
|---|---|---|---|---|---|---|
| Latência | v2-tr069 | cru | 0,4241 | 0,73 (0,7087 a 0,751) | 14,5874 | 44 |
| Latência | v2-tr069 | CQR | 0,4241 | 0,9329 (0,9184 a 0,9471) | 14,5452 | 0 |
| Latência | v3-tr069 | cru | 0,4249 | 0,7109 (0,6849 a 0,7383) | 14,5556 | 54 |
| Latência | v3-tr069 | CQR | 0,4249 | 0,923 (0,9058 a 0,9413) | 14,227 | 0 |
| Jitter | v2-tr069 | cru | 0,4481 | 0,7435 (0,6945 a 0,8022) | 10,077 | 12 |
| Jitter | v2-tr069 | CQR | 0,4481 | 0,9168 (0,8928 a 0,9413) | 9,5548 | 0 |
| Jitter | v3-tr069 | cru | 0,4588 | 0,7176 (0,6659 a 0,7812) | 10,1632 | 36 |
| Jitter | v3-tr069 | CQR | 0,4588 | 0,9008 (0,874 a 0,9294) | 9,217 | 0 |

A CQR só mexe no p90: a cobertura e o pinball do p50 não mudam, e os quantis cruzados somem.

Correção somada ao p90 (escala log) por prédio deixado de fora, `v3-tr069`:

| Prédio | Latência | Jitter |
|---|---|---|
| casa-marcelo | 0,6428 | 0,7572 |
| coworking | 0,9248 | 1,1929 |
| hotmilk | 0,5993 | 0,847 |
| residencia | 0,858 | 1,025 |

Cobertura do p90 por prédio, `v3-tr069`, cru contra CQR:

| Prédio | Latência cru | Latência CQR | Jitter cru | Jitter CQR |
|---|---|---|---|---|
| casa-marcelo | 0,8491 | 0,9371 | 0,8145 | 0,9119 |
| coworking | 0,7413 | 1,0 | 0,6573 | 0,986 |
| hotmilk | 0,6596 | 0,8856 | 0,696 | 0,872 |
| residencia | 0,6498 | 0,9198 | 0,6878 | 0,8903 |

"Atende completo" com CQR (n=1298): `v2-tr069` média 0,6699 (IC 0,6496 a 0,7004) e `v3-tr069` média
0,6611 (IC 0,6418 a 0,6904); sem CQR eram 0,6526 e 0,6522. Por aplicação, sem CQR → com CQR:

| Aplicação | v2-tr069 | v3-tr069 |
|---|---|---|
| Navegação | 0,5405 → 0,6266 | 0,5426 → 0,5893 |
| Chamada de vídeo | 0,6184 → 0,6906 | 0,6063 → 0,6956 |
| Streaming 4K | 0,7739 → 0,7658 | 0,7751 → 0,7662 |
| Jogo em nuvem | 0,6777 → 0,5965 | 0,6848 → 0,5933 |

O p90 corrigido é mais alto, então o "atende" fica mais conservador: Jogo em nuvem cai de cerca de
0,68 para cerca de 0,59 nas duas versões, que é o custo de uma faixa que agora cobre o que promete.
Navegação e Chamada de vídeo sobem nas duas versões; não investiguei a causa por aplicação.

Veredito de promoção `v3-tr069` contra `v2-tr069`, régua `2026-10-06.1`: latência **melhor**
(`delta_pinball` −0,3182, IC −0,4516 a −0,1989; cobertura do p90 0,923, na faixa) e jitter
**melhor** (`delta_pinball` −0,3378, IC −0,7323 a −0,0376; cobertura do p90 0,9008, na faixa).

### Critério de aceite

A CQR é **aceita** (spec, seção 7.3): a cobertura pooled do p90 da `v3-tr069` com CQR fica em
0,923 na latência e 0,9008 no jitter, os dois dentro da faixa de 0,80 a 0,95. Nenhum prédio fica
abaixo de 0,80. O coworking fica acima de 0,95 (latência 1,0 e jitter 0,986): a faixa é
conservadora ali, e a correção vem do escore juntado dos outros três prédios. Hotmilk (0,8856 e 0,872) e residencia em jitter (0,8903) ficam na faixa, mas abaixo de 0,90.

## Fica para depois

A frente C (spec anterior, seção 10).

---

# Changelog — Latência e jitter por quantis

**Data:** 2026-10-05

## Por quê

Latência e jitter eram tratados como regressão pontual, com R² pooled negativo nos dois (spec,
seção 1-2). A distribuição tem cauda longa (p99 de 350 ms em latência e 205 ms em jitter, spec,
seção 2), o que o MAE e o R² representam mal. E o "atende" só cobria download e upload: latência e
jitter nunca entravam na decisão por aplicação.

## Mudanças

- `core/quantis.py` (novo): p50 e p90 em escala log por gradient boosting quantílico
  (`HistGradientBoostingRegressor`, `loss='quantile'`), fora do fold (LOGO por prédio); pinball
  loss, cobertura, intervalo de 90% por bootstrap de posições, correção de quantis cruzados,
  `delta_pinball`, `veredito_quantis` e `atende_completo`.
- `core/avaliacao.py`: versão da régua `2026-10-05.2`; `atende` passa a delegar a um
  `_resumo_atende` reaproveitado por quantis.
- `studio/api.py`: `avaliacao_completa` grava `quantis` e `atende_completo` em latência e jitter;
  `_promocao` usa o veredito quantílico (cobertura e `delta_pinball`) nesses dois alvos.
- `studio/static/modelos.js` e `studio/static/assistente.js`: cobertura e pinball do p90 de
  latência e jitter nas versões salvas, coluna "Atende completo" e cartão de promoção com
  `delta_pinball` e cobertura.
- `regression_mlflow.py`: ramo quantílico quando `ALVO=latency_ms` ou `jitter_ms`.

## Efeito medido (`v2-tr069` contra `v3-tr069`, LOGO por prédio, 4 prédios)

| Alvo | Versão | Cobertura p50 | Cobertura p90 (IC 90%) | Pinball p50 | Pinball p90 | MAE mediana | MAE RF | Cruzados |
|---|---|---|---|---|---|---|---|---|
| Latência | v2-tr069 | 0,4241 | 0,73 (0,7087 a 0,751) | 11,5849 | 14,5874 | 23,1698 | 31,7348 | 44 |
| Latência | v3-tr069 | 0,4249 | 0,7109 (0,6849 a 0,7383) | 11,3632 | 14,5556 | 22,7264 | 31,3342 | 54 |
| Jitter | v2-tr069 | 0,4481 | 0,7435 (0,6945 a 0,8022) | 8,2032 | 10,077 | 16,4065 | 23,2775 | 12 |
| Jitter | v3-tr069 | 0,4588 | 0,7176 (0,6659 a 0,7812) | 8,1315 | 10,1632 | 16,2629 | 22,3425 | 36 |

Cobertura do p90 por prédio, `v3-tr069` (1.311 linhas em latência, 1.310 em jitter):

| Prédio | Latência | Jitter |
|---|---|---|
| casa-marcelo | 0,8491 | 0,8145 |
| coworking | 0,7413 | 0,6573 |
| hotmilk | 0,6596 | 0,696 |
| residencia | 0,6498 | 0,6878 |

"Atende completo" (download e upload pela previsão pontual, latência e jitter pelo p90; n=1298):
`v2-tr069` média 0,6526 (IC 0,6302 a 0,6903) e `v3-tr069` média 0,6522 (IC 0,6304 a 0,6878). Por
aplicação, `v2-tr069` → `v3-tr069`: Navegação 0,5405 → 0,5426, Chamada de vídeo 0,6184 → 0,6063,
Streaming 4K 0,7739 → 0,7751, Jogo em nuvem 0,6777 → 0,6848. Para referência, o "atende" só de
throughput (régua anterior) é `v2-tr069` 0,6446 (0,6254 a 0,6647) e `v3-tr069` 0,6551 (0,6381 a
0,6756).

Veredito de promoção `v3-tr069` contra `v2-tr069`: latência **pior** (`delta_pinball` −0,0318, IC
−0,1067 a 0,0245; cobertura do p90 0,71, fora da faixa de 0,80 a 0,95, "a faixa prevista não é
confiável"); jitter **pior** pela mesma razão (`delta_pinball` 0,0862, IC −0,1373 a 0,2698;
cobertura do p90 0,72).

### Conclusão sobre a CQR

O critério da spec (seção 7.3) pede que, se a cobertura do p90 de algum prédio deixado de fora sair
da faixa de 0,80 a 0,95, o CHANGELOG registre isso e a recomendação passe a ser implementar a
calibração conformal (CQR). Na `v3-tr069`, só a casa-marcelo fica dentro da faixa nos dois alvos
(0,8491 em latência, 0,8145 em jitter); coworking, hotmilk e residencia ficam abaixo de 0,80 nos
dois alvos. **Recomendação: implementar a CQR** antes de promover qualquer versão por latência ou
jitter — o p90 sem calibração sub-cobre na maioria dos prédios, então o "atende" derivado dele é
otimista fora da casa-marcelo.

## Para o responsável pela coleta

Confirmar em que momento do teste a latência e o jitter são medidos (enlace ocioso ou sob carga,
durante o próprio download) — ver spec, seção 8. A correlação de −0,4 a −0,7 entre latência e
download (spec, seção 2) é compatível com medição sob carga, mas isso não está confirmado pelo
coletor.

## Fica para depois

A frente C (spec anterior, seção 10) e, pelo critério acima, a CQR em latência e jitter.

---

# Changelog — Régua única, carga canônica e concorrência

**Data:** 2026-10-05

## Por quê

O Studio e os scripts de treino mediam com réguas diferentes: `regression_mlflow.py` agrupava por
posição (o mesmo prédio no treino e no teste), usava um fold só e lia um CSV antigo. E o fator que
mais move o download, quantos clientes testam ao mesmo tempo, não entrava em nenhuma versão: no
hotmilk o download mediano cai de 92 para 37 Mbps com 2 clientes (`n_clients` 1 contra 2).

## Mudanças

- `core/carga.py`: uma carga só para Studio e scripts. Descoberta e duplicatas (antes no Studio),
  `concorrentes_mesmo_radio` (clientes em teste simultâneo no mesmo `bssid`), descarte de linhas sem
  stats de estação (taxa PHY, SNR e sinal vazios), marca `_limitado_wan` (alvo no teto do plano de
  internet: residência 154/99 Mbps) e a chave `_linha`, estável entre alvos.
- `core/avaliacao.py`: uma régua só. LOGO por prédio, linhas no teto de WAN fora do treino e
  previsão cortada no teto, MAE em escala log, intervalo de 90% por bootstrap de posições,
  "atende em throughput" por aplicação (acurácia balanceada) e veredito de promoção pelo intervalo
  da diferença. Versão da régua `2026-10-05.1`.
- Limiares de aplicação saem do `studio.js` para `core/aplicacoes.json`.
- `n_clients` e `concorrentes_mesmo_radio` passam a `tr069`, marcadas como dependentes do coletor.
- `regression_mlflow.py` e `regression_benchmark.py` medem pela régua e leem o conjunto canônico
  (`DATASETS=` / `--datasets`). `--csv` e `DS_CSV` saíram.
- Nova `v3-tr069` (`v2-tr069` + concorrência), não ativa; a `v1` continua ativa. A `v2-tr069`
  segue imutável, com a avaliação antiga gravada: o Studio a marca como desatualizada.

## Efeito medido (deixando um prédio de fora, 4 prédios)

| Versão | Régua | Download R² pooled (90%) | Download MAE (90%) | Atende (90%) |
|---|---|---|---|---|
| v2-tr069 | antiga | 0,59 | 45,0 | – |
| v2-tr069 | nova | 0,41 (0,35 a 0,52) | 42,0 (31,6 a 52,1) | 0,645 (0,625 a 0,665) |
| v3-tr069 | nova | 0,42 (0,35 a 0,55) | 40,7 (29,9 a 50,8) | 0,655 (0,638 a 0,676) |

MAE log do download na régua nova: 0,736 na `v2-tr069` e 0,713 na `v3-tr069`. R² por prédio do
download (`v2-tr069` → `v3-tr069`): casa-marcelo 0,60 → 0,66, coworking 0,47 → 0,65, hotmilk
0,26 → 0,25, residencia 0,49 → 0,68. Upload (`v2-tr069` → `v3-tr069`): R² pooled 0,54 (0,47 a 0,61)
→ 0,62 (0,54 a 0,71) e MAE 44,5 (33,8 a 54,9) → 40,2 (30,8 a 49,6).

Veredito de promoção v3 contra v2: download **melhor** ("atende" subiu 0,011, 90%: 0,006 a 0,017,
sem piorar o MAE; o MAE variou −1,2, 90%: −3,1 a 0,5, dentro do ruído); upload **melhor** (o MAE
caiu 4,3, 90%: −5,5 a −2,8, sem piorar "atende"). O "atende" é calculado sobre o download, por isso
o `delta_atende` do upload é o mesmo do download.

### O R² não é comparável entre as duas réguas

A queda de 0,59 para 0,41 no R² da `v2-tr069` não é piora do modelo. Com as mesmas funções de
`carga` e `avaliacao` e cada regra nova ligada isoladamente (download, 4 prédios, RandomForest com
200 árvores, deixando um prédio de fora):

| Regras da carga ligadas | linhas | R² pooled | MAE (Mbps) |
|---|---|---|---|
| nenhuma (como na régua antiga) | 1628 | 0,5925 | 45,02 |
| só descartar linhas sem stats de estação | 1300 | 0,4493 | 41,34 |
| só teto de WAN (sem descartar linhas sem stats) | 1628 | 0,5922 | 45,01 |
| todas (padrão novo) | 1300 | 0,4137 | 41,99 |

- Sem nenhuma regra nova, a régua reproduz o número antigo (0,5925 e 45,02): a régua em si é fiel.
- O que baixa o R² é descartar as 328 linhas sem stats de estação (0,59 para 0,45) enquanto o MAE
  melhora (45,0 para 41,3). Essas linhas ainda têm `radio`, `client_mode` e `channel_width`, então o
  modelo as previa bem pelo contraste 2,4 contra 5 GHz, o que inflava o R².
- A regra de WAN custa um pouco mais de R² (0,45 para 0,41, porque as linhas cortadas são a ponta
  alta que o modelo costumava ajustar) e mantém o MAE estável.
- Por isso o R² não é comparável entre as duas réguas, e o MAE é o número a comparar.
- Contagem na carga atual do download: 328 linhas descartadas no total (não só as cerca de 253 do
  casa-marcelo), 14 testes que falharam, 20 linhas no teto de WAN e 24 sem
  `concorrentes_mesmo_radio`.

## Para o responsável pela coleta

Ver `docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`, seção 9: token
versionado em `src/get-all.py`, snapshot pré-teste, estações ativas por rádio, rodízio de clientes e
roteadores, `run_id` repetido e plano de WAN de cada local.

## Fica para depois

Frentes C (dados externos e fine-tuning) e D (latência e jitter): spec, seção 10.

---

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
