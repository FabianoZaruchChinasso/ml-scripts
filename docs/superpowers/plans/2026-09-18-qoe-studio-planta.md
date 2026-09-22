# QoE Studio: planta da casa (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **POLÍTICA DE COMMIT (override do projeto):** o dono do repositório faz **todos** os commits e pushes.
> Nenhum agente deve executar os passos marcados **"Commit (AÇÃO DO USUÁRIO)"**. Nesses passos, pare, mostre o
> comando e espere.

> **Modelo:** este plano é executado com o **Sonnet**, e quem troca o modelo é o usuário.

**Goal:** a view Planta passa a desenhar os pontos medidos sobre a planta real do prédio. Com as paredes (CSV) e a foto, desenha o vetor sobre a foto esmaecida, com um botão para esconder a foto. Só com a foto, desenha sobre ela. Só com as paredes, desenha o vetor. Sem nenhum dos dois, fica o retângulo de hoje. Há um botão de retrato/paisagem, e um modo de calibração grava o registro em `docs/planta/plantas.json`.

**Architecture:**
- `src/ml/studio/plans.py` converte as paredes para cm, endireita a foto com Pillow (correção de perspectiva) numa imagem em que 1 px = 1 cm, e lê e grava `plantas.json`.
- O payload ganha `plantas`, e `api.py` ganha as rotas `/api/plan/...`.
- `graficos.js` desenha tudo com uma única transformação cm → papel → tela.
- `planta.js` cuida dos modos, dos botões e da calibração.

**Tech Stack:** Python 3.12, numpy, pandas, Pillow, FastAPI, `unittest`, JavaScript sem build (canvas).

**Spec:** `docs/superpowers/specs/2026-09-18-qoe-studio-features-planta-design.md`, seções 8 a 13.

**Pré-requisito:** o plano da fase 1 (`docs/superpowers/plans/2026-09-18-qoe-studio-features.md`) concluído na branch `qoe-studio-features-planta`. Esta fase reaproveita `src/ml/core/arquivos.py`, o `descobertos()` do `data.py`, o `api.py` e os estilos `.btn`, `.btn-pri` e `.card-head` que a fase 1 criou.

---

## Antes de começar

- **O código deste plano já foi validado** numa cópia isolada do repositório: os testes passam, as rotas foram exercitadas com `curl`, e a view foi renderizada com os dados reais nos modos vetor + foto, retrato, paisagem, tema escuro e calibração. **Copie o código literalmente.** Se algo divergir, pare e reporte.
- Rode tudo a partir da raiz do repositório, com `./venv/bin/python`.
- Referencial dos dados: `station_x/y` e o envelope `house_x0 × house_y0` estão em cm. Para a casa, o envelope é 410 × 1386.
- A "matriz papel" (2×2, entradas −1/0/1) leva direções em cm para a orientação do desenho original. Para a casa ela é `[[-1, 0], [0, -1]]`, um giro de 180°. A view atual desenhava sem ela, ou seja, de cabeça para baixo em relação ao papel.
- **Para desligar o servidor**, não use `pkill -f "studio.py"`: o padrão casa com o próprio shell que roda o comando e o mata junto. Encerre o processo pelo ID do job ou com `kill <pid>`.

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `requirements.txt` | alterar | declarar `pillow` |
| `src/ml/studio/plans.py` | criar | registro das paredes, foto endireitada, `plantas.json` |
| `src/ml/studio/data.py` | alterar | payload ganha `plantas` e `plantasAvisos` |
| `src/ml/studio/api.py` | alterar | rotas `/api/plan/...` (o `_payload()` já vem da fase 1) |
| `src/ml/studio/static/graficos.js` | alterar | `drawFloorPlan` reescrito sobre cm → papel → tela |
| `src/ml/studio/static/planta.js` | criar | modos, botões Retrato e Foto ao fundo, calibração |
| `src/ml/studio/static/studio.js` | alterar | `renderPlan` passa a delegar a `planta.js` |
| `src/ml/studio/static/index.html` | alterar | linha de controles, avisos, painel de calibração, script |
| `src/ml/studio/static/styles.css` | alterar | estilos da planta e da calibração |
| `docs/planta/plantas.json` | criar | registro inicial: só as paredes da casa |
| `tests/test_plans.py` | criar | 17 testes |

---

### Task 0: Dependência

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Conferir a branch e o estado**

Run: `git branch --show-current && git status --short`
Expected: `qoe-studio-features-planta`, com a fase 1 já commitada. Só aparecem `?? docs/planta/` e `?? docs/superpowers/...`. Se houver outra coisa, **pare e pergunte**.

- [ ] **Step 2: Declarar o Pillow**

Acrescente ao final de `requirements.txt`:
```
pillow
```

- [ ] **Step 3: Commit (AÇÃO DO USUÁRIO)**

```bash
git add requirements.txt
git commit -m "chore: declara pillow para a planta do Studio"
```

---

### Task 1: Registro da planta no servidor

