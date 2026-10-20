import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import rtr_finetune as E


class TestRtrFinetune(unittest.TestCase):
  def test_variantes(self):
    v = E.variantes()
    self.assertEqual(sorted(v), ['ft_ap', 'ft_rssi', 'zero_ap', 'zero_rssi'])
    self.assertEqual(v['ft_ap'], ([], 'router_signal_dbm', True))
    self.assertEqual(v['zero_rssi'], (['RSSI'], 'RSSI', False))

  def test_comparacoes(self):
    self.assertEqual(E.COMPARACOES, [('ft_ap', 'base'), ('ft_ap', 'zero_ap'),
                                     ('ft_rssi', 'base'), ('ft_rssi', 'zero_rssi')])


if __name__ == '__main__':
  unittest.main()
