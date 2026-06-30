import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationSuppressNe(DirectiveOperationItf):
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
    if not columns:
      return df

    # Find rows where any of the specified columns is NOT equal to target value
    to_suppress = pd.Series(False, index=df.index)
    for col in columns:
      if col in df.columns:
        if isinstance(self.target_val, float):
          match_mask = (df[col] != self.target_val)
        else:
          match_mask = (df[col].astype(str) != str(self.target_val))
        to_suppress = to_suppress | match_mask

    # If a mask is active (e.g. from a preceding if-condition),
    # only suppress the matching rows that fall within the mask.
    if mask is not None:
      to_suppress = to_suppress & mask

    return df[~to_suppress]
