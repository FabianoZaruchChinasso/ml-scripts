"""Paralelos entre colunas de laboratório e o TR-069, e o teste de aceite de derivadas.

Para cada coluna que não é TR-069 (sniffer, cliente, manual, ambiente):
  1. importa?     somá-la a um modelo base melhora o alvo em prédio novo?
  2. reconstrói?  o TR-069 inteiro prevê a coluna em prédio novo?
  3. assinatura   quais colunas TR-069 andam com ela dentro de cada prédio, com o
                  mesmo sinal em todos? (correlação dentro do prédio, para a diferença
                  entre prédios não fabricar relação)
  4. receita      uma fórmula só com TR-069 que reproduza a coluna. A fórmula é
                  escrita por uma pessoa e passa pelo teste de aceite abaixo.
"""

import time
from statistics import mean

import numpy as np
import pandas as pd

from ml.core import features as F
from ml.core import formulas
from ml.studio import features as SF

RECONSTROI_MIN = 0.3
GANHO_MIN = 0.01
RHO_ASSINATURA = 0.3
ARVORES_PARALELOS = 100
MAX_PARALELOS = 40
TOP_ASSINATURA = 5
CLASSES_LABORATORIO = {'sniffer', 'cliente', 'ambiente', 'geometria', F.CLASSE_AUXILIAR}


def _br(valor: float) -> str:
  return f'{valor:g}'.replace('.', ',')


def _spearman(a: pd.Series, b: pd.Series):
  par = pd.concat([a, b], axis=1).dropna()
  if len(par) < 10 or par.iloc[:, 0].nunique() < 2 or par.iloc[:, 1].nunique() < 2:
    return None
  return float(par.iloc[:, 0].corr(par.iloc[:, 1], method='spearman'))


def assinatura(df: pd.DataFrame, coluna: str, tr069_numericas: list) -> list:
  """Correlação dentro de cada prédio entre a coluna e cada TR-069 numérica.

  `consistente` exige |ρ| ≥ RHO_ASSINATURA com o mesmo sinal em todos os prédios
  onde a coluna varia. Prédio onde ela é constante não conta a favor nem contra.
  """
  locais = sorted(df['_site'].unique())
  saida = []
  for t in tr069_numericas:
    if t == coluna:
      continue
    por_local = {l: _spearman(df.loc[df['_site'] == l, coluna], df.loc[df['_site'] == l, t]) for l in locais}
    validos = [v for v in por_local.values() if v is not None]
    consistente = (len(validos) >= 2 and all(abs(v) >= RHO_ASSINATURA for v in validos)
                   and len({np.sign(v) for v in validos}) == 1)
    saida.append({'coluna': t, 'por_local': {l: None if v is None else round(v, 3) for l, v in por_local.items()},
                  'minimo': round(min(abs(v) for v in validos), 3) if validos else None,
                  'locais_com_variacao': len(validos), 'consistente': consistente})
  saida.sort(key=lambda a: (not a['consistente'], -(a['minimo'] or 0)))
  return saida[:TOP_ASSINATURA]


def n_efetivo(df: pd.DataFrame, coluna: str) -> dict:
  """Coluna constante dentro de cada posição (típico de campo manual) tem poucos pontos independentes."""
  sub = df[['_pos', coluna]].dropna()
  variacao = sub.groupby('_pos')[coluna].nunique()
  return {'grupos': int(sub.drop_duplicates().shape[0]),
          'constante_por_posicao': bool((variacao <= 1).all())}


def veredito(importa: bool, reconstroi: bool) -> str:
  if importa and reconstroi:
    return 'candidata'
  if importa:
    return 'so_laboratorio'
  if reconstroi:
    return 'ja_no_tr069'
  return 'sem_paralelo'


def _tr069(inv: dict):
  por_nome = {c['coluna']: c for c in inv['colunas']}
  todas = [c for c in SF.elegiveis(inv) if por_nome[c]['classe'] == 'tr069']
  return todas, [c for c in todas if por_nome[c]['tipo'] == 'numerica']


