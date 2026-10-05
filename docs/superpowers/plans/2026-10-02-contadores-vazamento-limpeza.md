# Contadores como vazamento e limpeza do registro: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** marcar os 5 contadores da janela do speedtest como vazamento, acabar com a isenção `normaliza_volume`, reduzir o registro de versões à `v1` e descartar testes que falharam (alvo igual a 0) em todo carregamento de dados.

**Arquitetura:** a classificação vive em `column_provenance.json` e em `core/features.py`. O Studio e o registro de versões leem dali, então mudar a fonte propaga o efeito. O filtro de alvo 0 é uma função única em `core/data.py`, chamada por `load_datasets` (benchmarks e MLflow) e por `studio/features.preparar` (Studio).

**Stack:** Python 3, pandas, unittest. O venv fica em `venv/`. Rode tudo com `source venv/bin/activate` a partir da raiz do repositório.

**Spec:** `docs/superpowers/specs/2026-10-02-contadores-vazamento-limpeza-design.md`

**Regra do repositório:** quem executa o plano **não roda `git commit` nem `git push`**. O usuário commita à mão. No fim de cada tarefa há um passo "Pausa para commit": liste os arquivos alterados e espere.

**Linha de base:** `python -m unittest discover tests` passa 263 testes antes da tarefa 1.

---

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/column_provenance.json` | 5 contadores com `vazamento: true` e `parametro` novo |
| `src/ml/core/features.py` | sai `normaliza_volume`; muda `classificar_derivada`; `CATALOGO_VERSAO` |
| `src/ml/studio/features.py` | sai a chave `normaliza_volume` do inventário; `preparar` chama o filtro |
| `src/ml/studio/static/features.js` | sai a etiqueta "normaliza volume" |
| `src/ml/studio/selecao.py` | comentário de `CONTADORES_VOLUME` |
| `src/ml/core/modelos.json` | só `v1`, ativa |
| `src/ml/studio/api.py` | reserva do registro usa `v1` |
| `src/ml/core/data.py` | nova `descartar_testes_falhos`; `load_datasets` a chama |
| `tests/test_features_core.py` | testes de herança de vazamento e pendente; semente |
| `tests/test_modelos_core.py` | semente do registro |
| `tests/test_ml_core.py` | testes do filtro e de `load_datasets` |
| `tests/test_studio_features.py` | teste de `preparar` com alvo 0 |
| `CHANGELOG.md` | entrada nova no topo |

---

### Tarefa 1: derivada herda vazamento e pendente sem isenção

**Arquivos:**
- Modificar: `src/ml/core/features.py` (dataclass `Derivada` ~linha 187, `CATALOGO_VERSAO` ~209, `CATALOGO` ~211-259, `classificar_derivada` ~345-352)
- Modificar: `src/ml/studio/features.py:168`
- Modificar: `src/ml/studio/static/features.js:184`
- Modificar: `src/ml/studio/selecao.py:31-36`
- Teste: `tests/test_features_core.py`

- [ ] **Passo 1: reescrever os dois testes da isenção**

Em `tests/test_features_core.py`, classe `TestDerivadas`, troque o método `test_vazamento_herdado_e_anulado_por_normaliza_volume` inteiro por:

```python
  def test_razao_herda_vazamento(self):
    t = tabela_exemplo()
    razao = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '')
    self.assertTrue(F.classificar_derivada(razao, t).vazamento)

  def test_derivada_nao_aceita_normaliza_volume(self):
    with self.assertRaises(TypeError):
      F.Derivada('d', ('router_snr',), lambda df: df.router_snr, '', normaliza_volume=True)
```

Na classe `TestContadoresJanela`, troque o método `test_derivada_herda_pendente_salvo_normaliza_volume` inteiro por:

```python
  def test_derivada_herda_pendente(self):
    F.gravar_estado_contadores('nao_sei', self.path)
    t = F.carregar_tabela(self.path)
    d = F.Derivada('d', ('router_tx_duration_us', 'router_snr'), lambda df: df.router_snr, '')
    c = F.classificar_derivada(d, t)
    self.assertTrue(c.pendente)
    self.assertFalse(c.vazamento)

  def test_vazado_e_pendente_juntos_viram_so_vazado(self):
    F.gravar_estado_contadores('nao_sei', self.path)
    t = F.carregar_tabela(self.path)
    # router_tx_bytes vaza pelo prefixo router_tx_; router_rx_duration_us está pendente.
    d = F.Derivada('d', ('router_tx_bytes', 'router_rx_duration_us'), lambda df: df.router_tx_bytes, '')
    c = F.classificar_derivada(d, t)
    self.assertTrue(c.vazamento)
    self.assertFalse(c.pendente)
