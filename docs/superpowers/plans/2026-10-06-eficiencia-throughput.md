# Throughput como eficiência do enlace (C1) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma versão pode declarar um denominador por alvo (download ÷ `router_tx_rate_mbps`, upload ÷ `router_rx_rate_mbps`): a régua treina na eficiência e devolve Mbps, e a nova `v4-tr069` é medida contra a `v3-tr069`.

**Architecture:** O registro (`core/modelos.py`) ganha o campo opcional `denominador` (`{alvo: coluna}`). `avaliacao.prever_fora_do_fold` ganha `denominador=None`: treina em `y ÷ den`, multiplica a previsão por `den`, imputa `den` vazio com a mediana do treino do fold e marca `den_imputado`. O Studio e `regression_mlflow.py` passam o denominador de cada versão; o rascunho do Assistente herda o da base.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn, MLflow, FastAPI (Studio), JavaScript sem framework. Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-06-eficiencia-throughput-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add` nem `git stash`.** O usuário faz commit à mão.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 373 tests`, `OK`.
- `tests/test_studio_assistente.py` só roda por `discover`: `python3 -m unittest discover -s tests -p "test_studio_assistente.py"`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último.
- Leia cada função antes de editá-la: os trechos "troque X por Y" abaixo citam o código atual pelo conteúdo, não pelo número da linha.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/modelos.py` | Campo `denominador` (validação, `salvar_versao`, `denominador_de`) |
| `src/ml/core/avaliacao.py` | `prever_fora_do_fold`, `avaliar`, `avaliar_versao` com `denominador`; `resumir` com `den_imputados`; régua `2026-10-06.2` |
| `src/ml/studio/features.py` | `comparar` recebe os denominadores das versões |
| `src/ml/studio/api.py` | Comparação, avaliação, promoção, `avaliacao_completa` e salvamento com denominador |
| `src/ml/studio/static/assistente.js` | O salvamento manda `base` |
| `src/ml/studio/static/modelos.js` | Etiqueta "eficiência ÷ tx/rx" nas versões salvas |
| `src/ml/regression_mlflow.py` | Treino na eficiência e `eficiencia.json` |
| `src/ml/core/modelos.json` | Nova `v4-tr069` (via `salvar_versao`) |
| `tests/test_modelos_core.py`, `tests/test_avaliacao.py`, `tests/test_studio_assistente.py` | Testes |
| `CHANGELOG.md` | Entrada nova no topo |

---

### Task 1: Registro com `denominador`

**Files:**
- Modify: `src/ml/core/modelos.py`
- Test: `tests/test_modelos_core.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_modelos_core.py`, acima do bloco `__main__`:

```python
class TestDenominador(Base):
  def registro(self, denominador):
    return {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x',
                                              'denominador': denominador}}}

  def test_denominador_valido(self):
    M.validar_registro(self.registro({'speedtest_down_mbps': 'router_tx_rate_mbps',
                                      'speedtest_up_mbps': 'router_rx_rate_mbps'}))

  def test_denominador_invalido(self):
    for ruim in ({'latency_ms': 'router_snr'}, {'speedtest_down_mbps': ''},
                 {'speedtest_down_mbps': 3}, {}, ['router_snr'], 'router_snr'):
      with self.assertRaises(ValueError, msg=repr(ruim)):
        M.validar_registro(self.registro(ruim))

  def test_salvar_grava_e_le_o_denominador(self):
    M.salvar_versao('v2', ['router_snr'], 'eficiência', CONHECIDAS, TABELA,
                    denominador={'speedtest_down_mbps': 'router_signal_dbm'}, path=self.path)
    reg = M.carregar(self.path)
    self.assertEqual(M.denominador_de(reg, 'v2', 'speedtest_down_mbps'), 'router_signal_dbm')
    self.assertIsNone(M.denominador_de(reg, 'v2', 'speedtest_up_mbps'))
    self.assertIsNone(M.denominador_de(reg, 'v1', 'speedtest_down_mbps'))
    self.assertIsNone(M.denominador_de(reg, 'nao-existe', 'speedtest_down_mbps'))

  def test_salvar_recusa_denominador_desconhecido_ou_com_vazamento(self):
    for coluna in ('nao_existe', 'router_tx_bytes', 'RSSI'):
      with self.assertRaises(ValueError, msg=coluna):
        M.salvar_versao('v2', ['router_snr'], 'x', CONHECIDAS, TABELA,
                        denominador={'speedtest_down_mbps': coluna}, path=self.path)
