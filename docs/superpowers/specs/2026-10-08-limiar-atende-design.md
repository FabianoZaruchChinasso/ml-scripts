# Fator de decisão do "atende" em throughput (design)

**Data:** 2026-10-08
**Base:** `master` (commit `3056574`), depois da entrega "eficiência só em 5 GHz e scripts de classificação na régua".
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

Hoje a régua decide "atende" comparando a previsão de Mbps direto com o limiar da aplicação (download ≥ `dn` e upload ≥ `up`). O benchmark de classificação mostrou que essa decisão é fraca nas aplicações de limiar baixo: a acurácia balanceada da régua é 0,519 em Navegação e 0,558 em Chamada de vídeo, contra 0,62 a 0,81 dos classificadores diretos.

A causa é a regressão superestimar os enlaces quase mortos: ela prevê alguns Mbps para enlaces que entregam menos de 1, então diz "atende" demais. Esta entrega acrescenta um **fator de decisão por aplicação**: a régua passa a dizer "atende" quando a previsão é ≥ `k × limiar`, com `k` escolhido sem olhar o prédio de teste.

## 2. Evidência (protótipo em 2026-10-07, `v5-tr069`, régua `2026-10-07.1`)

Acurácia balanceada pooled do "atende" em throughput, com o fator escolhido por LOGO interno nos prédios de treino de cada fold (aninhado), numa grade de 0,8 a 8:

| Aplicação | Régua hoje (k = 1) | Fator ajustado (aninhado) | Fator escolhido por prédio de teste | Melhor classificador (`--tune`) |
|---|---|---|---|---|
| Navegação | 0,519 | 0,805 | 8,0 / 7,0 / 6,75 / 8,0 | 0,807 (`rf`) |
| Chamada de vídeo | 0,558 | 0,789 | 2,9 / 6,0 / 3,0 / 4,5 | 0,772 (`rf`) |
| Streaming 4K | 0,801 | 0,782 | 2,0 / 1,2 / 1,6 / 1,1 | 0,773 (`hist_gb`) |
| Jogo em nuvem | 0,765 | 0,788 | 2,6 / 1,8 / 2,1 / 1,9 | 0,770 (`hist_gb`) |
| Média | 0,661 | 0,791 | | |

- Numa primeira grade (0,8 a 3,0), Navegação parou em 3,0 em todos os folds: a grade foi ampliada e o fator subiu até 8. A grade deste desenho vai até 16.
- O ajuste empata ou supera o melhor classificador (com busca de hiperparâmetros) sem trocar o modelo.
- Em Streaming 4K o ajuste perde um pouco (0,801 para 0,782): o fator 1 já era bom e a seleção em 3 prédios adiciona ruído.
- O fator não corrige a previsão de Mbps (o MAE não muda); só a decisão.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Onde o fator entra | Só no lado do throughput (latência e jitter já usam o p90 calibrado pela CQR) |
| Como o fator é escolhido na régua | Por aplicação, em cada fold, por LOGO interno nos prédios de treino, maximizando a acurácia balanceada |
| Grade | Geométrica, de 0,5 a 16, passo 2^(1/8); empate fica com o fator mais perto de 1 |
| Números visíveis | O "atende" bruto (fator 1) continua; o "atende ajustado" é acrescentado |
| Promoção | Passa a usar o "atende ajustado" |
| Fator de produção | Escolhido por LOGO com todos os prédios, guardado na avaliação da versão |

## 4. Desenho: `src/ml/core/limiar.py` (novo)

- `FATORES`: grade geométrica `2 ** e` para `e` de −1 a 4 em passos de 0,125 (0,5 a 16).
- `escolher_fator(j, limiares, fatores=FATORES) -> float`: `j` é a junção (`avaliacao._juntar`) das previsões de download e upload. Devolve o fator com a maior acurácia balanceada de "atende", em que previsto = `p_dn ≥ k·dn` e `p_up ≥ k·up`. Empate: o fator mais perto de 1 em escala log. Real com uma classe só: 1.
- `decisoes_atende(conj_dn, conj_up, features, aplicacoes, den_dn=None, den_up=None, ajustar=True) -> dict`:
  - previsões fora do fold de download e upload (régua, com o denominador de cada alvo);
  - para cada prédio de teste: previsões fora do fold **só com os outros prédios** (LOGO interno) e `escolher_fator` por aplicação; com menos de 2 prédios de treino, fator 1;
  - `ajustar=False`: fator 1 em tudo (a régua de antes);
  - devolve `{aplicação: DataFrame(_linha, _site, _pos, real, previsto, fator)}`.
- `resumir_decisoes(decisoes) -> dict`: a mesma forma de `avaliacao.atende` (`por_aplicacao`, `media`, `intervalo`, `n`, `avisos`), mais `fatores` (`{aplicação: {prédio: fator}}`).
- `delta_decisoes(nova, base) -> dict | None`: acurácia balanceada média da nova menos a da base, nas mesmas linhas e reamostragens, como `avaliacao.delta_atende`, com `ajustado: true`.
- `fatores_producao(conj_dn, conj_up, features, aplicacoes, den_dn=None, den_up=None) -> dict`: `{aplicação: fator}`, escolhido sobre as previsões fora do fold de todos os prédios.
- `avaliacao.VERSAO_REGUA = '2026-10-08.1'`.

## 5. Integração

1. **`api.avaliacao_completa`:** acrescenta `atende_ajustado` = `resumir_decisoes(...)` mais `fatores_producao`. `atende_throughput` (bruto) e `atende_completo` continuam iguais.
2. **`api._promocao`:** para download e upload, `delta_atende` passa a vir de `delta_decisoes` (cada lado com o seu denominador), com `ajustado: true`. `veredito_promocao` não muda.
3. **`assistente.js`:** o rótulo do cartão de promoção passa a "Δ atende (limiar ajustado)" quando `delta_atende.ajustado`.
4. **`classification_benchmark.py`:** uma linha nova de referência, "régua (limiar ajustado)", ao lado de "régua (regressão)".
5. **Custo:** `decisoes_atende` faz, por versão, as previsões externas de 2 alvos mais 4 LOGOs internos de 2 alvos (cerca de 4 vezes o custo do "atende" bruto). A promoção faz isso para as duas versões.

## 6. Testes e experimento

- `tests/test_limiar.py` (novo):
  - `escolher_fator` encontra o fator que separa uma regressão que superestima (valor conferido à mão), fica com o mais perto de 1 em empate e devolve 1 com uma classe só;
  - `decisoes_atende` nunca usa o prédio de teste para escolher o fator dele (espião nas chamadas de `prever_fora_do_fold`) e o fator de cada prédio é o que `escolher_fator` dá sobre o LOGO interno;
  - `ajustar=False` reproduz o "atende" bruto;
  - `resumir_decisoes` e `delta_decisoes` com valores conferidos à mão; `fatores_producao` dentro da grade.
- `tests/test_studio_assistente.py`: `avaliacao_completa` traz `atende_ajustado` com `fatores` e `fatores_producao`; a promoção em download traz `delta_atende.ajustado`.
- Experimento (CHANGELOG): "atende" bruto contra ajustado na `v3`, `v4` e `v5`, por aplicação, com os fatores; vereditos da `v5` contra a `v3` na régua nova; o benchmark de classificação com as duas linhas de referência.

## 7. Fica fora

- Corrigir a previsão de Mbps na faixa baixa (o fator só corrige a decisão).
- Fator para latência e jitter.
- Mostrar os fatores na tabela de versões do Studio.
