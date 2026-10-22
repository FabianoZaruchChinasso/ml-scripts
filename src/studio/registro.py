"""Versões registradas no MLflow do Studio: @ativo, comparação, promoção e reavaliação."""

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.exceptions import MlflowException

from studio import aplicacoes, avaliacao, catalogo, predios, rastreio, treino


def _versao(cli, nome: str, versao):
  try:
    return cli.get_model_version(nome, str(versao))
  except MlflowException:
    raise KeyError(f'versão {versao} de {nome} não existe') from None


def _lista(texto: str) -> list:
  return [x for x in (texto or '').split(',') if x]


def resumo(cli, nome: str, mv) -> dict:
  run = cli.get_run(mv.run_id)
  m, params, tags = run.data.metrics, run.data.params, run.data.tags
  return {'versao': str(mv.version), 'run_id': mv.run_id, 'modelo': params.get('modelo'),
          'features': _lista(params.get('features')), 'datasets': _lista(params.get('datasets')),
          'mae': m.get('mae'), 'rmse': m.get('rmse'), 'r2': m.get('r2'),
          'predios': int(m['predios']) if 'predios' in m else None,
          'linhas': int(m['linhas']) if 'linhas' in m else None,
          'contem_vazamento': tags.get('contem_vazamento') == 'true',
          'link': rastreio.link_versao(nome, mv.version),
          'link_run': rastreio.link_run(run.info.experiment_id, mv.run_id)}


def ativo(alvo: str):
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  try:
    mv = cli.get_model_version_by_alias(nome, rastreio.ALIAS_ATIVO)
  except MlflowException:
    return None
  return resumo(cli, nome, mv)


def versoes(alvo: str) -> list:
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  try:
    mvs = cli.search_model_versions(f"name='{nome}'")
  except MlflowException:
    return []
  return [resumo(cli, nome, mv) for mv in sorted(mvs, key=lambda v: int(v.version), reverse=True)]


def comparar(alvo: str, versao) -> dict:
  """Candidata ao lado da @ativo, com avisos que não bloqueiam a promoção."""
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  candidata = resumo(cli, nome, _versao(cli, nome, versao))
  atual = ativo(alvo)
  avisos = []
  if candidata['contem_vazamento']:
    avisos.append('o treino desta versão usou colunas com vazamento (contadores da janela do speedtest): '
                  'o erro medido é otimista')
  if atual and atual['versao'] == candidata['versao']:
    avisos.append('esta versão já é a @ativo')
  elif atual and (candidata['predios'] or 0) < (atual['predios'] or 0):
    avisos.append(f"avaliada em {candidata['predios']} prédios; a @ativo foi avaliada em {atual['predios']}")
  return {'candidata': candidata, 'ativo': atual, 'avisos': avisos}


def promover(alvo: str, versao) -> dict:
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  _versao(cli, nome, versao)
  cli.set_registered_model_alias(nome, rastreio.ALIAS_ATIVO, str(versao))
  return ativo(alvo)


def preparar_reavaliacao(alvo: str, versao, ids, itens: list = None) -> dict:
  """Valida antes da fila: versão existe, features presentes, sem sobreposição; aplica as regras da versão."""
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  mv = _versao(cli, nome, versao)
  params = cli.get_run(mv.run_id).data.params
  features = _lista(params.get('features'))
  regras = {k[len('regra__'):]: v == 'True' for k, v in params.items() if k.startswith('regra__')}
  if not ids:
    raise ValueError('escolha pelo menos um dataset')
  itens = catalogo.descobertos() if itens is None else itens
  sobre = catalogo.sobreposicoes(ids, itens)
  if sobre:
    raise ValueError('datasets sobrepostos (as mesmas amostras contariam duas vezes): ' + '; '.join(sobre))
  falta = treino.faltando(ids, features, itens)
  if falta:
    raise ValueError(f'a versão {versao} usa features ausentes nestes datasets: {falta}')
  reg = predios.atual()
  df = treino.carregar(ids, itens, reg)
  df, removidas = avaliacao.aplicar_regras(df, alvo, regras, treino.tetos(df, alvo, reg))
  if df.empty:
    raise ValueError('nenhuma linha sobrou depois das regras da versão')
  de_treino = {fp.split(':', 1)[1] for fp in _lista(params.get('fingerprints')) if ':' in fp}
  escolhidos = catalogo.usaveis_por_id(ids, itens)
  avisos = [f"{d['id']} estava no treino desta versão: a medida é otimista"
            for d in escolhidos if d['fingerprint'] in de_treino]
  return {'alvo': alvo, 'nome': nome, 'versao': str(versao), 'run_treino': mv.run_id, 'features': features,
          'regras': regras, 'ids': list(ids), 'fingerprints': {d['id']: d['fingerprint'] for d in escolhidos},
          'df': df, 'removidas': removidas, 'avisos': avisos}


def executar_reavaliacao(prep: dict, progresso=None) -> dict:
  """Prevê com a versão registrada, sem retreinar, e grava um run tipo=reavaliacao."""
  progresso = progresso or (lambda texto: None)
  cli = rastreio.cliente()
  exp_id = rastreio.experimento_id(cli)
  progresso('carregando o modelo registrado')
  modelo = mlflow.sklearn.load_model(f"models:/{prep['nome']}/{prep['versao']}")
  df, alvo = prep['df'], prep['alvo']
  X = treino.matriz(df, prep['features'])
  y = pd.to_numeric(df[alvo])
  grupos = df[avaliacao.COLUNA_PREDIO]
  progresso('prevendo sem retreinar')
  pred = modelo.predict(X)
  met = avaliacao.metricas(y, pred, grupos, alvo, aplicacoes.carregar())
  with mlflow.start_run(experiment_id=exp_id) as run:
    mlflow.set_tags({'tipo': 'reavaliacao', 'alvo': alvo, 'modelo_versao': f"{prep['nome']}/{prep['versao']}",
                     'run_treino': prep['run_treino']})
    mlflow.log_params({'datasets': ','.join(prep['ids']),
                       'fingerprints': ','.join(f'{k}:{v}' for k, v in sorted(prep['fingerprints'].items())),
                       **{f'regra__{k}': v for k, v in prep['regras'].items()},
                       **{f'removidas__{k}': v for k, v in prep['removidas'].items()}})
    rastreio.registrar_metricas(met)
    treino.registrar_artefatos(df, alvo, pred, grupos, 'previsoes.csv')
    if prep['avisos']:
      mlflow.log_text('\n'.join(prep['avisos']) + '\n', 'avisos.txt')
  return {'run_id': run.info.run_id, 'link_run': rastreio.link_run(exp_id, run.info.run_id),
          'avisos': prep['avisos'], 'metricas': {k: met[k] for k in ('mae', 'rmse', 'r2', 'linhas', 'predios')}}
