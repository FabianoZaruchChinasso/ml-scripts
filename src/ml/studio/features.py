"""Análise das views Features e Modelos: inventário, teto, ganho +1, proxies e versões.

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
from ml.core.data import descartar_testes_falhos
from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_site_id
from ml.core.splits import COMFORTABLE_SITES, outer_logo_folds

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
# Diferença de R² abaixo disto é ruído com os poucos locais de coleta de hoje.
RUIDO_R2 = 0.02
UNIDADES = {'speedtest_down_mbps': 'Mbps', 'speedtest_up_mbps': 'Mbps', 'latency_ms': 'ms', 'jitter_ms': 'ms'}
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
  catalogo: tuple = F.CATALOGO


def preparar(frames: dict, alvo: str, tabela: dict, ambiente: str = None, catalogo=None) -> Conjunto:
  """Junta os frames, descarta linhas sem alvo/local e calcula as derivadas.

  `ambiente` ('domestico' ou 'corporativo') restringe o conjunto a esse tipo de
  local de coleta; None mantém todos. `catalogo` é o de derivadas (padrão: o curado
  mais as desenhadas no Studio, F.catalogo_completo()).
  """
  catalogo = F.catalogo_completo() if catalogo is None else tuple(catalogo)
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
  df, falhos = descartar_testes_falhos(df, alvo)
  if falhos:
    avisos.append(f'{falhos} testes que falharam ({alvo} = 0) descartados')

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

  df, avisos_derivadas = F.aplicar_derivadas(df, catalogo)
  avisos += avisos_derivadas

  derivadas = {d.nome: d for d in catalogo}
  classes = {}
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    if coluna in derivadas:
      classes[coluna] = F.classificar_derivada(derivadas[coluna], tabela)
    else:
      classes[coluna] = F.classificar(coluna, tabela)
  return Conjunto(df, alvo, sorted(frames), classes, tabela, avisos, catalogo)


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


def inventario(conj: Conjunto, modelo=F.MODELO_ATUAL) -> dict:
  """`modelo` é a lista de features da versão ativa (ver core/modelos.py)."""
  modelo = list(modelo)
  df, alvo = conj.df, conj.alvo
  derivadas = {d.nome: d for d in conj.catalogo}
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
      # Derivada desenhada no Studio que não passou no critério de aceite:
      # pode ser escolhida à mão, mas fica fora do teto, do ganho e do desenho automático.
      'hipotese': coluna in derivadas and derivadas[coluna].status == 'hipotese',
      'pendente': c.pendente,
      'formula': derivadas[coluna].formula if coluna in derivadas else None,
      'cobertura': cobertura,
      'cobertura_por_ds': {ds: round(float(v), 3) for ds, v in cobertura_ds[coluna].items()},
      'constante': bool(constante), 'tipo': tipo, 'rho': rho,
      'no_modelo': coluna in modelo,
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
  ausentes = [m for m in modelo if m not in df.columns]
  if ausentes:
    avisos.append(f'features do modelo ativo ausentes neste conjunto: {ausentes}')
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
    'modelo': modelo,
    'modelo_fora_do_tr069': [m for m in modelo if classe_de.get(m) not in (None, 'tr069')],
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
          and not c.get('hipotese')
          and c['coluna'] not in repetidas]


_FORA_DO_ASSISTENTE = {'identificador', 'alvo'}


def _motivo_bloqueio(c: dict, repetidas: set):
  if c['vazamento']:
    return 'vazamento: medida durante o teste'
  if c['classe'] != 'tr069':
    return f'fora do TR-069 ({c["classe"]})'
  if c.get('hipotese'):
    return 'hipótese: não passou no teste de aceite'
  if c['constante']:
    return 'constante neste conjunto'
  if c['cobertura'] < COBERTURA_MIN:
    return 'cobertura baixa'
  if c['tipo'] == 'categorica_alta':
    return 'categórica com muitos valores'
  if c['coluna'] in repetidas:
    return 'idêntica a outra coluna'
  return None


def lista_assistente(inv: dict, catalogo) -> list:
  """Colunas do assistente. `liberada` = TR-069 elegível; o resto vem com o motivo.

  O front mostra as liberadas e as que estiverem marcadas no rascunho; uma
  bloqueada pode ser desmarcada, nunca marcada de novo.
  """
  derivadas = {d.nome: d for d in catalogo}
  repetidas = set()
  for grupo in inv['grupos_identicos']:
    repetidas.update(grupo[1:])
  saida = []
  for c in inv['colunas']:
    if c['classe'] in _FORA_DO_ASSISTENTE:
      continue
    motivo = _motivo_bloqueio(c, repetidas)
    d = derivadas.get(c['coluna'])
    saida.append({'coluna': c['coluna'], 'liberada': motivo is None, 'motivo': motivo,
                  'classe': c['classe'], 'tipo': c['tipo'], 'vazamento': c['vazamento'],
                  'derivada': c['derivada'], 'hipotese': bool(c.get('hipotese')),
                  'pendente': c['pendente'], 'no_modelo': c['no_modelo'],
                  'descricao': d.descricao if d else c['parametro'],
                  'cobertura': c['cobertura'], 'rho': c['rho']})
  return sorted(saida, key=lambda c: c['coluna'])


# Movida para core/features.py: scripts de treino fora do Studio (regression_mlflow.py)
# também precisam converter categóricas em one-hot quando uma versão as usa.
matriz = F.matriz


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
  """LOGO por local de coleta. Devolve (R² por local, y real, y previsto, MAE por local)."""
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return {}, [], [], {}
  sub = df[df[y_col].notna()].reset_index(drop=True)
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  por_local, reais, previstos, mae_local = {}, [], [], {}
  for fold in outer_logo_folds(X, y, sub['_site']):
    if len(fold.y_test) < min_teste or len(fold.y_train) < min_treino:
      continue
    previsto = _modelo(arvores or ARVORES).fit(fold.X_train, fold.y_train).predict(fold.X_test)
    por_local[fold.test_site] = float(r2_score(fold.y_test, previsto))
    mae_local[fold.test_site] = float(mean_absolute_error(fold.y_test, previsto))
    reais.extend(fold.y_test.tolist())
    previstos.extend(previsto.tolist())
  return por_local, reais, previstos, mae_local


def r2_por_local(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1) -> dict:
  return _logo(df, colunas, y_col, vazadas, arvores, min_teste, min_treino)[0]


def _resumo(logo, n: int) -> dict:
  """Média por local, mais R² e MAE sobre todas as previsões fora do fold.

  Com poucos locais a média dos R² por fold é dominada pelo local de menor
  variância do alvo; o R² pooled e o MAE não têm esse problema.
  """
  por_local, reais, previstos, mae_local = logo
  return {'n': n, 'media': round(mean(por_local.values()), 4) if por_local else None,
          'pooled': round(float(r2_score(reais, previstos)), 4) if len(reais) > 1 else None,
          'mae': round(float(mean_absolute_error(reais, previstos)), 4) if reais else None,
          'por_local': {s: round(v, 4) for s, v in sorted(por_local.items())},
          'mae_por_local': {s: round(v, 4) for s, v in sorted(mae_local.items())}}


def _leitura(r2: float) -> str:
  if r2 >= PROXY_ALCANCAVEL:
    return 'alcancavel'
  return 'parcial' if r2 >= PROXY_PARCIAL else 'laboratorio'


_POUCOS_LOCAIS = re.compile(r'only (\d+) sites available')
RHO_REDUNDANTE = 0.9


def _checar_locais(df: pd.DataFrame) -> None:
  if df['_site'].nunique() < 2:
    raise ValueError(f'o conjunto tem só {df["_site"].nunique()} local de coleta '
                     f'({", ".join(sorted(df["_site"].unique()))}); deixar um local de fora '
                     'precisa de pelo menos 2. Ligue datasets de outro local ou mude o ambiente.')


def _avisos_de_locais(capturados) -> list:
  avisos = []
  for aviso in capturados:
    casou = _POUCOS_LOCAIS.search(str(aviso.message))
    if casou:
      avisos.append(f'só {casou.group(1)} locais de coleta: a dispersão por local não é '
                    'interpretável e a estimativa é instável')
  return avisos


def _vazadas(inv: dict) -> list:
  return [c['coluna'] for c in inv['colunas'] if c['vazamento']]


def vazadas_do_conjunto(conj: Conjunto) -> list:
  """Mesma lista de _vazadas, sem precisar montar o inventário inteiro."""
  return [c for c, k in conj.classes.items() if k is not None and k.vazamento]


def avaliar_versao(conj: Conjunto, features, vazadas) -> dict:
  """Como avaliar, mas uma versão salva que usa coluna hoje marcada como vazamento é
  avaliada sem ela, e a lista sai em `removidas_por_vazamento`. Assim a comparação
  continua de pé quando alguém confirma um vazamento depois de a versão existir."""
  removidas = [f for f in features if f in vazadas]
  resumo = avaliar(conj, [f for f in features if f not in vazadas], vazadas)
  resumo['removidas_por_vazamento'] = removidas
  return resumo


def avaliar(conj: Conjunto, features, vazadas) -> dict:
  """LOGO por local de coleta de uma lista de features, como está.

  Feature ausente do conjunto sai da conta e é listada; feature com vazamento
  levanta (assert_sem_vazamento), nunca é descartada em silêncio.
  """
  presentes = [f for f in features if f in conj.df.columns]
  logo = _logo(conj.df, presentes, conj.alvo, vazadas)
  resumo = _resumo(logo, len(presentes))
  resumo['ausentes'] = [f for f in features if f not in conj.df.columns]
  return resumo


def delta_por_local(resumo: dict, base: dict) -> dict:
  deltas = {s: round(v - base['por_local'][s], 4)
            for s, v in resumo['por_local'].items() if s in base['por_local']}
  return {'por_local': deltas,
          'media': round(mean(deltas.values()), 4) if deltas else None,
          'melhora': sum(d > 0 for d in deltas.values()), 'locais': len(deltas),
          'pooled': None if resumo['pooled'] is None or base['pooled'] is None
          else round(resumo['pooled'] - base['pooled'], 4),
          'mae': None if resumo['mae'] is None or base['mae'] is None
          else round(resumo['mae'] - base['mae'], 4)}


def _br_num(valor: float, casas: int) -> str:
  return f'{valor:.{casas}f}'.replace('.', ',')


def _com_sinal(valor: float, casas: int) -> str:
  return ('+' if valor > 0 else '−' if valor < 0 else '') + _br_num(abs(valor), casas)


def veredito(delta: dict, n_locais: int, pendentes=(), unidade: str = '') -> dict:
  """Melhor / empate / pior do rascunho contra a versão ativa, a partir de delta_por_local.

  Melhor exige R² pooled acima do ruído, MAE que não sobe e nenhum local piorando
  além do ruído. `pendentes` são features com vazamento ainda não confirmado.
  """
  dr2, dmae = delta.get('pooled'), delta.get('mae')
  piores = {s: d for s, d in sorted(delta.get('por_local', {}).items()) if d < -RUIDO_R2}
  mae_txt = lambda v: f'{_br_num(abs(v), 1)} {unidade}'.strip()
  if dr2 is None or dmae is None:
    resultado, motivo = 'empate', 'Sem R² pooled ou MAE para comparar.'
  elif dr2 <= -RUIDO_R2:
    resultado, motivo = 'pior', f'O R² caiu {_br_num(-dr2, 2)}.'
  elif dmae > 0 and dr2 < RUIDO_R2:
    resultado, motivo = 'pior', f'O MAE subiu {mae_txt(dmae)} e o R² não subiu além do ruído.'
  elif dr2 >= RUIDO_R2 and dmae <= 0 and not piores:
    resultado = 'melhor'
    mae = f'o MAE caiu {mae_txt(dmae)}' if dmae < 0 else 'o MAE não mudou'
    motivo = f'O R² subiu {_br_num(dr2, 2)} e {mae}, sem piorar nenhum local.'
  elif dr2 >= RUIDO_R2 and piores:
    lista = ', '.join(f'{s} ({_com_sinal(d, 3)})' for s, d in piores.items())
    resultado, motivo = 'empate', f'O R² subiu {_br_num(dr2, 2)}, mas piorou em {lista}.'
  elif dr2 >= RUIDO_R2:
    resultado, motivo = 'empate', f'O R² subiu {_br_num(dr2, 2)}, mas o MAE também subiu {mae_txt(dmae)}.'
  else:
    resultado = 'empate'
    motivo = (f'A diferença de R² ({_com_sinal(dr2, 3)}) é menor que o ruído '
              f'({_br_num(RUIDO_R2, 2)}) com {n_locais} locais.')
  provisorio = []
  if pendentes:
    provisorio.append(f'depende de vazamento não confirmado: {", ".join(pendentes)}')
  if n_locais < COMFORTABLE_SITES:
    provisorio.append(f'só {n_locais} locais de coleta')
  return {'resultado': resultado, 'motivo': motivo, 'provisorio': bool(provisorio),
          'motivos_provisorio': provisorio}


def comparar(conj: Conjunto, inv: dict, versoes: dict, ativo: str) -> dict:
  """Avalia cada versão salva mais as duas referências: TR-069 completo e Tudo."""
  _checar_locais(conj.df)
  inicio = time.time()
  ok = elegiveis(inv)
  por_nome = {c['coluna']: c for c in inv['colunas']}
  vazadas = _vazadas(inv)
  tr069 = [c for c in ok if por_nome[c]['classe'] == 'tr069']
  with warnings.catch_warnings(record=True) as capturados:
    warnings.simplefilter('always')
    resultado = [dict(avaliar_versao(conj, feats, vazadas), nome=nome, ativo=nome == ativo)
                 for nome, feats in versoes.items()]
    referencias = {'tr069': avaliar(conj, tr069, vazadas), 'tudo': avaliar(conj, ok, vazadas)}
  return {'alvo': conj.alvo, 'datasets': conj.datasets, 'locais': sorted(conj.df['_site'].unique()),
          'versoes': resultado, 'referencias': referencias,
          'avisos': sorted(set(_avisos_de_locais(capturados))),
          'segundos': round(time.time() - inicio, 1)}


def correlacoes(df: pd.DataFrame, features) -> dict:
  """Spearman entre as features numéricas; categóricas ficam listadas à parte."""
  numericas = [f for f in features if f in df.columns and pd.api.types.is_numeric_dtype(df[f])
               and df[f].nunique(dropna=True) > 1]
  outras = [f for f in features if f not in numericas]
  if not numericas:
    return {'colunas': [], 'matriz': [], 'fora': outras, 'redundantes': []}
  m = df[numericas].astype(float).corr(method='spearman', min_periods=10)
  redundantes = []
  for i, a in enumerate(numericas):
    for b in numericas[i + 1:]:
      v = m.loc[a, b]
      if pd.notna(v) and abs(v) >= RHO_REDUNDANTE:
        redundantes.append({'a': a, 'b': b, 'rho': round(float(v), 3)})
  matriz = [[None if pd.isna(v) else round(float(v), 3) for v in linha] for linha in m.values]
  return {'colunas': numericas, 'matriz': matriz, 'fora': outras,
          'redundantes': sorted(redundantes, key=lambda r: -abs(r['rho']))}


def ganho_mais_um(conj: Conjunto, base, candidatas, vazadas, progresso=None) -> list:
  """ΔR² médio por local ao somar cada candidata à base, do maior ganho para o menor.

  Features da base com vazamento ou ausentes do conjunto saem da conta. `progresso`
  recebe {'feito', 'total', 'coluna'} depois de cada candidata.
  """
  df, alvo = conj.df, conj.alvo
  base = [c for c in base if c in df.columns and c not in vazadas]
  ref = r2_por_local(df, base, alvo, vazadas)
  ganho = []
  if not ref:
    return ganho
  for i, coluna in enumerate(candidatas, 1):
    r = r2_por_local(df, base + [coluna], alvo, vazadas)
    deltas = [r[s] - ref[s] for s in ref if s in r]
    if deltas:
      ganho.append({'coluna': coluna, 'delta': round(mean(deltas), 4),
                    'melhora': sum(d > 0 for d in deltas), 'locais': len(deltas)})
    if progresso:
      progresso({'feito': i, 'total': len(candidatas), 'coluna': coluna})
  ganho.sort(key=lambda g: -g['delta'])
  return ganho


def ajuste(conj: Conjunto, inv: dict, versoes: dict = None) -> dict:
  """Teto, ganho +1 e proxies. `versoes` (nome -> features) entram no teto ao lado do ativo."""
  inicio = time.time()
  df, alvo = conj.df, conj.alvo
  _checar_locais(df)
  ok = elegiveis(inv)
  por_nome = {c['coluna']: c for c in inv['colunas']}
  vazadas = _vazadas(inv)
  tr069 = [c for c in ok if por_nome[c]['classe'] == 'tr069']
  # O modelo ativo entra como está (inv['modelo']); só o que falta no conjunto sai.
  atual = [c for c in inv['modelo'] if c in df.columns and c not in vazadas]
  avisos = []
  if len(atual) < len([c for c in inv['modelo'] if c in df.columns]):
    avisos.append('o modelo ativo usa colunas marcadas como vazamento; o teto dele foi calculado sem elas: '
                  f'{[c for c in inv["modelo"] if c in vazadas]}')
  with warnings.catch_warnings(record=True) as capturados:
    warnings.simplefilter('always')
    brutos = {nome: _logo(df, cols, alvo, vazadas)
              for nome, cols in (('atual', atual), ('tr069', tr069), ('tudo', ok))}
    teto = {nome: _resumo(brutos[nome], n) for nome, n in
            (('atual', len(atual)), ('tr069', len(tr069)), ('tudo', len(ok)))}
    outras = [dict(avaliar_versao(conj, feats, vazadas), nome=nome)
              for nome, feats in (versoes or {}).items() if list(feats) != inv['modelo']]

    ganho = ganho_mais_um(conj, atual, [c for c in inv['candidatas'] if c in ok], vazadas)

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

  avisos += _avisos_de_locais(capturados)
  return {
    'alvo': alvo, 'datasets': conj.datasets, 'locais': inv['locais'], 'posicoes': inv['posicoes'],
    'teto': teto, 'versoes': outras, 'ganho': ganho, 'proxy': proxy,
    'avisos': sorted(set(avisos)), 'segundos': round(time.time() - inicio, 1),
  }
