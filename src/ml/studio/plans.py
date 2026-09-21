"""Planta dos prédios: paredes (CSV) e foto registradas no referencial em cm dos dados.

O registro de cada prédio fica em docs/planta/plantas.json e é gravado pelo modo
de calibração do Studio. Tudo o que sai daqui para o navegador já está em cm.
"""

import hashlib
import io
import json
import os
import threading

import numpy as np
import pandas as pd
from PIL import Image

from ml.core.arquivos import gravar_json_atomico

PLANTA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'planta'))
ORIGENS = ('superior-esquerdo', 'superior-direito', 'inferior-esquerdo', 'inferior-direito')
EIXOS = ('horizontal', 'vertical')
COLUNAS_PAREDE = ['X1_px', 'Y1_px', 'X2_px', 'Y2_px']
EXTENSOES_FOTO = ('.jpg', '.jpeg', '.png')
MARGEM_CM = 60

_lock = threading.Lock()
_fotos = {}


def caminho(nome: str, pasta: str = None) -> str:
  """Resolve um nome de arquivo dentro de docs/planta, recusando qualquer caminho."""
  if not isinstance(nome, str) or not nome or nome != os.path.basename(nome) or nome in ('.', '..'):
    raise ValueError(f'nome de arquivo inválido: {nome!r}')
  return os.path.join(pasta or PLANTA_DIR, nome)


def listar_arquivos(pasta: str = None) -> dict:
  pasta = pasta or PLANTA_DIR
  nomes = sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []
  return {'paredes': [n for n in nomes if n.lower().endswith('.csv')],
          'fotos': [n for n in nomes if n.lower().endswith(EXTENSOES_FOTO)]}


def ler_paredes(path: str) -> np.ndarray:
  df = pd.read_csv(path)
  faltando = [c for c in COLUNAS_PAREDE if c not in df.columns]
  if faltando:
    raise ValueError(f'{os.path.basename(path)}: faltam as colunas {faltando}')
  segmentos = df[COLUNAS_PAREDE].to_numpy(dtype=float)
  if len(segmentos) == 0:
    raise ValueError(f'{os.path.basename(path)}: nenhum segmento')
  return segmentos


def _sinais(origem: str):
  if origem not in ORIGENS:
    raise ValueError(f'origem inválida {origem!r}; esperado uma de {list(ORIGENS)}')
  vertical, horizontal = origem.split('-')
  return (1 if horizontal == 'esquerdo' else -1), (1 if vertical == 'superior' else -1)


def registro_paredes(segmentos: np.ndarray, origem: str, eixo_x: str, W: float, H: float):
  """Devolve (px_para_cm, cm_para_px): o contorno do traçado encaixado no envelope W x H cm."""
  if eixo_x not in EIXOS:
    raise ValueError(f'eixo_x inválido {eixo_x!r}; esperado um de {list(EIXOS)}')
  ux, uy = _sinais(origem)
  xs, ys = segmentos[:, [0, 2]], segmentos[:, [1, 3]]
  X0, X1, Y0, Y1 = xs.min(), xs.max(), ys.min(), ys.max()
  if X1 <= X0 or Y1 <= Y0:
    raise ValueError('o contorno das paredes não tem área')
  Xo = X0 if ux == 1 else X1
  Yo = Y0 if uy == 1 else Y1
  if eixo_x == 'horizontal':
    sx, sy = (X1 - X0) / W, (Y1 - Y0) / H

    def cm_para_px(x, y):
      return Xo + ux * x * sx, Yo + uy * y * sy

    def px_para_cm(X, Y):
      return (X - Xo) / (ux * sx), (Y - Yo) / (uy * sy)
  else:
    sx, sy = (X1 - X0) / H, (Y1 - Y0) / W

    def cm_para_px(x, y):
      return Xo + ux * y * sx, Yo + uy * x * sy

    def px_para_cm(X, Y):
      return (Y - Yo) / (uy * sy), (X - Xo) / (ux * sx)
  return px_para_cm, cm_para_px


