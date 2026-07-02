import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationFillLast(DirectiveOperationItf):
  def set_values(self, values: List[str]):
    # fill-last does not require any parameters
    pass

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    for col in columns:
      if col in df.columns:
        if mask is not None:
          ffilled = df[col].ffill()
          nan_mask = df[col].isna() & mask
          df.loc[nan_mask, col] = ffilled.loc[nan_mask]
        else:
          df[col] = df[col].ffill()
    return df
