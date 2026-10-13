# Cobertura TR-069 por coluna e por versão, e a nova `v5` implantável

**Data:** 2026-10-09
**Estado:** desenho para revisão do usuário

## 1. Objetivo

O QoE Studio serve para **encontrar o melhor treinamento possível** com tudo o que a coleta mede e, a partir desse modelo, **descobrir como obter cada métrica em produção pelo TR-069**: derivar do que o TR-181 já expõe ou pedir coleta nova.

Hoje o Studio mistura duas coisas sob a classe `tr069`: "o roteador mediu" e "o ACS consegue ler em produção". A revisão de 2026-10-09 mostrou que elas não são a mesma:

- O coletor (`collector-telemetry-wifi-main`) não usa TR-069. Os campos `router_*` vêm de `iw dev <if> station dump`, `iwinfo <if> assoclist` e `iw dev <if> scan`, por SSH num roteador OpenWrt.
- `n_clients` e `combo` vêm do tópico MQTT do orquestrador: são desenho do teste.
- `client_mode`, `channel_width` e `radio` chegam no payload do celular.
- `router_expected_throughput_mbps` é a estimativa do rate control do mac80211 e não tem parâmetro padrão no TR-181.

Esta spec faz três coisas:

1. Grava, para cada coluna, **como a produção a obtém pelo TR-181** (padrão, derivável, proxy, extensão de fabricante, ausente ou desconhecido) e com que caminho.
2. Mostra, para **toda versão** (`v1` em diante), um **nível de cobertura TR-069**, e lista as lacunas de cada uma. Nenhuma versão é apresentada como 100% TR-069 sem ser.
3. Reorganiza o registro, como pedido: a `v4-tr069` atual sai, a `v5-tr069` atual passa a ser a `v4`, e entra uma **nova `v5`**, a melhor versão hoje só com parâmetros TR-181 padrão e um proxy de contenção declarado.

## 2. O que as medidas mostraram (régua `2026-10-08.1`)

Medidas feitas em 2026-10-09 com o conjunto canônico, para fundamentar a nova `v5`.

**Remoção de uma feature por vez da `v5-tr069` atual (download, promoção contra ela mesma):**

| Removida | Veredito | Δ MAE (IC 90%) | Δ "atende" (IC 90%) |
|---|---|---|---|
| `router_expected_throughput_mbps` | pior | −0,22 (−0,79 a 0,40) | −0,031 (−0,042 a −0,016) |
| `eficiencia_espectral_tx` | empate | +0,57 (−0,93 a 2,00) | +0,000 (−0,004 a 0,005) |
| `perda_percurso_db` | melhor | −0,14 (−0,43 a 0,09) | +0,008 (0,002 a 0,013) |

**Conjuntos candidatos contra a `v5-tr069` atual:**

| Conjunto | Download | Upload | Latência | Jitter |
|---|---|---|---|---|
| Estrito, sem contenção (7 features) | pior: "atende" −0,031 | pior: MAE +8,6 (5,0 a 12,5), nos 4 prédios | pior: pinball p90 +0,76 | empate |
| **Padrão + proxy de contenção (9 features, a nova `v5`)** | pior: "atende" −0,018 (−0,028 a −0,010); MAE +0,41 (−1,01 a 1,87) | pior: "atende" −0,018; MAE +0,36 (−0,11 a 0,82) | pior: pinball p90 +0,28 (0,08 a 0,51) | empate |

No conjunto estrito, o R² pooled do download sobe de 0,586 para 0,630, mas a alta vem só do hotmilk. Os outros três prédios pioram. O R² pooled em Mbps engana com 4 prédios; a promoção decide.

`router_expected_throughput_mbps` é quase todo reconstruível pelas colunas padrão: R² fora do prédio de 0,79 (casa-marcelo) a 0,99 (residência). Em resumo, é taxa PHY × fator da banda (mediana de expected ÷ taxa: 0,63 em 2,4 GHz e 0,85 em 5 GHz). O resíduo, que é a estimativa de sucesso do rate control, ainda informa o "atende".

