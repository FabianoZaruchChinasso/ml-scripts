# Upload de dados e reavaliação de versões: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incluir dados de uma casa nova pelo QoE Studio (upload com prévia e cadastro de prédio) e reavaliar versões existentes do `modelos.json` sem criar versão nova.

**Architecture:** Os prédios saem do código para `src/ml/core/predios.json`, lido por `core/sites.py` com a mesma API pública de hoje. Um módulo novo, `studio/ingestao.py`, guarda o arquivo enviado sob um token, monta a prévia e grava em `data/` na confirmação. `core/modelos.py` ganha `reavaliar`, que troca só `avaliacao`, `cobertura` e acrescenta ao `historico`. A API expõe as rotas finas e a interface usa o painel Conjunto (upload) e a área Modelo (reavaliar).

**Tech Stack:** Python 3.12, FastAPI 0.141 (sem `httpx` nem `python-multipart`: rotas testadas chamando a função direto), pandas, unittest; front em JavaScript puro (`src/ml/studio/static/`).

**Spec:** `docs/superpowers/specs/2026-10-20-upload-dados-reavaliar-design.md`

---

## Regras do repositório (leia antes de começar)

- **Commits são do usuário.** Nunca rode `git commit` nem `git push`. Nos passos "Commit", só rode `git add` e mostre a mensagem sugerida; o usuário commita à mão. A mensagem **não** leva linha `Co-Authored-By`.
- **Sem emojis** em código, mensagens e interface. Ícones são `<symbol>` SVG em `index.html`.
- Indentação Python de **2 espaços**, comentários e mensagens em português, como no resto do código.
- Testes: `venv/bin/python -m unittest discover -s tests -p '<arquivo>' -v` a partir da raiz (`/home/venko/ml/TR069/ml-scripts`). O `discover -s tests` é necessário: `test_studio_assistente.py` importa `test_studio_features` pelo nome.
- A suíte inteira leva mais de 2 minutos: rode com timeout alto.

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/ml/core/predios.json` (novo) | Registro de prédios: rótulo, chave do Studio, ambiente, prefixos, posições, tetos de WAN, aliases |
| `src/ml/core/sites.py` | Lê, valida, recarrega e grava o registro; resolve `local` em posição e prédio |
| `src/ml/core/carga.py` | Expõe `fingerprint`, `chaves_alvos` e `esquecer_descobertos` |
| `src/ml/core/modelos.py` | `reavaliar` e `nota_reavaliacao`; docstring da regra de imutabilidade |
| `src/ml/studio/data.py` | Prédios do Studio vindos do registro (`predios_studio`, `predio_studio_do_core`, `limpar_cache_predios`) |
| `src/ml/studio/ingestao.py` (novo) | Tokens de upload, prévia e confirmação |
| `src/ml/studio/api.py` | Rotas `/api/datasets/*` e `/api/modelos/reavaliar`; limpeza de caches |
| `src/ml/studio/static/studio.js` | `V.app.recarregarPayload` |
| `src/ml/studio/static/conjunto.js` | Botão, prévia e cadastro de prédio |
| `src/ml/studio/static/modelo.js` | Reavaliar no menu do cartão e em lote |
| `src/ml/studio/static/index.html` | Ícone `i-refresh` |
| `src/ml/studio/static/styles.css` | Estilos do formulário de upload e da barra de reavaliação |
| `tests/test_sites_predios.py` (novo) | Equivalência, validação e cadastro de prédios |
| `tests/test_studio_upload.py` (novo) | Ingestão e rotas de upload |
| `tests/test_modelos_core.py` | `reavaliar` e `nota_reavaliacao` |
| `tests/test_studio_reavaliar.py` (novo) | Rota de reavaliação |
| `CHANGELOG.md` | Entrada da mudança |

---

### Task 1: `predios.json` e `sites.py` lendo o registro

**Files:**
- Create: `src/ml/core/predios.json`
- Modify: `src/ml/core/sites.py` (reescrita completa)
- Create: `tests/test_sites_predios.py`

- [ ] **Step 1: Escrever o teste de equivalência e de validação (falha)**

Crie `tests/test_sites_predios.py`:

```python
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import sites as S
from ml.core.sites import BUILDING_ENVIRONMENT

# Todos os valores de `local` em data/ em 2026-10-20 e como o código antigo (regras em
# Python) os resolvia: (posição, prédio). O registro em JSON precisa dar o mesmo.
EQUIVALENCIA = {
  '1.0': ('res-sala', 'residencia'), '2.0': ('res-quarto', 'residencia'), '3.0': ('res-suite', 'residencia'),
  'sala': ('res-sala', 'residencia'), 'quarto': ('res-quarto', 'residencia'), 'suite': ('res-suite', 'residencia'),
  'cwpb-1': ('cwpb-1', 'coworking'), 'cwpb-10m': ('cwpb-10m', 'coworking'),
  'cwpb-10m-2a': ('cwpb-10m-2a', 'coworking'), 'cwpb-13m': ('cwpb-13m', 'coworking'),
  'cwpb-2': ('cwpb-2', 'coworking'), 'cwpb-2m': ('cwpb-2m', 'coworking'),
  'hotmilk-aquario': ('hotmilk-aquario', 'hotmilk'), 'hotmilk-aquario-fora': ('hotmilk-aquario-fora', 'hotmilk'),
  'hotmilk-copa': ('hotmilk-copa', 'hotmilk'), 'quarto-marcelo': ('hotmilk-aquario', 'hotmilk'),
  'marcelo-copa': ('marcelo-copa', 'casa-marcelo'), 'marcelo-copa-split': ('marcelo-copa-split', 'casa-marcelo'),
  'marcelo-inf-ext': ('marcelo-inf-ext', 'casa-marcelo'), 'marcelo-inf-quarto': ('marcelo-inf-quarto', 'casa-marcelo'),
  'marcelo-inf-quarto-split': ('marcelo-inf-quarto-split', 'casa-marcelo'),
  'marcelo-inf-sala': ('marcelo-inf-sala', 'casa-marcelo'), 'marcelo-inf-sala-split': ('marcelo-inf-sala-split', 'casa-marcelo'),
  'marcelo-quarto': ('marcelo-quarto', 'casa-marcelo'), 'marcelo-quarto-split': ('marcelo-quarto-split', 'casa-marcelo'),
  'marcelo-sala-estar': ('marcelo-sala-estar', 'casa-marcelo'),
}


class TestEquivalencia(unittest.TestCase):
  def test_registro_resolve_como_o_codigo_antigo(self):
    valores = pd.Series(list(EQUIVALENCIA))
    posicoes = list(S.resolve_site_id(valores))
    predios = list(S.resolve_site_id(valores, level='building'))
    self.assertEqual(posicoes, [p for p, _ in EQUIVALENCIA.values()])
    self.assertEqual(predios, [b for _, b in EQUIVALENCIA.values()])

  def test_ambientes_e_tetos(self):
    self.assertEqual(BUILDING_ENVIRONMENT, {'residencia': 'domestico', 'coworking': 'corporativo',
                                            'hotmilk': 'corporativo', 'casa-marcelo': 'domestico'})
    self.assertEqual(S.teto_wan('residencia', 'speedtest_up_mbps'), 99.0)
    self.assertIsNone(S.teto_wan('hotmilk', 'speedtest_down_mbps'))

  def test_valor_desconhecido_cita_o_registro(self):
    with self.assertRaises(ValueError) as ctx:
      S.resolve_site_id(pd.Series(['villa-sala']))
    self.assertIn('villa-sala', str(ctx.exception))
    self.assertIn('predios.json', str(ctx.exception))


class TestValidacao(unittest.TestCase):
  def setUp(self):
    self.reg = S.registro_atual()

  def recusa(self, trecho):
    with self.assertRaises(ValueError) as ctx:
      S.validar_predios(self.reg)
    self.assertIn(trecho, str(ctx.exception))

  def test_registro_atual_e_valido_e_uma_copia(self):
    S.validar_predios(self.reg)
    self.reg['predios'].clear()
    self.assertIn('hotmilk', S.registro_atual()['predios'])

  def test_recusa_prefixo_que_comeca_com_outro(self):
    self.reg['predios']['casa-marcelo']['prefixos'].append('marcelo2')
    self.recusa('marcelo2')

  def test_recusa_prefixo_repetido_entre_predios(self):
    self.reg['predios']['coworking']['prefixos'].append('hotmilk')
    self.recusa('hotmilk')

  def test_recusa_ambiente_invalido(self):
    self.reg['predios']['hotmilk']['ambiente'] = 'industrial'
    self.recusa('industrial')

  def test_recusa_chave_invalida(self):
    self.reg['predios']['Casa Nova'] = copy.deepcopy(self.reg['predios']['hotmilk'])
    self.reg['predios']['Casa Nova']['prefixos'] = ['nova']
    self.reg['predios']['Casa Nova']['studio'] = 'nova'
    self.recusa('Casa Nova')

  def test_recusa_predio_sem_prefixo_e_sem_posicoes(self):
    self.reg['predios']['hotmilk']['prefixos'] = []
    self.recusa('hotmilk')

  def test_recusa_chave_do_studio_repetida(self):
    self.reg['predios']['hotmilk']['studio'] = 'casa'
    self.recusa('casa')

  def test_recusa_posicao_que_comeca_com_prefixo(self):
    self.reg['predios']['residencia']['posicoes']['cwpb-x'] = 'res-sala'
    self.recusa('cwpb-x')


class TestCadastro(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.path)
    S.recarregar(self.path)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    shutil.rmtree(self.pasta)

  def villa(self, **extra):
    return dict({'chave': 'casa-villa', 'rotulo': 'Casa do Villa', 'ambiente': 'domestico', 'prefixo': 'villa'}, **extra)

  def test_cadastra_grava_e_resolve(self):
    S.cadastrar_predios([self.villa()])
    self.assertEqual(list(S.resolve_site_id(pd.Series(['villa-sala']), level='building')), ['casa-villa'])
    with open(self.path, encoding='utf-8') as h:
      gravado = json.load(h)['predios']['casa-villa']
    self.assertEqual(gravado, {'rotulo': 'Casa do Villa', 'studio': 'casa-villa', 'ambiente': 'domestico',
                               'prefixos': ['villa']})

  def test_atualiza_o_dicionario_importado_no_lugar(self):
    antes = BUILDING_ENVIRONMENT
    S.cadastrar_predios([self.villa()])
    self.assertIs(antes, S.BUILDING_ENVIRONMENT)
    self.assertEqual(BUILDING_ENVIRONMENT['casa-villa'], 'domestico')

  def test_recusa_chave_existente_sem_gravar(self):
    with open(self.path, encoding='utf-8') as h:
      antes = h.read()
    with self.assertRaises(ValueError):
      S.cadastrar_predios([self.villa(chave='hotmilk')])
    with open(self.path, encoding='utf-8') as h:
      self.assertEqual(h.read(), antes)

  def test_recusa_prefixo_em_conflito(self):
    with self.assertRaises(ValueError):
      S.cadastrar_predios([self.villa(prefixo='marcelo2')])
    self.assertNotIn('casa-villa', BUILDING_ENVIRONMENT)

  def test_recusa_campos_faltando(self):
    with self.assertRaises(ValueError):
      S.cadastrar_predios([{'chave': 'casa-villa', 'prefixo': 'villa'}])

  def test_com_novos_nao_toca_no_registro(self):
    reg = S.registro_atual()
    novo = S.com_novos(reg, [self.villa()])
    self.assertIn('casa-villa', novo['predios'])
    self.assertNotIn('casa-villa', reg['predios'])

  def test_resolve_com_registro_explicito(self):
    reg = S.com_novos(S.registro_atual(), [self.villa()])
    self.assertEqual(list(S.resolve_site_id(pd.Series(['villa-x']), level='building', registro=reg)), ['casa-villa'])
    with self.assertRaises(ValueError):
      S.resolve_site_id(pd.Series(['villa-x']))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_sites_predios.py' -v`
Expected: ERROR/FAIL, com `AttributeError: module 'ml.core.sites' has no attribute 'registro_atual'` e afins.

- [ ] **Step 3: Criar `src/ml/core/predios.json`**

As chaves vão em ordem alfabética porque `gravar_json_atomico` grava com `sort_keys=True`: assim o primeiro cadastro pela tela não reordena o arquivo inteiro no diff.

```json
{
  "aliases": {
    "quarto-marcelo": "hotmilk-aquario"
  },
  "predios": {
    "casa-marcelo": {
      "ambiente": "domestico",
      "prefixos": [
        "marcelo"
      ],
      "rotulo": "Casa do Marcelo",
      "studio": "casa-marcelo"
    },
    "coworking": {
      "ambiente": "corporativo",
      "prefixos": [
        "cwpb"
      ],
      "rotulo": "Cowork Pedra Branca",
      "studio": "cowork-pedra-branca"
    },
    "hotmilk": {
      "ambiente": "corporativo",
      "prefixos": [
        "hotmilk"
      ],
      "rotulo": "Hotmilk",
      "studio": "hotmilk"
    },
    "residencia": {
      "ambiente": "domestico",
      "posicoes": {
        "1": "res-sala",
        "2": "res-quarto",
        "3": "res-suite",
        "quarto": "res-quarto",
        "sala": "res-sala",
        "suite": "res-suite"
      },
      "prefixos": [],
      "rotulo": "Casa",
      "studio": "casa",
      "tetos_wan": {
        "speedtest_down_mbps": 154.0,
        "speedtest_up_mbps": 99.0
      }
    }
  }
}
```

- [ ] **Step 4: Reescrever `src/ml/core/sites.py`**

Substitua o arquivo inteiro por:

```python
"""Prédios e posições de coleta: de qual posição, prédio e ambiente é cada `local`.

O registro vive em predios.json, versionado e gravado pelo QoE Studio (cadastro de
prédio novo no upload de dados). Treino e Studio leem o mesmo arquivo, então nunca
discordam sobre de qual prédio é uma linha.
"""

import copy
import json
import math
import os
import re
import threading

import pandas as pd

from ml.core.arquivos import gravar_json_atomico

PREDIOS_PATH = os.path.join(os.path.dirname(__file__), 'predios.json')

# Ambiente de cada local de coleta. Doméstico e corporativo diferem em
# densidade de redes vizinhas, perfil de tráfego e distâncias: é o eixo que
# decide se um modelo treinado num pode ser usado no outro.
DOMESTIC = 'domestico'
CORPORATE = 'corporativo'
ENVIRONMENTS = (DOMESTIC, CORPORATE)
GROUP_LEVELS = ('position', 'building')

NOME = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
CAMPOS_OBRIGATORIOS = {'rotulo', 'studio', 'ambiente', 'prefixos'}
CAMPOS = CAMPOS_OBRIGATORIOS | {'posicoes', 'tetos_wan'}
CAMPOS_NOVO = {'chave', 'rotulo', 'ambiente', 'prefixo'}

# Preenchidos por recarregar() e mutados no lugar: carga.py, studio/api.py e os
# testes importam estes nomes, e uma reatribuição deixaria quem importou com a cópia velha.
BUILDING_ENVIRONMENT = {}
# Teto do plano de WAN por prédio e por alvo (Mbps): acima disto o speedtest mede a
# internet, não o Wi-Fi. Inferido pelo p99 em 2026-10-05 na residência. Prédio
# ausente = sem teto conhecido.
TETOS_WAN = {}
_estado = {'path': PREDIOS_PATH, 'registro': None}
_lock = threading.Lock()


def _texto(valor) -> bool:
  return isinstance(valor, str) and bool(valor.strip())


def _validar_predio(chave: str, p) -> None:
  if not NOME.match(chave):
    raise ValueError(f'{chave!r}: chave de prédio inválida (minúsculas, dígitos e hífen, 2 a 40 caracteres)')
  if not isinstance(p, dict) or not CAMPOS_OBRIGATORIOS <= set(p) <= CAMPOS:
    raise ValueError(f'{chave!r}: campos inválidos {sorted(p) if isinstance(p, dict) else p!r}; '
                     f'obrigatórios {sorted(CAMPOS_OBRIGATORIOS)}')
  if not _texto(p['rotulo']) or len(p['rotulo']) > 60:
    raise ValueError(f'{chave!r}: rótulo obrigatório, de até 60 caracteres')
  if not isinstance(p['studio'], str) or not NOME.match(p['studio']):
    raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} inválida")
  if p['ambiente'] not in ENVIRONMENTS:
    raise ValueError(f"{chave!r}: ambiente {p['ambiente']!r} inválido; esperado um de {list(ENVIRONMENTS)}")
  prefixos = p['prefixos']
  if not isinstance(prefixos, list) or not all(isinstance(x, str) and NOME.match(x) for x in prefixos):
    raise ValueError(f'{chave!r}: prefixos precisam ser minúsculas, dígitos e hífen, 2 a 40 caracteres')
  posicoes = p.get('posicoes', {})
  if not isinstance(posicoes, dict) or not all(
      isinstance(k, str) and k == k.strip().lower() and _texto(v) for k, v in posicoes.items()):
    raise ValueError(f'{chave!r}: posicoes precisa ser {{valor em minúsculas: posição}}')
  if not prefixos and not posicoes:
    raise ValueError(f'{chave!r}: prédio sem prefixos precisa de posicoes')
  tetos = p.get('tetos_wan', {})
  if not isinstance(tetos, dict) or not all(
      isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in tetos.values()):
    raise ValueError(f'{chave!r}: tetos_wan precisa ser {{alvo: Mbps positivo}}')


def validar_predios(registro) -> None:
  """Levanta ValueError com a causa; não devolve nada quando o registro é válido."""
  if not isinstance(registro, dict) or set(registro) != {'predios', 'aliases'}:
    raise ValueError("predios.json precisa ter exatamente as chaves 'predios' e 'aliases'")
  predios, aliases = registro['predios'], registro['aliases']
  if not isinstance(predios, dict) or not predios:
    raise ValueError('predios.json precisa de pelo menos um prédio')
  if not isinstance(aliases, dict) or not all(_texto(k) and _texto(v) for k, v in aliases.items()):
    raise ValueError('aliases precisa ser {valor antigo: valor corrigido}')
  donos_studio, prefixos = {}, []
  for chave, p in predios.items():
    _validar_predio(chave, p)
    if p['studio'] in donos_studio:
      raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} já usada por {donos_studio[p['studio']]!r}")
    donos_studio[p['studio']] = chave
    prefixos += [(x, chave) for x in p['prefixos']]
  # `startswith` decide o prédio: dois prefixos em que um começa com o outro
  # tornariam a resolução dependente da ordem do arquivo.
  for i, (a, dono_a) in enumerate(prefixos):
    for b, dono_b in prefixos[i + 1:]:
      if a.startswith(b) or b.startswith(a):
        raise ValueError(f'prefixos em conflito: {a!r} ({dono_a}) e {b!r} ({dono_b}); um começa com o outro')
  soltos = [k for p in predios.values() for k in p.get('posicoes', {})] + list(aliases)
  for valor in soltos:
    for prefixo, dono in prefixos:
      if valor.startswith(prefixo):
        raise ValueError(f'{valor!r} começa com o prefixo {prefixo!r} de {dono!r}: a resolução ficaria ambígua')


def carregar_predios(path: str = None) -> dict:
  with open(path or _estado['path'], encoding='utf-8') as handle:
    registro = json.load(handle)
  validar_predios(registro)
  return registro


def _aplicar(registro: dict) -> None:
  _estado['registro'] = registro
  BUILDING_ENVIRONMENT.clear()
  BUILDING_ENVIRONMENT.update({k: p['ambiente'] for k, p in registro['predios'].items()})
  TETOS_WAN.clear()
  TETOS_WAN.update({k: dict(p['tetos_wan']) for k, p in registro['predios'].items() if p.get('tetos_wan')})


def recarregar(path: str = None) -> None:
  """Relê o registro (de `path`, que passa a ser o arquivo em uso, ou do atual)."""
  with _lock:
    if path:
      _estado['path'] = path
    _aplicar(carregar_predios(_estado['path']))


def registro_atual() -> dict:
  """Cópia do registro em uso: quem altera a cópia não altera o registro."""
  return copy.deepcopy(_estado['registro'])


def _entrada_nova(novo) -> tuple:
  if not isinstance(novo, dict) or set(novo) != CAMPOS_NOVO or not all(_texto(novo[c]) for c in CAMPOS_NOVO):
    raise ValueError(f'prédio novo precisa de {sorted(CAMPOS_NOVO)} preenchidos')
  chave = novo['chave'].strip()
  return chave, {'rotulo': novo['rotulo'].strip(), 'studio': chave, 'ambiente': novo['ambiente'],
                 'prefixos': [novo['prefixo'].strip().lower()]}


def com_novos(registro: dict, novos) -> dict:
  """Cópia de `registro` com os prédios novos ({chave, rotulo, ambiente, prefixo}). Não valida o todo."""
  saida = copy.deepcopy(registro)
  for novo in novos:
    chave, entrada = _entrada_nova(novo)
    if chave in saida['predios']:
      raise ValueError(f'o prédio {chave!r} já existe')
    saida['predios'][chave] = entrada
  return saida


def cadastrar_predios(novos) -> dict:
  """Acrescenta prédios ao arquivo em uso. Valida o registro inteiro antes de gravar."""
  with _lock:
    path = _estado['path']
    registro = com_novos(carregar_predios(path), novos)
    validar_predios(registro)
    gravar_json_atomico(path, registro)
    _aplicar(registro)
  return copy.deepcopy(registro)


def teto_wan(predio: str, alvo: str):
  """Teto de WAN do prédio para o alvo, ou None quando não há teto conhecido."""
  return TETOS_WAN.get(predio, {}).get(alvo)


def _lookup_key(value) -> str:
  """Canonicaliza uma célula de `local`: '1.0' e 'Sala' viram chaves de busca."""
  if pd.isna(value):
    raise ValueError(
      "site resolution failed: 'local' contains an empty value. "
      'Every row must belong to a known position.'
    )
  text = str(value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  if not math.isfinite(number) or not number.is_integer():
    raise ValueError(
      f'site resolution failed: unrecognised local value {value!r}. '
      'Register its building in core/predios.json; never let an unknown value form its own group.'
    ) from None
  return str(int(number))


def _resolve_one(value, level: str, registro: dict) -> str:
  key = _lookup_key(value)
  key = registro['aliases'].get(key, key)
  for chave, p in registro['predios'].items():
    if any(key.startswith(prefixo) for prefixo in p['prefixos']):
      return chave if level == 'building' else key
  for chave, p in registro['predios'].items():
    posicao = p.get('posicoes', {}).get(key)
    if posicao is not None:
      return chave if level == 'building' else posicao
  raise ValueError(
    f'site resolution failed: unrecognised local value {value!r}. '
    'Register its building in core/predios.json (QoE Studio: Conjunto > Adicionar dados); '
    'never let an unknown value form its own group.'
  )


def resolve_site_id(local_values: pd.Series, level: str = 'position', registro: dict = None) -> pd.Series:
  """Mapeia valores brutos de `local` para identificadores canônicos de grupo.

  `local` é a posição de medição dentro de um prédio: a residência usa nomes de
  cômodo (reescritos como 1/2/3 pelo transform), os demais usam um prefixo por
  prédio (`cwpb-*`, `hotmilk-*`, `marcelo-*`), tudo em predios.json.

  level='position' -> um grupo por ponto de medição.
  level='building' -> um grupo por local de coleta: é o nível que não vaza o
  prédio entre treino e teste.
  `registro` permite resolver contra um registro que ainda não foi gravado (prévia do upload).
  """
  if level not in GROUP_LEVELS:
    raise ValueError(
      f'unknown group level {level!r}; expected one of {list(GROUP_LEVELS)}')
  reg = registro if registro is not None else _estado['registro']
  return local_values.map(lambda value: _resolve_one(value, level, reg))


def resolve_environment(local_values: pd.Series) -> pd.Series:
  """Mapeia valores brutos de `local` para o ambiente: `domestico` ou `corporativo`."""
  return resolve_site_id(local_values, level='building').map(BUILDING_ENVIRONMENT)


recarregar()
```

- [ ] **Step 5: Atualizar a mensagem de descarte em `src/ml/core/carga.py`**

Em `carga.py` (por volta da linha 295), troque:

```python
    avisos.append(f'{fora} linhas com local desconhecido em core/sites.py descartadas: '
```

por:

```python
    avisos.append(f'{fora} linhas com local desconhecido em core/predios.json descartadas: '
```

- [ ] **Step 6: Rodar os testes novos e os antigos de sites**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_sites_predios.py' -v`
Expected: todos PASS.

Run: `venv/bin/python -m unittest discover -s tests -p 'test_ml_core.py' -v`
Expected: todos PASS. `test_unknown_value_raises` continua passando porque a mensagem cita o valor.

Run: `venv/bin/python -m unittest discover -s tests -p 'test_carga.py' -v`
Expected: todos PASS (`teto_wan('residencia', ...)` vem do JSON).

- [ ] **Step 7: Commit (o usuário roda)**

```bash
git add src/ml/core/predios.json src/ml/core/sites.py src/ml/core/carga.py tests/test_sites_predios.py
```

Mensagem sugerida: `feat: prédios de coleta em core/predios.json, lido por sites.py`

---

### Task 2: Studio lê os prédios do registro

**Files:**
- Modify: `src/ml/studio/data.py:16-38` e `:59-71`, `:176`
- Modify: `src/ml/studio/api.py:36`, `:767`
- Test: `tests/test_sites_predios.py` (acrescentar classe)

- [ ] **Step 1: Escrever o teste (falha)**

Acrescente ao fim de `tests/test_sites_predios.py`, antes do `if __name__`:

```python
class TestStudio(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.path)
    S.recarregar(self.path)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    from ml.studio import data as D
    D.limpar_cache_predios()
    shutil.rmtree(self.pasta)

  def test_predios_do_studio_vem_do_registro(self):
    from ml.studio import data as D
    self.assertEqual(D.predios_studio()['casa'], {'label': 'Casa', 'ambiente': 'domestico'})
    self.assertEqual(D.predio_studio_do_core('residencia'), 'casa')

  def test_predio_cadastrado_aparece_depois_de_limpar_o_cache(self):
    from ml.studio import data as D
    with self.assertRaises(ValueError):
      D._building_of('villa-sala')
    S.cadastrar_predios([{'chave': 'casa-villa', 'rotulo': 'Casa do Villa', 'ambiente': 'domestico',
                          'prefixo': 'villa'}])
    D.limpar_cache_predios()
    self.assertEqual(D._building_of('villa-sala'), 'casa-villa')
    self.assertIn('casa-villa', D.predios_studio())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_sites_predios.py' -v`
Expected: FAIL/ERROR em `TestStudio` (`predios_studio` não existe).

- [ ] **Step 3: Trocar `BUILDINGS` e `PREDIO_DO_CORE` em `src/ml/studio/data.py`**

Troque o import da linha 16:

```python
from ml.core.sites import CORPORATE, DOMESTIC, resolve_site_id
```

por:

```python
from ml.core import sites as core_sites
from ml.core.sites import CORPORATE, DOMESTIC, resolve_site_id
```

Apague o bloco das linhas 21 a 38 (o comentário, `BUILDINGS` e `PREDIO_DO_CORE`) e ponha no lugar:

```python
# Rótulo, ambiente e chave do Studio de cada prédio vêm de core/predios.json, o mesmo
# registro que o treino usa: o Studio e o treino nunca discordam, e um prédio
# cadastrado no upload aparece aqui sem mudar código.
def predios_studio() -> dict:
  """{chave do Studio: {'label', 'ambiente'}} de todos os prédios do registro."""
  return {p['studio']: {'label': p['rotulo'], 'ambiente': p['ambiente']}
          for p in core_sites.registro_atual()['predios'].values()}


def predio_studio_do_core(predio: str) -> str:
  """Chave do Studio (a de plantas.json) de um prédio do core."""
  return core_sites.registro_atual()['predios'][predio]['studio']
```

Mantenha `AMBIENTES` e `POSITION_LABELS` como estão.

Troque a função `_building_de_texto` (linhas 59-61) por:

```python
@lru_cache(maxsize=None)
def _building_de_texto(texto: str) -> str:
  return predio_studio_do_core(resolve_site_id(pd.Series([texto]), level='building').iloc[0])


def limpar_cache_predios() -> None:
  """Depois de cadastrar um prédio: valores que antes eram desconhecidos passam a resolver."""
  _building_de_texto.cache_clear()
```

Na montagem do payload (linha 176), troque:

```python
    'buildings': {k: {'label': v['label'], 'ambiente': v['ambiente']} for k, v in BUILDINGS.items()},
```

por:

```python
    'buildings': predios_studio(),
```

- [ ] **Step 4: Ajustar `src/ml/studio/api.py`**

Linha 36, troque:

```python
from ml.studio.data import BUILDINGS, build_payload, descobertos
```

por:

```python
from ml.studio import data as studio_data
from ml.studio.data import build_payload, descobertos, predios_studio
```

Linha 767, troque:

```python
  if predio not in BUILDINGS:
```

por:

```python
  if predio not in predios_studio():
```

- [ ] **Step 5: Conferir que nada mais usa os nomes removidos**

Run: `grep -rn "BUILDINGS\|PREDIO_DO_CORE" src tests --include=*.py`
Expected: nenhuma linha.

- [ ] **Step 6: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_sites_predios.py' -v`
Expected: todos PASS.

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_*.py' -v` (timeout alto)
Expected: todos PASS.

- [ ] **Step 7: Commit (o usuário roda)**

```bash
git add src/ml/studio/data.py src/ml/studio/api.py tests/test_sites_predios.py
```

Mensagem sugerida: `refactor: Studio lê os prédios de core/predios.json`

---

### Task 3: `carga.py` expõe fingerprint, chaves dos alvos e recarga da descoberta

**Files:**
- Modify: `src/ml/core/carga.py:49-91`, `:93-109`
- Test: `tests/test_carga.py` (acrescentar classe)

- [ ] **Step 1: Escrever o teste (falha)**

Acrescente ao fim de `tests/test_carga.py`, antes do `if __name__` (se houver):

```python
class TestFingerprintPublico(unittest.TestCase):
  def frame(self, deslocamento=0.0):
    return pd.DataFrame({a: [1.0 + deslocamento, 2.0, 3.0] for a in ALVOS})

  def test_fingerprint_ignora_ruido_abaixo_da_sexta_casa(self):
    from ml.core import carga as C
    self.assertEqual(C.fingerprint(self.frame()), C.fingerprint(self.frame(1e-12)))
    self.assertNotEqual(C.fingerprint(self.frame()), C.fingerprint(self.frame(0.5)))

  def test_chaves_alvos_e_um_conjunto_de_linhas(self):
    from ml.core import carga as C
    self.assertEqual(len(C.chaves_alvos(self.frame())), 3)

  def test_esquecer_descobertos_refaz_a_varredura(self):
    from ml.core import carga as C
    with mock.patch.object(C, 'discover', side_effect=[['a'], ['b']]):
      C.esquecer_descobertos()
      self.assertEqual(C.descobertos(), ['a'])
      self.assertEqual(C.descobertos(), ['a'])
      C.esquecer_descobertos()
      self.assertEqual(C.descobertos(), ['b'])
    C.esquecer_descobertos()
```

Se `tests/test_carga.py` ainda não importa `mock`, acrescente no topo: `from unittest import mock`. Confira que `pd` já está importado (está, o arquivo usa DataFrames).

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_carga.py' -v`
Expected: ERROR em `TestFingerprintPublico` (`fingerprint` não existe).

- [ ] **Step 3: Implementar em `src/ml/core/carga.py`**

Logo depois de `_generation` (linha 46), acrescente:

```python
def fingerprint(frame: pd.DataFrame) -> str:
  """Identidade dos alvos até a 6a casa: o mesmo critério das duplicatas."""
  alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
  digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
  return digest.hexdigest()[:12]


def chaves_alvos(frame: pd.DataFrame) -> set:
  """Linhas de alvos como tuplas de texto: um dataset está contido noutro quando o conjunto está."""
  return set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))
```

Em `discover`, troque as linhas:

```python
    alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
    digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
```

por nada (apague as duas) e troque `'fingerprint': digest.hexdigest()[:12],` por:

```python
      'fingerprint': fingerprint(frame),
```

Em `_superseded`, troque:

```python
    frame = item['_frame']
    keys = set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))
    keyed[item['id']] = keys
```

por:

```python
    keyed[item['id']] = chaves_alvos(item['_frame'])
```

Depois de `descobertos()`, acrescente:

```python
def esquecer_descobertos() -> None:
  """Dataset novo em data/: a próxima chamada de descobertos() varre a pasta de novo."""
  global _descobertos
  _descobertos = None
```

- [ ] **Step 4: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_carga.py' -v`
Expected: todos PASS.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add src/ml/core/carga.py tests/test_carga.py
```

Mensagem sugerida: `refactor: carga expõe fingerprint, chaves dos alvos e recarga da descoberta`

---

### Task 4: `modelos.reavaliar` e a nota do histórico

**Files:**
- Modify: `src/ml/core/modelos.py:1-7` (docstring) e fim do arquivo
- Test: `tests/test_modelos_core.py` (acrescentar classe)

- [ ] **Step 1: Escrever o teste (falha)**

Acrescente a `tests/test_modelos_core.py`, antes do `if __name__`:

```python
class TestReavaliar(Base):
  AVAL = {'speedtest_down_mbps': {'datasets': ['a.csv', 'b.csv'], 'ambiente': 'todos'},
          'atende_completo': {'media': 0.7}}

  def test_troca_so_avaliacao_e_cobertura_e_acrescenta_historico(self):
    self.salvar()
    antes = M.carregar(self.path)['versoes']['v2']
    M.reavaliar('v2', self.AVAL, {'nivel': 'x'}, '2026-10-20: reavaliada', path=self.path)
    depois = M.carregar(self.path)['versoes']['v2']
    self.assertEqual(depois['avaliacao'], self.AVAL)
    self.assertEqual(depois['cobertura'], {'nivel': 'x'})
    self.assertEqual(depois['historico'], ['2026-10-20: reavaliada'])
    for campo in ('features', 'descricao', 'origem', 'criado_em'):
      self.assertEqual(depois[campo], antes[campo])

  def test_historico_so_cresce(self):
    M.reavaliar('v1', self.AVAL, {}, 'primeira', path=self.path)
    M.reavaliar('v1', self.AVAL, {}, 'segunda', path=self.path)
    self.assertEqual(M.carregar(self.path)['versoes']['v1']['historico'], ['primeira', 'segunda'])

  def test_reavalia_versao_com_vazamento(self):
    # A v1 de produção usa contadores que hoje são vazamento: precisa poder ser reavaliada.
    with open(self.path, 'w', encoding='utf-8') as h:
      json.dump({'ativo': 'v1', 'versoes': {'v1': {'features': ['router_tx_bytes'], 'descricao': 'x'}}}, h)
    M.reavaliar('v1', self.AVAL, {}, 'nota', path=self.path)
    self.assertEqual(M.carregar(self.path)['versoes']['v1']['avaliacao'], self.AVAL)

  def test_recusa_nome_inexistente_e_nota_vazia(self):
    with self.assertRaises(ValueError):
      M.reavaliar('v9', self.AVAL, {}, 'nota', path=self.path)
    with self.assertRaises(ValueError):
      M.reavaliar('v1', self.AVAL, {}, '  ', path=self.path)

  def test_nota_descreve_datasets_e_atende(self):
    antiga = {'speedtest_down_mbps': {'datasets': ['a.csv'], 'ambiente': 'todos'},
              'atende_completo': {'media': 0.6699}}
    nota = M.nota_reavaliacao(antiga, self.AVAL, '2026-10-20')
    self.assertEqual(nota, '2026-10-20: reavaliada; datasets +b.csv; atende completo 0,67 → 0,70')

  def test_nota_sem_avaliacao_antiga_e_com_mesmos_datasets(self):
    self.assertEqual(M.nota_reavaliacao(None, self.AVAL, '2026-10-20'),
                     '2026-10-20: reavaliada; datasets +a.csv +b.csv; atende completo – → 0,70')
    self.assertEqual(M.nota_reavaliacao(self.AVAL, self.AVAL, '2026-10-20'),
                     '2026-10-20: reavaliada; mesmos datasets; atende completo 0,70 → 0,70')

  def test_nota_registra_troca_de_ambiente(self):
    nova = {'speedtest_down_mbps': {'datasets': ['a.csv', 'b.csv'], 'ambiente': 'domestico'},
            'atende_completo': {'media': 0.7}}
    self.assertIn('ambiente todos → domestico', M.nota_reavaliacao(self.AVAL, nova, '2026-10-20'))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_modelos_core.py' -v`
Expected: ERROR em `TestReavaliar` (`reavaliar` não existe).

- [ ] **Step 3: Implementar em `src/ml/core/modelos.py`**

Troque a docstring do módulo (linhas 1-7) por:

```python
"""Registro das versões de modelo: quais features cada versão usa.

Vive em modelos.json, versionado e gravado pelo QoE Studio. A definição de uma
versão salva é imutável (features, denominador, descrição, origem, seleção, data):
mudar uma feature cria uma versão nova. Avaliação e cobertura são relatório e podem
ser recalculadas com dados novos (reavaliar), deixando uma linha no histórico. O
modelo treinado é refeito a partir da definição (e registrado no MLflow quando for
para produção).
"""
```

Acrescente ao fim do arquivo:

```python
# Alvo cujos datasets e ambiente descrevem a avaliação na nota: os quatro alvos usam o mesmo conjunto.
ALVO_DA_NOTA = 'speedtest_down_mbps'


def _media_texto(valor) -> str:
  return '–' if valor is None else f'{valor:.2f}'.replace('.', ',')


def nota_reavaliacao(antiga: Optional[dict], nova: dict, hoje: str) -> str:
  """Linha do histórico: o que mudou de datasets e ambiente, e o atende completo antes e depois."""
  ref_antiga = (antiga or {}).get(ALVO_DA_NOTA) or {}
  ref_nova = nova.get(ALVO_DA_NOTA) or {}
  ds_antes, ds_depois = set(ref_antiga.get('datasets') or []), set(ref_nova.get('datasets') or [])
  mudancas = [f'+{d}' for d in sorted(ds_depois - ds_antes)] + [f'-{d}' for d in sorted(ds_antes - ds_depois)]
  partes = [f'{hoje}: reavaliada', 'datasets ' + ' '.join(mudancas) if mudancas else 'mesmos datasets']
  if antiga and ref_antiga.get('ambiente') != ref_nova.get('ambiente'):
    partes.append(f"ambiente {ref_antiga.get('ambiente') or 'todos'} → {ref_nova.get('ambiente') or 'todos'}")
  media_antes = ((antiga or {}).get('atende_completo') or {}).get('media')
  media_depois = (nova.get('atende_completo') or {}).get('media')
  partes.append(f'atende completo {_media_texto(media_antes)} → {_media_texto(media_depois)}')
  return '; '.join(partes)


def reavaliar(nome: str, avaliacao: dict, cobertura, nota: str, path: str = MODELOS_PATH) -> dict:
  """Troca avaliação e cobertura de uma versão existente e acrescenta `nota` ao histórico.

  Não refaz as checagens de salvar_versao (vazamento, classificação): a definição já
  existe e não muda. A avaliação já descarta da conta as features com vazamento.
  """
  if not _texto(nota):
    raise ValueError('a reavaliação precisa de uma nota para o histórico')
  if not isinstance(avaliacao, dict) or not avaliacao:
    raise ValueError('avaliação vazia')
  with _lock:
    registro = carregar(path)
    if nome not in registro['versoes']:
      raise ValueError(f'versão {nome!r} não existe')
    versao = registro['versoes'][nome]
    versao['avaliacao'] = avaliacao
    versao['cobertura'] = cobertura
    versao['historico'] = list(versao.get('historico') or []) + [nota.strip()]
    validar_registro(registro)
    gravar_json_atomico(path, registro)
  return registro
```

- [ ] **Step 4: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_modelos_core.py' -v`
Expected: todos PASS.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add src/ml/core/modelos.py tests/test_modelos_core.py
```

Mensagem sugerida: `feat: reavaliar versão existente sem mudar a definição`

---

### Task 5: `studio/ingestao.py`: token, prévia e confirmação

**Files:**
- Create: `src/ml/studio/ingestao.py`
- Create: `tests/test_studio_upload.py`

- [ ] **Step 1: Escrever os testes (falham)**

Crie `tests/test_studio_upload.py`:

```python
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import sites as S
from ml.studio import ingestao as I

VILLA = {'chave': 'casa-villa', 'rotulo': 'Casa do Villa', 'ambiente': 'domestico', 'prefixo': 'villa'}


def frame(locais, inicio=10.0, n_clients=1.0, combo='a'):
  n = len(locais)
  base = np.arange(n, dtype=float) + inicio
  return pd.DataFrame({'local': locais, 'speedtest_down_mbps': base, 'speedtest_up_mbps': base / 2,
                       'latency_ms': base + 1, 'jitter_ms': base / 10, 'combo': combo,
                       'n_clients': n_clients, 'station_x': 1.0, 'house_x0': 0.0})


def csv_de(df) -> bytes:
  return df.to_csv(index=False).encode()


def zip_de(df, n_csv=1) -> bytes:
  buf = io.BytesIO()
  with zipfile.ZipFile(buf, 'w') as z:
    for i in range(n_csv):
      z.writestr(f'parte{i}.csv', df.to_csv(index=False))
  return buf.getvalue()


def existente(nome, df):
  return {'id': nome, 'usable': True, 'fingerprint': C.fingerprint(df), '_frame': df}


class Base(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.data = os.path.join(self.pasta, 'data')
    os.mkdir(self.data)
    self.predios = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.predios)
    S.recarregar(self.predios)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    shutil.rmtree(self.pasta)

  def previa(self, conteudo, nome='novo.csv', novos=(), existentes=()):
    token = I.guardar(nome, conteudo)
    return token, I.previa(token, nome, novos, data_dir=self.data, existentes=list(existentes))


class TestPrevia(Base):
  def test_csv_com_predios_conhecidos(self):
    _, p = self.previa(csv_de(frame(['sala', 'cwpb-2m', 'cwpb-2m'])))
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual((p['linhas'], p['geracao']), (3, 'current'))
    self.assertEqual([(x['predio'], x['linhas'], x['novo']) for x in p['predios']],
                     [('coworking', 2, False), ('residencia', 1, False)])

  def test_zip_com_um_csv(self):
    _, p = self.previa(zip_de(frame(['sala'])), nome='novo.zip')
    self.assertEqual(p['bloqueios'], [])

  def test_zip_com_dois_csv_bloqueia(self):
    _, p = self.previa(zip_de(frame(['sala']), n_csv=2), nome='novo.zip')
    self.assertTrue(any('ilegível' in b for b in p['bloqueios']))

  def test_local_desconhecido_agrupa_por_prefixo_e_bloqueia(self):
    _, p = self.previa(csv_de(frame(['villa-sala', 'villa-quarto', 'villa-sala', 'garagem'])))
    self.assertEqual(p['desconhecidos'], [
      {'prefixo': 'garagem', 'valores': ['garagem'], 'linhas': 1},
      {'prefixo': 'villa', 'valores': ['villa-quarto', 'villa-sala'], 'linhas': 3}])
    self.assertTrue(any('local desconhecido' in b for b in p['bloqueios']))

  def test_predio_novo_resolve_na_previa_sem_gravar(self):
    with open(self.predios, encoding='utf-8') as h:
      antes = h.read()
    _, p = self.previa(csv_de(frame(['villa-sala', 'villa-quarto'])), novos=[VILLA])
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual(p['predios'][0]['predio'], 'casa-villa')
    self.assertTrue(p['predios'][0]['novo'])
    with open(self.predios, encoding='utf-8') as h:
      self.assertEqual(h.read(), antes)

  def test_predio_novo_invalido_bloqueia(self):
    _, p = self.previa(csv_de(frame(['villa-sala'])), novos=[dict(VILLA, prefixo='marcelo2')])
    self.assertTrue(any('cadastro de prédio' in b for b in p['bloqueios']))

  def test_preenchimento_e_aviso_de_coluna_vazia(self):
    _, p = self.previa(csv_de(frame(['sala', 'sala'], n_clients=np.nan, combo=None)))
    self.assertEqual(p['preenchimento']['n_clients'], 0.0)
    self.assertEqual(p['preenchimento']['local'], 1.0)
    self.assertTrue(any('n_clients' in a for a in p['avisos']))
    self.assertTrue(any('combo' in a for a in p['avisos']))
    self.assertEqual(p['geracao'], 'current')

  def test_falta_alvo_bloqueia(self):
    _, p = self.previa(csv_de(frame(['sala']).drop(columns=['jitter_ms'])))
    self.assertTrue(any('jitter_ms' in b for b in p['bloqueios']))

  def test_geracao_legada_so_avisa(self):
    _, p = self.previa(csv_de(frame(['sala']).drop(columns=['house_x0'])))
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual(p['geracao'], 'legacy')
    self.assertTrue(any('legada' in a for a in p['avisos']))

  def test_local_vazio_bloqueia(self):
    _, p = self.previa(csv_de(frame(['sala', None])))
    self.assertTrue(any('local vazio' in b for b in p['bloqueios']))

  def test_nomes_bloqueados(self):
    open(os.path.join(self.data, 'ja.csv'), 'w').close()
    casos = {'ja.csv': 'já existe', 'x-qoe.csv': 'ignorados', 'x-filllast.csv': 'ignorados',
             'a..b.csv': 'inválido', 'novo.zip': 'terminar em .csv'}
    for nome, trecho in casos.items():
      token = I.guardar('original.csv', csv_de(frame(['sala'])))
      p = I.previa(token, nome, data_dir=self.data, existentes=[])
      self.assertTrue(any(trecho in b for b in p['bloqueios']), (nome, p['bloqueios']))

  def test_duplicata_bloqueia_e_contido_avisa(self):
    df = frame(['sala', 'sala', 'sala'])
    _, p = self.previa(csv_de(df), existentes=[existente('velho.csv', df)])
    self.assertEqual(p['duplicata_de'], 'velho.csv')
    self.assertTrue(any('duplicata' in b for b in p['bloqueios']))
    maior = pd.concat([df, frame(['sala'], inicio=99.0)])
    _, p = self.previa(csv_de(df), existentes=[existente('maior.csv', maior)])
    self.assertEqual(p['contido_em'], ['maior.csv'])
    self.assertTrue(any('maior.csv' in a for a in p['avisos']))

  def test_extensao_e_tamanho_recusados_no_envio(self):
    with self.assertRaises(ValueError):
      I.guardar('dados.xlsx', b'x')
    with self.assertRaises(ValueError):
      I.guardar('dados.csv', b'')

  def test_token_expirado(self):
    token = I.guardar('novo.csv', csv_de(frame(['sala'])), agora=time.time() - I.VALIDADE_S - 1)
    with self.assertRaises(KeyError):
      I.previa(token, 'novo.csv', data_dir=self.data, existentes=[])


class TestConfirmar(Base):
  def test_grava_arquivo_e_predio_e_descarta_o_token(self):
    token, _ = self.previa(csv_de(frame(['villa-sala'])), novos=[VILLA])
    r = I.confirmar(token, 'novo.csv', [VILLA], data_dir=self.data, existentes=[])
    self.assertEqual(r, {'dataset': 'novo.csv', 'predios': ['casa-villa'], 'linhas': 1})
    self.assertEqual(len(C._read_any(os.path.join(self.data, 'novo.csv'))), 1)
    self.assertIn('casa-villa', S.registro_atual()['predios'])
    with self.assertRaises(KeyError):
      I.confirmar(token, 'novo.csv', [VILLA], data_dir=self.data, existentes=[])

  def test_refaz_a_validacao_e_nao_grava_com_bloqueio(self):
    token, _ = self.previa(csv_de(frame(['villa-sala'])))
    with self.assertRaises(ValueError) as ctx:
      I.confirmar(token, 'novo.csv', [], data_dir=self.data, existentes=[])
    self.assertIn('local desconhecido', str(ctx.exception))
    self.assertEqual(os.listdir(self.data), [])
    self.assertNotIn('casa-villa', S.registro_atual()['predios'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_upload.py' -v`
Expected: ERROR na importação (`cannot import name 'ingestao'`).

- [ ] **Step 3: Criar `src/ml/studio/ingestao.py`**

```python
"""Entrada de datasets pelo QoE Studio: prévia guardada sob um token e confirmação que grava em data/.

O arquivo enviado fica numa pasta temporária do processo até a confirmação, e nada vai
para data/ antes dela. A confirmação refaz a prévia inteira: a tela nunca é a única a
validar.
"""

import os
import re
import shutil
import tempfile
import threading
import time
import uuid

import pandas as pd

from ml.core import carga as core_carga
from ml.core import sites as core_sites

LIMITE_BYTES = 100 * 1024 * 1024
VALIDADE_S = 3600
# Abaixo disto, uma coluna-chave da geração atual quase não ajuda: avisar na prévia.
LIMIAR_PREENCHIMENTO = 0.5
OBRIGATORIAS = ('local',) + tuple(core_carga.TARGETS)
COLUNAS_CHAVE = OBRIGATORIAS + tuple(core_carga.CURRENT_MARKERS)
NOME_ARQUIVO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.(csv|zip)$')
# A descoberta de datasets pula estes nomes (carga.discover).
IGNORADOS = ('-qoe', 'filllast')

_previas = {}
_lock = threading.Lock()


def _extensao(nome: str) -> str:
  for ext in ('.csv', '.zip'):
    if nome.lower().endswith(ext):
      return ext
  raise ValueError(f'{nome!r}: o arquivo precisa ser .csv ou .zip')


def _limpar_expiradas(agora: float) -> None:
  for token in [t for t, p in _previas.items() if agora - p['criado'] > VALIDADE_S]:
    shutil.rmtree(_previas.pop(token)['pasta'], ignore_errors=True)


def guardar(nome: str, conteudo: bytes, agora: float = None) -> str:
  """Guarda o arquivo enviado numa pasta temporária e devolve o token da prévia."""
  if not conteudo:
    raise ValueError('arquivo vazio')
  if len(conteudo) > LIMITE_BYTES:
    raise ValueError(f'arquivo acima de {LIMITE_BYTES // 2 ** 20} MB')
  ext = _extensao(nome)
  agora = time.time() if agora is None else agora
  pasta = tempfile.mkdtemp(prefix='qoe-upload-')
  path = os.path.join(pasta, 'arquivo' + ext)
  with open(path, 'wb') as handle:
    handle.write(conteudo)
  token = uuid.uuid4().hex
  with _lock:
    _limpar_expiradas(time.time())
    _previas[token] = {'pasta': pasta, 'path': path, 'ext': ext, 'criado': agora}
  return token


def _arquivo(token: str) -> dict:
  with _lock:
    _limpar_expiradas(time.time())
    item = _previas.get(token)
  if item is None:
    raise KeyError('prévia expirada ou desconhecida; envie o arquivo de novo')
  return item


def descartar(token: str) -> None:
  with _lock:
    item = _previas.pop(token, None)
  if item:
    shutil.rmtree(item['pasta'], ignore_errors=True)


def _bloqueios_de_nome(nome: str, ext: str, data_dir: str) -> list:
  saida = []
  if not NOME_ARQUIVO.match(nome) or '..' in nome:
    saida.append(f'nome {nome!r} inválido: letras, dígitos, ponto, hífen e sublinhado, terminando em .csv ou .zip')
  elif not nome.lower().endswith(ext):
    saida.append(f'o nome precisa terminar em {ext}, como o arquivo enviado')
  if any(m in nome for m in IGNORADOS):
    saida.append(f'nomes com {" ou ".join(IGNORADOS)} são ignorados pela descoberta de datasets')
  if os.path.exists(os.path.join(data_dir, nome)):
    saida.append(f'já existe data/{nome}')
  return saida


def _prefixo_candidato(valor) -> str:
  return str(valor).strip().lower().split('-')[0]


def _preenchimento(frame: pd.DataFrame) -> dict:
  return {c: (round(float(frame[c].notna().mean()), 4) if c in frame.columns and len(frame) else None)
          for c in COLUNAS_CHAVE}


def _locais(frame: pd.DataFrame, registro: dict, conhecidos: set) -> tuple:
  """(prédios reconhecidos, grupos de valores desconhecidos por prefixo candidato)."""
  predios, desconhecidos = {}, {}
  for valor, linhas in frame['local'].dropna().value_counts().items():
    try:
      predio = core_sites.resolve_site_id(pd.Series([valor]), level='building', registro=registro).iloc[0]
      posicao = core_sites.resolve_site_id(pd.Series([valor]), registro=registro).iloc[0]
    except ValueError:
      grupo = desconhecidos.setdefault(_prefixo_candidato(valor), {'valores': [], 'linhas': 0})
      grupo['valores'].append(str(valor))
      grupo['linhas'] += int(linhas)
      continue
    item = predios.setdefault(predio, {'linhas': 0, 'posicoes': set()})
    item['linhas'] += int(linhas)
    item['posicoes'].add(posicao)
  lista_predios = [{'predio': k, 'rotulo': registro['predios'][k]['rotulo'], 'novo': k not in conhecidos,
                    'linhas': v['linhas'], 'posicoes': sorted(v['posicoes'])} for k, v in sorted(predios.items())]
  lista_desc = [{'prefixo': k, 'valores': sorted(v['valores']), 'linhas': v['linhas']}
                for k, v in sorted(desconhecidos.items())]
  return lista_predios, lista_desc


def _relacoes(frame: pd.DataFrame, existentes: list) -> dict:
  usaveis = [d for d in existentes if d.get('usable')]
  digest = core_carga.fingerprint(frame)
  duplicata = next((d['id'] for d in usaveis if d['fingerprint'] == digest), None)
  chaves = core_carga.chaves_alvos(frame)
  contido, contem = [], []
  for d in usaveis:
    outras = core_carga.chaves_alvos(d['_frame'])
    if chaves and chaves < outras:
      contido.append(d['id'])
    elif outras and outras < chaves:
      contem.append(d['id'])
  return {'fingerprint': digest, 'duplicata_de': duplicata, 'contido_em': contido, 'contem': contem}


def previa(token: str, nome: str, predios_novos=(), data_dir: str = None, existentes: list = None) -> dict:
  """O que entraria em data/ com este nome e estes prédios novos. Não grava nada."""
  data_dir = data_dir or core_carga.DATA_DIR
  existentes = core_carga.descobertos() if existentes is None else existentes
  item = _arquivo(token)
  bloqueios, avisos = _bloqueios_de_nome(nome, item['ext'], data_dir), []
  try:
    frame = core_carga._read_any(item['path'])
  except Exception as erro:  # o motivo vai para a tela
    return {'nome': nome, 'bloqueios': bloqueios + [f'arquivo ilegível: {erro}'], 'avisos': avisos}
  saida = {'nome': nome, 'linhas': int(len(frame)), 'colunas': int(len(frame.columns))}
  faltam = [c for c in OBRIGATORIAS if c not in frame.columns]
  if faltam:
    return dict(saida, bloqueios=bloqueios + [f'faltam colunas obrigatórias: {faltam}'], avisos=avisos)

  saida['geracao'] = core_carga._generation(frame.columns)
  saida['marcadores_ausentes'] = [m for m in core_carga.CURRENT_MARKERS if m not in frame.columns]
  if saida['geracao'] == 'legacy':
    avisos.append(f"geração legada (faltam {saida['marcadores_ausentes']}): entra, mas fica fora do conjunto padrão")
  saida['preenchimento'] = _preenchimento(frame)
  for coluna in core_carga.CURRENT_MARKERS:
    valor = saida['preenchimento'][coluna]
    if valor is not None and valor < LIMIAR_PREENCHIMENTO:
      avisos.append(f'{coluna} preenchido em só {valor:.0%} das linhas')

  atual = core_sites.registro_atual()
  try:
    registro = core_sites.com_novos(atual, predios_novos)
    core_sites.validar_predios(registro)
  except ValueError as erro:
    bloqueios.append(f'cadastro de prédio: {erro}')
    registro = atual
  vazios = int(frame['local'].isna().sum())
  if vazios:
    bloqueios.append(f'{vazios} linhas com local vazio')
  saida['predios'], saida['desconhecidos'] = _locais(frame, registro, set(atual['predios']))
  if saida['desconhecidos']:
    prefixos = [g['prefixo'] for g in saida['desconhecidos']]
    bloqueios.append(f'local desconhecido: cadastre o prédio dos prefixos {prefixos}')

  saida.update(_relacoes(frame, existentes))
  if saida['duplicata_de']:
    bloqueios.append(f"mesmos alvos de {saida['duplicata_de']}: seria descartado como duplicata")
  if saida['contido_em']:
    avisos.append(f"todas as linhas já estão em {saida['contido_em']}: seria marcado como substituído")
  if saida['contem']:
    avisos.append(f"contém todas as linhas de {saida['contem']}: esses passariam a ser marcados como substituídos")
  return dict(saida, bloqueios=bloqueios, avisos=avisos)


def confirmar(token: str, nome: str, predios_novos=(), data_dir: str = None, existentes: list = None) -> dict:
  """Refaz a prévia; sem bloqueio, cadastra os prédios e grava data/<nome>."""
  data_dir = data_dir or core_carga.DATA_DIR
  p = previa(token, nome, predios_novos, data_dir, existentes)
  if p['bloqueios']:
    raise ValueError('; '.join(p['bloqueios']))
  item = _arquivo(token)
  novos = [n['chave'].strip() for n in predios_novos]
  if predios_novos:
    core_sites.cadastrar_predios(predios_novos)
  destino = os.path.join(data_dir, nome)
  # .tmp não termina em .csv nem .zip: a descoberta nunca vê o arquivo pela metade.
  temporario = destino + '.tmp'
  try:
    shutil.copyfile(item['path'], temporario)
    os.replace(temporario, destino)
  except OSError as erro:
    if os.path.exists(temporario):
      os.unlink(temporario)
    extra = f'; os prédios {novos} já ficaram cadastrados em core/predios.json' if novos else ''
    raise OSError(f'não foi possível gravar data/{nome}: {erro}{extra}') from erro
  descartar(token)
  return {'dataset': nome, 'predios': novos, 'linhas': p['linhas']}
```

- [ ] **Step 4: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_upload.py' -v`
Expected: todos PASS.

Se `test_nomes_bloqueados` falhar em `'a..b.csv'`: o regex aceita o nome e a checagem `'..' in nome` é que bloqueia; a mensagem contém "inválido". Confira que a condição usa `or`.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add src/ml/studio/ingestao.py tests/test_studio_upload.py
```

Mensagem sugerida: `feat: prévia e confirmação de upload de dataset no Studio`

---

### Task 6: Rotas de upload na API

**Files:**
- Modify: `src/ml/studio/api.py` (imports; nova seção antes de `# ---------------- Limites e pendências dos dados ----------------`)
- Test: `tests/test_studio_upload.py` (acrescentar classe)

- [ ] **Step 1: Escrever os testes (falham)**

Acrescente a `tests/test_studio_upload.py`, antes do `if __name__`:

```python
import asyncio
import types
from unittest import mock

from ml.studio import api


class Pedido:
  """Request mínimo: as rotas só usam client.host, headers e body()."""
  def __init__(self, corpo=b'', host='127.0.0.1'):
    self.client = types.SimpleNamespace(host=host)
    self.headers = {'content-length': str(len(corpo))}
    self._corpo = corpo

  async def body(self):
    return self._corpo


class TestRotas(Base):
  def setUp(self):
    super().setUp()
    self.patches = [mock.patch.object(C, 'DATA_DIR', self.data),
                    mock.patch.object(api, 'descobertos', return_value=[])]
    for p in self.patches:
      p.start()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def enviar(self, conteudo, nome='novo.csv', host='127.0.0.1'):
    return asyncio.run(api.datasets_previa(Pedido(conteudo, host), nome=nome))

  def test_fluxo_completo_com_predio_novo(self):
    r = self.enviar(csv_de(frame(['villa-sala', 'villa-quarto'])))
    self.assertTrue(r['previa']['bloqueios'])
    revisada = api.datasets_revisar(api.Revisao(token=r['token'], nome='novo.csv', predios_novos=[VILLA]),
                                    Pedido())
    self.assertEqual(revisada['bloqueios'], [])
    with mock.patch.object(api, '_dados_mudaram') as mudou:
      feito = api.datasets_confirmar(api.Revisao(token=r['token'], nome='novo.csv', predios_novos=[VILLA]),
                                     Pedido())
    mudou.assert_called_once()
    self.assertEqual(feito['dataset'], 'novo.csv')
    self.assertTrue(os.path.exists(os.path.join(self.data, 'novo.csv')))

  def test_confirmar_com_bloqueio_da_422(self):
    r = self.enviar(csv_de(frame(['villa-sala'])))
    with self.assertRaises(api.HTTPException) as ctx:
      api.datasets_confirmar(api.Revisao(token=r['token'], nome='novo.csv'), Pedido())
    self.assertEqual(ctx.exception.status_code, 422)

  def test_token_desconhecido_da_404(self):
    with self.assertRaises(api.HTTPException) as ctx:
      api.datasets_revisar(api.Revisao(token='nada', nome='novo.csv'), Pedido())
    self.assertEqual(ctx.exception.status_code, 404)

  def test_fora_da_maquina_da_403(self):
    with self.assertRaises(api.HTTPException) as ctx:
      self.enviar(csv_de(frame(['sala'])), host='10.0.0.5')
    self.assertEqual(ctx.exception.status_code, 403)

  def test_arquivo_grande_da_413(self):
    pedido = Pedido(b'x')
    pedido.headers['content-length'] = str(I.LIMITE_BYTES + 1)
    with self.assertRaises(api.HTTPException) as ctx:
      asyncio.run(api.datasets_previa(pedido, nome='novo.csv'))
    self.assertEqual(ctx.exception.status_code, 413)

  def test_extensao_errada_da_422(self):
    with self.assertRaises(api.HTTPException) as ctx:
      self.enviar(b'x', nome='novo.xlsx')
    self.assertEqual(ctx.exception.status_code, 422)

  def test_dados_mudaram_esquece_descoberta_e_caches(self):
    api._cache['payload'] = {'x': 1}
    api._modelos_cache['k'] = 1
    with mock.patch.object(api.core_carga, 'esquecer_descobertos') as esquecer:
      api._dados_mudaram()
    esquecer.assert_called_once()
    self.assertEqual((api._cache, api._modelos_cache), ({}, {}))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_upload.py' -v`
Expected: ERROR em `TestRotas` (`datasets_previa` não existe).

- [ ] **Step 3: Implementar em `src/ml/studio/api.py`**

Nos imports, acrescente depois de `from fastapi.staticfiles import StaticFiles`:

```python
from starlette.concurrency import run_in_threadpool
```

e depois de `from ml.studio import features as studio_features`:

```python
from ml.studio import ingestao as studio_ingestao
```

(`from ml.studio import data as studio_data` já entrou na Task 2.)

Acrescente esta seção logo antes da linha `# ---------------- Limites e pendências dos dados ----------------`:

```python
# ---------------- Dados novos pela interface ----------------

def _dados_mudaram() -> None:
  """Dataset ou prédio novo: descoberta, payload e tudo que depende do conjunto é refeito."""
  core_carga.esquecer_descobertos()
  studio_data.limpar_cache_predios()
  _cache.clear()
  _ajustes.clear()
  _modelos_cache.clear()
  with _desenhos_lock:
    for job_id in [j for j, job in _desenhos.items() if job['status'] != 'rodando']:
      del _desenhos[job_id]


@app.post('/api/datasets/previa')
async def datasets_previa(request: Request, nome: str):
  """Corpo cru (application/octet-stream): sem multipart, sem python-multipart."""
  _so_local(request)
  limite = studio_ingestao.LIMITE_BYTES
  tamanho = request.headers.get('content-length')
  if tamanho and tamanho.isdigit() and int(tamanho) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  conteudo = await request.body()
  if len(conteudo) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  try:
    token = studio_ingestao.guardar(nome, conteudo)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  previa = await run_in_threadpool(studio_ingestao.previa, token, nome, (), None, descobertos())
  return {'token': token, 'previa': previa}


class PredioNovo(BaseModel):
  chave: str
  rotulo: str
  ambiente: str
  prefixo: str


class Revisao(BaseModel):
  token: str
  nome: str
  predios_novos: list[PredioNovo] = []


@app.post('/api/datasets/revisar')
def datasets_revisar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    return studio_ingestao.previa(corpo.token, corpo.nome, novos, existentes=descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])


@app.post('/api/datasets/confirmar')
def datasets_confirmar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    resultado = studio_ingestao.confirmar(corpo.token, corpo.nome, novos, existentes=descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except OSError as erro:
    # O prédio pode ter sido cadastrado antes da falha: o registro em memória já mudou.
    _dados_mudaram()
    raise HTTPException(422, str(erro))
  _dados_mudaram()
  return resultado
```

Os testes passam `predios_novos=[VILLA]` como dicionário: o pydantic converte para `PredioNovo`.

- [ ] **Step 4: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_upload.py' -v`
Expected: todos PASS.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add src/ml/studio/api.py tests/test_studio_upload.py
```

Mensagem sugerida: `feat: rotas de prévia, revisão e confirmação de upload`

---

### Task 7: Rota de reavaliação na API

**Files:**
- Modify: `src/ml/studio/api.py` (depois de `modelos_ativo`)
- Create: `tests/test_studio_reavaliar.py`

- [ ] **Step 1: Escrever os testes (falham)**

Crie `tests/test_studio_reavaliar.py`:

```python
import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api

PEDIDO = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
ANTIGA = {'speedtest_down_mbps': {'datasets': ['a.csv'], 'ambiente': 'todos'}, 'atende_completo': {'media': 0.5}}
NOVA = {'speedtest_down_mbps': {'datasets': ['a.csv', 'villa.csv'], 'ambiente': 'todos'},
        'atende_completo': {'media': 0.6}}
REGISTRO = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'x', 'avaliacao': ANTIGA},
  'v2': {'features': ['router_snr', 'router_noise'], 'descricao': 'y',
         'denominador': {'speedtest_down_mbps': 'router_snr'}}}}


def sincrono(chave, tarefa):
  """_iniciar_job sem thread: a tarefa roda na hora e o resultado volta no lugar do id."""
  return {'resultado': tarefa(lambda evento: None)}


class TestReavaliarRota(unittest.TestCase):
  def setUp(self):
    self.patches = [mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
                    mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)),
                    mock.patch.object(api, '_iniciar_job', side_effect=sincrono),
                    mock.patch.object(api.core_features, 'cobertura_tr069', return_value={'c': 1})]
    for p in self.patches:
      p.start()

  def tearDown(self):
    for p in self.patches:
      p.stop()

  def rodar(self, nomes, avaliacoes):
    corpo = api.Reavaliacao(nomes=nomes, ds='a.csv,villa.csv', ambiente='')
    with mock.patch.object(api, 'avaliacao_completa', side_effect=avaliacoes) as aval, \
         mock.patch.object(api.core_modelos, 'reavaliar') as reav:
      try:
        r = api.modelos_reavaliar(corpo, PEDIDO)
      except Exception as erro:  # a falha no meio do lote volta para o teste examinar
        r = erro
    return r, aval, reav

  def test_reavalia_em_ordem_com_o_denominador_da_versao(self):
    r, aval, reav = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2']})
    self.assertEqual(aval.call_args_list[1].args, ('a.csv,villa.csv', '', ['router_snr', 'router_noise'],
                                                   {'speedtest_down_mbps': 'router_snr'}))
    nome, avaliacao, cobertura, nota = reav.call_args_list[0].args
    self.assertEqual((nome, avaliacao, cobertura), ('v1', NOVA, {'c': 1}))
    self.assertIn('+villa.csv', nota)
    self.assertIn('0,50 → 0,60', nota)

  def test_falha_no_meio_mantem_as_anteriores_e_cita_a_versao(self):
    r, _, reav = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertEqual(reav.call_count, 1)
    self.assertIn('v2', str(r))
    self.assertIn("['v1']", str(r))

  def test_recusa_lista_vazia_e_nome_inexistente(self):
    for nomes in ([], ['v9']):
      with self.assertRaises(api.HTTPException) as ctx:
        api.modelos_reavaliar(api.Reavaliacao(nomes=nomes), PEDIDO)
      self.assertEqual(ctx.exception.status_code, 422)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_reavaliar.py' -v`
Expected: ERROR (`Reavaliacao` não existe).

- [ ] **Step 3: Implementar em `src/ml/studio/api.py`**

Logo depois da função `modelos_ativo` (a que termina em `return modelos_listar()`, por volta da linha 670), acrescente:

```python
class Reavaliacao(BaseModel):
  nomes: list[str]
  ds: str = ''
  ambiente: str = ''


@app.post('/api/modelos/reavaliar')
def modelos_reavaliar(corpo: Reavaliacao, request: Request):
  """Recalcula a avaliação de versões existentes com o conjunto escolhido, uma por vez.

  Cada versão é gravada assim que termina: se o lote parar no meio, o que já foi
  reavaliado fica salvo e o erro diz em qual versão parou.
  """
  _so_local(request)
  registro, erro = _registro()
  if erro:
    raise HTTPException(422, erro)
  if not corpo.nomes:
    raise HTTPException(422, 'nenhuma versão para reavaliar')
  faltam = [n for n in corpo.nomes if n not in registro['versoes']]
  if faltam:
    raise HTTPException(422, f'versões que não existem: {faltam}')
  tabela, _ = _tabela()
  nomes = list(corpo.nomes)

  def tarefa(progresso):
    feitas = []
    for i, nome in enumerate(nomes):
      progresso({'nome': nome, 'i': i, 'total': len(nomes)})
      versao = registro['versoes'][nome]
      try:
        avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, versao['features'], versao.get('denominador'))
        nota = core_modelos.nota_reavaliacao(versao.get('avaliacao'), avaliacao, date.today().isoformat())
        core_modelos.reavaliar(nome, avaliacao, core_features.cobertura_tr069(versao['features'], tabela), nota)
      except Exception as falha:
        detalhe = falha.detail if isinstance(falha, HTTPException) else str(falha)
        raise RuntimeError(f'parou em {nome}: {detalhe}; já reavaliadas: {feitas}') from falha
      finally:
        _ajustes.clear()
        _modelos_cache.clear()
      feitas.append(nome)
    return {'reavaliadas': feitas}
  return _iniciar_job(('reavaliar', tuple(nomes), tuple(sorted(_lista(corpo.ds))), _ambiente(corpo.ambiente))
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/reavaliar/{job_id}')
def modelos_reavaliacao(job_id: str):
  return _job(job_id)
```

Confira que `date` já está importado no topo (`from datetime import date`: está) e que `_lista` existe (é usada por `modelos_desenhar`).

- [ ] **Step 4: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_reavaliar.py' -v`
Expected: todos PASS.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add src/ml/studio/api.py tests/test_studio_reavaliar.py
```

Mensagem sugerida: `feat: rota de reavaliação de versões em segundo plano`

---

### Task 8: Front: recarregar o payload e upload no painel Conjunto

**Files:**
- Modify: `src/ml/studio/static/studio.js` (objeto `V.app`)
- Modify: `src/ml/studio/static/conjunto.js`
- Modify: `src/ml/studio/static/styles.css` (fim do arquivo)

Sem teste automatizado de front para esta parte (o projeto só testa `logica.js` em node); a verificação é manual na Task 10.

- [ ] **Step 1: `V.app.recarregarPayload` em `studio.js`**

Dentro do objeto `V.app`, depois de `colunasMudaram() { ... },`, acrescente:

```js
    // Dataset ou prédio novo: relê o payload, mantém o que já estava ligado ou desligado
    // e liga os datasets que acabaram de chegar.
    recarregarPayload(ligar) {
      return V.util.pedir('api/payload').then((data) => {
        const antes = state.enabled;
        state.data = data;
        state.enabled = {};
        data.datasets.forEach((d) => { state.enabled[d.id] = d.id in antes ? antes[d.id] : d.enabled; });
        (ligar || []).forEach((id) => { state.enabled[id] = true; });
        V.app.colunasMudaram();
      });
    },
```

- [ ] **Step 2: Estado e funções de upload em `conjunto.js`**

No objeto `st` (linha 22), acrescente `up: null, upMsg: null,` antes de `dispensadas`:

```js
  const st = { ctx: null, aberto: false, voltarPara: null,
               pend: null, inv: null, chave: null, erro: null, respErro: null, ocupado: false,
               up: null, upMsg: null, dispensadas: new Set() };
```

Depois da função `responder` (fim da seção "carregamento"), acrescente:

```js
  /* ---------------- adicionar dados ---------------- */
  function enviar(arquivo) {
    st.upMsg = null;
    st.up = { nome: arquivo.name, token: null, previa: null, novos: {}, sujo: false, ocupado: true, erro: null };
    desenhar();
    U.pedir('api/datasets/previa?nome=' + encodeURIComponent(arquivo.name),
      { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: arquivo })
      .then((r) => { st.up.token = r.token; usarPrevia(r.previa); })
      .catch((e) => { st.up.erro = e.message; })
      .finally(() => { if (st.up) st.up.ocupado = false; desenhar(); });
  }

  // Os formulários de prédio ficam enquanto a prévia existir: depois de Verificar, os
  // prefixos deixam de ser desconhecidos, mas o cadastro ainda precisa ir na confirmação.
  function usarPrevia(p) {
    st.up.previa = p;
    st.up.sujo = false;
    (p.desconhecidos || []).forEach((g) => {
      if (!st.up.novos[g.prefixo]) {
        st.up.novos[g.prefixo] = { chave: 'casa-' + g.prefixo, rotulo: '', ambiente: 'domestico', prefixo: g.prefixo };
      }
    });
  }

  const novosLista = () => Object.values(st.up.novos).map((n) =>
    ({ chave: n.chave.trim(), rotulo: n.rotulo.trim(), ambiente: n.ambiente, prefixo: n.prefixo.trim() }));

  function revisar() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/datasets/revisar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then(usarPrevia)
      .catch((e) => { up.erro = e.message; })
      .finally(() => { up.ocupado = false; desenhar(); });
  }

  function confirmarUpload() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/datasets/confirmar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then((r) => {
        st.up = null;
        st.upMsg = `${r.dataset} adicionado em data/` +
          (r.predios.length ? ` e ${r.predios.join(', ')} em src/ml/core/predios.json` : '') +
          '. Revise no git diff antes do commit. As versões salvas ficam desatualizadas até serem reavaliadas na área Modelo.';
        return V.app.recarregarPayload([r.dataset]);
      })
      .catch((e) => { if (st.up) { st.up.erro = e.message; st.up.ocupado = false; } else { st.upMsg = e.message; } desenhar(); });
  }
