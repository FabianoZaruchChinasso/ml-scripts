# Correções da revisão de 2026-11-05 — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dar ao experimento "só cliente" uma comparação justa com a v5 (denominador `link_speed_mbps`), parar de duplicar runs no MLflow, e corrigir o que o CHANGELOG e a spec dizem sobre o piso absoluto e a resposta ao Otani.

**Architecture:** o `comodo_benchmark.py` ganha `EXPERIMENTO_DENOMINADOR=<coluna>`: a linha `experimento` passa a prever download e upload como eficiência (`y ÷ coluna`) no 5 GHz, o mesmo mecanismo da v5 (`{'coluna': ..., 'radio': '5ghz'}`, `core/avaliacao.py:57-142`). Com `EXPERIMENTO` definido, o `MLFLOW=1` registra só a linha `experimento`. O resto é texto.

**Tech Stack:** Python 3 (pandas, unittest), MLflow 3.15.1.

**Contexto da revisão (fatos medidos em 2026-11-05, não refaça):**
- A v5 normaliza download por `router_tx_rate_mbps` e upload por `router_rx_rate_mbps` no 5 GHz. O "só cliente" rodou sem denominador, então a perda medida (-0,167) mistura "sem roteador" com "sem normalização".
- `link_speed_mbps` (taxa negociada vista pelo celular) não tem zero nem vazio nas 1710 linhas; no 5 GHz correlaciona 0,57 com o download (o `router_tx_rate_mbps`, 0,63).
- O piso absoluto não aciona nesses dados: a menor referência de casa é 47 Mbps (upload da residência), então só cômodos com razão < ~0,08 cairiam abaixo de 3,8 Mbps, e esses já são ruins pela razão.
- Taxa de falha por posição não resolve o caso da cozinha do Vila: `villa_res_cozinha` tem 0 linhas de falha em 43 (as quedas nunca viraram linha). E "sem enlace" (stats do roteador vazias) não é sinal de Wi-Fi ruim: é 41% do **melhor** cômodo do hotmilk (`hotmilk-copa`) e 100% de `marcelo-quarto`, o que aponta para falha da coleta das stats. Alvo = 0 é raro (no máximo 7 por posição). Por isso o item "taxa de falha" vira requisito de coleta (Task 4), não código.

**Regras do projeto para quem executa:**
- **Nunca rode `git commit` nem `git push`.** Os passos de commit só sugerem a mensagem; o Lucas commita à mão. Sem linha `Co-Authored-By`.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`.
- Sem emojis.
- Trabalhe na branch `regua-hibrida` (já existe, com as mudanças do plano `2026-11-05-regua-hibrida-e-experimentos.md` ainda sem commit).
- Cada execução do benchmark leva ~10 min: rode em segundo plano e espere a notificação; não rode duas em paralelo.
- Testes: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`.

---

## Mapa de arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/comodo_benchmark.py` | `denominador_experimento`, `EXPERIMENTO_DENOMINADOR`, parâmetro `denominador` no MLflow, só a linha `experimento` no MLflow quando houver experimento |
| `tests/test_comodo_benchmark.py` | testes de `denominador_experimento` e do parâmetro novo |
| `CHANGELOG.md` | corrige a entrada de 2026-11-05 |
| `docs/superpowers/specs/2026-10-29-regua-comodo-design.md:81` | descreve o piso absoluto e a versão atual |

---

### Task 1: denominador no experimento

**Files:**
- Modify: `src/ml/comodo_benchmark.py`
- Test: `tests/test_comodo_benchmark.py`

- [ ] **Step 1: testes que falham**

Acrescente ao fim de `tests/test_comodo_benchmark.py`, antes do `if __name__`:

```python
class TestDenominadorExperimento(unittest.TestCase):
  def test_sem_coluna_e_none(self):
    self.assertIsNone(B.denominador_experimento(None))
    self.assertIsNone(B.denominador_experimento(''))

  def test_download_e_upload_no_5ghz(self):
    d = B.denominador_experimento('link_speed_mbps')
    esperado = {'coluna': 'link_speed_mbps', 'radio': '5ghz'}
    self.assertEqual(d, {B.core_comodo.DN: esperado, B.core_comodo.UP: esperado})


class TestMetricasMlflowDenominador(unittest.TestCase):
  def test_registra_o_denominador(self):
    params, _ = B.metricas_mlflow('experimento', ['RSSI'], 'todas', {'nota': 0.6, 'intervalo': None}, -0.1, 0, {},
                                  denominador='link_speed_mbps')
    self.assertEqual(params['denominador'], 'link_speed_mbps')

  def test_sem_denominador_vira_nenhum(self):
    params, _ = B.metricas_mlflow('piso', ['radio'], 'todas', {'nota': 0.4, 'intervalo': None}, 0.0, 0, {})
    self.assertEqual(params['denominador'], 'nenhum')
```

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: os 4 testes novos falham (`AttributeError: ... 'denominador_experimento'` e `TypeError: ... unexpected keyword argument 'denominador'`); os 2 antigos passam.

- [ ] **Step 2: implementar as funções**

Em `src/ml/comodo_benchmark.py`, troque `metricas_mlflow` por:

```python
def metricas_mlflow(nome: str, features, treino: str, r: dict, vs_ativa: float, graves: int, por_predio: dict,
                    denominador: str = None) -> tuple:
  """(parâmetros, métricas) de uma linha da tabela para o run do MLflow."""
  params = {'linha': nome, 'features': ','.join(features), 'n_features': len(features), 'treino': treino,
            'versao_comodo': core_comodo.VERSAO_COMODO, 'denominador': denominador or 'nenhum'}
  metricas = {'comodo_nota': r['nota'], 'vs_ativa': vs_ativa, 'graves': graves}
  if r.get('intervalo'):
    metricas['comodo_lo90'], metricas['comodo_hi90'] = r['intervalo'][0], r['intervalo'][1]
  for site, (acertos, n) in por_predio.items():
    metricas[f'acerto_{site}'] = acertos / n
  return params, metricas
```

e acrescente logo abaixo:

```python
def denominador_experimento(coluna):
  """Denominador da linha 'experimento': `coluna` divide download e upload no 5 GHz, como na v5."""
  if not coluna:
    return None
  por_banda = {'coluna': coluna, 'radio': '5ghz'}
  return {core_comodo.DN: dict(por_banda), core_comodo.UP: dict(por_banda)}
```

Run: `venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: 6 testes, todos PASS.

- [ ] **Step 3: ligar no `main`**

Em `main`, logo depois de `experimento = [...]`:

```python
  exp_den = os.environ.get('EXPERIMENTO_DENOMINADOR') or None
  if exp_den and not experimento:
    raise SystemExit('EXPERIMENTO_DENOMINADOR precisa de EXPERIMENTO')
```

No laço que monta `pos`, troque o ramo do experimento:

```python
    elif nome == EXPERIMENTO:
      features, denominador = experimento, denominador_experimento(exp_den)
```

Na docstring do módulo, depois da frase do `EXPERIMENTO`, acrescente:
`EXPERIMENTO_DENOMINADOR=<coluna> faz a linha 'experimento' prever download e upload como eficiência (alvo ÷ coluna) no 5 GHz, como a v5.`
e troque a frase do `MLFLOW=1` por:
`MLFLOW=1 registra cada linha como um run em 'MLflow Wifi Experimentos'; com EXPERIMENTO, só a linha 'experimento' (piso e versões já têm run próprio).`

- [ ] **Step 4: MLflow sem duplicar**

No bloco `if os.environ.get('MLFLOW') == '1':`, troque o laço e a chamada por:

```python
    registrar = [EXPERIMENTO] if experimento else [PISO] + nomes
    for nome in registrar:
      p = pos[nome]
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      den = exp_den if nome == EXPERIMENTO else (None if nome == PISO else
                                                 json.dumps({a: core_modelos.denominador_de(registro, nome, a)
                                                             for a in (core_comodo.DN, core_comodo.UP)},
                                                            ensure_ascii=False, sort_keys=True))
      params, metricas = metricas_mlflow(nome, features_de[nome], treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p), denominador=den)
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      sufixo = f'-{exp_den}' if nome == EXPERIMENTO and exp_den else ''
      with mlflow.start_run(run_name=f'{nome}-{treino}{sufixo}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {nome}-{treino}{sufixo}')
