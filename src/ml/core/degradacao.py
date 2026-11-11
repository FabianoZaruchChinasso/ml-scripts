"""Degradação da versão ativa: o erro do pacote implantado nas linhas que ele nunca viu.

Quando chega dado novo, o pacote da ativa (treinado só com os datasets dela) prevê as linhas dos datasets
novos, como faria em produção. O erro medido é comparado com o esperado, a validação cruzada gravada no run
da ativa: MAE de download e upload, pinball do p90 de latência e jitter. "degradou" quando o intervalo de 90%
do erro novo fica todo acima do esperado, ou quando a cobertura do p90 nas linhas novas sai da faixa.

O esperado vem de LOGO (prédios que o modelo não viu): para dado novo de um prédio que a ativa já viu, é uma
referência conservadora. Download e upload são cortados no teto de WAN do prédio, como na avaliação (o pacote
não corta). Não decide a promoção: vai para o relatório do portão.
"""

import numpy as np

from ml.core import avaliacao as core_avaliacao
from ml.core import pacote as core_pacote
from ml.core import quantis as core_quantis
from ml.core.sites import teto_wan

SAIDA = {'speedtest_down_mbps': 'download_mbps', 'speedtest_up_mbps': 'upload_mbps',
         'latency_ms': 'latency_ms_p90', 'jitter_ms': 'jitter_ms_p90'}
ESPERADO = {'speedtest_down_mbps': 'down_mae', 'speedtest_up_mbps': 'up_mae',
            'latency_ms': 'lat_pinball_q90', 'jitter_ms': 'jit_pinball_q90'}


def _erro(alvo: str, y: np.ndarray, previsto: np.ndarray) -> np.ndarray:
  """Erro por linha: absoluto na vazão, pinball do p90 em latência e jitter."""
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    return np.abs(y - previsto)
  e = y - previsto
  return np.maximum(0.9 * e, -0.1 * e)


def medir(pacote, conjs: dict, ids_antigos, esperado: dict) -> dict:
  """{alvo: bloco} com o erro do pacote nas linhas de datasets fora de `ids_antigos`.

  `esperado`: métricas do run da ativa (nomes em ESPERADO); a que faltar não entra na comparação. Alvo sem
  linhas novas fica de fora.
  """
  antigos = list(ids_antigos)
  saida = {}
  for alvo, coluna in SAIDA.items():
    df = conjs[alvo].df
    novas = df[~df['_ds'].isin(antigos) & df[alvo].notna()]
    if novas.empty:
      continue
    previsto = core_pacote.prever(pacote, novas)[0][coluna].to_numpy(dtype=float)
    y = novas[alvo].to_numpy(dtype=float)
    if alvo in core_avaliacao.ALVOS_COM_TETO:
      tetos = np.array([teto_wan(s, alvo) or np.inf for s in novas['_site']], dtype=float)
      previsto = np.minimum(previsto, tetos)
    erro = _erro(alvo, y, previsto)
    amostras = core_avaliacao.reamostras(novas['_pos'], novas['_site'])
    intervalo = core_avaliacao._intervalo([erro[i].mean() for i in amostras])
    referencia = esperado.get(ESPERADO[alvo])
    bloco = {'n': int(len(novas)), 'datasets': sorted(novas['_ds'].unique()), 'metrica': ESPERADO[alvo],
             'erro': round(float(erro.mean()), 4), 'intervalo': intervalo,
             'esperado': None if referencia is None else round(float(referencia), 4)}
    motivos = []
    if bloco['esperado'] is not None and intervalo is not None and intervalo[0] > bloco['esperado']:
      motivos.append(f"erro {bloco['erro']} (90%: {intervalo[0]} a {intervalo[1]}) acima do esperado "
                     f"{bloco['esperado']}")
    if alvo in core_quantis.ALVOS_QUANTILICOS:
      bloco['cobertura'] = round(core_quantis.cobertura(y, previsto), 4)
      lo, hi = core_quantis.FAIXA_COBERTURA
      if not lo <= bloco['cobertura'] <= hi:
        motivos.append(f"cobertura do p90 {bloco['cobertura']} fora da faixa de {lo} a {hi}")
    bloco['resultado'] = 'degradou' if motivos else 'estavel'
    bloco['motivo'] = '; '.join(motivos) or 'erro dentro do esperado'
    saida[alvo] = bloco
  return saida


def degradou(blocos: dict) -> bool:
  return any(b['resultado'] == 'degradou' for b in blocos.values())
