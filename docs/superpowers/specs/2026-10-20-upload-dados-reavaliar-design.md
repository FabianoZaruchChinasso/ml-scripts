# QoE Studio: dados novos pela interface e reavaliação de versões (design)

**Data:** 2026-10-20
**Estado:** desenho aprovado em conversa, para revisão do usuário. Falta o plano de implementação.

## 1. Objetivo

Incluir os dados de uma casa nova (o caso que motivou: a casa do Villa) hoje exige três passos fora do Studio e um que confunde:

1. copiar o CSV ou zip para `data/` à mão;
2. se o `local` usa um prefixo novo, editar `core/sites.py` e `studio/data.py`, senão a linha é descartada ou o Studio levanta erro;
3. para a casa nova aparecer na avaliação guardada em `modelos.json`, **criar uma versão nova**, porque a versão salva é imutável por inteiro.

Quem usa o Studio esperava que o `modelos.json` fosse "atualizado com os dados". Esta spec faz isso acontecer pela interface: upload com prévia, cadastro de prédio na mesma tela e reavaliação das versões existentes sem criar versão nova.

## 2. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Onde ficam os prédios | `src/ml/core/predios.json` é a **fonte única** (opção A). Os quatro prédios atuais migram; `sites.py` lê dele; `studio/data.py` deixa de ter `BUILDINGS` e `PREDIO_DO_CORE` próprios |
| `local` desconhecido no upload | **Cadastrar pela tela**: a prévia agrupa os valores por prefixo e pede chave, rótulo, ambiente e prefixo |
| Upload | **Prévia e confirmação**: nada vai para `data/` antes do clique em confirmar |
| Reavaliar | **Botão por versão e em lote** ("Reavaliar N desatualizadas"). Nunca automático |
| Imutabilidade | Features, denominador, descrição, origem, seleção e data de criação continuam imutáveis. **Avaliação e cobertura viram relatório recalculável**, com rastro no `historico` |
| Fora do escopo | Associar prefixo novo a prédio existente, apagar ou renomear dataset, desenhar planta no fluxo do upload |

## 3. Prédios em `predios.json`

### 3.1 Formato

```json
{
  "predios": {
    "residencia": {
      "rotulo": "Casa", "studio": "casa", "ambiente": "domestico",
      "prefixos": [],
      "posicoes": {"1": "res-sala", "sala": "res-sala", "2": "res-quarto", "quarto": "res-quarto",
                   "3": "res-suite", "suite": "res-suite"},
      "tetos_wan": {"speedtest_down_mbps": 154.0, "speedtest_up_mbps": 99.0}
    },
    "coworking":    {"rotulo": "Cowork Pedra Branca", "studio": "cowork-pedra-branca",
                     "ambiente": "corporativo", "prefixos": ["cwpb"]},
    "hotmilk":      {"rotulo": "Hotmilk", "studio": "hotmilk", "ambiente": "corporativo",
                     "prefixos": ["hotmilk"]},
    "casa-marcelo": {"rotulo": "Casa do Marcelo", "studio": "casa-marcelo", "ambiente": "domestico",
                     "prefixos": ["marcelo"]}
  },
  "aliases": {"quarto-marcelo": "hotmilk-aquario"}
}
```

- A chave de `predios` é o id do core (`residencia`, `coworking`...), o mesmo que aparece em `avaliacao` por prédio no `modelos.json`.
- `studio` é a chave usada pelo Studio e por `docs/planta/plantas.json`. Só a residência difere do id do core (`casa`). Prédio novo cadastrado pela tela usa a mesma chave nos dois.
- `posicoes` (opcional) mapeia valores exatos de `local` para o id de posição. Hoje só a residência usa.
- `tetos_wan` (opcional): prédio sem o campo não tem teto conhecido, como hoje.
- `aliases` vale para todos os prédios e é aplicado antes da resolução, como `POSITION_ALIASES` hoje.

### 3.2 Resolução

A ordem de `_resolve_one` não muda: canonicaliza o valor, aplica `aliases`, depois testa os prefixos de cada prédio (`startswith`) e depois as `posicoes`. Um valor que não resolve continua levantando o mesmo erro, e `carga.py` continua descartando essas linhas com aviso. O cadastro pela tela é o único caminho para um prefixo novo virar prédio.

### 3.3 API do `sites.py`

A API pública fica igual: `resolve_site_id`, `resolve_environment`, `teto_wan`, `BUILDING_ENVIRONMENT`, `DOMESTIC`, `CORPORATE`, `ENVIRONMENTS`, `GROUP_LEVELS`. As constantes de prédio (`RESIDENCE_BUILDING`, `MARCELO_PREFIX` etc.) saem; quem usa passa a usar o id literal ou o registro.

