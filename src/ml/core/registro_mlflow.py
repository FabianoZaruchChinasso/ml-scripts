"""Registro da avaliação do Studio no MLflow (experimento "MLflow Wifi Studio").

Chamado pelo Studio ao salvar e reavaliar uma versão, e por src/ml/studio_mlflow.py para
recuperar o registro à mão. Não treina nada: lê a avaliação que o Studio guardou em
core/modelos.json. Cada avaliação é um run '<nome>-studio'; reavaliar não apaga o run anterior,
só tira dele a tag atual=sim.

Usa MlflowClient direto (sem mlflow.start_run/set_experiment, que guardam estado global por
processo e por thread; os jobs do Studio rodam em threads). O mlflow é importado dentro das
funções: importar o Studio não fica mais lento e, com o pacote quebrado, só o registro falha.
"""

import functools
import json
import os
import subprocess
import threading
import time
from typing import Optional

EXPERIMENTO = 'MLflow Wifi Studio'
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
EVENTOS = ('salvar', 'reavaliar', 'script')
ALVOS = {'speedtest_down_mbps': 'down', 'speedtest_up_mbps': 'up', 'latency_ms': 'lat', 'jitter_ms': 'jit'}

# registrar_avaliacao lê os runs anteriores e só depois cria o novo: duas chamadas ao mesmo tempo para a
# mesma versão deixariam os dois runs com atual=sim. A trava vale para o processo (as threads do Studio);
# outro processo ao mesmo tempo (o script junto com o Studio) não é coberto: rodar o script de novo conserta.
_trava = threading.Lock()


def _exclusivo(funcao):
  @functools.wraps(funcao)
  def envolta(*args, **kwargs):
    with _trava:
      return funcao(*args, **kwargs)
  return envolta


def uri_rastreamento() -> str:
  """MLFLOW_TRACKING_URI, se definida; senão o mlflow.db da raiz do repositório, com caminho absoluto
  (o padrão do mlflow é relativo à pasta atual, e o Studio pode ser iniciado de qualquer pasta)."""
  return os.environ.get('MLFLOW_TRACKING_URI') or 'sqlite:///' + os.path.join(RAIZ, 'mlflow.db')


def _numero(valor):
  return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def parametros_e_metricas(nome: str, versao: dict) -> tuple:
  """(parâmetros, métricas) de uma versão; métrica ausente na avaliação fica de fora."""
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  regua = next((av[a]['versao_regua'] for a in ALVOS if (av.get(a) or {}).get('versao_regua')), None)
  denominador = versao.get('denominador')
  params = {
    'modelo': nome,
    'features': ','.join(versao.get('features') or []), 'n_features': len(versao.get('features') or []),
    'denominador': json.dumps(denominador, ensure_ascii=False, sort_keys=True) if denominador else 'nenhum',
    'datasets': ','.join(comodo.get('datasets') or []), 'ambiente': comodo.get('ambiente'),
    'perfil': av.get('perfil'), 'cobertura_tr069': (versao.get('cobertura') or {}).get('nivel'),
    'versao_comodo': comodo.get('versao_comodo'), 'versao_regua': regua,
  }
  jogo = comodo.get('jogo') or {}
  brutas = {
    'comodo_nota': comodo.get('nota'), 'comodo_piso': (comodo.get('piso') or {}).get('nota'),
    'comodo_contra_piso': (comodo.get('contra_piso') or {}).get('diferenca'), 'comodo_graves': comodo.get('graves'),
    'jogo_nota': jogo.get('nota'), 'jogo_piso': (jogo.get('piso') or {}).get('nota'),
  }
  for prefixo, bloco in (('comodo', comodo), ('jogo', jogo)):
    intervalo = bloco.get('intervalo')
    if intervalo:
      brutas[f'{prefixo}_lo90'], brutas[f'{prefixo}_hi90'] = intervalo[0], intervalo[1]
  for chave in ('atende_completo', 'atende_throughput', 'atende_ajustado'):
    brutas[chave] = (av.get(chave) or {}).get('media')
  for alvo, p in ALVOS.items():
    bloco = av.get(alvo) or {}
    brutas[f'{p}_pooled'], brutas[f'{p}_mae'], brutas[f'{p}_mae_log'] = bloco.get('pooled'), bloco.get('mae'), bloco.get('mae_log')
    if p in ('lat', 'jit'):
      brutas[f'{p}_cobertura_q90'] = ((bloco.get('quantis') or {}).get('cobertura') or {}).get('q90')
  metricas = {k: v for k, v in brutas.items() if _numero(v) is not None}
  return params, metricas


