# Throughput como eficiência do enlace (frente C1) (design)

**Data:** 2026-10-06
**Base:** `master` (commit `07b265c`), depois da régua única, dos quantis e da CQR.
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

A frente C (spec `2026-10-05-regua-unica-concorrencia-design.md`, seção 10) previa dados externos e fine-tuning. O protótipo desta conversa mostrou que o gargalo é outro: **as árvores não extrapolam**. O hotmilk tem download até 671 Mbps (p90 de 487), e os outros três prédios só chegam a 267; deixando o hotmilk de fora, o modelo não consegue prever acima disso, e o MAE lá é 91 Mbps.

O TR-069 já traz a capacidade nominal do enlace (taxa PHY). Esta entrega (C1) usa essa física como prior: o modelo prevê a **eficiência** (throughput ÷ taxa PHY da direção), que é comparável entre prédios, e a previsão volta para Mbps multiplicando pela taxa. Sem dados externos.

Os dados externos ficam para a C2, só se o critério da seção 8 indicar uma lacuna que eles possam explicar.

## 2. Evidência (protótipo em 2026-10-06, features da `v3-tr069`, régua `2026-10-06.1`)

| Denominador | Download R² / MAE / MAE log | Upload R² / MAE / MAE log |
|---|---|---|
| nenhum (Mbps absolutos, hoje) | 0,42 / 40,7 / 0,713 | 0,62 / 40,2 / 0,831 |
| `router_tx_rate_mbps` | 0,59 / 38,1 / 0,753 | 0,19 / 53,6 / 1,009 |
| `router_rx_rate_mbps` | 0,57 / 38,7 / 0,734 | 0,68 / 36,5 / 0,757 |
| média de `tx` e `rx` | 0,59 / 35,9 / 0,650 | 0,67 / 38,3 / 0,868 |
| máximo de `tx` e `rx` | 0,54 / 38,8 / 0,692 | 0,64 / 40,1 / 0,899 |
| raiz de `expected × tx` | 0,58 / 38,1 / 0,710 | 0,09 / 54,4 / 0,956 |
| `router_expected_throughput_mbps` | 0,54 / 38,4 / 0,677 | 0,04 / 54,9 / 0,906 |

R² do download por prédio (casa-marcelo / coworking / hotmilk / residência): absoluto 0,66 / 0,65 / 0,25 / 0,68; ÷ `tx` 0,36 / 0,66 / 0,50 / 0,69; ÷ `expected` 0,55 / 0,67 / 0,42 / 0,68.

Leituras:

- **A direção decide.** Download vai do roteador ao cliente (taxa de envio, `tx`); upload vai do cliente ao roteador (taxa de recepção, `rx`). Usar o lado errado no upload derruba o R² de 0,68 para 0,19. O efeito é físico, não acaso.
- **O hotmilk melhora** (R² 0,25 → 0,50 no download com `tx`), que era o objetivo.
- **A casa-marcelo piora** com denominadores de taxa PHY (0,66 → 0,36). Fica registrado como custo conhecido.
- A eficiência mediana do download (÷ `expected`) varia por prédio: casa-marcelo 0,62, coworking 0,33, hotmilk 0,31, residência 0,26.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Escopo da frente C | Dividida: C1 (prior físico, agora) e C2 (dados externos, só pelo critério da seção 8) |
| Denominador | Pela física da direção, sem escolha pelos dados: download ÷ `router_tx_rate_mbps`, upload ÷ `router_rx_rate_mbps` |
| Onde mora o denominador | Atributo da versão no registro; outras variantes viram outras versões, na mesma régua |
| Latência e jitter | Sem mudança (continuam quantis com CQR) |
| Rascunho do Assistente | Herda o denominador da versão base |

## 4. Registro e régua

### 4.1 Registro (`src/ml/core/modelos.py`, `modelos.json`)

- Campo opcional `denominador` por versão: `{alvo: coluna}`, com alvos só entre `speedtest_down_mbps` e `speedtest_up_mbps`, e cada coluna um texto não vazio.
- `CAMPOS` passa a incluir `denominador`. `validar_registro` valida o formato. `salvar_versao` aceita `denominador` (opcional), e a coluna precisa existir em `colunas_conhecidas` e ser TR-069 sem vazamento (mesma regra das features).
- Nova função `denominador_de(registro, nome, alvo) -> str | None`.
- Versão sem o campo prevê Mbps absolutos, como hoje.

### 4.2 Régua (`src/ml/core/avaliacao.py`)

- `prever_fora_do_fold(..., denominador=None)`, onde `denominador` é o nome de uma coluna:
  - treina em `y ÷ den` (só nas linhas de treino não limitadas pelo teto, como hoje) e devolve `previsão × den`;
  - `den` vazio ou menor que 1 Mbps: usa a **mediana de `den` nas linhas de treino do fold** (nunca do prédio de teste), e a linha fica com `den_imputado` verdadeiro;
  - a coluna nova `den_imputado` existe sempre (falsa sem denominador);
  - o teto de WAN é aplicado depois da multiplicação.
