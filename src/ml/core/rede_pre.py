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
