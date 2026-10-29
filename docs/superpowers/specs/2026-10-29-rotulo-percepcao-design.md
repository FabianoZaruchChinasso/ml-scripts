# Classificador do rótulo de percepção por cômodo (design)

**Data:** 2026-10-29
**Base:** `master` (commit `6a19d16`).
**Status:** desenho aprovado em conversa em 2026-10-29. Falta o plano de implementação.

## 1. Contexto

Na reunião de 2026-10-28 ficou alinhado acrescentar à coleta um rótulo dado por quem estava no local, dizendo se a experiência em cada cômodo era boa ou ruim. Os rótulos das coletas já feitas foram passados por posição (seção 3.1). Este trabalho mede se esse rótulo é aprendível a partir das features que o roteador expõe por TR-069, e se as features da v5 acrescentam algo ao piso "só `radio`". É um script de experimento; o Studio não muda.

## 2. Evidência (medida em 2026-10-29, conjunto padrão)

Conjunto padrão: `20260827`, `20260917-fix`, `20260921-distcalc`, `20260925`, `20260928`, `villa-20261025.csv`, `villa-esc-20261026.csv`. Medianas por posição, alvo `speedtest_down_mbps`:

| Posição | Rótulo | Linhas | Down / Up (Mbps) | Jitter (ms) |
|---|---|---|---|---|
| res-quarto | Bom | 142 | 13,4 / 5,6 | 11,1 |
| cwpb-2 | Bom | 71 | 13,4 / 9,0 | 9,0 |
| marcelo-inf-quarto | Ok | 22 | 18,4 / 20,6 | 2,7 |
| hotmilk-copa | Ok | 82 | 106,1 / 119,6 | 3,3 |
| villa_res_quarto2 | Ruim | 51 | 441,9 / 308,7 | 3,1 |
| villa_res_cozinha | Ruim / Ausente | 43 | 230,6 / 80,5 | 3,4 |
| res-suite | Ruim | 180 | 3,8 / 2,2 | 17,6 |

1. **O rótulo contradiz a medição em vários pontos.** `marcelo-inf-quarto` (Ok) mede melhor que `res-quarto` (Bom); `hotmilk-copa` (Ok) é o melhor ponto do hotmilk; `villa_res_quarto2` (Ruim) passa em qualquer limiar de aplicação.
2. **Cada prédio foi rotulado por uma pessoa diferente.** No LOGO por prédio, avaliador e prédio se confundem; o experimento não os separa.
3. **As quedas de conexão não viram linha.** `villa_res_cozinha` não tem nenhum teste com download vazio ou 0. Os testes falhos que existem (14 no total) se concentram em `hotmilk-aquario` (7, rotulado Excelente). O descarte de `descartar_testes_falhos` fica como está.
4. **`marcelo-quarto` não está na base padrão.** Só existe em `20260925`, sem stats de estação; `marcelo-quarto-split` está.
5. **O rótulo é por posição.** São 27 amostras na base padrão, não ~1500.

## 3. Desenho

### 3.1 Rótulos

Arquivo novo `src/ml/core/percepcao.json`, versionado, separado de `predios.json` (que é gravado pelo Studio):

```json
{
  "classes": {
    "Excelente": "excelente",
    "Bom": "media",
    "Ok": "media",
    "Ruim": "ruim",
    "Ausente": "ruim"
  },
  "posicoes": {
    "villa_res_sala": "Excelente",
    "villa_res_cozinha": "Ausente",
    "villa_res_escritorio": "Excelente",
    "villa_res_quarto1": "Bom",
    "villa_res_quarto2": "Ruim",
    "villa_esc_recepcao": "Bom",
    "villa_esc_sala1": "Excelente",
    "villa_esc_sala2": "Excelente",
    "villa_esc_copa": "Excelente",
    "villa_esc_estoque": "Bom",
    "marcelo-copa": "Bom",
    "marcelo-copa-split": "Bom",
    "marcelo-sala-estar": "Ruim",
    "marcelo-quarto": "Excelente",
    "marcelo-quarto-split": "Excelente",
    "marcelo-inf-sala": "Bom",
    "marcelo-inf-sala-split": "Bom",
    "marcelo-inf-quarto": "Ok",
    "marcelo-inf-quarto-split": "Ok",
    "marcelo-inf-ext": "Ruim",
    "res-sala": "Excelente",
    "res-quarto": "Bom",
    "res-suite": "Ruim",
    "cwpb-1": "Excelente",
    "cwpb-2": "Bom",
    "hotmilk-aquario": "Excelente",
    "hotmilk-aquario-fora": "Excelente",
    "hotmilk-copa": "Ok"
  }
}
```

