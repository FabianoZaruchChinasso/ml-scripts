"""Benchmark de classificadores de "atende" por aplicação, medidos na régua única.

Para cada aplicação de core/aplicacoes.json, o alvo é "atende" (download e upload acima dos
limiares). Os classificadores são avaliados deixando um prédio de fora por vez e comparados
com a referência da régua: o "atende" tirado das previsões de regressão da mesma versão (com
o denominador dela). Responde se classificar direto decide melhor que regredir Mbps e
comparar com o limiar.
"""

import argparse
import os
import sys
import warnings

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import classificacao as core_classificacao
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.splits import inner_logo_splits

ALVO_DN, ALVO_UP = 'speedtest_down_mbps', 'speedtest_up_mbps'
REMOVIDAS = ('--qoe-column', '--class-mode', '--fixed-thresholds', '--group-level', '--features',
             '--test-size', '--cv-folds', '--cv-gap', '--target-column', '--time-column', '--tune-top-k')
REMOVIDAS_FLAG = ('--no-tune', '--plot-confusion')


def build_models(seed: int):
  return {
    "rf": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=seed,
          ),
        ),
      ]
    ),
    "extra_trees": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          ExtraTreesClassifier(
            n_estimators=600,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=seed,
          ),
        ),
      ]
    ),
    "hist_gb": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=8,
            max_iter=400,
            min_samples_leaf=20,
            random_state=seed,
          ),
        ),
      ]
    ),
    "log_reg": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        (
          "clf",
          LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=seed,
          ),
        ),
      ]
    ),
  }


def get_search_space(model_name: str):
  if model_name == "rf":
    return {
      "clf__n_estimators": [300, 500, 800, 1000],
      "clf__max_depth": [None, 8, 12, 16, 24],
      "clf__min_samples_leaf": [1, 2, 4, 8],
      "clf__max_features": ["sqrt", "log2", None],
    }
  if model_name == "extra_trees":
    return {
      "clf__n_estimators": [300, 600, 900, 1200],
      "clf__max_depth": [None, 8, 12, 16, 24],
      "clf__min_samples_leaf": [1, 2, 4, 8],
      "clf__max_features": ["sqrt", "log2", None],
    }
  if model_name == "hist_gb":
    return {
      "clf__learning_rate": [0.01, 0.03, 0.05, 0.08, 0.12],
      "clf__max_depth": [None, 4, 6, 8, 10],
      "clf__max_iter": [200, 300, 400, 600],
      "clf__min_samples_leaf": [10, 20, 40, 80],
      "clf__l2_regularization": [0.0, 1e-4, 1e-3, 1e-2],
    }
  if model_name == "log_reg":
    return {
      "clf__C": [0.01, 0.1, 0.5, 1.0, 3.0, 10.0],
      "clf__solver": ["lbfgs", "newton-cg", "saga"],
    }
  raise ValueError(f"No search space defined for model: {model_name}")


def parse_args():
  parser = argparse.ArgumentParser(description='Benchmark de classificadores de "atende" por aplicação')
  parser.add_argument('--datasets', default='',
                      help='Nomes de arquivo em data/, separados por vírgula (padrão: o conjunto canônico)')
  parser.add_argument('--modelo', default='', help='Versão de core/modelos.json (padrão: a ativa)')
  parser.add_argument('--aplicacoes', default='',
                      help='Aplicações separadas por vírgula (padrão: todas de core/aplicacoes.json)')
  parser.add_argument('--tune', action='store_true', default=False,
                      help='Busca de hiperparâmetros por LOGO interno (lenta com poucos prédios)')
  parser.add_argument('--tune-iter', type=int, default=20, help='Iterações da busca por modelo')
  parser.add_argument('--seed', type=int, default=42, help='Semente')
  parser.add_argument('--csv', default=None, help='REMOVIDO; use --datasets')
  for flag in REMOVIDAS:
    parser.add_argument(flag, default=None, help='REMOVIDO')
  for flag in REMOVIDAS_FLAG:
    parser.add_argument(flag, action='store_true', default=None, help='REMOVIDO')
  return parser.parse_args()


def ajuste_com_busca(nome_modelo: str, tune_iter: int, seed: int):
  def ajustar(estimador, fold):
    busca = RandomizedSearchCV(estimator=clone(estimador), param_distributions=get_search_space(nome_modelo),
                               n_iter=tune_iter, scoring='balanced_accuracy',
                               cv=inner_logo_splits(fold.train_site_ids), n_jobs=-1, random_state=seed,
                               refit=True)
    return busca.fit(fold.X_train, fold.y_train).best_estimator_
  return ajustar


