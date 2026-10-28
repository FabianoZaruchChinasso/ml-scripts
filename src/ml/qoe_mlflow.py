"""Treina os classificadores de QoE de uma versão e registra no MLflow.

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Datasets: DATASETS=a.zip,b.zip
(padrão: o conjunto canônico, o mesmo do Studio). Um XGBoost monotônico (core/qoe.modelo_qoe)
por aplicação, com o rótulo do perfil da versão (core/modelos.perfil_de), treinado com todos os
prédios. A métrica registrada é a da régua de QoE (LOGO por prédio, core/qoe.avaliar).
Artefatos: um modelo por aplicação, contrato.json (core/producao.py), qoe.json (perfil,
limiares, fontes, restrições, versao_qoe) e cobertura_tr069.json.
"""

import os
import re
import sys
import unicodedata

import mlflow
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core import producao as core_producao
from ml.core import qoe as core_qoe

# Tipos que o skops não confia por padrão: o wrapper de core/qoe e o XGBoost.
TIPOS_CONFIAVEIS = ['numpy.dtype', 'ml.core.qoe.Balanceado', 'xgboost.core.Booster', 'xgboost.sklearn.XGBClassifier']


def _nome_artefato(aplicacao: str) -> str:
  """Nome ASCII do artefato; decompõe os acentos antes (vídeo -> video, não vdeo)."""
  ascii_ = unicodedata.normalize('NFKD', aplicacao.lower()).encode('ascii', 'ignore').decode()
  return 'qoe_' + re.sub(r'[^a-z0-9]+', '_', ascii_).strip('_')


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  perfil = core_modelos.perfil_de(registro, nome)
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_qoe.ALVOS}
  base = conjs[core_qoe.ALVOS[0]]
  vazadas = [c for c, k in base.classes.items() if k is not None and k.vazamento]
  pedidas = list(registro['versoes'][nome]['features'])
  avaliacao = core_qoe.avaliar(conjs, pedidas, vazadas, perfil)
  features = avaliacao['features']
  cobertura = core_features.cobertura_tr069(features, base.tabela, base.catalogo)
  piso = avaliacao['piso']['nota'] if avaliacao['piso'] else '-'
  print(f'Modelo {nome}, perfil {perfil}: {len(features)} features, datasets {base.datasets}')
  print(f"QoE por prédio {avaliacao['modelo']['nota']} (90%: {avaliacao['modelo']['intervalo']}), "
        f"RF {avaliacao['referencia']['nota']}, piso {piso}")

  df = core_qoe.conjunto_qoe(conjs)
  rot = core_qoe.rotulos(df, avaliacao['limiares'])
  X = core_features.matriz(df, features)
  mlflow.set_experiment('MLflow Wifi QoE')
  with mlflow.start_run(run_name=f'{nome}-qoe-{perfil}'):
    mlflow.log_params({'modelo_versao': nome, 'perfil_qoe': perfil, 'versao_qoe': core_qoe.VERSAO_QOE,
                       'datasets': ','.join(base.datasets), 'features': ','.join(features),
                       'cobertura_tr069': cobertura['nivel'],
                       'removidas_por_vazamento': ','.join(f for f in pedidas if f in vazadas)})
    for chave in ('modelo', 'referencia', 'piso'):
      resumo = avaliacao.get(chave)
      if resumo and resumo['nota'] is not None:
        mlflow.log_metric(f'qoe_{chave}_por_predio', resumo['nota'])
        if resumo['pooled'] is not None:
          mlflow.log_metric(f'qoe_{chave}_pooled', resumo['pooled'])
    if avaliacao['modelo']['intervalo']:
      mlflow.log_metric('qoe_modelo_lo90', avaliacao['modelo']['intervalo'][0])
      mlflow.log_metric('qoe_modelo_hi90', avaliacao['modelo']['intervalo'][1])
    for aplicacao, y in rot.items():
      y = np.asarray(y, dtype=int)
      if y.min() == y.max():
        print(f'aviso: {aplicacao} tem uma classe só no conjunto; modelo não treinado')
        continue
      modelo = core_qoe.modelo_qoe(list(X.columns)).fit(X, y)
      mlflow.sklearn.log_model(sk_model=modelo, name=_nome_artefato(aplicacao), serialization_format='skops',
                               skops_trusted_types=TIPOS_CONFIAVEIS)
      print(f'modelo registrado: {_nome_artefato(aplicacao)}')
    mlflow.log_dict(core_producao.contrato(df, features), 'contrato.json')
    mlflow.log_dict(cobertura, 'cobertura_tr069.json')
    mlflow.log_dict({'perfil': perfil, 'versao_qoe': core_qoe.VERSAO_QOE, 'limiares': avaliacao['limiares'],
                     'fontes': avaliacao['fontes'], 'restricoes': avaliacao['restricoes'],
                     'uso': 'atende[aplicação] = modelo_<aplicação>.predict(producao.preparar_entrada(linhas, contrato)[0]) == 1'},
                    'qoe.json')


if __name__ == '__main__':
  main()
