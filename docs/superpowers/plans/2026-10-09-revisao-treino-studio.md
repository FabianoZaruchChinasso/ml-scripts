# Revisão do treinamento e do Studio: plano de mitigação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar os problemas achados na revisão de 2026-10-09: a ativação no Assistente passa a seguir a régua de promoção, o Studio e os scripts medem cada versão do mesmo jeito, o MLflow passa a guardar o que a produção precisa para usar o modelo, e o Studio para de esconder dados e de aceitar escrita de outra origem.

**Architecture:** Mudanças pequenas e independentes, cada uma com teste próprio. Um módulo novo, `src/ml/core/producao.py`, guarda o contrato de entrada do modelo (as colunas exatas que o modelo final viu e as categorias) e refaz a matriz de uma linha de produção. O resto são correções em `core/avaliacao.py`, `core/limiar.py`, `core/carga.py`, `core/aplicacoes.py`, nos módulos do Studio e em dois scripts de treino. A régua (`VERSAO_REGUA`) não muda: nenhum número de avaliação muda, só o que é registrado e mostrado.

**Tech Stack:** Python 3.12, pandas 2.3, numpy, scikit-learn 1.9, MLflow 3.15, FastAPI. Testes com `unittest`. Front em JS puro.

---

## Achados da revisão

Gravidade: **alta** = decide errado ou quebra produção; **média** = mede diferente do que diz; **baixa** = robustez ou higiene.

| # | Achado | Onde | Gravidade | Task |
|---|---|---|---|---|
| 1 | "Salvar e tornar ativa" no Assistente libera pelo veredito antigo de R² (`studio_features.veredito`), não pela régua de promoção com intervalos. A promoção aparece no cartão, mas não decide nada. | `static/assistente.js` (`passoPublicar`, `testarOutros`) | alta | 1 |
| 2 | O MLflow não guarda as colunas da matriz final. `matriz` faz one-hot com as categorias presentes no treino (`radio_5ghz`, `client_mode_WiFi 4 (11n)`); uma linha de produção sozinha gera outras colunas. O TR-069 manda `OperatingFrequencyBand` como `5GHz`, o treino viu `5ghz`. | `regression_mlflow.py`, `core/features.py:matriz` | alta | 9 |
| 3 | Os fatores do "atende ajustado" (`fatores_producao`) só vão para `modelos.json` pelo Studio; o run do MLflow não os registra, então a produção não tem como aplicá-los. | `regression_mlflow.py` | alta | 9 |
| 4 | A view Features (`ajuste`) avalia as versões salvas sem o denominador delas; a view Modelos (`comparar`) usa o denominador. `v4-tr069` e `v5-tr069` aparecem com dois números diferentes. | `studio/features.py:ajuste`, `api.py:features_ajuste` | média | 2 |
| 5 | A nota aninhada do desenho automático treina com as linhas no teto de WAN e não corta a previsão no teto. A nota da seleção usa a régua. A diferença entre as duas, que é o ponto da tela, mistura otimismo de seleção com diferença de protocolo. | `studio/selecao.py:aninhada` | média | 3 |
| 6 | A chave de cache do Studio não inclui `aplicacoes.json`: mudar um limiar com o servidor no ar deixa a promoção e a avaliação antigas no cache. | `api.py:_chave_versoes` | média | 4 |
| 7 | O payload do Studio decide o prédio por uma lista própria de posições (`BUILDINGS[...]['positions']`), diferente das regras por prefixo de `core/sites.py`. Uma posição nova (`marcelo-garagem`) entra no treino e some do Studio sem aviso. Para uma view de qualidade de dados, esconder linhas em silêncio é o pior caso. | `studio/data.py:_building_of` | média | 5 |
| 8 | Entre datasets com os mesmos alvos, o mantido é o primeiro em ordem alfabética. Hoje isso escolhe `-fix` e `-distcalc` por sorte (`-` vem antes de `.`); um `_fix` escolheria o original. | `core/carga.py:duplicatas` | média | 6 |
| 9 | `veredito_promocao` quebra com `TypeError` se um intervalo vier `None` (`_intervalo` devolve `None` quando todas as reamostragens dão NaN). | `core/avaliacao.py` | baixa | 7 |
| 10 | O intervalo de 90% reamostra posições com os prédios fixos: não mede a variação entre prédios, que é a incerteza de "prédio novo". Com 4 prédios, um "melhor" pode esconder um prédio piorando. | `core/avaliacao.py`, `core/limiar.py` | média | 8 |
| 11 | `regression_benchmark.py` ignora o denominador da versão: para `v4`/`v5` mede outra coisa que o Studio. | `regression_benchmark.py` | baixa | 10 |
| 12 | Escritas e jobs do Studio aceitam POST de qualquer página aberta no navegador da máquina (rotas sem corpo JSON não têm preflight) e de um domínio com DNS rebinding apontando para 127.0.0.1. `_so_local` só olha o IP do cliente. | `api.py` | baixa | 11 |
| 13 | `classifier_mlflow.py` lê `data/metrics-20260630-qoe.csv` (geração antiga, fora da carga canônica), classifica `qoe_dw_score` (fórmula perdida), divide aleatoriamente e usa os contadores com vazamento. Parece um script de treino válido e não é. | `src/ml/classifier_mlflow.py` | baixa | 12 |

### Decisões que ficam com você (fora deste plano)

Nenhuma Task mexe nestes pontos. Cada um precisa de uma decisão sua ou de mudança fora do repositório.

- **Token do InfluxDB no git.** `src/get-all.py:10` tem um token em comentário, já no histórico. Apagar a linha não basta: o token precisa ser revogado e trocado no InfluxDB. As regras dos planos anteriores proíbem mexer em `src/get-all.py`, então a remoção fica com você.
- **A versão ativa ainda é `v1`.** 5 das 14 features dela (`router_tx_duration_us`, `router_rx_duration_us`, `router_tx_retries`, `router_tx_failed`, `router_rx_drop_misc`) estão marcadas como vazamento. `regression_mlflow.py` sem `MODELO=` treina a `v1` com 9 features, em silêncio, e a promoção nunca comparou `v5-tr069` contra `v1`. Vale rodar a promoção `v5` × `v1` e decidir a ativa.
- **`n_clients` e `concorrentes_mesmo_radio` são variáveis do desenho do teste.** Estão como `tr069` com a nota "em produção depende do coletor". Se o coletor de produção não tiver o equivalente (estações ativas no rádio), a `v3`/`v5` não roda em produção. Marcar como `pendente` até isso estar definido é uma opção.
- **Medidas instantâneas tiradas durante o teste.** `router_rx_rate_mbps`, `router_expected_throughput_mbps` e `router_opportunity_medium_use` não são contadores de volume, mas são amostrados com o speedtest rodando. Dentro de uma mesma posição, a correlação de Spearman com o download é 0,61, 0,57 e −0,43. Parte disso pode ser o enlace sob carga, que a produção (enlace ocioso) não vê. A correção é a mesma janela anterior ao teste (`router_pre_*`) já pedida ao coletor.
- **Otimismo de escolha que continua.** A varredura de 6 configurações em `regression_mlflow.py` escolhe a melhor olhando os mesmos 4 prédios. O teste de aceite de derivadas também roda nos mesmos 4 prédios a cada fórmula tentada. Com 4 prédios, não há como separar um conjunto de validação. Só coleta nova resolve.
- **O payload não marca as linhas que a régua descarta** (teste falho, sem stats de estação, teto de WAN). As views de capacidade mostram 328 linhas sem stats de estação que o treino não vê. Marcá-las por linha é uma feature nova para o Studio, não uma correção.

---

## Regras para quem executa