```

(`json` já é importado no topo do arquivo.)

Run: `venv/bin/python -c "import ast;ast.parse(open('src/ml/comodo_benchmark.py').read())" && venv/bin/python -m unittest tests/test_comodo_benchmark.py -v`
Expected: sem erro de sintaxe; 6 PASS.

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
feat(comodo): denominador na linha experimento do benchmark e MLflow sem runs duplicados
```

---

### Task 2: rodar o "só cliente" com denominador

**Files:** nenhum (só execução).

- [ ] **Step 1: cenário B' (só cliente, treino normal, com denominador)**

Run (em segundo plano):
```
cd /home/venko/ml/TR069/ml-scripts
F=RSSI,link_speed_mbps,channel_width,client_mode,radio,site_survey_same_channel_aps,site_survey_total_aps
MLFLOW=1 MODELO=v5 EXPERIMENTO=$F EXPERIMENTO_DENOMINADOR=link_speed_mbps venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/experimento_B_den.txt 2>&1
```
Expected: no fim, `registrado no MLflow: experimento-todas-link_speed_mbps` (uma linha só). Antes dela, a tabela `Nota` com `piso` 0,452, `v5` 0,722 e `experimento` com a nota nova.

- [ ] **Step 2: cenário C' (só cliente, um dispositivo, com denominador)**

Run (em segundo plano, depois do Step 1 terminar):
```
MLFLOW=1 MODELO=v5 TREINO=sozinhas EXPERIMENTO=$F EXPERIMENTO_DENOMINADOR=link_speed_mbps venv/bin/python src/ml/comodo_benchmark.py > /tmp/claude-1000/experimento_C_den.txt 2>&1
```
Expected: `registrado no MLflow: experimento-sozinhas-link_speed_mbps`.

- [ ] **Step 3: extrair os números**

Run: `grep -E "^  (piso|v5|experimento) |Acertos por prédio" /tmp/claude-1000/experimento_B_den.txt /tmp/claude-1000/experimento_C_den.txt | cut -c1-260`

Monte esta tabela para o CHANGELOG (os valores "sem denominador" são os já medidos):

