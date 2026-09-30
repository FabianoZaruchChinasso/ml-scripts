# QoE Studio: planta com andares (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a view Planta mostrar um cartão por andar da `casa-marcelo`, cada um com a sua planta vetorial em metros e só os pontos daquele andar, sem mudar os prédios de um andar só.

**Architecture:** O `docs/planta/plantas.json` ganha `andares` por prédio. O `studio/plans.py` passa a ler paredes em metros (escala fixa e deslocamento `dx`/`dy`) e monta uma planta por andar. O andar de cada ponto sai de `plans.andar_de(z)`, que o `studio/data.py` usa para anotar cada linha do payload. No front-end, o `studio.js` desdobra o prédio em um cartão por andar, e o `planta.js` calibra `dx`/`dy` por andar.

**Tech Stack:** Python 3.12 (pandas, numpy, FastAPI), unittest, JS puro com canvas (sem build).

**Spec:** [docs/superpowers/specs/2026-09-30-qoe-studio-planta-andares-design.md](../specs/2026-09-30-qoe-studio-planta-andares-design.md)

**Regras deste repositório:**
- **Nunca rode `git commit` nem `git push`**: o usuário commita à mão. Nos pontos marcados como **Checkpoint**, pare e liste os arquivos alterados.
- Testes: `venv/bin/python -m unittest discover -s tests ...`, a partir da raiz do repositório. O `pytest` não está instalado no venv.
- Indentação de 2 espaços em Python e JS. Comentários só quando o porquê não é óbvio.
- Sem emojis em código ou UI.

---

## Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/studio/plans.py` | alterar | `ler_paredes_metros`, escala fixa + `dx`/`dy` em `registro_paredes`, `andar_de`, `ler_registro`, montagem e gravação por andar |
| `src/ml/studio/data.py` | alterar | `routerZ` no envelope; campo `andar` em cada linha de prédio com andares |
| `src/ml/studio/api.py` | alterar | `GET .../paredes` aceita `formato`/`dx`/`dy`; `POST` aceita `andar` |
| `src/ml/studio/static/graficos.js` | alterar | `drawFloorPlan` pula o roteador quando `routerX` é nulo |
| `src/ml/studio/static/studio.js` | alterar | `renderPlan` gera um cartão por andar |
| `src/ml/studio/static/planta.js` | alterar | cartões com chave `k`; calibração com formato, `dx`/`dy` e `andar` |
| `docs/planta/planta-casa-cima.csv`, `docs/planta/planta-casa-baixo.csv` | criar | paredes do Marcelo, sem alteração |
| `docs/planta/plantas.json` | alterar | entrada `casa-marcelo` com os dois andares |
| `tests/test_plans.py` | alterar | testes de metros, escala, `andar_de`, montagem e gravação por andar |
| `tests/test_studio_features.py` | alterar | payload com `routerZ` e `andar` por linha |

---

### Task 1: Ler paredes em metros

**Files:**
- Modify: `src/ml/studio/plans.py` (constantes no topo; nova função depois de `ler_paredes`, linha ~52)
- Test: `tests/test_plans.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_plans.py`, adicione esta classe antes de `if __name__ == '__main__':`:

```python
class TestParedesMetros(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _csv(self, nome, texto):
    path = os.path.join(self.pasta, nome)
    with open(path, 'w', encoding='utf-8') as handle:
      handle.write(texto)
    return path

  def test_so_paredes_em_cm(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2,y2,label,notes\n'
                              'wall,w1,0.0,0.0,5.12,0.0,,a\n'
                              'dim,c1,0.0,-0.38,2.53,-0.38,"2,53",cota\n'
                              'wall,w2,-1.01,0.0,-1.01,2.75,,"x, y"\n')
    np.testing.assert_allclose(P.ler_paredes_metros(path), [[0, 0, 512, 0], [-101, 0, -101, 275]])

  def test_sem_parede_levanta(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2,y2\ndim,c1,0,0,1,0\n')
    with self.assertRaises(ValueError):
      P.ler_paredes_metros(path)

  def test_coluna_faltando_levanta(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2\nwall,w1,0,0,1\n')
    with self.assertRaises(ValueError):
      P.ler_paredes_metros(path)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestParedesMetros -v`
Expected: 3 erros com `AttributeError: module 'ml.studio.plans' has no attribute 'ler_paredes_metros'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/plans.py`, logo abaixo de `COLUNAS_PAREDE = [...]` (linha 22), adicione:

```python
COLUNAS_METROS = ['x1', 'y1', 'x2', 'y2']
FORMATOS = ('px', 'metros')
```

E logo depois da função `ler_paredes` (termina na linha 52):

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestParedesMetros -v`
Expected: 3 testes OK

---

### Task 2: Registro com escala fixa e deslocamento

**Files:**
- Modify: `src/ml/studio/plans.py:62-100` (`registro_paredes`, `paredes_em_cm`)
- Test: `tests/test_plans.py` (classe `TestRegistroParedes`)

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim da classe `TestRegistroParedes` (depois de `test_valores_invalidos_levantam`):

```python
  def test_escala_fixa_leva_a_origem_para_dx_dy(self):
    cantos = {'superior-esquerdo': (100, 50), 'superior-direito': (300, 50),
              'inferior-esquerdo': (100, 650), 'inferior-direito': (300, 650)}
    for origem, eixo in COMBOS:
      px_para_cm, _ = P.registro_paredes(SEGMENTOS, origem, eixo, W, H, escala=1.0, dx=7.0, dy=-3.0)
      np.testing.assert_allclose(px_para_cm(*cantos[origem]), (7, -3), atol=1e-9, err_msg=origem + eixo)

  def test_escala_fixa_nao_estica_no_envelope(self):
    px_para_cm, _ = P.registro_paredes(SEGMENTOS, 'superior-esquerdo', 'horizontal', W, H, escala=2.0)
    np.testing.assert_allclose(px_para_cm(120, 90), (10, 20), atol=1e-9)

  def test_escala_fixa_ida_e_volta(self):
    for origem, eixo in COMBOS:
      px_para_cm, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H, escala=1.0, dx=12.5, dy=-40.0)
      for x, y in [(0, 0), (58, 75), (861, 1448), (-20.5, 700.25)]:
        np.testing.assert_allclose(px_para_cm(*cm_para_px(x, y)), (x, y), atol=1e-9)

  def test_paredes_em_cm_com_escala(self):
    segmentos = np.array([[-101, 0, 760, 0], [760, 0, 760, 1348]], float)
    self.assertEqual(P.paredes_em_cm(segmentos, 'superior-esquerdo', 'horizontal', 861, 1448,
                                     escala=1.0, dx=10, dy=20),
                     [[10.0, 20.0, 871.0, 20.0], [871.0, 20.0, 871.0, 1368.0]])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestRegistroParedes -v`
Expected: os 4 testes novos falham com `TypeError: registro_paredes() got an unexpected keyword argument 'escala'` (ou `paredes_em_cm()`); os 5 antigos passam.

- [ ] **Step 3: Implementar**

Substitua `registro_paredes` e `paredes_em_cm` (linhas 62–100) por:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -v`
Expected: todos OK (incluindo os 5 antigos de `TestRegistroParedes`, que garantem o comportamento sem `escala`).

