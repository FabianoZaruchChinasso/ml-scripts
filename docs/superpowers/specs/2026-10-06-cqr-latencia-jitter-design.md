# Calibração conformal (CQR) do p90 de latência e jitter (design)

**Data:** 2026-10-06
**Base:** `master` (commit `7a81093`) com a frente D ainda não commitada (`docs/superpowers/specs/2026-10-05-latencia-jitter-quantis-design.md`).
**Status:** desenho aprovado em conversa (o usuário pediu seguir todas as recomendações). Falta o plano de implementação.

## 1. Objetivo

A régua quantílica da frente D mostrou que o p90 previsto de latência e jitter sub-cobre num prédio que o modelo não viu: a cobertura fica entre 0,65 e 0,74 em três dos quatro prédios, abaixo da faixa aceita (0,80 a 0,95). O critério da spec anterior (seção 7.3) pede a calibração conformal (CQR) nesse caso. Esta entrega:

- corrige o p90 com um termo conformal calculado em LOGO interno nos prédios de treino de cada fold;
- leva essa correção para o modelo de produção registrado no MLflow;
- mede o efeito na mesma régua (cobertura, pinball e "atende completo").

## 2. Evidência (protótipo em 2026-10-06, `v3-tr069`, conjunto canônico)

Cobertura do p90 no prédio deixado de fora:

| Método | casa-marcelo | coworking | hotmilk | residência |
|---|---|---|---|---|
| Latência, sem correção (hoje) | 0,85 | 0,74 | 0,66 | 0,65 |
| Latência, escores juntos (CQR padrão) | 0,94 | 1,00 | 0,89 | 0,92 |
| Latência, média das correções por prédio | 0,93 | 0,99 | 0,88 | 0,92 |
| Latência, máximo das correções por prédio | 0,94 | 1,00 | 0,90 | 0,95 |
| Jitter, sem correção | 0,81 | 0,66 | 0,70 | 0,68 |
| Jitter, escores juntos | 0,91 | 0,99 | 0,87 | 0,89 |

p90 mediano previsto de latência (ms), sem correção → escores juntos: casa-marcelo 24 → 47, coworking 25 → 63, hotmilk 13 → 25, residência 30 → 71. O tempo de uma avaliação com LOGO interno é cerca de 30 s por alvo, contra 12 s sem correção.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Agregação da correção entre prédios | Escores juntos, com o nível de quantil de amostra finita da CQR padrão |
| Quantis corrigidos | Só o p90 (o p50 não entra no "atende") |
| Escala da correção | Log (`log1p`): a correção vira um fator multiplicativo em ms |
| Fold com um único prédio de treino | Sem correção (0), marcado |
| Correção em produção | Calculada com todos os prédios; registrada no MLflow como métrica e em `conformal.json`, sem classe de modelo nova |
| Interface do Studio | Sem mudança |

## 4. Desenho: `src/ml/core/quantis.py`

### 4.1 `correcao_conformal(X, y_log, sites, q=0.9, estimador=None) -> float | None`

- LOGO pelos prédios de `sites`: para cada prédio `s`, ajusta o modelo quantílico do quantil `q` (clone de `estimador`, ou `modelo_quantil(q)`) sem `s` e calcula os escores `y_log - previsto` nas linhas de `s`.
- Junta todos os escores (`n` no total) e devolve o quantil de nível `min(1, ceil((n + 1) · q) / n)`, com `numpy.quantile(..., method='higher')`.
- Com menos de 2 prédios em `sites`, devolve `None` (não há como fazer LOGO).

### 4.2 `prever_quantis_fora_do_fold(..., conformal=True)`

- Novo parâmetro `conformal` (padrão `True`). Em cada fold externo, calcula `correcao_conformal(fold.X_train, fold.y_train, sites de treino, 0.9, estimadores.get(0.9))` e soma ao p90 **em escala log**, antes de `expm1`.
- Correção `None` vira 0 e a linha fica com `sem_correcao` verdadeiro.
- O corte em 0 e a correção de quantis cruzados continuam depois da soma, na mesma ordem.
- Novas colunas de saída: `correcao` (o termo em log usado naquele fold) e `sem_correcao` (booleano).
- `conformal=False` mantém o comportamento da frente D (útil para comparar e para testes).

