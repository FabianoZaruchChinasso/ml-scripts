"""Pacote de uma versão: os modelos finais e a receita de previsão.

Treina com todos os prédios pela mesma receita que a avaliação usa dentro de cada fold
(core/avaliacao.prever_fora_do_fold e core/quantis.prever_quantis_fora_do_fold), para que o modelo
entregue seja o modelo medido. Não importa o MLflow: core/pacote_mlflow.py grava e carrega.
O pacote não corta a previsão no teto de WAN: em produção o link da casa não é conhecido.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.core import avaliacao as core_avaliacao
from ml.core import producao as core_producao
from ml.core import quantis as core_quantis
from ml.core.features import matriz

VERSAO_PACOTE = '2026-11-10.1'
PREFIXOS = {'speedtest_down_mbps': 'down', 'speedtest_up_mbps': 'up', 'latency_ms': 'lat', 'jitter_ms': 'jit'}
SAIDA_VAZAO = {'speedtest_down_mbps': 'download_mbps', 'speedtest_up_mbps': 'upload_mbps'}
SAIDAS = ('download_mbps', 'upload_mbps', 'latency_ms_p50', 'latency_ms_p90', 'latency_ms_p90_bruto',
          'jitter_ms_p50', 'jitter_ms_p90', 'jitter_ms_p90_bruto')


@dataclass
class Pacote:
  modelos: dict
  receita: dict


def _treinar_vazao(conj, features: list, denominador, modelos: dict) -> dict:
  """Download ou upload: absoluto, eficiência (alvo ÷ denominador) ou os dois, quando a eficiência vale só numa banda."""
  p = PREFIXOS[conj.alvo]
  df = conj.df[conj.df[conj.alvo].notna()]
  if '_limitado_wan' in df.columns:
    df = df[~df['_limitado_wan'].astype(bool)]
  X = matriz(df, features)
  y = df[conj.alvo].astype(float)
  coluna = denominador['coluna'] if isinstance(denominador, dict) else denominador
  radio = denominador.get('radio') if isinstance(denominador, dict) else None
  bloco = {'contrato': core_producao.contrato(df, features), 'denominador': None}
  if coluna is None or radio is not None:
    modelos[f'{p}_absoluto'] = core_avaliacao.modelo_regua().fit(X, y)
  if coluna is not None:
    if coluna not in df.columns:
      raise ValueError(f'denominador {coluna!r} não existe no conjunto de {conj.alvo}')
    den = pd.to_numeric(df[coluna], errors='coerce')
    validos = den >= core_avaliacao.DEN_MINIMO
    if not validos.any():
      raise ValueError(f'nenhuma linha de treino com {coluna!r} válido em {conj.alvo}')
    mediana = float(den[validos].median())
    modelos[f'{p}_eficiencia'] = core_avaliacao.modelo_regua().fit(X, y / den.where(validos, mediana))
    bloco['denominador'] = {'coluna': coluna, 'radio': radio, 'mediana_imputacao': mediana,
                            'den_minimo': core_avaliacao.DEN_MINIMO}
  return bloco


def _treinar_quantis(conj, features: list, modelos: dict) -> dict:
  """Latência ou jitter: p50 e p90 em log1p, e a correção conformal do p90 entre todos os prédios."""
  p = PREFIXOS[conj.alvo]
  df = conj.df[conj.df[conj.alvo].notna()]
  X = matriz(df, features)
  y_log = np.log1p(df[conj.alvo].astype(float).clip(lower=0))
  for q in core_quantis.QUANTIS:
    modelos[f'{p}_{core_quantis.coluna(q)}'] = core_quantis.modelo_quantil(q).fit(X, y_log)
  correcao = core_quantis.correcao_conformal(X, y_log, df['_site'], 0.9)
  return {'contrato': core_producao.contrato(df, features),
          'correcao_log_q90': 0.0 if correcao is None else correcao, 'sem_correcao': correcao is None}


def treinar(conjs: dict, features, denominador: dict = None) -> Pacote:
  """Modelos finais dos quatro alvos e a receita para prever com eles.

  `conjs`: {alvo: Conjunto}. `features`: já sem as colunas de vazamento (se alguma chegar, levanta
  AssertionError). `denominador`: {alvo: coluna ou {'coluna', 'radio'}} da versão, ou None.
  """
  features = list(features)
  if not features:
    raise ValueError('o pacote precisa de pelo menos uma feature')
  denominador = denominador or {}
  modelos, alvos, entradas = {}, {}, list(features)
  for alvo in PREFIXOS:
    conj = conjs[alvo]
    core_avaliacao.assert_sem_vazamento(features, [c for c, k in conj.classes.items() if k is not None and k.vazamento])
    if alvo in SAIDA_VAZAO:
      alvos[alvo] = _treinar_vazao(conj, features, denominador.get(alvo), modelos)
      den = alvos[alvo]['denominador']
      if den:
        entradas += [c for c in (den['coluna'], 'radio' if den['radio'] else None) if c and c not in entradas]
    else:
      alvos[alvo] = _treinar_quantis(conj, features, modelos)
  receita = {'versao_pacote': VERSAO_PACOTE, 'versao_regua': core_avaliacao.VERSAO_REGUA, 'features': features,
             'entradas': entradas, 'saidas': list(SAIDAS), 'alvos': alvos}
  return Pacote(modelos, receita)


def _na_banda(radio: pd.Series, valor: str) -> np.ndarray:
  """Linhas da banda `valor`, sem diferença de maiúsculas e espaços ('5GHz' do ACS casa com '5ghz')."""
  igual = radio.astype('string').str.strip().str.lower() == valor.strip().lower()
  return igual.fillna(False).to_numpy(dtype=bool)


def _prever_vazao(pacote: Pacote, alvo: str, linhas: pd.DataFrame, avisos: list) -> np.ndarray:
  p = PREFIXOS[alvo]
  bloco = pacote.receita['alvos'][alvo]
  X, da_entrada = core_producao.preparar_entrada(linhas, bloco['contrato'])
  avisos += [f'{alvo}: {a}' for a in da_entrada]
  den = bloco['denominador']
  if den is None:
    return np.asarray(pacote.modelos[f'{p}_absoluto'].predict(X), dtype=float)
  valores = pd.to_numeric(linhas[den['coluna']], errors='coerce')
  invalido = ~(valores >= den['den_minimo']).to_numpy(dtype=bool)
  valores = valores.where(~invalido, den['mediana_imputacao']).to_numpy(dtype=float)
  previsto = np.asarray(pacote.modelos[f'{p}_eficiencia'].predict(X), dtype=float) * valores
  if den['radio'] is not None:
    na_banda = _na_banda(linhas['radio'], den['radio'])
    previsto = np.where(na_banda, previsto, np.asarray(pacote.modelos[f'{p}_absoluto'].predict(X), dtype=float))
    invalido = invalido & na_banda
  if invalido.any():
    avisos.append(f"{alvo}: {den['coluna']} vazio ou abaixo de {den['den_minimo']} em {int(invalido.sum())} "
                  'linha(s); usei a mediana do treino')
  return previsto


def _prever_quantis(pacote: Pacote, alvo: str, linhas: pd.DataFrame, avisos: list) -> dict:
  p = PREFIXOS[alvo]
  bloco = pacote.receita['alvos'][alvo]
  X, da_entrada = core_producao.preparar_entrada(linhas, bloco['contrato'])
  avisos += [f'{alvo}: {a}' for a in da_entrada]
  q90_log = np.asarray(pacote.modelos[f'{p}_q90'].predict(X), dtype=float)
  p50 = np.clip(np.expm1(np.asarray(pacote.modelos[f'{p}_q50'].predict(X), dtype=float)), 0, None)
  p90 = np.maximum(np.clip(np.expm1(q90_log + bloco['correcao_log_q90']), 0, None), p50)
  bruto = np.maximum(np.clip(np.expm1(q90_log), 0, None), p50)
  return {f'{alvo}_p50': p50, f'{alvo}_p90': p90, f'{alvo}_p90_bruto': bruto}


def prever(pacote: Pacote, linhas: pd.DataFrame):
  """Previsões das linhas, com as colunas de SAIDAS e o índice de `linhas`. Devolve (DataFrame, avisos).

  `linhas` precisa das colunas de receita['entradas']. O p90 leva a correção conformal; o p90_bruto é o
  que a régua por cômodo usa. Nenhum p90 fica abaixo do p50.
  """
  faltam = [c for c in pacote.receita['entradas'] if c not in linhas.columns]
  if faltam:
    raise ValueError(f'colunas ausentes na entrada do pacote: {faltam}')
  avisos, saida = [], {}
  for alvo, nome in SAIDA_VAZAO.items():
    saida[nome] = _prever_vazao(pacote, alvo, linhas, avisos)
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    saida.update(_prever_quantis(pacote, alvo, linhas, avisos))
  return pd.DataFrame(saida, index=linhas.index)[list(SAIDAS)], avisos