- O nível bruto (5 níveis, ordem Excelente > Bom > Ok > Ruim > Ausente) fica guardado; o agrupamento em 3 classes vive só em `classes`. "Ruim / Ausente", como foi passado para `villa_res_cozinha`, é gravado como `Ausente`.
- As chaves de `posicoes` são a posição canônica de `sites.resolve_site_id`. Posição que não resolve, nível fora de `classes` ou classe fora de {`excelente`, `media`, `ruim`} levanta `ValueError`.
- Posição rotulada sem linhas na base padrão (hoje só `marcelo-quarto`) não é erro: aparece no relatório como "sem linhas na base padrão". Linha da base cuja posição não tem rótulo sai do conjunto, com aviso.

Classes na base padrão (27 posições):

| Prédio | excelente | media | ruim |
|---|---|---|---|
| villa-residencial | 2 | 1 | 2 |
| villa-escritorio | 3 | 2 | 0 |
| casa-marcelo | 1 | 6 | 2 |
| residencia | 1 | 1 | 1 |
| coworking | 1 | 1 | 0 |
| hotmilk | 2 | 1 | 0 |
| **Total** | **10** | **12** | **5** |

Todo fold do LOGO tem as três classes no treino.

### 3.2 Experimento

Script novo `src/ml/percepcao_benchmark.py`, no padrão de `classification_benchmark.py`. Funções puras num módulo novo `src/ml/core/percepcao.py` (carga dos rótulos, pesos, agregação por posição, métricas); o script só orquestra e imprime.

1. **Linhas:** `carga.carregar('speedtest_down_mbps')`, base padrão, mesmas linhas e descartes do Studio. Cada linha recebe a classe da sua `_pos`.
2. **Modelo:** os mesmos hiperparâmetros de `qoe.modelo_referencia` (RF 300 árvores, folha 5, imputação pela mediana, `random_state=42`), mas sem `class_weight` (item 5). O XGBoost monotônico do QoE não entra: não aceita restrição monotônica com 3 classes.
3. **Features:** v5, lida de `core/modelos.json` (não duplicada no script), e o piso, só `radio`. `assert_sem_vazamento` como no QoE.
4. **Validação:** LOGO por `_site` (`splits.outer_logo_folds`).
5. **Peso das linhas:** `peso = 1 / linhas_da_posição`, depois reescalado para que cada classe some o mesmo total no treino do fold. Passado como `clf__sample_weight`; por isso o estimador não usa `class_weight='balanced'`, que balancearia duas vezes.
6. **Previsão por posição:** média de `predict_proba` das linhas da posição, depois a classe de maior probabilidade.

### 3.3 Avaliação

Unidade: posição (27).

- **Acurácia balanceada por posição** (média do recall das 3 classes), para v5 e piso. Acaso e classe majoritária: 0,333.
- **IC90** por bootstrap de posições estratificado por prédio: `avaliacao.reamostras` aplicado a uma linha por posição.
- **Diferença v5 − piso** pareada, sobre as mesmas reamostragens.
- **Matriz de confusão 3×3** em posições, com a contagem de erros graves (excelente previsto como ruim e o contrário).
- **Acertos por prédio** (x de n posições), com a nota de que avaliador e prédio se confundem.
- **Acurácia por linha**, só como referência.

Sem MLflow; saída no terminal.

### 3.4 Regra de leitura (fixada antes de rodar)

| Pergunta | Sim quando | Senão |
|---|---|---|
| O rótulo é aprendível? | Limite inferior do IC90 do piso **ou** da v5 acima de 0,333 | "não aprendível com estes dados" |
| A v5 acrescenta ao piso? | IC90 de v5 − piso todo acima de 0 | todo abaixo de 0: "piora"; cruzando 0: "empate" |

Com 27 posições o IC90 sai largo; "empate" na segunda pergunta é o resultado mais provável e não muda a regra.

## 4. Testes

`tests/test_percepcao.py`, sem treinar na base real:

- carga dos rótulos: nível para classe; posição desconhecida, nível desconhecido e classe desconhecida levantam `ValueError`;
- pesos: cada posição soma o mesmo peso antes do balanceamento; as classes somam o mesmo total depois;
- agregação por posição: média de probabilidades e argmax num caso montado à mão;
- acurácia balanceada por posição num caso montado à mão.

## 5. Fora do escopo

Studio, MLflow, app de coleta, registro no coletor dos testes que caem, conjunto de features só do lado do cliente.
