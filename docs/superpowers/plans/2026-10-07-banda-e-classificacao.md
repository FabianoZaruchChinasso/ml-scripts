# Eficiência só em 5 GHz e scripts de classificação na régua — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) O denominador de uma versão pode valer só numa banda (`{"coluna", "radio"}`), e a nova `v5-tr069` é medida contra a `v3-tr069`; (2) `classification_benchmark.py` e `compare_protocols.py` passam a usar a carga e a régua únicas, com o benchmark de classificação reapontado para "atende" por aplicação.

**Architecture:** Parte 1: `core/modelos.py` aceita a forma condicional do denominador; `avaliacao.prever_fora_do_fold` resolve essa forma chamando a si mesmo duas vezes (eficiência e absoluto, mesmos folds) e escolhendo a previsão por linha conforme `radio`. Parte 2: um módulo novo, `core/classificacao.py`, monta o alvo "atende", avalia classificadores fora do prédio e resume a acurácia balanceada; os dois scripts são reescritos sobre `carga`, `avaliacao` e esse módulo.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn, MLflow, JavaScript sem framework (Studio). Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-07-banda-e-classificacao-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add` nem `git stash`.** O usuário faz commit à mão.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 388 tests`, `OK`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último.
- Leia cada função antes de editá-la: os trechos "troque X por Y" citam o código atual pelo conteúdo, não pelo número da linha.

## Mapa de arquivos

| Arquivo | Parte | O que muda |
|---|---|---|
| `src/ml/core/modelos.py` | 1 | Forma condicional do denominador; `coluna_do_denominador` |
| `src/ml/core/avaliacao.py` | 1 | `prever_fora_do_fold` com denominador condicional; régua `2026-10-07.1` |
| `src/ml/studio/static/modelos.js` | 1 | Etiqueta com a banda |
| `src/ml/regression_mlflow.py` | 1 | Dois modelos finais com denominador condicional |
| `src/ml/core/modelos.json` | 1 | Nova `v5-tr069` (via `salvar_versao`) |
| `src/ml/core/classificacao.py` | 2 | Novo: alvo "atende", classificação fora do prédio, referência da régua, resumo |
| `src/ml/classification_benchmark.py` | 2 | Reescrito |
| `src/ml/compare_protocols.py` | 2 | Reescrito |
| `tests/test_modelos_core.py`, `tests/test_avaliacao.py`, `tests/test_classificacao.py` | 1 e 2 | Testes |
| `CHANGELOG.md` | 1 e 2 | Entrada nova no topo |

---

## Parte 1: denominador por banda

### Task 1: Forma condicional no registro

**Files:**
- Modify: `src/ml/core/modelos.py`
- Test: `tests/test_modelos_core.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_modelos_core.py`, acima do bloco `__main__`:

```python
class TestDenominadorPorBanda(Base):
  def registro(self, valor):
    return {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x',
                                              'denominador': {'speedtest_down_mbps': valor}}}}

  def test_forma_condicional_valida(self):
    M.validar_registro(self.registro({'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'}))
    M.validar_registro(self.registro('router_tx_rate_mbps'))

  def test_forma_condicional_invalida(self):
    for ruim in ({'coluna': 'x'}, {'coluna': 'x', 'radio': ''}, {'coluna': '', 'radio': '5ghz'},
                 {'coluna': 'x', 'radio': '5ghz', 'extra': 1}, {'coluna': 3, 'radio': '5ghz'}):
      with self.assertRaises(ValueError, msg=repr(ruim)):
        M.validar_registro(self.registro(ruim))

  def test_coluna_do_denominador(self):
    self.assertEqual(M.coluna_do_denominador('router_tx_rate_mbps'), 'router_tx_rate_mbps')
    self.assertEqual(M.coluna_do_denominador({'coluna': 'router_rx_rate_mbps', 'radio': '5ghz'}),
                     'router_rx_rate_mbps')
    self.assertIsNone(M.coluna_do_denominador(None))

  def test_salvar_checa_a_coluna_dentro_do_dicionario(self):
    with self.assertRaises(ValueError):
      M.salvar_versao('v2', ['router_snr'], 'x', CONHECIDAS, TABELA,
                      denominador={'speedtest_down_mbps': {'coluna': 'router_tx_bytes', 'radio': '5ghz'}},
                      path=self.path)
    den = {'speedtest_down_mbps': {'coluna': 'router_signal_dbm', 'radio': '5ghz'}}
    M.salvar_versao('v3', ['router_snr'], 'x', CONHECIDAS, TABELA, denominador=den, path=self.path)
    self.assertEqual(M.denominador_de(M.carregar(self.path), 'v3', 'speedtest_down_mbps'),
                     {'coluna': 'router_signal_dbm', 'radio': '5ghz'})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_modelos_core.TestDenominadorPorBanda -v 2>&1 | tail -12`