- **Nunca rode `git commit`, `git push`, `git add`, `git mv` nem `git stash`.** O usuário faz commit à mão.
- **Nunca acrescente linha `Co-Authored-By` de Claude** em nada.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python. Comentários e mensagens em português. Sem emojis.
- Rode a partir da raiz (`/home/venko/ml/TR069/ml-scripts`) com o venv ativo (`source venv/bin/activate`). O venv não tem `pytest` nem `httpx`: os testes são `unittest`.
- Suíte completa: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`. Antes deste plano: `Ran 415 tests`, `OK`, cerca de 90 s.
- Um arquivo só: `python3 -m unittest discover -s tests -p "test_carga.py" 2>&1 | tail -3`. `tests/test_studio_assistente.py` só roda por `discover`.
- Em cada arquivo de teste, o bloco `if __name__ == '__main__': unittest.main()` fica por último.
- Leia cada função antes de editá-la: os trechos "troque X por Y" citam o código atual pelo conteúdo, não pelo número da linha.
- **Não rode nada pesado em segundo plano junto com a suíte.** Os modelos usam `n_jobs=-1`.
- As Tasks são independentes, com duas exceções: a Task 8 usa `promocaoDe`, criada na Task 1, e a Task 13 fecha tudo. Ordem recomendada: a numérica.

## Mapa de arquivos

| Arquivo | O que muda | Task |
|---|---|---|
| `src/ml/studio/static/assistente.js` | Ativação e "outros alvos" pela régua de promoção; prédios contra no cartão | 1, 8 |
| `src/ml/studio/features.py` | `ajuste` recebe `denominadores` | 2 |
| `src/ml/studio/api.py` | `features_ajuste` passa denominadores; cache com `aplicacoes.json`; middleware de Host/Origin | 2, 4, 11 |
| `src/ml/studio/selecao.py` | `aninhada` com as regras de teto de WAN da régua | 3 |
| `src/ml/core/aplicacoes.py` | `versao()` | 4 |
| `src/ml/studio/data.py` | Prédio pelo `core/sites.py`; `locaisDesconhecidos` no payload | 5 |
| `src/ml/studio/static/studio.js` | Aviso de local desconhecido; `esc` | 5 |
| `src/ml/core/carga.py` | `duplicatas` com preferência explícita | 6 |
| `src/ml/core/avaliacao.py` | `veredito_promocao` robusto; `por_predio` e `predios_contra` | 7, 8 |
| `src/ml/core/limiar.py` | `delta_decisoes` com `por_predio` | 8 |
| `src/ml/core/producao.py` | Novo: contrato de entrada | 9 |
| `src/ml/regression_mlflow.py` | Registra `contrato.json` e `fatores_atende.json` | 9 |
| `src/ml/regression_benchmark.py` | `--modelo` e denominador da versão | 10 |
| `src/ml/classifier_mlflow.py` | Movido para `src/ml/experimental/` | 12 |
| `src/ml/experimental/README.md` | Defeitos do `classifier_mlflow.py` | 12 |
| `tests/test_studio_features.py`, `tests/test_selecao.py`, `tests/test_aplicacoes.py`, `tests/test_carga.py`, `tests/test_avaliacao.py`, `tests/test_limiar.py`, `tests/test_studio_assistente.py` | Testes novos | 2 a 8, 11 |
| `tests/test_producao.py` | Novo | 9 |
| `CHANGELOG.md` | Entrada nova no topo | 13 |

---

### Task 1: Ativação no Assistente pela régua de promoção

O botão "Salvar e tornar ativa" só libera quando o veredito é "melhor". Hoje esse veredito é o antigo, de R² sem intervalo (`a.veredito`). A régua de promoção (`a.promocao.veredito`: Δ MAE e Δ "atende ajustado" com intervalo de 90%; pinball e cobertura em latência e jitter) aparece no cartão, mas não decide. Esta Task faz a régua decidir. Sem teste automático: o front não tem suíte. A verificação é no navegador, na Task 13.

**Files:**
- Modify: `src/ml/studio/static/assistente.js`

- [ ] **Step 1: Helper `promocaoDe`**

Em `assistente.js`, logo antes de `function testarOutros() {`, acrescente:

```js
  // A ativação e o resumo seguem a régua de promoção (intervalos de 90%), não o veredito de R².
  // Sem `promocao` (avaliação sem base), cai no veredito antigo.
  const promocaoDe = (a) => (a.promocao ? a.promocao.veredito : a.veredito);
```

- [ ] **Step 2: "Outros alvos" pela régua**

Em `testarOutros`, troque:

```js
      .then((r) => ({ alvo: a, resultado: r.veredito.resultado }))
```

por:

```js
      .then((r) => ({ alvo: a, resultado: promocaoDe(r).resultado }))
```

Em `outrosAlvos`, troque o texto `Outros alvos, só informativo: ` por `Outros alvos pela régua de promoção, só informativo: `.

- [ ] **Step 3: Descrição sugerida pela régua**

Em `descricaoSugerida`, troque:

```js
      txt += ` · ${ALVO[st.alvo].rotulo.toLowerCase()}: ${VEREDITO[st.aval.veredito.resultado][0].toLowerCase()}` +
```

por:

```js
      txt += ` · ${ALVO[st.alvo].rotulo.toLowerCase()}: ${VEREDITO[promocaoDe(st.aval).resultado][0].toLowerCase()}` +
```

- [ ] **Step 4: Trava de ativação pela régua**

Em `passoPublicar`, troque:

```js
    const melhor = atual && st.aval.veredito.resultado === 'melhor';
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? '' : 'Para ativar uma versão que não é melhor que a ativa, use o modo Avançado.';
```

por:

```js
    const melhor = atual && promocaoDe(st.aval).resultado === 'melhor';
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? '' : 'A régua de promoção não diz "melhor": para ativar mesmo assim, use o modo Avançado.';
```

- [ ] **Step 5: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/assistente.js && echo ok`
Expected: `ok`

Run: `grep -n "st\.aval\.veredito\|r\.veredito" src/ml/studio/static/assistente.js`
Expected: nenhuma linha. O cartão (`cartaoVeredito`) continua mostrando os dois vereditos, por `v` e `p`.

---

### Task 2: View Features avalia cada versão com o denominador dela

**Files:**
- Modify: `src/ml/studio/features.py` (`ajuste`)
- Modify: `src/ml/studio/api.py` (`features_ajuste`)
- Test: `tests/test_studio_features.py` (classe `TestModelos`)

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_features.py`, na classe `TestModelos`, logo depois de `test_ajuste_inclui_versoes_que_nao_sao_a_ativa`, acrescente:

```python
  def test_ajuste_avalia_versao_com_o_denominador_dela(self):
    aj = SF.ajuste(self.conj, self.inv, {'v1': ['router_snr'], 'v2': ['router_snr', 'radio']},
                   {'v2': {'speedtest_down_mbps': 'router_snr'}})
    self.assertEqual(aj['versoes'][0]['denominador'], 'router_snr')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_features.py" 2>&1 | tail -3`
Expected: `FAILED (errors=1)`, com `TypeError: ajuste() takes from 2 to 3 positional arguments but 4 were given`.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/features.py`, troque a assinatura e a docstring de `ajuste`:

```python
def ajuste(conj: Conjunto, inv: dict, versoes: dict = None) -> dict:
  """Teto, ganho +1 e proxies. `versoes` (nome -> features) entram no teto ao lado do ativo."""
```

por:

```python
def ajuste(conj: Conjunto, inv: dict, versoes: dict = None, denominadores: dict = None) -> dict:
  """Teto, ganho +1 e proxies. `versoes` (nome -> features) entram no teto ao lado do ativo.

  `denominadores` ({nome: {alvo: coluna}}) avalia cada versão com o seu, como em `comparar`.
  """
```

E, no mesmo `ajuste`, troque:

```python
    outras = [dict(avaliar_versao(conj, feats, vazadas), nome=nome)
              for nome, feats in (versoes or {}).items() if list(feats) != inv['modelo']]
```

por:

```python
    outras = [dict(avaliar_versao(conj, feats, vazadas,
                                  denominador=((denominadores or {}).get(nome) or {}).get(conj.alvo)),
                   nome=nome)
              for nome, feats in (versoes or {}).items() if list(feats) != inv['modelo']]
```

Em `src/ml/studio/api.py`, em `features_ajuste`, troque:

```python
      _ajustes[chave] = studio_features.ajuste(conj, inv, _versoes_por_nome(registro))
```

por:

```python
      _ajustes[chave] = studio_features.ajuste(conj, inv, _versoes_por_nome(registro), _denominadores(registro))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_studio_features.py" 2>&1 | tail -3`
Expected: `OK`

---

### Task 3: Nota aninhada do desenho com as regras de teto de WAN

`prever_fora_do_fold` tira do treino as linhas `_limitado_wan` e corta a previsão no teto de WAN do prédio de teste. `aninhada` não faz nenhum dos dois. Esta Task aplica as mesmas regras ao modelo final de cada prédio de teste. A busca gulosa (`gulosa`/`_pooled`) continua como está: ela só ordena candidatas.

**Files:**
- Modify: `src/ml/studio/selecao.py` (`aninhada`)
- Test: `tests/test_selecao.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_selecao.py`, troque os imports do topo:

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd
```

por:

```python
import os
import sys
import unittest
from unittest import mock

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
```

Na classe `TestSelecao`, depois de `test_aninhada_nunca_ve_o_local_de_teste`, acrescente:

```python
  def test_aninhada_segue_as_regras_de_teto_de_wan_da_regua(self):
    tamanhos = []

    class Grava(BaseEstimator, RegressorMixin):
      def fit(self, X, y):
        tamanhos.append(len(X))
        return self

      def predict(self, X):
        return np.full(len(X), 1000.0)

    f = frame()
    f['router_expected_throughput_mbps'] = 500.0
    residencia = f.index[f['local'].isin(['sala', 'quarto'])]
    # 150 >= 0,85 x 154 (teto de download da residência) e o Wi-Fi esperado (500) passa do teto.
    f.loc[residencia[:10], 'speedtest_down_mbps'] = 150.0
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(int(conj.df['_limitado_wan'].sum()), 10)
    with mock.patch.object(A, 'modelo_regua', lambda arvores=None: Grava()):
      r = S.aninhada(conj.df, ['router_snr'], 'speedtest_down_mbps')
    # Folds em ordem: coworking, hotmilk, residencia (60 linhas cada; 10 da residência no teto).
    self.assertEqual(tamanhos, [110, 110, 120])
    y = conj.df.loc[conj.df['_site'] == 'residencia', 'speedtest_down_mbps']
    self.assertAlmostEqual(r['mae_por_local']['residencia'], round(float((y - 154.0).abs().mean()), 4))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_selecao.py" 2>&1 | tail -3`
Expected: `FAILED (failures=1)`, com `[120, 120, 120] != [110, 110, 120]`.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/selecao.py`, troque o import:

```python
from ml.core.splits import assert_sites_disjoint
```

por:

```python
from ml.core.sites import teto_wan
from ml.core.splits import assert_sites_disjoint
```

Em `aninhada`, troque:

```python
    feats, _ = gulosa(treino, candidatas, alvo)
    escolhas[local] = feats
    X_tr, X_te = SF.matriz(treino, feats), SF.matriz(teste, feats)
    X_te = X_te.reindex(columns=X_tr.columns, fill_value=0.0)
    y_te = teste[alvo].astype(float)
    p = A.modelo_regua().fit(X_tr, treino[alvo].astype(float)).predict(X_te)
```

por:

```python
    feats, _ = gulosa(treino, candidatas, alvo)
    escolhas[local] = feats
    # Mesmas regras da régua (prever_fora_do_fold): linha no teto de WAN fora do treino
    # e previsão cortada no teto do prédio de teste. Sem isso, a diferença entre a nota
    # da seleção e a aninhada mistura otimismo de seleção com diferença de protocolo.
    com_teto = alvo in A.ALVOS_COM_TETO
    if com_teto and '_limitado_wan' in treino.columns:
      treino = treino[~treino['_limitado_wan'].astype(bool)]
    X_tr, X_te = SF.matriz(treino, feats), SF.matriz(teste, feats)
    X_te = X_te.reindex(columns=X_tr.columns, fill_value=0.0)
    y_te = teste[alvo].astype(float)
    p = A.modelo_regua().fit(X_tr, treino[alvo].astype(float)).predict(X_te)
    teto = teto_wan(local, alvo) if com_teto else None
    if teto is not None:
      p = np.minimum(p, teto)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_selecao.py" 2>&1 | tail -3`
Expected: `OK`

---

### Task 4: Cache do Studio inclui `aplicacoes.json`

**Files:**
- Modify: `src/ml/core/aplicacoes.py`
- Modify: `src/ml/studio/api.py` (`_chave_versoes`)
- Test: `tests/test_aplicacoes.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_aplicacoes.py`, troque os imports do topo:

```python
import os
import sys
import unittest
```

por:

```python
import os
import sys
import tempfile
import unittest
from unittest import mock
```

No fim da classe `TestAplicacoes` (antes do bloco `if __name__`), acrescente:

```python
  def test_versao_muda_com_o_conteudo(self):
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'aplicacoes.json')
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 1}')
      antes = AP.versao(path)
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 2}')
      self.assertNotEqual(antes, AP.versao(path))
      self.assertEqual(AP.versao(os.path.join(pasta, 'nao-existe.json')), 'ausente')

  def test_chave_de_cache_do_studio_inclui_as_aplicacoes(self):
    from ml.studio import api
    with mock.patch.object(AP, 'versao', return_value='x1'):
      antes = api._chave_versoes()
    with mock.patch.object(AP, 'versao', return_value='x2'):
      depois = api._chave_versoes()
    self.assertNotEqual(antes, depois)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_aplicacoes.py" 2>&1 | tail -3`
Expected: `FAILED (errors=2)`, com `AttributeError: ... has no attribute 'versao'`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/aplicacoes.py`, troque:

```python
import json
import os
```

por:

```python
import hashlib
import json
import os
```

E acrescente no fim do arquivo:

```python
def versao(path: str = None) -> str:
  """Hash curto do arquivo: entra na chave de cache do Studio, como as versões da tabela e do registro."""
  try:
    with open(path or APLICACOES_PATH, 'rb') as handle:
      return hashlib.sha256(handle.read()).hexdigest()[:12]
  except OSError:
    return 'ausente'
```

Em `src/ml/studio/api.py`, troque:

```python
def _chave_versoes():
  return (core_features.versao_tabela(), core_features.CATALOGO_VERSAO,
          core_features.versao_derivadas(), core_modelos.versao_registro())
```

por:

```python
def _chave_versoes():
  return (core_features.versao_tabela(), core_features.CATALOGO_VERSAO,
          core_features.versao_derivadas(), core_modelos.versao_registro(), core_aplicacoes.versao())
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_aplicacoes.py" 2>&1 | tail -3`
Expected: `OK`

---

### Task 5: Payload decide o prédio pelo `core/sites.py` e avisa de local desconhecido

**Files:**
- Modify: `src/ml/studio/data.py`
- Modify: `src/ml/studio/static/studio.js` (`renderGates`)
- Test: `tests/test_studio_features.py` (classe `TestDados`)

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_studio_features.py`, na classe `TestDados`, troque o teste inteiro:

```python
  def test_ambiente_do_studio_bate_com_o_core(self):
    for predio, meta in SD.BUILDINGS.items():
      for posicao in meta['positions']:
        core = resolve_site_id(pd.Series([posicao]), level='building').iloc[0]
        self.assertEqual(BUILDING_ENVIRONMENT[core], meta['ambiente'], f'{predio}/{posicao}')
```

por:

```python
  def test_ambiente_do_studio_bate_com_o_core(self):
    self.assertEqual(set(SD.PREDIO_DO_CORE), set(BUILDING_ENVIRONMENT))
    for core, studio in SD.PREDIO_DO_CORE.items():
      self.assertEqual(SD.BUILDINGS[studio]['ambiente'], BUILDING_ENVIRONMENT[core], core)

  def test_posicao_nova_segue_a_regra_do_core(self):
    self.assertEqual(SD._building_of('marcelo-garagem'), 'casa-marcelo')
    self.assertEqual(SD._building_of('hotmilk-recepcao'), 'hotmilk')
    self.assertEqual(SD._building_of(2.0), 'casa')
    with self.assertRaises(ValueError):
      SD._building_of('garagem-x')

  def test_local_desconhecido_vira_aviso_no_payload(self):
    linhas = pd.DataFrame({
      'local': ['marcelo-copa', 'garagem-x', 'garagem-x'],
      'speedtest_down_mbps': [50.0, 20.0, 10.0], 'speedtest_up_mbps': [10.0, 5.0, 5.0],
      'latency_ms': [10.0, 12.0, 12.0], 'jitter_ms': [1.0, 2.0, 2.0],
    })
    with tempfile.TemporaryDirectory() as dados, tempfile.TemporaryDirectory() as planta:
      linhas.to_csv(os.path.join(dados, 'm.csv'), index=False)
      antes = (C.DATA_DIR, SP.PLANTA_DIR)
      C.DATA_DIR, SP.PLANTA_DIR, C._descobertos = dados, planta, None
      try:
        payload = SD.build_payload()
      finally:
        (C.DATA_DIR, SP.PLANTA_DIR), C._descobertos = antes, None
    self.assertEqual(payload['locaisDesconhecidos'], [{'dataset': 'm.csv', 'valores': ['garagem-x'], 'linhas': 2}])
    self.assertEqual(len(payload['rows']), 1)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_features.py" 2>&1 | tail -3`
Expected: `FAILED (errors=3)`: `PREDIO_DO_CORE` não existe, `marcelo-garagem` não está em nenhum prédio de `BUILDINGS`, e `KeyError: 'locaisDesconhecidos'`.

- [ ] **Step 3: Implementar em `data.py`**

Em `src/ml/studio/data.py`, troque os imports:

```python
from collections import Counter

import pandas as pd

from ml.core import aplicacoes as core_aplicacoes
from ml.core.carga import TARGETS as _TARGETS
from ml.core.carga import _superseded, descobertos, discover, duplicatas
from ml.core.sites import CORPORATE, DOMESTIC
from ml.studio.plans import andar_de, montar_plantas
```

por:

```python
from collections import Counter
from functools import lru_cache

import pandas as pd

from ml.core import aplicacoes as core_aplicacoes
from ml.core.carga import TARGETS as _TARGETS
from ml.core.carga import _superseded, descobertos, discover, duplicatas
from ml.core.sites import CORPORATE, DOMESTIC, resolve_site_id
from ml.studio.plans import andar_de, montar_plantas
```

Troque o bloco `BUILDINGS` inteiro (do comentário `# O prefixo \`cwpb\` deixou de distinguir predio...` até o `}` que fecha o dicionário) por:

```python
# Rótulo e ambiente de cada prédio do Studio. Qual posição é de qual prédio é
# decidido só por core/sites.py (PREDIO_DO_CORE): assim o Studio e o treino nunca
# discordam, e uma posição nova não some do Studio sem aviso.
BUILDINGS = {
  'casa': {'label': 'Casa', 'ambiente': DOMESTIC},
  'cowork-pedra-branca': {'label': 'Cowork Pedra Branca', 'ambiente': CORPORATE},
  'hotmilk': {'label': 'Hotmilk', 'ambiente': CORPORATE},
  'casa-marcelo': {'label': 'Casa do Marcelo', 'ambiente': DOMESTIC},
}

# Prédio de core/sites.py -> chave do Studio (as chaves do Studio já estão em plantas.json).
PREDIO_DO_CORE = {
  'residencia': 'casa',
  'coworking': 'cowork-pedra-branca',
  'hotmilk': 'hotmilk',
  'casa-marcelo': 'casa-marcelo',
}
```

Troque a função `_building_of` inteira por:

```python
@lru_cache(maxsize=None)
def _building_de_texto(texto: str) -> str:
  return PREDIO_DO_CORE[resolve_site_id(pd.Series([texto]), level='building').iloc[0]]


def _building_of(local_value) -> str:
  """Prédio do Studio para um valor de `local`, pela regra de core/sites.py.

  Levanta ValueError para valor vazio ou que o core não conhece: nunca vira grupo próprio.
  """
  if pd.isna(local_value):
    raise ValueError('local vazio')
  return _building_de_texto(str(local_value))
```

Em `build_payload`, troque:

```python
  rows = []
  descriptors = []
```

por:

```python
  rows = []
  descriptors = []
  locais_desconhecidos = []
```

Logo depois, troque:

```python
    buildings = set()
    positions = set()
    for _, row in frame.iterrows():
      local = row['local']
      try:
        building = _building_of(local)
      except ValueError:
        continue
```

por:

```python
    buildings = set()
    positions = set()
    desconhecidos = Counter()
    for _, row in frame.iterrows():
      local = row['local']
      try:
        building = _building_of(local)
      except ValueError:
        desconhecidos[str(local)] += 1
        continue
```

Logo antes de `descriptors.append({` (o do dataset utilizável, com `'id': item['id'], 'rows': ...`), acrescente:

```python
    if desconhecidos:
      locais_desconhecidos.append({'dataset': item['id'], 'valores': sorted(desconhecidos),
                                   'linhas': int(sum(desconhecidos.values()))})
```

No `return` de `build_payload`, troque:

```python
    'plantasAvisos': plantas_avisos,
  }
```

por:

```python
    'plantasAvisos': plantas_avisos,
    'locaisDesconhecidos': locais_desconhecidos,
  }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_studio_features.py" 2>&1 | tail -3`
Expected: `OK`

Run: `grep -n "positions'\]\|\['positions" src/ml/studio/*.py`
Expected: nenhuma linha.

- [ ] **Step 5: Aviso no Studio**

Em `src/ml/studio/static/studio.js`, logo depois de `const $ = (s) => document.querySelector(s);`, acrescente:

```js
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
```

Em `renderGates`, dentro do `Object.entries(state.enabled).forEach(([id, on]) => {`, logo depois do bloco `if (d && d.supersededBy) { ... }`, acrescente:

```js
      const fora = (state.data.locaisDesconhecidos || []).find((x) => x.dataset === id);
      if (fora) {
        gates.push({ sev: 'warning', title: `${esc(id)}: ${fora.linhas} linhas com local desconhecido`,
          msg: `Ficam fora de todas as views e do treino: ${fora.valores.map(esc).join(', ')}.`,
          causes: ['Acrescente a regra da posição em src/ml/core/sites.py.'] });
      }
```

Run: `node --check src/ml/studio/static/studio.js && echo ok`
Expected: `ok`

- [ ] **Step 6: Nada mudou nos dados reais**

Run:

```bash
PYTHONPATH=src python3 -c "
from ml.studio import data as SD
p = SD.build_payload()
print(len(p['rows']), p['locaisDesconhecidos'])
from collections import Counter
print(Counter(r['b'] for r in p['rows']))
"
```

Expected: `locaisDesconhecidos` vazio (`[]`) e os quatro prédios do Studio na contagem. Se aparecer algum valor, ele estava sumindo do Studio antes desta Task: anote para o CHANGELOG.

---

### Task 6: Duplicatas com preferência explícita pela versão corrigida

**Files:**
- Modify: `src/ml/core/carga.py` (`duplicatas`)
- Test: `tests/test_carga.py` (classe `TestDescoberta`)

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`, na classe `TestDescoberta`, depois de `test_ids_padrao_exclui_legacy_duplicata_e_substituido`, acrescente:

```python
  def test_duplicata_prefere_a_versao_corrigida_e_depois_mais_colunas(self):
    datasets = [
      {'id': 'b.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', 'columns': 10},
      {'id': 'b_fix.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', 'columns': 10},
      {'id': 'c.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f2', 'columns': 10},
      {'id': 'c-extra.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f2', 'columns': 12},
    ]
    self.assertEqual(C.duplicatas(datasets), {'b.csv': 'b_fix.csv', 'c.csv': 'c-extra.csv'})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_carga.py" 2>&1 | tail -3`
Expected: `FAILED (failures=1)`: hoje sai `{'b_fix.csv': 'b.csv', 'c-extra.csv': 'c.csv'}`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/carga.py`, troque a função `duplicatas` inteira por:

```python
# Marcas no nome de uma versão corrigida do mesmo arquivo (20260917-metrics-fix,
# 20260921-metrics-distcalc). Entre datasets com os mesmos alvos, a corrigida fica.
MARCAS_CORRECAO = ('fix', 'distcalc')


def _preferencia(item) -> tuple:
  """Ordem entre datasets com os mesmos alvos: corrigido, depois mais colunas, depois o nome."""
  corrigido = any(m in item['id'].lower() for m in MARCAS_CORRECAO)
  return (not corrigido, -int(item.get('columns') or 0), item['id'])


def duplicatas(datasets: list) -> dict:
  """Fingerprint igual = os mesmos alvos até a 6a casa: só um do grupo fica.

  Fica a versão corrigida (MARCAS_CORRECAO no nome); empate vai para a de mais colunas,
  depois para o nome. A ordem alfabética sozinha escolhia certo por acaso ('-' vem antes de '.').
  Manter os dois ligados duplica o peso de cada amostra sem avisar.
  """
  grupos = {}
  for item in datasets:
    if item.get('usable'):
      grupos.setdefault(item['fingerprint'], []).append(item)
  duplicata_de = {}
  for itens in grupos.values():
    primeiro, *resto = sorted(itens, key=_preferencia)
    for item in resto:
      duplicata_de[item['id']] = primeiro['id']
  return duplicata_de
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_carga.py" 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 5: O conjunto canônico real não mudou**

Run: `PYTHONPATH=src python3 -c "from ml.core import carga as C; ds = C.descobertos(); print(C.ids_padrao(ds)); print(C.duplicatas(ds))"`
Expected: `['20260827-metrics.zip', '20260917-metrics-fix.zip', '20260921-metrics-distcalc.zip', '20260925-metrics.zip', '20260928-metrics.zip']`, e `20260917-metrics.zip` e `20260921-metrics.zip` como duplicatas das versões corrigidas. Se a lista for outra, pare e avise o usuário.

---

### Task 7: `veredito_promocao` sem intervalo não quebra

**Files:**
- Modify: `src/ml/core/avaliacao.py` (`veredito_promocao`)
- Test: `tests/test_avaliacao.py` (classe `TestPromocao`)

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_avaliacao.py`, na classe `TestPromocao`, depois de `test_latencia_decide_so_pelo_mae`, acrescente:

```python
  def test_atende_sem_intervalo_decide_pelo_mae(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), {'valor': 0.0, 'intervalo': None})
    self.assertEqual(v['resultado'], 'melhor')

  def test_mae_sem_intervalo_e_empate(self):
    v = A.veredito_promocao({'valor': -5.0, 'intervalo': None, 'mae_base': 40.0}, None)
    self.assertEqual(v['resultado'], 'empate')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_avaliacao.py" 2>&1 | tail -3`