- `avaliar(..., denominador=None)` e `avaliar_versao(..., denominador=None)` repassam o argumento. `resumir` ganha `den_imputados` (contagem; 0 sem a coluna).
- `delta_mae` e `delta_atende` não mudam: comparam previsões em Mbps.
- `VERSAO_REGUA = '2026-10-06.2'`.

### 4.3 Nova versão `v4-tr069`

Features da `v3-tr069`, `denominador = {"speedtest_down_mbps": "router_tx_rate_mbps", "speedtest_up_mbps": "router_rx_rate_mbps"}`. Salva com a avaliação da régua nova, **não ativa**.

## 5. Integração

1. **`studio/features.comparar`:** recebe também `denominadores` (`{nome da versão: {alvo: coluna}}`) e avalia cada versão com o seu, para o alvo do conjunto.
2. **`api.py`:**
   - `_denominador(registro, nome, alvo)` lê do registro;
   - `modelos_comparar` e `modelos_avaliar` passam o denominador de cada versão; o rascunho usa o da `base` (ou da ativa, sem `base`);
   - `_promocao` e `_prever_pontual` usam o denominador de cada lado (rascunho e base);
   - `avaliacao_completa(ds, ambiente, features, denominador=None)` usa o denominador para download e upload;
   - `NovaVersao` ganha `base: Optional[str] = None`; ao salvar, o denominador da base é copiado para a versão nova e repassado a `avaliacao_completa` e `salvar_versao`.
3. **`assistente.js`:** o `post('api/modelos', ...)` passa a mandar `base: st.base`.
4. **`modelos.js` (versões salvas):** etiqueta "eficiência ÷ tx" ou "÷ rx" ao lado do nome, quando a versão tem denominador para o alvo da tela.
5. **`regression_mlflow.py`:** se a versão tem denominador para o `ALVO`, avalia e treina na eficiência, registra o parâmetro `denominador` e o artefato `eficiencia.json` (`{"alvo", "denominador", "mediana_imputacao", "uso": "mbps = predict(X) * denominador"}`). O modelo final é treinado em `y ÷ den` nas linhas não limitadas pelo teto.

## 6. Erros e avisos

- Denominador que não existe no conjunto: `ValueError` com o nome da coluna (a API devolve 422).
- Denominador para latência ou jitter no registro: recusado por `validar_registro`.
- Imputação não gera aviso por linha; a contagem `den_imputados` vai no resumo e é impressa pelo MLflow.

## 7. Testes e experimento

### 7.1 Testes

- `tests/test_avaliacao.py`:
  - com estimador constante `c`, a previsão é `c × den` em cada linha;
  - o teto de WAN é aplicado depois da multiplicação;
  - `den` vazio vira a mediana do treino do fold (conferido com um prédio de teste cujo `den` difere muito do treino) e a linha fica com `den_imputado`;
  - sem denominador, o resultado é idêntico ao atual;
  - `resumir` traz `den_imputados`.
- `tests/test_modelos_core.py`: `denominador` válido aceito; alvo de latência, coluna vazia e tipo errado recusados; `salvar_versao` recusa coluna com vazamento ou desconhecida; `denominador_de`.
- `tests/test_studio_assistente.py`: a promoção usa o denominador da base no lado da base; salvar com `base` copia o denominador.
- Os testes atuais continuam passando.

### 7.2 Experimento (CHANGELOG)

- `v3-tr069` contra `v4-tr069` em download e upload: R² e MAE pooled com intervalo, por prédio, MAE log, `den_imputados`, "atende em throughput", "atende completo" e os vereditos de promoção.
- A tabela de denominadores da seção 2, registrada como exploração.

## 8. Critério para a C2 (dados externos)

A C2 entra se, com a `v4-tr069`, o MAE de download do hotmilk continuar **maior que o dobro** do MAE de download dos outros três prédios juntos (média do erro absoluto sobre as previsões fora do fold das linhas desses três prédios). É o sinal de que ainda falta conhecimento de faixa alta que dados externos (IEEE 802.11ac, Komondor, prior sintético de MCS) poderiam trazer. O CHANGELOG registra a conta e a conclusão.

**Correção (2026-10-06, depois da implementação):** este critério comparava MAE absoluto e
disparou por escala (os valores do hotmilk são cerca de três vezes maiores). Ele passa a ser
relativo: a C2 entra se o MAE log de download de um prédio for mais que 1,5 vez o dos outros
prédios juntos. Com a `v4-tr069`, a razão é 0,97, e a C2 não entra. Detalhes no CHANGELOG.

## 9. Fica fora

- Escolher o denominador pelos dados (média de `tx` e `rx` dava o melhor MAE no download, mas a escolha olharia os mesmos prédios da régua). Pode virar outra versão depois.
- Seletor de denominador na interface.
- Dados externos (C2).