def _resumo(conj, features, vazadas):
  return SF._resumo(SF._logo(conj.df, features, conj.alvo, vazadas, arvores=ARVORES_PARALELOS), len(features))


def colunas_de_laboratorio(inv: dict) -> list:
  cols = [c for c in inv['colunas'] if c['classe'] in CLASSES_LABORATORIO and c['tipo'] == 'numerica'
          and not c['vazamento'] and not c['constante'] and c['cobertura'] >= SF.COBERTURA_MIN]
  cols.sort(key=lambda c: -(c['rho'] or 0))
  return cols


def analisar(conj: SF.Conjunto, inv: dict, base: list, progresso=None) -> dict:
  inicio = time.time()
  SF._checar_locais(conj.df)
  vazadas = SF.vazadas_do_conjunto(conj)
  tr069, tr069_num = _tr069(inv)
  if not tr069:
    raise ValueError('nenhuma coluna TR-069 elegível neste conjunto')
  base = [f for f in base if f in conj.df.columns and f not in vazadas]
  todas = colunas_de_laboratorio(inv)
  lab = todas[:MAX_PARALELOS]
  avisos = []
  if len(todas) > len(lab):
    avisos.append(f'{len(todas)} colunas de laboratório elegíveis; analisadas as {len(lab)} de maior |ρ| com o alvo')
  resumo_base = _resumo(conj, base, vazadas)
  linhas = []
  for i, c in enumerate(lab):
    nome = c['coluna']
    if progresso:
      progresso({'fase': f'{i + 1}/{len(lab)}: {nome}'})
    na_base = nome in base
    if na_base:
      sem = [f for f in base if f != nome]
      delta = SF.delta_por_local(resumo_base, _resumo(conj, sem, vazadas))
    else:
      delta = SF.delta_por_local(_resumo(conj, base + [nome], vazadas), resumo_base)
    rec = SF.r2_por_local(conj.df, tr069, nome, vazadas, arvores=ARVORES_PARALELOS, min_teste=5, min_treino=20)
    importa = (delta['media'] is not None and delta['media'] >= GANHO_MIN
               and delta['melhora'] == delta['locais'] > 0)
    reconstroi = bool(rec) and min(rec.values()) >= RECONSTROI_MIN
    ass = assinatura(conj.df, nome, tr069_num)
    linhas.append({
      'coluna': nome, 'classe': c['classe'], 'rho': c['rho'], 'na_base': na_base,
      'importa': importa, 'ganho': delta,
      'reconstroi': reconstroi,
      'reconstrucao': {'por_local': {k: round(v, 4) for k, v in sorted(rec.items())},
                       'minimo': round(min(rec.values()), 4) if rec else None,
                       'media': round(mean(rec.values()), 4) if rec else None},
      'assinatura': ass, 'n_efetivo': n_efetivo(conj.df, nome),
      'sugestao': [a['coluna'] for a in ass if a['consistente']],
      'veredito': veredito(importa, reconstroi),
    })
  return {'alvo': conj.alvo, 'datasets': conj.datasets, 'base': base,
          'resumo_base': resumo_base, 'colunas': linhas, 'avisos': avisos,
          'criterios': {'ganho_min': GANHO_MIN, 'reconstroi_min': RECONSTROI_MIN,
                        'rho_assinatura': RHO_ASSINATURA, 'arvores': ARVORES_PARALELOS},
          'segundos': round(time.time() - inicio, 1)}


def _derivada(nome: str, formula: str, inspirada_em=None) -> F.Derivada:
  _, insumos = formulas.analisar(formula)
  return F.Derivada(nome, tuple(insumos), lambda df: formulas.calcular(formula, df), '',
                    formula=formula, inspirada_em=inspirada_em)


