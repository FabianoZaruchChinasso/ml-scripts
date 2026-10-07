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
