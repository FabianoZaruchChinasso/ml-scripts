import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mlflow
import numpy as np

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, SRC)

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import pacote_mlflow as PM
from test_studio_features import TABELA, frame

DN, UP = 'speedtest_down_mbps', 'speedtest_up_mbps'
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}

# A entrada vai por pickle: JSON arredonda os números, e um valor de treino arredondado pode cair do
# outro lado de um corte do modelo quantílico.
PROCESSO_NOVO = '''
import sys
import mlflow, numpy as np, pandas as pd
uri, pasta, src = sys.argv[1:4]
assert src not in [p.rstrip('/') for p in sys.path], sys.path
saida = mlflow.pyfunc.load_model(uri).predict(pd.read_pickle(pasta + '/exemplo.pkl'))
origem = sys.modules['ml.core.pacote'].__file__
assert not origem.startswith(src), origem
np.testing.assert_allclose(saida.to_numpy(), pd.read_pickle(pasta + '/esperado.pkl').to_numpy(), rtol=1e-9)
'''


class TestGravarECarregar(unittest.TestCase):
  """Um mlflow.db temporário para a classe: gravar o pacote uma vez basta para os dois testes."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    tmp = tempfile.TemporaryDirectory()
    cls.addClassCleanup(tmp.cleanup)
    cls.tmp = tmp.name
    cls.addClassCleanup(mlflow.set_tracking_uri, mlflow.get_tracking_uri())
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{cls.tmp}/mlflow.db'})
    env.start()
    cls.addClassCleanup(env.stop)
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(conjs, FEATURES, POR_BANDA)
    cls.exemplo = conjs[DN].df[cls.pacote.receita['entradas']].head(5)
    experimento = mlflow.create_experiment('teste', artifact_location=os.path.join(cls.tmp, 'mlruns'))
    with mlflow.start_run(experiment_id=experimento) as run:
      PM.gravar(cls.pacote, cls.exemplo)
    cls.uri = f'runs:/{run.info.run_id}/{PM.NOME}'

  def test_carregar_devolve_um_pacote_que_preve_igual(self):
    volta = PM.carregar(self.uri)
    self.assertEqual(volta.receita, self.pacote.receita)
    self.assertEqual(sorted(volta.modelos), sorted(self.pacote.modelos))
    np.testing.assert_allclose(P.prever(volta, self.exemplo)[0].to_numpy(),
                               P.prever(self.pacote, self.exemplo)[0].to_numpy(), rtol=1e-12)

  def test_modelo_carregado_aceita_inteiro_valor_ausente_e_coluna_a_mais(self):
    """Os contadores chegam inteiros e às vezes faltam. A assinatura do MLflow recusaria os dois casos,
    e por isso o modelo é gravado sem ela."""
    modelo = mlflow.pyfunc.load_model(self.uri)
    self.assertIsNone(modelo.metadata.signature)
    esperado = P.prever(self.pacote, self.exemplo)[0]
    inteiros = self.exemplo.assign(router_snr=self.exemplo['router_snr'].astype('int64'), extra=1)
    np.testing.assert_allclose(modelo.predict(inteiros).to_numpy(), esperado.to_numpy(), rtol=1e-12)
    faltando = self.exemplo.copy()
    faltando.loc[faltando.index[0], ['router_snr', 'router_signal_dbm']] = np.nan
    faltando['radio'] = [None, '5GHz', '2.4GHz', '5ghz', '2.4ghz']
    saida = modelo.predict(faltando)
    self.assertEqual(list(saida.columns), list(P.SAIDAS))
    self.assertFalse(saida.isna().any().any())

  def test_carrega_em_processo_novo_fora_do_repositorio(self):
    self.exemplo.to_pickle(os.path.join(self.tmp, 'exemplo.pkl'))
    P.prever(self.pacote, self.exemplo)[0].to_pickle(os.path.join(self.tmp, 'esperado.pkl'))
    ambiente = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    r = subprocess.run([sys.executable, '-c', PROCESSO_NOVO, self.uri, self.tmp, SRC], cwd=self.tmp,
                       env=ambiente, capture_output=True, text=True, timeout=300)
    self.assertEqual(r.returncode, 0, r.stderr[-2000:])


if __name__ == '__main__':
  unittest.main()
