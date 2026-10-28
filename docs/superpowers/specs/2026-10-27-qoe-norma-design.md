# Avaliação e treino de QoE com limiares de norma (design)

**Data:** 2026-10-27
**Base:** `master` (commit `0085ddb`), com `modelos.json` e `predios.json` reavaliados (alterações do usuário ainda não commitadas).
**Status:** desenho aprovado em conversa em 2026-10-27. Falta o plano de implementação.

## 1. Contexto

A régua atual prevê Mbps e milissegundos e compara a previsão com os limiares de `core/aplicacoes.json`. O "atende completo" ficou parado em 0,63 a 0,66 da v1 à v5, enquanto MAE e R² mudavam. A diferença de MAE entre versões vem de linhas AX entre 500 e 800 Mbps (villa e hotmilk), longe do maior limiar (25 Mbps). Este trabalho acrescenta um caminho de avaliação e de treino que mede a decisão de QoE direto, com limiares de fonte publicada. Nada do caminho atual é removido.

## 2. Evidência (medida em 2026-10-27, conjunto padrão)

Conjunto: 6 datasets (`20260827`, `20260917-fix`, `20260921-distcalc`, `20260925`, `20260928`, `villa-20261025.csv`), 1575 linhas com os quatro alvos, 5 prédios, 22 posições, 81 grupos posição x banda x celular. LOGO por prédio; intervalos de 90% por `avaliacao.reamostras`. Scripts no scratchpad da sessão, fora do repositório.

1. **A régua perde para a banda sozinha.** Perfil atual, acurácia balanceada pooled média das 4 aplicações: régua v5 (regressão + limiar, p90 de latência e jitter) 0,649; Random Forest classificador só com `radio` 0,714 (+0,065, IC +0,034 a +0,095); classificador direto com as features da v5 0,764 (+0,115, IC +0,078 a +0,135). Tirar `n_clients` e `concorrentes_mesmo_radio` muda -0,001.
2. **Pooled engana.** Com o perfil de norma (seção 3.1) e média por prédio (só prédios com as duas classes): piso "só `radio`" 0,648, RF 0,692. A vantagem das features sobre a banda é de 0,044 (IC 0,014 a 0,067), não os 0,06 do pooled.
3. **Villa não tem falha.** Nas 275 linhas, nenhuma falha em Navegação, Chamada e Streaming 4K pelo perfil atual; no jogo, 7 linhas por jitter, todas em cômodos de sinal bom (escritório a -46 dBm). Pior download medido: 136 Mbps.
4. **`router_signal_dbm` do villa está fora de escala.** Em 5 GHz, sinal do roteador menos RSSI do celular (mediana) é +6 a +11 dB nos outros prédios e -15 dB no villa (correlação 0,91, um BSSID só, canal 48). A cozinha lê -85 a -90 dBm no roteador e -66 a -70 no celular, SNR 3 a 7, com 230 Mbps. `router_snr` herda o erro. A taxa PHY (`router_tx_rate_mbps` 263 a 288) é coerente com o throughput.
5. **Modelos testados** (perfil de norma, média por prédio, contra RF; cerca de 16 variantes nos mesmos dados):

| Modelo | Média por prédio | Contra RF (IC 90%) | Alarme falso villa (Navegação / Jogo) |
|---|---|---|---|
| RF 300 árvores, folha 5, balanceado | 0,692 | | 0,7% / 0,7% |
| XGBoost profundidade 6 padrão | 0,657 | -0,035 [-0,054, +0,002] | |
| XGBoost monotônico em tudo, prof. 3, 600 árvores | 0,714 | +0,021 [+0,002, +0,061] | 15,6% / 8,4% |
| XGBoost monotônico em tudo, prof. 6, 600 árvores | 0,710 | +0,018 [-0,001, +0,056] | |
| **XGBoost monotônico só em taxa PHY e contenção, prof. 3, 600 árvores** | **0,697** | **+0,004 [-0,013, +0,013]** | **0,0% / 0,7%** |
| Regressão logística | 0,672 | -0,021 [-0,035, +0,015] | |

   A restrição monotônica no sinal faz o modelo chamar a cozinha do villa de "não atende" em 53% das linhas (item 4). A média por prédio não vê esse erro, porque o villa tem uma classe só em Navegação; a trava de alarme falso (seção 3.5) vê.

## 3. Desenho

### 3.1 Perfil de norma

Arquivo novo `src/ml/core/aplicacoes_norma.json`. `aplicacoes.json` não muda: `classification_benchmark.py` o lê por `aplicacoes.carregar()` e o validador exige a chave única `aplicacoes`.

