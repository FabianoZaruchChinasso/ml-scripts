# Fine-tuning com pré-treino no RTR-Netztest: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** medir, na régua atual, se uma rede neural pré-treinada nos testes de Wi-Fi do RTR-Netztest e ajustada nas nossas coletas (fine-tuning) ganha da `v5` e da mesma rede treinada do zero, no download e no upload.

**Arquitetura:** `src/ml/core/rede_pre.py` define uma rede com duas entradas somadas na primeira camada. A entrada `comum` recebe o que o RTR tem (sinal e banda) e é a única usada no pré-treino. A entrada `extra` recebe as outras features da `v5` e começa zerada, então antes do ajuste a rede é exatamente a pré-treinada. O estimador `MLPAjustado`, compatível com scikit-learn, entra em `avaliacao.prever_fora_do_fold(estimador=...)`. O ajuste refaz o treino em cada fold, sem o prédio de teste. O script `src/ml/rtr_finetune.py` roda as variantes e compara pela régua.

**Stack:** PyTorch (CPU), pandas, scikit-learn 1.9, unittest.

---

## Contexto

- **Experimento anterior** (CHANGELOG, "Prior externo do RTR-Netztest", 2026-10-16): um modelo do RTR usado como coluna extra da `v5` deu "melhor" por cerca de 1 Mbps de MAE. Mas o MAE log do hotmilk caiu só 0,007, e o MAE acima de 267 Mbps foi de 199 para 197. Aquilo não era fine-tuning: o random forest continuava treinando só nos nossos dados. Este plano testa o fine-tuning de verdade, pedido pelo usuário em 2026-10-16.
- **RTR preparado:** `externo_rtr.ler_rtr` devolve 81.494 testes com `rssi` (dBm, medido no celular), `radio` (`2.4ghz`/`5ghz`), `down_mbps` e `up_mbps`. Download vai até 1.057 Mbps.
- **Matriz da `v5`:** `features.matriz` sobre as 9 features da `v5` dá 12 colunas: `client_mode_WiFi 4 (11n)`, `client_mode_WiFi 5 (11ac)`, `client_mode_WiFi 6 (11ax)`, `radio_2.4ghz`, `radio_5ghz`, `router_rx_rate_mbps`, `router_snr`, `router_signal_dbm`, `router_tx_rate_mbps`, `channel_width`, `n_clients`, `concorrentes_mesmo_radio`. Há poucos NaN: `channel_width` 5,5%, `concorrentes_mesmo_radio` 1,8%.
- **Download máximo por prédio:** hotmilk 671, coworking 267, casa-marcelo 226, residência 158. Com o hotmilk fora do treino, nenhuma linha de treino passa de 267.
- **Dois sinais possíveis para a entrada `comum`:**
  - `router_signal_dbm` é o que o TR-181 expõe; é a variante implantável.
  - `RSSI` é medido no celular, como no RTR. Correlação de 0,78 com `router_signal_dbm`.
- **Escala do sinal:** fixa, `(dBm + 60) ÷ 15`, igual no RTR e nos nossos dados, para que o pré-treino e o ajuste vejam a mesma unidade. Sinal inválido (≥ 0 dBm ou vazio) vira 0, que corresponde a −60 dBm.
- **Alvo da rede:** `log1p(Mbps)`, com perda L1, que é o MAE log da régua. A previsão volta com `expm1` e é cortada em `[0, teto]`.
  - O teto é o maior entre 1,2 × o máximo do treino e o p99,9 do alvo no RTR.
  - O corte responde ao problema relatado na reunião de 2026-10-14: a rede neural alucinou valores altos ao extrapolar para AX.
  - Depois do corte da rede, a régua ainda aplica o teto de WAN do prédio.
- **`prever_fora_do_fold`:**
  - Recebe o estimador e o clona a cada fold (`sklearn.base.clone`).
  - Chama `fit(X_train, y_train)` só com linhas fora do teto de WAN, e depois `predict(X_test)`.
  - `X` é o DataFrame de `matriz`, com os nomes de coluna acima.

