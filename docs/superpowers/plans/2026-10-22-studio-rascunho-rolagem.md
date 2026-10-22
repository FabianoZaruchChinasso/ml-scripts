# Studio: rascunho falso "−5" e página voltando ao topo (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir dois defeitos vistos em 2026-10-22 no Studio da branch `studio-conserto`: (1) clicar num cartão de versão pergunta "Descartar o rascunho (+0 −5)?" sem o usuário ter mudado nada; (2) a página volta para o topo a cada 1,5 s enquanto um job roda.

**Architecture:** Duas mudanças pequenas e independentes no front de `src/ml/studio/static/`.

**Tech Stack:** JS puro, `node --test`.

**Causas (investigadas e medidas, ver conversa de 2026-10-22):**
1. O conserto anterior (`2026-10-22-studio-antigo-conserto.md`, Task 4) faz o rascunho começar sem as colunas com vazamento, mas `diff()` em `modelo.js` compara o rascunho com a versão base completa (`featsBase()`). Partindo da v1, o rascunho sempre aparece com −5 (as 5 colunas com vazamento), então `sujo()` é verdadeiro sem mudança do usuário: a barra "Rascunho" fica sempre visível e clicar noutro cartão pede confirmação.
2. `U.redesenhar` (`util.js`) devolve o foco ao elemento que o tinha com `novo.focus()`, que rola a página até ele. Um cartão de versão clicado fica com o foco; cada redesenho do polling de jobs (reavaliar, salvar, sugestões, a cada 1,5 s) puxa a página de volta ao cartão. Medido: com o foco no cartão `v1`, um redesenho levou a rolagem de 504 para 0; sem foco, ficou em 504.

**Regras do projeto para quem executa:**
- Branch `studio-conserto`. Indentação de 2 espaços.
- **Não rodar `git commit` nem `git push`.** No "Ponto de commit", pare, liste os arquivos e sugira a mensagem (sem `Co-Authored-By`).
- Não editar `src/ml/regression_benchmark.py`, `src/ml/classification_benchmark.py`, `src/ml/core/`, `data/`. **`src/ml/core/modelos.json` já está modificado** (o usuário salvou a versão `v1-5`): não restaure nem altere.
- Não matar processos que você não iniciou. O usuário tem Studios nas portas 8100 e 8300.

---

### Task 1: Rascunho comparado com a base sem vazamento

**Files:**
- Modify: `src/ml/studio/static/logica.js`
- Modify: `src/ml/studio/static/modelo.js`
- Modify: `src/ml/studio/static/index.html`
- Modify: `tests/js/logica.test.js`

- [ ] **Step 1: Teste**

No fim de `tests/js/logica.test.js`:

```js
test('diffContraBase: colunas com vazamento tiradas da base não contam como mudança do rascunho', () => {
  const base = ['router_snr', 'router_tx_retries', 'router_noise'];
  assert.deepEqual(L.diffContraBase(base, ['router_tx_retries'], ['router_snr', 'router_noise']), { mais: [], menos: [] });
  assert.deepEqual(L.diffContraBase(base, ['router_tx_retries'], ['router_snr', 'router_power_dbm']),
    { mais: ['router_power_dbm'], menos: ['router_noise'] });
  assert.deepEqual(L.diffContraBase(base, undefined, ['router_snr']), { mais: [], menos: ['router_noise', 'router_tx_retries'] });
});
```

Antes de escrever, confira o formato de `diffRascunho` (`grep -n "function diffRascunho" -A 6 src/ml/studio/static/logica.js`): se ele não devolver as listas ordenadas como no teste, ajuste as expectativas do teste à ordem que `diffRascunho` já produz. Não mude `diffRascunho`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 1` (`L.diffContraBase is not a function`).

- [ ] **Step 3: Implementar em `logica.js`**

Logo depois da função `semVazamento`:

```js
  // O rascunho começa sem as colunas com vazamento da base: tirá-las não é mudança do usuário.
  const diffContraBase = (base, vazadas, sel) => diffRascunho(semVazamento(base, vazadas).features, sel);

