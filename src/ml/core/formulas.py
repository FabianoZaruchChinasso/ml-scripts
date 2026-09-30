"""Fórmulas de derivadas escritas no QoE Studio, interpretadas sem eval.

A gramática é a de uma expressão aritmética: números, nomes de coluna,
+ - * / **, parênteses, sinal e as funções de FUNCOES. Qualquer outra construção
do Python (atributo, índice, chamada arbitrária, comparação, lambda...) é recusada
na análise, antes de qualquer dado ser tocado.
"""

import ast

import numpy as np
import pandas as pd

MAX_TAMANHO = 300
MAX_EXPOENTE = 4


def _positivo(serie):
  return serie.where(serie > 0)


FUNCOES = {
  'log10': lambda s: np.log10(_positivo(s)),
  'log': lambda s: np.log(_positivo(s)),
  'sqrt': lambda s: np.sqrt(s.where(s >= 0)),
  'abs': lambda s: s.abs(),
}

_BINARIOS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.Pow: '**'}


def analisar(formula: str):
  """Valida a fórmula e devolve (árvore, colunas usadas, em ordem de aparição)."""
  if not isinstance(formula, str) or not formula.strip():
    raise ValueError('fórmula vazia')
  if len(formula) > MAX_TAMANHO:
    raise ValueError(f'fórmula com mais de {MAX_TAMANHO} caracteres')
  try:
    arvore = ast.parse(formula.strip(), mode='eval')
  except SyntaxError as erro:
    raise ValueError(f'fórmula inválida: {erro.msg}') from None
  colunas = []

  def visitar(no):
    if isinstance(no, ast.Expression):
      return visitar(no.body)
    if isinstance(no, ast.BinOp) and type(no.op) in _BINARIOS:
      if isinstance(no.op, ast.Pow) and not (isinstance(no.right, ast.Constant)
                                             and isinstance(no.right.value, (int, float))
                                             and abs(no.right.value) <= MAX_EXPOENTE):
        raise ValueError(f'expoente precisa ser um número entre -{MAX_EXPOENTE} e {MAX_EXPOENTE}')
      visitar(no.left)
      visitar(no.right)
      return
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
      visitar(no.operand)
      return
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)) and not isinstance(no.value, bool):
      return
    if isinstance(no, ast.Name):
      if no.id in FUNCOES:
        raise ValueError(f'{no.id} é função: use {no.id}(...)')
      if no.id not in colunas:
        colunas.append(no.id)
      return
    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id in FUNCOES:
      if len(no.args) != 1 or no.keywords:
        raise ValueError(f'{no.func.id} recebe exatamente um argumento')
      visitar(no.args[0])
      return
    raise ValueError(f'construção não permitida na fórmula: {type(no).__name__}. '
                     f'Use números, colunas, + - * / **, parênteses e {", ".join(FUNCOES)}.')

  visitar(arvore)
  if not colunas:
    raise ValueError('a fórmula precisa usar pelo menos uma coluna')
  return arvore, colunas


def calcular(formula: str, df: pd.DataFrame) -> pd.Series:
  """Avalia a fórmula linha a linha. Divisão por zero e log/sqrt fora do domínio viram NaN."""
  arvore, colunas = analisar(formula)
  faltando = [c for c in colunas if c not in df.columns]
  if faltando:
    raise ValueError(f'colunas que não existem no conjunto: {faltando}')

  def valor(no):
    if isinstance(no, ast.Expression):
      return valor(no.body)
    if isinstance(no, ast.Constant):
      return float(no.value)
    if isinstance(no, ast.Name):
      return pd.to_numeric(df[no.id], errors='coerce').astype(float)
    if isinstance(no, ast.UnaryOp):
      v = valor(no.operand)
      return -v if isinstance(no.op, ast.USub) else v
    if isinstance(no, ast.Call):
      return FUNCOES[no.func.id](_serie(valor(no.args[0])))
    a, b = valor(no.left), valor(no.right)
    if isinstance(no.op, ast.Add):
      return a + b
    if isinstance(no.op, ast.Sub):
      return a - b
    if isinstance(no.op, ast.Mult):
      return a * b
    if isinstance(no.op, ast.Div):
      return a / (b.replace(0, np.nan) if isinstance(b, pd.Series) else (np.nan if b == 0 else b))
    return a ** b

  def _serie(v):
    return v if isinstance(v, pd.Series) else pd.Series(v, index=df.index, dtype=float)

  with np.errstate(all='ignore'):
    saida = _serie(valor(arvore))
  return saida.replace([np.inf, -np.inf], np.nan).astype(float)
