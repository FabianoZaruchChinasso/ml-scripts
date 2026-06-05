import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationMultiply(DirectiveOperationItf):
  def __init__(self):
    self.factor = 1.0

  def set_values(self, values: List[str]):
    if values:
      try:
        self.factor = float(values[0])
      except ValueError:
        self.factor = 1.0

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    for col in columns:
      if col in df.columns:
        if mask is not None:
          df.loc[mask, col] = df.loc[mask, col] * self.factor
        else:
          df[col] = df[col] * self.factor
    return df
