# WIFI Metric Scripts

This project provides Python scripts to collect WIFI metrics from InfluxDB and transform them into CSV datasets for analysis and ML workflows.

For the QoE model (per-room Wi-Fi quality from TR-069 counters), see [QoE model from TR-069](#qoe-model-from-tr-069) at the end of this file.

## Main scripts

- `src/get-metrics.py`: collect raw metrics from InfluxDB into CSV.
- `src/get-router.py`: collect router site-survey data.
- `src/get-client.py`: collect client site-survey data.
- `src/fn-metrics.py`: apply filter/normalization directives from a `.dsc` file to an input CSV.

## Directive format

Each directive line follows:

`name; data; operation; values`

- `name`: free text label
- `data`: one column name or a Python-style list of columns
- `operation`: operation name
- `values`: optional operation-specific values

## `fill-last` behavior

`fill-last` forward-fills NaN values.

- Without `values`: global forward fill (legacy behavior), fallback default is `0`.
- With `values` as `group_column,group_name`: fill only rows that belong to `group_name` in `group_column`.
- With `values` as `group_column::group_name`: same grouped behavior.
- With `values` as `group_column,group_name,default_value`: grouped behavior plus custom fallback for first empty row in the group.

Examples:

- `fl1; empty_col; fill-last`
- `fl2; empty_col; fill-last; 99`
- `fl3; empty_col; fill-last; measure_group, client`
- `fl4; empty_col; fill-last; measure_group::client`
- `fl5; empty_col; fill-last; measure_group,client,99`

## `fill-last-auto` behavior

`fill-last-auto` forward-fills NaN values by group, where the group is automatically read from each current row.

- `values` must contain the group column name.
- For each NaN cell in target columns, the script searches previous rows with the same group value and uses the last valid value in that same target column.
- If no previous valid value exists for that group, the NaN is filled with `0`.

Examples:

- `fla1; empty_col; fill-last-auto; measure_group`
- `fla2; ['v1','v2']; fill-last-auto; measure_group`

## Testing

Run tests with:

```bash
python -m unittest tests/test_fn_metrics.py
```

## QoE model from TR-069

The model estimates the Wi-Fi quality of each room in a home using only counters the router exposes over TR-069 (the protocol an ISP uses to read and configure the router): transmit and receive PHY rates, signal, SNR, noise, channel width, client mode, band (`radio`) and number of clients. The predictions do not need a speed test; the per-room classification still uses one reference measurement per home (see "Known limitations").

### What the model answers

For each position (room), the model predicts download, upload, latency and jitter. From these it classifies the room relative to the rest of the home (the "per-room ruler", `comodo` in the code):

- **good**, **degraded** or **poor** (`bom`, `degradado`, `ruim`);
- **fit for cloud gaming** (`apto para jogo`), yes or no.

The code lives in `src/ml/core/`: `carga.py` (dataset loading), `features.py`, `modelos.py` (version registry), `avaliacao.py` (regression evaluation), `quantis.py` (latency and jitter), `comodo.py` (per-room ruler).

### Data

The canonical set has 7 datasets in `data/`: `20260827-metrics.zip`, `20260917-metrics-fix.zip`, `20260921-metrics-distcalc.zip`, `20260925-metrics.zip`, `20260928-metrics.zip`, `villa-20261025.csv` and `villa-esc-20261026.csv`. That is 1708 rows, 6 buildings (casa-marcelo, coworking, hotmilk, residencia, villa-escritorio, villa-residencial) and 27 positions in the per-room ruler. Buildings are registered in `src/ml/core/predios.json`; column classification is in `src/ml/core/column_provenance.json`.

Counters measured during the speed test (`router_tx_retries`, `router_rx_duration_us`, `router_tx_duration_us`, `router_tx_failed`, `router_rx_drop_misc`) are deltas over the test window itself. They leak the result, so the evaluation drops them.

### How it is evaluated

**LOGO (leave-one-building-out):** each building is predicted by a model trained on the other five. 90% intervals come from a bootstrap over positions, stratified by building.

**Floor (`piso`):** the same pipeline using only the band (`radio`). It is the minimum any version has to beat.

**Per-room ruler** (`src/ml/core/comodo.py`):

| Item | Rule |
|---|---|
| Rows used | only rows alone on the radio (`concorrentes_mesmo_radio == 1`): 981 of 1708 |
| Capacity ratio | min(download, upload) of the position / the same value at the best measured position of the building (reference V0, provisional) |
| Class by capacity | ratio < 0.25 poor; < 0.75 degraded; otherwise good |
| Latency and jitter | position p90 against the "norma" profile (`src/ml/core/aplicacoes_norma.json`) |
| Failures | failing Web browsing (Navegação) drops the room to poor; failing Video call (Chamada de vídeo) caps it at degraded |
| Fit for gaming | position p90 of latency and jitter within the Cloud gaming limits (80 ms and 10 ms) |
| Score | balanced accuracy over positions |

Latency and jitter are predicted by quantile models (p50 and p90). The CQR conformal correction (conformalized quantile regression, which adjusts the p90 to reach nominal coverage) is used in the coverage metrics. The per-room ruler uses the p90 without it (`q90_bruto`), because CQR is conservative per row and left every position outside "fit for gaming".

### Versions

The registry is `src/ml/core/modelos.json`. The active version is **v5** (TR-069 coverage "proxy": standard TR-181 only, plus a contention proxy).

| Version | What changes |
|---|---|
| v1 | Original model (`MODELO_ATUAL`), with `router_expected_throughput_mbps` and other counters; the window counters are dropped in evaluation |
| v2-tr069 | TR-069 only: PHY rate, SNR, signal, channel width, spectral efficiency and path loss |
| v3-tr069 | v2 plus contention (`n_clients`, `concorrentes_mesmo_radio`) |
| v4 | v3 predicting efficiency (throughput / PHY rate) on 5 GHz and absolute Mbps on 2.4 GHz |
| v5 | Same as v4 without `router_expected_throughput_mbps` (an extension outside TR-181); costs about 0.02 of "atende" |

Numbers stored in `modelos.json` (90% intervals in parentheses; the R² columns come from the MLflow "Studio" runs):

| Version | Per-room score | Fit for gaming | Atende completo | R² download | R² upload |
|---|---|---|---|---|---|
| floor (`radio` only) | 0.452 (0.346 to 0.553) | 0.550 (0.500 to 0.611) | - | - | - |
| v1 | 0.643 (0.546 to 0.765) | 0.782 (0.667 to 0.917) | 0.661 | 0.594 | 0.434 |
| v2-tr069 | 0.643 (0.556 to 0.750) | 0.594 (0.441 to 0.744) | 0.652 | 0.549 | 0.519 |
| v3-tr069 | 0.722 (0.630 to 0.833) | 0.644 (0.500 to 0.782) | 0.661 | 0.597 | 0.650 |
| v4 | 0.722 (0.630 to 0.833) | 0.644 (0.500 to 0.782) | 0.666 | 0.759 | 0.752 |
| v5 (active) | 0.722 (0.630 to 0.833) | 0.673 (0.528 to 0.815) | 0.661 | 0.746 | 0.739 |

"Atende completo" is the balanced accuracy, per row and per application, of "the measurement meets the application" (download and upload above the thresholds, latency and jitter p90 below), comparing predictions with measurements; the number is the mean over the four applications. R² is pooled, i.e. computed over all rows predicted outside the training buildings.

### How to run

Everything from the repository root.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt   # environment
venv/bin/python -m unittest discover -s tests -p 'test_*.py'       # Python tests, about 30 min
node --test tests/js/logica.test.js                                # Studio JS tests
venv/bin/python src/ml/studio.py --port 8100                       # Studio: http://127.0.0.1:8100
venv/bin/python src/ml/comodo_benchmark.py                         # per-room ruler (MODELO=<v> restricts)
MODELO=v5 ALVO=speedtest_down_mbps venv/bin/python src/ml/regression_mlflow.py
MODELO=v5 venv/bin/python src/ml/qoe_mlflow.py
MODELO=v5 venv/bin/python src/ml/versao_mlflow.py                  # one run: evaluation, model package and data version
venv/bin/python src/ml/ativar_mlflow.py                            # show the active version (alias "ativo")
MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py                  # activate the latest registered version of v5
venv/bin/python src/ml/studio_mlflow.py                            # re-logs the Studio evaluation (the Studio logs on its own)
```

In the scripts, `MODELO` is the version (default: the definition of the active version, the alias `ativo` of the registered model `qoe-wifi` in the working MLflow; on a machine without that MLflow, pass `MODELO=` or `--modelo`, or the script stops), `ALVO` is the target of `regression_mlflow.py` (default: download; also `speedtest_up_mbps`, `latency_ms`, `jitter_ms`) and `DATASETS=a.zip,b.zip` changes the dataset set (default: the canonical one). Recreating the models of all versions takes about 50 min. `versao_mlflow.py` takes `MODELO` and `DATASETS` the same way and takes about 7 minutes per version.

### MLflow

`res/mlflow/` is a versioned snapshot of MLflow from 2026-11-03 with v1 to v5, in the experiments "MLflow Wifi Regressions", "MLflow Wifi QoE" and "MLflow Wifi Studio". To open it (mlflow 3.15.1):

```bash
cd res/mlflow
../../venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5055
```

Then open http://127.0.0.1:5055 and switch the interface to "Model training".

- Model binaries (`model.skops`, about 45 MB each) are not versioned; the folder's `README.md` explains how to recreate them.
- The working MLflow at the root (`mlflow.db` and `mlruns/`) is in `.gitignore`.
- The Studio logs to the working MLflow by itself ("MLflow Wifi Studio"): saving or re-evaluating a version creates a run `<version>-studio`. Useful filter: `tags.atual = 'sim'` (latest run of each version). The Studio no longer activates versions. If logging fails, the version is still saved and the Studio shows a warning; run `venv/bin/python src/ml/studio_mlflow.py` to log again. Set `MLFLOW_TRACKING_URI` to log somewhere else.
- `src/ml/versao_mlflow.py` logs one run per version to the experiment "MLflow Wifi Pipeline" in the working MLflow: the full evaluation (the same numbers as the Studio), a single model package (`runs:/<run_id>/pacote`, a pyfunc that takes rows with the TR-181 counters and returns download, upload and the p50 and p90 of latency and jitter) and the data version (dataset `qoe-wifi`, with the dataset fingerprints as a parameter). The headline metrics are the errors of the four predictions; the per-room ruler and the "atende" scores are logged as secondary metrics, with the ruler versions as tags. The package carries its own copy of `src/ml/core`, so it loads without the repository, and it is logged without an MLflow signature (the signature would reject missing integer counters). It does not cap predictions at the WAN ceiling, which the evaluation does. Each run is also registered as a new version of the model `qoe-wifi` in the Model Registry (tags `definicao`, `fingerprints`, `versao_pacote`; run tag `versao_registrada`) and carries the training inputs in `referencia_entradas.parquet`, the reference for input-drift monitoring. Registering does not change the active version.
- The active version is the alias `ativo` of `qoe-wifi` (`models:/qoe-wifi@ativo`), the only source: `src/ml/core/modelos.json` keeps only the definitions (features, denominator, profile). A *definition* is an entry of `modelos.json` (v1 ... v5); a *registered version* is a Model Registry number, the package trained from a definition on a given dataset. `src/ml/ativar_mlflow.py` moves the alias by hand until the promotion gate exists. The Registry lives in the working MLflow, which is not in git: other machines see no active version.
- Runs logged before 2026-11-09 still carry an `ativo` parameter that may be stale (MLflow parameters cannot change); the `ativo` tag was removed from the Studio runs on 2026-11-11 (the active version is the Registry alias). The `git_arvore` tag says whether tracked files had uncommitted changes when the run was logged: right after saving it is always `suja`, because the new version only exists in the uncommitted `modelos.json`.
- Do not click "explore demo", "Detect Issues" or the assistant prompts: they write demo data into the open database. If that happens, run `git restore res/mlflow/mlflow.db`.

### Known limitations

- Only 6 buildings and 27 positions. The intervals are wide.
- Every version beats the floor, but v3, v4 and v5 tie with v1 on the per-room ruler (difference +0.079, 90% interval 0.000 to 0.170). That is why activation in the Studio, which only unlocks on a "better" verdict, stays locked.
- The class uses the best measured position of the home as reference. A new home in production does not have that reference without a reference test.
- The "fit for gaming" estimator was chosen after looking at these same 27 positions. Only v1 and v5 have a lower bound above 0.5, and the model tends to over-predict fit (12 to 14 positions against 10 real ones).
- The human perception label agrees with the ruler's truth on 17 of 27 positions: the label judges absolute experience, the ruler judges relative to the home.
- villa-escritorio is capped at 93.1 Mbps download and 100.2 upload (link limit, in `predios.json`), so per-building R² there is meaningless.

### Further reading

- `CHANGELOG.md` (in Portuguese): decisions and measured effects, newest first.
- `docs/superpowers/specs/` and `docs/superpowers/plans/`: designs and plans, by date.
