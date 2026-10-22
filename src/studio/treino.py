"""Treino pelo Studio: valida o pedido, avalia por LOGO, treina o final e registra no MLflow do Studio.

preparar() roda dentro da requisição (recusa rápida, com o motivo); executar() roda
na fila, fora dela.
"""

import json
import traceback
from dataclasses import dataclass, field

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from studio import aplicacoes, avaliacao, catalogo, colunas, predios, rastreio

SEMENTE = 42
MIN_PREDIOS = 2
# Padrões de build_models em src/ml/regression_benchmark.py, copiados em 2026-10-22 (sem importar).
MODELOS = {
  'RandomForest': (RandomForestRegressor, {'n_estimators': 600, 'min_samples_leaf': 2}),
  'ExtraTrees': (ExtraTreesRegressor, {'n_estimators': 600, 'min_samples_leaf': 2}),
  'HistGradientBoosting': (HistGradientBoostingRegressor,
                           {'learning_rate': 0.05, 'max_depth': 8, 'max_iter': 400, 'min_samples_leaf': 20}),
  'XGBoost': (XGBRegressor, {'n_estimators': 1000, 'learning_rate': 0.03, 'max_depth': 6, 'min_child_weight': 3,
                             'subsample': 0.8, 'colsample_bytree': 0.8, 'reg_alpha': 0.01, 'reg_lambda': 1.0}),
}
# Fixos por modelo: não aparecem no formulário.
FIXOS = {
  'RandomForest': {'n_jobs': -1, 'random_state': SEMENTE},
  'ExtraTrees': {'n_jobs': -1, 'random_state': SEMENTE},
  'HistGradientBoosting': {'random_state': SEMENTE},
  'XGBoost': {'objective': 'reg:squarederror', 'random_state': SEMENTE},
}


def hiper_efetivo(modelo: str, hiper: dict) -> dict:
  if modelo not in MODELOS:
    raise ValueError(f'modelo {modelo!r} desconhecido; esperado um de {list(MODELOS)}')
  padrao = MODELOS[modelo][1]
  desconhecidos = sorted(set(hiper or {}) - set(padrao))
  if desconhecidos:
    raise ValueError(f'hiperparâmetros desconhecidos para {modelo}: {desconhecidos}')
  return {**padrao, **(hiper or {})}


def montar(modelo: str, hiper: dict = None) -> Pipeline:
  efetivo = hiper_efetivo(modelo, hiper)
  classe = MODELOS[modelo][0]
  return Pipeline([('imputer', SimpleImputer(strategy='median')),
                   ('reg', classe(**efetivo, **FIXOS[modelo]))])


@dataclass
class Pedido:
  alvo: str
  datasets: list
  features: list
  modelo: str = 'RandomForest'
  hiper: dict = field(default_factory=dict)
  regras: dict = field(default_factory=lambda: dict(avaliacao.REGRAS_PADRAO))


@dataclass
class Preparado:
  pedido: Pedido
  df: pd.DataFrame
  removidas: dict
  fingerprints: dict
  contem_vazamento: bool


def carregar(ids, itens: list = None, registro: dict = None) -> pd.DataFrame:
  """Linhas dos datasets escolhidos, com `_ds` e o prédio de cada linha em avaliacao.COLUNA_PREDIO."""
  registro = registro if registro is not None else predios.atual()
  frames = []
  for item in catalogo.usaveis_por_id(ids, itens):
    frame = item['_frame'].copy()
    frame['_ds'] = item['id']
    try:
      frame[avaliacao.COLUNA_PREDIO] = predios.resolver(frame['local'], 'predio', registro).to_numpy()
    except ValueError as erro:
      raise ValueError(f"{item['id']}: {erro}") from None
    frames.append(frame)
  return pd.concat(frames, ignore_index=True, sort=False)


def tetos(df: pd.DataFrame, alvo: str, registro: dict) -> dict:
  saida = {}
  for predio in df[avaliacao.COLUNA_PREDIO].unique():
    teto = predios.teto_wan(predio, alvo, registro)
    if teto is not None:
      saida[predio] = teto
  return saida


def faltando(ids, features, itens: list = None) -> dict:
  """{dataset: [features ausentes]}; vazio quando todas existem em todos."""
  saida = {}
  for item in catalogo.usaveis_por_id(ids, itens):
    ausentes = [f for f in features if f not in item['_frame'].columns]
    if ausentes:
      saida[item['id']] = ausentes
  return saida


def matriz(df: pd.DataFrame, features: list) -> pd.DataFrame:
  return df[list(features)].apply(pd.to_numeric, errors='coerce')


