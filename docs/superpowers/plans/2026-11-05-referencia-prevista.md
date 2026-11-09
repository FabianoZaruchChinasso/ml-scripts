# Régua por cômodo com referência prevista — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** medir, com regra de decisão fixada antes, se classificar cada cômodo previsto contra o **melhor cômodo previsto da casa** (em vez do melhor cômodo real) acerta mais a classe bom / degradado / ruim do que a v5 de hoje.

**Architecture:** a verdade não muda (continua usando a referência real da casa). Só o lado da previsão muda: as medianas previstas por posição passam por `referencia()` (mesma regra da verdade: maior download e maior upload entre posições com pelo menos `MIN_LINHAS_REFERENCIA` linhas) e essa referência prevista substitui a real em `classificar`. Nesta etapa a mudança entra só como opção do `comodo_benchmark.py` (`REF=prevista`); a régua padrão, `VERSAO_COMODO`, o Studio e o `modelos.json` não mudam. Adotar ou não é decisão do Lucas depois do resultado (seção "Regra de decisão").

**Tech Stack:** Python 3 (pandas, numpy, unittest), MLflow 3.15.1.

## Por que (contexto para quem executa)

- A v5 erra 9 de 27 cômodos, todos por subestimar capacidade. Análise SHAP de 2026-10-30: a mesma taxa PHY rende throughput diferente em cada prédio (eficiência de upload de 0,15 a 0,73), e nenhuma feature explica isso. Com o prédio de teste fora do treino, o modelo erra o **nível** da casa inteira, mas tende a acertar a **proporção** entre cômodos.
- Hoje a classe prevista é `previsto ÷ melhor cômodo REAL`: o erro de nível vira erro de classe. Com `previsto ÷ melhor cômodo PREVISTO`, o erro de nível aparece nos dois lados e se cancela.
- Em produção, numa casa nova, o melhor cômodo real não é conhecido; o previsto é. A régua atual usa uma medida da casa de teste dentro da previsão.
- Rascunho de 2026-10-30 (fora do repositório, post hoc): piso 0,452 -> 0,603; v1 0,643 -> 0,889; v3/v5 0,722 -> 0,762. Este plano refaz isso no código do repositório, com intervalo, e decide por regra fixada antes.

## Regra de decisão (fixada antes de rodar; não mude depois de ver os números)

Comparações pareadas nas mesmas 27 posições e na mesma verdade, intervalo de 90% pelas reamostras da régua (`core_comodo.comparar`):

1. **A referência prevista é adotada** se, para a versão ativa (v5), `v5 prevista` contra `v5 real` tiver limite inferior > 0 **e** `v5 prevista` contra `piso prevista` tiver limite inferior > 0.
2. **Troca de versão (v1 no lugar da v5)** só se `v1 prevista` contra `v5 prevista` tiver limite inferior > 0. Empate mantém a v5.
3. Qualquer outro resultado: a régua continua com a referência real; registrar o resultado no CHANGELOG e parar.

São 6 linhas (piso, v1, v2-tr069, v3-tr069, v4, v5); as decisões usam só as três comparações acima. As outras linhas são descritivas.

**Regras do projeto para quem executa:**
- **Nunca rode `git commit` nem `git push`.** Os passos de commit só sugerem a mensagem; o Lucas commita à mão. Sem linha `Co-Authored-By`.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`.
- Sem emojis.
- Trabalhe na branch `regua-hibrida` (tem mudanças de dois planos de 2026-11-05 ainda sem commit; não as reverta).
- O benchmark leva ~10 min: rode em segundo plano e espere a notificação.
- Testes: `PYTHONPATH=src venv/bin/python -m unittest tests/test_comodo.py tests/test_comodo_benchmark.py -v` (o `test_comodo.py` inteiro leva ~9 min; para iterar use `-k` nas classes novas).

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/core/comodo.py` | `estatisticas_previstas`, `referencia_prevista`; `classe_prevista` usa `estatisticas_previstas` |
| `tests/test_comodo.py` | classe `TestReferenciaPrevista` |
| `src/ml/comodo_benchmark.py` | `REF=prevista`: tabela e comparações da referência prevista; parâmetro `referencia` no MLflow |
| `tests/test_comodo_benchmark.py` | parâmetro `referencia` em `metricas_mlflow` |
| `CHANGELOG.md` | entrada com o resultado e a decisão |

---

### Task 1: referência prevista no core

**Files:**
- Modify: `src/ml/core/comodo.py` (função `classe_prevista`, ~linha 140)
- Test: `tests/test_comodo.py`

