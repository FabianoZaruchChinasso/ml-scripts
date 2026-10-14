# QoE Studio: interface mais simples (design)

**Data:** 2026-10-13
**Estado:** desenho aprovado em conversa, para revisão do usuário. Falta o plano de implementação.
**Mockups:** `.superpowers/brainstorm/` (fora do git): `estrutura.html`, `modelo-m1-v2.html`, `dados-conjunto.html`.

## 1. Objetivo

A interface do Studio confunde até quem o construiu. Hoje são nove telas numa barra lateral, três filtros globais e um banner de avisos que aparecem em toda tela, mesmo onde não fazem efeito, e dois caminhos para o mesmo trabalho de modelo (o assistente "Modelo" e o grupo "Avançado").

O uso real se divide em partes iguais entre **entender os dados de QoE** e **treinar e comparar modelos**, na mesma sessão. Das telas avançadas, só **Versões + Comparação** e **Montar modelo + correlações** são usadas; o Montar é complicado demais, e o assistente é guiado demais.

Esta spec reorganiza o front em duas áreas (Dados e Modelo), um painel de conjunto ativo e um Laboratório. A área Modelo é reativa: o rascunho é reavaliado sozinho a cada mudança.

## 2. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Estrutura | Barra no topo com abas **Dados \| Modelo**, chip do conjunto ativo e link **Laboratório** (opção A). Sai a barra lateral |
| Conjunto ativo | Datasets, legacy, ambiente, avisos e pendências num **painel** que abre a partir do chip |
| Área Dados | **Matriz + detalhe da posição** (D2), com alternador Matriz/Planta |
| Área Modelo | **Página única** (M1): cartões de versão em cima, rascunho com chips embaixo, veredito ao lado, barra fixa para salvar |
| Avaliação | **Reativa**: roda sozinha cerca de 0,8 s depois da última mudança, sem botão "Testar" |
| Referência do veredito | Sempre a **versão ativa**, pela régua de promoção |
| Telas não usadas | Desenhar melhor modelo, cartões de Features, Paralelos e Desenhista vão para o **Laboratório**, sem mudança de comportamento |
| Removidos | Assistente de 4 passos, editor "Montar modelo", telas Limiares e Datasets, banner fixo de gates |

## 3. Estrutura e navegação

**Barra do topo** (fixa), da esquerda para a direita:

- a marca;
- as abas **Dados** e **Modelo**;
- o **chip do conjunto**: amostras · prédios · ambiente, com um contador quando há avisos ou pendências;
- o link discreto **Laboratório**;
- o botão de tema.

**Rotas** por hash: `#dados` (padrão), `#modelo` e `#laboratorio`. Os hashes antigos redirecionam, para não quebrar links salvos:

| Antigo | Novo |
|---|---|
| `#matrix`, `#contention`, `#constraint`, `#plan`, `#thresholds` | `#dados` |
| `#assistente`, `#modelos` | `#modelo` |
| `#features` | `#laboratorio` |
| `#datasets` | `#dados`, com o painel Conjunto aberto |

`?legacy=1`, `?ambiente=` e `?theme=` continuam valendo.

**Painel Conjunto.** Abre pela direita, por cima de qualquer área. Esc fecha, e o foco fica preso no painel enquanto ele está aberto. Tem quatro seções:

1. **Avisos.** São os gates de hoje (`renderGates`): menos de 2 locais, gerações misturadas, dataset idêntico ou contido em outro, linhas com local desconhecido. Quando há uma ação, ela fica no próprio aviso: "desligar" num dataset duplicado.
2. **Pendências.** Vêm de `api/features/inventario` (`sem_classificacao`, `suspeita`) e de `api/pendencias` (contadores, zeros ambíguos, número de locais). As perguntas e as gravações são as mesmas do passo "Preparar" do assistente e do card "Limites e pendências" do Modelos (`POST api/columns` e `POST api/contadores`).
3. **Ambiente.** Seletor segmentado: Todos, Doméstico ou Corporativo.
4. **Datasets.** A lista com interruptores, com os legacy num grupo recolhido e o interruptor "incluir legacy" no cabeçalho desse grupo. A observação "contido em" ou "idêntico a" continua na linha.