`BUILDING_ENVIRONMENT` é importado por nome em `carga.py`, `studio/api.py` e nos testes. Por isso o recarregamento **muta o dicionário no lugar** (`clear()` + `update()`), nunca o reatribui. O mesmo vale para `TETOS_WAN`.

Funções novas:

- `carregar_predios(path=PREDIOS_PATH) -> dict`: lê e valida.
- `validar_predios(registro) -> None`: levanta `ValueError` com mensagem legível.
- `recarregar() -> None`: relê o arquivo, atualiza os dicionários no lugar e limpa os caches de resolução.
- `cadastrar_predios(novos: list[dict], path=PREDIOS_PATH) -> dict`: acrescenta prédios com lock e gravação atômica (`gravar_json_atomico`), valida o registro inteiro antes de gravar, recusa chave existente e chama `recarregar()`.

### 3.4 Validação

- Chave: mesma regra de nome de `modelos.py` (`^[a-z0-9][a-z0-9-]{1,39}$`), sem repetição.
- `studio`: mesma regra, sem repetição entre prédios.
- `ambiente` ∈ `ENVIRONMENTS`.
- `rotulo`: texto não vazio, até 60 caracteres.
- Prefixos: minúsculas, dígitos e hífen. **Nenhum prefixo pode ser igual a outro nem começar com outro**, no mesmo prédio ou entre prédios (`marcelo` e `marcelo2` conflitam, porque `startswith` tornaria a resolução dependente da ordem).
- Nenhuma chave de `posicoes` ou de `aliases` pode começar com um prefixo cadastrado.
- Prédio sem `prefixos` precisa ter `posicoes`.

### 3.5 Studio

`studio/data.py` troca `BUILDINGS` e `PREDIO_DO_CORE` por funções que leem o registro de `sites.py` (`predios_studio()` → `{chave_studio: {label, ambiente}}`, `predio_studio_do_core(id)`). O `lru_cache` de `_building_de_texto` é limpo por `recarregar()`. `studio/api.py:767` (`if predio not in BUILDINGS`) passa a usar `predios_studio()`.

Prédio novo nasce sem planta. `plans.montar_plantas` já trata prédio sem entrada em `plantas.json`, e a área Dados mostra a matriz normalmente.

## 4. Upload com prévia

### 4.1 Interface

No painel **Conjunto** (`conjunto.js`), acima da lista de datasets, entra o botão **Adicionar dados** com um seletor de arquivo (`.csv`, `.zip`). Depois de escolher:

1. A prévia aparece no próprio painel.
2. O campo **nome do arquivo** vem preenchido com o nome original e pode ser editado.
3. Para cada grupo de `local` desconhecido aparece um formulário de prédio novo.
4. **Confirmar** fica desabilitado enquanto houver bloqueio; os bloqueios aparecem em lista acima do botão.
5. **Cancelar** descarta a prévia.

Depois de confirmar, o Studio recarrega o payload, o dataset novo vem **ligado** e a mensagem diz: "`<nome>` adicionado em data/ e `<n>` prédio(s) em src/ml/core/predios.json. Revise no git diff antes do commit." Se alguma versão ficou desatualizada, a mensagem aponta para a área Modelo.

### 4.2 Endpoints

Os dois só aceitam requisições da própria máquina (`_so_local`, além do middleware de Host/Origin que já existe).

**`POST /api/datasets/previa?nome=<arquivo>`**

- Corpo: o arquivo cru (`application/octet-stream`). Não usa multipart, para não depender de `python-multipart`.
- Limite: 100 MB. Acima disso, 413.
- O arquivo vai para uma área temporária do processo (`tempfile.mkdtemp`), fora de `data/`, sob um token aleatório. Tokens expiram em 1 hora e somem quando o servidor reinicia.
- A leitura usa a mesma função de `carga.py` (`_read_any`): zip com exatamente um CSV, ou CSV.
- Resposta: `{token, prévia}` (seção 4.3).

**`POST /api/datasets/revisar`**

- Corpo: `{token, nome, predios_novos}`. Refaz a prévia com o nome e os prédios preenchidos na tela, sem gravar nada. É o botão **Verificar** do formulário: os bloqueios se atualizam antes de confirmar.

**`POST /api/datasets/confirmar`**

