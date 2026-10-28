import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import qoe_mlflow


class TestNomeArtefato(unittest.TestCase):
  def test_acentos_e_espacos(self):
    self.assertEqual(qoe_mlflow._nome_artefato('Chamada de vídeo'), 'qoe_chamada_de_video')
    self.assertEqual(qoe_mlflow._nome_artefato('Streaming 4K'), 'qoe_streaming_4k')
    self.assertEqual(qoe_mlflow._nome_artefato('Jogo em nuvem'), 'qoe_jogo_em_nuvem')


if __name__ == '__main__':
  unittest.main()
