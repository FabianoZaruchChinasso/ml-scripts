"""Receitas de derivadas para o assistente: o técnico escolhe a forma e as colunas,
e a fórmula sai daqui, pronta para o teste de aceite de sempre (paralelos.testar)."""

import re

from ml.core import formulas
from ml.core.features import NOME_DERIVADA

MAX_NOME = 40

# id: (rótulo, nº de colunas, fórmula, nome, descrição, dica)
# Na fórmula entram os nomes completos ({a}); no nome, os curtos, sem `router_`.
RECEITAS = {
  'razao': ('Razão A ÷ B', 2, '{a} / {b}', '{a}_por_{b}', 'Razão entre {A} e {B}',
            'Divide dois contadores: o volume de tráfego se cancela.'),
  'diferenca': ('Diferença A − B', 2, '{a} - {b}', '{a}_menos_{b}', 'Diferença entre {A} e {B}', None),
  'fracao': ('Fração A ÷ (A + B)', 2, '{a} / ({a} + {b})', 'fracao_{a}',
             'Fração de {A} no total de {A} e {B}', None),
  'media': ('Média (A + B) ÷ 2', 2, '({a} + {b}) / 2', 'media_{a}_{b}', 'Média entre {A} e {B}', None),
  'produto': ('Produto A × B', 2, '{a} * {b}', '{a}_x_{b}', 'Produto de {A} e {B}', None),
  'por_canal': ('Por canal A ÷ (B × C)', 3, '{a} / ({b} * {c})', '{a}_por_canal',
                '{A} dividido por {B} vezes {C}',
                'Ex.: taxa ÷ (largura de canal × fluxos espaciais).'),
}
_LETRAS = 'abc'


def listar() -> list:
  return [{'id': k, 'rotulo': r[0], 'colunas': r[1], 'dica': r[5]} for k, r in RECEITAS.items()]


def _curto(coluna: str) -> str:
  c = coluna.lower()
  return c[len('router_'):] if c.startswith('router_') else c


def _nome(modelo: str, curtos: dict, existentes) -> str:
  base = re.sub(r'[^a-z0-9_]', '_', modelo.format(**curtos))
  base = re.sub(r'_+', '_', base).strip('_')
  if not base[:1].isalpha():
    base = 'm_' + base
  base = base[:MAX_NOME].rstrip('_')
  nome, i = base, 2
  while nome in existentes:
    sufixo = f'_{i}'
    nome = base[:MAX_NOME - len(sufixo)].rstrip('_') + sufixo
    i += 1
  return nome


def montar(receita: str, colunas, existentes) -> dict:
  """Fórmula, nome livre (fora de `existentes`) e descrição de uma receita."""
  if receita not in RECEITAS:
    raise ValueError(f'receita {receita!r} desconhecida; esperado uma de {list(RECEITAS)}')
  rotulo, n, formula, nome, descricao, _ = RECEITAS[receita]
  colunas = list(colunas)
  if len(colunas) != n or not all(colunas):
    raise ValueError(f'a receita "{rotulo}" usa {n} colunas')
  if len(set(colunas)) != len(colunas):
    raise ValueError('escolha colunas diferentes')
  completos = dict(zip(_LETRAS, colunas))
  curtos = {k: _curto(v) for k, v in completos.items()}
  formula = formula.format(**completos)
  formulas.analisar(formula)
  nome_final = _nome(nome, curtos, set(existentes))
  if not NOME_DERIVADA.match(nome_final):
    raise ValueError(f'nome gerado inválido ({nome_final!r}); escolha colunas com nomes mais descritivos')
  return {'formula': formula, 'nome': nome_final,
          'descricao': descricao.format(**{k.upper(): v for k, v in completos.items()})
          + ' (receita do assistente).'}
