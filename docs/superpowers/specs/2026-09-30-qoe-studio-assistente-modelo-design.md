# QoE Studio: assistente de modelo para técnicos de rede (design)

**Data:** 2026-09-30
**Base:** `qoe-studio-features-planta` (commit `a4b2a4e`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

O Studio existe para que ajustes no modelo e versões novas sejam testados sem mexer no código. Hoje, criar features e versões exige passar por três telas densas:

- **Features:** gates, teto por local, ganho +1, proxies e inventário.
- **Modelos:** pendências, versões, comparação, desenho automático, um editor com cerca de 150 checkboxes e a matriz de correlação.
- **Paralelos + Desenhista:** fórmula livre, "Inspirada em" e teste de aceite.

Um técnico de rede não consegue usar isso sozinho.

A entrega é uma view nova, **Modelo**, com um assistente em quatro passos. Com ele o técnico, sem apoio de um cientista de dados, consegue:

1. resolver pendências (classificar colunas novas e responder às perguntas de vazamento);
2. ligar e desligar features a partir da versão ativa;
3. criar métricas derivadas com receitas prontas, sem digitar fórmula;
4. testar contra a versão ativa, com um veredito claro, e promover a versão nova quando ela for melhor.

As telas de hoje continuam existindo como **modo avançado**, sem mudança de comportamento.

## 2. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Telas atuais | Viram "Avançado", sem mudança |
| Formato | Assistente em passos: Preparar → Ajustar → Testar → Publicar |
| Vocabulário | Nomes de coluna como hoje; descrição em tooltip quando houver |
| Veredito | Melhor / Empate / Pior, calculado no servidor. "Tornar ativa" só com Melhor |
| Alvo do veredito | Um alvo escolhido no passo 1 (padrão: download). Os outros alvos são só informativos |
| Colunas fora do TR-069 | Não aparecem no assistente; testá-las é no avançado |

## 3. Navegação

- Na barra lateral, **Features** e **Modelos** dão lugar a **Modelo**, com o ícone `i-model`, que abre o assistente.
- Um grupo recolhível **Avançado** na barra lateral guarda os botões `features` e `modelos` de hoje. As seções `view-features` e `view-modelos` (com o `pBody` de Paralelos) continuam iguais.
- O cabeçalho do assistente tem um link "Abrir no modo avançado", que leva à view `modelos`.
- O estado do assistente (passo atual, alvo, rascunho, veredito) vive em memória no `assistente.js` e se perde ao recarregar a página. Não há persistência.

## 4. Passo 1 · Preparar

**Alvo.** Seletor Download (padrão), Upload, Latência ou Jitter. Vale para os quatro passos. Trocar o alvo depois invalida as sugestões e o veredito.

**Pendências**, vindas de `api/features/inventario` e `api/pendencias`, escritas como perguntas:

- **Coluna sem classificação** (`sem_classificacao`): "De onde vem `xyz`?". As opções são Roteador (TR-069), Sniffer, Cliente, Ambiente, Geometria, Identificador e Alvo, com a sugestão de `F.sugerir` já marcada. A resposta grava por `POST api/columns`, como hoje.
- **Suspeita de vazamento** (`suspeita`, \|ρ\| ≥ 0,9 com o alvo) e **contadores do roteador** (`api/pendencias` → `contadores`): "Esse valor é medido durante o speedtest?", com Sim, Não e Não sei.
  - Na suspeita, Sim grava `vazamento: true` por `api/columns`, e Não/Não sei só dispensam o aviso nesta sessão.
  - Nos contadores, a resposta grava por `POST api/contadores`, como hoje.

Pendências **não bloqueiam** o avanço. O rodapé do passo avisa em uma frase: "colunas sem classificação ficam de fora; respostas 'não sei' marcam o resultado como provisório".

**Aviso de poucos locais.** Com menos de 4 locais de coleta, uma frase fixa: "Só N locais de coleta: os números ainda mudam quando novos prédios entrarem."

O botão **Próximo** fica sempre habilitado.

## 5. Passo 2 · Ajustar

**Ponto de partida.** A versão ativa (`api/modelos` → `ativo`) vem carregada no rascunho. Um seletor discreto, "partir de outra versão", lista as versões salvas. Trocar de base substitui o rascunho.

**Lista de features.** `GET api/assistente/colunas` (função `lista_assistente()` em `studio/features.py`) devolve as colunas que aparecem, com o critério de `elegiveis()` restrito à classe `tr069` (sem vazamento, não constante, cobertura ≥ 70%, sem `categorica_alta`, sem duplicata idêntica e sem hipótese). Há duas exceções:

- **Hipóteses marcadas no rascunho aparecem** com o selo "hipótese". Desmarcadas, somem.
- **Features da base que não passam no critério** (por exemplo, `client_opportunity_medium_use`, que é de cliente) aparecem marcadas com o selo "fora do TR-069" ou o motivo do bloqueio. O técnico pode desmarcá-las, mas não pode remarcá-las depois.

A lista tem dois grupos: **No modelo** (marcadas) e **Disponíveis**. Cada linha mostra:

- o nome da coluna;
- um tooltip com a descrição (da derivada, ou o `parametro` TR-069 quando existir);
- a cobertura;
- o selo **sugerida +0,03** quando a sugestão (abaixo) tem ganho médio ≥ `paralelos.GANHO_MIN` (0,01) e melhora em todos os locais.

No alto ficam um filtro por nome e o contador "N features".

**Sugestões.** Ao entrar no passo, o front chama `POST api/assistente/sugestoes` (job em thread, no padrão de `_iniciar_job`). O job calcula o ganho +1 de cada coluna disponível sobre o rascunho **da base**, no alvo escolhido, e reporta progresso em `GET api/assistente/sugestoes/{id}`. A lista já pode ser usada enquanto o job roda. Uma barra mostra "calculando sugestões… 14/38", e os selos aparecem quando o job termina. Mudar a base, o alvo, os datasets ou o ambiente dispara um job novo. O rascunho editado **não** dispara.

Para isso, o laço de ganho +1 hoje dentro de `studio/features.py::ajuste()` vira a função `ganho_mais_um(conj, base, candidatas, vazadas, progresso=None)`. `ajuste()` passa a chamá-la, sem mudar a saída.

**Criar métrica a partir de receita.** O botão "+ Criar métrica" abre um painel com três etapas:

1. **Receita:**

   | Receita | Fórmula | Sufixo do nome |
   |---|---|---|
   | Razão | `A / B` | `a_por_b` |
   | Diferença | `A - B` | `a_menos_b` |
   | Fração | `A / (A + B)` | `fracao_a` |
   | Média | `(A + B) / 2` | `media_a_b` |
   | Produto | `A * B` | `a_x_b` |
   | Por canal | `A / (B * C)` | `a_por_canal` |

   A Razão traz sempre a dica "divide dois contadores: o volume de tráfego se cancela", e Por canal traz um exemplo de uso.
2. **Colunas:** seletores com as colunas TR-069 brutas numéricas, sem vazamento, na quantidade que a receita pede.
3. **Nome:** gerado a partir dos sufixos acima. Remove o prefixo `router_`, passa para minúsculas, corta em 40 caracteres e troca o que sobrar fora de `[a-z0-9_]` por `_`, para passar em `NOME_DERIVADA`. Em caso de colisão, soma `_2`, `_3`… O técnico pode editar.

A montagem fica em Python (`studio/receitas.py`: `RECEITAS` e `montar(receita, colunas, existentes) -> {formula, nome, descricao}`). O front a acessa por `GET api/receitas` e `POST api/receitas/montar`. A descrição gerada é, por exemplo, "Razão entre router_tx_retries e router_tx_packets (receita do assistente)."

Com a fórmula montada, o painel chama `POST api/derivadas` (o endpoint de hoje), com `base` = base do rascunho, `alvo` = alvo escolhido e `inspirada_em` vazio — o teste de aceite roda no servidor antes de salvar, então não é preciso chamar `api/derivadas/testar` à parte. O resultado aparece em linguagem simples:

- aprovada: "Aprovada: melhora o <alvo> em todos os locais."
- hipótese: "Hipótese: não melhora em todos os locais. Fica salva, mas não é sugerida." Em seguida vem a lista de critérios que falharam, com o texto de `criterios`.

Nos dois casos a métrica entra marcada no rascunho. Não há fórmula livre nem "Inspirada em"; isso continua no desenhista do avançado.

**Próximo** fica desabilitado com o rascunho vazio.

## 6. Passo 3 · Testar

**Testar** chama `GET api/modelos/avaliar`, com `base` = versão **ativa** (não a base do rascunho) e o alvo escolhido. Quando `base` vem preenchido, a resposta ganha o campo `veredito`, calculado no servidor pela função pura `veredito(delta, n_locais, pendentes, unidade)` em `studio/features.py`:

| Veredito | Regra (alvo escolhido) |
|---|---|
| `melhor` | ΔR² pooled ≥ +`RUIDO_R2` **e** ΔMAE ≤ 0 **e** nenhum local com ΔR² < −`RUIDO_R2` |
| `pior` | ΔR² pooled ≤ −`RUIDO_R2` **ou** (ΔMAE > 0 **e** ΔR² pooled < +`RUIDO_R2`) |
| `empate` | qualquer outro caso |

`RUIDO_R2 = 0.02` é uma constante nova em `studio/features.py`, ao lado das outras. Pooled ou MAE ausentes (`None`) dão `empate`.

O `veredito` sai como `{"resultado": "melhor"|"empate"|"pior", "motivo": str, "provisorio": bool, "motivos_provisorio": [str]}`. O `motivo` é uma frase curta em português, por exemplo:

- "R² subiu 0,05 e o MAE caiu 4,1 Mbps, sem piorar nenhum local."
- "Piorou em residencia (−0,05)."
- "A diferença (+0,01) é menor que o ruído com 3 locais."

`provisorio` é verdadeiro quando o rascunho usa coluna `pendente` ou quando há menos de 4 locais.

Rascunho igual à versão ativa (mesmo conjunto de features): o botão Testar fica desabilitado, com a explicação "igual à versão ativa".

**Na tela:**

- o veredito em destaque, com cor semântica (`--good` / `--critical` / neutro) e ícone SVG, sem emoji;
- três números: R² pooled antes → depois, MAE antes → depois (na unidade do alvo) e "melhora em X de N locais";
- o `motivo`;
- o selo "provisório" com os `motivos_provisorio` no tooltip;
- a tabela por local recolhida em "ver detalhes", no formato do `cardResultado` de hoje;
- o botão **Ver nos outros alvos**, que chama `avaliar` para os três outros alvos e mostra uma linha informativa ("Upload: Empate · Latência: Pior · Jitter: Empate"). Essa linha não trava nada.

**Erros:** as mensagens 422 de hoje (por exemplo, menos de 2 locais) aparecem como gate crítico com o texto do servidor.

O veredito carrega uma chave (rascunho ordenado + datasets + ambiente + alvo + versão ativa). Mudar qualquer um desses itens marca o veredito como desatualizado e bloqueia "Tornar ativa".

## 7. Passo 4 · Publicar

- **Nome:** sugerido a partir da versão ativa, incrementando o primeiro número (`v2-tr069` → `v3-tr069`). Sem número, acrescenta `-2`. Se o nome já existir, incrementa até achar um livre. É validado por `NOME_OK`, como hoje.
- **Descrição:** obrigatória e pré-preenchida com o diff e o veredito, por exemplo "+retry_por_pacote −router_noise · download: melhor (R² 0,41→0,46)". O técnico completa com o porquê.
- **Salvar versão:** `POST api/modelos`, como hoje (a avaliação dos quatro alvos já é guardada pelo servidor). Pode ser feito com qualquer veredito.
- **Salvar e tornar ativa:** habilitado só com veredito `melhor` atual (§6). Chama `POST api/modelos` e depois `POST api/modelos/ativo`. Com `empate` ou `pior`, o botão fica desabilitado com a explicação: "Para ativar uma versão que não é melhor que a ativa, use o modo Avançado."
- A trava existe **só na UI do assistente**. `api/modelos/ativo` não muda.
- Ao final aparece a mensagem de hoje: "Salvo em `src/ml/core/modelos.json`. Revise no git diff antes do commit." O Studio não faz commit.

## 8. Arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/studio/static/assistente.js` | novo; `V.views.assistente` com `render(ctx)` |
| `src/ml/studio/static/index.html` | seção `view-assistente`, item **Modelo** na nav e grupo **Avançado** |
| `src/ml/studio/static/studio.js` | registrar a view nova e o grupo recolhível |
| `src/ml/studio/static/styles.css` | estilos do stepper, do cartão de veredito e do painel de receitas |
| `src/ml/studio/features.py` | `RUIDO_R2`, `veredito()`, `ganho_mais_um()` (extraída de `ajuste()`), `lista_assistente()` |
| `src/ml/studio/receitas.py` | novo; `RECEITAS`, `montar()` |
| `src/ml/studio/api.py` | `veredito` em `modelos/avaliar`; `api/assistente/colunas`, `api/assistente/sugestoes` (+ status), `api/receitas`, `api/receitas/montar` |
| `tests/test_studio_assistente.py` | novo |

## 9. Testes

- `veredito()`: casos de fronteira (ΔR² exatamente +0,02 e −0,02, ΔMAE = 0, um local em −0,021, pooled `None`) e `provisorio` com coluna pendente e com 3 locais.
- `ganho_mais_um()`: mesma saída que o trecho equivalente de `ajuste()` num conjunto sintético pequeno; o progresso é chamado uma vez por candidata.
- `receitas.montar()`: cada receita gera uma fórmula que `formulas.analisar` aceita; nome com maiúsculas (`router_NSS_TX_Station`) vira minúsculas; nome longo é cortado em 40; colisão gera `_2`; número errado de colunas levanta `ValueError`.
- `lista_assistente()`: exclui não TR-069, vazamento e hipótese não marcada; inclui hipótese marcada e feature da base fora do critério com o motivo.
- API: `modelos/avaliar` com `base` devolve `veredito`; sem `base`, não devolve. O job de sugestões termina com status `pronto`.

## 10. Fora do escopo

- Nomes amigáveis ou agrupamento por conceito de rede.
- Mudanças nas telas avançadas (Features, Modelos, Paralelos).
- Trava de promoção no servidor.
- Colunas fora do TR-069 no assistente.
- Desenho automático guloso no assistente.
- Persistência do estado do assistente entre recarregamentos.