---

### Task 3: `andar_de`

**Files:**
- Modify: `src/ml/studio/plans.py` (import `math`; novas funções antes de `carregar_config`, linha ~180)
- Test: `tests/test_plans.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione esta classe em `tests/test_plans.py`, antes de `if __name__ == '__main__':`:

```python
class TestAndarDe(unittest.TestCase):
  ANDARES = [{'id': 'baixo', 'z_min': None}, {'id': 'cima', 'z_min': 0}]

  def test_pelo_maior_piso_que_nao_passa_do_z(self):
    self.assertEqual(P.andar_de(80.0, self.ANDARES), 'cima')
    self.assertEqual(P.andar_de(0, self.ANDARES), 'cima')
    self.assertEqual(P.andar_de(-165.0, self.ANDARES), 'baixo')

  def test_z_nulo_nao_tem_andar(self):
    self.assertIsNone(P.andar_de(None, self.ANDARES))
    self.assertIsNone(P.andar_de(float('nan'), self.ANDARES))

  def test_abaixo_de_todos_os_pisos_nao_tem_andar(self):
    self.assertIsNone(P.andar_de(-1, [{'id': 'unico', 'z_min': 0}]))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestAndarDe -v`
Expected: 3 erros com `AttributeError: module 'ml.studio.plans' has no attribute 'andar_de'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/plans.py`, acrescente `import math` junto dos imports (depois de `import json`). Antes de `def carregar_config`, adicione:

```python
def _piso(andar: dict) -> float:
  z = andar.get('z_min')
  return -math.inf if z is None else float(z)


def andar_de(z, andares: list):
  """id do andar de maior `z_min` <= z (`z_min` nulo = sem piso). None se z for nulo ou abaixo de todos."""
  if z is None or (isinstance(z, float) and math.isnan(z)):
    return None
  candidatos = [a for a in andares if _piso(a) <= z]
  return max(candidatos, key=_piso)['id'] if candidatos else None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestAndarDe -v`
Expected: 3 testes OK

---

### Task 4: Montar plantas por andar

**Files:**
- Modify: `src/ml/studio/plans.py` (novas funções `ler_registro`, `_calibracao_paredes`, `_andares_validos`, `_montar_andares`; reescrever `montar_plantas`, linhas 194–232)
- Test: `tests/test_plans.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione esta classe em `tests/test_plans.py`, antes de `if __name__ == '__main__':`:

```python
class TestAndares(unittest.TestCase):
  REGISTRO = {'formato': 'metros', 'origem': 'superior-esquerdo', 'eixo_x': 'horizontal'}

  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    with open(os.path.join(self.pasta, 'cima.csv'), 'w', encoding='utf-8') as handle:
      handle.write('type,id,x1,y1,x2,y2,label,notes\n'
                   'wall,w1,-1.01,0.0,7.6,0.0,,topo\n'
                   'wall,w2,7.6,0.0,7.6,13.48,,lateral\n'
                   'dim,d1,-1.01,-0.42,2.64,-0.42,"3,65",cota\n')
    with open(os.path.join(self.pasta, 'baixo.csv'), 'w', encoding='utf-8') as handle:
      handle.write('type,id,x1,y1,x2,y2,label,notes\n'
                   'wall,w1,0.0,0.0,7.35,0.0,,topo\n'
                   'wall,w2,7.35,0.0,7.35,9.14,,lateral\n')
    self.env = {'casa-m': {'w': 861.0, 'h': 1448.0, 'routerZ': 80.0}}

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _gravar(self, config):
    with open(os.path.join(self.pasta, 'plantas.json'), 'w', encoding='utf-8') as handle:
      json.dump(config, handle)

  def _config(self):
    with open(os.path.join(self.pasta, 'plantas.json'), encoding='utf-8') as handle:
      return json.load(handle)

  def _dois_andares(self, arquivo_baixo='baixo.csv'):
    return {'casa-m': {'andares': [
      {'id': 'baixo', 'z_min': None, 'paredes': dict(self.REGISTRO, arquivo=arquivo_baixo, dx=10, dy=20)},
      {'id': 'cima', 'z_min': 0, 'paredes': dict(self.REGISTRO, arquivo='cima.csv', dx=0, dy=0)},
    ]}}

  def test_um_item_por_andar_do_mais_alto_para_o_mais_baixo(self):
    self._gravar(self._dois_andares())
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertEqual(avisos, [])
    andares = plantas['casa-m']['andares']
    self.assertEqual([a['id'] for a in andares], ['cima', 'baixo'])
    cima, baixo = andares
    self.assertEqual(cima['paredes'], [[0.0, 0.0, 861.0, 0.0], [861.0, 0.0, 861.0, 1348.0]])
    self.assertEqual(baixo['paredes'][0], [10.0, 20.0, 745.0, 20.0])
    self.assertEqual(cima['papel'], [[1, 0], [0, 1]])
    self.assertIsNone(cima['foto'])
    self.assertEqual(cima['calibracao']['paredes'],
                     {'arquivo': 'cima.csv', 'origem': 'superior-esquerdo', 'eixo_x': 'horizontal',
                      'formato': 'metros', 'dx': 0.0, 'dy': 0.0})

  def test_roteador_so_no_andar_do_router_z(self):
    self._gravar(self._dois_andares())
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    self.assertEqual([a['roteador'] for a in plantas['casa-m']['andares']], [True, False])

  def test_csv_quebrado_de_um_andar_nao_afeta_o_outro(self):
    self._gravar(self._dois_andares(arquivo_baixo='sumiu.csv'))
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    cima, baixo = plantas['casa-m']['andares']
    self.assertIsNotNone(cima['paredes'])
    self.assertIsNone(baixo['paredes'])
    self.assertTrue(any('paredes ignoradas' in a for a in baixo['avisos']))

  def test_andares_invalidos_viram_aviso_e_planta_simples(self):
    self._gravar({'casa-m': {'andares': 'cima'}})
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    item = plantas['casa-m']
    self.assertNotIn('andares', item)
    self.assertIsNone(item['paredes'])
    self.assertTrue(any('andares ignorados' in a for a in item['avisos']))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestAndares -v`
