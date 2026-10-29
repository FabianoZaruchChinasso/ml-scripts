"""Régua por cômodo (core/comodo.py): reavalia as versões do registro e o piso.

Versão: MODELO=<nome> restringe a uma versão (a ativa entra sempre, para a comparação).
Datasets: DATASETS=a.zip,b.zip (padrão: o conjunto canônico, o mesmo do Studio). Imprime a
referência da casa, a verdade por posição, a verdade contra o rótulo humano e, por versão, a
nota com intervalo de 90%, a comparação com o piso e com a ativa, a matriz de confusão, os
acertos por prédio e "apto para jogo". Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import comodo as core_comodo
from ml.core import modelos as core_modelos
from ml.core import percepcao as core_percepcao
from ml.core import qoe as core_qoe

PISO = 'piso'


def _faixa(intervalo) -> str:
  return '–' if intervalo is None else f'{intervalo[0]:+.3f} a {intervalo[1]:+.3f}'


def main():
  registro = core_modelos.carregar()
  pedido = os.environ.get('MODELO')
  if pedido and pedido not in registro['versoes']:
    raise SystemExit(f'MODELO={pedido!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ativa = registro['ativo']
  nomes = [pedido] if pedido else list(registro['versoes'])
  if ativa not in nomes:
    nomes.append(ativa)
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_qoe.ALVOS}
  vazadas = {alvo: [c for c, k in conj.classes.items() if k is not None and k.vazamento]
             for alvo, conj in conjs.items()}
  limiares = core_aplicacoes.carregar_perfil('norma')
  df = core_qoe.conjunto_qoe(conjs)
  real, ref = core_comodo.verdade(df, limiares)
  linhas = set(core_comodo.sozinhas(df)['_linha'])

  print(f'Régua por cômodo {core_comodo.VERSAO_COMODO}; datasets {conjs[core_comodo.DN].datasets}')
  print(f'{len(linhas)} de {len(df)} linhas sozinhas no rádio; {len(real)} posições; {real["_site"].nunique()} prédios')
  print('\nReferência da casa (V0 provisório, Mbps):')
  print(ref.round(1).to_string())
  print('\nVerdade por posição:')
  print(real.sort_values(['_site', 'razao']).round(2).to_string())
  print(f'Classes: {real["classe"].value_counts().to_dict()}; apto para jogo: {int(real["apto_jogo"].sum())}')

  core_percepcao.carregar()  # valida o arquivo de rótulos antes de ler os níveis brutos
  with open(core_percepcao.PERCEPCAO_PATH, encoding='utf-8') as handle:
    niveis = json.load(handle)['posicoes']
  acuracia, m = core_comodo.contra_rotulo(real, niveis)
  print(f'\nVerdade contra o rótulo humano (rótulo nas linhas): acurácia balanceada {acuracia:.3f}')
  print(m.to_string())

  pos = {}
  for nome in [PISO] + nomes:
    if nome == PISO:
      features, denominador = ['radio'], None
    else:
      features = registro['versoes'][nome]['features']
      denominador = {a: core_modelos.denominador_de(registro, nome, a) for a in (core_comodo.DN, core_comodo.UP)}
    prev = core_comodo.prever(conjs, features, vazadas, denominador)
    prev = prev[prev['_linha'].isin(linhas)]
    pos[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(prev, ref, limiares))
  if len({tuple(p.index) for p in pos.values()}) != 1:
    raise SystemExit('as versões não cobrem as mesmas posições: '
                     + '; '.join(f'{n}: {len(p)}' for n, p in pos.items()))
  amostras = core_avaliacao.reamostras(pos[PISO].index, pos[PISO]['_site'])

  print(f'\nNota (acurácia balanceada por posição, acaso 0,333); ativa = {ativa}')
  for nome in [PISO] + nomes:
    p = pos[nome]
    r = core_comodo.nota(p, amostras)
    c_piso = core_comodo.comparar(p, pos[PISO], amostras)
    c_ativa = core_comodo.comparar(p, pos[ativa], amostras)
    _, graves = core_comodo.confusao(p)
    acertos = int((p['real'] == p['previsto']).sum())
    print(f'  {nome:<10} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs piso {c_piso["diferenca"]:+.3f} '
          f'({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | vs {ativa} {c_ativa["diferenca"]:+.3f} '
          f'({_faixa(c_ativa["intervalo"])}) {c_ativa["resultado"]} | acertos {acertos}/{len(p)} | '
          f'graves {graves} | jogo {core_comodo.nota_jogo(p):.3f}')

  for nome in [PISO] + nomes:
    p = pos[nome]
    m, graves = core_comodo.confusao(p)
    print(f'\n{nome}: matriz de confusão (posições; verdade nas linhas), erros graves {graves}')
    print(m.to_string())
    print('Acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
    erradas = p[p['real'] != p['previsto']]
    print('Erradas: ' + ', '.join(f'{i} ({l.real}->{l.previsto})' for i, l in erradas.iterrows()))


if __name__ == '__main__':
  main()