Expected: falhas e erros (`ValueError` da forma condicional válida; `has no attribute 'coluna_do_denominador'`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/modelos.py`:

1. Logo depois da linha `ALVOS_COM_DENOMINADOR = (...)`, acrescente:

```python


def _texto(valor) -> bool:
  return isinstance(valor, str) and bool(valor.strip())


def _valor_denominador_valido(valor) -> bool:
  """Texto (nome da coluna) ou {'coluna': texto, 'radio': texto}: eficiência só nessa banda."""
  if isinstance(valor, dict):
    return set(valor) == {'coluna', 'radio'} and _texto(valor['coluna']) and _texto(valor['radio'])
  return _texto(valor)


def coluna_do_denominador(valor):
  """Coluna de um valor de denominador nas duas formas (texto ou dicionário condicional)."""
  if isinstance(valor, dict):
    return valor.get('coluna')
  return valor
```

2. Em `validar_registro`, troque o bloco inteiro que começa em `if 'denominador' in versao:` (até o `raise ValueError(...)` dele) por:

```python
    if 'denominador' in versao:
      den = versao['denominador']
      if (not isinstance(den, dict) or not den or not set(den) <= set(ALVOS_COM_DENOMINADOR)
          or not all(_valor_denominador_valido(v) for v in den.values())):
        raise ValueError(f'{nome!r}: denominador precisa ser {{alvo: coluna}} ou '
                         f'{{alvo: {{"coluna": ..., "radio": ...}}}}, só para {list(ALVOS_COM_DENOMINADOR)}')
```

3. Em `salvar_versao`, troque a linha `colunas = list(denominador.values())` por:

```python
    colunas = [coluna_do_denominador(v) for v in denominador.values()]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_modelos_core -v 2>&1 | tail -4`
Expected: `OK`

---

### Task 2: Régua com denominador condicional

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_avaliacao.py`, acima do bloco `__main__`:

```python
class TestDenominadorPorBanda(Base):
  DEN = {'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'}

  def conj(self):
    f = frame()
    f['router_tx_rate_mbps'] = 100.0
    f['radio'] = np.where(np.arange(len(f)) % 2 == 0, '5ghz', '2.4ghz')
    f.loc[2, 'radio'] = None
    return conjunto('speedtest_down_mbps', f)

  def test_cada_linha_usa_a_previsao_da_sua_banda(self):
    conj = self.conj()
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador=self.DEN)
    banda = prev['_linha'].map(conj.df.set_index('_linha')['radio'])
    # 5 GHz: eficiência 0,5 × 100; 2,4 GHz e sem banda: o absoluto, 0,5.
    self.assertEqual(prev.loc[banda.eq('5ghz').to_numpy(), 'yhat'].unique().tolist(), [50.0])
    self.assertEqual(prev.loc[~banda.eq('5ghz').to_numpy(), 'yhat'].unique().tolist(), [0.5])
    self.assertEqual(prev.loc[prev['_linha'] == 'a.csv:2', 'yhat'].tolist(), [0.5])

  def test_den_imputado_so_nas_linhas_da_banda(self):
    f = frame()
    f['router_tx_rate_mbps'] = 100.0
    f['radio'] = np.where(np.arange(len(f)) % 2 == 0, '5ghz', '2.4ghz')
    f.loc[[0, 1], 'router_tx_rate_mbps'] = np.nan
    conj = conjunto('speedtest_down_mbps', f)
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador=self.DEN)
    imputadas = prev.loc[prev['den_imputado'], '_linha'].tolist()
    self.assertEqual(imputadas, ['a.csv:0'])

  def test_dois_modelos_por_fold(self):
    conj = self.conj()
    ajustes = []
    A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                          denominador=self.DEN, ao_ajustar=lambda fold, m: ajustes.append(fold.test_site))
    self.assertEqual(sorted(ajustes), sorted(['coworking', 'hotmilk', 'residencia'] * 2))

  def test_sem_coluna_radio_levanta(self):
    conj = conjunto('speedtest_down_mbps', frame().assign(router_tx_rate_mbps=100.0))
    with self.assertRaisesRegex(ValueError, 'radio'):
      A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], denominador=self.DEN)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestDenominadorPorBanda -v 2>&1 | tail -10`
Expected: erros (o dicionário cai no caminho de texto: `TypeError` ou `ValueError` de coluna inexistente).

- [ ] **Step 3: Implementar**

Em `src/ml/core/avaliacao.py`:

1. Troque `VERSAO_REGUA = '2026-10-06.2'` por `VERSAO_REGUA = '2026-10-07.1'`.

2. Em `prever_fora_do_fold`:
   - na docstring, acrescente ao fim do parágrafo do denominador: `` `denominador` também pode ser {'coluna': ..., 'radio': ...}: dois modelos por fold (eficiência e absoluto, mesmas linhas de treino), e cada linha de teste recebe a eficiência se `radio` for igual ao valor indicado, e o absoluto nos demais casos (inclusive `radio` vazio). ``
   - logo depois da linha `assert_sem_vazamento(colunas, vazadas)`, acrescente:

```python
  if isinstance(denominador, dict):
    return _prever_por_banda(df, colunas, y_col, vazadas, arvores, min_teste, min_treino, estimador,
                             ao_ajustar, denominador)
```

3. Logo depois da função `prever_fora_do_fold`, acrescente:

```python
def _prever_por_banda(df, colunas, y_col, vazadas, arvores, min_teste, min_treino, estimador,
                      ao_ajustar, denominador: dict) -> pd.DataFrame:
  """Eficiência nas linhas de uma banda, absoluto nas demais (mesmos folds, dois modelos)."""
  if 'radio' not in df.columns:
    raise ValueError("denominador por banda precisa da coluna 'radio' no conjunto")
  eficiencia = prever_fora_do_fold(df, colunas, y_col, vazadas, arvores, min_teste, min_treino, estimador,
                                   ao_ajustar, denominador['coluna'])
  absoluto = prever_fora_do_fold(df, colunas, y_col, vazadas, arvores, min_teste, min_treino, estimador,
                                 ao_ajustar, None)
  if eficiencia.empty:
    return eficiencia
  absoluto = absoluto.loc[eficiencia.index]
  na_banda = (df.loc[eficiencia.index, 'radio'] == denominador['radio']).to_numpy()
  saida = eficiencia.copy()
  saida['yhat'] = np.where(na_banda, eficiencia['yhat'].to_numpy(dtype=float),
                           absoluto['yhat'].to_numpy(dtype=float))
  saida['den_imputado'] = na_banda & eficiencia['den_imputado'].to_numpy(dtype=bool)
  return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 3: Studio e MLflow com a forma condicional

**Files:**
- Modify: `src/ml/studio/static/modelos.js` (`cardVersoes`)
- Modify: `src/ml/regression_mlflow.py` (`main`)

- [ ] **Step 1: Etiqueta no Studio**

Em `src/ml/studio/static/modelos.js`, em `cardVersoes`, troque o bloco da etiqueta:

```js
          const den = (v.denominador || {})[st.alvo];
          if (!den) return '';
          const lado = den.includes('_tx_') ? 'tx' : den.includes('_rx_') ? 'rx' : den;
          return ` <span class="tag mid" title="prevê a eficiência (alvo ÷ ${esc(den)}) e volta para Mbps">eficiência ÷ ${esc(lado)}</span>`;
```

por:

```js
          const valor = (v.denominador || {})[st.alvo];
          if (!valor) return '';
          // Texto: eficiência em todas as linhas. {coluna, radio}: só nas linhas dessa banda.
          const den = typeof valor === 'string' ? valor : valor.coluna;
          const radio = typeof valor === 'string' ? '' : valor.radio;
          const banda = radio === '5ghz' ? '5 GHz' : radio === '2.4ghz' ? '2,4 GHz' : radio;
          const lado = den.includes('_tx_') ? 'tx' : den.includes('_rx_') ? 'rx' : den;
          const titulo = `prevê a eficiência (alvo ÷ ${den})${banda ? ` só em ${banda}, absoluto nas demais bandas` : ''} e volta para Mbps`;
          return ` <span class="tag mid" title="${esc(titulo)}">eficiência ÷ ${esc(lado)}${banda ? ` (${esc(banda)})` : ''}</span>`;
```

Run: `node --check src/ml/studio/static/modelos.js && echo ok`
Expected: `ok`

- [ ] **Step 2: MLflow**

Em `src/ml/regression_mlflow.py`, em `main`:

1. Troque o bloco:

```python
  denominador = core_modelos.denominador_de(registro, nome_modelo, ALVO)
  if denominador:
    validate_columns(conj.df, [denominador], 'denominador')
```

por:

```python
  denominador = core_modelos.denominador_de(registro, nome_modelo, ALVO)
  coluna_den = core_modelos.coluna_do_denominador(denominador)
  radio_den = denominador.get('radio') if isinstance(denominador, dict) else None
  if coluna_den:
    validate_columns(conj.df, [coluna_den] + (['radio'] if radio_den else []), 'denominador')
```

2. No dicionário `params`, troque a linha `'denominador': denominador or '',` por:

```python
    'denominador': coluna_den or '',
    'denominador_radio': radio_den or '',
```

3. Troque o bloco que vai de `treino = ~conj.df['_limitado_wan']` até o fim da função `main` por:

```python
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  y_final = conj.df.loc[treino, ALVO].astype(float)
  y_eficiencia, eficiencia = None, None
  if coluna_den:
    den = pd.to_numeric(conj.df.loc[treino, coluna_den], errors='coerce')
    mediana = float(den[den >= core_avaliacao.DEN_MINIMO].median())
    y_eficiencia = y_final / den.where(den >= core_avaliacao.DEN_MINIMO, mediana)
    uso = 'mbps = predict(X) * denominador (vazio ou abaixo de den_minimo: mediana_imputacao)'
    if radio_den:
      uso = (f'radio == {radio_den!r}: mbps = <modelo>_eficiencia.predict(X) * denominador '
             '(vazio ou abaixo de den_minimo: mediana_imputacao); demais linhas: mbps = <modelo>_absoluto.predict(X)')
    eficiencia = {'alvo': ALVO, 'denominador': coluna_den, 'radio': radio_den, 'mediana_imputacao': mediana,
                  'den_minimo': core_avaliacao.DEN_MINIMO, 'uso': uso}
  for config in CONFIGS:
    with mlflow.start_run(run_name=f"{nome_modelo}-{config['model_type']}-{config['max_depth']}"):
      mlflow.log_params(dict(params, **config))
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config),
                                                denominador=denominador)
      resumo = core_avaliacao.resumir(prev, len(features))
      registrar_metricas(resumo)
      finais = {config['model_type']: y_final}
      if coluna_den and radio_den:
        finais = {f"{config['model_type']}_eficiencia": y_eficiencia, f"{config['model_type']}_absoluto": y_final}
      elif coluna_den:
        finais = {config['model_type']: y_eficiencia}
      for nome_final, y_treino in finais.items():
        final = montar(config).fit(X_final, y_treino)
        # O imputer guarda um numpy.dtype, que o skops não confia por padrão.
        mlflow.sklearn.log_model(sk_model=final, name=nome_final, serialization_format='skops',
                                 skops_trusted_types=['numpy.dtype'])
      if eficiencia:
        mlflow.log_dict(eficiencia, 'eficiencia.json')
        mlflow.log_metric('den_imputados', resumo['den_imputados'])
      print('-' * 61)
      print(f"{config['model_type']} {config}: R² pooled {resumo['pooled']} "
            f"(90%: {resumo['intervalos'].get('pooled')}), MAE {resumo['mae']}, MAE log {resumo['mae_log']}")
      print(f"  por prédio: {resumo['por_local']}")
