#!/usr/bin/env python3
"""Sobe o QoE Studio em localhost.

  python3 src/ml/studio.py [--port 8100]
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))


def main():
  parser = argparse.ArgumentParser(description='QoE Studio — visualizacao local de QoE')
  parser.add_argument('--port', type=int, default=8100)
  parser.add_argument('--host', default='127.0.0.1')
  args = parser.parse_args()

  import uvicorn
  from ml.studio.api import app
  print(f'QoE Studio  ->  http://{args.host}:{args.port}')
  uvicorn.run(app, host=args.host, port=args.port, log_level='warning')


if __name__ == '__main__':
  main()
