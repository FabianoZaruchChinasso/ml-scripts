import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationIfGreater(DirectiveOperationItf):
  def __init__(self):
    self.threshold = 0.0

  def set_values(self, values: List[str]):
    if values:
      try:
        self.threshold = float(values[0])
      except ValueError:
        self.threshold = 0.0

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    # If operations don't modify the dataframe directly via do_operation
    return df

  def get_mask(self, df: pd.DataFrame, columns: List[str], current_mask: Optional[pd.Series] = None) -> pd.Series:
    if not columns:
      return pd.Series(False, index=df.index)
    
    col = columns[0]
    if col not in df.columns:
      return pd.Series(False, index=df.index)
    
    new_mask = (df[col] > self.threshold)
    if current_mask is not None:
      new_mask = new_mask & current_mask
    return new_mask
