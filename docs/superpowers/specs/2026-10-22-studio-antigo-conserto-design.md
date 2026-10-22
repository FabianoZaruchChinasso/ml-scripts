# Conserto do Studio atual: salvar versão, vazamento e assistente (design)

**Data:** 2026-10-22
**Base:** `master` (commit `68b8d86`).
**Status:** desenho aprovado em conversa. Parte B decidida com o Fabiano em 2026-10-22: fica como está (seção 4.3). Falta o plano de implementação da Parte A.

## 1. Contexto

Em 2026-10-21, ao tentar criar uma versão nova no Studio com o Fabiano, o botão ficou "gerando" e a versão não foi criada. A máquina dele estava sem o commit `68b8d86` (upload e reavaliação), mas o problema abaixo existe também com ele.

Uma reescrita do Studio integrada ao MLflow foi feita e guardada na branch `studio-novo` (commit `b5b384b`). Ela fica parada: perde o Laboratório, a régua com intervalos, quantis, eficiência e a cobertura TR-069, que o trabalho atual usa. Este documento conserta o Studio atual (`src/ml/studio/`).

## 2. Evidência (medida em 2026-10-22, conjunto padrão, 5 datasets)

1. **Salvar versão bloqueia a requisição.** `POST /api/modelos` chama `avaliacao_completa` antes de responder: 4 alvos com LOGO e intervalos, quantis de latência e jitter, `decisoes_atende` e `fatores_producao`. Com as 9 features da v1 sem vazamento, levou **81 s** nesta máquina. O front mostra o botão em "salvando" sem progresso. Recarregar a página no meio perde o retorno; se a conexão cair, nada indica se salvou.
2. **O assistente roda sozinho e disputa a CPU.** `modelo.js` chama `iniciarSugestoes()` ao carregar o registro, ao trocar a base, ao mudar o conjunto e ao terminar um salvamento (linhas 75, 213, 689, 695, 783). Cada chamada dispara `POST /api/assistente/sugestoes`, um job pesado em thread, que concorre com o salvamento.
3. **A versão ativa tem vazamento e trava quem parte dela.** A v1 (ativa) tem 5 colunas marcadas como vazamento em `column_provenance.json`: `router_rx_drop_misc`, `router_rx_duration_us`, `router_tx_duration_us`, `router_tx_failed`, `router_tx_retries` (contadores da janela do speedtest). O rascunho parte da ativa e herda essas colunas. `avaliacao_completa` passa todas para `core_avaliacao.avaliar`, que levanta `AssertionError: colunas com vazamento chegaram a um ajuste`. Salvar devolve 422 com essa frase, que não diz o que fazer. Reavaliar a v1 falha do mesmo jeito, e por isso o cartão dela mostra "– atende".
4. **Servidor com dados velhos.** O Studio na porta 8100 subiu às 08:44 de 2026-10-22 e ainda mostrava os datasets da villa que já tinham sido descartados. O Studio só relê `data/` e `predios.json` ao reiniciar (comportamento documentado em `api.py`). Não é defeito; vai como nota de uso.

## 3. Parte A: conserto (independe do Fabiano)

### A1. Salvar versão vira job com progresso

- `POST /api/modelos` faz na requisição só as validações rápidas que já faz hoje (tabela legível, nome novo, base existe, `validar_registro`) e a nova checagem de vazamento (A3). Qualquer recusa continua sendo 422 imediato.
- Passando, inicia um job com `_iniciar_job` (o mesmo da reavaliação) e devolve `{'id': ...}`. A tarefa roda `avaliacao_completa` e `core_modelos.salvar_versao`; se o pedido marcou "ativar", ativa no fim do mesmo job.
- `GET /api/modelos/salvar/{job_id}` devolve o job (`_job`), como `GET /api/modelos/reavaliar/{job_id}`.
- `avaliacao_completa` ganha `progresso=None` opcional e emite um evento por etapa: `{'etapa': 'download'|'upload'|'latência'|'jitter'|'atende', 'i': n, 'total': 5}`. A reavaliação passa a usar o mesmo callback, então o lote também mostra a etapa dentro de cada versão.
- Front (`modelo.js`): salvar acompanha o job a cada 1,5 s e mostra "Salvando v6: avaliando upload (2 de 5)". Ao terminar, recarrega o registro e mostra a mensagem que já existe. Em erro, mostra a mensagem do job.
- Recarregar a página no meio não cancela: o job termina e grava. Ao recarregar, a versão aparece quando estiver pronta. Não há retomada do acompanhamento (YAGNI).
- Dois salvamentos do mesmo nome: o segundo recebe 422 "a versão já existe" se o primeiro já gravou. Se o primeiro ainda roda, a chave do job é a mesma (`('salvar', nome, ...)`) e `_iniciar_job` devolve o job existente.