```

- [ ] **Step 3: Seção de upload em `conjunto.js`**

Antes de `function secaoDatasets()`, acrescente:

```js
  const lista = (itens) => '<ul>' + itens.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';

  function formPredio(prefixo, n, grupo) {
    const campo = (c, rotulo, extra = '') => `<label>${rotulo}<input type="text" data-novo="${esc(prefixo)}"
      data-campo="${c}" data-k="novo-${esc(prefixo)}-${c}" value="${esc(n[c])}"${extra}></label>`;
    return `<div class="pend-item ${grupo ? 'warning' : 'good'}"><div style="flex:1">
      <b>Prédio novo para <code>${esc(prefixo)}-…</code></b>
      ${grupo ? `<div class="gate-msg">${grupo.linhas.toLocaleString('pt-BR')} linhas: ${grupo.valores.map(esc).join(', ')}</div>` : ''}
      <div class="upload-campos">${campo('rotulo', 'Nome', ' placeholder="ex.: Casa do Villa"')}${campo('chave', 'Chave')}${campo('prefixo', 'Prefixo')}
        <label>Ambiente<select data-novo="${esc(prefixo)}" data-campo="ambiente" data-k="novo-${esc(prefixo)}-ambiente">${Object.entries(st.ctx.ambientes).map(([a, r]) =>
          `<option value="${a}"${a === n.ambiente ? ' selected' : ''}>${esc(r)}</option>`).join('')}</select></label></div>
    </div></div>`;
  }

  function secaoAdicionar() {
    const up = st.up;
    const msg = st.upMsg ? U.gate('good', 'Dados adicionados', esc(st.upMsg)) : '';
    const botao = `<div class="controls"><button class="btn" data-acao="escolher-arquivo" data-k="escolher-arquivo"${up && up.ocupado ? ' disabled' : ''}>
        ${U.icone('i-plus')} Adicionar dados</button>
      <input type="file" id="cArquivo" accept=".csv,.zip" class="hide"></div>`;
    if (!up) return msg + botao;
    if (!up.previa) {
      return botao + (up.ocupado ? '<p class="gate-msg">Lendo o arquivo…</p>' : '') +
        (up.erro ? U.gate('critical', 'Não foi possível ler o arquivo', esc(up.erro)) : '');
    }
    const p = up.previa;
    const resumo = p.linhas != null ? `<p class="gate-msg">${p.linhas.toLocaleString('pt-BR')} linhas · ${p.colunas} colunas` +
      (p.geracao ? ` · geração ${p.geracao === 'current' ? 'atual' : 'legada'}` : '') + '</p>' : '';
    const predios = (p.predios || []).map((x) => `<li><b>${esc(x.rotulo)}</b>${x.novo ? ' <span class="tag">novo</span>' : ''}
      · ${x.linhas.toLocaleString('pt-BR')} linhas · ${x.posicoes.map(esc).join(', ')}</li>`).join('');
    const preench = Object.entries(p.preenchimento || {}).map(([c, v]) =>
      `<li><code>${esc(c)}</code> ${v == null ? 'ausente' : U.pct(v)}</li>`).join('');
    const forms = Object.entries(up.novos).map(([k, n]) =>
      formPredio(k, n, (p.desconhecidos || []).find((g) => g.prefixo === k))).join('');
    const pode = !up.ocupado && !up.sujo && !p.bloqueios.length;
    return `<div class="upload">
      <label class="upload-nome">Nome em data/<input type="text" data-campo="nome-arquivo" data-k="nome-arquivo" value="${esc(up.nome)}"></label>
      ${resumo}${predios ? `<ul class="upload-predios">${predios}</ul>` : ''}
      ${preench ? `<details class="fold" data-k="up-preench"><summary>Preenchimento das colunas-chave</summary>
        <div class="inner"><ul>${preench}</ul></div></details>` : ''}
      ${forms}
      ${p.bloqueios.length ? U.gate('critical', 'Ainda não dá para confirmar', lista(p.bloqueios)) : ''}
      ${p.avisos.length ? U.gate('warning', 'Avisos', lista(p.avisos)) : ''}
      ${up.erro ? U.gate('critical', 'Algo deu errado', esc(up.erro)) : ''}
      ${up.sujo ? '<p class="gate-msg">Clique em Verificar depois de mudar o nome ou os prédios.</p>' : ''}
      <div class="controls"><button class="btn" data-acao="cancelar-upload" data-k="cancelar-upload">Cancelar</button>
        <button class="btn" data-acao="revisar-upload" data-k="revisar-upload"${up.ocupado ? ' disabled' : ''}>Verificar</button>
        <button class="btn-pri" data-acao="confirmar-upload" data-k="confirmar-upload"${pode ? '' : ' disabled'}>${up.ocupado ? 'Aguarde…' : 'Confirmar'}</button></div>
    </div>`;
  }
