"""Análise da view Features: inventário de colunas, teto, ganho +1 e proxies.

Funções puras sobre DataFrames. O api.py descobre os datasets e cuida do cache.
"""

import hashlib
import re
import time
import warnings
from dataclasses import dataclass, field
from statistics import mean

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline

from ml.core import features as F
from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_site_id
from ml.core.splits import outer_logo_folds

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')

COBERTURA_MIN = 0.7
RHO_SUSPEITA = 0.9
PROXY_ALCANCAVEL = 0.7
PROXY_PARCIAL = 0.3
PROXY_TR069 = 0.99
MAX_PROXIES = 15
MAX_CATEGORIAS = 10
ARVORES = 200
ARVORES_PROXY = 100
CLASSES_FORA_DOS_AJUSTES = {'identificador', 'geometria', 'alvo'}
CLASSES_AUXILIARES = {'sniffer', 'cliente', 'ambiente'}
# `_site` é o grupo dos folds: o local de coleta (prédio). Deixar só um cômodo
# de fora mantinha os outros cômodos do mesmo prédio no treino — mesmo roteador,
# mesmo ambiente, mesmo dia — e inflava o R² (ver CHANGELOG).
# `_pos` é o cômodo, só para exibição; `_amb` é doméstico/corporativo.
_INTERNAS = ('_ds', '_site', '_pos', '_amb')


@dataclass
class Conjunto:
  df: pd.DataFrame
  alvo: str
  datasets: list
  classes: dict
  tabela: dict
  avisos: list = field(default_factory=list)


def preparar(frames: dict, alvo: str, tabela: dict, ambiente: str = None) -> Conjunto:
  """Junta os frames, descarta linhas sem alvo/local e calcula as derivadas.

  `ambiente` ('domestico' ou 'corporativo') restringe o conjunto a esse tipo de
  local de coleta; None mantém todos.
  """
  if alvo not in TARGETS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(TARGETS)}')
  if ambiente is not None and ambiente not in ENVIRONMENTS:
    raise ValueError(f'ambiente {ambiente!r} desconhecido; esperado um de {list(ENVIRONMENTS)}')
  if not frames:
    raise ValueError('nenhum dataset não-legacy ativo')
  avisos = []
  df = pd.concat([f.assign(_ds=ds) for ds, f in frames.items()], ignore_index=True)
  if alvo not in df.columns:
    raise ValueError(f'o alvo {alvo!r} não existe nos datasets ativos')
  sem_alvo = int(df[alvo].isna().sum())
  if sem_alvo:
    avisos.append(f'{sem_alvo} linhas sem {alvo} descartadas')
  df = df[df[alvo].notna()]

  posicoes, predios = {}, {}
  desconhecidos = []
  for valor in df['local'].dropna().unique():
    try:
      posicoes[valor] = resolve_site_id(pd.Series([valor])).iloc[0]
      predios[valor] = resolve_site_id(pd.Series([valor]), level='building').iloc[0]
    except ValueError:
      desconhecidos.append(str(valor))
  fora = int((~df['local'].isin(list(posicoes))).sum())
  if fora:
    avisos.append(f'{fora} linhas com local desconhecido em core/sites.py descartadas: '
                  f'{sorted(desconhecidos)}')
  df = df[df['local'].isin(list(posicoes))].reset_index(drop=True)
  df = df.assign(_site=df['local'].map(predios), _pos=df['local'].map(posicoes))
  df['_amb'] = df['_site'].map(BUILDING_ENVIRONMENT)
  if ambiente is not None:
    df = df[df['_amb'] == ambiente].reset_index(drop=True)
    if df.empty:
      raise ValueError(f'nenhuma linha de ambiente {ambiente!r} nos datasets ativos')

  df, avisos_derivadas = F.aplicar_derivadas(df)
  avisos += avisos_derivadas

  derivadas = {d.nome: d for d in F.CATALOGO}
  classes = {}
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    if coluna in derivadas:
      classes[coluna] = F.classificar_derivada(derivadas[coluna], tabela)
    else:
      classes[coluna] = F.classificar(coluna, tabela)
  return Conjunto(df, alvo, sorted(frames), classes, tabela, avisos)


def _tipo(serie: pd.Series) -> str:
  if pd.api.types.is_numeric_dtype(serie):
    return 'numerica'
  return 'categorica' if serie.nunique(dropna=True) <= MAX_CATEGORIAS else 'categorica_alta'


def _amostra(serie: pd.Series) -> str:
  valores = serie.dropna()
  if valores.empty:
    return 'vazia'
  if pd.api.types.is_numeric_dtype(valores):
    return f'{valores.min():.4g} a {valores.max():.4g}'
  return ', '.join(str(v) for v in valores.unique()[:3])


def _grupos_identicos(df: pd.DataFrame, colunas: list) -> list:
  por_hash = {}
  for coluna in colunas:
    valores = df[coluna].astype(float).round(9)
    digest = hashlib.sha1(pd.util.hash_pandas_object(valores, index=False).values.tobytes()).hexdigest()
    por_hash.setdefault(digest, []).append(coluna)
  return sorted(sorted(g) for g in por_hash.values() if len(g) > 1)