### A2. Assistente só quando pedido

- `iniciarSugestoes()` deixa de ser chamado automaticamente nos cinco pontos.
- A seção de sugestões ganha o botão **Sugerir features**, que chama `iniciarSugestoes(true)`. Antes de rodar, o texto diz quanto leva (o mesmo aviso de tempo do Laboratório).
- Resultado de sugestões continua guardado por `sugKey`; trocar conjunto ou base marca as sugestões como desatualizadas, sem rodar de novo.

### A3. Vazamento tratado antes, com mensagem útil

- **Rascunho:** ao partir de uma versão (`usarBase`), as colunas da versão que hoje estão marcadas como vazamento (`v.vazadas`, já presente na listagem) não entram no rascunho. Um aviso diz quais saíram e por quê: "contadores da janela do speedtest: carregam o próprio resultado".
- **Salvar:** se mesmo assim chegarem colunas com vazamento, o servidor recusa na requisição com 422: "estas colunas estão marcadas como vazamento e não podem entrar numa versão nova: [...]. Tire-as do rascunho." Nada de `AssertionError` crua.
- **Reavaliar versão antiga com vazamento:** versões são imutáveis, então a v1 continua listando as 14 features. A reavaliação passa a avaliar sem as colunas com vazamento (como `regression_benchmark.py` já faz: "features com vazamento fora da conta") e grava na avaliação `removidas_por_vazamento: [...]`. O cartão mostra "avaliada sem 5 com vazamento". Assim a v1 volta a ter número de "atende".

### A4. Nota de uso: reiniciar depois de mexer em `data/` fora do Studio

Uma linha no topo do painel Conjunto, só quando o servidor foi iniciado antes da última mudança em `data/` (mtime da pasta maior que a hora de início): "data/ mudou depois que o Studio subiu: reinicie para ver os dados atuais." Sem recarga automática.

## 4. Parte B: isolamento do benchmark (decisão do Fabiano)

### 4.1 A régua mudou o código do benchmark (já na `master`)

`regression_benchmark.py` comparado à última versão do Fabiano (`373fe13`, 2026-09-18); mudanças nos commits `7a81093` e `d806e96`:

| | Antes | Agora |
|---|---|---|
| Comando | `--csv a.csv,b.csv`, quaisquer arquivos | `--csv` dá erro; `--datasets` só com nomes de `data/`, padrão o conjunto canônico |
| Grupos | `--group-level position` (padrão, 7 grupos) | sempre prédio; argumento ignorado |
| Features padrão | lista fixa no script (14) | as da versão ativa em `modelos.json` |
| Vazamento | sem filtro | colunas marcadas em `column_provenance.json` saem (v1: 14 -> 9) |
| Linhas | só alvo vazio sai | também alvo = 0, sem stats de estação (328), teto de WAN (20), duplicatas |
| Alvo | Mbps | eficiência quando a versão tem denominador (v4, v5) |
| Saída | métricas por fold | + intervalos de 90%, R² pooled, MAE em log |

`core/data.py:load_datasets` passou a descartar alvo = 0 (afeta quem não usa a régua). `classification_benchmark.py` foi reescrito sobre a régua (`cf89ed2`, `9e96285`); o Fabiano já trabalhou sobre essa versão (`a2eec33`, matriz de confusão).

Consequência: números atuais do benchmark de regressão não são comparáveis aos anteriores, e o comando antigo não roda. Opções: manter a régua no benchmark; voltar `regression_benchmark.py` e `load_datasets` ao comportamento de `373fe13` (o classificador fica como está); ou manter os dois (o antigo como `regression_benchmark.py` e o da régua com outro nome).