Expected: 4 falhas ou erros. `montar_plantas` ignora `andares` e devolve `KeyError: 'andares'` ou a asserção de `andares ignorados` falha.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/plans.py`, adicione estas funções logo depois de `andar_de` (Task 3):

```python
def ler_registro(p: dict, W: float, H: float, pasta: str = None):
  """(paredes em cm, papel) de uma entrada `paredes` do plantas.json, em px ou em metros."""
  formato = p.get('formato', 'px')
  if formato not in FORMATOS:
    raise ValueError(f'formato inválido {formato!r}; esperado um de {list(FORMATOS)}')
  path = caminho(p['arquivo'], pasta)
  if formato == 'metros':
    paredes = paredes_em_cm(ler_paredes_metros(path), p['origem'], p['eixo_x'], W, H,
                            escala=1.0, dx=float(p.get('dx', 0)), dy=float(p.get('dy', 0)))
  else:
    paredes = paredes_em_cm(ler_paredes(path), p['origem'], p['eixo_x'], W, H)
  return paredes, papel_das_paredes(p['origem'], p['eixo_x'])


def _calibracao_paredes(p: dict) -> dict:
  saida = {k: p[k] for k in ('arquivo', 'origem', 'eixo_x')}
  if p.get('formato', 'px') == 'metros':
    saida.update(formato='metros', dx=float(p.get('dx', 0)), dy=float(p.get('dy', 0)))
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
```

Depois substitua `montar_plantas` inteira (linhas 194–232 do arquivo original) por:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -v`
Expected: todos OK. Os testes antigos de `TestArquivos` (`test_salvar_e_montar`, `test_avisos`, `test_foto_corrompida_nao_derruba_as_paredes`) garantem que a `casa`, sem andares, não mudou.

---

### Task 5: Gravar calibração por andar

**Files:**
- Modify: `src/ml/studio/plans.py` (`salvar_calibracao`, linhas 235–261 do original; nova `_validar_paredes`, nova `_salvar_andar`)
- Test: `tests/test_plans.py` (classe `TestAndares`)

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim da classe `TestAndares`:

```python
  def test_salvar_grava_so_o_andar_pedido(self):
    config = self._dois_andares()
    config['casa'] = {'paredes': {'arquivo': 'x.csv', 'origem': 'inferior-direito', 'eixo_x': 'horizontal'}}
    self._gravar(config)
    P.salvar_calibracao('casa-m', dict(self.REGISTRO, arquivo='baixo.csv', dx=12, dy=-3), None,
                        self.pasta, andar='baixo')
    salvo = self._config()
    baixo = next(a for a in salvo['casa-m']['andares'] if a['id'] == 'baixo')
    cima = next(a for a in salvo['casa-m']['andares'] if a['id'] == 'cima')
    self.assertEqual(baixo['paredes'], {'arquivo': 'baixo.csv', 'origem': 'superior-esquerdo',
                                        'eixo_x': 'horizontal', 'formato': 'metros', 'dx': 12.0, 'dy': -3.0})
    self.assertEqual(cima, config['casa-m']['andares'][1])
    self.assertEqual(salvo['casa'], config['casa'])

  def test_salvar_recusa_andar_inexistente_dx_invalido_e_foto(self):
    self._gravar(self._dois_andares())
    bom = dict(self.REGISTRO, arquivo='baixo.csv', dx=0, dy=0)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', bom, None, self.pasta, andar='sotao')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(bom, dx='abc'), None, self.pasta, andar='baixo')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(bom, formato='polegadas'), None, self.pasta, andar='baixo')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', None, {'arquivo': 'f.jpeg', 'cantos': None}, self.pasta, andar='baixo')
    self.assertEqual(self._config(), self._dois_andares())

  def test_salvar_sem_andar_em_predio_com_andares_levanta(self):
    self._gravar(self._dois_andares())
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(self.REGISTRO, arquivo='cima.csv'), None, self.pasta)
    self.assertEqual(self._config(), self._dois_andares())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -k TestAndares -v`
Expected: os 3 testes novos dão erro com `TypeError: salvar_calibracao() got an unexpected keyword argument 'andar'`, ou falham na última asserção.

- [ ] **Step 3: Implementar**

Substitua `salvar_calibracao` inteira por:

```python
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
    dx, dy = paredes.get('dx', 0), paredes.get('dy', 0)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (dx, dy)):
      raise ValueError('dx e dy precisam ser números finitos')
    ler_paredes_metros(path)
    novo.update(formato='metros', dx=float(dx), dy=float(dy))
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_plans.py -v`
Expected: todos OK. `test_salvar_e_montar` confirma que a entrada em px continua sendo gravada só com `arquivo`, `origem` e `eixo_x`, sem `formato`.

---

### Task 6: Payload com `routerZ` e andar por linha

**Files:**
- Modify: `src/ml/studio/data.py:16` (import), `:246-251` (envelope e `montar_plantas`)
- Test: `tests/test_studio_features.py` (classe `TestDados`)

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_features.py`, acrescente `import json` aos imports (depois de `import os`) e `from ml.studio import plans as SP` depois de `from ml.studio import features as SF`. Adicione ao fim da classe `TestDados`:

```python
  def test_payload_traz_router_z_e_andar_por_linha(self):
    linhas = pd.DataFrame({
      'local': ['marcelo-copa', 'marcelo-inf-sala'],
      'speedtest_down_mbps': [50.0, 20.0], 'speedtest_up_mbps': [10.0, 5.0],
      'latency_ms': [10.0, 12.0], 'jitter_ms': [1.0, 2.0],
      'combo': ['B', 'B'], 'n_clients': [1, 1],
      'station_x': [238.0, 501.0], 'station_y': [811.0, 540.0], 'station_z': [80.0, -165.0],
      'house_x0': [861.0, 861.0], 'house_y0': [1448.0, 1448.0], 'house_z0': [250.0, 250.0],
      'router_x': [501.0, 501.0], 'router_y': [540.0, 540.0], 'router_z': [80.0, 80.0],
    })
    with tempfile.TemporaryDirectory() as dados, tempfile.TemporaryDirectory() as planta:
      linhas.to_csv(os.path.join(dados, 'm.csv'), index=False)
      with open(os.path.join(planta, 'plantas.json'), 'w', encoding='utf-8') as handle:
        json.dump({'casa-marcelo': {'andares': [{'id': 'cima', 'z_min': 0}, {'id': 'baixo', 'z_min': None}]}}, handle)
      antes = (SD.DATA_DIR, SP.PLANTA_DIR)
      SD.DATA_DIR, SP.PLANTA_DIR, SD._descobertos = dados, planta, None
      try:
        payload = SD.build_payload()
      finally:
        (SD.DATA_DIR, SP.PLANTA_DIR), SD._descobertos = antes, None
    self.assertEqual(payload['envelopes']['casa-marcelo']['routerZ'], 80.0)
    self.assertEqual([r['andar'] for r in payload['rows']], ['cima', 'baixo'])
    self.assertEqual([a['roteador'] for a in payload['plantas']['casa-marcelo']['andares']], [True, False])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_features.py -k test_payload_traz_router_z -v`
Expected: `KeyError: 'routerZ'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/data.py`, troque a linha 16:

```python
from ml.studio.plans import montar_plantas
```

por:

```python
from ml.studio.plans import andar_de, montar_plantas
```

No bloco do envelope (hoje nas linhas 246–249), troque:

```python
      envelopes[building] = {
        'w': float(row['house_x0']), 'h': float(row['house_y0']), 'z': float(row['house_z0']),
        'routerX': float(row['router_x']), 'routerY': float(row['router_y']),
      }
```

por:

```python
      envelopes[building] = {
        'w': float(row['house_x0']), 'h': float(row['house_y0']), 'z': float(row['house_z0']),
        'routerX': float(row['router_x']), 'routerY': float(row['router_y']),
        'routerZ': None if pd.isna(row.get('router_z')) else float(row['router_z']),
      }
```

Logo depois de `plantas, plantas_avisos = montar_plantas(envelopes)`, adicione:

```python
  for record in rows:
    andares = (plantas.get(record['b']) or {}).get('andares')
    if andares:
      record['andar'] = andar_de(record.get('z'), andares)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: `OK` na suíte inteira.

- [ ] **Checkpoint:** backend pronto. Liste para o usuário os arquivos alterados (`src/ml/studio/plans.py`, `src/ml/studio/data.py`, `tests/test_plans.py`, `tests/test_studio_features.py`) e aguarde o commit dele. Não rode git.

---

### Task 7: Semear as plantas da casa-marcelo

**Files:**
- Create: `docs/planta/planta-casa-cima.csv`
- Create: `docs/planta/planta-casa-baixo.csv`
- Modify: `docs/planta/plantas.json`

- [ ] **Step 1: Criar `docs/planta/planta-casa-baixo.csv`** com este conteúdo exato (o arquivo do Marcelo, sem alteração):

```csv
type,id,x1,y1,x2,y2,label,notes
wall,w01,0.0,0.0,5.12,0.0,,parede superior principal
wall,w02,0.0,0.0,0.0,6.78,,parede externa esquerda
wall,w03,5.12,0.0,5.12,0.58,,degrau superior direito
wall,w04,5.12,0.58,7.35,0.58,,parede superior da extensão direita
wall,w05,7.35,0.58,7.35,8.13,,parede externa direita
wall,w06,7.35,8.13,3.61,8.13,,parede inferior do bloco direito
wall,w07,3.61,8.13,3.61,9.14,,"trecho vertical inferior de 1,01 m"
wall,w08,3.61,9.14,1.02,9.14,,parede inferior esquerda
wall,w09,1.02,9.14,1.02,6.78,,reentrância inferior esquerda
wall,w10,1.02,6.78,0.0,6.78,,"trecho horizontal de 1,02 m"
wall,w11,0.0,1.62,2.53,1.62,,divisão horizontal superior esquerda
wall,w12,2.53,0.0,2.53,1.62,,divisão vertical superior esquerda
wall,w13,0.0,5.38,5.12,5.38,,parede horizontal central
wall,w14,5.12,0.58,5.12,5.38,,divisão vertical superior direita
wall,w15,5.12,2.08,7.35,2.08,,divisão horizontal superior direita
wall,w16,3.61,5.38,3.61,8.13,,divisão vertical inferior direita
dim,c01,0.0,-0.38,2.53,-0.38,"2,53",medida original
dim,c02,2.53,-0.38,5.12,-0.38,"2,59","2,60 ajustado em 1 cm para fechar com 5,12"
dim,c03,5.12,0.22,7.35,0.22,"2,23",medida original
dim,c04,0.0,5.04,5.12,5.04,"≈5,12","compromisso entre 5,10 e 5,13"
dim,c05,0.0,7.1,1.02,7.1,"1,02",medida original
dim,c06,3.61,8.47,7.35,8.47,"3,74",medida original
dim,c07,-0.38,0.0,-0.38,1.62,"1,62",medida original
dim,c08,-0.38,1.62,-0.38,5.38,"3,76",medida original
dim,c09,-0.38,5.38,-0.38,6.78,"1,40",medida original
dim,c10,7.72,0.58,7.72,2.08,"1,50",medida original
dim,c11,7.72,2.08,7.72,5.38,"3,30",medida original
dim,c12,7.72,5.38,7.72,8.13,"2,75",medida original
dim,c13,3.27,5.38,3.27,9.14,"3,76","2,75 + 1,01 = 3,76"
dim,c14,3.95,8.13,3.95,9.14,"1,01",medida original
wall,w17,5.12,5.38,7.35,5.38,,continuação da parede horizontal central até a parede externa direita
```

