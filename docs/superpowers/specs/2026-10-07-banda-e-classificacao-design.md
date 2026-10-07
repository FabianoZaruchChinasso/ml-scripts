# Eficiência só em 5 GHz e scripts de classificação na régua (design)

**Data:** 2026-10-07
**Base:** `master` (commit `977a924`), depois da frente C1 (`docs/superpowers/specs/2026-10-06-eficiencia-throughput-design.md`).
**Status:** desenho aprovado em conversa (o usuário pediu seguir as recomendações). Falta o plano de implementação.

## 1. Objetivo

Duas partes independentes, na mesma entrega:

1. **Denominador por banda.** A `v4-tr069` (eficiência em todas as linhas) melhorou R² e MAE, mas teve veredito "pior" porque o "atende" caiu. A causa é a banda de 2,4 GHz, em que a taxa PHY não indica a capacidade (seção 2). Esta parte faz o denominador valer só numa banda e mede a nova `v5-tr069`.
2. **Scripts de classificação na régua.** `classification_benchmark.py` e `compare_protocols.py` ainda usam o carregador antigo, agrupam por posição e usam features que vazam. Esta parte os coloca na carga e na régua únicas, e reaponta o benchmark de classificação para o "atende" por aplicação.

A frente C2 (dados externos e fine-tuning) foi **descartada** pelo usuário em 2026-10-07.

## 2. Evidência (medido em 2026-10-07, régua `2026-10-06.2`)

**Eficiência mediana (download ÷ `router_tx_rate_mbps`) por prédio e banda:**

| | casa-marcelo | coworking | hotmilk | residência |
|---|---|---|---|---|
| 2,4 GHz | 0,38 | 0,10 | 0,13 | 0,08 |
| 5 GHz | 0,68 | 0,48 | 0,34 | 0,33 |

Em 2,4 GHz, a eficiência acompanha o aparelho cliente: ideapad3 0,21 e Samsung SM-A566E 0,29 (casa-marcelo e hotmilk), contra moto g9 play 0,09, moto g9 plus 0,08 e netprobe 0,10 (residência e coworking). Cliente e prédio estão confundidos na coleta.

**Onde a `v4` e a `v3` decidem "atende" de forma diferente:** 63 de 66 linhas (Jogo em nuvem), 67 de 73 (Streaming 4K), 27 de 27 (Chamada de vídeo) e 4 de 4 (Navegação) são de 2,4 GHz.

**Protótipo (eficiência em 5 GHz, absoluto em 2,4 GHz; dois modelos completos por fold):**

| | Download R² / MAE / MAE log | Upload R² / MAE | Atende (90%) |
|---|---|---|---|
| `v3-tr069` | 0,42 / 40,7 / 0,713 | 0,62 / 40,2 | 0,655 (0,638 a 0,676) |
| `v4-tr069` | 0,59 / 38,1 / 0,753 | 0,68 / 36,5 | 0,643 (0,625 a 0,666) |
| híbrido | 0,59 / 37,8 / 0,694 | 0,68 / 36,8 | 0,661 (0,641 a 0,680) |

Híbrido contra `v3`: Δ atende +0,006 (90%: 0,001 a 0,009), Δ MAE de download −2,9 (90%: −6,8 a 1,3), veredito "melhor". **A divisão por banda foi escolhida olhando estes mesmos 4 prédios: o número é otimista.**

**Scripts de classificação:** `classification_benchmark.py` classifica `qoe_dw_score`, que só existe em `metrics-20260630-out.csv` (dataset da geração antiga, excluído pelo Studio porque a fórmula do score se perdeu); nenhum dataset atual tem a coluna. As features padrão dele e do `compare_protocols.py` incluem os contadores da janela do teste (vazamento).

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| C2 | Descartada |
| Denominador por banda | Forma condicional `{"coluna": ..., "radio": ...}`; dois modelos completos por fold, escolha por linha |
| Nova versão | `v5-tr069`: features da `v3`, eficiência em 5 GHz no download (÷ `tx`) e no upload (÷ `rx`) |
| `classification_benchmark.py` | Reapontado para "atende" por aplicação, com a régua como referência |
| `compare_protocols.py` | Carga canônica, features da versão sem vazamento, aleatório contra LOGO por prédio |

