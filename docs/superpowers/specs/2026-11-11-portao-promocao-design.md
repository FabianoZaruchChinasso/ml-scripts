# Portão de promoção

**Data:** 2026-11-11
**Origem:** item "Portão de promoção" da planilha "Anomalias de Rede - Backlog e Estimativas", com o ajuste
da revisão de 2026-11-11 (comparar no mesmo conjunto de dados). Passo 5 da ordem do inventário
(`docs/pipeline/2026-11-10-inventario-studio-mlflow.md`). Depende do Model Registry
(spec `2026-11-11-model-registry-alias-design.md`, branch `model-registry`).

## 1. Problema

Hoje o alias `ativo` só se move à mão (`ativar_mlflow.py`). A DAG de treino do backlog precisa de um passo que
decida sozinho, depois de cada `versao_mlflow.py`, se a versão recém-registrada substitui a ativa, e deixe
o motivo gravado. A decisão do Studio (veredito de promoção) é calculada na tela e não fica em lugar nenhum.

Comparar as métricas gravadas nos dois runs não serve: cada run pode ter sido avaliado com dados diferentes,
e R² ou MAE de conjuntos diferentes não se comparam.

## 2. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Base da comparação | Previsões fora do fold das duas definições, recalculadas nos dados da candidata, nas mesmas linhas | Mesmo conjunto por construção; é o que o Studio já faz, com as mesmas funções do core |
| Decisão por alvo | Download e upload: Δ MAE (`core_avaliacao.veredito_promocao`, sem o "atende"). Latência e jitter: Δ pinball do p90 e cobertura do p90 (`core_quantis.veredito_quantis`) | "Decide pelo erro das quatro previsões" (backlog); os vereditos já existem e já foram usados no Studio |
| Decisão final | Promove se nenhum alvo der "pior" e pelo menos um der "melhor". Empate mantém a ativa | Com 6 prédios os intervalos são largos; empate não justifica troca |
| Réguas de QoE | Auxiliares: nota por cômodo e "atende completo" dos dois runs vão para o relatório, sem decidir | A pesquisa de 2026-11-09 não validou nenhuma régua |
| Mesma definição (re-treino) | Promove se os dados da candidata contêm os da ativa e mais algum ("dado novo"); mesmos dados: nada a fazer; dados que não contêm os da ativa: não promove e explica | A validação cruzada da mesma receita nos mesmos dados dá diferença zero: o portão nunca promoveria o re-treino |
| Sem versão ativa | Promove a candidata ("primeira") | Primeira execução da DAG |
| Onde fica o veredito | Run da candidata: tags `portao_*` e arquivo `portao.json`. Versão registrada: tags `portao` e `portao_contra` | "Veredito gravado como tag do run" (backlog); a tag na versão aparece na tela do Registry |
| Simulação | `SIMULAR=1` calcula e grava o veredito sem mover o alias (tag `portao_simulado=sim`) | Para mostrar em reunião e testar a DAG sem trocar o modelo |
| Promoção à mão | `ativar_mlflow.py` continua, para voltar uma versão (rollback) ou forçar uma troca | O portão é o caminho normal; a mão fica como exceção |

## 3. Componentes

### 3.1 `src/ml/core/portao.py` (novo, sem MLflow)

- `comparar(conjs, candidata, ativa) -> dict`: `candidata` e `ativa` são `{'features', 'denominador'}`.
  Devolve `{alvo: bloco}` para os quatro alvos:
  - download/upload: `{'delta_mae': ..., 'veredito': ...}` com as previsões de
    `core_avaliacao.prever_fora_do_fold` (features presentes e sem vazamento, denominador da definição);
  - latência/jitter: `{'delta_pinball': ..., 'cobertura': ..., 'veredito': ...}` com
    `core_completa.prever_quantis`.
- `decidir(por_alvo) -> dict`: `{'promover', 'resultado', 'motivo'}`, `resultado` em
  `melhor | pior | empate`.