```

4. Na docstring do topo, acrescente ao fim: `Com denominador condicional ({"coluna", "radio"}), registra dois modelos finais por configuração (<modelo>_eficiencia e <modelo>_absoluto).`

- [ ] **Step 3: Conferir**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); import ml.regression_mlflow as m; print(m.ALVO)"`
Expected: `speedtest_down_mbps`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

(A rodada de verdade fica para a Task 7, depois que a `v5-tr069` existir.)

---

## Parte 2: scripts de classificação na régua

### Task 4: `core/classificacao.py`

**Files:**
- Create: `src/ml/core/classificacao.py`
- Test: `tests/test_classificacao.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_classificacao.py`:

```python
import os
import sys
import unittest
import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import classificacao as K

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']
LIM = {'dn': 30.0, 'up': 10.0, 'lat': 100, 'jit': 30}


class Lembra(BaseEstimator, ClassifierMixin):
  """Prevê sempre `classe` e guarda o índice das linhas de treino de cada ajuste."""
  vistos = []

  def __init__(self, classe=1):
    self.classe = classe

  def fit(self, X, y):
    self.classes_ = np.unique(y)
    Lembra.vistos.append(list(X.index))
    return self

  def predict(self, X):
    return np.full(len(X), self.classe)


def frame(n_por_local=10, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({'local': np.repeat(LOCAIS, n_por_local), 'speedtest_down_mbps': 2 * snr,
                       'speedtest_up_mbps': snr / 2, 'latency_ms': 10.0, 'jitter_ms': 2.0,
                       'router_snr': snr, 'router_tx_bytes': snr})


def conjuntos(f=None):
  f = frame() if f is None else f
  return (C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA, catalogo=()),
          C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA, catalogo=()))


class TestAlvo(unittest.TestCase):
  def test_atende_com_os_dois_limiares_e_so_linhas_comuns(self):
    f = frame()
    f.loc[0, 'speedtest_up_mbps'] = np.nan
    dn, up = conjuntos(f)
    df = K.alvo_atende(dn, up, LIM)
    self.assertNotIn('a.csv:0', df['_linha'].tolist())
    esperado = (df['speedtest_down_mbps'] >= 30) & (df['_linha'].map(up.df.set_index('_linha')['speedtest_up_mbps']) >= 10)
    self.assertTrue((df['_atende'] == esperado).all())


class TestClassificacao(unittest.TestCase):
  def setUp(self):
    Lembra.vistos = []

  def test_treino_nunca_tem_o_predio_de_teste(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    prev = K.prever_classe_fora_do_fold(df, ['router_snr'], [], Lembra())
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    for indices in Lembra.vistos:
      self.assertEqual(df.loc[indices, '_site'].nunique(), 2)

  def test_fold_com_uma_classe_no_treino_e_pulado(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    df['_atende'] = df['_site'] == 'residencia'
    with warnings.catch_warnings(record=True) as avisos:
      warnings.simplefilter('always')
      prev = K.prever_classe_fora_do_fold(df, ['router_snr'], [], Lembra())
    self.assertNotIn('residencia', prev['_site'].unique())
    self.assertTrue(any('uma classe' in str(a.message) for a in avisos))

  def test_vazamento_levanta(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    with self.assertRaises(AssertionError):
      K.prever_classe_fora_do_fold(df, ['router_tx_bytes'], ['router_tx_bytes'], Lembra())


class TestResumo(unittest.TestCase):
  def test_valores_conferidos_a_mao(self):
    prev = pd.DataFrame({'_linha': ['a', 'b', 'c', 'd'], 'y': [True, False, True, False],
                         'yhat': [True, False, False, True], '_site': ['s1', 's1', 's2', 's2'],
                         '_pos': ['p1', 'p2', 'p3', 'p4']})
    r = K.resumir_classe(prev)
    self.assertEqual(r['pooled'], 0.5)
    self.assertEqual(r['por_local'], {'s1': 1.0, 's2': 0.0})
    self.assertEqual(r['n'], 4)

  def test_vazio(self):
    r = K.resumir_classe(pd.DataFrame(columns=['_linha', 'y', 'yhat', '_site', '_pos']))
    self.assertEqual((r['pooled'], r['por_local'], r['intervalo'], r['n']), (None, {}, None, 0))


class TestReferencia(unittest.TestCase):
  def test_atende_tirado_das_previsoes_de_regressao(self):
    def p(y, yhat):
      return pd.DataFrame({'_linha': ['a', 'b'], 'y': y, 'yhat': yhat, '_site': ['s', 's'], '_pos': ['p', 'q']})
    ref = K.referencia_regua(p([40.0, 40.0], [40.0, 10.0]), p([20.0, 20.0], [20.0, 20.0]), LIM)
    self.assertEqual(ref['y'].tolist(), [True, True])
    self.assertEqual(ref['yhat'].tolist(), [True, False])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_classificacao -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'classificacao'`

