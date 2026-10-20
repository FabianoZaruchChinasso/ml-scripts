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