```

Em `desenhar()`, troque:

```js
      <h3>Datasets</h3>${secaoDatasets()}`);
```

por:

```js
      <h3>Datasets</h3>${secaoAdicionar()}${secaoDatasets()}`);
```

- [ ] **Step 4: Eventos em `conjunto.js`**

No listener de `click` do `#painelConjunto`, depois de `if (acao === 'ambiente') ...`, acrescente:

```js
    if (acao === 'escolher-arquivo') $('#cArquivo').click();
    if (acao === 'cancelar-upload') { st.up = null; desenhar(); }
    if (acao === 'revisar-upload') revisar();
    if (acao === 'confirmar-upload') confirmarUpload();
```

No listener de `change`, acrescente no começo do corpo:

```js
    if (t.id === 'cArquivo' && t.files && t.files[0]) { enviar(t.files[0]); return; }
```

Depois do listener de `change`, acrescente um listener de `input` (o `select` também dispara `input`):

```js
  $('#painelConjunto').addEventListener('input', (ev) => {
    const t = ev.target;
    if (!st.up || !t.dataset.campo) return;
    if (t.dataset.campo === 'nome-arquivo') st.up.nome = t.value;
    else if (t.dataset.novo) st.up.novos[t.dataset.novo][t.dataset.campo] = t.value;
    st.up.sujo = true;
    desenhar();
  });
```