- [ ] **Step 2: Criar `docs/planta/planta-casa-cima.csv`** com este conteúdo exato:

```csv
type,id,x1,y1,x2,y2,label,notes
wall,w001,-1.01,0.0,7.6,0.0,,"topo: 3,65 + 2,56 + 2,40 = 8,61"
wall,w002,-1.01,0.0,-1.01,2.75,,lateral do cômodo superior esquerdo
wall,w003,2.64,0.0,2.64,2.75,,"divisão: -1,01 + 3,65"
wall,w004,5.2,0.0,5.2,2.75,,"divisão: 2,64 + 2,56"
wall,w005,7.6,0.0,7.6,13.48,,lateral direita principal
wall,w006,-1.01,2.75,2.64,2.75,,base do cômodo superior esquerdo
wall,w007,5.2,2.75,7.6,2.75,,base do cômodo superior direito
wall,w008,2.64,2.75,2.64,4.31,,"queda de 1,56"
wall,w009,2.64,3.26,4.48,3.26,"1,84",trecho horizontal do recorte
wall,w010,4.4800,3.2600,4.7645,2.9376,"0,43","parede diagonal com comprimento real de 0,43 m"
wall,w011,4.7645,2.9376,5.20,2.9376,"≈0,45","trecho horizontal restante; fica em ~0,44 m, compatível com a cota 0,45"
wall,w012,2.64,4.31,2.67,4.31,,encontro com o cômodo inferior
wall,w013,0.0,4.31,2.67,4.31,"2,67",topo do segundo cômodo esquerdo
wall,w014,0.0,4.31,0.0,6.61,"2,30",lateral esquerda
wall,w015,0.0,6.61,3.85,6.61,,base do segundo cômodo esquerdo
wall,w016,3.85,5.28,3.85,6.61,,lado direito inferior do cômodo
wall,w017,3.85,5.28,5.2,5.28,"1,35",reentrância horizontal
wall,w018,5.2,4.23,5.2,5.28,"≈1,05",reentrância vertical
wall,w019,5.2,4.23,7.6,4.23,,base do segundo cômodo direito
wall,w020,5.2,2.75,5.2,4.23,"1,48",lateral esquerda do segundo cômodo direito
wall,w021,3.85,6.61,7.6,6.61,"3,75","linha horizontal de 3,75"
wall,w022,3.85,5.28,3.85,6.61,,fechamento esquerdo superior
wall,w023,3.85,6.61,3.85,8.91,,lado esquerdo do cômodo abaixo
wall,w024,3.85,8.91,7.6,8.91,,base do cômodo direito central
wall,w025,0.0,6.61,0.0,10.01,"3,40",lateral esquerda
wall,w026,0.0,10.01,3.8,10.01,,base do terceiro cômodo esquerdo
wall,w028,5.0,8.91,5.0,10.67,,divisão vertical interna aproximada
wall,w029,3.8,10.01,3.8,10.67,"0,66",degrau vertical
wall,w030,3.8,10.67,7.6,10.67,,topo do cômodo inferior direito
wall,w031,5.0,10.67,7.6,10.67,"2,60","trecho cotado de 2,60"
wall,w032,0.0,10.01,0.0,13.48,"3,47",lateral esquerda inferior
wall,w033,0.0,13.48,3.8,13.48,"3,80",base inferior esquerda
wall,w034,3.8,10.67,3.8,13.48,,divisão inferior central
wall,w035,3.8,13.48,7.6,13.48,"3,80",base inferior direita
dim,d001,-1.01,-0.42,2.64,-0.42,"3,65",original
dim,d002,2.64,-0.42,5.2,-0.42,"2,56",original; preservada
dim,d003,5.2,-0.42,7.6,-0.42,"2,40",original
dim,d004,0.0,13.9,3.8,13.9,"3,80",original
dim,d005,3.8,13.9,7.6,13.9,"3,80",original
dim,d006,0.0,4.0,2.67,4.0,"2,67",original
dim,d007,2.64,3.0,4.48,3.0,"1,84",original
dim,d008,4.7645,2.6676,5.20,2.6676,"≈0,44","resultado geométrico após fixar a diagonal em 0,43 m; próximo da cota 0,45"
dim,d009,3.85,5.0,5.2,5.0,"1,35",original
dim,d010,3.85,6.95,7.6,6.95,"3,75",original
dim,d011,5.0,10.98,7.6,10.98,"2,60",original
dim,d012,-1.42,0.0,-1.42,2.75,"2,75",original
dim,d013,-0.35,4.31,-0.35,6.61,"2,30",original
dim,d014,-0.35,6.61,-0.35,10.01,"3,40",original
dim,d015,-0.35,10.01,-0.35,13.48,"3,47",original
dim,d016,7.98,0.0,7.98,2.75,"≈2,72",aproximado para alinhar ao topo esquerdo
dim,d017,7.98,2.75,7.98,4.23,"1,48",original
dim,d018,5.48,4.23,5.48,5.28,"≈1,05",anotação do recorte
dim,d019,4.1,8.91,4.1,10.01,"≈1,10",geometria aproximada
dim,d020,3.55,10.01,3.55,10.67,"0,66",original
```