- [ ] **Step 1: testes que falham**

Em `tests/test_comodo.py`, acrescente antes de `def conjs_sinteticos():`:

```python
def prev_linhas(pos, n, dn, up, lat=10.0, jit=2.0, site='s1'):
  """Previsões no formato de C.prever: uma linha por _linha."""
  return pd.DataFrame({'_linha': [f'{pos}:{i}' for i in range(n)], '_site': [site] * n, '_pos': [pos] * n,
                       'dn': [float(dn)] * n, 'up': [float(up)] * n, 'lat': [lat] * n, 'jit': [jit] * n})


class TestReferenciaPrevista(unittest.TestCase):
  def test_maior_mediana_prevista_por_predio(self):
    prev = juntas(prev_linhas('sala', 10, 400, 380), prev_linhas('quarto', 10, 300, 390),
                  prev_linhas('x', 10, 50, 50, site='s2'))
    ref = C.referencia_prevista(prev)
    self.assertEqual((ref.loc['s1', 'dn'], ref.loc['s1', 'up']), (400.0, 390.0))
    self.assertEqual(ref.loc['s2', 'dn'], 50.0)

  def test_ignora_posicao_com_poucas_linhas(self):
    prev = juntas(prev_linhas('sala', 10, 400, 400), prev_linhas('canto', 9, 900, 900))
    self.assertEqual(C.referencia_prevista(prev).loc['s1', 'dn'], 400.0)

  def test_erro_de_nivel_se_cancela(self):
    # Real: sala 600, quarto 450 (razão 0,75, bom). O modelo previu tudo 1/3 abaixo.
    prev = juntas(prev_linhas('sala', 10, 400, 400), prev_linhas('quarto', 10, 300, 300))
    ref_real = pd.DataFrame({'dn': [600.0], 'up': [600.0]}, index=pd.Index(['s1'], name='_site'))
    com_real = C.classe_prevista(prev, ref_real, LIM)
    com_prevista = C.classe_prevista(prev, C.referencia_prevista(prev), LIM)
    self.assertEqual(com_real.loc['quarto', 'classe'], 'degradado')   # 300 / 600 = 0,50
    self.assertEqual(com_prevista.loc['quarto', 'classe'], 'bom')     # 300 / 400 = 0,75
    self.assertEqual(com_prevista.loc['sala', 'classe'], 'bom')

  def test_estatisticas_previstas_formato(self):
    est = C.estatisticas_previstas(prev_linhas('sala', 4, 100, 50, lat=20.0, jit=3.0))
    self.assertEqual(list(est.columns), ['_site', 'n', 'dn', 'up', 'lat', 'jit'])
    self.assertEqual(est.loc['sala', 'n'], 4)
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestReferenciaPrevista -v`
Expected: 4 ERROR, `AttributeError: module 'ml.core.comodo' has no attribute 'referencia_prevista'` (e `estatisticas_previstas`).

- [ ] **Step 2: implementar**

Em `src/ml/core/comodo.py`, troque a função `classe_prevista` inteira por:

```python
def estatisticas_previstas(prev: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição a partir das previsões: `_site`, `n`, medianas previstas de download, upload
  e dos p90 previstos de latência e jitter (mesmo formato de `estatisticas`)."""
  g = prev.groupby('_pos')
  return pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g['dn'].median(), 'up': g['up'].median(),
                       'lat': g['lat'].median(), 'jit': g['jit'].median()})


def referencia_prevista(prev: pd.DataFrame) -> pd.DataFrame:
  """Referência da casa pelas previsões: o melhor cômodo PREVISTO, com a mesma regra de `referencia`.

  Numa casa nova o melhor cômodo real não é conhecido; o previsto é. Um erro de nível da casa
  inteira (eficiência do prédio que o modelo não vê) aparece no cômodo e na referência e se cancela.
  """
  return referencia(estatisticas_previstas(prev))


def classe_prevista(prev: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Classe de cada posição pela previsão (medianas de download, upload e dos p90 previstos)
  contra a referência `ref`: a da verdade (`verdade`) ou a prevista (`referencia_prevista`)."""
  return classificar(estatisticas_previstas(prev), ref, limiares)
```

Run: `PYTHONPATH=src venv/bin/python -m unittest tests.test_comodo.TestReferenciaPrevista tests.test_comodo.TestClassificar -v`
Expected: tudo PASS.

- [ ] **Step 3: o resto do arquivo continua igual**