### 4.2 O Studio grava o que o benchmark lê

O Studio grava em cinco lugares que `regression_benchmark.py` e `classification_benchmark.py` leem:

| Ação no Studio | Arquivo | Efeito no benchmark |
|---|---|---|
| Upload | `data/` | entra no conjunto canônico (`carga.discover` varre a pasta) |
| Cadastro de prédio | `core/predios.json` | muda o agrupamento por prédio |
| Classificar coluna, contadores | `core/column_provenance.json` | muda quais features o benchmark descarta por vazamento |
| Salvar, ativar, reavaliar versão | `core/modelos.json` | muda qual versão e quais features são avaliadas |
| Derivada | `core/derivadas.json` | muda as colunas disponíveis |

Isso foi desenhado assim (régua única, 2026-10-05). O benchmark de outra pessoa só muda quando essas alterações entram na `master` e ela atualiza.

Os caminhos desses arquivos são padrões fixados na definição das funções do `core` (`def carregar(path=MODELOS_PATH)`), e o próprio `core` os chama sem passar caminho. Separar Studio e benchmark exige mudar o `core` ou o benchmark, e por isso depende do Fabiano. Opções, a escolher com ele:

- **B0. Compartilhar (como hoje).** Nada muda no código. Combina-se o processo: mudanças nesses arquivos vão em commit próprio, com mensagem que diz o efeito no benchmark.
- **B1. Benchmark com entradas fixas.** O benchmark lê uma lista fixa de datasets e cópias congeladas de `predios.json`, `column_provenance.json` e `modelos.json` (por exemplo em `src/ml/benchmark/`). Atualizar é um ato explícito dele.
- **B2. Separar fatos de decisões.** Prédios e datasets são compartilhados (são fatos sobre a coleta). Versões e marcação de vazamento ficam só no Studio; o benchmark usa as listas dele.

### 4.3 Decisão (2026-10-22, com o Fabiano)

Fica como está: o benchmark mantém a régua, e os arquivos do `core` continuam compartilhados com o Studio (B0, sem mudança de código). A partir de agora, `regression_benchmark.py` e `classification_benchmark.py` não são mais alterados. A Parte A respeita isso: nada nela toca os dois scripts.

## 5. Erros

| Situação | Comportamento |
|---|---|
| Nome já existe, base inexistente, tabela ilegível, coluna com vazamento | 422 imediato, sem job |
| Falha durante a avaliação no job | job com status `erro` e a mensagem; nada é gravado em `modelos.json` |
| Salvou mas não ativou | mensagem que já existe: "salva, mas não foi possível ativar: ..." |
| Servidor reiniciou durante o job | `GET` do job devolve 404 "o servidor pode ter reiniciado"; a versão não foi gravada |

## 6. Testes

Seguindo `tests/test_studio_reavaliar.py`, que já testa a reavaliação chamando as rotas direto e trocando `avaliacao_completa` por mock:

- `POST /api/modelos` devolve `{'id'}`; o job grava a versão e, com "ativar", a ativa.
- Validações (nome repetido, base inexistente, coluna com vazamento) são 422 sem criar job.
- `avaliacao_completa` com `progresso` emite as 5 etapas na ordem.
- Reavaliar uma versão com colunas de vazamento termina e grava `removidas_por_vazamento`.
- Falha dentro do job deixa `modelos.json` como estava.
- JS (`tests/js/logica.test.js`): função pura que tira do rascunho as colunas com vazamento e devolve a lista do aviso.
- Manual: abrir a aba Modelo não dispara `api/assistente/sugestoes` (aba de rede do navegador); salvar uma versão mostra as etapas e termina.

## 7. Fora de escopo

- Parte B: decidida, sem código (4.3).
- `regression_benchmark.py` e `classification_benchmark.py`: não se alteram mais.
- Recarga automática de `data/`.
- Retomar o acompanhamento de um job depois de recarregar a página.
- Qualquer coisa do Studio novo (`studio-novo`).