## 4. Parte 1: denominador por banda

### 4.1 Registro (`core/modelos.py`)

- Cada valor de `denominador` (por alvo) pode ser:
  - um texto: o nome da coluna (forma atual, eficiência em todas as linhas);
  - um dicionário com exatamente as chaves `coluna` (texto não vazio) e `radio` (texto não vazio): eficiência só nas linhas em que a coluna `radio` tem esse valor.
- `validar_registro` aceita as duas formas e recusa o resto (chave a mais ou a menos, valor vazio, tipo errado).
- `salvar_versao` extrai a coluna de cada valor (texto ou `coluna` do dicionário) para a checagem existente (coluna conhecida, TR-069, sem vazamento).
- `denominador_de` continua devolvendo o valor como está (texto, dicionário ou `None`).
- Função nova `coluna_do_denominador(valor) -> str | None`: devolve a coluna das duas formas.

### 4.2 Régua (`core/avaliacao.py`)

- `prever_fora_do_fold(..., denominador=None)` aceita texto ou dicionário:
  - texto: comportamento atual;
  - dicionário: em cada fold, ajusta **dois** modelos sobre as mesmas linhas de treino, um na eficiência (`y ÷ den`, com a imputação atual) e outro em `y` absoluto. Cada linha de teste recebe a previsão da eficiência (multiplicada por `den`) se `radio` for igual ao valor indicado, e a previsão absoluta se não for. Linha sem `radio` usa a absoluta;
  - `den_imputado` só é verdadeiro em linhas que usaram a eficiência;
  - o teto de WAN é aplicado depois, como hoje;
  - `ao_ajustar` é chamado uma vez por modelo ajustado.
- Coluna `radio` ausente do conjunto com denominador condicional: `ValueError`.
- `avaliar`, `avaliar_versao` e o resto da régua não mudam (repassam o valor).
- `VERSAO_REGUA = '2026-10-07.1'`.

### 4.3 Integração

- **Studio:** sem mudança de código no Python (o valor do registro já é repassado como está). Em `modelos.js`, a etiqueta passa a mostrar a banda quando o denominador é condicional: "eficiência ÷ tx (5 GHz)".
- **`regression_mlflow.py`:** com denominador condicional, treina e registra os dois modelos finais (`<modelo>_eficiencia` e `<modelo>_absoluto`), e o `eficiencia.json` ganha `"radio"` e a regra de uso (`eficiência × den` quando `radio` é igual ao valor; absoluto nos demais casos).
- **Nova versão `v5-tr069`:** features da `v3-tr069`; `denominador = {"speedtest_down_mbps": {"coluna": "router_tx_rate_mbps", "radio": "5ghz"}, "speedtest_up_mbps": {"coluna": "router_rx_rate_mbps", "radio": "5ghz"}}`; salva com a avaliação da régua nova, não ativa.

## 5. Parte 2: scripts de classificação na régua

### 5.1 `core/classificacao.py` (novo)

- `alvo_atende(conj_dn, conj_up, limiares) -> pd.DataFrame`: junta os dois conjuntos por `_linha` (só linhas presentes nos dois) e devolve o `df` do download com a coluna booleana `_atende` (`down >= dn` e `up >= up`). As colunas internas (`_site`, `_pos`, `_linha`) vêm do conjunto de download.
- `prever_classe_fora_do_fold(df, colunas, vazadas, estimador) -> pd.DataFrame`: LOGO por `_site` com `assert_sem_vazamento` e `matriz`, como a régua; o estimador é clonado a cada fold. Devolve `_linha`, `y` (real, booleano), `yhat` (previsto, booleano), `_site` e `_pos`. Fold cujo treino tem uma classe só é pulado, com aviso.
- `resumir_classe(prev) -> dict`: acurácia balanceada pooled e por prédio, com intervalo de 90% pelo bootstrap de posições (`avaliacao.reamostras`). Reaproveita `avaliacao._acuracia_balanceada`.

