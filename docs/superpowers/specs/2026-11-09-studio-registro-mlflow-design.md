# Studio: registro automático no MLflow

**Data:** 2026-11-09
**Origem:** reunião AI + TR-069 de 2026-11-04, tarefa "migração ou ajuste das ferramentas de estúdio para ML Flow".

## 1. Problema

O Studio grava as versões e as avaliações delas só em `src/ml/core/modelos.json`. O MLflow ("MLflow Wifi
Studio") recebe esses números apenas quando alguém roda `src/ml/studio_mlflow.py` à mão. Consequências:

- uma versão salva ou reavaliada no Studio não aparece no MLflow até alguém lembrar de rodar o script;
- rodar o script duas vezes duplica os runs (hoje: 10 runs para 5 versões, sem como saber qual é o atual);
- `ativo` é gravado como parâmetro, que o MLflow não deixa mudar: depois de trocar a versão ativa, os runs
  antigos continuam dizendo `ativo=True`;
- o destino do registro depende da pasta de onde o processo foi iniciado (`sqlite:///mlflow.db` relativo).

## 2. Objetivo

Toda ação do Studio que muda o que o MLflow deveria mostrar passa a registrar sozinha:

| Ação no Studio | O que acontece no MLflow |
|---|---|
| Salvar versão nova (`POST /api/modelos`) | run novo `<nome>-studio`, `evento=salvar`; se a versão também for ativada, troca a tag `ativo` |
| Reavaliar (`POST /api/modelos/reavaliar`) | um run novo por versão reavaliada, `evento=reavaliar` |
| Ativar (`POST /api/modelos/ativo`) | nenhum run novo; `ativo=sim` nos runs da versão ativada e `ativo=nao` nos das outras |

Critérios de sucesso:

1. Salvar, reavaliar e ativar no Studio deixam o MLflow coerente sem passo manual.
2. Uma falha do MLflow nunca impede gravar no `modelos.json`; o usuário vê um aviso com o motivo.
3. No MLflow, `tags.atual = 'sim'` filtra exatamente um run por versão (o mais recente) e `tags.ativo = 'sim'`
   mostra só os runs da versão ativa. Os 10 runs que já existem não têm tags; o critério vale depois de uma
   rodada de `studio_mlflow.py` (passo final do plano), que dá a cada versão um run `atual=sim`.
4. Nenhum teste grava no `mlflow.db` da raiz do repositório.

Fora do escopo: registrar os modelos treinados (o MLflow do Studio continua sem modelos, como o snapshot de
`res/mlflow/`); atualizar o snapshot versionado `res/mlflow/` (continua à mão); os experimentos
"MLflow Wifi Regressions", "MLflow Wifi QoE" e "MLflow Wifi Experimentos"; os benchmarks congelados
(`regression_benchmark.py`, `classification_benchmark.py`), que não mudam.

## 3. Abordagem

Módulo novo `src/ml/core/registro_mlflow.py`, chamado pelo Studio (`src/ml/studio/api.py`) e pelo script
`studio_mlflow.py`. O registro **não** entra em `core/modelos.py`: esse módulo é usado pelos benchmarks
congelados do Fabiano e por muitos testes, e todos passariam a gravar no MLflow.

Descartadas: registrar dentro de `core/modelos.py` (motivo acima); fila de pendências em arquivo (o caso
"MLflow fora do ar" já fica coberto pelo aviso + script de recuperação).

## 4. Desenho

### 4.1 `core/registro_mlflow.py`

Constantes: `EXPERIMENTO = 'MLflow Wifi Studio'`, `RAIZ` (raiz do repositório, calculada a partir de
`__file__`).

- `uri_rastreamento() -> str`: `os.environ['MLFLOW_TRACKING_URI']` se existir; senão
  `'sqlite:///' + <RAIZ>/mlflow.db` com caminho absoluto.
- `cliente() -> MlflowClient`: cliente com `uri_rastreamento()`. Usa `MlflowClient` direto, sem
  `mlflow.start_run`/`mlflow.set_experiment`, porque essas funções guardam estado global por processo e
  por thread, e os jobs do Studio rodam em threads. O `import mlflow` é feito dentro das funções: importar o
  `api.py` não fica mais lento e, com o pacote quebrado, o Studio sobe e só o registro falha (com aviso).
- Experimento novo é criado com `artifact_location` ao lado do banco (`<pasta do .db>/mlruns/studio`):
  sem isso o MLflow usa `./mlruns` relativo à pasta atual, e um teste com banco temporário gravaria os
  artefatos no `mlruns/` da raiz.
- `parametros_e_metricas(nome, versao) -> (params, metricas)`: movida de `studio_mlflow.py` sem mudança de
  conteúdo, exceto que `ativo` sai dos parâmetros (vira tag, 4.2).
- `registrar_avaliacao(nome, versao, evento, ativo: bool) -> str`: cria o experimento se não
  existir, cria o run `<nome>-studio` com parâmetros, métricas, tags (4.2) e os artefatos `avaliacao.json` e
  `posicoes.json` (os mesmos de hoje); termina o run como `FINISHED`; depois põe `atual=nao` nos outros runs
  da mesma versão. Devolve o `run_id`. `evento` em `{'salvar', 'reavaliar', 'script'}`; outro valor levanta
  `ValueError`.
- `marcar_ativo(nome) -> int`: em todos os runs do experimento, `ativo=sim` se o run é da versão
  `nome`, `ativo=nao` nos demais. Devolve quantos runs foram marcados como ativos.

A versão de um run é lida da tag `modelo` e, se faltar (runs antigos, gravados pelo script atual), do
parâmetro `modelo`. Assim os 10 runs que já existem entram na marcação de `ativo` e de `atual`.

### 4.2 Tags de cada run

| Tag | Valor |
|---|---|
| `modelo` | nome da versão |
| `evento` | `salvar`, `reavaliar` ou `script` |
| `atual` | `sim` no run mais recente da versão; `nao` nos anteriores |
| `ativo` | `sim` se a versão é a ativa no momento do registro (atualizada por `marcar_ativo`) |
| `versao_comodo` | `avaliacao.comodo.versao_comodo` (omitida se ausente) |
| `mlflow.source.git.commit` | `HEAD` do repositório no momento do registro (omitida sem git) |
| `git_arvore` | `limpa` ou `suja` (arquivos rastreados com mudança): logo depois de salvar é sempre `suja`, porque a versão nova só existe no `modelos.json` ainda não commitado; o commit sozinho não reproduz o run |

Os parâmetros continuam os de hoje menos `ativo`. O histórico fica no MLflow: reavaliar não apaga o run
anterior, só tira dele o `atual=sim`. `registrar_avaliacao` e `marcar_ativo` rodam sob uma trava do
processo: sem ela, dois registros simultâneos da mesma versão leem a mesma lista de anteriores e os dois
ficam `atual=sim` (medido em 2026-11-09). A trava não protege contra outro processo (o script rodando junto
com o Studio); nesse caso raro, rodar o script de novo conserta.

### 4.3 Studio (`studio/api.py`)

Função interna `_registrar_mlflow(acao) -> Optional[str]`: roda `acao()` e devolve `None`, ou, se qualquer
exceção ocorrer, `'não registrou no MLflow: <motivo>'`, com só a primeira linha da mensagem, cortada em 200
caracteres (o erro de banco travado do SQLAlchemy traz a consulta SQL inteira). Nunca propaga a exceção.
Banco travado: o MLflow força `PRAGMA busy_timeout = 20000` em toda sessão, então o aviso só vem depois de
20 s; um `timeout` na URI não muda isso (medido em 2026-11-09). Num uso normal o lock dura milissegundos.

- **Salvar**, dentro da `tarefa` do job, depois de `salvar_versao` (e de `definir_ativo`, se `ativar`):
  `registrar_avaliacao(nome, versao_gravada, 'salvar', ativo=<ativada com sucesso>)`; se ativada com sucesso,
  também `marcar_ativo(nome)`, numa chamada à parte (roda mesmo se o registro falhar, para a tag `ativo` sair
  da versão anterior). A `versao_gravada` é a que `salvar_versao` devolve. O resultado do job ganha
  `aviso_mlflow` (`None` ou os avisos das duas chamadas, separados por `; `).
- **Reavaliar**, depois de cada `core_modelos.reavaliar`: `registrar_avaliacao(nome, versao_regravada,
  'reavaliar', ativo=nome == ativo_atual)`. Os avisos são acumulados; o resultado do job ganha
  `avisos_mlflow: [{'nome': ..., 'aviso': ...}]` (lista vazia quando tudo registrou). Uma falha do MLflow não
  interrompe o lote. Se o lote parar por falha na avaliação, a mensagem de erro do job inclui os avisos do
  MLflow das versões que já tinham terminado.
- **Ativar** (`POST /api/modelos/ativo`), depois de `definir_ativo` dar certo: `marcar_ativo(nome)`. A
  resposta continua sendo `modelos_listar()`, com a chave `aviso_mlflow` acrescentada.

O registro roda dentro do job, já em thread própria; leva cerca de 1 a 2 s com sqlite, pouco perto do 1 a 2
min da avaliação completa.

### 4.4 Front (`studio/static/modelo.js`)

Onde hoje aparece `erro_ativar` depois de salvar, aparece também `aviso_mlflow`; depois de reavaliar, cada
item de `avisos_mlflow`; depois de ativar, o `aviso_mlflow` da resposta. Mesmo estilo de aviso já usado, sem
emoji. O texto termina com: "rode `venv/bin/python src/ml/studio_mlflow.py` para registrar de novo".

### 4.5 Script `studio_mlflow.py`

Passa a ser só a recuperação manual: para cada versão (ou só `MODELO=<nome>`),
`registrar_avaliacao(nome, versao, 'script', ativo=nome == ativa)`; ao fim, `marcar_ativo(ativa)`. A
docstring muda para dizer isso. `parametros_e_metricas` e `registrar_versao` deixam de existir no script;
quem as usa passa a importar de `core/registro_mlflow.py`.

## 5. Erros

| Situação | Comportamento |
|---|---|
| MLflow fora do ar, banco travado, pacote quebrado | versão gravada no `modelos.json`; aviso no Studio; script recupera depois |
| Avaliação sem bloco `comodo` | registra o que houver (como hoje); sem tag `versao_comodo` |
| `evento` inválido | `ValueError` (erro de programação, aparece no aviso) |
| Run antigo sem tag `modelo` | versão lida do parâmetro `modelo` |
| Run sem tag nem parâmetro `modelo` | ignorado por `marcar_ativo` e pela troca de `atual` |

## 6. Testes

- `tests/test_registro_mlflow.py` (novo), com sqlite temporário via `MLFLOW_TRACKING_URI`:
  - `uri_rastreamento`: com e sem a variável; sem ela, caminho absoluto terminando em `/mlflow.db` na raiz.
  - parâmetros e métricas (os casos de hoje de `test_studio_mlflow.py`, movidos), sem `ativo` nos parâmetros.
  - `registrar_avaliacao`: tags e artefatos; segundo registro da mesma versão deixa só o novo com `atual=sim`;
    `evento` inválido levanta `ValueError`.
  - `marcar_ativo`: troca entre duas versões; run antigo só com parâmetro `modelo` também é marcado.
- Testes da API (no arquivo de testes do Studio que já cobre salvar/reavaliar/ativar): salvar, reavaliar e
  ativar registram no sqlite temporário; com o registro forçado a falhar, a versão é gravada e o aviso vem no
  resultado.
- Isolamento: todo teste que passa por salvar, reavaliar ou ativar no Studio aponta `MLFLOW_TRACKING_URI`
  para uma pasta temporária ou troca `api.core_registro_mlflow` por um mock (são `test_studio_salvar.py`,
  `test_studio_reavaliar.py` e `test_studio_assistente.py`). Um teste de guarda varre `tests/*.py`: todo arquivo
  que chama `modelos_salvar(`, `modelos_reavaliar(` ou `modelos_ativo(` precisa citar `core_registro_mlflow`.
- `tests/test_studio_mlflow.py`: ajustado ao script novo (ou absorvido pelo arquivo novo).
- JS: se a exibição do aviso entrar em `logica.js`, teste em `tests/js/logica.test.js`.

## 7. Documentação

- `README.md`, seção MLflow: o Studio registra sozinho ao salvar, reavaliar e ativar; `studio_mlflow.py`
  serve para recuperar; filtros úteis no MLflow (`tags.atual = 'sim'`, `tags.ativo = 'sim'`).
- `CHANGELOG.md`: entrada nova.
