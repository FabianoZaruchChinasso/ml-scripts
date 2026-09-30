# QoE Studio: assistente de modelo (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a view **Modelo**, um assistente em quatro passos (Preparar → Ajustar → Testar → Publicar) que deixa um técnico de rede ajustar features, criar derivadas por receita, testar contra a versão ativa com veredito e publicar, sem passar pelas telas avançadas.

**Architecture:** O back-end ganha três funções puras em `studio/features.py`: `veredito`, `ganho_mais_um` (extraída de `ajuste`) e `lista_assistente`. Ganha também um módulo `studio/receitas.py` e quatro rotas em `studio/api.py`; `modelos/avaliar` passa a devolver `veredito` quando recebe `base`. O front-end ganha `static/assistente.js`, no padrão `V.views.*`. Features e Modelos vão para um grupo "Avançado" na barra lateral, sem mudança de comportamento.

**Tech Stack:** Python 3.12 (pandas, scikit-learn, FastAPI), unittest, JS puro sem build.

**Spec:** [docs/superpowers/specs/2026-09-30-qoe-studio-assistente-modelo-design.md](../specs/2026-09-30-qoe-studio-assistente-modelo-design.md)

**Regras deste repositório:**
- **Nunca rode `git commit` nem `git push`**: o usuário commita à mão. Nos pontos marcados como **Checkpoint**, pare e liste os arquivos alterados.
- Testes: `venv/bin/python -m unittest discover -s tests ...`, a partir da raiz do repositório. O `pytest` e o `httpx` não estão no venv; por isso os testes de API chamam as funções de rota direto, com `unittest.mock.patch`.
- Indentação de 2 espaços em Python e JS. Comentários só quando o porquê não é óbvio.
- Sem emojis em código ou UI; ícones são símbolos SVG do `index.html`.
- Textos de interface em português.

---

## Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `src/ml/studio/features.py` | alterar | `RUIDO_R2`, `UNIDADES`, `veredito()`, `ganho_mais_um()`, `lista_assistente()`; `ajuste()` passa a usar `ganho_mais_um()` |
| `src/ml/studio/receitas.py` | criar | `RECEITAS`, `listar()`, `montar()` |
| `src/ml/studio/api.py` | alterar | `veredito` em `modelos/avaliar`; rotas `assistente/colunas`, `assistente/sugestoes` (+ status), `receitas`, `receitas/montar` |
| `src/ml/studio/static/assistente.js` | criar | view `assistente`: estado, quatro passos e eventos |
| `src/ml/studio/static/index.html` | alterar | item **Modelo**, grupo **Avançado**, seção `view-assistente`, ícone `i-equal`, tags de script |
| `src/ml/studio/static/studio.js` | alterar | título da view, `render` do assistente e abertura do grupo Avançado |
| `src/ml/studio/static/styles.css` | alterar | stepper, grupo da nav, cartão de veredito e painel de receita |
| `tests/test_studio_assistente.py` | criar | testes de `veredito`, `ganho_mais_um`, `lista_assistente`, receitas e rotas |
| `docs/superpowers/specs/2026-09-30-qoe-studio-assistente-modelo-design.md` | alterar | alinhar a assinatura de `veredito` e a dica da Razão com o plano |

---

### Task 1: `veredito()` em `studio/features.py`

**Files:**
- Modify: `src/ml/studio/features.py` (constantes no topo; função nova depois de `delta_por_local`)
- Create: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_studio_assistente.py`:

```python
import os
import sys
import time
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F
from ml.core import formulas
from ml.studio import features as SF
from test_studio_features import TABELA, Base, frame


def delta(pooled, mae, por_local=None):
  return {'pooled': pooled, 'mae': mae,
          'por_local': por_local if por_local is not None else {'a': pooled, 'b': pooled}}


class TestVeredito(unittest.TestCase):
  def test_melhor_no_limiar(self):
    self.assertEqual(SF.veredito(delta(0.02, 0.0), 4)['resultado'], 'melhor')

  def test_abaixo_do_ruido_e_empate(self):
    v = SF.veredito(delta(0.019, -1.0), 4)
    self.assertEqual(v['resultado'], 'empate')
    self.assertIn('menor que o ruído', v['motivo'])

  def test_um_local_piorando_alem_do_ruido_segura_em_empate(self):
    v = SF.veredito(delta(0.05, -2.0, {'a': 0.1, 'b': -0.021}), 4)
    self.assertEqual(v['resultado'], 'empate')
    self.assertIn('piorou em b', v['motivo'])

  def test_queda_no_limiar_e_pior(self):
    self.assertEqual(SF.veredito(delta(-0.02, -1.0), 4)['resultado'], 'pior')

  def test_mae_subiu_sem_ganho_de_r2_e_pior(self):
    v = SF.veredito(delta(0.01, 0.5), 4, unidade='ms')
    self.assertEqual(v['resultado'], 'pior')
    self.assertEqual(v['motivo'], 'O MAE subiu 0,5 ms e o R² não subiu além do ruído.')

  def test_mae_subiu_com_ganho_de_r2_e_empate(self):
    self.assertEqual(SF.veredito(delta(0.03, 0.5), 4)['resultado'], 'empate')

  def test_sem_pooled_e_empate(self):
    self.assertEqual(SF.veredito(delta(None, None, {}), 4)['resultado'], 'empate')

  def test_motivo_do_melhor_usa_a_unidade(self):
    self.assertEqual(SF.veredito(delta(0.05, -4.1), 4, unidade='Mbps')['motivo'],
                     'O R² subiu 0,05 e o MAE caiu 4,1 Mbps, sem piorar nenhum local.')

  def test_provisorio_com_poucos_locais(self):
    v = SF.veredito(delta(0.05, -1.0), 3)
    self.assertTrue(v['provisorio'])
    self.assertEqual(v['motivos_provisorio'], ['só 3 locais de coleta'])

  def test_provisorio_com_pendente(self):
    v = SF.veredito(delta(0.05, -1.0), 4, ['router_tx_retries'])
    self.assertTrue(v['provisorio'])
    self.assertEqual(v['motivos_provisorio'], ['depende de vazamento não confirmado: router_tx_retries'])

  def test_nao_provisorio(self):
    v = SF.veredito(delta(0.05, -1.0), 4)
    self.assertEqual((v['provisorio'], v['motivos_provisorio']), (False, []))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestVeredito -v`
Expected: FAIL com `AttributeError: module 'ml.studio.features' has no attribute 'veredito'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/features.py`, troque o import de `ml.core.splits` por:

```python
from ml.core.splits import COMFORTABLE_SITES, outer_logo_folds
```

Logo depois de `ARVORES_PROXY = 100`, acrescente:

```python
# Diferença de R² abaixo disto é ruído com os poucos locais de coleta de hoje.
RUIDO_R2 = 0.02
UNIDADES = {'speedtest_down_mbps': 'Mbps', 'speedtest_up_mbps': 'Mbps', 'latency_ms': 'ms', 'jitter_ms': 'ms'}
```

Logo depois da função `delta_por_local`, acrescente:

```python
def _br_num(valor: float, casas: int) -> str:
  return f'{valor:.{casas}f}'.replace('.', ',')


def _com_sinal(valor: float, casas: int) -> str:
  return ('+' if valor > 0 else '−' if valor < 0 else '') + _br_num(abs(valor), casas)