## Hiperparâmetros fixados antes de rodar

Os hiperparâmetros abaixo não são ajustados olhando os folds de teste. Ajustá-los depois de ver o resultado seria escolher o modelo pelo teste.

| Parâmetro | Valor |
|---|---|
| neurônios por camada oculta | 64 (duas camadas) |
| pré-treino | 20 épocas, lote de 1.024, Adam com lr 1e-3, semente 42 |
| ajuste | 300 épocas com lote inteiro, Adam com lr 1e-3 e weight decay 1e-4 |
| lr das camadas pré-treinadas no ajuste | 0,1 × lr (a proposta do Lucas na reunião: o pré-treino pesa, mas cede aos nossos dados) |
| redes por estimador | 5, sementes 42 a 46, média em log (só muda algo no controle; com pré-treino, as 5 partem do mesmo ponto) |

## Critério decidido antes de rodar

- **Funciona** se as duas condições abaixo valerem juntas:
  1. `ft_ap` contra a `v5` no download: veredito `melhor` ou `empate`, MAE log do hotmilk pelo menos 0,05 menor e `predios_contra` vazio.
  2. `ft_ap` contra `zero_ap`: MAE log do hotmilk pelo menos 0,05 menor, ou veredito `melhor`. Sem isso, o ganho vem de trocar random forest por rede neural, não do RTR.
- **Alucinação:** o máximo previsto no fold do hotmilk tem que ficar abaixo de 1.000 Mbps (o real chega a 671). Acima disso o corte está segurando uma rede que extrapola mal, e o resultado não vale mesmo que o MAE caia.
- As variantes `_rssi` são diagnóstico, não candidatas: o `RSSI` do celular não vem pelo TR-181.

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/ml/core/rede_pre.py` | escala do sinal, rede, pré-treino no RTR, estimador `MLPAjustado` |
| `tests/test_rede_pre.py` | testes do módulo, com dados sintéticos |
| `src/ml/rtr_finetune.py` | o experimento: variantes, comparação na régua, tabela |
| `tests/test_rtr_finetune.py` | testes das partes puras do script |
| `CHANGELOG.md` | resultado e conclusão, no topo |

Commits: o usuário faz à mão. Os passos de commit abaixo só sugerem a mensagem, sem linha de co-autoria.

---

### Task 1: PyTorch no venv

**Arquivos:** nenhum (o `requirements.txt` já lista `torch`).

- [ ] **Passo 1: Instalar a versão CPU**

```bash
venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
```

- [ ] **Passo 2: Conferir**

```bash
venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Esperado: uma versão 2.x e `False`.

---

### Task 2: Escala do sinal e a rede

**Arquivos:**
- Criar: `src/ml/core/rede_pre.py`
- Testar: `tests/test_rede_pre.py`

- [ ] **Passo 1: Escrever os testes que falham**

Criar `tests/test_rede_pre.py`:

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd
import torch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import rede_pre as P


class TestSinal(unittest.TestCase):
  def test_normalizar_sinal(self):
    s = P.normalizar_sinal(pd.Series([-60.0, -75.0, 0.0, np.nan]))
    np.testing.assert_allclose(s, [0.0, -1.0, 0.0, 0.0])
    self.assertEqual(s.dtype, np.float32)


class TestRede(unittest.TestCase):
  def test_extra_comeca_zerada_e_nao_muda_a_saida(self):
    rede = P.Rede(3, 8)
    self.assertTrue(torch.all(rede.extra.weight == 0))
    xc = torch.randn(5, 2)
    with torch.no_grad():
      torch.testing.assert_close(rede(xc, torch.randn(5, 3)), rede(xc, torch.zeros(5, 3)))

  def test_sem_extra(self):
    rede = P.Rede(0, 8)
    self.assertIsNone(rede.extra)
    self.assertEqual(rede(torch.randn(4, 2)).shape, (4,))

  def test_pesos_pre_nao_levam_a_entrada_extra(self):
    pesos = P.Rede(3, 8).pesos_pre()
    self.assertTrue(pesos)
    self.assertFalse([k for k in pesos if k.startswith('extra.')])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: `ModuleNotFoundError: No module named 'ml.core.rede_pre'`.

