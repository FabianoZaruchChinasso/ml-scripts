# Snapshot do MLflow (2026-11-03)

Cópia estática do MLflow local, para consulta sem rodar os scripts. Contém só as execuções de 2026-11-03: as versões **v1, v2-tr069, v3-tr069, v4 e v5** (ativa: **v5**), todas treinadas sobre os 7 datasets canônicos.

## Experimentos

- **MLflow Wifi Regressions** (70 execuções): por versão, 14 execuções, 6 configurações (RandomForest, ExtraTrees e GradientBoosting, com 10 e 20 estimadores) para `speedtest_down_mbps` e `speedtest_up_mbps`, mais os quantis de `latency_ms` e `jitter_ms`.
- **MLflow Wifi QoE** (5 execuções): uma por versão.
- **MLflow Wifi Studio** (5 execuções, `<versão>-studio`): a avaliação que o Studio guarda por versão (nota por cômodo, apto para jogo, atende e régua por alvo), registrada por `src/ml/studio_mlflow.py`.

Cada execução traz parâmetros, métricas e os artefatos pequenos (JSON de contrato, cobertura TR-069, eficiência e fatores; MLmodel, conda e requirements dos modelos).

## Como abrir

O caminho dos artefatos é relativo (`./mlruns/...`) e resolve a partir do diretório atual, então o comando deve rodar de dentro de `res/mlflow/` (mlflow 3.15.1):

```bash
cd res/mlflow
../../venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5055
```

Depois abra http://127.0.0.1:5055.

Atenção: o MLflow 3 gera dados de demonstração (experimento "MLflow Demo") dentro do banco quando a interface aciona `POST /ajax-api/3.0/mlflow/demo/generate`. Não existe flag nem variável de ambiente que desligue isso. Para não sujar o snapshot, abra uma cópia (`cp -r res/mlflow /tmp/mlflow-view` e rode o comando lá) ou, se o experimento "MLflow Demo" aparecer, não commite o `mlflow.db` alterado (`git restore res/mlflow/mlflow.db`).

## Modelos não versionados

Os binários `model.skops` (~45 MB cada) não estão no repositório. Onde ficariam há um `MODELO_NAO_VERSIONADO.txt`. Para recriá-los, a partir da raiz do repositório:

```bash
MODELO=<v> ALVO=<alvo> venv/bin/python src/ml/regression_mlflow.py   # regressão
MODELO=<v> venv/bin/python src/ml/qoe_mlflow.py                      # QoE
venv/bin/python src/ml/studio_mlflow.py                              # Studio
```

Isso grava no MLflow de trabalho, não neste snapshot.

## MLflow de trabalho

O MLflow de trabalho (`mlflow.db` e `mlruns/` na raiz do repositório) está no `.gitignore` e é separado deste. Este diretório é um recorte estático.