- `decidir_mesma_definicao(fp_candidata, fp_ativa) -> dict`: `resultado` em
  `igual | dado_novo | dados_diferentes`.

### 3.2 `src/ml/core/registry_mlflow.py`

- `info_versao(n) -> dict`: `{'versao', 'definicao', 'run_id', 'fingerprints'}` (lista). `ValueError` se não existir.
- `versao_mais_recente() -> int`. `ValueError` sem versões.
- `marcar_portao(n, tags)`: grava tags na versão registrada.

### 3.3 `src/ml/portao_mlflow.py` (novo)

```bash
venv/bin/python src/ml/portao_mlflow.py              # candidata = versão registrada mais recente
VERSAO=6 venv/bin/python src/ml/portao_mlflow.py     # candidata = versão 6
SIMULAR=1 VERSAO=4 venv/bin/python src/ml/portao_mlflow.py
```

1. Lê a candidata (`info_versao`) e a ativa (`ativa()`, ou nenhuma).
2. Candidata já é a ativa: imprime e sai sem gravar.
3. Sem ativa: decisão "primeira".
4. As duas definições precisam existir em `modelos.json`.
5. Mesma definição: `decidir_mesma_definicao` (não carrega dados).
6. Definições diferentes: os fingerprints da candidata precisam estar em `data/` (`core_carga.descobertos()`),
   senão para, porque o dado da candidata não pode ser reproduzido; carrega os quatro conjuntos com esses ids,
   `comparar` e `decidir`.
7. Grava: no run da candidata, `portao.json` (decisão, blocos por alvo, auxiliares dos dois runs, ativa contra
   quem comparou, data) e as tags `portao` (resultado), `portao_promovida` (sim/nao), `portao_contra` (número
   da ativa ou `nenhuma`), `portao_simulado` (sim/nao); na versão registrada, `portao` e `portao_contra`.
8. Promove (`ativar`) se a decisão mandar e não for simulação. Imprime o resultado, o motivo e o alias.

Erros de entrada saem com `SystemExit` e mensagem. O código de saída é 0 tanto para "promovida" quanto para
"mantida": a DAG lê o resultado no Registry.

## 4. Testes

- `test_portao.py` (novo): `decidir` (pior em um alvo, melhor sem pior, só empates), `decidir_mesma_definicao`
  (igual, superconjunto, outros dados) e `comparar` com os conjuntos sintéticos dos testes do Studio (quatro
  alvos, estrutura e vereditos válidos; definição contra ela mesma dá empate).
- `test_registry_mlflow.py`: `info_versao`, `versao_mais_recente`, `marcar_portao`.
- `test_portao_mlflow.py` (novo), banco temporário, carga de dados e `comparar` substituídos por mock: sem
  ativa promove; candidata ativa não grava; melhor promove e grava tags e `portao.json`; pior não promove;
  `SIMULAR=1` não move o alias; mesma definição com dado novo promove sem chamar `comparar`; fingerprint
  ausente para antes de carregar; padrão é a versão mais recente.

## 5. Conferência com dado real

Com a v5 (versão 5) ativa: `SIMULAR=1 VERSAO=4` (v4 contra v5) grava o veredito sem trocar; `VERSAO=5` diz que
já é a ativa. Depois, `VERSAO=1 venv/bin/python src/ml/ativar_mlflow.py` e `VERSAO=5 portao_mlflow.py`: o
portão decide v5 contra v1 nos mesmos dados. Se não promover, a ativa volta à mão para a 5. O alias termina na 5.

## 6. Fora do escopo

- A DAG do Airflow (item próprio); este comando é o passo que ela chama.
- Mudar o Studio: ele sai no fim e já não ativa versões.
- Usar o "atende" ou a régua por cômodo na decisão.

## 7. Documentação

README (comando e regra de decisão), CHANGELOG, inventário (passo 5 feito).
