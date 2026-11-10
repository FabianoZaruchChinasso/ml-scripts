# Inventário do QoE Studio e destino de cada função no MLflow

Data: 2026-11-10. Estado: proposta, aguardando aprovação do time.

Decisões já tomadas, que este documento assume: a pipeline usa só o MLflow (o Studio sai), o
versionamento de dados é o que funcionar melhor com o MLflow (DVC é o primeiro candidato), o deploy é
uma API e, por enquanto, tudo roda local.

Nada do Studio deve ser apagado antes de esta lista ser aprovada. A reescrita anterior (branch
`studio-novo`) perdeu funções justamente por não ter esse passo.

## Resumo

O Studio tem 36 rotas de API, que formam 19 funções do ponto de vista de quem usa. O destino proposto:

| Destino | Funções | Quais |
|---|---|---|
| Run no MLflow | 9 | comparação, avaliação do rascunho, régua por cômodo, reavaliação, pendências dos dados e as análises do Laboratório |
| Model Registry do MLflow | 3 | lista de versões, salvar versão, ativar versão |
| Arquivo no git e comando | 5 | conjunto ativo, entrada de dataset, classificação de colunas, derivadas, receitas |
| Sem equivalente no MLflow | 2 | visão de dados (matriz, detalhe e gráficos) e planta baixa |

Três coisas precisam de decisão do time, e estão na seção "Decisões para o time":

1. O que fazer com as duas funções sem equivalente.
2. Aceitar que o rascunho deixa de ser avaliado na hora, na tela.
3. Onde fica a definição de uma versão (a lista de features), já que o MLflow guarda resultados e
   não configuração.

## O que muda no dia a dia

Hoje: abrir o Studio, marcar features numa tela, ver o veredito em 1 a 2 minutos, salvar e ativar
com um botão.

Depois: editar um arquivo com a lista de features, rodar um comando, abrir o MLflow para ver o run
e comparar com os outros. A promoção é feita por um comando que aplica o veredito e só então move
o alias do modelo ativo. O tempo de cálculo é o mesmo, porque o código de avaliação é o mesmo. O
que se perde é a tela.

## Como ler a coluna "Destino"

- **Run no MLflow:** um comando calcula e grava parâmetros, métricas e arquivos num run. O
  resultado é visto e comparado na interface do MLflow.
- **Model Registry:** o cadastro de modelos do MLflow. Cada versão vira uma versão de modelo
  registrado, e o modelo ativo vira um alias.
- **Arquivo no git e comando:** a função já é, no fundo, a edição de um arquivo versionado. Passa
  a ser feita à mão ou por um comando, com um teste que valida o arquivo.
- **Sem equivalente:** o MLflow não tem nada parecido. O time decide entre manter fora da
  pipeline, trocar por um relatório ou largar.

## Inventário

### Área Dados

| Função | Rotas | Código | Destino | O que precisa ser feito |
|---|---|---|---|---|
| Visão de dados: matriz de posição por aplicação, detalhe da posição, queda com dispositivos simultâneos e qual métrica reprova mais | `GET /api/payload` | `studio/data.py`, `static/dados.js`, `static/graficos.js` | Sem equivalente | Decisão 1. A proposta é um relatório estático gerado na etapa de preparo e guardado no run |
| Planta baixa: posições em escala, foto ao fundo e calibração | 5 rotas em `/api/plan/` | `studio/plans.py`, `static/planta.js` | Sem equivalente | Decisão 1. A proposta é largar da pipeline e manter os arquivos em `docs/planta/` |
| Conjunto ativo: escolher datasets e ambiente | nenhuma (fica no navegador) | `static/conjunto.js` | Arquivo no git e comando | Vira parâmetro dos comandos, junto com a revisão do dado no DVC. Os scripts já aceitam `DATASETS=` |
| Entrada de dataset com prévia: colunas obrigatórias, duplicatas e cadastro de prédio novo | `POST /api/datasets/previa`, `/revisar`, `/confirmar` | `studio/ingestao.py`, `core/carga.py` | Arquivo no git e comando | Comando de validação que usa as mesmas checagens e depois adiciona o arquivo ao DVC |
| Pendências dos dados: prédios por ambiente, zeros ambíguos e estado dos contadores | `GET /api/pendencias` | `studio/api.py` | Run no MLflow | Relatório de qualidade gravado no run da etapa de preparo |
| Classificação de colunas e estado dos contadores da janela | `POST /api/columns`, `POST /api/contadores` | `core/features.py`, `column_provenance.json` | Arquivo no git e comando | Editar `column_provenance.json` direto. As funções de gravação já validam; falta um teste que rode a validação |