def paredes_em_cm(segmentos, origem, eixo_x, W, H) -> list:
  px_para_cm, _ = registro_paredes(segmentos, origem, eixo_x, W, H)
  saida = []
  for X1, Y1, X2, Y2 in segmentos:
    x1, y1 = px_para_cm(X1, Y1)
    x2, y2 = px_para_cm(X2, Y2)
    # `+ 0.0` normaliza o -0.0 que sai de 0 dividido por escala negativa.
    saida.append([round(float(v), 1) + 0.0 for v in (x1, y1, x2, y2)])
  return saida


def papel_das_paredes(origem: str, eixo_x: str) -> list:
  """Matriz 2x2 [[a, b], [c, d]]: papel_x = a*x + b*y, papel_y = c*x + d*y (cm, y para baixo)."""
  ux, uy = _sinais(origem)
  return [[ux, 0], [0, uy]] if eixo_x == 'horizontal' else [[0, ux], [uy, 0]]


def _encaixar(vetor):
  vx, vy = vetor
  if abs(vx) >= abs(vy):
    return (1 if vx > 0 else -1, 0)
  return (0, 1 if vy > 0 else -1)


def papel_da_foto(cantos: list) -> list:
  c0, c1, _, c3 = [np.array(c, dtype=float) for c in cantos]
  ex, ey = _encaixar(c1 - c0), _encaixar(c3 - c0)
  if (ex[0] == 0) == (ey[0] == 0):
    raise ValueError('os cantos não definem dois eixos distintos')
  return [[ex[0], ey[0]], [ex[1], ey[1]]]


def validar_cantos(cantos, largura: int, altura: int) -> list:
  if not isinstance(cantos, (list, tuple)) or len(cantos) != 4:
    raise ValueError('são exigidos exatamente 4 cantos')
  saida = []
  for canto in cantos:
    if (not isinstance(canto, (list, tuple)) or len(canto) != 2
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in canto)):
      raise ValueError(f'canto inválido: {canto!r}')
    x, y = float(canto[0]), float(canto[1])
    if not (0 <= x <= largura and 0 <= y <= altura):
      raise ValueError(f'canto {canto!r} fora da imagem ({largura} x {altura})')
    saida.append([round(x, 1), round(y, 1)])
  return saida


def coeficientes_perspectiva(destino, origem) -> list:
  """Coeficientes do PIL PERSPECTIVE: levam cada ponto de `destino` (saída) ao de `origem` (foto)."""
  A, b = [], []
  for (u, v), (x, y) in zip(destino, origem):
    A.append([u, v, 1, 0, 0, 0, -u * x, -v * x])
    b.append(x)
    A.append([0, 0, 0, u, v, 1, -u * y, -v * y])
    b.append(y)
  try:
    return np.linalg.solve(np.array(A, dtype=float), np.array(b, dtype=float)).tolist()
  except np.linalg.LinAlgError:
    raise ValueError('os 4 cantos não formam um quadrilátero válido') from None