- [ ] **Step 3: Acrescentar a `casa-marcelo` ao `docs/planta/plantas.json`**

Substitua o arquivo inteiro por (a entrada `casa` fica idêntica à atual):

```json
{
  "casa": {
    "foto": {
      "arquivo": "casa_roni_planta_baixa.jpeg",
      "cantos": [
        [
          60.0,
          1011.5
        ],
        [
          310.0,
          1013.5
        ],
        [
          338.0,
          129.5
        ],
        [
          100.0,
          123.5
        ]
      ]
    },
    "paredes": {
      "arquivo": "Coordenadas_CSV_2D_casa_roni_v2.csv",
      "eixo_x": "horizontal",
      "origem": "inferior-esquerdo"
    }
  },
  "casa-marcelo": {
    "andares": [
      {
        "id": "cima",
        "z_min": 0,
        "paredes": {
          "arquivo": "planta-casa-cima.csv",
          "formato": "metros",
          "origem": "superior-esquerdo",
          "eixo_x": "horizontal",
          "dx": 0.0,
          "dy": 0.0
        }
      },
      {
        "id": "baixo",
        "z_min": null,
        "paredes": {
          "arquivo": "planta-casa-baixo.csv",
          "formato": "metros",
          "origem": "superior-esquerdo",
          "eixo_x": "horizontal",
          "dx": 0.0,
          "dy": 0.0
        }
      }
    ]
  }
}
```

- [ ] **Step 4: Conferir a montagem com os dados reais**

Run:
```bash
venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from ml.studio import data as SD
p = SD.build_payload()
for a in p['plantas']['casa-marcelo']['andares']:
  print(a['id'], a['roteador'], len(a['paredes'] or []), a['avisos'])
from collections import Counter
print(Counter(r.get('andar') for r in p['rows'] if r['b'] == 'casa-marcelo'))
"
```
Expected:
```
cima True 34 []
baixo False 17 []
Counter({'cima': ..., 'baixo': ...})
```
Ou seja: 34 paredes em cima, 17 embaixo, nenhum aviso e nenhuma linha com `andar` = `None`. A soma das duas contagens tem que dar 358.

---

### Task 8: API

**Files:**
- Modify: `src/ml/studio/api.py:540-548` (`plan_paredes`), `:576-593` (`Calibracao`, `plan_salvar`)

- [ ] **Step 1: `GET /api/plan/{predio}/paredes` com formato e deslocamento**

Substitua `plan_paredes` por:

```python
@app.get('/api/plan/{predio}/paredes')
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str, formato: str = 'px',
                 dx: float = 0.0, dy: float = 0.0):
  env = _envelope(predio)
  registro = {'arquivo': arquivo, 'origem': origem, 'eixo_x': eixo_x, 'formato': formato, 'dx': dx, 'dy': dy}
  try:
    paredes, papel = plans.ler_registro(registro, env['w'], env['h'])
    return {'paredes': paredes, 'papel': papel}
  except (OSError, ValueError, KeyError) as erro:
    raise HTTPException(422, str(erro))
```

- [ ] **Step 2: `POST /api/plan/{predio}` com andar**

Troque a classe `Calibracao` por:

```python
class Calibracao(BaseModel):
  paredes: Optional[dict] = None
  foto: Optional[dict] = None
  andar: Optional[str] = None
```

E, em `plan_salvar`, troque:

```python
    plans.salvar_calibracao(predio, corpo.paredes, corpo.foto)
```

por:

```python
    plans.salvar_calibracao(predio, corpo.paredes, corpo.foto, andar=corpo.andar)
```

Isso basta: o `andar` de cada linha não muda com a calibração, porque os andares e os `z_min` não são editados pela UI.

- [ ] **Step 3: Reiniciar o Studio e testar com curl**

O payload fica em cache no processo, então é preciso reiniciar:

```bash
pkill -f "src/ml/studio.py" ; sleep 1
nohup venv/bin/python3 src/ml/studio.py --port 8100 > /tmp/qoe-studio.log 2>&1 &
sleep 4
curl -s "http://127.0.0.1:8100/api/plan/casa-marcelo/paredes?arquivo=planta-casa-cima.csv&origem=superior-esquerdo&eixo_x=horizontal&formato=metros&dx=0&dy=0" | head -c 200; echo
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8100/api/plan/casa-marcelo/paredes?arquivo=planta-casa-cima.csv&origem=superior-esquerdo&eixo_x=horizontal&formato=polegadas"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8100/api/plan/casa/paredes?arquivo=Coordenadas_CSV_2D_casa_roni_v2.csv&origem=inferior-esquerdo&eixo_x=horizontal"
```
Expected: o primeiro começa com `{"paredes":[[0.0,0.0,861.0,0.0]`, o segundo imprime `422` e o terceiro `200`. Não faça POST aqui: os valores de `dx`/`dy` quem define é o usuário, na calibração.

---

### Task 9: `drawFloorPlan` sem roteador

**Files:**
- Modify: `src/ml/studio/static/graficos.js:274-290`

- [ ] **Step 1: Envolver o desenho do roteador**

Troque o bloco que começa em `// Roteador: marca de identidade, nunca uma cor de serie.` e termina em `ctx.fillText('roteador', rx, ry + 24);` por:

```js
    // Roteador: marca de identidade, nunca uma cor de serie. Andar sem roteador vem com routerX nulo.
    if (env.routerX != null && env.routerY != null) {
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
    }
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/graficos.js && echo ok`
Expected: `ok`

