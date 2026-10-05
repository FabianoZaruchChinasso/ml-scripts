# Contadores do roteador como vazamento e limpeza do registro (design)

**Data:** 2026-10-02
**Base:** `qoe-studio-features-planta` (commit `7c1f154`).
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

Os contadores de volume do roteador medem a janela do próprio speedtest. Hoje o catálogo de derivadas e o registro de versões aceitam features que carregam o alvo, e testes que falharam entram no treino. Esta entrega limpa essa base. A versão nova do modelo vem depois, montada no assistente do Studio sobre a base limpa.

Esta é a frente 1 de 4. As outras ficam fora do escopo (seção 8).

## 2. Evidência

Medido em 2026-10-02 sobre os 5 datasets (`20260827`, `20260917-fix`, `20260921-distcalc`, `20260925`, `20260928`), 4 prédios:

- `router_tx_bytes·8 / speedtest_down_mbps` fica entre 11,2 e 12,5 s em todos os prédios. O mesmo vale para rx e upload. O contador é o tráfego do teste.
- Os contadores não são acumulados: só cerca de 45% dos valores sobem entre linhas seguidas do mesmo `mac`.
- `router_tx_duration_us` soma de 3 a 7 s de airtime dentro desses 11 s.
- As razões por pacote não cancelam o volume. Correlação de Spearman, média dentro de cada prédio:

| Derivada | ρ com pacotes | ρ com download |
|---|---|---|
| retry por pacote | −0,61 | −0,64 |
| µs por pacote | −0,73 | −0,81 |
| bytes por airtime | 0,82 | 0,85 |

- Testes com alvo exatamente 0 falharam (14 de download, 4 de upload, 2 de latência, 3 de jitter). Valores entre 0 e 0,5 Mbps vêm com latência real (5 a 70 ms) e são enlaces ruins de verdade.

Com o pipeline do Studio (RandomForest de 200 árvores, imputação pela mediana, deixando um prédio de fora), o download sobe de R² pooled 0,348 (MAE 50,7) para 0,439 (MAE 44,7). Esse ganho vem de duas fontes: as colunas e derivadas físicas que já existem (`router_snr`, `router_signal_dbm`, `router_tx_rate_mbps`, `channel_width`, `router_NSS_TX_Station`, `eficiencia_espectral_tx`, `eficiencia_phy`, `perda_percurso_db`) e o filtro de alvo igual a 0. Duas features novas testadas (`phy_min` e `exp_por_vizinho`) não ajudaram e ficam de fora.

## 3. Decisões tomadas na conversa

| Tema | Decisão |
|---|---|
| Os 5 contadores de `CONTADORES_JANELA` | Vazamento confirmado (estado "sim") |
| Isenção `normaliza_volume` | Removida: derivada vaza se qualquer insumo vazar |
| As 4 derivadas afetadas | Ficam no catálogo, visíveis, fora de ajuste e de versão |
| Registro de versões | Só `v1` (era `v1-legado`), ativa |
| Filtro de teste que falhou | Alvo igual a 0, em uma função compartilhada por `load_datasets` e Studio |
| Features novas | Nenhuma |
| Versão nova do modelo | Depois, no assistente |

## 4. Proveniência: `src/ml/core/column_provenance.json`

- Os 5 de `CONTADORES_JANELA` (`router_tx_duration_us`, `router_rx_duration_us`, `router_tx_retries`, `router_tx_failed`, `router_rx_drop_misc`) ficam com `"classe": "tr069"`, `"vazamento": true`, sem `pendente`.
- O `parametro` de cada um passa a ser: `"delta da janela do speedtest (~11 s): tx_bytes·8/down ≈ 11 s em todos os prédios"`. Cabe no limite de 200 caracteres de `validar_regra`.
- `estado_contadores` passa a devolver `'sim'`. A pergunta em Modelos → Limites e pendências continua funcionando como hoje: quem responder de novo sobrescreve.
- A alteração local não commitada, que tirava `vazamento` desses 5, é substituída por esta.

## 5. Derivadas: `src/ml/core/features.py`

- Sai o campo `normaliza_volume` do dataclass `Derivada` e dos 3 itens do `CATALOGO` que o usam (`retry_por_pacote`, `falha_por_pacote`, `descarte_por_pacote_rx`).
- `classificar_derivada` passa a ser:
  - `vazamento = any(c.vazamento for c in insumos)`
  - `pendente = any(c.pendente for c in insumos) and not vazamento` (o mesmo invariante de `validar_regra`: vazamento confirmado não está pendente)
- Efeito: `retry_por_pacote`, `falha_por_pacote`, `descarte_por_pacote_rx` e `fracao_airtime_tx` ficam vazadas. `bytes_por_pacote_tx` já era.
- `CATALOGO_VERSAO = '2026-10-02.1'`.
- `src/ml/studio/features.py:168`: sai a chave `normaliza_volume` do item do inventário.
- `src/ml/studio/static/features.js:184`: sai a etiqueta "normaliza volume". Fica só a etiqueta "derivada".
- `src/ml/studio/selecao.py:31-36`: o comentário de `CONTADORES_VOLUME` passa a dizer que as razões por pacote herdam o vazamento dos contadores. O parâmetro `sem_volume` de `desenhar` continua existindo, porque o estado pode voltar a "não sei".