### Área Modelo

| Função | Rotas | Código | Destino | O que precisa ser feito |
|---|---|---|---|---|
| Lista de versões com cobertura TR-069 e colunas fora do TR-069 | `GET /api/modelos` | `core/modelos.py` | Model Registry | Cada versão de `modelos.json` vira versão de modelo registrado. Cobertura e pendências viram tags |
| Comparação entre versões, por prédio | `GET /api/modelos/comparar` | `studio/features.py` | Run no MLflow | A comparação do MLflow cobre o geral. Por prédio, as métricas precisam ser gravadas uma a uma; hoje estão só dentro de `avaliacao.json` |
| Avaliar rascunho nos quatro alvos, com veredito contra outra versão | `GET /api/modelos/avaliar` | `core/avaliacao.py`, `core/quantis.py`, `core/limiar.py` | Run no MLflow | Comando que lê as features de um arquivo, avalia e grava o run. O veredito vira tag do run. Decisão 2 |
| Régua por cômodo do rascunho, com intervalo da diferença | `GET /api/modelos/avaliar_comodo` | `core/comodo.py` | Run no MLflow | Mesmo comando. A diferença pareada com intervalo de 90% precisa ser calculada pelo comando, porque a interface do MLflow não calcula |
| Salvar versão: avaliação completa e gravação imutável | `POST /api/modelos`, `GET /api/modelos/salvar/{id}` | `studio/api.py` (`avaliacao_completa`), `core/modelos.py` | Model Registry | Um comando treina, avalia e registra a versão. Hoje o Studio grava só a avaliação; os binários saem de `regression_mlflow.py` e `qoe_mlflow.py`, em outros experimentos |
| Ativar versão | `POST /api/modelos/ativo` | `core/modelos.py`, `core/registro_mlflow.py` | Model Registry | O alias do modelo ativo no lugar do campo `ativo` e da tag `ativo` |
| Reavaliar versões existentes com outro conjunto | `POST /api/modelos/reavaliar`, `GET /api/modelos/reavaliar/{id}` | `studio/api.py`, `core/registro_mlflow.py` | Run no MLflow | Rodar o comando de avaliação de novo. A tag `atual` já marca o run mais recente de cada versão |

### Laboratório

| Função | Rotas | Código | Destino | O que precisa ser feito |
|---|---|---|---|---|
| Inventário de features e teto de desempenho | `GET /api/features/inventario`, `/ajuste` | `studio/features.py` | Run no MLflow | Comando que grava a tabela como arquivo do run |
| Desenho automático: seleção gulosa de features | `POST /api/modelos/desenhar`, `GET /api/modelos/desenhar/{id}` | `studio/selecao.py` | Run no MLflow | Comando que grava os passos e a nota aninhada; a lista escolhida vira arquivo de features |
| Paralelos entre colunas de laboratório e TR-069 | `POST /api/paralelos`, `GET /api/paralelos/{id}` | `studio/paralelos.py` | Run no MLflow | Comando que grava a tabela como arquivo do run |
| Derivadas: prévia, teste e gravação de fórmulas | 4 rotas em `/api/derivadas` | `studio/paralelos.py`, `core/formulas.py`, `derivadas.json` | Arquivo no git e comando | Editar `derivadas.json` direto. O teste que define o status vira comando; a regra "o status vem do teste" passa a ser um teste automático |
| Assistente: ganho de acrescentar uma coluna TR-069 de cada vez | 3 rotas em `/api/assistente/` | `studio/features.py` | Run no MLflow | Comando que grava a tabela de ganho |
| Receitas de conjuntos de features | `GET /api/receitas`, `POST /api/receitas/montar` | `studio/receitas.py` | Arquivo no git e comando | As receitas já são código; montar vira uma opção do comando de avaliação |

## O que o MLflow já recebe hoje

Desde 2026-11-09, salvar, reavaliar e ativar no Studio gravam no experimento "MLflow Wifi Studio"
(`core/registro_mlflow.py`):

- parâmetros: versão, features, denominador, datasets, ambiente, perfil, cobertura TR-069 e versões
  das réguas;
- métricas: nota por cômodo com intervalo de 90%, piso, apto para jogo, os três "atende" e, por
  alvo, R² e MAE;
- arquivos: `avaliacao.json` (a avaliação inteira) e `posicoes.json` (a tabela por posição);
- tags: `atual`, `ativo`, `evento` e o commit do git.