```

Atenção: em `tabela_exemplo()`, o prefixo `router_tx_` tem `vazamento: True`, mas `gravar_estado_contadores` grava regras exatas para os 5 contadores, e a regra exata ganha do prefixo. Por isso `router_tx_duration_us` fica pendente no estado `'nao_sei'`, enquanto `router_tx_bytes` (sem regra exata) vaza pelo prefixo.

- [ ] **Passo 2: rodar e ver falhar**

Rode: `python -m unittest tests.test_features_core -v 2>&1 | tail -20`
Esperado: FAIL em `test_derivada_nao_aceita_normaliza_volume` (o campo ainda existe) e em `test_vazado_e_pendente_juntos_viram_so_vazado` (hoje `pendente` sai True).

- [ ] **Passo 3: implementar em `src/ml/core/features.py`**

No dataclass `Derivada`, apague a linha:

```python
  normaliza_volume: bool = False
```

Troque a versão do catálogo:

```python
CATALOGO_VERSAO = '2026-10-02.1'
```

No `CATALOGO`, tire o argumento `normaliza_volume=True` das 3 derivadas. Elas ficam assim:

```python
  Derivada('retry_por_pacote', ('router_tx_retries', 'router_tx_packets'),
           _razao('router_tx_retries', 'router_tx_packets'),
           'Retransmissões por pacote enviado: qualidade do enlace, sem depender do volume.'),
  Derivada('falha_por_pacote', ('router_tx_failed', 'router_tx_packets'),
           _razao('router_tx_failed', 'router_tx_packets'),
           'Falhas de envio por pacote.'),
```

```python
  Derivada('descarte_por_pacote_rx', ('router_rx_drop_misc', 'router_rx_packets'),
           _razao('router_rx_drop_misc', 'router_rx_packets'),
           'Pacotes descartados na recepção por pacote recebido.'),
```

Troque `classificar_derivada` inteira por:

```python
def classificar_derivada(derivada: Derivada, tabela: dict) -> Optional[Classificacao]:
  """Classe e vazamento herdados dos insumos.

  Razão entre contadores não cancela o volume: medido em 2026-10-02, retry por
  pacote acompanha o volume (ρ −0,61) quase tanto quanto o alvo (ρ −0,64). Por
  isso qualquer insumo vazado vaza a derivada. Vazamento confirmado não fica
  pendente, como em validar_regra.
  """
  insumos = [classificar(c, tabela) for c in derivada.insumos]
  if any(c is None for c in insumos):
    return None
  classe = 'tr069' if all(c.classe == 'tr069' for c in insumos) else CLASSE_AUXILIAR
  vazamento = any(c.vazamento for c in insumos)
  pendente = any(c.pendente for c in insumos) and not vazamento
  return Classificacao(classe, vazamento, None, 'derivada', pendente)
```

- [ ] **Passo 4: tirar os usos de `normaliza_volume` no Studio**

Em `src/ml/studio/features.py`, no dicionário montado em `inventario` (~linha 168), apague a linha:

```python
      'normaliza_volume': coluna in derivadas and derivadas[coluna].normaliza_volume,
```

Em `src/ml/studio/static/features.js` (~linha 183), troque:

```js
    const tipo = (c) => c.derivada
      ? '<span class="tag">derivada</span>' + (c.normaliza_volume ? ' <span class="tag ok" title="razão entre dois contadores de volume: o volume se cancela">normaliza volume</span>' : '')
      : '<span class="tag">bruta</span>';
```

por:

```js
    const tipo = (c) => c.derivada ? '<span class="tag">derivada</span>' : '<span class="tag">bruta</span>';
