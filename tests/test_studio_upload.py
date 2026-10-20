import asyncio
import io
import os
import shutil
import sys
import tempfile
import time
import types
import unittest
import zipfile
from unittest import mock

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import sites as S
from ml.studio import api
from ml.studio import ingestao as I

VILLA = {'chave': 'casa-zeta', 'rotulo': 'Casa Zeta', 'ambiente': 'domestico', 'prefixo': 'zeta'}


def frame(locais, inicio=10.0, n_clients=1.0, combo='a'):
  n = len(locais)
  base = np.arange(n, dtype=float) + inicio
  return pd.DataFrame({'local': locais, 'speedtest_down_mbps': base, 'speedtest_up_mbps': base / 2,
                       'latency_ms': base + 1, 'jitter_ms': base / 10, 'combo': combo,
                       'n_clients': n_clients, 'station_x': 1.0, 'house_x0': 0.0})


def csv_de(df) -> bytes:
  return df.to_csv(index=False).encode()


def zip_de(df, n_csv=1) -> bytes:
  buf = io.BytesIO()
  with zipfile.ZipFile(buf, 'w') as z:
    for i in range(n_csv):
      z.writestr(f'parte{i}.csv', df.to_csv(index=False))
  return buf.getvalue()


def existente(nome, df):
  return {'id': nome, 'usable': True, 'fingerprint': C.fingerprint(df), '_frame': df}


class Base(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.data = os.path.join(self.pasta, 'data')
    os.mkdir(self.data)
    self.predios = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.predios)
    S.recarregar(self.predios)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    shutil.rmtree(self.pasta)

  def previa(self, conteudo, nome='novo.csv', novos=(), existentes=()):
    token = I.guardar(nome, conteudo)
    return token, I.previa(token, nome, novos, data_dir=self.data, existentes=list(existentes))