Os binários dos modelos estão em outros dois experimentos ("MLflow Wifi Regressions" e "MLflow
Wifi QoE"), gravados por scripts separados.

## O que falta no MLflow

1. **Model Registry.** Nenhum script registra modelo; a versão ativa é um campo de `modelos.json`.
2. **Um run que una modelo e avaliação.** Hoje a avaliação está num experimento e os binários em
   outros dois, sem ligação entre eles.
3. **Versão do dado no run.** Só `experimental/classifier_mlflow.py` usa `mlflow.log_input`.
4. **Métricas por prédio.** Existem só dentro de `avaliacao.json`, e por isso não aparecem na
   comparação do MLflow.
5. **Veredito de promoção.** É calculado pelo Studio na hora e não fica gravado em lugar nenhum.

## Decisões para o time

**Decisão 1: as duas funções sem equivalente.**

| Função | Opções | Proposta |
|---|---|---|
| Visão de dados | largar; relatório estático no run; manter uma tela só de leitura fora da pipeline | Relatório estático gerado no preparo. Perde o recálculo de limiares na tela |
| Planta baixa | largar; figura estática no relatório; manter fora da pipeline | Largar da pipeline. Os arquivos de `docs/planta/` ficam no repositório |

**Decisão 2: o rascunho deixa de ser interativo.** O ciclo passa a ser editar o arquivo, rodar o
comando e abrir o MLflow. O cálculo leva o mesmo 1 a 2 minutos. Não há como manter a tela sem
manter o Studio.

**Decisão 3: onde fica a definição de uma versão.** O MLflow guarda resultados, não a lista de
features que define o que treinar. A proposta é dividir `modelos.json` em dois:

- a **definição** (features, denominador e perfil) continua em arquivo no git, porque é a entrada
  do comando de treino;
- o **resultado** (avaliação) e o **estado** (qual é a ativa) saem do arquivo e ficam só no MLflow.

Assim deixa de haver duas fontes de resultados, que é o risco anotado na planilha.

## O que apagar e o que mover

"Desligar o Studio" não é apagar a pasta `src/ml/studio/` inteira. Ela tem quatro partes:

| Parte | Tamanho | Destino |
|---|---|---|
| Tela: `static/` (HTML, JS e CSS) | 4.292 linhas | Apagar, depois da Decisão 1 |
| Servidor: `api.py` e `studio.py` | 1.124 linhas na contagem de 2026-11-10 | Apagar. `avaliacao_completa` já saiu para `core/completa.py`; `_promocao` sai junto com o portão de promoção |
| Lógica de análise: `features.py`, `selecao.py`, `paralelos.py`, `receitas.py`, `ingestao.py`, `data.py` | 1.259 linhas | Fica onde está. São módulos Python comuns, e os comandos novos podem importá-los de `ml.studio`. Mudar de pasta é só arrumação, a decidir quando a tela for apagada |
| Planta: `plans.py` | 402 linhas | Conforme a Decisão 1 |

Os 9 arquivos `tests/test_studio_*.py` e os testes de JS precisam ser migrados ou apagados junto.

## Ordem proposta

1. Aprovar este inventário e as três decisões.
2. Extrair `avaliacao_completa` do servidor para `core/completa.py`, sem mudar comportamento. Feito
   em 2026-11-10: a avaliação da v5 deu resultado idêntico antes e depois, e o Studio continua
   funcionando.
3. Criar o comando único de avaliação, que grava um run com modelo, avaliação, métricas por prédio
   e versão do dado. Feito em 2026-11-10: `src/ml/versao_mlflow.py`
   (spec em `docs/superpowers/specs/2026-11-10-versao-mlflow-design.md`).
4. Registrar as versões v1 a v5 no Model Registry e criar o alias do modelo ativo.
5. Criar o portão de promoção.
6. Criar os comandos do Laboratório.
7. Conferir, função por função desta lista, que o resultado novo bate com o do Studio.
8. Apagar o Studio.

O Studio só sai no passo 8. Até lá os dois funcionam, e o passo 7 é a prova de que nada se perdeu.

## Efeito na estimativa

A planilha tinha 11 dias para esta trilha. O inventário mostra três pontos que não estavam contados:

| Ponto | Efeito |
|---|---|
| O Laboratório são seis funções, não uma | de 2 para 3 dias |
| Conferência função por função antes de apagar (passo 7) | mais 1 dia |
| Relatório estático da visão de dados, se a Decisão 1 for essa | mais 2 dias |
| Servidor MLflow compartilhado: com tudo local, não é necessário agora | menos 1 dia |

Total revisado: de 12 a 14 dias, conforme a Decisão 1. São estimativas pela leitura do código, não
por execução.