- [ ] **Step 3: Criar `src/ml/core/classificacao.py`**

```python
"""Classificação direta de "atende" por aplicação, medida na régua única (LOGO por prédio).

Serve para responder se um classificador treinado para "atende" decide melhor que o
caminho da régua: regredir Mbps e comparar a previsão com o limiar da aplicação.
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone

from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, assert_sem_vazamento,
                               reamostras)
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds

_COLUNAS = ['_linha', 'y', 'yhat', '_site', '_pos']


def alvo_atende(conj_dn, conj_up, limiares: dict) -> pd.DataFrame:
  """O df do download, só nas linhas presentes nos dois conjuntos, com `_atende` (download >= dn e upload >= up)."""
  upload = conj_up.df.set_index('_linha')[conj_up.alvo]
  df = conj_dn.df[conj_dn.df['_linha'].isin(upload.index)].copy()
  df['_atende'] = ((df[conj_dn.alvo] >= limiares['dn']).to_numpy()
                   & (df['_linha'].map(upload) >= limiares['up']).to_numpy())
  return df.reset_index(drop=True)


def prever_classe_fora_do_fold(df: pd.DataFrame, colunas, vazadas, estimador, ajustar=None,
                               y_col: str = '_atende') -> pd.DataFrame:
  """Classe de cada linha pelo classificador treinado sem o prédio dela (LOGO por `_site`).

  `estimador` é clonado a cada fold; `ajustar(estimador, fold)` troca o ajuste (por exemplo,
  uma busca de hiperparâmetros) e devolve o modelo ajustado. Fold cujo treino tem uma classe
  só é pulado, com aviso. Devolve _linha, y, yhat (booleanos), _site, _pos.
  """
  assert_sem_vazamento(colunas, vazadas)
  X = matriz(df, colunas)
  y = df[y_col].astype(bool).astype(int)
  partes = []
  for fold in outer_logo_folds(X, y, df['_site']):
    if fold.y_train.nunique() < 2:
      warnings.warn(f'fold de {fold.test_site!r} pulado: o treino tem uma classe só', UserWarning, stacklevel=2)
      continue
    modelo = ajustar(estimador, fold) if ajustar is not None else clone(estimador).fit(fold.X_train, fold.y_train)
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': df.loc[indice, '_linha'].to_numpy(),
                                'y': fold.y_test.astype(bool).to_numpy(),
                                'yhat': np.asarray(modelo.predict(fold.X_test)).astype(bool),
                                '_site': fold.test_site, '_pos': df.loc[indice, '_pos'].to_numpy()},
                               index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS)
  return pd.concat(partes)


def referencia_regua(prev_dn: pd.DataFrame, prev_up: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """O "atende" da régua: previsões de regressão de download e upload comparadas com os limiares."""
  j = _juntar(dn=prev_dn, up=prev_up)
  return pd.DataFrame({'_linha': j.index.to_numpy(), 'y': _atende_em(j, limiares, 'y_dn', 'y_up'),
                       'yhat': _atende_em(j, limiares, 'p_dn', 'p_up'),
                       '_site': j['_site'].to_numpy(), '_pos': j['_pos'].to_numpy()})


def _arredondar(valor):
  return None if np.isnan(valor) else round(float(valor), 4)


def resumir_classe(prev: pd.DataFrame, amostras=None) -> dict:
  """Acurácia balanceada pooled e por prédio, com intervalo de 90% pelo bootstrap de posições."""
  if prev.empty:
    return {'pooled': None, 'por_local': {}, 'intervalo': None, 'n': 0}
  real, previsto = prev['y'].to_numpy(dtype=bool), prev['yhat'].to_numpy(dtype=bool)
  por_local = {}
  for site, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0]):
    valor = _acuracia_balanceada(g['y'].to_numpy(dtype=bool), g['yhat'].to_numpy(dtype=bool))
    if not np.isnan(valor):
      por_local[site] = round(valor, 4)
  intervalo = None
  if len(prev) > 1:
    amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
    intervalo = _intervalo([_acuracia_balanceada(real[i], previsto[i]) for i in amostras])
  return {'pooled': _arredondar(_acuracia_balanceada(real, previsto)), 'por_local': por_local,
          'intervalo': intervalo, 'n': int(len(prev))}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_classificacao -v 2>&1 | tail -4`