**Files:**
- Create: `src/ml/studio/plans.py`
- Test: `tests/test_plans.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_plans.py`:
```python
import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import plans as P

SEGMENTOS = np.array([[100, 50, 300, 50], [300, 50, 300, 650], [300, 650, 100, 650],
                      [100, 650, 100, 50], [100, 300, 200, 300]], dtype=float)
W, H = 410.0, 1386.0
COMBOS = list(itertools.product(P.ORIGENS, P.EIXOS))


class TestRegistroParedes(unittest.TestCase):
  def test_origem_vai_para_zero_e_oposto_para_W_H(self):
    cantos = {'superior-esquerdo': (100, 50), 'superior-direito': (300, 50),
              'inferior-esquerdo': (100, 650), 'inferior-direito': (300, 650)}
    opostos = {'superior-esquerdo': (300, 650), 'superior-direito': (100, 650),
               'inferior-esquerdo': (300, 50), 'inferior-direito': (100, 50)}
    for origem, eixo in COMBOS:
      px_para_cm, _ = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      np.testing.assert_allclose(px_para_cm(*cantos[origem]), (0, 0), atol=1e-9, err_msg=origem + eixo)
      np.testing.assert_allclose(px_para_cm(*opostos[origem]), (W, H), atol=1e-9, err_msg=origem + eixo)

  def test_ida_e_volta_e_identidade(self):
    for origem, eixo in COMBOS:
      px_para_cm, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      for x, y in [(0, 0), (58, 75), (410, 1386), (200.5, 700.25)]:
        np.testing.assert_allclose(px_para_cm(*cm_para_px(x, y)), (x, y), atol=1e-9)

  def test_casa_real(self):
    _, cm_para_px = P.registro_paredes(np.array([[725, 360, 810, 660]], float),
                                       'inferior-direito', 'horizontal', W, H)
    np.testing.assert_allclose(cm_para_px(58, 75), (810 - 58 * 85 / 410, 660 - 75 * 300 / 1386))

  def test_papel_acompanha_o_registro(self):
    for origem, eixo in COMBOS:
      _, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      papel = P.papel_das_paredes(origem, eixo)
      zero = np.array(cm_para_px(0, 0))
      for coluna, (x, y) in enumerate([(1, 0), (0, 1)]):
        direcao = np.sign(np.array(cm_para_px(x, y)) - zero)
        self.assertEqual(list(direcao), [papel[0][coluna], papel[1][coluna]], origem + eixo)

  def test_valores_invalidos_levantam(self):
    with self.assertRaises(ValueError):
      P.registro_paredes(SEGMENTOS, 'meio', 'horizontal', W, H)
    with self.assertRaises(ValueError):
      P.registro_paredes(SEGMENTOS, 'superior-esquerdo', 'diagonal', W, H)
    with self.assertRaises(ValueError):
      P.registro_paredes(np.array([[1, 1, 1, 5]], float), 'superior-esquerdo', 'horizontal', W, H)


class TestFoto(unittest.TestCase):
  def test_papel_da_foto(self):
    cantos = [[300, 900], [80, 900], [100, 120], [330, 120]]
    self.assertEqual(P.papel_da_foto(cantos), [[-1, 0], [0, -1]])
    self.assertEqual(P.papel_da_foto([[0, 0], [0, 10], [10, 10], [10, 0]]), [[0, 1], [1, 0]])

  def test_papel_degenerado_levanta(self):
    with self.assertRaises(ValueError):
      P.papel_da_foto([[0, 0], [10, 0], [20, 1], [30, 0]])

  def test_validar_cantos(self):
    self.assertEqual(P.validar_cantos([[1, 2], [3, 4], [5, 6], [7, 8]], 10, 10),
                     [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    for ruim in ([[1, 2]] * 3, [[1, 2], [3, 4], [5, 6], [70, 8]], [[1, 2], [3, 4], [5, 6], [True, 8]]):
      with self.assertRaises(ValueError):
        P.validar_cantos(ruim, 10, 10)

  def test_endireitar_leva_os_cantos_aos_cantos_do_envelope(self):
    pasta = tempfile.mkdtemp()
    try:
      marcas = [(40, 30, (255, 0, 0)), (350, 50, (0, 255, 0)), (370, 260, (0, 0, 255)), (20, 280, (255, 0, 255))]
      img = Image.new('RGB', (400, 300), 'white')
      for x, y, cor in marcas:
        for dx in range(-3, 4):
          for dy in range(-3, 4):
            img.putpixel((x + dx, y + dy), cor)
      path = os.path.join(pasta, 'f.png')
      img.save(path)
      png = P.endireitar(path, [[x, y] for x, y, _ in marcas], 200, 100, margem=10)
      saida = Image.open(__import__('io').BytesIO(png)).convert('RGB')
      self.assertEqual(saida.size, (220, 120))
      for (u, v), (_, _, cor) in zip([(10, 10), (210, 10), (210, 110), (10, 110)], marcas):
        self.assertEqual(saida.getpixel((u, v)), cor)
    finally:
      shutil.rmtree(pasta)

  def test_cantos_colineares_levantam(self):
    with self.assertRaises(ValueError):
      P.coeficientes_perspectiva([(0, 0), (1, 0), (1, 1), (0, 1)], [[0, 0], [1, 1], [2, 2], [3, 3]])


class TestArquivos(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    with open(os.path.join(self.pasta, 'paredes.csv'), 'w') as handle:
      handle.write('Elemento,X1_px,Y1_px,X2_px,Y2_px\nP1,725,360,810,360\nP2,810,360,810,660\nP3,725,660,810,660\n')
    Image.new('RGB', (720, 1280), 'white').save(os.path.join(self.pasta, 'foto.jpeg'))
    self.env = {'casa': {'w': W, 'h': H}}

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _config(self):
    with open(os.path.join(self.pasta, 'plantas.json'), encoding='utf-8') as handle:
      return json.load(handle)

  def test_caminho_recusa_diretorios(self):
    for ruim in ('../x.csv', 'a/b.csv', '', '..'):
      with self.assertRaises(ValueError):
        P.caminho(ruim, self.pasta)

  def test_listar_arquivos(self):
    self.assertEqual(P.listar_arquivos(self.pasta), {'paredes': ['paredes.csv'], 'fotos': ['foto.jpeg']})

  def test_sem_plantas_json_nao_e_erro(self):
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertEqual(avisos, [])
    self.assertIsNone(plantas['casa']['paredes'])

  def test_salvar_e_montar(self):
    P.salvar_calibracao('casa', {'arquivo': 'paredes.csv', 'origem': 'inferior-direito', 'eixo_x': 'horizontal'},
                        None, self.pasta)
    P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg',
                                       'cantos': [[307, 935], [76, 935], [97, 124], [328, 124]]}, self.pasta)
    self.assertEqual(set(self._config()['casa']), {'paredes', 'foto'})
    self.assertEqual(sorted(os.listdir(self.pasta)), ['foto.jpeg', 'paredes.csv', 'plantas.json'])
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    casa = plantas['casa']
    self.assertEqual(casa['papel'], [[-1, 0], [0, -1]])
    self.assertEqual(casa['paredes'][1], [0.0, 1386.0, 0.0, 0.0])
    self.assertTrue(casa['foto']['url'].startswith('api/plan/casa/foto.png?v='))

  def test_foto_sem_cantos_fica_so_na_calibracao(self):
    P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg', 'cantos': None}, self.pasta)
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    self.assertIsNone(plantas['casa']['foto'])
    self.assertEqual(plantas['casa']['calibracao']['foto'], {'arquivo': 'foto.jpeg', 'cantos': None})

  def test_salvar_rejeita_invalidos(self):
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', {'arquivo': 'paredes.csv', 'origem': 'meio', 'eixo_x': 'horizontal'}, None, self.pasta)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', None, {'arquivo': '../foto.jpeg', 'cantos': None}, self.pasta)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg', 'cantos': [[1, 1]] * 4}, self.pasta)
    self.assertFalse(os.path.exists(os.path.join(self.pasta, 'plantas.json')))

  def test_avisos(self):
    with open(os.path.join(self.pasta, 'plantas.json'), 'w') as handle:
      json.dump({'casa': {'foto': {'arquivo': 'sumiu.jpg', 'cantos': None}}, 'galpao': {}}, handle)
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertTrue(any('galpao' in a for a in avisos))
    self.assertTrue(any('sumiu.jpg' in a for a in plantas['casa']['avisos']))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_plans.py -v`
Expected: erro de importação, `ImportError: cannot import name 'plans' from 'ml.studio'`.

- [ ] **Step 3: Criar `plans.py`**

Crie `src/ml/studio/plans.py`:
```python
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
          versao = hashlib.sha1(json.dumps(cantos).encode()).hexdigest()[:8]
          item['foto'] = {'url': f'api/plan/{predio}/foto.png?v={versao}', 'margem_cm': MARGEM_CM}
          if item['papel'] is None:
            item['papel'] = papel_da_foto(cantos)
      except ValueError as e:
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_plans.py -v`
Expected: `Ran 17 tests` e `OK`.

- [ ] **Step 5: Endireitar a foto real, para inspeção visual**

