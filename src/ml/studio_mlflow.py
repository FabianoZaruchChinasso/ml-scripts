"""Registra no MLflow a avaliação que o Studio guardou para cada versão do registro.

Versões: MODELO=<nome> limita a uma (padrão: todas de core/modelos.json). Não treina nada: lê
versoes[nome]['avaliacao'] e registra um run '<nome>-studio' no experimento 'MLflow Wifi Studio',
para ver no MLflow os mesmos números do Studio (nota por cômodo, jogo, "atende" e a
régua de cada alvo). Artefatos: avaliacao.json (a avaliação inteira) e posicoes.json (posições
do cômodo e do piso).
"""

import json
import os
import sys

import mlflow

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import modelos as core_modelos

ALVOS = {'speedtest_down_mbps': 'down', 'speedtest_up_mbps': 'up', 'latency_ms': 'lat', 'jitter_ms': 'jit'}


def _numero(valor):
  return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def parametros_e_metricas(nome: str, versao: dict, ativo: bool) -> tuple:
  """(parâmetros, métricas) de uma versão; métrica ausente na avaliação fica de fora."""
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  regua = next((av[a]['versao_regua'] for a in ALVOS if (av.get(a) or {}).get('versao_regua')), None)
  denominador = versao.get('denominador')
  params = {
    'modelo': nome, 'ativo': bool(ativo),
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


def registrar_versao(nome: str, versao: dict, ativo: bool) -> None:
  params, metricas = parametros_e_metricas(nome, versao, ativo)
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  with mlflow.start_run(run_name=f'{nome}-studio'):
    mlflow.log_params({k: v for k, v in params.items() if v is not None})
    mlflow.log_metrics(metricas)
    mlflow.log_dict(av, 'avaliacao.json')
    mlflow.log_dict({'posicoes': comodo.get('posicoes') or [], 'piso_posicoes': comodo.get('piso_posicoes') or []},
                    'posicoes.json')


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO')
  if nome and nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  nomes = [nome] if nome else list(registro['versoes'])
  mlflow.set_experiment('MLflow Wifi Studio')
  for n in nomes:
    registrar_versao(n, registro['versoes'][n], n == registro['ativo'])
    print(f'registrado: {n}-studio')


if __name__ == '__main__':
  main()