```

(`router_tx_bytes` é vazamento e `RSSI` é `cliente` na `TABELA` desse arquivo; `router_signal_dbm` é TR-069 e está em `CONHECIDAS`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_modelos_core.TestDenominador -v`
Expected: falhas e erros (`ValueError` não levantado; `unexpected keyword argument 'denominador'`; `has no attribute 'denominador_de'`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/modelos.py`:

1. Troque a linha de `CAMPOS` por:

```python
CAMPOS = {'features', 'descricao', 'origem', 'criado_em', 'avaliacao', 'selecao', 'denominador'}
# Alvos em que a versão pode prever a eficiência (alvo ÷ coluna) em vez de Mbps absolutos.
ALVOS_COM_DENOMINADOR = ('speedtest_down_mbps', 'speedtest_up_mbps')
```

2. Em `validar_registro`, dentro do laço `for nome, versao in versoes.items():`, logo depois da verificação de `features repetidas`, acrescente:

```python
    if 'denominador' in versao:
      den = versao['denominador']
      if (not isinstance(den, dict) or not den or not set(den) <= set(ALVOS_COM_DENOMINADOR)
          or not all(isinstance(c, str) and c.strip() for c in den.values())):
        raise ValueError(f'{nome!r}: denominador precisa ser {{alvo: coluna}}, só para '
                         f'{list(ALVOS_COM_DENOMINADOR)}, com nomes de coluna não vazios')
```

3. Logo depois de `def ativo(registro)`, acrescente:

```python
def denominador_de(registro: dict, nome: str, alvo: str):
  """Coluna que divide o alvo na versão `nome` (eficiência), ou None se ela prevê Mbps absolutos."""
  versao = registro['versoes'].get(nome) or {}
  return (versao.get('denominador') or {}).get(alvo)
```

4. Em `salvar_versao`:
   - acrescente o parâmetro `denominador: Optional[dict] = None` logo antes de `path: str = MODELOS_PATH`;
   - logo depois do bloco que recusa `features com vazamento`, acrescente:

```python
  if denominador:
    colunas = list(denominador.values())
    fora = [c for c in colunas if c not in colunas_conhecidas]
    if fora:
      raise ValueError(f'denominador com colunas que não existem nos datasets: {fora}')
    classes_den = classificar_features(colunas, tabela)
    ruins = [c for c in colunas if classes_den[c] is None or classes_den[c].classe != 'tr069'
             or classes_den[c].vazamento]
    if ruins:
      raise ValueError(f'o denominador precisa ser coluna TR-069 sem vazamento: {ruins}')
```

   - dentro do `with _lock:`, logo depois de `if selecao: versao['selecao'] = selecao`, acrescente:

```python
    if denominador:
      versao['denominador'] = dict(denominador)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_modelos_core -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 2: Régua com denominador

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_avaliacao.py`, acima do bloco `__main__`:

```python
class TestDenominador(Base):
  def conj_com_den(self, valores, alvo='speedtest_down_mbps'):
    f = frame()
    f['router_tx_rate_mbps'] = valores(f)
    return conjunto(alvo, f)

  def test_previsao_e_constante_vezes_denominador(self):
    conj = self.conj_com_den(lambda f: np.where(f['local'].str.startswith('hotmilk'), 600.0, 100.0))
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['hotmilk'], [300.0])
    self.assertEqual(por_site['coworking'], [50.0])
    self.assertFalse(prev['den_imputado'].any())

  def test_treina_na_eficiencia(self):
    conj = self.conj_com_den(lambda f: np.full(len(f), 10.0))
    alvos = []

    class Espiao(Constante):
      def fit(self, X, y):
        alvos.append(np.asarray(y, dtype=float))
        return super().fit(X, y)

    A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Espiao(0.0),
                          denominador='router_tx_rate_mbps')
    reais = conj.df['speedtest_down_mbps'].to_numpy(dtype=float) / 10.0
    self.assertTrue(all(np.all(np.isin(np.round(a, 6), np.round(reais, 6))) for a in alvos))

  def test_teto_depois_da_multiplicacao(self):
    conj = self.conj_com_den(lambda f: np.full(len(f), 1000.0))
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['residencia'], [154.0])
    self.assertEqual(por_site['hotmilk'], [500.0])

  def test_den_vazio_usa_a_mediana_do_treino_do_fold(self):
    def valores(f):
      v = np.where(f['local'].str.startswith('hotmilk'), 1000.0, 100.0)
      v[(f['local'] == 'hotmilk-copa').to_numpy()] = np.nan
      return v
    conj = self.conj_com_den(valores)
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    copa, aquario = prev[prev['_pos'] == 'hotmilk-copa'], prev[prev['_pos'] == 'hotmilk-aquario']
    # O treino do fold do hotmilk é residência + coworking, todos com 100: a mediana é 100, não 1000.
    self.assertEqual(copa['yhat'].unique().tolist(), [50.0])
    self.assertTrue(copa['den_imputado'].all())
    self.assertEqual(aquario['yhat'].unique().tolist(), [500.0])
    self.assertFalse(aquario['den_imputado'].any())
    self.assertEqual(A.avaliar(conj, ['router_snr'], [], denominador='router_tx_rate_mbps')['den_imputados'],
                     len(copa))

  def test_sem_denominador_nada_muda(self):
    conj = conjunto()
    a = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(7.0))
    b = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(7.0), denominador=None)
    np.testing.assert_allclose(a['yhat'], b['yhat'])
    self.assertFalse(a['den_imputado'].any())

  def test_denominador_inexistente_levanta(self):
    conj = conjunto()
    with self.assertRaisesRegex(ValueError, 'nao_existe'):
      A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], denominador='nao_existe')

  def test_resumir_sem_a_coluna(self):
    r = A.resumir(pd.DataFrame({'_linha': ['a', 'b'], 'y': [1.0, 2.0], 'yhat': [1.0, 2.0],
                                '_site': ['s', 's'], '_pos': ['p', 'q']}), 1)
    self.assertEqual(r['den_imputados'], 0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestDenominador -v 2>&1 | tail -12`
Expected: erros com `unexpected keyword argument 'denominador'` e `KeyError: 'den_imputado'`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/avaliacao.py`:

1. Troque `VERSAO_REGUA = '2026-10-06.1'` por `VERSAO_REGUA = '2026-10-06.2'`.
2. Troque `_COLUNAS_PREVISAO` por:

```python
_COLUNAS_PREVISAO = ['_linha', 'y', 'yhat', 'den_imputado', '_site', '_pos']
# Abaixo disto a taxa PHY é sinal de leitura ruim, não de enlace: a linha usa a mediana do treino.
DEN_MINIMO = 1.0
```

3. Troque a função `prever_fora_do_fold` inteira por:

```python
def prever_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas, arvores: int = None,
                        min_teste: int = 1, min_treino: int = 1, estimador=None,
                        ao_ajustar=None, denominador: str = None) -> pd.DataFrame:
  """Previsão de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Para download e upload, linhas `_limitado_wan` saem do treino e a previsão é
  cortada no teto de WAN do prédio de teste. `estimador` troca o modelo da régua
  (é clonado a cada fold); `ao_ajustar(fold, modelo)` é chamado depois de cada ajuste.
  Com `denominador` (nome de coluna), o modelo aprende a eficiência `y ÷ den` e a
  previsão volta para a unidade do alvo multiplicando por `den`; `den` vazio ou menor
  que DEN_MINIMO vira a mediana das linhas de treino do fold, e a linha fica com
  `den_imputado`. O teto de WAN é aplicado depois da multiplicação.
  Devolve colunas _linha, y, yhat, den_imputado, _site, _pos, indexadas como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  sub = df[df[y_col].notna()]
  den = None
  if denominador is not None:
    if denominador not in sub.columns:
      raise ValueError(f'denominador {denominador!r} não existe no conjunto')
    den = pd.to_numeric(sub[denominador], errors='coerce')
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  com_teto = y_col in ALVOS_COM_TETO
  limitado = pd.Series(False, index=sub.index)
  if com_teto and '_limitado_wan' in sub.columns:
    limitado = sub['_limitado_wan'].astype(bool)
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y, sub['_site']):
    treino = ~limitado.loc[fold.X_train.index].to_numpy()
    if len(fold.y_test) < min_teste or int(treino.sum()) < min_treino:
      continue
    alvo_treino = fold.y_train[treino]
    imputado = np.zeros(len(fold.y_test), dtype=bool)
    if den is not None:
      den_treino = den.loc[fold.X_train.index]
      validos = (den_treino >= DEN_MINIMO).to_numpy() & treino
      if not validos.any():
        raise ValueError(f'nenhuma linha de treino com {denominador!r} válido no fold de {fold.test_site!r}')
      mediana = float(den_treino[validos].median())
      den_treino = den_treino.where(den_treino >= DEN_MINIMO, mediana).to_numpy()
      den_teste = den.loc[fold.X_test.index]
      imputado = ~(den_teste >= DEN_MINIMO).to_numpy()
      den_teste = den_teste.where(den_teste >= DEN_MINIMO, mediana).to_numpy()
      alvo_treino = alvo_treino / den_treino[treino]
    modelo = clone(estimador) if estimador is not None else modelo_regua(arvores)
    modelo.fit(fold.X_train[treino], alvo_treino)
    previsto = np.asarray(modelo.predict(fold.X_test), dtype=float)
    if den is not None:
      previsto = previsto * den_teste
    teto = teto_wan(fold.test_site, y_col) if com_teto else None
    if teto is not None:
      previsto = np.minimum(previsto, teto)
    if ao_ajustar is not None:
      ao_ajustar(fold, modelo)
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': fold.y_test.to_numpy(),
                                'yhat': previsto, 'den_imputado': imputado, '_site': fold.test_site,
                                '_pos': posicao.loc[indice].to_numpy()}, index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  return pd.concat(partes)
```

4. Em `resumir`, antes de `resumo['versao_regua'] = VERSAO_REGUA`, acrescente:

```python
  resumo['den_imputados'] = (int(prev['den_imputado'].astype(bool).sum())
                             if 'den_imputado' in prev.columns else 0)
```

5. Troque `avaliar` e `avaliar_versao` inteiras por:

```python
def avaliar(conj, features, vazadas, com_previsoes: bool = False, denominador: str = None):
  """LOGO por local de coleta de uma lista de features, como está.

  Feature ausente do conjunto sai da conta e é listada; feature com vazamento
  levanta (assert_sem_vazamento), nunca é descartada em silêncio. `denominador`
  faz o modelo prever a eficiência (ver prever_fora_do_fold). Com `com_previsoes`,
  devolve (resumo, previsões fora do fold).
  """
  presentes = [f for f in features if f in conj.df.columns]
  prev = prever_fora_do_fold(conj.df, presentes, conj.alvo, vazadas, denominador=denominador)
  resumo = resumir(prev, len(presentes))
  resumo['ausentes'] = [f for f in features if f not in conj.df.columns]
  resumo['denominador'] = denominador
  return (resumo, prev) if com_previsoes else resumo


def avaliar_versao(conj, features, vazadas, com_previsoes: bool = False, denominador: str = None):
  """Como avaliar, mas uma versão salva que usa coluna hoje marcada como vazamento é
  avaliada sem ela, e a lista sai em `removidas_por_vazamento`. Assim a comparação
  continua de pé quando alguém confirma um vazamento depois de a versão existir."""
  removidas = [f for f in features if f in vazadas]
  saida = avaliar(conj, [f for f in features if f not in vazadas], vazadas, com_previsoes, denominador)
  resumo = saida[0] if com_previsoes else saida
  resumo['removidas_por_vazamento'] = removidas
  return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 3: Studio com o denominador de cada versão

**Files:**
- Modify: `src/ml/studio/features.py` (`comparar`)
- Modify: `src/ml/studio/api.py`
- Modify: `src/ml/studio/static/assistente.js`, `src/ml/studio/static/modelos.js`
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_assistente.py`, acrescente `import types` aos imports do topo e, acima do bloco `__main__`, uma classe nova:

```python
REGISTRO_DEN = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'teste', 'denominador': {'speedtest_down_mbps': 'router_snr'}},
  'v2': {'features': ['router_snr'], 'descricao': 'absoluta'}}}


class TestDenominadorNaApi(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.patches = [mock.patch.object(api, '_conjunto', return_value=(conj, None)),
                    mock.patch.object(api, '_registro', return_value=(REGISTRO_DEN, None)),
                    mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr', 'router_signal_dbm'})]
    for p in self.patches:
      p.start()
    api._modelos_cache.clear()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def denominadores_usados(self, chamada):
    with mock.patch.object(A, 'prever_fora_do_fold', wraps=A.prever_fora_do_fold) as espiao:
      chamada()
    return [c.kwargs.get('denominador') for c in espiao.call_args_list]

  def test_rascunho_herda_o_denominador_da_base(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(features='router_snr,router_signal_dbm',
                                                                   ds='a.csv', base='v1'))
    self.assertIn('router_snr', usados)
    self.assertNotIn(None, usados)

  def test_promocao_contra_base_absoluta(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(features='router_snr,router_signal_dbm',
                                                                   ds='a.csv', base='v2'))
    self.assertEqual(set(usados), {None})

  def test_comparar_usa_o_denominador_de_cada_versao(self):
    r = api.modelos_comparar(ds='a.csv')
    por_nome = {v['nome']: v for v in r['versoes']}
    self.assertEqual(por_nome['v1']['denominador'], 'router_snr')
    self.assertIsNone(por_nome['v2']['denominador'])

  def test_salvar_copia_o_denominador_da_base(self):
    pedido = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
    corpo = api.NovaVersao(nome='v9', features=['router_snr'], descricao='x', ds='a.csv', base='v1')
    with mock.patch.object(api.core_modelos, 'salvar_versao') as salvar:
      api.modelos_salvar(corpo, pedido)
    self.assertEqual(salvar.call_args.kwargs['denominador'], {'speedtest_down_mbps': 'router_snr'})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -15`
Expected: falhas em `TestDenominadorNaApi` (denominador não repassado; `KeyError: 'denominador'`; `base` não aceito em `NovaVersao`).

- [ ] **Step 3: `studio/features.comparar`**

Em `src/ml/studio/features.py`, troque a assinatura e a linha que monta `resultado` em `comparar`:

```python
def comparar(conj: Conjunto, inv: dict, versoes: dict, ativo: str, denominadores: dict = None) -> dict:
  """Avalia cada versão salva mais as duas referências: TR-069 completo e Tudo.

  `denominadores` ({nome: {alvo: coluna}}) faz cada versão ser avaliada com o seu.
  """
```

```python
    resultado = [dict(avaliar_versao(conj, feats, vazadas,
                                     denominador=((denominadores or {}).get(nome) or {}).get(conj.alvo)),
                      nome=nome, ativo=nome == ativo)
                 for nome, feats in versoes.items()]
```

- [ ] **Step 4: API**

Em `src/ml/studio/api.py`:

1. Depois de `_versoes_por_nome`, acrescente:

```python
def _denominadores(registro) -> dict:
  return {nome: v.get('denominador') or {} for nome, v in registro['versoes'].items()}
```

2. Em `modelos_comparar`, troque a chamada de `studio_features.comparar(...)` por:

```python
      _modelos_cache[chave] = studio_features.comparar(conj, inv, _versoes_por_nome(registro),
                                                       registro['ativo'], _denominadores(registro))
```

3. Troque `_prever_pontual` e `_promocao` inteiras por:

```python
def _prever_pontual(c, lista, denominador: dict = None):
  presentes, vazadas = _presentes(c, lista)
  return core_avaliacao.prever_fora_do_fold(c.df, presentes, c.alvo, vazadas,
                                            denominador=(denominador or {}).get(c.alvo))


def _promocao(ds: str, ambiente: str, alvo: str, feats: list, feats_base: list, conj,
              den_nova: dict = None, den_base: dict = None) -> dict:
  """Veredito de promoção da régua contra a versão base.

  Latência e jitter: Δ pinball do p90 e cobertura da nova versão. Download e upload:
  Δ MAE e Δ "atende em throughput", cada lado com o seu denominador ({alvo: coluna}).
  """
  if alvo in core_quantis.ALVOS_QUANTILICOS:
    nova = _prever_quantis(conj, feats)
    d_pinball = core_quantis.delta_pinball(nova, _prever_quantis(conj, feats_base))
    cobertura = round(core_quantis.cobertura(nova['y'], nova['q90']), 4)
    return {'delta_pinball': d_pinball, 'cobertura': cobertura,
            'veredito': core_quantis.veredito_quantis(d_pinball, cobertura),
            'versao_regua': core_avaliacao.VERSAO_REGUA}
  d_mae = core_avaliacao.delta_mae(_prever_pontual(conj, feats, den_nova),
                                   _prever_pontual(conj, feats_base, den_base))
  d_atende = None
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    d_atende = core_avaliacao.delta_atende(_prever_pontual(dn, feats, den_nova), _prever_pontual(up, feats, den_nova),
                                           _prever_pontual(dn, feats_base, den_base),
                                           _prever_pontual(up, feats_base, den_base),
                                           core_aplicacoes.carregar())
  return {'delta_mae': d_mae, 'delta_atende': d_atende,
          'veredito': core_avaliacao.veredito_promocao(d_mae, d_atende),
          'versao_regua': core_avaliacao.VERSAO_REGUA}
```

4. Em `modelos_avaliar`:
   - logo depois de `vazadas = studio_features.vazadas_do_conjunto(conj)`, acrescente:

```python
    # O rascunho herda o denominador da versão de onde partiu (ou da ativa, sem base).
    den_nova = registro['versoes'][base or registro['ativo']].get('denominador') or {}
    den_base = (registro['versoes'][base].get('denominador') or {}) if base else {}
```

   - troque `resumo = studio_features.avaliar(conj, feats, vazadas)` por:

```python
      resumo = studio_features.avaliar(conj, feats, vazadas, denominador=den_nova.get(alvo))
```

   - troque a linha de `saida['resumo_base'] = ...` por:

```python
        saida['resumo_base'] = studio_features.avaliar_versao(conj, registro['versoes'][base]['features'], vazadas,
                                                              denominador=den_base.get(alvo))
```

   - troque a linha de `saida['promocao'] = ...` por:

```python
        saida['promocao'] = _promocao(ds, ambiente, alvo, feats, registro['versoes'][base]['features'], conj,
                                      den_nova, den_base)
```

5. Em `avaliacao_completa`, troque a assinatura e a chamada de `core_avaliacao.avaliar`:

```python
def avaliacao_completa(ds: str, ambiente: str, features: list, denominador: dict = None) -> dict:
```

```python
    resumo, previsoes[alvo] = core_avaliacao.avaliar(conj, features, studio_features.vazadas_do_conjunto(conj),
                                                     com_previsoes=True,
                                                     denominador=(denominador or {}).get(alvo))
```

6. Em `NovaVersao`, acrescente o campo `base: Optional[str] = None`. Em `modelos_salvar`, logo depois do bloco que recusa nome existente, acrescente:

```python
  if corpo.base and corpo.base not in registro['versoes']:
    raise HTTPException(422, f'versão base {corpo.base!r} não existe')
  # Mesma regra da avaliação do rascunho: herda o denominador da base (ou da ativa).
  denominador = registro['versoes'][corpo.base or registro['ativo']].get('denominador') or None
```

   e troque as duas chamadas dentro do `try`:

```python
    avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, corpo.features, denominador)
    core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, _colunas_conhecidas(),
                               tabela, origem='selecao-gulosa' if selecao else 'studio',
                               avaliacao=avaliacao, selecao=selecao, denominador=denominador)
```

- [ ] **Step 5: Interface**

1. `src/ml/studio/static/assistente.js`: troque

```js
    post('api/modelos', { nome, descricao: st.desc, features: selLista(), ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente })
```

por

```js
    post('api/modelos', { nome, descricao: st.desc, features: selLista(), ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente, base: st.base })
```

2. `src/ml/studio/static/modelos.js`, em `cardVersoes`: troque

```js
        <td><code>${esc(v.nome)}</code>${v.ativo ? ' <span class="tag current">ativo</span>' : ''}
```

por

```js
        <td><code>${esc(v.nome)}</code>${v.ativo ? ' <span class="tag current">ativo</span>' : ''}${(() => {
          const den = (v.denominador || {})[st.alvo];
          if (!den) return '';
          const lado = den.includes('_tx_') ? 'tx' : den.includes('_rx_') ? 'rx' : den;
          return ` <span class="tag mid" title="prevê a eficiência (alvo ÷ ${esc(den)}) e volta para Mbps">eficiência ÷ ${esc(lado)}</span>`;
        })()}
```

Run: `for f in modelos assistente; do node --check src/ml/studio/static/$f.js && echo "ok $f"; done`
Expected: `ok modelos` e `ok assistente`

- [ ] **Step 6: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 4: `regression_mlflow.py` na eficiência

**Files:**
- Modify: `src/ml/regression_mlflow.py` (`main`, docstring do topo)

- [ ] **Step 1: Implementar**

1. Na docstring do topo, acrescente ao fim: `Se a versão tiver denominador para o ALVO (core/modelos.json), o modelo aprende a eficiência (alvo ÷ coluna) e eficiencia.json diz como voltar para Mbps.`

2. Em `main`, logo depois de `validate_columns(conj.df, features, 'feature')`, acrescente:

```python
  denominador = core_modelos.denominador_de(registro, nome_modelo, ALVO)
  if denominador:
    validate_columns(conj.df, [denominador], 'denominador')
```

3. No dicionário `params`, acrescente a chave `'denominador': denominador or ''`.

4. Troque o bloco que vai de `treino = ~conj.df['_limitado_wan']` até `y_final = conj.df.loc[treino, ALVO].astype(float)` por:

```python
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  y_final = conj.df.loc[treino, ALVO].astype(float)
  eficiencia = None
  if denominador:
    den = pd.to_numeric(conj.df.loc[treino, denominador], errors='coerce')
    mediana = float(den[den >= core_avaliacao.DEN_MINIMO].median())
    y_final = y_final / den.where(den >= core_avaliacao.DEN_MINIMO, mediana)
    eficiencia = {'alvo': ALVO, 'denominador': denominador, 'mediana_imputacao': mediana,
                  'den_minimo': core_avaliacao.DEN_MINIMO,
                  'uso': 'mbps = predict(X) * denominador (vazio ou abaixo de den_minimo: mediana_imputacao)'}
```

5. No laço `for config in CONFIGS:`, troque a linha do `prev = ...` por:

```python
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config),
                                                denominador=denominador)
```

   e, logo depois de `mlflow.sklearn.log_model(...)`, acrescente:

```python
      if eficiencia:
        mlflow.log_dict(eficiencia, 'eficiencia.json')
        mlflow.log_metric('den_imputados', resumo['den_imputados'])
```

6. Acrescente `import pandas as pd` aos imports do topo, junto de `import numpy as np`.

- [ ] **Step 2: Conferir import**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); import ml.regression_mlflow as m; print(m.ALVO)"`
Expected: `speedtest_down_mbps`