def previa(conj: SF.Conjunto, nome: str, formula: str, inspirada_em=None) -> dict:
  """Sem ajuste de modelo: cobertura, classe herdada, distribuição por local e correlações."""
  if not F.NOME_DERIVADA.match(nome or ''):
    raise ValueError('nome inválido: minúsculas, dígitos e _, começando por letra (3 a 40 caracteres)')
  if nome in conj.df.columns:
    raise ValueError(f'{nome!r} já é o nome de uma coluna ou derivada')
  derivada = _derivada(nome, formula, inspirada_em)
  de_derivada = [c for c in derivada.insumos if c in {d.nome for d in conj.catalogo}]
  if de_derivada:
    raise ValueError(f'{de_derivada} já são derivadas: escreva a fórmula com as colunas brutas '
                     '(derivada de derivada não é suportada)')
  serie = formulas.calcular(formula, conj.df)
  classe = F.classificar_derivada(derivada, conj.tabela)
  por_local = {}
  for local, g in serie.groupby(conj.df['_site']):
    v = g.dropna()
    por_local[local] = None if v.empty else {
      'min': round(float(v.min()), 4), 'mediana': round(float(v.median()), 4), 'max': round(float(v.max()), 4)}
  saida = {'nome': nome, 'formula': formula, 'insumos': list(derivada.insumos),
           'classe': None if classe is None else classe.classe,
           'vazamento': None if classe is None else classe.vazamento,
           'sem_classificacao': [c for c in derivada.insumos if F.classificar(c, conj.tabela) is None
                                 and c not in {d.nome for d in conj.catalogo}],
           'cobertura': round(float(serie.notna().mean()), 3),
           'distribuicao': por_local,
           'rho_alvo': None if _spearman(serie, conj.df[conj.alvo]) is None
           else round(abs(_spearman(serie, conj.df[conj.alvo])), 3)}
  if inspirada_em:
    if inspirada_em not in conj.df.columns:
      raise ValueError(f'coluna de inspiração {inspirada_em!r} não existe no conjunto')
    saida['inspirada_em'] = inspirada_em
    saida['rho_inspirada_por_local'] = {
      l: None if (r := _spearman(serie[conj.df['_site'] == l], conj.df.loc[conj.df['_site'] == l, inspirada_em])) is None
      else round(r, 3) for l in sorted(conj.df['_site'].unique())}
  return saida


def testar(conj: SF.Conjunto, nome: str, formula: str, base: list, inspirada_em=None) -> dict:
  """Critério de aceite. `aprovada` só se todos os critérios passarem."""
  inicio = time.time()
  SF._checar_locais(conj.df)
  pre = previa(conj, nome, formula, inspirada_em)
  df = conj.df.copy()
  df[nome] = formulas.calcular(formula, df)
  vazadas = SF.vazadas_do_conjunto(conj)
  base = [f for f in base if f in df.columns and f not in vazadas]
  com = SF._resumo(SF._logo(df, base + [nome], conj.alvo, vazadas), len(base) + 1)
  sem = SF._resumo(SF._logo(df, base, conj.alvo, vazadas), len(base))
  ganho = SF.delta_por_local(com, sem)
  criterios = [
    {'criterio': 'todos os insumos são TR-069', 'ok': pre['classe'] == 'tr069'},
    {'criterio': 'nenhum insumo com vazamento', 'ok': pre['vazamento'] is False},
    {'criterio': f'ganho médio de R² ≥ {_br(GANHO_MIN)} e melhora em todos os locais',
     'ok': ganho['media'] is not None and ganho['media'] >= GANHO_MIN and ganho['melhora'] == ganho['locais'] > 0},
  ]
  reconstrucao = None
  if inspirada_em:
    rec = SF.r2_por_local(df, [nome], inspirada_em, vazadas, min_teste=5, min_treino=20)
    reconstrucao = {'por_local': {k: round(v, 4) for k, v in sorted(rec.items())},
                    'minimo': round(min(rec.values()), 4) if rec else None}
    criterios.append({'criterio': f'reconstrói {inspirada_em} com R² ≥ {_br(RECONSTROI_MIN)} em todos os locais',
                      'ok': bool(rec) and min(rec.values()) >= RECONSTROI_MIN})
  return dict(pre, base=base, ganho=ganho, resumo_com=com, resumo_sem=sem, reconstrucao=reconstrucao,
              criterios=criterios, status='aprovada' if all(c['ok'] for c in criterios) else 'hipotese',
              segundos=round(time.time() - inicio, 1))
