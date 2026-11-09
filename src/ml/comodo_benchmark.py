"""Régua por cômodo (core/comodo.py): reavalia as versões do registro e o piso.

Versão: MODELO=<nome> restringe a uma versão (a ativa entra sempre, para a comparação).
Datasets: DATASETS=a.zip,b.zip (padrão: o conjunto canônico, o mesmo do Studio). Imprime a
referência da casa, a verdade por posição, a verdade contra o rótulo humano e, por versão, a
nota com intervalo de 90%, a comparação com o piso e com a ativa, a matriz de confusão, os
acertos por prédio e "apto para jogo". Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.

Experimentos: TREINO=sozinhas treina todas as linhas da tabela só com as linhas sozinhas no rádio
(a verdade já é só delas). EXPERIMENTO=f1,f2,... acrescenta a linha 'experimento' com essas
features (sem denominador). EXPERIMENTO_DENOMINADOR=<coluna> faz a linha 'experimento' prever download
e upload como eficiência (alvo ÷ coluna) no 5 GHz, como a v5. MLFLOW=1 registra cada linha como um run
em 'MLflow Wifi Experimentos'; com EXPERIMENTO, só a linha 'experimento' (piso e versões já têm run próprio).
REF=prevista calcula também a nota com a referência PREVISTA (melhor cômodo previsto da casa, em vez
do real) e imprime as comparações da regra de decisão de docs/superpowers/plans/2026-11-05-referencia-prevista.md.
RELATIVAS=1 acrescenta, para a versão ativa, '<ativa>-rel' (prevê a razão de capacidade com as features
de core_comodo.RELATIVAS relativas à casa) e '<ativa>-razao-abs' (mesma razão, features absolutas) e
imprime a regra de decisão de docs/superpowers/plans/2026-11-05-features-relativas.md.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import comodo as core_comodo
from ml.core import modelos as core_modelos
from ml.core import percepcao as core_percepcao
from ml.core import qoe as core_qoe

PISO = 'piso'
EXPERIMENTO = 'experimento'


def _faixa(intervalo) -> str:
  return '–' if intervalo is None else f'{intervalo[0]:+.3f} a {intervalo[1]:+.3f}'


def metricas_mlflow(nome: str, features, treino: str, r: dict, vs_ativa: float, graves: int, por_predio: dict,
                    denominador: str = None, referencia: str = 'real') -> tuple:
  """(parâmetros, métricas) de uma linha da tabela para o run do MLflow."""
  params = {'linha': nome, 'features': ','.join(features), 'n_features': len(features), 'treino': treino,
            'versao_comodo': core_comodo.VERSAO_COMODO, 'denominador': denominador or 'nenhum',
            'referencia': referencia}
  metricas = {'comodo_nota': r['nota'], 'vs_ativa': vs_ativa, 'graves': graves}
  if r.get('intervalo'):
    metricas['comodo_lo90'], metricas['comodo_hi90'] = r['intervalo'][0], r['intervalo'][1]
  for site, (acertos, n) in por_predio.items():
    metricas[f'acerto_{site}'] = acertos / n
  return params, metricas


def denominador_experimento(coluna):
  """Denominador da linha 'experimento': `coluna` divide download e upload no 5 GHz, como na v5."""
  if not coluna:
    return None
  por_banda = {'coluna': coluna, 'radio': '5ghz'}
  return {core_comodo.DN: dict(por_banda), core_comodo.UP: dict(por_banda)}


def main():
  registro = core_modelos.carregar()
  pedido = os.environ.get('MODELO')
  if pedido and pedido not in registro['versoes']:
    raise SystemExit(f'MODELO={pedido!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ativa = registro['ativo']
  nomes = [pedido] if pedido else list(registro['versoes'])
  if ativa not in nomes:
    nomes.append(ativa)
  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_qoe.ALVOS}
  vazadas = {alvo: [c for c, k in conj.classes.items() if k is not None and k.vazamento]
             for alvo, conj in conjs.items()}
  treino = os.environ.get('TREINO', 'todas')
  if treino not in ('todas', 'sozinhas'):
    raise SystemExit(f'TREINO={treino!r}: use todas ou sozinhas')
  conjs_treino = core_comodo.conjuntos_sozinhos(conjs) if treino == 'sozinhas' else conjs
  modo_ref = os.environ.get('REF', 'real')
  if modo_ref not in ('real', 'prevista'):
    raise SystemExit(f'REF={modo_ref!r}: use real ou prevista')
  relativas_on = os.environ.get('RELATIVAS') == '1'
  experimento = [x for x in os.environ.get('EXPERIMENTO', '').split(',') if x]
  if experimento:
    nomes.append(EXPERIMENTO)
  exp_den = os.environ.get('EXPERIMENTO_DENOMINADOR') or None
  if exp_den and not experimento:
    raise SystemExit('EXPERIMENTO_DENOMINADOR precisa de EXPERIMENTO')
  limiares = core_aplicacoes.carregar_perfil('norma')
  df = core_qoe.conjunto_qoe(conjs)
  real, ref = core_comodo.verdade(df, limiares)
  linhas = set(core_comodo.sozinhas(df)['_linha'])

  print(f'Régua por cômodo {core_comodo.VERSAO_COMODO}; datasets {conjs[core_comodo.DN].datasets}; treino {treino}')
  print(f'{len(linhas)} de {len(df)} linhas sozinhas no rádio; {len(real)} posições; {real["_site"].nunique()} prédios')
  print('\nReferência da casa (V0 provisório, Mbps):')
  print(ref.round(1).to_string())
  print('\nVerdade por posição:')
  print(real.sort_values(['_site', 'razao']).round(2).to_string())
  print(f'Classes: {real["classe"].value_counts().to_dict()}; apto para jogo: {int(real["apto_jogo"].sum())}')

  core_percepcao.carregar()  # valida o arquivo de rótulos antes de ler os níveis brutos
  with open(core_percepcao.PERCEPCAO_PATH, encoding='utf-8') as handle:
    niveis = json.load(handle)['posicoes']
  acuracia, m = core_comodo.contra_rotulo(real, niveis)
  print(f'\nVerdade contra o rótulo humano (rótulo nas linhas): acurácia balanceada {acuracia:.3f}')
  print(m.to_string())

  pos = {}
  pos_prev = {}
  prevs = {}
  features_de = {}
  for nome in [PISO] + nomes:
    if nome == PISO:
      features, denominador = ['radio'], None
    elif nome == EXPERIMENTO:
      features, denominador = experimento, denominador_experimento(exp_den)
    else:
      features = registro['versoes'][nome]['features']
      denominador = {a: core_modelos.denominador_de(registro, nome, a) for a in (core_comodo.DN, core_comodo.UP)}
    features_de[nome] = features
    prev = core_comodo.prever(conjs_treino, features, vazadas, denominador)
    prev = prev[prev['_linha'].isin(linhas)]
    prevs[nome] = prev
    pos[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(prev, ref, limiares))
    if modo_ref == 'prevista':
      pos_prev[nome] = core_comodo.juntar(real, core_comodo.classe_prevista(
          prev, core_comodo.referencia_prevista(prev), limiares))
  if len({tuple(p.index) for p in pos.values()}) != 1:
    raise SystemExit('as versões não cobrem as mesmas posições: '
                     + '; '.join(f'{n}: {len(p)}' for n, p in pos.items()))
  amostras = core_avaliacao.reamostras(pos[PISO].index, pos[PISO]['_site'])

  print(f'\nNota (acurácia balanceada por posição, acaso 0,333); ativa = {ativa}')
  for nome in [PISO] + nomes:
    p = pos[nome]
    r = core_comodo.nota(p, amostras)
    c_piso = core_comodo.comparar(p, pos[PISO], amostras)
    c_ativa = core_comodo.comparar(p, pos[ativa], amostras)
    _, graves = core_comodo.confusao(p)
    acertos = int((p['real'] == p['previsto']).sum())
    print(f'  {nome:<10} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs piso {c_piso["diferenca"]:+.3f} '
          f'({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | vs {ativa} {c_ativa["diferenca"]:+.3f} '
          f'({_faixa(c_ativa["intervalo"])}) {c_ativa["resultado"]} | acertos {acertos}/{len(p)} | '
          f'graves {graves} | jogo {core_comodo.nota_jogo(p):.3f}')

  for nome in [PISO] + nomes:
    p = pos[nome]
    m, graves = core_comodo.confusao(p)
    print(f'\n{nome}: matriz de confusão (posições; verdade nas linhas), erros graves {graves}')
    print(m.to_string())
    print('Acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
    erradas = p[p['real'] != p['previsto']]
    print('Erradas: ' + ', '.join(f'{i} ({l.real}->{l.previsto})' for i, l in erradas.iterrows()))

  if modo_ref == 'prevista':
    print('\nReferência prevista (melhor cômodo PREVISTO da casa; a verdade não muda)')
    for nome in [PISO] + nomes:
      p = pos_prev[nome]
      r = core_comodo.nota(p, amostras)
      c_real = core_comodo.comparar(p, pos[nome], amostras)
      c_piso = core_comodo.comparar(p, pos_prev[PISO], amostras)
      _, graves = core_comodo.confusao(p)
      print(f'  {nome:<11} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs mesma linha com ref real '
            f'{c_real["diferenca"]:+.3f} ({_faixa(c_real["intervalo"])}) {c_real["resultado"]} | vs piso previsto '
            f'{c_piso["diferenca"]:+.3f} ({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | '
            f'acertos {int((p["real"] == p["previsto"]).sum())}/{len(p)} | graves {graves}')
      print('    acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
    print('\nRegra de decisão')
    a = core_comodo.comparar(pos_prev[ativa], pos[ativa], amostras)
    b = core_comodo.comparar(pos_prev[ativa], pos_prev[PISO], amostras)
    print(f'  1a. {ativa} prevista vs {ativa} real: {a["diferenca"]:+.3f} ({_faixa(a["intervalo"])}) {a["resultado"]}')
    print(f'  1b. {ativa} prevista vs piso previsto: {b["diferenca"]:+.3f} ({_faixa(b["intervalo"])}) {b["resultado"]}')
    adotada = a['resultado'] == 'melhor' and b['resultado'] == 'melhor'
    print(f'  -> referência prevista {"ADOTADA" if adotada else "não adotada"}')
    if 'v1' in pos_prev and ativa != 'v1':
      c = core_comodo.comparar(pos_prev['v1'], pos_prev[ativa], amostras)
      destino = 'trocar para v1' if c['resultado'] == 'melhor' else f'manter {ativa}'
      print(f'  2.  v1 prevista vs {ativa} prevista: {c["diferenca"]:+.3f} ({_faixa(c["intervalo"])}) '
            f'{c["resultado"]} -> {destino}')

  pos_rel = {}
  if relativas_on:
    feats_ativa = registro['versoes'][ativa]['features']
    ref_feat = core_comodo.referencia_features(df, list(core_comodo.RELATIVAS))
    ref_feat_banda = core_comodo.referencia_features(df, list(core_comodo.RELATIVAS), por_banda=True)
    variantes = ((f'{ativa}-rel', dict(relativas=True), ref_feat, False),
                 (f'{ativa}-razao-abs', dict(relativas=False), ref_feat, False),
                 (f'{ativa}-rel-justo', dict(relativas=True, por_banda=True, excluir_wan=True), ref_feat_banda, True))
    for rotulo, opcoes, rf, saturar in variantes:
      pr = core_comodo.prever_razao(conjs_treino, feats_ativa, vazadas, ref, rf, **opcoes)
      pr = pr[pr['_linha'].isin(linhas)]
      pos_rel[rotulo] = core_comodo.juntar(real, core_comodo.classe_prevista_razao(prevs[ativa], pr, limiares,
                                                                                   saturar_wan=saturar))
      if tuple(pos_rel[rotulo].index) != tuple(pos[ativa].index):
        raise SystemExit(f'{rotulo} não cobre as mesmas posições de {ativa}')
    print(f'\nModelo de razão (referência das features: maior valor da casa; relativas: '
          f'{", ".join(core_comodo.RELATIVAS)})')
    print('Referência das features por prédio:')
    print(ref_feat.round(1).to_string())
    print('Referência das features por prédio e banda (rel-justo):')
    print(ref_feat_banda.round(1).to_string())
    for rotulo, p in pos_rel.items():
      r = core_comodo.nota(p, amostras)
      c_ativa = core_comodo.comparar(p, pos[ativa], amostras)
      c_piso = core_comodo.comparar(p, pos[PISO], amostras)
      m, graves = core_comodo.confusao(p)
      print(f'  {rotulo:<16} {r["nota"]:.3f} (90%: {r["intervalo"]}) | vs {ativa} {c_ativa["diferenca"]:+.3f} '
            f'({_faixa(c_ativa["intervalo"])}) {c_ativa["resultado"]} | vs piso {c_piso["diferenca"]:+.3f} '
            f'({_faixa(c_piso["intervalo"])}) {c_piso["resultado"]} | acertos {int((p["real"] == p["previsto"]).sum())}'
            f'/{len(p)} | graves {graves}')
      print('    acertos por prédio: ' + ', '.join(f'{s} {a}/{n}' for s, (a, n) in core_comodo.por_predio(p).items()))
      erradas = p[p['real'] != p['previsto']]
      print('    erradas: ' + ', '.join(f'{i} ({l.real}->{l.previsto})' for i, l in erradas.iterrows()))
    cand, abl = pos_rel[f'{ativa}-rel'], pos_rel[f'{ativa}-razao-abs']
    a = core_comodo.comparar(cand, pos[ativa], amostras)
    b = core_comodo.comparar(cand, pos[PISO], amostras)
    d = core_comodo.comparar(cand, abl, amostras)
    print('\nRegra de decisão (features relativas)')
    print(f'  1a. {ativa}-rel vs {ativa}: {a["diferenca"]:+.3f} ({_faixa(a["intervalo"])}) {a["resultado"]}')
    print(f'  1b. {ativa}-rel vs piso: {b["diferenca"]:+.3f} ({_faixa(b["intervalo"])}) {b["resultado"]}')
    aprovado = a['resultado'] == 'melhor' and b['resultado'] == 'melhor'
    print(f'  -> candidato {"APROVADO" if aprovado else "não aprovado"}')
    print(f'  descritivo: {ativa}-rel vs {ativa}-razao-abs: {d["diferenca"]:+.3f} ({_faixa(d["intervalo"])}) '
          f'{d["resultado"]}')
    justo = pos_rel[f'{ativa}-rel-justo']
    ja = core_comodo.comparar(justo, pos[ativa], amostras)
    jb = core_comodo.comparar(justo, pos[PISO], amostras)
    jd = core_comodo.comparar(justo, cand, amostras)
    print('\nRegra de decisão (rodada justa, desenhada depois da revisão; ver o plano 2026-11-05-features-relativas-justo)')
    print(f'  1a. {ativa}-rel-justo vs {ativa}: {ja["diferenca"]:+.3f} ({_faixa(ja["intervalo"])}) {ja["resultado"]}')
    print(f'  1b. {ativa}-rel-justo vs piso: {jb["diferenca"]:+.3f} ({_faixa(jb["intervalo"])}) {jb["resultado"]}')
    aprovado_justo = ja['resultado'] == 'melhor' and jb['resultado'] == 'melhor'
    print(f'  -> candidato {"APROVADO" if aprovado_justo else "não aprovado"}')
    print(f'  descritivo: {ativa}-rel-justo vs {ativa}-rel: {jd["diferenca"]:+.3f} ({_faixa(jd["intervalo"])}) '
          f'{jd["resultado"]}')

  if os.environ.get('MLFLOW') == '1':
    import mlflow
    mlflow.set_experiment('MLflow Wifi Experimentos')
    registrar = [EXPERIMENTO] if experimento else [PISO] + nomes
    pares = [(n, pos, 'real') for n in registrar]
    if modo_ref == 'prevista':
      pares += [(n, pos_prev, 'prevista') for n in registrar]
    for nome, tabela, ref_nome in pares:
      p = tabela[nome]
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      if nome == EXPERIMENTO:
        den = exp_den
      elif nome == PISO:
        den = None
      else:
        den = json.dumps({a: core_modelos.denominador_de(registro, nome, a)
                          for a in (core_comodo.DN, core_comodo.UP)}, ensure_ascii=False, sort_keys=True)
      params, metricas = metricas_mlflow(nome, features_de[nome], treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p), denominador=den, referencia=ref_nome)
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      sufixo = f'-{exp_den}' if nome == EXPERIMENTO and exp_den else ''
      sufixo += '-refprevista' if ref_nome == 'prevista' else ''
      with mlflow.start_run(run_name=f'{nome}-{treino}{sufixo}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {nome}-{treino}{sufixo}')
    for rotulo, p in pos_rel.items():
      r = core_comodo.nota(p, amostras)
      _, graves = core_comodo.confusao(p)
      rel = '-rel' in rotulo
      feats = [f'{f}_rel' if rel and f in core_comodo.RELATIVAS else f
               for f in registro['versoes'][ativa]['features']]
      params, metricas = metricas_mlflow(rotulo, feats, treino, r,
                                         core_comodo.comparar(p, pos[ativa], amostras)['diferenca'], graves,
                                         core_comodo.por_predio(p),
                                         referencia=('razao_prevista_rel_justo' if rotulo.endswith('-justo') else
                                                     'razao_prevista_rel' if rel else 'razao_prevista_abs'))
      params['datasets'] = ','.join(conjs[core_comodo.DN].datasets)
      with mlflow.start_run(run_name=f'{rotulo}-{treino}'):
        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
      print(f'registrado no MLflow: {rotulo}-{treino}')


if __name__ == '__main__':
  main()
