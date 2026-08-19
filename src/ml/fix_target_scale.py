"""Converte alvos normalizados de volta para unidades físicas num CSV transformado.

O transform da residência dividiu três colunas-alvo pelo máximo da própria coluna;
o transform do coworking não dividiu nenhuma. Isso torna os dois prédios
incomparáveis: 0,5 significa 334 Mbps num e 284 no outro. Este script multiplica as
colunas normalizadas de volta pelos máximos encontrados no CSV bruto, deixando todos
os prédios com os alvos em Mbps / ms.

Idempotente: uma coluna que já está em unidade física é deixada intacta.
"""

import argparse
import math
import os
import shutil
import sys

import pandas as pd

TARGETS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']

# Uma coluna normalizada tem máximo exatamente 1.0; todo alvo físico deste projeto
# fica muito acima disso (o menor observado é ~292 Mbps).
NORMALISED_MAX = 1.5


def denormalise_targets(df: pd.DataFrame, raw_maxima: dict):
  """Devolve (df_corrigido, relatorio).

  Colunas ausentes são registradas no relatório (não silenciadas); colunas já em
  unidade física são preservadas, o que torna a operação segura de repetir.
  """
  corrected = df.copy()
  report = {}
  for column, maximum in raw_maxima.items():
    if column not in corrected.columns:
      report[column] = 'not found in dataframe'
      continue
    observed = corrected[column].max()
    if pd.isna(observed):
      report[column] = 'no data (all NaN)'
      continue
    if observed > NORMALISED_MAX:
      report[column] = 'already physical'
      continue
    corrected[column] = corrected[column] * maximum
    report[column] = f'multiplied by {maximum:.6f}'
  return corrected, report


def read_raw_maxima(raw_path: str) -> dict:
  """Máximos por alvo no CSV bruto — as constantes exatas usadas no normalize."""
  raw = pd.read_csv(raw_path, low_memory=False)
  maxima = {}
  for c in TARGETS:
    if c not in raw.columns:
      continue
    value = float(raw[c].max())
    if not math.isfinite(value) or value <= NORMALISED_MAX:
      raise ValueError(
        f'máximo bruto inválido para {c!r}: {value!r}. Esperado um valor finito '
        f'maior que {NORMALISED_MAX} (o corte usado para detectar colunas normalizadas).'
      )
    maxima[c] = value
  return maxima


def main():
  parser = argparse.ArgumentParser(
    description='Reescreve um -out.csv com os alvos em unidade física')
  parser.add_argument('--raw', required=True,
                      help='CSV bruto de onde os máximos originais são lidos')
  parser.add_argument('--out', required=True,
                      help='CSV transformado a corrigir (sobrescrito no lugar)')
  parser.add_argument('--reference', default=None,
                      help='CSV opcional já em unidade física, para verificar a correção')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='Mostra o que faria sem escrever')
  args = parser.parse_args()

  maxima = read_raw_maxima(args.raw)
  df = pd.read_csv(args.out, low_memory=False)
  fixed, report = denormalise_targets(df, maxima)

  targets_in_df = [c for c in TARGETS if c in df.columns]
  missing_from_raw = sorted(set(targets_in_df) - set(report.keys()))
  for column in missing_from_raw:
    report[column] = 'ausente do CSV bruto — nenhuma correção pôde ser verificada'

  print(f'{args.out}:')
  for column, action in sorted(report.items()):
    print(f'  {column:22} {action}')

  if args.reference is not None:
    ref = pd.read_csv(args.reference, low_memory=False)
    if len(ref) != len(fixed):
      print(f'  AVISO: referência tem {len(ref)} linhas e o alvo {len(fixed)}; '
            'verificação pulada')
    else:
      for column in report:
        if column not in ref.columns:
          continue
        both = fixed[column].notna() & ref[column].notna()
        worst = (fixed[column][both] - ref[column][both]).abs().max()
        status = 'OK' if worst < 1e-6 else 'DIVERGE'
        print(f'  verificação {column:22} maior_diferenca={worst:.3e} {status}')
  else:
    print('  AVISO: nenhuma verificação foi feita (rode com --reference para conferir a correção)')

  if args.dry_run:
    print('  (dry-run: nada foi escrito)')
    return

  backup_path = args.out + '.bak'
  shutil.copy2(args.out, backup_path)
  print(f'  backup: {backup_path}')

  fixed.to_csv(args.out, index=False)
  print(f'  escrito: {args.out}')


if __name__ == '__main__':
  main()
