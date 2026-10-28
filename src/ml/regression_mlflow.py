"""Treina uma versão do registro e registra no MLflow, medida pela régua única.

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Alvo: ALVO= (padrão:
download). Datasets: DATASETS=a.zip,b.zip (nomes em data/; padrão: o conjunto
canônico, o mesmo do Studio). Cada configuração de árvore é avaliada deixando um
prédio de fora por vez, e o modelo final é treinado com todas as linhas fora do
teto de WAN. Para ALVO=latency_ms ou jitter_ms, treina os dois modelos quantílicos
(p50 e p90) em vez da varredura de árvores, e registra em conformal.json a correção conformal do
p90 (em escala log) que a produção soma à previsão do modelo antes de voltar para ms.
Se a versão tiver denominador para o ALVO (core/modelos.json), o modelo aprende a eficiência
(alvo ÷ coluna) e eficiencia.json diz como voltar para Mbps.
Com denominador condicional ({"coluna", "radio"}), registra dois modelos finais por configuração (<modelo>_eficiencia e <modelo>_absoluto).
Todo run grava contrato.json (core/producao.py: as colunas exatas que o modelo final viu). Download
e upload gravam também fatores_atende.json, o fator de decisão do "atende" por aplicação (core/limiar.py),
com os limiares do perfil da versão (core/modelos.perfil_de).
Todo run grava também cobertura_tr069.json e o parâmetro cobertura_tr069 (core/features.cobertura_tr069).
"""

import os
import sys

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import limiar as core_limiar
from ml.core import modelos as core_modelos
from ml.core import producao as core_producao
from ml.core import quantis as core_quantis
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


def treinar_quantis(conj, features, vazadas, params: dict, cobertura: dict) -> None:
  """Latência e jitter: p50 e p90 em escala log, medidos pela régua quantílica."""
  with mlflow.start_run(run_name=f"{params['modelo_versao']}-quantis-{ALVO}"):
    mlflow.log_params(dict(params, quantis=','.join(str(q) for q in core_quantis.QUANTIS)))
    prev = core_quantis.prever_quantis_fora_do_fold(conj.df, features, ALVO, vazadas)
    resumo = core_quantis.resumir_quantis(prev, len(features))
    for q in core_quantis.QUANTIS:
      c = core_quantis.coluna(q)
      mlflow.log_metric(f'pinball_{c}', resumo['pinball'][c])
      mlflow.log_metric(f'cobertura_{c}', resumo['cobertura'][c])
      for site, metricas in resumo['por_local'].items():
        mlflow.log_metric(f'pinball_{c}_{site}', metricas['pinball'][c])
        mlflow.log_metric(f'cobertura_{c}_{site}', metricas['cobertura'][c])
    for chave, intervalo in resumo['intervalos'].items():
      if intervalo:
        mlflow.log_metric(f'{chave}_lo90', intervalo[0])
        mlflow.log_metric(f'{chave}_hi90', intervalo[1])
    mlflow.log_metric('mediana_mae', resumo['mediana_mae'])
    mlflow.log_metric('cruzados', resumo['cruzados'])
    X = core_features.matriz(conj.df, features)
    y_log = np.log1p(conj.df[ALVO].astype(float).clip(lower=0))
    for q in core_quantis.QUANTIS:
      modelo = core_quantis.modelo_quantil(q).fit(X, y_log)
      mlflow.sklearn.log_model(sk_model=modelo, name=f'quantil_{core_quantis.coluna(q)}',
                               serialization_format='skops')
    mlflow.log_dict(core_producao.contrato(conj.df, features), 'contrato.json')
    mlflow.log_dict(cobertura, 'cobertura_tr069.json')
    # A produção não vê prédio novo durante o treino: a correção usa LOGO entre todos os prédios.
    correcao = core_quantis.correcao_conformal(X, y_log, conj.df['_site'], 0.9)
    termo = 0.0 if correcao is None else correcao
    mlflow.log_metric('correcao_log_q90', termo)
    mlflow.log_dict({'quantil': 0.9, 'correcao_log': termo, 'escala': 'log1p',
                     'uso': 'q90_ms = expm1(predict(X) + correcao_log)',
                     'sem_correcao': correcao is None,
                     'versao_regua': core_avaliacao.VERSAO_REGUA}, 'conformal.json')
    print(f"Quantis {ALVO}: cobertura {resumo['cobertura']} (90%: "
          f"{resumo['intervalos'].get('cobertura_q90')}), pinball {resumo['pinball']}, "
          f"MAE da mediana {resumo['mediana_mae']}, cruzados {resumo['cruzados']}")
    print(f'  correção conformal do p90 (log): {termo:.4f}; por prédio na régua: {resumo["correcao_por_local"]}')
    for site, metricas in resumo['por_local'].items():
      print(f'  {site}: {metricas}')