def endireitar(path: str, cantos: list, W: float, H: float, margem: int = MARGEM_CM,
               cache: bool = True) -> bytes:
  """PNG em que 1 px = 1 cm; o pixel (u, v) é o ponto (u - margem, v - margem) do envelope.

  Pré-visualizações da calibração passam cache=False: cada clique geraria uma entrada nova.
  """
  chave = (path, os.path.getmtime(path), json.dumps(cantos), W, H, margem)
  if cache and chave in _fotos:
    return _fotos[chave]
  destino = [(margem, margem), (W + margem, margem), (W + margem, H + margem), (margem, H + margem)]
  coefs = coeficientes_perspectiva(destino, cantos)
  tamanho = (int(round(W + 2 * margem)), int(round(H + 2 * margem)))
  with Image.open(path) as foto:
    saida = foto.convert('RGBA').transform(tamanho, Image.Transform.PERSPECTIVE, coefs,
                                           Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
  buffer = io.BytesIO()
  saida.save(buffer, 'PNG')
  if cache:
    _fotos[chave] = buffer.getvalue()
  return buffer.getvalue()


def tamanho_imagem(path: str):
  with Image.open(path) as foto:
    return foto.size


def carregar_config(pasta: str = None):
  path = os.path.join(pasta or PLANTA_DIR, 'plantas.json')
  if not os.path.exists(path):
    return {}, None
  try:
    with open(path, encoding='utf-8') as handle:
      config = json.load(handle)
    if not isinstance(config, dict):
      raise ValueError('o topo precisa ser um objeto')
    return config, None
  except (OSError, ValueError) as erro:
    return {}, f'plantas.json ilegível: {erro}'


def montar_plantas(envelopes: dict, pasta: str = None):
  """Devolve (plantas por prédio com envelope, avisos gerais)."""
  config, erro = carregar_config(pasta)
  avisos_gerais = [erro] if erro else []
  avisos_gerais += [f'{p!r} está em plantas.json mas não tem envelope nos dados ativos'
                    for p in config if p not in envelopes]
  saida = {}
  for predio, env in envelopes.items():
    W, H = env['w'], env['h']
    item = {'paredes': None, 'papel': None, 'foto': None, 'margem_cm': MARGEM_CM,
            'calibracao': {'paredes': None, 'foto': None}, 'avisos': []}
    cfg = config.get(predio) or {}
    p = cfg.get('paredes')
    if p:
      try:
        segmentos = ler_paredes(caminho(p['arquivo'], pasta))
        item['paredes'] = paredes_em_cm(segmentos, p['origem'], p['eixo_x'], W, H)
        item['papel'] = papel_das_paredes(p['origem'], p['eixo_x'])
        item['calibracao']['paredes'] = {k: p[k] for k in ('arquivo', 'origem', 'eixo_x')}
      except (OSError, ValueError, KeyError) as e:
        item['avisos'].append(f'paredes ignoradas: {e}')
    f = cfg.get('foto')
    if f:
      try:
        path = caminho(f.get('arquivo', ''), pasta)
        if not os.path.exists(path):
          raise ValueError(f"{f.get('arquivo')!r} não encontrado em docs/planta/")
        item['calibracao']['foto'] = {'arquivo': f['arquivo'], 'cantos': f.get('cantos')}
        if f.get('cantos'):
          cantos = validar_cantos(f['cantos'], *tamanho_imagem(path))
          # Resolve o papel antes de tocar em item['foto']/['papel']: se falhar, nada muda.
          papel = papel_da_foto(cantos) if item['papel'] is None else item['papel']
          versao = hashlib.sha1(json.dumps(cantos).encode()).hexdigest()[:8]
          item['foto'] = {'url': f'api/plan/{predio}/foto.png?v={versao}', 'margem_cm': MARGEM_CM}
          item['papel'] = papel
      except (OSError, ValueError) as e:
        item['avisos'].append(f'foto ignorada: {e}')
    saida[predio] = item
  return saida, avisos_gerais


def salvar_calibracao(predio: str, paredes, foto, pasta: str = None) -> None:
  """Valida e grava a entrada do prédio em plantas.json. `None` mantém o que já existe."""
  novo = {}
  if paredes is not None:
    if paredes.get('origem') not in ORIGENS or paredes.get('eixo_x') not in EIXOS:
      raise ValueError('origem ou eixo_x inválidos')
    ler_paredes(caminho(paredes.get('arquivo', ''), pasta))
    novo['paredes'] = {k: paredes[k] for k in ('arquivo', 'origem', 'eixo_x')}
  if foto is not None:
    path = caminho(foto.get('arquivo', ''), pasta)
    if not os.path.exists(path) or not path.lower().endswith(EXTENSOES_FOTO):
      raise ValueError(f"foto {foto.get('arquivo')!r} não encontrada em docs/planta/")
    cantos = foto.get('cantos')
    if cantos is not None:
      cantos = validar_cantos(cantos, *tamanho_imagem(path))
      coeficientes_perspectiva([(0, 0), (1, 0), (1, 1), (0, 1)], cantos)
    novo['foto'] = {'arquivo': foto['arquivo'], 'cantos': cantos}
  if not novo:
    raise ValueError('nada para salvar')
  with _lock:
    config, erro = carregar_config(pasta)
    if erro:
      raise ValueError(erro)
    entrada = config.get(predio) or {}
    entrada.update(novo)
    config[predio] = entrada
    gravar_json_atomico(os.path.join(pasta or PLANTA_DIR, 'plantas.json'), config)
