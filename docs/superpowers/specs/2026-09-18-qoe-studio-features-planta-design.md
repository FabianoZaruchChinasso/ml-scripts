# QoE Studio: features TR-069 e planta da casa (design)

**Data:** 2026-09-18
**Base:** `master` atualizado (já inclui o PR #2, `new-data-revision`). A implementação sai de uma branch nova.
**Status:** desenho aprovado em conversa. Falta o plano de implementação.

## 1. Objetivo

O QoE Studio (`src/ml/studio/`) serve para avaliar a qualidade dos dados coletados, não o modelo, que é acompanhado no MLflow. Esta entrega traz duas coisas:

1. **View Features.** A partir das colunas dos CSVs de `data/`, mostra o que dá para levar ao modelo de produção, que só enxerga o que o ACS lê via TR-069. São quatro perguntas:
   - Quais colunas TR-069 ainda estão fora do modelo?
   - Quais features derivadas dá para construir?
   - O TR-069 consegue reconstruir o sinal das métricas auxiliares (sniffer, cliente, ambiente)?
   - Qual é o teto de desempenho de cada conjunto de features?
2. **Planta.** A view Planta passa a desenhar os pontos sobre a planta real da casa (traçado vetorial em CSV e/ou foto), e não mais sobre um retângulo vazio.

## 2. Achados que moldaram o desenho

Todos foram medidos no `20260827-metrics.zip` (638 linhas com alvo, 5 posições: `res-sala`, `res-quarto`, `res-suite`, `cwpb-1`, `cwpb-2`).

**Colunas**
- A geração atual tem **172 colunas**. O modelo usa 14 (`compare_protocols.FEATURES`). As colunas novas se dividem em:
  - `router_*` novas: `tx/rx_bytes`, `tx/rx_packets`, `NSS_*`, `bandwith_*`, `connected_time_sec` e `power_dbm`.
  - ~100 colunas `stats_80211_client_*` e `stats_80211_global_*`, de um sniffer 802.11.
  - `temperature_c` e `humidity_pct`.
  - Identificadores (`run_id`, `session_id`, `mac`, `bssid` etc.).
- Os contadores do roteador **não são cumulativos**. Só ~43% das diferenças consecutivas por cliente são ≥ 0, ou seja, os valores são por janela de medição, e razões linha a linha (retry/pacote, bytes/pacote) são válidas. A exceção é `router_connected_time_sec`, que é cumulativo (90% das diferenças ≥ 0).
- **`client_opportunity_medium_use` está no modelo, mas não é TR-069.** Ela conta vizinhos no site survey do *cliente* ([get-metrics.py:268-282](../../../src/get-metrics.py)), que o ACS não lê. Tirá-la muda o R² LOGO (download) de 0,685 para 0,684, então não custa nada.
- Há 13 colunas constantes (todos os `ampdu_*`) e 6 grupos de colunas idênticas, por exemplo `retry_overhead_pct` ≡ `retry_payload_fraction_pct` e `client_id` ≡ `old_client_id`.

**Protótipo da análise** (classificação provisória, RandomForest, LOGO por posição, alvo download)
- **Teto:** as 14 atuais dão **0,685**. Todo o TR-069 (27 colunas) dá **0,712** e melhora 4 de 5 posições. Tudo junto (83) dá **0,709**. Sem as colunas de vazamento, as auxiliares não sobem o teto.
- **Vazamento:** muitas colunas são medidas *durante* o speedtest e carregam o próprio alvo. É o caso de `download_*`/`upload_*`, dos bytes, pacotes, frames e throughput do sniffer e de `router_tx_bytes`/`router_tx_packets` (as duas têm ρ ≈ 0,8 com o alvo). Em produção o ACS lê esses contadores com tráfego de usuário, então elas não valem nada. Sem uma proteção, o cenário "tudo" daria R² ≈ 1.
- **Ganho ao somar cada candidata às 14:**
  - `bytes_por_pacote_tx` dá +0,048 (4/5), mas os insumos dela têm vazamento.
  - `largura_x_nss` dá +0,009, com 5/5 posições melhorando.
  - O resto fica em ±0,01. Com 5 posições, isso é ruído.
- **Proxy:** `stats_80211_client_amsdu_msdu_avg` é reconstruível pelo TR-069 (R² 0,79) e `link_speed_mbps` não é (0,03). `AP_channel` sai com R² = 1,00, o que indica que é legível pelo roteador e estava mal classificada.
- **Tempo:** no protótipo, o teto levou ~4 s, os proxies ~13 s e o ganho por candidata ~20 s. Com a semente real da seção 5.5 (16 candidatas, 15 proxies), a implementação validada levou **~80 s** pela API. Reduzir para 100 árvores cortou o tempo para 53 s, mas embaralhou o ranking do ganho (`largura_x_nss` foi de +0,009 para +0,017). Por isso ficam as 200 árvores.

**Planta**
- `docs/planta/Coordenadas_CSV_2D_casa_roni_v2.csv` traça **uma** unidade (a UND.03 da foto), com 31 segmentos a 20 px/m. O contorno mede 425 × 1500 cm, e o envelope dos dados mede 410 × 1386 cm.
- `docs/planta/casa_roni_planta_baixa.jpeg` é uma foto de celular (720 × 1280) de papel impresso, com as duas unidades espelhadas e o hall. O papel tem dobra e inclinação de ~1,5°. O CSV e a foto **não compartilham referencial**: o CSV vai até x = 810 e a foto tem 720 px de largura.
- Nada declara a origem de `station_x/y`. Das 8 orientações testadas, só uma põe 8 de 9 pontos no cômodo certo: origem no canto inferior direito do traçado (parede do hall, lado da sala), x na horizontal e escala ajustada ao envelope. O ponto que sobra, suite (90, 1105), cai no corredor, na porta da suíte.
- A view atual desenha a origem no canto superior esquerdo, o que dá a planta girada 180° em relação ao papel.
- O coworking agora tem envelope (480 × 1000 cm) mas não tem planta.

**Ambiente**
- `fastapi`, `uvicorn` e `pillow` estão no venv, mas não no `requirements.txt`.

## 3. Decisões

| Tema | Decisão | Motivo |
|---|---|---|
| Escopo da view Features | Os quatro ângulos: lacuna TR-069, derivadas, proxy e teto | Pedido explícito |
| Proveniência das colunas | Tabela explícita e versionada, sem convenção de nome | As colunas ambíguas (`RSSI`, `AP_channel`, `channel_width`) exigem declaração |
| Onde fica a tabela | `src/ml/core/column_provenance.json`, lida por `core/features.py` | É a fonte única de "o que é TR-069"; os scripts de treino poderão lê-la depois |
| Quem mantém a tabela | O Studio grava pela interface: o analista confirma a classe e salva | Pedido explícito: o analista não edita arquivo à mão |
| Colunas consideradas | As dos datasets ativos que não são legacy | Pedido explícito; com os padrões de hoje, é o 0827 |
| Cálculo pesado | Endpoint sob demanda, com botão, respeitando os datasets ativos | O número precisa refletir o conjunto ligado |
| Derivadas | Catálogo curado em Python | O catálogo automático viraria ruído de seleção com 5 posições |
| Vazamento | Marca `vazamento` na tabela; as colunas marcadas nunca entram em ajuste | Sem isso, o teto e os proxies mentem |
| Fonte da planta | Modo C (vetor sobre foto esmaecida) quando há os dois; B só com foto; A só com CSV; retângulo sem nenhum | Pedido explícito |
| Orientação | Paisagem por padrão, com botão para retrato | Pedido explícito ("se for simples, as duas") |
| Registro da foto | Modo de calibração no Studio, com 4 cliques, gravado em `docs/planta/plantas.json` | Pedido explícito |

## 4. Arquitetura

```
src/ml/core/
  arquivos.py                 # NOVO: gravar_json_atomico (usado pela tabela e pelo plantas.json)
  features.py                 # NOVO: carrega/valida/grava a tabela; catálogo de derivadas; MODELO_ATUAL
  column_provenance.json      # NOVO: tabela de classificação (semente, seção 5.5)
src/ml/studio/
  data.py                     # cacheia os frames descobertos; payload ganha `plantas`
  features.py                 # NOVO: inventário, teto, ganho +1, proxy
  plans.py                    # NOVO: plantas.json, paredes → cm, endireitamento da foto, gravação da calibração
  api.py                      # endpoints novos (seção 9)
  static/
    index.html                # item de navegação Features, seção da view, scripts ?v=2
    studio.js                 # estado e views atuais; delega Features e Planta
    features.js               # NOVO: view Features
    planta.js                 # NOVO: modos A/B/C/retângulo, botões, calibração
    graficos.js               # drawFloorPlan reescrito sobre uma transformação cm → tela
    styles.css
docs/planta/plantas.json      # NOVO: registro por prédio (semente, seção 8.1)
requirements.txt              # + fastapi, uvicorn, pillow
.gitignore                    # + .superpowers/
```

A view Features (seções 5 a 7) e a planta (seção 8) são independentes: não compartilham código novo além de `api.py` e `index.html`. O plano de implementação as trata como duas fases, cada uma entregável sozinha, com a Features primeiro.

O servidor continua em 127.0.0.1. As duas escritas novas tocam só arquivos versionados. Cada escrita é atômica (grava num arquivo temporário no mesmo diretório e faz `os.replace`), com chaves ordenadas, e passa por um `threading.Lock`. Os endpoints de escrita recusam requisições cujo `request.client.host` não seja loopback. Assim, subir com `--host 0.0.0.0` não expõe gravação. O commit é sempre humano.

## 5. Classificação de colunas (`core/features.py`)

### 5.1 Formato

```json
{
  "prefixos": {
    "stats_80211_": {"classe": "sniffer"},
    "router_":      {"classe": "tr069"},
    "download_":    {"classe": "cliente", "vazamento": true}
  },
  "colunas": {
    "AP_channel":      {"classe": "tr069", "parametro": "Device.WiFi.Radio.{i}.Channel"},
    "router_tx_bytes": {"classe": "tr069", "vazamento": true},
    "router_x":        {"classe": "geometria"}
  }
}
```

- **Classes** (constante `CLASSES` no código): `tr069`, `sniffer`, `cliente`, `ambiente`, `geometria`, `identificador`, `alvo`.
- **`vazamento`** é opcional e vale `false` por padrão. O texto exibido na interface é: *"Medida durante o teste: carrega o próprio alvo e não existe em produção."*
- **`parametro`** é opcional (caminho no data model TR-181) e só serve para documentar.

### 5.2 Resolução

`classificar(coluna) -> Classificacao(classe, vazamento, parametro, origem)`:
- A entrada exata em `colunas` vence.
- Depois vem o prefixo mais longo que casar em `prefixos`.
- Se nada casar, o resultado é `None`. **Nunca se adivinha.** A `origem` (`exata` / `prefixo`) aparece no inventário.

`sugerir(coluna)` só serve para pré-selecionar a classe na interface de uma coluna sem classificação. Devolve a classe da coluna classificada que tem o maior prefixo em comum, contado em tokens separados por `_`, com mínimo de 1 token. Se houver empate entre classes diferentes, ou se nada casar, devolve `None`.

### 5.3 Gravação

`gravar_classificacao(coluna, classe, vazamento, parametro)`:
- Valida `classe ∈ CLASSES`, `vazamento` booleano e `parametro` como `str | None` de até 200 caracteres.
- A coluna precisa existir em algum dataset descoberto ou já ter uma entrada na tabela.
- `vazamento` e `parametro` só são escritos quando verdadeiros ou preenchidos, o que deixa o diff mínimo.
- Grava a entrada exata em `colunas`: `json.dump(..., sort_keys=True, indent=2, ensure_ascii=False)` mais uma quebra de linha no fim, com escrita atômica.
- A reclassificação usa a mesma função.

### 5.4 Derivadas

```python
@dataclass(frozen=True)
class Derivada:
  nome: str
  insumos: tuple
  calcular: Callable[[pd.DataFrame], pd.Series]
  descricao: str
  normaliza_volume: bool = False
```

- **Classe:** `tr069` se todos os insumos forem `tr069`. Caso contrário, `auxiliar`, que é uma classe só de derivadas.
- **Vazamento:** `any(vazamento dos insumos) and not normaliza_volume`. A marca `normaliza_volume` serve para razões entre dois contadores de volume, em que o volume se cancela.
- **Divisão por zero:** vira `NaN` e conta contra a cobertura.
- Uma derivada cujo insumo não exista no frame é omitida, com um aviso no inventário.

**Catálogo inicial:**

| Nome | Fórmula | normaliza_volume |
|---|---|---|
| `retry_por_pacote` | `router_tx_retries / router_tx_packets` | sim |
| `falha_por_pacote` | `router_tx_failed / router_tx_packets` | sim |
| `bytes_por_pacote_tx` | `router_tx_bytes / router_tx_packets` | não (o tamanho médio de quadro depende do tráfego do teste) |
| `eficiencia_phy` | `router_expected_throughput_mbps / router_tx_rate_mbps` | — |
| `instabilidade_sinal` | `router_signal_dbm − router_signal_avg_dbm` | — |
| `assimetria_phy` | `router_tx_rate_mbps / router_rx_rate_mbps` | — |
| `fracao_airtime_tx` | `router_tx_duration_us / (router_tx_duration_us + router_rx_duration_us)` | — |
| `largura_x_nss` | `router_bandwith_TX_station × router_NSS_TX_Station` | — |
| `assimetria_enlace` | `RSSI − router_signal_dbm` (auxiliar: o `RSSI` vem do cliente) | — |

`CATALOGO_VERSAO` é uma string constante que entra na chave de cache e muda sempre que o catálogo mudar.

`MODELO_ATUAL` é a lista das 14 features de `compare_protocols.FEATURES`, copiada. Unificar as duas listas está fora do escopo (seção 13).

### 5.5 Semente da tabela

É uma proposta inicial para o analista revisar pela interface.

- **alvo:** os 4 alvos e `qoe_dw_score`.
- **identificador:**
  - `_time`, `stored_at`, `run_id`, `session_id`
  - `client_id`, `client_ID`, `old_client_id`, `client_name`
  - `mac`, `bssid`, `ssid`
  - `local`, `local_test`, `combo`, `n_clients`, `router_model`
  - `site_survey_strongest_ssid`
  - `stats_80211_raw`, `stats_80211_client_raw`, `stats_80211_global_timestamp`, `stats_80211_client_assoc_ap`, `*_retry_top_flow_key`
- **geometria:** `distance_m`, `related_distance`, `obstacles`, `house_x0/y0/z0`, `router_x/y/z`, `station_x/y/z`.
- **ambiente:** `temperature_c`, `humidity_pct`.
- **cliente:**
  - `RSSI`, `signal_level`, `link_speed_mbps`, `channel_width`
  - o prefixo `site_survey_`
  - `client_opportunity_medium_use`: gera o aviso da seção 6.4.
  - os prefixos `download_` e `upload_` com vazamento
- **tr069:**
  - o prefixo `router_`
  - `AP_channel` (`Device.WiFi.Radio.{i}.Channel`)
  - `radio` (`Device.WiFi.Radio.{i}.OperatingFrequencyBand`)
  - `client_mode` (`...AssociatedDevice.{i}.OperatingStandard`)
- **sniffer:** o prefixo `stats_80211_`.
- **Vazamento, como entradas exatas:** as colunas `tr069`, `sniffer` e `cliente` cujo nome case com `bytes|packets|throughput|_frames|_count$|_data$|qos_data|_msdu_total|subframes|elapsed`. O regex é aplicado **uma vez**, na hora de gerar a semente. A tabela guarda só as entradas explícitas, sem regex.
  - **Exceções:** `router_expected_throughput_mbps` (uma das 14 do modelo; é a estimativa do rate control, não volume medido durante o teste), `stats_80211_per_ap_count` e `stats_80211_per_client_count` (contagem de APs e de clientes vistos, não volume).
  - Resultado medido: 174 colunas em todos os datasets, 0 sem regra, 92 entradas exatas, 42 marcadas com vazamento, além dos prefixos `download_`/`upload_`.

## 6. Análise (`studio/features.py`)

### 6.1 Conjunto de dados

- **Entrada:** `ds` (ids separados por vírgula) e `alvo` (um dos 4, com `speedtest_down_mbps` como padrão). Id desconhecido devolve 400.
- **Datasets legacy** presentes em `ds` são ignorados e reportados em `avisos`.
- **Frames:** vêm de um cache de processo em `data.py`. `discover()` passa a guardar os frames, para o CSV não ser relido a cada requisição.
- **Preparação:**
  - As linhas com o alvo vazio são descartadas, e a contagem é reportada.
  - As derivadas do catálogo são calculadas.
  - Os grupos saem de `core.sites.resolve_site_id(level='position')`.
- **Categóricas:** colunas não numéricas com até 10 valores distintos (`MAX_CATEGORIAS`) são codificadas em one-hot nos ajustes. As que passam desse limite ficam fora, marcadas como "categórica de alta cardinalidade".

### 6.2 Inventário: `GET /api/features/inventario?ds=…&alvo=…` (rápido)

Por coluna, incluindo as derivadas:
- `classe`, `origem`, `vazamento`, `parametro`, `derivada`
- `cobertura` total e por dataset
- `constante` (no máximo 1 valor distinto)
- `rho`: |Spearman| com o alvo, só para numéricas não constantes, calculado nos pares sem NaN
- `no_modelo`
- `suspeita`: |ρ| ≥ 0,9 (`RHO_SUSPEITA`), sem vazamento marcado e classe ≠ `alvo`

No nível do conjunto:
- `sem_classificacao`: lista de `{coluna, sugestao, cobertura, amostra}`. A `amostra` é um texto: "mín a máx" para numéricas, até 3 valores para categóricas.
- `tabela_erro`: a mensagem quando `column_provenance.json` está ausente ou inválido (vira aviso crítico), senão `null`.
- `grupos_identicos`: agrupamento das colunas não constantes pelo hash dos valores arredondados a 9 casas, com NaN incluído.
- `modelo_fora_do_tr069`: membros de `MODELO_ATUAL` cuja classe ≠ `tr069`.
- `avisos`.

**Candidatas diretas:** classe `tr069` (bruta ou derivada), fora do modelo, sem vazamento, não constante e com `cobertura ≥ 0,7` (`COBERTURA_MIN`).

### 6.3 Ajuste: `GET /api/features/ajuste?ds=…&alvo=…` (lento, ~80 s)

**Elegíveis:** colunas classificadas, sem vazamento, não constantes, com cobertura ≥ 0,7 e classe ∉ {`identificador`, `geometria`, `alvo`}. De cada grupo de colunas idênticas entra só a primeira em ordem alfabética.

**Modelo:** `Pipeline(SimpleImputer(median), RandomForestRegressor(n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=42))`. As dobras saem de `core.splits.outer_logo_folds`, que já valida o número de sites e a disjunção. O `UserWarning` de poucas posições vira um aviso na resposta.

1. **Teto:** R² por dobra e a média, em três conjuntos:
   - `atual`: `MODELO_ATUAL` ∩ elegíveis.
   - `tr069`: todas as elegíveis `tr069`.
   - `tudo`: todas as elegíveis.
2. **Ganho +1:** para cada candidata direta *c* que também seja elegível (ou seja, representante do seu grupo de colunas idênticas), calcula R²(`atual` + *c*) − R²(`atual`) por dobra, pareado. Devolve a média e a quantidade de dobras que melhoram.
3. **Proxy:**
   - Entram as auxiliares elegíveis (`sniffer`, `cliente`, `ambiente`, numéricas), no máximo 15 (`MAX_PROXIES`), ordenadas por |ρ| com o alvo.
   - `y` é a auxiliar e `X` são as elegíveis `tr069`. Usa `n_estimators=100`.
   - Pula as dobras com menos de 5 linhas de teste ou menos de 20 de treino.
   - Devolve média, mínimo e máximo.
   - A leitura é: alcançável ≥ 0,7, parcial entre 0,3 e 0,7, só laboratório < 0,3.
   - Se todas as dobras derem R² ≥ 0,99 (`PROXY_TR069`), a resposta traz `parece_tr069: true`.

**Asserção estrutural:** antes de cada `fit`, `assert not (set(X.columns) & colunas_com_vazamento)`. É o mesmo motivo do `splits.py`: fazer o erro ser impossível, não só improvável.

**Cache:** a chave é `(tuple(sorted(ds)), alvo, sha256(bytes da tabela), CATALOGO_VERSAO)`. Fica num dict do processo e é limpo a cada gravação na tabela.

### 6.4 Avisos da view Features

| Condição | Severidade | Ação oferecida |
|---|---|---|
| Coluna sem classificação | crítico | Linha com a classe pré-selecionada (`sugerir`), a caixa vazamento e o botão **Adicionar** |
| Proxy com `parece_tr069` | atenção | **Reclassificar como TR-069** |
| Coluna suspeita (|ρ| ≥ 0,9 sem vazamento) | atenção | **Marcar vazamento** |
| Membro do modelo que não é TR-069 (hoje, `client_opportunity_medium_use`) | atenção | Só o texto: "está no modelo, mas não é TR-069" |
| Datasets legacy ativos | informação | Só o texto: "ignorados nesta view" |
| Menos de 4 posições | atenção | Reaproveita a mensagem do `validate_site_count` |

## 7. View Features (`features.js`)

- **Navegação:** novo item "Features" (ícone SVG `i-layers`, sem emoji), entre Restrição e Planta.
- **Título:** "Features". **Subtítulo:** "O que dá para levar para produção a partir do TR-069."
- **Controles:** seletor de alvo e um chip com os datasets ativos, as amostras e as posições.
- **Ordem dos blocos:**
  1. **Avisos** da seção 6.4. Os avisos globais do Studio (acima da view) continuam aparecendo, como em todas as views.
  2. **Teto de desempenho.** Um gráfico de pontos em eixo truncado (não barras, já que o eixo não começa em zero). Tem uma linha por conjunto, um ponto por posição (as cores de série identificam a posição, com legenda) e uma marca vertical na média. Um texto explica a leitura, e o aviso "com N posições, diferenças abaixo de ~0,02 são ruído" usa o N real. O botão **Rodar análise** mostra os segundos decorridos durante o cálculo e fica desabilitado até terminar. O rodapé mostra "calculado às HH:MM · Xs".
  3. **Candidatas TR-069 fora do modelo.** Tabela com coluna, tipo (bruta/derivada, e a tag "normaliza volume" quando se aplicar), cobertura, |ρ| com barra, ganho e "melhora N/5". Fica ordenada por ganho quando existe; antes do ajuste, por |ρ|. As linhas com vazamento vão para o fim, esmaecidas, com a tag "vazamento" (ou "vazamento herdado") e o texto "fora dos ajustes".
  4. **Auxiliares: o TR-069 consegue reconstruir?** Tabela com auxiliar, fonte, |ρ|, R² do proxy com barra, faixa por posição e a leitura em tag. Colunas idênticas aparecem numa linha só, com a nota "idêntica a …".
  5. **Blocos recolhidos (`<details>`):** Vazamento (lista e explicação), Qualidade das colunas (constantes e grupos idênticos) e Inventário completo (todas as colunas com classe, origem, cobertura, ρ e contagem por classe).
- **Carregamento:** o inventário carrega ao abrir a view e sempre que mudarem o alvo ou os datasets. O ajuste só roda pelo botão. Se o conjunto mudar, o resultado anterior fica marcado como "desatualizado".
- **Ações de gravação:** Adicionar, Reclassificar e Marcar vazamento chamam `POST /api/columns` e recarregam o inventário. O ajuste em cache é invalidado no servidor.
- Os erros aparecem dentro do card afetado, e a view continua usável.

## 8. Planta (`plans.py`, `planta.js`, `graficos.js`)

### 8.1 `docs/planta/plantas.json`

```json
{
  "casa": {
    "paredes": {"arquivo": "Coordenadas_CSV_2D_casa_roni_v2.csv", "origem": "inferior-direito", "eixo_x": "horizontal"},
    "foto":    {"arquivo": "casa_roni_planta_baixa.jpeg", "cantos": null}
  }
}
```

- **Chave:** a mesma do `BUILDINGS` em `studio/data.py`.
- **Arquivos:** só nome base (sem caminho), relativo a `docs/planta/`.
- **`origem`** ∈ {`superior-esquerdo`, `superior-direito`, `inferior-esquerdo`, `inferior-direito`}. **`eixo_x`** ∈ {`horizontal`, `vertical`}.
- **`cantos`**: pixels da foto original correspondentes aos cantos do envelope, na ordem (0,0), (W,0), (W,H), (0,H). Na semente fica `null` e é preenchido pela calibração.

### 8.2 Paredes → cm

- **Contorno:** `X0..X1`, `Y0..Y1` em px do CSV, com y para baixo.
- **Origem:** `(Xo, Yo)` é o canto indicado por `origem`. `ux = +1` se a origem estiver à esquerda, `−1` à direita. `uy = +1` se estiver em cima, `−1` embaixo.
- **Transformação direta:**
  - `horizontal`: `X = Xo + ux·x·(X1−X0)/W` e `Y = Yo + uy·y·(Y1−Y0)/H`.
  - `vertical`: `X = Xo + ux·y·(X1−X0)/H` e `Y = Yo + uy·x·(Y1−Y0)/W`.
- **Paredes:** o servidor aplica a inversa a cada extremidade e entrega os segmentos em cm.
- **Colunas exigidas no CSV:** `X1_px, Y1_px, X2_px, Y2_px`.
- **Casa:** com `inferior-direito` e `horizontal`, fica `X = 810 − x·85/410` e `Y = 660 − y·300/1386`.

### 8.3 Orientação "papel"

`papel` é uma matriz 2×2 com entradas em {−1, 0, 1} que leva direções em cm para a orientação do desenho original (suíte em cima), em cm isotrópicos.
- **Com CSV:**
  - `horizontal`: `[[ux,0],[0,uy]]`
  - `vertical`: `[[0,ux],[uy,0]]`
- **Só com foto:** a matriz vem de encaixar numa das 8 orientações os vetores `c(W,0) − c(0,0)` e `c(0,H) − c(0,0)`, usando o eixo dominante e o sinal de cada um.
- **Sem nenhum dos dois:** identidade (x para a direita, y para baixo). É o comportamento de hoje para o coworking.

### 8.4 Foto endireitada

- **Saída:** 1 px = 1 cm, com margem `m = 60` cm, tamanho `(W+2m) × (H+2m)`. Para a casa, 530 × 1506.
- **Homografia:** o pixel de saída `(u, v)` corresponde a `(u−m, v−m)` em cm. A homografia vai da saída para a foto e é resolvida com numpy (sistema 8×8) a partir dos 4 pares `(m,m) → cantos[0]`, `(W+m,m) → cantos[1]`, `(W+m,H+m) → cantos[2]` e `(m,H+m) → cantos[3]`.
- **Pillow:** `Image.transform(size, Image.Transform.PERSPECTIVE, coefs, Image.Resampling.BICUBIC, fillcolor=(0,0,0,0))` em RGBA. Sai em PNG.
- **Cache:** em memória, com chave `(mtime do arquivo, cantos)`.
- **Pré-visualização da calibração:** `?cantos=x0,y0,…,x3,y3` endireita na hora, sem cache.

### 8.5 Payload

`build_payload()` ganha:
```
plantas: {prédio: {                                   # todo prédio com envelope tem entrada
  paredes: [[x1,y1,x2,y2], …] (cm) | null,
  papel: [[a,b],[c,d]] | null,
  foto: {url: "api/plan/casa/foto.png?v=<hash dos cantos>", margem_cm: 60} | null,   # só se calibrada
  margem_cm: 60,
  calibracao: {paredes: {arquivo, origem, eixo_x} | null, foto: {arquivo, cantos | null} | null},
  avisos: [str]
}},
plantasAvisos: [str]
```
O `?v=` muda quando os cantos mudam, o que invalida o cache do navegador depois de uma calibração nova. Um prédio que esteja em `plantas.json` sem envelope nos dados fica fora e gera um aviso em `plantasAvisos`.

### 8.6 Desenho

- **Transformação única** para o canvas: `tela = encaixe ∘ R ∘ papel`.
  - `R` é a identidade em retrato e `(x,y) → (−y, x)` em paisagem (90° no sentido horário, com y para baixo).
  - O encaixe é uma escala uniforme mais translação, com folga para o raio das marcas.
- **Os pontos, as paredes, o envelope e o roteador** passam pela mesma transformação. O texto (percentual, rótulos) é desenhado sem girar, na posição já transformada. Os alvos de hover ficam em px de tela, e `attachTooltip` segue igual.
- **Modos:**

| Paredes | Foto calibrada | Modo | Desenho |
|---|---|---|---|
| sim | sim | C | foto a 28% por baixo, paredes em `--ink-1` |
| não | sim | B | foto opaca |
| sim | não | A | só paredes |
| não | não | retângulo | contorno do envelope em `--axis` |

- **Botões**, numa linha de controles no topo do card da view (valem para todos os prédios):
  - **Retrato**, um toggle, guardado em `localStorage['qoe-plan-orient']` ∈ {`paisagem`, `retrato`}, com `paisagem` como padrão.
  - **Foto ao fundo**, um toggle que só aparece quando algum prédio está no modo C, guardado em `localStorage['qoe-plan-foto']`.
  - As leituras e gravações do `localStorage` vão em `try/catch`.
- **Texto dos pontos:** branco acima de 55%, `#0b0b0b` abaixo. A rampa sequencial é a mesma nos dois temas, então a cor do texto segue o fundo, não o tema.
- **Rótulos de dimensão:** ficam fora da caixa com margem; por dentro, cairiam sobre a foto.
- **Layout:**
  - Paisagem usa uma coluna, com a altura do canvas dada pela proporção e limitada a 520 px.
  - Retrato usa duas colunas, com 640 px de altura.
  - Continua valendo a montagem do DOM em duas passadas do `renderPlan` atual, que evita os círculos achatados.
- **Tema escuro:** a foto é desenhada com `ctx.filter = 'invert(1) hue-rotate(180deg)'`. Onde `ctx.filter` não existir, usa opacidade 15%.
- **Aviso extra:** a contagem de pontos fora do envelope (`x ∉ [0,W]` ou `y ∉ [0,H]`).

### 8.7 Calibração

- **Onde fica:** o botão **Calibrar planta** em cada card de prédio com envelope abre um painel.
- **Escolha dos arquivos:** para o prédio sem entrada, o analista escolhe os arquivos da pasta. A lista vem de `GET /api/plan/arquivos`, com `.jpg/.jpeg/.png/.csv` de `docs/planta/`.
- **Foto:**
  - A foto original é exibida num canvas, e um texto indica o próximo canto: "(0, 0), origem", depois "(W, 0)", "(W, H)" e "(0, H)", com W e H do envelope.
  - Um botão desfaz o último clique.
  - Depois dos 4 cliques, a pré-visualização mostra a foto endireitada (`foto.png?arquivo=…&cantos=…`, sem cache no servidor) com as paredes e os pontos por cima, sempre em retrato.
- **Paredes:** dois seletores (`origem` e `eixo_x`) com pré-visualização ao vivo via `GET /api/plan/{prédio}/paredes`.
- **Salvar calibração:** faz `POST /api/plan/{prédio}`. A resposta traz `plantas` e `plantasAvisos` novos, e o Studio redesenha sem recarregar a página.

## 9. API

| Método | Rota | Função |
|---|---|---|
| GET | `/api/payload` | O de hoje, mais `plantas` |
| GET | `/api/features/inventario?ds&alvo` | Seção 6.2 |
| GET | `/api/features/ajuste?ds&alvo` | Seção 6.3 |
| POST | `/api/columns` | `{coluna, classe, vazamento, parametro}` → grava (seção 5.3), limpa os caches de ajuste |
| GET | `/api/plan/arquivos` | `{paredes: [.csv], fotos: [.jpg/.jpeg/.png]}` de `docs/planta/` |
| GET | `/api/plan/arquivo/{nome}` | Arquivo sem tratamento (a foto original, para calibrar) |
| GET | `/api/plan/{prédio}/paredes?arquivo&origem&eixo_x` | Paredes em cm e `papel`, para a pré-visualização |
| GET | `/api/plan/{prédio}/foto.png` | Foto endireitada da calibração salva (com cache) |
| GET | `/api/plan/{prédio}/foto.png?arquivo&cantos=x0,y0,…,x3,y3` | Pré-visualização, sem cache |
| POST | `/api/plan/{prédio}` | `{paredes?: {arquivo, origem, eixo_x}, foto?: {arquivo, cantos \| null}}` → valida e grava `plantas.json`; devolve `{plantas, plantasAvisos}` |

**Validação da planta:**
- O prédio precisa existir no `BUILDINGS`.
- `arquivo` precisa ser um nome base, sem `/` nem `..`, e existir em `docs/planta/`.
- Os enums precisam ser válidos.
- `cantos` são 4 pares numéricos dentro das dimensões da imagem.

Uma validação que falha devolve 422 com a mensagem em português. Uma escrita que não vem de loopback devolve 403.

## 10. Tratamento de erros

| Situação | Comportamento |
|---|---|
| `column_provenance.json` ausente ou inválido | Aviso crítico na view Features; todas as colunas contam como sem classificação; nada quebra fora da view |
| Coluna sem classificação | Fica fora do inventário analítico e dos ajustes até ser classificada; aviso crítico com a ação de classificar |
| Insumo de derivada ausente | Derivada omitida, com aviso |
| Ajuste com menos de 2 posições | `validate_site_count` levanta erro → 422 com a mensagem, mostrada no card |
| Exceção dentro de um ajuste | 500 com a mensagem; o card do teto mostra o erro e o inventário continua |
| `plantas.json` ausente | Todos os prédios desenhados como retângulo; sem aviso (é o estado normal sem planta) |
| Arquivo de planta referenciado e inexistente | Aviso no card; cai para o modo que ainda der |
| CSV de paredes sem as colunas exigidas | Aviso; as paredes são ignoradas |
| Foto sem `cantos` | Tratada como ausente no desenho; o botão **Calibrar planta** fica em destaque |
| Pontos fora do envelope | Aviso com a contagem |

## 11. Testes

`unittest` com dados sintéticos, seguindo `tests/test_ml_core.py` (sem depender dos CSVs grandes).

- **`tests/test_features_core.py`**
  - A entrada exata vence o prefixo, e entre prefixos vence o mais longo.
  - Coluna sem regra devolve `None` e nunca uma classe.
  - `sugerir`: prefixo de tokens em comum, `None` em empate entre classes, `None` sem casamento.
  - Derivada: `tr069` só se todos os insumos forem `tr069`. O vazamento é herdado, e `normaliza_volume` o anula. A divisão por zero dá NaN.
  - Gravação: ler o que foi gravado devolve o mesmo, as chaves ficam ordenadas, e classe inválida ou coluna inexistente levantam erro. Após a escrita não sobra arquivo temporário.
- **`tests/test_studio_features.py`**
  - Inventário: cobertura, constante, grupos idênticos (constantes excluídos), Spearman e `suspeita`.
  - Elegibilidade: vazamento, constante, cobertura < 0,7 e identificador ficam de fora; um representante por grupo idêntico.
  - Asserção estrutural: injetar uma coluna com vazamento no conjunto de ajuste levanta `AssertionError`.
  - As dobras têm posições disjuntas.
  - O ganho +1 é pareado por dobra.
  - `parece_tr069` aparece quando a auxiliar é função exata de uma coluna TR-069.
- **`tests/test_plans.py`**
  - As 8 combinações `origem`/`eixo_x` levam os cantos do contorno aos cantos do envelope (0,0), (W,0), (W,H), (0,H), e a volta cm → px → cm é a identidade.
  - `papel` bate com o esperado nas 8 combinações e no caso só com foto.
  - Endireitamento: uma imagem sintética com marcadores de cor nos 4 cantos, após a transformação, tem os marcadores em `(m,m)`, `(W+m,m)`, `(W+m,H+m)` e `(m,H+m)`, com tolerância de 2 px.
  - Validação: arquivo com `..`, canto fora da imagem e enum inválido são rejeitados; a escrita é atômica.
- **Roteiro manual no navegador** (`python3 src/ml/studio.py`)
  - Modos C, B, A e retângulo, obtidos mudando temporariamente o `plantas.json`.
  - Botões Foto e Girar, tema claro e escuro, e recarregar a página mantendo as preferências.
  - Calibração completa da foto da casa.
  - Classificar uma coluna e reclassificar `AP_channel`, conferindo o `git diff` do JSON.
  - Rodar a análise, mudar datasets e alvo, e ver o resultado marcado como "desatualizado".

## 12. Riscos e limites

- Com **5 posições em 2 prédios**, um ΔR² abaixo de ~0,02 é ruído. A interface diz isso com o N real, e a coluna "melhora N/5" existe para não se ler ruído como sinal.
- A semente de vazamento vem de um regex sobre os nomes. Ela é revisável e explícita na tabela, mas pode ter falso positivo ou negativo, e o aviso de |ρ| ≥ 0,9 é a rede de segurança.
- A qualidade da foto endireitada é limitada pelo original, uma foto de 720 × 1280 com ~250 px úteis por unidade.
- O ajuste é uma requisição síncrona de ~80 s. Isso é aceitável para uso local por uma pessoa, porque o botão mostra o cronômetro e o resultado fica em cache. Se crescer, o caminho é limitar as candidatas; menos árvores já se mostrou instável no ranking.
- A orientação da casa (origem no canto inferior direito) é a que melhor encaixa os dados, mas **não foi confirmada por quem mediu**. A calibração existe para corrigir isso sem mexer em código.

## 13. Fora do escopo

- Fazer `compare_protocols.py` e os benchmarks lerem `column_provenance.json` e `MODELO_ATUAL`. Fica como recomendação para o lado do MLflow, junto com tirar `client_opportunity_medium_use` do modelo (seção 2).
- Registrar resultados no MLflow. Os números da view são de viabilidade dos dados, não do modelo.
- Cômodos como polígonos e o aviso "ponto fora do cômodo". O caso suite (90, 1105) fica como observação.
- Editar receitas de derivadas pela interface.
- Registro automático da foto por correspondência de feições.
- Planta para o coworking (não há arquivo).