Formato:

```json
{
  "perfil": "norma",
  "aplicacoes": {
    "Chamada de vídeo": {
      "dn":  {"valor": 3.0, "fonte": "Zoom, requisitos de sistema, 1080p", "url": "https://developers.zoom.us/docs/video-sdk/system-requirements/"},
      "up":  {"valor": 3.8, "fonte": "Zoom, requisitos de sistema, 1080p", "url": "..."},
      "lat": {"valor": 200, "fonte": "ITU-T Y.1541 classe 0", "url": "https://www.rfc-editor.org/rfc/rfc5976.html", "nota": "100 ms de ida x 2: latency_ms é ping de ida e volta"},
      "jit": {"valor": 50,  "fonte": "ITU-T Y.1541 classe 0", "url": "...", "nota": "a Y.1541 define variação como quantil 0,999 menos o mínimo; o jitter do speedtest é outra conta"}
    }
  }
}
```

Regra: requisito publicado para a qualidade que o nome da aplicação indica. Onde não há norma, vale o valor do perfil atual com `"fonte": "sem norma; valor do perfil atual"`.

| Aplicação | dn | up | lat | jit |
|---|---|---|---|---|
| Navegação | 2 (sem norma) | 0,5 (sem norma) | 800 (Y.1541 classe 3, 400 x 2) | 100 (sem norma) |
| Chamada de vídeo | 3,0 (Zoom 1080p) | 3,8 (Zoom 1080p) | 200 (Y.1541 classe 0, 100 x 2) | 50 (Y.1541) |
| Streaming 4K | 15 (Netflix 4K) | 0 (sem norma) | 500 (sem norma) | 100 (sem norma) |
| Jogo em nuvem | 15 (NVIDIA GeForce NOW, mínimo 720p60) | 1 (sem norma) | 80 (NVIDIA, exigido; já é ida e volta) | 10 (sem norma) |

`core/aplicacoes.py`:

- `carregar(path=APLICACOES_PATH)` continua igual (mesma assinatura, mesmo retorno).
- `carregar_perfil(perfil: str) -> dict`: `'atual'` devolve `carregar()`; `'norma'` lê o arquivo novo, valida e devolve `{nome: {'dn': v, 'up': v, 'lat': v, 'jit': v}}` no mesmo formato.
- `fontes(perfil: str) -> dict`: `{nome: {chave: {'fonte', 'url', 'nota'}}}`; vazio para `'atual'`.
- `PERFIS = ('atual', 'norma')`; `versao(perfil)` entra na chave de cache do Studio.
- Validação do arquivo de norma: mesmas chaves e números não negativos do validador atual, mais `fonte` obrigatória em todo limiar.

### 3.2 Rótulo e treino

Módulo novo `src/ml/core/qoe.py`.

- `rotulos(df, limiares) -> dict[str, np.ndarray]`: por aplicação, `atende` = download >= dn, upload >= up, latência <= lat e jitter <= jit. Só linhas com os quatro alvos.
- `conjunto_qoe(ds, ambiente)`: as linhas comuns aos quatro `carga.carregar` (junção por `_linha`, como `avaliacao._juntar`), com os descartes de cada alvo. Linhas `_limitado_wan` ficam: no teto de WAN o throughput medido é real para a decisão.
- Features: as da versão, sem as de vazamento (`vazadas_do_conjunto`), via `features.matriz`. Sem denominador.
- `MONOTONIA`: tabela fixa no código, decidida pela física e pela evidência 2.4:
  - +1: `router_tx_rate_mbps`, `router_rx_rate_mbps`, `router_expected_throughput_mbps`.
  - -1: `n_clients`, `concorrentes_mesmo_radio`.
  - 0: todo o resto, inclusive sinal, SNR, ruído, colunas one-hot e features desconhecidas.
  - `restricoes(colunas_da_matriz) -> tuple` monta o vetor na ordem das colunas de `matriz`.
- Modelos fixos (`modelo_qoe()`, `modelo_referencia()`, `modelo_piso()`):
  - **Principal:** `XGBClassifier(n_estimators=600, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, tree_method='hist', random_state=42, monotone_constraints=restricoes(...))`, com `sample_weight` balanceado (`compute_sample_weight('balanced', y)`). Valores ausentes ficam para o XGBoost (sem imputação).
  - **Referência:** `RandomForestClassifier(300, min_samples_leaf=5, class_weight='balanced', random_state=42)` com imputação pela mediana.
  - **Piso:** o RF de referência só com `radio`.
