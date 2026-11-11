"""Mostra ou troca a versão ativa: o alias 'ativo' do modelo 'qoe-wifi' no Model Registry.

Sem variáveis, mostra a ativa. MODELO=<definição> ativa a versão registrada mais recente dessa definição;
VERSAO=<n> ativa a versão registrada n. É a promoção manual até o portão de promoção existir.

  venv/bin/python src/ml/ativar_mlflow.py
  MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py
  VERSAO=3 venv/bin/python src/ml/ativar_mlflow.py
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import registry_mlflow as core_registry


def _rotulo(versao, definicao) -> str:
  return 'nenhuma' if versao is None else f'{versao} ({definicao})'


def main():
  definicao, numero = os.environ.get('MODELO'), os.environ.get('VERSAO')
  if definicao and numero:
    raise SystemExit('use MODELO ou VERSAO, não os dois')
  if not definicao and not numero:
    try:
      a = core_registry.ativa()
    except core_registry.SemVersaoAtiva as erro:
      raise SystemExit(f'nenhuma versão ativa: {erro}') from erro
    print(f"ativa: versão {a['versao']} de {core_registry.NOME_MODELO} "
          f"(definição {a['definicao']}, run {a['run_id']})")
    return
  if numero:
    if not numero.isdigit():
      raise SystemExit(f'VERSAO={numero!r}: use o número da versão registrada')
    versao = int(numero)
  else:
    try:
      versao = core_registry.versao_da_definicao(definicao)
    except ValueError as erro:
      raise SystemExit(str(erro)) from erro
  try:
    r = core_registry.ativar(versao)
  except ValueError as erro:
    raise SystemExit(str(erro)) from erro
  print(f"{core_registry.NOME_MODELO}@{core_registry.ALIAS}: {_rotulo(r['anterior'], r['definicao_anterior'])}"
        f" -> {_rotulo(r['atual'], r['definicao_atual'])}")


if __name__ == '__main__':
  main()