`U.redesenhar` devolve o foco e o cursor ao campo pelo `data-k`, então redesenhar a cada tecla não atrapalha a digitação.

- [ ] **Step 5: Estilos em `styles.css`**

Acrescente ao fim do arquivo:

```css
/* Upload de dados no painel Conjunto */
.upload { display: grid; gap: 8px; margin-bottom: 12px; }
.upload label { display: inline-flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--ink-muted); }
.upload input[type=text], .upload select { font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--surface-1); color: var(--ink-1); min-width: 0; }
.upload input[type=text]:focus-visible, .upload select:focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
.upload-campos { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-top: 8px; }
.upload-predios { margin: 0; padding-left: 18px; font-size: 13px; }
```

- [ ] **Step 6: Conferir sintaxe do JS**

Run: `node --check src/ml/studio/static/conjunto.js && node --check src/ml/studio/static/studio.js && echo ok`
Expected: `ok`

- [ ] **Step 7: Commit (o usuário roda)**

```bash
git add src/ml/studio/static/studio.js src/ml/studio/static/conjunto.js src/ml/studio/static/styles.css
```

Mensagem sugerida: `feat: adicionar dados pelo painel Conjunto, com prévia e cadastro de prédio`

---

### Task 9: Front: Reavaliar na área Modelo

