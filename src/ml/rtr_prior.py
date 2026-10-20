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
