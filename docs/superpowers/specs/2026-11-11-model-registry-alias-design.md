# Model Registry e alias do modelo ativo

**Data:** 2026-11-11
**Origem:** item "Model Registry e alias do modelo ativo" da planilha "Anomalias de Rede - Backlog e
Estimativas", com os ajustes da revisão de 2026-11-11. Passo 4 da ordem do inventário
(`docs/pipeline/2026-11-10-inventario-studio-mlflow.md`). Vem depois de `versao_mlflow.py`
(spec `2026-11-10-versao-mlflow-design.md`) e antes do portão de promoção.

## 1. Problema

- A versão ativa é o campo `ativo` de `src/ml/core/modelos.json`. O MLflow não sabe qual é: a tag `ativo` dos
  runs do Studio é uma cópia mantida à mão por `registro_mlflow.marcar_ativo`.
- O run de `versao_mlflow.py` grava o pacote (modelo pyfunc), mas nada o registra no Model Registry. Não há
  como servir "o modelo ativo" (`models:/<nome>@<alias>`), que é o que a API e o portão vão precisar.
- O nome "v5" quer dizer duas coisas: a definição (features, denominador, perfil) e o modelo treinado com ela.
  Quando a coleta voltar, a v5 será treinada de novo com mais dados, e as duas coisas se separam.
- O monitoramento vai comparar as entradas recebidas pela API com as do treino, mas o run guarda só o esquema
  e o digest do dado (`mlflow.log_input`), não os valores.

## 2. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Fonte da versão ativa | Só o alias do Registry. O campo `ativo` sai do `modelos.json` | Uma fonte só; o portão de promoção move o alias |
| Máquina sem Registry (o MLflow é local e fica fora do git) | Os scripts pedem `MODELO=` ou `--modelo` e param com mensagem clara | Sem chute e sem cópia no git |
| Studio até ser desligado | Lê o alias; o botão "Tornar ativa" e a opção "ativar ao salvar" saem | Um caminho de promoção só (o portão) |
| Benchmarks (`regression_benchmark.py`, `classification_benchmark.py`) | Mudam como os outros scripts | Congelamento suspenso em 2026-11-11 |
| Referência do monitoramento | As entradas do treino em `referencia_entradas.parquet` no run | O teste de desvio fica livre para ser escolhido depois, sem retreinar |
| Registro | Todo run de `versao_mlflow.py` vira uma versão registrada; o alias não se move sozinho | Quem promove é o comando `ativar_mlflow.py` (agora) e o portão (depois) |

Nomes: o modelo registrado chama-se **`qoe-wifi`**; o alias, **`ativo`**. "Definição" é a entrada de
`modelos.json` (v1, v2-tr069, ..., v5); "versão registrada" é o número do Registry (1, 2, 3...). Cada versão
registrada leva a tag `definicao`.

## 3. Componentes

### 3.1 `src/ml/core/registry_mlflow.py` (novo)

Única porta para o Registry. Não importa o Studio.

- `NOME_MODELO = 'qoe-wifi'`, `ALIAS = 'ativo'`.
- `class SemVersaoAtiva(RuntimeError)`: não há banco, não há modelo registrado ou não há alias. A mensagem diz
  como resolver (passar `MODELO=`, ou rodar `ativar_mlflow.py`).
- `registrar(model_uri, definicao, fingerprints, versao_pacote) -> int`: cria uma versão de `qoe-wifi` com as
  tags `definicao`, `fingerprints` e `versao_pacote`; devolve o número.
- `versao_da_definicao(definicao) -> int`: a versão registrada mais recente com essa definição. `ValueError`
  se não houver.
- `ativa() -> dict`: `{'versao', 'definicao', 'run_id'}` da versão apontada pelo alias. `SemVersaoAtiva` se
  faltar algo. Se a URI for `sqlite:///` e o arquivo não existir, levanta `SemVersaoAtiva` **sem** criar o banco
  (na máquina de outra pessoa, ler não pode deixar um `mlflow.db` vazio para trás).