(A rodada de verdade fica para a Task 5, depois que a `v4-tr069` existir.)

---

### Task 5: `v4-tr069`, experimento e CHANGELOG

**Files:**
- Modify: `src/ml/core/modelos.json` (via `salvar_versao`)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Salvar a `v4-tr069`**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys; sys.path.insert(0, 'src')
from ml.core import carga as C, features as F, modelos as M
from ml.studio import api
ds = ','.join(C.ids_padrao(C.descobertos()))
v3 = M.carregar()['versoes']['v3-tr069']['features']
den = {'speedtest_down_mbps': 'router_tx_rate_mbps', 'speedtest_up_mbps': 'router_rx_rate_mbps'}
av = api.avaliacao_completa(ds, '', v3, den)
M.salvar_versao('v4-tr069', v3,
  'v3-tr069 prevendo a eficiência do enlace: download ÷ taxa PHY de envio, upload ÷ taxa PHY de recepção '
  '(spec 2026-10-06, frente C1).', api._colunas_conhecidas(), F.carregar_tabela(), origem='studio',
  avaliacao=av, denominador=den)
reg = M.carregar()
print('ativo', reg['ativo'], '| v4 denominador', reg['versoes']['v4-tr069']['denominador'])
EOF
```

Expected: `ativo v1 | v4 denominador {...}`. Se `salvar_versao` levantar porque a `v4-tr069` já existe, pare e reporte (não escolha outro nome).

- [ ] **Step 2: Medir `v3-tr069` contra `v4-tr069`**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
import numpy as np
from ml.core import carga as C, modelos as M, avaliacao as A, aplicacoes as AP
from ml.studio import api
reg = M.carregar(); ds = ','.join(C.ids_padrao(C.descobertos()))
prev = {}
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  conj = C.carregar(alvo)
  vaz = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  for nome in ('v3-tr069', 'v4-tr069'):
    r, prev[(nome, alvo)] = A.avaliar(conj, reg['versoes'][nome]['features'], vaz, com_previsoes=True,
                                      denominador=M.denominador_de(reg, nome, alvo))
    print(alvo, nome, 'R2', r['pooled'], r['intervalos']['pooled'], 'MAE', r['mae'], r['intervalos']['mae'],
          'MAElog', r['mae_log'], 'den_imputados', r['den_imputados'])
    print('   R2 por prédio', r['por_local'], '\n   MAE por prédio', r['mae_por_local'])
apps = AP.carregar()
for nome in ('v3-tr069', 'v4-tr069'):
  at = A.atende(prev[(nome, 'speedtest_down_mbps')], prev[(nome, 'speedtest_up_mbps')], apps)
  print(nome, 'atende_throughput', at['media'], at['intervalo'], at['por_aplicacao'])
  ac = api.avaliacao_completa(ds, '', reg['versoes'][nome]['features'], reg['versoes'][nome].get('denominador'))
  print(nome, 'atende_completo', ac['atende_completo']['media'], ac['atende_completo']['intervalo'])
# Critério da C2 (spec, seção 8)
p = prev[('v4-tr069', 'speedtest_down_mbps')]
erro = (p['y'] - p['yhat']).abs()
mae_hot, mae_outros = erro[p['_site'] == 'hotmilk'].mean(), erro[p['_site'] != 'hotmilk'].mean()
print('C2: MAE hotmilk', round(mae_hot, 2), '| MAE outros três', round(mae_outros, 2),
      '| razão', round(mae_hot / mae_outros, 2), '| entra C2:', bool(mae_hot > 2 * mae_outros))
v3, v4 = reg['versoes']['v3-tr069'], reg['versoes']['v4-tr069']
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  conj, _ = api._conjunto(ds, alvo, '')
  r = api._promocao(ds, '', alvo, v4['features'], v3['features'], conj, v4.get('denominador'), v3.get('denominador'))
  print(alvo, 'promocao v4 contra v3', json.dumps(r, ensure_ascii=False))
EOF
```

