"""Planta dos prédios: paredes (CSV) e foto registradas no referencial em cm dos dados.

O registro de cada prédio fica em docs/planta/plantas.json e é gravado pelo modo
de calibração do Studio. Tudo o que sai daqui para o navegador já está em cm.
"""

import hashlib
import io
import json
import math
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
COLUNAS_METROS = ['x1', 'y1', 'x2', 'y2']
FORMATOS = ('px', 'metros')
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


def ler_paredes_metros(path: str) -> np.ndarray:
  """Paredes (`type == wall`) de um CSV em metros, devolvidas em cm. Cotas (`dim`) ficam de fora."""
  df = pd.read_csv(path)
  faltando = [c for c in ['type'] + COLUNAS_METROS if c not in df.columns]
  if faltando:
    raise ValueError(f'{os.path.basename(path)}: faltam as colunas {faltando}')
  paredes = df[df['type'].astype(str).str.strip().str.lower() == 'wall']
  if len(paredes) == 0:
    raise ValueError(f'{os.path.basename(path)}: nenhuma linha type=wall')
  return paredes[COLUNAS_METROS].to_numpy(dtype=float) * 100


def _sinais(origem: str):
  if origem not in ORIGENS:
    raise ValueError(f'origem inválida {origem!r}; esperado uma de {list(ORIGENS)}')
  vertical, horizontal = origem.split('-')
  return (1 if horizontal == 'esquerdo' else -1), (1 if vertical == 'superior' else -1)


def registro_paredes(segmentos: np.ndarray, origem: str, eixo_x: str, W: float, H: float,
                     escala: float = None, dx: float = 0.0, dy: float = 0.0):
  """Devolve (px_para_cm, cm_para_px).

  Sem `escala`, o contorno do traçado é esticado no envelope W x H cm. Com `escala`
  (unidades do CSV por cm), o traçado mantém o tamanho e a origem vai para (dx, dy).
  """
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
    sx, sy = (escala, escala) if escala is not None else ((X1 - X0) / W, (Y1 - Y0) / H)

    def cm_para_px(x, y):
      x, y = x - dx, y - dy
      return Xo + ux * x * sx, Yo + uy * y * sy

    def px_para_cm(X, Y):
      return (X - Xo) / (ux * sx) + dx, (Y - Yo) / (uy * sy) + dy
  else:
    sx, sy = (escala, escala) if escala is not None else ((X1 - X0) / H, (Y1 - Y0) / W)

    def cm_para_px(x, y):
      x, y = x - dx, y - dy
      return Xo + ux * y * sx, Yo + uy * x * sy

    def px_para_cm(X, Y):
      return (Y - Yo) / (uy * sy) + dx, (X - Xo) / (ux * sx) + dy
  return px_para_cm, cm_para_px


def paredes_em_cm(segmentos, origem, eixo_x, W, H, escala=None, dx=0.0, dy=0.0) -> list:
  px_para_cm, _ = registro_paredes(segmentos, origem, eixo_x, W, H, escala, dx, dy)
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


def _piso(andar: dict) -> float:
  z = andar.get('z_min')
  return -math.inf if z is None else float(z)


def andar_de(z, andares: list):
  """id do andar de maior `z_min` <= z (`z_min` nulo = sem piso). None se z for nulo ou abaixo de todos."""
  if z is None or (isinstance(z, float) and math.isnan(z)):
    return None
  candidatos = [a for a in andares if _piso(a) <= z]
  return max(candidatos, key=_piso)['id'] if candidatos else None


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


def _deslocamento(p: dict):
  dx, dy = p.get('dx', 0), p.get('dy', 0)
  if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (dx, dy)):
    raise ValueError('dx e dy precisam ser números finitos')
  return float(dx), float(dy)


def ler_registro(p: dict, W: float, H: float, pasta: str = None):
  """(paredes em cm, papel) de uma entrada `paredes` do plantas.json, em px ou em metros."""
  if not isinstance(p, dict):
    raise ValueError('paredes precisa ser um objeto')
  formato = p.get('formato', 'px')
  if formato not in FORMATOS:
    raise ValueError(f'formato inválido {formato!r}; esperado um de {list(FORMATOS)}')
  path = caminho(p['arquivo'], pasta)
  if formato == 'metros':
    dx, dy = _deslocamento(p)
    paredes = paredes_em_cm(ler_paredes_metros(path), p['origem'], p['eixo_x'], W, H,
                            escala=1.0, dx=dx, dy=dy)
  else:
    paredes = paredes_em_cm(ler_paredes(path), p['origem'], p['eixo_x'], W, H)
  return paredes, papel_das_paredes(p['origem'], p['eixo_x'])


def _calibracao_paredes(p: dict) -> dict:
  saida = {k: p[k] for k in ('arquivo', 'origem', 'eixo_x')}
  if p.get('formato', 'px') == 'metros':
    dx, dy = _deslocamento(p)
    saida.update(formato='metros', dx=dx, dy=dy)
  return saida