class TestPrevia(Base):
  def test_csv_com_predios_conhecidos(self):
    _, p = self.previa(csv_de(frame(['sala', 'cwpb-2m', 'cwpb-2m'])))
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual((p['linhas'], p['geracao']), (3, 'current'))
    self.assertEqual([(x['predio'], x['linhas'], x['novo']) for x in p['predios']],
                     [('coworking', 2, False), ('residencia', 1, False)])

  def test_zip_com_um_csv(self):
    _, p = self.previa(zip_de(frame(['sala'])), nome='novo.zip')
    self.assertEqual(p['bloqueios'], [])

  def test_zip_com_dois_csv_bloqueia(self):
    _, p = self.previa(zip_de(frame(['sala']), n_csv=2), nome='novo.zip')
    self.assertTrue(any('ilegível' in b for b in p['bloqueios']))

  def test_local_desconhecido_agrupa_por_prefixo_e_bloqueia(self):
    _, p = self.previa(csv_de(frame(['zeta-sala', 'zeta-quarto', 'zeta-sala', 'garagem'])))
    self.assertEqual(p['desconhecidos'], [
      {'prefixo': 'garagem', 'valores': ['garagem'], 'linhas': 1},
      {'prefixo': 'zeta', 'valores': ['zeta-quarto', 'zeta-sala'], 'linhas': 3}])
    self.assertTrue(any('local desconhecido' in b for b in p['bloqueios']))

  def test_prefixo_candidato_corta_em_hifen_sublinhado_e_ponto(self):
    _, p = self.previa(csv_de(frame(['zeta_r1', 'zeta_r2', 'zeta-r3', 'zeta.r4'])))
    self.assertEqual([(g['prefixo'], g['linhas']) for g in p['desconhecidos']], [('zeta', 4)])
    _, p = self.previa(csv_de(frame(['zeta_r1', 'zeta_r2'])), novos=[VILLA])
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual([(x['predio'], x['linhas']) for x in p['predios']], [('casa-zeta', 2)])

  def test_predio_novo_resolve_na_previa_sem_gravar(self):
    with open(self.predios, encoding='utf-8') as h:
      antes = h.read()
    _, p = self.previa(csv_de(frame(['zeta-sala', 'zeta-quarto'])), novos=[VILLA])
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual(p['predios'][0]['predio'], 'casa-zeta')
    self.assertTrue(p['predios'][0]['novo'])
    with open(self.predios, encoding='utf-8') as h:
      self.assertEqual(h.read(), antes)

  def test_predio_novo_invalido_bloqueia(self):
    _, p = self.previa(csv_de(frame(['zeta-sala'])), novos=[dict(VILLA, prefixo='marcelo2')])
    self.assertTrue(any('cadastro de prédio' in b for b in p['bloqueios']))

  def test_preenchimento_e_aviso_de_coluna_vazia(self):
    _, p = self.previa(csv_de(frame(['sala', 'sala'], n_clients=np.nan, combo=None)))
    self.assertEqual(p['preenchimento']['n_clients'], 0.0)
    self.assertEqual(p['preenchimento']['local'], 1.0)
    self.assertTrue(any('n_clients' in a for a in p['avisos']))
    self.assertTrue(any('combo' in a for a in p['avisos']))
    self.assertEqual(p['geracao'], 'current')

  def test_falta_alvo_bloqueia(self):
    _, p = self.previa(csv_de(frame(['sala']).drop(columns=['jitter_ms'])))
    self.assertTrue(any('jitter_ms' in b for b in p['bloqueios']))

  def test_geracao_legada_so_avisa(self):
    _, p = self.previa(csv_de(frame(['sala']).drop(columns=['house_x0'])))
    self.assertEqual(p['bloqueios'], [])
    self.assertEqual(p['geracao'], 'legacy')
    self.assertTrue(any('legada' in a for a in p['avisos']))

  def test_local_vazio_bloqueia(self):
    _, p = self.previa(csv_de(frame(['sala', None])))
    self.assertTrue(any('local vazio' in b for b in p['bloqueios']))

  def test_nomes_bloqueados(self):
    open(os.path.join(self.data, 'ja.csv'), 'w').close()
    casos = {'ja.csv': 'já existe', 'x-qoe.csv': 'ignorados', 'x-filllast.csv': 'ignorados',
             'a..b.csv': 'inválido', 'novo.zip': 'terminar em .csv'}
    for nome, trecho in casos.items():
      token = I.guardar('original.csv', csv_de(frame(['sala'])))
      p = I.previa(token, nome, data_dir=self.data, existentes=[])
      self.assertTrue(any(trecho in b for b in p['bloqueios']), (nome, p['bloqueios']))

  def test_duplicata_bloqueia_e_contido_avisa(self):
    df = frame(['sala', 'sala', 'sala'])
    _, p = self.previa(csv_de(df), existentes=[existente('velho.csv', df)])
    self.assertEqual(p['duplicata_de'], 'velho.csv')
    self.assertTrue(any('duplicata' in b for b in p['bloqueios']))
    maior = pd.concat([df, frame(['sala'], inicio=99.0)])
    _, p = self.previa(csv_de(df), existentes=[existente('maior.csv', maior)])
    self.assertEqual(p['contido_em'], ['maior.csv'])
    self.assertTrue(any('maior.csv' in a for a in p['avisos']))

  def test_extensao_e_tamanho_recusados_no_envio(self):
    with self.assertRaises(ValueError):
      I.guardar('dados.xlsx', b'x')
    with self.assertRaises(ValueError):
      I.guardar('dados.csv', b'')

  def test_token_expirado(self):
    token = I.guardar('novo.csv', csv_de(frame(['sala'])), agora=time.time() - I.VALIDADE_S - 1)
    with self.assertRaises(KeyError):
      I.previa(token, 'novo.csv', data_dir=self.data, existentes=[])