**Files:**
- Modify: `src/ml/studio/static/index.html:32` (ícone)
- Modify: `src/ml/studio/static/modelo.js`
- Modify: `src/ml/studio/static/styles.css` (fim do arquivo)

- [ ] **Step 1: Ícone `i-refresh` em `index.html`**

Depois da linha do `<symbol id="i-undo" ...>`, acrescente:

```html
  <symbol id="i-refresh" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></symbol>
```

- [ ] **Step 2: Estado e funções em `modelo.js`**

No objeto `st`, na linha que começa com `reg: null, regErro: null,`, acrescente `reav: null,` ao fim:

```js
    reg: null, regErro: null, regAviso: null, msg: null, erro: null, menu: null, vereditos: {}, pendente: null, reav: null,
```

Depois da função `ativarManual`, acrescente:

```js
  /* ---------------- reavaliar ---------------- */
  // Mesma régua do selo "desatualizada": a lista que a tela mostra é a que vai para o servidor.
  const desatualizadas = () => st.reg.versoes
    .filter((v) => motivoDesatualizada((v.avaliacao || {})[st.alvo])).map((v) => v.nome);

  function reavaliar(nomes) {
    st.menu = null; st.msg = null; st.erro = null;
    st.reav = { status: 'rodando', progresso: [], total: nomes.length };
    desenhar();
    U.post('api/modelos/reavaliar', { nomes, ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente })
      .then((r) => acompanharReav(r.id))
      .catch((e) => { st.reav = null; st.erro = `Não foi possível reavaliar: ${e.message}`; desenhar(); });
  }

  function acompanharReav(id) {
    U.pedir('api/modelos/reavaliar/' + id).then((job) => {
      if (job.status === 'rodando') {
        st.reav = Object.assign(job, { total: st.reav.total });
        desenhar();
        setTimeout(() => acompanharReav(id), 1500);
        return;
      }
      if (job.status === 'pronto') {
        const n = job.resultado.reavaliadas.length;
        st.msg = `${n} ${n === 1 ? 'versão reavaliada' : 'versões reavaliadas'} em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
      } else {
        st.erro = `A reavaliação parou: ${job.erro}`;
      }
      st.reav = null; st.cmpKey = null;
      // Mesmo com erro, as versões que terminaram já foram gravadas: recarrega o registro.
      carregarRegistro();
    }).catch((e) => { st.reav = null; st.erro = e.message; desenhar(); });
  }

  function barraReav() {
    if (st.reav) {
      const atual = st.reav.progresso[st.reav.progresso.length - 1];
      const feito = atual ? atual.i / st.reav.total : 0;
      return `<div class="reav" role="status">
        <span>${atual ? `Reavaliando <code>${esc(atual.nome)}</code> (${atual.i + 1} de ${st.reav.total})…` : 'Reavaliando…'}</span>
        <span class="ver-barra"><i style="width:${Math.round(feito * 100)}%"></i></span></div>`;
    }
    const n = desatualizadas().length;
    return n ? `<button class="linkbtn link" data-acao="reavaliar-todas" data-k="reavaliar-todas">${icone('i-refresh')}
      Reavaliar ${n} ${n === 1 ? 'desatualizada' : 'desatualizadas'}</button>` : '';
  }
