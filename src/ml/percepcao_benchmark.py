"""Classificador do rótulo de percepção por cômodo (core/percepcao.json), medido por posição.

Versão: MODELO=<nome> (padrão: v5). Datasets: DATASETS=a.zip,b.zip (padrão: o conjunto
canônico, o mesmo do Studio). Treina o RF de core/percepcao com as features da versão e com o
piso (só `radio`), LOGO por prédio, e imprime a acurácia balanceada por posição com intervalo
de 90%, a diferença pareada, a matriz de confusão, os acertos por prédio e a leitura da regra
fixada no spec (docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md).
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import modelos as core_modelos
from ml.core import percepcao as core_percepcao

ALVO = 'speedtest_down_mbps'
PISO = ['radio']


def _linha(nome: str, r: dict) -> str:
  return f'  {nome:<6} {r["nota"]:.3f}  (90%: {r["intervalo"]})'


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or 'v5'
  if nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conj = core_carga.carregar(ALVO, ids=ids)
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  df, sem_rotulo, sem_linhas = core_percepcao.rotular(conj.df, core_percepcao.carregar())
  pedidas = list(registro['versoes'][nome]['features'])
  features = [f for f in pedidas if f in df.columns and f not in vazadas]
  fora = [f for f in pedidas if f not in features]

  print(f'Datasets: {conj.datasets}')
  for aviso in conj.avisos:
    print(f'  aviso: {aviso}')
  if sem_rotulo:
    print(f'Posições sem rótulo (fora): {sem_rotulo}')
  if sem_linhas:
    print(f'Rotuladas sem linhas na base: {sem_linhas}')
  print(f'Modelo {nome}: {len(features)} features' + (f'; fora (vazamento ou ausentes): {fora}' if fora else ''))

  resultados = {}
  for chave, colunas in ((nome, features), ('piso', PISO)):
    proba = core_percepcao.prever_fora_do_fold(df, colunas, vazadas)
    resultados[chave] = (proba, core_percepcao.por_posicao(df, proba))
  pos_piso = resultados['piso'][1]
  pos_nova = resultados[nome][1]
  print(f'{len(df)} linhas, {len(pos_piso)} posições, {pos_piso["_site"].nunique()} prédios; '
        f'classes por posição: {pos_piso["real"].value_counts().to_dict()}')

  amostras = core_avaliacao.reamostras(pos_piso.index, pos_piso['_site'])
  r_piso = core_percepcao.resumir(pos_piso, amostras)
  r_nova = core_percepcao.resumir(pos_nova, amostras)
  dif = core_percepcao.diferenca(pos_nova, pos_piso, amostras)

  print(f'\nAcurácia balanceada por posição (acaso {core_percepcao.ACASO:.3f}):')
  print(_linha(nome, r_nova))
  print(_linha('piso', r_piso))
  print(f'  {nome} - piso: {dif["diferenca"]:+.3f}  (90%: {dif["intervalo"]})')

  print('\nAcurácia balanceada por linha (só referência):')
  for chave, (proba, _) in resultados.items():
    print(f'  {chave:<6} {core_percepcao.acuracia_balanceada(df["_classe"], proba.idxmax(axis=1)):.3f}')

  for chave, (_, pos_df) in resultados.items():
    m, graves = core_percepcao.confusao(pos_df)
    print(f'\nMatriz de confusão {chave} (posições; real nas linhas), erros graves: {graves}')
    print(m.to_string())
    print('Acertos por prédio (cada prédio teve um avaliador; avaliador e prédio não se separam):')
    for site, (acertos, n) in core_percepcao.por_predio(pos_df).items():
      print(f'  {site:<18} {acertos}/{n}')
    erradas = pos_df[pos_df['real'] != pos_df['previsto']]
    print('Posições erradas:')
    for pos, linha in erradas.iterrows():
      print(f'  {pos:<26} real {linha["real"]:<10} previsto {linha["previsto"]}')

  regra = core_percepcao.leitura(r_piso, r_nova, dif)
  print(f'\nLeitura (regra do spec, seção 3.4): aprendível = {regra["aprendivel"]}; '
        f'{nome} contra o piso = {regra["contra_piso"]}')


if __name__ == '__main__':
  main()
