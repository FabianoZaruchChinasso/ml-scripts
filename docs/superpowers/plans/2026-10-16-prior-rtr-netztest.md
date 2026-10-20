# Prior externo do RTR-Netztest: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** medir, na régua atual, se um modelo treinado nos testes de Wi-Fi do RTR-Netztest, usado como feature de prior, melhora a `v5` no download e no upload, principalmente no hotmilk fora do treino.

**Arquitetura:** um módulo `src/ml/core/externo_rtr.py` lê o CSV aberto do RTR, filtra testes WLAN de Android e treina modelos de quantil de throughput por RSSI e banda. O script `src/ml/rtr_prior.py` aplica esses modelos às nossas linhas como colunas novas e compara cada variante contra a `v5` com `avaliacao.avaliar`, `delta_mae`, `delta_atende` e `veredito_promocao`. Como o prior só vê dados do RTR, não há vazamento entre os folds por prédio.

**Stack:** pandas, scikit-learn 1.9 (`HistGradientBoostingRegressor` com `loss='quantile'` e `monotonic_cst`), scipy, unittest.

---

## Contexto

- Reunião de 2026-10-14: o Lucas ficou de procurar datasets compatíveis para fine-tuning e mapear as features. A frente C2 (dados externos) tinha sido descartada em 2026-10-07, e a reunião a reabriu como hipótese auxiliar enquanto a coleta AX não termina.
- Na busca de 2026-10-16, o RTR-Netztest (`https://www.netztest.at/en/Opendata`, CC BY 4.0) foi o único dataset aberto com throughput de Wi-Fi em volume. Junho de 2025 tem 81.969 testes WLAN com RSSI, todos de Android: 51.959 em 5 GHz, 29.566 em 2,4 GHz e 298 em 6 GHz. Download mediano de 81 Mbps em 5 GHz (p90 de 271), com 5.436 testes de 5 GHz acima de 267 Mbps.
- Colunas do RTR que importam: `cat_technology`, `platform`, `signal_strength` (RSSI medido no celular, em dBm), `channel_number` (frequência em MHz, de 2412 a 6375), `download_kbit`, `upload_kbit`, `implausible` e `open_uuid` (cliente anônimo, com 46.235 distintos).
- Nos nossos dados, `RSSI` é o sinal medido no celular (classe `cliente`, presente em 100% das linhas, correlação de 0,78 com `router_signal_dbm`). É o equivalente direto do `signal_strength` do RTR. `router_signal_dbm` é o que o TR-181 expõe (`AssociatedDevice.{i}.SignalStrength`), e é o que a produção teria.
- O conjunto canônico de download tem 1.300 linhas: residência 470, hotmilk 369, casa-marcelo 318, coworking 143. `n_clients`: 1 = 532, 2 = 622, 3 = 143. `radio`: `2.4ghz` = 711, `5ghz` = 589.
- No RTR, o plano de internet de cada teste é desconhecido. Throughput baixo com sinal forte pode ser o plano contratado, não o Wi-Fi. Por isso entram dois quantis: q50 (típico) e q90 (envoltória do que o Wi-Fi entrega quando o plano não limita).

## Critério decidido antes de rodar

- **Funciona** se alguma variante `_ap` (prior calculado de `router_signal_dbm`, implantável) der veredito `melhor` ou `empate` no download, com MAE log do hotmilk pelo menos 0,05 menor que o da `v5` e `predios_contra` vazio.
- Uma variante `_rssi` só conta como transferência de conhecimento se for melhor que o controle `ctrl_rssi` (`v5` + `RSSI` cru). Senão, o ganho vem da informação nova do RSSI, não do RTR.
- **Hipótese do Ronaldo** (cada teste do RTR é um cliente sozinho): vale se a razão mediana `y ÷ prior_q50` for mais próxima de 1 em `n_clients` = 1 e cair com 2 e 3.

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `.gitignore` | ignorar `data/externos/` (o zip mensal tem 39 MB) |
| `src/ml/core/externo_rtr.py` | ler e filtrar o RTR, treinar e aplicar o prior |
| `tests/test_externo_rtr.py` | testes do módulo, com dados sintéticos |
| `src/ml/rtr_prior.py` | o experimento: variantes, comparação na régua, diagnóstico, tabela |
| `tests/test_rtr_prior.py` | testes das partes puras do script |
| `CHANGELOG.md` | resultado e conclusão, no topo |