```

- [ ] **Step 3: Menu do cartão com "Reavaliar" também na versão ativa**

Em `cartao(v)`, troque o bloco:

```js
      ${v.ativo ? '' : `<button class="btn-icone ver-menu" data-acao="menu" data-nome="${esc(v.nome)}" data-k="menu-${esc(v.nome)}"
        aria-haspopup="menu" aria-expanded="${st.menu === v.nome}" aria-label="Mais ações para ${esc(v.nome)}">${icone('i-more')}</button>
      ${st.menu === v.nome ? `<div class="menu" role="menu"><button role="menuitem" data-acao="ativar" data-nome="${esc(v.nome)}">Tornar ativa</button></div>` : ''}`}
```

por:

```js
      <button class="btn-icone ver-menu" data-acao="menu" data-nome="${esc(v.nome)}" data-k="menu-${esc(v.nome)}"
        aria-haspopup="menu" aria-expanded="${st.menu === v.nome}" aria-label="Mais ações para ${esc(v.nome)}">${icone('i-more')}</button>
      ${st.menu === v.nome ? `<div class="menu" role="menu">
        <button role="menuitem" data-acao="reavaliar" data-nome="${esc(v.nome)}"${st.reav ? ' disabled' : ''}>Reavaliar</button>
        ${v.ativo ? '' : `<button role="menuitem" data-acao="ativar" data-nome="${esc(v.nome)}">Tornar ativa</button>`}</div>` : ''}