Não há mais banner fixo. Um aviso **crítico** (menos de 2 locais) aparece também em linha na tela que ele invalida: acima da matriz em Dados e no lugar do veredito em Modelo.

**Laboratório.** Uma tela só, com estas partes, sem mudança de comportamento:

- os cartões de Features (`features.js`);
- "Desenhar melhor modelo", extraído de `modelos.js`;
- Paralelos e o Desenhista (`paralelos.js`).

O alvo dessas partes vem de um seletor próprio do Laboratório.

## 4. Área Dados

**Cabeçalho.**

- Seletor **Aplicação**, e os quatro limiares ao lado como chips: `↓ ≥ 4 Mbps`, `↑ ≥ 2 Mbps`, `lat ≤ 150 ms`, `jit ≤ 30 ms`.
- Clicar num chip abre um popover com o slider daquele limiar (mesmos `max` e `step` de `METRICS`).
- Ao editar um limiar, o seletor mostra "Personalizado" e aparece o link "restaurar". Os limiares continuam valendo só na sessão.

Esse é o único lugar da aplicação e dos limiares. Eles mudam os números de Dados, mas não o "atende" do Modelo, que é calculado no servidor com `aplicacoes.json`; a área Modelo diz isso numa linha discreta.

**Visão principal.** Um alternador **Matriz | Planta**.

- **Matriz.**
  - Posições agrupadas por prédio, com uma linha de cabeçalho por prédio e o selo de ambiente.
  - Colunas de 1, 2 e 3 dispositivos, com o percentual dentro da célula colorida (rampa `--seq-*`). Com menos de 5 amostras (`MIN_SAMPLES`), a célula mostra "–".
  - A tabela numérica separada sai.
  - Posições sem `n` (legacy) aparecem numa nota: "N posições sem contagem de dispositivos: veja na planta ou no detalhe".
- **Planta.** A view de hoje: retrato, foto ao fundo e calibração. Clicar num ponto seleciona a posição, como clicar na linha da matriz.

**Detalhe da posição** (painel à direita; abaixo da matriz em telas estreitas).

- **Sem seleção:** resumo do conjunto, com o gargalo geral (a métrica que mais reprova em todas as amostras) e as 3 posições com menor percentual, clicáveis.
- **Com uma posição selecionada:**
  - nome, prédio, ambiente e número de amostras;
  - **Gargalo:** a métrica com maior percentual de reprovação ali, numa frase ("download reprova em 54% das amostras"). Se nenhuma reprovar em mais de 5%, a frase é "atende em praticamente todas as amostras";
  - **quatro mini-gráficos de contenção**, um por métrica: a mediana com 1, 2 e 3 dispositivos e uma linha tracejada no limiar. Sem `n`, a posição mostra só a mediana geral de cada métrica;
  - **barras horizontais** com o percentual reprovado por métrica.
- **Ver todas as posições.** Um link que abre, abaixo da matriz, os gráficos completos de hoje: Contenção, com o seletor de métrica, e Restrição, com as barras agrupadas.

**Mudanças em arquivos existentes.**

- `planta.js` ganha um callback `aoSelecionar(b, p)`, disparado pelo clique num ponto. O canvas já guarda os pontos desenhados.
- `graficos.js` ganha duas opções em `drawLines`: `ref: {valor, rotulo}`, que desenha uma linha horizontal tracejada (o limiar) e entra na escala do eixo y, e `compacto: true`, que reduz as margens fixas de hoje (62 px à esquerda e 104 px à direita para os rótulos de fim de linha) para caber nos mini-gráficos. Sem essas opções, o desenho é idêntico ao de hoje.

## 5. Área Modelo

### 5.1 Alvo e versões

**Alvo.** Seletor segmentado: Download (padrão), Upload, Latência ou Jitter. Trocar o alvo reavalia o rascunho e dispara um novo job de sugestões.

