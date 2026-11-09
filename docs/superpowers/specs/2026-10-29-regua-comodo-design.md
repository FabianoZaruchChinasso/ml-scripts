# Régua por cômodo: experiência relativa à casa (design)

**Data:** 2026-10-29
**Base:** `master` (commit `6a19d16`), com `core/percepcao.py` e `core/percepcao.json` ainda não commitados (spec `2026-10-29-rotulo-percepcao-design.md`).
**Status:** desenho aprovado em conversa em 2026-10-29. Falta o plano de implementação.

## 1. Contexto

Depois da reavaliação de 2026-10-28, todas as versões ficaram em cerca de 0,66 no Studio, tanto na nota de QoE quanto no "atende completo". Duas causas, medidas em 2026-10-29:

1. **Defeito da nota de QoE.** Os dois prédios do Villa entram na nota só por "Jogo em nuvem" (poucas falhas de jitter, nos melhores cômodos) e tiram exatamente 0,5 em todo modelo e no piso. A nota vira 4/6 x (nota real) + 1/6. Sem o Villa, v1 a v5 ficam entre 0,739 e 0,744 e o piso em 0,695.
2. **O alvo não separa as versões.** As duas réguas medem "atende a um limiar absoluto" (no máximo 25 Mbps). No Villa, os cômodos rotulados Ruim entregam 231 e 442 Mbps e passam em tudo.

A análise do rótulo de percepção (mesma data) mostrou que as pessoas julgam o cômodo **em relação ao resto da casa**: no Villa, quarto2 e cozinha perdem capacidade (download 442 e 231 contra 636 a 680; upload 309 e 81 contra 632 a 671), sinal, SNR e taxa do link em relação aos cômodos bons, sem mudar latência e jitter.

Esta régua responde à pergunta do produto: **numa casa que o modelo nunca viu, ele aponta quais cômodos têm experiência ruim?**

## 2. Decisões (conversa de 2026-10-29)

| Decisão | Escolha |
|---|---|
| Pergunta principal | Diagnóstico do cliente: quais cômodos de uma casa nova estão ruins |
| Verdade de referência (destino) | Teste de aplicação objetivo (vídeo com URL fixa, carga de página) contra a linha de base com cabo (V0) da casa |
| Transição até existir a coleta nova | V0 aproximado: a melhor posição do próprio prédio |
| O que é comparado | Capacidade relativa (download e upload) **e** interatividade absoluta (latência e jitter contra a norma) |
| Formato da resposta | Três classes: bom, degradado, ruim |
| Cortes de capacidade | Semânticos fixos: ruim abaixo de 1/4 da casa, degradado de 1/4 a 3/4, bom a partir de 3/4. Trocados pelo teste de vídeo quando existir |
| Interatividade | Falhar em Navegação: ruim. Falhar em Chamada: no máximo degradado. Jogo em nuvem fica fora da classe, como indicação "apto para jogo" |
| O que o modelo prevê | As grandezas físicas (download, upload, p90 de latência e jitter), como a régua de regressão já faz. A classe é calculada depois, com o V0 da casa como dado conhecido |
| Integração | Primeiro núcleo e script; Studio e critério de ativação num segundo spec, depois de ver os números |

O protocolo do teste de vídeo e do V0 com cabo é da coleta (coletor ou app), fora deste repositório, e terá spec própria.

## 3. Evidência (medida em 2026-10-29, conjunto padrão)

### 3.1 Razão de capacidade contra o rótulo humano

Razão = pior de (mediana do download ÷ maior mediana do prédio) e (mediana do upload ÷ maior mediana do prédio), com todas as linhas (antes do filtro de concorrência da seção 4.1):

| Faixa de razão | Posições e rótulo humano |
|---|---|
| 0,06 a 0,12 | res-suite, marcelo-inf-ext, marcelo-sala-estar (Ruim), villa_res_cozinha (Ausente) |
| 0,16 a 0,20 | res-quarto, cwpb-2 (Bom), marcelo-inf-quarto, marcelo-inf-quarto-split (Ok) |
| 0,35 a 0,47 | marcelo-copa, marcelo-copa-split (Bom), villa_res_quarto2 (Ruim), hotmilk-aquario, hotmilk-aquario-fora (Excelente) |
| 0,74 a 1,00 | as demais 14: Bom ou Excelente, exceto hotmilk-copa (Ok) |