```

- [ ] **Step 4: Barra na seção de versões**

Em `secaoVersoes()`, troque:

```js
    return `<div class="secao"><div class="secao-cab"><h2>Versões</h2>
        <button class="linkbtn link" data-acao="comparar" aria-expanded="${st.cmpAberto}">${icone('i-bars')} Comparar por prédio</button></div>
```

por:

```js
    return `<div class="secao"><div class="secao-cab"><h2>Versões</h2>${barraReav()}
        <button class="linkbtn link" data-acao="comparar" aria-expanded="${st.cmpAberto}">${icone('i-bars')} Comparar por prédio</button></div>
```

- [ ] **Step 5: Eventos**

No `switch (b.dataset.acao)` do listener de clique da área, depois de `case 'ativar': ...`, acrescente:

```js
      case 'reavaliar': reavaliar([b.dataset.nome]); break;
      case 'reavaliar-todas': reavaliar(desatualizadas()); break;
```

- [ ] **Step 6: Estilos em `styles.css`**

Acrescente ao fim do arquivo:

```css
/* Reavaliação de versões na área Modelo */
.reav { display: inline-flex; align-items: center; gap: 10px; font-size: 12.5px; color: var(--ink-muted); }
.reav .ver-barra { width: 120px; }
.secao-cab .linkbtn .icon { width: 15px; height: 15px; }
```

- [ ] **Step 7: Conferir sintaxe do JS**

Run: `node --check src/ml/studio/static/modelo.js && echo ok`
Expected: `ok`

- [ ] **Step 8: Commit (o usuário roda)**

```bash
git add src/ml/studio/static/index.html src/ml/studio/static/modelo.js src/ml/studio/static/styles.css
```

Mensagem sugerida: `feat: reavaliar versões na área Modelo, uma ou todas as desatualizadas`

---

### Task 10: CHANGELOG, suíte completa e verificação no navegador

**Files:**
- Modify: `CHANGELOG.md` (entrada nova no topo, no formato das existentes)

- [ ] **Step 1: Entrada no CHANGELOG**

Leia as primeiras 40 linhas de `CHANGELOG.md` para copiar o formato do cabeçalho de data. Acrescente no topo uma entrada `2026-10-20` com:

```markdown
### Dados novos pela interface e reavaliação de versões