- `prever_qoe_fora_do_fold(df, colunas, y, estimador)`: LOGO por `_site` (`splits.outer_logo_folds`). Fold cujo treino tem uma classe só prevê essa classe para o prédio de teste e marca `fold_uma_classe`. Reaproveita a forma de `classificacao.prever_classe_fora_do_fold` (`_linha`, `y`, `yhat`, `_site`, `_pos`).

### 3.3 Medida

`qoe.resumir(prev_por_app) -> dict`, igual para os três modelos:

- **Por prédio e aplicação:** com as duas classes no real, acurácia balanceada; com uma classe só, `alarme_falso` (fração prevista como "não atende" quando tudo atende) ou `perda` (fração prevista "atende" quando nada atende).
- **Nota principal:** média, entre prédios com pelo menos uma aplicação de duas classes, da média das aplicações de duas classes daquele prédio. Cada prédio pesa igual.
- `pooled`: a acurácia balanceada de hoje, só como referência.
- `intervalo`: percentis 5 e 95 da nota principal em `avaliacao.reamostras(_pos, _site)`.
- `n_predios`, `n_posicoes`, e a lista de prédios fora da nota por terem uma classe só.

### 3.4 Registro e avaliação

- `modelos.CAMPOS` ganha `perfil_qoe` (`'atual'` ou `'norma'`). Versões sem o campo são lidas como `'atual'`; v1 a v5 não são editadas.
- `salvar_versao(..., perfil_qoe='norma')`: versões novas recebem `norma` por padrão.
- `avaliacao_completa` ganha a etapa "QoE" (`N_ETAPAS` passa a 6) e grava `avaliacao['qoe']`:

```text
qoe = {perfil, versao_qoe, modelo: resumir(XGBoost), referencia: resumir(RF), piso: resumir(radio),
       supera_piso: bool, restricoes: {coluna: sinal}, fontes: aplicacoes.fontes(perfil)}
```

- `versao_qoe = '2026-10-27.1'` em `qoe.py`, mudando a cada alteração de modelo, monotonia ou medida, como `VERSAO_REGUA`.
- **Reavaliar** recalcula `qoe` de qualquer versão no perfil dela. A nota do `historico` passa a dizer também "QoE x -> y".

### 3.5 Veredito de QoE

`qoe.veredito(nova, base, amostras)` compara duas versões nas mesmas linhas e reamostras:

- `delta` = nota principal da nova menos a da base, com intervalo.
- **Pior:** intervalo todo abaixo de 0, ou, em algum prédio de uma classe só, `alarme_falso` da nova acima de 0,05 e mais de 0,02 acima do da base.
- **Melhor:** intervalo todo acima de 0 e a trava acima não dispara.
- **Empate:** o resto.
- `predios_contra`: prédios em que a nova cai mais de 0,02.
- Aviso à parte, não muda o veredito: `supera_piso` falso ("não supera a banda sozinha").

A comparação recalcula as duas versões com o perfil pedido (os mesmos rótulos e as mesmas linhas), então o perfil salvo da base não impede o veredito.

### 3.6 Studio

- Endpoint novo `GET /api/modelos/avaliar_qoe?features=&ds=&ambiente=&base=&contra=&perfil=`, devolvendo `qoe` do rascunho e `promocao_qoe` contra `contra`. É separado de `GET /api/modelos/avaliar`, que é por alvo: o QoE junta os quatro alvos e não muda quando se troca o alvo na tela.
- `avaliacao_completa` usa os limiares do perfil da versão em todas as métricas de "atende" (throughput, ajustado, completo) e grava `perfil` na avaliação.
- Área Modelo (`modelo.js`):
  - Cartão: "QoE (norma) 0,70" como número principal, com o "atende completo" ao lado em texto menor. Selo do perfil; selo "abaixo do piso" quando for o caso.
  - Rascunho: seletor de perfil (norma, atual); bloco de veredito de QoE acima do veredito de promoção atual, com as notas dos três modelos, o alarme falso por prédio de uma classe só e a tabela de limiares com fonte (link) e nota.
  - Salvar e ativar: a ativação pelo Studio passa a seguir o veredito de QoE, com a mesma forma da trava de hoje (`L.podeAtivar`): libera só com QoE "melhor", sem prédio contra e com cobertura 100% ou proxy; nos outros casos, salvar e usar o menu do cartão (que pede confirmação). O veredito de promoção atual continua exibido e não trava mais.
  - Progresso do job: "Avaliando QoE (6 de 6)".