**Cartões de versão.** Um por versão de `api/modelos`, em grade. Cada cartão mostra:

- o nome e o selo **ativa** ou **editando**;
- **atende completo** (`avaliacao.atende_completo.media`) em destaque, com uma barrinha;
- os selos de cobertura TR-069 (`100%`, `proxy` ou `parcial`, pelo `tagNivel` de hoje), de vazamento ("N c/ vazamento"), de eficiência (quando há `denominador`) e de **desatualizada**, com o motivo no tooltip (o mesmo de `motivoDesatualizada`).

O comportamento do cartão:

- **Clicar** carrega a versão no rascunho como base. Se o rascunho tiver mudanças não salvas, pergunta "Descartar rascunho?" antes.
- O **menu ⋯** tem **Tornar ativa**, que é a ativação manual de hoje (`POST api/modelos/ativo`). Se o último veredito conhecido daquela versão contra a ativa não for "Melhor", ou se não houver veredito, a confirmação mostra isso antes de ativar.

**Comparar por prédio.** Um link acima dos cartões abre, abaixo deles, o gráfico de comparação de hoje (`api/modelos/comparar`, com R² ou MAE por local). Roda só quando pedido, porque leva cerca de 20 s.

### 5.2 Rascunho

O rascunho começa na versão ativa. As features aparecem como **chips com ×**:

- **adicionadas** em relação à base: em verde;
- **removidas**: riscadas, com um botão para desfazer;
- uma bolinha colorida indica o status TR-181: verde para padrão ou derivável, âmbar para proxy ou "depende do coletor", vermelho para laboratório;
- colunas da base hoje **bloqueadas** (vazamento, constante, `categorica_alta`) ficam com borda vermelha e o motivo; podem ser removidas, mas não readicionadas;
- colunas da base **ausentes neste conjunto** ficam com borda tracejada e o texto "ausente neste conjunto".

**Adicionar feature.** Um campo com busca por nome e uma lista em grupos:

1. **Sugeridas.** Vêm do job de ganho +1 de hoje (`POST api/assistente/sugestoes` sobre a base, no alvo). Mostram o ganho e só incluem quem melhora em todos os locais com ganho ≥ `ganho_min`. Enquanto o job roda, o grupo mostra "calculando sugestões… 14/38".
2. **Outras TR-069.** Colunas liberadas de `api/assistente/colunas`, ordenadas por ganho e depois por |ρ|.
3. **Laboratório.** As demais colunas sem bloqueio, ocultas atrás de "mostrar (N colunas)".

No rodapé da lista fica **+ Criar métrica a partir de receita**, que abre o painel de receitas do assistente sem mudança: `api/receitas`, `api/receitas/montar` e `POST api/derivadas`.

Teclado: Enter adiciona o item em destaque; Backspace com o campo vazio remove o último chip.

**Correlações.** Abaixo dos chips fica a linha "N pares redundantes (|ρ| ≥ 0,9)", que expande para a matriz de correlação de hoje (`correlacoes` da resposta de `avaliar`).

### 5.3 Avaliação reativa

- A avaliação dispara cerca de **0,8 s depois da última mudança** no rascunho ou no alvo, e também ao carregar uma base.
- Funciona em **voo único**: só existe um pedido a `api/modelos/avaliar` por vez. Se o rascunho mudar enquanto um pedido roda, um novo pedido sai quando ele voltar, com o estado mais recente. Respostas de estados antigos são descartadas pela chave.
- Enquanto roda, o veredito anterior fica esmaecido e aparece "reavaliando… N s", com o tempo decorrido (a rota não informa progresso).
- Se o rascunho tiver as mesmas features da ativa, nada roda e aparece "Igual à versão ativa".
- Voltar a um estado já avaliado é instantâneo, por causa do cache do servidor (`_modelos_cache`).

**Referência.** O veredito compara o rascunho sempre com a **versão ativa**. Clicar no cartão de uma versão mostra na hora como ela se sai contra a ativa.

### 5.4 Veredito