Run (em segundo plano, ~9 min): `PYTHONPATH=src venv/bin/python -m unittest tests/test_comodo.py tests/test_studio_comodo.py`
Expected: `OK`. `classe_prevista` mudou só por dentro; `tabela_posicoes` (Studio) segue usando a referência real.

- [ ] **Step 4: sugerir commit (o Lucas commita)**

```
feat(comodo): referência prevista da casa (melhor cômodo previsto)
```

---

### Task 2: `REF=prevista` no benchmark

**Files:**
- Modify: `src/ml/comodo_benchmark.py`
- Test: `tests/test_comodo_benchmark.py`

- [ ] **Step 1: teste que falha**

Acrescente a `tests/test_comodo_benchmark.py`, antes do `if __name__`:

```python
class TestMetricasMlflowReferencia(unittest.TestCase):
  def test_referencia_padrao_real(self):
    params, _ = B.metricas_mlflow('v5', ['a'], 'todas', {'nota': 0.7, 'intervalo': None}, 0.0, 0, {})
    self.assertEqual(params['referencia'], 'real')

  def test_referencia_prevista(self):
    params, _ = B.metricas_mlflow('v5', ['a'], 'todas', {'nota': 0.7, 'intervalo': None}, 0.0, 0, {},
                                  referencia='prevista')
    self.assertEqual(params['referencia'], 'prevista')
```

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: 2 novos falham (`KeyError: 'referencia'` e `TypeError: ... 'referencia'`).

- [ ] **Step 2: parâmetro no MLflow**

Em `metricas_mlflow`, acrescente o argumento `referencia: str = 'real'` depois de `denominador: str = None`, e no dicionário `params` a chave `'referencia': referencia`.

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: 8 PASS.

- [ ] **Step 3: tabela da referência prevista**

Em `src/ml/comodo_benchmark.py`:

1. Docstring do módulo, depois do parágrafo de experimentos, acrescente:
```
REF=prevista calcula também a nota com a referência PREVISTA (melhor cômodo previsto da casa, em vez
do real) e imprime as comparações da regra de decisão de docs/superpowers/plans/2026-11-05-referencia-prevista.md.
```

2. Em `main`, junto da leitura de `TREINO`:
```python
  modo_ref = os.environ.get('REF', 'real')
  if modo_ref not in ('real', 'prevista'):
    raise SystemExit(f'REF={modo_ref!r}: use real ou prevista')
```

3. Antes do laço que monta `pos`, crie `pos_prev = {}`. Dentro do laço, logo depois de `pos[nome] = core_comodo.juntar(...)`:
```python
    if modo_ref == 'prevista':
      pos_prev[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(
          prev, core_comodo.referencia_prevista(prev), limiares))
```

4. Depois do laço que imprime matriz de confusão, acertos e erradas (antes do bloco `if os.environ.get('MLFLOW') == '1':`), acrescente:
```python
  if modo_ref == 'prevista':
    print('\nReferência prevista (melhor cômodo PREVISTO da casa; a verdade não muda)')
    for nome in [PISO] + nomes:
      p = pos_prev[nome]
      r = core_comodo.nota(p, amostras)
      c_real = core_comodo.comparar(p, pos[nome], amostras)
      c_piso = core_comodo.comparar(p, pos_prev[PISO], amostras)
      _, graves = core_comodo.confusao(p)
      print(f'  {nome:<11} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs mesma linha com ref real '
            f'{c_real["diferenca"]:+.3f} ({_faixa(c_real["intervalo"])}) {c_real["resultado"]} | vs piso previsto '
            f'{c_piso["diferenca"]:+.3f} ({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | '
            f'acertos {int((p["real"] == p["previsto"]).sum())}/{len(p)} | graves {graves}')
      print('    acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
    print('\nRegra de decisão')
    a = core_comodo.comparar(pos_prev[ativa], pos[ativa], amostras)
    b = core_comodo.comparar(pos_prev[ativa], pos_prev[PISO], amostras)
    print(f'  1a. {ativa} prevista vs {ativa} real: {a["diferenca"]:+.3f} ({_faixa(a["intervalo"])}) {a["resultado"]}')
    print(f'  1b. {ativa} prevista vs piso previsto: {b["diferenca"]:+.3f} ({_faixa(b["intervalo"])}) {b["resultado"]}')
    print(f'  -> referência prevista {"ADOTADA" if a["resultado"] == "melhor" and b["resultado"] == "melhor" else "não adotada"}')
    if 'v1' in pos_prev and ativa != 'v1':
      c = core_comodo.comparar(pos_prev['v1'], pos_prev[ativa], amostras)
      print(f'  2.  v1 prevista vs {ativa} prevista: {c["diferenca"]:+.3f} ({_faixa(c["intervalo"])}) {c["resultado"]}'
            f' -> {"trocar para v1" if c["resultado"] == "melhor" else f"manter {ativa}"}')
```