Expected: `FAILED (errors=2)`, com `TypeError` (`'NoneType' object is not subscriptable` e `cannot unpack non-iterable NoneType object`).

- [ ] **Step 3: Implementar**

Em `src/ml/core/avaliacao.py`, em `veredito_promocao`, troque:

```python
  `delta_atende` é None em latência e jitter, que decidem só pelo MAE.
  """
  lo_m, hi_m = delta_mae['intervalo']
```

por:

```python
  `delta_atende` é None em latência e jitter, que decidem só pelo MAE. Um intervalo
  None (todas as reamostragens deram NaN) não decide: sem o do MAE, é empate; sem o
  do "atende", decide só o MAE.
  """
  if delta_mae.get('intervalo') is None:
    return {'resultado': 'empate', 'motivo': 'Sem intervalo para a diferença de MAE: não dá para '
                                             'separar as duas versões.'}
  if delta_atende is not None and delta_atende.get('intervalo') is None:
    delta_atende = None
  lo_m, hi_m = delta_mae['intervalo']
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_avaliacao.py" 2>&1 | tail -3`
Expected: `OK`

---

### Task 8: Diferença por prédio na promoção

O intervalo de 90% reamostra posições dentro de cada prédio, com os prédios fixos. Ele não mede a variação entre prédios, então um "melhor" pode vir com um prédio piorando. Esta Task não muda o veredito: acrescenta a diferença por prédio (`por_predio`) e a lista dos prédios em que a nova versão piora além do ruído (`predios_contra`). O Assistente mostra a lista e só libera a ativação sem prédio contra. Vale para download e upload; latência e jitter (`veredito_quantis`) ficam como estão.