Um cartão grande diz **"Melhor / Empate / Pior que <ativa> (ativa)"** pelo resultado de `promocao.veredito`, com o selo **provisório** quando `veredito.provisorio` estiver marcado. Embaixo, uma frase com `promocao.veredito.motivo` e três números:

| Alvo | Números |
|---|---|
| Download e upload | Δ atende (com o intervalo de 90%), Δ MAE e prédios que melhoram (`delta.melhora` de `delta.locais`) |
| Latência e jitter | Δ pinball p90 (com intervalo), cobertura p90 e prédios que melhoram |

Ficam recolhidos:

- **Por prédio:** a tabela de R² e MAE da ativa e do rascunho;
- **Nos outros alvos:** calculados sob demanda, como o "Ver nos outros alvos" de hoje;
- **Cobertura TR-069:** o nível e as lacunas do rascunho (`cobertura`);
- **Piora em:** `predios_contra`, quando houver.

### 5.5 Barra fixa

Fica no rodapé da área Modelo e só aparece quando o rascunho difere da base. Mostra "Rascunho de <base> · +N −M · <veredito>" e três botões:

- **Descartar:** volta à base.
- **Salvar:** abre um formulário curto, com nome e descrição já preenchidos. O nome é `sugerirNome` de hoje; a descrição é `descricaoSugerida` (+feature −feature e o veredito). Grava por `POST api/modelos`.
- **Salvar e tornar ativa:** habilitado só quando todas estas condições valem:
  - o veredito está atual e é **Melhor**;
  - `predios_contra` está vazio;
  - a cobertura é `100%` ou `proxy`.

  Fora disso, o botão fica desabilitado, com o motivo no tooltip (os mesmos textos do `passoPublicar` de hoje). A ativação manual fica no menu do cartão.

**Estado:** em memória, no `modelo.js`. Alternar entre Dados e Modelo não perde o rascunho; recarregar a página perde.

## 6. Mudança no backend

`GET api/modelos/avaliar` ganha o parâmetro opcional **`contra`**:

- `base` continua dizendo de onde o rascunho partiu, e por isso **de qual versão ele herda o denominador** (`den_nova`).
- `contra` diz **contra qual versão** comparar: `resumo_base`, `delta`, `veredito` e `promocao` passam a usar as features e o denominador de `contra`.
- Sem `contra`, vale `contra = base`, e a resposta é idêntica à de hoje.
- `contra` entra na chave do cache.
- Um `contra` inexistente devolve 404, como `base`.

A área Modelo sempre manda `contra=<ativa>`. Nenhuma outra rota muda. Rotas que deixarem de ser usadas pelo front ficam; removê-las fica para depois.

## 7. Arquivos do front (`src/ml/studio/static/`)

| Arquivo | Papel |
|---|---|
| `index.html` | casca nova: barra do topo, seções `#area-dados`, `#area-modelo` e `#area-laboratorio`, e o painel Conjunto |
| `studio.js` | estado global (dados do payload, datasets ligados, ambiente, aplicação e limiares), rotas, chip, tema |
| `conjunto.js` *(novo)* | painel Conjunto |
| `dados.js` *(novo)* | matriz, detalhe da posição, alternador da planta, "ver todas as posições" |
| `modelo.js` *(novo)* | alvo, cartões, comparação, rascunho, avaliação reativa, veredito, barra fixa, receitas |
| `laboratorio.js` *(novo)* | seletor de alvo do Laboratório; monta Features, Desenho e Paralelos |
| `desenho.js` *(novo)* | "Desenhar melhor modelo", extraído de `modelos.js` sem mudança de comportamento |
| `logica.js` *(novo)* | funções puras, sem DOM, usadas pelos módulos acima e testadas com `node --test` |
| `assistente.js`, `modelos.js` | **removidos** depois que o que é reaproveitado migrar |
| `features.js`, `paralelos.js` | passam a desenhar dentro do Laboratório; comportamento igual |
| `planta.js`, `graficos.js` | só as adições da seção 4 |
| `styles.css` | barra do topo, painel, cartões, chips, barra fixa; a barra lateral sai |

`logica.js` exporta, no mínimo:

