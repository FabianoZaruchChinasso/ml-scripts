"""Recupera à mão o registro do Studio no MLflow (experimento "MLflow Wifi Studio").

O Studio já registra sozinho ao salvar, reavaliar e ativar (core/registro_mlflow.py). Este script
serve quando esse registro falhou (o Studio mostra o aviso) ou para registrar todas as versões de uma
vez. MODELO=<nome> limita a uma versão (padrão: todas de core/modelos.json). Não treina nada: cria um
run '<nome>-studio' com evento=script a partir da avaliação guardada e, no fim, marca a versão ativa.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import modelos as core_modelos
from ml.core import registro_mlflow


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO')
  if nome and nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  nomes = [nome] if nome else list(registro['versoes'])
  ativa = registro['ativo']
  for n in nomes:
    registro_mlflow.registrar_avaliacao(n, registro['versoes'][n], 'script', ativo=n == ativa)
    print(f'registrado: {n}-studio')
  print(f'ativa: {ativa} ({registro_mlflow.marcar_ativo(ativa)} runs marcados)')


if __name__ == '__main__':
  main()