def preparar(pedido: Pedido, itens: list = None) -> Preparado:
  """Valida tudo o que dá para validar antes da fila. ValueError com o motivo."""
  if pedido.alvo not in rastreio.ALVOS:
    raise ValueError(f'alvo {pedido.alvo!r} desconhecido; esperado um de {list(rastreio.ALVOS)}')
  if not pedido.datasets:
    raise ValueError('escolha pelo menos um dataset')
  if not pedido.features:
    raise ValueError('escolha pelo menos uma feature')
  alvos = [f for f in pedido.features if f in catalogo.TARGETS]
  if alvos:
    raise ValueError(f'alvo não pode ser feature: {alvos}')
  desconhecidas = sorted(set(pedido.regras) - set(avaliacao.REGRAS_PADRAO))
  if desconhecidas:
    raise ValueError(f'regras desconhecidas: {desconhecidas}')
  hiper_efetivo(pedido.modelo, pedido.hiper)
  itens = catalogo.descobertos() if itens is None else itens
  sobre = catalogo.sobreposicoes(pedido.datasets, itens)
  if sobre:
    raise ValueError('datasets sobrepostos (as mesmas amostras contariam duas vezes): ' + '; '.join(sobre))
  falta = faltando(pedido.datasets, pedido.features, itens)
  if falta:
    raise ValueError(f'features ausentes: {falta}')
  registro = predios.atual()
  regras = {**avaliacao.REGRAS_PADRAO, **pedido.regras}
  df = carregar(pedido.datasets, itens, registro)
  df, removidas = avaliacao.aplicar_regras(df, pedido.alvo, regras, tetos(df, pedido.alvo, registro))
  n = int(df[avaliacao.COLUNA_PREDIO].nunique())
  if n < MIN_PREDIOS:
    raise ValueError(f'só {n} prédio depois das regras: a avaliação deixa um prédio de fora por vez '
                     f'e precisa de pelo menos {MIN_PREDIOS}')
  cfg = colunas.carregar()
  fingerprints = {d['id']: d['fingerprint'] for d in catalogo.usaveis_por_id(pedido.datasets, itens)}
  normalizado = Pedido(pedido.alvo, list(pedido.datasets), list(pedido.features), pedido.modelo,
                       dict(pedido.hiper), regras)
  return Preparado(normalizado, df, removidas, fingerprints,
                   any(colunas.com_vazamento(f, cfg) for f in pedido.features))


def params(prep: Preparado) -> dict:
  p = prep.pedido
  saida = {'alvo': p.alvo, 'datasets': ','.join(p.datasets),
           'fingerprints': ','.join(f'{k}:{v}' for k, v in sorted(prep.fingerprints.items())),
           'features': ','.join(p.features), 'modelo': p.modelo}
  saida.update({f'hiper__{k}': v for k, v in hiper_efetivo(p.modelo, p.hiper).items()})
  saida.update({f'regra__{k}': v for k, v in p.regras.items()})
  saida.update({f'removidas__{k}': v for k, v in prep.removidas.items()})
  return saida


def registrar_artefatos(df: pd.DataFrame, alvo: str, pred, grupos, nome_previsoes: str) -> None:
  """por_predio.csv e as previsões linha a linha, no run ativo."""
  mlflow.log_text(avaliacao.tabela_por_predio(df[alvo], pred, grupos).to_csv(index=False), 'por_predio.csv')
  previsoes = pd.DataFrame({'dataset': df['_ds'], 'local': df['local'], 'predio': grupos,
                            'real': df[alvo], 'previsto': pred})
  mlflow.log_text(previsoes.to_csv(index=False), nome_previsoes)


def executar(prep: Preparado, progresso=None) -> dict:
  """Avalia por LOGO, treina o final, registra run + versão nova em studio-<alvo>."""
  progresso = progresso or (lambda texto: None)
  p = prep.pedido
  cli = rastreio.cliente()
  exp_id = rastreio.experimento_id(cli)
  nome = rastreio.nome_modelo(p.alvo)
  modelo = montar(p.modelo, p.hiper)
  X = matriz(prep.df, p.features)
  y = pd.to_numeric(prep.df[p.alvo])
  grupos = prep.df[avaliacao.COLUNA_PREDIO]
  tags = {'tipo': 'treino', 'alvo': p.alvo}
  if prep.contem_vazamento:
    tags['contem_vazamento'] = 'true'
  # Uma exceção dentro do `with` deixa o run como FAILED.
  with mlflow.start_run(experiment_id=exp_id) as run:
    mlflow.set_tags(tags)
    mlflow.log_params(params(prep))
    mlflow.log_text(json.dumps(p.features, ensure_ascii=False, indent=2), 'features.json')
    try:
      progresso('avaliando: um prédio fora por vez')
      pred = avaliacao.fora_do_fold(modelo, X, y, grupos)
      met = avaliacao.metricas(y, pred, grupos, p.alvo, aplicacoes.carregar())
      rastreio.registrar_metricas(met)
      registrar_artefatos(prep.df, p.alvo, pred, grupos, 'previsoes_fora_do_fold.csv')
      progresso('treinando o modelo final com todas as linhas')
      final = clone(modelo).fit(X, y)
      progresso('registrando a versão')
      info = mlflow.sklearn.log_model(final, name='modelo', signature=infer_signature(X, final.predict(X)),
                                      serialization_format='cloudpickle', registered_model_name=nome)
    except Exception:
      mlflow.log_text(traceback.format_exc(), 'erro.txt')
      raise
  versao = str(info.registered_model_version)
  return {'run_id': run.info.run_id, 'versao': versao,
          'link_run': rastreio.link_run(exp_id, run.info.run_id), 'link_versao': rastreio.link_versao(nome, versao),
          'metricas': {k: met[k] for k in ('mae', 'rmse', 'r2', 'linhas', 'predios')}}
