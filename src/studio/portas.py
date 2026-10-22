"""Porta livre em localhost: o Studio nunca se pendura num serviço que já está rodando."""

import socket


def livre(porta: int, host: str = '127.0.0.1') -> bool:
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # Sem isso, conexões em TIME-WAIT de uma execução anterior travam a porta por ~60 s.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      s.bind((host, porta))
    except OSError:
      return False
  return True