**Leitura:** a nova `v5` custa cerca de 0,02 de acurácia balanceada no "atende" e 0,28 de pinball na latência, frente à `v4` (antiga `v5`). É o preço de não depender de `expected_throughput`. A nova `v5` não é promovida a ativa por esta spec.

## 3. Proveniência TR-181 por coluna

### 3.1 Formato

Cada regra de `src/ml/core/column_provenance.json` (em `colunas` e em `prefixos`) ganha um campo opcional `tr181`:

```json
"router_tx_rate_mbps": {
  "classe": "tr069",
  "tr181": {
    "status": "padrao",
    "caminho": "Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.LastDataDownlinkRate",
    "nota": "kbps no TR-181; o coletor grava Mbps"
  }
}
```

`status` é um destes valores, do mais implantável para o menos:

| status | Quer dizer |
|---|---|
| `padrao` | parâmetro do data model TR-181 padrão |
| `derivavel` | conta feita só com parâmetros `padrao` (ex.: SNR = sinal − ruído) |
| `proxy` | um parâmetro padrão existe, mas mede uma coisa parecida, não a mesma (a `nota` diz a diferença) |
| `extensao` | o roteador mede, mas o TR-181 padrão não expõe; só por extensão do fabricante (`X_...`) |
| `ausente` | não há caminho pelo ACS (lado do cliente, sniffer, geometria, desenho do teste) |
| `desconhecido` | ninguém classificou ainda |

`caminho` e `nota` são texto de até 200 caracteres. `caminho` é obrigatório para `padrao` e `proxy`. Coluna sem `tr181`, direto ou por prefixo, conta como `desconhecido`: **nada é adivinhado**, como já é a regra de `classificar`.

`classe` continua dizendo **onde a coleta mediu a coluna**. A chave `tr069` fica por compatibilidade (versões salvas, testes e `gravar_estado_contadores` dependem dela), mas a interface passa a chamá-la de "Roteador". Isto substitui a classe `extensao` da seção 1 do brainstorming: a pergunta "produção consegue?" fica só em `tr181`.

### 3.2 Tabela inicial

Os caminhos foram escritos a partir do data model TR-181 e **precisam ser confirmados com o ACS de produção** antes de qualquer versão ir para produção. Cada um entra com `"nota": "... (a confirmar com o ACS)"`.