```

Em `src/ml/studio/selecao.py`, troque o comentário acima de `CONTADORES_VOLUME = F.CONTADORES_JANELA` por:

```python
# Contadores brutos que crescem com o volume de tráfego. O coletor os mede na janela
# do teste (confirmado em 2026-10-02), então carregam o próprio alvo. As razões por
# pacote (retry_por_pacote, fracao_airtime_tx, ...) herdam esse vazamento. A exclusão
# continua aqui porque o estado pode voltar a "não sei" em Limites e pendências.
```

- [ ] **Passo 5: confirmar que não sobrou referência**

Rode: `grep -rn "normaliza_volume" src tests`
Esperado: nenhuma linha.

- [ ] **Passo 6: rodar e ver passar**

Rode: `python -m unittest tests.test_features_core tests.test_studio_features tests.test_selecao -v 2>&1 | tail -5`
Esperado: `OK`.

- [ ] **Passo 7: pausa para commit**

Arquivos: `src/ml/core/features.py`, `src/ml/studio/features.py`, `src/ml/studio/static/features.js`, `src/ml/studio/selecao.py`, `tests/test_features_core.py`. Sugestão de mensagem: `fix(features): derivada herda vazamento dos insumos, sem isenção por volume`. Não commite: avise o usuário e espere.

---

### Tarefa 2: os 5 contadores da janela como vazamento

**Arquivos:**
- Modificar: `src/ml/core/column_provenance.json`
- Teste: `tests/test_features_core.py` (classe `TestSemente`)

- [ ] **Passo 1: escrever o teste da semente**

Em `tests/test_features_core.py`, classe `TestSemente`, acrescente:

```python
  def test_contadores_da_janela_sao_vazamento(self):
    tabela = F.carregar_tabela()
    self.assertEqual(F.estado_contadores(tabela), 'sim')
    for coluna in F.CONTADORES_JANELA:
      c = F.classificar(coluna, tabela)
      self.assertEqual((c.classe, c.vazamento, c.pendente), ('tr069', True, False), coluna)
    derivadas = {d.nome: d for d in F.CATALOGO}
    for nome in ('retry_por_pacote', 'falha_por_pacote', 'descarte_por_pacote_rx', 'fracao_airtime_tx'):
      self.assertTrue(F.classificar_derivada(derivadas[nome], tabela).vazamento, nome)
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `python -m unittest tests.test_features_core.TestSemente -v 2>&1 | tail -8`
Esperado: FAIL com `'nao' != 'sim'` (o arquivo de trabalho tem a mudança local que tirou o vazamento).

- [ ] **Passo 3: atualizar o JSON**

Rode este script uma vez, da raiz do repositório. Ele usa a gravação atômica do próprio projeto e mantém a ordenação e a formatação do arquivo:

```bash
source venv/bin/activate && python - <<'EOF'
import sys
sys.path.insert(0, 'src')
from ml.core import features as F
from ml.core.arquivos import gravar_json_atomico

PARAMETRO = 'delta da janela do speedtest (~11 s): tx_bytes·8/down ≈ 11 s em todos os prédios'
tabela = F.carregar_tabela()
for coluna in F.CONTADORES_JANELA:
  regra = {'classe': 'tr069', 'vazamento': True, 'parametro': PARAMETRO}
  F.validar_regra(coluna, regra)
  tabela['colunas'][coluna] = regra
gravar_json_atomico(F.TABELA_PATH, tabela)
EOF
```

Depois confira o resultado:

Rode: `git diff src/ml/core/column_provenance.json`
Esperado: só as 5 entradas de `CONTADORES_JANELA` mudam, cada uma com `"vazamento": true` e o `parametro` novo. Se aparecer qualquer outra mudança, como reordenação de chaves ou outra indentação, pare e avise o usuário em vez de seguir.

- [ ] **Passo 4: rodar e ver passar**

Rode: `python -m unittest tests.test_features_core -v 2>&1 | tail -5`
Esperado: `OK`.

- [ ] **Passo 5: pausa para commit**

Arquivos: `src/ml/core/column_provenance.json`, `tests/test_features_core.py`. Sugestão de mensagem: `fix(proveniencia): contadores da janela do speedtest marcados como vazamento`. Não commite: avise o usuário e espere.

---

### Tarefa 3: registro de versões só com `v1`

**Arquivos:**
- Modificar: `src/ml/core/modelos.json`
- Modificar: `src/ml/studio/api.py:79-80`
- Teste: `tests/test_modelos_core.py` (classe `TestSemente`, ~linhas 86-93)

- [ ] **Passo 1: reescrever o teste de semente**

Em `tests/test_modelos_core.py`, troque o método `test_registro_do_repositorio` inteiro por:

```python
  def test_registro_do_repositorio(self):
    reg = M.carregar()
    self.assertEqual(list(reg['versoes']), ['v1'])
    self.assertEqual(reg['ativo'], 'v1')
    self.assertEqual(reg['versoes']['v1']['features'], list(F.MODELO_ATUAL))
    self.assertNotIn('avaliacao', reg['versoes']['v1'])
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `python -m unittest tests.test_modelos_core.TestSemente -v 2>&1 | tail -8`
Esperado: FAIL, porque a lista tem 4 versões.

- [ ] **Passo 3: reescrever o registro**

Rode, da raiz do repositório:

```bash
source venv/bin/activate && python - <<'EOF'
import sys
sys.path.insert(0, 'src')
from ml.core import features as F
from ml.core import modelos as M
from ml.core.arquivos import gravar_json_atomico

