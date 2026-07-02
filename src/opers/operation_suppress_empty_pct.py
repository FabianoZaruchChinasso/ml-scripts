import pandas as pd
from typing import List, Optional
from opers.directive_operation_itf import DirectiveOperationItf

class DirectiveOperationSuppressEmptyPct(DirectiveOperationItf):
  def __init__(self):
    self.threshold = 0.0

  def set_values(self, values: List[str]):
    if values:
      try:
        self.threshold = float(values[0])
      except ValueError:
        self.threshold = 0.0

  def do_operation(self, df: pd.DataFrame, columns: List[str], mask: Optional[pd.Series] = None) -> pd.DataFrame:
    if not columns:
      return df

    # Calculate percentage of empty cells in specified columns for each row
    # isna() returns True for NaN, False otherwise.
    # mean(axis=1) calculates the average of booleans (True=1, False=0) per row.
    empty_pct = df[columns].isna().mean(axis=1)
    
    # Identify rows where empty percentage is greater than threshold
    to_suppress = empty_pct > self.threshold
    
    # If a mask is active (e.g. from a preceding if-condition),
    # only suppress the matching rows that fall within the mask.
    if mask is not None:
      to_suppress = to_suppress & mask
      
    return df[~to_suppress]