class TestConfirmar(Base):
  def test_grava_arquivo_e_predio_e_descarta_o_token(self):
    token, _ = self.previa(csv_de(frame(['zeta-sala'])), novos=[VILLA])
    r = I.confirmar(token, 'novo.csv', [VILLA], data_dir=self.data, existentes=[])
    self.assertEqual(r, {'dataset': 'novo.csv', 'predios': ['casa-zeta'], 'linhas': 1})
    self.assertEqual(len(C._read_any(os.path.join(self.data, 'novo.csv'))), 1)
    self.assertIn('casa-zeta', S.registro_atual()['predios'])
    with self.assertRaises(KeyError):
      I.confirmar(token, 'novo.csv', [VILLA], data_dir=self.data, existentes=[])

  def test_refaz_a_validacao_e_nao_grava_com_bloqueio(self):
    token, _ = self.previa(csv_de(frame(['zeta-sala'])))
    with self.assertRaises(ValueError) as ctx:
      I.confirmar(token, 'novo.csv', [], data_dir=self.data, existentes=[])
    self.assertIn('local desconhecido', str(ctx.exception))
    self.assertEqual(os.listdir(self.data), [])
    self.assertNotIn('casa-zeta', S.registro_atual()['predios'])


class Pedido:
  """Request mínimo: as rotas só usam client.host, headers e body()."""
  def __init__(self, corpo=b'', host='127.0.0.1'):
    self.client = types.SimpleNamespace(host=host)
    self.headers = {'content-length': str(len(corpo))}
    self._corpo = corpo

  async def body(self):
    return self._corpo


class TestRotas(Base):
  def setUp(self):
    super().setUp()
    self.patches = [mock.patch.object(C, 'DATA_DIR', self.data),
                    mock.patch.object(api, 'descobertos', return_value=[])]
    for p in self.patches:
      p.start()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def enviar(self, conteudo, nome='novo.csv', host='127.0.0.1'):
    return asyncio.run(api.datasets_previa(Pedido(conteudo, host), nome=nome))

  def test_fluxo_completo_com_predio_novo(self):
    r = self.enviar(csv_de(frame(['zeta-sala', 'zeta-quarto'])))
    self.assertTrue(r['previa']['bloqueios'])
    revisada = api.datasets_revisar(api.Revisao(token=r['token'], nome='novo.csv', predios_novos=[VILLA]),
                                    Pedido())
    self.assertEqual(revisada['bloqueios'], [])
    with mock.patch.object(api, '_dados_mudaram') as mudou:
      feito = api.datasets_confirmar(api.Revisao(token=r['token'], nome='novo.csv', predios_novos=[VILLA]),
                                     Pedido())
    mudou.assert_called_once()
    self.assertEqual(feito['dataset'], 'novo.csv')
    self.assertTrue(os.path.exists(os.path.join(self.data, 'novo.csv')))

  def test_confirmar_com_bloqueio_da_422(self):
    r = self.enviar(csv_de(frame(['zeta-sala'])))
    with self.assertRaises(api.HTTPException) as ctx:
      api.datasets_confirmar(api.Revisao(token=r['token'], nome='novo.csv'), Pedido())
    self.assertEqual(ctx.exception.status_code, 422)

  def test_token_desconhecido_da_404(self):
    with self.assertRaises(api.HTTPException) as ctx:
      api.datasets_revisar(api.Revisao(token='nada', nome='novo.csv'), Pedido())
    self.assertEqual(ctx.exception.status_code, 404)

  def test_fora_da_maquina_da_403(self):
    with self.assertRaises(api.HTTPException) as ctx:
      self.enviar(csv_de(frame(['sala'])), host='10.0.0.5')
    self.assertEqual(ctx.exception.status_code, 403)

  def test_arquivo_grande_da_413(self):
    pedido = Pedido(b'x')
    pedido.headers['content-length'] = str(I.LIMITE_BYTES + 1)
    with self.assertRaises(api.HTTPException) as ctx:
      asyncio.run(api.datasets_previa(pedido, nome='novo.csv'))
    self.assertEqual(ctx.exception.status_code, 413)

  def test_extensao_errada_da_422(self):
    with self.assertRaises(api.HTTPException) as ctx:
      self.enviar(b'x', nome='novo.xlsx')
    self.assertEqual(ctx.exception.status_code, 422)

  def test_dados_mudaram_esquece_descoberta_e_caches(self):
    api._cache['payload'] = {'x': 1}
    api._modelos_cache['k'] = 1
    with mock.patch.object(api.core_carga, 'esquecer_descobertos') as esquecer:
      api._dados_mudaram()
    esquecer.assert_called_once()
    self.assertEqual((api._cache, api._modelos_cache), ({}, {}))


if __name__ == '__main__':
  unittest.main()