| Cenário | Sem denominador | Com `link_speed_mbps` | vs v5 | vs piso |
|---|---|---|---|---|
| Só cliente | 0,556 (0,43 a 0,69) | (B') | (B') | (B') |
| Só cliente e um dispositivo | 0,532 (0,40 a 0,66) | (C') | (C') | (C') |

**Reporte ao Lucas** a tabela preenchida e os acertos por prédio do `experimento` em B' e C'. Se o intervalo contra o piso deixar de incluir zero, diga isso em destaque: é a diferença entre "o celular sozinho não serve" e "serve, com perda".

---

### Task 3: CHANGELOG e spec

**Files:**
- Modify: `CHANGELOG.md` (entrada do topo, "Piso absoluto na régua por cômodo e experimentos...")
- Modify: `docs/superpowers/specs/2026-10-29-regua-comodo-design.md:81`

- [ ] **Step 1: corrigir o "Efeito medido" do piso**

No `CHANGELOG.md`, troque o primeiro item de "## Efeito medido" (o que começa com "- Piso absoluto: nenhuma das 27 posições") por:

```
- Piso absoluto: nenhuma das 27 posições mudou de classe (14 bom, 6 degradado, 7 ruim nas duas réguas) e
  as notas de v1 a v5 não mudaram (v1 e v2 0,643; v3, v4 e v5 0,722). Nestes dados o piso não tem como
  acionar: a menor referência de casa é 47 Mbps (upload da residência), então só um cômodo com razão abaixo
  de ~0,08 cairia sob 3,8 Mbps, e esse já é ruim pela razão. O piso protege a casa de internet lenta; não
  responde ao caso da cozinha do Vila (cômodo que mede bem, mas cai), que fica em "Pendente para a coleta".
```

- [ ] **Step 2: tabela dos experimentos e frase do jogo**

Ainda em "## Efeito medido", troque a tabela dos três cenários e os dois parágrafos que vêm depois dela pela tabela abaixo, com os números da Task 2 no lugar de B' e C':

```
| Cenário | Nota (90%) | vs v5 | vs piso |
|---|---|---|---|
| Um dispositivo (v5, treino só com linhas sozinhas) | 0,722 (0,63 a 0,83) | 0,000 | +0,262 melhor |
| Só cliente, sem denominador | 0,556 (0,43 a 0,69) | -0,167 pior | +0,103 empate |
| Só cliente, denominador `link_speed_mbps` | (B') | (B') | (B') |
| Só cliente e um dispositivo, sem denominador | 0,532 (0,40 a 0,66) | -0,191 pior | +0,071 empate |
| Só cliente e um dispositivo, denominador `link_speed_mbps` | (C') | (C') | (C') |

As features "só cliente" são RSSI, link_speed_mbps, channel_width, client_mode, radio,
site_survey_same_channel_aps e site_survey_total_aps (todas presentes nos seis prédios, nenhuma com
vazamento). A v5 normaliza download e upload pela taxa negociada do roteador no 5 GHz; a comparação justa
para o celular é a linha com `link_speed_mbps`, a taxa negociada vista pelo cliente. Com 27 posições os
intervalos são largos: as linhas mostram se há perda, não o tamanho exato dela. Treinar só com um
dispositivo não mudou a nota da v5 (18 de 27 nos dois casos).
```

Depois escreva uma frase de conclusão com os números reais de B' e C': se a linha com denominador ainda empata com o piso, "sem o roteador, mesmo normalizado, o modelo não se distingue do piso"; se passa a ser melhor que o piso, "normalizado pela taxa do cliente, o modelo do celular fica acima do piso e X abaixo da v5".

- [ ] **Step 3: seção "Pendente para a coleta"**

No fim da entrada (depois de "## Efeito medido"), acrescente:

```
## Pendente para a coleta (V2)

- Cômodo que mede bem, mas cai (cozinha do Vila): as quedas nunca viraram linha no dataset
  (`villa_res_cozinha` tem 0 linhas de falha em 43), então nenhuma régua feita sobre estes dados as vê.
  O coletor precisa gravar cada tentativa, inclusive a que desconecta ou não devolve resultado, com
  posição e horário. Com isso a régua pode tratar "fração de tentativas que falharam" como falha de
  Navegação, que é a resposta ao ponto do Otani.
- "Sem enlace" (stats do roteador vazias) não serve como sinal de falha: é 41% do melhor cômodo do
  hotmilk (`hotmilk-copa`) e 100% de `marcelo-quarto`, o que indica falha na coleta das stats, não Wi-Fi
  ruim. Vale checar com o Marcelo e o Fabiano por que o roteador não responde nessas coletas.
```

- [ ] **Step 4: spec**

Em `docs/superpowers/specs/2026-10-29-regua-comodo-design.md`, linha 81, troque o parágrafo por:

```
Limiares: `aplicacoes.carregar_perfil('norma')`. Latência e jitter (`lat`, `jit`) de Navegação, Chamada de vídeo e Jogo em nuvem; desde 2026-11-05 também os mínimos de capacidade (`dn`, `up`) de Navegação (abaixo: ruim) e Chamada de vídeo (abaixo: degradado), para a casa cujo melhor cômodo já é fraco. "Apto para jogo" continua só latência e jitter. Nenhum limiar é copiado no código. Cortes de capacidade relativa: constantes `CORTE_RUIM = 0.25` e `CORTE_BOM = 0.75`. Versão: `VERSAO_COMODO` (atual `2026-11-05.1`); sobe quando cortes, referência, filtro de linhas ou regras mudam.
```

- [ ] **Step 5: sugerir commit (o Lucas commita)**

```
docs: changelog e spec da régua por cômodo com o piso absoluto e o pendente da coleta
```

---

## Fora deste plano

- Apagar do MLflow de trabalho os runs duplicados `v5-sozinhas` e `piso-sozinhas` do cenário C: só com o ok do Lucas.
- Atualizar o snapshot `res/mlflow/` (montado à mão, sem script): decisão do Lucas.
- Implementar a taxa de falha na régua: depende do coletor do V2 gravar as tentativas que falham.