def fatores_atende(registro: dict, nome_modelo: str, conj, ids, features) -> dict:
  """Fator de decisão do "atende" por aplicação (core/limiar.py), para a produção usar com este modelo.

  Precisa das previsões de download e upload: carrega o outro alvo com os mesmos datasets.
  Os fatores vêm do modelo da régua (LOGO com todos os prédios), não da configuração da varredura.
  """
  outro = 'speedtest_up_mbps' if conj.alvo == 'speedtest_down_mbps' else 'speedtest_down_mbps'
  conj_outro = core_carga.carregar(outro, ids=ids)
  dn, up = (conj, conj_outro) if conj.alvo == 'speedtest_down_mbps' else (conj_outro, conj)
  perfil = core_modelos.perfil_de(registro, nome_modelo)
  aplicacoes = core_aplicacoes.carregar_perfil(perfil)
  fatores = core_limiar.fatores_producao(dn, up, features, aplicacoes,
                                         core_modelos.denominador_de(registro, nome_modelo, dn.alvo),
                                         core_modelos.denominador_de(registro, nome_modelo, up.alvo))
  return {'fatores': fatores, 'perfil': perfil, 'aplicacoes': aplicacoes, 'versao_regua': core_avaliacao.VERSAO_REGUA,
          'uso': 'atende = previsao_download >= k * dn e previsao_upload >= k * up, k = fatores[aplicação]',
          'origem': 'LOGO com todos os prédios, modelo da régua (core/avaliacao.modelo_regua)'}


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
  cobertura = core_features.cobertura_tr069(features, conj.tabela, conj.catalogo)
  print(f"Cobertura TR-069: {cobertura['nivel']}"
        + (f"; lacunas {[(l['feature'], l['status']) for l in cobertura['lacunas']]}" if cobertura['lacunas'] else ''))
  denominador = core_modelos.denominador_de(registro, nome_modelo, ALVO)
  coluna_den = core_modelos.coluna_do_denominador(denominador)
  radio_den = denominador.get('radio') if isinstance(denominador, dict) else None
  if coluna_den:
    validate_columns(conj.df, [coluna_den] + (['radio'] if radio_den else []), 'denominador')
  print(f"Modelo: {nome_modelo}" + (' (ativo)' if nome_modelo == registro['ativo'] else '')
        + f" — {len(features)} features, alvo {ALVO}, datasets {conj.datasets}")

  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  params = {
    'modelo_versao': nome_modelo, 'alvo': ALVO,
    'datasets': ','.join(conj.datasets),
    'fingerprints': ','.join(impressoes[i] for i in conj.datasets),
    'versao_tabela': core_features.versao_tabela(),
    'versao_catalogo': core_features.CATALOGO_VERSAO,
    'versao_regua': core_avaliacao.VERSAO_REGUA,
    'features': ','.join(features),
    'cobertura_tr069': cobertura['nivel'],
    'removidas_por_vazamento': ','.join(removidas),
    'denominador': coluna_den or '',
    'denominador_radio': radio_den or '',
  }
  mlflow.set_experiment('MLflow Wifi Regressions')
  if ALVO in core_quantis.ALVOS_QUANTILICOS:
    treinar_quantis(conj, features, vazadas, params, cobertura)
    return

  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  contrato = core_producao.contrato(conj.df[treino], features)
  fatores = fatores_atende(registro, nome_modelo, conj, ids, features)
  print(f"Fatores do atende (produção): {fatores['fatores']}")
  y_final = conj.df.loc[treino, ALVO].astype(float)
  y_eficiencia, eficiencia = None, None
  if coluna_den:
    den = pd.to_numeric(conj.df.loc[treino, coluna_den], errors='coerce')
    mediana = float(den[den >= core_avaliacao.DEN_MINIMO].median())
    y_eficiencia = y_final / den.where(den >= core_avaliacao.DEN_MINIMO, mediana)
    uso = 'mbps = predict(X) * denominador (vazio ou abaixo de den_minimo: mediana_imputacao)'
    if radio_den:
      uso = (f'radio == {radio_den!r}: mbps = <modelo>_eficiencia.predict(X) * denominador '
             '(vazio ou abaixo de den_minimo: mediana_imputacao); demais linhas: mbps = <modelo>_absoluto.predict(X)')
    eficiencia = {'alvo': ALVO, 'denominador': coluna_den, 'radio': radio_den, 'mediana_imputacao': mediana,
                  'den_minimo': core_avaliacao.DEN_MINIMO, 'uso': uso}
  for config in CONFIGS:
    with mlflow.start_run(run_name=f"{nome_modelo}-{config['model_type']}-{config['max_depth']}"):
      mlflow.log_params(dict(params, **config))
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config),
                                                denominador=denominador)
      resumo = core_avaliacao.resumir(prev, len(features))
      registrar_metricas(resumo)
      finais = {config['model_type']: y_final}
      if coluna_den and radio_den:
        finais = {f"{config['model_type']}_eficiencia": y_eficiencia, f"{config['model_type']}_absoluto": y_final}
      elif coluna_den:
        finais = {config['model_type']: y_eficiencia}
      for nome_final, y_treino in finais.items():
        final = montar(config).fit(X_final, y_treino)
        # O imputer guarda um numpy.dtype, que o skops não confia por padrão.
        mlflow.sklearn.log_model(sk_model=final, name=nome_final, serialization_format='skops',
                                 skops_trusted_types=['numpy.dtype'])
      mlflow.log_dict(contrato, 'contrato.json')
      mlflow.log_dict(cobertura, 'cobertura_tr069.json')
      mlflow.log_dict(fatores, 'fatores_atende.json')
      if eficiencia:
        mlflow.log_dict(eficiencia, 'eficiencia.json')
        mlflow.log_metric('den_imputados', resumo['den_imputados'])
      print('-' * 61)
      print(f"{config['model_type']} {config}: R² pooled {resumo['pooled']} "
            f"(90%: {resumo['intervalos'].get('pooled')}), MAE {resumo['mae']}, MAE log {resumo['mae_log']}")
      print(f"  por prédio: {resumo['por_local']}")


if __name__ == '__main__':
  main()
