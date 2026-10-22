import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import fila  # noqa: E402


class TestFila(unittest.TestCase):
  def test_conclui_com_resultado_e_etapa(self):
    def tarefa(progresso):
      progresso('somando')
      return 1 + 1
    job = fila.enfileirar('teste', 'soma', tarefa)
    self.assertIn(job['status'], ('na fila', 'rodando', 'concluído'))
    final = A.esperar_job(job['id'], 10)
    self.assertEqual((final['status'], final['resultado'], final['etapa']), ('concluído', 2, 'somando'))

  def test_falha_guarda_o_erro(self):
    def tarefa(progresso):
      raise ValueError('quebrou')
    final = A.esperar_job(fila.enfileirar('teste', 'falha', tarefa)['id'], 10)
    self.assertEqual(final['status'], 'falhou')
    self.assertIn('quebrou', final['erro'])

  def test_job_desconhecido(self):
    with self.assertRaises(KeyError):
      fila.job('nao-existe')

  def test_listar_mais_recente_primeiro(self):
    a = fila.enfileirar('teste', 'a', lambda p: None)
    b = fila.enfileirar('teste', 'b', lambda p: None)
    A.esperar_job(b['id'], 10)
    ids = [j['id'] for j in fila.listar()]
    self.assertLess(ids.index(b['id']), ids.index(a['id']))


if __name__ == '__main__':
  unittest.main()
