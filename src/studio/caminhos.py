"""Onde o Studio lê e grava.

Os outros módulos leem estes nomes na hora da chamada (`caminhos.DATA_DIR`), nunca
como valor padrão de argumento: assim os testes trocam tudo por pastas temporárias
com mock.patch.multiple.
"""

import os

PACOTE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(PACOTE, '..', '..'))

# Só leitura. É a pasta que o benchmark varre inteira (ml.core.carga.discover):
# qualquer arquivo gravado aqui mudaria o conjunto canônico dele.
DATA_DIR = os.path.join(REPO, 'data')

CONFIG_DIR = os.path.join(PACOTE, 'config')
PREDIOS_PATH = os.path.join(CONFIG_DIR, 'predios.json')
APLICACOES_PATH = os.path.join(CONFIG_DIR, 'aplicacoes.json')
COLUNAS_PATH = os.path.join(CONFIG_DIR, 'colunas.json')

# Plantas: o benchmark não usa docs/planta/.
PLANTA_DIR = os.path.join(REPO, 'docs', 'planta')

# Estado local, fora do git.
ESTADO_DIR = os.path.join(REPO, '.studio')
UPLOADS_DIR = os.path.join(ESTADO_DIR, 'uploads')
CONJUNTO_PATH = os.path.join(ESTADO_DIR, 'conjunto.json')


# MLflow do Studio. Nunca o mlflow.db/mlruns da raiz, que são do Fabiano.
MLFLOW_PORTA = 5100
MLFLOW_URI = f'http://127.0.0.1:{MLFLOW_PORTA}'
MLFLOW_UI = MLFLOW_URI
MLFLOW_DB = os.path.join(ESTADO_DIR, 'mlflow.db')
ARTEFATOS_DIR = os.path.join(ESTADO_DIR, 'artefatos')
# Só nos testes (sqlite sem servidor). Com o servidor, ele decide (mlflow-artifacts:/).
ARTEFATOS_URI = None