| Coluna | classe | status | caminho / nota |
|---|---|---|---|
| `router_tx_rate_mbps` | tr069 | padrao | `AssociatedDevice.{i}.LastDataDownlinkRate` (kbps) |
| `router_rx_rate_mbps` | tr069 | padrao | `AssociatedDevice.{i}.LastDataUplinkRate` (kbps) |
| `router_signal_dbm` | tr069 | padrao | `AssociatedDevice.{i}.SignalStrength` |
| `router_noise` | tr069 | padrao | `Radio.{i}.Stats.Noise`; no coletor é por estação (iwinfo), no TR-181 é do rádio |
| `router_snr` | tr069 | derivavel | `SignalStrength − Radio.{i}.Stats.Noise` |
| `radio` | tr069 | padrao | `Radio.{i}.OperatingFrequencyBand`; valores `2.4GHz`/`5GHz` (o treino viu `2.4ghz`/`5ghz`; o contrato casa sem maiúsculas) |
| `channel_width` | tr069 | padrao | `Radio.{i}.CurrentOperatingChannelBandwidth`; no coletor vem do celular |
| `client_mode` | tr069 | padrao | `AssociatedDevice.{i}.OperatingStandard`; vocabulário `n`/`ac`/`ax`, o treino viu `WiFi 5 (11ac)`: precisa de tabela de valores (seção 8) |
| `router_opportunity_medium_use` | tr069 | derivavel | contagem de `NeighboringWiFiDiagnostic.Result.{i}` no mesmo canal do rádio |
| `router_tx_bytes`, `router_rx_bytes`, `router_tx_packets`, `router_rx_packets` | tr069 (vazamento) | padrao | `AssociatedDevice.{i}.Stats.BytesSent` / `BytesReceived` / `PacketsSent` / `PacketsReceived` |
| `router_tx_retries`, `router_tx_failed` | tr069 (vazamento) | padrao | `AssociatedDevice.{i}.Stats.RetransCount` / `FailedRetransCount` |
| `router_rx_drop_misc` | tr069 (vazamento) | extensao | sem equivalente direto |
| `router_tx_duration_us`, `router_rx_duration_us` | tr069 (vazamento) | extensao | airtime por estação não é padrão |
| `router_expected_throughput_mbps` | tr069 | extensao | estimativa do rate control (mac80211) |
| `router_signal_avg_dbm` | tr069 | extensao | o TR-181 não tem média; o ACS pode amostrar `SignalStrength` |
| `router_NSS_TX_Station`, `router_NSS_RX_Station`, `router_bandwith_TX_station`, `router_bandwith_RX_station` | tr069 | extensao | NSS e largura por estação (a confirmar se a versão do data model do CPE expõe) |
| `router_power_dbm` | tr069 | extensao | `Radio.{i}.TransmitPower` é percentual, não dBm |
| `router_connected_time_sec` | tr069 | extensao | a confirmar se o CPE expõe tempo de associação |
| `n_clients` | **ambiente** | proxy | `AccessPoint.{i}.AssociatedDeviceNumberOfEntries`, somado nos APs; no teste todos os clientes saturavam o enlace ao mesmo tempo, em produção muitos associados ficam ociosos |
| `concorrentes_mesmo_radio` | **ambiente** | proxy | `AccessPoint.{i}.AssociatedDeviceNumberOfEntries` do AP da estação (mesmo bssid); mesma ressalva |
| `combo`, `session_id`, `run_id` | identificador | ausente | desenho do teste |
| prefixo `router_` | tr069 | desconhecido | coluna nova do roteador fica `desconhecido` até alguém classificar |
| colunas `cliente`, `sniffer`, `geometria`, `ambiente` restantes | (como hoje) | ausente | lado do cliente, sniffer, planta ou ambiente |

### 3.3 Derivadas

O status de uma derivada vem dos insumos: se todos são `padrao` ou `derivavel`, ela é `derivavel`; senão, recebe o pior status entre os insumos, na ordem `proxy` < `extensao` < `ausente` < `desconhecido`. Por exemplo: `eficiencia_espectral_tx` (usa NSS) e `perda_percurso_db` (usa potência) saem `extensao`; `assimetria_phy` (taxa ÷ taxa) sai `derivavel`.

## 4. Cobertura de uma versão

Nova função em `src/ml/core/features.py`:

```python
def cobertura_tr069(features, tabela) -> dict:
  """{'nivel': '100%' | 'proxy' | 'parcial', 'por_feature': {f: status}, 'lacunas': [{feature, status, caminho, nota}]}"""
```

- `100%`: toda feature é `padrao` ou `derivavel`.
- `proxy`: o pior status é `proxy`.
- `parcial`: alguma feature é `extensao`, `ausente` ou `desconhecido`.
- `lacunas`: as features que não são `padrao` nem `derivavel`, com o que a tabela diz delas. É a lista de trabalho do objetivo da seção 1.

Onde aparece:

- **Studio, views Modelos e Assistente:** cada versão e o rascunho mostram uma etiqueta com o nível ("100% TR-069", "TR-069 com proxy" ou "TR-069 parcial: n de m") e, ao abrir, as lacunas. Isso vale para `v1` a `v5` e para qualquer versão futura. A etiqueta atual "fora do TR-069" (`fora_do_tr069`) é substituída pela cobertura.
- **Studio, view Features:** cada coluna mostra status e caminho TR-181. A tela de classificação de coluna ganha os campos status, caminho e nota, gravados em `column_provenance.json` pela rota que já existe.
- **Registro:** `salvar_versao` grava a cobertura calculada na hora (`cobertura`), para que a versão diga com que tabela foi avaliada. A cobertura mostrada no Studio é sempre recalculada com a tabela atual; se divergir da gravada, a etiqueta avisa.
- **MLflow:** `regression_mlflow.py` registra o parâmetro `cobertura_tr069` (o nível) e grava `cobertura_tr069.json` (as lacunas) junto do `contrato.json`.

## 5. O Studio busca o melhor treino possível

Hoje o Assistente só libera colunas de classe `tr069`, e o desenho automático e os paralelos só consideram `tr069` como candidatas. Isso contradiz o objetivo da seção 1.

- **Assistente:** libera qualquer coluna elegível (sem vazamento, não constante, cobertura de dados ≥ 0,7, não identificador nem alvo, não categórica com muitos valores, não duplicada). Cada uma vem com o status TR-181. O motivo de bloqueio "fora do TR-069 (classe)" deixa de existir.
- **Desenho automático (`selecao.desenhar`):** ganha o parâmetro `escopo`: `implantavel` (só `padrao`, `derivavel` e `proxy`) ou `tudo` (todas as elegíveis). O padrão é `tudo`. O resultado traz a cobertura das features escolhidas.
- **Paralelos:** "colunas de laboratório" passam a ser as elegíveis com status fora de `padrao`/`derivavel`. A pergunta "reconstrói?" passa a valer para `expected_throughput` também, que é exatamente o caso a investigar.
- **Teste de aceite de derivada:** o critério "todos os insumos são TR-069" passa a ser "a derivada é `derivavel`" (todos os insumos `padrao` ou `derivavel`).
- **Trava de ativação do Assistente:** além da régua dizer "melhor" sem prédio contra (Tasks 1 e 8 do plano de 2026-10-09), o rascunho precisa de cobertura `100%` ou `proxy`. Rascunho `parcial` pode ser salvo, não ativado pelo Assistente; o modo Avançado continua livre.
- **Denominador de versão:** `salvar_versao` passa a exigir denominador com status `padrao` ou `derivavel` (hoje exige classe `tr069`). `router_tx_rate_mbps` e `router_rx_rate_mbps` são `padrao`.

## 6. Registro de versões

Mudança pedida pelo usuário em 2026-10-09. É uma exceção à regra "versão salva é imutável" e fica registrada assim no CHANGELOG.

| Antes | Depois |
|---|---|
| `v1`, `v2-tr069`, `v3-tr069` | iguais (ativa continua `v1`) |
| `v4-tr069` (eficiência nas duas bandas) | **removida** |
| `v5-tr069` (eficiência só em 5 GHz) | **`v4`**, com features, denominador e avaliação iguais |
| — | **nova `v5`** |

**Nomes.** As versões renomeadas e as novas não levam o sufixo `-tr069`: o nome não deve afirmar cobertura, quem diz isso é a etiqueta da seção 4. `v2-tr069` e `v3-tr069` mantêm o nome, porque aparecem no CHANGELOG e em runs do MLflow, e passam a mostrar a etiqueta "TR-069 parcial".

**Rastro.** O registro aceita um campo novo, `historico` (lista de textos), com entradas como `"2026-10-09: era v5-tr069"` na nova `v4`. Runs do MLflow anteriores a 2026-10-09 com `modelo_versao=v4-tr069` ou `v5-tr069` se referem aos nomes antigos; a entrada do CHANGELOG traz a tabela de correspondência.