- `definicao_ativa() -> Optional[str]`: a definição do alias, ou `None` quando `ativa()` levantaria
  `SemVersaoAtiva`. Para quem só marca "(ativa)" num texto, e para o Studio.
- `ativar(versao) -> dict`: move o alias; devolve `{'anterior', 'atual', 'definicao_anterior',
  'definicao_atual'}` (`anterior` e `definicao_anterior` são `None` quando não havia alias). `ValueError` se a
  versão não existir.
- `escolher_definicao(explicita, registro) -> str`: `explicita` se vier; senão a definição do alias. Sai com
  `SystemExit` e mensagem clara se não houver alias ou se a definição não existir em `modelos.json`. É o que os
  8 scripts chamam.

A URI é a de `registro_mlflow.uri_rastreamento()` (variável `MLFLOW_TRACKING_URI` ou `mlflow.db` da raiz).
`MlflowException` com `RESOURCE_DOES_NOT_EXIST` (modelo não existe) e `INVALID_PARAMETER_VALUE` (alias não existe)
viram `SemVersaoAtiva`; as demais sobem. Os aliases são lidos de `get_registered_model(...).aliases`, porque
`search_model_versions` volta com `aliases` vazio no MLflow 3.15.1 (conferido em protótipo).

### 3.2 `src/ml/versao_mlflow.py`

- `MODELO=` continua opcional: sem ele, usa `escolher_definicao(None, registro)`.
- Grava `referencia_entradas.parquet`: `base.df[receita['entradas']]` do conjunto de download (o mesmo que já vai
  para `log_input`), sem alvos e sem índice.
- Depois de gravar e conferir o pacote, registra a versão (`registry_mlflow.registrar`) e põe no run a tag
  `versao_registrada=<n>`. Não move o alias. Se o registro falhar, o run termina FAILED, como já acontece com a
  falha do pacote.
- Imprime o número da versão registrada e o comando para ativá-la.

### 3.3 `src/ml/ativar_mlflow.py` (novo)

Promoção manual até o portão existir:

```bash
venv/bin/python src/ml/ativar_mlflow.py            # mostra a ativa
MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py  # ativa a versão registrada mais recente da v5
VERSAO=3 venv/bin/python src/ml/ativar_mlflow.py   # ativa a versão registrada 3
```

`MODELO` e `VERSAO` juntos é erro. Imprime "anterior -> atual" com a definição de cada uma.

### 3.4 `src/ml/core/modelos.py` e `modelos.json`

- `modelos.json` passa a ter só `versoes`.
- `validar_registro` exige exatamente a chave `versoes`. Se vier `ativo`, recusa com a mensagem "o campo ativo
  saiu do modelos.json em 2026-11-11: a versão ativa é o alias 'ativo' do Model Registry (src/ml/ativar_mlflow.py)".
- Saem `ativo(registro)` e `definir_ativo`. Entra `features_de(registro, nome) -> list`.

### 3.5 `src/ml/core/registro_mlflow.py` (runs do Studio)

- `registrar_avaliacao` perde o parâmetro `ativo` e a tag `ativo`.
- `marcar_ativo` sai.
- Na migração, a tag `ativo` é apagada dos runs antigos do experimento "MLflow Wifi Studio", para a interface do
  MLflow não mostrar uma ativa velha.

### 3.6 Os scripts que liam `registro['ativo']`

`qoe_mlflow.py`, `regression_mlflow.py`, `compare_protocols.py`, `classification_benchmark.py`,
`regression_benchmark.py`, `comodo_benchmark.py`, `studio_mlflow.py` e `versao_mlflow.py` passam a usar
`escolher_definicao`. Onde o script só marcava "(ativa)" num texto, a marca vem de `ativa()` e some, sem erro,
se não houver alias. `comodo_benchmark.py` sem `MODELO` roda todas as definições e inclui a ativa só se houver
alias. `studio_mlflow.py` deixa de marcar runs.

### 3.7 Studio

- `api.py` ganha `_ativa() -> Optional[str]`: a definição do alias, ou `None` (sem alias, ou alias apontando
  para definição que não está mais em `modelos.json`). `/api/modelos` devolve `ativo: None` nesse caso, com
  um texto em `erro`.