**Files:**
- Modify: `src/ml/core/avaliacao.py` (`delta_mae`, `veredito_promocao`)
- Modify: `src/ml/core/limiar.py` (`delta_decisoes`)
- Modify: `src/ml/studio/static/assistente.js` (`cartaoVeredito`, `passoPublicar`)
- Test: `tests/test_avaliacao.py`, `tests/test_limiar.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_avaliacao.py`, na classe `TestPromocao`, depois de `test_mae_sem_intervalo_e_empate`, acrescente:

```python
  def test_delta_mae_traz_a_diferenca_por_predio(self):
    self.assertEqual(A.delta_mae(self.nova, self.base)['por_predio'], {'s1': -10.0, 's2': -10.0})

  def test_veredito_lista_predio_em_que_o_mae_piora(self):
    d_mae = dict(delta(-5.0, -8.0, -2.0, 40.0), por_predio={'a': -9.0, 'b': 1.0})
    v = A.veredito_promocao(d_mae, None)
    self.assertEqual((v['resultado'], v['predios_contra']), ('melhor', ['b']))

  def test_piora_dentro_do_ruido_nao_conta(self):
    d_mae = dict(delta(-5.0, -8.0, -2.0, 40.0), por_predio={'a': -9.0, 'b': 0.5})
    self.assertEqual(A.veredito_promocao(d_mae, None)['predios_contra'], [])

  def test_veredito_lista_predio_em_que_o_atende_cai(self):
    d_mae = dict(delta(-5.0, -8.0, -2.0, 40.0), por_predio={'a': -9.0, 'b': -1.0})
    d_atende = dict(delta(0.0, -0.01, 0.01), por_predio={'a': 0.05, 'b': -0.03})
    self.assertEqual(A.veredito_promocao(d_mae, d_atende)['predios_contra'], ['b'])
```

