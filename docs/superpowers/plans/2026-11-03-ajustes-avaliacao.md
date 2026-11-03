# Ajustes antes da avaliação externa do modelo (2026-11-03)

Executar no Sonnet, nesta ordem. Não commitar nem dar push (o usuário faz). Não editar
`regression_benchmark.py` nem `classification_benchmark.py` (acordo com o Fabiano).

## Tarefa 1: testes "antigos" que falham

1. `tests/test_modelos_core.py::TestSemente.test_registro_do_repositorio`: tirar
   `assertNotIn('avaliacao', reg['versoes']['v1'])` (as versões são reavaliadas desde 2026-10-23) e trocar
   `assertEqual(reg['ativo'], 'v1')` por `assertEqual(reg['ativo'], 'v5')` (tarefa 2). Manter a checagem
   de que `v1` tem as features de `MODELO_ATUAL`.
2. `src/ml/core/column_provenance.json`: adicionar `"router_site_survey_ap": {"classe": "identificador"}`
   (JSON bruto do site survey, como `site_survey_strongest_ssid`; não é feature nem tem caminho TR-181).
   Fazer pela função do core (`core_features.gravar_classificacao`) se ela aceitar a classe sem TR-181;
   senão, editar o JSON mantendo a ordem alfabética. Conferir que `test_tabela_tr181_do_repositorio` passa.
   A versão da tabela muda: a avaliação guardada fica "desatualizada" no Studio, o que a tarefa 4 resolve.

## Tarefa 2: v5 vira a ativa

- Pelo caminho do Studio (`POST /api/modelos/ativo` ou a função do core que ele chama), para o
  histórico registrar a troca. v5 tem cobertura "proxy" (n_clients e concorrentes_mesmo_radio), que é
  aceita para ativar.
- Efeito colateral a registrar no CHANGELOG: `regression_benchmark.py`, `classification_benchmark.py`,
  `compare_protocols.py`, `regression_mlflow.py`, `qoe_mlflow.py` e `comodo_benchmark.py` usam
  `registro['ativo']` como padrão; depois do push o benchmark do Fabiano passa a rodar a v5 por padrão.

## Tarefa 3: "apto para jogo"

Causa (CHANGELOG 2026-10-29): a verdade é o p90 de jitter e de latência da posição; a previsão é a
mediana do q90 por linha **com CQR**, que é um limite conservador por linha (jitter previsto mínimo de
13 a 15 ms contra o limite de 10 ms). Resultado: ninguém é previsto apto, e a nota fica em 0,500.

1. Medir antes de mudar, num script no scratchpad, nas 27 posições e nas 5 versões, a acurácia
   balanceada do apto com: (a) q90 com CQR (atual), (b) q90 sem CQR (`expm1(log1p(q90) - correcao)`,
   as colunas `q90` e `correcao` já saem de `quantis.prever_quantis_fora_do_fold`), (c) q50. Medir
   também a nota das 3 classes com (b) usado em todas as comparações de latência e jitter.
   Referência anterior (só v3): (b) 0,644, (c) 0,588.
2. Portão: seguir só se (b) passar de 0,5 com folga em todas as versões e não piorar a nota das 3 classes.
   Se não passar, parar e relatar.
3. `core/comodo.py`: `de_previsoes` e `prever` passam a usar o q90 sem CQR para `lat` e `jit` (mesma
   estatística para Navegação, Chamada e Jogo). Subir `VERSAO_COMODO` para `2026-11-03.1`. No `bloco`, um
   campo `jogo`: {nota, intervalo, piso: {nota, intervalo}} (`nota_jogo` com as mesmas reamostras).
   Teste novo em `tests/test_comodo.py` para o q90 sem CQR e para o campo `jogo`.
4. Studio: mostrar "Apto para jogo" como KPI informativo no bloco "Cômodo" do Assistente (rascunho,
   ativa e piso); não entra na ativação. `avaliar_comodo` devolve `jogo`. Ajustar `tests/test_studio_comodo.py`.
5. Escrever no CHANGELOG que o estimador foi escolhido depois de olhar estas 27 posições e que a verdade
   do apto é instável (8 de 27 posições trocam de lado em mais de 10% das reamostras de linhas).

## Tarefa 4: limpeza e reavaliação

1. `studio/api.py::_dados_mudaram`: limpar também `_piso_comodo_cache`; teste em `test_studio_comodo.py`.
2. Reavaliar v1 a v5 pelo caminho do Studio (`modelos_reavaliar` / `avaliacao_completa`) com o conjunto
   padrão (7 datasets). Rodar em segundo plano, uma versão por vez (duas em paralelo passaram de 10 min).
3. Conferir: as 5 versões com o mesmo `versao_comodo`, as mesmas 27 posições e o mesmo piso; um rascunho
   igual à v5 dá diferença 0 contra a v5 guardada.
4. Suíte completa (`venv/bin/python -m unittest discover -s tests`) sem falhas e `node --test tests/js/logica.test.js`.
5. CHANGELOG: entrada nova com as tarefas 1 a 4, a tabela nova por versão (cômodo e apto) e a verificação real.

## Tarefa 5: MLflow

Depois da tarefa 4, com a v5 ativa: `regression_mlflow.py` para os quatro alvos (`ALVO=...`) e
`qoe_mlflow.py`. O último run é de 2026-10-07 (sem Villa, sem v5) e o experimento de QoE nunca rodou.
`mlflow.db` e `mlruns/` são ignorados pelo git: o resultado fica só nesta máquina.
