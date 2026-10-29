# Studio: a régua por cômodo como nota principal e critério de ativação (design)

**Data:** 2026-10-29
**Base:** `master`, com `core/comodo.py`, `comodo_benchmark.py` e `tests/test_comodo.py` (spec `2026-10-29-regua-comodo-design.md`) ainda não commitados.
**Status:** desenho aprovado em conversa em 2026-10-29. Falta o plano de implementação.

## 1. Contexto

O cartão de cada versão no Studio mostra a nota de QoE, e o botão de ativação do Assistente segue o veredito de QoE. Depois da reavaliação de 2026-10-28, todas as versões ficaram em cerca de 0,66: os dois prédios do Villa prendem um terço da nota de QoE em 0,5, e o alvo de limiar absoluto não separa as versões.

A régua por cômodo (`core/comodo.py`, medida em 2026-10-29) responde à pergunta do produto, "quais cômodos de uma casa nova estão ruins?", e separa as versões do piso: piso 0,452; v1 e v2-tr069 0,643; v3, v4 e v5 0,722; todas melhores que o piso e empatadas com a v1.

A `avaliacao_completa` do Studio já calcula as previsões que essa régua usa (download e upload fora do fold, p90 de latência e jitter com CQR). A nota por cômodo sai delas sem treino adicional; o QoE treina classificadores próprios (cerca de 40 s por versão).

## 2. Decisões (conversa de 2026-10-29)

| Decisão | Escolha |
|---|---|
| Papel da nota por cômodo | Número principal do cartão e critério de ativação, no lugar do QoE |
| QoE | Sai da avaliação do Studio e do Assistente; `core/qoe.py`, `qoe_mlflow.py` e `perfil_qoe` ficam no repositório |
| Régua de regressão e as três métricas de "atende" | Ficam como estão, sem destaque; o veredito por alvo do Assistente vira informativo |
| Número secundário do cartão | Diferença da nota por cômodo contra o piso |
| Avaliação do rascunho | Cada avaliação guarda a tabela por posição; o Assistente calcula só o rascunho e compara com a tabela guardada da ativa |
| "Apto para jogo" | Calculado e guardado, não exibido, até ser consertado (spec próprio) |
| Regra de ativação | Sem mudança: só "melhor" libera; "empate" e "pior" travam; o modo Avançado ativa sem trava |

## 3. Núcleo (`core/comodo.py`)

### 3.1 Funções novas

- `de_previsoes(base_df, prev_dn, prev_up, q_lat, q_jit) -> pd.DataFrame`: junta por `_linha` os `yhat` de download e upload e os `q90` de latência e jitter, com `_site` e `_pos` de `base_df`; linha sem previsão em algum alvo sai. Mesmo formato que `prever` devolve hoje (`_linha, _site, _pos, dn, up, lat, jit`). `prever` passa a calcular as quatro previsões e chamar `de_previsoes`.
- `tabela_posicoes(df, prev, limiares) -> pd.DataFrame`: verdade e classe prevista por posição, só nas linhas sozinhas no rádio; colunas `_site, real, previsto, razao_prevista, apto_real, apto_previsto`, índice `_pos`.
- `amostras_posicoes(tabela) -> list`: `avaliacao.reamostras` sobre as posições da tabela (semente fixa, a de `avaliacao.SEMENTE`). Duas tabelas com as mesmas posições geram as mesmas reamostras.
- `bloco(tabela, piso, meta) -> dict`: o bloco `comodo` da seção 3.2.
- `comparar_blocos(nova, base) -> dict`: compara dois blocos (ou o bloco guardado com uma tabela nova) a partir de `posicoes`; levanta `ValueError` se `versao_comodo`, `datasets`, `ambiente` ou o conjunto de posições diferirem. Devolve `diferenca`, `intervalo`, `resultado` e as notas das duas.

### 3.2 Bloco `comodo` guardado em cada avaliação

| Campo | Conteúdo |
|---|---|
| `versao_comodo` | `VERSAO_COMODO` |
| `datasets`, `ambiente` | Do conjunto avaliado |
| `nota`, `intervalo` | Acurácia balanceada por posição (3 classes) e IC 90% |
| `piso` | `{nota, intervalo}` do piso |
| `contra_piso` | `{diferenca, intervalo, resultado}` |
| `por_predio` | `{prédio: [acertos, posições]}` |
| `confusao` | Matriz 3x3 em posições, verdade nas linhas, como lista de listas na ordem de `CLASSES` |
| `graves` | Erros bom <-> ruim |
| `posicoes` | Lista de `{pos, site, real, previsto, razao_prevista, apto_real, apto_previsto}`, uma por posição |
| `piso_posicoes` | A mesma lista para o piso |

O "apto para jogo" é guardado em `posicoes` e não entra em nenhum outro campo do bloco.

### 3.3 Piso