`carga.discover()` só lista arquivos no nível de `data/` (`os.listdir` sem recursão), então `data/externos/` não entra no conjunto canônico.

Commits: o usuário faz à mão. Os passos de commit abaixo só sugerem a mensagem, sem linha de co-autoria.

---

### Task 1: Dados do RTR fora do git

**Arquivos:**
- Modificar: `.gitignore`

- [ ] **Passo 1: Ignorar a pasta de dados externos**

Acrescentar ao fim de `.gitignore`:

```
data/externos/
```

- [ ] **Passo 2: Baixar junho de 2025**

```bash
mkdir -p data/externos
curl -sSL -o data/externos/netztest-opendata-2025-06.zip \
  "https://www.netztest.at/RMBTStatisticServer/export/netztest-opendata-2025-06.zip"
unzip -l data/externos/netztest-opendata-2025-06.zip
```

Esperado: `LIZENZ.txt` e `netztest-opendata-2025-06.csv` (cerca de 129 MB descompactado).

- [ ] **Passo 3: Confirmar que o git e o carregador ignoram a pasta**

```bash
git status --short
PYTHONPATH=src venv/bin/python -c "from ml.core import carga; print([d['id'] for d in carga.discover()])"
```

Esperado: `git status` mostra só `.gitignore` modificado, e a lista de ids não tem nada de `externos`.

- [ ] **Passo 4: Sugestão de commit (o usuário faz)**

`chore: ignora data/externos (dados abertos do RTR-Netztest)`

---

### Task 2: Ler e filtrar o RTR

**Arquivos:**
- Criar: `src/ml/core/externo_rtr.py`
- Testar: `tests/test_externo_rtr.py`

- [ ] **Passo 1: Escrever os testes que falham**

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import externo_rtr as R


class TestLeitura(unittest.TestCase):
  def test_banda_por_frequencia(self):
    banda = R.banda_por_frequencia(pd.Series([2412, 5180, 5745, 6115, np.nan]))
    self.assertEqual(banda.iloc[:3].tolist(), ['2.4ghz', '5ghz', '5ghz'])
    self.assertTrue(banda.iloc[3:].isna().all())

  def test_limpar_rssi_descarta_zero_e_positivo(self):
    r = R.limpar_rssi(pd.Series([-60, 0, 7, -1]))
    self.assertEqual(r.iloc[0], -60)
    self.assertTrue(r.iloc[1:3].isna().all())
    self.assertEqual(r.iloc[3], -1)

  def test_preparar_rtr_fica_so_com_wlan_android_plausivel(self):
    bruto = pd.DataFrame({
      'cat_technology': ['WLAN', 'LAN', 'WLAN', 'WLAN', 'WLAN', 'WLAN'],
      'platform': ['Android', 'Android', 'iOS', 'Android', 'Android', 'Android'],
      'signal_strength': [-55, -55, -55, -55, np.nan, -55],
      'channel_number': [5180, 5180, 5180, 5180, 5180, 6115],
      'download_kbit': [50000, 1, 1, 1, 1, 1],
      'upload_kbit': [20000, 1, 1, 1, 1, 1],
      'implausible': [False, False, False, True, False, False],
    })
    rtr = R.preparar_rtr(bruto)
    self.assertEqual(len(rtr), 1)
    self.assertEqual(rtr.loc[0, 'radio'], '5ghz')
    self.assertAlmostEqual(rtr.loc[0, 'down_mbps'], 50.0)
    self.assertAlmostEqual(rtr.loc[0, 'up_mbps'], 20.0)
    self.assertEqual(rtr.loc[0, 'rssi'], -55)

  def test_preparar_rtr_implausible_vazio_conta_como_plausivel(self):
    bruto = pd.DataFrame({'cat_technology': ['WLAN'], 'platform': ['Android'], 'signal_strength': [-50],
                          'channel_number': [2437], 'download_kbit': [10000], 'upload_kbit': [5000],
                          'implausible': [np.nan]})
    self.assertEqual(len(R.preparar_rtr(bruto)), 1)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_externo_rtr -v`
Esperado: `ModuleNotFoundError: No module named 'ml.core.externo_rtr'`.

- [ ] **Passo 3: Implementar a leitura**

Criar `src/ml/core/externo_rtr.py`:

```python
"""Prior externo do RTR-Netztest (Áustria, CC BY 4.0): throughput de Wi-Fi por RSSI e banda.

Experimento de 2026-10-16 (docs/superpowers/plans/2026-10-16-prior-rtr-netztest.md). O prior
é treinado só no RTR, então a coluna que ele gera não viu nenhuma linha nossa: não vaza
entre os folds por prédio.
"""

