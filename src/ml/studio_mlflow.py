"""Recupera à mão o registro do Studio no MLflow (experimento "MLflow Wifi Studio").

O Studio já registra sozinho ao salvar e reavaliar (core/registro_mlflow.py). Este script
serve quando esse registro falhou (o Studio mostra o aviso) ou para registrar todas as versões de uma
vez. MODELO=<nome> limita a uma versão (padrão: todas de core/modelos.json). Não treina nada: cria um
run '<nome>-studio' com evento=script a partir da avaliação guardada. A versão ativa não é marcada aqui: é o alias 'ativo'
do Model Registry (core/registry_mlflow.py).
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
  for n in nomes:
    registro_mlflow.registrar_avaliacao(n, registro['versoes'][n], 'script')
    print(f'registrado: {n}-studio')


if __name__ == '__main__':
  main()