**Nova `v5`:**
- Features: `client_mode`, `radio`, `router_rx_rate_mbps`, `router_snr`, `router_signal_dbm`, `router_tx_rate_mbps`, `channel_width`, `n_clients`, `concorrentes_mesmo_radio`.
- Denominador igual ao da `v4`: download ÷ `router_tx_rate_mbps` e upload ÷ `router_rx_rate_mbps`, só em 5 GHz.
- Cobertura esperada: "TR-069 com proxy" (lacunas: `n_clients` e `concorrentes_mesmo_radio`).
- Avaliação completa gravada pela régua (`avaliacao_completa`), como as outras.
- Descrição: "Melhor versão só com TR-181 padrão mais o proxy de contenção. Custa ~0,02 de 'atende' frente à v4 por não usar expected_throughput (extensão)."
- Não é ativada.

**Cobertura esperada das demais**, pela tabela da seção 3.2: `v1` parcial (`expected_throughput`, `signal_avg`, contadores de airtime e outros); `v2-tr069` parcial (`expected_throughput`, `eficiencia_espectral_tx`, `perda_percurso_db`); `v3-tr069` e `v4` parcial (as mesmas, mais o proxy de contenção).

## 7. Testes

- `validar_regra` aceita `tr181` com status válido e recusa status desconhecido, `caminho` ausente em `padrao`/`proxy`, e texto acima de 200 caracteres.
- Toda coluna `router_*` presente nos datasets canônicos tem `tr181` explícito (coluna, não prefixo). O teste lê `data/` como os testes de carga já fazem.
- `cobertura_tr069`: o nível sai `100%`, `proxy` e `parcial` nos três casos; derivadas herdam o status como na seção 3.3.
- Registro: não existe mais `v4-tr069` nem `v5-tr069`; `v4` tem as features e o denominador da antiga `v5-tr069` e `historico`; a nova `v5` tem as 9 features e a cobertura `proxy`.
- Studio: o Assistente libera `expected_throughput` com status `extensao`; `selecao.desenhar(escopo='implantavel')` não escolhe coluna `extensao`; o teste de aceite recusa derivada com insumo `extensao`.
- `salvar_versao` recusa denominador com status `extensao`.
- Assistente: a trava de ativação exige cobertura `100%` ou `proxy` (verificação no navegador, como na Task 13 do plano anterior).
- Suíte completa verde.

## 8. Fora do escopo e próximos passos

- **Confirmar os caminhos com o ACS.** Todos os caminhos da seção 3.2 estão "a confirmar". Sem isso, "100% TR-069" quer dizer "100% dentro do que esta tabela afirma".
- **Tabela de valores do `client_mode`.** O TR-181 usa `n`, `ac`, `ax`; o treino viu `WiFi 4 (11n)` etc. A produção precisa de um mapa antes de usar qualquer versão com `client_mode`. Fica para o plano de produção.
- **Coleta nova (pedido ao coletor, não implementado aqui):**
  - gravar a contagem de estações do `iw station dump` (todas e as ativas) por rádio, para validar o proxy de `n_clients`;
  - gravar uma leitura anterior ao teste (`router_pre_*`), porque hoje sinal e taxas são lidos depois do speedtest, e a produção lê o enlace ocioso.
- **Derivar `expected_throughput` de colunas padrão.** É a lacuna que mais pesa (−0,031 de "atende"). Os paralelos passam a medir isso (seção 5). Fazer a derivada é o próximo ciclo.
- **Promover a nova `v5`** e qualquer mudança da ativa.
- **Caminho B** (alvo em log, modelo por banda, ensemble).

## 9. Riscos

- **A tabela pode estar errada.** Mitigação: tudo marcado "a confirmar"; status `desconhecido` como padrão para coluna nova; a etiqueta mostra a cobertura recalculada.
- **Renomear versões confunde o histórico.** Mitigação: campo `historico`, tabela de correspondência no CHANGELOG, e nomes novos sem o sufixo, para não colidir com os antigos no MLflow.
- **Abrir o Assistente para colunas não implantáveis pode levar a promover um modelo que não roda em produção.** Mitigação: a etiqueta de cobertura aparece no cartão de promoção e na publicação; a trava de ativação do Assistente exige nível `100%` ou `proxy`. O modo Avançado continua livre.