import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

COLUNAS_RTR = ['cat_technology', 'platform', 'signal_strength', 'channel_number',
               'download_kbit', 'upload_kbit', 'implausible']
# Alvo da régua → coluna do RTR preparado.
ALVO_RTR = {'speedtest_down_mbps': 'down_mbps', 'speedtest_up_mbps': 'up_mbps'}
# RSSI >= 0 é leitura inválida dos dois lados (o coletor grava 0 e até +7 dBm).
RSSI_MAXIMO = -1.0


def banda_por_frequencia(mhz: pd.Series) -> pd.Series:
  """Frequência do canal em MHz → '2.4ghz' ou '5ghz', o vocabulário de `radio`.

  6 GHz vira NaN: nenhuma coleta nossa usa a banda.
  """
  f = pd.to_numeric(mhz, errors='coerce')
  banda = pd.Series(np.nan, index=f.index, dtype=object)
  banda[f.between(2400, 2500)] = '2.4ghz'
  banda[f.between(5150, 5925)] = '5ghz'
  return banda


def limpar_rssi(rssi: pd.Series) -> pd.Series:
  r = pd.to_numeric(rssi, errors='coerce')
  return r.where(r <= RSSI_MAXIMO)


def preparar_rtr(bruto: pd.DataFrame) -> pd.DataFrame:
  """Testes WLAN de Android, plausíveis, com RSSI, em 2,4 ou 5 GHz.

  Colunas: rssi (dBm), radio, down_mbps, up_mbps.
  """
  plausivel = ~bruto['implausible'].fillna(False).astype(bool)
  w = bruto[(bruto['cat_technology'] == 'WLAN') & (bruto['platform'] == 'Android') & plausivel]
  saida = pd.DataFrame({'rssi': limpar_rssi(w['signal_strength']),
                        'radio': banda_por_frequencia(w['channel_number']),
                        'down_mbps': w['download_kbit'] / 1000.0,
                        'up_mbps': w['upload_kbit'] / 1000.0})
  return saida.dropna(subset=['rssi', 'radio']).reset_index(drop=True)