def imprimir(app: str, limiares: dict, df, linhas) -> None:
  sites = sorted(df['_site'].unique())
  print(f"\n{app} (download >= {limiares['dn']}, upload >= {limiares['up']}): "
        f"{len(df)} linhas, {int(df['_atende'].sum())} atendem")
  print(f"  {'modelo':22s} {'pooled':>8s} {'90%':>17s} " + ' '.join(f'{s:>13s}' for s in sites))
  for nome, r in linhas:
    faixa = f"{r['intervalo'][0]:.3f} a {r['intervalo'][1]:.3f}" if r['intervalo'] else '-'
    pooled = f"{r['pooled']:.3f}" if r['pooled'] is not None else '-'
    locais = ' '.join(f"{r['por_local'][s]:13.3f}" if s in r['por_local'] else f"{'-':>13s}" for s in sites)
    print(f'  {nome:22s} {pooled:>8s} {faixa:>17s} {locais}')


def main():
  args = parse_args()
  if args.csv is not None:
    raise SystemExit('--csv saiu: use --datasets com nomes de data/ (padrão: o conjunto canônico)')
  for flag in REMOVIDAS + REMOVIDAS_FLAG:
    if getattr(args, flag.lstrip('-').replace('-', '_')) is not None:
      print(f'WARNING: {flag} saiu; o alvo agora é "atende" por aplicação (core/aplicacoes.json) '
            'e a carga é a canônica.')
  np.random.seed(args.seed)

  registro = core_modelos.carregar()
  nome = args.modelo or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'--modelo {nome!r} não existe; versões: {sorted(registro["versoes"])}')
  ids = [x for x in args.datasets.split(',') if x] or None
  tabela = core_features.carregar_tabela()
  conj_dn = core_carga.carregar(ALVO_DN, ids=ids, tabela=tabela)
  conj_up = core_carga.carregar(ALVO_UP, ids=ids, tabela=tabela)
  vazadas = [c for c, k in conj_dn.classes.items() if k is not None and k.vazamento]
  pedidas = registro['versoes'][nome]['features']
  features = [f for f in pedidas if f in conj_dn.df.columns and f not in vazadas]
  fora = [f for f in pedidas if f not in features]
  print(f'Modelo {nome}: {len(features)} features' + (f'; fora da conta (vazamento ou ausentes): {fora}' if fora else ''))
  print(f'Datasets: {conj_dn.datasets}')

  # Referência: as previsões de regressão da régua, calculadas uma vez para todas as aplicações.
  vazadas_up = [c for c, k in conj_up.classes.items() if k is not None and k.vazamento]
  prev_dn = core_avaliacao.avaliar(conj_dn, features, vazadas, com_previsoes=True,
                                   denominador=core_modelos.denominador_de(registro, nome, ALVO_DN))[1]
  prev_up = core_avaliacao.avaliar(conj_up, [f for f in features if f not in vazadas_up], vazadas_up,
                                   com_previsoes=True,
                                   denominador=core_modelos.denominador_de(registro, nome, ALVO_UP))[1]

  aplicacoes = core_aplicacoes.carregar()
  pedidas_apps = [a for a in args.aplicacoes.split(',') if a] or list(aplicacoes)
  desconhecidas = [a for a in pedidas_apps if a not in aplicacoes]
  if desconhecidas:
    raise SystemExit(f'aplicações desconhecidas: {desconhecidas}; disponíveis: {list(aplicacoes)}')
  modelos = build_models(args.seed)
  for app in pedidas_apps:
    limiares = aplicacoes[app]
    df = core_classificacao.alvo_atende(conj_dn, conj_up, limiares)
    if df['_atende'].nunique() < 2:
      print(f'\n{app}: só uma classe no "atende" real; fora da tabela')
      continue
    linhas = [('régua (regressão)', core_classificacao.resumir_classe(
      core_classificacao.referencia_regua(prev_dn, prev_up, limiares)))]
    for nome_modelo, estimador in modelos.items():
      ajustar = ajuste_com_busca(nome_modelo, args.tune_iter, args.seed) if args.tune else None
      with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter('always')
        prev = core_classificacao.prever_classe_fora_do_fold(df, features, vazadas, estimador, ajustar=ajustar)
      for aviso in avisos:
        if 'pulado' in str(aviso.message):
          print(f'  aviso ({nome_modelo}): {aviso.message}')
      linhas.append((nome_modelo, core_classificacao.resumir_classe(prev)))
    imprimir(app, limiares, df, linhas)


if __name__ == '__main__':
  main()