### 4.3 `resumir_quantis`

- Novo campo `correcao_por_local`: `{prédio: correção em log}`, do primeiro valor de `correcao` de cada prédio (é constante dentro do fold).
- Novo campo `sem_correcao`: quantas linhas ficaram sem correção.
- Se `prev` não tiver a coluna `correcao` (previsões feitas com `conformal=False`), `correcao_por_local` fica `{}` e `sem_correcao` fica 0.

### 4.4 Versão da régua

`avaliacao.VERSAO_REGUA` passa a `2026-10-06.1`. Avaliações guardadas antes aparecem como "desatualizadas".

## 5. Integração

1. **Studio (`api.py`):** nenhuma mudança de código. `_prever_quantis` chama `prever_quantis_fora_do_fold` com o padrão `conformal=True`; `avaliacao_completa` e `_promocao` passam a usar o p90 corrigido.
2. **Interface:** sem mudança. Cobertura e pinball do p90 já são lidos de `quantis`.
3. **`regression_mlflow.py`, ramo quantílico (`treinar_quantis`):**
   - as métricas de régua passam a vir do p90 corrigido (é o padrão);
   - calcula a correção de produção com `correcao_conformal(X, y_log, conj.df['_site'], 0.9)` sobre todos os prédios;
   - registra a métrica `correcao_log_q90`, e o artefato `conformal.json` com `{"quantil": 0.9, "correcao_log": <valor>, "escala": "log1p", "uso": "q90_ms = expm1(predict(X) + correcao_log)", "versao_regua": ...}`;
   - imprime a correção.
4. **Sem mudança:** `carga.py`, `avaliacao.py` (exceto a versão), registro de versões, `regression_benchmark.py`.

## 6. Erros e avisos

- `correcao_conformal` com menos de 2 prédios: devolve `None`, nunca levanta.
- Escores vazios (um prédio sem linhas com alvo): o prédio é ignorado; se nenhum sobra, devolve `None`.
- O restante dos erros (vazamento, menos de 2 prédios no total) continua como na frente D.

## 7. Testes, experimento e critério de aceite

### 7.1 Testes (`tests/test_quantis.py`)

- `correcao_conformal`:
  - com um estimador constante e alvos conhecidos, devolve o quantil de nível de amostra finita esperado (valor conferido à mão);
  - com um único prédio, devolve `None`.
- `prever_quantis_fora_do_fold`:
  - com `conformal=True` e estimadores constantes, o p90 sai deslocado pelo fator `expm1(log1p(p90) + correcao)` esperado;
  - com `conformal=False`, sai idêntico ao da frente D (os testes existentes passam a fixar `conformal=False` quando dependem do p90 cru);
  - as colunas `correcao` e `sem_correcao` existem.
- `resumir_quantis` traz `correcao_por_local` e `sem_correcao`, e funciona com previsões sem a coluna `correcao`.
- Os testes atuais continuam passando.

### 7.2 Experimento (CHANGELOG)

- `v2-tr069` e `v3-tr069` em latência e jitter, com e sem CQR: cobertura do p90 por prédio e pooled, pinball, correção por prédio e "atende completo".
- Veredito de promoção `v3-tr069` contra `v2-tr069` com a régua `2026-10-06.1`.
- O efeito no "atende" por aplicação, principalmente em Jogo em nuvem (limiar de latência de 40 ms), onde o p90 mais largo muda a decisão.

### 7.3 Critério de aceite

A CQR é aceita se a cobertura pooled do p90 da `v3-tr069` ficar dentro de 0,80 a 0,95 nos dois alvos. Prédios fora da faixa por **excesso** de cobertura (como o coworking, perto de 1,00) ficam registrados como conservadorismo, não como falha. Se a cobertura pooled sair da faixa, o CHANGELOG registra isso e a próxima recomendação passa a ser a média das correções por prédio (opção 2 da conversa).

## 8. Próximo passo

A frente C (dados externos e fine-tuning), conforme a seção 10 de `docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`.
