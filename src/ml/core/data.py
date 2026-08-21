import pandas as pd

from ml.core.sites import resolve_site_id

SITE_COLUMN = 'site_id'
RAW_SITE_COLUMN = 'local'


def validate_columns(df: pd.DataFrame, columns, role: str) -> None:
  missing = [col for col in columns if col not in df.columns]
  if missing:
    raise ValueError(f'missing {role} columns in dataset: {missing}')


def load_datasets(paths, target: str = None, group_level: str = 'position') -> pd.DataFrame:
  """Load and concatenate CSVs, attaching a canonical site_id column.

  `group_level` selects the grouping granularity: 'position' (default, one group
  per measurement spot) or 'building' (one group per physical building).
  Rows whose target is empty are dropped and the count reported.
  """
  frames = []
  for path in paths:
    try:
      frame = pd.read_csv(path, low_memory=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
      raise ValueError(f'failed to read {path!r}: {e}') from e
    validate_columns(frame, [RAW_SITE_COLUMN], 'site')
    if target is not None:
      validate_columns(frame, [target], 'target')
    frame[SITE_COLUMN] = resolve_site_id(frame[RAW_SITE_COLUMN], level=group_level)
    frames.append(frame)

  df = pd.concat(frames, ignore_index=True)

  if target is not None:
    before = len(df)
    df = df.dropna(subset=[target]).reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
      print(f'dropped {dropped} rows with empty target {target!r}')

  return df