def inventario(conj: Conjunto) -> dict:
  df, alvo = conj.df, conj.alvo
  derivadas = {d.nome: d for d in F.CATALOGO}
  cobertura_ds = df.drop(columns=list(_INTERNAS)).notna().groupby(df['_ds']).mean()
  colunas, sem_classificacao, numericas = [], [], []
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    serie = df[coluna]
    c = conj.classes.get(coluna)
    tipo = _tipo(serie)
    constante = serie.nunique(dropna=True) <= 1
    cobertura = round(float(serie.notna().mean()), 3)
    if c is None:
      sem_classificacao.append({'coluna': coluna, 'sugestao': F.sugerir(coluna, conj.tabela),
                                'cobertura': cobertura, 'amostra': _amostra(serie)})
      continue
    rho = None
    if tipo == 'numerica' and not constante and c.classe != 'alvo':
      par = pd.concat([serie, df[alvo]], axis=1).dropna()
      if len(par) >= 3 and par.iloc[:, 0].nunique() > 1:
        rho = round(abs(float(par.iloc[:, 0].corr(par.iloc[:, 1], method='spearman'))), 3)
    if tipo == 'numerica' and not constante:
      numericas.append(coluna)
    colunas.append({
      'coluna': coluna, 'classe': c.classe, 'origem': c.origem, 'vazamento': c.vazamento,
      'parametro': c.parametro, 'derivada': coluna in derivadas,
      'normaliza_volume': coluna in derivadas and derivadas[coluna].normaliza_volume,
      'cobertura': cobertura,
      'cobertura_por_ds': {ds: round(float(v), 3) for ds, v in cobertura_ds[coluna].items()},
      'constante': bool(constante), 'tipo': tipo, 'rho': rho,
      'no_modelo': coluna in F.MODELO_ATUAL,
      'suspeita': rho is not None and rho >= RHO_SUSPEITA and not c.vazamento,
    })
  classe_de = {c['coluna']: c['classe'] for c in colunas}
  candidatas = [c['coluna'] for c in colunas
                if c['classe'] == 'tr069' and not c['no_modelo'] and not c['vazamento']
                and not c['constante'] and c['cobertura'] >= COBERTURA_MIN]
  contagem = {}
  for c in colunas:
    contagem[c['classe']] = contagem.get(c['classe'], 0) + 1
  avisos = list(conj.avisos)
  ausentes = [m for m in F.MODELO_ATUAL if m not in df.columns]
  if ausentes:
    avisos.append(f'features do modelo atual ausentes neste conjunto: {ausentes}')
  return {
    'alvo': alvo,
    'datasets': conj.datasets,
    'n_linhas': int(len(df)),
    'locais': sorted(df['_site'].unique()),
    'posicoes': sorted(df['_pos'].unique()),
    'ambientes': {k: int(v) for k, v in df.groupby('_amb')['_site'].nunique().items()},
    'colunas': colunas,
    'candidatas': candidatas,
    'sem_classificacao': sem_classificacao,
    'grupos_identicos': _grupos_identicos(df, numericas),
    'modelo_fora_do_tr069': [m for m in F.MODELO_ATUAL if classe_de.get(m) not in (None, 'tr069')],
    'contagem_por_classe': contagem,
    'avisos': avisos,
  }


def elegiveis(inv: dict) -> list:
  repetidas = set()
  for grupo in inv['grupos_identicos']:
    repetidas.update(grupo[1:])
  return [c['coluna'] for c in inv['colunas']
          if c['classe'] not in CLASSES_FORA_DOS_AJUSTES
          and not c['vazamento'] and not c['constante']
          and c['cobertura'] >= COBERTURA_MIN
          and c['tipo'] != 'categorica_alta'
          and c['coluna'] not in repetidas]


def matriz(df: pd.DataFrame, colunas: list) -> pd.DataFrame:
  partes = []
  for coluna in colunas:
    serie = df[coluna]
    if pd.api.types.is_numeric_dtype(serie):
      partes.append(serie.astype(float).rename(coluna))
    else:
      partes.append(pd.get_dummies(serie.astype('string'), prefix=coluna, dtype=float))
  return pd.concat(partes, axis=1)


def assert_sem_vazamento(colunas, vazadas) -> None:
  proibidas = sorted(set(colunas) & set(vazadas))
  if proibidas:
    raise AssertionError(f'colunas com vazamento chegaram a um ajuste: {proibidas}')


def _modelo(arvores: int) -> Pipeline:
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=arvores, min_samples_leaf=2, n_jobs=-1, random_state=42)),
  ])