- Regras puras novas em `static/logica.js` (escolha do número do cartão, texto do veredito de QoE, bloqueio de ativação), testadas em `tests/js/logica.test.js`.

### 3.7 Produção

Script novo `src/ml/qoe_mlflow.py` (`MODELO=<versão>`), no padrão de `regression_mlflow.py`:

- Treina o XGBoost principal com todos os prédios, um por aplicação, com o perfil da versão.
- Registra no MLflow: os 4 modelos; `contrato.json` (`producao.contrato` com colunas da matriz e categorias); `qoe.json` (perfil, limiares, fontes, restrições, `versao_qoe`); `cobertura_tr069.json`; parâmetros `perfil_qoe`, `versao_qoe`, `cobertura_tr069`; métricas `qoe_por_predio`, `qoe_pooled`, `qoe_piso`.
- `regression_mlflow.py`: `fatores_producao` passa a receber os limiares do perfil da versão. Para v1 a v5 (perfil atual), o resultado é o de hoje.

### 3.8 Fora deste trabalho

- `regression_benchmark.py` e `classification_benchmark.py` não mudam (acordo com o Fabiano, 2026-10-22). Os dois leem o registro por `core_modelos.carregar()`, que valida contra `CAMPOS` em `core/modelos.py`; incluir `perfil_qoe` em `CAMPOS` basta para eles aceitarem as versões novas. Avisar o Fabiano na mensagem de commit, porque `core/` e `modelos.json` são compartilhados.
- Calibração das probabilidades (Brier pior que a taxa base em Navegação): só se um dia a saída for risco em vez de decisão.
- Correção do sinal do villa (item 2.4): é dado, não régua. Pergunta ao Villa: modelo e firmware do roteador e de onde o coletor lê `router_signal_dbm`.
- Busca de hiperparâmetros: o modelo é fixo. Novo teste de configuração só quando entrar um 6º prédio com falhas, contra o RF de referência, sempre com a trava de alarme falso.

## 4. Testes

- `test_aplicacoes.py`: `carregar()` sem argumento devolve exatamente o de hoje; `carregar_perfil('norma')` passa no validador, tem as 4 aplicações e as 4 chaves; todo limiar de norma tem `fonte`; arquivo de norma sem `fonte` é recusado.
- `test_qoe.py` (novo):
  - `rotulos` com os 4 critérios (cada um derruba sozinho).
  - `restricoes`: vetor certo para colunas conhecidas, one-hot e desconhecidas; sinal e SNR saem 0.
  - `prever_qoe_fora_do_fold`: nenhum prédio de teste no treino do próprio fold; fold de treino com uma classe só.
  - `resumir`: prédio de uma classe só entra como alarme falso e fica fora da nota; nota é média por prédio (dois prédios de tamanhos diferentes pesam igual).
  - `veredito`: um caso para cada ramo (pior por intervalo, pior pela trava, melhor, empate) e perfis diferentes.
  - Monotonia respeitada: aumentar `router_tx_rate_mbps` numa linha nunca reduz a probabilidade prevista.
- `test_modelos_core.py`: `perfil_qoe` aceito e validado; versão sem o campo lida como `atual`.
- `test_studio_salvar.py` / `test_studio_reavaliar.py`: `avaliacao['qoe']` presente; 6 etapas no progresso; ativação recusada com veredito QoE `pior`.
- `tests/js/logica.test.js`: número do cartão, texto do veredito, bloqueio de ativação.
- Conferência no navegador: `tests/studio_screenshots.sh` nas áreas Modelo claro e escuro, sem erro no console.
- Medida de aceite: reavaliar v1 a v5 e uma versão nova com as features da v5 no perfil de norma; a nota do XGBoost da v5 em norma deve ficar perto de 0,697 e o alarme falso do villa abaixo de 0,05 (seção 2.5). Diferença grande indica que a implementação não reproduz o experimento.

## 5. Ressalvas

- Com 5 prédios os intervalos são largos; o XGBoost escolhido empata com o RF. A escolha vale pelo comportamento previsível (monotonia nas taxas, ausentes sem imputação), não pela nota.
- Cerca de 16 variantes foram testadas nos mesmos dados. Esta configuração fica fixada agora, antes do próximo prédio.
- Latência e jitter vêm do speedtest (ida e volta, jitter próprio), não da medida que a norma descreve; cada limiar leva a nota.
- `router_signal_dbm` não é comparável entre roteadores (item 2.4). Por isso o sinal fica sem restrição monotônica.
