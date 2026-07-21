import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationFillLast(DirectiveOperationItf):
  def __init__(self):
    self.fill_value = 0.0

  def set_values(self, values: List[str]):
    if values:
      try:
        self.fill_value = float(values[0])
      except ValueError:
        self.fill_value = values[0]
    else:
      self.fill_value = 0.0

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    for col in columns:
      if col in df.columns:
        filled = df[col].ffill().fillna(self.fill_value)
        if mask is not None:
          nan_mask = df[col].isna() & mask
          df.loc[nan_mask, col] = filled.loc[nan_mask]
        else:
          df[col] = filled
    return df