def cliente():
  from mlflow import MlflowClient
  return MlflowClient(tracking_uri=uri_rastreamento())


def _local_artefatos() -> Optional[str]:
  """Pasta dos artefatos de um experimento novo: ao lado do banco. Sem isso o mlflow usa ./mlruns
  relativo à pasta atual, e um banco temporário gravaria artefatos no mlruns/ da raiz."""
  uri = uri_rastreamento()
  if uri.startswith('sqlite:///'):
    return os.path.join(os.path.dirname(uri[len('sqlite:///'):]), 'mlruns', 'studio')
  return None


def _experimento(cli) -> str:
  exp = cli.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  return cli.create_experiment(EXPERIMENTO, artifact_location=_local_artefatos())


def _runs(cli, exp_id: str) -> list:
  runs, token = [], None
  while True:
    pagina = cli.search_runs([exp_id], max_results=1000, page_token=token)
    runs.extend(pagina)
    token = pagina.token
    if not token:
      return runs


def _versao_do_run(run) -> Optional[str]:
  """Tag 'modelo'; os runs antigos (gravados antes de 2026-11-09) só têm o parâmetro 'modelo'."""
  return run.data.tags.get('modelo') or run.data.params.get('modelo')


def _tags_git() -> dict:
  """Commit do HEAD e se a árvore (arquivos rastreados) tinha mudanças. Logo depois de salvar, é sempre
  'suja': a versão nova só existe no modelos.json ainda não commitado, então o commit sozinho não
  reproduz o run. Sem git, ou com erro do git, não há tags."""
  try:
    commit = subprocess.run(['git', '-C', RAIZ, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                            timeout=5, check=True).stdout.strip()
    mudancas = subprocess.run(['git', '-C', RAIZ, 'status', '--porcelain', '--untracked-files=no'],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
  except (OSError, subprocess.SubprocessError):
    return {}
  if not commit:
    return {}
  return {'mlflow.source.git.commit': commit, 'git_arvore': 'suja' if mudancas else 'limpa'}


def tags_git() -> dict:
  """As tags do git de um run (commit e git_arvore), para os outros registros no MLflow."""
  return _tags_git()


@_exclusivo
def registrar_avaliacao(nome: str, versao: dict, evento: str) -> str:
  """Cria o run '<nome>-studio' da avaliação guardada em `versao` e devolve o run_id.

  Tags: modelo, evento, atual=sim, versao_comodo (se houver), o commit do git e git_arvore (limpa/suja).
  Depois de gravar, os runs anteriores da mesma versão ficam com atual=nao. Se algo falhar no
  meio, o run fica FAILED com atual=nao, os anteriores não mudam e a exceção sobe.
  """
  if evento not in EVENTOS:
    raise ValueError(f'evento {evento!r} inválido; use um de {EVENTOS}')
  from mlflow.entities import Metric, Param
  cli = cliente()
  exp_id = _experimento(cli)
  params, metricas = parametros_e_metricas(nome, versao)
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  tags = {'modelo': nome, 'evento': evento, 'atual': 'sim'}
  if comodo.get('versao_comodo'):
    tags['versao_comodo'] = str(comodo['versao_comodo'])
  tags.update(_tags_git())
  anteriores = [r.info.run_id for r in _runs(cli, exp_id) if _versao_do_run(r) == nome]
  rid = cli.create_run(exp_id, run_name=f'{nome}-studio', tags=tags).info.run_id
  try:
    agora = int(time.time() * 1000)
    cli.log_batch(rid, metrics=[Metric(k, float(v), agora, 0) for k, v in metricas.items()],
                  params=[Param(k, str(v)) for k, v in params.items() if v is not None])
    cli.log_dict(rid, av, 'avaliacao.json')
    cli.log_dict(rid, {'posicoes': comodo.get('posicoes') or [], 'piso_posicoes': comodo.get('piso_posicoes') or []},
                 'posicoes.json')
  except Exception:
    cli.set_tag(rid, 'atual', 'nao')
    cli.set_terminated(rid, 'FAILED')
    raise
  cli.set_terminated(rid, 'FINISHED')
  for antigo in anteriores:
    cli.set_tag(antigo, 'atual', 'nao')
  return rid