- Prédios de coleta saem de `core/sites.py` para `src/ml/core/predios.json`, a fonte única do treino e do Studio. A resolução de `local` não muda (teste de equivalência com todos os valores de `data/`).
- Painel Conjunto: **Adicionar dados** envia um CSV ou zip, mostra a prévia (linhas, prédios, posições, % preenchido de `combo`, `n_clients`, `station_x`, `house_x0`, duplicatas) e grava em `data/` só na confirmação. Prefixo de `local` desconhecido é cadastrado como prédio novo na mesma tela.
- Área Modelo: **Reavaliar** recalcula a avaliação de uma versão existente com o conjunto atual, sem criar versão nova. Features continuam imutáveis; avaliação e cobertura são relatório, e cada reavaliação deixa uma linha no `historico`.
```

- [ ] **Step 2: Rodar a suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_*.py'` (timeout de 10 minutos)
Expected: `OK` no fim. Se algo falhar, pare e use superpowers:systematic-debugging antes de mexer.

Run: `node --test tests/js/logica.test.js`
Expected: todos passam.

- [ ] **Step 3: Verificação no navegador**

Suba o Studio: `PYTHONPATH=src venv/bin/python src/ml/studio.py` (em segundo plano) e abra `http://localhost:8100`.

Prepare um arquivo de teste fora do repositório: copie um CSV atual e troque os `local` de algumas linhas por `teste-sala`, salvando como `/tmp/qoe-teste/teste-upload.csv`.

Confira, nesta ordem:
1. Painel Conjunto → **Adicionar dados** → escolha o arquivo. A prévia mostra linhas, prédios, o grupo `teste` desconhecido e o bloqueio de local desconhecido.
2. Preencha **Nome** do prédio, clique em **Verificar**. O bloqueio some e o prédio aparece com o selo "novo".
3. **Cancelar** limpa a prévia sem gravar nada (`git status` não muda).
4. Envie de novo e **Confirme**. O dataset aparece ligado na lista, o chip do conjunto conta um prédio a mais e `git status` mostra `data/teste-upload.csv` e `src/ml/core/predios.json`.
5. Área Modelo: os cartões mostram "desatualizada". **Reavaliar N desatualizadas** mostra a barra de progresso e, no fim, a mensagem. `git diff src/ml/core/modelos.json` mostra só `avaliacao`, `cobertura` e `historico` mudando.
6. Repita no tema escuro (botão de tema) e numa janela estreita (cerca de 400 px) para conferir o formulário.

- [ ] **Step 4: Desfazer os artefatos do teste manual**

Os arquivos do passo 3 não podem ir para o commit:

```bash
rm data/teste-upload.csv
git checkout -- src/ml/core/predios.json src/ml/core/modelos.json
```

Antes do `git checkout`, confira com `git diff` que as únicas mudanças nesses dois arquivos são as do teste manual.

- [ ] **Step 5: Commit (o usuário roda)**

```bash
git add CHANGELOG.md
```

Mensagem sugerida: `docs(changelog): dados novos pela interface e reavaliação de versões`