### 5.2 `classification_benchmark.py`

- Lê a carga canônica (`--datasets`, padrão `ids_padrao`), a versão (`--modelo`, padrão a ativa) e as aplicações de `aplicacoes.json` (`--aplicacoes` para filtrar).
- Para cada aplicação com as duas classes no "atende" real: avalia os quatro classificadores atuais (rf, extra_trees, hist_gb, log_reg; com `class_weight='balanced'` onde já existe) por `prever_classe_fora_do_fold` e a **referência** da régua: o "atende" calculado das previsões de regressão da mesma versão (com o denominador dela), comparadas com os limiares.
- Imprime, por aplicação, uma tabela modelo × prédio de acurácia balanceada e a linha pooled com intervalo, com a referência na primeira linha.
- `--tune` (opcional) mantém a busca com `inner_logo_splits`; o padrão é sem busca.
- Saem: `--csv`, `--qoe-column`, `--class-mode`, `--fixed-thresholds`, `--group-level` e as opções ignoradas; usá-las dá erro (`--csv`) ou aviso (as demais), no padrão do `regression_benchmark.py`.

### 5.3 `compare_protocols.py`

- Carga canônica (`--datasets`), alvo (`--alvo`, padrão download), features da versão (`--modelo`, padrão a ativa) sem as que vazam.
- Protocolo antigo: divisão aleatória 80/20 nas mesmas linhas. Protocolo atual: `avaliacao.prever_fora_do_fold` (LOGO por prédio, sem denominador, para comparar só o protocolo).
- Imprime R² e MAE dos dois e a diferença ("otimismo do protocolo antigo").
- Saem `--csv` (erro) e `--group-level` (aviso).

## 6. Erros e avisos

- Denominador condicional sem coluna `radio` no conjunto: `ValueError` (422 no Studio).
- Aplicação com uma classe só no "atende" real: fora da tabela, com aviso.
- Fold de classificação com uma classe só no treino: pulado, com aviso.

## 7. Testes e experimento

### 7.1 Testes

- `tests/test_modelos_core.py`: forma condicional aceita; chaves erradas, `radio` vazio e tipos errados recusados; `salvar_versao` checa a coluna dentro do dicionário; `coluna_do_denominador` nas duas formas.
- `tests/test_avaliacao.py`: com dois estimadores constantes distintos (um por modelo), cada linha recebe a previsão da banda certa; linha sem `radio` usa a absoluta; `den_imputado` só nas linhas da banda; sem `radio` no conjunto, `ValueError`; a forma texto continua idêntica.
- `tests/test_classificacao.py` (novo): `alvo_atende` só nas linhas comuns e com o booleano certo; `prever_classe_fora_do_fold` nunca treina com o prédio de teste; fold com uma classe no treino é pulado; `resumir_classe` com valores conferidos à mão.
- Os testes atuais continuam passando.

### 7.2 Experimento (CHANGELOG)

- `v3-tr069`, `v4-tr069` e `v5-tr069` em download e upload: R² e MAE com intervalo, por prédio, MAE log, "atende em throughput", "atende completo" e os vereditos de `v5` contra `v3`, com a ressalva de otimismo da seção 2.
- `classification_benchmark.py` com a `v5-tr069`: classificadores contra a referência por aplicação.
- `compare_protocols.py` com a `v5-tr069` no download: otimismo do protocolo antigo no conjunto canônico.

## 8. Para o responsável pela coleta

Rodízio dos aparelhos clientes entre prédios (já pedido na spec da régua única, seção 9, item 4): é o que separa o efeito do aparelho do efeito do prédio em 2,4 GHz e tiraria a ressalva de otimismo da `v5-tr069`.