def ler_rtr(caminho_zip: str) -> pd.DataFrame:
  """Lê o CSV mensal de dentro do zip do RTR e aplica preparar_rtr."""
  with zipfile.ZipFile(caminho_zip) as arquivo:
    nome = next(n for n in arquivo.namelist() if n.endswith('.csv'))
    with arquivo.open(nome) as handle:
      bruto = pd.read_csv(handle, usecols=COLUNAS_RTR, low_memory=False)
  return preparar_rtr(bruto)
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_externo_rtr -v`
Esperado: 4 testes, `OK`.

- [ ] **Passo 5: Conferir no arquivo real**

```bash
PYTHONPATH=src venv/bin/python -c "
from ml.core import externo_rtr as R
rtr = R.ler_rtr('data/externos/netztest-opendata-2025-06.zip')
print(len(rtr), rtr.radio.value_counts().to_dict())
print(rtr.describe().round(1))"
```

Esperado: cerca de 81,5 mil linhas (os 81.969 testes WLAN com sinal, menos os 298 de 6 GHz e os de RSSI >= 0). Divisão perto de 52 mil em `5ghz` e 29,5 mil em `2.4ghz`.

- [ ] **Passo 6: Sugestão de commit (o usuário faz)**

`feat: leitura dos dados abertos do RTR-Netztest`

---

### Task 3: Treinar e aplicar o prior

**Arquivos:**
- Modificar: `src/ml/core/externo_rtr.py`
- Testar: `tests/test_externo_rtr.py`

- [ ] **Passo 1: Escrever os testes que falham**

Acrescentar a `tests/test_externo_rtr.py`, antes do `if __name__`:

```python
def _rtr_sintetico(n=4000, semente=0):
  """Throughput sobe com o RSSI, e 5 GHz entrega três vezes mais que 2,4 GHz."""
  rng = np.random.default_rng(semente)
  rssi = rng.uniform(-90, -30, n)
  radio = np.where(rng.random(n) < 0.5, '5ghz', '2.4ghz')
  base = (rssi + 100) * np.where(radio == '5ghz', 3.0, 1.0)
  down = base * rng.uniform(0.5, 1.5, n)
  return pd.DataFrame({'rssi': rssi, 'radio': radio, 'down_mbps': down, 'up_mbps': down / 2})