DESCRICAO = ('Modelo em produção (MODELO_ATUAL). Desde 2026-10-02, router_rx_drop_misc, '
             'router_rx_duration_us, router_tx_duration_us, router_tx_failed e router_tx_retries '
             'são vazamento (delta da janela do speedtest) e saem da conta na avaliação. '
             'client_opportunity_medium_use não é TR-069.')
antigo = M.carregar()['versoes']['v1-legado']
assert antigo['features'] == list(F.MODELO_ATUAL)
registro = {'ativo': 'v1', 'versoes': {'v1': {
  'features': list(F.MODELO_ATUAL), 'descricao': DESCRICAO,
  'origem': 'MODELO_ATUAL', 'criado_em': antigo['criado_em']}}}
M.validar_registro(registro)
gravar_json_atomico(M.MODELOS_PATH, registro)
EOF
```

Confira: `cat src/ml/core/modelos.json`
Esperado: só a versão `v1`, `"ativo": "v1"`, `"criado_em": "2026-09-25"`, sem `avaliacao` e sem `selecao`.

- [ ] **Passo 4: atualizar a reserva em `src/ml/studio/api.py`**

Em `_registro()`, troque:

```python
    reserva = {'ativo': 'v1-legado', 'versoes': {'v1-legado': {
```

por:

```python
    reserva = {'ativo': 'v1', 'versoes': {'v1': {
```

- [ ] **Passo 5: confirmar que não sobrou referência em código**

Rode: `grep -rn "v1-legado\|v1-sem-cliente\|v2-tr069" src tests --include=*.py --include=*.js --include=*.html`
Esperado: nenhuma linha. Duas exceções são esperadas e ficam como estão: `src/ml/core/derivadas.json`, que guarda o histórico de `taxa_phy_media` e não é coberto por esse grep, e o placeholder `ex.: v2-tr069` em `src/ml/studio/static/modelos.js:438`, que é só texto de exemplo. Se o grep mostrar o placeholder, deixe-o como está.

- [ ] **Passo 6: rodar e ver passar**

Rode: `python -m unittest tests.test_modelos_core tests.test_studio_assistente -v 2>&1 | tail -5`
Esperado: `OK`.

- [ ] **Passo 7: pausa para commit**

Arquivos: `src/ml/core/modelos.json`, `src/ml/studio/api.py`, `tests/test_modelos_core.py`. Sugestão de mensagem: `chore(modelos): registro reduzido à v1; versões v2 descartadas por vazamento`. Não commite: avise o usuário e espere.

---

### Tarefa 4: função `descartar_testes_falhos` e uso em `load_datasets`

**Arquivos:**
- Modificar: `src/ml/core/data.py`
- Teste: `tests/test_ml_core.py` (classe `TestData`, ~linha 262)

- [ ] **Passo 1: escrever os testes**

Em `tests/test_ml_core.py`, troque a linha de import:

```python
from ml.core.data import load_datasets, validate_columns
```

por:

```python
from ml.core.data import descartar_testes_falhos, load_datasets, validate_columns
```

E acrescente à classe `TestData`:

```python
  def test_descartar_testes_falhos_remove_so_zero(self):
    df = pd.DataFrame({'alvo': [0.0, 0.3, np.nan, 50.0, 0]})
    saida, n = descartar_testes_falhos(df, 'alvo')
    self.assertEqual(n, 2)
    self.assertEqual(len(saida), 3)
    self.assertEqual(saida['alvo'].iloc[0], 0.3)
    self.assertTrue(np.isnan(saida['alvo'].iloc[1]))
    self.assertEqual(list(saida.index), [0, 1, 2])

  def test_descartar_testes_falhos_sem_zero_nao_muda_nada(self):
    df = pd.DataFrame({'alvo': [1.0, 2.0]})
    saida, n = descartar_testes_falhos(df, 'alvo')
    self.assertEqual(n, 0)
    self.assertEqual(list(saida['alvo']), [1.0, 2.0])

  def test_rows_with_zero_target_are_dropped(self):
    path = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 2.0},
      {'local': 1.0, 'feat': 1.0, 'target': 0.0},
      {'local': 1.0, 'feat': 1.0, 'target': 0.3},
    ])
    df = load_datasets([path], target='target')
    self.assertEqual(sorted(df['target']), [0.3, 2.0])

  def test_zero_target_kept_when_no_target_is_given(self):
    path = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 0.0},
      {'local': 1.0, 'feat': 1.0, 'target': 2.0},
    ])
    self.assertEqual(len(load_datasets([path])), 2)