Run:
```bash
./venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from ml.studio import plans as P
png = P.endireitar('docs/planta/casa_roni_planta_baixa.jpeg', [[307.3, 935.0], [76.0, 935.0], [97.5, 124.0], [328.7, 124.0]], 410, 1386)
open('/tmp/foto-endireitada.png', 'wb').write(png); print(len(png))"
```
Expected: um número perto de `900000`. Abra `/tmp/foto-endireitada.png`: a UND.03 aparece com as paredes retas, a sala **em cima** e o hall **à esquerda**, com o texto de cabeça para baixo. Isso é o esperado, porque a imagem está no referencial dos dados; o navegador aplica a matriz papel. Os cantos acima são uma **estimativa** usada só na validação, e a calibração de verdade é feita pelo usuário na Task 5.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/plans.py tests/test_plans.py
git commit -m "feat(studio): registro das paredes, foto endireitada e plantas.json"
```

---

### Task 2: Payload e rotas da planta

**Files:**
- Modify: `src/ml/studio/data.py`
- Modify: `src/ml/studio/api.py`

- [ ] **Step 1: `plantas` no payload**

Em `src/ml/studio/data.py`, substitua a primeira ocorrência de:
```python
import pandas as pd
```
por:
```python
import pandas as pd

from ml.studio.plans import montar_plantas
```

E, no fim de `build_payload`, substitua:
```python
  return {
    'datasets': descriptors,
    'rows': rows,
    'buildings': {k: {'label': v['label']} for k, v in BUILDINGS.items()},
    'envelopes': envelopes,
  }
```
por:
```python
  plantas, plantas_avisos = montar_plantas(envelopes)
  return {
    'datasets': descriptors,
    'rows': rows,
    'buildings': {k: {'label': v['label']} for k, v in BUILDINGS.items()},
    'envelopes': envelopes,
    'plantas': plantas,
    'plantasAvisos': plantas_avisos,
  }
```

- [ ] **Step 2: Imports do `api.py`**

Em `src/ml/studio/api.py`, substitua:
```python
from fastapi.responses import JSONResponse
```
por:
```python
from fastapi.responses import FileResponse, JSONResponse, Response
```

E substitua:
```python
from ml.studio import features as studio_features
from ml.studio.data import build_payload, descobertos
```
por:
```python
from ml.studio import features as studio_features
from ml.studio import plans
from ml.studio.data import BUILDINGS, build_payload, descobertos
```

- [ ] **Step 3: Rotas da planta**

O `api.py` da fase 1 já tem o `_payload()` compartilhado, que as rotas abaixo usam. Em `src/ml/studio/api.py`, substitua:
```python
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
```
por:
```python
def _envelope(predio: str) -> dict:
  env = _payload()['envelopes'].get(predio)
  if env is None:
    raise HTTPException(404, f'prédio {predio!r} sem envelope nos dados')
  return env


@app.get('/api/plan/arquivos')
def plan_arquivos():
  return plans.listar_arquivos()


@app.get('/api/plan/arquivo/{nome}')
def plan_arquivo(nome: str):
  try:
    path = plans.caminho(nome)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if not os.path.exists(path):
    raise HTTPException(404, f'{nome!r} não encontrado em docs/planta/')
  return FileResponse(path)


@app.get('/api/plan/{predio}/paredes')
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str):
  env = _envelope(predio)
  try:
    segmentos = plans.ler_paredes(plans.caminho(arquivo))
    return {'paredes': plans.paredes_em_cm(segmentos, origem, eixo_x, env['w'], env['h']),
            'papel': plans.papel_das_paredes(origem, eixo_x)}
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))


@app.get('/api/plan/{predio}/foto.png')
def plan_foto(predio: str, arquivo: Optional[str] = None, cantos: Optional[str] = None,
              v: Optional[str] = None):
  env = _envelope(predio)
  previa = arquivo is not None
  if previa:
    try:
      numeros = [float(t) for t in (cantos or '').split(',') if t]
    except ValueError:
      raise HTTPException(422, 'cantos inválidos')
    lista = [numeros[i:i + 2] for i in range(0, len(numeros), 2)]
  else:
    calibrada = (_payload()['plantas'].get(predio) or {}).get('calibracao', {}).get('foto') or {}
    arquivo, lista = calibrada.get('arquivo'), calibrada.get('cantos')
    if not arquivo or not lista:
      raise HTTPException(404, 'foto ainda não calibrada')
  try:
    path = plans.caminho(arquivo)
    lista = plans.validar_cantos(lista, *plans.tamanho_imagem(path))
    png = plans.endireitar(path, lista, env['w'], env['h'], cache=not previa)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  return Response(png, media_type='image/png')


class Calibracao(BaseModel):
  paredes: Optional[dict] = None
  foto: Optional[dict] = None


@app.post('/api/plan/{predio}')
def plan_salvar(predio: str, corpo: Calibracao, request: Request):
  _so_local(request)
  if predio not in BUILDINGS:
    raise HTTPException(404, f'prédio {predio!r} desconhecido')
  _envelope(predio)
  try:
    plans.salvar_calibracao(predio, corpo.paredes, corpo.foto)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  dados = _payload()
  dados['plantas'], dados['plantasAvisos'] = plans.montar_plantas(dados['envelopes'])
  return {'plantas': dados['plantas'], 'plantasAvisos': dados['plantasAvisos']}


app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
```

- [ ] **Step 4: Subir o servidor e verificar**

Run (em segundo plano): `./venv/bin/python src/ml/studio.py --port 8100`

Run:
```bash
B=http://127.0.0.1:8100
curl -s $B/api/payload | ./venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print({k:(v['paredes'], v['foto'], v['margem_cm']) for k,v in d['plantas'].items()}, d['plantasAvisos'])"
curl -s $B/api/plan/arquivos; echo
curl -s "$B/api/plan/casa/paredes?arquivo=Coordenadas_CSV_2D_casa_roni_v2.csv&origem=inferior-direito&eixo_x=horizontal" | ./venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print(len(d['paredes']), d['papel'], d['paredes'][0])"
curl -s -w " %{http_code}\n" "$B/api/plan/casa/paredes?arquivo=Coordenadas_CSV_2D_casa_roni_v2.csv&origem=meio&eixo_x=horizontal"
curl -s -w " %{http_code}\n" "$B/api/plan/casa/foto.png"
curl -s -o /dev/null -w "previa %{http_code} %{content_type}\n" "$B/api/plan/casa/foto.png?arquivo=casa_roni_planta_baixa.jpeg&cantos=307.3,935,76,935,97.5,124,328.7,124"
curl -s -o /dev/null -w "original %{http_code} %{content_type}\n" "$B/api/plan/arquivo/casa_roni_planta_baixa.jpeg"
curl -s -w " %{http_code}\n" -X POST $B/api/plan/casa -H 'Content-Type: application/json' -d '{"paredes":{"arquivo":"../x.csv","origem":"inferior-direito","eixo_x":"horizontal"}}'
curl -s -w " %{http_code}\n" -X POST $B/api/plan/galpao -H 'Content-Type: application/json' -d '{}'
```
Expected:
```
{'casa': (None, None, 60), 'cowork-pedra-branca': (None, None, 60)} []
{"paredes":["Coordenadas_CSV_2D_casa_roni_v2.csv"],"fotos":["casa_roni_planta_baixa.jpeg"]}
31 [[-1, 0], [0, -1]] [48.2, 0.0, 410.0, 0.0]
{"detail":"origem inválida 'meio'; esperado uma de ['superior-esquerdo', 'superior-direito', 'inferior-esquerdo', 'inferior-direito']"} 422
{"detail":"foto ainda não calibrada"} 404
previa 200 image/png
original 200 image/jpeg
{"detail":"nome de arquivo inválido: '../x.csv'"} 422
{"detail":"prédio 'galpao' desconhecido"} 404
```
Confira também que `git status --short docs/planta` continua mostrando só `?? docs/planta/`: nenhuma dessas chamadas pode ter criado `plantas.json`.

Pare o servidor (pelo ID do processo; veja "Antes de começar").

- [ ] **Step 5: Suíte completa**

Run: `./venv/bin/python -m unittest discover -s tests -p "test_*.py"`
Expected: `OK`.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/data.py src/ml/studio/api.py
git commit -m "feat(studio): rotas da planta e plantas no payload"
```

