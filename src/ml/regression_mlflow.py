"""Treina uma versão do registro e registra no MLflow, medida pela régua única.

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Alvo: ALVO= (padrão:
download). Datasets: DATASETS=a.zip,b.zip (nomes em data/; padrão: o conjunto
canônico, o mesmo do Studio). Cada configuração de árvore é avaliada deixando um
prédio de fora por vez, e o modelo final é treinado com todas as linhas fora do
teto de WAN.
"""

import os
import sys

import mlflow
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.data import validate_columns

ALVO = os.environ.get('ALVO', 'speedtest_down_mbps')

CONFIGS = [
  {'model_type': 'RandomForest', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'RandomForest', 'n_estimators': 200, 'max_depth': 20},
  {'model_type': 'ExtraTreesRegressor', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'ExtraTreesRegressor', 'n_estimators': 200, 'max_depth': 20},
  {'model_type': 'GradientBoostingRegressor', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'GradientBoostingRegressor', 'n_estimators': 200, 'max_depth': 20},
]
CLASSES = {'RandomForest': RandomForestRegressor, 'ExtraTreesRegressor': ExtraTreesRegressor,
           'GradientBoostingRegressor': GradientBoostingRegressor}


def montar(config: dict) -> Pipeline:
  regressor = CLASSES[config['model_type']](n_estimators=config['n_estimators'],
                                            max_depth=config['max_depth'], random_state=42)
  return Pipeline([('imputer', SimpleImputer(strategy='median')), ('reg', regressor)])


def registrar_metricas(resumo: dict) -> None:
  for chave in ('pooled', 'mae', 'mae_log', 'media'):
    if resumo.get(chave) is not None:
      mlflow.log_metric(chave, resumo[chave])
  for chave, intervalo in (resumo.get('intervalos') or {}).items():
    if intervalo:
      mlflow.log_metric(f'{chave}_lo90', intervalo[0])
      mlflow.log_metric(f'{chave}_hi90', intervalo[1])
  for site, valor in resumo['por_local'].items():
    mlflow.log_metric(f'r2_{site}', valor)
  for site, valor in resumo['mae_por_local'].items():
    mlflow.log_metric(f'mae_{site}', valor)


def main():
  registro = core_modelos.carregar()
  nome_modelo = os.environ.get('MODELO') or registro['ativo']
  if nome_modelo not in registro['versoes']:
    raise SystemExit(
      f"MODELO={nome_modelo!r} não existe em core/modelos.json; "
      f"versões disponíveis: {sorted(registro['versoes'])}")

  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conj = core_carga.carregar(ALVO, ids=ids)
  for aviso in conj.avisos:
    print(f'aviso: {aviso}')
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  pedidas = list(registro['versoes'][nome_modelo]['features'])
  removidas = [f for f in pedidas if f in vazadas]
  features = [f for f in pedidas if f not in vazadas]
  if removidas:
    print(f'features com vazamento fora da conta: {removidas}')
  validate_columns(conj.df, features, 'feature')
  print(f"Modelo: {nome_modelo}" + (' (ativo)' if nome_modelo == registro['ativo'] else '')
        + f" — {len(features)} features, alvo {ALVO}, datasets {conj.datasets}")

  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  y_final = conj.df.loc[treino, ALVO].astype(float)

  mlflow.set_experiment('MLflow Wifi Regressions')
  for config in CONFIGS:
    with mlflow.start_run(run_name=f"{nome_modelo}-{config['model_type']}-{config['max_depth']}"):
      mlflow.log_params({
        'modelo_versao': nome_modelo, 'alvo': ALVO,
        'datasets': ','.join(conj.datasets),
        'fingerprints': ','.join(impressoes[i] for i in conj.datasets),
        'versao_tabela': core_features.versao_tabela(),
        'versao_catalogo': core_features.CATALOGO_VERSAO,
        'versao_regua': core_avaliacao.VERSAO_REGUA,
        'features': ','.join(features),
        'removidas_por_vazamento': ','.join(removidas),
        **config,
      })
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config))
      resumo = core_avaliacao.resumir(prev, len(features))
      registrar_metricas(resumo)
      final = montar(config).fit(X_final, y_final)
      # O imputer guarda um numpy.dtype, que o skops não confia por padrão.
      mlflow.sklearn.log_model(sk_model=final, name=config['model_type'], serialization_format='skops',
                               skops_trusted_types=['numpy.dtype'])
      print('-' * 61)
      print(f"{config['model_type']} {config}: R² pooled {resumo['pooled']} "
            f"(90%: {resumo['intervalos'].get('pooled')}), MAE {resumo['mae']}, MAE log {resumo['mae_log']}")
      print(f"  por prédio: {resumo['por_local']}")


if __name__ == '__main__':
  main()