def veredito(delta: dict, n_locais: int, pendentes=(), unidade: str = '') -> dict:
  """Melhor / empate / pior do rascunho contra a versão ativa, a partir de delta_por_local.

  Melhor exige R² pooled acima do ruído, MAE que não sobe e nenhum local piorando
  além do ruído. `pendentes` são features com vazamento ainda não confirmado.
  """
  dr2, dmae = delta.get('pooled'), delta.get('mae')
  piores = {s: d for s, d in sorted(delta.get('por_local', {}).items()) if d < -RUIDO_R2}
  mae_txt = lambda v: f'{_br_num(abs(v), 1)} {unidade}'.strip()
  if dr2 is None or dmae is None:
    resultado, motivo = 'empate', 'Sem R² pooled ou MAE para comparar.'
  elif dr2 <= -RUIDO_R2:
    resultado, motivo = 'pior', f'O R² caiu {_br_num(-dr2, 2)}.'
  elif dmae > 0 and dr2 < RUIDO_R2:
    resultado, motivo = 'pior', f'O MAE subiu {mae_txt(dmae)} e o R² não subiu além do ruído.'
  elif dr2 >= RUIDO_R2 and dmae <= 0 and not piores:
    resultado = 'melhor'
    mae = f'o MAE caiu {mae_txt(dmae)}' if dmae < 0 else 'o MAE não mudou'
    motivo = f'O R² subiu {_br_num(dr2, 2)} e {mae}, sem piorar nenhum local.'
  elif dr2 >= RUIDO_R2 and piores:
    lista = ', '.join(f'{s} ({_com_sinal(d, 3)})' for s, d in piores.items())
    resultado, motivo = 'empate', f'O R² subiu {_br_num(dr2, 2)}, mas piorou em {lista}.'
  elif dr2 >= RUIDO_R2:
    resultado, motivo = 'empate', f'O R² subiu {_br_num(dr2, 2)}, mas o MAE também subiu {mae_txt(dmae)}.'
  else:
    resultado = 'empate'
    motivo = (f'A diferença de R² ({_com_sinal(dr2, 3)}) é menor que o ruído '
              f'({_br_num(RUIDO_R2, 2)}) com {n_locais} locais.')
  provisorio = []
  if pendentes:
    provisorio.append(f'depende de vazamento não confirmado: {", ".join(pendentes)}')
  if n_locais < COMFORTABLE_SITES:
    provisorio.append(f'só {n_locais} locais de coleta')
  return {'resultado': resultado, 'motivo': motivo, 'provisorio': bool(provisorio),
          'motivos_provisorio': provisorio}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestVeredito -v`
Expected: 11 testes, OK

---

### Task 2: `ganho_mais_um()` extraída de `ajuste()`

**Files:**
- Modify: `src/ml/studio/features.py` (função nova antes de `ajuste`; bloco `ganho` dentro de `ajuste`)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente em `tests/test_studio_assistente.py`, antes do `if __name__`:

```python
class TestGanhoMaisUm(Base):
  def setUp(self):
    super().setUp()
    self.conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)

  def test_igual_ao_ganho_do_ajuste(self):
    inv = SF.inventario(self.conj, ['router_snr'])
    ok = SF.elegiveis(inv)
    candidatas = [c for c in inv['candidatas'] if c in ok]
    g = SF.ganho_mais_um(self.conj, ['router_snr'], candidatas, SF.vazadas_do_conjunto(self.conj))
    self.assertEqual(g, SF.ajuste(self.conj, inv)['ganho'])
    self.assertTrue(g)

  def test_progresso_uma_vez_por_candidata(self):
    eventos = []
    SF.ganho_mais_um(self.conj, ['router_snr'], ['router_signal_dbm', 'router_nss'], [], eventos.append)
    self.assertEqual([(e['feito'], e['total'], e['coluna']) for e in eventos],
                     [(1, 2, 'router_signal_dbm'), (2, 2, 'router_nss')])

  def test_base_vazia_devolve_lista_vazia(self):
    self.assertEqual(SF.ganho_mais_um(self.conj, [], ['router_snr'], []), [])

  def test_vazamento_na_base_sai_da_conta(self):
    g = SF.ganho_mais_um(self.conj, ['router_snr', 'router_tx_bytes'], ['router_nss'], ['router_tx_bytes'])
    self.assertEqual([x['coluna'] for x in g], ['router_nss'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestGanhoMaisUm -v`
Expected: FAIL com `AttributeError: ... has no attribute 'ganho_mais_um'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/features.py`, logo antes de `def ajuste(`:

```python
def ganho_mais_um(conj: Conjunto, base, candidatas, vazadas, progresso=None) -> list:
  """ΔR² médio por local ao somar cada candidata à base, do maior ganho para o menor.

  Features da base com vazamento ou ausentes do conjunto saem da conta. `progresso`
  recebe {'feito', 'total', 'coluna'} depois de cada candidata.
  """
  df, alvo = conj.df, conj.alvo
  base = [c for c in base if c in df.columns and c not in vazadas]
  ref = r2_por_local(df, base, alvo, vazadas)
  ganho = []
  if not ref:
    return ganho
  for i, coluna in enumerate(candidatas, 1):
    r = r2_por_local(df, base + [coluna], alvo, vazadas)
    deltas = [r[s] - ref[s] for s in ref if s in r]
    if deltas:
      ganho.append({'coluna': coluna, 'delta': round(mean(deltas), 4),
                    'melhora': sum(d > 0 for d in deltas), 'locais': len(deltas)})
    if progresso:
      progresso({'feito': i, 'total': len(candidatas), 'coluna': coluna})
  ganho.sort(key=lambda g: -g['delta'])
  return ganho
```

Dentro de `ajuste()`, troque este bloco:

```python
    ganho = []
    base = brutos['atual'][0]
    if base:
      for coluna in [c for c in inv['candidatas'] if c in ok]:
        r = r2_por_local(df, atual + [coluna], alvo, vazadas)
        deltas = [r[s] - base[s] for s in base if s in r]
        ganho.append({'coluna': coluna, 'delta': round(mean(deltas), 4),
                      'melhora': sum(d > 0 for d in deltas), 'locais': len(deltas)})
    ganho.sort(key=lambda g: -g['delta'])
```

por:

```python
    ganho = ganho_mais_um(conj, atual, [c for c in inv['candidatas'] if c in ok], vazadas)
```

- [ ] **Step 4: Rodar os testes novos e os de ajuste**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestGanhoMaisUm -v`
Expected: 4 testes, OK

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_features.py -v`
Expected: todos OK (o `ajuste()` não mudou de saída)

---

### Task 3: `lista_assistente()`

**Files:**
- Modify: `src/ml/studio/features.py` (função nova depois de `elegiveis`)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente em `tests/test_studio_assistente.py`:

```python
HIPOTESE = F.Derivada('snr_x_sinal', ('router_snr', 'router_signal_dbm'),
                      lambda df: df['router_snr'] * df['router_signal_dbm'], 'produto de teste',
                      formula='router_snr * router_signal_dbm', status='hipotese')


class TestListaAssistente(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, catalogo=(HIPOTESE,))
    inv = SF.inventario(conj, ['router_snr', 'AP_channel'])
    self.lista = {c['coluna']: c for c in SF.lista_assistente(inv, conj.catalogo)}

  def test_tr069_elegivel_e_liberada(self):
    c = self.lista['router_signal_dbm']
    self.assertTrue(c['liberada'])
    self.assertIsNone(c['motivo'])

  def test_vazamento_nao_e_liberado(self):
    c = self.lista['router_tx_bytes']
    self.assertFalse(c['liberada'])
    self.assertTrue(c['motivo'].startswith('vazamento'))

  def test_feature_da_base_fora_do_tr069_vem_com_motivo(self):
    c = self.lista['AP_channel']
    self.assertFalse(c['liberada'])
    self.assertTrue(c['no_modelo'])
    self.assertIn('fora do TR-069', c['motivo'])

  def test_cobertura_baixa(self):
    self.assertEqual(self.lista['router_power_dbm']['motivo'], 'cobertura baixa')

  def test_identificador_e_alvo_ficam_de_fora(self):
    self.assertNotIn('client_id', self.lista)
    self.assertNotIn('speedtest_down_mbps', self.lista)

  def test_hipotese_nao_e_liberada_e_traz_descricao(self):
    c = self.lista['snr_x_sinal']
    self.assertEqual((c['liberada'], c['hipotese'], c['derivada']), (False, True, True))
    self.assertEqual(c['descricao'], 'produto de teste')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestListaAssistente -v`
Expected: FAIL com `AttributeError: ... has no attribute 'lista_assistente'`

- [ ] **Step 3: Implementar**

Em `src/ml/studio/features.py`, logo depois de `def elegiveis(...)`:

```python
_FORA_DO_ASSISTENTE = {'identificador', 'alvo'}


def _motivo_bloqueio(c: dict, repetidas: set):
  if c['vazamento']:
    return 'vazamento: medida durante o teste'
  if c['classe'] != 'tr069':
    return f'fora do TR-069 ({c["classe"]})'
  if c.get('hipotese'):
    return 'hipótese: não passou no teste de aceite'
  if c['constante']:
    return 'constante neste conjunto'
  if c['cobertura'] < COBERTURA_MIN:
    return 'cobertura baixa'
  if c['tipo'] == 'categorica_alta':
    return 'categórica com muitos valores'
  if c['coluna'] in repetidas:
    return 'idêntica a outra coluna'
  return None


def lista_assistente(inv: dict, catalogo) -> list:
  """Colunas do assistente. `liberada` = TR-069 elegível; o resto vem com o motivo.

  O front mostra as liberadas e as que estiverem marcadas no rascunho; uma
  bloqueada pode ser desmarcada, nunca marcada de novo.
  """
  derivadas = {d.nome: d for d in catalogo}
  repetidas = set()
  for grupo in inv['grupos_identicos']:
    repetidas.update(grupo[1:])
  saida = []
  for c in inv['colunas']:
    if c['classe'] in _FORA_DO_ASSISTENTE:
      continue
    motivo = _motivo_bloqueio(c, repetidas)
    d = derivadas.get(c['coluna'])
    saida.append({'coluna': c['coluna'], 'liberada': motivo is None, 'motivo': motivo,
                  'classe': c['classe'], 'tipo': c['tipo'], 'vazamento': c['vazamento'],
                  'derivada': c['derivada'], 'hipotese': bool(c.get('hipotese')),
                  'pendente': c['pendente'], 'no_modelo': c['no_modelo'],
                  'descricao': d.descricao if d else c['parametro'],
                  'cobertura': c['cobertura'], 'rho': c['rho']})
  return sorted(saida, key=lambda c: c['coluna'])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestListaAssistente -v`
Expected: 6 testes, OK

---

### Task 4: `studio/receitas.py`

**Files:**
- Create: `src/ml/studio/receitas.py`
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever os testes que falham**

No topo de `tests/test_studio_assistente.py`, junto dos outros imports de `ml.studio`:

```python
from ml.studio import receitas as R
```

E antes do `if __name__`:

```python
class TestReceitas(unittest.TestCase):
  def test_cada_receita_gera_formula_e_nome_validos(self):
    colunas = ['router_tx_retries', 'router_tx_packets', 'router_NSS_TX_Station']
    for r in R.listar():
      m = R.montar(r['id'], colunas[:r['colunas']], set())
      formulas.analisar(m['formula'])
      self.assertRegex(m['nome'], F.NOME_DERIVADA)
      self.assertTrue(m['descricao'].endswith('(receita do assistente).'))

  def test_razao(self):
    self.assertEqual(R.montar('razao', ['router_tx_retries', 'router_tx_packets'], set()), {
      'formula': 'router_tx_retries / router_tx_packets',
      'nome': 'tx_retries_por_tx_packets',
      'descricao': 'Razão entre router_tx_retries e router_tx_packets (receita do assistente).'})

  def test_fracao_repete_a_primeira_coluna(self):
    m = R.montar('fracao', ['router_tx_duration_us', 'router_rx_duration_us'], set())
    self.assertEqual(m['formula'], 'router_tx_duration_us / (router_tx_duration_us + router_rx_duration_us)')
    self.assertEqual(m['nome'], 'fracao_tx_duration_us')

  def test_maiusculas_viram_minusculas(self):
    m = R.montar('produto', ['router_bandwith_TX_station', 'router_NSS_TX_Station'], set())
    self.assertEqual(m['nome'], 'bandwith_tx_station_x_nss_tx_station')

  def test_nome_longo_e_cortado_em_40(self):
    m = R.montar('razao', ['router_expected_throughput_mbps', 'router_bandwith_TX_station'], set())
    self.assertEqual(m['nome'], 'expected_throughput_mbps_por_bandwith_tx')

  def test_colisao_ganha_sufixo(self):
    m = R.montar('razao', ['router_tx_retries', 'router_tx_packets'], {'tx_retries_por_tx_packets'})
    self.assertEqual(m['nome'], 'tx_retries_por_tx_packets_2')

  def test_quantidade_errada_de_colunas(self):
    with self.assertRaises(ValueError):
      R.montar('por_canal', ['router_tx_rate_mbps', 'router_bandwith_TX_station'], set())

  def test_colunas_repetidas(self):
    with self.assertRaises(ValueError):
      R.montar('razao', ['router_snr', 'router_snr'], set())

  def test_receita_desconhecida(self):
    with self.assertRaises(ValueError):
      R.montar('logaritmo', ['router_snr'], set())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -v`
Expected: ERROR na importação: `ImportError: cannot import name 'receitas'`

- [ ] **Step 3: Implementar**

Crie `src/ml/studio/receitas.py`:

```python
"""Receitas de derivadas para o assistente: o técnico escolhe a forma e as colunas,
e a fórmula sai daqui, pronta para o teste de aceite de sempre (paralelos.testar)."""

import re

from ml.core import formulas

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
  return {'formula': formula, 'nome': _nome(nome, curtos, set(existentes)),
          'descricao': descricao.format(**{k.upper(): v for k, v in completos.items()})
          + ' (receita do assistente).'}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestReceitas -v`
Expected: 9 testes, OK

- [ ] **Step 5: Checkpoint**

Pare e liste para o usuário: `src/ml/studio/features.py`, `src/ml/studio/receitas.py` e `tests/test_studio_assistente.py`. Ele commita à mão.

---

### Task 5: Rotas da API

**Files:**
- Modify: `src/ml/studio/api.py` (`modelos_avaliar`, bloco de paralelos/derivadas e import)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever os testes que falham**

No topo de `tests/test_studio_assistente.py`, acrescente:

```python
from ml.studio import api
```

E antes do `if __name__`:

```python
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'teste'}}}