---

### Task 10: Um cartão por andar em `renderPlan`

**Files:**
- Modify: `src/ml/studio/static/studio.js:195-214` (`renderPlan`, até antes de `V.views.planta.render({`)

- [ ] **Step 1: Substituir o começo de `renderPlan`**

Troque o trecho de `/* ---------------- planta ---------------- */` até `    });` (o fim do `forEach` sobre `state.data.envelopes`, linha 214) por:

```js
  /* ---------------- planta ---------------- */
  function pontos(rows) {
    const groups = new Map();
    rows.forEach((r) => {
      const k = `${r.x}|${r.y}`;
      if (!groups.has(k)) groups.set(k, { x: r.x, y: r.y, p: r.p, rows: [] });
      groups.get(k).rows.push(r);
    });
    return [...groups.values()].map((g) => {
      const pct = 100 * g.rows.filter((r) => meets(r, state.thr)).length / g.rows.length;
      return { x: g.x, y: g.y, n: g.rows.length, value: pct, label: g.p, color: rampColor(pct) };
    });
  }

  function renderPlan() {
    const rows = activeRows().filter((r) => r.x != null);
    const predios = [];
    Object.entries(state.data.envelopes).forEach(([b, env]) => {
      const mine = rows.filter((r) => r.b === b);
      if (!mine.length) return;
      const label = state.data.buildings[b].label;
      const planta = (state.data.plantas || {})[b] || null;
      if (!planta || !planta.andares) {
        predios.push({ k: b, b, andar: null, label, env, points: pontos(mine), planta });
        return;
      }
      // r.andar vem do servidor (plans.andar_de); aqui so se separa por andar.
      const semAndar = mine.filter((r) => r.andar == null).length;
      planta.andares.forEach((a, i) => {
        const extras = i > 0 ? [] : planta.avisos.concat(
          semAndar ? [`${semAndar} linha(s) sem z ficaram fora da planta`] : []);
        predios.push({
          k: `${b}|${a.id}`, b, andar: a.id, label: `${label} · ${a.id}`,
          env: a.roteador ? env : Object.assign({}, env, { routerX: null, routerY: null }),
          points: pontos(mine.filter((r) => r.andar === a.id)),
          planta: Object.assign({}, a, { avisos: a.avisos.concat(extras) }),
        });
      });
    });
```

O resto de `renderPlan` (a chamada `V.views.planta.render({...})`) não muda.

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/studio.js && echo ok`
Expected: `ok`

---

### Task 11: Calibração por andar em `planta.js`

**Files:**
- Modify: `src/ml/studio/static/planta.js` (`render`, `abrirCalibracao`, `carregarParedes`, `renderCalibracao`, `salvar`, listener `change`)

Cada cartão passa a ser identificado por `p.k`: o prédio, ou `prédio|andar`. `p.b` continua sendo o prédio, que é o que vai nas URLs da API.

- [ ] **Step 1: `render` usa `p.k`**

Em `render`, troque `data-calibrar="${esc(p.b)}"` por `data-calibrar="${esc(p.k)}"`. No segundo `forEach` (`pendentes.forEach`), troque as duas ocorrências de `st.hits[p.b]` por `st.hits[p.k]`:

```js
    pendentes.forEach(({ p, pl, wrap }) => {
      const canvas = wrap.querySelector('canvas');
      st.hits[p.k] = V.drawFloorPlan(canvas, especificacao(p, pl));
      V.attachTooltip(canvas, wrap.querySelector('.tooltip'), () => st.hits[p.k], tooltip);
    });
