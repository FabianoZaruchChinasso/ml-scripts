import os
import subprocess
import sys
import types
import unittest
from unittest import mock

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(SRC)

from ml.core import completa


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None, classes={})


class TestSemOStudio(unittest.TestCase):
  def test_importa_sem_o_studio_nem_o_servidor(self):
    codigo = ('import sys; sys.path.insert(0, %r); import ml.core.completa; '
              "ruins = [m for m in sys.modules if m == 'fastapi' or m.startswith('ml.studio')]; "
              'sys.exit(1 if ruins else 0)' % SRC)
    self.assertEqual(subprocess.run([sys.executable, '-c', codigo]).returncode, 0)


class TestAvaliacaoCompleta(unittest.TestCase):
  """O peso (LOGO, quantis, limiar) vai para mocks: aqui só importa a ordem e o que quem chama fornece."""

  def rodar(self, conjunto, ambiente, progresso=None):
    patches = [
      mock.patch.object(completa.core_avaliacao, 'avaliar', return_value=({'n': 10}, 'prev')),
      mock.patch.object(completa, 'prever_quantis', return_value='q'),
      mock.patch.object(completa.core_quantis, 'resumir_quantis', return_value={}),
      mock.patch.object(completa.core_avaliacao, 'atende', return_value={}),
      mock.patch.object(completa.core_limiar, 'decisoes_atende', return_value={}),
      mock.patch.object(completa.core_limiar, 'resumir_decisoes', return_value={}),
      mock.patch.object(completa.core_limiar, 'fatores_producao', return_value={}),
      mock.patch.object(completa.core_quantis, 'atende_completo', return_value={}),
      mock.patch.object(completa.core_aplicacoes, 'carregar_perfil', return_value={}),
      mock.patch.object(completa.core_comodo, 'de_previsoes', return_value='prev4'),
    ]
    self.bloco = mock.patch.object(completa, 'bloco_comodo', return_value={'nota': 0.7}).start()
    for p in patches:
      p.start()
    self.addCleanup(mock.patch.stopall)
    return completa.avaliacao_completa(conjunto, ambiente, ['router_snr'], progresso=progresso)

  def test_pede_o_conjunto_de_cada_alvo_depois_do_aviso_da_etapa(self):
    ordem = []

    def conjunto(alvo):
      ordem.append(('conjunto', alvo))
      return conj(alvo)
    self.rodar(conjunto, None, lambda evento: ordem.append(('etapa', evento['etapa'])))
    self.assertEqual(ordem[:8], [('etapa', 'download'), ('conjunto', 'speedtest_down_mbps'),
                                 ('etapa', 'upload'), ('conjunto', 'speedtest_up_mbps'),
                                 ('etapa', 'latência'), ('conjunto', 'latency_ms'),
                                 ('etapa', 'jitter'), ('conjunto', 'jitter_ms')])
    self.assertEqual(ordem[8:], [('etapa', 'atende'), ('etapa', 'cômodo')])

  def test_aceita_os_conjuntos_ja_carregados(self):
    conjs = {alvo: conj(alvo) for alvo in completa.TARGETS}
    saida = self.rodar(conjs.__getitem__, None)
    self.assertEqual(self.bloco.call_args.args[0], conjs)
    self.assertEqual(saida['comodo'], {'nota': 0.7})

  def test_sem_ambiente_vale_todos(self):
    for ambiente in (None, '', 'todos'):
      saida = self.rodar(conj, ambiente)
      self.assertEqual(saida['speedtest_down_mbps']['ambiente'], 'todos')
    self.assertEqual(self.rodar(conj, 'domestico')['jitter_ms']['ambiente'], 'domestico')


if __name__ == '__main__':
  unittest.main()