Expected: `OK`

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

### Task 5: `classification_benchmark.py` reescrito

**Files:**
- Modify: `src/ml/classification_benchmark.py` (conteúdo inteiro)

- [ ] **Step 1: Reescrever o script**

Leia o arquivo atual antes (as funções `build_models` e `get_search_space` continuam iguais). Conteúdo completo novo de `src/ml/classification_benchmark.py`:

```python
"""Benchmark de classificadores de "atende" por aplicação, medidos na régua única.

Para cada aplicação de core/aplicacoes.json, o alvo é "atende" (download e upload acima dos
limiares). Os classificadores são avaliados deixando um prédio de fora por vez e comparados
com a referência da régua: o "atende" tirado das previsões de regressão da mesma versão (com
o denominador dela). Responde se classificar direto decide melhor que regredir Mbps e
comparar com o limiar.
"""

import argparse
import os
import sys
import warnings

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import classificacao as core_classificacao
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.splits import inner_logo_splits

ALVO_DN, ALVO_UP = 'speedtest_down_mbps', 'speedtest_up_mbps'
REMOVIDAS = ('--qoe-column', '--class-mode', '--fixed-thresholds', '--group-level', '--features',
             '--test-size', '--cv-folds', '--cv-gap', '--target-column', '--time-column', '--tune-top-k')
REMOVIDAS_FLAG = ('--no-tune', '--plot-confusion')
```

Em seguida, copie **sem mudança** as funções `build_models(seed)` e `get_search_space(model_name)` do arquivo atual. Depois delas, o resto do arquivo:

```python
def parse_args():
  parser = argparse.ArgumentParser(description='Benchmark de classificadores de "atende" por aplicação')
  parser.add_argument('--datasets', default='',
                      help='Nomes de arquivo em data/, separados por vírgula (padrão: o conjunto canônico)')
  parser.add_argument('--modelo', default='', help='Versão de core/modelos.json (padrão: a ativa)')
  parser.add_argument('--aplicacoes', default='',
                      help='Aplicações separadas por vírgula (padrão: todas de core/aplicacoes.json)')
  parser.add_argument('--tune', action='store_true', default=False,
                      help='Busca de hiperparâmetros por LOGO interno (lenta com poucos prédios)')
  parser.add_argument('--tune-iter', type=int, default=20, help='Iterações da busca por modelo')
  parser.add_argument('--seed', type=int, default=42, help='Semente')
  parser.add_argument('--csv', default=None, help='REMOVIDO; use --datasets')
  for flag in REMOVIDAS:
    parser.add_argument(flag, default=None, help='REMOVIDO')
  for flag in REMOVIDAS_FLAG:
    parser.add_argument(flag, action='store_true', default=None, help='REMOVIDO')
  return parser.parse_args()


def ajuste_com_busca(nome_modelo: str, tune_iter: int, seed: int):
  def ajustar(estimador, fold):
    busca = RandomizedSearchCV(estimator=clone(estimador), param_distributions=get_search_space(nome_modelo),
                               n_iter=tune_iter, scoring='balanced_accuracy',
                               cv=inner_logo_splits(fold.train_site_ids), n_jobs=-1, random_state=seed,
                               refit=True)
    return busca.fit(fold.X_train, fold.y_train).best_estimator_
  return ajustar


def imprimir(app: str, limiares: dict, df, linhas) -> None:
  sites = sorted(df['_site'].unique())
  print(f"\n{app} (download >= {limiares['dn']}, upload >= {limiares['up']}): "
        f"{len(df)} linhas, {int(df['_atende'].sum())} atendem")
  print(f"  {'modelo':22s} {'pooled':>8s} {'90%':>17s} " + ' '.join(f'{s:>13s}' for s in sites))
  for nome, r in linhas:
    faixa = f"{r['intervalo'][0]:.3f} a {r['intervalo'][1]:.3f}" if r['intervalo'] else '-'
    pooled = f"{r['pooled']:.3f}" if r['pooled'] is not None else '-'
    locais = ' '.join(f"{r['por_local'][s]:13.3f}" if s in r['por_local'] else f"{'-':>13s}" for s in sites)
    print(f'  {nome:22s} {pooled:>8s} {faixa:>17s} {locais}')


def main():
  args = parse_args()
  if args.csv is not None:
    raise SystemExit('--csv saiu: use --datasets com nomes de data/ (padrão: o conjunto canônico)')
  for flag in REMOVIDAS + REMOVIDAS_FLAG:
    if getattr(args, flag.lstrip('-').replace('-', '_')) is not None:
      print(f'WARNING: {flag} saiu; o alvo agora é "atende" por aplicação (core/aplicacoes.json) '
            'e a carga é a canônica.')
  np.random.seed(args.seed)

  registro = core_modelos.carregar()
  nome = args.modelo or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'--modelo {nome!r} não existe; versões: {sorted(registro["versoes"])}')
  ids = [x for x in args.datasets.split(',') if x] or None
  tabela = core_features.carregar_tabela()
  conj_dn = core_carga.carregar(ALVO_DN, ids=ids, tabela=tabela)
  conj_up = core_carga.carregar(ALVO_UP, ids=ids, tabela=tabela)
  vazadas = [c for c, k in conj_dn.classes.items() if k is not None and k.vazamento]
  pedidas = registro['versoes'][nome]['features']
  features = [f for f in pedidas if f in conj_dn.df.columns and f not in vazadas]
  fora = [f for f in pedidas if f not in features]
  print(f'Modelo {nome}: {len(features)} features' + (f'; fora da conta (vazamento ou ausentes): {fora}' if fora else ''))
  print(f'Datasets: {conj_dn.datasets}')

  # Referência: as previsões de regressão da régua, calculadas uma vez para todas as aplicações.
  vazadas_up = [c for c, k in conj_up.classes.items() if k is not None and k.vazamento]
  prev_dn = core_avaliacao.avaliar(conj_dn, features, vazadas, com_previsoes=True,
                                   denominador=core_modelos.denominador_de(registro, nome, ALVO_DN))[1]
  prev_up = core_avaliacao.avaliar(conj_up, [f for f in features if f not in vazadas_up], vazadas_up,
                                   com_previsoes=True,
                                   denominador=core_modelos.denominador_de(registro, nome, ALVO_UP))[1]

  aplicacoes = core_aplicacoes.carregar()
  pedidas_apps = [a for a in args.aplicacoes.split(',') if a] or list(aplicacoes)
  desconhecidas = [a for a in pedidas_apps if a not in aplicacoes]
  if desconhecidas:
    raise SystemExit(f'aplicações desconhecidas: {desconhecidas}; disponíveis: {list(aplicacoes)}')
  modelos = build_models(args.seed)
  for app in pedidas_apps:
    limiares = aplicacoes[app]
    df = core_classificacao.alvo_atende(conj_dn, conj_up, limiares)
    if df['_atende'].nunique() < 2:
      print(f'\n{app}: só uma classe no "atende" real; fora da tabela')
      continue
    linhas = [('régua (regressão)', core_classificacao.resumir_classe(
      core_classificacao.referencia_regua(prev_dn, prev_up, limiares)))]
    for nome_modelo, estimador in modelos.items():
      ajustar = ajuste_com_busca(nome_modelo, args.tune_iter, args.seed) if args.tune else None
      with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter('always')
        prev = core_classificacao.prever_classe_fora_do_fold(df, features, vazadas, estimador, ajustar=ajustar)
      for aviso in avisos:
        if 'pulado' in str(aviso.message):
          print(f'  aviso ({nome_modelo}): {aviso.message}')
      linhas.append((nome_modelo, core_classificacao.resumir_classe(prev)))
    imprimir(app, limiares, df, linhas)


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Conferir referências antigas**

Run: `grep -n "load_datasets\|SITE_COLUMN\|qoe_column\|quartile_thresholds\|apply_thresholds\|DEFAULT_FEATURES" src/ml/classification_benchmark.py`
Expected: nenhuma linha.

- [ ] **Step 3: Rodar de verdade (com a versão ativa)**

Run: `timeout 580 python3 src/ml/classification_benchmark.py --modelo v3-tr069 2>&1 | grep -v Warning | tail -30`
Expected: a linha `Modelo v3-tr069: 12 features`, e para cada aplicação com as duas classes uma tabela com a linha `régua (regressão)` e uma linha por classificador (rf, extra_trees, hist_gb, log_reg), com pooled, intervalo e uma coluna por prédio. Sem traceback.

Run: `python3 src/ml/classification_benchmark.py --csv x 2>&1 | tail -1`
Expected: `--csv saiu: use --datasets ...`

---

### Task 6: `compare_protocols.py` reescrito

**Files:**
- Modify: `src/ml/compare_protocols.py` (conteúdo inteiro)

- [ ] **Step 1: Reescrever o script**

Conteúdo completo novo de `src/ml/compare_protocols.py`:

```python
"""Quanto o protocolo antigo (divisão aleatória) é otimista contra a régua (LOGO por prédio).

Mesmas linhas (carga canônica), mesmas features (versão do registro, sem vazamento) e o
mesmo modelo da régua, sem denominador, para comparar só o protocolo. Rode quando quiser
lembrar por que a régua deixa um prédio inteiro de fora.
"""