```

- [ ] **Step 2: `abrirCalibracao` e `carregarParedes`**

Substitua as duas funções por:

```js
  async function abrirCalibracao(k) {
    const p = st.ctx.predios.find((x) => x.k === k);
    const cal = (p.planta && p.planta.calibracao) || { paredes: null, foto: null };
    const arquivos = await fetch('api/plan/arquivos').then((r) => r.json());
    const cp = cal.paredes || {};
    const cf = cal.foto || {};
    st.cal = { k, b: p.b, andar: p.andar, arquivos, csv: cp.arquivo || '',
               formato: cp.formato || (p.andar ? 'metros' : 'px'), dx: cp.dx || 0, dy: cp.dy || 0,
               origem: cp.origem || (p.andar ? 'superior-esquerdo' : 'inferior-direito'),
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
    const q = new URLSearchParams({ arquivo: c.csv, origem: c.origem, eixo_x: c.eixo,
                                    formato: c.formato, dx: c.dx, dy: c.dy });
    const r = await fetch(`api/plan/${encodeURIComponent(c.b)}/paredes?${q}`);
    const corpo = await r.json().catch(() => ({}));
    if (r.ok) c.paredes = corpo;
    else c.erro = typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`;
  }
```

- [ ] **Step 3: `renderCalibracao`**

Substitua a função inteira por:

```js
  function renderCalibracao() {
    const host = $('#planCal');
    const c = st.cal;
    const p = c && st.ctx.predios.find((x) => x.k === c.k);
    if (!p) { st.cal = null; host.innerHTML = ''; host.classList.add('hide'); return; }
    host.classList.remove('hide');
    const passos = ['(0, 0), a origem', `(${p.env.w}, 0)`, `(${p.env.w}, ${p.env.h})`, `(0, ${p.env.h})`];
    const opcoes = (lista, atual, vazio) => `<option value="">${vazio}</option>` +
      lista.map((n) => `<option${n === atual ? ' selected' : ''}>${esc(n)}</option>`).join('');
    const escolha = (lista, atual, campo) => `<select data-campo="${campo}">` +
      lista.map((k) => `<option${k === atual ? ' selected' : ''}>${k}</option>`).join('') + '</select>';
    const passo = c.cantos.length < 4 ? `Clique no canto <b>${passos[c.cantos.length]}</b> do envelope na foto.`
      : 'Os 4 cantos estão marcados. Confira a pré-visualização.';
    const deslocamento = c.formato === 'metros'
      ? `<label>dx (cm)</label><input type="number" step="1" data-campo="dx" value="${c.dx}">
         <label>dy (cm)</label><input type="number" step="1" data-campo="dy" value="${c.dy}">` : '';
    const explicacao = c.andar
      ? `Paredes em metros no envelope dos dados (${p.env.w} × ${p.env.h} cm). Ajuste dx/dy até os pontos deste andar caírem nos cômodos. Nada é gravado antes de salvar.`
      : `Os cantos são os do envelope dos dados (${p.env.w} × ${p.env.h} cm), a partir da origem. Nada é gravado antes de salvar.`;
    const blocoFoto = c.andar ? '' : `<div class="controls"><label>Foto</label><select data-campo="foto">${opcoes(c.arquivos.fotos, c.foto, 'nenhuma foto')}</select>
          <button class="btn" data-cal="desfazer"${c.cantos.length ? '' : ' disabled'}>Desfazer</button>
          <button class="btn" data-cal="recomecar"${c.cantos.length ? '' : ' disabled'}>Recomeçar</button></div>
        ${c.foto ? `<p class="hint">${passo}</p><div class="cal-foto"><canvas id="calFoto"></canvas></div>`
          : '<p class="hint">Sem foto: o registro usa só as paredes.</p>'}`;
    host.innerHTML = `<div class="card"><div class="card-head"><div><h2>Calibrar planta · ${esc(p.label)}</h2>
      <p class="hint">${explicacao}</p></div>
      <div><button class="btn" data-cal="cancelar">Cancelar</button> <button class="btn-pri" data-cal="salvar">Salvar calibração</button></div></div>
      ${c.erro ? `<div class="plan-aviso">${ALERTA}${esc(c.erro)}</div>` : ''}
      <div class="cal-grid"><div>
        <div class="controls"><label>Paredes</label><select data-campo="csv">${opcoes(c.arquivos.paredes, c.csv, 'nenhum CSV')}</select>
          <label>Formato</label>${escolha(['px', 'metros'], c.formato, 'formato')}
          <label>Origem</label><select data-campo="origem">${ORIGENS.map(([k, r]) => `<option value="${k}"${k === c.origem ? ' selected' : ''}>${r}</option>`).join('')}</select>
          <label>Eixo x</label>${escolha(['horizontal', 'vertical'], c.eixo, 'eixo')}
          ${deslocamento}</div>
        ${blocoFoto}
      </div><div><p class="hint">Pré-visualização</p>
        <div class="chartwrap"><canvas id="calPrevia"></canvas><div class="tooltip" id="calTip"></div></div></div></div></div>`;
    desenharFoto();
    desenharPrevia(p);
  }
```

- [ ] **Step 4: `salvar`**

Substitua a montagem do `corpo` no começo de `salvar`:

```js
    const corpo = {};
    if (c.csv) corpo.paredes = { arquivo: c.csv, origem: c.origem, eixo_x: c.eixo };
    if (c.foto) corpo.foto = { arquivo: c.foto, cantos: c.cantos.length === 4 ? c.cantos : null };
```

por:

```js
    const corpo = {};
    if (c.csv) {
      corpo.paredes = Object.assign({ arquivo: c.csv, origem: c.origem, eixo_x: c.eixo },
        c.formato === 'metros' ? { formato: 'metros', dx: c.dx, dy: c.dy } : {});
    }
    if (c.andar) corpo.andar = c.andar;
    else if (c.foto) corpo.foto = { arquivo: c.foto, cantos: c.cantos.length === 4 ? c.cantos : null };
```

- [ ] **Step 5: Listener `change` converte dx/dy para número**

No listener `$('#planCal').addEventListener('change', ...)`, troque:

```js
    c[campo] = ev.target.value;
```

por:

```js
    c[campo] = campo === 'dx' || campo === 'dy' ? (Number(ev.target.value) || 0) : ev.target.value;
```

- [ ] **Step 6: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/planta.js && echo ok`
Expected: `ok`

---

### Task 12: Verificação final

- [ ] **Step 1: Suíte completa**

Run: `venv/bin/python -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`. Eram 201 testes; com os 18 novos devem ser 219.

- [ ] **Step 2: Reiniciar o Studio e conferir o payload**

```bash
pkill -f "src/ml/studio.py" ; sleep 1
nohup venv/bin/python3 src/ml/studio.py --port 8100 > /tmp/qoe-studio.log 2>&1 &
sleep 4
curl -s http://127.0.0.1:8100/api/payload | venv/bin/python -c "
import json, sys
d = json.load(sys.stdin)
print([(a['id'], a['roteador']) for a in d['plantas']['casa-marcelo']['andares']])
print(sorted(k for k, v in d['plantas'].items() if 'andares' not in v))
print(d['envelopes']['casa-marcelo']['routerZ'])
"
```
Expected:
```
[('cima', True), ('baixo', False)]
['casa', 'cowork-pedra-branca', 'hotmilk']
80.0
```

- [ ] **Step 3: Entregar para a validação visual do usuário**

Não dá para calibrar sem olhar a planta, então esta parte é do usuário. Informe a URL `http://127.0.0.1:8100` e peça que ele confira na view Planta:
1. aparecem dois cartões, "Casa do Marcelo · cima" e "Casa do Marcelo · baixo", e o roteador só no de cima;
2. "Calibrar planta" em cada andar mostra Formato `metros`, `dx`/`dy` e nenhum bloco de foto; mudar `dx`/`dy` move as paredes na pré-visualização;
3. depois de salvar, o `docs/planta/plantas.json` guarda `dx`/`dy` só daquele andar;
4. `casa`, `cowork-pedra-branca` e `hotmilk` estão iguais a antes, inclusive a calibração com foto da `casa`.

- [ ] **Checkpoint:** liste os arquivos alterados e criados para o usuário commitar. Não rode git.
