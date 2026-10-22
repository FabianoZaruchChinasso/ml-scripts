#!/usr/bin/env python3
"""Sobe o QoE Studio novo e o MLflow do Studio em localhost.

  ./venv/bin/python src/studio/run.py [--port 8100] [--mlflow-port 5100]
"""

import argparse
import os
import sys

# Rodado como script, sys.path[0] é src/studio: troca por src para `import studio` funcionar.
sys.path[0] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def main():
  parser = argparse.ArgumentParser(description='QoE Studio (novo)')
  parser.add_argument('--port', type=int, default=8100)
  parser.add_argument('--mlflow-port', type=int, default=5100)
  args = parser.parse_args()

  # Antes de importar o mlflow: sem servidor, falhar rápido em vez de ~2 min de novas tentativas.
  os.environ.setdefault('MLFLOW_HTTP_REQUEST_MAX_RETRIES', '0')
  os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT', '120')

  from studio import caminhos, mlflow_servidor, portas
  for porta in (args.port, args.mlflow_port):
    if not portas.livre(porta):
      raise SystemExit(f'porta {porta} ocupada: feche o que está nela ou escolha outra (--port, --mlflow-port)')
  caminhos.MLFLOW_PORTA = args.mlflow_port
  caminhos.MLFLOW_URI = caminhos.MLFLOW_UI = f'http://127.0.0.1:{args.mlflow_port}'
  os.makedirs(caminhos.ESTADO_DIR, exist_ok=True)

  print('Subindo o MLflow do Studio (.studio/mlflow.db)...')
  try:
    mlflow_servidor.iniciar(args.mlflow_port)
  except RuntimeError as erro:
    raise SystemExit(str(erro))
  try:
    import uvicorn
    from studio.api import app
    print(f'QoE Studio  ->  http://127.0.0.1:{args.port}')
    print(f'MLflow      ->  {caminhos.MLFLOW_UI}')
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
  finally:
    mlflow_servidor.parar()


if __name__ == '__main__':
  main()