(O limite do MAE é `RUIDO_MAE_REL × mae_base` = 0,02 × 40 = 0,8: 1,0 conta, 0,5 não.)

Em `tests/test_limiar.py`, antes do bloco `if __name__`, acrescente:

```python
class TestDeltaPorPredio(unittest.TestCase):
  def test_delta_decisoes_traz_a_diferenca_por_predio(self):
    def decisoes(previsto):
      return {'App': pd.DataFrame({'_linha': [f'a:{i}' for i in range(5)], '_site': ['s1', 's1', 's2', 's2', 's2'],
                                   '_pos': [f'p{i}' for i in range(5)], 'real': [True, False, True, False, True],
                                   'previsto': previsto, 'fator': 1.0})}
    # s1: nova acerta tudo (1,0), base diz "atende" para todos (0,5). s2: o contrário.
    d = L.delta_decisoes(decisoes([True, False, True, True, True]), decisoes([True, True, True, False, True]))
    self.assertEqual(d['por_predio'], {'s1': 0.5, 's2': -0.5})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_avaliacao.py" 2>&1 | tail -3`
Expected: `FAILED`, com `KeyError: 'por_predio'` e `KeyError: 'predios_contra'`.

Run: `python3 -m unittest discover -s tests -p "test_limiar.py" 2>&1 | tail -3`
Expected: `FAILED (errors=1)`, com `KeyError: 'por_predio'`.

- [ ] **Step 3: `por_predio` em `avaliacao.py`**

Em `src/ml/core/avaliacao.py`, logo antes de `def delta_mae(`, acrescente:

```python
def _por_predio(sites, diferenca) -> dict:
  """`diferenca(idx)` só com as linhas de cada prédio (índices posicionais); NaN vira None."""
  sites = np.asarray(sites).astype(str)
  saida = {}
  for site in sorted(set(sites)):
    valor = float(diferenca(np.flatnonzero(sites == site)))
    saida[site] = None if np.isnan(valor) else round(valor, 4)
  return saida
```

Em `delta_mae`, troque:

```python
  return {'valor': round(float(erro_nova.mean() - erro_base.mean()), 4),
          'intervalo': _intervalo([erro_nova[i].mean() - erro_base[i].mean() for i in amostras]),
          'mae_base': round(float(erro_base.mean()), 4), 'n': int(len(j))}
```

por:

```python
  return {'valor': round(float(erro_nova.mean() - erro_base.mean()), 4),
          'intervalo': _intervalo([erro_nova[i].mean() - erro_base[i].mean() for i in amostras]),
          'mae_base': round(float(erro_base.mean()), 4), 'n': int(len(j)),
          'por_predio': _por_predio(j['_site'], lambda i: erro_nova[i].mean() - erro_base[i].mean())}
```

- [ ] **Step 4: `predios_contra` em `veredito_promocao`**

Ainda em `avaliacao.py`, renomeie `def veredito_promocao(delta_mae: dict, delta_atende: dict = None) -> dict:` para `def _veredito_promocao(delta_mae: dict, delta_atende: dict = None) -> dict:` (o corpo, com a guarda da Task 7, fica igual). Logo depois do fim dessa função, acrescente:

```python
def _predios_contra(delta_mae: dict, delta_atende: dict = None) -> list:
  """Prédios em que a nova versão piora além do ruído: MAE acima de RUIDO_MAE_REL do MAE da
  base, ou acurácia de "atende" abaixo de -RUIDO_ATENDE."""
  limite = RUIDO_MAE_REL * delta_mae.get('mae_base', 0.0)
  contra = {s for s, v in (delta_mae.get('por_predio') or {}).items() if v is not None and v > limite}
  if delta_atende is not None:
    contra |= {s for s, v in (delta_atende.get('por_predio') or {}).items() if v is not None and v < -RUIDO_ATENDE}
  return sorted(contra)


def veredito_promocao(delta_mae: dict, delta_atende: dict = None) -> dict:
  """Melhor / empate / pior pela régua de promoção (nova − base, intervalo de 90%), mais
  `predios_contra`.

  O intervalo reamostra posições com os prédios fixos: não mede a variação entre prédios.
  `predios_contra` mostra onde a nova versão piora, mesmo quando o resultado é "melhor".
  """
  saida = _veredito_promocao(delta_mae, delta_atende)
  saida['predios_contra'] = _predios_contra(delta_mae, delta_atende)
  return saida
```

- [ ] **Step 5: `por_predio` em `limiar.py`**

Em `src/ml/core/limiar.py`, troque o import:

```python
from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, _media_sem_nan,
                               _resumo_atende, prever_fora_do_fold, reamostras)
```

por:

```python
from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, _media_sem_nan,
                               _por_predio, _resumo_atende, prever_fora_do_fold, reamostras)
```

Em `delta_decisoes`, troque:

```python
  return {'valor': round(diferenca(np.arange(len(j))), 4), 'intervalo': _intervalo([diferenca(i) for i in amostras]),
          'n': int(len(j)), 'ajustado': True}
```

por:

```python
  return {'valor': round(diferenca(np.arange(len(j))), 4), 'intervalo': _intervalo([diferenca(i) for i in amostras]),
          'n': int(len(j)), 'ajustado': True, 'por_predio': _por_predio(j['_site'], diferenca)}
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_avaliacao.py" 2>&1 | tail -3 && python3 -m unittest discover -s tests -p "test_limiar.py" 2>&1 | tail -3`
Expected: `OK` nas duas.

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
Expected: `OK` (a rota `/api/modelos/avaliar` agora devolve `predios_contra` no veredito da promoção).

- [ ] **Step 7: Mostrar no Assistente e travar a ativação**

Em `src/ml/studio/static/assistente.js`, em `cartaoVeredito`, troque:

```js
          <div class="gate-msg">${detalhePromocao}</div></div></div>` : '';
```

por:

```js
          <div class="gate-msg">${detalhePromocao}</div>
          ${(p.veredito.predios_contra || []).length ? `<div class="gate-msg">Piora em: ${esc(p.veredito.predios_contra.join(', '))}</div>` : ''}</div></div>` : '';
```

Em `passoPublicar`, troque (texto criado na Task 1):

```js
    const melhor = atual && promocaoDe(st.aval).resultado === 'melhor';
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? '' : 'A régua de promoção não diz "melhor": para ativar mesmo assim, use o modo Avançado.';
```

por:

```js
    const contra = atual ? (promocaoDe(st.aval).predios_contra || []) : [];
    const melhor = atual && promocaoDe(st.aval).resultado === 'melhor' && !contra.length;
    const trava = !atual ? 'Teste o rascunho atual no passo 3 para liberar a ativação.'
      : melhor ? ''
      : contra.length ? `A régua diz "melhor", mas piora em ${contra.join(', ')}: para ativar mesmo assim, use o modo Avançado.`
      : 'A régua de promoção não diz "melhor": para ativar mesmo assim, use o modo Avançado.';
```

O texto da trava entra em `<span class="gate-msg">${trava}</span>` sem escape; os nomes de prédio vêm de `core/sites.py` (`residencia`, `coworking`, `hotmilk`, `casa-marcelo`), não de dado digitado.

Run: `node --check src/ml/studio/static/assistente.js && echo ok`
Expected: `ok`

---

### Task 9: Contrato de entrada e fatores do "atende" no MLflow

`matriz` transforma categóricas em one-hot com as categorias presentes nos dados. O modelo final aprende colunas como `radio_5ghz` e `client_mode_WiFi 5 (11ac)`. Uma linha de produção sozinha gera só as colunas dos valores dela, e o ACS manda `5GHz`, não `5ghz`. Esta Task grava no run o contrato (as colunas exatas e as categorias de treino) e oferece uma função que refaz a matriz de uma linha de produção a partir dele. Também grava os fatores do "atende ajustado" (`fatores_producao`), que hoje só vão para `modelos.json` pelo Studio.

**Files:**
- Create: `src/ml/core/producao.py`
- Modify: `src/ml/regression_mlflow.py`
- Test: `tests/test_producao.py`

- [ ] **Step 1: Escrever o teste que falha**

Crie `tests/test_producao.py`:

```python
import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F
from ml.core import producao as P

FEATURES = ['router_snr', 'radio', 'client_mode']


class TestContrato(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({'router_snr': [10.0, 20.0, 30.0], 'radio': ['2.4ghz', '5ghz', '5ghz'],
                            'client_mode': ['WiFi 4 (11n)', 'WiFi 5 (11ac)', None]})
    self.contrato = P.contrato(self.df, FEATURES)

  def test_guarda_as_colunas_da_matriz_e_as_categorias(self):
    self.assertEqual(self.contrato['colunas'], ['router_snr', 'radio_2.4ghz', 'radio_5ghz',
                                                'client_mode_WiFi 4 (11n)', 'client_mode_WiFi 5 (11ac)'])
    self.assertEqual(self.contrato['categorias'], {'radio': ['2.4ghz', '5ghz'],
                                                   'client_mode': ['WiFi 4 (11n)', 'WiFi 5 (11ac)']})
    self.assertEqual(self.contrato['features'], FEATURES)

  def test_a_matriz_do_treino_e_reproduzida(self):
    X, avisos = P.preparar_entrada(self.df, self.contrato)
    pd.testing.assert_frame_equal(X, F.matriz(self.df, FEATURES))
    self.assertEqual(avisos, [])

  def test_uma_linha_do_acs_vira_as_mesmas_colunas(self):
    linha = pd.DataFrame({'router_snr': [25.0], 'radio': ['5GHz'], 'client_mode': ['WiFi 5 (11ac)']})
    X, avisos = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(list(X.columns), self.contrato['colunas'])
    self.assertEqual(X.iloc[0].tolist(), [25.0, 0.0, 1.0, 0.0, 1.0])
    self.assertEqual(avisos, [])

  def test_categoria_que_o_treino_nao_viu_vira_zeros_e_avisa(self):
    linha = pd.DataFrame({'router_snr': [25.0], 'radio': ['6GHz'], 'client_mode': ['WiFi 5 (11ac)']})
    X, avisos = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(X[['radio_2.4ghz', 'radio_5ghz']].iloc[0].tolist(), [0.0, 0.0])
    self.assertEqual(len(avisos), 1)
    self.assertIn('6GHz', avisos[0])

  def test_numero_que_chega_como_texto_continua_numero(self):
    linha = pd.DataFrame({'router_snr': ['12.5'], 'radio': ['5ghz'], 'client_mode': [None]})
    X, _ = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(X['router_snr'].iloc[0], 12.5)
    self.assertEqual(list(X.columns), self.contrato['colunas'])

  def test_feature_faltando_levanta(self):
    with self.assertRaisesRegex(ValueError, 'client_mode'):
      P.preparar_entrada(pd.DataFrame({'router_snr': [1.0], 'radio': ['5ghz']}), self.contrato)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_producao.py" 2>&1 | tail -3`
Expected: `ImportError` / `ModuleNotFoundError: No module named 'ml.core.producao'`.

- [ ] **Step 3: Criar `src/ml/core/producao.py`**

```python
"""Contrato de entrada do modelo em produção: as colunas exatas que o modelo final viu.

O treino monta a matriz com features.matriz, que transforma categóricas em one-hot com as
categorias presentes nos dados. Em produção chega uma linha por vez, com a grafia do ACS
('5GHz' no lugar de '5ghz'): as colunas precisam vir do contrato, não da linha.
"""

import pandas as pd

from ml.core.features import matriz


def _categorica(serie: pd.Series) -> bool:
  return not pd.api.types.is_numeric_dtype(serie)


def contrato(df: pd.DataFrame, features) -> dict:
  """Features, colunas da matriz de treino (na ordem) e categorias vistas de cada categórica."""
  features = list(features)
  categorias = {f: sorted(df[f].dropna().astype(str).unique()) for f in features if _categorica(df[f])}
  return {'features': features, 'colunas': list(matriz(df, features).columns), 'categorias': categorias,
          'uso': 'X = producao.preparar_entrada(linhas, contrato)[0]; modelo.predict(X)'}


def _casar(valor, conhecidas: list):
  """O valor como o treino o viu: igual, ou igual sem diferença de maiúsculas e espaços.

  None quando não há uma correspondência só (categoria que o treino não viu).
  """
  if pd.isna(valor):
    return None
  texto = str(valor).strip()
  if texto in conhecidas:
    return texto
  iguais = [c for c in conhecidas if c.lower() == texto.lower()]
  return iguais[0] if len(iguais) == 1 else None


def preparar_entrada(df: pd.DataFrame, contrato: dict):
  """Matriz de produção com as colunas do contrato, na mesma ordem. Devolve (X, avisos).

  Categoria que o treino não viu vira zero em todas as colunas dela, com aviso. Feature
  numérica que chega como texto é convertida (texto inválido vira NaN, que o imputer trata).
  """
  faltam = [f for f in contrato['features'] if f not in df.columns]
  if faltam:
    raise ValueError(f'features do contrato ausentes na entrada: {faltam}')
  df = df[contrato['features']].copy()
  avisos = []
  for f in contrato['features']:
    if f in contrato['categorias']:
      conhecidas = contrato['categorias'][f]
      casados = df[f].map(lambda v: _casar(v, conhecidas))
      fora = sorted({str(v) for v, c in zip(df[f], casados) if not pd.isna(v) and c is None})
      if fora:
        avisos.append(f'{f}: valores que o treino não viu {fora}; viram zero em todas as colunas de {f}')
      df[f] = casados.astype(object)
    else:
      df[f] = pd.to_numeric(df[f], errors='coerce').astype(float)
  X = matriz(df, contrato['features']).reindex(columns=contrato['colunas'], fill_value=0.0)
  return X, avisos
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_producao.py" 2>&1 | tail -3`
Expected: `OK`

Se `test_a_matriz_do_treino_e_reproduzida` falhar só por dtype de coluna, confira se a coluna numérica saiu `float64` nos dois lados. Não afrouxe o teste.

- [ ] **Step 5: Registrar contrato e fatores em `regression_mlflow.py`**

Em `src/ml/regression_mlflow.py`, troque os imports do `ml.core`:

```python
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core import quantis as core_quantis
from ml.core.data import validate_columns
```

por:

```python
from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import limiar as core_limiar
from ml.core import modelos as core_modelos
from ml.core import producao as core_producao
from ml.core import quantis as core_quantis
from ml.core.data import validate_columns
```

Na docstring do módulo, acrescente ao fim (antes do `"""` de fechamento):

```
Todo run grava contrato.json (core/producao.py: as colunas exatas que o modelo final viu). Download
e upload gravam também fatores_atende.json, o fator de decisão do "atende" por aplicação (core/limiar.py).
```

Logo antes de `def main():`, acrescente:

```python
def fatores_atende(registro: dict, nome_modelo: str, conj, ids, features) -> dict:
  """Fator de decisão do "atende" por aplicação (core/limiar.py), para a produção usar com este modelo.

  Precisa das previsões de download e upload: carrega o outro alvo com os mesmos datasets.
  Os fatores vêm do modelo da régua (LOGO com todos os prédios), não da configuração da varredura.
  """
  outro = 'speedtest_up_mbps' if conj.alvo == 'speedtest_down_mbps' else 'speedtest_down_mbps'
  conj_outro = core_carga.carregar(outro, ids=ids)
  dn, up = (conj, conj_outro) if conj.alvo == 'speedtest_down_mbps' else (conj_outro, conj)
  aplicacoes = core_aplicacoes.carregar()
  fatores = core_limiar.fatores_producao(dn, up, features, aplicacoes,
                                         core_modelos.denominador_de(registro, nome_modelo, dn.alvo),
                                         core_modelos.denominador_de(registro, nome_modelo, up.alvo))
  return {'fatores': fatores, 'aplicacoes': aplicacoes, 'versao_regua': core_avaliacao.VERSAO_REGUA,
          'uso': 'atende = previsao_download >= k * dn e previsao_upload >= k * up, k = fatores[aplicação]',
          'origem': 'LOGO com todos os prédios, modelo da régua (core/avaliacao.modelo_regua)'}
```

Em `treinar_quantis`, troque:

```python
    for q in core_quantis.QUANTIS:
      modelo = core_quantis.modelo_quantil(q).fit(X, y_log)
      mlflow.sklearn.log_model(sk_model=modelo, name=f'quantil_{core_quantis.coluna(q)}',
                               serialization_format='skops')
```

por:

```python
    for q in core_quantis.QUANTIS:
      modelo = core_quantis.modelo_quantil(q).fit(X, y_log)
      mlflow.sklearn.log_model(sk_model=modelo, name=f'quantil_{core_quantis.coluna(q)}',
                               serialization_format='skops')
    mlflow.log_dict(core_producao.contrato(conj.df, features), 'contrato.json')
```

Em `main`, troque:

```python
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
```

por:

```python
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  contrato = core_producao.contrato(conj.df[treino], features)
  fatores = fatores_atende(registro, nome_modelo, conj, ids, features)
  print(f"Fatores do atende (produção): {fatores['fatores']}")
```

E, dentro do `for config in CONFIGS:`, troque:

```python
      if eficiencia:
        mlflow.log_dict(eficiencia, 'eficiencia.json')
        mlflow.log_metric('den_imputados', resumo['den_imputados'])
```

por:

```python
      mlflow.log_dict(contrato, 'contrato.json')
      mlflow.log_dict(fatores, 'fatores_atende.json')
      if eficiencia:
        mlflow.log_dict(eficiencia, 'eficiencia.json')
        mlflow.log_metric('den_imputados', resumo['den_imputados'])
```

- [ ] **Step 6: Conferir que o script ainda importa**

Run: `PYTHONPATH=src python3 -c "import importlib.util as u; s = u.spec_from_file_location('r', 'src/ml/regression_mlflow.py'); m = u.module_from_spec(s); s.loader.exec_module(m); print(m.fatores_atende.__name__)"`
Expected: `fatores_atende`

A rodada de verdade, com MLflow num banco temporário, fica na Task 13.

---

### Task 10: `regression_benchmark.py` com o denominador da versão

**Files:**
- Modify: `src/ml/regression_benchmark.py`

Sem teste automático: o script não tem suíte e roda 5 modelos grandes. A verificação é a rodada do Step 4.

- [ ] **Step 1: Argumento `--modelo`**

Em `parse_args`, logo depois do argumento `--features`, acrescente:

```python
  parser.add_argument('--modelo', default='',
                      help='Versão de core/modelos.json (padrão: a ativa). Sem --features nem --use-stats, '
                           'usa as features e o denominador dela.')
```

- [ ] **Step 2: `evaluate_target` recebe o denominador**

Troque:

```python
def evaluate_target(conj, features, models, shap_config=None):
  """Avalia cada modelo pela régua (LOGO por prédio, teto de WAN, intervalos)."""
```

por:

```python
def evaluate_target(conj, features, models, shap_config=None, denominador=None):
  """Avalia cada modelo pela régua (LOGO por prédio, teto de WAN, intervalos).

  `denominador` é o da versão para este alvo (ver core/avaliacao.prever_fora_do_fold).
  """
```

E troque:

```python
    prev = core_avaliacao.prever_fora_do_fold(conj.df, features, target, vazadas, estimador=model,
                                              ao_ajustar=explicar)
```

por:

```python
    prev = core_avaliacao.prever_fora_do_fold(conj.df, features, target, vazadas, estimador=model,
                                              ao_ajustar=explicar, denominador=denominador)
```

- [ ] **Step 3: `main` lê a versão**

Em `main`, troque:

```python
  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  elif args.features:
    features = parse_csv_list(args.features)
  else:
    features = core_modelos.ativo(core_modelos.carregar())
```

por:

```python
  registro = core_modelos.carregar()
  nome = args.modelo or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'--modelo {nome!r} não existe; versões: {sorted(registro["versoes"])}')
  denominadores = {}
  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  elif args.features:
    features = parse_csv_list(args.features)
  else:
    features = list(registro['versoes'][nome]['features'])
    denominadores = registro['versoes'][nome].get('denominador') or {}
    print(f'Versão {nome}' + (f'; denominador {denominadores}' if denominadores else ''))
```

Logo depois do bloco `if args.shap: ... elif ...:` (antes de `print(f'Features ({len(features)}): {features}')`), acrescente:

```python
  if shap_config is not None and any(isinstance(d, dict) for d in denominadores.values()):
    # Com denominador por banda, cada fold ajusta dois modelos (eficiência e absoluto) em escalas
    # diferentes; o beeswarm juntaria as duas.
    raise SystemExit('--shap não funciona com denominador por banda: use --features para explicar a versão')
```

E troque:

```python
    results, shap_ranking = evaluate_target(conj, features, models, shap_config)
```

por:

```python
    results, shap_ranking = evaluate_target(conj, features, models, shap_config, denominadores.get(target))
```

- [ ] **Step 4: Rodar**

Run: `timeout 3600 python3 src/ml/regression_benchmark.py --modelo v5-tr069 --targets speedtest_down_mbps 2>&1 | grep -v "Warning\|warnings.warn\|validate_site" | tail -25`
Expected: a linha `Versão v5-tr069; denominador {...}`, uma linha `R² pooled` por modelo e as tabelas por prédio, sem traceback. O `rf` deve ficar perto do R² pooled da `v5-tr069` no CHANGELOG (régua `2026-10-07.1`), sem ser igual: são 600 árvores, a régua usa 200. Anote os números para o CHANGELOG.

---

### Task 11: Studio aceita POST só da própria máquina, por Host e Origin

`_so_local` olha o IP do cliente. Uma página aberta no navegador da máquina também chega de 127.0.0.1. As rotas de job (`/api/modelos/desenhar`, `/api/paralelos`, `/api/assistente/sugestoes`) não têm corpo JSON, então não passam por preflight de CORS. Com DNS rebinding, até as rotas com JSON passam. Esta Task exige, em todo POST, `Host` de loopback e `Origin` ausente ou de loopback. GET continua livre: quem sobe com `--host 0.0.0.0` ainda vê o Studio de outra máquina, mas não grava nem dispara jobs.

**Files:**
- Modify: `src/ml/studio/api.py`
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_assistente.py`, antes do bloco `if __name__`, acrescente:

```python
class TestPostSoLocal(unittest.TestCase):
  def test_loopback_passa(self):
    self.assertTrue(api._post_permitido('127.0.0.1:8100', None))
    self.assertTrue(api._post_permitido('localhost:8100', 'http://localhost:8100'))
    self.assertTrue(api._post_permitido('[::1]:8100', None))

  def test_dns_rebinding_e_barrado_pelo_host(self):
    self.assertFalse(api._post_permitido('evil.example:8100', None))
    self.assertFalse(api._post_permitido('evil.example:8100', 'http://evil.example:8100'))

  def test_pagina_de_outra_origem_e_barrada(self):
    self.assertFalse(api._post_permitido('127.0.0.1:8100', 'http://evil.example'))
    self.assertFalse(api._post_permitido('127.0.0.1:8100', 'null'))

  def test_sem_host_e_barrado(self):
    self.assertFalse(api._post_permitido(None, None))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
Expected: `FAILED (errors=4)`, com `AttributeError: module 'ml.studio.api' has no attribute '_post_permitido'`.

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`, troque:

```python
import os
import threading
import uuid
from datetime import date
from typing import Optional
```

por:

```python
import os
import threading
import uuid
from datetime import date
from typing import Optional
from urllib.parse import urlsplit
```

Logo depois de `app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)`, acrescente:

```python
def _post_permitido(host: Optional[str], origin: Optional[str]) -> bool:
  """POST só com Host de loopback (contra DNS rebinding) e Origin ausente ou de loopback (contra
  uma página de outro site aberta no navegador desta máquina)."""
  if not host or urlsplit('//' + host).hostname not in LOOPBACK:
    return False
  return origin is None or urlsplit(origin).hostname in LOOPBACK