O villa-escritorio fica todo entre 0,98 e 1,00 porque está no teto da WAN (93/98 Mbps): o Wi-Fi entrega o que a internet entrega em todos os cômodos, e os rótulos ali são Bom ou Excelente.

### 3.2 Concorrência

`concorrentes_mesmo_radio` conta a própria linha (1 = sozinho no rádio). Toda posição tem pelo menos 10 linhas sozinha. A concorrência divide a capacidade e parece defeito do cômodo:

| Posição | Download mediano, todas as linhas | Download mediano, sozinho |
|---|---|---|
| cwpb-2 | 13,4 | 61,1 |
| hotmilk-copa | 106,1 | 182,4 |
| hotmilk-aquario-fora | 49,6 | 125,7 |
| res-sala | 58,1 | 98,7 |

### 3.3 Interatividade (p90 por posição, perfil de norma)

- Navegação (latência 800, jitter 100): nenhuma posição falha.
- Chamada de vídeo (latência 200, jitter 50): res-suite, res-quarto, marcelo-copa, marcelo-copa-split.
- Jogo em nuvem (latência 80, jitter 10): 17 de 27 posições falham. Por isso fica fora da classe.

## 4. Desenho

### 4.1 Verdade de referência, por posição

Linhas: as do `qoe.conjunto_qoe` (presentes nos quatro alvos) com `concorrentes_mesmo_radio == 1`. Linhas com o valor vazio ficam de fora.

1. **Estatísticas da posição:** mediana de `speedtest_down_mbps`, mediana de `speedtest_up_mbps`, p90 de `latency_ms`, p90 de `jitter_ms`.
2. **Referência da casa (V0 provisório):** por prédio (`_site`), a maior mediana de download entre as posições com pelo menos `MIN_LINHAS_REFERENCIA = 10` linhas, e o mesmo para o upload, separadamente.
3. **Razão de capacidade:** `min(download ÷ ref_download, upload ÷ ref_upload)`.
4. **Classe** (função `classificar`, a mesma para verdade e previsão):
   - `ruim` se razão `< 0,25`, ou se latência p90 `>` limiar de Navegação, ou jitter p90 `>` limiar de Navegação;
   - senão, `degradado` se razão `< 0,75`, ou se latência p90 `>` limiar de Chamada de vídeo, ou jitter p90 `>` limiar de Chamada de vídeo;
   - senão, `bom`.
5. **Apto para jogo:** latência p90 `<=` limiar de Jogo em nuvem e jitter p90 `<=` limiar de Jogo em nuvem.

Limiares: `aplicacoes.carregar_perfil('norma')`. Latência e jitter (`lat`, `jit`) de Navegação, Chamada de vídeo e Jogo em nuvem; desde 2026-11-05 também os mínimos de capacidade (`dn`, `up`) de Navegação (abaixo: ruim) e Chamada de vídeo (abaixo: degradado), para a casa cujo melhor cômodo já é fraco. "Apto para jogo" continua só latência e jitter. Nenhum limiar é copiado no código. Cortes de capacidade relativa: constantes `CORTE_RUIM = 0.25` e `CORTE_BOM = 0.75`. Versão: `VERSAO_COMODO` (atual `2026-11-05.1`); sobe quando cortes, referência, filtro de linhas ou regras mudam.

### 4.2 Previsão e nota de uma versão

1. **Previsões fora do fold**, nas linhas da seção 4.1, casadas por `_linha`:
   - download e upload: `avaliacao.prever_fora_do_fold(conj.df, features, conj.alvo, vazadas, denominador=...)`, com o denominador da versão para cada alvo quando houver;
   - latência e jitter: `quantis.prever_quantis_fora_do_fold(conj.df, features, conj.alvo, vazadas)`, coluna `q90` (já com a CQR).
   Linha sem previsão em algum dos quatro alvos sai da conta, com aviso.