```

Confira que `numpy` já está importado como `np` no topo do arquivo (está, na linha 5).

- [ ] **Passo 2: rodar e ver falhar**

Rode: `python -m unittest tests.test_ml_core -v 2>&1 | tail -8`
Esperado: ERROR com `ImportError: cannot import name 'descartar_testes_falhos'`.

- [ ] **Passo 3: implementar em `src/ml/core/data.py`**

Acrescente, depois de `validate_columns`:

```python
def descartar_testes_falhos(df: pd.DataFrame, alvo: str):
  """Remove linhas com alvo exatamente 0: teste que falhou, não enlace ruim.

  Valores pequenos e positivos (ex.: 0,3 Mbps) ficam: são enlaces ruins de
  verdade e são justamente o que o modelo precisa aprender. NaN fica para o
  chamador, que já trata alvo vazio.
  Devolve (df sem essas linhas, com índice refeito, e quantas saíram).
  """
  falhos = pd.to_numeric(df[alvo], errors='coerce') == 0
  return df[~falhos].reset_index(drop=True), int(falhos.sum())
```

Em `load_datasets`, dentro do bloco `if target is not None:`, depois do `if dropped:` que imprime as linhas sem alvo, acrescente:

```python
    df, falhos = descartar_testes_falhos(df, target)
    if falhos:
      print(f'dropped {falhos} rows with failed test (target == 0) {target!r}')
```

Atualize a docstring de `load_datasets`. Troque a linha:

```python
  Rows whose target is empty are dropped and the count reported.
```

por:

```python
  Rows whose target is empty or exactly 0 (failed test) are dropped and the
  counts reported.
```

- [ ] **Passo 4: rodar e ver passar**

Rode: `python -m unittest tests.test_ml_core -v 2>&1 | tail -5`
Esperado: `OK`.

- [ ] **Passo 5: pausa para commit**

Arquivos: `src/ml/core/data.py`, `tests/test_ml_core.py`. Sugestão de mensagem: `feat(data): descarta testes que falharam (alvo == 0) ao carregar`. Não commite: avise o usuário e espere.

---

### Tarefa 5: filtro de testes que falharam no Studio

**Arquivos:**
- Modificar: `src/ml/studio/features.py` (imports no topo e `preparar` ~linhas 57-80)
- Teste: `tests/test_studio_features.py` (classe `TestPreparar`, ~linha 74)

- [ ] **Passo 1: escrever o teste**

Em `tests/test_studio_features.py`, classe `TestPreparar`, acrescente:

```python
  def test_descarta_testes_que_falharam_e_avisa(self):
    f = frame()
    f.loc[0, 'speedtest_down_mbps'] = 0.0
    f.loc[1, 'speedtest_down_mbps'] = 0.3
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(len(conj.df), len(f) - 1)
    self.assertIn(0.3, conj.df['speedtest_down_mbps'].tolist())
    self.assertTrue(any('1 testes que falharam' in a for a in conj.avisos))
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `python -m unittest tests.test_studio_features.TestPreparar -v 2>&1 | tail -8`
Esperado: FAIL, porque o tamanho é `len(f)` e não `len(f) - 1`.

- [ ] **Passo 3: implementar em `src/ml/studio/features.py`**

Acrescente, logo depois de `from ml.core import features as F` (linha 19):

```python
from ml.core.data import descartar_testes_falhos
```

Em `preparar`, logo depois da linha `df = df[df[alvo].notna()]`, acrescente:

```python
  df, falhos = descartar_testes_falhos(df, alvo)
  if falhos:
    avisos.append(f'{falhos} testes que falharam ({alvo} = 0) descartados')
```

`descartar_testes_falhos` já refaz o índice. O resto de `preparar` não depende do índice antigo: ele filtra por `local` e chama `reset_index(drop=True)` de novo.

- [ ] **Passo 4: rodar e ver passar**

Rode: `python -m unittest tests.test_studio_features -v 2>&1 | tail -5`
Esperado: `OK`.

- [ ] **Passo 5: pausa para commit**

