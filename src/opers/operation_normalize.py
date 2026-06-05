import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationNormalize(DirectiveOperationItf):
  def set_values(self, values: List[str]):
    pass

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    for col in columns:
      if col in df.columns:
        if mask is not None:
          max_val = df.loc[mask, col].max()
          if pd.notnull(max_val) and max_val != 0:
            df.loc[mask, col] = df.loc[mask, col] / max_val
        else:
          max_val = df[col].max()
          if pd.notnull(max_val) and max_val != 0:
            df[col] = df[col] / max_val
    return df