2. **Classe prevista por posição:** mediana das previsões de download e de upload, mediana dos `q90` de latência e de jitter, passadas por `classificar` com **a mesma referência da casa** da verdade (o V0 é dado conhecido, como o plano da operadora ou um teste TR-143 em produção).
3. **Nota:** acurácia balanceada das 3 classes sobre as **posições** de todos os prédios juntas (média do recall das classes presentes na verdade). Não é média entre prédios: um prédio com uma classe só não prende a nota.
4. **Intervalo de 90%:** `avaliacao.reamostras` aplicado a uma linha por posição (bootstrap de posições estratificado por prédio).
5. **Comparações:** contra o **piso** (a mesma régua com `features = ['radio']`) e contra a **versão ativa** do registro. Diferença pareada nas mesmas reamostras; intervalo todo acima de 0: `melhor`; todo abaixo: `pior`; senão `empate`.
6. **Relatório por versão:** nota e intervalo; diferença contra o piso e contra a ativa; matriz 3x3 em posições (verdade nas linhas); erros graves (`bom` previsto como `ruim` e o contrário); acertos por prédio; acurácia balanceada de "apto para jogo" por posição (binária).
7. **Verdade contra o rótulo humano** (uma vez, não por versão): `core/percepcao.json` convertido (Excelente e Bom -> bom, Ok -> degradado, Ruim e Ausente -> ruim), matriz 3x3 em posições e acurácia balanceada da verdade contra o rótulo. É validação cruzada, não alvo.

### 4.3 Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/core/comodo.py` | criar | `verdade`, `classificar`, `prever`, `nota`, `comparar`, `confusao`, `contra_rotulo`, constantes e `VERSAO_COMODO` |
| `src/ml/comodo_benchmark.py` | criar | reavalia todas as versões do registro e o piso; imprime o relatório da seção 4.2. `MODELO=` restringe a uma versão; `DATASETS=` como no `qoe_mlflow.py` |
| `tests/test_comodo.py` | criar | testes da seção 5, sem a base real |
| `CHANGELOG.md` | modificar (topo) | seção nova com os números medidos |

Funções genéricas de métrica vêm de `core/percepcao.py` (`acuracia_balanceada`, `resumir`, `diferenca`, `por_predio`), sem cópia. `core/percepcao.py` precisa estar commitado antes da execução do plano.

## 5. Testes

- `verdade` usa só linhas com `concorrentes_mesmo_radio == 1`; linhas com 2 ou vazio não mudam o resultado.
- A referência ignora posição com menos de 10 linhas sozinha.
- A razão é o pior entre download e upload.
- `classificar` nos limites: razão 0,25 é `degradado`, 0,2499 é `ruim`, 0,75 é `bom`, 0,7499 é `degradado`.
- Falha em Navegação dá `ruim` mesmo com razão 1,0.
- Falha em Chamada com razão 1,0 dá `degradado`; com razão 0,5 continua `degradado`; nunca `ruim` só por Chamada.
- "Apto para jogo" não muda a classe.
- Os limiares vêm do perfil passado (teste com um perfil montado à mão diferente da norma).
- A classe prevista usa a referência da verdade, não uma calculada das previsões.
- A nota sobre posições: dois prédios montados à mão, um deles só com `bom`, não prendem a nota (caso do Villa).
- `contra_rotulo` converte os 5 níveis nas 3 classes.

## 6. Fora do escopo

Studio e critério de ativação (segundo spec, depois dos números); campo de V0 medido no `predios.json` (só quando houver medição com cabo); protocolo do teste de vídeo e do V0 (spec da coleta); réguas de regressão e de QoE, que continuam como estão; o conserto da nota de QoE discutido em 2026-10-29 (não decidido).

## 7. Limites conhecidos

1. A posição que define a referência é `bom` em capacidade por construção, na verdade e na previsão: leve otimismo.
2. A referência é relativa: num prédio em que todos os cômodos são ruins, a referência fica errada. Só o V0 real resolve.
3. O V0 é tratado como conhecido. Na transição, ele vem da verdade da própria casa de teste; em produção, do plano ou de um teste TR-143.
4. A nota é provisória até existirem o teste de vídeo e o V0 real. Quando chegarem, mudam a referência e os cortes, e `VERSAO_COMODO` sobe.
5. Com 27 posições e 6 prédios, o intervalo de 90% sai largo.
6. O intervalo reamostra posições com os prédios fixos: não mede a variação entre prédios.
