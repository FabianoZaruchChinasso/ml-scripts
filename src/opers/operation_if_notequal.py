import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationIfNotequal(DirectiveOperationItf):
  def __init__(self):
    self.target_val = None

  def set_values(self, values: List[str]):
    if values:
      val = values[0].strip().strip('"').strip("'")
      try:
        self.target_val = float(val)
      except ValueError:
        self.target_val = val

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    return df

  def get_mask(self, df: pd.DataFrame, columns: List[str], current_mask: Optional[pd.Series] = None) -> pd.Series:
    if not columns:
      return pd.Series(False, index=df.index)
    
    col = columns[0]
    if col not in df.columns:
      return pd.Series(False, index=df.index)
    
    if isinstance(self.target_val, float):
      new_mask = (df[col] != self.target_val)
    else:
      new_mask = (df[col].astype(str) != str(self.target_val))
      
    if current_mask is not None:
      new_mask = new_mask & current_mask
    return new_mask