class TestRotasAssistente(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.patches = [mock.patch.object(api, '_conjunto', return_value=(conj, None)),
                    mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
                    mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr'})]
    for p in self.patches:
      p.start()
    api._modelos_cache.clear()
    api._desenhos.clear()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def test_avaliar_com_base_traz_veredito(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn(r['veredito']['resultado'], {'melhor', 'empate', 'pior'})
    self.assertTrue(r['veredito']['provisorio'])

  def test_avaliar_sem_base_nao_traz_veredito(self):
    r = api.modelos_avaliar(features='router_snr', ds='a.csv')
    self.assertNotIn('veredito', r)

  def test_colunas_do_assistente(self):
    colunas = {c['coluna']: c for c in api.assistente_colunas(ds='a.csv')['colunas']}
    self.assertTrue(colunas['router_signal_dbm']['liberada'])
    self.assertFalse(colunas['router_tx_bytes']['liberada'])

  def test_job_de_sugestoes_termina(self):
    job_id = api.assistente_sugestoes(ds='a.csv', base='v1')['id']
    fim = time.time() + 120
    while api.assistente_sugestoes_status(job_id)['status'] == 'rodando' and time.time() < fim:
      time.sleep(0.2)
    job = api.assistente_sugestoes_status(job_id)
    self.assertEqual(job['status'], 'pronto', job.get('erro'))
    self.assertEqual(job['resultado']['base'], 'v1')
    self.assertEqual(job['resultado']['ganho_min'], 0.01)
    self.assertNotIn('router_snr', [g['coluna'] for g in job['resultado']['ganho']])
    self.assertTrue(job['progresso'])

  def test_receitas(self):
    self.assertEqual([r['id'] for r in api.receitas_listar()['receitas']][0], 'razao')
    m = api.receitas_montar(api.MontarReceita(receita='razao', colunas=['router_tx_retries', 'router_tx_packets']))
    self.assertEqual(m['nome'], 'tx_retries_por_tx_packets')

  def test_receita_invalida_vira_422(self):
    with self.assertRaises(api.HTTPException) as ctx:
      api.receitas_montar(api.MontarReceita(receita='razao', colunas=['router_snr']))
    self.assertEqual(ctx.exception.status_code, 422)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -k TestRotasAssistente -v`
Expected: FAIL em `test_avaliar_com_base_traz_veredito` (`KeyError: 'veredito'`) e ERROR nos outros (`AttributeError: module 'ml.studio.api' has no attribute 'assistente_colunas'` etc.)

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`, acrescente aos imports de `ml.studio` (em ordem alfabética, depois de `plans`):

```python
from ml.studio import receitas as studio_receitas
```

Em `modelos_avaliar`, troque:

```python
      if base:
        saida['base'] = base
        saida['resumo_base'] = studio_features.avaliar_versao(conj, registro['versoes'][base]['features'], vazadas)
        saida['delta'] = studio_features.delta_por_local(resumo, saida['resumo_base'])
```

por:

```python
      if base:
        saida['base'] = base
        saida['resumo_base'] = studio_features.avaliar_versao(conj, registro['versoes'][base]['features'], vazadas)
        saida['delta'] = studio_features.delta_por_local(resumo, saida['resumo_base'])
        pendentes = [f for f in feats if conj.classes.get(f) is not None and conj.classes[f].pendente]
        saida['veredito'] = studio_features.veredito(saida['delta'], int(conj.df['_site'].nunique()),
                                                     pendentes, studio_features.UNIDADES[alvo])
```

Logo antes de `def _metadados_do_desenho(`, acrescente:

```python
# ---------------- Assistente ----------------

@app.get('/api/assistente/colunas')
def assistente_colunas(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  inv = studio_features.inventario(conj, core_modelos.ativo(registro))
  return {'colunas': studio_features.lista_assistente(inv, conj.catalogo)}


@app.post('/api/assistente/sugestoes')
def assistente_sugestoes(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '', base: str = ''):
  """Ganho +1 de cada coluna TR-069 liberada sobre a versão de partida, em thread."""
  feats = _features_base(base)

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    studio_features._checar_locais(conj.df)
    inv = studio_features.inventario(conj, core_modelos.ativo(registro))
    liberadas = [c['coluna'] for c in studio_features.lista_assistente(inv, conj.catalogo) if c['liberada']]
    candidatas = [c for c in liberadas if c not in feats]
    ganho = studio_features.ganho_mais_um(conj, feats, candidatas, studio_features.vazadas_do_conjunto(conj),
                                          progresso)
    return {'base': base or registro['ativo'], 'alvo': alvo, 'ganho': ganho,
            'ganho_min': studio_paralelos.GANHO_MIN}
  return _iniciar_job(('sugestoes', tuple(sorted(_lista(ds))), alvo, _ambiente(ambiente), base)
                      + _chave_versoes(), tarefa)


@app.get('/api/assistente/sugestoes/{job_id}')
def assistente_sugestoes_status(job_id: str):
  return _job(job_id)


@app.get('/api/receitas')
def receitas_listar():
  return {'receitas': studio_receitas.listar()}


class MontarReceita(BaseModel):
  receita: str
  colunas: list


@app.post('/api/receitas/montar')
def receitas_montar(corpo: MontarReceita):
  try:
    return studio_receitas.montar(corpo.receita, corpo.colunas, _colunas_conhecidas())
  except ValueError as erro:
    raise HTTPException(422, str(erro))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p test_studio_assistente.py -v`
Expected: todos OK (as Tasks 1 a 5 juntas)

- [ ] **Step 5: Checkpoint**

Pare e liste: `src/ml/studio/api.py` e `tests/test_studio_assistente.py`.

---

### Task 6: Navegação, seção e estilos

**Files:**
- Modify: `src/ml/studio/static/index.html`
- Modify: `src/ml/studio/static/studio.js`
- Modify: `src/ml/studio/static/styles.css`

- [ ] **Step 1: Ícone `i-equal`**

Em `index.html`, dentro de `<defs>`, logo depois do símbolo `i-check`:

```html
  <symbol id="i-equal" viewBox="0 0 24 24"><line x1="5" y1="9" x2="19" y2="9"/><line x1="5" y1="15" x2="19" y2="15"/></symbol>
```

- [ ] **Step 2: Barra lateral**

Em `index.html`, troque o `<nav>` inteiro por:

```html
  <nav>
    <button data-view="matrix" aria-current="true"><svg class="icon"><use href="#i-grid"/></svg> Capacidade</button>
    <button data-view="contention"><svg class="icon"><use href="#i-trend"/></svg> Contenção</button>
    <button data-view="constraint"><svg class="icon"><use href="#i-bars"/></svg> Restrição</button>
    <button data-view="assistente"><svg class="icon"><use href="#i-model"/></svg> Modelo</button>
    <button data-view="plan"><svg class="icon"><use href="#i-plan"/></svg> Planta</button>
    <button data-view="thresholds"><svg class="icon"><use href="#i-sliders"/></svg> Limiares</button>
    <button data-view="datasets"><svg class="icon"><use href="#i-db"/></svg> Datasets</button>
    <details class="nav-avancado">
      <summary>Avançado</summary>
      <button data-view="features"><svg class="icon"><use href="#i-layers"/></svg> Features</button>
      <button data-view="modelos"><svg class="icon"><use href="#i-model"/></svg> Modelos</button>
    </details>
  </nav>
```

- [ ] **Step 3: Seção e scripts**

Em `index.html`, logo antes de `<section id="view-features" class="view hide">`:

```html
  <section id="view-assistente" class="view hide">
    <div id="aBody"></div>
  </section>

```

No fim do arquivo, troque o bloco de scripts e o link do CSS para forçar recarga:

```html
<script src="graficos.js?v=4"></script>
<script src="features.js?v=5"></script>
<script src="modelos.js?v=9"></script>
<script src="paralelos.js?v=3"></script>
<script src="planta.js?v=4"></script>
<script src="assistente.js?v=1"></script>
<script src="studio.js?v=7"></script>
```

e, no `<head>`, `styles.css?v=10` por `styles.css?v=11`.

- [ ] **Step 4: `studio.js`**

Em `renderAll()`, logo depois da linha `if (state.view === 'features') V.views.features.render(ctxAnalise());`:

```js
    if (state.view === 'assistente') V.views.assistente.render(ctxAnalise());
```

Em `TITLES`, logo depois de `constraint: [...]`:

```js
    assistente: ['Modelo', 'Ajustar o modelo e testar uma versão nova, passo a passo, sem mexer no código.'],
```

Em `show(view)`, logo depois da linha que mexe em `aria-current`:

```js
    // Features e Modelos moram no grupo Avançado: abri-lo mostra onde a pessoa está.
    if (view === 'features' || view === 'modelos') $('.nav-avancado').open = true;
```

- [ ] **Step 5: Estilos**

No fim de `styles.css`:

```css
/* Assistente (view Modelo) */
.nav-avancado { margin-top: 8px; }
.nav-avancado summary { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-muted);
  padding: 8px 12px 4px; cursor: pointer; }
.passos { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
.passo { font: inherit; font-size: 12.5px; display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px;
  border-radius: 999px; border: 1px solid var(--border); background: var(--surface-1); color: var(--ink-2); cursor: pointer; }
.passo span { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%;
  background: var(--grid); font-size: 11px; font-weight: 650; }
.passo[aria-current="step"] { border-color: var(--s1); color: var(--ink-1); font-weight: 600; }
.passo[aria-current="step"] span { background: var(--s1); color: #fff; }
.passo:focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
.rodape-passo { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; }
.grupo { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-muted); margin: 14px 0 4px; }
.receita { border: 1px dashed var(--border); border-radius: 9px; padding: 12px 14px; margin-top: 16px; }
.veredito { display: flex; gap: 14px; align-items: center; padding: 14px 16px; margin: 14px 0 4px;
  border: 1px solid var(--border); border-left: 4px solid var(--axis); border-radius: 10px; }
.veredito .icon { width: 28px; height: 28px; stroke: var(--axis); flex: none; }
.veredito b { font-size: 20px; }
.veredito.melhor { border-left-color: var(--good); }
.veredito.melhor .icon { stroke: var(--good); }
.veredito.pior { border-left-color: var(--critical); }
.veredito.pior .icon { stroke: var(--critical); }
.btn.marcado { border-color: var(--s1); background: color-mix(in srgb, var(--s1) 10%, transparent); }
```

(Sem verificação isolada aqui: o `assistente.js` da Task 7 é quem registra `V.views.assistente`. As Tasks 6 e 7 são verificadas juntas no fim da Task 7.)

---

### Task 7: `assistente.js`, com a estrutura e o passo 1 (Preparar)

**Files:**
- Create: `src/ml/studio/static/assistente.js`

- [ ] **Step 1: Criar o arquivo**

Crie `src/ml/studio/static/assistente.js`. Os passos 2, 3 e 4 entram aqui como funções curtas e são trocados nas Tasks 8 e 9:

```js
/* assistente.js — view Modelo: assistente em quatro passos para o técnico de rede.
   Estado próprio; studio.js chama render(ctx) quando a view está visível. As views
   Features e Modelos continuam como modo avançado. */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d));
  const pct = (v) => Math.round(v * 100) + '%';

  const ALVOS = [['speedtest_down_mbps', 'Download', 'Mbps'], ['speedtest_up_mbps', 'Upload', 'Mbps'],
    ['latency_ms', 'Latência', 'ms'], ['jitter_ms', 'Jitter', 'ms']];
  const ALVO = Object.fromEntries(ALVOS.map(([k, r, u]) => [k, { rotulo: r, unidade: u }]));
  const PASSOS = ['Preparar', 'Ajustar', 'Testar', 'Publicar'];
  const CLASSES = [['tr069', 'Roteador (TR-069)'], ['sniffer', 'Sniffer'], ['cliente', 'Cliente'],
    ['ambiente', 'Ambiente'], ['geometria', 'Geometria'], ['identificador', 'Identificador'], ['alvo', 'Alvo']];
  const VEREDITO = { melhor: ['Melhor', 'i-check'], empate: ['Empate', 'i-equal'], pior: ['Pior', 'i-alert'] };
  const RESPOSTAS = { sim: 'Sim', nao: 'Não', nao_sei: 'Não sei' };
  const NOME_OK = /^[a-z0-9][a-z0-9-]{1,39}$/;

  const st = { ctx: null, passo: 1, alvo: 'speedtest_down_mbps', erro: null,
               reg: null, inv: null, invKey: null, pend: null, pendKey: null, dispensadas: new Set(),
               base: null, sel: new Set(), filtro: '', cols: null, colsKey: null,
               sug: null, sugKey: null, sugTimer: null,
               receitas: null, recAberto: false,
               rec: { id: 'razao', colunas: [], montada: null, nome: '', ocupado: false, erro: null, resultado: null },
               aval: null, avalKey: null, avalErro: null, avaliando: false,
               outros: null, outrosKey: null, outrosCarregando: false,
               nome: '', desc: '', descTocada: false, publicando: false, pubErro: null, pubMsg: null };

  const dsIds = () => st.ctx.enabledIds.slice().sort();
  const chaveConj = () => dsIds().join(',') + '|' + st.alvo + '|' + st.ctx.ambiente;
  const queryDe = (alvo) => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(alvo) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente);
  const query = () => queryDe(st.alvo);
  const selLista = () => [...st.sel].sort();
  const ativa = () => st.reg && st.reg.versoes.find((v) => v.nome === st.reg.ativo);
  const chaveVeredito = () => chaveConj() + '|' + selLista().join(',') + '|' + (st.reg ? st.reg.ativo : '');
  const igualAtiva = () => {
    const a = ativa();
    return !!a && JSON.stringify(a.features.slice().sort()) === JSON.stringify(selLista());
  };

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }
  const post = (url, corpo) => pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });

  const gate = (sev, titulo, msg) => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div></div></div>`;

  /* ---------------- carregamento ---------------- */
  function usarBase(nome) {
    st.base = nome;
    const v = st.reg && st.reg.versoes.find((x) => x.nome === nome);
    st.sel = new Set(v ? v.features : []);
  }

  function carregarRegistro() {
    return pedir('api/modelos').then((reg) => {
      st.reg = reg;
      if (!st.base || !reg.versoes.some((v) => v.nome === st.base)) usarBase(reg.ativo);
      if (st.passo === 2) iniciarSugestoes();
    }).catch((e) => { st.erro = e.message; }).finally(desenhar);
  }

  function carregarInventario() {
    const k = chaveConj();
    if (st.invKey === k) return;
    st.invKey = k; st.inv = null;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.invKey === k) st.inv = inv; })
      .catch((e) => { if (st.invKey === k) st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarPendencias() {
    const k = dsIds().join(',') + '|' + st.ctx.ambiente;
    if (st.pendKey === k) return;
    st.pendKey = k; st.pend = null;
    pedir('api/pendencias?ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) + '&ambiente=' + encodeURIComponent(st.ctx.ambiente))
      .then((p) => { if (st.pendKey === k) st.pend = p; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarColunas() {
    const k = chaveConj();
    if (st.colsKey === k) return;
    st.colsKey = k; st.cols = null;
    pedir('api/assistente/colunas?' + query())
      .then((r) => { if (st.colsKey === k) st.cols = r.colunas; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function carregarReceitas() {
    if (st.receitas) return;
    pedir('api/receitas').then((r) => { st.receitas = r.receitas; }).catch((e) => { st.erro = e.message; }).finally(desenhar);
  }

  function iniciarSugestoes() {
    if (!st.base) return;
    const k = chaveConj() + '|' + st.base;
    if (st.sugKey === k) return;
    st.sugKey = k; st.sug = { status: 'rodando', progresso: [] };
    clearTimeout(st.sugTimer);
    pedir('api/assistente/sugestoes?' + query() + '&base=' + encodeURIComponent(st.base), { method: 'POST' })
      .then((r) => acompanhar(r.id, k))
      .catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }

  function acompanhar(id, k) {
    pedir('api/assistente/sugestoes/' + id).then((job) => {
      if (st.sugKey !== k) return;
      st.sug = job;
      if (job.status === 'rodando') st.sugTimer = setTimeout(() => acompanhar(id, k), 1500);
      desenhar();
    }).catch((e) => { if (st.sugKey === k) { st.sug = { status: 'erro', erro: e.message }; desenhar(); } });
  }

  function carregar() {
    if (!st.reg) carregarRegistro();
    carregarInventario(); carregarPendencias(); carregarColunas(); carregarReceitas();
    if (st.passo === 2) iniciarSugestoes();
  }

  // Classificação, contadores ou derivada nova mudam as colunas e a chave das análises.
  function recarregarTudo() {
    st.invKey = null; st.pendKey = null; st.colsKey = null; st.sugKey = null;
    carregar();
    if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
  }

  /* ---------------- passo 1 · Preparar ---------------- */
  const pergunta = (titulo, msg, tipo, col, atual) => `<div class="pend-item warning"><div style="flex:1"><b>${titulo}</b>
    <div class="gate-msg">${msg}</div>
    <div class="controls" style="margin:8px 0 0">${Object.entries(RESPOSTAS).map(([k, r]) =>
      `<button class="btn${atual === k ? ' marcado' : ''}" data-aacao="${tipo}" data-col="${esc(col)}" data-resp="${k}">${r}</button>`).join('')}</div></div></div>`;

  function passoPreparar() {
    const alvo = `<div class="controls"><label for="aAlvo">O que o modelo prevê</label>
      <select id="aAlvo">${ALVOS.map(([k, r, u]) => `<option value="${k}"${k === st.alvo ? ' selected' : ''}>${r} (${u})</option>`).join('')}</select></div>`;
    const inv = st.inv, p = st.pend;
    if (!inv || !p) return alvo + '<p class="hint">Carregando pendências…</p>';
    const itens = [];
    inv.sem_classificacao.forEach((c) => itens.push(`<div class="pend-item warning" data-col="${esc(c.coluna)}"><div style="flex:1">
      <b>De onde vem <code>${esc(c.coluna)}</code>?</b>
      <div class="gate-msg">${pct(c.cobertura)} das linhas têm valor · ex.: ${esc(c.amostra)}</div>
      <div class="controls" style="margin:8px 0 0"><select aria-label="Origem de ${esc(c.coluna)}">${CLASSES.map(([k, r]) =>
        `<option value="${k}"${k === c.sugestao ? ' selected' : ''}>${r}${k === c.sugestao ? ' (sugerido)' : ''}</option>`).join('')}</select>
        <button class="btn-pri" data-aacao="classificar">Salvar</button></div></div></div>`));
    inv.colunas.filter((c) => c.suspeita && !c.derivada && !st.dispensadas.has(c.coluna)).forEach((c) => itens.push(pergunta(
      `<code>${esc(c.coluna)}</code> é medido durante o speedtest?`,
      `Anda quase igual ao alvo (|ρ| = ${num(c.rho, 2)}). Se for medido durante o teste, carrega o próprio resultado e não existe em produção.`,
      'suspeita', c.coluna, null)));
    if (p.contadores.estado === 'nao_sei') {
      itens.push(pergunta('Os contadores do roteador são medidos durante o speedtest?',
        `<code>${p.contadores.colunas.map(esc).join('</code>, <code>')}</code>. Enquanto ninguém responder, resultados que usam esses contadores ficam provisórios.`,
        'contadores', '', 'nao_sei'));
    }
    const lista = itens.length ? `<div class="pend-grid">${itens.join('')}</div>`
      : gate('good', 'Nenhuma pendência', 'Todas as colunas estão classificadas e não há pergunta de vazamento em aberto.');
    const poucos = p.n_locais < p.minimo_confortavel
      ? gate('warning', `Só ${p.n_locais} locais de coleta`, 'Os números ainda mudam quando novos prédios entrarem.') : '';
    return `${alvo}${poucos}<div class="card"><h2>Pendências</h2>
      <p class="hint">Não bloqueiam os próximos passos. Colunas sem classificação ficam de fora; respostas "não sei" marcam o resultado como provisório.</p>
      ${lista}</div>`;
  }

  function responder(acao, alvo) {
    st.erro = null;
    const col = alvo.dataset.col;
    const c = st.inv && st.inv.colunas.find((x) => x.coluna === col);
    let pedido = null;
    if (acao === 'classificar') {
      const classe = alvo.closest('.pend-item').querySelector('select').value;
      pedido = post('api/columns', { coluna: col, classe, vazamento: false, parametro: null });
    }
    if (acao === 'suspeita') {
      if (alvo.dataset.resp !== 'sim') { st.dispensadas.add(col); desenhar(); return; }
      pedido = post('api/columns', { coluna: col, classe: c.classe, vazamento: true, parametro: c.parametro || null });
    }
    if (acao === 'contadores') pedido = post('api/contadores', { estado: alvo.dataset.resp });
    pedido.then(recarregarTudo).catch((e) => { st.erro = e.message; desenhar(); });
  }

  /* ---------------- passos 2 a 4 (Tasks 8 e 9) ---------------- */
  function passoAjustar() { return '<p class="hint">Ajustar: entra na Task 8.</p>'; }
  function passoTestar() { return '<p class="hint">Testar: entra na Task 9.</p>'; }
  function passoPublicar() { return '<p class="hint">Publicar: entra na Task 9.</p>'; }

  /* ---------------- moldura ---------------- */
  function cabecalho() {
    return `<div class="passos">${PASSOS.map((p, i) => `<button class="passo" data-aacao="passo" data-n="${i + 1}"${st.passo === i + 1 ? ' aria-current="step"' : ''}><span>${i + 1}</span> ${p}</button>`).join('')}
      <a class="gate-msg" href="#modelos" style="margin-left:auto">Abrir no modo avançado</a></div>`;
  }

  function rodape() {
    const ant = st.passo > 1 ? `<button class="btn" data-aacao="passo" data-n="${st.passo - 1}">Voltar</button>` : '<span></span>';
    const prox = st.passo < PASSOS.length
      ? `<button class="btn-pri" data-aacao="passo" data-n="${st.passo + 1}"${st.passo === 2 && !st.sel.size ? ' disabled' : ''}>Próximo: ${PASSOS[st.passo]}</button>` : '';
    return `<div class="rodape-passo">${ant}${prox}</div>`;
  }

  function desenhar() {
    const host = $('#aBody');
    if (!st.ctx) return;
    if (!st.ctx.enabledIds.length) { host.innerHTML = '<p class="hint">Nenhum dataset ativo. Ligue um na view Datasets.</p>'; return; }
    const el = document.activeElement;
    const foco = el && host.contains(el) ? el.id : null;
    const cursor = foco && typeof el.selectionStart === 'number' ? el.selectionStart : null;
    const abertos = [...host.querySelectorAll('details.fold')].map((d) => d.open);
    const corpo = [passoPreparar, passoAjustar, passoTestar, passoPublicar][st.passo - 1]();
    host.innerHTML = cabecalho() + (st.erro ? gate('critical', 'Algo deu errado', esc(st.erro)) : '') + corpo + rodape();
    host.querySelectorAll('details.fold').forEach((d, i) => { if (i < abertos.length) d.open = abertos[i]; });
    if (foco && $('#' + foco)) {
      const novo = $('#' + foco);
      novo.focus();
      if (cursor != null) try { novo.setSelectionRange(cursor, cursor); } catch (e) { /* select não tem cursor */ }
    }
  }

  function irPara(n) {
    st.passo = n;
    if (n === 2) iniciarSugestoes();
    desenhar();
    window.scrollTo(0, 0);
  }

  /* ---------------- eventos ---------------- */
  $('#aBody').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-aacao]');
    if (!alvo || alvo.disabled) return;
    const acao = alvo.dataset.aacao;
    if (acao === 'passo') irPara(Number(alvo.dataset.n));
    if (acao === 'classificar' || acao === 'suspeita' || acao === 'contadores') responder(acao, alvo);
  });
  $('#aBody').addEventListener('change', (ev) => {
    if (ev.target.id === 'aAlvo') { st.alvo = ev.target.value; carregar(); desenhar(); }
  });

  V.views.assistente = {
    render(ctx) {
      st.ctx = ctx;
      carregar();
      desenhar();
    },
  };
})();
```

- [ ] **Step 2: Subir o Studio e verificar navegação e passo 1**

Run: `venv/bin/python src/ml/studio.py --port 8100` (em segundo plano)

No navegador, em `http://127.0.0.1:8100/#assistente`, verifique:
- a barra lateral mostra **Modelo** no lugar de Features/Modelos, e o grupo **Avançado** abre com os dois; clicar em Features ou Modelos continua funcionando como antes;
- `#features` na URL abre a view com o grupo Avançado aberto;
- o assistente mostra o stepper 1 a 4, o seletor de alvo e o cartão Pendências (ou "Nenhuma pendência"), e o aviso "Só N locais de coleta" enquanto houver menos de 4;
- "Abrir no modo avançado" leva à view Modelos;
- o console do navegador não tem erro.

Se não houver pendência nos dados atuais, simule uma: em `/api/features/inventario` confira `sem_classificacao` e `colunas[].suspeita`. **Não** grave respostas de teste em `column_provenance.json`; se gravar, reverta com `git checkout src/ml/core/column_provenance.json`.

- [ ] **Step 3: Checkpoint**

Pare e liste: `src/ml/studio/static/index.html`, `studio.js`, `styles.css` e `assistente.js`.

---

### Task 8: Passo 2 (Ajustar) e receitas

**Files:**
- Modify: `src/ml/studio/static/assistente.js`

- [ ] **Step 1: Trocar `passoAjustar` e acrescentar o painel de receita**

Em `assistente.js`, troque a linha:

```js
  function passoAjustar() { return '<p class="hint">Ajustar: entra na Task 8.</p>'; }
```

por:

```js
  function statusSugestoes(sug, sugerida) {
    if (!st.sug || st.sug.status === 'rodando') {
      const u = st.sug && st.sug.progresso && st.sug.progresso[st.sug.progresso.length - 1];
      return `calculando sugestões…${u ? ` ${u.feito}/${u.total}` : ''}`;
    }
    if (st.sug.status === 'erro') return `sugestões indisponíveis: ${esc(st.sug.erro)}`;
    return `sugestões sobre ${esc(sug.base)} · ${sug.ganho.filter(sugerida).length} coluna(s) sugerida(s)`;
  }

  function passoAjustar() {
    if (!st.reg || !st.cols) return '<p class="hint">Carregando colunas…</p>';
    const porNome = Object.fromEntries(st.cols.map((c) => [c.coluna, c]));
    const pronta = st.sug && st.sug.status === 'pronto' && st.sugKey === chaveConj() + '|' + st.base;
    const sug = pronta ? st.sug.resultado : null;
    const ganho = sug ? Object.fromEntries(sug.ganho.map((g) => [g.coluna, g])) : {};
    const sugerida = (g) => !!g && !!sug && g.delta >= sug.ganho_min && g.melhora === g.locais;
    const f = st.filtro.trim().toLowerCase();
    const vis = (nome) => !f || nome.toLowerCase().includes(f);
    const noModelo = selLista().filter(vis);
    const pontos = (c) => (ganho[c.coluna] ? ganho[c.coluna].delta : -9);
    const disponiveis = st.cols.filter((c) => c.liberada && !st.sel.has(c.coluna) && vis(c.coluna))
      .sort((a, b) => (pontos(b) - pontos(a)) || ((b.rho || 0) - (a.rho || 0)));
    const linha = (nome) => {
      const c = porNome[nome];
      const marcado = st.sel.has(nome);
      const g = ganho[nome];
      const tags = !c ? '<span class="tag leak">ausente neste conjunto</span>' : [
        c.derivada ? '<span class="tag">derivada</span>' : '',
        c.hipotese ? '<span class="tag mid" title="não passou no teste de aceite">hipótese</span>' : '',
        c.pendente ? '<span class="tag mid" title="vazamento ainda não confirmado">não confirmado</span>' : '',
        c.motivo && !c.hipotese ? `<span class="tag leak">${esc(c.motivo)}</span>` : '',
        sugerida(g) ? `<span class="tag ok">sugerida ${sinal(g.delta, 2)}</span>` : ''].join(' ');
      const travada = !marcado && !(c && c.liberada);
      return `<label class="mrow${travada ? ' dim' : ''}" title="${c && c.descricao ? esc(c.descricao) : ''}">
        <input type="checkbox" data-col="${esc(nome)}"${marcado ? ' checked' : ''}${travada ? ' disabled' : ''}>
        <code>${esc(nome)}</code><span>${tags}</span>
        <span class="num">${c ? pct(c.cobertura) : '–'}</span>
        <span class="num">${g ? sinal(g.delta, 3) : '–'}</span></label>`;
    };
    const opcoes = st.reg.versoes.map((v) => `<option value="${esc(v.nome)}"${v.nome === st.base ? ' selected' : ''}>${esc(v.nome)}${v.ativo ? ' (ativa)' : ''}</option>`).join('');
    return `<div class="card"><h2>Ajustar o rascunho</h2>
      <p class="hint">Só colunas do roteador (TR-069), que existem em produção. Marque e desmarque à vontade. "Sugerida" é a coluna que mais melhorou o modelo quando somada à versão de partida, em todos os locais de coleta.</p>
      <div class="controls"><label for="aBase">Partir de</label><select id="aBase">${opcoes}</select>
        <label for="aFiltro">Filtrar</label><input id="aFiltro" class="minput" type="search" placeholder="nome da coluna" value="${esc(st.filtro)}">
        <span class="chip">${st.sel.size} features</span><span class="gate-msg">${statusSugestoes(sug, sugerida)}</span></div>
      <div class="mhead"><span></span><span>Coluna</span><span></span><span class="num">Cobertura</span><span class="num">Ganho</span></div>
      <h3 class="grupo">No modelo</h3>${noModelo.map(linha).join('') || '<p class="hint">Nada marcado.</p>'}
      <h3 class="grupo">Disponíveis</h3>${disponiveis.map((c) => linha(c.coluna)).join('') || '<p class="hint">Nada com esse filtro.</p>'}
      ${painelReceita()}</div>`;
  }

  function painelReceita() {
    if (!st.recAberto) return '<div style="margin-top:14px"><button class="btn" data-aacao="abrir-receita">+ Criar métrica</button></div>';
    const r = st.rec;
    const def = (st.receitas || []).find((x) => x.id === r.id);
    const brutas = (st.cols || []).filter((c) => !c.derivada && c.classe === 'tr069' && c.tipo === 'numerica' && !c.vazamento)
      .map((c) => c.coluna);
    const letras = ['A', 'B', 'C'].slice(0, def ? def.colunas : 2);
    const seletores = letras.map((l, i) => `<label for="aCol${i}">${l}</label><select id="aCol${i}" data-rcol="${i}">
      <option value="">— escolha —</option>${brutas.map((b) => `<option${b === r.colunas[i] ? ' selected' : ''}>${esc(b)}</option>`).join('')}</select>`).join('');
    const montada = r.montada ? `<label>Fórmula</label><code>${esc(r.montada.formula)}</code>
      <label for="aRecNome">Nome</label><input id="aRecNome" class="minput" maxlength="40" value="${esc(r.nome)}">` : '';
    return `<div class="receita"><h2 style="font-size:13px">Criar métrica a partir de receita</h2>
      <div class="pform">
        <label for="aReceita">Receita</label><select id="aReceita">${(st.receitas || []).map((x) => `<option value="${x.id}"${x.id === r.id ? ' selected' : ''}>${esc(x.rotulo)}</option>`).join('')}</select>
        ${seletores}${montada}
      </div>
      ${def && def.dica ? `<p class="gate-msg" style="margin-top:6px">${esc(def.dica)}</p>` : ''}
      <div class="controls" style="margin-top:10px">
        <button class="btn-pri" data-aacao="salvar-receita"${!r.montada || r.ocupado ? ' disabled' : ''}>${r.ocupado ? 'Testando…' : 'Testar e salvar'}</button>
        <button class="btn" data-aacao="fechar-receita">Fechar</button>
        ${r.ocupado ? '<span class="gate-msg">o teste de aceite leva cerca de 1 minuto</span>' : ''}
      </div>
      ${r.erro ? gate('critical', 'Não deu', esc(r.erro)) : ''}
      ${r.resultado ? resultadoReceita(r.resultado) : ''}</div>`;
  }

  function resultadoReceita(res) {
    const ok = res.status === 'aprovada';
    const falhas = res.teste.criterios.filter((c) => !c.ok).map((c) => `<li>${esc(c.criterio)}</li>`).join('');
    const titulo = ok ? `Aprovada: melhora o ${ALVO[st.alvo].rotulo.toLowerCase()} em todos os locais`
      : 'Hipótese: não passou em todos os critérios';
    return gate(ok ? 'good' : 'warning', titulo,
      (ok ? '' : 'Fica salva e entra no rascunho, mas não é sugerida. ') + 'A métrica já está marcada no rascunho.' +
      (falhas ? `<ul>${falhas}</ul>` : ''));
  }

  function montarReceita() {
    const r = st.rec;
    const def = st.receitas.find((x) => x.id === r.id);
    r.montada = null; r.erro = null;
    const colunas = r.colunas.slice(0, def.colunas);
    if (colunas.length < def.colunas || colunas.some((c) => !c)) { desenhar(); return; }
    post('api/receitas/montar', { receita: r.id, colunas })
      .then((m) => { r.montada = m; r.nome = m.nome; })
      .catch((e) => { r.erro = e.message; })
      .finally(desenhar);
  }

  function salvarReceita() {
    const r = st.rec;
    r.ocupado = true; r.erro = null; r.resultado = null; desenhar();
    post('api/derivadas', { nome: r.nome, formula: r.montada.formula, descricao: r.montada.descricao,
                            base: st.base, ds: st.ctx.enabledIds.join(','), alvo: st.alvo, ambiente: st.ctx.ambiente })
      .then((res) => {
        r.resultado = res; st.sel.add(r.nome);
        r.montada = null; r.colunas = []; r.nome = '';
        recarregarTudo();
      })
      .catch((e) => { r.erro = e.message; })
      .finally(() => { r.ocupado = false; desenhar(); });
  }
```

- [ ] **Step 2: Ligar os eventos do passo 2**

No listener de `click`, logo depois da linha de `responder(acao, alvo)`:

```js
    if (acao === 'abrir-receita') { st.recAberto = true; desenhar(); }
    if (acao === 'fechar-receita') { st.recAberto = false; st.rec.resultado = null; st.rec.erro = null; desenhar(); }
    if (acao === 'salvar-receita') salvarReceita();
```

Troque o listener de `change` inteiro por:

```js
  $('#aBody').addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.id === 'aAlvo') { st.alvo = t.value; carregar(); desenhar(); return; }
    if (t.id === 'aBase') { usarBase(t.value); iniciarSugestoes(); desenhar(); return; }
    if (t.id === 'aReceita') { st.rec.id = t.value; st.rec.colunas = []; montarReceita(); return; }
    if (t.dataset.rcol != null) { st.rec.colunas[Number(t.dataset.rcol)] = t.value; montarReceita(); return; }
    if (t.dataset.col && t.type === 'checkbox') {
      if (t.checked) st.sel.add(t.dataset.col); else st.sel.delete(t.dataset.col);
      desenhar();
    }
  });
  $('#aBody').addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.id === 'aFiltro') { st.filtro = t.value; desenhar(); }
    if (t.id === 'aRecNome') st.rec.nome = t.value;
  });
```

(Os `data-col` do passo 1 estão em `div` e `button`, que não disparam `change`; por isso o `t.type === 'checkbox'` basta para separar os dois usos.)

- [ ] **Step 3: Verificar no navegador**

Recarregue `http://127.0.0.1:8100/#assistente` (Ctrl+Shift+R) e vá ao passo 2. Verifique:
- a versão ativa vem marcada em **No modelo**, e colunas dela fora do TR-069 aparecem com o motivo em vermelho; desmarcar faz a coluna sumir da lista e não dá para marcá-la de novo;
- **Disponíveis** tem só TR-069 liberadas, cerca de 40 e não mais de 150;
- a barra "calculando sugestões… N/M" anda, e no fim aparecem selos "sugerida +0,0x" nas colunas com ganho ≥ 0,01 em todos os locais, que vão para o topo;
- o filtro mantém o foco e o cursor enquanto se digita;
- trocar "Partir de" substitui o rascunho e recomeça as sugestões;
- "+ Criar métrica": escolher Razão e duas colunas mostra a fórmula e o nome gerado. Se estiver testando com dados reais, **não** clique em "Testar e salvar", porque isso grava em `derivadas.json`. Se clicar, reverta com `git checkout src/ml/core/derivadas.json`.
- console sem erro.

---

### Task 9: Passos 3 (Testar) e 4 (Publicar)

**Files:**
- Modify: `src/ml/studio/static/assistente.js`

- [ ] **Step 1: Trocar `passoTestar` e `passoPublicar`**

Troque as duas linhas:

```js
  function passoTestar() { return '<p class="hint">Testar: entra na Task 9.</p>'; }
  function passoPublicar() { return '<p class="hint">Publicar: entra na Task 9.</p>'; }
```

por:

```js
  function urlAvaliar(alvo) {
    return 'api/modelos/avaliar?' + queryDe(alvo) + '&features=' + encodeURIComponent(selLista().join(',')) +
      '&base=' + encodeURIComponent(st.reg.ativo);
  }

  function testar() {
    const k = chaveVeredito();
    st.avaliando = true; st.avalErro = null; desenhar();
    pedir(urlAvaliar(st.alvo))
      .then((a) => { st.aval = a; st.avalKey = k; })
      .catch((e) => { st.avalErro = e.message; })
      .finally(() => { st.avaliando = false; desenhar(); });
  }

  function testarOutros() {
    const k = chaveVeredito();
    st.outrosCarregando = true; desenhar();
    Promise.all(ALVOS.filter(([a]) => a !== st.alvo).map(([a]) => pedir(urlAvaliar(a))
      .then((r) => ({ alvo: a, resultado: r.veredito.resultado }))
      .catch(() => ({ alvo: a, erro: true }))))
      .then((xs) => { st.outros = xs; st.outrosKey = k; })
      .finally(() => { st.outrosCarregando = false; desenhar(); });
  }

  function outrosAlvos() {
    if (!st.outros || st.outrosKey !== chaveVeredito()) {
      return `<button class="btn" data-aacao="outros"${st.outrosCarregando ? ' disabled' : ''}>${st.outrosCarregando ? 'Calculando…' : 'Ver nos outros alvos'}</button>`;
    }
    return `<p class="gate-msg">Outros alvos, só informativo: ${st.outros.map((o) =>
      `${ALVO[o.alvo].rotulo}: ${o.erro ? 'erro' : VEREDITO[o.resultado][0]}`).join(' · ')}</p>`;
  }

  function cartaoVeredito(a, atual) {
    const v = a.veredito, d = a.delta, u = ALVO[a.alvo].unidade;
    const [rotulo, icone] = VEREDITO[v.resultado];
    const linhas = Object.keys(a.resumo.por_local).map((s) => `<tr><td>${esc(s)}</td>
      <td class="num">${num(a.resumo_base.por_local[s], 3)}</td><td class="num">${num(a.resumo.por_local[s], 3)}</td>
      <td class="num">${sinal(d.por_local[s])}</td>
      <td class="num">${num(a.resumo_base.mae_por_local[s], 1)}</td><td class="num">${num(a.resumo.mae_por_local[s], 1)}</td></tr>`).join('');
    return `<div class="${atual ? '' : 'stale'}">
      <div class="veredito ${v.resultado}"><svg class="icon"><use href="#${icone}"/></svg>
        <div><b>${rotulo}</b>${v.provisorio ? ` <span class="tag mid" title="${esc(v.motivos_provisorio.join('; '))}">provisório</span>` : ''}
          ${atual ? '' : ' <span class="tag lab">desatualizado: o rascunho, os dados ou o alvo mudaram</span>'}
          <div class="gate-msg">${esc(v.motivo)}</div></div></div>
      <div class="kpis">
        <div><span>R² pooled</span><b>${num(a.resumo_base.pooled, 3)} → ${num(a.resumo.pooled, 3)}</b></div>
        <div><span>MAE (${u})</span><b>${num(a.resumo_base.mae, 1)} → ${num(a.resumo.mae, 1)}</b></div>
        <div><span>Melhora em</span><b>${d.melhora} de ${d.locais}</b><em>locais</em></div>
      </div>
      <details class="fold"><summary>Ver detalhes por local</summary><div class="inner" style="overflow-x:auto"><table>
        <thead><tr><th>Local de coleta</th><th class="num">R² ativa</th><th class="num">R² rascunho</th><th class="num">Δ R²</th>
        <th class="num">MAE ativa</th><th class="num">MAE rascunho</th></tr></thead><tbody>${linhas}</tbody></table></div></details>
      <div style="margin-top:10px">${outrosAlvos()}</div></div>`;
  }

  function passoTestar() {
    if (!st.reg) return '<p class="hint">Carregando versões…</p>';
    const vazio = !st.sel.size, igual = igualAtiva();
    const motivo = vazio ? 'O rascunho está vazio.' : igual ? `O rascunho é igual à versão ativa (${esc(st.reg.ativo)}).` : '';
    let corpo = '';
    if (st.avalErro) corpo = gate('critical', 'Não foi possível testar', esc(st.avalErro));
    else if (st.aval) corpo = cartaoVeredito(st.aval, st.avalKey === chaveVeredito());
    return `<div class="card"><div class="card-head"><div><h2>Testar contra a versão ativa</h2>
      <p class="hint">Rascunho com ${st.sel.size} features contra <code>${esc(st.reg.ativo)}</code>, prevendo ${ALVO[st.alvo].rotulo.toLowerCase()}. Cada local de coleta fica de fora uma vez. Leva cerca de 20 s.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-aacao="testar"${vazio || igual || st.avaliando ? ' disabled' : ''}>${st.avaliando ? 'Testando…' : 'Testar'}</button>
      <div class="status">${motivo}</div></div></div>${corpo}</div>`;
  }

  function sugerirNome(ativo, nomes) {
    const m = ativo.match(/^(\D*)(\d+)(.*)$/);
    const gerar = m ? (i) => m[1] + i + m[3] : (i) => `${ativo}-${i}`;
    let i = m ? Number(m[2]) + 1 : 2;
    while (nomes.includes(gerar(i))) i += 1;
    return gerar(i);
  }

  function descricaoSugerida() {
    const a = ativa();
    const antes = new Set(a ? a.features : []);
    const mais = selLista().filter((f) => !antes.has(f)).map((f) => '+' + f);
    const menos = [...antes].filter((f) => !st.sel.has(f)).sort().map((f) => '−' + f);
    let txt = mais.concat(menos).join(' ') || 'sem mudança de features';
    if (st.aval && st.avalKey === chaveVeredito()) {
      txt += ` · ${ALVO[st.alvo].rotulo.toLowerCase()}: ${VEREDITO[st.aval.veredito.resultado][0].toLowerCase()}` +
        ` (R² ${num(st.aval.resumo_base.pooled, 2)}→${num(st.aval.resumo.pooled, 2)})`;
    }
    return txt.slice(0, 500);
  }

  function publicar(ativar) {
    st.pubErro = null; st.pubMsg = null;
    if (!NOME_OK.test(st.nome)) { st.pubErro = 'Nome inválido: use minúsculas, dígitos e hífen (2 a 40 caracteres).'; desenhar(); return; }
    if (!st.desc.trim()) { st.pubErro = 'Escreva uma descrição: ela é o que explica a versão no git log.'; desenhar(); return; }
    const nome = st.nome;
    st.publicando = true; desenhar();
    post('api/modelos', { nome, descricao: st.desc, features: selLista(), ds: st.ctx.enabledIds.join(','), ambiente: st.ctx.ambiente })
      .then((reg) => (ativar ? post('api/modelos/ativo', { nome }) : reg))
      .then((reg) => {
        st.reg = reg; st.base = nome; st.nome = ''; st.descTocada = false;
        st.pubMsg = `Versão ${nome} salva${ativar ? ' e ativa' : ''} em src/ml/core/modelos.json. Revise no git diff antes do commit.`;
        st.invKey = null; st.sugKey = null;
        if (V.views.modelos && V.views.modelos.recarregar) V.views.modelos.recarregar();
      })
      .catch((e) => { st.pubErro = e.message; })
      .finally(() => { st.publicando = false; desenhar(); });
  }

  function passoPublicar() {
    if (!st.reg) return '<p class="hint">Carregando versões…</p>';
    if (!st.nome) st.nome = sugerirNome(st.reg.ativo, st.reg.versoes.map((v) => v.nome));
    if (!st.descTocada) st.desc = descricaoSugerida();
    const atual = st.aval && st.avalKey === chaveVeredito();
    const melhor = atual && st.aval.veredito.resultado === 'melhor';
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? '' : 'Para ativar uma versão que não é melhor que a ativa, use o modo Avançado.';
    return `<div class="card"><h2>Publicar</h2>
      <p class="hint">A versão salva é imutável e vai para <code>src/ml/core/modelos.json</code>. Complete a descrição com o porquê da mudança.</p>
      <div class="pform"><label for="aNome">Nome</label><input id="aNome" class="minput" maxlength="40" value="${esc(st.nome)}">
        <label for="aDesc">Descrição</label><input id="aDesc" class="minput" maxlength="500" value="${esc(st.desc)}"></div>
      <div class="controls" style="margin-top:12px">
        <button class="btn" data-aacao="salvar"${st.publicando || !st.sel.size ? ' disabled' : ''}>Salvar versão</button>
        <button class="btn-pri" data-aacao="salvar-ativar"${st.publicando || !melhor ? ' disabled' : ''}>Salvar e tornar ativa</button>
        ${trava ? `<span class="gate-msg">${trava}</span>` : ''}</div>
      ${st.pubErro ? gate('critical', 'Não foi possível salvar', esc(st.pubErro)) : ''}
      ${st.pubMsg ? gate('good', 'Feito', esc(st.pubMsg)) : ''}</div>`;
  }
```

- [ ] **Step 2: Ligar os eventos dos passos 3 e 4**

No listener de `click`, logo depois da linha de `salvar-receita`:

```js
    if (acao === 'testar') testar();
    if (acao === 'outros') testarOutros();
    if (acao === 'salvar') publicar(false);
    if (acao === 'salvar-ativar') publicar(true);
```

No listener de `input`, logo depois da linha de `aRecNome`:

```js
    if (t.id === 'aNome') st.nome = t.value;
    if (t.id === 'aDesc') { st.desc = t.value; st.descTocada = true; }
```

- [ ] **Step 3: Verificar no navegador**

Recarregue (Ctrl+Shift+R) e verifique:
- **Passo 3**, com o rascunho igual à ativa: "Testar" fica desabilitado com "O rascunho é igual à versão ativa". Tire ou ponha uma feature no passo 2 e volte: "Testar" liga; em cerca de 20 s aparece o veredito com ícone, motivo, os três números e o selo "provisório" (hoje há menos de 4 locais). "Ver detalhes por local" abre a tabela. "Ver nos outros alvos" mostra uma linha com os três outros alvos.
- Mudar o rascunho depois do teste deixa o cartão esmaecido com "desatualizado".
- **Passo 4**: o nome vem sugerido (por exemplo, `v3-tr069` se a ativa for `v2-tr069`) e a descrição vem com o diff e o veredito. Com veredito que não é Melhor, "Salvar e tornar ativa" fica desabilitado com a explicação. Sem teste atual, a mensagem pede para testar.
- **Não** salve versões de teste em `modelos.json`. Se salvar, reverta com `git checkout src/ml/core/modelos.json`.
- Console sem erro. Tema escuro (botão Tema) legível no stepper e no cartão de veredito.

---

### Task 10: Suíte completa, alinhamento do spec e fechamento

**Files:**
- Modify: `docs/superpowers/specs/2026-09-30-qoe-studio-assistente-modelo-design.md`

- [ ] **Step 1: Alinhar o spec com o que foi implementado**

No spec, §6, troque:

```
calculado no servidor pela função pura `veredito(resumo, resumo_base, delta, n_locais)` em `studio/features.py`:
```

por:

```
calculado no servidor pela função pura `veredito(delta, n_locais, pendentes, unidade)` em `studio/features.py`:
```

No §5, troque:

```
   A Razão traz a dica "normaliza pelo volume" quando A e B são contadores.
```

por:

```
   A Razão traz sempre a dica "divide dois contadores: o volume de tráfego se cancela", e Por canal traz um exemplo de uso.
```

- [ ] **Step 2: Rodar a suíte inteira**

Run: `venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: `OK` no fim, sem falhas nem erros

- [ ] **Step 3: Conferir que nenhum arquivo de dados versionado mudou**

Run: `git status --short src/ml/core/`
Expected: nenhuma linha para `column_provenance.json`, `derivadas.json` ou `modelos.json`. Se houver, foi teste manual: reverta com `git checkout <arquivo>`.

- [ ] **Step 4: Checkpoint final**

Pare e liste para o usuário todos os arquivos alterados ou criados:
- `src/ml/studio/features.py`
- `src/ml/studio/receitas.py`
- `src/ml/studio/api.py`
- `src/ml/studio/static/assistente.js`
- `src/ml/studio/static/index.html`
- `src/ml/studio/static/studio.js`
- `src/ml/studio/static/styles.css`
- `tests/test_studio_assistente.py`
- `docs/superpowers/specs/2026-09-30-qoe-studio-assistente-modelo-design.md`
- `docs/superpowers/plans/2026-09-30-qoe-studio-assistente-modelo.md`

Ele commita à mão.