class TestPrior(unittest.TestCase):
  def test_prior_sobe_com_sinal_e_com_5ghz(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    p = R.aplicar_prior(modelo, pd.Series([-80.0, -40.0, -50.0, -50.0]),
                        pd.Series(['5ghz', '5ghz', '2.4ghz', '5ghz']))
    self.assertLess(p[0], p[1])
    self.assertLess(p[2], p[3])

  def test_q90_fica_acima_do_q50(self):
    rtr = _rtr_sintetico()
    rssi, radio = pd.Series([-60.0]), pd.Series(['5ghz'])
    q50 = R.aplicar_prior(R.treinar_prior(rtr, 'down_mbps', 0.5), rssi, radio)[0]
    q90 = R.aplicar_prior(R.treinar_prior(rtr, 'down_mbps', 0.9), rssi, radio)[0]
    self.assertGreater(q90, q50)

  def test_rssi_invalido_vira_nan(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    p = R.aplicar_prior(modelo, pd.Series([0.0, np.nan, -50.0]), pd.Series(['5ghz', '5ghz', '5ghz']))
    self.assertTrue(np.isnan(p[0]))
    self.assertTrue(np.isnan(p[1]))
    self.assertFalse(np.isnan(p[2]))

  def test_aplicar_prior_ignora_indice_do_dataframe(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    rssi = pd.Series([-50.0, -70.0], index=[10, 20])
    radio = pd.Series(['5ghz', '5ghz'], index=[10, 20])
    self.assertEqual(len(R.aplicar_prior(modelo, rssi, radio)), 2)
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_externo_rtr -v`
Esperado: os 4 testes novos falham com `AttributeError: module 'ml.core.externo_rtr' has no attribute 'treinar_prior'`.

- [ ] **Passo 3: Implementar**

Acrescentar ao fim de `src/ml/core/externo_rtr.py`:

```python
def _x(rssi: pd.Series, radio: pd.Series) -> pd.DataFrame:
  radio = pd.Series(radio).reset_index(drop=True)
  cinco = np.where(radio.isna(), np.nan, (radio == '5ghz').astype(float))
  return pd.DataFrame({'rssi': limpar_rssi(pd.Series(rssi)).reset_index(drop=True), 'cinco_ghz': cinco})


def treinar_prior(rtr: pd.DataFrame, coluna_alvo: str, quantil: float) -> HistGradientBoostingRegressor:
  """Quantil `quantil` do throughput dado RSSI e banda.

  Restrição monotônica no RSSI: mais sinal nunca prevê menos.
  """
  modelo = HistGradientBoostingRegressor(loss='quantile', quantile=quantil, monotonic_cst=[1, 0],
                                         max_iter=300, random_state=42)
  modelo.fit(_x(rtr['rssi'], rtr['radio']), rtr[coluna_alvo].to_numpy(dtype=float))
  return modelo


def aplicar_prior(modelo, rssi: pd.Series, radio: pd.Series) -> np.ndarray:
  """Previsão do prior para as nossas linhas. RSSI inválido vira NaN, e o imputer da régua cuida."""
  x = _x(rssi, radio)
  previsto = modelo.predict(x)
  return np.where(x['rssi'].isna().to_numpy(), np.nan, previsto)
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_externo_rtr -v`
Esperado: 8 testes, `OK`.

- [ ] **Passo 5: Sugestão de commit (o usuário faz)**

`feat: prior de throughput por RSSI e banda treinado no RTR-Netztest`

---

### Task 4: Script do experimento

**Arquivos:**
- Criar: `src/ml/rtr_prior.py`
- Testar: `tests/test_rtr_prior.py`

- [ ] **Passo 1: Escrever os testes que falham**

Criar `tests/test_rtr_prior.py`:

```python
import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import rtr_prior as E


class TestRtrPrior(unittest.TestCase):
  def test_variantes_tem_controle_e_quatro_priores(self):
    v = E.variantes()
    self.assertEqual(v['ctrl_rssi'], ['RSSI'])
    self.assertEqual(sorted(k for k in v if k.startswith('prior_')),
                     ['prior_q50_ap', 'prior_q50_rssi', 'prior_q90_ap', 'prior_q90_rssi'])
    self.assertEqual(v['prior_q90_ap'], ['prior_rtr_q90_ap'])

  def test_mae_faixa_alta_so_conta_acima_de_267(self):
    prev = pd.DataFrame({'y': [100.0, 300.0, 500.0], 'yhat': [0.0, 250.0, 400.0]})
    self.assertEqual(E.mae_faixa_alta(prev), 75.0)

  def test_mae_faixa_alta_sem_linhas_altas(self):
    self.assertIsNone(E.mae_faixa_alta(pd.DataFrame({'y': [10.0], 'yhat': [5.0]})))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_rtr_prior -v`
Esperado: `ModuleNotFoundError: No module named 'ml.rtr_prior'`.

- [ ] **Passo 3: Implementar o script**

Criar `src/ml/rtr_prior.py`:

```python
"""Experimento: o prior do RTR-Netztest melhora a v5 no download e no upload?

Uso:
  PYTHONPATH=src venv/bin/python src/ml/rtr_prior.py data/externos/netztest-opendata-2025-06.zip \
    --saida /tmp/rtr_prior.json

Critério decidido antes de rodar: docs/superpowers/plans/2026-10-16-prior-rtr-netztest.md.
"""

import argparse
import json
import os
import sys

from scipy.stats import spearmanr

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as A
from ml.core import carga as core_carga
from ml.core import externo_rtr as R
from ml.core import modelos as core_modelos

BASE = 'v5'
QUANTIS = (0.5, 0.9)
# De onde vem o sinal que alimenta o prior: o RSSI do celular (como o RTR mede) ou o do
# roteador (o que o TR-181 expõe; a única variante implantável).
FONTES = {'rssi': 'RSSI', 'ap': 'router_signal_dbm'}
# Maior download fora do hotmilk (CHANGELOG, critério da C2).
FAIXA_ALTA = 267.0
DOWN, UP = 'speedtest_down_mbps', 'speedtest_up_mbps'


def _coluna(quantil: float, fonte: str) -> str:
  return f'prior_rtr_q{int(round(quantil * 100))}_{fonte}'


def variantes() -> dict:
  """Nome → colunas somadas às da v5.

  `ctrl_rssi` separa "informação nova" (o RSSI do celular) de "conhecimento do RTR".
  """
  saida = {'ctrl_rssi': ['RSSI']}
  for fonte in FONTES:
    for quantil in QUANTIS:
      saida[f'prior_q{int(round(quantil * 100))}_{fonte}'] = [_coluna(quantil, fonte)]
  return saida


def adicionar_priores(conj, rtr):
  """Uma coluna de prior por quantil e fonte, treinada no RTR para o alvo do conjunto."""
  coluna_rtr = R.ALVO_RTR[conj.alvo]
  for quantil in QUANTIS:
    modelo = R.treinar_prior(rtr, coluna_rtr, quantil)
    for fonte, sinal in FONTES.items():
      conj.df[_coluna(quantil, fonte)] = R.aplicar_prior(modelo, conj.df[sinal], conj.df['radio'])
  return conj


def diagnostico(conj) -> dict:
  """Spearman prior × alvo por prédio, e razão mediana alvo ÷ prior por n_clients (hipótese do Ronaldo)."""
  df, y = conj.df, conj.df[conj.alvo]
  saida = {}
  for fonte in FONTES:
    p = df[_coluna(0.5, fonte)]
    saida[fonte] = {
      'spearman_por_predio': {s: round(float(spearmanr(p.loc[g.index], y.loc[g.index], nan_policy='omit').statistic), 3)
                              for s, g in df.groupby('_site')},
      'razao_mediana_por_n_clients': {int(n): round(float((y.loc[g.index] / p.loc[g.index]).median()), 3)
                                      for n, g in df.groupby('n_clients')},
    }
  return saida


def mae_faixa_alta(prev):
  """MAE só nas linhas com alvo acima de FAIXA_ALTA, ou None se não houver."""
  alta = prev['y'] > FAIXA_ALTA
  if not alta.any():
    return None
  return round(float((prev.loc[alta, 'y'] - prev.loc[alta, 'yhat']).abs().mean()), 2)


def rodar(caminho_zip: str) -> dict:
  rtr = R.ler_rtr(caminho_zip)
  registro = core_modelos.carregar()
  features_base = list(registro['versoes'][BASE]['features'])
  aplicacoes = core_aplicacoes.carregar()
  resultado = {'rtr': {'linhas': int(len(rtr)), 'por_banda': rtr['radio'].value_counts().to_dict()}}
  previsoes = {}
  for alvo in (DOWN, UP):
    conj = adicionar_priores(core_carga.carregar(alvo), rtr)
    vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
    denominador = core_modelos.denominador_de(registro, BASE, alvo)
    resultado[alvo] = {'diagnostico': diagnostico(conj)}
    for nome, extras in {'base': [], **variantes()}.items():
      resumo, prev = A.avaliar(conj, features_base + extras, vazadas, com_previsoes=True,
                               denominador=denominador)
      previsoes[(alvo, nome)] = prev
      resultado[alvo][nome] = {'mae': resumo['mae'], 'mae_log': resumo['mae_log'],
                               'mae_log_por_local': resumo['mae_log_por_local'],
                               'mae_faixa_alta': mae_faixa_alta(prev)}
  for nome in variantes():
    d_atende = A.delta_atende(previsoes[(DOWN, nome)], previsoes[(UP, nome)],
                              previsoes[(DOWN, 'base')], previsoes[(UP, 'base')], aplicacoes)
    for alvo in (DOWN, UP):
      d_mae = A.delta_mae(previsoes[(alvo, nome)], previsoes[(alvo, 'base')])
      resultado[alvo][nome]['delta_mae'] = d_mae
      resultado[alvo][nome]['delta_atende'] = d_atende
      resultado[alvo][nome]['veredito'] = A.veredito_promocao(d_mae, d_atende)
  return resultado


def imprimir(resultado: dict) -> None:
  print(f"RTR: {resultado['rtr']['linhas']} testes {resultado['rtr']['por_banda']}")
  for alvo in (DOWN, UP):
    print(f'\n{alvo}')
    print(f"{'variante':<16} {'MAE':>7} {'MAE log':>8} {'hotmilk log':>12} {'>267 MAE':>9}  veredito")
    for nome, r in resultado[alvo].items():
      if nome == 'diagnostico':
        continue
      v = r.get('veredito', {})
      contra = ', '.join(v.get('predios_contra', []))
      print(f"{nome:<16} {r['mae']:>7.2f} {r['mae_log']:>8.3f} {r['mae_log_por_local'].get('hotmilk', float('nan')):>12.3f} "
            f"{r['mae_faixa_alta'] if r['mae_faixa_alta'] is not None else '-':>9}  "
            f"{v.get('resultado', '')} {('(contra: ' + contra + ')') if contra else ''}")
    print('diagnóstico:', json.dumps(resultado[alvo]['diagnostico'], ensure_ascii=False))


def main():
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument('rtr_zip')
  parser.add_argument('--saida', help='grava o resultado completo em JSON')
  args = parser.parse_args()
  resultado = rodar(args.rtr_zip)
  imprimir(resultado)
  if args.saida:
    with open(args.saida, 'w', encoding='utf-8') as handle:
      json.dump(resultado, handle, ensure_ascii=False, indent=2, default=str)


if __name__ == '__main__':
  main()
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_rtr_prior -v`
Esperado: 3 testes, `OK`.

- [ ] **Passo 5: Rodar a suíte inteira**

Rodar: `venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -5`
Esperado: `OK` (mais 11 testes que antes).

- [ ] **Passo 6: Sugestão de commit (o usuário faz)**

`feat: experimento do prior RTR-Netztest contra a v5`

---

### Task 5: Rodar o experimento e registrar

**Arquivos:**
- Modificar: `CHANGELOG.md` (nova seção no topo)

- [ ] **Passo 1: Rodar**

```bash
PYTHONPATH=src venv/bin/python src/ml/rtr_prior.py data/externos/netztest-opendata-2025-06.zip \
  --saida /tmp/rtr_prior.json
```

Esperado: duas tabelas (download e upload) com as linhas `base`, `ctrl_rssi` e as quatro `prior_*`, cada uma com veredito, mais o diagnóstico. A linha `base` tem que bater com a avaliação gravada da `v5` em `modelos.json`: MAE de download 38,25 e MAE log do hotmilk 0,698. Se não bater, parar e investigar antes de seguir: a base não é a mesma.

- [ ] **Passo 2: Aplicar o critério decidido antes de rodar**

Com o JSON:
1. Alguma `prior_*_ap` teve `melhor` ou `empate` no download, MAE log do hotmilk pelo menos 0,05 menor que o da `base`, e `predios_contra` vazio? Se sim, **funciona**.
2. Alguma `prior_*_rssi` ficou melhor que `ctrl_rssi` (MAE log e MAE da faixa alta)? Se sim, o RTR transfere conhecimento. Se não, o ganho que houver é do RSSI cru.
3. Hipótese do Ronaldo: a razão mediana `y ÷ prior_q50` fica mais perto de 1 em `n_clients` = 1 e cai com 2 e 3?

- [ ] **Passo 3: Registrar no CHANGELOG**

Nova seção no topo de `CHANGELOG.md`, no formato das outras:

```markdown
# Changelog — Prior externo do RTR-Netztest

**Data:** <data da execução>

Experimento da frente C2 (dados externos), reaberta na reunião de 2026-10-14. Plano:
`docs/superpowers/plans/2026-10-16-prior-rtr-netztest.md`.

## Resultado

<as duas tabelas do passo 1, como tabelas markdown>

## Conclusão

<as três respostas do passo 2, uma frase cada, com os números>
```

- [ ] **Passo 4: Sugestão de commit (o usuário faz)**

`docs: resultado do experimento do prior RTR-Netztest`

---

## Fora do escopo

- Rede neural pré-treinada no RTR e ajustada nas nossas coletas: fica para depois das coletas AX do Rodrigo, como decidido na reunião.
- Inferir `client_mode` pelo modelo do aparelho do RTR. Só vale tentar se o prior simples funcionar.
- Filtrar o teto de WAN por cliente (`open_uuid`). O q90 é a primeira resposta a esse problema. Se o q50 e o q90 divergirem muito no resultado, o filtro vira o próximo passo.
- Salvar uma versão nova no registro. Se funcionar, a promoção segue o fluxo do Studio, com a etiqueta de cobertura.