def _logo(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1):
  """LOGO por local de coleta. Devolve (R² por local, y real, y previsto fora do fold)."""
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return {}, [], []
  sub = df[df[y_col].notna()].reset_index(drop=True)
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  por_local, reais, previstos = {}, [], []
  for fold in outer_logo_folds(X, y, sub['_site']):
    if len(fold.y_test) < min_teste or len(fold.y_train) < min_treino:
      continue
    previsto = _modelo(arvores or ARVORES).fit(fold.X_train, fold.y_train).predict(fold.X_test)
    por_local[fold.test_site] = float(r2_score(fold.y_test, previsto))
    reais.extend(fold.y_test.tolist())
    previstos.extend(previsto.tolist())
  return por_local, reais, previstos


def r2_por_local(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1) -> dict:
  return _logo(df, colunas, y_col, vazadas, arvores, min_teste, min_treino)[0]


def _resumo(logo, n: int) -> dict:
  """Média por local, mais R² e MAE sobre todas as previsões fora do fold.

  Com poucos locais a média dos R² por fold é dominada pelo local de menor
  variância do alvo; o R² pooled e o MAE não têm esse problema.
  """
  por_local, reais, previstos = logo
  return {'n': n, 'media': round(mean(por_local.values()), 4) if por_local else None,
          'pooled': round(float(r2_score(reais, previstos)), 4) if len(reais) > 1 else None,
          'mae': round(float(mean_absolute_error(reais, previstos)), 4) if reais else None,
          'por_local': {s: round(v, 4) for s, v in sorted(por_local.items())}}


def _leitura(r2: float) -> str:
  if r2 >= PROXY_ALCANCAVEL:
    return 'alcancavel'
  return 'parcial' if r2 >= PROXY_PARCIAL else 'laboratorio'


_POUCOS_LOCAIS = re.compile(r'only (\d+) sites available')


def ajuste(conj: Conjunto, inv: dict) -> dict:
  inicio = time.time()
  df, alvo = conj.df, conj.alvo
  if df['_site'].nunique() < 2:
    raise ValueError(f'o conjunto tem só {df["_site"].nunique()} local de coleta '
                     f'({", ".join(sorted(df["_site"].unique()))}); deixar um local de fora '
                     'precisa de pelo menos 2. Ligue datasets de outro local ou mude o ambiente.')
  ok = elegiveis(inv)
  por_nome = {c['coluna']: c for c in inv['colunas']}
  vazadas = [c['coluna'] for c in inv['colunas'] if c['vazamento']]
  tr069 = [c for c in ok if por_nome[c]['classe'] == 'tr069']
  atual = [c for c in F.MODELO_ATUAL if c in ok]
  avisos = []
  with warnings.catch_warnings(record=True) as capturados:
    warnings.simplefilter('always')
    brutos = {nome: _logo(df, cols, alvo, vazadas)
              for nome, cols in (('atual', atual), ('tr069', tr069), ('tudo', ok))}
    teto = {nome: _resumo(brutos[nome], n) for nome, n in
            (('atual', len(atual)), ('tr069', len(tr069)), ('tudo', len(ok)))}

    ganho = []
    base = brutos['atual'][0]
    if base:
      for coluna in [c for c in inv['candidatas'] if c in ok]:
        r = r2_por_local(df, atual + [coluna], alvo, vazadas)
        deltas = [r[s] - base[s] for s in base if s in r]
        ganho.append({'coluna': coluna, 'delta': round(mean(deltas), 4),
                      'melhora': sum(d > 0 for d in deltas), 'locais': len(deltas)})
    ganho.sort(key=lambda g: -g['delta'])

    proxy = []
    auxiliares = [por_nome[c] for c in ok if por_nome[c]['classe'] in CLASSES_AUXILIARES
                  and por_nome[c]['tipo'] == 'numerica' and por_nome[c]['rho'] is not None]
    auxiliares.sort(key=lambda c: -c['rho'])
    if auxiliares and not tr069:
      avisos.append('nenhuma coluna TR-069 elegível: proxies não calculados')
    for c in auxiliares[:MAX_PROXIES] if tr069 else []:
      r = r2_por_local(df, tr069, c['coluna'], vazadas, arvores=ARVORES_PROXY, min_teste=5, min_treino=20)
      if not r:
        continue
      valores = list(r.values())
      media = mean(valores)
      proxy.append({'coluna': c['coluna'], 'classe': c['classe'], 'rho': c['rho'],
                    'r2': round(media, 4), 'min': round(min(valores), 4), 'max': round(max(valores), 4),
                    'leitura': _leitura(media), 'parece_tr069': min(valores) >= PROXY_TR069})

  for aviso in capturados:
    casou = _POUCOS_LOCAIS.search(str(aviso.message))
    if casou:
      avisos.append(f'só {casou.group(1)} locais de coleta: a dispersão por local não é '
                    'interpretável e a estimativa é instável')
  return {
    'alvo': alvo, 'datasets': conj.datasets, 'locais': inv['locais'], 'posicoes': inv['posicoes'],
    'teto': teto, 'ganho': ganho, 'proxy': proxy,
    'avisos': sorted(set(avisos)), 'segundos': round(time.time() - inicio, 1),
  }