import argparse
import os
import sys

from sklearn.model_selection import train_test_split

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.metrics import regression_metrics


def main():
  parser = argparse.ArgumentParser(description='Protocolo antigo (aleatório) contra a régua (LOGO por prédio)')
  parser.add_argument('--datasets', default='',
                      help='Nomes de arquivo em data/, separados por vírgula (padrão: o conjunto canônico)')
  parser.add_argument('--alvo', '--target', dest='alvo', default='speedtest_down_mbps')
  parser.add_argument('--modelo', default='', help='Versão de core/modelos.json (padrão: a ativa)')
  parser.add_argument('--seed', type=int, default=42)
  parser.add_argument('--csv', default=None, help='REMOVIDO; use --datasets')
  parser.add_argument('--group-level', default=None, help='IGNORADO; a régua agrupa sempre por prédio')
  args = parser.parse_args()
  if args.csv is not None:
    raise SystemExit('--csv saiu: use --datasets com nomes de data/ (padrão: o conjunto canônico)')
  if args.group_level is not None:
    print('WARNING: --group-level é ignorado; a régua agrupa sempre por prédio.')

  registro = core_modelos.carregar()
  nome = args.modelo or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'--modelo {nome!r} não existe; versões: {sorted(registro["versoes"])}')
  ids = [x for x in args.datasets.split(',') if x] or None
  conj = core_carga.carregar(args.alvo, ids=ids)
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  features = [f for f in registro['versoes'][nome]['features'] if f in conj.df.columns and f not in vazadas]
  print(f'Modelo {nome}: {len(features)} features; alvo {args.alvo}; {len(conj.df)} linhas; '
        f'prédios {sorted(conj.df["_site"].unique())}')

  X = core_features.matriz(conj.df, features)
  y = conj.df[args.alvo].astype(float)
  X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=args.seed)
  antigo = regression_metrics(y_te.to_numpy(), core_avaliacao.modelo_regua().fit(X_tr, y_tr).predict(X_te))
  prev = core_avaliacao.prever_fora_do_fold(conj.df, features, args.alvo, vazadas)
  regua = core_avaliacao.resumir(prev, len(features))

  print('\nProtocolo antigo (divisão aleatória 80/20, linhas do mesmo prédio dos dois lados):')
  print(f"  R² {antigo['r2']:.4f}  MAE {antigo['mae']:.2f}")
  print('\nRégua (deixa um prédio inteiro de fora):')
  print(f"  R² pooled {regua['pooled']:.4f} (90%: {regua['intervalos'].get('pooled')})  "
        f"MAE {regua['mae']:.2f} (90%: {regua['intervalos'].get('mae')})")
  print(f"  R² por prédio: {regua['por_local']}")
  print(f"\nOtimismo do protocolo antigo: R² +{antigo['r2'] - regua['pooled']:.4f}, "
        f"MAE {antigo['mae'] - regua['mae']:+.2f}")


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Rodar de verdade**

Run: `timeout 300 python3 src/ml/compare_protocols.py --modelo v3-tr069 2>&1 | grep -v Warning | tail -12`
Expected: as linhas do protocolo antigo e da régua, e a linha "Otimismo do protocolo antigo". Sem traceback.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

---

## Experimento

### Task 7: `v5-tr069`, medições e CHANGELOG

**Files:**
- Modify: `src/ml/core/modelos.json` (via `salvar_versao`)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Salvar a `v5-tr069`**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys; sys.path.insert(0, 'src')
from ml.core import carga as C, features as F, modelos as M
from ml.studio import api
ds = ','.join(C.ids_padrao(C.descobertos()))
v3 = M.carregar()['versoes']['v3-tr069']['features']
den = {'speedtest_down_mbps': {'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'},
       'speedtest_up_mbps': {'coluna': 'router_rx_rate_mbps', 'radio': '5ghz'}}