O piso (`features = ['radio']`, sem denominador) é o mesmo para todas as versões. O Studio o calcula uma vez por `(datasets, ambiente, VERSAO_COMODO)` e guarda em cache na memória do servidor; cada avaliação copia `piso_posicoes`.

## 4. Backend do Studio (`studio/api.py`)

- `avaliacao_completa`: a etapa "QoE" vira a etapa "cômodo" (`N_ETAPAS` continua 6). Ela usa `previsoes` de download e upload e `quantis` de latência e jitter já calculados, mais o piso em cache, e grava `saida['comodo']`. `saida['qoe']` deixa de ser gerado. O parâmetro `perfil_qoe` continua, porque define os limiares das métricas de "atende"; a régua por cômodo usa sempre o perfil de norma.
- `GET /api/modelos/avaliar_comodo` (parâmetros `features`, `ds`, `ambiente`, `contra`, `base`; o denominador é o da `base`, ou da ativa sem `base`, pela mesma regra do salvar): calcula as quatro previsões só do rascunho, monta a tabela e chama `comparar_blocos` contra o bloco guardado de `contra`. Resposta: nota e intervalo do rascunho, nota da ativa, piso, `diferenca`, `intervalo`, `resultado`, `por_predio`. Cache por chave, como o endpoint de QoE de hoje.
  - Sem bloco `comodo` em `contra`, ou com `versao_comodo`, `datasets` ou `ambiente` diferentes: HTTP 409, mensagem "reavalie a versão ativa antes de comparar".
- `GET /api/modelos/avaliar_qoe`: removido.
- `_promocao` (ΔMAE, Δ"atende ajustado", pinball, cobertura): sem mudança; deixa de decidir a ativação.
- `core/modelos.nota_reavaliacao` (linha do histórico de cada versão): passa a registrar `cômodo <antes> → <depois>`; a parte do QoE continua só quando uma das duas avaliações tem o bloco `qoe`.

## 5. Frontend (`studio/static/`)

- `logica.js`:
  - `notaCartao(v)`: com `avaliacao.comodo`, `{valor: comodo.nota, rotulo: 'cômodo', secundario: comodo.contra_piso.diferenca}`; sem ele, `{valor: atende_completo.media, rotulo: 'reavaliar', secundario: null}`.
  - `podeAtivar(aval, atual, comodo)`: lê `comodo.resultado` da resposta de `avaliar_comodo`; só `melhor` libera.
  - `precisaPedirQoe` vira `precisaPedirComodo`, com a mesma regra de idempotência por chave.
- `modelo.js` (Assistente): o bloco de QoE vira o bloco "Cômodo": nota do rascunho e da ativa, piso, diferença contra a ativa com intervalo e resultado, acertos por prédio. O seletor de perfil de QoE sai. O 409 aparece como aviso, com o botão de reavaliar a ativa.
- "Apto para jogo" não aparece em nenhuma tela.

## 6. Testes

Python:
- `de_previsoes` casa os quatro alvos por `_linha` e reproduz a saída de `prever`.
- `tabela_posicoes` e `bloco` trazem os campos da seção 3.2.
- `comparar_blocos` sobre blocos guardados dá a mesma diferença e o mesmo intervalo que `comparar` sobre as tabelas.
- `comparar_blocos` levanta com `versao_comodo`, `datasets`, `ambiente` ou posições diferentes.
- `avaliacao_completa` traz `comodo` e não traz `qoe`.
- `avaliar_comodo` devolve 409 contra uma versão sem bloco `comodo`; `avaliar_qoe` responde 404.

JS (`tests/js/logica.test.js`): `notaCartao` com e sem `comodo`; `podeAtivar` com melhor, empate e pior; `precisaPedirComodo`.

Navegador (Playwright): reavaliar v1 a v5 pelo menu de cada cartão; conferir o número do cartão e o bloco Cômodo do rascunho; console sem erros.

## 7. Migração

Depois de implantado, v1 a v5 são reavaliadas pelo Studio (menu de cada cartão); até lá, os cartões mostram o rótulo "reavaliar". A reavaliação grava o bloco `comodo` no `modelos.json`. As avaliações antigas mantêm o bloco `qoe`, que deixa de ser exibido.

## 8. Fora do escopo

Conserto do "apto para jogo"; conserto da nota de QoE; mudanças na régua de regressão; V0 medido com cabo; mudança na regra de ativação.

## 9. Limites conhecidos

1. Hoje toda versão empata com a v1 pela régua por cômodo: o botão de ativar fica travado na prática até haver dados que separem as versões.
2. Avaliar um rascunho custa as previsões dos quatro alvos (cerca de 1 min), contra cerca de 40 s do QoE.
3. A régua por cômodo é provisória (V0 aproximado, cortes semânticos); quando `VERSAO_COMODO` subir, todas as versões precisam ser reavaliadas antes de comparar.