- [ ] **Passo 3: Implementar**

Criar `src/ml/core/rede_pre.py`:

```python
"""Rede pré-treinada no RTR-Netztest e ajustada nas nossas coletas (fine-tuning).

Plano: docs/superpowers/plans/2026-10-16-finetune-rtr.md. O RTR só tem sinal e banda. As
outras features da v5 entram por uma camada própria que começa zerada, então, antes do
ajuste, a rede é exatamente a pré-treinada.
"""

import numpy as np
import pandas as pd
import torch
from sklearn.base import BaseEstimator, RegressorMixin
from torch import nn

from ml.core.externo_rtr import limpar_rssi

# Escala fixa do sinal, igual nos dois domínios: (dBm + 60) / 15. Inválido vira 0 (= -60 dBm).
SINAL_CENTRO = -60.0
SINAL_ESCALA = 15.0


def normalizar_sinal(dbm) -> np.ndarray:
  s = (limpar_rssi(pd.Series(dbm, dtype=float)) - SINAL_CENTRO) / SINAL_ESCALA
  return s.fillna(0.0).to_numpy(dtype=np.float32)


class Rede(nn.Module):
  """Duas entradas somadas na primeira camada: `comum` (sinal e 5 GHz) e `extra` (o resto).

  `extra` começa zerada: só os dados nossos a fazem pesar.
  """

  def __init__(self, n_extra: int, oculta: int):
    super().__init__()
    self.comum = nn.Linear(2, oculta)
    self.extra = nn.Linear(n_extra, oculta, bias=False) if n_extra else None
    if self.extra is not None:
      nn.init.zeros_(self.extra.weight)
    self.tronco = nn.Sequential(nn.ReLU(), nn.Linear(oculta, oculta), nn.ReLU(), nn.Linear(oculta, 1))

  def forward(self, xc, xe=None):
    h = self.comum(xc)
    if self.extra is not None and xe is not None:
      h = h + self.extra(xe)
    return self.tronco(h).squeeze(-1)

  def pesos_pre(self) -> dict:
    """O que o pré-treino aprende: `comum` e `tronco`."""
    return {k: v.detach().clone() for k, v in self.state_dict().items() if not k.startswith('extra.')}
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: 4 testes, `OK`.

- [ ] **Passo 5: Sugestão de commit (o usuário faz)**

`feat: rede com entrada comum ao RTR e entrada extra zerada`

---

### Task 3: Pré-treino no RTR

**Arquivos:**
- Modificar: `src/ml/core/rede_pre.py`
- Testar: `tests/test_rede_pre.py`

- [ ] **Passo 1: Escrever os testes que falham**

Acrescentar a `tests/test_rede_pre.py`, antes do `if __name__`:

```python
def _rtr(n=3000, semente=0):
  """Throughput sobe com o sinal, e 5 GHz entrega três vezes mais que 2,4 GHz."""
  rng = np.random.default_rng(semente)
  rssi = rng.uniform(-90, -30, n)
  radio = np.where(rng.random(n) < 0.5, '5ghz', '2.4ghz')
  down = (rssi + 100) * np.where(radio == '5ghz', 3.0, 1.0) * rng.uniform(0.8, 1.2, n)
  return pd.DataFrame({'rssi': rssi, 'radio': radio, 'down_mbps': down, 'up_mbps': down / 2})