## 6. Registro de versões

### `src/ml/core/modelos.json`

```json
{
  "ativo": "v1",
  "versoes": {
    "v1": {
      "features": ["...as mesmas 14 de MODELO_ATUAL, na mesma ordem..."],
      "descricao": "<texto abaixo>",
      "origem": "MODELO_ATUAL",
      "criado_em": "2026-09-25"
    }
  }
}
```

Descrição (até 500 caracteres): "Modelo em produção (MODELO_ATUAL). Desde 2026-10-02, router_rx_drop_misc, router_rx_duration_us, router_tx_duration_us, router_tx_failed e router_tx_retries são vazamento (delta da janela do speedtest) e saem da conta na avaliação. client_opportunity_medium_use não é TR-069."

Ficam de fora:
- a `avaliacao`, que foi feita com 3 datasets e outra classificação. O Studio recalcula ao comparar;
- as versões `v1-sem-cliente`, `v2-tr069` e `v2-tr069-volume`.

Correção: a lista de 14 tem 5 contadores da janela, não 4 como dito na conversa. A avaliação continua de pé porque `avaliar_versao` tira as vazadas e as lista em `removidas_por_vazamento`.

### Código que acompanha a renomeação

- `src/ml/studio/api.py:79`: o registro de reserva (modelos.json ilegível) passa a usar `'v1'`.
- `tests/test_modelos_core.py:89-92`: o teste de semente verifica só `v1`, ativa, com `MODELO_ATUAL`. A verificação de `v1-sem-cliente` sai.

### O que fica como está

- `src/ml/core/derivadas.json`: o `teste.base: "v2-tr069"` e a menção na descrição de `taxa_phy_media` são histórico imutável.
- `CHANGELOG.md`: as entradas antigas não mudam. A entrada nova é a da seção 9.

## 7. Filtro de testes que falharam

Em `src/ml/core/data.py`:

```python
def descartar_testes_falhos(df: pd.DataFrame, alvo: str):
  """Remove linhas com alvo exatamente 0: teste que falhou, não enlace ruim.

  Valores pequenos e positivos (ex.: 0,3 Mbps) ficam: são enlaces ruins de
  verdade e são justamente o que o modelo precisa aprender.
  Devolve (df sem essas linhas, com índice refeito, e quantas saíram).
  """
```

- Compara com `== 0` sobre a coluna convertida para float. NaN não é removido aqui: cada chamador já trata alvo vazio.
- `load_datasets`: chama a função logo depois do `dropna` do alvo, só quando `target` não é None, e imprime `dropped N rows with failed test (target == 0) 'alvo'` quando N > 0, no mesmo formato da mensagem de alvo vazio.
- `src/ml/studio/features.py`, `preparar`: chama a função logo depois de descartar as linhas sem alvo e acrescenta a `avisos` `f'{n} testes que falharam ({alvo} = 0) descartados'` quando n > 0.
- Vale para os 4 alvos (`speedtest_down_mbps`, `speedtest_up_mbps`, `latency_ms`, `jitter_ms`). Latência 0 é impossível e jitter 0 aparece só nas mesmas linhas de teste que falhou.

## 8. Fora do escopo

- **Frente 2, deadzone temporal no coletor:** gravar contadores acumulados numa janela que termina `D` segundos antes do teste (colunas `router_pre_*`). É o único caminho para reaproveitar as razões sem vazamento.
- **Frente 3, teto de WAN:** a residência fica limitada pelo plano (p99 de 154 Mbps no download e 99 no upload).
- **Frente 4, nulos de TR-069:** o AX3000 da casa-marcelo e todo o `20260925` não têm stats de estação.
- Trocar o modelo do Studio para HistGradientBoosting.
- Features novas.
- Criar a versão nova do modelo.

## 9. CHANGELOG

Uma entrada nova com:
- a evidência da janela;
- a mudança de classificação;
- o fim da isenção;
- a limpeza do registro;
- o filtro de alvo 0;
- a tabela de R² da seção 2.

## 10. Testes

`tests/test_features_core.py`:
- `test_vazamento_herdado_e_anulado_por_normaliza_volume` vira `test_razao_herda_vazamento`: uma derivada de dois insumos, um deles vazado, sai vazada.
- `test_derivada_herda_pendente_salvo_normaliza_volume` vira `test_derivada_herda_pendente`: um insumo pendente deixa a derivada pendente. Com um insumo vazado e outro pendente, a derivada sai vazada e não pendente.
- Um teste que carrega a `column_provenance.json` real e verifica `estado_contadores(...) == 'sim'`.

`tests/test_ml_core.py`:
- `descartar_testes_falhos` remove só as linhas com 0, mantém 0,3 e NaN, devolve a contagem e não falha quando nada sai;
- `load_datasets` com um CSV temporário contendo uma linha com alvo 0 devolve o conjunto sem ela.

`tests/test_studio_features.py`:
- `preparar` com uma linha de alvo 0 tira a linha e registra o aviso.

`tests/test_modelos_core.py`:
- a semente tem só `v1`, ativa, com `MODELO_ATUAL`.

Antes de concluir, roda a suíte inteira (`python -m unittest discover tests`; o venv não tem pytest).