---

### Task 3: Desenho da planta em cm

**Files:**
- Modify: `src/ml/studio/static/graficos.js` (o bloco `planta baixa` inteiro)

- [ ] **Step 1: Substituir `drawFloorPlan`**

Em `src/ml/studio/static/graficos.js`, substitua o bloco inteiro:
```javascript
  /* ---------- planta baixa: pontos medidos, sem interpolacao ---------- */
  VENKO.drawFloorPlan = function (canvas, spec) {
    const H = spec.height || 340;
    const { ctx, width } = prepare(canvas, H);
    // Folga suficiente para o raio da maior marca nao vazar o retangulo.
    const pad = 34;
    // O envelope vem em cm; preserva a proporcao real do comodo.
    const scale = Math.min((width - pad * 2) / spec.envelope.w, (H - pad * 2) / spec.envelope.h);
    const ox = (width - spec.envelope.w * scale) / 2;
    const oy = (H - spec.envelope.h * scale) / 2;
    const px = (x) => ox + x * scale;
    const py = (y) => oy + y * scale;

    ctx.strokeStyle = css('--axis');
    ctx.lineWidth = 1.5;
    ctx.strokeRect(px(0), py(0), spec.envelope.w * scale, spec.envelope.h * scale);

    ctx.fillStyle = css('--ink-muted');
    ctx.font = '10.5px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${spec.envelope.w} cm`, px(spec.envelope.w / 2), py(0) - 12);
    ctx.save();
    ctx.translate(px(0) - 13, py(spec.envelope.h / 2));
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${spec.envelope.h} cm`, 0, 0);
    ctx.restore();

    // Roteador: marca de identidade, nunca uma cor de serie.
    const rx = px(spec.envelope.routerX);
    const ry = py(spec.envelope.routerY);
    ctx.strokeStyle = css('--ink-2');
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(rx, ry, 5, 0, Math.PI * 2); ctx.stroke();
    [9, 13].forEach((r) => {
      ctx.beginPath();
      ctx.arc(rx, ry, r, -Math.PI * 0.85, -Math.PI * 0.15);
      ctx.stroke();
    });
    // Rotulo abaixo do icone com halo da superficie: o roteador fica junto da
    // parede, onde quase sempre ha um ponto medido por perto.
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 3;
    ctx.strokeStyle = css('--surface-1');
    ctx.strokeText('roteador', rx, ry + 24);
    ctx.fillStyle = css('--ink-2');
    ctx.fillText('roteador', rx, ry + 24);

    const hits = [];
    spec.points.forEach((p) => {
      const X = px(p.x);
      const Y = py(p.y);
      const r = 6.5 + Math.min(7, Math.sqrt(p.n) * 1.2);  // marcas >= 8px de diametro
      ctx.beginPath(); ctx.arc(X, Y, r + 2, 0, Math.PI * 2);
      ctx.fillStyle = css('--surface-1'); ctx.fill();
      ctx.beginPath(); ctx.arc(X, Y, r, 0, Math.PI * 2);
      ctx.fillStyle = p.color; ctx.fill();
      ctx.fillStyle = css('--ink-1');
      ctx.font = '10px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(Math.round(p.value) + '%', X, Y);
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color });
    });
    return hits;
  };

```
por:
```javascript
  /* ---------- planta baixa: pontos medidos, sem interpolacao ----------
     Tudo chega em cm. `papel` leva o referencial dos dados para a orientacao do
     desenho original; em paisagem/retrato um giro de 90 graus deixa o lado maior
     na horizontal/vertical. Uma unica transformacao serve pontos, paredes e foto. */
  function matrizTela(papel, W, H, orient) {
    const P = papel || [[1, 0], [0, 1]];
    const w = Math.abs(P[0][0] * W + P[0][1] * H);
    const h = Math.abs(P[1][0] * W + P[1][1] * H);
    const girar = orient === 'paisagem' ? h > w : w > h;
    // Giro horario com y para baixo: (x, y) -> (-y, x).
    return girar ? [[-P[1][0], -P[1][1]], [P[0][0], P[0][1]]] : P;
  }

  VENKO.drawFloorPlan = function (canvas, spec) {
    const env = spec.envelope;
    const W = env.w;
    const H = env.h;
    const M = matrizTela(spec.papel, W, H, spec.orient);
    const m = spec.margem || 0;
    const girado = (x, y) => [M[0][0] * x + M[0][1] * y, M[1][0] * x + M[1][1] * y];
    const caixa = [[-m, -m], [W + m, -m], [W + m, H + m], [-m, H + m]].map(([x, y]) => girado(x, y));
    const minX = Math.min(...caixa.map((c) => c[0]));
    const maxX = Math.max(...caixa.map((c) => c[0]));
    const minY = Math.min(...caixa.map((c) => c[1]));
    const maxY = Math.max(...caixa.map((c) => c[1]));
    // Folga suficiente para o raio da maior marca nao vazar o desenho.
    const pad = 34;
    const width = canvas.clientWidth;
    const altura = spec.orient === 'paisagem'
      ? Math.max(220, Math.min(520, Math.round((width - pad * 2) * (maxY - minY) / (maxX - minX) + pad * 2)))
      : (spec.altura || 640);
    const { ctx } = prepare(canvas, altura);
    const s = Math.min((width - pad * 2) / (maxX - minX), (altura - pad * 2) / (maxY - minY));
    const tx = (width - (maxX - minX) * s) / 2 - minX * s;
    const ty = (altura - (maxY - minY) * s) / 2 - minY * s;
    const T = (x, y) => { const g = girado(x, y); return [tx + s * g[0], ty + s * g[1]]; };

    if (spec.foto) {
      const ratio = window.devicePixelRatio || 1;
      ctx.save();
      ctx.setTransform(ratio * s * M[0][0], ratio * s * M[1][0], ratio * s * M[0][1], ratio * s * M[1][1],
                       ratio * tx, ratio * ty);
      ctx.globalAlpha = spec.fotoAlpha;
      if (spec.escuro) {
        if ('filter' in ctx) ctx.filter = 'invert(1) hue-rotate(180deg)';
        else ctx.globalAlpha = Math.min(spec.fotoAlpha, 0.15);
      }
      // A foto endireitada tem 1 px = 1 cm e comeca em (-margem, -margem).
      ctx.drawImage(spec.foto.img, -spec.foto.margem, -spec.foto.margem,
                    W + 2 * spec.foto.margem, H + 2 * spec.foto.margem);
      ctx.restore();
    }

    const quinas = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => T(x, y));
    if (!spec.paredes && !spec.foto) {
      ctx.strokeStyle = css('--axis');
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      quinas.forEach(([X, Y], i) => (i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y)));
      ctx.closePath();
      ctx.stroke();
    }
    if (spec.paredes) {
      ctx.strokeStyle = css('--ink-1');
      ctx.lineWidth = 2;
      ctx.lineCap = 'square';
      ctx.beginPath();
      spec.paredes.forEach(([x1, y1, x2, y2]) => {
        const a = T(x1, y1);
        const b = T(x2, y2);
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
      });
      ctx.stroke();
    }

    // Rotulos fora da caixa com margem: por dentro, cairiam sobre a foto.
    const esq = tx + s * minX;
    const dir = tx + s * maxX;
    const cima = ty + s * minY;
    const baixo = ty + s * maxY;
    const horizontal = M[0][0] !== 0 ? W : H;
    ctx.fillStyle = css('--ink-muted');
    ctx.font = '10.5px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`${horizontal} cm`, (esq + dir) / 2, cima - 12);
    ctx.save();
    ctx.translate(esq - 13, (cima + baixo) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${horizontal === W ? H : W} cm`, 0, 0);
    ctx.restore();

    // Roteador: marca de identidade, nunca uma cor de serie.
    const [rx, ry] = T(env.routerX, env.routerY);
    ctx.strokeStyle = css('--ink-2');
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(rx, ry, 5, 0, Math.PI * 2); ctx.stroke();
    [9, 13].forEach((r) => {
      ctx.beginPath();
      ctx.arc(rx, ry, r, -Math.PI * 0.85, -Math.PI * 0.15);
      ctx.stroke();
    });
    // Rotulo abaixo do icone com halo da superficie: o roteador fica junto da
    // parede, onde quase sempre ha um ponto medido por perto.
    ctx.lineWidth = 3;
    ctx.strokeStyle = css('--surface-1');
    ctx.strokeText('roteador', rx, ry + 24);
    ctx.fillStyle = css('--ink-2');
    ctx.fillText('roteador', rx, ry + 24);

    const hits = [];
    spec.points.forEach((p) => {
      const [X, Y] = T(p.x, p.y);
      const r = 6.5 + Math.min(7, Math.sqrt(p.n) * 1.2);  // marcas >= 8px de diametro
      ctx.beginPath(); ctx.arc(X, Y, r + 2, 0, Math.PI * 2);
      ctx.fillStyle = css('--surface-1'); ctx.fill();
      ctx.beginPath(); ctx.arc(X, Y, r, 0, Math.PI * 2);
      ctx.fillStyle = p.color; ctx.fill();
      // A rampa sequencial e a mesma nos dois temas: a cor do texto segue o fundo, nao o tema.
      ctx.fillStyle = p.value > 55 ? '#ffffff' : '#0b0b0b';
      ctx.font = '10px system-ui, -apple-system, sans-serif';
      ctx.fillText(Math.round(p.value) + '%', X, Y);
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color });
    });
    return hits;
  };

