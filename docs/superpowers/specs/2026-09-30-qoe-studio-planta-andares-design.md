# QoE Studio: planta com andares (design)

**Data:** 2026-09-30
**Base:** `qoe-studio-features-planta`, com o `20260928-metrics.zip` e o prédio `casa-marcelo` já cadastrados (`core/sites.py`, `studio/data.py`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

A casa do Marcelo (`casa-marcelo`) tem dois andares. Hoje a view Planta assume **um prédio = um envelope = uma planta 2D**, e o `z` dos pontos é ignorado no front-end. Com isso, pontos dos dois andares caem na mesma planta e se sobrepõem. O ponto (501, 540) é um exemplo: é o roteador no andar de cima e o `marcelo-inf-sala` no de baixo.

A entrega faz a view Planta mostrar **um cartão por andar**, cada um com a sua planta vetorial e só os pontos daquele andar. Prédios sem andares (`casa`, `cowork-pedra-branca`, `hotmilk`) continuam exatamente como estão.

## 2. Material recebido

O Marcelo mandou três arquivos. Ele gera SVGs a partir deles com um script próprio, que não temos.

- `planta-casa-cima.csv` e `planta-casa-baixo.csv`, com colunas `type,id,x1,y1,x2,y2,label,notes` **em metros**. As linhas `type=wall` são paredes e as `type=dim` são cotas. É um formato diferente do CSV atual (`X1_px,Y1_px,X2_px,Y2_px`, em pixels de uma foto).
- `casa.json`, com o roteador `R` e os pontos `P1`–`P6` em cm, no mesmo referencial dos dados (`R` = `router_x/y` = 501, 540). Nas palavras dele, o P3 é para ignorar: "não achei nenhum outro ponto muito interessante de testar no andar de cima", e ainda não se sabe se vai haver coleta lá.

## 3. Achados que moldaram o desenho

**Andar de cada ponto.** Cruzando o `casa.json` com `station_x/y/z` do zip:

| ponto | x, y, z | `local` nos dados |
|---|---|---|
| R (roteador) | 501, 540, 80 | — |
| P1 | 238, 811, 80 | `marcelo-copa`, `marcelo-copa-split` |
| P2 | 340, 1378, 46 | `marcelo-sala-estar` |
| P3 | 15, 15, 80 | nenhum |
| P4 | 135, 135, −160 | `marcelo-inf-ext` (z = −165 nos dados) |
| P5 | 501, 540, −165 | `marcelo-inf-sala`, `marcelo-inf-sala-split` |
| P6 | 232, 1024, −165 | `marcelo-inf-quarto-split` |

O P3 é do andar de cima e tem z = 80. Então **z ≥ 0 é o andar de cima** (onde está o roteador) **e z < 0 é o de baixo**. Isso bate com o prefixo `inf-` (inferior) e com a largura do envelope (861 cm), que é exatamente a largura da planta de cima (3,65 + 2,56 + 2,40 m).

**Inconsistências no dado.** Não são corrigidas aqui, mas vale avisar o Marcelo:
- `marcelo-quarto-split` está em (731, 540, 80), que não aparece no `casa.json`.
- `marcelo-inf-quarto` aparece no P6 (z = −165) e também no P1 (238, 811, 80). No P1 deve ser rótulo trocado.

**Nenhum encaixe por canto do envelope deixa todos os pontos dentro das paredes:**
- Cima: a planta mede 861 × 1348 cm e o envelope 861 × 1448. O P2 (y = 1378) fica além da parede inferior se a origem estiver no topo, e o P3 (y = 15) fica fora se estiver embaixo.
- Baixo: a planta mede 735 × 914 cm. O P6 (y = 1024) fica fora em qualquer canto. O P4 é externo e pode mesmo ficar fora.

Como a escala é conhecida (metros), falta o **deslocamento** de cada andar em relação à origem dos dados. Ele sai da calibração no Studio (seção 6).

## 4. Modelo de dados: `docs/planta/plantas.json`

A entrada do prédio ganha `andares`, opcional. Sem `andares`, vale tudo como hoje (`paredes` em px + `foto`, com encaixe esticado no envelope).

```json
"casa-marcelo": {
  "andares": [
    {"id": "cima",  "z_min": 0,    "paredes": {"arquivo": "planta-casa-cima.csv",  "formato": "metros",
                                               "origem": "superior-esquerdo", "eixo_x": "horizontal", "dx": 0, "dy": 0}},
    {"id": "baixo", "z_min": null, "paredes": {"arquivo": "planta-casa-baixo.csv", "formato": "metros",
                                               "origem": "superior-esquerdo", "eixo_x": "horizontal", "dx": 0, "dy": 0}}
  ]
}
```

- **`id`** é o rótulo exibido no cartão ("Casa do Marcelo · cima").
- **`z_min`** define o piso do andar. O andar de um ponto é o de **maior `z_min` ≤ z**, e `null` significa sem piso (o andar mais baixo). Assim, z = 0 cai em `cima` e z = −165 em `baixo`. A regra não depende do `local`, então coletas futuras entram sem cadastro extra.
- **`paredes.formato`** vale `px` (o padrão, comportamento atual) ou `metros`.
- **`dx`, `dy`** são o deslocamento em cm, aplicado depois do giro (`origem`/`eixo_x`). Só existem no formato `metros`.
- Os dois CSVs do Marcelo são copiados para `docs/planta/` sem alteração, e a entrada acima já vai semeada. Os valores de `dx`/`dy` saem da calibração.
- O `casa.json` **não** entra no Studio: os pontos vêm dos dados. O P3 não aparece porque não há coleta lá.

## 5. Backend

**`studio/plans.py`**
- `ler_paredes_metros(path)`: lê as linhas `type == 'wall'` de `x1,y1,x2,y2` e multiplica por 100 (resultado em cm). Levanta `ValueError` se faltar coluna ou se não houver nenhuma parede.
- `registro_paredes(..., escala=None, dx=0, dy=0)`: com `escala` definida, usa esse fator fixo (1 cm do CSV = 1 cm dos dados) em vez de esticar o contorno no envelope, e soma `dx`/`dy` depois do giro. Sem `escala`, o comportamento é o de hoje.
- `andar_de(z, andares)`: devolve o `id` do andar pela regra do `z_min`, ou `None` se `z` for nulo. É a **única** implementação da regra: o front-end não a repete.
- `montar_plantas`: para um prédio com `andares`, devolve `{'andares': [{'id', 'z_min', 'roteador', 'paredes', 'papel', 'margem_cm', 'foto': None, 'calibracao', 'avisos'}, ...], 'avisos': [...]}`, do andar mais alto para o mais baixo. Cada item tem o mesmo formato da planta de um prédio sem andares, e o erro de um andar não afeta o outro. `roteador` é `True` só no andar de `routerZ`. Um `andares` malformado vira aviso, e o prédio sai como planta simples. Prédios sem `andares` saem idênticos a hoje.
- `salvar_calibracao(predio, paredes, foto, andar=None)`: com `andar`, grava em `andares[i].paredes` (o andar precisa existir) e preserva o resto do arquivo. Valida `formato`, `origem`, `eixo_x` e, se for `metros`, `dx`/`dy` numéricos.

**`studio/data.py`**: o envelope ganha `routerZ` (de `router_z`). Cada linha de um prédio com andares ganha o campo `andar` (via `andar_de`).

**`studio/api.py`**
- `GET api/plan/{predio}/paredes` aceita `formato`, `dx` e `dy`. As paredes não dependem do andar.
- `POST api/plan/{predio}` aceita `andar` no corpo.
- Erros de validação continuam saindo como 422, como hoje.

## 6. Front-end

**`studio.js` / `renderPlan`**
- Cada prédio cuja planta tem `andares` vira **uma entrada por andar**: `{b, andar, label: '<prédio> · <andar>', env, points, planta: <planta do andar>}`.
- Os pontos são filtrados pelo campo `andar` de cada linha, que vem do servidor, e agrupados por `x|y` dentro do andar.
- O roteador só aparece no cartão do andar com `roteador: true`. Os outros andares recebem o `env` sem `routerX/routerY`. Esta é a única mudança em `graficos.js`: hoje o `drawFloorPlan` desenha o marcador sempre (`graficos.js:275`) e passa a pulá-lo quando `routerX` é nulo.
- Os dois andares usam o mesmo envelope (861 × 1448 cm), então saem na mesma escala e alinhados.

**`planta.js`**
- O cartão não muda: continua sendo "um cartão = uma planta".
- O botão "Calibrar planta" leva `b` e `andar`.
- No painel de calibração de um andar em `metros`: seletor de CSV, origem e eixo x como hoje, mais **`dx`/`dy` em cm** (campos numéricos). Cada alteração recarrega a pré-visualização com os pontos do andar por cima. O bloco de foto e cantos fica escondido.
- "Salvar calibração" envia `andar` junto.

## 7. Erros e avisos

Todos seguem o padrão atual: aviso no cartão, e nada derruba a view.

- CSV do andar ilegível ou sem paredes: "paredes ignoradas: …" no cartão daquele andar. O outro andar segue normal.
- Ponto sem `z` num prédio com andares: fica fora da planta, e o primeiro cartão do prédio (o do andar de `z_min` mais alto) avisa "N pontos sem z".
- Andar sem pontos nos dados ativos: o cartão aparece com as paredes e "0 pontos", o que permite calibrar antes da coleta.
- `andar` inexistente, `formato`/`origem`/`eixo_x` inválidos ou `dx`/`dy` não numéricos no `salvar_calibracao`: `ValueError`, e a API responde 422. Salvar sem `andar` num prédio que tem andares também é recusado.

## 8. Testes

Em unittest, nos arquivos existentes.

**`tests/test_plans.py`**
- `ler_paredes_metros`: só as linhas `wall`, multiplicadas por 100. As linhas `dim` são ignoradas, e CSV sem parede levanta erro.
- `registro_paredes` com `escala` fixa: um canto conhecido vai para o ponto esperado, com `dx`/`dy` somados depois do giro.
- `andar_de`: z = 80 dá `cima`, z = 0 dá `cima`, z = −165 dá `baixo`, e z nulo dá `None`.
- `montar_plantas` com andares: dois andares em cm, e o CSV quebrado de um andar não afeta o outro.
- Regressão: a `casa` (sem andares) sai idêntica.
- `salvar_calibracao` com `andar`: grava só aquele andar, preserva os outros prédios e andares, e recusa andar inexistente.

**`tests/test_studio_features.py`**
- O envelope traz `routerZ`.

**Validação manual**
- Subir o Studio (`python3 src/ml/studio.py`).
- Calibrar `dx`/`dy` dos dois andares da casa-marcelo pelo navegador.
- Conferir que P1/P2 caem nos cômodos de cima, P5/P6 nos de baixo, o roteador só no cartão de cima, e que `casa`, `cowork` e `hotmilk` não mudaram.

## 9. Fora do escopo

- Desenhar as linhas `dim` (cotas).
- Foto por andar.
- Criar ou remover andar pela UI (os andares são declarados no `plantas.json`).
- Corrigir no dado o `marcelo-inf-quarto` no P1 e o `marcelo-quarto-split` ausente do `casa.json`.
- Os benchmarks de linha de comando e o treino: andar não vira feature nem grupo de split.
