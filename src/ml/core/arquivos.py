import json
import os
import tempfile


def gravar_json_atomico(path: str, dados) -> None:
  """Grava JSON com chaves ordenadas via arquivo temporário + os.replace.

  Quem lê nunca vê um arquivo pela metade, e a ordem estável deixa o git diff limpo.
  """
  texto = json.dumps(dados, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
  pasta = os.path.dirname(os.path.abspath(path))
  fd, temporario = tempfile.mkstemp(dir=pasta, prefix='.tmp-', suffix='.json')
  try:
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
      handle.write(texto)
    os.replace(temporario, path)
  except BaseException:
    if os.path.exists(temporario):
      os.unlink(temporario)
    raise