def _andares_validos(andares) -> bool:
  return (isinstance(andares, list) and len(andares) > 0
          and all(isinstance(a, dict) and a.get('id')
                  and (a.get('z_min') is None
                       or (isinstance(a.get('z_min'), (int, float)) and not isinstance(a.get('z_min'), bool)))
                  for a in andares))


def _item_vazio() -> dict:
  return {'paredes': None, 'papel': None, 'foto': None, 'margem_cm': MARGEM_CM,
          'calibracao': {'paredes': None, 'foto': None}, 'avisos': []}


def _montar_andares(andares: list, env: dict, pasta: str = None) -> dict:
  ordenados = sorted(andares, key=_piso, reverse=True)
  do_roteador = andar_de(env.get('routerZ'), ordenados)
  saida = []
  for a in ordenados:
    item = dict(_item_vazio(), id=a['id'], z_min=a.get('z_min'), roteador=a['id'] == do_roteador)
    p = a.get('paredes')
    if p:
      try:
        item['paredes'], item['papel'] = ler_registro(p, env['w'], env['h'], pasta)
        item['calibracao']['paredes'] = _calibracao_paredes(p)
      except (OSError, ValueError, KeyError, TypeError) as e:
        item['avisos'].append(f'paredes ignoradas: {e}')
    saida.append(item)
  return {'andares': saida, 'avisos': []}


def montar_plantas(envelopes: dict, pasta: str = None):
  """Devolve (plantas por prédio com envelope, avisos gerais).

  Prédio com `andares` válidos vira {'andares': [...], 'avisos': [...]}, um item por andar
  do mais alto para o mais baixo. Os demais saem no formato de sempre.
  """
  config, erro = carregar_config(pasta)
  avisos_gerais = [erro] if erro else []
  avisos_gerais += [f'{p!r} está em plantas.json mas não tem envelope nos dados ativos'
                    for p in config if p not in envelopes]
  saida = {}
  for predio, env in envelopes.items():
    W, H = env['w'], env['h']
    cfg = config.get(predio) or {}
    item = _item_vazio()
    if 'andares' in cfg:
      if _andares_validos(cfg['andares']):
        saida[predio] = _montar_andares(cfg['andares'], env, pasta)
        continue
      item['avisos'].append('andares ignorados: esperado uma lista de objetos com id e z_min numérico ou null')
    p = cfg.get('paredes')
    if p:
      try:
        item['paredes'], item['papel'] = ler_registro(p, W, H, pasta)
        item['calibracao']['paredes'] = _calibracao_paredes(p)
      except (OSError, ValueError, KeyError, TypeError) as e:
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


def _validar_paredes(paredes, pasta: str = None) -> dict:
  """Entrada `paredes` normalizada para gravar; levanta ValueError se algo não fecha."""
  if not isinstance(paredes, dict):
    raise ValueError('paredes precisa ser um objeto')
  formato = paredes.get('formato', 'px')
  if formato not in FORMATOS or paredes.get('origem') not in ORIGENS or paredes.get('eixo_x') not in EIXOS:
    raise ValueError('formato, origem ou eixo_x inválidos')
  novo = {'arquivo': paredes.get('arquivo', ''), 'origem': paredes['origem'], 'eixo_x': paredes['eixo_x']}
  path = caminho(novo['arquivo'], pasta)
  if formato == 'metros':
    dx, dy = _deslocamento(paredes)
    ler_paredes_metros(path)
    novo.update(formato='metros', dx=dx, dy=dy)
  else:
    ler_paredes(path)
  return novo


def _salvar_andar(predio: str, andar: str, paredes, foto, pasta: str = None) -> None:
  if foto is not None:
    raise ValueError('andares não têm foto')
  if paredes is None:
    raise ValueError('nada para salvar')
  novo = _validar_paredes(paredes, pasta)
  with _lock:
    config, erro = carregar_config(pasta)
    if erro:
      raise ValueError(erro)
    andares = (config.get(predio) or {}).get('andares') or []
    alvo = next((a for a in andares if isinstance(a, dict) and a.get('id') == andar), None)
    if alvo is None:
      raise ValueError(f'andar {andar!r} não existe em {predio!r}')
    alvo['paredes'] = novo
    gravar_json_atomico(os.path.join(pasta or PLANTA_DIR, 'plantas.json'), config)


def salvar_calibracao(predio: str, paredes, foto, pasta: str = None, andar: str = None) -> None:
  """Valida e grava a entrada do prédio (ou de um andar dele) em plantas.json. `None` mantém o que já existe."""
  if andar is not None:
    _salvar_andar(predio, andar, paredes, foto, pasta)
    return
  novo = {}
  if paredes is not None:
    novo['paredes'] = _validar_paredes(paredes, pasta)
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
    if 'andares' in entrada:
      raise ValueError(f'{predio!r} tem andares: informe o andar')
    entrada.update(novo)
    config[predio] = entrada
    gravar_json_atomico(os.path.join(pasta or PLANTA_DIR, 'plantas.json'), config)