5. No bloco `if os.environ.get('MLFLOW') == '1':`, troque tudo a partir de `registrar = ...` até o fim do bloco por (o `vs_ativa` continua contra `pos[ativa]`, a v5 com referência real, que é o número de hoje):
```python
    registrar = [EXPERIMENTO] if experimento else [PISO] + nomes
    pares = [(n, pos, 'real') for n in registrar]
    if modo_ref == 'prevista':
      pares += [(n, pos_prev, 'prevista') for n in registrar]
    for nome, tabela, ref_nome in pares:
      p = tabela[nome]
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      if nome == EXPERIMENTO:
        den = exp_den
      elif nome == PISO:
        den = None
      else:
        den = json.dumps({a: core_modelos.denominador_de(registro, nome, a)
                          for a in (core_comodo.DN, core_comodo.UP)}, ensure_ascii=False, sort_keys=True)
      params, metricas = metricas_mlflow(nome, features_de[nome], treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p), denominador=den, referencia=ref_nome)
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      sufixo = f'-{exp_den}' if nome == EXPERIMENTO and exp_den else ''
      sufixo += '-refprevista' if ref_nome == 'prevista' else ''
      with mlflow.start_run(run_name=f'{nome}-{treino}{sufixo}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {nome}-{treino}{sufixo}')
```

Run: `venv/bin/python -c "import ast;ast.parse(open('src/ml/comodo_benchmark.py').read())" && venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: sintaxe ok; 8 PASS.

- [ ] **Step 4: sugerir commit (o Lucas commita)**

```
feat(comodo): REF=prevista no benchmark, com a regra de decisão da referência prevista
```

---

### Task 3: rodar e decidir

**Files:** nenhum (execução).

- [ ] **Step 1: rodar uma vez**

Run (em segundo plano):
`cd /home/venko/ml/TR069/ml-scripts && MLFLOW=1 REF=prevista venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/referencia_prevista.txt 2>&1`
Expected: termina sem erro; a seção "Nota" (referência real) repete os números de hoje (piso 0,452, v1 0,643, v5 0,722); aparecem as seções "Referência prevista" e "Regra de decisão"; 12 linhas `registrado no MLflow`.

Rode **uma vez**. Não ajuste cortes, features ou a regra depois de ver o resultado.

- [ ] **Step 2: reportar**

Run: `sed -n '/^Referência prevista/,$p' /tmp/claude-1000/referencia_prevista.txt | grep -v '^registrado'`

**Reporte ao Lucas**: a tabela da referência prevista (nota, intervalo, contra a mesma linha com referência real, contra o piso previsto, graves, acertos por prédio) e as três linhas da regra de decisão com o veredito impresso. Compare com o rascunho de 2026-10-30 (piso 0,603, v1 0,889, v3/v5 0,762) e diga se reproduziu.

---

### Task 4: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (nova entrada no topo)

- [ ] **Step 1: escrever**

No topo do `CHANGELOG.md`, uma entrada `# Changelog — Régua por cômodo: referência prevista (experimento)` com `**Data:** 2026-11-05` e as seções:
- `## Por quê`: o parágrafo "Por que" deste plano, resumido em 4 a 6 linhas.
- `## Mudanças`: `estatisticas_previstas` e `referencia_prevista` em `core/comodo.py`; `REF=prevista` no benchmark; parâmetro `referencia` nos runs de "MLflow Wifi Experimentos". A régua padrão, `VERSAO_COMODO`, o Studio e o `modelos.json` não mudaram.
- `## Efeito medido`: a tabela da Task 3 e as três linhas da regra de decisão, com o veredito.
- `## Próximo passo`: se adotada, "levar a referência prevista para a régua padrão (sobe `VERSAO_COMODO`, `tabela_posicoes` do Studio, reavaliar v1 a v5), em plano próprio"; se não, "referência real mantida".

- [ ] **Step 2: sugerir commit (o Lucas commita)**

```
docs: changelog do experimento da referência prevista
```

---

## Fora deste plano

- Levar a referência prevista para a régua padrão e o Studio: só depois da decisão, em plano próprio (precisa do Opus para planejar).
- Candidato 2 (modelo com features relativas à casa): só se a referência prevista não resolver.