```

E acrescentar `diffContraBase` ao `return` (depois de `semVazamento`).

- [ ] **Step 4: Usar em `modelo.js`**

Antes:
```js
  const diff = () => L.diffRascunho(featsBase(), selLista());
```
Depois:
```js
  const diff = () => L.diffContraBase(featsBase(), (versao(st.base) || {}).vazadas, selLista());
```

`usarBase` fica como está (continua usando `L.semVazamento` para montar o rascunho e o aviso).

- [ ] **Step 5: Cache do navegador**

Em `src/ml/studio/static/index.html`, aumentar em 1 o `?v=N` de `logica.js` e de `modelo.js`.

- [ ] **Step 6: Rodar**

Run: `node --check src/ml/studio/static/modelo.js && node --check src/ml/studio/static/logica.js && node --test tests/js/ 2>&1 | grep -E "^# (pass|fail)"`
Expected: sem erro de sintaxe; `# fail 0`.

---

### Task 2: Devolver o foco sem rolar a página

**Files:**
- Modify: `src/ml/studio/static/util.js`
- Modify: `src/ml/studio/static/index.html`

- [ ] **Step 1: Implementar**

Em `src/ml/studio/static/util.js`, na função `redesenhar`, antes:
```js
    novo.focus();
```
Depois:
```js
    // Sem preventScroll, o polling de jobs (a cada 1,5 s) puxava a página de volta ao elemento focado.
    novo.focus({ preventScroll: true });
```

Em `index.html`, aumentar em 1 o `?v=N` de `util.js`.

Run: `node --check src/ml/studio/static/util.js && echo ok`
Expected: `ok`.

---

### Task 3: Verificação no navegador

- [ ] **Step 1: Subir uma instância própria**

Run (background, guarde o PID): `./venv/bin/python src/ml/studio.py --port 8400`

- [ ] **Step 2: Medir (Playwright)**

Em `http://127.0.0.1:8400/#modelo`, recarregue a página e espere o registro carregar.

1. **Rascunho:** a barra "Rascunho de v1" **não** aparece logo ao abrir (sem mudança do usuário). O aviso "5 colunas com vazamento fora do rascunho" continua lá. Clicar no cartão `v1-5` carrega a `v1-5` **sem** a pergunta "Descartar o rascunho". Tirar uma feature faz a barra aparecer com −1, e só aí clicar noutro cartão pede confirmação (aceite o diálogo do Playwright com cancelar).
2. **Rolagem:** rode no navegador:

```js
async () => {
  const card = document.querySelector('#mCorpo [data-k^="ver-"]');
  card.focus();
  window.scrollTo(0, document.body.scrollHeight);
  const antes = Math.round(window.scrollY);
  const depois = [];
  for (let i = 0; i < 3; i++) { window.VENKO.app.atualizar(); await new Promise((r) => setTimeout(r, 300)); depois.push(Math.round(window.scrollY)); }
  return { antes, depois, foco: document.activeElement.dataset.k };
}
```

Expected: `depois` igual a `antes` nas três medidas (antes da correção ia para 0), e `foco` continua sendo o cartão.

**Não** clicar em Salvar nem Reavaliar (gravariam em `src/ml/core/modelos.json`).

- [ ] **Step 3: Limpar**

Parar só o processo da porta 8400 (pelo PID). Apagar `.playwright-mcp/`. Conferir `git status --short src/ml/core` (deve mostrar só o `M src/ml/core/modelos.json` que já existia, com a `v1-5`).

- [ ] **Step 4: Ponto de commit**

Arquivos: `src/ml/studio/static/logica.js`, `src/ml/studio/static/modelo.js`, `src/ml/studio/static/util.js`, `src/ml/studio/static/index.html`, `tests/js/logica.test.js`.
Mensagem sugerida: `fix(studio): rascunho sem vazamento não conta como alterado e redesenho não rola a página`