- `diffRascunho(base, sel)`: devolve `{mais, menos}`;
- `podeAtivar(aval, chaveAtual)`: devolve `{ok, motivo}`, com a regra da seção 5.5;
- `gargalo(rows, thr)`: devolve a métrica e o percentual da seção 4;
- `vooUnico(executar)`: o agendador da seção 5.3 (com atraso, voo único, descarte de resposta velha).

O arquivo é carregado no navegador (`window.VENKO.logica`) e no Node (`module.exports`).

## 8. Erros e estados vazios

- Cada área mostra os próprios erros onde eles acontecem. Exemplos:
  - "Não foi possível avaliar: <detalhe do 422>" no lugar do veredito;
  - "Registro de modelos indisponível" no lugar dos cartões.
- **Nenhum dataset ativo:** Dados e Modelo mostram um estado vazio com o botão "Abrir Conjunto".
- **Job de sugestões perdido** (404, servidor reiniciado): o grupo "Sugeridas" mostra "sugestões indisponíveis · tentar de novo"; o resto funciona.
- **Falha ao salvar ou ativar:** a mensagem aparece no formulário da barra fixa, com o texto do servidor. "Salva, mas não foi possível ativar" continua como hoje.

## 9. Testes

- **Backend** (`unittest` com `TestClient`, em `tests/test_studio_assistente.py`, que já testa as rotas):
  - sem `contra`, a resposta de `avaliar` é igual à de hoje;
  - com `contra`, o denominador do rascunho vem de `base` e a referência vem de `contra` (caso: base `v4`, com eficiência, contra a ativa `v1`);
  - `contra` muda a chave do cache;
  - um `contra` inexistente devolve 404.
- **Front, lógica:** `tests/js/logica.test.js` com `node --test`, sem dependências, cobrindo as quatro funções de `logica.js`. Para `vooUnico`: duas mudanças durante um pedido geram exatamente mais um pedido, com o último estado.
- **Fumaça no navegador:** um script em `tests/` sobe o Studio e tira screenshots com `google-chrome --headless --screenshot` de `#dados`, `#modelo`, `#laboratorio` e `#dados` com o painel aberto, em claro e escuro. O objetivo é olhar as telas de verdade, porque até hoje a UI do Studio nunca foi conferida num navegador.

## 10. Ordem de entrega

Uma spec e um plano. Ao fim de cada fase o Studio funciona:

1. **Casca + Conjunto:** barra do topo, rotas com redirecionamento, chip e painel Conjunto. As telas antigas ficam penduradas temporariamente nas abas novas.
2. **Dados:** `dados.js`, com matriz, detalhe, mini-gráficos, clique na planta e "ver todas as posições".
3. **Modelo:** `contra=` no backend, `logica.js`, `modelo.js` e o estilo.
4. **Laboratório + limpeza:** `laboratorio.js` e `desenho.js`; remover `assistente.js`, `modelos.js` e as seções antigas do `index.html`; screenshots; entrada no `CHANGELOG.md`.

## 11. Fora do escopo

- Mudar a régua, a avaliação ou qualquer número: só muda onde e como os números aparecem.
- Persistir o rascunho entre recargas.
- Progresso real da avaliação (exigiria transformar `avaliar` em job).
- Remover rotas da API que fiquem sem uso.
- Redesenhar as telas do Laboratório.

## 12. Riscos

- **Avaliação reativa pesada.** Cada mudança custa cerca de 20 s de CPU no servidor. O voo único limita a carga a um pedido por vez, mas uma sequência de cliques ainda gera avaliações intermediárias. Se incomodar, o atraso de 0,8 s pode subir.
- **Comparar contra a ativa muda o significado do veredito** para quem estava acostumado ao editor (que comparava com a base). O cartão sempre diz contra quem está comparando.
- **"Atende" em dois sentidos.** Em Dados, ele usa os limiares da sessão; em Modelo, usa `aplicacoes.json`. A linha explicativa na área Modelo existe para isso; se ainda confundir, os chips de limiar podem ganhar o selo "só nesta sessão".