Arquivos: `src/ml/studio/features.py`, `tests/test_studio_features.py`. Sugestão de mensagem: `feat(studio): preparar descarta testes que falharam e avisa`. Não commite: avise o usuário e espere.

---

### Tarefa 6: CHANGELOG e verificação final

**Arquivos:**
- Modificar: `CHANGELOG.md` (entrada nova no topo, antes da linha 1 atual)

- [ ] **Passo 1: escrever a entrada**

Insira no topo de `CHANGELOG.md`, seguida de uma linha em branco antes do `# Changelog — Coletor sem zeros falsos...` que já existe:

```markdown
# Changelog — Contadores do roteador como vazamento e limpeza do registro

**Data:** 2026-10-02

## Por quê

Os contadores de volume do roteador são o delta da janela do próprio speedtest:
`router_tx_bytes·8 / speedtest_down_mbps` fica entre 11,2 e 12,5 s em todos os prédios, e os
contadores não são acumulados (só cerca de 45% sobem entre linhas seguidas do mesmo `mac`).
Razões por pacote não cancelam o volume: retry por pacote tem ρ −0,61 com o número de pacotes e
−0,64 com o download.

## Mudanças

- `router_tx_duration_us`, `router_rx_duration_us`, `router_tx_retries`, `router_tx_failed` e
  `router_rx_drop_misc` passam a ser **vazamento** (resposta "sim" em Limites e pendências).
- Fim da isenção `normaliza_volume`: uma derivada vaza se qualquer insumo vazar.
  `retry_por_pacote`, `falha_por_pacote`, `descarte_por_pacote_rx` e `fracao_airtime_tx`
  continuam no catálogo, mas saem de ajustes e versões. Catálogo `2026-10-02.1`.
- Registro de versões reduzido à `v1` (era `v1-legado`), ativa. `v1-sem-cliente`, `v2-tr069` e
  `v2-tr069-volume` foram removidas. Na avaliação, a `v1` perde os 5 contadores, listados em
  `removidas_por_vazamento`.
- Testes que falharam (alvo exatamente 0) são descartados em `load_datasets` e no Studio, com a
  contagem impressa ou nos avisos. Valores pequenos e positivos ficam: são enlaces ruins reais.

## Efeito medido (download, deixando um prédio de fora, RandomForest do Studio, 4 prédios)

| Conjunto | R² pooled | MAE (Mbps) |
|---|---|---|
| Base TR-069 sem contadores | 0,348 | 50,7 |
| + colunas e derivadas físicas que já existem | 0,404 | 47,4 |
| + físicas, sem testes que falharam | 0,439 | 44,7 |

A versão nova do modelo será montada no assistente sobre essa base.

## Fica para depois

- Deadzone temporal no coletor: contadores numa janela que termina antes do teste (`router_pre_*`).
- Teto de WAN da residência.
- Stats de estação ausentes no AX3000 da casa-marcelo e em todo o `20260925`.
```

- [ ] **Passo 2: rodar a suíte inteira**

Rode: `python -m unittest discover tests 2>&1 | tail -4`
Esperado: `OK`, com 263 + 7 = 270 testes. São 7 novos no saldo:
- tarefa 1: +3, -2 (`test_razao_herda_vazamento`, `test_derivada_nao_aceita_normaliza_volume`, `test_derivada_herda_pendente`, `test_vazado_e_pendente_juntos_viram_so_vazado`, no lugar dos 2 antigos);
- tarefa 2: +1;
- tarefa 3: 0;
- tarefa 4: +4;
- tarefa 5: +1.

Se a contagem for outra, confira antes de concluir.

- [ ] **Passo 3: conferir o Studio no navegador**

Suba o Studio com `python src/ml/studio.py` (padrão: http://127.0.0.1:8100; `--port` muda a porta) e confira:
- **Modelos:** a lista mostra só `v1`, ativa.
- **Comparação:** a `v1` aparece com os 5 contadores em "removidas por vazamento".
- **Limites e pendências:** a pergunta dos contadores aparece respondida como "sim".
- **Features:** as 4 derivadas afetadas aparecem como vazamento e não há etiqueta "normaliza volume".
- **Avisos:** com o alvo de download, aparece "N testes que falharam (speedtest_down_mbps = 0) descartados".

Se algum item falhar, reporte com o que apareceu na tela. Não marque a tarefa como concluída.

- [ ] **Passo 4: pausa para commit**

Arquivos: `CHANGELOG.md`. Sugestão de mensagem: `docs(changelog): contadores como vazamento e limpeza do registro`. Não commite: avise o usuário e espere.