- Onde o código usava `base or registro['ativo']`, passa a usar `_base(base)`: `base` se vier; senão a ativa;
  sem nenhuma das duas, HTTP 409 "sem versão ativa no Model Registry: escolha a versão base".
- `core_modelos.ativo(registro)` vira `core_modelos.features_de(registro, _base(None))`.
- Saem a rota `POST /api/modelos/ativo`, o modelo `Ativo`, o campo `ativar` do corpo de salvar e as chamadas
  a `definir_ativo` e `marcar_ativo`. A resposta de salvar perde `ativa` e `erro_ativar`.
- `_registro()` (reserva quando `modelos.json` está ilegível) deixa de pôr `ativo`.
- JS: saem o item "Tornar ativa" do menu de versão, o `U.post('api/modelos/ativo')` e a opção de ativar no
  formulário de salvar. Onde se lê `st.reg.ativo`, um `null` não pode quebrar a tela: a base inicial cai na
  última versão, e os textos "contra <ativa>" usam a base escolhida.

## 4. Migração (dado real, cerca de 35 min de máquina)

1. Com o código novo, para cada definição em ordem (v1, v2-tr069, v3-tr069, v4, v5):
   `MODELO=<def> venv/bin/python src/ml/versao_mlflow.py`. Saem as versões registradas 1 a 5.
2. `MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py` (a v5 é a ativa hoje).
3. Apagar a tag `ativo` dos runs de "MLflow Wifi Studio".
4. Conferir: `ativar_mlflow.py` sem argumentos mostra v5; o Studio abre com v5 como ativa; as métricas do run
   novo da v5 batem com o run 9b7a4ece25884f3bb164fd7f06986923 (mesma avaliação, nas 17 métricas de
   referência do item anterior); `models:/qoe-wifi@ativo` carrega e prevê as 5 linhas do exemplo.

A remoção de `ativo` do `modelos.json` vai no mesmo commit que o código que deixa de lê-lo.

## 5. Testes

- `tests/test_registry_mlflow.py` (novo), com banco SQLite temporário: registrar, tags, versão mais recente
  por definição, ativar e anterior, `ativa()` sem banco (e sem criar o arquivo), sem modelo, sem alias,
  `escolher_definicao` com explícita, com alias, sem alias e com definição inexistente.
- `test_versao_mlflow.py`: o run tem `referencia_entradas.parquet` com as colunas da receita e o mesmo número de
  linhas; tem a tag `versao_registrada`; a versão registrada tem as tags; o alias não se move; falha no registro
  deixa o run FAILED; `main` sem `MODELO` usa o alias e sai com mensagem clara sem ele.
- `test_ativar_mlflow.py` (novo): mostrar, ativar por definição, por número, os dois juntos dá erro.
- `test_modelos_core.py`: registro sem `ativo` passa; com `ativo` é recusado com a mensagem nova;
  `features_de`.
- `test_registro_mlflow.py` e os `test_studio_*`: fixtures sem `ativo`; `_ativa` substituída por mock; a rota
  `/api/modelos/ativo` responde 404/405; salvar não aceita `ativar`; base ausente sem alias dá 409.
- A suíte inteira roda no fim (cerca de 5 min; se for morta por falta de memória, rodar de novo sozinha).

## 6. Fora do escopo

- Portão de promoção (próximo item): vai usar `registry_mlflow.ativar`.
- Teste de desvio e limiar: item do monitoramento, que lê `referencia_entradas.parquet` da versão ativa.
- Servidor MLflow compartilhado. Enquanto o MLflow for local, quem não tem o banco passa `MODELO=`/`--modelo`
  (o Fabiano precisa saber disso antes de rodar os benchmarks depois do merge).
- Apagar o Studio.

## 7. Documentação

README (seção do MLflow: Registry, alias, `ativar_mlflow.py`, `MODELO=` obrigatório sem Registry), CHANGELOG,
docstring de `versao_mlflow.py`, inventário (passo 4 feito; "Ativar versão" e "Lista de versões" no Registry).