av = api.avaliacao_completa(ds, '', v3, den)
M.salvar_versao('v5-tr069', v3,
  'v3-tr069 com eficiência só em 5 GHz (download ÷ taxa PHY de envio, upload ÷ taxa PHY de recepção) e '
  'Mbps absoluto em 2,4 GHz (spec 2026-10-07). A divisão por banda foi escolhida nos mesmos 4 prédios.',
  api._colunas_conhecidas(), F.carregar_tabela(), origem='studio', avaliacao=av, denominador=den)
reg = M.carregar()
print('ativo', reg['ativo'], '| v5 denominador', reg['versoes']['v5-tr069']['denominador'])
EOF
```

Expected: `ativo v1 | v5 denominador {...}`. Se a `v5-tr069` já existir, pare e reporte.

- [ ] **Step 2: Medir `v3`, `v4` e `v5`**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M, avaliacao as A, aplicacoes as AP
from ml.studio import api
reg = M.carregar(); ds = ','.join(C.ids_padrao(C.descobertos())); apps = AP.carregar(); prev = {}
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  conj = C.carregar(alvo)
  vaz = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  for nome in ('v3-tr069', 'v4-tr069', 'v5-tr069'):
    r, prev[(nome, alvo)] = A.avaliar(conj, reg['versoes'][nome]['features'], vaz, com_previsoes=True,
                                      denominador=M.denominador_de(reg, nome, alvo))
    print(alvo, nome, 'R2', r['pooled'], r['intervalos']['pooled'], 'MAE', r['mae'], r['intervalos']['mae'],
          'MAElog', r['mae_log'], 'den_imputados', r['den_imputados'])
    print('   R2 por prédio', r['por_local'], '\n   MAE log por prédio', r['mae_log_por_local'])
for nome in ('v3-tr069', 'v4-tr069', 'v5-tr069'):
  at = A.atende(prev[(nome, 'speedtest_down_mbps')], prev[(nome, 'speedtest_up_mbps')], apps)
  ac = api.avaliacao_completa(ds, '', reg['versoes'][nome]['features'], reg['versoes'][nome].get('denominador'))
  print(nome, 'atende_throughput', at['media'], at['intervalo'], at['por_aplicacao'],
        '| atende_completo', ac['atende_completo']['media'], ac['atende_completo']['intervalo'])
v3, v5 = reg['versoes']['v3-tr069'], reg['versoes']['v5-tr069']
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  conj, _ = api._conjunto(ds, alvo, '')
  r = api._promocao(ds, '', alvo, v5['features'], v3['features'], conj, v5.get('denominador'), v3.get('denominador'))
  print(alvo, 'promocao v5 contra v3', json.dumps(r, ensure_ascii=False))
EOF
```

Expected: três versões por alvo, as linhas de "atende" e um veredito por alvo. Anote todos os números.

- [ ] **Step 3: MLflow, benchmark de classificação e protocolo**

Run: `MODELO=v5-tr069 timeout 580 python3 src/ml/regression_mlflow.py 2>&1 | grep -v Warning | tail -6`
Expected: os blocos de configuração sem traceback.

Run: `python3 -c "import mlflow; c = mlflow.MlflowClient(); r = c.search_runs([c.get_experiment_by_name('MLflow Wifi Regressions').experiment_id], order_by=['start_time DESC'], max_results=1)[0]; print(r.info.run_name, r.data.params.get('denominador'), r.data.params.get('denominador_radio')); print([a.path for a in c.list_artifacts(r.info.run_id)])"`
Expected: um run da `v5-tr069`, `router_tx_rate_mbps 5ghz`, e entre os artefatos `eficiencia.json` e os dois modelos (`..._eficiencia` e `..._absoluto`).

Run: `timeout 580 python3 src/ml/classification_benchmark.py --modelo v5-tr069 2>&1 | grep -v Warning | tail -30`
Expected: as tabelas por aplicação. Anote, por aplicação, a referência da régua e o melhor classificador (pooled e intervalo).

Run: `timeout 300 python3 src/ml/compare_protocols.py --modelo v5-tr069 2>&1 | grep -v Warning | tail -10`
Expected: a linha de otimismo. Anote.

- [ ] **Step 4: CHANGELOG**

No topo de `CHANGELOG.md`, no estilo das entradas existentes. Use **só** números impressos nos Steps 2 e 3 (e os da seção 2 da spec, citando-a):

- **Por quê:** a `v4-tr069` teve veredito "pior" por causa do "atende"; a causa é 2,4 GHz, em que a eficiência acompanha o aparelho cliente (a tabela de eficiência por prédio e banda da spec, seção 2). E `classification_benchmark.py` e `compare_protocols.py` ainda mediam com o carregador antigo, por posição, com features que vazam; o primeiro classificava `qoe_dw_score`, que não existe nos dados atuais.
- **Mudanças:** forma condicional do denominador; régua `2026-10-07.1`; `v5-tr069` (não ativa); `core/classificacao.py`; os dois scripts reescritos; dois modelos finais no MLflow para denominador condicional. Registre também que a C2 (dados externos) foi descartada.
- **Efeito medido:** tabela `v3` × `v4` × `v5` (R² e MAE com intervalo, MAE log, por prédio, "atende em throughput", "atende completo"); vereditos `v5` contra `v3`, **com a ressalva de que a divisão por banda foi escolhida nos mesmos 4 prédios**; o resultado do benchmark de classificação por aplicação (referência contra o melhor classificador); o otimismo do protocolo antigo.
- **Para o responsável pela coleta:** rodízio dos aparelhos clientes entre prédios, que separaria o efeito do aparelho do efeito do prédio em 2,4 GHz.

- [ ] **Step 5: Conferir**

Run: `sed -n 1,100p CHANGELOG.md | grep -n "<\|TBD\|TODO"`
Expected: nenhuma linha.

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`