Expected: duas linhas por alvo e versão, as linhas de "atende", a linha da C2 e um veredito por alvo. Anote todos os números.

- [ ] **Step 3: Rodada real no MLflow**

Run: `MODELO=v4-tr069 timeout 580 python3 src/ml/regression_mlflow.py 2>&1 | grep -v Warning | tail -8`
Expected: os 6 blocos de configuração com R² e MAE (sem traceback).

Run: `python3 -c "import mlflow; c = mlflow.MlflowClient(); r = c.search_runs([c.get_experiment_by_name('MLflow Wifi Regressions').experiment_id], order_by=['start_time DESC'], max_results=1)[0]; print(r.info.run_name, r.data.params.get('denominador')); print([a.path for a in c.list_artifacts(r.info.run_id)])"`
Expected: o nome de um run da `v4-tr069`, `router_tx_rate_mbps` e `eficiencia.json` entre os artefatos.

- [ ] **Step 4: CHANGELOG**

No topo de `CHANGELOG.md`, antes da entrada da CQR, no mesmo estilo das entradas existentes. Use **só** números impressos nos Steps 2 e 3 (e os da seção 2 da spec, citando-a, para a tabela de exploração):

- **Por quê:** as árvores não extrapolam; no hotmilk o download chega a 671 Mbps e os outros prédios a 267, e o MAE lá era 91 Mbps na `v3-tr069`.
- **Mudanças:** campo `denominador` no registro; régua `2026-10-06.2` com eficiência, imputação pela mediana do treino e `den_imputados`; Studio avaliando cada versão com o seu denominador e o rascunho herdando o da base; `regression_mlflow.py` com `eficiencia.json`; nova `v4-tr069` (não ativa).
- **Efeito medido:** tabela `v3-tr069` × `v4-tr069` em download e upload (R² e MAE com intervalo, MAE log, `den_imputados`), R² e MAE por prédio, "atende em throughput" e "atende completo", e os vereditos de promoção.
- **Exploração dos denominadores:** a tabela da seção 2 da spec, dizendo que a escolha foi pela física da direção e não pelo melhor número.
- **Critério da C2:** a linha da C2 do Step 2 e a conclusão (entra ou não entra).
- **Fica para depois:** a C2, se o critério mandar; variantes de denominador como outras versões.

- [ ] **Step 5: Conferir**

Run: `sed -n 1,90p CHANGELOG.md | grep -n "<\|TBD\|TODO"`
Expected: nenhuma linha.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`