```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/graficos.js && echo ok`
Expected: `ok`

---

### Task 4: `planta.js` e a ligação com o Studio

**Files:**
- Create: `src/ml/studio/static/planta.js`
- Modify: `src/ml/studio/static/studio.js`
- Modify: `src/ml/studio/static/index.html`
- Modify: `src/ml/studio/static/styles.css`

- [ ] **Step 1: Criar `planta.js`**

Crie `src/ml/studio/static/planta.js`:
```javascript
/* planta.js — view Planta: vetor + foto, so foto, so vetor ou retangulo; giro e
   calibracao. studio.js calcula os pontos (os limiares sao dele) e chama render(ctx). */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const ler = (k, padrao) => { try { return localStorage.getItem(k) || padrao; } catch (e) { return padrao; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* modo privado */ } };
  const escuro = () => {
    const tema = document.documentElement.getAttribute('data-theme');
    return tema ? tema === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  };

  const ORIGENS = [['superior-esquerdo', 'superior esquerdo'], ['superior-direito', 'superior direito'],
    ['inferior-esquerdo', 'inferior esquerdo'], ['inferior-direito', 'inferior direito']];
  const ROTULO_MODO = { C: 'vetor + foto', B: 'foto', A: 'vetor', R: 'sem planta' };
  const ALERTA = '<svg class="icon"><use href="#i-alert"/></svg>';

  const st = { ctx: null, orient: ler('qoe-plan-orient', 'paisagem'), foto: ler('qoe-plan-foto', 'on'),
               imgs: {}, hits: {}, cal: null };

  function imagem(url) {
    let img = st.imgs[url];
    if (!img) {
      img = new Image();
      img.onload = () => { if (st.ctx) render(st.ctx); };
      img.src = url;
      st.imgs[url] = img;
    }
    return img.complete && img.naturalWidth ? img : null;
  }

  function modo(pl) {
    if (pl && pl.paredes && pl.foto) return 'C';
    if (pl && pl.foto) return 'B';
    if (pl && pl.paredes) return 'A';
    return 'R';
  }

  function especificacao(p, pl) {
    const md = modo(pl);
    const img = pl && pl.foto ? imagem(pl.foto.url) : null;
    const comFoto = img && (md === 'B' || st.foto === 'on');
    return {
      envelope: p.env, points: p.points,
      paredes: pl ? pl.paredes : null, papel: pl ? pl.papel : null,
      margem: pl && pl.foto ? pl.margem_cm : 0,
      foto: comFoto ? { img, margem: pl.margem_cm } : null,
      fotoAlpha: md === 'B' ? 1 : 0.28, orient: st.orient, escuro: escuro(),
    };
  }

  const tooltip = (h) => `<b>${esc(h.label)}</b>${Math.round(h.value)}% atende · ${esc(h.at)}`;

  function render(ctx) {
    st.ctx = ctx;
    const host = $('#plans');
    $('#planGirar').setAttribute('aria-pressed', String(st.orient === 'retrato'));
    $('#planFoto').setAttribute('aria-pressed', String(st.foto === 'on'));
    $('#planFoto').classList.toggle('hide', !ctx.predios.some((p) => modo(p.planta) === 'C'));
    $('#planAvisos').innerHTML = ctx.avisos.map((a) => `<div class="plan-aviso">${ALERTA}${esc(a)}</div>`).join('');
    host.classList.toggle('paisagem', st.orient === 'paisagem');
    st.hits = {};
    if (!ctx.predios.length) {
      host.innerHTML = '<p class="hint">Nenhum dataset com geometria está ativo.</p>';
      renderCalibracao();
      return;
    }
    host.innerHTML = '';
    // Duas passadas: monta TODO o DOM antes de desenhar. Desenhar durante a
    // montagem mede o canvas enquanto ele ainda e o unico filho do grid — ele
    // fica com backing store da largura inteira e depois encolhe para meia
    // coluna, o que achata os circulos em elipses.
    const pendentes = [];
    ctx.predios.forEach((p) => {
      const pl = p.planta;
      const fora = p.points.filter((q) => q.x < 0 || q.x > p.env.w || q.y < 0 || q.y > p.env.h).length;
      const avisos = (pl ? pl.avisos : []).concat(fora ? [`${fora} ponto(s) fora do envelope de ${p.env.w} × ${p.env.h} cm`] : []);
      const pendente = pl && pl.calibracao.foto && !pl.foto;
      const wrap = document.createElement('div');
      wrap.innerHTML = `<div class="plan-head"><h2>${esc(p.label)} <span>· ${p.env.w}×${p.env.h} cm · ${p.points.length} pontos · ${ROTULO_MODO[modo(pl)]}</span></h2>
        <button class="${pendente ? 'btn-pri' : 'btn'}" data-calibrar="${esc(p.b)}">Calibrar planta</button></div>
        ${avisos.map((a) => `<div class="plan-aviso">${ALERTA}${esc(a)}</div>`).join('')}
        <div class="chartwrap"><canvas></canvas><div class="tooltip"></div></div>`;
      host.appendChild(wrap);
      pendentes.push({ p, pl, wrap });
    });
    pendentes.forEach(({ p, pl, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      st.hits[p.b] = V.drawFloorPlan(canvas, especificacao(p, pl));
      V.attachTooltip(canvas, wrap.querySelector('.tooltip'), () => st.hits[p.b], tooltip);
    });
    renderCalibracao();
  }

  /* ---------------- calibracao ---------------- */
  async function abrirCalibracao(b) {
    const p = st.ctx.predios.find((x) => x.b === b);
    const cal = (p.planta && p.planta.calibracao) || { paredes: null, foto: null };
    const arquivos = await fetch('api/plan/arquivos').then((r) => r.json());
    const cp = cal.paredes || {};
    const cf = cal.foto || {};
    st.cal = { b, arquivos, csv: cp.arquivo || '', origem: cp.origem || 'inferior-direito',
               eixo: cp.eixo_x || 'horizontal', foto: cf.arquivo || '',
               cantos: (cf.cantos || []).map((c) => c.slice()), paredes: null, erro: null, escala: 1 };
    await carregarParedes();
    render(st.ctx);
    $('#planCal').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function carregarParedes() {
    const c = st.cal;
    c.paredes = null;
    c.erro = null;
    if (!c.csv) return;
    const q = new URLSearchParams({ arquivo: c.csv, origem: c.origem, eixo_x: c.eixo });
    const r = await fetch(`api/plan/${encodeURIComponent(c.b)}/paredes?${q}`);
    const corpo = await r.json().catch(() => ({}));
    if (r.ok) c.paredes = corpo;
    else c.erro = typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`;
  }

  // Mesma regra de plans.papel_da_foto: cada eixo vai para o eixo dominante da foto.
  function papelDaFoto(cantos) {
    const encaixar = (dx, dy) => (Math.abs(dx) >= Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)]);
    const ex = encaixar(cantos[1][0] - cantos[0][0], cantos[1][1] - cantos[0][1]);
    const ey = encaixar(cantos[3][0] - cantos[0][0], cantos[3][1] - cantos[0][1]);
    return [[ex[0], ey[0]], [ex[1], ey[1]]];
  }

  function renderCalibracao() {
    const host = $('#planCal');
    const c = st.cal;
    const p = c && st.ctx.predios.find((x) => x.b === c.b);
    if (!p) { st.cal = null; host.innerHTML = ''; host.classList.add('hide'); return; }
    host.classList.remove('hide');
    const passos = ['(0, 0), a origem', `(${p.env.w}, 0)`, `(${p.env.w}, ${p.env.h})`, `(0, ${p.env.h})`];
    const opcoes = (lista, atual, vazio) => `<option value="">${vazio}</option>` +
      lista.map((n) => `<option${n === atual ? ' selected' : ''}>${esc(n)}</option>`).join('');
    const passo = c.cantos.length < 4 ? `Clique no canto <b>${passos[c.cantos.length]}</b> do envelope na foto.`
      : 'Os 4 cantos estão marcados. Confira a pré-visualização.';
    host.innerHTML = `<div class="card"><div class="card-head"><div><h2>Calibrar planta · ${esc(p.label)}</h2>
      <p class="hint">Os cantos são os do envelope dos dados (${p.env.w} × ${p.env.h} cm), a partir da origem. Nada é gravado antes de salvar.</p></div>
      <div><button class="btn" data-cal="cancelar">Cancelar</button> <button class="btn-pri" data-cal="salvar">Salvar calibração</button></div></div>
      ${c.erro ? `<div class="plan-aviso">${ALERTA}${esc(c.erro)}</div>` : ''}
      <div class="cal-grid"><div>
        <div class="controls"><label>Paredes</label><select data-campo="csv">${opcoes(c.arquivos.paredes, c.csv, 'nenhum CSV')}</select>
          <label>Origem</label><select data-campo="origem">${ORIGENS.map(([k, r]) => `<option value="${k}"${k === c.origem ? ' selected' : ''}>${r}</option>`).join('')}</select>
          <label>Eixo x</label><select data-campo="eixo">${['horizontal', 'vertical'].map((k) => `<option${k === c.eixo ? ' selected' : ''}>${k}</option>`).join('')}</select></div>
        <div class="controls"><label>Foto</label><select data-campo="foto">${opcoes(c.arquivos.fotos, c.foto, 'nenhuma foto')}</select>
          <button class="btn" data-cal="desfazer"${c.cantos.length ? '' : ' disabled'}>Desfazer</button>
          <button class="btn" data-cal="recomecar"${c.cantos.length ? '' : ' disabled'}>Recomeçar</button></div>
        ${c.foto ? `<p class="hint">${passo}</p><div class="cal-foto"><canvas id="calFoto"></canvas></div>`
          : '<p class="hint">Sem foto: o registro usa só as paredes.</p>'}
      </div><div><p class="hint">Pré-visualização</p>
        <div class="chartwrap"><canvas id="calPrevia"></canvas><div class="tooltip" id="calTip"></div></div></div></div></div>`;
    desenharFoto();
    desenharPrevia(p);
  }

  function desenharFoto() {
    const c = st.cal;
    const canvas = $('#calFoto');
    if (!canvas) return;
    const img = imagem('api/plan/arquivo/' + encodeURIComponent(c.foto));
    if (!img) return;
    c.escala = Math.min(canvas.parentElement.clientWidth / img.naturalWidth, 640 / img.naturalHeight);
    const w = Math.round(img.naturalWidth * c.escala);
    const h = Math.round(img.naturalHeight * c.escala);
    const ratio = window.devicePixelRatio || 1;
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.drawImage(img, 0, 0, w, h);
    const cor = getComputedStyle(document.documentElement).getPropertyValue('--s1').trim();
    const pts = c.cantos.map(([x, y]) => [x * c.escala, y * c.escala]);
    if (pts.length > 1) {
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (pts.length === 4) ctx.closePath();
      ctx.stroke();
    }
    ctx.font = '600 11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    pts.forEach(([x, y], i) => {
      ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fillStyle = cor; ctx.fill();
      ctx.fillStyle = '#ffffff'; ctx.fillText(String(i + 1), x, y);
    });
  }

  function desenharPrevia(p) {
    const c = st.cal;
    const canvas = $('#calPrevia');
    const margem = p.planta ? p.planta.margem_cm : 0;
    let foto = null;
    if (c.foto && c.cantos.length === 4) {
      const q = new URLSearchParams({ arquivo: c.foto, cantos: c.cantos.flat().join(',') });
      const img = imagem(`api/plan/${encodeURIComponent(c.b)}/foto.png?${q}`);
      if (img) foto = { img, margem };
    }
    const papel = c.paredes ? c.paredes.papel : (c.foto && c.cantos.length === 4 ? papelDaFoto(c.cantos) : null);
    const hits = V.drawFloorPlan(canvas, {
      envelope: p.env, points: p.points, paredes: c.paredes ? c.paredes.paredes : null, papel,
      margem: c.foto ? margem : 0, foto, fotoAlpha: c.paredes ? 0.28 : 1,
      orient: 'retrato', altura: 640, escuro: escuro(),
    });
    V.attachTooltip(canvas, $('#calTip'), () => hits, tooltip);
  }

  async function salvar() {
    const c = st.cal;
    const corpo = {};
    if (c.csv) corpo.paredes = { arquivo: c.csv, origem: c.origem, eixo_x: c.eixo };
    if (c.foto) corpo.foto = { arquivo: c.foto, cantos: c.cantos.length === 4 ? c.cantos : null };
    const r = await fetch(`api/plan/${encodeURIComponent(c.b)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
    const resp = await r.json().catch(() => ({}));
    if (!r.ok) {
      c.erro = typeof resp.detail === 'string' ? resp.detail : `HTTP ${r.status}`;
      renderCalibracao();
      return;
    }
    st.cal = null;
    st.ctx.atualizarPlantas(resp.plantas, resp.plantasAvisos);
  }

  /* ---------------- eventos ---------------- */
  $('#planGirar').addEventListener('click', () => {
    st.orient = st.orient === 'paisagem' ? 'retrato' : 'paisagem';
    guardar('qoe-plan-orient', st.orient);
    render(st.ctx);
  });
  $('#planFoto').addEventListener('click', () => {
    st.foto = st.foto === 'on' ? 'off' : 'on';
    guardar('qoe-plan-foto', st.foto);
    render(st.ctx);
  });
  $('#plans').addEventListener('click', (ev) => {
    const botao = ev.target.closest('[data-calibrar]');
    if (botao) abrirCalibracao(botao.dataset.calibrar);
  });
  $('#planCal').addEventListener('click', (ev) => {
    const c = st.cal;
    if (!c) return;
    if (ev.target.id === 'calFoto' && c.cantos.length < 4) {
      const r = ev.target.getBoundingClientRect();
      const arred = (v) => Math.round(v * 10) / 10;
      c.cantos.push([arred((ev.clientX - r.left) / c.escala), arred((ev.clientY - r.top) / c.escala)]);
      renderCalibracao();
      return;
    }
    const acao = ev.target.closest('[data-cal]');
    if (!acao) return;
    if (acao.dataset.cal === 'cancelar') { st.cal = null; renderCalibracao(); }
    if (acao.dataset.cal === 'desfazer') { c.cantos.pop(); renderCalibracao(); }
    if (acao.dataset.cal === 'recomecar') { c.cantos = []; renderCalibracao(); }
    if (acao.dataset.cal === 'salvar') salvar();
  });
  $('#planCal').addEventListener('change', async (ev) => {
    const c = st.cal;
    const campo = ev.target.dataset.campo;
    if (!c || !campo) return;
    c[campo] = ev.target.value;
    if (campo === 'foto') c.cantos = [];
    if (campo !== 'foto') await carregarParedes();
    renderCalibracao();
  });

  V.views.planta = { render };
})();
```

- [ ] **Step 2: `renderPlan` delega a `planta.js`**

Em `src/ml/studio/static/studio.js`, substitua o bloco inteiro:
```javascript
  /* ---------------- planta ---------------- */
  function renderPlan() {
    const rows = activeRows().filter((r) => r.x != null);
    const host = $('#plans');
    if (!rows.length) { host.innerHTML = '<p class="hint">Nenhum dataset com geometria está ativo.</p>'; return; }
    host.innerHTML = '';
    hits.plan = {};
    // Duas passadas: monta TODO o DOM antes de desenhar. Desenhar durante a
    // montagem mede o canvas enquanto ele ainda e o unico filho do grid — ele
    // fica com backing store da largura inteira e depois encolhe para meia
    // coluna, o que achata os circulos em elipses.
    const pending = [];
    Object.entries(state.data.envelopes).forEach(([b, env]) => {
      const mine = rows.filter((r) => r.b === b);
      if (!mine.length) return;
      const groups = new Map();
      mine.forEach((r) => {
        const k = `${r.x}|${r.y}`;
        if (!groups.has(k)) groups.set(k, { x: r.x, y: r.y, p: r.p, rows: [] });
        groups.get(k).rows.push(r);
      });
      const points = [...groups.values()].map((g) => {
        const pct = 100 * g.rows.filter((r) => meets(r, state.thr)).length / g.rows.length;
        return { x: g.x, y: g.y, n: g.rows.length, value: pct, label: g.p, color: rampColor(pct) };
      });
      const wrap = document.createElement('div');
      wrap.innerHTML = `<h2 style="font-size:13px;margin:0 0 8px">${state.data.buildings[b].label}
        <span style="color:var(--ink-muted);font-weight:400">· ${env.w}×${env.h} cm · ${points.length} pontos</span></h2>
        <div class="chartwrap"><canvas></canvas><div class="tooltip"></div></div>`;
      host.appendChild(wrap);
      pending.push({ b, env, points, wrap });
    });
    pending.forEach(({ b, env, points, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      const tip = wrap.querySelector('.tooltip');
      hits.plan[b] = V.drawFloorPlan(canvas, { height: 460, envelope: env, points });
      V.attachTooltip(canvas, tip, () => hits.plan[b],
        (h) => `<b>${h.label}</b>${Math.round(h.value)}% atende · ${h.at}`);
    });
  }

```
por:
```javascript
  /* ---------------- planta ---------------- */
  function renderPlan() {
    const rows = activeRows().filter((r) => r.x != null);
    const predios = [];
    Object.entries(state.data.envelopes).forEach(([b, env]) => {
      const mine = rows.filter((r) => r.b === b);
      if (!mine.length) return;
      const groups = new Map();
      mine.forEach((r) => {
        const k = `${r.x}|${r.y}`;
        if (!groups.has(k)) groups.set(k, { x: r.x, y: r.y, p: r.p, rows: [] });
        groups.get(k).rows.push(r);
      });
      const points = [...groups.values()].map((g) => {
        const pct = 100 * g.rows.filter((r) => meets(r, state.thr)).length / g.rows.length;
        return { x: g.x, y: g.y, n: g.rows.length, value: pct, label: g.p, color: rampColor(pct) };
      });
      predios.push({ b, label: state.data.buildings[b].label, env, points,
                     planta: (state.data.plantas || {})[b] || null });
    });
    V.views.planta.render({
      predios,
      avisos: state.data.plantasAvisos || [],
      atualizarPlantas: (plantas, avisos) => {
        state.data.plantas = plantas;
        state.data.plantasAvisos = avisos;
        renderAll();
      },
    });
  }

```

E substitua:
```javascript
    plan: ['Planta baixa', 'Pontos realmente medidos, em escala. Sem interpolação.'],
```
por:
```javascript
    plan: ['Planta baixa', 'Pontos realmente medidos, sobre a planta do prédio quando houver. Sem interpolação.'],
```

- [ ] **Step 3: Controles, avisos, calibração e script no `index.html`**

Em `src/ml/studio/static/index.html`, substitua:
```html
      <div id="plans"></div>
    </div>
```
por:
```html
      <div class="controls">
        <button class="toggle" id="planGirar" aria-pressed="false"><span class="dot"></span> Retrato</button>
        <button class="toggle hide" id="planFoto" aria-pressed="true"><span class="dot"></span> Foto ao fundo</button>
      </div>
      <div id="planAvisos"></div>
      <div id="plans"></div>
    </div>
    <div id="planCal" class="hide"></div>
```

E substitua:
```html
<script src="features.js?v=2"></script>
```
por:
```html
<script src="features.js?v=2"></script>
<script src="planta.js?v=2"></script>
```

- [ ] **Step 4: Estilos**

Acrescente ao final de `src/ml/studio/static/styles.css`:
```css
/* ---------- planta ---------- */
#plans.paisagem { grid-template-columns: 1fr; }
.plan-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; }
.plan-head h2 { font-size: 13px; margin: 0; }
.plan-head h2 span { color: var(--ink-muted); font-weight: 400; }
.plan-aviso { display: flex; gap: 8px; align-items: center; font-size: 12.5px; color: var(--ink-2);
              padding: 6px 10px; border-left: 3px solid var(--warning); border-radius: 6px; margin-bottom: 8px;
              background: color-mix(in srgb, var(--warning) 8%, transparent); }
.plan-aviso .icon { stroke: var(--warning); width: 15px; height: 15px; }
.cal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; align-items: start; }
.cal-foto canvas { cursor: crosshair; }
.btn:disabled { opacity: .5; cursor: default; }
```

- [ ] **Step 5: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/planta.js && node --check src/ml/studio/static/studio.js && echo ok`
Expected: `ok`

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/static/graficos.js src/ml/studio/static/planta.js src/ml/studio/static/studio.js src/ml/studio/static/index.html src/ml/studio/static/styles.css
git commit -m "feat(studio): planta com vetor, foto, giro e calibracao"
```

---

### Task 5: Registro inicial e verificação no navegador

**Files:**
- Create: `docs/planta/plantas.json` (pela própria rota de calibração)

- [ ] **Step 1: Registrar as paredes da casa pela API**

Suba o servidor (`./venv/bin/python src/ml/studio.py --port 8100`) e rode:
```bash
curl -s -X POST http://127.0.0.1:8100/api/plan/casa -H 'Content-Type: application/json' \
  -d '{"paredes":{"arquivo":"Coordenadas_CSV_2D_casa_roni_v2.csv","origem":"inferior-direito","eixo_x":"horizontal"},"foto":{"arquivo":"casa_roni_planta_baixa.jpeg","cantos":null}}' \
  | ./venv/bin/python -c "import json,sys; d=json.load(sys.stdin); c=d['plantas']['casa']; print(c['papel'], len(c['paredes']), c['foto'], c['calibracao']['foto'])"
cat docs/planta/plantas.json
```
Expected:
```
[[-1, 0], [0, -1]] 31 None {'arquivo': 'casa_roni_planta_baixa.jpeg', 'cantos': None}
{
  "casa": {
    "foto": {
      "arquivo": "casa_roni_planta_baixa.jpeg",
      "cantos": null
    },
    "paredes": {
      "arquivo": "Coordenadas_CSV_2D_casa_roni_v2.csv",
      "eixo_x": "horizontal",
      "origem": "inferior-direito"
    }
  }
}
```
A origem no canto inferior direito é a que pôs 8 de 9 pontos no cômodo certo, mas **não foi confirmada por quem mediu** (spec, seção 12).

- [ ] **Step 2: Verificar no navegador**

Abra `http://127.0.0.1:8100/#plan` e confira:

1. **Casa em paisagem (padrão), modo "vetor":** 31 paredes em traço escuro, com a sala à esquerda e a suíte à direita. Cada ponto cai no seu cômodo, exceto suite (90, 1105), que fica no corredor, na porta da suíte (achado conhecido). O botão **Calibrar planta** da casa aparece em azul, porque a foto está registrada mas sem cantos.
2. **Cowork, modo "sem planta":** o retângulo de 1000 × 480 cm com os 7 pontos e o roteador.
3. **Retrato:** clique **Retrato**. A casa fica na orientação do arquiteto, com a suíte em cima, e os dois prédios lado a lado em canvas de 640 px. Recarregue a página: a escolha continua valendo.
4. O botão **Foto ao fundo** ainda não aparece, porque nenhum prédio está no modo vetor + foto.
5. Passe o mouse num ponto: a tooltip mostra a posição, o % que atende e o número de amostras.

- [ ] **Step 3: Calibração da foto (AÇÃO DO USUÁRIO)**

Esta etapa depende de olho humano, então **peça ao usuário** para fazer:

1. Clicar **Calibrar planta** na casa. O painel abre com o CSV e a foto já escolhidos e a origem no canto inferior direito.
2. Clicar, na foto, os 4 cantos do envelope na ordem indicada: (0, 0) a origem, depois (410, 0), (410, 1386) e (0, 1386). Como referência, a estimativa usada na validação foi perto de (307, 935), (76, 935), (97, 124) e (329, 124), em pixels da foto de 720 × 1280.
3. Conferir a pré-visualização: as paredes vetoriais precisam cair sobre as paredes da foto. Se não caírem, usar **Desfazer** ou **Recomeçar**, e rever também a origem das paredes.
4. Clicar **Salvar calibração**.

Depois de salvo, confira:
- A casa passa a mostrar "vetor + foto": a foto esmaecida por baixo e as paredes por cima. O botão **Foto ao fundo** aparece e liga ou desliga a foto.
- No tema escuro, a foto aparece invertida (fundo escuro), as paredes ficam claras e o texto dos pontos claros continua preto.
- Os rótulos "1386 cm" e "410 cm" ficam fora da foto.
- `git diff docs/planta/plantas.json` mostra apenas os `cantos` preenchidos.

- [ ] **Step 4: Suíte completa**

Pare o servidor e rode `./venv/bin/python -m unittest discover -s tests -p "test_*.py"`.
Expected: `OK`.

- [ ] **Step 5: Commit (AÇÃO DO USUÁRIO)**

```bash
git add docs/planta/
git commit -m "docs(planta): planta da casa, tracado das paredes e registro da calibracao"
```

- [ ] **Step 6: Relatar ao usuário**

Informe o que foi entregue e lembre dois pontos abertos da spec (seções 12 e 13):
- A orientação da casa precisa ser confirmada por quem mediu.
- A recomendação de tirar `client_opportunity_medium_use` do modelo fica com o lado do MLflow.