class TestPreTreino(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.rtr = _rtr()
    cls.pre = P.pre_treinar(cls.rtr, 'down_mbps', oculta=16, epocas=30, lr=1e-2)

  def test_devolve_pesos_oculta_e_teto(self):
    self.assertEqual(self.pre['oculta'], 16)
    self.assertAlmostEqual(self.pre['teto_mbps'], float(np.quantile(self.rtr['down_mbps'], 0.999)))
    self.assertIn('comum.weight', self.pre['pesos'])

  def test_aprende_sinal_e_banda(self):
    rede = P.Rede(0, 16)
    rede.load_state_dict(self.pre['pesos'], strict=False)
    xc = P._comum(pd.Series([-80.0, -40.0, -50.0, -50.0]), np.array([1.0, 1.0, 0.0, 1.0]))
    with torch.no_grad():
      p = rede(xc)
    self.assertLess(p[0], p[1])
    self.assertLess(p[2], p[3])
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: os 2 testes novos dão erro com `AttributeError: module 'ml.core.rede_pre' has no attribute 'pre_treinar'`.

- [ ] **Passo 3: Implementar**

Acrescentar ao fim de `src/ml/core/rede_pre.py`:

```python
def _comum(sinal, radio_5ghz) -> torch.Tensor:
  cinco = np.nan_to_num(np.asarray(radio_5ghz, dtype=np.float32), nan=0.0)
  return torch.from_numpy(np.column_stack([normalizar_sinal(sinal), cinco]).astype(np.float32))


def pre_treinar(rtr: pd.DataFrame, coluna_alvo: str, oculta: int = 64, epocas: int = 20,
                lote: int = 1024, lr: float = 1e-3, semente: int = 42) -> dict:
  """Treina `comum` e `tronco` no RTR, com perda L1 em log1p(Mbps), que é o MAE log da régua.

  Devolve {'pesos', 'oculta', 'teto_mbps'}. `teto_mbps` é o p99,9 do alvo no RTR, o maior
  valor que a rede ajustada pode prever (contra a alucinação para cima vista na reunião
  de 2026-10-14).
  """
  torch.manual_seed(semente)
  xc = _comum(rtr['rssi'], (rtr['radio'] == '5ghz').astype(float))
  y = torch.from_numpy(np.log1p(rtr[coluna_alvo].to_numpy(dtype=np.float32)))
  rede = Rede(0, oculta)
  otimizador = torch.optim.Adam(rede.parameters(), lr=lr)
  gerador = torch.Generator().manual_seed(semente)
  for _ in range(epocas):
    for idx in torch.randperm(len(y), generator=gerador).split(lote):
      otimizador.zero_grad()
      nn.functional.l1_loss(rede(xc[idx]), y[idx]).backward()
      otimizador.step()
  return {'pesos': rede.pesos_pre(), 'oculta': oculta,
          'teto_mbps': float(np.quantile(rtr[coluna_alvo], 0.999))}
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: 6 testes, `OK`.

- [ ] **Passo 5: Sugestão de commit (o usuário faz)**

`feat: pré-treino da rede no RTR-Netztest`

---

### Task 4: Estimador `MLPAjustado`

**Arquivos:**
- Modificar: `src/ml/core/rede_pre.py`
- Testar: `tests/test_rede_pre.py`

- [ ] **Passo 1: Escrever os testes que falham**

Acrescentar a `tests/test_rede_pre.py`, antes do `if __name__` (usa `_rtr` da Task 3):

```python
from sklearn.base import clone


def _nossos(n=80, semente=1):
  """Mesma física do _rtr, mais contenção: o throughput se divide por n_clients."""
  rng = np.random.default_rng(semente)
  sinal = rng.uniform(-80, -40, n)
  cinco = (rng.random(n) < 0.5).astype(float)
  n_clients = rng.integers(1, 4, n).astype(float)
  y = (sinal + 100) * np.where(cinco == 1, 3.0, 1.0) / n_clients
  X = pd.DataFrame({'router_signal_dbm': sinal, 'radio_2.4ghz': 1 - cinco, 'radio_5ghz': cinco,
                    'n_clients': n_clients})
  return X, pd.Series(y)


class TestMLPAjustado(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.pre = P.pre_treinar(_rtr(), 'down_mbps', oculta=16, epocas=30, lr=1e-2)
    cls.X, cls.y = _nossos()

  def test_sem_ajuste_e_a_rede_pre_treinada(self):
    est = P.MLPAjustado(pre=self.pre, epocas=0, n_redes=1).fit(self.X, self.y)
    outro = self.X.assign(n_clients=99.0)
    np.testing.assert_allclose(est.predict(self.X), est.predict(outro), rtol=1e-6)
    rede = P.Rede(0, 16)
    rede.load_state_dict(self.pre['pesos'], strict=False)
    with torch.no_grad():
      esperado = np.expm1(rede(P._comum(self.X['router_signal_dbm'], self.X['radio_5ghz'])).numpy())
    np.testing.assert_allclose(est.predict(self.X), np.clip(esperado, 0, est.teto_), rtol=1e-5)

  def test_clone_ajusta_e_respeita_o_teto(self):
    est = clone(P.MLPAjustado(pre=self.pre, epocas=50, n_redes=2)).fit(self.X, self.y)
    p = est.predict(self.X)
    self.assertEqual(len(p), len(self.X))
    self.assertTrue((p >= 0).all() and (p <= est.teto_).all())
    self.assertGreaterEqual(est.teto_, self.pre['teto_mbps'])

  def test_controle_e_reprodutivel(self):
    a = P.MLPAjustado(pre=None, epocas=50, n_redes=2).fit(self.X, self.y).predict(self.X)
    b = P.MLPAjustado(pre=None, epocas=50, n_redes=2).fit(self.X, self.y).predict(self.X)
    np.testing.assert_allclose(a, b)

  def test_ajuste_aprende_a_feature_extra(self):
    est = P.MLPAjustado(pre=self.pre, epocas=500, lr=1e-2, n_redes=1).fit(self.X, self.y)
    linhas = pd.DataFrame({'router_signal_dbm': [-50.0, -50.0], 'radio_2.4ghz': [0.0, 0.0],
                           'radio_5ghz': [1.0, 1.0], 'n_clients': [1.0, 3.0]})
    p = est.predict(linhas)
    self.assertGreater(p[0], p[1])

  def test_nan_nas_extras_usa_a_mediana_do_treino(self):
    est = P.MLPAjustado(pre=None, epocas=10, n_redes=1).fit(self.X, self.y)
    com_nan = self.X.iloc[:3].assign(n_clients=np.nan)
    self.assertFalse(np.isnan(est.predict(com_nan)).any())
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: os 5 testes novos dão erro com `AttributeError: module 'ml.core.rede_pre' has no attribute 'MLPAjustado'`.

- [ ] **Passo 3: Implementar**

Acrescentar ao fim de `src/ml/core/rede_pre.py`:

```python
class MLPAjustado(BaseEstimator, RegressorMixin):
  """Estimador scikit-learn para `avaliacao.prever_fora_do_fold(estimador=...)`.

  Com `pre`, carrega a rede pré-treinada e ajusta tudo, com taxa de aprendizado
  `fator_lr_pre` vezes menor nas camadas pré-treinadas. Sem `pre`, é o controle: a mesma
  rede, do zero. `col_sinal` e `col_5ghz` são as colunas da matriz que fazem o papel do
  sinal e da banda do RTR; as demais vão para a entrada `extra`, com mediana e
  padronização do treino. `n_redes` redes com sementes seguidas, média em log.
  """

  def __init__(self, pre=None, col_sinal='router_signal_dbm', col_5ghz='radio_5ghz', oculta=64,
               epocas=300, lr=1e-3, fator_lr_pre=0.1, n_redes=5, semente=42):
    self.pre = pre
    self.col_sinal = col_sinal
    self.col_5ghz = col_5ghz
    self.oculta = oculta
    self.epocas = epocas
    self.lr = lr
    self.fator_lr_pre = fator_lr_pre
    self.n_redes = n_redes
    self.semente = semente

  def _entradas(self, X: pd.DataFrame):
    xc = _comum(X[self.col_sinal], X[self.col_5ghz])
    extra = X[self.extras_].astype(float).fillna(self.medianas_)
    xe = ((extra - self.medias_) / self.escalas_).to_numpy(dtype=np.float32)
    return xc, torch.from_numpy(xe)

  def _grupos(self, rede: Rede) -> list:
    if not self.pre:
      return [{'params': list(rede.parameters()), 'lr': self.lr}]
    grupos = [{'params': [p for n, p in rede.named_parameters() if not n.startswith('extra.')],
               'lr': self.lr * self.fator_lr_pre}]
    if rede.extra is not None:
      grupos.append({'params': list(rede.extra.parameters()), 'lr': self.lr})
    return grupos

  def fit(self, X, y):
    X = pd.DataFrame(X)
    self.extras_ = [c for c in X.columns if c not in (self.col_sinal, self.col_5ghz)]
    extra = X[self.extras_].astype(float)
    self.medianas_ = extra.median()
    extra = extra.fillna(self.medianas_)
    self.medias_ = extra.mean()
    self.escalas_ = extra.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
    xc, xe = self._entradas(X)
    alvo = torch.from_numpy(np.log1p(np.asarray(y, dtype=np.float32)))
    oculta = self.pre['oculta'] if self.pre else self.oculta
    self.redes_ = []
    for i in range(self.n_redes):
      torch.manual_seed(self.semente + i)
      rede = Rede(len(self.extras_), oculta)
      if self.pre:
        rede.load_state_dict(self.pre['pesos'], strict=False)
      otimizador = torch.optim.Adam(self._grupos(rede), weight_decay=1e-4)
      for _ in range(self.epocas):
        otimizador.zero_grad()
        nn.functional.l1_loss(rede(xc, xe), alvo).backward()
        otimizador.step()
      self.redes_.append(rede)
    teto_pre = self.pre['teto_mbps'] if self.pre else 0.0
    self.teto_ = max(1.2 * float(np.max(np.asarray(y, dtype=float))), teto_pre)
    return self

  def predict(self, X):
    xc, xe = self._entradas(pd.DataFrame(X))
    with torch.no_grad():
      log = torch.stack([rede(xc, xe) for rede in self.redes_]).mean(0).numpy()
    return np.clip(np.expm1(log), 0.0, self.teto_)
```

- [ ] **Passo 4: Rodar e ver passar**

Rodar: `venv/bin/python -m unittest tests.test_rede_pre -v`
Esperado: 11 testes, `OK`.

- [ ] **Passo 5: Sugestão de commit (o usuário faz)**

`feat: estimador MLPAjustado (fine-tuning sobre o pré-treino do RTR)`

---

### Task 5: Script do experimento

**Arquivos:**
- Criar: `src/ml/rtr_finetune.py`
- Testar: `tests/test_rtr_finetune.py`

- [ ] **Passo 1: Escrever os testes que falham**

Criar `tests/test_rtr_finetune.py`:

```python
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import rtr_finetune as E


class TestRtrFinetune(unittest.TestCase):
  def test_variantes(self):
    v = E.variantes()
    self.assertEqual(sorted(v), ['ft_ap', 'ft_rssi', 'zero_ap', 'zero_rssi'])
    self.assertEqual(v['ft_ap'], ([], 'router_signal_dbm', True))
    self.assertEqual(v['zero_rssi'], (['RSSI'], 'RSSI', False))

  def test_comparacoes(self):
    self.assertEqual(E.COMPARACOES, [('ft_ap', 'base'), ('ft_ap', 'zero_ap'),
                                     ('ft_rssi', 'base'), ('ft_rssi', 'zero_rssi')])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Passo 2: Rodar e ver falhar**

Rodar: `venv/bin/python -m unittest tests.test_rtr_finetune -v`
Esperado: `ImportError: cannot import name 'rtr_finetune' from 'ml'`.

- [ ] **Passo 3: Implementar o script**

Criar `src/ml/rtr_finetune.py`:

```python
"""Experimento: fine-tuning de uma rede pré-treinada no RTR-Netztest, contra a v5 e contra a mesma rede do zero.

Uso:
  PYTHONPATH=src venv/bin/python src/ml/rtr_finetune.py data/externos/netztest-opendata-2025-06.zip \\
    --saida /tmp/rtr_finetune.json

Hiperparâmetros e critério decididos antes de rodar: docs/superpowers/plans/2026-10-16-finetune-rtr.md.
"""

import argparse
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as A
from ml.core import carga as core_carga
from ml.core import externo_rtr as R
from ml.core import modelos as core_modelos
from ml.core.rede_pre import MLPAjustado, pre_treinar
from ml.rtr_prior import BASE, DOWN, UP, mae_faixa_alta

# Fonte → (colunas somadas às da v5, coluna que faz o papel do sinal do RTR). `ap` é a
# implantável (TR-181); `rssi` usa o sinal do celular, como o RTR mede, e é só diagnóstico.
FONTES = {'ap': ([], 'router_signal_dbm'), 'rssi': (['RSSI'], 'RSSI')}
# (nova, referência): contra a v5 decide a promoção; contra o controle do zero mostra se o RTR ajudou.
COMPARACOES = [(f'ft_{fonte}', ref) for fonte in FONTES for ref in ('base', f'zero_{fonte}')]


def variantes() -> dict:
  """Nome → (colunas extras, coluna de sinal, usa pré-treino)."""
  saida = {}
  for fonte, (extras, sinal) in FONTES.items():
    saida[f'zero_{fonte}'] = (extras, sinal, False)
    saida[f'ft_{fonte}'] = (extras, sinal, True)
  return saida


def _linha(resumo: dict, prev) -> dict:
  return {'mae': resumo['mae'], 'mae_log': resumo['mae_log'],
          'mae_log_por_local': resumo['mae_log_por_local'], 'mae_faixa_alta': mae_faixa_alta(prev),
          'max_previsto_por_local': {s: round(float(g['yhat'].max()), 1) for s, g in prev.groupby('_site')}}


def rodar(caminho_zip: str) -> dict:
  rtr = R.ler_rtr(caminho_zip)
  registro = core_modelos.carregar()
  features_base = list(registro['versoes'][BASE]['features'])
  aplicacoes = core_aplicacoes.carregar()
  resultado, previsoes = {}, {}
  for alvo in (DOWN, UP):
    conj = core_carga.carregar(alvo)
    vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
    pre = pre_treinar(rtr, R.ALVO_RTR[alvo])
    resumo, prev = A.avaliar(conj, features_base, vazadas, com_previsoes=True,
                             denominador=core_modelos.denominador_de(registro, BASE, alvo))
    previsoes[(alvo, 'base')] = prev
    resultado[alvo] = {'base': _linha(resumo, prev)}
    for nome, (extras, sinal, usa_pre) in variantes().items():
      colunas = features_base + extras
      estimador = MLPAjustado(pre=pre if usa_pre else None, col_sinal=sinal)
      prev = A.prever_fora_do_fold(conj.df, colunas, alvo, vazadas, estimador=estimador)
      previsoes[(alvo, nome)] = prev
      resultado[alvo][nome] = _linha(A.resumir(prev, len(colunas)), prev)
  resultado['comparacoes'] = {}
  for nova, ref in COMPARACOES:
    d_atende = A.delta_atende(previsoes[(DOWN, nova)], previsoes[(UP, nova)],
                              previsoes[(DOWN, ref)], previsoes[(UP, ref)], aplicacoes)
    for alvo in (DOWN, UP):
      d_mae = A.delta_mae(previsoes[(alvo, nova)], previsoes[(alvo, ref)])
      resultado['comparacoes'][f'{alvo}: {nova} x {ref}'] = {
        'delta_mae': d_mae, 'delta_atende': d_atende, 'veredito': A.veredito_promocao(d_mae, d_atende)}
  return resultado


def imprimir(resultado: dict) -> None:
  for alvo in (DOWN, UP):
    print(f'\n{alvo}')
    print(f"{'variante':<10} {'MAE':>7} {'MAE log':>8} {'hotmilk log':>12} {'>267 MAE':>9} {'máx hotmilk':>12}")
    for nome, r in resultado[alvo].items():
      alta = r['mae_faixa_alta'] if r['mae_faixa_alta'] is not None else '-'
      print(f"{nome:<10} {r['mae']:>7.2f} {r['mae_log']:>8.3f} "
            f"{r['mae_log_por_local'].get('hotmilk', float('nan')):>12.3f} {alta:>9} "
            f"{r['max_previsto_por_local'].get('hotmilk', float('nan')):>12.1f}")
  print('\ncomparações')
  for chave, c in resultado['comparacoes'].items():
    v = c['veredito']
    contra = ', '.join(v['predios_contra'])
    print(f"{chave:<44} Δ MAE {c['delta_mae']['valor']:+.2f} {c['delta_mae']['intervalo']}  "
          f"{v['resultado']}{' (contra: ' + contra + ')' if contra else ''}")


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

Rodar: `venv/bin/python -m unittest tests.test_rtr_finetune -v`
Esperado: 2 testes, `OK`.

- [ ] **Passo 5: Rodar a suíte inteira**

Rodar: `venv/bin/python -m unittest discover -s tests 2>&1 | tail -3`
Esperado: `OK`, com 490 testes (os 477 de antes mais 13 novos).

- [ ] **Passo 6: Sugestão de commit (o usuário faz)**

`feat: experimento de fine-tuning sobre o pré-treino do RTR`

---

### Task 6: Rodar o experimento e registrar

**Arquivos:**
- Modificar: `CHANGELOG.md` (nova seção no topo)

- [ ] **Passo 1: Rodar**

```bash
PYTHONPATH=src venv/bin/python -W ignore src/ml/rtr_finetune.py data/externos/netztest-opendata-2025-06.zip \
  --saida /tmp/rtr_finetune.json
```

Esperado: tabelas de download e upload com `base`, `zero_ap`, `ft_ap`, `zero_rssi` e `ft_rssi`, mais 8 comparações. A linha `base` tem que repetir a do experimento anterior: download com MAE 38,25 e MAE log do hotmilk 0,698. Se não repetir, parar e investigar.

- [ ] **Passo 2: Aplicar o critério decidido antes de rodar**

1. Condição 1: `ft_ap x base` no download tem `melhor` ou `empate`, MAE log do hotmilk pelo menos 0,05 menor que o da base, e `predios_contra` vazio?
2. Condição 2: `ft_ap x zero_ap` tem MAE log do hotmilk pelo menos 0,05 menor, ou veredito `melhor`?
3. Alucinação: o máximo previsto no hotmilk fica abaixo de 1.000 Mbps nas variantes `ft_`?

"Funciona" só se 1 e 2 valerem e 3 passar. Não ajustar hiperparâmetros depois de ver o resultado.

- [ ] **Passo 3: Registrar no CHANGELOG**

Nova seção no topo de `CHANGELOG.md`, seguida de `---`, no formato da seção "Prior externo do RTR-Netztest": título `# Changelog — Fine-tuning com pré-treino no RTR-Netztest`, data, um parágrafo de contexto citando este plano, as tabelas de download e upload, as 8 comparações e a conclusão com as três respostas do passo 2, uma frase cada, com os números.

- [ ] **Passo 4: Sugestão de commit (o usuário faz)**

`docs: resultado do fine-tuning com pré-treino no RTR`

---

## Fora do escopo

- Busca de hiperparâmetros. Se fizer, precisa de validação aninhada dentro dos folds de treino (`splits.inner_logo_splits`), nunca olhando o prédio de teste.
- Rede neural treinada só nos nossos dados como candidata a versão. Aqui ela é só o controle.
- Misturar linhas do RTR durante o ajuste, com peso decrescente. É a outra leitura da proposta do Lucas, que fica para um segundo ciclo, se o pré-treino simples mostrar transferência.
- Salvar uma versão no registro.