@app.middleware('http')
async def _so_post_local(request: Request, call_next):
  if request.method == 'POST' and not _post_permitido(request.headers.get('host'),
                                                      request.headers.get('origin')):
    return JSONResponse({'detail': 'POST só a partir da própria máquina (Host e Origin de loopback)'},
                        status_code=403)
  return await call_next(request)
```

(`urlsplit('null').hostname` é `None`, que não está em `LOOPBACK`: Origin `null` é barrado.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -p "test_studio_assistente.py" 2>&1 | tail -3`
Expected: `OK`

O teste de ponta a ponta, com `curl` no servidor de verdade, fica na Task 13.

---

### Task 12: Aposentar `classifier_mlflow.py`

**Files:**
- Move: `src/ml/classifier_mlflow.py` → `src/ml/experimental/classifier_mlflow.py`
- Modify: `src/ml/experimental/README.md`

- [ ] **Step 1: Mover (sem git)**

Run: `mv src/ml/classifier_mlflow.py src/ml/experimental/classifier_mlflow.py && ls src/ml/experimental/`
Expected: `README.md  classifier_keras.py  classifier_mlflow.py  regression_keras.py`

- [ ] **Step 2: Registrar os defeitos**

Em `src/ml/experimental/README.md`, logo depois do item de `classifier_keras.py`, acrescente:

```markdown
- `classifier_mlflow.py` — moved here on 2026-10-09. Reads `data/metrics-20260630-qoe.csv` (old schema
  generation, outside the canonical loader), classifies `qoe_dw_score` (formula lost, see
  `core/carga.py:discover`), uses a random split, and trains on the speedtest-window counters marked as
  leakage in `column_provenance.json`. Its scores do not measure anything the régua measures.
```

E troque a última linha:

```markdown
Use `src/ml/regression_benchmark.py` or `src/ml/classification_benchmark.py` instead.
```

por:

```markdown
Use `src/ml/regression_mlflow.py`, `src/ml/regression_benchmark.py` or `src/ml/classification_benchmark.py` instead.
```

- [ ] **Step 3: Nada importa o script**

Run: `grep -rn "classifier_mlflow" src tests --include=*.py`
Expected: nenhuma linha.

---

### Task 13: Verificação final e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Suíte completa**

Run: `python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 439 tests` (415 + 24 novos: Task 2: 1, Task 3: 1, Task 4: 2, Task 5: 2 líquidos, Task 6: 1, Task 7: 2, Task 8: 5, Task 9: 6, Task 11: 4), `OK`. Se a contagem for outra, confira se todos os testes deste plano entraram; não ajuste o número sem saber por quê.

- [ ] **Step 2: MLflow num banco temporário**

Run:

```bash
D=$(mktemp -d)
MLFLOW_TRACKING_URI="sqlite:///$D/mlflow.db" MODELO=v5-tr069 ALVO=speedtest_down_mbps \
  timeout 3600 python3 src/ml/regression_mlflow.py 2>&1 | grep -v "Warning\|warnings.warn\|validate_site" | tail -20
MLFLOW_TRACKING_URI="sqlite:///$D/mlflow.db" python3 - <<'EOF'
import json
import mlflow
c = mlflow.MlflowClient()
exp = c.get_experiment_by_name('MLflow Wifi Regressions')
run = c.search_runs([exp.experiment_id], order_by=['attributes.start_time DESC'], max_results=1)[0]
print(sorted(a.path for a in c.list_artifacts(run.info.run_id)))
contrato = json.loads(open(c.download_artifacts(run.info.run_id, 'contrato.json')).read())
print(contrato['categorias'])
print(len(contrato['colunas']), contrato['colunas'][:6])
print(json.loads(open(c.download_artifacts(run.info.run_id, 'fatores_atende.json')).read())['fatores'])
EOF
echo "banco temporário: $D"
```

Expected: a linha `Fatores do atende (produção): {...}` no treino. Na lista de artefatos: `contrato.json`, `eficiencia.json`, `fatores_atende.json` e os dois modelos (`..._eficiencia` e `..._absoluto`). `categorias` com `radio` (`['2.4ghz', '5ghz']`) e `client_mode`. Os fatores devem bater com a linha `v5-tr069` da tabela "Fatores de produção" do CHANGELOG de 2026-10-08 (Navegação 6,1688; Chamada de vídeo 3,3636; Streaming 4K 1,834; Jogo em nuvem 2,3784). Se não baterem, pare e avise o usuário. Com backend sqlite, os artefatos vão para `./mlruns`, que está no `.gitignore`.

- [ ] **Step 3: Studio no ar: rotas e Host/Origin**

Run:

```bash
python3 src/ml/studio.py --port 8123 > /tmp/qoe-studio-check.log 2>&1 &
PID=$!
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:8123/api/modelos && break; sleep 1; done
curl -s http://127.0.0.1:8123/api/payload | python3 -c "import json,sys; p=json.load(sys.stdin); print(len(p['rows']), p['locaisDesconhecidos'])"
B='{"receita":"razao","colunas":["router_tx_rate_mbps","router_rx_rate_mbps"]}'
curl -s -o /dev/null -w 'local %{http_code}\n' -X POST -H 'Content-Type: application/json' -d "$B" http://127.0.0.1:8123/api/receitas/montar
curl -s -o /dev/null -w 'host %{http_code}\n' -X POST -H 'Host: evil.example:8123' -H 'Content-Type: application/json' -d "$B" http://127.0.0.1:8123/api/receitas/montar
curl -s -o /dev/null -w 'origin %{http_code}\n' -X POST -H 'Origin: http://evil.example' -H 'Content-Type: application/json' -d "$B" http://127.0.0.1:8123/api/receitas/montar
curl -s -o /dev/null -w 'get %{http_code}\n' -H 'Host: evil.example:8123' http://127.0.0.1:8123/api/modelos
kill $PID
```

Expected: `locaisDesconhecidos` `[]`; `local 200`, `host 403`, `origin 403`, `get 200`.

- [ ] **Step 4: Studio no navegador**

O Studio nunca foi conferido num navegador (registro de 2026-10-07). Suba com `python3 src/ml/studio.py` e abra `http://127.0.0.1:8100` (ou use a skill `run`). Confira e anote:

1. **Modelo (Assistente):** monte um rascunho a partir da ativa, clique em Testar. O cartão mostra o veredito antigo e "Régua de promoção: ...". Se houver prédio contra, aparece "Piora em: ...". O botão "Salvar e tornar ativa" só habilita com a régua dizendo "melhor" e sem prédio contra; o texto da trava cita a régua. **Não clique em salvar**: isso grava `modelos.json`.
2. **Ver nos outros alvos:** a linha diz "pela régua de promoção".
3. **Features:** com o alvo download, as versões `v4-tr069` e `v5-tr069` aparecem com os mesmos R² pooled e MAE da view Modelos (Task 2).
4. **Topo:** com o conjunto padrão, nenhum aviso de local desconhecido.
5. **Console do navegador:** sem erro de JS.

Se algo divergir, pare e descreva o que viu ao usuário antes de corrigir.

- [ ] **Step 5: CHANGELOG**

No topo de `CHANGELOG.md`, no estilo das entradas existentes (título `# Changelog — ...`, `**Data:** 2026-10-09`, seções `## Por quê`, `## Mudanças`, `## Efeito medido`, `## Ressalvas`, separador `---`). Use só números impressos nos Steps 2 a 4 desta Task e no Step 4 da Task 10:

- **Por quê:** a revisão de 2026-10-09 achou a ativação no Assistente decidida pelo veredito antigo de R², o MLflow sem o que a produção precisa (colunas da matriz e fatores do "atende"), números diferentes para a mesma versão entre as views Features e Modelos e entre a nota da seleção e a aninhada, posições que somem do Studio sem aviso, a escolha entre duplicatas por ordem alfabética e POST aceito de outra origem.
- **Mudanças:** uma linha por Task, de 1 a 12.
- **Efeito medido:** artefatos e fatores do run de teste (Step 2), a rodada do benchmark com a `v5-tr069` (Task 10), `locaisDesconhecidos` com os dados reais (Task 5, Step 6), o resultado dos `curl` (Step 3).
- **Ressalvas:** a régua (`VERSAO_REGUA`) não mudou e nenhuma avaliação salva ficou desatualizada; `predios_contra` não muda o veredito, só a trava do Assistente; o intervalo continua reamostrando posições com os prédios fixos; o modo Avançado continua ativando sem trava; quem sobe o Studio com `--host 0.0.0.0` não grava nem dispara jobs de outra máquina; as decisões da seção "Decisões que ficam com você" do plano continuam abertas.

- [ ] **Step 6: Conferir**

Run: `sed -n 1,80p CHANGELOG.md | grep -n "TBD\|TODO\|<preencher"`
Expected: nenhuma linha.

Run: `git status --short`
Expected: os arquivos do Mapa de arquivos, mais `src/ml/classifier_mlflow.py` como apagado e `src/ml/experimental/classifier_mlflow.py` como novo. Nada em `data/`. Avise o usuário para revisar o diff e fazer o commit.
