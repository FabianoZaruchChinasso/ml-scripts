"""Treina, avalia e grava uma versão do registro num run do MLflow (experimento "MLflow Wifi Pipeline").

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Datasets: DATASETS=a.zip,b.zip (nomes em
data/; padrão: o conjunto canônico, o mesmo do Studio). O run leva a avaliação completa
(core/completa.py), o pacote com os modelos finais e a receita de previsão (core/pacote.py) e a versão
do dado. A métrica principal é o erro das quatro previsões; a régua por cômodo e os "atende" vão como
métricas secundárias, com a versão de cada régua em tag. Não escreve em core/modelos.json nem toca nos
runs do Studio.
"""

import hashlib
import os
import sys

import mlflow

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import completa as core_completa
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core import pacote as core_pacote
from ml.core import pacote_mlflow as core_pacote_mlflow
from ml.core import registro_mlflow as core_registro_mlflow

EXPERIMENTO = 'MLflow Wifi Pipeline'
DN = 'speedtest_down_mbps'


def metricas_do_pipeline(avaliacao: dict) -> dict:
  """Intervalos de 90%, métricas por prédio e pinball do p90, por alvo.

  Completa registro_mlflow.parametros_e_metricas, que já traz pooled, mae, mae_log e cobertura_q90.
  """
  brutas = {}
  for alvo, p in core_registro_mlflow.ALVOS.items():
    bloco = avaliacao.get(alvo) or {}
    for chave in ('pooled', 'mae'):
      intervalo = (bloco.get('intervalos') or {}).get(chave)
      if intervalo:
        brutas[f'{p}_{chave}_lo90'], brutas[f'{p}_{chave}_hi90'] = intervalo[0], intervalo[1]
    for predio, valor in (bloco.get('por_local') or {}).items():
      brutas[f'{p}_r2_{predio}'] = valor
    for predio, valor in (bloco.get('mae_por_local') or {}).items():
      brutas[f'{p}_mae_{predio}'] = valor
    brutas[f'{p}_pinball_q90'] = ((bloco.get('quantis') or {}).get('pinball') or {}).get('q90')
  return {k: float(v) for k, v in brutas.items()
          if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v}


def _experimento() -> str:
  """Id do experimento. Ao criar, põe os artefatos ao lado do banco: o padrão do mlflow é ./mlruns da pasta atual."""
  exp = mlflow.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  uri = core_registro_mlflow.uri_rastreamento()
  local = None
  if uri.startswith('sqlite:///'):
    local = os.path.join(os.path.dirname(uri[len('sqlite:///'):]), 'mlruns', 'pipeline')
  return mlflow.create_experiment(EXPERIMENTO, artifact_location=local)


def registrar(nome: str, versao: dict, conjs: dict, avaliacao: dict, pacote, fingerprints: list) -> str:
  """Grava o run '<nome>-pipeline' e devolve o run_id.

  `versao`: features, denominador e cobertura da versão avaliada. Se gravar ou carregar o pacote
  falhar, o run termina FAILED e a exceção sobe.
  """
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  base = conjs[DN]
  params, metricas = core_registro_mlflow.parametros_e_metricas(nome, dict(versao, avaliacao=avaliacao))
  params.update({'fingerprints': ','.join(fingerprints), 'versao_tabela': core_features.versao_tabela(),
                 'versao_catalogo': core_features.CATALOGO_VERSAO,
                 'versao_pacote': pacote.receita['versao_pacote'],
                 'removidas_por_vazamento': ','.join(avaliacao.get('removidas_por_vazamento') or [])})
  metricas.update(metricas_do_pipeline(avaliacao))
  tags = {'modelo': nome, 'metrica_principal': 'erro_das_previsoes'}
  for chave in ('versao_comodo', 'versao_regua'):
    if params.get(chave):
      tags[chave] = str(params[chave])
  tags.update(core_registro_mlflow.tags_git())
  entradas = pacote.receita['entradas']
  dados = base.df[list(dict.fromkeys(entradas + list(core_pacote.PREFIXOS)))]
  digest = hashlib.sha256(','.join(fingerprints).encode()).hexdigest()[:8]
  comodo = avaliacao.get('comodo') or {}
  exemplo = base.df[entradas].head(5)
  with mlflow.start_run(experiment_id=_experimento(), run_name=f'{nome}-pipeline', tags=tags) as run:
    mlflow.log_params({k: v for k, v in params.items() if v is not None})
    mlflow.log_metrics(metricas)
    mlflow.log_input(mlflow.data.from_pandas(dados, name='qoe-wifi', digest=digest), context='treino')
    mlflow.log_dict(avaliacao, 'avaliacao.json')
    mlflow.log_dict({'posicoes': comodo.get('posicoes') or [], 'piso_posicoes': comodo.get('piso_posicoes') or []},
                    'posicoes.json')
    mlflow.log_dict(pacote.receita, 'receita.json')
    mlflow.log_dict(versao.get('cobertura') or {}, 'cobertura_tr069.json')
    core_pacote_mlflow.gravar(pacote, exemplo)
    mlflow.pyfunc.load_model(f'runs:/{run.info.run_id}/{core_pacote_mlflow.NOME}').predict(exemplo)
  return run.info.run_id


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f"MODELO={nome!r} não existe em core/modelos.json; "
                     f"versões disponíveis: {sorted(registro['versoes'])}")
  definicao = registro['versoes'][nome]
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
  base = conjs[DN]
  for aviso in base.avisos:
    print(f'aviso: {aviso}')
  denominador = definicao.get('denominador') or None
  print(f"Versão {nome}" + (' (ativa)' if nome == registro['ativo'] else '')
        + f": {len(definicao['features'])} features, datasets {base.datasets}")
  avaliacao = core_completa.avaliacao_completa(
    conjs.__getitem__, None, definicao['features'], denominador,
    progresso=lambda e: print(f"  etapa {e['passo'] + 1}/{e['passos']}: {e['etapa']}"),
    perfil_qoe=core_modelos.perfil_de(registro, nome))
  removidas = avaliacao['removidas_por_vazamento']
  if removidas:
    print(f'features com vazamento fora da conta: {removidas}')
  usadas = [f for f in definicao['features'] if f not in removidas]
  print('  treinando os modelos finais')
  pacote = core_pacote.treinar(conjs, usadas, denominador)
  versao = {'features': definicao['features'], 'denominador': denominador,
            'cobertura': core_features.cobertura_tr069(definicao['features'], base.tabela, base.catalogo)}
  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  run_id = registrar(nome, versao, conjs, avaliacao, pacote, [impressoes[i] for i in base.datasets])
  for alvo, p in core_registro_mlflow.ALVOS.items():
    bloco = avaliacao[alvo]
    print(f"{alvo}: R² {bloco['pooled']} (90%: {(bloco.get('intervalos') or {}).get('pooled')}), MAE {bloco['mae']}")
  print(f"secundárias: nota por cômodo {avaliacao['comodo']['nota']}, "
        f"atende completo {avaliacao['atende_completo']['media']}")
  print(f'run {run_id} em "{EXPERIMENTO}" ({core_registro_mlflow.uri_rastreamento()})')


if __name__ == '__main__':
  main()