- Corpo: `{token, nome, predios_novos: [{chave, rotulo, ambiente, prefixo}]}`.
- Refaz a prévia **com os prédios novos aplicados** e recusa (422) se ainda houver bloqueio. Não confia no que a tela já validou.
- Ordem de gravação:
  1. `sites.cadastrar_predios(predios_novos)`, se houver;
  2. copia o arquivo para `data/<nome>.tmp` e renomeia para `data/<nome>` (atômico no mesmo sistema de arquivos);
  3. limpa os caches: `carga._descobertos`, `_cache` do payload, `_modelos_cache`, `_ajustes`, os jobs prontos de desenho e o cache de resolução de prédios;
  4. apaga o token.
- Se o passo 2 falhar depois do 1, o prédio fica cadastrado. Isso é inofensivo (prédio sem dados) e a mensagem de erro diz isso.
- Resposta: `{dataset: <nome>, predios: [...], payload_recarregado: true}`.

### 4.3 Conteúdo da prévia

| Item | Origem |
|---|---|
| Linhas e colunas | o frame lido |
| Geração (atual ou legada) e marcadores ausentes | `carga._generation`, `CURRENT_MARKERS` |
| Prédios e posições reconhecidos, com linhas de cada | `resolve_site_id` nos dois níveis |
| `local` desconhecidos agrupados por prefixo candidato | texto antes do primeiro `-`; valor sem `-` vira o próprio candidato |
| % preenchido | alvos, `local` e `CURRENT_MARKERS` (`combo`, `n_clients`, `station_x`, `house_x0`) |
| Fingerprint e relação com os existentes | mesma conta de `discover`, `_superseded` e `duplicatas` contra `descobertos()` |

A geração "atual" é decidida pela **presença** dos marcadores, não pelo preenchimento. Um arquivo com `n_clients` e `combo` quase vazios (o caso do Villa) passa como atual sem aviso nenhum hoje. A prévia mostra o % e emite aviso abaixo de 50 %.

### 4.4 Bloqueios e avisos

**Bloqueiam a confirmação:**

- arquivo ilegível, ou zip com quantidade de CSV diferente de 1;
- falta a coluna `local` ou algum dos alvos de `carga.TARGETS`;
- nome que não termina em `.csv` ou `.zip`, que contém `/` ou `..`, que já existe em `data/`, ou que contém `-qoe` ou `filllast` (a descoberta ignoraria o arquivo);
- fingerprint igual ao de um dataset existente (seria descartado como duplicata);
- `local` vazio em alguma linha;
- `local` desconhecido sem prédio novo preenchido que o cubra;
- prédio novo que falha na validação da seção 3.4.

**Só avisam:**

- geração legada (o dataset entra, mas não faz parte do conjunto canônico de `ids_padrao`);
- coluna-chave com menos de 50 % preenchido;
- o dataset contém um existente, ou está contido em um.

## 5. Reavaliar sem criar versão nova

### 5.1 Regra de imutabilidade

Hoje "a versão salva é imutável" vale para tudo. Passa a ser:

- **imutáveis**: `features`, `denominador`, `descricao`, `origem`, `selecao`, `criado_em`;
- **recalculáveis**: `avaliacao` e `cobertura`, que são relatório. A produção (`regression_mlflow.py`) já refaz tudo a partir das features e não lê esses campos;
- **só cresce**: `historico`, que ganha uma linha a cada reavaliação.

A docstring de `core/modelos.py` é atualizada com essa regra.

### 5.2 Core

`modelos.reavaliar(nome, avaliacao, cobertura, nota, path=MODELOS_PATH) -> dict`:

- recusa nome inexistente e nota vazia;
- troca só `avaliacao` e `cobertura` e acrescenta `nota` ao `historico`;
- usa o mesmo `_lock` e `gravar_json_atomico`, e valida o registro antes de gravar;
- **não** roda o bloqueio de vazamento e de classificação de `salvar_versao`. A `v1` tem features com vazamento e precisa poder ser reavaliada; a avaliação já descarta as vazadas da conta.

Nota do histórico, montada pela API:

```
2026-10-20: reavaliada; datasets +20261019-villa.zip; atende completo 0,67 → 0,70
```

- datasets: diferença entre `avaliacao[alvo].datasets` antiga e nova (`+x`, `-y`), ou "mesmos datasets";
- se o ambiente mudou: `ambiente todos → domestico`;
- atende completo: `media` antiga → nova, com "–" quando não havia.

### 5.3 API

**`POST /api/modelos/reavaliar`**, com corpo `{nomes: [...], ds, ambiente}`:

- só da própria máquina;
- recusa lista vazia ou nome inexistente (422) antes de começar;
- roda como job, com o mecanismo de `_iniciar_job` que o desenhar usa;
- para cada nome, em ordem: `avaliacao_completa(ds, ambiente, features, denominador)`, `F.cobertura_tr069`, `modelos.reavaliar(...)` e um evento de progresso `{nome, i, total}`;
- **grava uma versão por vez**: se o job falha no meio, as já reavaliadas ficam salvas e o erro diz em qual parou;
- ao terminar, limpa `_modelos_cache` e `_ajustes`.

**`GET /api/modelos/reavaliar/{job_id}`** devolve o estado do job, como `GET /api/modelos/desenhar/{job_id}`.

A base de comparação é a mesma do salvar: os datasets ligados e o ambiente escolhidos no Studio naquele momento. Por isso o selo "desatualizada" some depois de reavaliar.

### 5.4 Interface (`modelo.js`)

- O menu ⋯ de cada cartão ganha **Reavaliar**. A versão ativa, que hoje não tem menu, passa a ter, só com esse item.
- Quando houver versão com selo "desatualizada", o topo da lista mostra **Reavaliar N desatualizadas**. A tela manda a lista dos nomes que ela mesma marcou (`motivoDesatualizada`); o servidor não decide sozinho.
- Durante o job, os botões ficam desabilitados e aparece uma barra de progresso com o nome da versão em curso.
- Ao terminar: "N versões reavaliadas em src/ml/core/modelos.json. Revise no git diff antes do commit."

## 6. Erros

| Situação | Resposta |
|---|---|
| POST de fora da própria máquina | 403, como hoje |
| Arquivo acima de 100 MB | 413 |
| Token desconhecido ou expirado | 404 "prévia expirada; envie o arquivo de novo" |
| Bloqueio na confirmação | 422 com a lista de bloqueios |
| `predios.json` ilegível ou inválido | a importação de `core/sites.py` levanta o erro com a causa: Studio, treino e scripts não sobem. Não há reserva silenciosa, porque um prédio a menos mudaria os folds sem aviso. O arquivo só é gravado já validado e de forma atômica, então isso só acontece por edição manual |
| Falha no meio do lote de reavaliação | job em `erro`, com o nome da versão; as anteriores ficam gravadas |

## 7. Testes

**Prédios** (`tests/test_sites_predios.py`, novo):

- o `predios.json` migrado resolve todos os valores de `local` dos datasets em `data/` exatamente como o código anterior, nos dois níveis. Os valores esperados ficam fixados no teste;
- a validação recusa: prefixo repetido, prefixo que começa com outro, ambiente inválido, chave inválida, prédio sem prefixo e sem posições;
- `cadastrar_predios` grava, recusa chave existente e atualiza `BUILDING_ENVIRONMENT` no lugar (o mesmo objeto importado antes continua válido).

**Upload** (`tests/test_studio_upload.py`, novo, com `TestClient` e `DATA_DIR` e `PREDIOS_PATH` temporários):

- prévia de CSV e de zip;
- cada bloqueio da seção 4.4;
- % preenchido e agrupamento por prefixo candidato;
- confirmar grava o arquivo e o prédio, e `/api/payload` passa a ter o dataset sem reiniciar o servidor;
- confirmar refaz a validação (prédio novo inválido enviado direto é recusado);
- token desconhecido dá 404; POST com Host não loopback dá 403.

**Reavaliar** (`tests/test_modelos_core.py` e `tests/test_studio_assistente.py`):

- `reavaliar` troca só `avaliacao` e `cobertura`, mantém o resto e acrescenta ao `historico`;
- funciona numa versão com feature de vazamento;
- recusa nome inexistente;
- o job grava versão a versão (falha forçada na segunda deixa a primeira gravada);
- a nota descreve a diferença de datasets e de "atende completo".

Os testes que já existem continuam passando, em especial `tests/test_ml_core.py`, `tests/test_studio_features.py`, `tests/test_modelos_core.py` e `tests/test_carga.py`.

## 8. Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `src/ml/core/predios.json` | novo |
| `src/ml/core/sites.py` | lê o registro; funções de carga, validação, cadastro e recarga |
| `src/ml/core/modelos.py` | `reavaliar`; docstring da regra de imutabilidade |
| `src/ml/studio/data.py` | prédios do Studio vindos do registro |
| `src/ml/studio/ingestao.py` | novo: prévia, tokens e confirmação (fora do `api.py`, que já tem 779 linhas) |
| `src/ml/studio/api.py` | rotas finas de upload e reavaliação; limpeza de caches |
| `src/ml/studio/static/conjunto.js` | botão, prévia e formulário de prédio |
| `src/ml/studio/static/modelo.js` | Reavaliar no menu e em lote |
| `CHANGELOG.md` | entrada da mudança |
